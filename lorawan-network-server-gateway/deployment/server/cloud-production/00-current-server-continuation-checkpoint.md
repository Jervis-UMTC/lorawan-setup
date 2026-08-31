# Current Server Continuation Checkpoint — 2026-08-29

> **Purpose:** this is the first file to read when continuing the current three-Droplet cloud HA build in a new chat. It summarizes the latest accepted server state and the immediate server-only continuation boundary. Detailed historical evidence remains in `00-build-execution-log.md`; component manuals remain authoritative for exact commands.

## 1. Operating scope

Current workspace:

```text
lorawan-setup/lorawan-network-server-gateway
```

Current deployment target:

```text
three-Droplet cloud HA POC / future-deployment scale model
ulc-01 = 10.104.0.2
ulc-02 = 10.104.0.4
ulc-03 = 10.104.0.8
OS      = Ubuntu Server 24.04 LTS x64
size    = 1 shared vCPU / 2 GiB / 50 GiB per host
region  = AS923 / MQTT prefix as923
```

Do not replace this topology with the separate single-VM lab manuals. Do not inject deliberate failures while setup is still incomplete.

## 2. Current continuation rule

The physical gateway is not currently accessible, so hardware-dependent work is **deferred, not failed and not complete**. Use the time to finish every server-only setup step that does not require a physical uplink or provider-owned public resource.

Current server-only Grafana staging is complete. There is no remaining Grafana server mutation to perform while the physical gateway is unavailable.

The interim **13S server-only snapshot/export and 14S evidence harness are complete** for their current scopes. Do not run another backup/export/evidence cycle merely because setup continues or a new chat starts. Node-RED atomic telemetry/outbox and Grafana server-only synthetic commissioning are also complete. Gateway/security evidence source, Go compile/test, current Linux binary locking, S3 backend source, and the reproducible three-host deployment bundle are now prepared. The current server-only task is the remaining deployment boundary: build/pin OCI images, select/prove the durable object store, apply the reviewed evidence migration with least-privilege login identities, issue Evidence PKI/read-only MQTT credentials, resolve shared `:443`, then commission the frozen replicas one logical boundary at a time. Final Phase 13B and final Phase 14 still require refresh after the real gateway/public-ingress/Fabric dependencies are commissioned. Full Phase 12A/14A RF acceptance still waits for a real EMU-01 payload-v2 event.

## 3. Commissioned server foundation — do not rebuild

The following server layers have accepted execution evidence and must not be redeployed merely because a new chat starts:

```text
etcd                                  3-member quorum commissioned
PostgreSQL / Patroni                  3-member HA cluster commissioned
PostgreSQL runtime                    18.6
TimescaleDB                           2.29.2 in lorawan_telemetry
telemetry schema                      v3; uplinks + measurements hypertables
HAProxy database routing              commissioned on all three hosts
PgBouncer                             1.22.0-1build4; TLS + SCRAM; all three hosts
Mosquitto                             redundant broker pair on ulc-01/02
Valkey + Sentinel                     3-node HA commissioned
ChirpStack                            two private application nodes commissioned
telemetry.fabric_outbox               ordinary PostgreSQL table; schema/ACL/immutability PASS
Phase 13A fast backup                 PASS including off-host SHA-256 verified copy
Phase 13S server-only package         PASS; local full-manifest/archive verification accepted for current setup
OpenBao                               3-node normal path COMPLETE / PASS
Node-RED                              server runtime PASS; A active, B fenced/stopped
Grafana                               server-only staging PASS; running loopback-only on ulc-03
```

For any leader-specific PostgreSQL mutation, rediscover the current Patroni leader first. Do not assume a previously recorded primary is still current.

## 4. MQTT service boundaries

Keep the authentication domains separate:

```text
Gateway mTLS:      Mosquitto :8884 on ulc-01/02
ChirpStack:        HAProxy :18883 -> Mosquitto :8885 on ulc-01/02
Node-RED mTLS:     node-local HAProxy :18884 -> Mosquitto :8886 pair
```

Node-RED MQTT identities:

```text
Node-RED A / ulc-03: node-red-ingest
Node-RED B / ulc-02: node-red-ingest-standby
allowed topic:        application/+/device/+/event/up read-only
```

Do not merge these listeners or reuse one private key across the two Node-RED candidates.

## 5. Node-RED current accepted state

### Runtime revision

```text
image:
  nodered/node-red@sha256:10f40d0a83e7e5852b13d4d472b2006b05b1cca6d55e2f29a55a12c25a630cb6
Node-RED: 5.0.4
Node.js:   24.18.1
npm:       11.19.0
PostgreSQL palette: node-red-contrib-postgresql 0.16.2
package-lock SHA-256:
  89289e301cab799ac7e85e2fbe2fc40b34ff195e799313a4f720c642397ba85e
flows.json SHA-256:
  02be61d7fafdaa8877b9b6f5cf5ef32f7685730e300d4af55b49aadd76518718
```

### Active/passive state

```text
Node-RED A: ulc-03 / 10.104.0.8 / ACTIVE / healthy
Node-RED B: ulc-02 / 10.104.0.4 / STANDBY / stopped
single-active invariant: PASS
```

A and B carry the same reviewed runtime revision. B must remain stopped until an approved fenced promotion.

### Database path

Both candidates use their local PgBouncer endpoint:

```text
pgbouncer.internal.lorawan.com:6432
  -> local PgBouncer
  -> local HAProxy :15432
  -> current Patroni primary
  -> lorawan_telemetry
```

Node-RED uses role `telemetry_writer`. Its controlled password rotation and all-three-PgBouncer verifier refresh are complete. Do not repeat that rotation unless authentication later fails for a new reason.

### PgBouncer CA repair

The original PgBouncer PKI directory remains protected for the `postgres` service. Node-RED reads a dedicated public-CA copy instead:

```text
/etc/lorawan-pki/node-red-pgbouncer/ca.crt
SHA-256 = 6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb
```

The same corrected Compose mount is present on A and B. A runtime database authentication passed after the repair; B runtime-read/config parity passed while B remained stopped.

### Server-only Node-RED application proof — COMPLETE / PASS

The reviewed A/B candidate revision, isolated synthetic atomic telemetry + outbox enqueue, and replay/idempotency proof are complete and authoritative. Do not repeat that server-only fixture unless the relevant flow/schema changes. Only the real-RF acceptance below remains open.

### Hardware-dependent Node-RED acceptance still open

Do not fabricate the **RF acceptance** PASS with synthetic data. When EMU-01 hardware becomes available, the remaining final Phase 12A acceptance is:

```text
real EMU-01 payload-v2 uplink
-> active Node-RED A
-> exactly one telemetry.uplinks row
-> expected normalized telemetry.measurements rows
-> replay/idempotency confirmation for the same stable event
```

## 6. OpenBao current accepted state

OpenBao server infrastructure is **COMPLETE / PASS for the normal path**:

```text
version: OpenBao 2.6.2
OCI index digest:
  sha256:11fd73a2102cda9c55d5d881a8c3210303146a7ec1e8ac76f526e175c6d24641
members: ulc-01 / ulc-02 / ulc-03
Raft: 3 voters, quorum 2
API: private TLS :8200
Raft: private :8201
stable KMS HAProxy: :18200 on ulc-01 and ulc-02
service name: openbao-kms.internal.lorawan.com
Transit key: lorawan-evidence, ecdsa-p256, non-exportable, version 1 at commissioning
signer policy: fabric-evidence-signer, sign/verify only
AppRole: fabric-adapter exists; no adapter SecretID issued prematurely
normal stable-endpoint sign/verify: PASS
```

Do not repeat initialization, Raft join, Transit setup, or HAProxy rollout unless configuration changes or a real failure provides a reason.

## 7. Fabric outbox and external Fabric status

Database preparation is complete:

```text
telemetry.fabric_outbox = commissioned / replicated 3/3
ordinary PostgreSQL table, not a hypertable
least-privilege ACLs = PASS
immutability rules = PASS
commissioning residue rows = 0
```

The repository now contains the reviewed Fabric-adapter source, pinned Fabric Gateway/JCS dependencies, worker/reconciliation tests, fail-closed standby runtime, and a reproducibly locked Linux/amd64 adapter binary. Full Fabric execution is still blocked on the real immutable OCI `image@sha256` build/push, the external Fabric Gateway/MSP/channel/chaincode/client handoff, and deliberate credential activation. Do not issue an adapter SecretID merely to make the standby container healthy, and do not substitute Node-RED as the adapter.

## 8. Gateway-integrity status

The gateway-integrity path now has reviewed source artifacts for evidence ingest, dual-broker MQTT collector, verifier/trusted decoder, S3-compatible immutable storage, migration/ACLs, Rust journal/segment/correlation core, deterministic binary candidates, and a reproducible three-host Compose/preflight bundle. It still has **no commissioned OCI image digest or live evidence runtime**. The active engineering boundary is deployment packaging and infrastructure inputs—Buildx image creation/pinning, durable object-store commissioning, DB login identities/migration, Evidence PKI/read-only MQTT credentials, shared-443 routing, and then the frozen replicas. Do not represent source/binary candidates as deployed services and do not create placeholder images merely to satisfy Phase 14B.

## 9. Phase 13A backup boundary

The streamlined non-destructive Phase 13A backup checkpoint is PASS.

```text
source directory:
  /home/opsadmin/backups/phase13a-20260827T032756Z
transport archive:
  phase13a-20260827T032756Z.tar.gz
SHA-256:
  e97d50c31252ede1fe55b734b6686f270e92ebecb69a36d637b04fbf726cda1c
off-host Windows copy/hash verification: PASS
```

Do not recreate these dumps merely for normal-path commissioning. The stronger isolated restore / destructive recovery evidence remains a pre-Phase-15 requirement.

## 10. Grafana latest preflight and immutable pin — PASS

Operator evidence on `ulc-03` records:

```text
TCP/3000: FREE
host memory: 1.9 GiB total, about 1.2 GiB available
swap: 0
root disk: about 34 GiB available
Node-RED A: healthy, restart_count=0
PgBouncer CA source SHA-256:
  6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb
Grafana service running: NO
```

Observed colocated container memory at the preflight:

```text
Node-RED A  ~64.6 MiB
OpenBao     ~31.13 MiB / 512 MiB
Spilo       ~164.6 MiB
etcd        ~19.06 MiB
```

Pinned Grafana runtime:

```text
release tag: 13.2.0
immutable image:
  grafana/grafana@sha256:3fd54ae1214669f8355f065ec9f6445d5279a3d77095ab048ca045685272429b
commit:
  f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b
runtime UID: 472
runtime GID: 0
runtime groups: 0
/var/lib/grafana in image: owner 472:0, mode 777
```

Grafana preflight, host staging, and first server-only activation are **COMPLETE / PASS**. Grafana 13.2.0 runs on `ulc-03` with restart count `0`, no OOM state, a 512 MiB memory limit, and only `127.0.0.1:3000` exposed. The dedicated PgBouncer CA remains byte-identical to SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`; `pgbouncer.internal.lorawan.com` resolves to local `10.104.0.8` inside Grafana. The provisioned PostgreSQL datasource is healthy over strict `verify-full` TLS as `telemetry_reader`; a Grafana-executed ACL query proved SELECT access and denied INSERT on both telemetry hypertables. The runtime datasource type is `grafana-postgresql-datasource`, observed plugin version `13.0.1`, and preinstalled-plugin auto-update is disabled for the immutable POC baseline. The four-panel `LoRaWAN Telemetry Overview` dashboard is provisioned. `GRAFANA_SERVER_STAGING=PASS`; full Phase 14A still waits for a real EMU-01 reading/freshness proof.

## 11. Grafana credential boundary — COMPLETE / PASS

The missing plaintext-custody problem is closed by a controlled `telemetry_reader` rotation. The role password was changed once on the freshly rediscovered Patroni leader, direct verify-full authentication passed, then each PgBouncer userlist was refreshed one node at a time from authoritative replicated PostgreSQL SCRAM verifiers. `ulc-03`, `ulc-02`, and `ulc-01` each accepted the rotated credential through `pgbouncer.internal.lorawan.com` with physical `hostaddr` targeting its own `:6432` endpoint and strict CA/hostname verification.

Final evidence: `THREE_NODE_PGBOUNCER_READER_AUTH=PASS`; Patroni remained one leader (`10.104.0.2`) plus two replicas; the protected active Grafana bootstrap credential now exists only at `/root/grafana-bootstrap/telemetry-reader-password` as `0600 root:root`, 65 bytes. Do not print it, copy it to Git/Markdown/Compose, weaken SCRAM/TLS, or give Grafana `telemetry_writer`. The next task is to consume it into Grafana's protected host environment without exposing the value.

## 12. Immediate next Grafana boundary

Server-only Grafana commissioning is complete. Do not repeat the credential rotation, filesystem staging, datasource provisioning, or first-start acceptance without a new failure or deliberate change.

The remaining Phase 14A work is hardware-dependent only:

```text
1. Restore physical gateway/device availability.
2. Send one real EMU-01 Agriculture Kit payload-v2 uplink through the commissioned ChirpStack -> Node-RED path.
3. Prove exactly one canonical telemetry.uplinks row and the reviewed telemetry.measurements rows exist.
4. Prove replay/idempotency for that same stable event.
5. Confirm the provisioned Grafana dashboard shows the same test_sequence/timestamp and selected measurements.
6. Confirm the reading-age/freshness panel advances correctly on a later real uplink.
7. Only then record PHASE14A=PASS.
```

Do not add Prometheus/Loki merely to complete this POC.

## 13. Hardware/provider/implementation blockers that remain

### Hardware deferred

```text
Phase 11 physical gateway access / remaining normal-path work
Phase 12 authoritative gateway/device cutover/provisioning
Phase 12A real EMU-01 storage + replay/idempotency acceptance
Phase 14A real-reading/freshness acceptance
```

Gateway details and the exact resume point remain in `11a-phase11-continuation-checkpoint.md`.

### Provider-owned/external

```text
DigitalOcean Reserved IPv4
provider firewall evidence/activation
real public DNS
public PKI/public MQTT hostname activation
```

Do not invent a raw-IP substitute for certificate-verified public MQTT.

### Remaining implementation / handoff

```text
immutable OCI image@sha256 references for the four cloud binaries
external Fabric Gateway/MSP/channel/chaincode/client handoff
production Go object-store S9 helper acceptance + remaining evidence LOGIN/PgBouncer credentials + Evidence PKI/shared-443/service commissioning
gateway HTTP uploader + durable receipt persistence + real hardware lineage
```

These keep the full Phase 14B gate and Phase 15 full-feature acceptance blocked. Source-level ingest/collector/verifier/Fabric-adapter runtimes are no longer the missing implementation.

## 14. Things not to repeat in the next chat

Unless a later failure or configuration change gives a reason, do **not** redo:

```text
etcd/Patroni/TimescaleDB bootstrap
HAProxy/PgBouncer commissioning
Valkey/Sentinel commissioning
ChirpStack two-node commissioning
OpenBao initialization/Raft/Transit/HAProxy setup
Fabric outbox migration
Phase 13A source dumps/off-host hash proof
Node-RED MQTT :8886 broker listener/ACL setup
Node-RED A/B MQTT identities
Node-RED telemetry_writer password rotation
Node-RED runtime bundle/palette/flows staging
Node-RED A activation and PgBouncer CA repair
Node-RED B CA parity staging
Grafana image pull/runtime identity preflight
SeaweedFS metadata/core/bucket/S3-identity/internal-TLS/HAProxy S0-S8 commissioning
gateway_evidence migration and three-node schema verification
evidence PostgreSQL HBA canary/persistence/fresh-replication-auth rollout
```

Passed gates stay passed until relevant state changes.

## 15. Secret-handling reminders

Do not put any of these in Markdown/chat/Git:

```text
PostgreSQL/PgBouncer plaintext passwords
Grafana admin password
Node-RED credential secret or editor password/hash value
MQTT private keys
OpenBao root token or Shamir shares
OpenBao AppRole SecretID
Fabric client private key
OTAA AppKeys
DigitalOcean API token
```

Public certificate hashes, image digests, software versions, non-secret service names, and file paths are safe to record.

## 16. New-chat startup instruction

In the next chat, begin with:

1. read this file;
2. read `00-build-execution-log.md` only for detailed history when needed;
3. treat Grafana server staging as COMPLETE / PASS and do not repeat its credential rotation, provisioning, or first-start sequence without cause;
4. keep Grafana running loopback-only on `ulc-03`;
5. keep Node-RED A active and Node-RED B fenced;
6. do not resume Phase 11/12 or real Phase 12A/14A acceptance until physical gateway access is available.

**Immediate continuation:** Phase 13S and Phase 14S are both complete for the current server-first preparation scope and must not be repeated without a relevant state change. Phase 14S run `SERVER-PRESTAGE-20260829T133354Z` produced `SERVER_ONLY_EVIDENCE_HARNESS=PASS` with a 16-file protected/hash-verified evidence set at `/home/opsadmin/lorawan-ha-evidence/SERVER-PRESTAGE-20260829T133354Z`. Authoritative gates include three-host evidence, etcd 3/3, Patroni one leader/two replicas, PostgreSQL/TimescaleDB/outbox, Node-RED single-active, corrected Grafana health, ChirpStack two-node runtime, OpenBao 3-node initialized/unsealed/HA-enabled health, deferred/BLOCKED recording, secret-sanity, filesystem protection, and SHA-256 verification. No restart, configuration mutation, backup, or failure injection occurred.

The later runtime/Markdown audit withdrew the earlier `SERVER_ONLY_PREPARATION=COMPLETE` claim because additional independent server work remained. The Node-RED atomic `queued_fabric` / `$25` application gap has since been closed and its synthetic/replay proof is authoritative. Do not repeat Phase 13S, Phase 14S, Node-RED rollout, or Grafana synthetic commissioning. Continue with the missing gateway/security evidence-service implementation described below.

**Node-RED atomic-outbox pre-mutation gate: PASS.** `NODE_RED_ATOMIC_OUTBOX_PREMUTATION=PASS` is authoritative. A remained `running|0|healthy`; B remained fenced/stopped; both still matched old flow SHA-256 `02be61d7fafdaa8877b9b6f5cf5ef32f7685730e300d4af55b49aadd76518718` and old Compose SHA-256 `5607fddf6a31eea71376d720c2f2f24903818635800a967fa276ca1f21f00934`; neither had outbox logic or `FABRIC_SELECTED_DEV_EUI` live. Synthetic DevEUI counts were `0|0|0`, and the outbox schema/defaults plus `telemetry_writer` INSERT/SELECT/sequence-USAGE permissions passed.

**Node-RED B atomic-outbox staging: PASS.** `NODE_RED_B_ATOMIC_OUTBOX_STAGING_FINAL=PASS` is authoritative. The reviewed candidate was reconstructed and hash-verified, transferred to `ulc-02`, installed with a temporary rollback guard, and validated without starting B. Deployed B hashes are `compose.yml=17aade702bf2206e9a4f2177fa8b0f47a7012da431a2adc7d4b064ce0b897730` and `flows.json=476056c5cff951ff46bb48c2eeb0e153b666c8cdc42eab88532fd3bebbcdc753`; protected `FABRIC_SELECTED_DEV_EUI=0000000000000000` exists exactly once; JSON/flow structure and `docker compose ... config --quiet` passed; B remained stopped. A remained `running|0|healthy` on the prior live revision throughout. No database row was created and no synthetic event was injected.

**Node-RED A/B atomic-outbox runtime: COMPLETE / PASS.** A and stopped B both carry candidate `compose.yml=17aade702bf2206e9a4f2177fa8b0f47a7012da431a2adc7d4b064ce0b897730` and `flows.json=476056c5cff951ff46bb48c2eeb0e153b666c8cdc42eab88532fd3bebbcdc753` with protected `FABRIC_SELECTED_DEV_EUI=0000000000000000` exactly once. A is `running|0|healthy`; B remains fenced. The corrected read-only resume proved runtime UID/GID `1000:1000` can read all required MQTT/PgBouncer certificate/key files plus the reviewed `/data` runtime files; both runtime CA hashes equal `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`; selector, parity, fencing, and final health all remained unchanged. `NODE_RED_RUNTIME_FILE_ACCESS=PASS`, `NODE_RED_RUNTIME_CA_ACCESS=PASS`, `NODE_RED_A_ATOMIC_OUTBOX_ROLLOUT=PASS`, and `NODE_RED_A_B_ATOMIC_OUTBOX_RUNTIME=PASS` are authoritative. Do not recreate A or repeat the deployment rollout.

**Node-RED synthetic atomic-outbox/replay: COMPLETE / PASS.** The exact deployed normalization Function on active A processed reserved synthetic event `server-synthetic-NODERED-OUTBOX-SYNTH-20260829T152713Z` without a flow edit, restart, or synthetic MQTT publish. It generated exactly 25 SQL parameters and thirteen normalized metrics; the first execution produced exactly one canonical uplink, thirteen distinct measured measurement rows, and one pending/unclaimed/unsealed `telemetry-attestation-v1` outbox row. Replaying the same stable event returned final SQL rowcount `0` and database counts remained `1|13|1`. A stayed `running|0|healthy`; B stayed fenced. Evidence is under `/home/opsadmin/lorawan-ha-evidence/NODERED-OUTBOX-SYNTH-20260829T152713Z`. `NODE_RED_SYNTHETIC_ATOMIC_OUTBOX=PASS` is authoritative.

**Grafana synthetic read path + cleanup: COMPLETE / PASS.** The prior cleanup anomaly is attributed and no longer treated as HA loss: `SYNTHETIC_ROWSET_CLEANUP_ATTRIBUTED=PASS`. Fresh fixture `grafana-synthetic-GRAFANA-SYNTH-20260830T000012Z` was created through the exact deployed Node-RED Function from a clean all-zero-DevEUI baseline and produced exactly `1` uplink, `13` measurements, and `1` pending outbox row. Grafana's actual four provisioned panel targets returned `1/1/6/1` rows, and a code-mode datasource probe executed as `telemetry_reader` returned the exact event, all 13 measurements, one pending outbox, matching `test_sequence=1788048012`, reading age `5` seconds, and correct latest-view counts. `GRAFANA_SYNTHETIC_FIXTURE_AND_READ_PATH=PASS` is authoritative. The later cleanup-only boundary revalidated the exact fixture and safe pending/unclaimed outbox state, deleted only that event on the single Patroni primary, and proved `0|0|0` on all three PostgreSQL members plus `0|0|0` for the reserved synthetic identity. Grafana and Node-RED A stayed healthy and B stayed fenced. Evidence remains under `/home/opsadmin/lorawan-ha-evidence/GRAFANA-SYNTH-20260830T000012Z`. `GRAFANA_SYNTHETIC_CLEANUP_COMPLETE=PASS` is authoritative. Full Phase 14A remains hardware-deferred.

**Immediate next server-only boundary:** source/build readiness remains closed, and major live evidence prerequisites are now commissioned. SeaweedFS core/metadata quorum/bucket/S3 identities/internal TLS/HAProxy create-only boundary are live; the reviewed `gateway_evidence` migration is live and replicated; and the evidence-aware PostgreSQL HBA is live + persistent on all three Patroni members. The current resume point is the six evidence LOGIN identities: `evidence_ingest_ulc01` was created with SCRAM and the intended `gateway_evidence_ingestor` membership, but its first direct verify-full login stopped at `FATAL: permission denied for database "lorawan_telemetry"` because database-level CONNECT is not yet granted through the authority shell. The other five evidence LOGIN identities are still absent and PgBouncer remains unchanged at the existing four-entry static SCRAM userlist. Resolve the CONNECT authority deliberately, then resume the idempotent LOGIN issuance block and only afterward refresh PgBouncer sequentially `ulc-01 -> ulc-02 -> ulc-03`. Production Go object-store S9 acceptance remains separately blocked on staging the accepted ingest binary/image; do not call the entire object store commissioned until that helper gate passes. Evidence PKI/read-only MQTT credentials, shared-443 ingest, and service replica commissioning follow. The gateway HTTP uploader/durable receipt-file path and real paired gateway lineage remain hardware-side prerequisites for full v2. OpenBao audit closure is complete; preserve zero Fabric-adapter SecretID until the explicit activation gate and external Fabric handoff are ready. Do not repeat Node-RED/Grafana synthetic commissioning, Phase 13S, Phase 14S, the gateway_evidence migration, or the completed HBA rollout.

After that operational evidence-service deployment, continue the remaining **server-security / pre-Fabric-activation queue** below before declaring server preparation exhausted. Physical gateway Phase 11/12 and real EMU-01 Phase 12A/14A acceptance; provider-owned Reserved IPv4/firewall/public DNS/public PKI; immutable evidence/Fabric OCI deployment; external Fabric handoff/confirmed transaction; and live gateway-integrity commissioning remain separate blockers. Final Phase 13B and final Phase 14 must still be refreshed after those required dependencies are commissioned. Phase 14B and Phase 15 remain blocked until the full-feature pre-test gate can pass.

## 17. Deep server-security / Fabric audit — 2026-08-29

`OpenBao 3/3 PASS` is only the KMS normal-path result; it does **not** mean the complete security/Fabric layer is finished.

### 17.1 Hardware-independent work still available

Execute one verified boundary at a time:

1. **Node-RED atomic outbox + Grafana server-only proof: COMPLETE.** Do not repeat the already-passed synthetic/replay/read-path journey.
2. **Gateway/security evidence services: CURRENT PRIORITY / LIVE COMMISSIONING IN PROGRESS.** The source/build layer is complete and the exact four Linux/amd64 binaries are locked. Live SeaweedFS 4.41 now has a separate 3-voter metadata-etcd quorum, three SeaweedFS nodes, empirically proven `010` two-rack placement, the `lorawan-evidence` bucket, least-privilege runtime S3 identities, internal object-store PKI, and a three-node HAProxy create-only TLS boundary. The reviewed `gateway_evidence` migration is also live and replicated. PostgreSQL HBA authorization was expanded without increasing the 20-rule policy: the three existing `lorawan_telemetry` `/32` SCRAM rules now include `+gateway_evidence_ingestor,+gateway_evidence_collector,+gateway_evidence_verifier`; live/persistent HBA SHA is `a943358a884249aaae74b663a81fa6dde2d7c98deeb31f93def8e5bb4aa729f1` on all three nodes, and fresh SCRAM + verify-full `IDENTIFY_SYSTEM` sessions from both replicas to the leader passed. Current stop: the first workload LOGIN `evidence_ingest_ulc01` exists with valid SCRAM and exactly one membership but direct DB authentication is denied by missing database CONNECT privilege. Resolve that authority boundary, resume the remaining five LOGIN identities, refresh PgBouncer `ulc-01 -> ulc-02 -> ulc-03`, then continue Evidence PKI/read-only MQTT identities, shared `:443`, and service replica deployment. Production Go object-store S9 acceptance is still pending because the accepted ingest binary/image has not yet been staged on a server; do not collapse that separate binary gate into the already-passed SeaweedFS/HAProxy infrastructure checks. Fabric activation still waits for the real external handoff and zero adapter SecretID must be preserved until then.
3. **Gateway journal/uploader implementation.** Journal/segment/state + receipt validation + pinned Concentratord uplink adapter: SOURCE + CARGO TEST PASS. Real Concentratord/MQTT fixture: BLOCKED only on hardware access, not schema ambiguity. HTTP transport and durable receipt-file persistence remain implementation work. Local evidence retirement remains deliberately absent. Package/install on the physical gateway only when hardware access returns.
4. **OpenBao audit-device closure: COMPLETE.** Keep the commissioned audit path/rotation behavior intact. Do not reconfigure or disable/re-enable it merely for adapter work, and preserve zero adapter SecretID until the explicit enabled-adapter activation gate.
5. **Certificate-expiry monitoring.** Inventory commissioned service certificates and install a lightweight read-only expiry checker/timer with warning thresholds; never read or print private-key contents.
6. **Fabric canonicalization startup vectors: COMPLETE.** v1 remains `c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c`; independently frozen v2 is `25740c6bd9eee20b01151789c891f9b100b7dd0aa1144c20689ce1231cf7b96f`. Both pass the pinned RFC 8785 JCS test path and are startup blockers on mismatch.
7. **Container/image security inventory.** Record effective runtime hardening and image/SBOM coverage gaps without restarting healthy services or installing heavy scanners merely for paperwork.

### 17.2 Fabric adapter boundary

The repository now contains the real Go Fabric-adapter implementation, tests, pinned `fabric-gateway v1.12.0`, pinned JCS `v1.0.1`, scratch-image packaging path, fourth deterministic Linux/amd64 binary, and two-host deployment wiring. Worker behavior includes committed lease claims, v2 verifier-owned eligibility, fixed projection/JCS/SHA-256, exact-byte OpenBao signing, immutable seal persistence before Fabric, seal re-read/re-hash/Transit verification, seven-argument submission, valid-commit confirmation, `submitted_unknown` reconciliation-only handling, bounded retry/backoff, and permanent conflict/security failure handling. A read-only `reconstruct <outbox_id>` mode exists for the integrity test.

The base Compose profile is intentionally fail-closed: adapter-1 on ulc-01 and adapter-2 on ulc-02 start with `FABRIC_ADAPTER_ENABLED=false`, health/readiness only, and no DB/OpenBao/Fabric credential mounts. Actual activation requires the separate `compose.fabric-adapter-enabled.yml` plus `fabric-adapter-enable-preflight.sh`. The existing OpenBao `fabric-adapter` AppRole still has a RoleID but no SecretID should be issued until that activation boundary and the external Fabric handoff are complete. Prefer independently revocable adapter-1/adapter-2 workload identities where practical.

No real Fabric transaction or immutable adapter OCI image digest is claimed yet. The external handoff must also confirm whether the Fabric Gateway transport uses server-auth TLS only (the current client implementation) or requires a separate transport-mTLS client identity; if mTLS is required, extend/rebuild rather than weakening TLS checks.

### 17.3 Gateway-integrity / evidence-service boundary

The evidence path is a required setup boundary for the full v2 security target, not just a test-time logging feature. It is separate from the already-passed Phase 14S operational evidence harness.

Canonical service chain:

```text
Gateway journal -> uploader -> evidence.<DOMAIN>:443 HTTPS/mTLS -> evidence ingest -> protected raw-object store
remote gateway MQTT -> read-only MQTT evidence collector
journal + MQTT + ChirpStack + TimescaleDB -> verifier -> pinned trusted decoder -> gateway_evidence.event_verification
verified v2 only -> Fabric adapter -> OpenBao -> external Fabric
```

The evidence path is no longer Markdown-only: repository source exists for the shared Go foundation, `mqtt-capture-v1`, trusted decoder, full evidence-ingest source including stable `evidence-ingest-receipt-v1`, dual-backend MQTT collector with `event/up` semantic projection, verifier discovery/lease/application validation plus deterministic MQTT/journal/checkpoint lineage, S3-compatible immutable object storage, versioned `gateway_evidence` migration, the Fabric adapter, and the Rust journal/segment/receipt/Concentratord-adapter core. The complete Go module passes `gofmt`, `go test ./...`, `go build ./...`, and Linux/amd64 cross-builds from the checksum-pinned Go 1.25.0 path. Current accepted binaries are ingest `18179015` bytes / `a5de435343ee57b8725608e11cf356249a921d208cc041f5c59686f554bc3bf2`, collector `18552641` / `3d31d2b501fccf1bc5472708f2eb858eafd3efa7c6d0e66309d12937658aa0b5`, verifier `17814443` / `69095c14a65e281b2574efcf968b2e77c260d66ed59396afa7bb31a3b922ab3a`, and Fabric adapter `25527785` / `ac2180e96e31a8e66ea8a5a3ef41c51c458865f550b3ef94159f4bbc5c256afd`. The ingest binary additionally carries the production object-store contract write/read-verification commands used for SeaweedFS commissioning. The verifier carries the deterministic trusted-decoder source-package digest and can atomically promote complete matching lineage to `verified`; the offline packaging gate verifies the four-binary lock plus the minimal `FROM scratch` Dockerfile. No registry OCI image digest is claimed yet. Local evidence retirement remains disabled. [Gateway Integrity Guide 5](../integrations/gateway-integrity/05-preimplementation-readiness-and-deployment-gate.md) remains the readiness gate, and [Guide 7](../integrations/gateway-integrity/07-implementation-blueprint-and-ha-placement.md) remains the concrete implementation/HA blueprint.

Immediate evidence-service preparation queue:

```text
1. all three evidence host preflights are already recorded PASS; retain the measured placement and use ulc-02 as the preferred staged Buildx host unless a fresh resource check shows otherwise
2. accepted Linux/amd64 binaries are frozen in `packaging/binaries.lock`, but the evidence source tree is still untracked and no server currently holds the accepted ingest binary/image; stage the accepted artifacts from an approved source before building/pushing the four minimal scratch OCI images and freezing real `image@sha256` references in `release.env`
3. SeaweedFS infrastructure through S8 is live PASS: immutable 4.41 + metadata-etcd image pins, 3-voter metadata quorum, three SeaweedFS nodes, `010` two-rack placement, `lorawan-evidence` bucket, runtime S3 identities, internal TLS, and three-node HAProxy create-only semantics are proven. S9 remains pending specifically on the production `gateway-evidence-ingest objectstore-contract-write/verify` binary gate; retain the commissioning fixtures and do not mark full `EVIDENCE_OBJECTSTORE=PASS` before S9
4. `gateway_evidence` migration is live PASS and replicated. Evidence HBA admission is live + persistent on all three nodes at SHA `a943358a884249aaae74b663a81fa6dde2d7c98deeb31f93def8e5bb4aa729f1`. LOGIN issuance is partially started: `evidence_ingest_ulc01` exists with SCRAM and intended group membership but its direct verify-full session is blocked by missing CONNECT on `lorawan_telemetry`; the other five identities are absent and PgBouncer is still unchanged. Root cause is now identified from the authoritative Phase 6 activation record: `PUBLIC` CONNECT was deliberately revoked and CONNECT was granted only to the original runtime roles, while the later evidence migration did not add database CONNECT for its NOLOGIN authority shells. The first CONNECT-authority repair script stopped before mutation because its role-state harness concatenated booleans and got `true/false` text while asserting the separate-column `t/f` representation; the returned state still exactly represented the accepted `evidence_ingest_ulc01` privileges and **no ACL change occurred**. Retry with separate boolean columns, then perform `GRANT CONNECT ON DATABASE lorawan_telemetry` to `gateway_evidence_ingestor`, `gateway_evidence_collector`, and `gateway_evidence_verifier`, preserving group-based least privilege; verify the resulting matrix and re-authenticate the existing `evidence_ingest_ulc01` before resuming the remaining five identities, then refresh PgBouncer ulc-01 -> ulc-02 -> ulc-03 with per-node authentication proof
5. issue direct-ingest Evidence PKI plus four dedicated read-only MQTT collector mTLS identities/ACLs; preserve gateway client-certificate identity through shared TCP/443 passthrough instead of terminating evidence TLS at HAProxy
6. stage protected inputs, run final `preflight.sh` on all three hosts, then commission ingest -> collector -> verifier one logical replica boundary at a time; adapter-1/2 may be started only in the base disabled standby profile
7. prepare shared-443 SNI/TCP dispatch only after private evidence ingest is healthy; keep ChirpStack routing behavior unchanged while passing evidence TLS through end-to-end
8. guarded Node-RED v2 provenance rollout remains separate from already-passed v1 telemetry/outbox behavior; the v2 RFC8785 vector and verifier `verified` authority gates are already source/build complete
9. prepare read-only Grafana evidence-state/checkpoint panels + alerts after live schema/service state exists
10. after the external Fabric handoff arrives, issue adapter workload credentials deliberately, run `fabric-adapter-enable-preflight.sh`, activate one adapter at a time, and prove one real confirmed transaction plus reconciliation behavior before calling Fabric live-complete
```

Evidence host-preflight status is `ulc-01=PASS`, `ulc-02=PASS`, `ulc-03=PASS`. The measured three-host placement is retained and `ulc-02` is the preferred staged Buildx host unless a fresh resource check gives a reason to change it. The ulc-01 capture recorded one x86_64 vCPU, `1967 MiB` RAM with `1255 MiB` available, about `40 GiB` free root disk, free UID/GID `65532`, Docker `29.7.2`, Compose `v5.5.0`, and Buildx `v0.36.1`. HAProxy/PgBouncer/Mosquitto were healthy, Patroni showed one leader/two replicas, and broker `:8884` enforced client-certificate identity. Port choices are now reflected by the live SeaweedFS and evidence deployment documentation; do not reuse the earlier provisional-port language as if commissioning had not occurred.

Critical ingress finding: current Phase 10 `chirpstack_https` already terminates TLS on each anchor IP `:443`. Evidence deployment therefore cannot add another independent bind on the same address/port. Freeze and validate one shared-443 SNI/multi-certificate design with evidence-route-specific client-certificate enforcement, or another explicitly approved ingress architecture, before public mutation. Do not globally require gateway client certificates from ordinary ChirpStack browser/API users.

The evidence service target is now explicitly HA and the architectural placement is frozen: ingest replicas on `ulc-01/02`; collector replicas on `ulc-01/03`, with each collector maintaining persistent read-only sessions to **both** Mosquitto backends; verifier + identical trusted-decoder replicas on `ulc-02/03` using PostgreSQL discovery, `SKIP LOCKED`, and expiring worker leases. The raw evidence store must survive one Droplet loss; two unsynchronized local directories are not HA. PostgreSQL evidence metadata inherits the existing three-node Patroni boundary, but its current asynchronous replication does not by itself satisfy the raw-byte acknowledgement durability requirement.

The streamlined operator journey is `../integrations/gateway-integrity/06-replicated-ha-deployment-journey.md`: one guarded block per logical boundary, canary verification before the second replica, one named PASS marker, and resume from the first failed gate without rerunning earlier PASS work.

Current high-level evidence markers after the live storage/database/HBA work:

```text
EVIDENCE_CONTRACTS=PASS
EVIDENCE_REPLICATION_DESIGN=PASS
EVIDENCE_IMPLEMENTATION_BLUEPRINT=PASS
EVIDENCE_PREIMPLEMENTATION_GATE=ACTIVE
GATEWAY_EVIDENCE_RUNTIME=BLOCKED
GATEWAY_EVIDENCE_V2_NORMAL_PATH=NOT_YET_CLAIMED
```

### 17.4 Deliberately deferred security mutations

- **UFW/provider firewall:** keep the remote-lockout exception until provider/recovery-console access exists.
- **etcd TLS:** current private HTTP is an explicit POC exception. Retrofitting TLS is a high-risk Patroni-DCS-wide change and is not a Phase 14B blocker; keep it out of the fast server-completion track unless deliberately scheduled as its own migration.
- **auditd:** optional stronger host evidence, not required while the accepted journal/Fail2ban/AppArmor baseline and 2-GiB resource budget remain in force.
- **Fabric SecretID/client key:** do not issue/import until the reviewed adapter, runtime UID/GID, external handoff, and credential-delivery design are known.
