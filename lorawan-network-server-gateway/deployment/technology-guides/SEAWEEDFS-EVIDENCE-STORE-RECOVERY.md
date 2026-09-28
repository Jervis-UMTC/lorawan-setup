# SeaweedFS — Three-Host Raw Evidence Storage, Create-Only Ingest and Recovery

**Scope:** the actual gateway-evidence S3-compatible store, not general scratch storage. Read [SeaweedFS operator guide 13](13-seaweedfs.md). This chapter consolidates the commissioned reproducibility and recovery boundary; the current running roles and capacity should be checked before any service change. It is not a new object-race or destructive restore test.

## 1. Why object storage is not optional for verified evidence

The gateway journal contains original event observations; the cloud retains exact raw segment/checkpoint and MQTT-witness objects in SeaweedFS. PostgreSQL `gateway_evidence` stores *references, hashes, receipts and verification outcomes*. A database-only restore with absent/mismatched object bytes cannot recreate truth by hand. SeaweedFS stores retained bytes, while independent verifier reopens and hashes them. Ordinary Node-RED telemetry may continue when object storage is down, but a new event must **not** be described as fully gateway-verified until the required evidence is available.

## 2. Pinned deployed architecture

| Item | Commissioned baseline |
|---|---|
| Data center / “rack” | All hosts in `sgp1`; rack=`ulc-01`/`ulc-02`/`ulc-03` (one Droplet per rack) |
| SeaweedFS image | OSS 4.41, `chrislusf/seaweedfs:4.41@sha256:43b768cd62b00d132439cda881b93fd1adebf1b315e996e794087743821d771d` |
| Independent metadata-etcd | `quay.io/coreos/etcd:v3.5.15@sha256:0934690612905554eb61ddefb9faaaecb47c2f6931dbb453e694358092ee8990` |
| Metadata quorum | separate 3-voter `swmeta-*` at private TCP `12379/12380`, *not* Patroni etcd `2379/2380` |
| Seaweed master | HTTP `19333` / gRPC `19334` |
| Seaweed volume | HTTP `18082` / gRPC `18083` |
| Seaweed filer | HTTP `18888` / gRPC `18889` |
| Raw S3 | `127.0.0.1:18333` only; no app access |
| Service endpoint | `https://evidence-objects.internal.lorawan.com:18443`; node-private HAProxy terminates TLS and gates methods |
| Bucket/prefix | `lorawan-evidence` / `lorawan-gateway-evidence` |
| Placement | `010` = one extra copy on a different modeled rack; acknowledged object **two host copies**, not independent geographical regions |
| Resource envelope | All-in-one SeaweedFS 256 MiB cap / `GOMEMLIMIT=220MiB`; metadata-etcd 96 MiB cap; initial new-host preflight >=600 MiB available and >=5 GiB free |
| Persistent paths | `/srv/seaweedfs/metadata-etcd`, `/srv/seaweedfs/master`, `/srv/seaweedfs/volume` |

Releases before 4.30 are disallowed by the project's security selection because of a fixed S3 cross-bucket path-traversal vulnerability. Do not silently downgrade while recovering a host.

## 3. Local and protected files

~~~text
/evidence-services/cloud/deploy/seaweedfs/    (tracked: compose.yml, release example,
  hosts/*.env.example, filer.toml, s3.json.example,
  haproxy-evidence-s3.cfg.example, preflight.sh)
/etc/lorawan-cloud/seaweedfs/release.env      (root:root 0600)
/etc/lorawan-cloud/seaweedfs/host.env         (root:root 0600)
/etc/lorawan-cloud/seaweedfs/filer.toml       (root:root 0644)
/etc/lorawan-cloud/seaweedfs/s3.json          (root:1000 0640; contains credentials)
/etc/lorawan-pki/evidence-objectstore/        (public CA + protected node HAProxy leaf/key)
/srv/seaweedfs/{metadata-etcd,master,volume}  (persistent host storage)
~~~

The actual runtime reads `release.env`/`host.env`; the examples **are not** production identities. Preserve host-specific rack names, data-center placement and private listener map. Do not paste `s3.json` or access keys into command output, research capture or PDF.

## 4. Safe read-only health checks (each Ubuntu ULC)

~~~bash
hostname -f
date -u
sudo docker ps --filter 'name=seaweedfs' --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
sudo docker inspect seaweedfs-metadata-etcd seaweedfs --format '{{.Name}} status={{.State.Status}} restarts={{.RestartCount}}'
sudo ss -lntp | grep -E ':(12379|12380|19333|19334|18082|18083|18888|18889|18333|18334|18443)\b' || true
df -h /srv/seaweedfs
sudo du -sh /srv/seaweedfs/metadata-etcd /srv/seaweedfs/master /srv/seaweedfs/volume
~~~

Confirm each node's bound addresses, not just port numbers: raw `:18333` must be **loopback** while `:18443` is the reviewed private VPC endpoint. On the local metadata-etcd member:

~~~bash
sudo docker exec -e ETCDCTL_API=3 seaweedfs-metadata-etcd \
 etcdctl --endpoints=http://127.0.0.1:12379 endpoint health
sudo docker exec -e ETCDCTL_API=3 seaweedfs-metadata-etcd \
 etcdctl --endpoints=http://127.0.0.1:12379 member list -w table
sudo docker inspect seaweedfs --format '{{json .Config.Cmd}}'
~~~

**PASS:** 3 metadata members visible, correct private peer identities, `defaultReplication`/`defaultReplicaPlacement` equivalently `010`, correct `dataCenter`/unique rack and no error loop. A healthy metadata-etcd alone does not prove raw S3 policy or two actual object copies. Prefer existing accepted object inventory/readiness for non-destructive check.

## 5. Understand the security boundary precisely

SeaweedFS S3 IAM `Write` can include delete-capable operations, so this project places the runtime behind an HAProxy **create-only** gate, separate from the raw loopback listener:

~~~text
GET or HEAD                  allowed
PUT with exact If-None-Match: *  allowed
unconditional PUT           denied
POST and DELETE              denied
other methods                denied
~~~

The SeaweedFS backend must itself honor conditional create-if-absent atomically under concurrent writers; the proxy's header/method check alone is **not** proof of storage atomicity. The S9 acceptance exercised create, identical retry/idempotency, conflicting write rejection, concurrent writer races and cross-host retained-object read. Preserve its original result/manifest; do not generate additional objects merely to audit docs. This boundary means the **application endpoint** cannot casually overwrite/delete evidence. It is **not** a universal hardware/legal WORM property: root storage administrators and physical loss remain distinct threats and require audited access/off-host backup.

Cloud role split: ingest and collector have `HeadBucket/GetObject/PutObject` on the evidence prefix; verifier has `HeadBucket/GetObject` only. Do not give the verifier delete or bucket admin. Distinct root-owned S3 credentials live outside Git. All evidence-service containers resolve the logical S3 endpoint to their **own host VPC IP** while TLS verifies `evidence-objects.internal.lorawan.com`; the raw S3 backend remains loopback only.

## 6. Controlled fresh deployment — only for an empty authorized store

1. Check all existing Patroni etcd/PostgreSQL, HAProxy frontends, gateway evidence traffic, time, VPC routes, disk and RAM; record the new-host free-port inventory. Do not assume a candidate port is free on a commissioned server.
2. Resolve/pull the approved exact two image **digests**, verify linux/amd64 and inspect startup args/UID before writing data directory owners. Use the tracked Compose and reviewed external protected host env; do not invent S3 access keys.
3. Stage **separate** metadata-etcd directories/member names and exact `12379/12380` private addresses on all three; bootstrap the new metadata cluster only when no member state already exists. **Never** point it at Patroni etcd or copy the Patroni data dir.
4. Start one metadata member per reviewed coordinated bootstrap, then obtain three-member quorum and stable filer metadata before exposing the service.
5. Stage SeaweedFS master/volume/filer/S3 with custom HTTP **and** explicit gRPC ports, unique rack, placement 010, private/loopback binds and approved resource caps. Port shortcuts can break clients: in this build the custom master `19333.19334` and filer `18888.18889` address syntax is needed where the program would otherwise infer HTTP+10000 incorrectly.
6. Create the intended bucket and **separate** runtime S3 identities/ACL, with keys protected in `/etc/lorawan-cloud/seaweedfs/s3.json`. Verify per-role read/create permissions before the evidence services become active.
7. On each host stage HAProxy `:18443` TLS and exact method/header policy as an **off-path candidate**; validate the *whole* HAProxy config and keep the original other frontends, then reload one host at a time. Never open backend `18333` publicly.
8. Check metadata quorum, current copies for a reviewed fixture, TLS hostname verification, denied unconditional PUT/DELETE, conditional create and application `/readyz`. Follow the guarded S9 acceptance only when commissioning/new storage architecture requires it. Test outputs must not overwrite previously sealed research evidence.

**Do not run the fresh installation sequence to repair one unhealthy member of an existing three-node store.** First inspect its current authoritative metadata/volume state and replica availability; restore/rejoin only that member using the reviewed recovery path.

## 7. Test TLS and applications without creating evidence

On the relevant host, with the approved readable public CA:

~~~bash
openssl s_client -connect evidence-objects.internal.lorawan.com:18443 \
 -servername evidence-objects.internal.lorawan.com \
 -verify_hostname evidence-objects.internal.lorawan.com \
 -verify_return_error \
 -CAfile /etc/lorawan-pki/evidence-objectstore/ca.crt \
 </dev/null 2>/dev/null | grep -E 'Verify return code|subject=|issuer='
~~~

Require `Verify return code: 0 (ok)` and intended SAN. Then check each evidence ingest/collector/verifier `/readyz`: that service's S3 bucket/identity/metadata checks are the preferred **application-side no-mutation proof**. TLS alone does not validate bucket, prefix or permissions.

## 8. Restore and disaster-recovery boundaries

A complete backup requires **both** the consistent independent metadata-etcd snapshot and actual retained raw object bytes/volumes, **plus** PostgreSQL evidence references/checkpoints, approved configuration, identities/CA and selected recovery time. Replication (two copies in one data center) protects a normal single-host loss; it is **not** an off-site backup, nor immunity from correlated deletion/corruption. Off-host snapshot/archive hashes and an isolated readback/restore rehearsal matter more than a filename.

For a one-host failure: preserve available quorum/two-host object copies, verify where each referenced object currently resides and replenish redundancy using reviewed volume/filer procedure. For missing bytes/hash conflicts: preserve error and evidence; do **not** fill a new object under the same key with reconstructed JSON to force `verified`. A PostgreSQL restore older than the Fabric ledger/gateway checkpoint needs explicit reconciliation; do not roll external authority backwards by restoring only SQL.

**PASS:** three metadata members, service components on all intended hosts, private/loopback bind map, placement 010, two-host retained object copies where the placement contract applies, read-only role restrictions, no forbidden mutation via :18443, healthy evidence-service dependencies and protected backups. A new S9 race test is not necessary after a Markdown-only change.

Source maintenance: [commissioned Seaweed design](../../evidence-services/cloud/deploy/seaweedfs/README.md) and [staged S0–S9 procedure](../../evidence-services/cloud/deploy/seaweedfs/01-live-commissioning.md). Print complete necessary steps in the final Word document; links are maintenance provenance only.
