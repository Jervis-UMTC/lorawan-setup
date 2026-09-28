# 20. OpenBao + Fabric Adapter for the Tiny HA POC

> **Status: ULC-01 TASK-37 EXTERNAL QUALIFICATION PASS.** Three-node OpenBao, audit, `telemetry.fabric_outbox`, the Fabric-adapter runtime, database authentication, and the HRC Task 37 handoff are commissioned. HRC `hrc-evidence` v1.1 / sequence 2 is live-qualified and the frozen API is `CreateSourceBoundAnchor(SourceRecordID, sourceType, producer, producedAt, schemaVersion)` with exact payload only in transient `hrc.exact_payload`, followed by `QuerySourceBoundAnchor(SourceRecordID)` and `VerifySourceBoundDigest(SourceRecordID, observedDigest)`. On 2026-09-08 ULC-01 completed the explicitly authorized one-record qualification for outbox `1960` / SourceRecordID `fdadcf14-741e-4293-ad38-39ba89369ea7`. The exact 2828-byte payload SHA-256 was `827e443857118c0f922c2f03e66f950a79092c74d8d8b947d489ace43d157b51`; the resulting Fabric transaction ID is `dd11910c1e7c28edd11334a03cce10d80d574692733458c9059d2775be5131b8` and the stored HRC record ID is `hrc-record-ad1258ae5ee243c01d1e091c684df1c950589bcbcde820d736a257f8cd052bfb`. The one-shot runner reached `confirmed` only after durable prepared-transaction/commit-status state, authoritative commit success, `QuerySourceBoundAnchor` field matching, and `VerifySourceBoundDigest=MATCH`; the final outbox state is `confirmed`, `attempts=1`. Two defects encountered before the successful write were corrected without producing a duplicate Fabric proposal: the common outbox `finish()` helper now types nullable SQL parameters explicitly, and the expired ULC-01 OpenBao SecretID was refreshed using the current active OpenBao member (`10.104.0.4`) after audit evidence showed that SecretID issuance against a standby can fail persistence with read-only storage. The existing AppRole role/policy, Transit key, RoleID, Fabric identity, channel, chaincode, and source binding were not changed. As re-verified on 2026-09-09, Adapter-1 on ULC-01 is now the continuous production writer with `FABRIC_ADAPTER_ENABLED=true`; the authoritative activation preflight passes and 325 post-activation outbox records have reached `confirmed` on Fabric. The live image is `sha256:d12e73ae24f7823730b6632fe8209e844c0d6125bd6a9c13e9d75cc330664f74` with service-binary SHA-256 `a53990277d9032e60a9f0bfb52619a21e8c999a3573477dbfb3efe6ca6fb9591`. The one-shot qualification container was removed; temporary SSH authorization and secret-bearing qualification staging were removed. Adapter-2 on ULC-02 remains `FABRIC_ADAPTER_ENABLED=false` and must stay deferred until the lease-renewal/ownership-fencing HA gate is proven. Do not rerun candidate `1960`, use the old K3s-only `10.43.25.198:7051` endpoint, or use legacy Fabric APIs. Future AppRole credential rotation must respect the role's 24-hour SecretID TTL and issue against the current active OpenBao member.

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

## 20.7 Fabric writer ownership and HA target

```text
ULC-01 / adapter-1 -> ENABLED production writer
ULC-02 / adapter-2 -> INSTALLED but FABRIC_ADAPTER_ENABLED=false
```

Both candidates have distinct worker identities, but lease-based row claiming alone is not sufficient proof that two processes may safely own an external Fabric side effect. The commissioned normal path therefore keeps only ULC-01 enabled. ULC-02 must remain fail-closed until the separate ownership/fencing and failover acceptance gate proves that at most one writer can submit/reconcile externally at a time.

A timeout after Fabric submission enters durable reconciliation using the already-prepared transaction and signed commit-status request; it is not permission to generate a fresh transaction. ULC-01 loss and deliberate ULC-02 takeover remain a later HA acceptance test.

## 20.8 External Fabric handoff

For a new environment, follow [../fabric-attestation/01-collect-external-fabric-handoff.md](../fabric-attestation/01-collect-external-fabric-handoff.md) and collect the real values from the other team. For this commissioned HRC environment, the handoff is already complete: private Gateway `10.104.0.7:7051`, TLS name `peer1.hrc.local`, MSP `HrcMSP`, channel `hrc-channel`, chaincode `hrc-evidence`, empty/default contract, and source identity `lorawan-gateway-evidence`.

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

## 20.8A Historical server-first security readiness — commissioning complete

The adapter implementation gate below does **not** prevent independent preparation that requires no gateway hardware and no Fabric worker runtime.

The block below records the pre-activation gate that was used before Fabric credentials existed. It is retained for rebuild/recovery context and is not a statement that credentials are still absent:

```text
OpenBao 3/3 healthy/unsealed through the stable :18200 endpoint
OpenBao audit-device state explicitly inspected and a reviewed audit path commissioned
fabric-adapter SecretID accessor count remains zero while no runtime exists
Node-RED selected-event atomic telemetry + outbox enqueue proven with the isolated synthetic fixture
frozen telemetry-attestation-v1 canonical-byte fixture hash reproduces exactly
expected v1 SHA-256 = c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c
```

The frozen v1 canonical string is already committed in `../integrations/hyperledger-fabric/04-data-contract-and-chaincode.md`. Reproducing its exact SHA-256 is safe now and proves the byte fixture has not drifted. A true RFC 8785 **canonicalizer implementation** still belongs to the reviewed adapter/runtime and must pass the same vector at startup; hashing the already-frozen canonical string is not a substitute for that implementation test.

OpenBao auditing is part of the **signing** trust boundary. The Fabric security/incident-response manuals depend on KMS audit evidence to establish a possible unauthorized-signing window. The current cloud execution history does not record a commissioned audit device, so inspect that state and close the gap before releasing any signing workload credential. This does **not** block the gateway/security evidence ingest, collector, verifier, trusted-decoder, storage, or database implementation because those services hold no OpenBao/Fabric signing authority. Keep audit storage protected and separate from Raft data, use bounded host-side rotation, and avoid casually disabling/re-enabling an audit device because that destroys its existing salt/HMAC continuity.

**Current commissioned state:** the pre-activation gate is complete. ULC-01 is the enabled production writer and uses the commissioned least-privilege OpenBao/Fabric identity; ULC-02 retains protected standby material but remains `FABRIC_ADAPTER_ENABLED=false`. Do not copy one worker's SecretID or Fabric private identity to the other host, and do not enable ULC-02 until the HA ownership/fencing gate passes.

## 20.8B Adapter implementation readiness gate

The Fabric adapter implementation, immutable runtime image, HRC Task 37 handoff, qualification transaction, and ULC-01 continuous-writer activation are commissioned. The current recorded ULC-01 image is `sha256:d12e73ae24f7823730b6632fe8209e844c0d6125bd6a9c13e9d75cc330664f74`. ULC-02 remains the deliberately write-disabled standby. The remaining Fabric infrastructure gate is ULC-02 ownership/fencing failover acceptance, not another external handoff.

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
  -> ULC-01 adapter-1 enabled in production
  -> ULC-02 adapter-2 installed with a separate protected identity but write-disabled until HA fencing acceptance
```

The adapter implementation/image gate is now **PASS**. Keep the workers in fail-closed standby until the external Fabric Gateway endpoint/TLS identity, MSP client identity, channel/chaincode/contract/function values are installed and `fabric-adapter-enable-preflight.sh` passes. Until that handoff is complete, do not claim a real ledger transaction or Fabric-adapter failover acceptance.

Gateway-integrity v2 has passed its implementation gate: reviewed ingest/collector/verifier/trusted-decoder components and the evidence storage path are commissioned, with real Gateway-01 lineage accepted. Keep Fabric activation independent from that evidence lane; evidence readiness is not permission to release Fabric signing credentials.

## 20.9 Failure behavior

### External Fabric unavailable

```text
LoRaWAN             continues
Node-RED            continues on the current active host; standby remains stopped
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
Node-RED A is lost; after fencing, Node-RED B on ha-02 is promoted
Grafana pauses
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

Steps 1-7 and the ULC-01 activation path below are already commissioned on the current build. For a future rebuild, re-run only the relevant gates. Do not treat this sequence as permission to enable ULC-02:

  8. deploy/validate adapter-1 on ULC-01; keep adapter-2 on ULC-02 write-disabled
  9. require immutable `finalized_payload`; for v2 require verifier-owned `verified` state
  10. build/verify the separate local RFC 8785/OpenBao evidence seal
  11. compute SHA-256 over the exact immutable `finalized_payload` bytes for HRC
  12. prepare `CreateSourceBoundAnchor` with five metadata args + transient `hrc.exact_payload`
  13. persist txid, record_id, endorsed transaction bytes, and signed commit-status request before orderer submit
  14. submit the already-prepared transaction
  15. require authoritative commit status
  16. require `QuerySourceBoundAnchor` field match + `VerifySourceBoundDigest=MATCH`
  17. keep ULC-01/OpenBao/Fabric healthy; test ULC-02 takeover only under the explicit HA gate
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

- ULC-01 adapter-1 is the enabled writer and ULC-02 adapter-2 remains write-disabled until HA ownership/fencing is accepted;
- the selected event is converted to the fixed canonical evidence projection;
- the locally stored SHA-256 digest matches the exact canonical bytes;
- OpenBao signs/verifies the same canonical bytes and the versioned signature/key ID are persisted;
- a real selected event reaches valid external Fabric commit status;
- the returned Fabric tx ID/status is recorded in the outbox;
- read-only reconstruction can re-create the digest and verify the stored seal;
- ULC-01 remains healthy as the writer and ULC-02 remains healthy-but-write-disabled for the final recovery snapshot.

The adapter runtime itself is no longer unavailable: both immutable workers are deployed and internally commissioned. Real Fabric execution remains **externally gated** until the other Fabric system supplies its Gateway/TLS/MSP/channel/chaincode/function handoff and a real transaction can be committed and queried. Do not substitute a mock ledger for that final acceptance. Adapter loss, OpenBao member loss, Fabric outage/backlog, and reconcile/drain behavior are proven later when a real Fabric target exists.

Next required checkpoint: **Phase 13B** in [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md), then Phase 14 and Phase 14B.
