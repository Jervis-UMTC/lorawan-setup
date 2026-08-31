#!/usr/bin/env bash
set -Eeuo pipefail

fail() { echo "FAIL|$*" >&2; exit 1; }
pass() { echo "PASS|$*"; }

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASE_ENV="${1:-$BASE_DIR/release.env}"
HOST_ENV="${2:-$BASE_DIR/host.env}"

[ -f "$RELEASE_ENV" ] || fail "missing release env: $RELEASE_ENV"
[ -f "$HOST_ENV" ] || fail "missing host env: $HOST_ENV"
set -a
# shellcheck disable=SC1090
. "$RELEASE_ENV"
# shellcheck disable=SC1090
. "$HOST_ENV"
set +a

required=(
  SEAWEEDFS_IMAGE SEAWEED_METADATA_ETCD_IMAGE SEAWEED_NODE_NAME SEAWEED_NODE_IP
  SEAWEED_RACK SEAWEED_META_MEMBER_NAME SEAWEED_DATACENTER SEAWEED_REPLICATION
  SEAWEED_META_CLIENT_PORT SEAWEED_META_PEER_PORT SEAWEED_MASTER_PORT
  SEAWEED_MASTER_GRPC_PORT SEAWEED_VOLUME_PORT SEAWEED_VOLUME_GRPC_PORT
  SEAWEED_FILER_PORT SEAWEED_FILER_GRPC_PORT SEAWEED_S3_BACKEND_PORT
  SEAWEED_S3_GRPC_PORT SEAWEED_S3_TLS_FRONTEND_PORT SEAWEED_MASTER_PEERS
  SEAWEED_META_INITIAL_CLUSTER SEAWEED_META_CLUSTER_TOKEN
)
for name in "${required[@]}"; do
  [ -n "${!name:-}" ] || fail "missing $name"
done

[ "$(hostname -s)" = "$SEAWEED_NODE_NAME" ] || fail "hostname mismatch"
ip -4 addr show | grep -Fq " ${SEAWEED_NODE_IP}/" || fail "node VPC IP not present"
[ "$SEAWEED_DATACENTER" = "sgp1" ] || fail "data center must be sgp1"
[ "$SEAWEED_RACK" = "$SEAWEED_NODE_NAME" ] || fail "rack must equal physical host name"
[ "$SEAWEED_REPLICATION" = "010" ] || fail "replication must be 010"

case "$SEAWEED_NODE_NAME:$SEAWEED_NODE_IP:$SEAWEED_META_MEMBER_NAME" in
  ulc-01:10.104.0.2:swmeta-01|ulc-02:10.104.0.4:swmeta-02|ulc-03:10.104.0.8:swmeta-03) ;;
  *) fail "host identity does not match frozen topology" ;;
esac
pass "host identity and rack topology"

for image in "$SEAWEEDFS_IMAGE" "$SEAWEED_METADATA_ETCD_IMAGE"; do
  [[ "$image" == *@sha256:* ]] || fail "image is not digest pinned: $image"
  [[ "$image" != *'<'* && "$image" != *'>'* ]] || fail "image digest placeholder not replaced"
done
[[ "$SEAWEEDFS_IMAGE" == chrislusf/seaweedfs:4.41@sha256:* ]] || fail "SeaweedFS release must remain 4.41"
pass "immutable image references"

[ "$SEAWEED_META_CLIENT_PORT" != "2379" ] || fail "must not reuse Patroni etcd client port"
[ "$SEAWEED_META_PEER_PORT" != "2380" ] || fail "must not reuse Patroni etcd peer port"

ports=(
  "$SEAWEED_META_CLIENT_PORT" "$SEAWEED_META_PEER_PORT"
  "$SEAWEED_MASTER_PORT" "$SEAWEED_MASTER_GRPC_PORT"
  "$SEAWEED_VOLUME_PORT" "$SEAWEED_VOLUME_GRPC_PORT"
  "$SEAWEED_FILER_PORT" "$SEAWEED_FILER_GRPC_PORT"
  "$SEAWEED_S3_BACKEND_PORT" "$SEAWEED_S3_GRPC_PORT"
  "$SEAWEED_S3_TLS_FRONTEND_PORT"
)
if [ "$(printf '%s\n' "${ports[@]}" | sort -u | wc -l)" -ne "${#ports[@]}" ]; then
  fail "SeaweedFS candidate ports are not unique"
fi
for port in "${ports[@]}"; do
  if ss -H -lnt "sport = :$port" | grep -q .; then
    fail "candidate port already in use: $port"
  fi
done
pass "candidate ports are free"

# Existing Patroni DCS etcd must remain separate and healthy enough to own its
# established ports. We only assert listener separation here, not cluster health.
ss -H -lnt "sport = :2379" | grep -q . || fail "existing Patroni etcd client listener 2379 missing"
ss -H -lnt "sport = :2380" | grep -q . || fail "existing Patroni etcd peer listener 2380 missing"
pass "existing Patroni etcd remains separate"

command -v docker >/dev/null || fail "docker missing"
docker compose version >/dev/null 2>&1 || fail "docker compose missing"

avail_kib="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
[ "${avail_kib:-0}" -ge 614400 ] || fail "less than 600 MiB memory available"
avail_disk_kib="$(df -Pk /srv 2>/dev/null | awk 'NR==2 {print $4}')"
[ "${avail_disk_kib:-0}" -ge 5242880 ] || fail "less than 5 GiB free under /srv"
pass "minimum memory and disk headroom"

for path in \
  /etc/lorawan-cloud/seaweedfs/filer.toml \
  /etc/lorawan-cloud/seaweedfs/s3.json; do
  [ -f "$path" ] || fail "missing protected config: $path"
done
[ "$(stat -c '%a' /etc/lorawan-cloud/seaweedfs/s3.json)" = "640" ] || fail "s3.json must be mode 0640"
[ "$(stat -c '%u:%g' /etc/lorawan-cloud/seaweedfs/s3.json)" = "0:1000" ] || fail "s3.json must be root:1000 for the commissioned SeaweedFS runtime"

grep -Fq 'enabled = true' /etc/lorawan-cloud/seaweedfs/filer.toml || fail "etcd filer store not enabled"
grep -Fq '10.104.0.2:12379,10.104.0.4:12379,10.104.0.8:12379' /etc/lorawan-cloud/seaweedfs/filer.toml || fail "wrong metadata etcd endpoints"
if grep -Eq '"Admin"|anonymous' /etc/lorawan-cloud/seaweedfs/s3.json; then
  fail "runtime S3 config must not contain Admin or anonymous identity"
fi
pass "protected filer/S3 configuration"

set -a
. "$RELEASE_ENV"
. "$HOST_ENV"
set +a
docker compose -f "$BASE_DIR/compose.yml" config --quiet || fail "compose rendering failed"
pass "compose rendering"

echo "SEAWEEDFS_PREFLIGHT=PASS"
