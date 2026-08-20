# CHAPTER IV
# RESULTS AND DISCUSSION

Chapter 4 presents the results obtained from the final dissertation test arrangement described in Chapter 3. The chapter should report only measured values supported by the retained raw evidence. The agricultural-style readings used for the counted experiments are generated deterministically by the RAK4631 legitimate sensor emulator, EMU-01, but are transmitted through the real AS923 LoRaWAN radio path. SEC-02 is used only for the defined invalid-device, replay, and spoofing conditions. No result should describe the deterministic emulator values as physical measurements from the Agriculture Kit probes.

The final test architecture differs from an earlier all-in-one Raspberry Pi design. The Raspberry Pi 4B and RAK5146 operate as the physical LoRaWAN gateway, while ChirpStack and the application services run on a separate 5 GiB, 4-vCPU Ubuntu Server VM. This separation should be reflected consistently in the interpretation of performance and resilience results. In particular, server resource utilization must not be reported as Raspberry Pi utilization, and the external Hyperledger Fabric network must not be described as a local service that remained available during an Internet outage when it was actually unreachable.

## 4.1 Prototype Design and Implementation

This section answers Problem 1 by describing the final implemented prototype and explaining why the test arrangement was organized in this form.

The prototype used two RAK4631 WisBlock Core modules from the Agriculture Kit, a Raspberry Pi 4B with a RAK5146 concentrator, a separate Linux test laptop, and a local Ubuntu Server virtual machine. The first RAK4631, EMU-01, served as the registered deterministic OTAA sensor emulator. It produced one versioned 17-byte agricultural-style payload every 15 seconds. Each payload contained a `test_sequence`, emulator uptime, temperature, humidity, soil-moisture, and battery fields whose values were generated deterministically. The second RAK4631, SEC-02, was isolated from the legitimate device credentials and was used for wrong-AppKey joins, unregistered-device joins, replay transmission, and invalid-MIC spoofing.

The use of deterministic emulation allowed the expected order and value of every scheduled reading to be known before the record reached the network. This made it possible to identify missing, duplicated, modified, and incorrectly ordered records using the source `test_sequence`. At the same time, the experiment retained the physical LoRaWAN link. EMU-01 still performed OTAA, transmitted over the approved AS923 channel plan, and passed through the RAK5146 gateway and ChirpStack security checks. The counted test therefore emulated the measurement source rather than the LoRaWAN network itself.

The Raspberry Pi gateway used ChirpStack Gateway OS Base, ChirpStack Concentratord, MQTT Forwarder, and a local Mosquitto broker. MQTT Forwarder published Protobuf gateway messages at QoS 1 to the loopback broker. The local broker maintained a bounded persistent queue and bridged gateway traffic to the server through mutual TLS. This design gave the gateway a simple store-and-forward capability while keeping the local broker unavailable to ordinary LAN clients. The gateway was treated as a transport and availability component; LoRaWAN authentication remained the responsibility of ChirpStack on the server.

The server-side dissertation testbed ran on a single VM with 5 GiB of RAM and 4 vCPU cores. The physical host had 8 GiB of RAM and 8 CPU threads, so the VM was intentionally not assigned all available host resources. This preserved operating capacity for the host OS and hypervisor and reduced the risk that host swapping would distort latency and throughput measurements.

The minimum server stack contained Mosquitto, Valkey, ChirpStack, PostgreSQL/TimescaleDB, Node-RED, OpenBao, and the Fabric adapter. Production high-availability and visualization components such as etcd, Patroni/Spilo, HAProxy, PgBouncer, and Grafana were excluded because they were not required to generate the Chapter IV measures. Linux and Docker logs were used for resource measurements instead of adding a monitoring stack that would consume resources during the experiments.

Accepted ChirpStack application events were first passed through Node-RED and only then written to PostgreSQL/TimescaleDB. Node-RED served as the application-ingestion gate: it validated required identity and timestamp fields, normalized the reviewed sensor fields, derived the stable event identity, used parameterized SQL, and relied on the database transaction and uniqueness constraints to prevent partial or duplicate operational records. These are application and database-safety controls; Node-RED was not the production cryptographic signer.

Selected events also created durable Fabric outbox records in the same database transaction as telemetry ingestion. The Fabric adapter processed the outbox asynchronously, constructed the approved canonical evidence from the stored source fields, calculated SHA-256, and used OpenBao for cryptographic sign/verify operations. Complete raw telemetry and canonical evidence remained off-chain. The external Hyperledger Fabric transaction contained the stable event identity and compact attestation proof: schema version, event type, digest, OpenBao signature algorithm, signing-key version identifier, and complete versioned signature. This separation prevented Fabric unavailability from blocking normal telemetry storage and allowed later database changes to be detected by recomputing the approved evidence digest and comparing it with the committed attestation.

The complete measured path was therefore:

`RAK4631 EMU-01 -> real AS923 LoRaWAN RF -> RAK5146 + Raspberry Pi 4B -> Concentratord -> MQTT Forwarder -> gateway Mosquitto persistent buffer -> mTLS -> server Mosquitto -> ChirpStack -> Node-RED -> PostgreSQL/TimescaleDB -> Fabric outbox -> Fabric adapter -> OpenBao -> external Hyperledger Fabric.`

The discussion for this section should emphasize that the final architecture was intentionally smaller than the full deployment design. The dissertation testbed retained only the technologies required to answer the research problems. This reduced unnecessary background resource use while preserving the actual LoRaWAN, messaging, storage, integrity, and blockchain paths under evaluation.

## 4.2 Prototype Performance under Normal Operating Conditions

This section answers Problem 2. The normal-operation experiment consists of three 30-minute runs with EMU-01 transmitting one deterministic reading every 15 seconds. Approximately 120 scheduled readings are expected in each run. No attack traffic, WAN interruption, or intentional service failure is introduced.

Before presenting the performance measures, state the exact latency definition used. Sensor-transmission-to-database latency should be reported only if the EMU-01 transmission timestamp was demonstrably correlated with the server clock. Otherwise, report the verified gateway- or ChirpStack-to-database latency and use that same definition consistently throughout Chapter 4.

### 4.2.1 Packet-Delivery Rate

Packet-delivery rate should be calculated from the number of unique legitimate packets accepted by ChirpStack divided by the scheduled legitimate transmission attempts recorded by EMU-01. The emulator source log is important because the denominator must include scheduled transmission attempts even when a corresponding record does not appear later in the pipeline.

`PDR (%) = (unique legitimate uplinks accepted by ChirpStack / scheduled EMU-01 transmission attempts) × 100`

Duplicate MQTT delivery must not be counted as an additional radio delivery. The discussion should compare the three runs and identify whether any missing sequence values corresponded to source-side transmission failure, RF loss, gateway delivery failure, or later application processing failure.

**Suggested Table. Normal-Operation Packet-Delivery Results**

| Run | Scheduled EMU-01 attempts | Unique uplinks accepted by ChirpStack | Missing sequence values | PDR (%) |
|---|---:|---:|---:|---:|
| Run 1 | | | | |
| Run 2 | | | | |
| Run 3 | | | | |
| Overall | | | | |

### 4.2.2 End-to-End Latency

Latency should be calculated only for successfully matched records using the verified timestamp boundaries defined in Chapter 3. Each matched observation should retain the `test_sequence`, Device EUI, frame counter or event identity, source timestamp, database timestamp, and calculated latency.

Report the mean, standard deviation, minimum, and maximum for each run and for the combined valid observations when appropriate.

**Suggested Table. Normal-Operation Latency Results**

| Run | Valid matched records | Mean latency (s) | SD (s) | Minimum (s) | Maximum (s) |
|---|---:|---:|---:|---:|---:|
| Run 1 | | | | | |
| Run 2 | | | | | |
| Run 3 | | | | | |

The discussion should not attribute latency only to the Raspberry Pi. The current data path contains the radio link, gateway forwarding, MQTT bridge, server broker, ChirpStack, Node-RED, and database storage. If the source timestamp begins at ChirpStack or the gateway, state that the earlier radio portion is outside the reported latency interval.

### 4.2.3 Transaction Success Rate

The transaction success rate should represent valid confirmed Fabric commits rather than the number of transaction IDs received from a submission call.

`TSR (%) = (confirmed valid Fabric transactions / Fabric transactions submitted) × 100`

A submitted transaction whose commit status is unknown or invalid should not be counted as successful. The discussion should also distinguish locally queued outbox work from confirmed external Fabric transactions.

**Suggested Table. Fabric Transaction Results**

| Run | Transactions submitted | Confirmed valid commits | Failed/invalid | Submitted-unknown | TSR (%) |
|---|---:|---:|---:|---:|---:|
| Run 1 | | | | | |
| Run 2 | | | | | |
| Run 3 | | | | | |

### 4.2.4 System Throughput

System throughput represents the number of unique legitimate EMU-01 records successfully stored in TimescaleDB per minute.

`Throughput = unique legitimate stored records / observation minutes`

Because the input rate is intentionally low, the result should be interpreted as the prototype’s ability to keep pace with the configured sensing interval rather than as a maximum-capacity benchmark. The flooding test later provides the more meaningful stress comparison.

**Suggested Table. Normal-Operation Throughput**

| Run | Unique stored records | Duration (min) | Throughput (records/min) |
|---|---:|---:|---:|
| Run 1 | | 30 | |
| Run 2 | | 30 | |
| Run 3 | | 30 | |

### 4.2.5 Gateway and Test-Server CPU and Memory Utilization

The earlier heading “Raspberry Pi CPU and Memory Utilization” should be expanded because the current architecture separates gateway and application services. The Raspberry Pi runs the gateway functions, while the 5 GiB/4-vCPU VM runs the network server, application, database, KMS, and Fabric-adapter services.

Report the two systems separately. Do not average gateway and server percentages together.

**Suggested Table. Resource Utilization during Normal Operation**

| Run | Server mean CPU (%) | Server max CPU (%) | Server mean memory (%) | Server max memory (%) | Gateway mean CPU (%) | Gateway max CPU (%) | Gateway mean memory (%) | Gateway max memory (%) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Run 1 | | | | | | | | |
| Run 2 | | | | | | | | |
| Run 3 | | | | | | | | |

The discussion should relate the server values to the intentionally minimal seven-service stack and should note whether any required container restarted or whether the host or VM experienced out-of-memory conditions. A run with an unrelated OOM kill or service restart should be treated as invalid rather than silently included in the baseline average.

## 4.3 Security and Resilience Evaluation

This section answers Problem 3.

### 4.3.1 Authentication and Access-Control Test

This section presents the results of the authentication and access-control tests conducted at the LoRaWAN, MQTT, and Hyperledger Fabric layers. The tests examined whether authorized devices and identities were correctly accepted and whether invalid credentials and prohibited actions were rejected. The results were assessed using correct decisions, false acceptances, false rejections, response time, and unauthorized state changes. Table 12 summarizes the 90 counted attempts.

The LoRaWAN trials use EMU-01 for the authorized condition and SEC-02 for the wrong-AppKey and unregistered-DevEUI conditions. The MQTT trials use a temporary test-only listener restricted to the test laptop rather than weakening the normal gateway mTLS listener. Fabric trials use identities supplied or approved by the external Fabric environment.

**Table 12. Results of the Authentication and Access-Control Tests**

| Test layer | Test condition | Trials | Expected decision | Allowed | Rejected | Correct decisions, n (%) | False acceptance | False rejection | Unauthorized state change | Mean response time ± SD (s) |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| LoRaWAN | EMU-01 with correct OTAA credentials | 10 | Allow | | | | — | | — | |
| LoRaWAN | SEC-02 using registered DevEUI with incorrect AppKey | 10 | Reject | | | | | — | — | |
| LoRaWAN | SEC-02 using unregistered DevEUI | 10 | Reject | | | | | — | — | |
| MQTT | Authorized account publishes to allowed test topic | 10 | Allow | | | | — | | — | |
| MQTT | Account uses incorrect password | 10 | Reject | | | | | — | — | |
| MQTT | Limited account publishes to prohibited topic | 10 | Reject publish | | | | | — | — | |
| Hyperledger Fabric | Authorized writer submits test attestation | 10 | Allow/commit | | | | — | | | |
| Hyperledger Fabric | Valid identity without writer permission | 10 | Reject | | | | | — | | |
| Hyperledger Fabric | Invalid or untrusted identity | 10 | Reject | | | | | — | | |

*Note.* False acceptance refers to an unauthorized request that was incorrectly allowed. False rejection refers to an authorized request that was incorrectly denied. An unauthorized state change occurs when a prohibited Fabric request creates or modifies protected ledger state. A LoRaWAN invalid-device transmission that the gateway never received should not be counted as a successful authentication rejection.

The discussion should compare the three layers separately because they use different authentication mechanisms. A successful result should be supported by zero false acceptance and zero unauthorized state change. Any authorized failure caused by RF delivery rather than authentication should be explained separately.

### 4.3.2 Replay and Spoofing Resistance Test

This section presents the results of the LoRaWAN replay and spoofing tests. The assessment examines whether legitimate EMU-01 uplinks are processed normally and whether previously accepted or address-level forged frames transmitted by SEC-02 are rejected before application processing.

A security attempt is counted only when the RAK5146 gateway proves RF reception. This prevents a missed transmission from being misclassified as successful replay or spoofing resistance.

**Table 13. Results of the Replay and Spoofing Tests**

| Test | Test condition | Trials | Expected decision | Received by gateway, n | Accepted by ChirpStack, n | Rejected by ChirpStack, n | Reached MQTT/Node-RED, n | Database records created, n | Fabric transactions created, n | Correct decisions, n (%) | False acceptance, n | False rejection, n | Mean decision time ± SD (s) |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Replay | New legitimate EMU-01 uplink | 10 | Accept | | | | | | | | — | | |
| Replay | Previously accepted PHYPayload retransmitted by SEC-02 with old frame counter | 10 | Reject | 10 | | | | | | | | — | |
| Spoofing | Genuine EMU-01 uplink | 10 | Accept | | | | | | | | — | | |
| Spoofing | SEC-02 raw frame using legitimate address but invalid MIC | 10 | Reject | 10 | | | | | | | | — | |
| Overall | All counted conditions | 40 | — | | | | | | | | | | |

*Note.* False acceptance refers to a replayed or invalid-MIC frame incorrectly accepted as a new legitimate application uplink. Unauthorized propagation occurs when an attack frame reaches the accepted MQTT/Node-RED path, TimescaleDB, or the Fabric outbox/ledger. Attack transmissions not received by the RAK5146 are invalid attempts and are repeated rather than counted as secure rejections.

The spoofing discussion should avoid claiming that SEC-02 generated a semantically valid forged sensor reading without the legitimate session keys. The result demonstrates whether address-level impersonation or modified LoRaWAN bytes with invalid cryptographic authentication are rejected.

### 4.3.3 Data-Integrity Test

This section presents the results of the 40 data-integrity attempts conducted at the application and storage layers. The experiment has two distinct mechanisms and the discussion should keep them separate.

The application-layer experiment uses a temporary Node-RED test hash gate that calculates a SHA-256 value before and after the controlled mutation point. This is an experimental control used to determine whether the deliberately altered record is detected and quarantined before valid storage. It is not the production Fabric evidence signer.

The post-storage experiment uses the production evidence contract. The original Fabric attestation is based on the Fabric adapter’s canonical evidence, SHA-256 digest, and OpenBao sign/verify process. After a selected TimescaleDB source row is modified, the reviewed read-only canonicalizer reconstructs the current source using the same rules and compares the resulting digest with the original Fabric digest.

**Table 14. Results of the Data-Integrity Tests**

| Test area | Test condition | Trials | Expected result | Hash match, n | Hash mismatch, n | Correct decisions, n (%) | False positives, n | False negatives, n | Unauthorized storage, n | Mean verification time ± SD (s) |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|---:|
| Application-layer integrity | EMU-01 record processed without alteration | 10 | Test hashes match; record stored | | | | | — | — | |
| Application-layer integrity | Selected sensor value altered before storage | 10 | Test hashes differ; record quarantined | | | | — | | | |
| Post-storage integrity | Stored source row remains unchanged | 10 | Current-source canonical digest matches original Fabric digest | | | | | — | — | |
| Post-storage integrity | Stored source value altered after confirmed Fabric evidence | 10 | Current-source digest differs from original Fabric digest | | | | — | | — | |
| Overall | All test conditions | 40 | — | | | | | | | |

*Note.* A false positive occurs when an unchanged record is incorrectly reported as altered. A false negative occurs when an altered record is incorrectly reported as valid. Unauthorized storage refers only to an application-layer altered event that was incorrectly stored as a valid operational record. The Node-RED test hash and Fabric adapter evidence digest are different experimental roles and should not be described as the same hash mechanism.

The discussion should also state that the post-storage test verifies whether a stored record changed after the original evidence was created. It does not prove that the original sensor value was physically correct before it entered the system.

### 4.3.4 Traceability Test

This section presents the results of the traceability assessment. The current implementation uses the application `event_key` as the trace identifier and preserves the same value as the Fabric outbox `source_event_key`. The traceability tests therefore evaluate whether that stable identity can be followed from the accepted LoRaWAN/application event through TimescaleDB and the corresponding Fabric evidence.

**Table 15. Results of the Traceability Tests**

| Traceability test | Trials | Records tested | Successfully retrieved, n (%) | Complete records, n (%) | Correct database–Fabric links, n (%) | Correct chronological order, n (%) | Missing records, n | Duplicate records, n | Mean retrieval/reconstruction time ± SD (s) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Individual sensor-record trace | 10 | 10 | | | | Not applicable | | | |
| Device-history reconstruction | 10 sequences | 50 | | | | | | | |
| Overall | 20 trials | 60 | | | | | | | — |

The discussion should use the EMU-01 `test_sequence` as an independent reference for the expected order and values. Successful traceability requires more than finding a database row; the Device EUI, frame counter, event identity, stored value, digest, and Fabric transaction must remain correctly linked.

### 4.3.5 DoS and Flooding Resistance Test

This section presents the results of the MQTT invalid-connection flooding and invalid application-message flooding tests under normal, moderate, and high traffic conditions. Each condition consists of three five-minute runs. EMU-01 continues transmitting one legitimate deterministic reading every 15 seconds during every run.

Moderate flooding generates approximately 10 invalid requests or messages per second, or about 3,000 per five-minute run. High flooding generates approximately 50 per second, or about 15,000 per run. Across three repetitions, the expected invalid totals are approximately 9,000 for the moderate condition and 45,000 for the high condition.

Flooding is directed only at the temporary isolated test listener and test topic. The normal gateway mTLS listener is not intentionally flooded.

**Table 16. Results of the DoS or Flooding Tests**

| Test area | Traffic condition | Valid messages delivered, n (%) | Invalid traffic rejected, n (%) | Mean latency ± SD (s) | Mean server CPU (%) | Mean server memory (%) | Mean gateway CPU (%) | Mean gateway memory (%) | Service available | Unauthorized records, n | Mean recovery time ± SD (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| MQTT connection flooding | Normal | | Not applicable | | | | | | | | Not applicable |
| MQTT connection flooding | Moderate | | | | | | | | | | |
| MQTT connection flooding | High | | | | | | | | | | |
| Invalid application-message flooding | Normal | | Not applicable | | | | | | | | Not applicable |
| Invalid application-message flooding | Moderate | | | | | | | | | | |
| Invalid application-message flooding | High | | | | | | | | | | |

*Note.* Server and gateway resource utilization are separate measurement series. Service availability refers to the required local path relevant to the flooding test, including Mosquitto, ChirpStack, Node-RED, TimescaleDB, OpenBao, and the Fabric adapter where required. External Fabric availability should be described separately when it affects a particular run.

The discussion should compare legitimate delivery and latency with the normal-operation baseline. A security success requires that invalid requests are rejected, no invalid test message creates a valid telemetry/Fabric record, and the prototype continues processing legitimate EMU-01 readings without sustained service failure. If the load generator itself fails to reach the target rate, the run should be treated as invalid rather than interpreted as evidence that the server resisted the intended load.

### 4.3.6 Resilience and Recovery Test

This section presents the results of the Internet/WAN interruption and recovery test. The assessment examines whether the prototype continues receiving and storing EMU-01 telemetry while external Internet access is unavailable and whether external Fabric work recovers correctly after reconnection.

The counted experiment blocks external Internet egress from the dissertation server while preserving the local gateway-to-server LAN. The Raspberry Pi gateway, server Mosquitto, ChirpStack, Node-RED, TimescaleDB, OpenBao, and Fabric outbox therefore remain local. The Hyperledger Fabric network is external. During the interruption, Fabric commits may stop while local outbox records accumulate. The results must report this behavior accurately rather than describing the external Fabric network as a local service.

Each of the three runs contains 30 minutes of normal operation, 60 minutes of Internet interruption, and 30 minutes of recovery. At a 15-second EMU-01 interval, approximately 120 readings are expected before interruption, 240 during interruption, and 120 after reconnection. Across three runs, the expected totals are 360, 720, and 360 respectively, or approximately 1,440 readings overall.

**Table 17. Results of the Internet-Connectivity Interruption and Recovery Test**

| Test period | Total duration across three runs | Expected readings | Readings stored in database, n (%) | Missing records, n | Duplicate records, n | Local services available | Fabric work queued during period, n | Fabric work confirmed after recovery, n | Mean latency ± SD (s) | Mean recovery time ± SD (s) |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| Normal operation before interruption | 90 minutes | 360 | | | | | | | | Not applicable |
| Internet interruption | 180 minutes | 720 | | | | | | | | Not applicable |
| Recovery after reconnection | 90 minutes | 360 | | | | | | | | |
| Overall | 360 minutes | 1,440 | | | | — | | | | — |

*Note.* Local services include the gateway-to-server MQTT path, server Mosquitto, ChirpStack, Node-RED, PostgreSQL/TimescaleDB, OpenBao, and the Fabric outbox/adapter process as applicable. Hyperledger Fabric itself is external. When the external Fabric endpoint is unreachable during the interruption, queued outbox work must not be reported as a successful Fabric commit. Recovery time refers to the period from restoration of Internet connectivity until external reachability returns and retry-eligible Fabric work is reconciled to the defined normal state.

The discussion should evaluate whether the expected EMU-01 `test_sequence` values remained complete and in order, whether any duplicate application records were created by delayed or QoS 1 redelivery, and whether pending blockchain work recovered without conflicting duplicate ledger state. The result should also make clear that this experiment evaluates resilience to external Internet loss only. It does not demonstrate resilience to Raspberry Pi power failure, complete LAN failure, or failure of the local test server.

## Guidance for Final Discussion

The final discussion should connect the measured results directly to the three research problems rather than treating every technology as a separate success. For performance, explain whether the minimum testbed kept pace with the configured 15-second source interval and what resource limits were observed. For security, explain which layer made each allow-or-deny decision and whether any invalid input propagated beyond that layer. For integrity and traceability, explain how the deterministic source identity and Fabric evidence made changes or missing links observable. For resilience, explain the distinction between local telemetry continuity and delayed external blockchain confirmation.

Do not interpret an unobserved attack packet as a secure rejection, a transaction ID as a valid Fabric commit, an outbox job as a blockchain record, or server-VM CPU as Raspberry Pi CPU. These distinctions are necessary so the reported results accurately describe the final architecture that was actually tested.
