# Granular Data-Flow Architecture Diagram Plan

> **Scope:** full LoRaWAN production/cloud HA architecture documented in this repository, with current commissioning state made explicit. This is not the stripped-down dissertation VM diagram.
>
> **Source basis:** all 160 Markdown files under `lorawan-network-server-gateway` were inventoried and scanned before defining this plan. The runtime build log and continuation checkpoints take precedence where older planning documents describe an earlier state.
>
> **Primary design rule:** include every technology that materially participates in the runtime data path, security/evidence path, HA/routing path, or read-only operational path, but do not create one box for every process, host, port, sensor board, or HA replica. Repeated technologies are grouped into logical clusters and their physical multiplicity is shown inside the cluster label.

## 1. Diagram objective

The final architecture diagram must let a reader answer these questions without reading the runbooks first:

1. Where does an uplink originate, and what exact path does it follow until it becomes durable telemetry?
2. Where is LoRaWAN security enforced, and where does IP/TLS security begin?
3. Why are there multiple MQTT layers on the gateway and in the cloud?
4. Where do HAProxy, PgBouncer, Patroni, Spilo, etcd, Valkey, Sentinel, and Mosquitto fit without falsely implying that all of them carry the same payload?
5. How does Node-RED receive an application uplink and persist it without synchronously depending on Hyperledger Fabric?
6. How does `telemetry.fabric_outbox` decouple telemetry ingestion from ledger submission?
7. What exactly does the Fabric Adapter read, hash, sign, submit, and reconcile?
8. Why is OpenBao a side security/KMS dependency rather than another hop in the normal telemetry payload chain?
9. How does the independent gateway integrity path relate raw radio evidence to MQTT delivery, ChirpStack processing, decoded telemetry, and Fabric v2 eligibility?
10. Which parts are already commissioned, which are still being commissioned, and which are external or implementation-blocked?

The diagram should therefore be a **layered data-flow architecture**, not a host inventory and not a deployment topology diagram disguised as a data-flow diagram.

## 2. Visual strategy

Use one large left-to-right architecture with four semantic lanes. Do not create four unrelated diagrams unless the final render becomes unreadable.

### 2.0 Global arrow-direction contract

The final render must use **one arrow meaning everywhere**:

> **An arrowhead points toward the component receiving the data, state, command, result, or control message named on that arrow.**

Do not alternate between "connection initiator" arrows and "data movement" arrows. That is the main cause of counterintuitive architecture diagrams.

Apply these rules consistently:

1. **Normal uplink payload moves left -> right only.** No main-path arrow may point backward.
2. **Downlink commands move right -> left only** and live in a separate thin lower lane so they never cross the uplink arrows.
3. **Database writes point toward PostgreSQL.** Database reads point away from PostgreSQL toward the reader.
4. **MQTT publication points publisher -> broker; MQTT delivery points broker -> subscriber.** Do not collapse publish and subscribe into one ambiguous arrow.
5. **Request/response integrations use two arrows when both directions matter.** Example: Adapter -> OpenBao for the sign request, then OpenBao -> Adapter for the returned signature.
6. **HA/control traffic is dashed and physically separated below the payload lanes.** A dashed arrow never masquerades as telemetry flow.
7. **A bidirectional arrow is allowed only when the relationship is genuinely ongoing two-way state exchange**, such as Patroni <-> etcd DCS or Sentinel <-> Valkey monitoring/reconfiguration. Prefer two explicitly labelled one-way arrows when the two directions carry different meanings.
8. **Read-only consumers receive arrows from the data source.** For example, PostgreSQL/TimescaleDB -> Grafana, not Grafana -> PostgreSQL, because the diagram is showing returned data rather than TCP session initiation.
9. **Avoid diagonal arrows across zones.** Route side branches vertically up/down first, then horizontally inside their own lane.
10. **No arrow may terminate on a label, boundary, or technology name that does not actually receive that traffic.** Every arrow ends on a concrete functional node or composite service boundary.

### 2.0A Visual routing rule

To keep arrow direction intuitive, the major boxes must be positioned in the same order as the event lifecycle. In particular, the cloud MQTT tier must be drawn as two logical broker surfaces belonging to the same Mosquitto HA pair:

```text
Gateway MQTT topics
        |
        v
Cloud MQTT gateway lane
        |
        v
ChirpStack
        |
        v
Cloud MQTT application-event lane
        |
        v
Node-RED
```

The two MQTT lane boxes should share one outer label such as `Cloud MQTT HA Tier - HAProxy + Mosquitto x2`. This avoids drawing a visually backward ChirpStack -> broker arrow merely because the same broker pair handles both gateway and application topics.

### Lane A - Primary uplink / application data plane

This is the dominant path and should visually read first:

```text
End device
  -> AS923 LoRaWAN RF
  -> RAK5146 gateway radio
  -> Concentratord
  -> MQTT Forwarder
  -> gateway-local Mosquitto buffer
  -> IP backhaul
  -> cloud MQTT ingress / broker HA
  -> ChirpStack
  -> application MQTT event
  -> Node-RED
  -> PostgreSQL / TimescaleDB
```

Use the thickest or strongest solid arrows for this lane.

### Lane B - Integrity and attestation plane

This lane runs in parallel with, and later correlates against, the main path:

```text
Concentratord
  -> Gateway Integrity Journal
  -> HTTPS/mTLS checkpoint + segment ingest

Cloud gateway MQTT topics
  -> Gateway MQTT Evidence Collector

Journal evidence + captured MQTT + ChirpStack application event + trusted decode + stored telemetry
  -> Gateway Evidence Verifier
  -> verification state
  -> Fabric v2 eligibility guard

TimescaleDB / fabric_outbox
  -> Fabric Adapter
     claim/read eligible durable work

Fabric Adapter
  -> OpenBao Transit
     sign/verify request
OpenBao Transit
  -> Fabric Adapter
     versioned signature / verification result

Fabric Adapter
  -> Fabric Gateway / chaincode
     transaction submission
Fabric Gateway / ledger
  -> Fabric Adapter
     commit status

Fabric Adapter
  -> fabric_outbox
     persist seal / submitted_unknown / confirmed state
```

Do **not** draw the integrity journal as feeding ChirpStack. Both readers consume Concentratord output independently and meet only during verification/reconciliation.

### Lane C - HA, routing, and coordination plane

This lane uses thin/dashed control arrows because it controls availability but normally does not carry the application payload itself. Direction must match the actual control exchange:

- Patroni <-> etcd: DCS reads/writes, leader lock, member state;
- Patroni -> PostgreSQL member: apply primary/replica role decisions;
- Sentinel <-> Valkey members: monitor, elect, and reconfigure the writable master;
- HAProxy -> Patroni / Valkey / Mosquitto / OpenBao: health probes;
- backend -> HAProxy: health/role response only when the response needs to be shown explicitly;
- Reserved-IP failover controller -> etcd: acquire/release the distributed ownership lock;
- Reserved-IP failover controller -> DigitalOcean API: move the Reserved IPv4 after the lock/health decision;
- PostgreSQL primary -> PostgreSQL replicas: WAL streaming;
- OpenBao voter <-> OpenBao voter: internal Raft replication/consensus, shown inside the KMS cluster rather than as an external payload arrow.

The purpose is to show **why an endpoint remains stable when the active backend changes** without making the main telemetry path zig-zag through control-plane services.

### Lane D - Read-only operations / observability

Keep this small and visually subordinate. Because arrows represent returned data, draw the read result from the database toward the consumer:

```text
PostgreSQL / TimescaleDB
  -> HAProxy replica/read route
  -> PgBouncer read connection boundary
  -> Grafana
```

If the final deployment uses the opposite local PgBouncer/HAProxy ordering for the Grafana connection, preserve the actual configured client path, but keep the arrowhead toward Grafana. Grafana is a consumer only. It must not appear between Node-RED and the database or as a control dependency.

## 3. Recommended top-level zones

Use six vertical zones from left to right.

### Zone 1 - Sensor / end-device domain

Use **one end-device group**, not one box per sensor board.

Inside the group label:

- RAK4631 WisBlock Core / nRF52840 + SX1262;
- EMU-01 normal deterministic sensor-emulation fixture;
- SEC-02 security-test fixture;
- Agriculture Kit sensor stack as an internal annotation, not individual network nodes.

The agriculture boards may be listed in compact secondary text when the diagram is intended for a technical audience, but they should not each receive arrows because they do not speak independently to the network. The RAK5802 RS485, RAK5801 4-20 mA, and RAK13010 SDI-12 boards are interfaces for possible external instruments and should not become main architecture nodes unless an actual external instrument is later commissioned.

Arrow to gateway:

```text
AS923 LoRaWAN / OTAA
AES-128 LoRaWAN session security
MIC + frame counters
```

Do not create separate boxes for Join Server, Network Session Key, AppSKey, frame counter, ADR, or spreading factor. Those are protocol/security properties, not independent runtime nodes in this deployment.

## 4. Zone 2 - Physical gateway appliance

Use one enclosing node titled approximately:

```text
Physical LoRaWAN Gateway
Raspberry Pi 4B + RAK5146/SX1303
ChirpStack Gateway OS 4.12.0
```

Inside it, show four functional subcomponents because they materially change data behavior.

### 4.1 RAK5146 / SX1303 concentrator

Role:

- receives LoRa RF frames;
- demodulates legal AS923 channels;
- is the only radio owner.

Connection into software:

```text
RAK5146 -> Concentratord
SPI
```

Do not create a separate Linux SPI-driver node.

### 4.2 ChirpStack Concentratord

Role:

- owns the concentrator interface;
- exposes the supported event/command IPC boundary;
- fans out radio observations to independent consumers.

Primary delivery output:

```text
Concentratord
  -> MQTT Forwarder
  event IPC: ipc:///tmp/concentratord_event
```

Integrity output:

```text
Concentratord
  -> Gateway Integrity Journal
  supported read-only interface
```

This fan-out is a critical concept and should be visually obvious.

### 4.3 ChirpStack MQTT Forwarder

Role:

- converts Concentratord gateway events/commands to MQTT;
- uses the local broker rather than the Internet broker directly.

Arrow:

```text
MQTT Forwarder
  -> Local Mosquitto
  127.0.0.1:1883
  topic prefix: as923
  Protobuf gateway events
  uplink/state QoS 1 target
```

Reverse command arrow:

```text
Local Mosquitto
  -> MQTT Forwarder
  -> Concentratord
  command traffic QoS 0
```

### 4.4 Gateway-local Mosquitto persistent store-and-forward

This is a separate MQTT role from the cloud broker and must remain visible.

Purpose:

- loopback-only broker for local decoupling;
- persistent bounded queue during backhaul loss;
- two bridge directions with different delivery semantics;
- prevents MQTT Forwarder availability from being directly tied to WAN availability.

Label it explicitly:

```text
Local Mosquitto
127.0.0.1:1883 only
persistent bounded store-and-forward
```

Do not call this the cloud broker and do not draw application subscribers against it.

### 4.5 Gateway Integrity Journal

Show as a sidecar inside the gateway, not inline with MQTT delivery.

Role:

- records the received radio/source evidence from the supported Concentratord boundary;
- maintains gateway sequence, previous hash, record hash, and closed evidence segments;
- emits checkpoints/segments independently of the delivery broker queue.

Output when the reviewed server evidence service exists:

```text
Gateway Integrity Journal
  -> Gateway Evidence Ingest
  HTTPS + mTLS / TCP 443
  checkpoint + closed segment uploads
```

Status should be shown as **contract defined / runtime implementation pending** unless a later build log proves a pinned deployable implementation.

## 5. Zone 3 - Backhaul and public transport boundary

Do not turn every network interface into a node. Use one transport band between the gateway and cloud.

### 5.1 Gateway backhaul annotation

Inside the transport band list:

- Ethernet / Wi-Fi during commissioning and management;
- Waveshare SIM7600G-H USB 4G/LTE as the intended mobile cloud path;
- logical LTE interface must remain distinct from the existing Wi-Fi `wwan` interface;
- outbound-only TLS sessions; CGNAT is acceptable.

Current SIM7600 state must be represented accurately:

- custom ChirpStack Gateway OS 4.12.0 image build has passed Stage-1 artifact/package verification;
- QMI support is included as a **candidate** path;
- PPP remains fallback;
- actual runtime QMI/PPP selection must be based on first-boot USB binding evidence.

Therefore the diagram should label the backhaul `Ethernet/Wi-Fi or SIM7600 LTE (QMI candidate, PPP fallback)` rather than asserting that QMI is already the proven production link.

### 5.2 Public cloud ingress

Use one grouped ingress block rather than separate boxes for floating IP, DNS, controller, and every HAProxy instance:

```text
DigitalOcean public ingress
Reserved IPv4 + HAProxy active/passive pair
```

Main gateway data arrow:

```text
Gateway bridge
  -> mqtt.<DOMAIN>:8883
  -> Reserved IPv4 / HAProxy TCP pass-through
```

The host-side HAProxy/anchor design is commissioned, while provider-owned Reserved-IP/DNS/firewall activation has been documented as an external handoff. Show this status so the diagram does not claim a provider action already happened when it has not.

The same public ingress may also expose ChirpStack HTTPS management on `:443`, but that is not part of the sensor uplink lifecycle. Show it only as a small management annotation, not another main data-flow branch.

HA control annotation:

```text
Reserved-IP failover controller
  -> etcd
     acquire ownership lock

Reserved-IP failover controller
  -> DigitalOcean API
     move Reserved IPv4 after health + lock decision
```

The DigitalOcean API controller should be a small control annotation, not a full main-path node.

## 6. Zone 4 - Cloud messaging and LoRaWAN network layer

### 6.1 MQTT HA tier

Create one composite box:

```text
Cloud MQTT HA Tier
HAProxy routing + Mosquitto 2.0.18 x2
ulc-01 / ulc-02
```

Inside it, show three distinct logical listener lanes instead of three broker boxes.

#### Gateway lane

```text
Public HAProxy :8883
  -> Mosquitto backend :8884
```

Purpose:

- gateway event/state and command transport;
- TLS end-to-end through pass-through;
- cloud broker pair survives one broker outage.

The live `:8884` listener is currently server TLS with anonymous access denied; do not label the existing listener itself as mTLS unless the corresponding client-certificate listener/policy has actually been commissioned.

#### ChirpStack workload lane

```text
Private HAProxy :18883
  -> Mosquitto ChirpStack backend :8885
```

Purpose:

- dedicated application/network-server MQTT identity and ACL boundary;
- used by the two ChirpStack application nodes.

#### Node-RED ingestion lane

```text
ulc-03 HAProxy :18884
  -> Mosquitto Node-RED backend :8886
```

Purpose:

- dedicated read-only Node-RED subscription to application uplinks;
- mTLS identity `node-red-ingest`;
- separate from the ChirpStack broker credentials.

Current status:

- Node-RED client certificate issuance is PASS;
- `:8886` dedicated broker listener/ACL commissioning is the next active boundary in the latest build evidence;
- therefore mark this lane **IN PROGRESS**, not fully live.

Do not add RabbitMQ, Kafka, NATS, or another queue. They are not part of this project.

### 6.2 ChirpStack application/network-server cluster

Use one logical node:

```text
ChirpStack v4.19.1 x2
ulc-01 + ulc-02
AS923 region / prefix as923
```

Inbound gateway path:

```text
Cloud MQTT gateway topics
  -> ChirpStack
```

Application event path must be drawn as two distinct MQTT transfers so the broker is not visually skipped:

```text
ChirpStack
  -> Cloud MQTT application-event lane
     publish: application/+/device/+/event/up

Cloud MQTT application-event lane
  -> Node-RED
     subscribed application uplink delivery
```

Node-RED therefore never receives a direct ChirpStack socket arrow. In the final layout, place the application-event broker surface **between ChirpStack and Node-RED** even though it is implemented by the same Mosquitto HA pair as the earlier gateway MQTT surface.

ChirpStack runtime dependencies should leave the node vertically downward into the HA/control layer rather than interrupting the left-to-right payload path.

#### PostgreSQL dependency

```text
ChirpStack
  -> local PgBouncer :6432
  -> local HAProxy PostgreSQL-primary route :15432
  -> Patroni current primary
  -> chirpstack database
```

#### Valkey dependency

```text
ChirpStack
  -> local HAProxy writable-master route :16379
  -> Valkey current primary
```

### 6.3 Generic downlink path

Do **not** draw the downlink as a reverse arrow laid directly on top of the uplink path. Give it a separate thin lane along the bottom of the diagram, flowing right -> left.

Use explicit publisher/broker/subscriber steps:

```text
Approved application command source
  -> ChirpStack
     command request

ChirpStack
  -> Cloud MQTT gateway-command lane
     publish gateway command

Cloud MQTT gateway-command lane
  -> Gateway bridge / local Mosquitto
     broker delivery

Local Mosquitto
  -> MQTT Forwarder
     subscribed command delivery

MQTT Forwarder
  -> Concentratord
     command IPC

Concentratord
  -> RAK5146
  -> Class A LoRaWAN downlink
  -> End device
```

In the landscape render, place the command source at the **right-hand end** of this lower lane so every arrowhead naturally points right -> left toward the end device. Use one small vertical connector only where the lane enters ChirpStack and one where it enters the gateway enclosure; do not create diagonal crossings through the uplink lane.

For EMU-01 specifically, annotate that automatic command actions remain disabled until a frozen downlink command contract exists. Do not imply that the current sensor firmware already supports arbitrary commands.

## 7. Zone 5 - Application processing and durable data

### 7.1 Node-RED

Use one node:

```text
Node-RED ingestion / normalization
ulc-03 target
```

Responsibilities:

1. subscribe read-only to `application/+/device/+/event/up`;
2. validate expected device/application identity and timestamps;
3. normalize fields and units;
4. derive a stable `event_key`;
5. execute parameterized SQL;
6. write accepted telemetry transactionally;
7. enqueue Fabric work in the same durable database boundary when the event is selected for attestation.

Node-RED must **not** be drawn as:

- computing the production evidence signature;
- owning the OpenBao private key;
- holding OpenBao root/unseal credentials;
- speaking directly to Fabric peers/orderers;
- waiting synchronously for a Fabric commit before accepting telemetry.

That separation is one of the main architectural messages the diagram should communicate.

### 7.2 Database access/routing tier

Because the user wants all technologies but not duplicate nodes, use one compact composite step:

```text
PgBouncer 1.22
connection pool / client TLS / SCRAM
        |
        v
HAProxy PostgreSQL routing
:15432 primary / :15433 replica-test
```

PgBouncer and HAProxy must both appear by name because they solve different problems:

- PgBouncer controls client connection pooling/authentication/TLS boundary;
- HAProxy selects the currently healthy Patroni primary or replica role.

Do not draw one PgBouncer box and one HAProxy box per host. Put `x3 / local endpoint per node` in the composite label.

### 7.3 PostgreSQL HA + TimescaleDB cluster

Use one enclosing node:

```text
PostgreSQL 18.6 HA cluster x3
Spilo + Patroni
1 primary + 2 streaming replicas
TimescaleDB 2.29.2 in lorawan_telemetry
```

Inside it, show two logical databases and the key telemetry objects.

#### `chirpstack` database

Purpose:

- ChirpStack durable network/application state.

Do not show TimescaleDB inside this database.

#### `lorawan_telemetry` database

Show:

```text
telemetry.uplinks          Timescale hypertable
telemetry.measurements     Timescale hypertable
telemetry.device_registry  relational table
telemetry.fabric_outbox    durable relational integration queue
```

The outbox is deliberately an ordinary PostgreSQL table, not a Timescale hypertable.

Main Node-RED transaction concept:

```text
BEGIN
  write uplink
  write measurements
  optionally enqueue fabric_outbox
COMMIT
```

The diagram should make the transaction boundary visible with a bracket or note because it explains why telemetry is not lost when Fabric is unavailable.

### 7.4 PostgreSQL replication and Patroni

Inside/below the DB node, show:

```text
PostgreSQL WAL streaming
primary -> replica x2
```

and a dashed control arrow:

```text
Patroni <-> etcd 3-member DCS
```

Spilo is the packaged PostgreSQL/Patroni runtime and should be named inside the cluster, not drawn as another hop between HAProxy and PostgreSQL.

### 7.5 Valkey HA

Use one side dependency node:

```text
Valkey 7.2.13 x3
TLS-only
1 master + 2 replicas
Sentinel x3 / quorum 2
```

Data arrow:

```text
ChirpStack
  -> HAProxy :16379
  -> current Valkey master
```

Control relationships:

```text
Sentinel <-> Valkey members
monitor / elect / reconfigure master

HAProxy -> Valkey backends
health + role probe

Valkey writable master -> HAProxy
healthy master result / accepted traffic target
```

Do not draw `Sentinel -> HAProxy`; HAProxy discovers the writable backend through its own health checks after Sentinel changes Valkey roles.

Do not show Valkey as a telemetry datastore. It is a ChirpStack runtime/state dependency.

### 7.6 etcd HA coordination

Use one compact control-plane node:

```text
etcd 3-member cluster
ulc-01 / ulc-02 / ulc-03
```

Only dashed control relationships should touch it:

- Patroni <-> etcd for DCS state, member state, and the Patroni leader lock;
- Reserved-IP failover controller -> etcd to acquire/release the separate failover ownership lock.

Do not draw a one-way `etcd -> controller` arrow. etcd stores/coordinates the lock; the controller is the client that requests it.

Do not put etcd on the uplink path and do not describe it as the telemetry database.

## 8. Zone 5 side branch - Gateway evidence services

Use one composite server-side block, because creating separate top-level boxes for ingest API, MQTT collector, verifier, decoder, and protected evidence store would overwhelm the picture.

Suggested label:

```text
Gateway Evidence Services
- Evidence Ingest API
- MQTT Evidence Collector
- Evidence Verifier
- Trusted Decoder
- protected evidence store / gateway_evidence state
```

Inputs must point **into** Gateway Evidence Services from the system that supplies each piece of evidence:

1. Gateway Integrity Journal -> Gateway Evidence Services: checkpoints/segments over HTTPS + mTLS.
2. Cloud MQTT gateway lane -> Gateway Evidence Services: raw remote gateway MQTT events delivered to the read-only collector.
3. ChirpStack / application-event lane -> Gateway Evidence Services: accepted application-event identity/context.
4. Accepted raw application payload -> Trusted Decoder inside Gateway Evidence Services.
5. PostgreSQL/TimescaleDB -> Gateway Evidence Services: stored normalized telemetry returned for comparison.

After correlation, persist the result in the opposite direction:

```text
Gateway Evidence Services
  -> PostgreSQL / telemetry gateway_evidence state
  verified | evidence_gap | integrity_failure | other reviewed states
```

The Fabric Adapter does **not** receive a direct verifier-to-adapter arrow. It later reads the durable outbox/source state from PostgreSQL; for v2 that read is eligible only when the persisted gateway verification state is exactly `verified`.

Verification output:

```text
source/journal continuity
+ remote MQTT delivery correlation
+ application-event correlation
+ trusted decoder comparison
+ TimescaleDB normalized-value comparison
= gateway evidence verification state
```

For `telemetry-attestation-v2`, the diagram should place a guard on the DB-to-adapter arrow:

```text
v2 eligible only when gateway_evidence.status = verified
```

Do not create a separate runtime “Evidence Gate” service unless one is actually implemented. The gate is a database/policy decision made from verifier output.

Current status should be **architecture/contract defined; deployable runtime implementation still pending** unless superseded by later execution evidence.

## 9. Zone 6 - Asynchronous Fabric attestation and KMS

### 9.1 Fabric Adapter

Use one top-level node, with multiplicity/status inside the label rather than one box per future worker:

```text
Fabric Adapter
asynchronous outbox worker
protected application host(s)
STATUS: implementation/image + external Fabric handoff pending
```

The adapter is necessary in the architecture even though it is not yet deployed. The diagram must distinguish **architectural presence** from **runtime readiness**.

Input arrow:

```text
PostgreSQL / fabric_outbox
  -> Fabric Adapter
```

Label the arrow with:

```text
claim with FOR UPDATE SKIP LOCKED
commit worker lease before network calls
load approved source projection
```

The adapter flow should be shown as a numbered mini-sequence inside or immediately below the node:

1. claim eligible outbox row;
2. commit the claim/lease;
3. load the approved schema-specific source evidence;
4. build `telemetry-attestation-v1` or verified `v2` canonical evidence object;
5. RFC 8785 JCS canonicalize;
6. encode exact UTF-8 bytes;
7. calculate SHA-256 over those exact bytes;
8. ask OpenBao Transit to sign those exact canonical bytes;
9. persist canonical JSON, digest, algorithm, key ID, complete versioned signature, and seal timestamp before the first Fabric call;
10. verify the persisted seal on every retry;
11. submit the compact seven-field Fabric transaction contract through Fabric Gateway;
12. wait for valid commit status;
13. mark the outbox `confirmed` only after valid commit;
14. use `submitted_unknown` + ledger reconciliation when final commit state is uncertain.

The diagram should explicitly show that the **complete canonical evidence and raw telemetry remain off-chain**.

### 9.2 OpenBao KMS tier

Use one composite node:

```text
OpenBao 2.6.2 HA KMS
Raft x3 voters / quorum 2
ulc-01 + ulc-02 + ulc-03
Transit key: lorawan-evidence
ECDSA P-256 / non-exportable
```

Prepend a small routing interface inside the same security zone:

```text
HAProxy KMS stable endpoint
openbao-kms.internal.lorawan.com:18200
frontends on ulc-01 / ulc-02
```

Adapter/OpenBao must be drawn as a paired request/response branch, not one ambiguous arrow:

```text
Fabric Adapter
  -> local HAProxy KMS :18200
  -> OpenBao Transit
  sign/verify request: exact canonical UTF-8 bytes + operation

OpenBao Transit
  -> local HAProxy KMS :18200
  -> Fabric Adapter
  response: versioned signature OR verify valid/invalid
```

Use a compact parallel pair of arrows or a narrow U-shaped request/response branch. This is a request/response side dependency. Do **not** draw:

```text
Node-RED -> OpenBao -> database
```

or

```text
telemetry -> OpenBao -> Fabric
```

as if OpenBao transports the event. OpenBao receives only the bytes/signature operation necessary to create or verify the evidence seal.

Control details to annotate, not promote to separate nodes:

- three Raft voters;
- Shamir unseal operational boundary;
- `fabric-evidence-signer` least-privilege policy;
- `fabric-adapter` AppRole exists;
- no adapter SecretID has been issued prematurely;
- Transit key version 1 is protected/non-exportable;
- normal-path stable-endpoint sign/verify has passed.

Status: **LIVE / PASS for prepared KMS infrastructure**.

### 9.3 External Hyperledger Fabric boundary

Use exactly one external-system block:

```text
External Hyperledger Fabric Network
Fabric Gateway
channel + chaincode
ledger / commit status
```

Do not add project-owned boxes for:

- peer 1 / peer 2;
- orderer nodes;
- Fabric CA;
- MSP administration;
- chaincode lifecycle tooling.

The repository explicitly treats peers, orderers, Fabric CAs, channels, and deployed chaincode as externally operated infrastructure supplied through a Fabric handoff.

Adapter-to-Fabric arrows must be explicit in both directions:

```text
Fabric Adapter
  -> Fabric Gateway
  TLS-authenticated Fabric client identity
  submit seven-field chaincode transaction

Fabric Gateway / ledger commit service
  -> Fabric Adapter
  transaction ID + valid / invalid / unknown commit status
```

Do not combine these into a double-headed line because the forward payload and return result mean different things. `submitted_unknown` is a local adapter/outbox state created only when the final ledger state cannot be established from the returned result.

Do not invent a concrete Fabric Gateway host/port, organization, MSP ID, channel name, or chaincode endpoint until the external handoff supplies them.

Ledger content note:

```text
ON-CHAIN: compact attestation metadata + digest + seal metadata
OFF-CHAIN: raw payload, decoded values, DevEUI detail, radio observations, complete canonical evidence
```

## 10. Grafana and operational read path

Show Grafana as one small read-only node. Keep session-initiation details in the label, but point the data arrow toward the reader:

```text
lorawan_telemetry
  -> HAProxy/PgBouncer read boundary
  -> telemetry_reader result set
  -> Grafana
```

If showing the SQL request is useful, add a very thin dotted return arrow from Grafana back to the read boundary labelled `read-only query`; do not let that request arrow visually compete with the returned telemetry-data arrow.

Purpose:

- visualize telemetry/test evidence;
- no write/control capability.

Do not include Prometheus, Loki, Alloy, or Alertmanager as nodes in this diagram. The current cloud POC documentation deliberately avoids adding that monitoring stack; ordinary service logs/CLI checks are sufficient beside Grafana.

## 11. Technology inclusion matrix

The final diagram should account for the following technologies in these exact roles.

| Technology | Show as | Why it belongs |
|---|---|---|
| RAK4631 WisBlock Core | End-device group | Actual LoRaWAN sensor/emulator platform |
| Agriculture Kit sensor boards | Compact annotation inside end-device group | Source measurements, but not independent network nodes |
| RAK5146 / SX1303 | Gateway radio subcomponent | Physical LoRa concentrator |
| Raspberry Pi 4B | Gateway enclosure label | Gateway compute platform |
| ChirpStack Gateway OS 4.12.0 | Gateway enclosure label | Gateway runtime OS |
| ChirpStack Concentratord | Gateway subcomponent | Sole radio owner / event IPC |
| ChirpStack MQTT Forwarder | Gateway subcomponent | Converts Concentratord events/commands to MQTT |
| Local Mosquitto | Gateway subcomponent | Persistent store-and-forward during WAN loss |
| Gateway Integrity Journal | Gateway sidecar | Independent tamper-evidence chain |
| Waveshare SIM7600G-H | Backhaul annotation | Intended USB LTE path; not an application processor |
| DigitalOcean Reserved IPv4 | Public ingress group | Stable public entry point / failover target |
| HAProxy | Shared routing technology with labelled endpoints | MQTT, PostgreSQL, Valkey, OpenBao KMS, public ingress |
| Mosquitto 2.0.18 | Cloud MQTT HA group | Gateway and application MQTT transport |
| ChirpStack v4.19.1 x2 | LoRaWAN application/network-server group | Network server and application integration |
| PgBouncer 1.22 | DB access tier | Pooling, SCRAM and client-facing TLS boundary |
| PostgreSQL 18.6 | HA database cluster | Durable ChirpStack + telemetry state |
| TimescaleDB 2.29.2 | Inside `lorawan_telemetry` | Time-series hypertables |
| Spilo | Inside PostgreSQL cluster label | Packaged PostgreSQL/Patroni runtime |
| Patroni | Inside PostgreSQL cluster label | DB role management/failover |
| etcd x3 | HA/control-plane node | Patroni DCS + ingress failover lock |
| Valkey 7.2.13 x3 | ChirpStack dependency node | Shared runtime/state dependency |
| Sentinel x3 | Inside Valkey HA node | Valkey leader election/quorum |
| Node-RED | Application processing node | Validation, normalization, transactional telemetry write |
| `telemetry.fabric_outbox` | Inside PostgreSQL/Timescale group | Durable async attestation queue |
| Gateway Evidence Services | Composite evidence node | Journal/MQTT/app/decoder/DB reconciliation |
| Fabric Adapter | Async attestation node | Canonicalize/hash/seal/submit/reconcile |
| OpenBao 2.6.2 x3 | KMS/security node | Non-exportable evidence signing and verification |
| OpenBao Raft | Inside OpenBao cluster | HA KMS storage/leadership |
| OpenBao Transit | Inside OpenBao cluster | ECDSA P-256 sign/verify service |
| OpenBao AppRole | Security annotation | Machine authentication boundary for adapter |
| Hyperledger Fabric | One external network boundary | Final attestation ledger |
| Fabric Gateway / channel / chaincode | Inside external Fabric boundary | Supported application submission/commit contract |
| Grafana | Read-only operations branch | Telemetry visualization |
| PKI / TLS / mTLS | Arrow/boundary labels | Cross-service authentication and encryption, not standalone nodes |

## 12. Technologies intentionally not promoted to main nodes

These exist in the repository or operating procedures but should not become top-level boxes in the data-flow diagram because doing so would make it less accurate or less readable.

### Backup and DR mechanisms

Do not put WAL-G, logical `pg_dump`, snapshots, S3/Spaces, or recovery archives on the main runtime diagram. They are operational recovery mechanisms, not normal sensor-data processing hops. A separate DR diagram can cover them later.

### Prometheus / Loki / Alloy / Alertmanager

Do not show them. The cloud POC explicitly avoids deploying this stack.

### VPN / SSH / LuCI / operator workstation

These are management paths. They are not part of the normal telemetry lifecycle and should remain outside the primary architecture diagram.

### Individual HA replicas

Do not create separate top-level nodes such as `etcd-1`, `etcd-2`, `etcd-3`, `Valkey-1`, `Valkey-2`, `Valkey-3`, `OpenBao-1`, and so on. Use cluster boxes with multiplicity and, where useful, the host placement in smaller text.

### Fabric peers, orderers, and Fabric CAs

Do not instantiate them in this project diagram. They are externally operated and the handoff values are not yet frozen.

### Every sensor board

Do not create eight sensor-node boxes simply because eight boards can be attached to a WisBlock base. They are measurement sources inside one LoRaWAN end device.

### Cryptographic concepts as boxes

MIC, AppSKey, NwkSKey, SHA-256, RFC 8785, ECDSA, SCRAM, TLS, mTLS, and X.509 belong on arrows or processing annotations. They are not network services by themselves.

## 13. Arrow taxonomy

The final diagram should use a consistent arrow language, with the arrowhead always identifying the receiver of the labelled information.

### Solid primary arrows - normal uplink payload

These are thick and flow left -> right only.

Examples:

- sensor -> gateway RF: LoRaWAN uplink;
- RAK5146 -> Concentratord: received packet;
- Concentratord -> MQTT Forwarder: gateway event;
- MQTT Forwarder -> Local Mosquitto: MQTT publish;
- Local Mosquitto -> cloud MQTT gateway lane: bridged uplink;
- cloud MQTT gateway lane -> ChirpStack: subscribed gateway event;
- ChirpStack -> cloud MQTT application lane: application event publish;
- cloud MQTT application lane -> Node-RED: subscribed uplink delivery;
- Node-RED -> PostgreSQL/TimescaleDB: committed telemetry write.

### Solid secondary arrows - evidence / attestation data

These are thinner than the primary path and remain in their own side lane.

Examples:

- Gateway Integrity Journal -> Gateway Evidence Services: checkpoint/segment upload;
- cloud MQTT gateway lane -> Gateway Evidence Services: captured raw gateway event;
- PostgreSQL/TimescaleDB -> Gateway Evidence Services: stored telemetry read result;
- Gateway Evidence Services -> PostgreSQL: persisted verification state;
- PostgreSQL/fabric_outbox -> Fabric Adapter: claimed durable work/source evidence;
- Fabric Adapter -> OpenBao: sign/verify request;
- OpenBao -> Fabric Adapter: signature/verification response;
- Fabric Adapter -> Fabric Gateway: transaction submit;
- Fabric Gateway -> Fabric Adapter: commit result;
- Fabric Adapter -> PostgreSQL/fabric_outbox: worker/seal/commit-state update.

### Thin reverse solid arrows - downlink command lane

These flow right -> left only and stay below the uplink lane.

Examples:

- application command source -> ChirpStack;
- ChirpStack -> cloud MQTT command lane;
- cloud MQTT command lane -> gateway Local Mosquitto bridge;
- Local Mosquitto -> MQTT Forwarder;
- MQTT Forwarder -> Concentratord;
- Concentratord -> RAK5146 -> end device.

### Dashed arrows - control / HA

These stay below the data planes.

Examples:

- Patroni <-> etcd: DCS state and leader lock;
- Patroni -> PostgreSQL member: role/config action;
- Sentinel <-> Valkey: monitoring/election/reconfiguration;
- HAProxy -> backend: health probe;
- backend -> HAProxy: health/role result when explicitly shown;
- Reserved-IP controller -> etcd: ownership lock;
- Reserved-IP controller -> DigitalOcean API: move Reserved IPv4;
- OpenBao voter <-> voter: Raft consensus/replication inside the KMS composite.

### Dotted arrows - read-only requests or optional correlation lookups

Use dotted arrows only when the request itself is useful to explain. Otherwise show the returned data using a normal thin arrow from source to reader.

Examples:

- Grafana -> DB read boundary: optional `SELECT` request;
- Fabric Adapter -> PostgreSQL: claim/read request if the query action itself is being explained;
- Evidence verifier -> PostgreSQL: optional correlation-query request.

The corresponding result/data still points in the opposite direction, from PostgreSQL toward the reader.

### Prohibited arrow patterns

Do not use any of these in the final render:

```text
Cloud MQTT <-> ChirpStack          # too ambiguous; publication and delivery are different
Fabric Adapter <-> OpenBao         # hides request vs signature/verify result
Fabric Adapter <-> Fabric          # hides submit vs commit status
Grafana -> TimescaleDB             # misleading if the arrow is labelled telemetry data
etcd -> failover controller        # lock is acquired by the controller from etcd
Journal -> ChirpStack              # architecturally false
Node-RED -> OpenBao -> Fabric      # falsely makes KMS/Fabric synchronous ingestion hops
```

## 13A. Authoritative directed-edge list for rendering

When generating the actual diagram, this table is the **source of truth for arrowheads**. If any prose, sketch, or automated layout appears to disagree with this table, follow this table.

| ID | From | To | Arrow meaning | Visual class |
|---|---|---|---|---|
| U1 | End Device | RAK5146 / SX1303 | AS923 LoRaWAN uplink RF | thick solid -> |
| U2 | RAK5146 / SX1303 | Concentratord | demodulated received packet | thick solid -> |
| U3 | Concentratord | MQTT Forwarder | gateway event over supported IPC | thick solid -> |
| U4 | MQTT Forwarder | Local Mosquitto | MQTT publish, `as923` gateway event | thick solid -> |
| U5 | Local Mosquitto | Public ingress / Cloud MQTT gateway lane | bridged outbound MQTT/TLS uplink | thick solid -> |
| U6 | Cloud MQTT gateway lane | ChirpStack | broker delivers subscribed gateway event | thick solid -> |
| U7 | ChirpStack | Cloud MQTT application-event lane | publish accepted application uplink | thick solid -> |
| U8 | Cloud MQTT application-event lane | Node-RED | broker delivers subscribed application event | thick solid -> |
| U9 | Node-RED | PgBouncer | SQL write transaction request | thick solid -> |
| U10 | PgBouncer | HAProxy PostgreSQL primary route | pooled authenticated PostgreSQL session | thick solid -> |
| U11 | HAProxy PostgreSQL primary route | PostgreSQL current primary | routed SQL write | thick solid -> |
| E1 | Concentratord | Gateway Integrity Journal | independent source-evidence copy | secondary solid -> |
| E2 | Gateway Integrity Journal | Gateway Evidence Services | checkpoint / closed segment upload | secondary solid -> |
| E3 | Cloud MQTT gateway lane | Gateway Evidence Services | raw gateway MQTT event copy | secondary solid -> |
| E4 | ChirpStack / application-event lane | Gateway Evidence Services | accepted application-event context | secondary solid -> |
| E5 | PostgreSQL / TimescaleDB | Gateway Evidence Services | stored normalized telemetry read result | secondary solid -> |
| E6 | Gateway Evidence Services | PostgreSQL | persist gateway verification state | secondary solid -> |
| A1 | PostgreSQL / `fabric_outbox` | Fabric Adapter | eligible durable job + approved source projection | secondary solid -> |
| A2 | Fabric Adapter | OpenBao Transit via HAProxy :18200 | canonical-byte sign/verify request | secondary solid -> |
| A3 | OpenBao Transit via HAProxy :18200 | Fabric Adapter | versioned signature / verify result | secondary solid -> |
| A4 | Fabric Adapter | PostgreSQL / `fabric_outbox` | persist immutable seal / worker state | secondary solid -> |
| A5 | Fabric Adapter | Fabric Gateway | submit seven-field attestation transaction | secondary solid -> |
| A6 | Fabric Gateway / ledger commit service | Fabric Adapter | transaction ID + commit status | secondary solid -> |
| A7 | Fabric Adapter | PostgreSQL / `fabric_outbox` | confirmed / submitted_unknown / failure state | secondary solid -> |
| O1 | PostgreSQL / TimescaleDB | Grafana | returned telemetry / visualization result set | thin read-data -> |
| C1 | Patroni | etcd | DCS write / leader-lock request | dashed -> |
| C2 | etcd | Patroni | DCS state / lock result / membership read | dashed -> |
| C3 | Patroni | PostgreSQL member | apply role/config decision | dashed -> |
| C4 | PostgreSQL primary | PostgreSQL replicas | WAL stream | thin HA-data -> |
| C5 | Sentinel | Valkey members | monitor/election/reconfiguration commands | dashed -> |
| C6 | Valkey members | Sentinel | health/role/state observations | dashed -> |
| C7 | HAProxy | Valkey / Patroni / Mosquitto / OpenBao backends | health/role probes | dashed -> |
| C8 | Backend health endpoint | HAProxy | health/role response | dashed -> |
| C9 | Reserved-IP failover controller | etcd | acquire/release ownership lock | dashed -> |
| C10 | Reserved-IP failover controller | DigitalOcean API | move Reserved IPv4 | dashed -> |
| D1 | Application command source | ChirpStack | approved downlink command request | thin reverse solid <- in layout |
| D2 | ChirpStack | Cloud MQTT gateway-command lane | publish gateway command | thin reverse solid <- in layout |
| D3 | Cloud MQTT gateway-command lane | Local Mosquitto bridge | broker/bridge command delivery | thin reverse solid <- in layout |
| D4 | Local Mosquitto | MQTT Forwarder | subscribed command delivery | thin reverse solid <- in layout |
| D5 | MQTT Forwarder | Concentratord | command IPC | thin reverse solid <- in layout |
| D6 | Concentratord | RAK5146 / SX1303 | radio transmit command | thin reverse solid <- in layout |
| D7 | RAK5146 / SX1303 | End Device | Class A LoRaWAN downlink RF | thin reverse solid <- in layout |

Important placement note for `D1-D7`: the **logical From/To directions above remain authoritative**. In the landscape drawing, arrange the command source on the right and the end device on the left, so these arrows visually travel right -> left without changing their semantic source/destination.

### 13A.1 Edges that must not exist

The following connections are forbidden because they imply a false runtime dependency:

```text
Gateway Integrity Journal -> ChirpStack
Node-RED -> OpenBao
Node-RED -> Hyperledger Fabric
OpenBao -> Hyperledger Fabric
etcd -> telemetry payload path
Sentinel -> telemetry payload path
Grafana -> telemetry write path
Fabric Adapter -> gateway verification status writer
```

## 14. Exact main uplink sequence to number on the diagram

Number the primary path from 1 through 14 so a presentation audience can follow it without chasing arrows.

1. **Measurement generated** on EMU-01/real WisBlock sensor firmware.
2. **LoRaWAN uplink constructed and transmitted** using AS923 and active session security/frame counter.
3. **RAK5146 receives RF** and passes the demodulated packet to Concentratord.
4. **Concentratord publishes the gateway event** over its supported event IPC.
5. **MQTT Forwarder converts the event to gateway MQTT** with `as923` topic prefix.
6. **Gateway-local Mosquitto persists/queues the event** on loopback; WAN loss does not require dropping it immediately.
7. **Gateway bridge establishes outbound TLS** through Ethernet/Wi-Fi or the intended SIM7600 LTE route.
8. **Public ingress / HAProxy routes MQTT** to a healthy cloud Mosquitto backend.
9. **Cloud MQTT delivers the gateway event to ChirpStack**, which applies LoRaWAN network/application processing and uses PostgreSQL plus Valkey shared state.
10. **ChirpStack publishes the accepted application uplink into the cloud MQTT application-event lane** at `application/+/device/+/event/up`.
11. **The cloud MQTT application-event lane delivers that event to Node-RED** through its dedicated subscription identity.
12. **Node-RED validates and normalizes** the payload and derives stable identity/event keys.
13. **Node-RED commits telemetry transactionally** through PgBouncer -> HAProxy -> Patroni primary into `telemetry.uplinks` / `telemetry.measurements`, optionally inserting `fabric_outbox` in the same durable boundary.
14. **Durable data fans out asynchronously after commit**: PostgreSQL/TimescaleDB -> Grafana for read-only visualization, and PostgreSQL/`fabric_outbox` -> Fabric Adapter when attestation work is eligible. Neither consumer is required for the telemetry transaction to succeed.

## 15. Exact attestation sequence to number separately

Use labels `A1` through `A12` so it cannot be confused with the primary uplink stages.

A1. `fabric_outbox` row becomes eligible after the telemetry transaction commits.

A2. For v2, adapter eligibility additionally requires gateway evidence verification status exactly `verified`.

A3. Fabric Adapter claims one job with `FOR UPDATE SKIP LOCKED` and commits its lease before network calls.

A4. Adapter loads the approved schema-specific source projection.

A5. Adapter builds the versioned canonical evidence object.

A6. Adapter applies RFC 8785 JCS and obtains exact UTF-8 canonical bytes.

A7. Adapter calculates SHA-256 over those bytes.

A8. Adapter sends the exact canonical bytes to OpenBao Transit for ECDSA P-256 / SHA-256 signing through the stable HAProxy KMS endpoint.

A9. Adapter persists canonical JSON, digest, versioned signature, algorithm, KMS key ID, and seal timestamp as the immutable outbox seal.

A10. Adapter submits the compact approved transaction envelope through Fabric Gateway / chaincode.

A11. Adapter waits for and interprets commit status; timeout becomes `submitted_unknown`, not false success/failure.

A12. Adapter updates the outbox to `confirmed` only after valid Fabric commit; reconciliation uses the stable event key/transaction ID and the already-persisted seal.

## 16. Exact gateway-integrity sequence to number separately

Use labels `G1` through `G8`.

G1. Concentratord exposes the received gateway event to the delivery path and independent journal reader.

G2. Gateway Integrity Journal hashes/appends the source evidence record and maintains sequence/chain continuity.

G3. Closed journal segments/checkpoints are delivered to the server evidence ingest service over HTTPS/mTLS when connectivity exists.

G4. Cloud MQTT gateway topics deliver a copy of each relevant remote gateway event to the independent MQTT Evidence Collector before application normalization.

G5. Verifier correlates journal evidence against captured MQTT delivery.

G6. Verifier correlates the corresponding ChirpStack application event and runs the trusted decoder against accepted raw application data.

G7. Verifier compares trusted decoded values with normalized TimescaleDB values and records verification state.

G8. Only `verified` v2 evidence is allowed to enter the v2 Fabric sealing/submission path.

## 17. Status legend for the final render

The diagram must not make planned components look commissioned. Use a simple status tag in each major composite node.

### LIVE / PASS

Use for components with recorded normal-path commissioning evidence, including:

- PostgreSQL/Spilo/Patroni three-member HA;
- etcd three-member cluster;
- PgBouncer;
- HAProxy database routes;
- Valkey/Sentinel HA;
- cloud Mosquitto core and HAProxy broker routing;
- ChirpStack private application nodes;
- TimescaleDB telemetry schema;
- `telemetry.fabric_outbox` schema/ACL/immutability boundary;
- OpenBao three-member Raft/Transit/AppRole prepared KMS boundary and HAProxy KMS endpoints.

### IN PROGRESS / COMMISSIONING

Use for components where current build evidence has not closed the final runtime gate, including:

- SIM7600 LTE runtime data mode after custom image flash/first-boot proof;
- provider-owned public Reserved-IP/DNS/firewall handoff where still pending;
- Node-RED dedicated MQTT `:8886` mTLS broker lane and full application-path commissioning.

### CONTRACT DEFINED / IMPLEMENTATION PENDING

Use for:

- gateway integrity journal/server evidence runtime components if no reviewed pinned implementation has been deployed;
- gateway evidence verifier/collector/trusted decoder runtime.

### BLOCKED / EXTERNAL HANDOFF

Use for:

- Fabric Adapter executable/runtime image and machine credential issuance;
- external Hyperledger Fabric endpoint/channel/chaincode/client-identity handoff.

The architecture is still shown because the design contract is required, but the status prevents accidental claims of deployment completion.

## 18. Proposed diagram skeleton

The first render should follow this approximate spatial arrangement. This version intentionally duplicates the **logical broker surfaces** of the same Mosquitto HA tier so the primary arrows never double back.

```text
PRIMARY UPLINK - DRAW AS ONE STRAIGHT LEFT-TO-RIGHT SPINE

End Device
  -> RAK5146 / SX1303
  -> Concentratord
  -> MQTT Forwarder
  -> Local Mosquitto
  -> Backhaul / Public Ingress
  -> Cloud MQTT: Gateway Topics
  -> ChirpStack
  -> Cloud MQTT: Application-Event Topics
  -> Node-RED
  -> PgBouncer
  -> HAProxy PostgreSQL Primary Route
  -> PostgreSQL / TimescaleDB

ASYNC READ / ATTESTATION FAN-OUT - BELOW DATABASE, NOT INLINE WITH UPLINK

PostgreSQL / TimescaleDB
  -> Grafana
     telemetry read result

PostgreSQL / fabric_outbox
  -> Fabric Adapter
     eligible durable work

Fabric Adapter
  -> OpenBao KMS
     sign / verify request

OpenBao KMS
  -> Fabric Adapter
     signature / verification result

Fabric Adapter
  -> Fabric Gateway
     submit transaction

Fabric Gateway / Ledger
  -> Fabric Adapter
     transaction ID / commit status

Fabric Adapter
  -> PostgreSQL / fabric_outbox
     seal + worker + final commit-state update

EVIDENCE LANE - PARALLEL SIDE LANE, NO DIAGONAL CROSSINGS

Concentratord
  -> Gateway Integrity Journal
  -> Gateway Evidence Services

Cloud MQTT: Gateway Topics
  -> Gateway Evidence Services
     captured raw gateway event

ChirpStack / Application-Event Context
  -> Gateway Evidence Services

PostgreSQL / TimescaleDB
  -> Gateway Evidence Services
     stored normalized telemetry for comparison

Gateway Evidence Services
  -> PostgreSQL
     persisted gateway verification state

CONTROL LANE - BELOW DATA PLANES, DASHED ONLY

Patroni -> etcd
  DCS write / leader-lock request
etcd -> Patroni
  DCS state / lock result
Patroni -> PostgreSQL member
  role / config decision
PostgreSQL primary -> PostgreSQL replicas
  WAL stream
Sentinel -> Valkey members
  monitor / elect / reconfigure
Valkey members -> Sentinel
  health / role state
HAProxy -> backends
  health / role probes
backends -> HAProxy
  health / role result
Reserved-IP controller -> etcd
  ownership lock
Reserved-IP controller -> DigitalOcean API
  move Reserved IPv4
OpenBao voter <-> OpenBao voter
  internal Raft only

DOWNLINK LANE - DRAW AS A SEPARATE STRAIGHT RIGHT-TO-LEFT SPINE

Approved Command Source
  -> ChirpStack
  -> Cloud MQTT: Gateway-Command Topics
  -> Local Mosquitto bridge
  -> MQTT Forwarder
  -> Concentratord
  -> RAK5146 / SX1303
  -> End Device

Physical placement rule for the downlink lane:
put Approved Command Source at the far RIGHT and End Device at the far LEFT,
so the semantic source-to-destination sequence above is rendered with arrowheads
visually travelling RIGHT -> LEFT.
```

The final graphic should replace ASCII arrows with clean orthogonal connectors, but it must preserve these directed relationships and use the authoritative edge table in Section 13A if there is any ambiguity.

## 19. Host-placement annotation without host explosion

The full cloud topology uses:

```text
ulc-01  10.104.0.2
ulc-02  10.104.0.4
ulc-03  10.104.0.8
```

Do not make the whole diagram three vertical host columns; that would turn the artifact into a deployment topology and obscure data flow.

Instead, put small placement text inside relevant cluster nodes, for example:

```text
ChirpStack x2 - ulc-01 / ulc-02
Mosquitto x2 - ulc-01 / ulc-02
OpenBao x3 - ulc-01 / ulc-02 / ulc-03
PostgreSQL/Patroni x3 - ulc-01 / ulc-02 / ulc-03
Valkey/Sentinel x3 - ulc-01 / ulc-02 / ulc-03
Node-RED target - ulc-03
Grafana target - ulc-03
```

Where HAProxy appears in several services, name the endpoint next to the consumer path instead of drawing a generic HAProxy megabox with every port crossing through it.

## 20. Security annotations that belong on the diagram

Keep security labels near the trust boundary where they matter.

### End device / LoRaWAN

- OTAA;
- DevEUI/AppKey provisioning boundary;
- LoRaWAN MIC/frame-counter validation;
- SEC-02 security fixture exercises wrong-key/unregistered/replay/spoofing behavior.

### Gateway -> cloud

- outbound TLS;
- gateway certificate identity when the final gateway mTLS lane is commissioned;
- local `1883` remains loopback-only;
- no inbound LTE port forwarding.

### Cloud MQTT

- anonymous denied;
- client-specific identities/ACLs;
- dedicated ChirpStack and Node-RED broker lanes.

### PostgreSQL

- client TLS;
- SCRAM roles;
- PgBouncer + HAProxy stable routing;
- least-privilege `telemetry_writer`, `telemetry_reader`, `fabric_adapter` roles.

### OpenBao

- private TLS;
- AppRole machine authentication;
- non-exportable ECDSA P-256 Transit key;
- adapter can sign/verify only, not administer the KMS.

### Hyperledger Fabric

- dedicated Fabric client identity;
- TLS root / server-name verification from external handoff;
- authenticated caller identity is authoritative for ledger submitter metadata.

Do not put secrets, certificate fingerprints, AppKeys, passwords, unseal shares, root tokens, SecretIDs, or private keys in the diagram.

## 21. Final diagram acceptance checklist

Before calling the architecture diagram complete, verify all of the following against the repository again.

### Completeness

- [ ] RAK4631/WisBlock end-device platform present.
- [ ] RAK5146/Raspberry Pi gateway present.
- [ ] Concentratord present.
- [ ] MQTT Forwarder present.
- [ ] gateway-local Mosquitto buffer present.
- [ ] SIM7600 backhaul represented with correct non-proven QMI status.
- [ ] DigitalOcean Reserved-IP/HAProxy public ingress represented without overclaiming provider handoff.
- [ ] cloud Mosquitto HA represented.
- [ ] ChirpStack x2 represented.
- [ ] PgBouncer represented.
- [ ] HAProxy DB route represented.
- [ ] PostgreSQL + Spilo + Patroni represented.
- [ ] TimescaleDB represented inside telemetry DB, not as an unrelated server.
- [ ] Valkey + Sentinel represented.
- [ ] etcd represented as control plane.
- [ ] Node-RED represented.
- [ ] gateway integrity path represented separately from MQTT delivery.
- [ ] `telemetry.fabric_outbox` represented.
- [ ] Gateway Evidence Services represented with implementation status.
- [ ] Fabric Adapter represented with blocked/runtime-pending status.
- [ ] OpenBao + HAProxy KMS + Transit represented.
- [ ] Hyperledger Fabric external boundary represented.
- [ ] Grafana represented as read-only only.

### Semantic correctness

- [ ] Main uplink does not pass through etcd, Sentinel, Grafana, OpenBao, or Fabric.
- [ ] OpenBao is shown as a side sign/verify dependency of the Fabric Adapter.
- [ ] Fabric submission is asynchronous from Node-RED telemetry ingestion.
- [ ] Outbox row is committed before external KMS/Fabric work.
- [ ] Fabric Adapter waits for valid commit status before confirmation.
- [ ] `submitted_unknown` reconciliation is represented or explained.
- [ ] gateway journal does not feed ChirpStack.
- [ ] v2 Fabric eligibility depends on gateway verification state.
- [ ] canonical evidence remains off-chain.
- [ ] raw telemetry remains in TimescaleDB rather than Fabric.
- [ ] Fabric peer/orderer topology is not invented.

### Readability

- [ ] Reader can follow normal uplink in one left-to-right pass.
- [ ] Every primary uplink arrow points left -> right.
- [ ] Every downlink command arrow points right -> left in its own lower lane.
- [ ] No primary uplink arrow doubles back to reuse a broker box placed earlier in the diagram.
- [ ] MQTT publish and MQTT delivery are shown as separate directed transfers where both matter.
- [ ] OpenBao sign request and signature/verify result use separate directed arrows.
- [ ] Fabric submit and commit-status return use separate directed arrows.
- [ ] Database write arrows point toward PostgreSQL; returned read data points toward the reader.
- [ ] HA/control arrows stay below the data planes and do not cross the main uplink.
- [ ] Primary path has no more than roughly 10-14 visually dominant nodes/subnodes.
- [ ] HA replicas are grouped, not repeated as separate main nodes.
- [ ] ports/topics are placed on arrows or inside composite service labels.
- [ ] status labels clearly distinguish LIVE, IN PROGRESS, IMPLEMENTATION PENDING, and EXTERNAL/BLOCKED.
- [ ] downlink is a thin reverse path, not a duplicate full diagram.
- [ ] control-plane arrows are visually different from payload arrows.

## 22. Recommended implementation sequence for the actual diagram

When moving from this plan to the rendered artifact, build it in this order so readability is preserved.

### Pass 1 - Main uplink only

Render the broker publish/delivery steps explicitly so there is never a backward broker arrow:

```text
End Device
  -> Gateway
  -> Backhaul/Public Ingress
  -> Cloud MQTT Gateway Topics
  -> ChirpStack
  -> Cloud MQTT Application-Event Topics
  -> Node-RED
  -> PgBouncer
  -> HAProxy PostgreSQL Primary Route
  -> PostgreSQL/TimescaleDB
```

Do not add HA or evidence details yet. Confirm the left-to-right flow reads naturally.

### Pass 2 - Internal gateway detail

Expand only the gateway node into:

```text
RAK5146 -> Concentratord -> MQTT Forwarder -> Local Mosquitto
```

Add the journal branch from Concentratord.

### Pass 3 - Runtime dependency branches

Add:

- ChirpStack -> PgBouncer/HAProxy -> PostgreSQL;
- ChirpStack -> HAProxy -> Valkey;
- Node-RED -> PgBouncer/HAProxy -> PostgreSQL.

### Pass 4 - Evidence / Fabric branch

Add:

- Gateway Evidence Services;
- outbox -> Fabric Adapter;
- Adapter -> OpenBao;
- Adapter -> External Fabric;
- commit-status return path.

### Pass 5 - HA/control layer

Add only the dashed control relationships, with correct client/state direction:

- Patroni -> etcd: DCS write / leader-lock request;
- etcd -> Patroni: DCS state / lock result;
- Patroni -> PostgreSQL member: role/config action;
- Sentinel -> Valkey: monitor/elect/reconfigure;
- Valkey -> Sentinel: state/health observation;
- HAProxy -> backend: health/role probe;
- backend -> HAProxy: probe result when needed;
- Reserved-IP controller -> etcd: ownership lock;
- Reserved-IP controller -> DigitalOcean API: move Reserved IPv4;
- OpenBao voter <-> voter: internal Raft only.

### Pass 6 - Operations branch

Add Grafana read-only.

### Pass 7 - Status and trust-boundary annotations

Apply current-state tags and TLS/mTLS/SCRAM/OTAA labels only after the topology is visually stable.

### Pass 8 - Final simplification review

For every box ask:

> If this box is removed, does the reader lose a real processing, durability, routing, security, evidence, HA, or external-system boundary?

If the answer is no, remove it or convert it to an annotation.

That rule is the final defense against an unreadable “every package is a box” architecture diagram.
