# CHAPTER III
# FRAMEWORK AND METHODOLOGY

Chapter 3 presents the framework and methodology used to design, develop, and evaluate the proposed blockchain-enabled LoRaWAN agricultural monitoring prototype. It discusses the study’s conceptual framework, research design, prototype architecture and experimental setting, development and data-collection procedures, security boundary and threat model, evaluation methods, data analysis, and ethical considerations. The chapter reflects the final dissertation test arrangement, in which two RAK4631 WisBlock Core modules are used as controlled sensor emulators, a Raspberry Pi 4B with a RAK5146 operates as the physical LoRaWAN gateway, and the minimum server-side services required for the experiments run in a separate local virtual machine. The arrangement was selected so that the study can preserve the real LoRaWAN radio and security path while keeping the generated agricultural values controlled, repeatable, and suitable for comparison across repeated tests.

## 3.1 Conceptual Framework

The Input–Process–Output (IPO) model was used as the conceptual framework because the study focuses on the design, operation, and evaluation of a technological prototype. The inputs consist of deterministic agricultural-style sensor data, LoRaWAN network events, system loads, and predefined normal and attack conditions. These inputs are processed through physical LoRaWAN transmission, Raspberry Pi gateway forwarding, ChirpStack network processing, MQTT messaging, Node-RED validation, PostgreSQL/TimescaleDB storage, cryptographic evidence generation, and Hyperledger Fabric verification. The resulting outputs are evaluated in terms of system performance, security effectiveness, data integrity, traceability, and resilience.

The input stage uses controlled sensor values rather than relying exclusively on changing environmental conditions. A RAK4631-based legitimate sensor emulator, designated **EMU-01**, produces deterministic temperature, humidity, soil-moisture, and battery values every 15 seconds. Each payload contains a monotonically increasing `test_sequence` and an emulator uptime value. The values are synthetic, but the transmission is not simulated at the application layer. EMU-01 performs OTAA and sends the payload through the physical AS923 LoRaWAN radio link to the RAK5146 gateway. A second RAK4631, designated **SEC-02**, is reserved for invalid-credential, replay, and spoofing conditions. Separating the two roles prevents security-test settings from altering the normal device configuration and allows the legitimate transmitter to remain unchanged across repeated experiments.

This controlled source was selected because the research questions concern the behavior of the LoRaWAN, application, storage, and blockchain pipeline rather than the agronomic accuracy of a particular probe. Deterministic values provide a known expected sequence that can be compared with the records received by ChirpStack, stored in TimescaleDB, and linked to Hyperledger Fabric. Missing, duplicated, altered, or reordered records can therefore be identified more reliably than when the source values change unpredictably with the environment. The use of a hardware emulator also preserves the physical radio path, including OTAA, frame counters, message integrity codes, RF reception, and gateway forwarding. Directly publishing fabricated JSON to MQTT would be useful for application testing but would bypass the LoRaWAN controls that are part of this study.

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

`Input: deterministic agricultural-style telemetry, LoRaWAN events, security-test conditions, traffic load, and WAN-interruption conditions -> Process: RAK4631 over real AS923 LoRaWAN -> Raspberry Pi 4B + RAK5146 gateway -> local gateway MQTT buffer -> mTLS server MQTT -> ChirpStack -> Node-RED -> PostgreSQL/TimescaleDB + Fabric outbox -> Fabric adapter/OpenBao -> external Hyperledger Fabric -> Output: performance, security, integrity, traceability, and resilience.`

## 3.2 Methodology

### 3.2.1 Research Design

This study used a design and development research approach supported by experimental prototype testing. This approach was appropriate because the study involved creating, integrating, and evaluating a working Hyperledger Fabric-based security prototype for LoRaWAN IoT data in a smart agricultural-monitoring context. Similar studies developed and experimentally tested LoRa-blockchain and agricultural IoT prototypes to assess system functionality, data verification, access control, and transaction performance [25], [26], [31].

In this study, the prototype was designed to transmit controlled agricultural-style readings through a physical LoRaWAN link, process the accepted events through an edge-to-server pipeline, store the complete records in PostgreSQL/TimescaleDB, and produce cryptographic evidence that can be verified against Hyperledger Fabric. Experimental testing was then used to determine whether the prototype could reliably complete the data flow, reject selected invalid inputs, detect controlled changes to records, reconstruct record history, and recover from temporary Internet interruption with acceptable prototype-level performance.

The counted dissertation experiments use deterministic sensor emulation rather than uncontrolled field measurements. This does not remove the physical LoRaWAN path from the experiment. The radio, gateway, OTAA authentication, frame-counter validation, MIC verification, MQTT transport, ChirpStack processing, database storage, and Fabric integration remain real components of the tested system. The controlled input was chosen so repeated trials can be compared against a known sequence and known expected values.

### 3.2.2 Prototype Architecture and Experimental Setting

The experimental testbed was configured as an isolated local LoRaWAN laboratory environment using hardware from the WisBlock Agriculture Kit, a Raspberry Pi 4B with a RAK5146 concentrator, a separate test laptop, and a local Ubuntu Server virtual machine. The WisBlock Agriculture Kit provides agricultural sensor modules and two RAK4631 WisBlock Core modules. For the counted experiments, the two RAK4631 cores are assigned fixed test roles rather than relying on the physical sensor modules to produce naturally changing values.

The first RAK4631 is designated **EMU-01**, the legitimate deterministic sensor emulator. It is registered in ChirpStack as a Class A OTAA end device and is the only device that holds the legitimate DevEUI, JoinEUI, and AppKey used for normal operation. EMU-01 sends one 17-byte versioned test payload every 15 seconds. The payload contains the payload version, `test_sequence`, emulator uptime, deterministic temperature, humidity, soil-moisture, and battery values. The second RAK4631 is designated **SEC-02** and is reserved for controlled invalid-device, replay, and spoofing tests. SEC-02 is not provided with EMU-01’s legitimate AppKey or legitimate session keys.

Using two fixed hardware roles improves experimental control. The legitimate device can remain on one frozen firmware, payload format, region, interval, and credential set throughout the experiment, while SEC-02 can be reconfigured for wrong-AppKey joins, unregistered-device joins, and raw LoRa transmissions. This prevents security-test preparation from unintentionally changing the source used for baseline, integrity, traceability, flooding, and resilience measurements.

The actual Agriculture Kit probes may be connected for a separate physical-sensor demonstration, but they are not required for the counted network and security dataset. This separation prevents changes in soil, temperature, light, or rain from becoming uncontrolled variables in experiments whose principal purpose is to measure delivery, authentication, data handling, integrity, traceability, and recovery. The final results must therefore describe the values generated by EMU-01 as deterministic synthetic agricultural readings, not as physical measurements observed by the probes.

The Raspberry Pi 4B and RAK5146 form the physical LoRaWAN gateway. The gateway uses the official ChirpStack Gateway OS Base image rather than running the full application stack on Raspberry Pi OS. The RAK5146 is controlled by ChirpStack Concentratord using the approved Philippines AS923/AS923-1 channel plan. The active 16-hexadecimal Gateway EUI reported by Concentratord is used consistently in ChirpStack registration, the gateway certificate common name, and the server MQTT access-control rules.

The gateway data path is intentionally narrow. ChirpStack MQTT Forwarder publishes Protobuf gateway messages at QoS 1 to a Mosquitto broker listening only on `127.0.0.1:1883`. Mosquitto persists a bounded queue and bridges uplink and state topics to the server through mutual TLS on TCP port 8883. A separate non-persistent downlink bridge is used so expired Class A downlinks are not intentionally replayed after an outage. UDP Forwarder remains disabled so the experiment has one defined gateway-to-server path.

This local buffer was retained because resilience is part of the prototype design. A temporary loss of remote connectivity should not require the gateway to discard every uplink immediately. At the same time, the queue is treated as an availability mechanism rather than an immutable security record. LoRaWAN authentication still occurs in ChirpStack, and the later integrity evidence is generated in the server-side attestation path.

The application and network-server services run on one Ubuntu Server 24.04 LTS virtual machine with 5 GiB of RAM, 4 vCPU cores, and at least 50 GiB of SSD-backed storage. The physical laboratory computer has 8 GiB of RAM and 8 CPU threads. The VM is deliberately not assigned all host resources. Retaining approximately 3 GiB of host memory and the remaining CPU capacity reduces the risk that the host operating system, hypervisor, browser, and SSH tools will force the machine into sustained swapping during measured runs.

The server contains seven required services: Mosquitto, Valkey, ChirpStack, PostgreSQL/TimescaleDB, Node-RED, OpenBao, and the Fabric adapter. The single PostgreSQL/TimescaleDB container hosts two logically separate databases: one for ChirpStack state and one for LoRaWAN telemetry and Fabric outbox records. This consolidation is a test-only resource optimization. It reduces memory overhead on the 5 GiB VM without changing the logical separation of ChirpStack state and telemetry data. A full deployment may use separate database nodes or high-availability components, but those components are outside the measured dissertation testbed.

Grafana, etcd, Patroni/Spilo replicas, HAProxy, PgBouncer, Prometheus, and other production monitoring or high-availability services are not installed on the dissertation VM. Their exclusion is intentional because they would consume resources while not contributing directly to the defined experimental measures. Resource utilization is captured through Docker and Linux system logs so the measurements can be obtained without adding another continuously running service.

ChirpStack is configured for the AS923 region and uses the server Mosquitto broker for both gateway and application messaging. Node-RED receives accepted application events, validates the decoded payload, retains the deterministic `test_sequence`, and writes normalized records to TimescaleDB. A stable application event identity, `event_key`, is used as the trace identifier. This same value is preserved as `source_event_key` in the Fabric outbox, and the corresponding Fabric event key is derived as `uplink:<event_key>`. Reusing the application’s stable identity avoids introducing a second random trace identifier solely for the dissertation.

The Fabric outbox decouples telemetry ingestion from blockchain availability. Node-RED stores the accepted telemetry and selected outbox job locally before Fabric submission occurs. The Fabric adapter then performs canonicalization, SHA-256 hashing, OpenBao sign/verify operations, and Fabric submission. The external Fabric network is not treated as a local service inside the dissertation VM. If the Fabric endpoint is unavailable, telemetry storage continues and the outbox retains the pending work for later reconciliation. This behavior is important to the resilience test because the system should not lose sensor telemetry merely because the external blockchain path is temporarily unreachable.

**Figure 2. RAK4631 WisBlock Core Modules and Agriculture Kit Components Used in the Prototype**

The figure may retain the Agriculture Kit hardware image, but the caption or accompanying text should make clear that the two RAK4631 cores are configured as EMU-01 and SEC-02 for the counted tests, while the physical probes are optional for demonstration.

**Figure 3. Raspberry Pi 4B and RAK5146 LoRaWAN Gateway Used in the Prototype**

**Figure 4. Revised LoRaWAN–Gateway–Server–Blockchain Experimental Architecture**

The revised architecture should show the following actual test path:

`RAK4631 EMU-01 -> real AS923 RF -> RAK5146 + Raspberry Pi 4B -> Concentratord -> MQTT Forwarder -> gateway Mosquitto persistent buffer -> mTLS -> server Mosquitto -> ChirpStack -> Node-RED -> PostgreSQL/TimescaleDB -> Fabric outbox -> Fabric adapter -> OpenBao -> external Hyperledger Fabric.`

A second branch should identify `RAK4631 SEC-02` as the security test node used for invalid OTAA and raw-RF replay/spoofing conditions. The server VM resource profile of 5 GiB RAM and 4 vCPU may also be shown to distinguish it from the 8 GiB/8-thread physical host.

### 3.2.3 Prototype Development and Data Collection Procedure

The prototype will be developed and verified in stages. The Raspberry Pi 4B and RAK5146 gateway will first be assembled, the official ChirpStack Gateway OS Base image installed, Concentratord configured for the approved AS923 channel plan, and the active Gateway EUI recorded. The test server will then be created as a local Ubuntu Server VM and the seven minimum services will be deployed. The server broker will issue the mutual-TLS identity and topic access rules for the recorded Gateway EUI before the gateway’s remote MQTT bridge is enabled.

After the server identity is prepared, the gateway Mosquitto store-and-forward buffer and MQTT Forwarder will be configured and verified. The gateway will be considered ready only after a real gateway event is observed locally, delivered through the mTLS bridge, processed by the server broker, and reflected by ChirpStack. The testbed will not rely on automatic gateway discovery; the exact Gateway EUI must be registered explicitly in ChirpStack.

The two RAK4631 cores will then be standardized on the same RUI3 firmware family and physically labeled. EMU-01 will be configured as the legitimate deterministic OTAA transmitter, while SEC-02 will be prepared as the security node. The firmware version, hardware identity, AS923 sub-band, payload-contract version, and relevant non-secret configuration values will be frozen and recorded before counted tests begin. The legitimate AppKey and session keys will not be placed in result files, screenshots, or SEC-02.

EMU-01 will use a fixed 17-byte payload contract. The deterministic values are generated from `test_sequence`, allowing the expected value and order of every scheduled reading to be known independently of the database. The serial evidence log from EMU-01 will record one line for every scheduled transmission attempt. This source log will be retained because packet-delivery calculations require a denominator that includes scheduled transmissions even when a reading does not later appear in the database.

Before any counted experiment, the complete path will be tested using one real over-the-air EMU-01 uplink. The reading must be observed at the gateway and ChirpStack, accepted through Node-RED, written to TimescaleDB, and, for a selected event, processed through the outbox, OpenBao, and a valid Fabric commit. The test VM will also be checked for service restarts, out-of-memory events, or other conditions that could invalidate performance measurements.

A configuration baseline will be saved before the final tests. Container images, Compose configuration, Gateway EUI, Device EUI, firmware versions, payload contract, region settings, Node-RED flow revision, database schema version, and Fabric contract version will be recorded. The configuration will remain unchanged during repeated trials of the same experiment. Raw logs and calculated summaries will be stored separately so later calculations can be traced back to original evidence.

System logs, emulator source logs, ChirpStack events, MQTT logs, Node-RED logs, TimescaleDB exports, Fabric outbox records, external Fabric transaction evidence, network counters, and CPU/memory samples will be retained. A five-second resource-sampling interval will be used for the server containers and, when required, for the Raspberry Pi gateway. Gateway and server resource utilization will be kept as separate measurement series because they represent different physical systems.

### 3.2.4 Normal-Operation Performance Test Procedure

A normal-operation performance test will be conducted to establish the baseline performance of the prototype before the security, flooding, and resilience tests. During this test, only EMU-01 and the normal authorized services will be active. SEC-02 will remain idle, no invalid traffic will be generated, no Internet interruption will be introduced, and no required service will be intentionally restarted.

EMU-01 will transmit one deterministic reading every 15 seconds for 30 minutes, producing approximately 120 scheduled transmissions per run. The test will be repeated three times using the same firmware, payload format, channel plan, Node-RED flow, database schema, and server configuration. The 15-second interval is retained because it provides enough observations for calculating delivery and latency while keeping the traffic load representative of a low-rate agricultural sensing application.

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

The test will be conducted on the isolated laboratory network using EMU-01 for the legitimate LoRaWAN condition and SEC-02 for the invalid-device conditions. This arrangement is used so the legitimate emulator firmware and secret root key do not need to be modified between normal and invalid trials.

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

For the 10 unchanged application-layer controls, the selected deterministic EMU-01 value will remain unchanged and the two test hashes should match. The record may then continue through the normal TimescaleDB and Fabric path. For the 10 alteration trials, a controlled Node-RED test function will modify one defined value after the initial test hash has been generated. The second test hash should differ, causing the event to be quarantined. The altered event must not be stored as a valid telemetry record or submitted as a valid Fabric attestation.

The normal Fabric evidence path remains separate. The Fabric adapter constructs the approved canonical evidence representation, applies the defined canonicalization rules, calculates SHA-256, requests OpenBao Transit signing and verification, and submits the resulting evidence to the external Fabric network. This separation is methodologically important because the temporary Node-RED hash is an experimental control, while the Fabric adapter digest is the production attestation digest.

For the post-storage test, 10 valid EMU-01 records must first have confirmed Fabric evidence. A temporary database role with narrowly limited update permission will then modify only the selected controlled field in each test row. The already sealed outbox evidence and original Fabric transaction will not be changed. A reviewed read-only verification function using the same production v1 canonicalization rules will reconstruct the canonical evidence from the current database row and calculate the current-source SHA-256 without signing, updating the outbox, or submitting another Fabric transaction. The recomputed current-source digest will then be compared with the original Fabric digest.

This requirement prevents the test from hashing an arbitrary PostgreSQL JSON representation that may differ from the actual bytes used by the production evidence contract. If the reviewed read-only canonicalization function is unavailable, the exact post-storage integrity test is considered blocked rather than replaced with a different hash calculation.

The integrity analysis will report integrity-verification rate, tamper-detection rate, false positives, false negatives, unauthorized storage, and verification time. The principal requirement is zero false negatives and zero unauthorized storage for application-layer altered records.

#### 3.2.6.4 Traceability Test Procedure

Traceability refers to the ability of the prototype to identify the origin and complete processing history of a sensor reading. The current implementation already creates a stable `event_key` for each accepted application event. This value will be used as the trace identifier rather than creating an additional random `trace_id` only for the dissertation. The Fabric outbox stores the same value as `source_event_key`, and the Fabric event identity is derived from it. This provides one consistent link across the application database and blockchain path.

The traceability assessment will include 10 individual-record trials and 10 device-history reconstruction trials. Each history trial will contain five consecutive EMU-01 readings, giving 60 records across 20 traceability trials.

For each tested record, the researcher will retain the event key, Device EUI, frame counter, EMU-01 `test_sequence`, sensor value and unit, event timestamp, Gateway EUI, TimescaleDB identity, SHA-256 digest, Fabric transaction ID, and commit timestamp or block reference when available. The deterministic `test_sequence` is useful because the expected order can be checked independently of the database query.

For individual-record tracing, one event key will be used to retrieve the TimescaleDB record, normalized measurements, outbox entry, digest, and Fabric transaction. A trial will succeed only when the expected fields are complete and the database-to-Fabric link is correct.

For device-history reconstruction, five consecutive EMU-01 readings will be selected using their sequence/frame-counter/time boundaries. The database and corresponding Fabric links will be queried and compared with the original EMU-01 source log. Missing, duplicated, incorrectly ordered, or incorrectly linked records will be counted as traceability errors.

Trace retrieval success rate, record completeness rate, database–Fabric linkage rate, chronological-order accuracy, missing-record count, duplicate-record count, retrieval time, and reconstruction time will be reported.

#### 3.2.6.5 DoS or Flooding Test Procedure

A Denial-of-Service or flooding condition occurs when a large number of requests or messages are sent within a short period and may consume processing, memory, bandwidth, or connection resources. The present study adapts this concept to the MQTT and application layers of the prototype. Radio-frequency jamming is not included because it requires different equipment and could interfere with other wireless users.

Two controlled tests will be conducted: MQTT invalid-connection flooding and invalid application-message flooding. Both will use a separate Linux test laptop as the traffic generator. EMU-01 will continue sending one legitimate deterministic reading every 15 seconds so the study can measure whether valid telemetry continues while the invalid load is present.

The normal gateway mTLS listener will not be flooded. Instead, a temporary test-only broker listener will be published on the laboratory interface and restricted by the host firewall to the test laptop. A dedicated test account and test topic will be used. This design reduces the chance that the load generator alters the security assumptions of the actual gateway ingress and makes the experiment easier to remove cleanly after testing.

Each test will use three conditions: normal traffic, moderate flooding at 10 invalid requests or messages per second, and high flooding at 50 per second. Each condition will run for five minutes and will be repeated three times, producing 18 experimental runs. EMU-01 should generate approximately 20 legitimate readings per five-minute run. Moderate flooding therefore produces approximately 3,000 invalid events per run and high flooding approximately 15,000 per run. A five-minute recovery observation period will follow each run.

The traffic rates will first be verified in a short pilot. Once the load generator can reliably reach the selected rates without itself becoming the bottleneck, the rates will be frozen for the three repetitions. This prevents a change in traffic generation from becoming an uncontrolled variable between runs.

For MQTT connection flooding, the test laptop will repeatedly attempt new connections using intentionally incorrect credentials. Mosquitto should reject the connections while legitimate gateway/ChirpStack traffic continues. For invalid application-message flooding, the test laptop will publish malformed records containing missing fields, invalid device identifiers, invalid timestamps, or incorrect value types to the isolated test topic. Node-RED should reject or quarantine the invalid messages before they enter the valid telemetry or Fabric path.

The measures will include legitimate-message delivery, invalid-traffic rejection, legitimate-message latency, valid-message throughput, server CPU/memory, gateway CPU/memory when collected, network counters, service availability, unauthorized record count, and recovery time. Server and gateway utilization will be reported separately. Security success requires that invalid traffic does not create valid database or Fabric records and that legitimate EMU-01 traffic continues without sustained service failure.

#### 3.2.6.6 Resilience and Recovery Test Procedure

System resilience refers to the ability of the prototype to continue its essential local functions during a disruption and return to normal operation without losing, duplicating, or incorrectly linking data. Following the general interruption-and-recovery approach used in earlier related work [40], [47], the present study will conduct an Internet/WAN interruption test. This test does not represent a Raspberry Pi power failure or complete local-network failure.

Each run will include a 30-minute normal period, a 60-minute Internet-interruption period, and a 30-minute recovery period. EMU-01 will continue its fixed 15-second schedule throughout the two-hour run. Approximately 120 readings are expected before interruption, 240 during the interruption, and 120 after reconnection, for approximately 480 readings per run and 1,440 across three runs.

The interruption will be implemented using a router, hypervisor, or firewall rule that blocks external Internet egress from the dissertation server while preserving the local laboratory subnet. The VM network interface will not simply be disabled if doing so would also break the gateway-to-server LAN. Before the test, the researcher will prove that the gateway can reach server MQTT over the LAN and that the external Fabric endpoint is reachable. During the interruption, the gateway-to-server MQTT path must remain reachable while the external Internet/Fabric endpoint is unavailable.

This distinction reflects the actual architecture. ChirpStack, Mosquitto, Node-RED, TimescaleDB, OpenBao, and the Fabric outbox are local to the test environment and should remain available. The external Fabric network may be unreachable during the WAN block. Consequently, the expected behavior is that local telemetry continues to be received and stored, while Fabric work becomes pending or otherwise retryable in the outbox. The study will not report a Fabric commit during the disconnected period unless the external Fabric service was actually reachable and a valid commit can be proven.

After Internet connectivity is restored, the Fabric adapter will be observed while pending or uncertain work is reconciled. Recovery is successful when eligible outage work drains or reconciles without conflicting duplicate ledger state and the system resumes its normal external connectivity. Telemetry collection will continue for the full 30-minute recovery period.

For each period, the researcher will record expected EMU-01 sequence values, stored readings, missing readings, duplicate readings, local service availability, Fabric work queued during the interruption, Fabric work confirmed after recovery, latency, recovery time, and chronological/frame-counter accuracy. The resilience requirement is that local telemetry remains available during external Internet loss and that queued blockchain work can recover without corrupting or duplicating the stored record history.

A separate gateway-backhaul buffer test may also be conducted to demonstrate that the Raspberry Pi local Mosquitto queue can retain uplinks when the gateway’s route to the server broker is interrupted. This is an architectural availability check and is not part of the counted Table 17 experiment unless the methodology is explicitly expanded to include it.

## 3.3 Ethical Considerations

This study involves the development and testing of an IoT and blockchain-based prototype and does not collect personal information from human participants. The counted experiments use deterministic synthetic agricultural-style readings generated by the RAK4631 emulator. The values are used to test system behavior and are not presented as actual agronomic observations of a particular plantation.

Any separate field or physical-sensor demonstration should be conducted only with the permission of the concerned site or plantation management and should not interfere with normal operations or damage crops and equipment. The counted security experiments, including replay, spoofing, controlled database tampering, and flooding, will be conducted only inside the authorized isolated laboratory environment.

All device identifiers, access keys, login credentials, server addresses, certificates, and blockchain identities will be handled securely. Legitimate AppKeys, session keys, Fabric private keys, OpenBao recovery material, passwords, and tokens will not be placed in screenshots, result CSV files, Markdown documentation, or public repositories. SEC-02 will not be provisioned with EMU-01’s legitimate session keys for the spoofing experiment.

The data-integrity experiment will modify only dedicated test records. A readable database backup will be created before post-storage tampering, and the temporary tamper account will be removed after the experiment. The flooding test will use temporary listeners, test accounts, and firewall restrictions and will not target external systems or unrelated network users.

The results will be reported honestly, including failed transmissions, invalid trials, service failures, and blocked test conditions. A trial will not be reported as a successful security rejection when the attack packet failed to reach the layer being evaluated. Likewise, Fabric-dependent results will not be fabricated when the external Fabric endpoint, approved identities, or reviewed adapter functionality are unavailable. Since the dissertation expands earlier published work, the original publication will be cited and acknowledged as required to preserve academic integrity.
