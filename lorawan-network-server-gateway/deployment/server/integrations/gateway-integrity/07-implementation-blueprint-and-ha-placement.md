# 7. Evidence Services Implementation Blueprint and HA Placement

> **Status: CLOUD RUNTIME + PUBLIC NORMAL PATH COMMISSIONED / GATEWAY TARGET PACKAGE PENDING.** The full replicated cloud evidence placement is live with SeaweedFS S0-S9, three-node database/PgBouncer auth, immutable GHCR images, Evidence PKI/MQTT identities, ingest/collector/verifier replicas, disabled Fabric standbys, shared-443 and Grafana evidence views. The public ChirpStack/Evidence/MQTT normal path is also PASS. The Rust writer/uploader source runtime is implemented/tested. Remaining work is target-native Gateway OS/OpenWrt `concentratord-zmq` packaging and one real physical lineage; Reserved-IP failover authority and Fabric activation remain external gates.

## 7.1 Goal

Implement the evidence path as small, separately privileged services instead of one watcher with access to every trust boundary.

The target is:

```text
PHYSICAL GATEWAY

RAK5146
   |
   v
Concentratord 4.7.1
   |
   | ipc:///tmp/concentratord_event
   | local ZMQ / Concentratord event contract
   |
   +----------------------+----------------------+
   |                                             |
   v                                             v
MQTT Forwarder                           gateway-integrity-journal
   |                                             |
   v                                             v
local Mosquitto                         crash-safe hash chain
   |                                             |
   |                                     gateway-journal-uploader
   |                                             |
   |                                        HTTPS + mTLS
   |                                             |
===+=============================================+=================
   |                                             |
   v                                             v
cloud Mosquitto pair                    gateway-evidence-ingest-1/2
   |                                             |
   v                                             v
gateway-mqtt-evidence-collector-1/2     durable raw evidence store
   |                                             |
   +----------------------+----------------------+
                          |
                          v
                 gateway_evidence PostgreSQL
                          |
                    +-----+-----+
                    |           |
                    v           v
             verifier-1     verifier-2
             + decoder      + decoder
                    \           /
                     +---------+
                          |
                          v
              event_verification
                  status=verified
                          |
                          v
              telemetry.fabric_outbox
                          |
                          v
                    Fabric adapter
                          |
                       OpenBao
                          |
                          v
                  Hyperledger Fabric
```

The evidence services strengthen source provenance. They do not replace normal LoRaWAN authentication, MQTT delivery buffering, PostgreSQL HA, OpenBao, or Fabric.

## 7.2 Implementation language split

### Gateway: Rust

Use Rust for the gateway journal and uploader implementation.

Reasons:

- the gateway is ChirpStack Gateway OS / OpenWrt rather than Ubuntu;
- the implementation must subscribe to the pinned Concentratord event interface without owning SPI;
- the runtime should be a small compiled binary with no Python or Node runtime dependency;
- the existing custom Gateway OS build can package the reviewed binary reproducibly;
- crash-safe file I/O, deterministic hashing, Protobuf handling, and long-running low-memory operation are a good fit.

The current project implementation target, which must be re-proved before compiling the final package, is:

```text
Gateway OS:     ChirpStack Gateway OS 4.12.0 Base
Concentratord:  chirpstack-concentratord-sx1302 4.7.1
Gateway EUI:    0016c001f139a1cb
Region:         AS923
Event IPC:      ipc:///tmp/concentratord_event
```

Do not reverse-engineer an arbitrary binary stream. Pin and reuse the exact compatible Concentratord event Protobuf/schema contract for the commissioned release.

### Cloud: Go

Use Go for the initial cloud implementations of:

```text
gateway-evidence-ingest
gateway-mqtt-evidence-collector
gateway-evidence-verifier
```

Reasons:

- static compiled services with small operational footprint;
- mature HTTP/mTLS, MQTT, PostgreSQL, object-storage, metrics, and concurrency libraries;
- easy container packaging for the current Ubuntu/Docker cloud tier;
- lower operational overhead than adding a scripting runtime to every host.

This language split is an implementation decision, not a trust boundary. Contracts and fixtures must remain language-independent.

## 7.3 Gateway runtime implementation

### `gateway-integrity-journal`

The journal is an independent read-only subscriber beside MQTT Forwarder.

It must never:

```text
open /dev/spidev*
reset the RAK5146
change Concentratord configuration
publish MQTT
administer Mosquitto
hold cloud database credentials
hold OpenBao/Fabric credentials
```

For each accepted Concentratord uplink event:

```text
receive event
  -> extract only fields actually present in the pinned interface
  -> preserve exact PHYPayload/source evidence
  -> assign monotonic gateway sequence
  -> add previous_record_hash
  -> build gateway-journal-v1 record_body
  -> RFC 8785 canonicalize
  -> SHA-256 exact UTF-8 bytes
  -> append complete record
  -> advance durable state
```

Preferred filesystem shape:

```text
/var/spool/gateway-journal/
  state/
    current-sequence
    previous-record-hash
    previous-segment-hash
  open/
    segment-<id>.open
  closed/
    segment-<id>.evidence
  upload-state/
    receipts.db
```

The implementation may refine filenames, but the permission boundary must remain:

```text
journal writer
  write state/open/closed

uploader
  read closed
  read chain/checkpoint state
  write upload-state only
```

Closed segments are create-once historical evidence. The uploader must not rewrite them to make an upload pass.

### `gateway-journal-uploader`

Run independently from the writer, even if both commands come from the same Rust codebase.

Healthy WAN:

```text
journal continues
MQTT delivery continues
uploader checkpoints/uploads
```

WAN outage:

```text
journal continues
Mosquitto queue grows
uploader retries/stops advancing cloud state
closed segments remain local
```

WAN recovery:

```text
Mosquitto drains independently
uploader sends missing segments independently
```

A plain HTTP `200` is not permission to delete local evidence. The accepted response must bind at least:

```text
gateway_id
segment/checkpoint identity
expected digest/hash
receipt_id
server_received_at
```

Only then may the local retention policy consider an acknowledged segment removable.

## 7.4 Cloud raw evidence storage decision

PostgreSQL remains the authoritative metadata, lease, and verification-state layer. Do not use the current Patroni cluster alone as the raw-byte durability mechanism.

The commissioned Patroni replicas use asynchronous streaming replication. Therefore a primary COMMIT acknowledgement does not by itself prove that a just-accepted raw object already exists on another PostgreSQL member at that instant.

Use this split:

```text
PostgreSQL
  identities
  hashes
  object_ref
  receipts
  uniqueness constraints
  verifier leases
  verification state

Durable raw evidence backend
  exact closed journal segment bytes
  exact serialized MQTT event bytes when required
```

The cloud POC now uses a staged **SeaweedFS OSS 4.41** design rather than a managed object-store dependency. The three existing Droplets are separate SeaweedFS racks inside data center `sgp1`; placement `010` keeps two synchronous raw-data copies on two distinct hosts. Filer namespace metadata uses a separate tiny three-member etcd quorum on `12379/12380`, not the Patroni DCS etcd. The Seaweed S3 listener is loopback-only and the evidence services reach it through an internal-PKI HAProxy endpoint on `:18443` that permits only GET/HEAD and `PUT` with exact `If-None-Match: *`; DELETE, POST/multipart, administration, and unconditional overwrite are rejected before SeaweedFS. This extra proxy restriction is required because SeaweedFS's S3 `Write` permission is broader than our immutable-runtime authority.

The storage interface and the selected-backend acceptance path are implemented. The accepted ingest binary includes `objectstore-contract-write` and `objectstore-contract-verify`, which exercise the exact production AWS Go SDK/S3 implementation for first-create, idempotent duplicate, conflicting duplicate, concurrent-create arbitration, read-back SHA-256, and cross-host verification. What remains is operational commissioning: pin real SeaweedFS/metadata-etcd image digests, deploy and measure the cluster, create the private bucket, prove effective `010` placement and the HAProxy/TLS method boundary, then run those production-binary acceptance commands before live HA evidence activation.

Required ACK rule:

```text
HTTP/MQTT evidence object is not "accepted" until
  raw-byte durability policy is satisfied
  AND
  PostgreSQL metadata commit succeeds
```

Required storage semantics:

```text
create-if-absent
no in-place overwrite
stable non-secret object_ref
SHA-256 stored independently in PostgreSQL
conflicting duplicate rejected/preserved
one Droplet loss cannot remove the only accepted copy
exact-byte recovery must reproduce recorded SHA-256
```

Do not replace this with two unsynchronized folders or periodic rsync and call that HA.

## 7.5 Cloud service placement - pursue HA

The cloud evidence tier must be deployed with two independent runtime replicas for every evidence-processing responsibility.

Target placement:

```text
ulc-01
  gateway-evidence-ingest-1
  gateway-mqtt-evidence-collector-1

ulc-02
  gateway-evidence-ingest-2
  gateway-evidence-verifier-1
  trusted decoder copy 1

ulc-03
  gateway-mqtt-evidence-collector-2
  gateway-evidence-verifier-2
  trusted decoder copy 2

Downstream sealing tier already frozen elsewhere in the cloud architecture:
ulc-01
  Fabric adapter-1 target
ulc-02
  Fabric adapter-2 target
```

Why this distribution:

- each evidence role survives loss of the host carrying its peer;
- no host carries both replicas of the same responsibility;
- the two roles are balanced at roughly two evidence runtimes per host;
- both verifier copies are kept off `ulc-01`, which already carries several ingress/database/broker responsibilities;
- collector replicas are split across the two sides of the broker topology rather than colocated;
- ingest remains available from either public-ingress candidate when one application host is lost.

Initial measurement ceiling per cloud evidence runtime remains:

```text
RAM  192 MiB
CPU  0.20
```

Expected starting evidence-service reservation:

```text
ulc-01  ~384 MiB / 0.40 CPU
ulc-02  ~384 MiB / 0.40 CPU
ulc-03  ~384 MiB / 0.40 CPU
```

These are guardrails, not guaranteed production sizing. HA is not optional to preserve a 2-GiB price point. If measured headroom is unsafe, increase server capacity instead of deleting replicas.

### Critical-path HA policy

The server tier pursues HA according to consequence of failure:

```text
MUST survive one server loss without losing authoritative state or requiring manual reconstruction
  etcd / Patroni coordination
  PostgreSQL/TimescaleDB data
  MQTT cloud ingress
  ChirpStack application service
  Valkey/Sentinel dependency path
  OpenBao signing service
  Node-RED ingestion through fenced active/passive promotion
  evidence ingest
  MQTT evidence collector
  evidence verifier
  raw evidence bytes
  Fabric adapter/outbox processing

MAY remain single-instance when its loss does not stop ingestion, verification, or durable data
  Grafana visualization
```

The current physical gateway is still one Raspberry Pi/RAK5146 device. Cloud HA cannot make that single radio gateway physically redundant. If end-to-end gateway availability must also survive hardware loss, a second independently provisioned LoRaWAN gateway is a separate future HA requirement. Do not claim complete end-to-end HA from server replication alone.

## 7.6 `gateway-evidence-ingest` implementation

Run `ingest-1` on `ulc-01` and `ingest-2` on `ulc-02` active/active.

The service accepts only authenticated gateway evidence uploads. It does not declare telemetry verified.

For a closed segment:

```text
1. validate evidence-route mTLS client certificate
2. map certificate identity to exactly one Gateway EUI
3. require request gateway_id to match that mapping
4. enforce body/version/rate limits
5. calculate SHA-256 of exact uploaded bytes
6. create raw object under stable identity
7. insert immutable segment/checkpoint metadata
8. return receipt only after raw durability + DB commit
```

Idempotency:

```text
same gateway + same segment identity + same digest
  -> return existing logical acceptance safely

same gateway + same segment identity + different digest
  -> security conflict
  -> never UPDATE historical content to match retry
```

Use separate workload credentials for ingest-1 and ingest-2.

## 7.7 Shared public :443 design

The public anchor already uses TCP/443 for ChirpStack HTTPS. Evidence must not create another independent listener on the same address/port.

Target behavior:

```text
public :443
   |
   +-> SNI chirpstack.<DOMAIN>
   |     normal ChirpStack browser/API TLS policy
   |
   +-> SNI evidence.<DOMAIN>
         evidence-specific TLS/mTLS policy
         client certificate mandatory
         backend = ingest-1/2
```

The commissioned implementation uses HAProxy TCP ClientHello inspection on each DigitalOcean anchor address. `shared_https_sni` remains TCP mode; `evidence.internal.lorawan.com` is passed unchanged to the local ingest listener on the host private address, while `chirpstack.internal.lorawan.com` is sent to a loopback `127.0.0.1:14443` TLS-terminating frontend that preserves the pre-existing ChirpStack HTTP backend. On `ulc-01`, for example, the verified shape is:

```haproxy
frontend shared_https_sni
    bind 10.15.0.5:443
    mode tcp
    tcp-request inspect-delay 5s
    tcp-request content accept if { req_ssl_hello_type 1 }
    acl sni_evidence req.ssl_sni -i evidence.internal.lorawan.com
    acl sni_chirpstack req.ssl_sni -i chirpstack.internal.lorawan.com
    use_backend evidence_https_passthrough if sni_evidence
    use_backend chirpstack_https_termination if sni_chirpstack
    default_backend chirpstack_https_termination

backend evidence_https_passthrough
    mode tcp
    server evidence-ingest-local 10.104.0.2:18100 check

backend chirpstack_https_termination
    mode tcp
    server chirpstack-tls-local 127.0.0.1:14443 check
```

`ulc-02` uses the same pattern with its own anchor/private ingest address. The anchor `10.15.0.x` addresses are DigitalOcean host-local anchor addresses, not the east-west `10.104.0.x` service VPC. Public activation later substitutes real public FQDN/certificates/Reserved-IP provider state without changing the trust split.

The implementation preserves these invariants:

```text
ordinary ChirpStack clients are not forced to present gateway client certificates
evidence uploads cannot reach the ChirpStack backend
unauthenticated evidence uploads are rejected
valid evidence identity maps to exactly one Gateway EUI
```

This was validated one anchor at a time on 2026-09-01 with rollback copies retained. ChirpStack stayed HTTP 200, evidence without a client certificate was rejected, and a representative gateway mTLS request traversed the shared SNI layer to ingest readiness successfully.

## 7.8 `gateway-mqtt-evidence-collector` implementation

Run:

```text
collector-1 -> ulc-01
collector-2 -> ulc-03
```

Each collector must maintain direct persistent read-only sessions to both broker backends:

```text
collector-N -> broker ulc-01
collector-N -> broker ulc-02
```

Do not rely on one HAProxy-routed session because the Mosquitto brokers do not replicate MQTT session/queue state.

Use four distinct client IDs in total and independently revocable credentials.

ACL:

```text
ALLOW READ  as923/gateway/+/event/#
DENY WRITE
DENY command/#
DENY application command topics
DENY unrelated administrative/state topics unless explicitly required later
```

For every observation compute a versioned deterministic capture identity, for example conceptually:

```text
capture_key_sha256 = SHA256(
  version tag
  + exact MQTT topic bytes
  + fixed delimiter
  + exact serialized event bytes
)
```

The exact byte construction must be frozen by tests before deployment.

Both collectors may see the same event. PostgreSQL `UNIQUE(capture_key_sha256)` plus create-if-absent raw-object semantics must collapse duplicate execution into one logical MQTT witness.

## 7.9 `gateway-evidence-verifier` implementation

Run verifier workers active/active on `ulc-02` and `ulc-03`.

The verifier is the correlation/security engine. It has no OpenBao signing permission, no Fabric client key, and no MQTT publish permission.

### Work discovery

The earlier contracts define pending-row leasing but did not explicitly assign initial work creation. Freeze this responsibility in the verifier implementation.

The verifier contains two logical loops:

```text
A. discovery/reconciliation loop
B. verification worker loop
```

Discovery scans durable evidence-selected application work, primarily `telemetry-attestation-v2` outbox/source identities, and idempotently ensures a matching verifier work row exists:

```text
(source_event_key, observed_at)
  -> INSERT gateway_evidence.event_verification status=pending
  -> ON CONFLICT DO NOTHING
```

Node-RED does not create `verified` state. The Fabric adapter does not create verifier work. No new Kafka/RabbitMQ/Valkey queue is required.

### Work claiming

Both verifier replicas use the existing documented pattern:

```text
FOR UPDATE SKIP LOCKED
worker_id
lease_expires_at
attempts
next_attempt_at
```

Commit the lease before raw-object reads or trusted decoding. A crashed worker leaves an expiring lease that the other verifier may reclaim.

### Verification algorithm

For one evidence-selected application event:

```text
1. load source_event_key + observed_at
2. identify exactly one accepted ChirpStack application row and validate its stored first-reception provenance
3. locate exactly one MQTT witness by Gateway EUI + uplink ID + frequency + gateway context; never by nearest timestamp
4. reopen the immutable MQTT object and recompute serialized SHA-256 + mqtt-capture-v1
5. re-decode the pinned gw.UplinkFrame and recompute concentratord-uplink-correlation-v1
6. locate the journal record carrying exactly that semantic digest
7. reopen the candidate closed journal object and recompute object/record/content/segment hashes
8. reopen and fully verify every predecessor segment object from segment 1 through the match
9. prove cross-segment previous_segment_hash / previous_record_hash / sequence continuity from GENESIS
10. load the accepted checkpoint for the matched segment final sequence and recompute gateway-checkpoint-v1 checkpoint_digest
11. run the pinned trusted decoder on exact raw application bytes
12. canonicalize/hash normalized result and compare all approved TimescaleDB metrics
13. persist the complete gateway/journal/checkpoint/MQTT/decoder lineage under the worker lease
14. if and only if every required check succeeded, atomically persist that complete projection and promote the still-owned pending row to status=verified; otherwise keep/release pending or record the reviewed failure state
```

Terminal states:

```text
verified
evidence_gap
integrity_failure
not_required
```

Keep `pending` only for work still legitimately waiting on evidence or retry time.

## 7.10 Trusted decoder implementation

The trusted decoder should initially be a pure deterministic library packaged inside the verifier image rather than another network service.

Both verifier images must contain the same immutable decoder bytes and expose at startup:

```text
decoder_id
decoder_version
decoder_digest
fixture-suite result
```

Decoder rules:

```text
input = exact raw ChirpStack application bytes
output = versioned normalized metric object + normalized digest
no wall clock
no random input
no network call
no database-dependent decoding
```

Node-RED remains the operational normalization path. The trusted decoder is a second independent implementation used for evidence comparison.

If the trusted decoder and stored telemetry materially disagree, result is `integrity_failure`; never choose whichever result looks more plausible.

## 7.11 PostgreSQL ownership and queues

Keep PostgreSQL as the durable coordination layer:

```text
gateway_evidence.checkpoints
gateway_evidence.segments
gateway_evidence.mqtt_gateway_events
gateway_evidence.event_verification
telemetry.fabric_outbox
```

Consider a dedicated append-only `gateway_evidence.ingest_conflicts` table during migration review so security conflicts can be retained without mutating accepted history.

Do not use Valkey as an evidence work queue. PostgreSQL already supplies:

```text
transactional source identity
uniqueness
SKIP LOCKED
worker leases
durable retry state
HA through Patroni
```

Introducing another queue would create an extra reconciliation boundary without a demonstrated need at the expected sensor rate.

## 7.12 Health, readiness, metrics, and logs

Every cloud evidence service must expose bounded operational endpoints such as:

```text
/healthz
/readyz
/metrics
```

Readiness must fail when the service cannot safely perform its responsibility. Examples:

```text
ingest: required raw store or DB path unavailable
collector: required broker sessions unavailable beyond policy
verifier: database unavailable, evidence object store unavailable, or trusted-decoder startup vector fails
```

Use structured logs containing identifiers and reason codes, not secrets.

Allowed examples:

```text
service
gateway_id
segment_id
capture_key_sha256
source_event_key
verification_id
status
reason_code
worker_id
```

Never log:

```text
private keys
certificate private material
passwords
OpenBao tokens/SecretIDs
Fabric client private keys
raw secret bootstrap material
```

## 7.13 Repository implementation shape

The initial source tree should separate language-independent contracts from runtimes:

```text
evidence-services/
  contracts/
    gateway-journal-v1
    gateway-checkpoint-v1
    mqtt-capture-v1
    telemetry-attestation-v2 vectors

  gateway/
    Cargo.toml
    journal/
    uploader/
    concentratord/
    tests/

  cloud/
    go.mod
    cmd/
      evidence-ingest/
      mqtt-evidence-collector/
      evidence-verifier/
    internal/
      canonical/
      database/
      objectstore/
      mqttcapture/
      verification/
      trusteddecoder/
    tests/

  migrations/
    001_gateway_evidence.sql

  fixtures/
    valid/
    tampered/
    reordered/
    missing-record/
    checkpoint-conflict/
    decoder-mismatch/

  build/
    gateway-openwrt/
    containers/
```

Do not create empty placeholder images only to make this tree appear deployed. Each runtime is promoted only after a reproducible build, immutable artifact, startup self-test, and the minimum Guide 6 commissioning checks exist. The extended failure suite does not block initial deployment.

## 7.14 Implementation order

Build in this order:

```text
1. freeze the language-independent record/checkpoint/capture contracts and one valid v2/decoder vector
2. create the `evidence-services/` source tree and shared Go config/log/database/object-store packages
3. implement the object-store interface plus a filesystem **dev-only** backend
4. create reviewed `001_gateway_evidence.sql` + least-privilege grants
5. build/pin the trusted decoder and one valid fixed fixture
6. build `gateway-evidence-ingest`
7. build `gateway-mqtt-evidence-collector` with deterministic `capture_key_sha256`
8. build `gateway-evidence-verifier` discovery + lease workers
9. **PASS** - build immutable cloud images, pin the four GHCR `image@sha256` refs and run startup/smoke checks
10. **PASS** - commission SeaweedFS S9, Evidence PKI and shared-443 TCP/SNI ingress
11. **PASS** - deploy ingest pair, dual-broker collector pair and verifier/trusted-decoder pair with Guide 6 readiness checks; keep both Fabric adapters disabled
12. **PASS** - add read-only Grafana evidence checkpoint/verification observability
13. **CURRENT GATE** - cross-build/package the implemented Rust writer/uploader with `concentratord-zmq` in the pinned Gateway OS/OpenWrt toolchain, install the consolidated gateway identities/config and validate service supervision/filesystem paths
14. run one real gateway v2 lineage when hardware returns
15. Fabric adapter cloud standby is already deployed; release its OpenBao/Fabric credentials and enable it only after the external Fabric handoff and one deliberate activation preflight
```

Do not start with six empty containers. Buildable immutable artifacts and minimum smoke checks come before live credentials/listeners; the extended failure/chaos suite does **not** block the first working deployment.

## 7.15 HA acceptance matrix

| Responsibility | HA model | Duplicate-work control | Durable truth |
|---|---|---|---|
| Gateway journal | Single physical gateway, crash-safe | monotonic sequence/hash chain | local journal + cloud checkpoints |
| Gateway uploader | Restart/resume | receipt identity | upload-state + server receipt |
| Evidence ingest | 2x active/active | stable segment/checkpoint identity + digest | raw store + PostgreSQL |
| MQTT collector | 2x active/active, each sees both brokers | `capture_key_sha256` uniqueness | raw store + PostgreSQL |
| Verifier | 2x active/active | DB lease + `SKIP LOCKED` | `event_verification` |
| Trusted decoder | identical stateless copy per verifier | immutable digest + fixture suite | verifier result records decoder identity |
| PostgreSQL | Patroni 3-node HA | database transactions/constraints | metadata/state |
| Raw evidence | independent replicated/object storage | create-if-absent + SHA-256 | exact raw bytes |
| OpenBao | 3-node Raft HA | Raft | signing key/state |
| Fabric adapter | target 2x lease-safe workers | outbox lease/idempotency | outbox + Fabric ledger |

`replicas: 2` alone is never the proof. Every pair needs a deterministic convergence mechanism and a durable state layer.

## 7.16 One real acceptance lineage

The first complete runtime proof must trace one real uplink through both independent branches:

```text
EMU-01
  -> LoRaWAN RF
  -> RAK5146
  -> Concentratord
       |\
       | +-> journal record
       |      -> closed segment/checkpoint
       |      -> replicated evidence ingest
       |      -> durable raw evidence object
       |
       +-> MQTT Forwarder
              -> local Mosquitto
              -> cloud Mosquitto
              -> collector witness

ChirpStack
  -> accepted application event
  -> Node-RED
  -> TimescaleDB

journal + MQTT witness + ChirpStack identity + TimescaleDB
  -> verifier + trusted decoder
  -> gateway_evidence.event_verification = verified
  -> matching telemetry-attestation-v2 outbox becomes eligible
  -> Fabric adapter
  -> OpenBao
  -> Hyperledger Fabric
```

Only this kind of complete lineage may justify:

```text
GATEWAY_EVIDENCE_V2_NORMAL_PATH=PASS
```

## 7.17 Immediate implementation boundary

The first real source tranche now exists under repository root `evidence-services/`:

```text
evidence-services/
  contracts/
    mqtt-capture-v1/README.md
  cloud/
    go.mod
    internal/config/
    internal/database/
    internal/logging/
    internal/mqttcapture/
    internal/objectstore/
  migrations/
    001_gateway_evidence.sql
    001_gateway_evidence.verify.sql
```

Implemented/current boundaries:

```text
shared Go config/log/database/object-store foundation        BUILD/TEST PASS
filesystem object store                                     DEV/SMOKE ONLY
SeaweedFS production S3-compatible path                      LIVE S0-S9 / PASS
create-if-absent + exact-duplicate + conflict semantics      LIVE / PASS
mqtt-capture-v1 exact byte construction/vector               FROZEN / PASS
001_gateway_evidence.sql + verifier                          LIVE / THREE-NODE PASS
NOLOGIN ingestor/collector/verifier authority shells         LIVE
six workload SCRAM LOGIN identities                          LIVE / THREE-NODE PASS
20-rule evidence-aware HBA + group CONNECT                   LIVE / PASS
PgBouncer evidence userlist                                  THREE-NODE TEN-ROLE PASS
immutable GHCR release + cloud evidence listeners            LIVE / PASS
Evidence PKI + collector MQTT mTLS/ACLs                      LIVE / PASS
shared-443 SNI + Grafana evidence views                      LIVE / PASS
gateway Rust writer/uploader runtime                         SOURCE TEST PASS; TARGET PACKAGE PENDING
```

The fixed replicated-collector vector is:

```text
capture_key_sha256 = de1a848838d6d27e02261e0cc37d3478e70dfd5e0e1d381927349dfe803ead74
```

The cloud Go source now has a real reproducible compile/test gate. A project-local, checksum-pinned Go 1.25.0 toolchain runs `gofmt`, `go test ./...`, `go build ./...`, and Linux/amd64 cross-builds without requiring a global Go installation. An offline `-ResetToolchain` run rebuilt the compiler from the verified cached archive and reproduced identical executable hashes. Docker/OCI packaging and live cloud runtime readiness are now commissioned; only the Gateway OS target package/physical lineage remains unclaimed.

Current status:

```text
EVIDENCE_CONTRACTS=PASS
EVIDENCE_REPLICATION_DESIGN=PASS
EVIDENCE_IMPLEMENTATION_BLUEPRINT=PASS
EVIDENCE_SOURCE_FOUNDATION_STATIC=PASS
EVIDENCE_MIGRATION_STATIC_POLICY=PASS
MQTT_CAPTURE_V1_VECTOR=PASS
EVIDENCE_GO_COMPILE_TEST=PASS
EVIDENCE_GO_REPRODUCIBLE_BUILD=PASS
EVIDENCE_GO_OFFLINE_RESET_REBUILD=PASS
TRUSTED_DECODER_SOURCE_VECTOR_STATIC=PASS
EVIDENCE_INGEST_API_CONTRACT=FROZEN
EVIDENCE_INGEST_CORE_STATIC=PASS
EVIDENCE_CHECKPOINT_DIGEST_VECTOR=PASS
EVIDENCE_POSTGRES_CONNECTION_POLICY_STATIC=PASS
EVIDENCE_POSTGRES_REPOSITORY_STATIC=PASS
EVIDENCE_DB_CHECKPOINT_INVARIANT_STATIC=PASS
EVIDENCE_INGEST_EXEC_STATIC=PASS
EVIDENCE_MQTT_SESSION_CONFIG_STATIC=PASS
EVIDENCE_MQTT_DURABLE_CAPTURE_STATIC=PASS
EVIDENCE_MQTT_READONLY_ACK_STATIC=PASS
EVIDENCE_MQTT_EXEC_HEALTH_STATIC=PASS
MQTT_CAPTURE_V1_VECTOR_RECHECK=PASS
EVIDENCE_VERIFIER_LEASE_DISCOVERY_STATIC=PASS
EVIDENCE_VERIFIER_APPLICATION_STAGE_STATIC=PASS
EVIDENCE_VERIFIER_DECODER_RUNTIME_STATIC=PASS
EVIDENCE_VERIFIED_DB_INVARIANT_STATIC=PASS
EVIDENCE_VERIFIER_NO_VERIFIED_PATH=PASS
NODE_RED_V2_RECEPTION_PROVENANCE_SOURCE=PASS
EVIDENCE_MQTT_CONTEXT_STATIC=PASS
EVIDENCE_VERIFIER_JOURNAL_READER_STATIC=PASS
EVIDENCE_VERIFIER_CHECKPOINT_DIGEST_STATIC=PASS
EVIDENCE_VERIFIER_LINEAGE_SOURCE_STATIC=PASS
GATEWAY_JOURNAL_RUST_TESTS=PASS
GATEWAY_JOURNAL_V1_VECTOR=PASS
GATEWAY_SEGMENT_V1_VECTOR=PASS
GATEWAY_CONCENTRATORD_SCHEMA_PIN=PASS
GATEWAY_CONCENTRATORD_ADAPTER_RUST=PASS
MQTT_UPLINK_CORRELATION_V1_SOURCE=PASS
GATEWAY_CONCENTRATORD_REAL_FIXTURE=BLOCKED
EVIDENCE_VERIFIER_JOURNAL_READER_STATIC=PASS
EVIDENCE_INGEST_RECEIPT_V1=PASS
GATEWAY_UPLOADER_RECEIPT_VALIDATION=PASS
GATEWAY_UPLOADER_RECEIPT_RETIREMENT=BLOCKED
EVIDENCE_PREIMPLEMENTATION_GATE=PASS
EVIDENCE_CLOUD_RUNTIME=PASS
PUBLIC_INGRESS_NORMAL_PATH=PASS
PUBLIC_RESERVED_IP_FAILOVER=EXTERNAL_AUTH_PENDING
GATEWAY_EVIDENCE_RUNTIME=SERVER_PASS_GATEWAY_PENDING
GATEWAY_EVIDENCE_V2_NORMAL_PATH=NOT_YET_CLAIMED
```

The trusted-decoder, complete ingest path, replicated MQTT collector, and verifier lineage path are implemented and pass the pinned Go 1.25.0 format/test/build gate. The collector contract is intentionally direct to `10.104.0.2:8884` and `10.104.0.4:8884` with TLS identity `mqtt.internal.lorawan.com`, one persistent client per backend, unique client IDs, dedicated authentication, subscription `as923/gateway/+/event/#`, opaque exact payload bytes, and no publish API. Raw MQTT bytes are written create-if-absent before PostgreSQL metadata; a QoS > 0 PUBLISH is manually acknowledged only after both persistence layers succeed. Duplicate observations converge through `mqtt-capture-v1`; conflicting durable identity fails closed. The fixed capture vector remains `de1a848838d6d27e02261e0cc37d3478e70dfd5e0e1d381927349dfe803ead74`.

A QoS 1 subscription cannot upgrade publisher QoS 0, so final outage-resilient MQTT evidence still depends on the gateway publisher/bridge being promoted to QoS 1. This is a later hardware boundary and is not falsely claimed by the collector source.

Verifier source owns v2 discovery, `FOR UPDATE SKIP LOCKED` claim with a committed lease before reads, lease-owner-fenced updates, exact application source loading, strict Base64 raw payload decoding, independent trusted-decoder execution, and the 13-metric stored-telemetry comparison. ChirpStack's preserved first `rxInfo` supplies a deterministic Gateway-EUI/uplink-ID/frequency/context join to the MQTT witness. The verifier then reopens and re-decodes the immutable MQTT object, recomputes its capture/correlation identities, parses and rehashes the exact closed journal object, reopens and verifies every predecessor segment object back to `GENESIS`, and recomputes the accepted `gateway-checkpoint-v1` digest. Complete matching lineage now enters the lease-fenced `CompleteVerified` path, which persists the complete projection and writes `status='verified'` only while the row is still pending and owned by that worker. Deterministic corruption or ambiguity can become `integrity_failure`; still-arriving evidence remains pending. The migration refuses any verified row unless the complete gateway/journal/checkpoint/MQTT/decoder/raw/normalized projection is present.

The Rust gateway journal core freezes exact record/segment bytes and passes real Cargo compilation/tests plus independent hash vectors. `evidence-ingest-receipt-v1` binds accepted checkpoint/segment identity, digest(s), and original persisted server time into stable receipt IDs; the receipt hash is not a signature and there is still no Rust evidence-delete/retire API.

The source-protobuf ambiguity is closed without fabricating a physical capture. Exact upstream inspection proved Concentratord 4.7.1 wraps `gw::UplinkFrame` inside `gw::Event` on `ipc:///tmp/concentratord_event`, while MQTT Forwarder 4.6.0 unwraps that event and publishes `UplinkFrame.encode_to_vec()` to `as923/gateway/<eui>/event/up`. Their locked `chirpstack_api` 4.17.0/4.18.0 artifacts contain byte-identical `gw.proto` SHA-256 `227fda5fd77fb115cb00610fb1ea1fa87c3112d972fc6534342dc7083a6dc12b`. `concentratord-uplink-correlation-v1` therefore correlates Gateway EUI, uplink ID, PHYPayload SHA-256, frequency, and gateway context rather than raw Protobuf bytes. Independent synthetic wire bytes produce digest `a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494`; the Rust adapter compiles/tests on Rust 1.82. Go MQTT collector source projects the same fields only after immutable raw-object persistence, and the **live migration** enforces the all-or-none semantic projection. Go compilation is closed for the current four-service tree: the pinned portable Go 1.25.0 full offline gate passes and `build-images.ps1 -Offline -ValidateOnly` reproduces the exact four-binary lock. Registry OCI image build/push/digest pinning is commissioned; production release files use immutable GHCR references and the hardened replicas are running.

The cloud lane is now complete for server commissioning. The remaining engineering boundary is the gateway target: the writer/uploader source includes crash-safe journal persistence, durable receipts, HTTPS/mTLS transport, bounded retry/backoff and continuous loops, and the fresh Rust 1.82 default gate passes 28 tests total plus format/Clippy/locked build. `concentratord-zmq` must now be compiled in the Gateway OS/OpenWrt-capable toolchain, packaged with service supervision and the consolidated gateway identity/config bundle, then proven with real Concentratord bytes. Do not repeat PgBouncer/S9/PKI/OCI/replica/shared-443/Grafana cloud commissioning without a relevant state change. One complete physical v2 lineage remains the gateway acceptance gate; Fabric ledger activation remains external-handoff dependent.
