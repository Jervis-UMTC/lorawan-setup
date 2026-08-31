#!/usr/bin/env bash
# Read-only activation gate for the Fabric adapter.
#
# Run only after the external Fabric handoff is complete and the adapter's
# protected OpenBao/Fabric credentials have been installed. This script never
# issues credentials, starts containers, pulls images, changes permissions, or
# mutates PostgreSQL/OpenBao/Fabric state.
set -u

fail() {
  printf 'FABRIC_ADAPTER_ENABLE_PREFLIGHT_FAIL|%s\n' "$1" >&2
  exit 1
}

pass() {
  printf 'FABRIC_ADAPTER_ENABLE_PREFLIGHT_PASS|%s\n' "$1"
}

[ "$#" -eq 2 ] || fail 'usage: fabric-adapter-enable-preflight.sh /path/release.env /path/host.env'
RELEASE_ENV=$1
HOST_ENV=$2
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
COMPOSE_FILE="$SCRIPT_DIR/compose.yml"
ADAPTER_OVERRIDE="$SCRIPT_DIR/compose.fabric-adapter-enabled.yml"
COLLECTOR_OVERRIDE="$SCRIPT_DIR/compose.collector-mtls.yml"

[ "$(id -u)" -eq 0 ] || fail 'run as root so credential ownership/mode checks are authoritative'
for command in docker stat grep sed awk curl openssl sha256sum mktemp; do
  command -v "$command" >/dev/null 2>&1 || fail "$command is required"
done
docker compose version >/dev/null 2>&1 || fail 'docker compose v2 is required'

check_nonsecret_input() {
  file=$1
  label=$2
  [ -f "$file" ] || fail "$label missing: $file"
  uid=$(stat -c '%u' "$file") || fail "cannot stat $label"
  mode=$(stat -c '%a' "$file") || fail "cannot stat $label mode"
  [ "$uid" = 0 ] || fail "$label must be root-owned"
  perm=$((8#$mode))
  (( (perm & 022) == 0 )) || fail "$label must not be group/world writable"
}

check_nonsecret_input "$RELEASE_ENV" 'release.env'
check_nonsecret_input "$HOST_ENV" 'host.env'

# release.env and host.env are the already-reviewed non-secret interpolation
# inputs. The protected adapter env is deliberately NOT sourced because its DSN
# contains shell-significant characters and secrets must not enter this shell's
# exported environment.
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

case "${EVIDENCE_HOST_ID-}" in
  ulc-01)
    [ "${EVIDENCE_PRIVATE_BIND_IP-}" = '10.104.0.2' ] || fail 'ulc-01 private IP must be 10.104.0.2'
    [ "${FABRIC_ADAPTER_WORKER_ID-}" = 'fabric-adapter-ulc-01' ] || fail 'ulc-01 adapter worker ID mismatch'
    ;;
  ulc-02)
    [ "${EVIDENCE_PRIVATE_BIND_IP-}" = '10.104.0.4' ] || fail 'ulc-02 private IP must be 10.104.0.4'
    [ "${FABRIC_ADAPTER_WORKER_ID-}" = 'fabric-adapter-ulc-02' ] || fail 'ulc-02 adapter worker ID mismatch'
    ;;
  *) fail 'Fabric adapter activation is allowed only on ulc-01 or ulc-02' ;;
esac
pass "host placement ${EVIDENCE_HOST_ID}/${FABRIC_ADAPTER_WORKER_ID}"

require_var EVIDENCE_ADAPTER_IMAGE
printf '%s' "$EVIDENCE_ADAPTER_IMAGE" | grep -Eq '^.+@sha256:[0-9a-f]{64}$' || fail 'EVIDENCE_ADAPTER_IMAGE must be one immutable image@sha256:<64hex> reference'

for name in \
  FABRIC_ADAPTER_ENV_FILE \
  OPENBAO_CA_HOST_PATH \
  OPENBAO_APPROLE_ROLE_ID_HOST_PATH \
  OPENBAO_APPROLE_SECRET_ID_HOST_PATH \
  FABRIC_TLS_ROOT_CERT_HOST_PATH \
  FABRIC_CERT_HOST_PATH \
  FABRIC_KEY_HOST_PATH \
  EVIDENCE_POSTGRES_CA_HOST_PATH; do
  require_var "$name"
done

check_secret_env() {
  file=$1
  label=$2
  [ -f "$file" ] || fail "$label missing: $file"
  [ "$(stat -c '%u:%g:%a' "$file")" = '0:0:600' ] || fail "$label must be root:root mode 0600"
  grep -Eq '<[A-Z0-9_]+>' "$file" && fail "$label still contains example placeholder tokens"
}

check_runtime_key() {
  file=$1
  label=$2
  [ -s "$file" ] || fail "$label missing or empty: $file"
  [ "$(stat -c '%u:%g:%a' "$file")" = '0:65532:440' ] || fail "$label must be root:GID-65532 mode 0440"
}

check_runtime_public_file() {
  file=$1
  label=$2
  [ -s "$file" ] || fail "$label missing or empty: $file"
  uid=$(stat -c '%u' "$file") || fail "cannot stat $label owner"
  gid=$(stat -c '%g' "$file") || fail "cannot stat $label group"
  mode=$(stat -c '%a' "$file") || fail "cannot stat $label mode"
  [ "$uid" = 0 ] || fail "$label must be root-owned"
  perm=$((8#$mode))
  (( (perm & 022) == 0 )) || fail "$label must not be group/world writable"
  readable=0
  if [ "$gid" = '65532' ] && (( (perm & 040) != 0 )); then readable=1; fi
  if (( (perm & 004) != 0 )); then readable=1; fi
  [ "$readable" -eq 1 ] || fail "$label must be readable by runtime 65532:65532"
}

check_secret_env "$FABRIC_ADAPTER_ENV_FILE" 'fabric-adapter.env'
check_runtime_public_file "$EVIDENCE_POSTGRES_CA_HOST_PATH" 'PostgreSQL CA'
check_runtime_public_file "$OPENBAO_CA_HOST_PATH" 'OpenBao CA'
check_runtime_key "$OPENBAO_APPROLE_ROLE_ID_HOST_PATH" 'OpenBao AppRole RoleID file'
check_runtime_key "$OPENBAO_APPROLE_SECRET_ID_HOST_PATH" 'OpenBao AppRole SecretID file'
check_runtime_public_file "$FABRIC_TLS_ROOT_CERT_HOST_PATH" 'Fabric TLS root certificate'
check_runtime_public_file "$FABRIC_CERT_HOST_PATH" 'Fabric client identity certificate'
check_runtime_key "$FABRIC_KEY_HOST_PATH" 'Fabric client identity private key'

get_env_value() {
  file=$1
  key=$2
  line=$(grep -m1 -E "^${key}=.+$" "$file" || true)
  [ -n "$line" ] || fail "fabric-adapter.env lacks $key"
  printf '%s' "${line#*=}"
}

require_env_exact() {
  key=$1
  expected=$2
  actual=$(get_env_value "$FABRIC_ADAPTER_ENV_FILE" "$key")
  [ "$actual" = "$expected" ] || fail "$key does not match the frozen runtime path/value"
}

DB_URL=$(get_env_value "$FABRIC_ADAPTER_ENV_FILE" FABRIC_ADAPTER_DATABASE_URL)
printf '%s' "$DB_URL" | grep -Eq '^postgres(ql)?://fabric_adapter:[^@]+@pgbouncer\.internal\.lorawan\.com:6432/lorawan_telemetry\?' || fail 'Fabric adapter DSN must use the commissioned fabric_adapter login and logical PgBouncer endpoint'
printf '%s' "$DB_URL" | grep -Fq 'sslmode=verify-full' || fail 'Fabric adapter DSN must use sslmode=verify-full'
printf '%s' "$DB_URL" | grep -Fq 'sslrootcert=/run/evidence/postgres/ca.crt' || fail 'Fabric adapter DSN must use the mounted PostgreSQL CA'
pass 'database DSN trust path'

require_env_exact FABRIC_ADAPTER_DATABASE_EXPECTED_HOST 'pgbouncer.internal.lorawan.com'
require_env_exact FABRIC_ADAPTER_DATABASE_EXPECTED_NAME 'lorawan_telemetry'
require_env_exact OPENBAO_ADDR 'https://openbao-kms.internal.lorawan.com:18200'
require_env_exact OPENBAO_CA_FILE '/run/openbao/ca.crt'
require_env_exact OPENBAO_TRANSIT_MOUNT 'transit'
require_env_exact OPENBAO_TRANSIT_KEY 'lorawan-evidence'
require_env_exact OPENBAO_APPROLE_ROLE_ID_FILE '/run/openbao-approle/role_id'
require_env_exact OPENBAO_APPROLE_SECRET_ID_FILE '/run/openbao-approle/secret_id'
require_env_exact FABRIC_TLS_ROOT_CERT '/run/fabric/tls/ca.crt'
require_env_exact FABRIC_CERT_PATH '/run/fabric/identity/client.crt'
require_env_exact FABRIC_KEY_PATH '/run/fabric/identity/client.key'

for key in FABRIC_MSP_ID FABRIC_CHANNEL FABRIC_CHAINCODE FABRIC_SUBMIT_FUNCTION FABRIC_QUERY_FUNCTION; do
  value=$(get_env_value "$FABRIC_ADAPTER_ENV_FILE" "$key")
  [ -n "$value" ] || fail "$key must not be empty"
done

FABRIC_ENDPOINT=$(get_env_value "$FABRIC_ADAPTER_ENV_FILE" FABRIC_GATEWAY_ENDPOINT)
FABRIC_TLS_NAME=$(get_env_value "$FABRIC_ADAPTER_ENV_FILE" FABRIC_TLS_SERVER_NAME)
case "$FABRIC_ENDPOINT" in
  *://*) fail 'FABRIC_GATEWAY_ENDPOINT must be host:port, not a URL' ;;
esac
FABRIC_HOST=${FABRIC_ENDPOINT%:*}
FABRIC_PORT=${FABRIC_ENDPOINT##*:}
[ -n "$FABRIC_HOST" ] && [ "$FABRIC_HOST" != "$FABRIC_ENDPOINT" ] || fail 'FABRIC_GATEWAY_ENDPOINT must contain host:port'
printf '%s' "$FABRIC_PORT" | grep -Eq '^[0-9]+$' || fail 'Fabric Gateway port must be numeric'
[ "$FABRIC_PORT" -ge 1 ] && [ "$FABRIC_PORT" -le 65535 ] || fail 'Fabric Gateway port must be 1..65535'
[ -n "$FABRIC_TLS_NAME" ] || fail 'FABRIC_TLS_SERVER_NAME must not be empty'
pass 'external Fabric endpoint syntax'

# Prove the Fabric application certificate and private key are a pair without
# printing private-key material.
CERT_PUB=$(openssl x509 -in "$FABRIC_CERT_HOST_PATH" -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform DER 2>/dev/null | sha256sum | awk '{print $1}') || fail 'cannot derive Fabric certificate public key'
KEY_PUB=$(openssl pkey -in "$FABRIC_KEY_HOST_PATH" -pubout -outform DER 2>/dev/null | sha256sum | awk '{print $1}') || fail 'cannot derive Fabric private-key public key'
[ -n "$CERT_PUB" ] && [ "$CERT_PUB" = "$KEY_PUB" ] || fail 'Fabric certificate/private key do not match'
pass 'Fabric client certificate/private-key match'

# Verify the already-commissioned stable OpenBao route using the same hostname
# the container will use while forcing resolution to this host's local HAProxy.
OPENBAO_CODE=$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' \
  --connect-timeout 5 --max-time 10 \
  --cacert "$OPENBAO_CA_HOST_PATH" \
  --resolve "openbao-kms.internal.lorawan.com:18200:${EVIDENCE_PRIVATE_BIND_IP}" \
  'https://openbao-kms.internal.lorawan.com:18200/v1/sys/health?standbyok=true' || true)
[ "$OPENBAO_CODE" = '200' ] || fail "stable OpenBao health returned HTTP ${OPENBAO_CODE:-000}"
pass 'stable OpenBao TLS/health through local HAProxy'

# A successful server-auth TLS handshake is the minimum safe transport gate for
# the current adapter implementation. If the external Gateway requires a
# separate TLS client certificate (gRPC mTLS), this check will fail and the
# adapter must be extended/rebuilt instead of bypassing TLS authentication.
TLS_OUTPUT=$(mktemp)
MERGED=''
trap 'rm -f "$TLS_OUTPUT" ${MERGED:+"$MERGED"}' EXIT
if ! openssl s_client \
  -connect "$FABRIC_ENDPOINT" \
  -servername "$FABRIC_TLS_NAME" \
  -verify_hostname "$FABRIC_TLS_NAME" \
  -verify_return_error \
  -CAfile "$FABRIC_TLS_ROOT_CERT_HOST_PATH" \
  </dev/null >"$TLS_OUTPUT" 2>&1; then
  fail 'external Fabric Gateway TLS handshake/hostname verification failed'
fi
grep -Fq 'Verify return code: 0 (ok)' "$TLS_OUTPUT" || fail 'external Fabric Gateway certificate verification did not return code 0'
pass 'external Fabric Gateway server TLS verification'

# Validate the exact activation composition. This expands the enabled overlay
# but performs no pull, create, or start operation.
MERGED=$(mktemp)
cat "$RELEASE_ENV" "$HOST_ENV" > "$MERGED"
COMPOSE_ARGS=(--env-file "$MERGED" -f "$COMPOSE_FILE" -f "$ADAPTER_OVERRIDE")
if [ "${EVIDENCE_COLLECTOR_AUTH_MODE-}" = 'mtls' ] && [ "${EVIDENCE_HOST_ID-}" = 'ulc-01' ]; then
  COMPOSE_ARGS+=( -f "$COLLECTOR_OVERRIDE" )
fi
COMPOSE_PROFILES="$COMPOSE_PROFILES" docker compose "${COMPOSE_ARGS[@]}" config --quiet || fail 'enabled Fabric adapter Compose configuration is invalid'
pass 'enabled Compose configuration'

printf 'FABRIC_ADAPTER_ENABLE_PREFLIGHT=PASS\n'
printf 'No image pulled. No container started. No credential issued. No DB/OpenBao/Fabric state changed.\n'
