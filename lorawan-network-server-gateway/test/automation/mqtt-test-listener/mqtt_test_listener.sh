#!/bin/sh
set -eu

# Isolated Mosquitto listener for Chapter-IV MQTT authentication/flooding tests.
# This launches a second broker process and never edits/restarts production Mosquitto.
# The flood profile has two isolated listeners:
#   * password-auth publisher/observer listener (loopback by default)
#   * private mTLS read-only listener for the production Node-RED identity

ACTION="${1:-status}"
PROFILE="${2:-auth}"
BIND_ADDR="${3:-127.0.0.1}"
PORT="${4:-}"
CLIENT_CIDR="${5:-}"

case "$PROFILE" in
  auth) DEFAULT_PORT=1884 ;;
  flood) DEFAULT_PORT=1885 ;;
  *) echo "ERROR: profile must be auth or flood" >&2; exit 2 ;;
esac
PORT="${PORT:-$DEFAULT_PORT}"

RUNTIME="/run/lorawan-research-mqtt-${PROFILE}"
UNIT="lorawan-research-mqtt-${PROFILE}"
CONF="$RUNTIME/mosquitto.conf"
PASSWD="$RUNTIME/passwd"
ACL="$RUNTIME/acl"
MTLS_ACL="$RUNTIME/mtls-read.acl"
CREDS="$RUNTIME/credentials.env"
LOG="$RUNTIME/mosquitto.log"
FIREWALL_STATE="$RUNTIME/ufw-rule.txt"

MQTT_CA="${MQTT_CA:-/etc/lorawan-pki/mqtt/ca.crt}"
MQTT_SERVER_CERT="${MQTT_SERVER_CERT:-/etc/lorawan-pki/mqtt/server.crt}"
MQTT_SERVER_KEY="${MQTT_SERVER_KEY:-/etc/lorawan-pki/mqtt/server.key}"
FLOOD_MTLS_PORT="${FLOOD_MTLS_PORT:-1887}"
FLOOD_MTLS_BIND="${FLOOD_MTLS_BIND:-}"

need_root() {
  [ "$(id -u)" -eq 0 ] || { echo "ERROR: run with sudo/root" >&2; exit 2; }
}

private_bind_auto() {
  ip -4 -o addr show dev eth1 2>/dev/null | awk 'NR==1 {split($4,a,"/"); print a[1]}'
}

validate_port() {
  P="$1"
  case "$P" in ''|*[!0-9]*) echo "ERROR: invalid port: $P" >&2; exit 2;; esac
  [ "$P" -ge 1 ] && [ "$P" -le 65535 ] || { echo "ERROR: port out of range: $P" >&2; exit 2; }
}

validate_inputs() {
  validate_port "$PORT"
  if [ "$BIND_ADDR" != "127.0.0.1" ] && [ "$BIND_ADDR" != "::1" ] && [ -z "$CLIENT_CIDR" ]; then
    echo "ERROR: non-loopback password listener requires an explicit client CIDR" >&2
    exit 2
  fi
  if [ "$PROFILE" = "flood" ]; then
    validate_port "$FLOOD_MTLS_PORT"
    [ "$PORT" != "$FLOOD_MTLS_PORT" ] || { echo "ERROR: flood password and mTLS ports must differ" >&2; exit 2; }
    if [ -z "$FLOOD_MTLS_BIND" ]; then
      FLOOD_MTLS_BIND="$(private_bind_auto)"
    fi
    [ -n "$FLOOD_MTLS_BIND" ] || { echo "ERROR: could not discover private eth1 IPv4 for mTLS listener" >&2; exit 2; }
    case "$FLOOD_MTLS_BIND" in
      127.*|0.0.0.0|::|::1) echo "ERROR: flood mTLS listener must bind the private VPC address" >&2; exit 2 ;;
    esac
    for F in "$MQTT_CA" "$MQTT_SERVER_CERT" "$MQTT_SERVER_KEY"; do
      [ -r "$F" ] || { echo "ERROR: required MQTT TLS file is not readable: $F" >&2; exit 2; }
    done
  fi
}

load_runtime_password_endpoint() {
  [ -r "$CONF" ] || { echo "ERROR: active listener config is missing: $CONF" >&2; exit 2; }
  LINE="$(sed -n 's/^listener \([0-9][0-9]*\) \([^ ][^ ]*\)$/\1|\2/p' "$CONF" | head -n1)"
  [ -n "$LINE" ] || { echo "ERROR: could not discover active password listener endpoint" >&2; exit 2; }
  PORT="${LINE%%|*}"
  BIND_ADDR="${LINE#*|}"
  validate_port "$PORT"
  [ -n "$BIND_ADDR" ] || { echo "ERROR: active password listener bind is empty" >&2; exit 2; }
}

random_secret() {
  openssl rand -hex 24
}

write_auth_profile() {
  A="$(random_secret)"; L="$(random_secret)"; O="$(random_secret)"
  mosquitto_passwd -b -c "$PASSWD" auth_allowed "$A"
  mosquitto_passwd -b "$PASSWD" auth_limited "$L"
  mosquitto_passwd -b "$PASSWD" auth_observer "$O"
  cat >"$ACL" <<'EOF'
user auth_allowed
topic write test/auth/allowed

user auth_limited
topic write test/auth/limited

user auth_observer
topic read test/auth/allowed
EOF
  umask 077
  {
    printf 'AUTH_ALLOWED_PASSWORD=%s\n' "$A"
    printf 'AUTH_LIMITED_PASSWORD=%s\n' "$L"
    printf 'AUTH_OBSERVER_PASSWORD=%s\n' "$O"
  } >"$CREDS"
}

write_flood_profile() {
  # This password is deliberately non-secret: the flood password listener is
  # loopback-only and reachable from the test laptop solely through a
  # permitopen-restricted SSH tunnel. Never reuse it on production listeners.
  P="lorawan-research-flood-only"; O="$(random_secret)"
  mosquitto_passwd -b -c "$PASSWD" flood_publisher "$P"
  mosquitto_passwd -b "$PASSWD" flood_observer "$O"
  cat >"$ACL" <<'EOF'
user flood_publisher
topic write test/flood/invalid

user flood_observer
topic read test/flood/invalid
EOF
  cat >"$MTLS_ACL" <<'EOF'
user node-red-ingest
topic read test/flood/invalid

user node-red-ingest-standby
topic read test/flood/invalid
EOF
  umask 077
  {
    printf 'FLOOD_PUBLISHER_PASSWORD=%s\n' "$P"
    printf 'FLOOD_OBSERVER_PASSWORD=%s\n' "$O"
    printf 'FLOOD_MTLS_BIND=%s\n' "$FLOOD_MTLS_BIND"
    printf 'FLOOD_MTLS_PORT=%s\n' "$FLOOD_MTLS_PORT"
  } >"$CREDS"
}

write_config() {
  cat >"$CONF" <<EOF
per_listener_settings true
listener $PORT $BIND_ADDR
protocol mqtt
allow_anonymous false
password_file $PASSWD
acl_file $ACL
EOF
  if [ "$PROFILE" = "flood" ]; then
    cat >>"$CONF" <<EOF

listener $FLOOD_MTLS_PORT $FLOOD_MTLS_BIND
protocol mqtt
cafile $MQTT_CA
certfile $MQTT_SERVER_CERT
keyfile $MQTT_SERVER_KEY
tls_version tlsv1.3
require_certificate true
use_identity_as_username true
allow_anonymous false
acl_file $MTLS_ACL
EOF
  fi
  cat >>"$CONF" <<EOF

persistence false
connection_messages true
log_dest file $LOG
log_type error
log_type warning
log_type notice
log_type information
EOF
}

add_firewall_rule() {
  [ "$BIND_ADDR" = "127.0.0.1" ] && return 0
  [ "$BIND_ADDR" = "::1" ] && return 0
  command -v ufw >/dev/null 2>&1 || { echo "ERROR: ufw required for non-loopback password listener" >&2; exit 2; }
  ufw allow proto tcp from "$CLIENT_CIDR" to "$BIND_ADDR" port "$PORT" comment "$UNIT" >/dev/null
  printf '%s|%s|%s\n' "$CLIENT_CIDR" "$BIND_ADDR" "$PORT" >"$FIREWALL_STATE"
}

remove_firewall_rule() {
  [ -r "$FIREWALL_STATE" ] || return 0
  IFS='|' read -r SRC DST P <"$FIREWALL_STATE"
  ufw --force delete allow proto tcp from "$SRC" to "$DST" port "$P" >/dev/null 2>&1 || true
  rm -f "$FIREWALL_STATE"
}

start_listener() {
  need_root; validate_inputs
  command -v mosquitto >/dev/null 2>&1 || { echo "ERROR: mosquitto missing" >&2; exit 2; }
  command -v mosquitto_passwd >/dev/null 2>&1 || { echo "ERROR: mosquitto_passwd missing" >&2; exit 2; }
  command -v systemd-run >/dev/null 2>&1 || { echo "ERROR: systemd-run missing" >&2; exit 2; }
  if systemctl is-active --quiet "$UNIT.service" 2>/dev/null; then
    echo "ERROR: $UNIT already active" >&2
    exit 2
  fi
  rm -rf "$RUNTIME"
  install -d -m 0750 -o mosquitto -g mosquitto "$RUNTIME"
  : >"$LOG"; chown mosquitto:mosquitto "$LOG"; chmod 0640 "$LOG"
  case "$PROFILE" in auth) write_auth_profile;; flood) write_flood_profile;; esac
  write_config
  chown mosquitto:mosquitto "$PASSWD" "$ACL" "$CONF" "$CREDS" 2>/dev/null || true
  chmod 0640 "$PASSWD" "$ACL" "$CONF"
  chmod 0600 "$CREDS"
  if [ "$PROFILE" = "flood" ]; then
    chown mosquitto:mosquitto "$MTLS_ACL"
    chmod 0640 "$MTLS_ACL"
  fi
  add_firewall_rule
  if ! systemd-run --unit="$UNIT" --collect --property=User=mosquitto --property=Group=mosquitto \
      /usr/sbin/mosquitto -c "$CONF" >/dev/null; then
    remove_firewall_rule
    echo "ERROR: failed to launch isolated broker" >&2
    exit 1
  fi
  sleep 1
  if ! systemctl is-active --quiet "$UNIT.service"; then
    journalctl -u "$UNIT.service" --no-pager -n 30 >&2 || true
    remove_firewall_rule
    exit 1
  fi
  printf 'profile=%s\npassword_bind=%s\npassword_port=%s\nunit=%s\ncredentials=%s\n' \
    "$PROFILE" "$BIND_ADDR" "$PORT" "$UNIT.service" "$CREDS"
  if [ "$PROFILE" = "flood" ]; then
    printf 'mtls_bind=%s\nmtls_port=%s\n' "$FLOOD_MTLS_BIND" "$FLOOD_MTLS_PORT"
  fi
}

status_listener() {
  need_root
  if systemctl is-active --quiet "$UNIT.service" 2>/dev/null; then
    echo "listener=ACTIVE"
  else
    echo "listener=INACTIVE"
  fi
  if [ -r "$CONF" ]; then
    printf 'profile=%s\n' "$PROFILE"
    sed -n -e 's/^listener /listener=/p' -e 's/^allow_anonymous /allow_anonymous=/p' "$CONF"
    printf 'credentials=%s\n' "$CREDS"
  fi
}

smoke_auth() {
  need_root
  load_runtime_password_endpoint
  . "$CREDS"
  MARKER="auth-smoke-$(date +%s)"
  OUT="$RUNTIME/smoke.out"
  : >"$OUT"
  mosquitto_sub -h "$BIND_ADDR" -p "$PORT" -u auth_observer -P "$AUTH_OBSERVER_PASSWORD" \
    -t test/auth/allowed -C 1 -W 5 >"$OUT" 2>"$RUNTIME/sub.stderr" & SUB=$!
  sleep 1
  mosquitto_pub -h "$BIND_ADDR" -p "$PORT" -u auth_allowed -P "$AUTH_ALLOWED_PASSWORD" \
    -t test/auth/allowed -m "$MARKER" -q 1
  wait "$SUB"
  grep -Fxq "$MARKER" "$OUT" || { echo "ERROR: allowed marker not observed" >&2; exit 1; }
  if mosquitto_pub -h "$BIND_ADDR" -p "$PORT" -u auth_allowed -P "definitely-wrong-${MARKER}" \
      -t test/auth/allowed -m must-not-arrive -q 1 >/dev/null 2>&1; then
    echo "ERROR: wrong password unexpectedly accepted" >&2; exit 1
  fi
  : >"$OUT"
  mosquitto_sub -h "$BIND_ADDR" -p "$PORT" -u auth_observer -P "$AUTH_OBSERVER_PASSWORD" \
    -t test/auth/allowed -W 2 >"$OUT" 2>/dev/null & SUB=$!
  sleep 1
  mosquitto_pub -h "$BIND_ADDR" -p "$PORT" -u auth_limited -P "$AUTH_LIMITED_PASSWORD" \
    -t test/auth/allowed -m prohibited-marker -q 1 >/dev/null 2>&1 || true
  wait "$SUB" 2>/dev/null || true
  [ ! -s "$OUT" ] || { echo "ERROR: prohibited marker reached observer" >&2; exit 1; }
  echo "AUTH_SMOKE=PASS"
}


run_auth_trials() {
  need_root
  [ "$PROFILE" = "auth" ] || { echo "ERROR: auth trials require auth profile" >&2; exit 2; }
  systemctl is-active --quiet "$UNIT.service" || { echo "ERROR: listener is not active" >&2; exit 2; }
  load_runtime_password_endpoint
  . "$CREDS"
  TRIAL_DIR="$RUNTIME/trials"
  rm -rf "$TRIAL_DIR"
  install -d -m 0700 "$TRIAL_DIR"

  trial=1
  while [ "$trial" -le 10 ]; do
    marker="a1-mqtt-allowed-$(date +%s)-$trial"
    out="$TRIAL_DIR/allowed-$trial.out"
    : >"$out"
    mosquitto_sub -h "$BIND_ADDR" -p "$PORT" -u auth_observer -P "$AUTH_OBSERVER_PASSWORD"       -t test/auth/allowed -C 1 -W 3 >"$out" 2>/dev/null & sub=$!
    sleep 0.1
    start_ms=$(date +%s%3N)
    pub_rc=0
    mosquitto_pub -h "$BIND_ADDR" -p "$PORT" -u auth_allowed -P "$AUTH_ALLOWED_PASSWORD"       -t test/auth/allowed -m "$marker" -q 1 >/dev/null 2>&1 || pub_rc=$?
    end_ms=$(date +%s%3N)
    wait "$sub" 2>/dev/null || true
    actual=REJECT; delivered=0
    if grep -Fxq "$marker" "$out"; then delivered=1; fi
    [ "$pub_rc" -eq 0 ] && [ "$delivered" -eq 1 ] && actual=ALLOW
    printf 'AUTH_TRIAL|MQTT_ALLOWED|%d|ALLOW|%s|%d|%d\n' "$trial" "$actual" "$((end_ms-start_ms))" "$delivered"
    trial=$((trial+1))
  done

  trial=1
  while [ "$trial" -le 10 ]; do
    marker="a1-mqtt-wrong-$(date +%s)-$trial"
    out="$TRIAL_DIR/wrong-$trial.out"
    : >"$out"
    mosquitto_sub -h "$BIND_ADDR" -p "$PORT" -u auth_observer -P "$AUTH_OBSERVER_PASSWORD" \
      -t test/auth/allowed -W 1 >"$out" 2>/dev/null & sub=$!
    sleep 0.1
    start_ms=$(date +%s%3N)
    pub_rc=0
    mosquitto_pub -h "$BIND_ADDR" -p "$PORT" -u auth_allowed -P "intentionally-wrong-$marker" \
      -t test/auth/allowed -m "$marker" -q 1 >/dev/null 2>&1 || pub_rc=$?
    end_ms=$(date +%s%3N)
    wait "$sub" 2>/dev/null || true
    actual=REJECT; delivered=0
    if grep -Fxq "$marker" "$out"; then delivered=1; fi
    if [ "$pub_rc" -eq 0 ] || [ "$delivered" -eq 1 ]; then actual=ALLOW; fi
    printf 'AUTH_TRIAL|MQTT_WRONG_PASSWORD|%d|REJECT|%s|%d|%d\n' "$trial" "$actual" "$((end_ms-start_ms))" "$delivered"
    trial=$((trial+1))
  done

  trial=1
  while [ "$trial" -le 10 ]; do
    marker="a1-mqtt-prohibited-$(date +%s)-$trial"
    out="$TRIAL_DIR/prohibited-$trial.out"
    : >"$out"
    mosquitto_sub -h "$BIND_ADDR" -p "$PORT" -u auth_observer -P "$AUTH_OBSERVER_PASSWORD"       -t test/auth/allowed -W 1 >"$out" 2>/dev/null & sub=$!
    sleep 0.1
    start_ms=$(date +%s%3N)
    mosquitto_pub -h "$BIND_ADDR" -p "$PORT" -u auth_limited -P "$AUTH_LIMITED_PASSWORD"       -t test/auth/allowed -m "$marker" -q 1 >/dev/null 2>&1 || true
    end_ms=$(date +%s%3N)
    wait "$sub" 2>/dev/null || true
    actual=REJECT; delivered=0
    if grep -Fxq "$marker" "$out"; then actual=ALLOW; delivered=1; fi
    printf 'AUTH_TRIAL|MQTT_PROHIBITED_TOPIC|%d|REJECT|%s|%d|%d\n' "$trial" "$actual" "$((end_ms-start_ms))" "$delivered"
    trial=$((trial+1))
  done
}

smoke_flood() {
  need_root
  load_runtime_password_endpoint
  . "$CREDS"
  MARKER="flood-smoke-$(date +%s)"
  OUT="$RUNTIME/smoke.out"
  mosquitto_sub -h "$BIND_ADDR" -p "$PORT" -u flood_observer -P "$FLOOD_OBSERVER_PASSWORD" \
    -t test/flood/invalid -C 1 -W 5 >"$OUT" 2>"$RUNTIME/sub.stderr" & SUB=$!
  sleep 1
  mosquitto_pub -h "$BIND_ADDR" -p "$PORT" -u flood_publisher -P "$FLOOD_PUBLISHER_PASSWORD" \
    -t test/flood/invalid -m "$MARKER" -q 1
  wait "$SUB"
  grep -Fxq "$MARKER" "$OUT" || { echo "ERROR: flood marker not observed" >&2; exit 1; }
  echo "FLOOD_PASSWORD_SMOKE=PASS"
  echo "FLOOD_MTLS_ENDPOINT=${FLOOD_MTLS_BIND}:${FLOOD_MTLS_PORT}"
}

stop_listener() {
  need_root
  systemctl stop "$UNIT.service" >/dev/null 2>&1 || true
  if systemctl is-active --quiet "$UNIT.service" 2>/dev/null; then
    echo "ERROR: $UNIT.service remained active; refusing fixture cleanup" >&2
    exit 1
  fi
  remove_firewall_rule
  # The listener is an ephemeral research fixture. Do not leave generated
  # passwords, ACLs, TLS test config, or logs under /run after teardown.
  rm -rf "$RUNTIME"
  echo "listener=INACTIVE"
}

case "$ACTION" in
  start) start_listener ;;
  status) status_listener ;;
  smoke)
    need_root
    systemctl is-active --quiet "$UNIT.service" || { echo "ERROR: listener is not active" >&2; exit 2; }
    case "$PROFILE" in auth) smoke_auth;; flood) smoke_flood;; esac
    ;;
  run)
    [ "$PROFILE" = "auth" ] || { echo "ERROR: run action is available only for auth profile" >&2; exit 2; }
    run_auth_trials
    ;;
  credentials)
    need_root
    [ -r "$CREDS" ] || { echo "ERROR: credentials not prepared" >&2; exit 2; }
    cat "$CREDS"
    ;;
  stop) stop_listener ;;
  *) echo "usage: $0 {start|status|smoke|run|credentials|stop} {auth|flood} [password-bind] [password-port] [client-cidr]" >&2; exit 2 ;;
esac
