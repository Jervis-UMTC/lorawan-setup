# SeaweedFS — Operator Manual

## What this technology does

SeaweedFS stores the immutable/raw gateway-evidence objects that the verifier reopens later. PostgreSQL keeps metadata, hashes, references, leases, and verification state; SeaweedFS keeps the retained byte objects those records point to.

The commissioned object store is part of the evidence trust path. It is **not** scratch storage and it must not be cleared when telemetry tables are reset for a new research epoch.

## Current commissioned topology

SeaweedFS OSS 4.41 is deployed on all three cloud hosts. Each Droplet is one SeaweedFS rack inside the same `sgp1` data center.

```text
ULC-01 10.104.0.2 -> metadata-etcd + SeaweedFS master/volume/filer/S3
ULC-02 10.104.0.4 -> metadata-etcd + SeaweedFS master/volume/filer/S3
ULC-03 10.104.0.8 -> metadata-etcd + SeaweedFS master/volume/filer/S3

metadata-etcd client/peer   12379 / 12380
master HTTP/gRPC           19333 / 19334
volume HTTP/gRPC           18082 / 18083
filer HTTP/gRPC            18888 / 18889
raw S3 backend             127.0.0.1:18333
S3 gRPC                    18334
TLS/create-only frontend   node VPC :18443
logical endpoint           evidence-objects.internal.lorawan.com:18443
bucket                     lorawan-evidence
placement                  010
```

Placement `010` means one additional copy in another rack in the same data center. Because each Droplet is modeled as a different rack, an acknowledged raw object has two host copies.

SeaweedFS uses a **separate** three-member metadata-etcd cluster on `12379/12380`. Never point the filer at the Patroni DCS etcd on `2379/2380`.

## Current protected layout

```text
/etc/lorawan-cloud/seaweedfs/release.env
/etc/lorawan-cloud/seaweedfs/host.env
/etc/lorawan-cloud/seaweedfs/filer.toml
/etc/lorawan-cloud/seaweedfs/s3.json
/etc/lorawan-pki/evidence-objectstore/
/srv/seaweedfs/metadata-etcd
/srv/seaweedfs/master
/srv/seaweedfs/volume

containers:
  seaweedfs-metadata-etcd
  seaweedfs
```

Do not print or copy live S3 credentials from `s3.json`.

## Security and immutability boundary

The evidence services do not connect directly to the raw S3 listener. The raw S3 listener stays loopback-only on `127.0.0.1:18333`.

Applications use the TLS endpoint on `:18443`, where HAProxy enforces:

```text
GET / HEAD                         allowed
PUT with exact If-None-Match: *   allowed
unconditional PUT                 denied
POST                              denied
DELETE                            denied
other methods                     denied
```

Ingest and collector identities can read/list/create evidence objects. The verifier is read/list only. No runtime identity receives SeaweedFS administration authority.

## Step 1 — Check both containers on every host

Run on ULC-01, ULC-02, and ULC-03:

```bash
sudo docker ps   --filter 'name=seaweedfs-metadata-etcd'   --filter 'name=seaweedfs'   --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'

sudo docker inspect seaweedfs-metadata-etcd seaweedfs   --format '{{.Name}} status={{.State.Status}} restarts={{.RestartCount}}'
```

**PASS means:** both containers are running on every host and neither is in a restart loop.

A running process alone is not enough; continue through metadata quorum, listener, and object-store checks.

## Step 2 — Verify the custom listener map

```bash
sudo ss -lntp | grep -E ':(12379|12380|19333|19334|18082|18083|18888|18889|18333|18334|18443)\b'
```

**PASS means:**

- metadata-etcd and Seaweed core ports are present on the intended private/loopback addresses;
- raw S3 `:18333` is loopback-only;
- HAProxy `:18443` is the service-facing TLS endpoint on the node VPC address.

Do not change the ports to generic Seaweed defaults. The custom allocation avoids existing service collisions.

## Step 3 — Verify the separate metadata-etcd member

```bash
sudo docker exec -e ETCDCTL_API=3 seaweedfs-metadata-etcd   etcdctl --endpoints=http://127.0.0.1:12379 endpoint health

sudo docker exec -e ETCDCTL_API=3 seaweedfs-metadata-etcd   etcdctl --endpoints=http://127.0.0.1:12379 member list -w table
```

**PASS means:** the local endpoint is healthy and the common cluster view contains the intended three members.

Do not repair this cluster with the Patroni etcd data directory, cluster token, or peer set.

## Step 4 — Verify the effective replication arguments

```bash
sudo docker inspect seaweedfs --format '{{json .Config.Cmd}}'   | tr ',' '\n'   | grep -E 'defaultReplication|defaultReplicaPlacement|dataCenter|rack'
```

**PASS means:** the effective command still carries replication `010`, the expected data center, and the node-specific rack identity.

A directory existing on two hosts is not equivalent to proven object-store replication.

## Step 5 — Verify the TLS/create-only frontend

Inspect the certificate and perform a bounded server-auth TLS check with the commissioned CA:

```bash
openssl s_client   -connect evidence-objects.internal.lorawan.com:18443   -servername evidence-objects.internal.lorawan.com   -verify_hostname evidence-objects.internal.lorawan.com   -verify_return_error   -CAfile /etc/lorawan-pki/evidence-objectstore/ca.crt   </dev/null 2>/dev/null   | grep -E 'Verify return code|subject=|issuer='
```

**PASS means:** hostname and chain validation succeed. Do not use `-k` or disable certificate verification.

The commissioned S9 create/idempotency/race/cross-host contract has already passed. Do **not** create new commissioning objects merely to prove a documentation change.

## Step 6 — Check storage and recent logs

```bash
df -h /srv/seaweedfs
sudo du -sh /srv/seaweedfs/metadata-etcd /srv/seaweedfs/master /srv/seaweedfs/volume
sudo docker logs --since=15m --tail=120 seaweedfs-metadata-etcd
sudo docker logs --since=15m --tail=160 seaweedfs
```

Look for quorum loss, master/filer membership churn, volume errors, write failures, corruption warnings, OOM/restart events, or sustained disk pressure.

Do not delete retained evidence objects or commissioning fixtures to solve disk usage without an explicit retention/recovery decision.

## Step 7 — Verify application-facing object-store readiness

The normal evidence-service configuration is:

```text
EVIDENCE_OBJECTSTORE_BACKEND=s3
EVIDENCE_S3_ENDPOINT=https://evidence-objects.internal.lorawan.com:18443
EVIDENCE_S3_BUCKET=lorawan-evidence
EVIDENCE_S3_PREFIX=lorawan-gateway-evidence
```

Use the Gateway Evidence Services manual to prove ingest/collector/verifier `/readyz` state. Their readiness checks include the object-store dependency and are the preferred non-destructive application-level proof.

If all Seaweed containers are healthy but those services report object-store failure, inspect CA trust, HAProxy `:18443`, local name mapping, role credentials, and method policy before changing Seaweed data.

## Safe configuration change procedure

1. Prove all three metadata-etcd members and all three Seaweed containers are healthy.
2. Record current image IDs and effective arguments.
3. Back up the exact configuration being changed.
4. Change one node at a time.
5. Validate the Compose/configuration model before recreate.
6. Preserve metadata quorum and a healthy raw-object copy throughout.
7. Verify local listeners and metadata membership.
8. Verify `:18443` TLS.
9. Verify evidence-service readiness.
10. Re-run the destructive/empirical S9 object contract only when a storage change actually requires re-acceptance.

Do not restart all three storage members together for an ordinary configuration edit.

## Backup and recovery rules

Replication is availability, not a complete backup policy. Preserve protected deployment/configuration, metadata-etcd recovery material using its reviewed snapshot procedure, retained raw evidence, PostgreSQL evidence metadata that references those objects, and the internal object-store CA/required service identities.

Do not copy a live etcd data directory as a substitute for a consistent snapshot. Do not restore PostgreSQL metadata without considering the matching retained raw objects.

## Troubleshooting map

| Symptom | First check |
|---|---|
| both containers down on one host | Docker/runtime, protected env/config, disk, image |
| metadata-etcd unhealthy | separate `12379/12380` quorum and peer reachability |
| Seaweed up but application S3 fails | `:18443` HAProxy/TLS/name mapping/role credentials |
| raw S3 reachable on non-loopback | security regression; fix bind immediately |
| evidence object missing | object reference, replication/member health, retained object; do not fabricate replacement |
| DB metadata exists but verifier cannot read bytes | object-store reachability/hash/reference before verifier code |
| disk pressure | retained-object growth and volume capacity; do not delete evidence casually |
| only one host has object | replication/placement investigation before accepting new evidence writes |

## Completion checklist

- `seaweedfs-metadata-etcd` and `seaweedfs` are running on all three hosts;
- metadata-etcd shows the intended three-member cluster;
- custom port map is intact;
- raw S3 remains loopback-only;
- HAProxy `:18443` passes TLS hostname verification;
- effective placement remains `010`;
- no immediate storage/quorum/restart errors exist;
- evidence-service readiness passes;
- retained raw evidence and commissioning fixtures remain intact.

## Complete raw-object storage and protected recovery companion

Use [SeaweedFS cross-host raw evidence, custom port map, create-only S3, replication and restore](SEAWEEDFS-EVIDENCE-STORE-RECOVERY.md). It distinguishes two host copies in one data center from off-site backup, and the runtime create-only endpoint from a universal legal WORM property.

## Detailed references

- [`../../evidence-services/cloud/deploy/seaweedfs/README.md`](../../evidence-services/cloud/deploy/seaweedfs/README.md)
- [`../../evidence-services/cloud/deploy/seaweedfs/01-live-commissioning.md`](../../evidence-services/cloud/deploy/seaweedfs/01-live-commissioning.md)
- [`../server/integrations/gateway-integrity/06-replicated-ha-deployment-journey.md`](../server/integrations/gateway-integrity/06-replicated-ha-deployment-journey.md)
