# 20. OpenBao + Fabric Adapter for the Tiny HA POC

> **Status: STANDBY / DRAFT.** OpenBao and the Fabric adapter are not yet deployed or live-validated in the current cloud build. Keep this as architecture guidance until the external Fabric handoff, exact OpenBao version, adapter implementation/image, policies, and failure behavior are available.

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

## 20.5 OpenBao POC cluster

Use [../fabric-attestation/01-deploy-openbao-kms.md](../fabric-attestation/01-deploy-openbao-kms.md) as the detailed OpenBao command/config reference, but apply this **cloud POC mapping** instead of copying its larger production example blindly:

```text
OpenBao node count:       3, not 5
OpenBao-1:                ha-01
OpenBao-2:                ha-02
OpenBao-3:                ha-03
API:                      private TLS :8200
Raft/cluster:             private :8201
adapter stable endpoint:  openbao-kms.internal.<DOMAIN>:18200 on ha-01/02 HAProxy
server SAN:               openbao-kms.internal.<DOMAIN> + node private name/IP
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
14. stop one OpenBao member and prove the stable endpoint still works at 2/3;
15. restore/unseal/rejoin it before proceeding to adapters.

**Stop here** if any node was initialized as a separate cluster, if fewer than three intended members are visible before the failure test, or if HAProxy treats a sealed node as healthy.

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

The POC needs to demonstrate only:

```text
3/3 healthy/unsealed
Transit key exists
adapter can sign/verify
stop one OpenBao member
2/3 still serves sign/verify
restore 3/3
```

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

Expected:

```text
adapter-1 owns live lease
adapter-2 skips it

adapter-1 dies
lease expires
adapter-2 can reclaim
```

A timeout after Fabric submission must be reconciled before retrying so the POC does not demonstrate duplicate conflicting submissions.

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
  -> cloud https://openbao-kms.internal.<DOMAIN>:18200

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

## 20.12 Iteration order

```text
1. create lorawan_telemetry + fabric_outbox
2. prove Node-RED telemetry/outbox atomic commit and retry safety
3. deploy OpenBao 3/3
4. prove Transit sign/verify through :18200
5. remove one OpenBao member and prove 2/3
6. restore OpenBao 3/3
7. validate external Fabric handoff
8. check the adapter implementation readiness gate

IF adapter image/source is still missing:
  9. record adapter execution as BLOCKED
  10. do not claim Fabric commit/failover success

IF adapter is available and reviewed:
  9. start adapter-1 and prove one real commit
  10. start adapter-2 and prove lease behavior
  11. stop adapter-1 and prove adapter-2 takeover
  12. block external Fabric and prove telemetry still commits
  13. restore Fabric and prove outbox drains/reconciles
  14. include the path in the full ha-01/02/03 failure rehearsal
```

## 20.13 Pass condition

### Architecture/infrastructure pass

This part can pass before the adapter implementation exists:

- outbox lives in `lorawan_telemetry` on the Patroni cluster;
- TimescaleDB is enabled inside the Patroni cluster; no separate TimescaleDB server is needed;
- Node-RED can atomically create telemetry + selected outbox work;
- OpenBao is 3/3 normally and usable at 2/3;
- the Transit key is non-exportable;
- the external Fabric handoff is complete and TLS identity is verifiable;
- losing `ha-03` does not remove the PostgreSQL outbox.

### Full Fabric execution pass

Claim this **only when a reviewed adapter implementation/image exists** and all are proven:

- adapter-1/2 have different worker IDs and cannot own the same live lease;
- a real selected event reaches valid external Fabric commit status;
- uncertain submission is reconciled rather than blindly duplicated;
- adapter-1 loss is recovered by adapter-2 after valid lease expiry/reclaim;
- Fabric outage does not block telemetry commits and the outbox drains after recovery;
- the integration runs inside the same three cheap POC Droplets.

If the adapter is unavailable, report this second block as **blocked by missing implementation**, not failed architecture and not passed execution. Because this deployment target now requires **all features with no feature omission**, the overall full-feature POC/commissioning status also remains **BLOCKED** until this Full Fabric execution pass succeeds. The other HA layers may still have their own valid PASS evidence, but they do not substitute for the missing adapter runtime.

Return to [19-cloud-ha-grafana-deployment-day-runbook.md](19-cloud-ha-grafana-deployment-day-runbook.md).
