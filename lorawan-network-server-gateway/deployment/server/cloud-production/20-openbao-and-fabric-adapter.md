# 20. OpenBao + Fabric Adapter for the Tiny HA POC

> **Status: REQUIRED PRE-TEST SETUP / DRAFT despite file number 20.** For the full-feature POC, OpenBao and both reviewed Fabric adapter workers must be commissioned on their **normal path before Phase 15**. If the adapter implementation/image is still absent, Phase 14B is `BLOCKED`; do not begin counted chaos testing with an intentionally incomplete architecture.

## 20.1 Goal

Keep the future security/integration **shape** in the POC without creating another database server.

Our side owns:

```text
lorawan_telemetry.fabric_outbox
Fabric adapter-1/2
OpenBao Transit KMS
integration credentials
submission/reconciliation logic
```

The external Fabric team owns its Fabric network, Gateway endpoint, organizations, channel, and chaincode.

## 20.2 Placement

```text
ha-01
  OpenBao-1
  Fabric adapter-1

ha-02
  OpenBao-2
  Fabric adapter-2

ha-03
  OpenBao-3
```

The outbox is not on `ha-03`. It is a table in `lorawan_telemetry` on the **three-member Patroni PostgreSQL cluster**.

That means a PostgreSQL primary change automatically carries the outbox with the rest of the database state.

## 20.3 Architecture

```text
ChirpStack event
      |
      v
   Node-RED
      |
      | one PostgreSQL transaction
      +--------------------------+
      |                          |
      v                          v
telemetry row              fabric_outbox row
                                 |
                         +-------+-------+
                         |               |
                         v               v
                    adapter-1       adapter-2
                      ha-01           ha-02
                         \               /
                          +------+------+
                                 |
                                 v
                    openbao-kms.internal
                          HAProxy :18200
                                 |
                +----------------+----------------+
                |                |                |
                v                v                v
            OpenBao-1        OpenBao-2        OpenBao-3
                \                |                /
                 +--------- Raft quorum 2 -------+
                                 |
                         Transit sign/verify
                                 |
                                 v
                       external Fabric Gateway
                                 |
                                 v
                       channel + chaincode
                                 |
                       commit status / tx ID
                                 |
                                 v
                         update fabric_outbox
```

## 20.4 Database path

Both adapters use their host-local database route:

```text
Fabric adapter
  -> PgBouncer :6432
  -> HAProxy :15432
  -> current Patroni primary :5432
  -> lorawan_telemetry
  -> telemetry.fabric_outbox
```

Do not give the adapters a fixed PostgreSQL node IP.

## 20.4A Prepared OpenBao-only parallel subphase

The OpenBao infrastructure itself has no physical-gateway dependency. While Phase 11 is compiling, the three-node KMS may be commissioned independently by following [20A. OpenBao Three-Node HA Deployment Runbook](20a-openbao-three-node-ha-deployment.md). This does **not** advance the Fabric adapter or full Phase 20 pass: outbox integration, adapter deployment, and one real Fabric commit still wait for their own prerequisites.

The prepared cloud pin is OpenBao `2.6.2` at OCI index digest `sha256:11fd73a2102cda9c55d5d881a8c3210303146a7ec1e8ac76f526e175c6d24641` (`linux/amd64` manifest `sha256:e29524ba7c3f20d01f562c481e3eccbad6c91df45a2f2531433da4951e408cff`). Normal-path setup ends after 3/3 Raft health, private TLS, Transit key/policy, HAProxy `:18200`, and one harmless sign/verify. Member-loss and quorum-loss remain Phase 15 tests.

## 20.5 OpenBao POC cluster

Use [../fabric-attestation/01-deploy-openbao-kms.md](../fabric-attestation/01-deploy-openbao-kms.md) as the detailed OpenBao command/config reference, but apply this **cloud POC mapping** instead of copying its larger production example blindly:

```text
OpenBao node count:       3, not 5
OpenBao-1:                ha-01
OpenBao-2:                ha-02
OpenBao-3:                ha-03
API:                      private TLS :8200
Raft/cluster:             private :8201
adapter stable endpoint:  openbao-kms.internal.lorawan.com:18200 on ha-01/02 HAProxy
server SAN:               openbao-kms.internal.lorawan.com + node private name/IP
```

Bootstrap step-by-step:

1. install the same pinned OpenBao version/config pattern on all three hosts;
2. configure Integrated Storage/Raft with each node's unique `node_id`, `api_addr`, and `cluster_addr`;
3. install node-specific TLS key/certificate plus the common internal CA;
4. start **OpenBao-1 only** and initialize the cluster exactly once;
5. move the recovery/unseal material immediately to its protected off-node location;
6. unseal OpenBao-1 and record the initial Raft state;
7. start OpenBao-2 and join it to the existing Raft cluster—never initialize it separately;
8. unseal OpenBao-2 and verify it appears in `bao operator raft list-peers`;
9. repeat for OpenBao-3;
10. verify all three members are initialized, unsealed, and one is active;
11. enable/configure the Transit engine and create/verify the non-exportable `lorawan-evidence` key under the approved policy;
12. only now enable the HAProxy `:18200` frontend from [07-haproxy-and-pgbouncer.md](07-haproxy-and-pgbouncer.md);
13. call `/v1/sys/health?standbyok=true` and a harmless Transit sign/verify through the stable endpoint;
14. record the healthy 3/3 Raft peer/seal state and stable-endpoint sign/verify evidence;
15. keep all three members running while proceeding to adapters.

**Stop here** if any node was initialized as a separate cluster, if fewer than three intended members are visible, or if HAProxy treats a sealed node as healthy. **Do not stop an OpenBao member in setup; the 2/3 survival test belongs to Phase 15.**

Use three Integrated Storage/Raft members:

```text
OpenBao-1 ha-01
OpenBao-2 ha-02
OpenBao-3 ha-03
quorum = 2
```

Private ports:

```text
8200  OpenBao API/TLS
8201  OpenBao Raft
18200 HAProxy stable adapter-facing KMS endpoint
```

The pre-test setup must demonstrate:

```text
3/3 healthy/unsealed
Transit key exists and is non-exportable
stable :18200 endpoint is healthy
adapter identity can sign/verify through the stable endpoint
fixed canonicalization/digest vectors pass
```

The one-member-loss / 2-of-3 KMS survival experiment is reserved for Phase 15.

The evidence signing key stays non-exportable. An adapter never falls back to a local signing key.

## 20.6 Outbox

Create the outbox inside the Timescale-enabled `lorawan_telemetry` database on the Patroni cluster. Keep `telemetry.fabric_outbox` as an **ordinary PostgreSQL table** with the documented lease, index, permission, and immutability rules; do not convert the work queue itself into a hypertable. The telemetry event tables in the same database remain Timescale hypertables.

Required POC behavior:

```text
BEGIN
  write telemetry using stable event identity
  create selected outbox row
COMMIT
```

Then the adapters process the outbox asynchronously.

Why: Fabric or KMS downtime should make the queue wait, not make sensor telemetry disappear.

## 20.7 Two workers

```text
ha-01 -> adapter-1
ha-02 -> adapter-2
```

Both use different `worker_id` values and lease-based claims.

Normal-path setup must prove the two workers use distinct `worker_id` values and cannot simultaneously own the same live lease. Keep both workers running. A timeout after Fabric submission must be reconciled before retrying so the POC does not demonstrate duplicate conflicting submissions.

Adapter-1 loss, lease expiry/reclaim by adapter-2, and worker failover are Phase 15 tests.

## 20.8 External Fabric handoff

Follow [../fabric-attestation/01-collect-external-fabric-handoff.md](../fabric-attestation/01-collect-external-fabric-handoff.md) and collect these real values from the other team:

```text
<FABRIC_GATEWAY_ENDPOINT>
<FABRIC_GATEWAY_PORT>
<FABRIC_TLS_SERVER_NAME>
<FABRIC_MSP_ID>
<FABRIC_CHANNEL_NAME>
<FABRIC_CHAINCODE_NAME>
submit function
query function
commit-status behavior
CA certificate
client identity
```

Do not deploy a Fabric test network on these three Droplets.

## 20.8A Adapter implementation readiness gate

The detailed outbox/adapter reference currently states that this repository **does not yet contain a completed reviewed Fabric adapter image**. `<PINNED_FABRIC_ADAPTER_IMAGE>` is therefore an unresolved implementation input, not a deployable image name.

Before attempting `adapter-1` or `adapter-2`, require all of these:

```text
reviewed adapter source exists
build/test procedure exists
immutable image digest exists
runtime UID/GID is known
supported Fabric SDK/version is known
outbox claim/reconcile implementation matches the documented schema
OpenBao Transit client behavior is implemented
external Fabric handoff test vector passes
```

Then follow [../fabric-attestation/02-create-outbox-and-adapter.md](../fabric-attestation/02-create-outbox-and-adapter.md), substituting the cloud endpoints:

```text
lab DB host telemetry-db:5432
  -> cloud pgbouncer.internal.lorawan.com:6432 / lorawan_telemetry

lab OpenBao service openbao:8200
  -> cloud https://openbao-kms.internal.lorawan.com:18200

one lab adapter
  -> adapter-1 on ha-01 + adapter-2 on ha-02
     with different worker_id values and separate protected identities
```

**If the reviewed adapter implementation/image is still absent, stop at this gate.** The POC may still prove LoRaWAN HA, TimescaleDB/outbox durability, OpenBao HA, and the external Fabric handoff contract, but it must not claim that Fabric-adapter failover or real ledger commit has been executed.

Gateway-integrity v2 has a similar implementation gate for its reviewed ingestor/collector/verifier components. Do not turn documented v2 contracts into a claimed runtime result until those implementations exist.

## 20.9 Failure behavior

### External Fabric unavailable

```text
LoRaWAN             continues
Node-RED            continues while ha-03 is healthy
PostgreSQL telemetry continues
fabric_outbox       accumulates
adapters             wait/reconcile/retry
```

### One adapter lost

```text
other worker remains
expired jobs can be reclaimed
outbox remains in PostgreSQL HA cluster
```

### One OpenBao member lost

```text
2/3 quorum remains
KMS endpoint remains usable
```

### ha-03 lost

```text
Node-RED + Grafana pause
PostgreSQL stays available on ha-01/ha-02
lorawan_telemetry stays available
fabric_outbox stays available
adapter-1/2 stay alive
OpenBao remains 2/3
existing eligible outbox work can continue
```

This is a stronger POC shape than keeping the outbox in a single standalone telemetry database.

## 20.10 Minimal monitoring

For this POC, command-line evidence is enough:

```text
OpenBao member/raft status
sealed/unsealed state
Transit sign/verify result
fabric_outbox counts by status
oldest pending age
adapter-1/2 logs
worker_id and lease owner
Fabric tx ID / commit status
```

Do not deploy a large monitoring stack solely for this integration proof.

## 20.11 POC backup

Before destructive tests keep:

```text
lorawan_telemetry logical dump
OpenBao Raft snapshot or documented rebuild/recovery material appropriate to the test
OpenBao recovery/unseal material outside the runtime hosts
Fabric handoff metadata
adapter configuration/image reference
```

Production backup/retention is not what this POC is trying to certify.

## 20.12 Pre-test setup order

```text
1. confirm Phase 12A telemetry + fabric_outbox atomic commit and retry safety
2. deploy OpenBao 3/3
3. prove Transit sign/verify through :18200 with the non-exportable key
4. run the fixed RFC 8785 canonicalization vector
5. calculate SHA-256 over the exact canonical UTF-8 bytes and verify the expected digest
6. validate the external Fabric handoff and TLS identity
7. complete the adapter implementation readiness gate

IF adapter image/source is still missing:
  8. set Phase 14B = BLOCKED
  9. do not start Phase 15 counted tests

IF adapter is available and reviewed:
  8. deploy adapter-1 on ulc-01 and adapter-2 on ulc-02 with unique worker IDs
  9. prove live-lease exclusivity while both remain healthy
  10. select one staging outbox event
  11. build the fixed evidence projection
  12. RFC 8785 canonical JSON -> exact UTF-8 bytes -> SHA-256 digest
  13. OpenBao Transit signs the exact canonical bytes and the adapter stores the versioned seal
  14. submit the compact digest/signature attestation to external Fabric
  15. wait for commit status and write the tx ID/result back to the outbox
  16. run the adapter's read-only digest reconstruction/signature verification check
  17. keep OpenBao, both adapters, and Fabric connectivity healthy for Phase 13B backup
```

Do **not** remove an OpenBao member, stop an adapter, or block Fabric connectivity here. Those are Phase 15 experiments.

## 20.13 Pass condition

### Pre-test architecture/infrastructure pass

Require:

- outbox lives in `lorawan_telemetry` on the Patroni cluster;
- TimescaleDB remains inside that Patroni cluster;
- Node-RED atomically creates telemetry + selected outbox work;
- OpenBao is 3/3 healthy/unsealed through the stable endpoint;
- the Transit key is non-exportable;
- RFC 8785 canonicalization and SHA-256 fixed vectors pass;
- external Fabric handoff is complete and TLS identity is verifiable.

### Full pre-test Fabric execution pass

Claim this **only when a reviewed adapter implementation/image exists** and all are proven on the healthy path:

- adapter-1/2 have different worker IDs and cannot own the same live lease;
- the selected event is converted to the fixed canonical evidence projection;
- the locally stored SHA-256 digest matches the exact canonical bytes;
- OpenBao signs/verifies the same canonical bytes and the versioned signature/key ID are persisted;
- a real selected event reaches valid external Fabric commit status;
- the returned Fabric tx ID/status is recorded in the outbox;
- read-only reconstruction can re-create the digest and verify the stored seal;
- both adapter workers remain healthy for the final Phase 13B snapshot.

If the adapter is unavailable, the full-feature **pre-test commissioning gate is BLOCKED**. Do not substitute Node-RED, invent an adapter, or begin counted Phase 15 tests. Adapter loss, OpenBao member loss, Fabric outage/backlog, and reconcile/drain behavior are proven later in Phase 15.

Next required checkpoint: **Phase 13B** in [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md), then Phase 14 and Phase 14B.
