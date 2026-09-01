# 4. Canonical Integrity-Watcher Service Architecture

This document is the canonical runtime architecture for the software-only gateway integrity and Fabric-attestation path.

Use it to answer one question consistently across the project:

> **Which long-running service observes each boundary, what durable state does it own, and what is allowed to happen before an event can reach OpenBao and Hyperledger Fabric?**

The design deliberately does **not** use one privileged process that “watches everything.” The system is split into small services with different credentials and write permissions. PostgreSQL and protected evidence storage carry durable state between them.

The individual data contracts remain authoritative in the gateway journal, server verifier, and Fabric-attestation manuals. This page defines how those contracts fit together as one deployable architecture.

---

## 4.1 Architectural rule: verification is a pipeline, not a mega-watcher

The safe design is:

```text
PHYSICAL GATEWAY
────────────────────────────────────────────────────────────────────

RAK5146 / SX1303
      |
      v
Concentratord
   /       \
  /         \
 v           v
MQTT       gateway-integrity-journal
Forwarder          |
  |                v
  v          local hash-chained journal
Local              |
Mosquitto           v
  |          gateway-journal-uploader
  |                |
  |                | HTTPS + mTLS
  |                v
  +---------> CLOUD / SERVER <--------------------------------------+

CLOUD / SERVER
────────────────────────────────────────────────────────────────────

remote Mosquitto                    gateway-evidence-ingest
      |                                      |
      |                                      +-> protected segment objects
      |                                      +-> checkpoint/segment metadata
      v                                      |
gateway-mqtt-evidence-collector              |
      |                                      |
      +-------------------+------------------+
                          |
                          v
                 gateway-evidence-verifier
                    ^        ^        ^
                    |        |        |
               ChirpStack  trusted   TimescaleDB
               app event   decoder   telemetry
                    \        |        /
                     +-------+-------+
                             |
                             v
              gateway_evidence.event_verification
                             |
                     status = verified
                             |
                             v
                    telemetry.fabric_outbox
                             |
                             v
                       fabric-adapter
                        /          \
                       v            v
                OpenBao Transit   Fabric Gateway
                                      |
                                      v
                              Hyperledger Fabric
```

There are two independent evidence branches before the verifier:

```text
Gateway journal path
  Concentratord -> journal -> uploader -> evidence ingest

Remote delivery witness path
  Concentratord -> MQTT Forwarder -> Mosquitto -> cloud MQTT collector
```

They meet only in the verifier. The journal never feeds ChirpStack, and the MQTT collector never writes the gateway journal.

---

## 4.2 Service inventory and ownership

### Service 1 - `gateway-integrity-journal`

**Location:** physical Raspberry Pi gateway.

**Purpose:** record what the supported Concentratord event interface exposed before application decoding and before the ordinary MQTT delivery path can transform the event.

**Reads:**

```text
supported Concentratord event/IPC interface - read only
```

**Writes:**

```text
journal open segment
journal sequence state
record hashes
segment hashes
```

**Must not own:**

```text
RAK5146 SPI control
Mosquitto administration
cloud evidence database credentials
OpenBao credentials
Fabric identity
```

For each accepted source event it performs:

```text
source event
  -> versioned record_body
  -> add gateway sequence + previous_record_hash
  -> RFC 8785 canonicalization
  -> UTF-8 bytes
  -> SHA-256
  -> append {record_body, record_hash}
  -> advance sequence/hash state
```

The record chain answers:

> Did a complete recorded gateway observation change, disappear from the middle, move, or break continuity?

### Service 2 - `gateway-journal-uploader`

**Location:** physical Raspberry Pi gateway.

**Purpose:** move already-created evidence off the gateway without making WAN availability a prerequisite for local evidence recording.

**Reads:**

```text
closed journal segments
current checkpoint state
upload acknowledgement state
```

**Writes locally:**

```text
upload receipt/acknowledgement state only
```

**Network access:**

```text
HTTPS + mutual TLS -> gateway-evidence-ingest
```

The uploader does not rewrite record bodies or recompute historical content to make an upload pass. It sends closed segments and checkpoints and accepts only a response that identifies the expected gateway, segment/checkpoint identity, and digest.

A WAN outage therefore behaves as:

```text
journal writer       continues
Mosquitto queue      grows
journal uploader     cannot advance cloud anchor
closed segments      remain local
```

When WAN returns, MQTT delivery and journal upload recover independently.

### Service 3 - `gateway-evidence-ingest`

**Location:** protected cloud/server application tier.

**Purpose:** authenticate each gateway upload and append accepted evidence to server-side durable storage.

**Responsibilities:**

1. terminate/validate the approved HTTPS + mTLS identity boundary;
2. map one upload identity to exactly one Gateway EUI;
3. apply body-size and version limits;
4. calculate the uploaded object SHA-256;
5. reject conflicting retries;
6. store raw closed-segment objects without overwrite;
7. insert checkpoint/segment metadata and receipt information;
8. return a receipt that identifies the accepted object.

It does **not** declare an application event verified. Ingest means “accepted for verification,” not “trusted.”

### Service 4 - `gateway-mqtt-evidence-collector`

**Location:** cloud/server application tier.

**Purpose:** independently preserve what the remote MQTT broker actually received from gateways.

**Broker permission:**

```text
READ gateway event topics only
WRITE denied
command topics denied
```

For each matching broker event it preserves:

```text
exact serialized event or protected object reference
serialized_event_sha256
PHYPayload digest when available
gateway ID
broker receive time
correlation identifiers
radio metadata required by the versioned matching contract
collector version
```

This service is an independent delivery witness. It does not replace ChirpStack and cannot publish corrective gateway events.

### Service 5 - `gateway-evidence-verifier`

**Location:** cloud/server application tier.

**Purpose:** turn independent evidence into one durable verification result.

This is the correlation engine, but it is still not a Fabric signer.

Its work is split into two logical loops so initial work creation is explicit:

```text
discovery/reconciliation loop
  -> scan durable evidence-selected application work, primarily telemetry-attestation-v2 source/outbox identities
  -> idempotently ensure one gateway_evidence.event_verification row exists
  -> new work begins as status=pending
  -> duplicate discovery uses the unique source identity and does not create a second authority row

verification worker loop
  -> claim pending work with DB lease and commit before evidence reads
  -> load exactly one accepted application source + first-reception provenance
  -> locate MQTT by exact Gateway-EUI/uplink-ID/frequency/context tuple
  -> reopen raw MQTT object, recompute object/capture identity, re-decode pinned gw.UplinkFrame
  -> recompute concentratord-uplink-correlation-v1 and compare application reception metadata
  -> locate the journal record carrying that semantic digest
  -> reopen and exactly verify the matching closed segment object
  -> reopen and exactly verify every predecessor segment object back to segment 1 / GENESIS
  -> verify record hashes, previous_record_hash links, segment hashes, and cross-segment continuity
  -> load the accepted checkpoint for the matched segment final sequence and recompute checkpoint_digest
  -> run the pinned trusted decoder on exact application bytes
  -> compare the matching TimescaleDB normalized rows
  -> persist the complete lineage projection and atomically promote the owned pending row to status=verified
```

Node-RED must not create `verified` state, and the Fabric adapter must not create verifier authority rows. The verifier is now the sole application-level author of that transition: `CompleteVerified` is lease-owner fenced, requires the row to remain `pending`, clears the worker lease, records `verified_at`, and writes the complete lineage projection in the same update. The migration additionally rejects incomplete verified rows. This does not claim a live verified event before the production evidence stack and real gateway lineage are commissioned. A separate Kafka/RabbitMQ/Valkey queue is not required for this low-rate design because durable discovery, uniqueness, retries, and leases already live in PostgreSQL.

The verifier owns transitions into states such as:

```text
pending
verified
evidence_gap
integrity_failure
not_required
```

It must not possess:

```text
OpenBao sign permission
OpenBao root/unseal material
Fabric client private key
Fabric submit authority
MQTT publish permission
```

### Component 6 - pinned trusted decoder

The trusted decoder is a deterministic service or library used by the verifier. It is independent of Node-RED's operational normalization flow.

Input:

```text
accepted raw ChirpStack application data
```

Output:

```text
versioned deterministic normalized metric object
normalized digest
```

The verifier compares this result with the stored telemetry row. This prevents the Node-RED flow from becoming its own evidence authority.

The decoder version or code identity must be pinned and recorded with the verification result.

### 4.2A Replication and failover model

Replication is defined per responsibility; do not clone processes without defining how duplicate work becomes safe.

```text
Gateway edge
  gateway-integrity-journal        one physical gateway; crash-safe local state, not fake HA
  gateway-journal-uploader         one physical gateway; restart/resume from durable acknowledgement state

Cloud evidence tier
  gateway-evidence-ingest          2 replicas, active/active
  gateway-mqtt-evidence-collector  2 replicas, active/active
  gateway-evidence-verifier        2 replicas, active/active DB-leased workers
  trusted decoder                  same immutable/stateless package on both verifier replicas
  raw evidence storage             cross-host durable; must survive one Droplet loss
  gateway_evidence PostgreSQL      inherits commissioned 3-node Patroni HA

Later sealing tier
  OpenBao                          commissioned 3-node Raft HA
  fabric-adapter                   target two lease-safe workers
```

**Ingest replicas:** both may receive the same gateway retry. Checkpoint `(gateway_id,last_sequence)` and segment `(gateway_id,segment_id)` identities are authoritative. Exact duplicate content is idempotent; different content under an existing identity is a security conflict. Raw objects are create-only. A response is not successful until both the raw-object durability rule and PostgreSQL metadata commit are satisfied.

**Collector replicas:** each replica uses its own revocable MQTT client identity and maintains persistent read-only sessions to both commissioned broker backends, not merely one session through the active/standby HAProxy route. The brokers do not replicate session state. Both collector replicas may therefore observe the same event. A versioned deterministic `capture_key_sha256` plus create-if-absent object semantics and a database uniqueness constraint collapse those duplicate observations into one logical MQTT counterpart.

**Verifier replicas:** both run the same reviewed image and trusted-decoder digest. Pending `event_verification` rows are claimed with a short `FOR UPDATE SKIP LOCKED` transaction plus expiring `worker_id` lease. The worker commits the lease before object reads/decoding and clears it only when persisting a terminal result. Expired leases are reclaimable after a crash. No verifier replica receives OpenBao or Fabric authority.

**Raw evidence storage:** two local directories are not replication. The selected live backend must provide at least two independent durable copies or equivalent erasure/replication semantics across failure domains. Initial commissioning proves the configured durability policy plus normal create/get/exact-SHA behavior; the deliberate one-Droplet-loss recovery exercise is deferred to Guide 3 / Phase 15. PostgreSQL `object_ref` remains logical/stable even if a storage replica moves. The commissioned Patroni replicas currently stream asynchronously, so PostgreSQL HA alone must not be treated as proof that a newly acknowledged raw evidence byte-object already exists on another member at ACK time. Keep PostgreSQL as metadata/state unless an explicit stronger raw-byte durability mechanism is separately proven.

**Single-host loss behavior:** normal telemetry may continue; evidence work may pause briefly but must resume without rewriting historical objects, creating a second authoritative MQTT counterpart, or losing an already-accepted checkpoint. A replica loss is a Phase 15 failure test, not part of commissioning.

### Durable state - `gateway_evidence`

PostgreSQL carries evidence indexes, hashes, references, and verification state. Large raw objects remain in protected evidence/object storage.

Key objects are:

```text
gateway_evidence.checkpoints
  server-side anchors of accepted gateway history

gateway_evidence.segments
  closed-segment metadata, hashes, object references, verification status

gateway_evidence.mqtt_gateway_events
  remote broker witness indexes/hashes

gateway_evidence.event_verification
  authoritative per-application-event verification result
```

The database is the durable handoff between the evidence services and the later Fabric worker. Services must not rely on an in-memory queue as the only copy of security state.

### Durable state - `telemetry.fabric_outbox`

The outbox is the asynchronous boundary between telemetry ingestion and blockchain availability.

Node-RED may atomically enqueue an attestation job with accepted telemetry, but Node-RED does not verify gateway evidence, create the OpenBao signature, or submit to Fabric.

For `telemetry-attestation-v2`, an outbox row is eligible for sealing only when the matching verifier-owned row is exactly:

```text
status = verified
```

### Service 7 - `fabric-adapter`

**Location:** protected application host/service tier.

**Purpose:** consume eligible durable outbox work, create the canonical attestation, seal it with OpenBao, submit it through Fabric Gateway, and reconcile the final ledger result.

It watches only durable database work. It does **not** watch Concentratord, the journal directory, or MQTT gateway topics.

Its work loop is:

```text
claim eligible outbox row with FOR UPDATE SKIP LOCKED
  -> commit worker lease
  -> load fixed source projection
  -> for v2 load exactly one status=verified gateway_evidence result
  -> build versioned canonical evidence
  -> RFC 8785 JCS
  -> exact UTF-8 bytes
  -> SHA-256 digest
  -> request OpenBao Transit signature
  -> persist the complete immutable seal before Fabric call
  -> re-read and verify persisted seal
  -> submit compact transaction through Fabric Gateway
  -> wait for commit status
  -> confirmed only after VALID commit
```

If final commit state is uncertain:

```text
submitted_unknown
  -> query/reconcile ledger
  -> do not blindly resubmit
```

---

## 4.3 Trust and permission matrix

| Component | Gateway journal write | MQTT gateway topics | Verification-state write | Telemetry/outbox write | OpenBao sign | Fabric submit |
|---|---:|---:|---:|---:|---:|---:|
| `gateway-integrity-journal` | Own evidence only | No | No | No | No | No |
| `gateway-journal-uploader` | No historical rewrite | No | No | No | No | No |
| `gateway-evidence-ingest` | Server append only | No | No | Evidence metadata only | No | No |
| `gateway-mqtt-evidence-collector` | No | Read only | No | Capture indexes only | No | No |
| `gateway-evidence-verifier` | No | No publish | Yes, verifier result only | Read telemetry | No | No |
| Node-RED | No | Application subscription only | No | Telemetry + enqueue only | No | No |
| `fabric-adapter` | No | No | Read only | Restricted outbox state/seal update | Yes, Transit policy only | Yes |
| Grafana | No | No | No | Read only | No | No |

This separation is a security property. A component compromise should not automatically grant enough authority to fabricate the complete evidence chain and blockchain attestation.

---

## 4.4 Exact end-to-end lifecycle for one uplink

### Stage 1 - Observe

```text
RAK5146 -> Concentratord
```

Concentratord remains the only radio owner.

### Stage 2 - Fan out before application processing

```text
Concentratord -> MQTT Forwarder
Concentratord -> gateway-integrity-journal
```

The two paths are independent.

### Stage 3 - Journal locally

The journal assigns its own monotonic gateway sequence, links the previous record hash, canonicalizes the record, computes SHA-256, and appends the complete record.

### Stage 4 - Deliver normally

MQTT Forwarder publishes to gateway-local Mosquitto. Mosquitto provides the bounded persistent delivery queue and bridges gateway events to the remote broker.

### Stage 5 - Anchor evidence off-device

The uploader sends checkpoints during healthy connectivity and uploads closed segments. The server stores accepted anchors outside the Raspberry Pi.

### Stage 6 - Capture an independent remote MQTT witness

The read-only MQTT collector stores what the cloud broker actually received before ChirpStack application processing.

### Stage 7 - Process the application event

ChirpStack performs the normal LoRaWAN processing and publishes the accepted application event. Node-RED performs operational validation/normalization and persists telemetry.

### Stage 8 - Verify source lineage

The verifier proves journal hash/segment/checkpoint continuity and correlates the journal observation with the remote MQTT witness and the accepted ChirpStack event.

### Stage 9 - Independently decode and compare

The pinned trusted decoder reconstructs the approved normalized values from accepted raw application data. The verifier compares that deterministic result with TimescaleDB.

### Stage 10 - Persist authoritative verification state

The verifier writes one `gateway_evidence.event_verification` row.

Only an unambiguous successful lineage becomes:

```text
verified
```

### Stage 11 - Gate v2 work

The Fabric Adapter's claim query requires the matching v2 verification row to be `verified`.

`pending`, `evidence_gap`, and `integrity_failure` must never be silently promoted just to drain an outbox queue.

### Stage 12 - Build attestation evidence

The Fabric Adapter loads the fixed v2 telemetry + gateway-evidence projection and creates the versioned canonical evidence object.

### Stage 13 - Hash and seal

```text
canonical evidence
  -> RFC 8785
  -> UTF-8
  -> SHA-256
  -> OpenBao Transit ECDSA P-256 signature
```

The journal record hash and the Fabric evidence digest are different hashes with different jobs:

```text
journal hash
  protects ordered gateway-history consistency

Fabric evidence digest
  identifies the complete verified attestation object
```

### Stage 14 - Persist the seal before network submission

The Adapter stores the canonical JSON, SHA-256 digest, signature algorithm, OpenBao key-version ID, complete versioned signature, and seal timestamp before the first Fabric network call.

### Stage 15 - Submit to Fabric

Only compact attestation fields are submitted through Fabric Gateway. Full raw evidence and telemetry remain off-chain.

### Stage 16 - Confirm or reconcile

A row becomes `confirmed` only after a valid Fabric commit. Unknown post-submit state becomes `submitted_unknown` and is reconciled against the ledger before any retry decision.

---

## 4.5 Service state machines

### Journal/uploader

```text
RECORDING
  |
  +-> segment closes -> READY_TO_UPLOAD
                         |
                         +-> WAN unavailable -> remain local
                         |
                         +-> accepted receipt -> ACKNOWLEDGED
```

A complete invalid historical record does not transition back into normal recording through automatic repair. It raises an integrity/recovery fault.

### Segment verification

```text
pending
  |
  +-> all cryptographic/lineage checks pass -> verified
  |
  +-> required evidence unavailable --------> evidence_gap
  |
  +-> contradictory bytes/hash/history -----> integrity_failure
```

### Per-event verification

```text
pending
  |
  +-> unique full lineage + decoder match -> verified
  |
  +-> required counterpart never arrives -> evidence_gap
  |
  +-> payload/hash/normalized conflict ---> integrity_failure
```

### Fabric outbox

```text
pending / failed
      |
      v
processing --valid commit--> confirmed
      |
      +--transient pre-submit failure--> failed + backoff
      |
      +--uncertain post-submit result--> submitted_unknown -> reconcile
      |
      +--permanent/security conflict--> dead_letter
```

For v2, `pending` outbox status alone does not mean eligible. The matching gateway verification must also be `verified`.

---

## 4.6 Startup and dependency order

### Gateway startup

```text
1. persistent gateway storage mounts
2. Concentratord starts and owns RAK5146
3. gateway-integrity-journal verifies/reopens local chain
4. local Mosquitto starts
5. MQTT Forwarder starts
6. network/backhaul becomes available
7. Mosquitto bridge reconnects
8. gateway-journal-uploader resumes checkpoints/closed segments
```

Evidence failure does not automatically stop telemetry delivery. The default architecture is availability-first: telemetry may continue while the evidence state becomes pending/gapped. That condition must remain visible and must block v2 promotion as required.

### Cloud/server startup

A safe logical order is:

```text
1. PostgreSQL/TimescaleDB and protected evidence storage available
2. cloud MQTT available
3. gateway-evidence-ingest starts
4. gateway-mqtt-evidence-collector starts
5. ChirpStack/application path available
6. gateway-evidence-verifier starts after DB/evidence dependencies are readable
7. OpenBao KMS available and unsealed
8. fabric-adapter starts only after its reviewed image, credentials, and external Fabric handoff exist
```

Services may restart independently because security state is durable. Restarting one evidence replica, the verifier pool, or the Fabric Adapter must not erase jobs or require reconstructing previously sealed evidence from mutable current telemetry. Replication never changes trust ownership: two ingestors are still only ingestors, two collectors are still read-only witnesses, and two verifiers still cannot sign.

---

## 4.7 WAN outage and recovery sequence

During gateway WAN loss:

```text
LoRaWAN reception                    continues
journal sequence/hash chain         continues
local journal segments              continue/rotate
Mosquitto persistent queue          grows
cloud MQTT witness                  receives nothing new
cloud checkpoint                    must not falsely advance
verification                        remains pending for missing remote evidence
```

After WAN returns:

```text
1. Mosquitto bridge reconnects and drains gateway events.
2. MQTT evidence collector captures those delivered events.
3. Journal uploader sends missing closed segments/checkpoints.
4. Evidence ingest stores them without replacing prior accepted evidence.
5. Verifier proves continuity from the latest accepted cloud anchor.
6. Verifier correlates journal records to MQTT captures.
7. Verifier links accepted ChirpStack application events.
8. Trusted decoder is compared with TimescaleDB.
9. Result becomes verified / evidence_gap / integrity_failure.
10. Only verified v2 events become eligible for OpenBao/Fabric work.
```

Delivery recovery and evidence recovery are separate. One becoming healthy does not imply the other is healthy.

---

## 4.8 What “monitoring the architecture” actually means

There is no additional privileged watcher required to decide whether the pipeline is healthy. Each service records durable state, and read-only operational views/Grafana can inspect that state.

Monitor at minimum:

### Gateway

```text
journal process/restarts
last journal sequence
last record hash
open/closed segment IDs
journal storage usage
unuploaded segment count/bytes
last accepted checkpoint receipt age
uploader retry/error state
Mosquitto queue usage and drain state
```

### Evidence server

```text
checkpoint ingest success/conflicts
segment upload backlog
oldest pending segment verification
gateway MQTT collector connectivity/lag
unmatched journal records
unmatched MQTT events
pending event-verification age
evidence_gap count
integrity_failure count
trusted decoder mismatch count
```

### Fabric gate

```text
v2 outbox rows blocked waiting for verification
verified-but-not-sealed age
failed adapter work
submitted_unknown count/age
dead_letter count
OpenBao sign/verify failures
Fabric commit/reconciliation failures
```

A key diagnostic example is:

```text
telemetry fresh + MQTT healthy + checkpoint stale
```

This means delivery is healthy while the evidence uploader/ingest path is degraded. Do not report the whole gateway as simply “healthy.”

---

## 4.9 Failure ownership

| Failure | Normal telemetry | Verification result | Fabric v2 consequence |
|---|---|---|---|
| Journal service down | May continue | Pending -> gap under policy | Blocked |
| WAN down | Buffered locally | Pending while remote evidence absent | Blocked until recovery/verification |
| Journal hash conflict | May continue | `integrity_failure` | Permanently blocked/security path |
| Journal segment missing | May continue | `evidence_gap` if contradiction not proven | Blocked or explicit business gap policy |
| MQTT collector down | Delivery may still work | Pending -> gap if evidence expires | Blocked |
| ChirpStack event missing | No accepted app lineage | Pending/gap | Blocked |
| Trusted decoder mismatch | Telemetry exists | `integrity_failure` | Blocked |
| Evidence verifier down | Telemetry remains available | Stays pending | Blocked |
| OpenBao down | Telemetry + verified evidence remain durable | Remains verified | Outbox waits/fails with retry policy |
| Fabric unavailable | Telemetry + seal remain durable | Remains verified | Outbox retries/reconciles; ingestion unaffected |

---

## 4.10 Implementation order

Build and commission in this order. Do not start at Fabric and work backward.

1. **Journal source adapter + fixed record test vector** — prove the exact supported Concentratord input and RFC 8785/SHA-256 output.
2. **Crash-safe journal/segment storage** — prove sequence continuity, reboot recovery, torn-tail handling, and segment chaining.
3. **Journal uploader + mTLS receipt contract** — prove checkpoints and closed-segment upload without coupling recording to WAN health.
4. **Evidence ingest + protected object store** — prove identity binding, idempotency, conflict rejection, and no overwrite.
5. **Read-only MQTT evidence collector** — prove exact capture and broker ACL isolation.
6. **Verifier cryptographic checks** — prove record/segment/checkpoint validation on fixed fixtures.
7. **Correlation + pinned trusted decoder** — prove journal/MQTT/ChirpStack/TimescaleDB lineage and mismatch classification.
8. **`gateway_evidence.event_verification` gate** — prove only verifier-owned `verified` results make v2 eligible.
9. **Fabric Adapter implementation** — only after the reviewed image/runtime exists and the external Fabric handoff is frozen.
10. **OpenBao/Fabric end-to-end attestation** — prove persisted seal verification, valid commit, unknown-result reconciliation, and idempotency.

For **initial commissioning**, prove only the minimum normal-path and trust-boundary checks needed to show the component works and cannot exceed its intended authority. Keep outage, process-loss, lease-expiry, tamper/reorder/delete/checkpoint-conflict, and other fault matrices in Guide 3 / Phase 15. A deeper failure test is required early only when the specific boundary cannot be trusted without it, such as rejecting an unauthenticated evidence upload.

---

## 4.11 Current implementation status boundary

Current recorded state:

```text
telemetry.fabric_outbox schema/ACL/immutability              -> commissioned / PASS
OpenBao 3-node KMS + audit                                  -> commissioned / PASS
SeaweedFS raw evidence infrastructure S0-S9                 -> commissioned / PASS
gateway_evidence migration/HBA/CONNECT/six LOGIN identities -> commissioned / PASS
PgBouncer evidence expansion                                -> three-node ten-role PASS
Immutable cloud OCI + ingest/collector/verifier replicas    -> commissioned / PASS
Evidence PKI + collector MQTT identities/ACLs               -> commissioned / PASS
Shared anchor :443 SNI + Grafana evidence views             -> commissioned / PASS
Fabric adapter immutable standbys                           -> disabled / PASS; external activation pending
Gateway Rust writer/uploader source runtime                 -> 28-test/build PASS; target OpenWrt package pending
```

The cloud implementation is now live rather than a source-only claim. The next work is target-specific: compile/package `concentratord-zmq` in the pinned Gateway OS/OpenWrt toolchain, install the protected gateway identities/config, and prove one physical lineage. The extended Guide 3 / Phase 15 failure matrix does not block that first real normal-path deployment.

OpenBao audit closure is already complete. Preserve that audit boundary and keep Fabric-adapter SecretID/ledger activation at zero until the external Fabric handoff and enabled-adapter preflight pass.

---

## 4.12 One-sentence architecture summary

```text
The gateway independently hash-chains what Concentratord observed, the cloud verifies that history against what MQTT and ChirpStack actually delivered and what the trusted decoder reconstructs from stored telemetry, and only the resulting verifier-owned `verified` evidence can be sealed by OpenBao and asynchronously committed to Hyperledger Fabric.
```
