# CHAPTER III
# FRAMEWORK AND METHODOLOGY

Chapter 3 presents the framework and methodology used to design, develop, and evaluate the proposed blockchain-enabled LoRaWAN agricultural monitoring prototype. It reflects the final dissertation arrangement: EMU-01 is the assembled RAK4631 Agriculture Kit sensor node, SEC-02 is the separate RAK4631 security-test fixture, the Raspberry Pi 4B + RAK5146 is the physical LoRaWAN gateway, and the minimum experiment services run on a separate local virtual machine. This keeps the real sensing, LoRaWAN radio, security, application, storage, and blockchain paths in the measured system while preserving repeatable identities, payload structure, test conditions, and evidence collection.

## 3.1 Conceptual Framework

The Input-Process-Output (IPO) model was used as the conceptual framework because the study focuses on the design, operation, and evaluation of a technological prototype. The inputs consist of real Agriculture Kit sensor readings, LoRaWAN network events, system loads, and predefined normal and attack conditions. These inputs are processed through physical LoRaWAN transmission, Raspberry Pi gateway forwarding, ChirpStack network processing, MQTT messaging, Node-RED validation, PostgreSQL/TimescaleDB storage, cryptographic evidence generation, and Hyperledger Fabric verification. The resulting outputs are evaluated in terms of system performance, security effectiveness, data integrity, traceability, and resilience.

The input stage uses the assembled **EMU-01** physical sensor node. EMU-01 samples the installed soil, UV, barometric, ambient-light, environmental, rain, and battery inputs and transmits the frozen 46-byte payload-v2 containing a monotonically increasing `sequence`, uptime, sensor fields, and a validity bitmap. The values are real readings from the prototype hardware; experimental repeatability comes from the frozen hardware map, payload contract, radio profile, cadence profile, and sequence identity rather than from fabricated sensor values. A second RAK4631, **SEC-02**, is reserved for invalid-credential, replay, spoofing, and other authorized security fixtures and never reuses EMU-01 credentials.

This physical source was selected because the study evaluates the complete IoT path, not only synthetic application traffic. The monotonic EMU-01 sequence, LoRaWAN frame counter, Device EUI, Gateway EUI, stable application event identity, and retained Serial/gateway/server evidence allow missing, duplicated, altered, or reordered records to be detected without assuming that naturally changing sensor values should be deterministic. Keeping the real sensor and RF path also preserves OTAA, frame-counter checks, MIC verification, RF reception, gateway forwarding, payload decoding, and application processing that would be bypassed by publishing fabricated JSON directly to MQTT.

In the process stage, EMU-01 transmits through the AS923 radio link to the Raspberry Pi 4B and RAK5146 gateway. ChirpStack Concentratord controls the concentrator hardware, while ChirpStack MQTT Forwarder converts gateway events to the standard ChirpStack MQTT format. The MQTT Forwarder publishes first to a Mosquitto broker bound only to `127.0.0.1` on the gateway. This local broker provides a bounded persistent store-and-forward queue. The first MQTT hop is intentionally kept on the gateway because temporary backhaul loss should not require the radio side of the prototype to stop collecting uplinks. The loopback-only listener also prevents ordinary LAN clients from using the local gateway broker as an exposed message-ingress point.

The gateway Mosquitto broker then forwards gateway events to the server broker through a mutual-TLS bridge. The gateway certificate identity is bound to the Gateway EUI and the broker access-control list limits the gateway to its own topic hierarchy. This design separates local availability from remote transport security: the local queue retains uplinks during temporary disconnection, while mutual TLS authenticates and protects the gateway-to-server connection.

The server-side test environment runs on a single Ubuntu Server virtual machine allocated 5 GiB of RAM and 4 virtual CPU cores on a physical host with 8 GiB of RAM and 8 CPU threads. Only a portion of the host resources is assigned to the VM so that the host operating system and hypervisor retain enough memory and CPU capacity to operate without sustained swapping. This is important because host-side resource starvation could artificially increase latency and distort the performance measurements being collected from the prototype.

The minimum server stack contains Mosquitto, Valkey, ChirpStack, PostgreSQL/TimescaleDB, Node-RED, OpenBao, and the Fabric adapter. Production high-availability components such as etcd, Patroni replicas, HAProxy, PgBouncer, and Grafana are deliberately excluded from the dissertation test VM. They are useful in a full deployment but do not directly contribute to the Chapter III and Chapter IV measurements. Removing them reduces background CPU and memory consumption and makes the measured resource use more representative of the functions actually under evaluation. CPU and memory utilization are collected using Linux and Docker resource logs instead of adding a separate monitoring platform.

On the server, Mosquitto receives the authenticated gateway MQTT traffic. ChirpStack validates the LoRaWAN device and protocol state and publishes accepted application events. Node-RED is placed **before PostgreSQL** as the application-ingestion gate. It validates required identity and timestamp fields, applies the reviewed sensor-field mapping, normalizes values and units, derives the stable `event_key`, and builds parameterized database writes. PostgreSQL with the TimescaleDB extension then provides durable storage, uniqueness constraints, transactions, roles, and schema enforcement for the complete telemetry records and normalized measurements. For events selected by the dissertation Fabric policy, Node-RED also creates the Fabric outbox row in the same PostgreSQL transaction as the telemetry insert, so telemetry and its required blockchain work item cannot silently drift apart.

Node-RED therefore contributes input validation, duplicate control, parameterized-SQL safety, deterministic provenance, and atomic ingestion, but it is not treated as the cryptographic trust anchor. It does not hold the Fabric private key or the OpenBao evidence private key, and it does not generate the production blockchain signature. Those responsibilities remain outside the flow editor so compromise or failure of Node-RED does not automatically expose the evidence-signing key.

The Fabric adapter processes selected outbox records asynchronously. It loads only the approved TimescaleDB source projection, constructs the versioned canonical evidence object, canonicalizes it using the approved rules, calculates SHA-256, and asks OpenBao Transit to sign and verify the exact canonical bytes using the non-exportable `lorawan-evidence` key. The full telemetry record and canonical evidence remain off-chain. The planned Fabric transaction carries only the stable `event_key`, evidence `schema_version` and `event_type`, the SHA-256 digest, and the OpenBao seal algorithm, key-version identifier, and complete versioned signature. Fixed or authoritative ledger metadata such as the digest algorithm, submitting organization, and transaction time should be derived by chaincode or Fabric from the approved contract and caller identity rather than trusted from arbitrary sensor data.

Hyperledger Fabric is external to the dissertation VM and is operated as a separate permissioned network. This separation is deliberate. Sensor telemetry must continue to be received and stored even when the external Fabric service is unavailable. The outbox therefore acts as a durable handoff point: telemetry is committed locally first, while Fabric work can remain pending and be retried or reconciled after connectivity is restored. The blockchain is consequently used as an attestation and traceability layer rather than as the primary time-series database.

The output stage represents the measurable results produced by the prototype. System performance is assessed through packet-delivery rate, end-to-end latency, transaction success rate, throughput, and resource utilization. Security effectiveness is examined through the system’s ability to accept authorized requests and reject invalid OTAA credentials, unauthorized MQTT actions, unauthorized Fabric transactions, replayed LoRaWAN frames, and forged frames with invalid authentication. Data integrity is evaluated through controlled alteration before storage and post-storage database tampering. Traceability is evaluated by reconstructing the link from the LoRaWAN event to TimescaleDB and the corresponding Fabric attestation. Resilience is evaluated by interrupting external Internet access while preserving the local gateway-to-server network and observing whether local telemetry continues and delayed Fabric work recovers correctly afterward.

**Figure 1. Conceptual Framework of the Study**

The revised conceptual framework should present the following flow:

`Input: physical Agriculture Kit telemetry, LoRaWAN events, security-test conditions, traffic load, and WAN-interruption conditions -> Process: RAK4631 over real AS923 LoRaWAN -> Raspberry Pi 4B + RAK5146 gateway -> local gateway MQTT buffer -> mTLS server MQTT -> ChirpStack -> Node-RED -> PostgreSQL/TimescaleDB + Fabric outbox -> Fabric adapter/OpenBao -> external Hyperledger Fabric -> Output: performance, security, integrity, traceability, and resilience.`

## 3.2 Methodology

### 3.2.1 Research Design

This study used a design and development research approach supported by experimental prototype testing. This approach was appropriate because the study involved creating, integrating, and evaluating a working Hyperledger Fabric-based security prototype for LoRaWAN IoT data in a smart agricultural-monitoring context. Similar studies developed and experimentally tested LoRa-blockchain and agricultural IoT prototypes to assess system functionality, data verification, access control, and transaction performance [25], [26], [31].

In this study, the prototype was designed to transmit controlled agricultural-style readings through a physical LoRaWAN link, process the accepted events through an edge-to-server pipeline, store the complete records in PostgreSQL/TimescaleDB, and produce cryptographic evidence that can be verified against Hyperledger Fabric. Experimental testing was then used to determine whether the prototype could reliably complete the data flow, reject selected invalid inputs, detect controlled changes to records, reconstruct record history, and recover from temporary Internet interruption with acceptable prototype-level performance.

The counted dissertation experiments use the same physical EMU-01 payload and sensor hardware that were accepted during bring-up. Repeated trials are controlled by freezing the hardware slot map, firmware/payload version, AS923 radio settings, credentials, application flow, server configuration, and the experiment-specific cadence profile. The sensor values themselves are allowed to vary naturally; `sequence`, frame counter, event identity, and timestamps provide the repeatable record linkage used for delivery, integrity, and traceability analysis.

### 3.2.2 Prototype Architecture and Experimental Setting

The experimental testbed uses the assembled WisBlock Agriculture Kit node, a second RAK4631 security-test core, Gateway-01 (Raspberry Pi 4B with RAK5146 and SIM7600 LTE), a separate test workstation, and the commissioned three-node DigitalOcean Ubuntu Server proof-of-concept. Gateway-01 uses the SIM7600 LTE link as its health-gated primary cloud backhaul, Wi-Fi as automatic fallback, and Ethernet for management/recovery. The two RAK4631 cores have fixed roles: EMU-01 remains the legitimate physical-sensor source, while SEC-02 is reconfigured only for the specific authorized security experiment.

The first RAK4631 is designated **EMU-01**, the legitimate physical Agriculture Kit sensor node. It is registered in ChirpStack as a Class A OTAA end device and is the only device that holds its legitimate DevEUI, JoinEUI, and AppKey. Its frozen payload-v2 is exactly 46 bytes and carries version, monotonic sequence, uptime, soil moisture/temperature, UV index, barometric pressure/temperature, VEML7700 and OPT3001 light values, BME680 environmental values, rain state, battery voltage, and validity bits. The second RAK4631 is designated **SEC-02** and is reserved for controlled invalid-device, replay, and spoofing tests; it is not provided with EMU-01 root or session keys.

Using two fixed hardware roles improves experimental control. The legitimate device can remain on one frozen firmware, payload format, region, interval, and credential set throughout the experiment, while SEC-02 can be reconfigured for wrong-AppKey joins, unregistered-device joins, and raw LoRa transmissions. This prevents security-test preparation from unintentionally changing the source used for baseline, integrity, traceability, flooding, and resilience measurements.

The installed Agriculture Kit probes are part of EMU-01 and are used in the final physical-sensor payload. Their environmental values are not treated as fixed experimental inputs; the controlled experimental variables are the test condition, source identity, payload contract, sequence progression, radio/network configuration, and counted time window. Results must therefore describe these values as prototype sensor measurements, not as deterministic synthetic readings or as calibrated agronomic ground truth.

The Raspberry Pi 4B and RAK5146 form the physical LoRaWAN gateway. The gateway uses the official ChirpStack Gateway OS Base image rather than running the full application stack on Raspberry Pi OS. The RAK5146 is controlled by ChirpStack Concentratord using the approved Philippines AS923/AS923-1 channel plan. The active 16-hexadecimal Gateway EUI reported by Concentratord is used consistently in ChirpStack registration, the gateway certificate common name, and the server MQTT access-control rules.

The gateway data path is intentionally narrow. ChirpStack MQTT Forwarder publishes Protobuf gateway messages at QoS 1 to a Mosquitto broker listening only on `127.0.0.1:1883`. Mosquitto persists a bounded queue and bridges uplink and state topics to the server through mutual TLS on TCP port 8883. A separate non-persistent downlink bridge is used so expired Class A downlinks are not intentionally replayed after an outage. UDP Forwarder remains disabled so the experiment has one defined gateway-to-server path.

This local buffer was retained because resilience is part of the prototype design. A temporary loss of remote connectivity should not require the gateway to discard every uplink immediately. At the same time, the queue is treated as an availability mechanism rather than an immutable security record. LoRaWAN authentication still occurs in ChirpStack, and the later integrity evidence is generated in the server-side attestation path.

The application and network-server services run on the actual commissioned three-node DigitalOcean Ubuntu Server 24.04 LTS proof-of-concept. Each cloud node uses the 1-vCPU/2-GiB profile. The measured system therefore includes the HA and security components that were actually active while the data were generated rather than substituting a reduced single-VM simulation.

The commissioned cloud stack includes etcd, Patroni/Spilo PostgreSQL with TimescaleDB, HAProxy, PgBouncer, Mosquitto HA, Valkey/Sentinel, two ChirpStack instances, OpenBao HA, Node-RED, Grafana, gateway-evidence services, and two Fabric-adapter workers that remain fail-closed/disabled until the external Fabric handoff is installed. Service placement differs by node, so raw CPU and memory observations are retained per node. Chapter IV may summarize the cloud plane using clearly defined aggregate values, but the maximum-loaded node and raw per-node evidence remain available and Gateway-01 utilization is reported separately.

ChirpStack is configured for the AS923 region and uses the server Mosquitto broker for gateway and application messaging. Node-RED receives accepted application events, validates the decoded payload, retains the monotonic EMU-01 `sequence` and sensor validity fields, and writes normalized records to TimescaleDB. A stable application event identity, `event_key`, is used as the trace identifier. This same value is preserved as `source_event_key` in the Fabric outbox, and the corresponding Fabric event key is derived from that stable identity.

The Fabric outbox decouples telemetry ingestion from blockchain availability. Node-RED stores the accepted telemetry and selected outbox job locally before Fabric submission occurs. The Fabric adapter then performs canonicalization, SHA-256 hashing, OpenBao sign/verify operations, and Fabric submission. The external Fabric network is not treated as a local service inside the dissertation VM. If the Fabric endpoint is unavailable, telemetry storage continues and the outbox retains the pending work for later reconciliation. This behavior is important to the resilience test because the system should not lose sensor telemetry merely because the external blockchain path is temporarily unreachable.

**Figure 2. RAK4631 WisBlock Core Modules and Agriculture Kit Components Used in the Prototype**

The figure may retain the Agriculture Kit hardware image, but the caption or accompanying text should make clear that the two RAK4631 cores are configured as EMU-01 and SEC-02 for the counted tests, while the physical probes are optional for demonstration.

**Figure 3. Raspberry Pi 4B and RAK5146 LoRaWAN Gateway Used in the Prototype**

**Figure 4. Revised LoRaWAN–Gateway–Server–Blockchain Experimental Architecture**

The revised architecture should show the following actual test path:

`RAK4631 EMU-01 -> real AS923 RF -> RAK5146 + Raspberry Pi 4B Gateway-01 -> Concentratord -> MQTT Forwarder -> gateway Mosquitto persistent buffer -> mTLS over SIM7600 LTE (Wi-Fi fallback) -> DigitalOcean Reserved IPv4 -> cloud Mosquitto/HA path -> ChirpStack -> Node-RED -> Patroni PostgreSQL/TimescaleDB -> Fabric outbox -> Fabric adapter -> OpenBao -> external Hyperledger Fabric.`

A second branch should identify `RAK4631 SEC-02` as the security test node used for invalid OTAA and raw-RF replay/spoofing conditions. The three cloud nodes should be shown as a cooperating HA proof-of-concept rather than as one local dissertation VM.

### 3.2.3 Prototype Development and Data Collection Procedure

The prototype will be developed and verified in stages. The Raspberry Pi 4B and RAK5146 gateway will first be assembled, the official ChirpStack Gateway OS Base image installed, Concentratord configured for the approved AS923 channel plan, and the active Gateway EUI recorded. The commissioned three-node DigitalOcean cloud proof-of-concept will then provide the network-server, HA, application, database, KMS, monitoring, and evidence services. The public broker path will issue the mutual-TLS identity and topic access rules for the recorded Gateway EUI before the gateway’s remote MQTT bridge is enabled.

After the server identity is prepared, the gateway Mosquitto store-and-forward buffer and MQTT Forwarder will be configured and verified. The gateway will be considered ready only after a real gateway event is observed locally, delivered through the mTLS bridge, processed by the server broker, and reflected by ChirpStack. The testbed will not rely on automatic gateway discovery; the exact Gateway EUI must be registered explicitly in ChirpStack.

The two RAK4631 cores use different firmware roles and must not be forced onto one firmware family. EMU-01 uses the pinned Arduino/RAKwireless build that implements the accepted 46-byte physical-sensor payload-v2 and AS923 OTAA behavior. SEC-02 uses the firmware mode required by its authorized security fixture (currently prepared on RUI3 for LoRaWAN/P2P switching). Both are physically labelled and their non-secret firmware/hardware identity, region, and role are recorded before counted tests. EMU-01 AppKey/session material is never copied into result files or SEC-02.

EMU-01 uses the frozen 46-byte payload-v2. Its monotonic `sequence` and retained Serial `SENSOR_TX` line identify each transmission attempt independently of downstream storage, while the payload validity bitmap records which physical sensor groups were valid. The source log is retained because packet-delivery calculations require a denominator that includes legitimate transmission attempts even when a corresponding event does not later appear in ChirpStack or the database.

Before a counted experiment, the readiness gate must match the decision path being measured. For the complete application/Fabric track, one real over-the-air EMU-01 uplink must be observed at Gateway-01 and ChirpStack, accepted through Node-RED, written to TimescaleDB, and, for a selected event, processed through the outbox/OpenBao path to a valid confirmed Fabric commit; this full path requires `SENSOR_PREFLIGHT_STATUS=GO`. The independent LoRaWAN security track is narrower: when `LORAWAN_TRACK_STATUS=GO`, only the 30 LoRaWAN authentication attempts and the 40 replay/spoofing attempts may begin before external Fabric activation because their allow/reject decision is made at Gateway-01/ChirpStack. These results remain final counted LoRaWAN evidence and are not rerun merely because Fabric is activated later. A fresh run-level precheck is still required immediately before each counted group.

A configuration baseline will be saved before the final tests. Container images, Compose configuration, Gateway EUI, Device EUI, firmware versions, payload contract, region settings, Node-RED flow revision, database schema version, and Fabric contract version will be recorded. The configuration will remain unchanged during repeated trials of the same experiment. Raw logs and calculated summaries will be stored separately so later calculations can be traced back to original evidence.

System logs, EMU-01 Serial source logs, ChirpStack events, MQTT logs, Node-RED logs, TimescaleDB exports, Fabric outbox records, external Fabric transaction evidence, network counters, and CPU/memory samples will be retained. A five-second resource-sampling interval will be used for the server containers and, when required, for the Raspberry Pi gateway. Gateway and server resource utilization will be kept as separate measurement series because they represent different physical systems.

### 3.2.4 Normal-Operation Performance Test Procedure

A normal-operation performance test will be conducted to establish the baseline performance of the prototype before the security, flooding, and resilience tests. During this test, only EMU-01 and the normal authorized services will be active. SEC-02 will remain idle, no invalid traffic will be generated, no Internet interruption will be introduced, and no required service will be intentionally restarted.

For the counted Chapter IV performance/flooding/resilience dataset, EMU-01 uses a **dedicated counted-test cadence profile of one normal uplink every 15 seconds** while retaining the same 46-byte payload-v2, physical sensors, AS923, OTAA, Class A, ADR policy, credentials, decoder, and application path. This cadence is deliberately different from the accepted production profile (60-second local sampling and nominal 5-minute uplinks with +/-15-second jitter) because the 30-minute and five-minute counted windows need enough observations for delivery/latency comparisons. The exact counted-test firmware/configuration hash must be recorded before run 1, kept unchanged across the counted series, and the production profile restored afterward. At 15 seconds, a 30-minute run yields about 120 scheduled normal uplinks.

During each run, the complete data path will be monitored from EMU-01 through the RAK5146 gateway, ChirpStack, Node-RED, TimescaleDB, Fabric outbox, OpenBao, and Hyperledger Fabric. EMU-01’s source log will provide the scheduled `test_sequence` values and transmission attempts. ChirpStack records will identify accepted LoRaWAN uplinks. TimescaleDB will provide accepted application records and database timestamps. The Fabric outbox and ledger evidence will identify submitted and confirmed blockchain transactions.

Packet-delivery rate (PDR) will represent the percentage of unique legitimate LoRaWAN packets successfully accepted by ChirpStack relative to the legitimate transmission attempts scheduled by EMU-01 during the counted window. A failed source-side attempt will not be silently removed from the denominator. Duplicate MQTT delivery caused by QoS 1 will not be counted as an additional radio delivery.

`PDR (%) = (Nreceived / Ntransmitted) × 100`

where `Nreceived` is the number of unique legitimate uplinks accepted by ChirpStack and `Ntransmitted` is the number of scheduled legitimate transmission attempts recorded by EMU-01.

End-to-end latency will measure the elapsed time between a clearly defined upstream event and successful database storage. The preferred definition is sensor-transmission-to-database latency when the EMU-01 transmission timestamp can be reliably correlated with the server clock. If the emulator timestamp cannot be proven comparable with the server clock, the experiment will instead report a clearly named gateway- or ChirpStack-to-database latency. This rule prevents unsynchronized clocks from producing an apparently precise but methodologically invalid end-to-end measurement.

For a valid matched reading:

`Li = Tstorage,i - Tsource,i`

where `Tsource,i` is the verified source timestamp used by the selected latency definition and `Tstorage,i` is the corresponding database storage timestamp. The mean, standard deviation, minimum, and maximum latency will be reported.

Fabric transaction success rate will measure whether selected attestation submissions are confirmed as valid blockchain commits. A transaction identifier alone will not be treated as success. A successful transaction requires a valid commit result.

`TSR (%) = (Nconfirmed / Nsubmitted) × 100`

where `Nconfirmed` is the number of valid confirmed Fabric transactions and `Nsubmitted` is the number of Fabric transactions submitted during the observation window.

System throughput will represent the rate at which unique legitimate records complete the normal application-processing flow and are stored in TimescaleDB.

`Throughput = Nprocessed / T`

where `Nprocessed` is the number of unique legitimate records successfully stored and `T` is the observation duration in minutes. Throughput will be reported as records per minute.

CPU and memory utilization will be measured separately for the server testbed and the Raspberry Pi gateway. The server VM/container measurements will show the computational cost of Mosquitto, Valkey, ChirpStack, Node-RED, TimescaleDB, OpenBao, and the Fabric adapter. The gateway measurements will show the resource use of the Raspberry Pi while Concentratord, MQTT Forwarder, and the local Mosquitto buffer operate. These two series will not be merged into a single percentage because they represent different machines and different responsibilities.

For each normal-operation run, PDR, transaction success rate, throughput, latency, server CPU and memory, and gateway CPU and memory will be recorded. The three runs will establish the baseline against which flooding and resilience conditions are compared.

### 3.2.5 Security Boundary, Threat Model, and Test Scenarios

The prototype will be evaluated through a multilayer security assessment covering the LoRaWAN device and communication layer, gateway and messaging layer, application layer, storage layer, cryptographic evidence path, and blockchain authorization layer. The selected tests focus on threats that can be reproduced safely within the isolated laboratory environment and measured using the available hardware and logs.

The study does not attempt to evaluate every possible IoT attack. Radio-frequency jamming, destructive hardware attacks, and attacks requiring unauthorized access to external systems are outside the scope. Replay and spoofing tests are limited to the authorized laboratory LoRaWAN environment. Flooding is directed only at temporary test listeners and test topics that are isolated from the normal gateway mTLS ingress.

**Table 5. Proposed Security Assessment and Test Plan for the Prototype**

| Security area | Proposed test | Main layer | Why the test is included |
|---|---|---|---|
| Authentication and access control | Correct and incorrect OTAA credentials, MQTT account/topic authorization, and Fabric writer authorization | Device, messaging, blockchain | Verifies that each layer distinguishes authorized from unauthorized identities and actions. |
| Replay and spoofing | Retransmit a previously accepted PHYPayload and transmit an address-level forged frame with invalid MIC | LoRaWAN | Tests ChirpStack frame-counter and cryptographic authentication behavior using real RF reception. |
| Data integrity | Alter a controlled value before storage and modify a stored row after its evidence has been committed | Application and storage | Distinguishes protection before valid storage from later detection of post-storage changes. |
| Traceability | Retrieve one event and reconstruct five-reading histories across TimescaleDB and Fabric | Storage and blockchain | Verifies that stored records can be linked to their source identity and blockchain evidence. |
| DoS or flooding | Invalid MQTT connections and invalid application messages at fixed rates | Messaging and application | Measures whether invalid load affects legitimate processing without exposing the normal gateway listener to deliberate flooding. |
| Resilience | Block external Internet/Fabric reachability while preserving the local gateway-to-server LAN | Edge, server, external integration | Determines whether local telemetry continues and whether queued Fabric work recovers after reconnection. |

### 3.2.6 Prototype Evaluation and Data Analysis

#### 3.2.6.1 Authentication and Access-Control Test Procedure

The authentication and access-control test will determine whether the prototype accepts registered devices and authorized identities while rejecting invalid credentials and prohibited actions. The method retains the three evaluated layers in the original design: LoRaWAN device authentication, MQTT authentication/authorization, and Hyperledger Fabric authorization. Each condition will be repeated 10 times, giving 90 counted attempts in total.

The test will be conducted on the isolated laboratory network using EMU-01 for the legitimate LoRaWAN condition and SEC-02 for the invalid-device conditions. This fixed-role arrangement prevents security-fixture changes from modifying the legitimate source firmware, payload contract, or credentials between normal and invalid trials.

**Table 6. Authentication and Access-Control Test Design**

| Test area | Test condition | Trials | Expected result | Evidence collected |
|---|---|---:|---|---|
| LoRaWAN | EMU-01 with correct OTAA credentials | 10 | Join accepted and test uplink processed | Gateway/ChirpStack JoinRequest, JoinAccept, accepted uplink |
| LoRaWAN | SEC-02 using registered DevEUI/JoinEUI with incorrect AppKey | 10 | Join rejected | Gateway/ChirpStack evidence, absence of JoinAccept and accepted application data |
| LoRaWAN | SEC-02 using unregistered DevEUI | 10 | Device not activated | Gateway/ChirpStack evidence and absence of accepted application data |
| MQTT | Authorized account publishes to allowed test topic | 10 | Publish accepted | Mosquitto and Node-RED test-flow logs |
| MQTT | Correct user with incorrect password | 10 | Connection rejected | Broker authentication error and absence of Node-RED message |
| MQTT | Limited user publishes to prohibited topic | 10 | Publish denied | Broker ACL evidence and absence of Node-RED message |
| Hyperledger Fabric | Authorized writer submits test attestation | 10 | Transaction confirmed | Fabric transaction and commit evidence |
| Hyperledger Fabric | Valid identity without writer permission | 10 | Rejected with unchanged world state | Authorization error and before/after ledger query |
| Hyperledger Fabric | Invalid or untrusted identity | 10 | Identity/transaction rejected | Identity/certificate error and unchanged state |

For the LoRaWAN tests, EMU-01 will perform clean OTAA joins for the legitimate condition. SEC-02 will be configured with a deliberately wrong AppKey for the registered-DevEUI condition and with a separate unregistered DevEUI for the unregistered condition. A join attempt that is never received by the gateway will not be counted as an authentication rejection because that outcome would measure radio-delivery failure rather than the network server’s decision.

For MQTT testing, the normal gateway mTLS ingress will not be exposed for password-based experiments. A temporary test-only listener will be created on the server and restricted by the host firewall to the separate test laptop. Authorized, wrong-password, and prohibited-topic trials will be performed against this isolated listener. The temporary listener and test Node-RED observation flow will be removed after the experiment. This approach tests broker authentication and authorization without weakening the normal gateway transport path.

For Hyperledger Fabric, three identities must be supplied or approved by the external Fabric environment: an authorized writer, a valid identity without write permission, and an invalid/untrusted test identity or certificate fixture. The study will not create local roles and assume that they represent the external Fabric authorization policy. Each unauthorized attempt will be followed by a query of the intended state to verify that no prohibited change occurred.

For every trial, the expected decision, actual decision, response time, error or transaction reference, and unauthorized state change will be recorded. Authorized success rate, unauthorized rejection rate, false acceptance, false rejection, correct-decision rate, mean response time, and unauthorized state-change count will be reported. The principal security requirement is zero false acceptance and zero unauthorized state change.

#### 3.2.6.2 Replay and Spoofing Test Procedure

A replay attack occurs when a previously accepted message is transmitted again so that the receiver may process the same information more than once. Spoofing occurs when an unauthorized transmitter creates a frame that appears to originate from a legitimate device. Following the controlled-injection approach used in earlier related studies [47], [56], the prototype will conduct two practical LoRaWAN-level tests through the physical RAK5146 gateway: an uplink-frame replay test and an invalid-MIC address-impersonation test.

EMU-01 will provide the legitimate control traffic. SEC-02 will be switched to LoRa P2P/raw-transmit mode for the attack traffic. Frame-counter validation will remain enabled in ChirpStack. The security mechanisms will not be disabled to make the attacks easier.

The replay condition will capture the exact PHYPayload bytes of a legitimate accepted EMU-01 uplink together with its frame counter, frequency, data rate, spreading factor, bandwidth, coding rate, and reception information. EMU-01 will then send at least three additional uplinks so the legitimate counter advances. SEC-02 will retransmit the exact old PHYPayload using the matching approved radio parameters. A replay attempt will be counted only when the RAK5146 evidence proves that the RF frame was received. If the gateway did not receive the frame, the trial will be repeated rather than recorded as a successful rejection.

The spoofing condition will use a controlled raw frame that preserves the legitimate device address but contains modified protected bytes or a deliberately invalid MIC that cannot authenticate with EMU-01’s session keys. SEC-02 will not contain the legitimate session keys. This test therefore evaluates address-level impersonation without cryptographic authentication. It does not claim that an outsider without the session keys can construct a correctly encrypted meaningful temperature or soil value.

Each replay and spoofing test will contain 10 legitimate controls and 10 attack attempts, giving 40 counted attempts. For each attack, the gateway reception result, ChirpStack decision, application propagation, database result, Fabric result, and decision time will be recorded. The main requirement is that all legitimate controls are accepted, all received replay/invalid-MIC frames are rejected before application processing, and no attack-generated database or Fabric record is created.

#### 3.2.6.3 Data Integrity Test Procedure

Data integrity refers to maintaining the accuracy and unchanged condition of data while they are processed and stored. The present study will retain two integrity experiments: application-layer alteration before valid storage and post-storage database tampering after the original evidence has been committed to Fabric. Forty attempts will be conducted in total: 10 unchanged application-layer controls, 10 application-layer alterations, 10 unchanged stored-record controls, and 10 post-storage tamper trials.

The current system separates the dissertation’s application-layer test hash from the production blockchain evidence path. Node-RED is not the production evidence signer. For the application-layer experiment only, a temporary test hash gate will calculate one SHA-256 hash before the controlled mutation point and a second hash immediately afterward. The gate will operate only on the designated EMU-01 test records and will be removed or disabled after the experiment. This temporary mechanism exists solely to reproduce the intended “before and after application processing” tamper test.

For the 10 unchanged application-layer controls, the selected EMU-01 sensor field is passed through without mutation and the two test hashes should match. For the 10 alteration trials, a controlled Node-RED test function modifies one defined field only after the initial test hash is generated; the second hash should differ and the event should be quarantined. This experiment tests mutation detection and does not depend on the physical sensor value being predetermined.

The normal Fabric evidence path remains separate. The Fabric adapter constructs the approved canonical evidence representation, applies the defined canonicalization rules, calculates SHA-256, requests OpenBao Transit signing and verification, and submits the resulting evidence to the external Fabric network. This separation is methodologically important because the temporary Node-RED hash is an experimental control, while the Fabric adapter digest is the production attestation digest.

For the post-storage test, 10 valid EMU-01 records must first have confirmed Fabric evidence. A temporary database role with narrowly limited update permission will then modify only the selected controlled field in each test row. The already sealed outbox evidence and original Fabric transaction will not be changed. A reviewed read-only verification function using the same production v1 canonicalization rules will reconstruct the canonical evidence from the current database row and calculate the current-source SHA-256 without signing, updating the outbox, or submitting another Fabric transaction. The recomputed current-source digest will then be compared with the original Fabric digest.

This requirement prevents the test from hashing an arbitrary PostgreSQL JSON representation that may differ from the actual bytes used by the production evidence contract. If the reviewed read-only canonicalization function is unavailable, the exact post-storage integrity test is considered blocked rather than replaced with a different hash calculation.

The integrity analysis will report integrity-verification rate, tamper-detection rate, false positives, false negatives, unauthorized storage, and verification time. The principal requirement is zero false negatives and zero unauthorized storage for application-layer altered records.

#### 3.2.6.4 Traceability Test Procedure

Traceability refers to the ability of the prototype to identify the origin and complete processing history of a sensor reading. The current implementation already creates a stable `event_key` for each accepted application event. This value will be used as the trace identifier rather than creating an additional random `trace_id` only for the dissertation. The Fabric outbox stores the same value as `source_event_key`, and the Fabric event identity is derived from it. This provides one consistent link across the application database and blockchain path.

The traceability assessment will include 10 individual-record trials and 10 device-history reconstruction trials. Each history trial will contain five consecutive EMU-01 readings, giving 60 records across 20 traceability trials.

For each tested record, the researcher will retain the event key, Device EUI, frame counter, EMU-01 `sequence`, relevant sensor value/unit and validity state, event timestamp, Gateway EUI, TimescaleDB identity, SHA-256 digest, Fabric transaction ID, and commit timestamp or block reference when available. The monotonic source sequence provides the independent ordering reference; the physical sensor value itself is not assumed deterministic.

For individual-record tracing, one event key will be used to retrieve the TimescaleDB record, normalized measurements, outbox entry, digest, and Fabric transaction. A trial will succeed only when the expected fields are complete and the database-to-Fabric link is correct.

For device-history reconstruction, five consecutive EMU-01 readings will be selected using their sequence/frame-counter/time boundaries. The database and corresponding Fabric links will be queried and compared with the original EMU-01 source log. Missing, duplicated, incorrectly ordered, or incorrectly linked records will be counted as traceability errors.

Trace retrieval success rate, record completeness rate, database–Fabric linkage rate, chronological-order accuracy, missing-record count, duplicate-record count, retrieval time, and reconstruction time will be reported.

#### 3.2.6.5 DoS or Flooding Test Procedure

A Denial-of-Service or flooding condition occurs when a large number of requests or messages are sent within a short period and may consume processing, memory, bandwidth, or connection resources. The present study adapts this concept to the MQTT and application layers of the prototype. Radio-frequency jamming is not included because it requires different equipment and could interfere with other wireless users.

Two controlled tests will be conducted: MQTT invalid-connection flooding and invalid application-message flooding. Both will use a separate Linux test laptop as the traffic generator. During the counted flooding runs, EMU-01 remains on the frozen **15-second counted-test cadence profile** with the same physical payload-v2 so legitimate continuity can be measured against the invalid load.

The normal gateway mTLS listener will not be flooded. Instead, a temporary test-only broker listener will be published on the laboratory interface and restricted by the host firewall to the test laptop. A dedicated test account and test topic will be used. This design reduces the chance that the load generator alters the security assumptions of the actual gateway ingress and makes the experiment easier to remove cleanly after testing.

Each test will use three conditions: normal traffic, moderate flooding at 10 invalid requests or messages per second, and high flooding at 50 per second. Each condition will run for five minutes and will be repeated three times, producing 18 experimental runs. EMU-01 should generate approximately 20 legitimate readings per five-minute run. Moderate flooding therefore produces approximately 3,000 invalid events per run and high flooding approximately 15,000 per run. A five-minute recovery observation period will follow each run.

The traffic rates will first be verified in a short pilot. Once the load generator can reliably reach the selected rates without itself becoming the bottleneck, the rates will be frozen for the three repetitions. This prevents a change in traffic generation from becoming an uncontrolled variable between runs.

For MQTT connection flooding, the test laptop will repeatedly attempt new connections using intentionally incorrect credentials. Mosquitto should reject the connections while legitimate gateway/ChirpStack traffic continues. For invalid application-message flooding, the test laptop will publish malformed records containing missing fields, invalid device identifiers, invalid timestamps, or incorrect value types to the isolated test topic. Node-RED should reject or quarantine the invalid messages before they enter the valid telemetry or Fabric path.

The measures will include legitimate-message delivery, invalid-traffic rejection, legitimate-message latency, valid-message throughput, server CPU/memory, gateway CPU/memory when collected, network counters, service availability, unauthorized record count, and recovery time. Server and gateway utilization will be reported separately. Security success requires that invalid traffic does not create valid database or Fabric records and that legitimate EMU-01 traffic continues without sustained service failure.

#### 3.2.6.6 Resilience and Recovery Test Procedure

System resilience refers to the ability of the prototype to isolate and recover from failure of a downstream dependency without losing, duplicating, or incorrectly linking telemetry. The live Gateway-01-to-cloud LoRaWAN path itself depends on LTE/Internet connectivity, so a whole-Internet interruption would remove the production transport and would no longer reproduce the architecture assumed by the earlier local-laboratory draft. The counted resilience experiment therefore isolates **external Hyperledger Fabric reachability** while preserving Gateway-01 LTE/public MQTT ingress, the DigitalOcean Reserved-IP path, the three cloud nodes/private VPC, ChirpStack, Node-RED, TimescaleDB, OpenBao, and the Fabric outbox.

Each resilience run will include a 30-minute normal period, a 60-minute external-Fabric interruption period, and a 30-minute recovery period. EMU-01 remains on the frozen **15-second counted-test cadence profile** for the entire two-hour run, yielding approximately 120, 240, and 120 scheduled normal uplinks respectively (about 480 per run and 1,440 across three runs). Do not substitute the production 5-minute scheduler midway through the counted series.

The interruption will be implemented using a narrowly scoped, pre-rehearsed rule on the active Fabric-adapter worker path that prevents reachability to the commissioned external Fabric endpoint without breaking Gateway-01 ingress, cloud/VPC connectivity, PostgreSQL, OpenBao, or operator management. Before the test, the researcher will prove both the normal LoRaWAN/cloud path and a valid Fabric transaction. During the interruption, legitimate LoRaWAN telemetry must continue to reach TimescaleDB while Fabric work remains pending/retryable and no false commit is recorded.

After Fabric reachability is restored, the adapter will be observed while pending or uncertain work is reconciled. Recovery is successful when eligible outage work drains or reconciles without conflicting duplicate ledger state and the system returns to the defined confirmed state. Telemetry collection will continue for the full 30-minute recovery period.

For each period, the researcher will record expected EMU-01 sequence values, stored readings, missing readings, duplicate readings, required service availability, Fabric work queued during the interruption, Fabric work confirmed after recovery, latency, recovery time, and chronological/frame-counter accuracy. The resilience requirement is that telemetry remains available while the external Fabric dependency is isolated and that queued blockchain work recovers without corrupting or duplicating the stored record history. This experiment remains blocked until the real Fabric path has first reached a healthy confirmed state.

A separate gateway-backhaul buffer test may also be conducted to demonstrate that the Raspberry Pi local Mosquitto queue can retain uplinks when the gateway’s route to the server broker is interrupted. This is an architectural availability check and is not part of the counted Table 17 experiment unless the methodology is explicitly expanded to include it.

## 3.3 Ethical Considerations

This study involves the development and testing of an IoT and blockchain-based prototype and does not collect personal information from human participants. EMU-01 records physical prototype sensor readings during the laboratory experiments, but these readings are used to evaluate system behavior and are not presented as calibrated agronomic measurements or claims about a specific plantation.

Any separate field or physical-sensor demonstration should be conducted only with the permission of the concerned site or plantation management and should not interfere with normal operations or damage crops and equipment. The counted security experiments, including replay, spoofing, controlled database tampering, and flooding, will be conducted only inside the authorized isolated laboratory environment.

All device identifiers, access keys, login credentials, server addresses, certificates, and blockchain identities will be handled securely. Legitimate AppKeys, session keys, Fabric private keys, OpenBao recovery material, passwords, and tokens will not be placed in screenshots, result CSV files, Markdown documentation, or public repositories. SEC-02 will not be provisioned with EMU-01’s legitimate session keys for the spoofing experiment.

The data-integrity experiment will modify only dedicated test records. A readable database backup will be created before post-storage tampering, and the temporary tamper account will be removed after the experiment. The flooding test will use temporary listeners, test accounts, and firewall restrictions and will not target external systems or unrelated network users.

The results will be reported honestly, including failed transmissions, invalid trials, service failures, and blocked test conditions. A trial will not be reported as a successful security rejection when the attack packet failed to reach the layer being evaluated. Likewise, Fabric-dependent results will not be fabricated when the external Fabric endpoint, approved identities, or reviewed adapter functionality are unavailable. Since the dissertation expands earlier published work, the original publication will be cited and acknowledged as required to preserve academic integrity.
