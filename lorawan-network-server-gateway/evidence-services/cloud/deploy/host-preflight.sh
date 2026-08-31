#!/usr/bin/env bash
# Read-only evidence-service host preflight.
# Run from an authorized session on ulc-01, ulc-02, or ulc-03:
#   sudo bash host-preflight.sh
# No files, services, images, or ports are changed/reserved.
set -u

failures=0
warnings=0
pass() { printf 'PASS|%s\n' "$1"; }
warn() { printf 'WARN|%s\n' "$1"; warnings=$((warnings + 1)); }
fail() { printf 'FAIL|%s\n' "$1" >&2; failures=$((failures + 1)); }
section() { printf '\n=== %s ===\n' "$1"; }

if [ "$(id -u)" -ne 0 ]; then
  printf 'FAIL|run with sudo/root so protected service metadata can be inspected without weakening permissions\n' >&2
  exit 1
fi

HOST=$(hostname -s 2>/dev/null || hostname)
case "$HOST" in
  ulc-01) EXPECTED_IP=10.104.0.2; EXPECTED_PROFILES=ingest,collector,fabric-adapter; NEED_MQTT=1; NEED_INGEST=1; NEED_COLLECTOR=1; NEED_VERIFIER=0; NEED_ADAPTER=1 ;;
  ulc-02) EXPECTED_IP=10.104.0.4; EXPECTED_PROFILES=ingest,verifier,fabric-adapter; NEED_MQTT=1; NEED_INGEST=1; NEED_COLLECTOR=0; NEED_VERIFIER=1; NEED_ADAPTER=1 ;;
  ulc-03) EXPECTED_IP=10.104.0.8; EXPECTED_PROFILES=collector,verifier; NEED_MQTT=0; NEED_INGEST=0; NEED_COLLECTOR=1; NEED_VERIFIER=1; NEED_ADAPTER=0 ;;
  *) printf 'FAIL|unexpected hostname=%s\n' "$HOST" >&2; exit 1 ;;
esac

has_listener() {
  port=$1
  ss -H -ltn 2>/dev/null | awk -v suffix=":$port" '$4 ~ suffix"$" {found=1} END {exit(found ? 0 : 1)}'
}

first_free_port() {
  port=$1; end=$2
  while [ "$port" -le "$end" ]; do
    if ! has_listener "$port"; then printf '%s\n' "$port"; return 0; fi
    port=$((port + 1))
  done
  return 1
}

service_state() {
  unit=$1
  active=$(systemctl is-active "$unit" 2>/dev/null || true)
  enabled=$(systemctl is-enabled "$unit" 2>/dev/null || true)
  printf '%s|active=%s|enabled=%s\n' "$unit" "${active:-unknown}" "${enabled:-unknown}"
}

section 'HOST IDENTITY + CAPACITY'
printf 'HOST=%s\nEXPECTED_PRIVATE_IP=%s\nEXPECTED_PROFILES=%s\n' "$HOST" "$EXPECTED_IP" "$EXPECTED_PROFILES"
if ip -o addr show 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | grep -Fxq "$EXPECTED_IP"; then pass "private_ip=$EXPECTED_IP"; else fail "expected private IP $EXPECTED_IP is not configured"; fi
if [ -r /etc/os-release ]; then . /etc/os-release; printf 'OS=%s\n' "${PRETTY_NAME:-unknown}"; fi
printf 'KERNEL=%s\nARCH=%s\nCPU_COUNT=%s\n' "$(uname -r)" "$(uname -m)" "$(nproc 2>/dev/null || echo unknown)"
free -m 2>/dev/null || true
printf '%s\n' '-- swap --'; swapon --show 2>/dev/null || true
printf '%s\n' '-- root disk --'; df -h / 2>/dev/null || true
printf '%s\n' '-- load --'; uptime 2>/dev/null || true
mem_available=$(awk '/MemAvailable:/ {print int($2/1024)}' /proc/meminfo 2>/dev/null || true)
if [ -n "${mem_available:-}" ]; then
  printf 'MEM_AVAILABLE_MIB=%s\n' "$mem_available"
  if [ "$NEED_ADAPTER" -eq 1 ]; then
    if [ "$mem_available" -ge 832 ]; then pass 'memory_headroom_for_three_192MiB_evidence_containers_plus_margin'; elif [ "$mem_available" -ge 576 ]; then warn 'memory covers three configured evidence limits but margin is thin'; else fail 'available memory is below combined 576 MiB evidence-container limits'; fi
  else
    if [ "$mem_available" -ge 640 ]; then pass 'memory_headroom_for_two_192MiB_evidence_containers_plus_margin'; elif [ "$mem_available" -ge 384 ]; then warn 'memory covers configured evidence limits but margin is thin'; else fail 'available memory is below combined 384 MiB evidence-container limits'; fi
  fi
fi

section 'NUMERIC RUNTIME ID SAFETY'
if getent passwd 65532 >/dev/null 2>&1; then fail 'host UID 65532 already assigned'; else pass 'host_uid_65532_unassigned'; fi
if getent group 65532 >/dev/null 2>&1; then fail 'host GID 65532 already assigned; root:65532 key mounts need review'; else pass 'host_gid_65532_unassigned'; fi

section 'DOCKER + BUILDX'
if command -v docker >/dev/null 2>&1; then
  docker version --format 'DOCKER|client={{.Client.Version}}|server={{.Server.Version}}' 2>/dev/null || fail 'docker daemon/version query failed'
  docker compose version 2>/dev/null || fail 'docker compose v2 unavailable'
  if docker buildx version >/dev/null 2>&1; then printf 'BUILDX=%s\n' "$(docker buildx version 2>/dev/null | head -n1)"; pass 'docker_buildx_available'; else warn 'docker Buildx unavailable on this host'; fi
  printf '%s\n' '-- running containers --'; docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}' 2>/dev/null || true
  printf '%s\n' '-- container resource snapshot --'; docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}' 2>/dev/null || true
else
  fail 'docker command missing'
fi

section 'CORE SERVICE STATE'
service_state haproxy; service_state pgbouncer; service_state mosquitto
printf '%s\n' '-- failed systemd units --'; systemctl --failed --no-legend 2>/dev/null || true
if systemctl is-active --quiet haproxy && haproxy -c -f /etc/haproxy/haproxy.cfg >/dev/null 2>&1; then pass 'haproxy_active_config_valid'; else fail 'HAProxy inactive or config invalid'; fi
if systemctl is-active --quiet pgbouncer; then pass 'pgbouncer_active'; else fail 'pgbouncer is not active'; fi
if has_listener 6432; then pass 'tcp_6432_listening'; else fail 'PgBouncer tcp/6432 not listening'; fi
if [ -f /etc/pgbouncer/userlist.txt ]; then printf 'PGBOUNCER_USERLIST_META=%s|entries=%s\n' "$(stat -c '%u:%g:%a' /etc/pgbouncer/userlist.txt 2>/dev/null || true)" "$(wc -l < /etc/pgbouncer/userlist.txt 2>/dev/null || true)"; else fail 'PgBouncer userlist missing'; fi

section 'PATRONI + ETCD HEALTH'
for endpoint in 10.104.0.2 10.104.0.4 10.104.0.8; do
  leader=$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 2 "http://$endpoint:8008/leader" 2>/dev/null || echo 000)
  replica=$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 2 "http://$endpoint:8008/replica" 2>/dev/null || echo 000)
  printf 'PATRONI|%s|leader=%s|replica=%s\n' "$endpoint" "$leader" "$replica"
done
if command -v etcdctl >/dev/null 2>&1; then ETCDCTL_API=3 etcdctl --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 endpoint health 2>&1 || warn 'etcd endpoint-health did not pass locally'; else warn 'etcdctl unavailable locally'; fi

section 'MQTT GATEWAY LISTENER'
if [ "$NEED_MQTT" -eq 1 ]; then
  if systemctl is-active --quiet mosquitto; then pass 'mosquitto_active'; else fail 'Mosquitto expected but inactive'; fi
  if has_listener 8884; then pass 'gateway_mqtt_tcp_8884_listening'; else fail 'gateway MQTT tcp/8884 not listening'; fi
  if [ -f /etc/mosquitto/conf.d/tls.conf ]; then
    printf '%s\n' '-- non-secret :8884 policy directives --'
    grep -E '^[[:space:]]*(listener[[:space:]]+8884|require_certificate|use_identity_as_username|allow_anonymous|acl_file|tls_version)[[:space:]]' /etc/mosquitto/conf.d/tls.conf 2>/dev/null || true
    grep -Eq '^[[:space:]]*require_certificate[[:space:]]+true([[:space:]]|$)' /etc/mosquitto/conf.d/tls.conf && pass 'mqtt_client_certificate_required' || fail 'require_certificate true not observed'
    grep -Eq '^[[:space:]]*use_identity_as_username[[:space:]]+true([[:space:]]|$)' /etc/mosquitto/conf.d/tls.conf && pass 'mqtt_certificate_identity_maps_to_username' || fail 'use_identity_as_username true not observed'
    grep -Eq '^[[:space:]]*allow_anonymous[[:space:]]+false([[:space:]]|$)' /etc/mosquitto/conf.d/tls.conf && pass 'mqtt_anonymous_denied' || fail 'allow_anonymous false not observed'
  else fail 'Mosquitto TLS config missing'; fi
  if [ -f /etc/mosquitto/gateway.acl ]; then printf 'GATEWAY_ACL_META=%s\n' "$(stat -c '%u:%g:%a|%s bytes' /etc/mosquitto/gateway.acl 2>/dev/null || true)"; else fail 'gateway ACL file missing'; fi
else
  printf 'MQTT_LOCAL_BROKER=not_expected_on_%s\n' "$HOST"
fi

section 'CURRENT LISTENERS RELEVANT TO EVIDENCE'
ss -H -ltnp 2>/dev/null | awk '$4 ~ /:(443|6432|8008|8080|8200|8201|8883|8884|8885|8886|15432|15433|16379|18080|18200|18883|18884)$/ {print}' || true

section 'DYNAMIC PORT SUGGESTIONS - NOT RESERVED'
if [ "$NEED_INGEST" -eq 1 ]; then ingest_port=$(first_free_port 18100 18149 || true); [ -n "${ingest_port:-}" ] && printf 'SUGGESTED_EVIDENCE_INGEST_HOST_PORT=%s\n' "$ingest_port" || fail 'no free ingest candidate in 18100-18149'; fi
health_cursor=19100
if [ "$NEED_COLLECTOR" -eq 1 ]; then collector_port=$(first_free_port "$health_cursor" 19149 || true); if [ -n "${collector_port:-}" ]; then printf 'SUGGESTED_EVIDENCE_COLLECTOR_HEALTH_PORT=%s\n' "$collector_port"; health_cursor=$((collector_port + 1)); else fail 'no free collector health candidate in 19100-19149'; fi; fi
if [ "$NEED_VERIFIER" -eq 1 ]; then verifier_port=$(first_free_port "$health_cursor" 19149 || true); if [ -n "${verifier_port:-}" ]; then printf 'SUGGESTED_EVIDENCE_VERIFIER_HEALTH_PORT=%s\n' "$verifier_port"; health_cursor=$((verifier_port + 1)); else fail 'no free verifier health candidate in 19100-19149'; fi; fi
if [ "$NEED_ADAPTER" -eq 1 ]; then adapter_port=$(first_free_port "$health_cursor" 19149 || true); [ -n "${adapter_port:-}" ] && printf 'SUGGESTED_EVIDENCE_ADAPTER_HEALTH_PORT=%s\n' "$adapter_port" || fail 'no free Fabric adapter health candidate in 19100-19149'; fi

section 'SHARED 443 OBSERVATION'
if [ "$HOST" = ulc-01 ] || [ "$HOST" = ulc-02 ]; then
  if [ "$HOST" = ulc-01 ]; then anchor_ip=10.15.0.5; else anchor_ip=10.15.0.7; fi
  if ss -H -ltn 2>/dev/null | awk -v target="$anchor_ip:443" '$4 == target {found=1} END {exit(found ? 0 : 1)}'; then printf 'ANCHOR_443=%s:443|LISTENING\n' "$anchor_ip"; pass 'existing shared-443 listener observed; evidence needs reviewed SNI/TCP dispatch'; else warn "expected anchor $anchor_ip:443 not observed"; fi
fi

section 'RESULT'
printf 'EVIDENCE_HOST_PREFLIGHT|host=%s|failures=%s|warnings=%s\n' "$HOST" "$failures" "$warnings"
if [ "$failures" -ne 0 ]; then printf 'EVIDENCE_HOST_PREFLIGHT=FAIL\n'; exit 1; fi
printf 'EVIDENCE_HOST_PREFLIGHT=PASS\nNo image pulled. No container started. No service/file/configuration changed.\n'
