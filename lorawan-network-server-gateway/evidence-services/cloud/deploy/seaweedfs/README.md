# SeaweedFS HA Raw-Evidence Store

This directory freezes the self-hosted production candidate for gateway raw evidence. It replaces the earlier managed-S3 placeholder with SeaweedFS while preserving the Go services' generic S3 interface.

**Selection:** SeaweedFS OSS `4.41`, live linux/amd64 image `chrislusf/seaweedfs:4.41@sha256:43b768cd62b00d132439cda881b93fd1adebf1b315e996e794087743821d771d`, commit `de34a1a87`. Dedicated filer metadata uses `quay.io/coreos/etcd:v3.5.15@sha256:0934690612905554eb61ddefb9faaaecb47c2f6931dbb453e694358092ee8990`. Releases before `4.30` are not acceptable because the S3 gateway had a fixed cross-bucket path-traversal vulnerability.

## Topology

```text
                           sgp1 / 10.104.0.0/20

 ulc-01 / rack=ulc-01       ulc-02 / rack=ulc-02       ulc-03 / rack=ulc-03
 +--------------------+     +--------------------+     +--------------------+
 | swmeta-01 etcd     |<--->| swmeta-02 etcd     |<--->| swmeta-03 etcd     |
 | 12379 / 12380      |     | 12379 / 12380      |     | 12379 / 12380      |
 |                    |     |                    |     |                    |
 | master             |<--->| master             |<--->| master             |
 | volume             |<--->| volume             |<--->| volume             |
 | filer              |     | filer              |     | filer              |
 | S3 127.0.0.1:18333|     | S3 127.0.0.1:18333|     | S3 127.0.0.1:18333|
 +---------+----------+     +---------+----------+     +---------+----------+
           |                          |                          |
           v                          v                          v
    HAProxy TLS :18443         HAProxy TLS :18443         HAProxy TLS :18443
    method/header gate         method/header gate         method/header gate
           ^                          ^                          ^
           |                          |                          |
       local evidence             local evidence             local evidence
       service replicas           service replicas           service replicas
```

SeaweedFS placement is `010`: one additional copy in a **different rack in the same data center**. Each physical Droplet is deliberately one rack, so an acknowledged raw object has two host copies. Do not replace this with `001`; `001` means another server in the same rack and does not describe our host-failure model as clearly.

The separate `swmeta-*` etcd quorum exists only for SeaweedFS filer namespace metadata. It uses `12379/12380`, separate data directories, and a separate cluster token. Never point the filer at the commissioned Patroni DCS etcd on `2379/2380`.

## Why the runtime S3 endpoint is stricter than SeaweedFS IAM

SeaweedFS's `Write` action includes delete-capable S3 operations. Therefore IAM alone is **not** our immutability boundary.

The evidence services only require:

```text
HEAD bucket/object readiness
GET object bytes
PUT object with If-None-Match: *
```

The host HAProxy frontend enforces exactly that surface:

```text
GET / HEAD                         allowed
PUT + If-None-Match: *             allowed
PUT without create-only condition  denied
POST                               denied
DELETE                             denied
all other methods                  denied
```

This means a runtime S3 credential cannot use the commissioned endpoint to issue object deletion, multipart completion, bucket administration, ACL mutation, or unconditional overwrite. SeaweedFS's own conditional write then arbitrates two concurrent create attempts atomically. Filer WORM may be enabled later as defense in depth only after its exact behavior is empirically proven; correctness does not depend on assuming undocumented retention semantics.

The raw Seaweed S3 listener binds `127.0.0.1:18333`, so application containers never connect to it directly. They connect to `https://evidence-objects.internal.lorawan.com:18443`, resolved to the local host VPC address. TLS is terminated by the already-managed host HAProxy with an internal-PKI certificate.

## Resource policy

The three application servers have only 2 GiB RAM. The candidate therefore uses:

```text
SeaweedFS all-in-one process: 256 MiB container cap, GOMEMLIMIT=220MiB
Seaweed metadata etcd:          96 MiB container cap
volume index:                   leveldb, not in-memory
S3 chunk cache:                 disabled
volume size limit:              1 GiB
```

These are commissioning caps, not claims about observed runtime usage. `preflight.sh` requires at least 600 MiB currently available before adding the storage pair. After deployment, record actual RSS before starting the evidence replicas; if the cap causes OOM/restarts, stop and resize rather than silently removing limits.

## Port allocation

```text
12379  Seaweed metadata-etcd client
12380  Seaweed metadata-etcd peer
19333  Seaweed master HTTP
19334  Seaweed master gRPC
18082  Seaweed volume HTTP
18083  Seaweed volume gRPC
18888  Seaweed filer HTTP
18889  Seaweed filer gRPC
18333  Seaweed S3 HTTP backend, loopback only
18334  Seaweed S3 gRPC, loopback/process-internal use
18443  evidence S3 TLS/immutability frontend on VPC address
```

All ports are explicit because SeaweedFS otherwise derives gRPC ports as HTTP port + 10000, and its normal volume default `8080` collides with the commissioned ChirpStack backend. Custom master/filer gRPC addresses must be expressed explicitly to SeaweedFS tools, for example `10.104.0.2:19333.19334` and `10.104.0.2:18888.18889`; using only `:19333`/`:18888` incorrectly derives `29333`/`28888`. The preflight refuses any candidate port already in use before initial deployment.

## Tracked vs protected files

Tracked:

```text
compose.yml
release.env.example
hosts/*.env.example
filer.toml
s3.json.example
haproxy-evidence-s3.cfg.example
preflight.sh
```

Live protected inputs:

```text
/etc/lorawan-cloud/seaweedfs/release.env        0600 root:root
/etc/lorawan-cloud/seaweedfs/host.env           0600 root:root
/etc/lorawan-cloud/seaweedfs/filer.toml         0644 root:root
/etc/lorawan-cloud/seaweedfs/s3.json            0640 root:1000
/etc/lorawan-pki/evidence-objectstore/ca.crt      0644 root:root
/etc/lorawan-pki/evidence-objectstore/<node>.*    0640 root:haproxy
/srv/seaweedfs/metadata-etcd                     persistent
/srv/seaweedfs/master                            persistent
/srv/seaweedfs/volume                            persistent
```

Never commit live S3 access keys or the TLS private key.

## S3 identities

Use unique role credentials, not one shared key:

```text
gateway-evidence-ingest
  Read:lorawan-evidence
  List:lorawan-evidence
  Write:lorawan-evidence

gateway-mqtt-evidence-collector
  Read:lorawan-evidence
  List:lorawan-evidence
  Write:lorawan-evidence

gateway-evidence-verifier
  Read:lorawan-evidence
  List:lorawan-evidence
```

No runtime identity receives `Admin`. Create the `lorawan-evidence` bucket from a local privileged SeaweedFS administration session before installing the runtime-only identity file.

## Commissioning order

Do not start all three nodes at once without checkpoints.

```text
1. Pin SeaweedFS 4.41 + etcd 3.5.15 linux/amd64 image digests.
2. Run preflight on ulc-01, ulc-02, ulc-03. All must PASS.
3. Stage protected directories/configs on all three hosts.
4. Start swmeta-01 only; expect no quorum yet and make no filer claims.
5. Start swmeta-02; prove two-member quorum/health.
6. Start swmeta-03; prove 3 voters and common cluster ID.
7. Start SeaweedFS on ulc-01; verify only that node's process/listeners.
8. Start ulc-02 SeaweedFS; verify master membership and second rack/volume.
9. Start ulc-03 SeaweedFS; verify all three masters/racks/volumes/filers.
10. Create private bucket lorawan-evidence once.
11. Apply fs.configure for /buckets/lorawan-evidence/ with replication=010.
12. Prove the effective rule reports replication 010.
13. Issue three runtime S3 identities and install identical protected s3.json on all nodes.
14. Issue per-node internal TLS certs for evidence-objects.internal.lorawan.com.
15. Merge/validate the HAProxy method/header frontend one host at a time.
16. Configure evidence services to use the local :18443 TLS endpoint.
17. Run gateway-evidence-ingest objectstore-contract-write through HAProxy.
18. Verify the printed immutable fixture from another host using objectstore-contract-verify.
19. Record exact SHA/size/ref and retain the commissioning objects; do not delete them.
```

The dedicated one-Droplet-loss exercise remains Phase 15. Initial commissioning proves the configured two-copy placement, exact create-only behavior through the production endpoint, and cross-host readability without deliberately killing a healthy production node.

## Application configuration

The evidence-service common environment is frozen to:

```text
EVIDENCE_OBJECTSTORE_BACKEND=s3
EVIDENCE_S3_ENDPOINT=https://evidence-objects.internal.lorawan.com:18443
EVIDENCE_S3_REGION=us-east-1
EVIDENCE_S3_BUCKET=lorawan-evidence
EVIDENCE_S3_PREFIX=lorawan-gateway-evidence
EVIDENCE_S3_CA_FILE=/run/evidence/s3/ca.crt
EVIDENCE_S3_USE_PATH_STYLE=true
```

`us-east-1` is used only as the SigV4 signing region expected by the S3-compatible endpoint; the physical SeaweedFS data center remains `sgp1`.

## Live commissioning checkpoint — 2026-08-31

Infrastructure through the host HAProxy boundary is live PASS on all three nodes. `SEAWEEDFS_CORE_3_NODE=PASS`, `SEAWEEDFS_REPLICATION_010_EMPIRICAL=PASS`, `EVIDENCE_OBJECTSTORE_TLS_BUNDLES=PASS`, and `HAPROXY_EVIDENCE_S3_3_NODE=PASS` are authoritative.

The retained replication fixture has fid `3,01e3ab96f3`, size `89`, SHA-256 `bf981516163ff1e35d6315213458423860be84f0b7fe74269ac8d780577bb5b`, and exactly two copies on distinct Droplet racks. The bucket is `lorawan-evidence` with replication `010` and volumeGrowthCount `2`.

Active identical runtime `s3.json` SHA-256 is `310aa8b74145256bae9e15f759bacfc37d590a5b54c08c348c38ea7e0c6371f8`, mode `0640 root:1000`. Ingest/collector are read/list/write; verifier is read/list only. The earlier leaked credential set is retired permanently and must not be reused.

Object-store CA SHA-256 is `c1dedc8cc6b58217e955cf763868b429dacdd933bbe7d9ffed147122e9d013fd`. The production logical endpoint is `https://evidence-objects.internal.lorawan.com:18443`. HAProxy enforces TLS >=1.2, GET/HEAD, and PUT only with exactly one `If-None-Match: *`; other methods return `405` and invalid/unconditional PUT returns `428`. Raw S3 remains loopback-only.

Full `EVIDENCE_OBJECTSTORE=PASS` is **not** yet claimed. The accepted production ingest binary is not currently staged on ulc-01/02/03, so S9 `objectstore-contract-write` plus cross-host `objectstore-contract-verify` remains the final application-contract gate.

## Hard acceptance boundary

Do not write `EVIDENCE_OBJECTSTORE=PASS` until real servers prove all of:

```text
3 Seaweed masters healthy
3 dedicated metadata-etcd voters healthy
3 volume servers present with three distinct rack labels
bucket rule = replication 010
raw S3 backend loopback-only
HAProxy TLS endpoint valid with internal CA
runtime endpoint rejects DELETE/POST/unconditional PUT
production Go helper: first create PASS
production Go helper: exact duplicate idempotent PASS
production Go helper: conflicting duplicate rejected PASS
production Go helper: concurrent create has exactly one winner PASS
exact bytes/SHA readable through another host's endpoint
```

Upstream compatibility statements are not enough; the production Go helper is the authority for the conditional-write contract used by this project.
