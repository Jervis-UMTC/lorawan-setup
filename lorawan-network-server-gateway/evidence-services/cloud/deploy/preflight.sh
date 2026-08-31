#!/usr/bin/env bash
# Read-only deployment preflight. It never pulls images, starts containers,
# changes permissions, creates credentials, or modifies live configuration.
set -u

fail() {
  printf 'PREFLIGHT_FAIL|%s\n' "$1" >&2
  exit 1
}

pass() {
  printf 'PREFLIGHT_PASS|%s\n' "$1"
}

[ "$#" -eq 2 ] || fail 'usage: preflight.sh /path/release.env /path/host.env'
RELEASE_ENV=$1
HOST_ENV=$2
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/compose.yml"
MTLS_OVERRIDE="$SCRIPT_DIR/compose.collector-mtls.yml"

[ "$(id -u)" -eq 0 ] || fail 'run as root so ownership/mode checks are authoritative'
command -v docker >/dev/null 2>&1 || fail 'docker is required'
docker compose version >/dev/null 2>&1 || fail 'docker compose v2 is required'
command -v ss >/dev/null 2>&1 || fail 'ss is required'
command -v ip >/dev/null 2>&1 || fail 'ip is required'
command -v stat >/dev/null 2>&1 || fail 'stat is required'

check_source_file() {
  file=$1
  [ -f "$file" ] || fail "missing env file: $file"
  uid=$(stat -c '%u' "$file") || fail "cannot stat $file"
  mode=$(stat -c '%a' "$file") || fail "cannot stat $file"
  [ "$uid" = 0 ] || fail "$file must be root-owned"
  perm=$((8#$mode))
  (( (perm & 022) == 0 )) || fail "$file must not be group/world writable"
}

check_source_file "$RELEASE_ENV"
check_source_file "$HOST_ENV"

# release.env and host.env are non-secret root-owned deployment inputs. Source
# them only after ownership/writability has been checked.
set -a
# shellcheck disable=SC1090
. "$RELEASE_ENV" || fail 'could not parse release.env'
# shellcheck disable=SC1090
. "$HOST_ENV" || fail 'could not parse host.env'
set +a

require_var() {
  name=$1
  eval "value=\${$name-}"
  [ -n "$value" ] || fail "$name is required"
  case "$value" in
    *'<'*|*'>'*) fail "$name still contains an example placeholder" ;;
  esac
}

require_image() {
  name=$1
  require_var "$name"
  eval "value=\${$name}"
  printf '%s' "$value" | grep -Eq '^.+@sha256:[0-9a-f]{64}$' || fail "$name must be one immutable image@sha256:<64hex> reference"
}

require_port_free() {
  name=$1
  require_var "$name"
  eval "port=\${$name}"
  printf '%s' "$port" | grep -Eq '^[0-9]+$' || fail "$name must be numeric"
  [ "$port" -ge 1024 ] && [ "$port" -le 65535 ] || fail "$name must be 1024..65535"
  if ss -H -ltn | awk -v suffix=":$port" '$4 ~ suffix"$" { found=1 } END { exit(found ? 0 : 1) }'; then
    fail "$name=$port is already listening"
  fi
  pass "$name=$port free"
}

check_regular_public_file() {
  file=$1
  label=$2
  [ -f "$file" ] || fail "$label missing: $file"
  uid=$(stat -c '%u' "$file") || fail "cannot stat $label"
  mode=$(stat -c '%a' "$file") || fail "cannot stat $label"
  [ "$uid" = 0 ] || fail "$label must be root-owned"
  perm=$((8#$mode))
  (( (perm & 022) == 0 )) || fail "$label must not be group/world writable"
}

check_runtime_public_file() {
  file=$1
  label=$2
  check_regular_public_file "$file" "$label"
  gid=$(stat -c '%g' "$file") || fail "cannot stat $label group"
  mode=$(stat -c '%a' "$file") || fail "cannot stat $label mode"
  perm=$((8#$mode))
  runtime_readable=0
  if [ "$gid" = '65532' ] && (( (perm & 040) != 0 )); then runtime_readable=1; fi
  if (( (perm & 004) != 0 )); then runtime_readable=1; fi
  [ "$runtime_readable" -eq 1 ] || fail "$label must be readable by runtime 65532:65532 (group 65532 read or world read)"
}

check_no_template_tokens() {
  file=$1
  label=$2
  if grep -Eq '<[A-Z0-9_]+>' "$file"; then
    fail "$label still contains example placeholder tokens"
  fi
}

check_secret_env() {
  file=$1
  label=$2
  [ -f "$file" ] || fail "$label missing: $file"
  meta=$(stat -c '%u:%g:%a' "$file") || fail "cannot stat $label"
  [ "$meta" = '0:0:600' ] || fail "$label must be root:root mode 0600"
  check_no_template_tokens "$file" "$label"
}

check_runtime_key() {
  file=$1
  label=$2
  [ -f "$file" ] || fail "$label missing: $file"
  meta=$(stat -c '%u:%g:%a' "$file") || fail "cannot stat $label"
  [ "$meta" = '0:65532:440' ] || fail "$label must be root:GID-65532 mode 0440 so only root/container runtime group can read it"
}

env_has_nonempty() {
  file=$1
  key=$2
  grep -Eq "^${key}=.+$" "$file"
}

env_has_exact() {
  file=$1
  pair=$2
  grep -Fqx "$pair" "$file"
}

validate_role_env_common() {
  file=$1
  label=$2
  check_secret_env "$file" "$label"
  env_has_nonempty "$file" EVIDENCE_DATABASE_DSN || fail "$label lacks EVIDENCE_DATABASE_DSN"
  env_has_nonempty "$file" EVIDENCE_S3_ACCESS_KEY_ID || fail "$label lacks EVIDENCE_S3_ACCESS_KEY_ID"
  env_has_nonempty "$file" EVIDENCE_S3_SECRET_ACCESS_KEY || fail "$label lacks EVIDENCE_S3_SECRET_ACCESS_KEY"
  grep -Fq 'pgbouncer.internal.lorawan.com:6432/lorawan_telemetry' "$file" || fail "$label DSN must use commissioned logical PgBouncer endpoint"
  grep -Fq 'sslmode=verify-full' "$file" || fail "$label DSN must use sslmode=verify-full"
  grep -Fq 'sslrootcert=/run/evidence/postgres/ca.crt' "$file" || fail "$label DSN must use mounted PostgreSQL CA"
}

require_image EVIDENCE_INGEST_IMAGE
require_image EVIDENCE_COLLECTOR_IMAGE
require_image EVIDENCE_VERIFIER_IMAGE
require_image EVIDENCE_ADAPTER_IMAGE

require_var EVIDENCE_HOST_ID
require_var COMPOSE_PROFILES
require_var EVIDENCE_PRIVATE_BIND_IP
case "$EVIDENCE_HOST_ID" in
  ulc-01)
    [ "$EVIDENCE_PRIVATE_BIND_IP" = '10.104.0.2' ] || fail 'ulc-01 private IP must be 10.104.0.2'
    [ "$COMPOSE_PROFILES" = 'ingest,collector,fabric-adapter' ] || fail 'ulc-01 profiles must be ingest,collector,fabric-adapter'
    ACTIVE_INGEST=1; ACTIVE_COLLECTOR=1; ACTIVE_VERIFIER=0; ACTIVE_ADAPTER=1
    ;;
  ulc-02)
    [ "$EVIDENCE_PRIVATE_BIND_IP" = '10.104.0.4' ] || fail 'ulc-02 private IP must be 10.104.0.4'
    [ "$COMPOSE_PROFILES" = 'ingest,verifier,fabric-adapter' ] || fail 'ulc-02 profiles must be ingest,verifier,fabric-adapter'
    ACTIVE_INGEST=1; ACTIVE_COLLECTOR=0; ACTIVE_VERIFIER=1; ACTIVE_ADAPTER=1
    ;;
  ulc-03)
    [ "$EVIDENCE_PRIVATE_BIND_IP" = '10.104.0.8' ] || fail 'ulc-03 private IP must be 10.104.0.8'
    [ "$COMPOSE_PROFILES" = 'collector,verifier' ] || fail 'ulc-03 profiles must be collector,verifier'
    ACTIVE_INGEST=0; ACTIVE_COLLECTOR=1; ACTIVE_VERIFIER=1; ACTIVE_ADAPTER=0
    ;;
  *) fail 'EVIDENCE_HOST_ID must be ulc-01, ulc-02, or ulc-03' ;;
esac

ip -o addr show | awk '{print $4}' | cut -d/ -f1 | grep -Fxq "$EVIDENCE_PRIVATE_BIND_IP" || fail "private bind IP $EVIDENCE_PRIVATE_BIND_IP is not configured on this host"
require_var EVIDENCE_PGBOUNCER_HOST_IP
[ "$EVIDENCE_PGBOUNCER_HOST_IP" = "$EVIDENCE_PRIVATE_BIND_IP" ] || fail 'PgBouncer logical host must map to this node private IP'
pass "host placement $EVIDENCE_HOST_ID/$COMPOSE_PROFILES"
pass "local PgBouncer mapping pgbouncer.internal.lorawan.com=$EVIDENCE_PGBOUNCER_HOST_IP"

require_var EVIDENCE_COMMON_ENV_FILE
check_regular_public_file "$EVIDENCE_COMMON_ENV_FILE" 'common.env'
check_no_template_tokens "$EVIDENCE_COMMON_ENV_FILE" 'common.env'
env_has_exact "$EVIDENCE_COMMON_ENV_FILE" 'EVIDENCE_OBJECTSTORE_BACKEND=s3' || fail 'production common.env must use S3 backend'
env_has_exact "$EVIDENCE_COMMON_ENV_FILE" 'EVIDENCE_ALLOW_DEV_FILESYSTEM=false' || fail 'production common.env must disable filesystem backend'
env_has_nonempty "$EVIDENCE_COMMON_ENV_FILE" EVIDENCE_S3_ENDPOINT || fail 'common.env lacks S3 endpoint'
env_has_nonempty "$EVIDENCE_COMMON_ENV_FILE" EVIDENCE_S3_REGION || fail 'common.env lacks S3 region'
env_has_nonempty "$EVIDENCE_COMMON_ENV_FILE" EVIDENCE_S3_BUCKET || fail 'common.env lacks S3 bucket'
env_has_exact "$EVIDENCE_COMMON_ENV_FILE" 'EVIDENCE_DB_MAX_CONNS=2' || fail 'POC common.env must start with EVIDENCE_DB_MAX_CONNS=2'

require_var EVIDENCE_POSTGRES_CA_HOST_PATH
require_var EVIDENCE_S3_CA_HOST_PATH
check_runtime_public_file "$EVIDENCE_POSTGRES_CA_HOST_PATH" 'PostgreSQL CA'
check_runtime_public_file "$EVIDENCE_S3_CA_HOST_PATH" 'S3 CA'

if [ "$ACTIVE_INGEST" -eq 1 ]; then
  require_port_free EVIDENCE_INGEST_HOST_PORT
  require_var EVIDENCE_INGEST_ENV_FILE
  validate_role_env_common "$EVIDENCE_INGEST_ENV_FILE" 'ingest.env'
  require_var EVIDENCE_INGEST_TLS_CERT_HOST_PATH
  require_var EVIDENCE_INGEST_TLS_KEY_HOST_PATH
  require_var EVIDENCE_INGEST_CLIENT_CA_HOST_PATH
  check_runtime_public_file "$EVIDENCE_INGEST_TLS_CERT_HOST_PATH" 'ingest server certificate'
  check_runtime_key "$EVIDENCE_INGEST_TLS_KEY_HOST_PATH" 'ingest server private key'
  check_runtime_public_file "$EVIDENCE_INGEST_CLIENT_CA_HOST_PATH" 'gateway evidence client CA'
  env_has_exact "$EVIDENCE_INGEST_ENV_FILE" 'EVIDENCE_TLS_CERT_FILE=/run/evidence/ingest/tls.crt' || fail 'ingest TLS certificate path mismatch'
  env_has_exact "$EVIDENCE_INGEST_ENV_FILE" 'EVIDENCE_TLS_KEY_FILE=/run/evidence/ingest/tls.key' || fail 'ingest TLS key path mismatch'
  env_has_exact "$EVIDENCE_INGEST_ENV_FILE" 'EVIDENCE_TLS_CLIENT_CA_FILE=/run/evidence/ingest/client-ca.crt' || fail 'ingest client CA path mismatch'
fi

if [ "$ACTIVE_COLLECTOR" -eq 1 ]; then
  require_port_free EVIDENCE_COLLECTOR_HEALTH_PORT
  require_var EVIDENCE_COLLECTOR_ENV_FILE
  validate_role_env_common "$EVIDENCE_COLLECTOR_ENV_FILE" 'collector.env'
  require_var EVIDENCE_MQTT_CA_HOST_PATH
  check_runtime_public_file "$EVIDENCE_MQTT_CA_HOST_PATH" 'MQTT CA'
  require_var EVIDENCE_MQTT_BROKER1_CLIENT_ID
  require_var EVIDENCE_MQTT_BROKER2_CLIENT_ID
  [ "$EVIDENCE_MQTT_BROKER1_CLIENT_ID" != "$EVIDENCE_MQTT_BROKER2_CLIENT_ID" ] || fail 'collector broker client IDs must differ'
  require_var EVIDENCE_COLLECTOR_AUTH_MODE
  [ "$EVIDENCE_COLLECTOR_AUTH_MODE" = 'mtls' ] || fail 'production collector auth mode is frozen to mtls'
  for name in EVIDENCE_MQTT_BROKER1_CERT_HOST_PATH EVIDENCE_MQTT_BROKER1_KEY_HOST_PATH EVIDENCE_MQTT_BROKER2_CERT_HOST_PATH EVIDENCE_MQTT_BROKER2_KEY_HOST_PATH; do require_var "$name"; done
  check_runtime_public_file "$EVIDENCE_MQTT_BROKER1_CERT_HOST_PATH" 'collector broker1 certificate'
  check_runtime_key "$EVIDENCE_MQTT_BROKER1_KEY_HOST_PATH" 'collector broker1 private key'
  check_runtime_public_file "$EVIDENCE_MQTT_BROKER2_CERT_HOST_PATH" 'collector broker2 certificate'
  check_runtime_key "$EVIDENCE_MQTT_BROKER2_KEY_HOST_PATH" 'collector broker2 private key'
  env_has_exact "$EVIDENCE_COLLECTOR_ENV_FILE" 'EVIDENCE_MQTT_BROKER1_CLIENT_CERT_FILE=/run/evidence/mqtt/broker1.crt' || fail 'collector broker1 certificate path mismatch'
  env_has_exact "$EVIDENCE_COLLECTOR_ENV_FILE" 'EVIDENCE_MQTT_BROKER1_CLIENT_KEY_FILE=/run/evidence/mqtt/broker1.key' || fail 'collector broker1 key path mismatch'
  env_has_exact "$EVIDENCE_COLLECTOR_ENV_FILE" 'EVIDENCE_MQTT_BROKER2_CLIENT_CERT_FILE=/run/evidence/mqtt/broker2.crt' || fail 'collector broker2 certificate path mismatch'
  env_has_exact "$EVIDENCE_COLLECTOR_ENV_FILE" 'EVIDENCE_MQTT_BROKER2_CLIENT_KEY_FILE=/run/evidence/mqtt/broker2.key' || fail 'collector broker2 key path mismatch'
  env_has_exact "$EVIDENCE_COLLECTOR_ENV_FILE" 'EVIDENCE_MQTT_REGION=as923' || fail 'collector region must be as923'
  env_has_exact "$EVIDENCE_COLLECTOR_ENV_FILE" 'EVIDENCE_MQTT_TOPIC_FILTER=as923/gateway/+/event/#' || fail 'collector topic filter mismatch'
fi

if [ "$ACTIVE_VERIFIER" -eq 1 ]; then
  require_port_free EVIDENCE_VERIFIER_HEALTH_PORT
  require_var EVIDENCE_VERIFIER_ENV_FILE
  validate_role_env_common "$EVIDENCE_VERIFIER_ENV_FILE" 'verifier.env'
  require_var EVIDENCE_VERIFIER_WORKER_ID
  case "$EVIDENCE_VERIFIER_WORKER_ID" in
    evidence-verifier-ulc-02|evidence-verifier-ulc-03) ;;
    *) fail 'verifier worker ID must match frozen host identity' ;;
  esac
fi

if [ "$ACTIVE_ADAPTER" -eq 1 ]; then
  require_port_free EVIDENCE_ADAPTER_HEALTH_PORT
  # The base adapter profile is intentionally fail-closed before external
  # Fabric handoff. It accepts no DB, OpenBao, or Fabric credential mounts.
  pass 'Fabric adapter base profile is standby-only (FABRIC_ADAPTER_ENABLED=false)'
fi

# Compose interpolation needs one merged non-secret release/host env file. Role
# secrets remain in protected env_file inputs and are never copied/printed here.
MERGED=$(mktemp)
trap 'rm -f "$MERGED"' EXIT
cat "$RELEASE_ENV" "$HOST_ENV" > "$MERGED"
COMPOSE_ARGS=(--env-file "$MERGED" -f "$COMPOSE_FILE")
if [ "${EVIDENCE_COLLECTOR_AUTH_MODE-}" = 'mtls' ] && [ "$ACTIVE_COLLECTOR" -eq 1 ]; then
  COMPOSE_ARGS+=( -f "$MTLS_OVERRIDE" )
fi
COMPOSE_PROFILES="$COMPOSE_PROFILES" docker compose "${COMPOSE_ARGS[@]}" config --quiet || fail 'docker compose config validation failed'
pass 'docker compose config'

printf 'EVIDENCE_DEPLOYMENT_PREFLIGHT=PASS\n'
printf 'No image pulled. No container started. No live file changed.\n'
