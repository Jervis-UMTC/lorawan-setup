# SeaweedFS Live Commissioning — One Boundary at a Time

This runbook is the live operator companion to `README.md`. It deliberately separates read-only discovery from image pulls, filesystem creation, metadata quorum bootstrap, SeaweedFS startup, bucket/identity creation, HAProxy rollout, and application acceptance.

Do not combine the phases. Stop at the first failed gate and preserve the output.

## S0 — ulc-02 immutable-image + host preflight

Run this block **only on ulc-02** first. It is read-only with respect to running services and does not pull/start/restart a container.

```bash
sudo bash <<'SEAWEED_S0'
set -Eeuo pipefail

fail() { echo "FAIL|$*" >&2; exit 1; }
pass() { echo "PASS|$*"; }

[ "$(hostname -s)" = "ulc-02" ] || fail "run S0 only on ulc-02"

SEAWEED_TAG='chrislusf/seaweedfs:4.41'
ETCD_TAG='quay.io/coreos/etcd:v3.5.15'
CANDIDATE_PORTS='12379 12380 19333 19334 18082 18083 18888 18889 18333 18334 18443'

echo '============================================================'
echo ' SEAWEEDFS S0 - IMMUTABLE IMAGE + HOST PREFLIGHT'
echo ' READ ONLY / NO IMAGE PULL / NO CONTAINER START'
echo '============================================================'

echo
echo '=== 1. HOST IDENTITY ==='
hostname -f || true
ip -4 -br addr
ip -4 addr show | grep -Fq '10.104.0.4/' || fail 'ulc-02 VPC address 10.104.0.4 missing'
pass 'ulc-02 VPC identity'

echo
echo '=== 2. DOCKER TOOLING ==='
docker --version
docker compose version
docker buildx version
pass 'Docker/Compose/Buildx available'

echo
echo '=== 3. RESOLVE IMMUTABLE REGISTRY DIGESTS ==='
resolve_ref() {
    local tag="$1"
    local label="$2"
    local out digest

    out="$(docker buildx imagetools inspect "$tag")" || fail "$label registry inspection failed"
    printf '%s\n' "$out" | grep -Fq 'linux/amd64' || fail "$label does not advertise linux/amd64"
    digest="$(printf '%s\n' "$out" | awk '/^Digest:/ {print $2; exit}')"
    [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || fail "$label digest parse failed"

    docker buildx imagetools inspect "${tag}@${digest}" >/dev/null || fail "$label digest lookup failed"
    printf '%s|%s@%s\n' "$label" "$tag" "$digest"
}

SEAWEED_LINE="$(resolve_ref "$SEAWEED_TAG" SEAWEEDFS)"
ETCD_LINE="$(resolve_ref "$ETCD_TAG" SEAWEED_METADATA_ETCD)"
printf '%s\n' "$SEAWEED_LINE"
printf '%s\n' "$ETCD_LINE"
pass 'immutable registry references resolved and amd64 advertised'

echo
echo '=== 4. CURRENT MEMORY / DISK ==='
free -m
df -h / /srv 2>/dev/null || df -h /
MEM_AVAILABLE_KIB="$(awk '/MemAvailable:/ {print $2}' /proc/meminfo)"
[ "${MEM_AVAILABLE_KIB:-0}" -ge 614400 ] || fail 'less than 600 MiB MemAvailable'
DISK_TARGET=/srv
[ -d /srv ] || DISK_TARGET=/
DISK_AVAILABLE_KIB="$(df -Pk "$DISK_TARGET" | awk 'NR==2 {print $4}')"
[ "${DISK_AVAILABLE_KIB:-0}" -ge 5242880 ] || fail 'less than 5 GiB free on storage filesystem'
pass 'minimum current memory/disk headroom'

echo
echo '=== 5. EXISTING PATRONI DCS ETCD MUST REMAIN PRESENT ==='
ss -H -lnt 'sport = :2379' | tee /dev/stderr | grep -q . || fail '2379 listener missing'
ss -H -lnt 'sport = :2380' | tee /dev/stderr | grep -q . || fail '2380 listener missing'
pass 'existing etcd listeners remain present'

echo
echo '=== 6. SEAWEEDFS CANDIDATE PORTS MUST ALL BE FREE ==='
for port in $CANDIDATE_PORTS; do
    if ss -H -lnt "sport = :$port" | grep -q .; then
        ss -lntp "sport = :$port" || true
        fail "candidate port already in use: $port"
    fi
    echo "port_${port}=FREE"
done
pass 'all SeaweedFS candidate ports free on ulc-02'

echo
echo '=== 7. EXISTING CONTAINER RESOURCE SNAPSHOT ==='
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
echo
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}' || true

echo
echo '============================================================'
echo ' S0 RESULT'
echo '============================================================'
echo 'SEAWEEDFS_S0_ULC02=PASS'
echo 'NO_IMAGE_PULLED_BY_THIS_BLOCK=YES'
echo 'NO_CONTAINER_STARTED_BY_THIS_BLOCK=YES'
echo 'NEXT=PIN_THE_TWO_PRINTED_IMAGE_REFS_THEN_PULL_INSPECT_ON_ULC02'
SEAWEED_S0
```

Expected output includes exactly two immutable reference lines:

```text
SEAWEEDFS|chrislusf/seaweedfs:4.41@sha256:<64-hex>
SEAWEED_METADATA_ETCD|quay.io/coreos/etcd:v3.5.15@sha256:<64-hex>
```

Do not copy a digest from documentation or another architecture. The registry result from the approved Docker/Buildx host is the input for the next boundary.

## Live boundary status — 2026-08-31

```text
S0  PASS - immutable-image/host discovery completed
S1  PASS - SeaweedFS 4.41 and metadata-etcd immutable refs inspected
S2  PASS - three-host resource/port preflight completed
S3  PASS - protected SeaweedFS directories/config staged
S4  PASS - swmeta-01/02/03 form a healthy 3-voter metadata-etcd quorum
S5  PASS - SeaweedFS core healthy on ulc-01/02/03
S6  PASS - lorawan-evidence bucket + replication=010; empirical two-rack placement proven
S7  PASS - least-privilege runtime S3 identities + internal object-store PKI installed
S8  PASS - HAProxy TLS/create-only boundary proven on all three nodes
S9  PENDING - production gateway-evidence-ingest helper binary is not yet staged on any server
S10 BLOCKED ON S9 - do not claim EVIDENCE_OBJECTSTORE=PASS yet
```

Pinned live images:

```text
SeaweedFS  chrislusf/seaweedfs:4.41@sha256:43b768cd62b00d132439cda881b93fd1adebf1b315e996e794087743821d771d
metadata   quay.io/coreos/etcd:v3.5.15@sha256:0934690612905554eb61ddefb9faaaecb47c2f6931dbb453e694358092ee8990
```

Live custom ports are master `19333/19334`, volume `18082/18083`, filer `18888/18889`, raw S3 `127.0.0.1:18333`, S3 gRPC `18334`, and HAProxy TLS `18443`. When using SeaweedFS CLI/shell with the custom master/filer gRPC ports, use explicit combined address forms such as `10.104.0.2:19333.19334` and `10.104.0.2:18888.18889`; plain `:19333` or `:18888` incorrectly derives `29333` or `28888`.

The one-Droplet-loss kill/recovery exercise remains Phase 15 and is not part of this streamlined initial commissioning.
