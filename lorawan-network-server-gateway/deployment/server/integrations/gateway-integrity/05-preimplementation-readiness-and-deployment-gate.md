# Gateway Evidence Services Pre-Implementation Readiness and Deployment Gate

> **Status: READINESS CONTRACT PASS / CLOUD RUNTIME + PUBLIC NORMAL PATH COMMISSIONED.** The cloud pre-implementation/deployment gate is closed: SeaweedFS S0-S9, database/HBA/CONNECT/six LOGINs, three-node PgBouncer evidence auth, immutable OCI refs, Evidence PKI/MQTT identities, replicated services, shared-443, read-only evidence observability, and the public ChirpStack/Evidence/MQTT normal path are PASS. The remaining normal-path gate is the Gateway OS/OpenWrt target package plus one real physical lineage; Reserved-IP failover authority and Fabric remain separate external gates.

This guide is for the full cloud/full-feature gateway-integrity path. The minimum dissertation VM remains a separate v1-compatible profile unless its methodology is explicitly changed.

## 5.1 What this gate prevents

Do not wait until the physical gateway returns to discover that the evidence stack still needs:

```text
cloud service placement
raw evidence storage
PostgreSQL migration + least-privilege roles
collector MQTT identity/ACL
HTTPS/mTLS ingress design
per-gateway evidence-upload PKI
trusted-decoder package and fixtures
v2 canonicalization vector
monitoring/alerts
backup/recovery rules
Phase 14 evidence files
```

Equally, do not create placeholder containers, empty database roles, a fake object store, or a public TCP/443 listener merely to make the topology appear complete.

## 5.2 Authoritative service chain

```text
PHYSICAL GATEWAY

Concentratord
  |\
  | +-> MQTT Forwarder -> local Mosquitto -> cloud MQTT
  |
  +----> gateway-integrity-journal
           -> closed hash-chained segments
           -> gateway-journal-uploader
                    |
                    | HTTPS + mTLS
                    v
CLOUD               gateway-evidence-ingest
                         |
                         +-> protected immutable/raw evidence store
                         +-> gateway_evidence checkpoint/segment metadata

cloud MQTT
  -> gateway-mqtt-evidence-collector
       -> protected captured-event object
       -> gateway_evidence.mqtt_gateway_events

ChirpStack application event -----+
TimescaleDB telemetry -------------+--> gateway-evidence-verifier
journal/checkpoint state ----------+        |
MQTT witness ----------------------+        +-> pinned trusted decoder
                                            |
                                            v
                                  gateway_evidence.event_verification
                                  pending / verified / evidence_gap /
                                  integrity_failure / not_required
                                            |
                           verified v2 only |
                                            v
                                   telemetry.fabric_outbox
                                            |
                                            v
                                      Fabric adapter
                                            |
                                      OpenBao Transit
                                            |
                                       external Fabric
```

The verifier decides whether evidence is trustworthy. The Fabric adapter signs/submits only eligible durable work. They must remain different trust identities.

## 5.3 Current implementation boundary

Already available/commissioned:

```text
PostgreSQL/TimescaleDB HA foundation + telemetry/outbox              PASS
OpenBao 3-node KMS + audit                                           PASS
Node-RED/Grafana server paths                                        PASS
cloud MQTT gateway/ChirpStack/Node-RED listener separation          PASS
SeaweedFS raw evidence infrastructure S0-S9                          PASS
gateway_evidence migration + HBA + CONNECT + six LOGIN identities    PASS
PgBouncer evidence expansion                                         PASS on all three nodes
immutable cloud OCI refs + six evidence replicas                     PASS
Evidence PKI + four collector MQTT identities/ACLs                   PASS
shared anchor :443 SNI route + end-to-end evidence mTLS              PASS
read-only Grafana checkpoint/verification panels                     PASS
cloud ingest/collector/verifier/trusted-decoder/Fabric adapter source BUILD/TEST PASS
v1/v2 canonicalization and correlation vectors                       FROZEN / PASS
```

Still not live-complete:

```text
Gateway OS target-native concentratord-zmq build   TARGET TOOLCHAIN PENDING
Gateway OS package/service installation            PENDING
real verified gateway journal/uploader lineage     HARDWARE DEPENDENT
public WAN ChirpStack/Evidence/MQTT normal path     PASS
Reserved-IP reassignment/failover authority          EXTERNAL PROVIDER INPUT
Fabric ledger activation                           EXTERNAL HANDOFF DEPENDENT
```

`GATEWAY_EVIDENCE_RUNTIME=SERVER_PASS_GATEWAY_PENDING` is the accurate current marker: the replicated cloud runtime is commissioned, while the physical gateway lineage is not yet claimed.

## 5.4 Decisions and artifacts that can be frozen now

### A. Implementation package contract

Every future evidence service must provide before deployment:

```text
reviewed source location and revision
reproducible build procedure
reproducible build command plus minimum smoke/self-test command
immutable OCI image digest or reviewed executable SHA-256
runtime UID/GID
configuration schema/example with no live secrets
startup self-tests
bounded health/readiness contract
structured log contract and redaction rules
memory/CPU starting ceiling
persistent paths and required filesystem permissions
SBOM/provenance or recorded scan gap
upgrade/rollback procedure
```

Do not accept a mutable tag alone.

### B. Replicated cloud placement and capacity

The evidence services must be **replication-capable**, but replication is allowed only where duplicate work is deterministic and idempotent. The physical gateway itself remains one device; do not call two cloud copies of its history a replacement for the gateway-local crash-safe journal.

The **target HA placement** is now frozen architecturally; live activation still requires the reviewed-image and capacity gates:

```text
ulc-01
  gateway-evidence-ingest-1
  gateway-mqtt-evidence-collector-1

ulc-02
  gateway-evidence-ingest-2
  gateway-evidence-verifier-1 + trusted decoder

ulc-03
  gateway-mqtt-evidence-collector-2
  gateway-evidence-verifier-2 + trusted decoder
```

This gives every cloud evidence-processing responsibility two runtime replicas while adding roughly two evidence roles to each Droplet instead of three. No host contains both replicas of one responsibility. If measured 2-GiB headroom is unsafe, increase host capacity; do not delete an HA replica merely to keep the smaller server size.

Replication contract:

```text
ingest-1/2      active/active; exact retry idempotent; conflicting identity rejected
collector-1/2   active/active; each opens persistent read-only sessions to BOTH Mosquitto backends
verifier-1/2    active/active; PostgreSQL SKIP LOCKED + expiring worker lease
trusted decoder identical immutable digest on verifier-1/2
raw store       survives any one Droplet loss; two local folders are NOT sufficient proof
PostgreSQL      existing three-node Patroni durability
```

Use separate workload identities for replica 1 and replica 2 wherever practical so one compromised or retired replica can be revoked independently. Replicas share capabilities, not private keys.

Do **not** activate this frozen target placement on the live hosts until the reviewed images exist and a read-only resource preflight plus measured healthy-state run proves the 2-GiB hosts retain acceptable headroom. Initial per-role ceiling remains:

```text
192 MiB RAM
0.20 CPU
```

Two roles therefore reserve an initial measurement ceiling of about `384 MiB / 0.40 CPU` on each host. This is only a starting guardrail. If the complete feature set does not fit safely, increase capacity; do not silently remove a replica or security role to preserve the 2-GiB number.

### C. Public evidence ingress and the existing TCP/443 conflict

The target endpoint is:

```text
https://evidence.<DOMAIN>:443
```

with a unique evidence-upload machine identity per gateway.

The current public-ingress design already binds each anchor IP TCP/443 for `chirpstack.<DOMAIN>` TLS termination. Therefore **do not add a second independent `bind <ANCHOR_IP>:443`** for evidence.

Before v2 deployment, freeze one reviewed shared-443 design that preserves both services. The intended result must provide:

```text
chirpstack.<DOMAIN> -> existing browser/API HTTPS behavior
evidence.<DOMAIN>   -> evidence service only
                         + server certificate valid for evidence.<DOMAIN>
                         + gateway client certificate requested/validated
                         + client identity mapped to exactly one Gateway EUI
                         + unauthenticated upload rejected
                         + body/version/rate limits
```

A possible HAProxy design is one shared TLS frontend with SNI/hostname routing, multiple certificates, and evidence-route-specific client-certificate enforcement. Treat that as a design candidate until the exact HAProxy 2.8 configuration is reviewed and validated off-path. Do not weaken ChirpStack HTTPS or make client certificates globally mandatory for ordinary browser/API users by accident.

The public normal path is now commissioned on Reserved IPv4 `129.212.208.168` with `smartagri-chirpstack.duckdns.org`, `smartagri-evidence.duckdns.org`, and `smartagri-mqtt.duckdns.org`. ChirpStack ordinary HTTPS, Evidence gateway mTLS/no-client rejection, and MQTT gateway mTLS CONNECT/SUBSCRIBE are accepted. The remaining provider input is least-privilege Reserved-IP reassignment authority plus controlled failover acceptance; do not conflate that open HA test with the already-working public normal path.

### D. Evidence PKI profile

Freeze a separate purpose from gateway MQTT where practical:

```text
Evidence server identity
  SAN: evidence.<DOMAIN>
  purpose: serverAuth

Per-gateway evidence upload identity
  identity -> exactly one 16-hex Gateway EUI
  purpose: clientAuth / evidence upload only
  MQTT publish permission: NONE
```

Required evidence for issuance:

```text
issuer reference
serial
fingerprint/SHA-256
notBefore/notAfter
key/public-key match
EKU result
Gateway EUI mapping
revocation reference
protected installation path
```

Never reset journal history during certificate rotation.

### E. Protected raw evidence store contract

The raw-evidence backend is selected and **commissioned through S9**: SeaweedFS OSS 4.41 on ulc-01/02/03, with one master/volume/filer/S3 process per host, a separate three-member metadata-etcd quorum on `12379/12380`, and SeaweedFS placement `010`. Each Droplet is modeled as a distinct rack in the same `sgp1` data center, so `010` creates one additional raw-data copy on another physical host. Live cluster membership, bucket placement, internal TLS, least-privilege S3 identities, two-rack replication, HAProxy create-only semantics, the locked production `gateway-evidence-ingest` helper write, and cross-host retained-object verification are all PASS. See `../../../../evidence-services/cloud/deploy/seaweedfs/README.md`.

Required behavior:

```text
create new object by stable identity
no in-place overwrite by ingestor/collector
SHA-256 recorded independently in PostgreSQL
exact raw closed segment retained
exact serialized MQTT event retained when forensic replay requires it
object_ref is stable and non-secret
separate write identities for ingestor and collector where practical
verifier read-only access
Fabric adapter no raw-store write access
retention and capacity limits are explicit
backup/recovery preserves object bytes + database references together
conflicting duplicate is preserved/rejected, never silently replaced
one-Droplet loss does not remove the only accepted copy
replica repair/rebuild can revalidate every object by recorded SHA-256
```

For the one-VM lab, a protected persistent volume is allowed. The cloud/full-feature POC must explicitly record its durability/failure-domain decision before claiming HA evidence durability. Initial commissioning requires a backend whose documented/configured semantics provide two independent durable copies or equivalent erasure/replication across failure domains, plus one normal create/get/SHA-256 proof. The live one-member-unavailable recovery exercise is deferred to Guide 3 / Phase 15. Do not assume two manually synchronized local directories are an object store.

The current PostgreSQL/Patroni cluster is intentionally asynchronous. Therefore raw evidence acceptance must not rely only on `INSERT bytea ... COMMIT` to the current primary and infer that one-Droplet-loss durability has already been satisfied. PostgreSQL remains the authoritative metadata/lease/result layer; the raw store must independently satisfy its ACK durability rule.

### F. PostgreSQL migration and role bundle

Guide 2 already defines the required schema shape:

```text
gateway_evidence.checkpoints
gateway_evidence.segments
gateway_evidence.mqtt_gateway_events
gateway_evidence.event_verification
```

Before live application, turn that design into one reviewed, versioned migration with rollback/forward rules and exact grants. Role names may be chosen during implementation, but capability boundaries are fixed:

```text
ingestor
  INSERT checkpoint/segment metadata only
  no verification-state authority

collector
  INSERT MQTT capture index only
  no telemetry write

verifier
  SELECT evidence + required telemetry source
  UPDATE only verifier-owned result/status fields
  no OpenBao sign
  no Fabric identity
  no MQTT publish

Grafana
  SELECT approved status/checkpoint view/table only

Fabric adapter
  SELECT verified event_verification only for v2
  never INSERT/UPDATE verifier result
```

The reviewed migration/role boundary is now live and must not be re-applied. The three authority roles remain NOLOGIN capability shells; database CONNECT is granted at that group layer, and six node-specific SCRAM LOGIN identities inherit exactly one intended authority role. Preserve these names/ACLs and use the migration as rebuild/recovery source, not as a command to rerun on the commissioned cluster.

### G. MQTT evidence collector identity

The collector is a server-side witness, never a gateway identity. Its minimum ACL is:

```text
READ as923/gateway/+/event/#
WRITE denied
state/# denied unless a reviewed matching contract explicitly needs it
command/# denied
application command topics denied
```

The cloud broker implementation must use dedicated collector credentials and direct/private broker paths that witness both broker backends. Do not reuse the ChirpStack account, Node-RED account, or physical gateway certificate.

Because the commissioned Mosquitto pair provides service failover but **does not replicate MQTT sessions/queues**, each collector replica must maintain a persistent read-only session to both broker backends. Use unique client IDs per collector/backend session. This produces deliberate duplicate observations when both collectors are healthy; the reviewed `capture_key_sha256` contract, raw-object create-if-absent rule, and database uniqueness collapse those observations into one logical gateway event. Freeze the exact TLS hostname/hostaddr/client-ID arrangement with the runtime.

### H. Verifier + trusted decoder package

The decoder must be independent of Node-RED operational mapping and must provide:

```text
reviewed source/revision or immutable package digest
stable decoder_id
decoder_version or code hash
fixed input/output fixtures
exact raw application bytes as input
versioned deterministic normalized object
normalized_digest_sha256
no dependence on wall clock, random data, or network state for decoding
```

The verifier package must also own the idempotent discovery/reconciliation loop that creates missing `pending` `event_verification` work from durable evidence-selected v2 source/outbox identities. Use the existing `(source_event_key, observed_at)` uniqueness boundary and `INSERT ... ON CONFLICT DO NOTHING`; Node-RED and the Fabric adapter must not become verification-work authorities.

The verifier must fail closed on ambiguous lineage and must preserve reason codes for:

```text
journal hash/sequence/segment conflict
checkpoint rollback/conflict
missing segment / evidence gap
zero or multiple MQTT counterparts
zero or multiple application counterparts
Gateway EUI mismatch
trusted-decoder mismatch
stored telemetry mismatch
unsupported version
```

### I. v2 canonicalization vector

This is a deployment blocker independent of the v1 fixture.

Required artifact:

```text
one fixed telemetry-attestation-v2 input object
exact expected RFC 8785 canonical UTF-8 string
exact expected SHA-256
result independently reproduced by at least two approved implementations/reference paths
fixture committed with adapter/verifier tests
startup test fails on any mismatch
```

Do not reuse the v1 digest `c2952e8c...` and call it the v2 vector.

### J. Grafana / operational observability

After the schema/services exist, add read-only evidence views/panels for:

```text
latest verification state + reason
pending age
integrity_failure count/reasons
evidence_gap count/reasons
latest checkpoint age per gateway
ingest conflict/rejection count
collector lag/unmatched events
trusted-decoder mismatch count
v2 outbox rows blocked waiting for verification
```

Telemetry freshness and evidence freshness must remain separate.

## 5.5 Evidence required at each commissioning step

Every implementation step must leave a small machine-readable proof. Do not rely on screenshots alone.

| Step | Minimum proof before advancing |
|---|---|
| Implementation package | source/revision, reproducible build PASS, immutable digest/executable SHA, UID/GID, config validation, startup self-test |
| Placement/capacity | two-replica placement, memory/CPU limits, listener/mount inventory, healthy-state resource snapshot |
| Evidence store | backend identity, create-if-absent, exact object SHA, permissions, documented one-Droplet durability policy; live member-loss testing is later |
| DB migration | migration hash/version, four objects present, constraints/uniqueness, grants matrix |
| Evidence PKI | server SAN/EKU/chain, client EUI mapping/EKU, fingerprint/expiry, no private key in evidence output |
| Shared `:443` ingress | HAProxy validation, ChirpStack HTTPS regression PASS, valid evidence mTLS route, no-cert rejection |
| Ingest service | both replicas healthy, one valid fixture accepted, exact retry stays one metadata/object identity, object hash matches |
| MQTT collector | both replicas healthy, four persistent read-only broker sessions, one duplicated fixture converges to one `capture_key_sha256` |
| Verifier | both replicas healthy, identical decoder digest, one pending fixture processed exactly once to the expected state |
| Trusted decoder | decoder identity/version and one fixed valid vector PASS with raw/normalized digests |
| Grafana/alerts | one read-only evidence-state/freshness query and replica health visible |
| Real v2 lineage | deferred until physical gateway access; one real event later closes `GATEWAY_EVIDENCE_V2_NORMAL_PATH=PASS` |
| Fabric v2 gate | separate later boundary; OpenBao audit must be closed before signing credentials are released |

A PASS marker should name the boundary, for example:

```text
EVIDENCE_STORAGE_CONTRACT=PASS
EVIDENCE_DB_MIGRATION=PASS
EVIDENCE_PKI_INGRESS=PASS
EVIDENCE_INGEST_NORMAL_PATH=PASS
EVIDENCE_MQTT_COLLECTOR=PASS
EVIDENCE_VERIFIER_FIXED_FIXTURES=PASS
TRUSTED_DECODER=PASS
GATEWAY_EVIDENCE_V2_NORMAL_PATH=PASS
```

Do not use `GATEWAY_EVIDENCE_V2_NORMAL_PATH=PASS` until one real staging event has completed the whole lineage.

## 5.6 Streamlined operator rule: one guarded block per boundary

The preferred execution style is **one copy/paste block for one logical boundary**, not twenty tiny commands and not one uncontrolled script for the entire stack.

Every block must internally perform:

```text
1. read-only preflight
2. verify previous PASS prerequisites
3. create only the minimum rollback copy needed for THIS mutation
4. apply one logical change/canary
5. validate configuration before restart/reload
6. activate/reload only the affected service
7. verify health + permissions + HA invariant
8. capture bounded secret-free evidence
9. print one named PASS marker
10. stop immediately on the first failed gate
```

A single block may configure replica 1 then replica 2 **only if** it verifies replica 1 before touching replica 2. The block may use `set -euo pipefail` inside its controlled child shell, but not as an unreviewed top-level interactive-shell setting. SSH calls inside heredoc-fed wrappers must use `ssh -n` when no payload is expected, or explicit stdin redirection when transporting a script.

Do not create a fresh full backup before every block. Existing passed backup/snapshot gates stay passed until a relevant state change. Save only the new service evidence and configuration hash needed for the current boundary.

Every live block should write or print a compact journey footer like:

```text
STEP=<boundary-name>
UTC=<timestamp>
REPLICA_1=PASS
REPLICA_2=PASS
HA_INVARIANT=PASS
EVIDENCE_PATH=<protected-path>
<BOUNDARY_PASS_MARKER>=PASS
```

After the operator pastes the result back into the project session, record the verified PASS/failure and exact resume point in the component manual, `00-build-execution-log.md`, and current continuation checkpoint. Never copy plaintext credentials into Markdown.

The executable journey/order is maintained in [06-replicated-ha-deployment-journey.md](06-replicated-ha-deployment-journey.md).

## 5.7 What can be completed before hardware/provider access returns

Active implementation work now:

```text
[x] create the evidence-services/ source tree from Guide 7
[x] implement shared Go configuration/logging/database/object-store interfaces
[x] implement a filesystem object-store backend for local/dev smoke only
[x] implement and test the S3-compatible immutable object-store source backend behind the same Store interface
[ ] select/provision the real production object-storage service and prove its failure domain survives one Droplet loss
[x] convert Guide 2 DDL into versioned 001_gateway_evidence.sql + least-privilege grants + verify script
[x] freeze mqtt-capture-v1 deterministic identity + independent fixed SHA-256 vector
[x] compile/run the complete cloud module with pinned project-local Go 1.25.0; gofmt, go test ./..., go build ./..., Linux/amd64 builds PASS; current S3-capable source reproduces identical binaries across two offline builds, while the checksum-pinned reset/recovery mechanism was proven separately
[x] implement the trusted decoder source + one independently reproduced valid raw/normalized fixed vector
[x] implement gateway-evidence-ingest HTTP/core contract, identity/body guards, idempotency/conflict/regression logic, and test repository
[x] implement the production PostgreSQL evidence repository + executable ingest wiring + DB-level checkpoint monotonicity invariant
[x] implement gateway-mqtt-evidence-collector source + PostgreSQL capture repository + dual-session/read-only/ACK contract
[x] implement gateway-evidence-verifier discovery/lease/application-trusted-decoder source with lease-fenced verifier-owned `verified` promotion
[x] implement deterministic application/MQTT/journal/checkpoint verifier lineage with full predecessor-object verification and atomic complete-lineage terminal transition
[x] implement/test the separate Fabric adapter with v1/v2 JCS startup vectors, OpenBao seal verification, submit/reconciliation state machine, and fail-closed standby mode
[x] build/push immutable cloud OCI images, pin `image@sha256` refs, and run minimum startup/smoke checks
[x] create the reproducible three-host Compose deployment bundle, secret-safe env/host templates, four-image release file, disabled adapter-1/2 standby placement, and separate Fabric activation preflight under `evidence-services/cloud/deploy/`
[x] implement and compile/test the Rust journal/segment/state core + independent fixed vectors
[x] freeze evidence-ingest-receipt-v1 + stable retry receipt IDs/server time + Rust receipt validation state; no deletion path
[x] pin Concentratord 4.7.1 + MQTT Forwarder 4.6.0 upstream schema and implement `concentratord-uplink-correlation-v1` with an independent synthetic vector; Rust adapter Cargo PASS and the complete Go collector/verifier correlation path now passes Go tests/build
[x] select and commission SeaweedFS 4.41 durable raw-evidence infrastructure through S9 with cross-host production-helper verification
[x] finalize and commission shared-443 TCP/SNI passthrough + Evidence PKI; ChirpStack normal HTTPS and evidence client-certificate enforcement both verified
[x] provision read-only Grafana checkpoint and verification-state panels through the existing `telemetry_reader` datasource
```

The cloud source is beyond static-only validation: the pinned project-local Go 1.25.0 build path passes `gofmt`, `go test ./...`, `go build ./...`, and Linux/amd64 cross-builds. The current four-service tree has an accepted exact artifact set frozen in `cloud/packaging/binaries.lock`; `build-images.ps1 -Offline -ValidateOnly` rebuilds all four and passes the binary lock plus minimal `FROM scratch` Dockerfile gate. The checksum-pinned `-ResetToolchain` recovery mechanism was proven earlier; do not claim a new reset replay of the current four-binary tree. The accepted images were built/pushed through the Linux Buildx path and the production hosts now use immutable `ghcr.io/jervis-umtc/lorawan/...@sha256` references; host pull/inspection and runtime startup are commissioned. Rust/Cargo 1.82 also compiles/tests the journal/segment/state core. No physical gateway package was installed.

Verifier boundary: journal bytes, uplink schema, and the deterministic correlation path are implemented rather than guessed. Concentratord 4.7.1 is pinned to commit `0904a8ddf4eeb3150b4675b35f067865cb68827d` / `chirpstack_api 4.17.0`; MQTT Forwarder 4.6.0 is pinned to commit `04e870b4af97bebb278ab29259941fd8b3aad72b` / `chirpstack_api 4.18.0`; both published API artifacts contain byte-identical `gw.proto` SHA-256 `227fda5fd77fb115cb00610fb1ea1fa87c3112d972fc6534342dc7083a6dc12b`. ChirpStack 4.18 preserves `gw.UplinkRxInfo.uplink_id` inside application `rxInfo`, so the reviewed Node-RED provenance fields provide the first reception's Gateway EUI, uplink ID, frequency, context, RSSI, and SNR without a timestamp fallback. The Go verifier reopens/redecodes the MQTT object, verifies the semantic digest, fully verifies the matching closed journal segment and every predecessor object back to segment 1, recomputes the accepted checkpoint digest, and calls the lease-fenced `CompleteVerified` path only after the complete lineage and trusted-decoder comparison succeed. Go compilation/tests and the four deterministic Linux binary candidates are PASS. Live migration/credentials are no longer blockers. Those former cloud blockers are closed: three-node PgBouncer expansion, OCI digest pinning, SeaweedFS S9, Evidence PKI, collector ACLs, replicated services, shared-443 and read-only Grafana evidence views are live PASS. Full v2 normal-path acceptance now waits on the Gateway OS target package/physical lineage, plus public-provider activation where WAN access is required.

Uploader boundary: `evidence-ingest-receipt-v1`, the Rust HTTP/mTLS uploader process, durable receipt-file persistence and bounded retry/backoff are implemented and pass the current 28-test/default build gate. PostgreSQL returns the original `server_received_at`/`uploaded_at` on exact retry; Rust validates the returned identity/hash, persists canonical receipts before considering work acknowledged, and is restart-idempotent. SeaweedFS S9 and cloud ingest are commissioned. This is **not** approval to delete local evidence: the Rust source intentionally contains no retirement/delete API and physical-gateway reconciliation/retention policy remains pending.

Collector reliability note: a QoS 1 subscription does not upgrade a publisher's QoS 0 PUBLISH. The collector can withhold protocol acknowledgment only for received QoS > 0; final offline witness durability therefore requires the gateway-side publisher/bridge to use QoS 1 for the evidence topic path. The current gateway staging history still records QoS 0 with final QoS 1 planned, so do not claim outage-proof MQTT evidence until that later gateway boundary is closed.

The filesystem backend is **development-only** and may not be called HA storage. Production raw storage is the commissioned SeaweedFS S3-compatible path; S0-S9, including the exact locked production Go helper and cross-host retained-object verification, are PASS. Full application acceptance now waits on the physical gateway lineage rather than another storage gate.

OpenBao audit-device closure is complete. Preserve the commissioned audit path/rotation behavior and keep Fabric-adapter SecretID issuance at zero until the explicit activation preflight plus external Fabric handoff are ready.

## 5.8 Live deployment stop gate

Do not start `gateway-evidence-ingest`, `gateway-mqtt-evidence-collector`, or `gateway-evidence-verifier` until all are true:

```text
reviewed source/builds exist
immutable image/executable hashes are pinned
runtime UID/GID and writable paths are known
resource preflight fits the selected hosts
object-store technology/path and backup/recovery behavior are frozen
versioned gateway_evidence migration + grants are reviewed
collector broker identity/path is frozen
server/evidence-upload PKI is ready
shared TCP/443 ingress design validates without breaking ChirpStack
trusted decoder is pinned and passes fixed vectors
v2 canonicalization vector is independently reviewed
health/startup self-tests exist
Phase 14 capture commands are ready
rollback procedure is documented
```

Then deploy one dependency at a time in the logical order from Guide 4:

```text
storage + DB
-> ingest
-> collector
-> application path
-> verifier + trusted decoder
-> Grafana evidence views
-> one real verified staging lineage
-> Fabric v2 eligibility
```

Fabric adapter deployment remains its own implementation/handoff gate.

## 5.9 Current result

At the present repository state:

```text
EVIDENCE_CONTRACTS=PASS
EVIDENCE_REPLICATION_DESIGN=PASS
EVIDENCE_IMPLEMENTATION_BLUEPRINT=PASS
EVIDENCE_PREIMPLEMENTATION_GATE=PASS
EVIDENCE_CLOUD_RUNTIME=PASS
PUBLIC_INGRESS_NORMAL_PATH=PASS
PUBLIC_RESERVED_IP_FAILOVER=EXTERNAL_AUTH_PENDING
GATEWAY_EVIDENCE_RUNTIME=SERVER_PASS_GATEWAY_PENDING
GATEWAY_EVIDENCE_V2_NORMAL_PATH=NOT_YET_CLAIMED
```

The reviewed cloud implementation/deployment decisions and ordinary public Internet path are no longer blockers. The remaining normal-path gate is target Gateway OS packaging plus one physical gateway lineage; Reserved-IP failover authority/acceptance and Fabric remain separate external gates.
