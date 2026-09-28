# Zacarias Chapter 3 — Authoritative Research Test and Metrics Source of Truth

## Authority and scope

This document is the testing authority derived from `chapters/Zacarias_Chapter3.pdf` (74 PDF pages).

**Use the new chapter as authoritative for the research questions, experimental conditions, trial/run counts, durations, metrics, evidence requirements, analysis rules, and stated success/security criteria only.**

Do **not** use its architecture diagrams, host placement, service placement, topology, deployment descriptions, component ownership, paths, addresses, or other implementation prose as current infrastructure truth. Those descriptions may be stale. The commissioned system must be tested as it actually exists, using verified live configuration and current deployment documentation, while preserving the experimental condition and measurement intent defined here.

When sources disagree:

1. This document controls **what formal research test is required and what must be measured**.
2. The new `Zacarias_Chapter3.pdf` is the provenance source for those requirements.
3. Verified live state and current deployment/runbooks control **how the commissioned system implements the test**.
4. Older Chapter 3/4/5 drafts and obsolete architecture prose do not override either of the above.

A test must not be silently changed because the current architecture differs from the dissertation prose. Adapt the injection/observation method to the live system while keeping the intended independent variable, observation boundary, metric, and evidence intact.

## Formal experiment inventory

| ID | Formal experiment | Required design from Zacarias Chapter 3 | Primary chapter pages |
|---|---|---|---|
| P1 | End-to-end normal-operation performance | 3 runs × 30 min; legitimate sensor every 15 s; ≈120 transmissions/run; no attacks/outages/failures | PDF pp. 17–21 |
| P2 | Hyperledger Fabric performance and overhead | 4 workloads: 1 tx/15 s, 1 TPS, 5 TPS, 10 TPS; 5 min/condition; 3 repetitions = 12 workload runs; compare processing with vs without Fabric | PDF pp. 21–27 |
| R1 | Internet-connectivity interruption and recovery | 3 × 2-hour runs: 30 min normal + 60 min external-Internet interruption + 30 min recovery; sensor remains at 15 s cadence | PDF pp. 31–34 |
| R2 | Database–blockchain consistency and Fabric recovery | 10 normal records; 10 additional records while Fabric unavailable; reconcile the same 10 pending records after restoration | PDF pp. 35–41 |
| A1 | Authentication and access control | 9 conditions × 10 trials = 90 attempts: 3 LoRaWAN + 3 MQTT + 3 Fabric identity/authorization conditions | PDF pp. 43–46 |
| A2 | Fabric endorsement-policy enforcement | 10 normal valid transactions + 10 policy-violation attempts + 10 post-restoration valid transactions = 30 attempts | PDF pp. 46–50 |
| S1 | LoRaWAN replay and spoofing | Replay: 10 legitimate controls + 10 **gateway-received** replay attempts. Spoofing: 10 genuine controls + 10 **gateway-received** forged/invalid-MIC attempts. Total = 40 counted attempts | PDF pp. 50–55 |
| S2 | Application-layer duplicate/replay | **Listed in Table 3.4 as a proposed test, but the chapter provides no standalone detailed procedure, trial count, duration, metric formula, or acceptance rule for it.** Treat as an unresolved methodology requirement; do not silently omit it and do not invent counted results. | PDF pp. 28–30 |
| F1 | MQTT connection flooding | normal 0/s, moderate 10 invalid connections/s, high 50/s; 5 min/condition × 3 repetitions; 5-min recovery after every run | PDF pp. 55–61 |
| F2 | Invalid application-message flooding | normal 0/s, moderate 10 invalid messages/s, high 50/s; 5 min/condition × 3 repetitions; 5-min recovery after every run | PDF pp. 55–61 |
| I1 | Application-layer data alteration | 10 unchanged controls + 10 deliberately altered records | PDF pp. 61–65 |
| I2 | Post-storage database tampering | 10 unchanged controls + 10 deliberately modified stored records | PDF pp. 62–65 |
| I3 | Blockchain duplicate / unauthorized overwrite | Establish 10 valid baseline anchors; submit the same 10 trace IDs with same hashes (duplicate attempts); submit the same 10 trace IDs with different hashes (overwrite attempts) | PDF pp. 66–68 |
| T1 | Individual sensor-record traceability | 10 individual-record trace trials | PDF pp. 69–72 |
| T2 | Device-history reconstruction | 10 sequences × 5 consecutive readings = 50 records | PDF pp. 69–73 |

Traceability total: **20 trials covering 60 records**. Flooding total: **18 five-minute load runs** across two flood types, with a five-minute recovery observation after each run.

### Chapter-internal consistency notes

The new chapter contains a few internal inconsistencies that must be handled explicitly instead of guessed:

- **Application-layer duplicate/replay:** Table 3.4 lists this as a proposed replay/spoofing test and the surrounding prose says replay/spoofing assessment includes duplicate records, but the detailed replay section and Table 3.8 define only LoRaWAN replay and invalid-MIC spoofing. Because no count, duration, exact injection method, metric formula, or success threshold is supplied for the application-layer duplicate/replay item, it remains a **methodology-resolution blocker** for that specific test. It must either be formally specified by the research team/adviser or explicitly removed from the methodology before final completion. Existing duplicate detection in I3 or database deduplication must not be silently reported as this missing test unless the methodology is formally amended.
- **Integrity-count wording:** the introduction to Section 3.2.4.2.3 says the integrity testing yields “40 total test attempts,” which matches the detailed I1/I2 design (10 unchanged + 10 altered at application layer, plus 10 unchanged + 10 tampered post-storage). The later I3 blockchain-layer procedure is an additional design using 10 already-valid baseline anchors followed by 10 duplicate and 10 conflicting-overwrite submissions. Therefore report I1/I2 as 40 counted application/post-storage attempts and report I3 separately; do not collapse them into an unsupported single “40 total including I3,” and do not invent a grand-total count without stating whether the 10 I3 baseline anchors are fixtures or counted controls.
- **R1 blockchain behavior:** Chapter 3 assumes blockchain verification can continue locally during external-Internet loss because of its older deployment model. In the commissioned system Fabric is an external dependency. Preserve the **R1 independent variable and metrics** (external-Internet interruption, local monitoring continuity, loss/duplication/order/latency/recovery) but report actual Fabric state truthfully; queued/PENDING work is not a Fabric commit.
- **P2 no-Fabric comparison count:** the chapter fixes the Fabric workload runs at four rates × three five-minute repetitions, but it does not state how many matching “without Fabric” comparison runs are required for the overhead equations. Before P2 counted testing, freeze and document the comparison design (which workload(s), duration, repetitions, warm-up/stabilization, and pairing method) so additional-latency/CPU/memory overhead cannot be selected post hoc.
- **Synthetic-versus-physical test data:** the chapter explicitly calls for synthetic/known test readings in authentication, LoRaWAN replay, integrity, and traceability procedures, while the current project sensor manuals deliberately use real physical Agriculture Kit readings. This is a methodology divergence, not an architecture detail. Before those counted tests, formally choose and document the data provenance for each experiment. Do not label real physical readings “synthetic,” and do not replace a required known-value/synthetic fixture with uncontrolled physical values unless the methodology is explicitly amended while preserving the same security condition and identifiers.

## Measurement rules and units

Use raw timestamps/counters in their native precision and preserve them in evidence. Report human-facing metrics with explicit units; never show an unlabeled number.

Recommended reporting normalization, without changing the chapter definition:

- latency, response, verification, reconciliation, retrieval, and recovery time: retain raw timestamps; calculate in seconds and report milliseconds where useful;
- CPU utilization: percent of available processing capacity, with average and maximum;
- memory: used bytes and total bytes plus utilization percent; dashboards may show MiB/GiB used / total;
- network bandwidth: retain RX/TX byte counters and derive rate in Mbps over the measurement interval;
- throughput: records/s for system processing and transactions/s (TPS) for Fabric; records/min may additionally be shown for the slow 15-second sensor baseline;
- transaction/block size: bytes, with KiB only as a display conversion;
- rates: percent with numerator and denominator retained;
- counts: integer counts, never converted to percentages without preserving the denominator.

### P1 — End-to-end normal-operation metrics

Required measures:

- **Packet-delivery rate (PDR)** = `N_received_by_ChirpStack / N_transmitted_by_sensor × 100`.
- **End-to-end latency per reading** = `T_database_storage - T_sensor_transmission`.
- **Mean end-to-end latency** across successfully delivered readings.
- **System throughput** = `N_readings_successfully_processed_and_stored / test_duration`.
- **Fabric transaction success rate (TSR)** = `N_valid_committed / N_submitted × 100`.
- **Average CPU utilization** and **maximum CPU utilization**.
- **Memory utilization per observation** = `memory_used / memory_total × 100`.
- **Average memory utilization** and **maximum memory utilization**.

Evidence must permit correlation among the sensor transmission, ChirpStack acceptance, database row, and Fabric result. A transaction ID alone is not proof of a successful commit.

Timing caveat: sensor→database latency is valid only when the source timestamp and database clock are demonstrably correlated. If that timing boundary cannot be proven for a run, do not invent the Chapter 3 metric; classify the timing evidence as unavailable/invalid and repair the clock/correlation gate before formal measurement.

### P2 — Hyperledger Fabric performance and overhead metrics

For each workload (1/15 s, 1 TPS, 5 TPS, 10 TPS), collect:

- **Commit latency per transaction** = `T_commit - T_submission`.
- **Mean commit latency**.
- **Transaction throughput** = `N_committed / duration_seconds` TPS.
- **Transaction success rate** = `N_committed / N_submitted × 100`.
- **Average transaction size** in bytes.
- **Average block size** in bytes.
- **Average / maximum CPU utilization**.
- **Average / maximum memory utilization**.

For the same processing workload with and without Fabric submission, calculate. **The chapter does not specify the count/repetition structure of the no-Fabric comparison, so that comparison design must be frozen before counted P2 execution and retained in run metadata:**

- **Additional latency** = `L_with_Fabric - L_without_Fabric`.
- **Percentage latency increase** = `(L_with_Fabric - L_without_Fabric) / L_without_Fabric × 100`.
- **CPU overhead** = `CPU_with_Fabric - CPU_without_Fabric`.
- **Memory overhead** = `Memory_with_Fabric - Memory_without_Fabric`.

Only valid transactions are used for the performance load. Invalid/rejection traffic belongs to the security tests, not P2.

## Resilience tests

### R1 — External-Internet interruption and recovery

This is a formal test in the new chapter and is **not equivalent to Fabric-only endpoint isolation**.

Each run:

- 30 min normal operation ≈120 readings;
- 60 min external-Internet interruption ≈240 readings;
- 30 min recovery ≈120 readings;
- repeat the complete two-hour run 3 times.

The intended fault is loss of the system's **external Internet connection while local monitoring functions remain powered and operational**. The exact live implementation must isolate the WAN dependency without accidentally injecting an unrelated failure.

Required measures, separately for normal/interruption/recovery periods:

- local service availability;
- data-delivery rate = transmitted readings successfully received/stored ÷ transmitted readings × 100;
- data-loss count;
- duplicate-record count;
- database–blockchain consistency rate;
- end-to-end latency;
- recovery time from restoration until external connectivity returns to normal;
- chronological accuracy using timestamps/frame counters.

Use frequencies/percentages for availability, delivery, missing/duplicate records, chronology, and database–blockchain consistency. Report mean and standard deviation for latency and recovery time.

Research success criterion: essential local monitoring continues through the interruption and normal connectivity returns without database–blockchain inconsistency. Compare loss/duplication/linkage behavior against the normal baseline so ordinary LoRaWAN loss is not falsely attributed to the outage.

### R2 — Fabric unavailability, database–blockchain consistency, and reconciliation

This is a **separate** resilience test from R1.

Stages:

1. Normal control: 10 valid readings should move `PENDING → VERIFIED` only after confirmed Fabric commitment.
2. Fabric unavailable: 10 additional valid readings remain locally stored and **PENDING**; no fabricated Fabric transaction ID and no false `VERIFIED` state.
3. Fabric restored: reconcile those same 10 pending records; do not create new recovery test records.

For every record retain at least trace ID, database-storage result, initial/final blockchain state, submission result, Fabric transaction ID when applicable, original hash, recomputed database hash, blockchain hash, and timestamps.

Metrics:

- pending-record identification rate = correctly PENDING outage records ÷ outage records × 100;
- recovery success rate = pending records successfully reconciled/VERIFIED ÷ pending records requiring reconciliation × 100;
- post-recovery hash-consistency rate = recovered records with matching DB/Fabric hashes ÷ recovered records verified × 100;
- false-verification count;
- orphaned database record count;
- missing blockchain record count;
- duplicate blockchain record count;
- conflicting-hash count;
- failed-reconciliation count;
- records remaining PENDING after recovery;
- recovery time from Fabric restoration until every recoverable pending record is VERIFIED or classified FAILED;
- optionally mean per-record reconciliation time.

Required criteria stated by the chapter:

- 100% pending-record identification;
- zero false verifications;
- 100% recovery success for valid pending records;
- 100% post-recovery hash consistency;
- zero missing or duplicate valid blockchain integrity anchors.

## Authentication and authorization

### A1 — 90 authentication/access-control attempts

LoRaWAN, 10 trials each:

1. registered device + correct OTAA credentials → allow/join/uplink;
2. registered DevEUI + incorrect AppKey → reject;
3. unregistered DevEUI → reject/not activated.

MQTT, 10 trials each:

1. authorized account + allowed topic → accept;
2. incorrect password → reject connection;
3. valid limited account + prohibited topic → authenticate as applicable but deny publish.

Fabric identity/authorization, 10 trials each:

1. authorized writer → endorse/commit;
2. valid identity without writer permission → reject, unchanged world state;
3. invalid/untrusted identity → reject, unchanged world state.

Metrics:

- authorized success rate;
- unauthorized rejection rate;
- false-acceptance count;
- false-rejection count;
- correct-decision rate;
- response time per layer;
- unauthorized state-change count.

Response boundaries:

- LoRaWAN: JoinRequest → JoinAccept or final rejection decision;
- MQTT: connection/publish request → broker response;
- Fabric: transaction submission → commitment or rejection.

Use frequencies/percentages for decisions and mean + standard deviation for response time.

Required security criterion: **zero false acceptance and zero unauthorized state change**.

### A2 — Fabric endorsement-policy enforcement

Three conditions, 10 attempts each:

1. required endorsers available; valid transactions should commit;
2. required endorsement missing; policy-violating transaction must not create valid world-state change;
3. required endorser restored; valid transactions should again commit.

Metrics:

- endorsement-policy enforcement rate;
- valid transaction success rate;
- post-restoration recovery transaction success rate;
- unauthorized state-change count.

Required criterion: **100% policy enforcement and zero unauthorized state changes** during the violation condition; valid transactions should resume when required endorsement is available.

## Replay and spoofing

### S1 — LoRaWAN replay and spoofing

A counted attack attempt is valid only after the gateway proves RF reception. A transmit command by the attack node is not sufficient.

Replay: 10 legitimate packets + 10 corresponding received replays using an old frame counter. The legitimate device must advance its counter before the old captured frame is replayed.

Spoofing: 10 genuine packets + 10 received forged packets using the legitimate address identity but an invalid MIC/no legitimate session key.

Required measures:

- replay-rejection rate;
- spoofing-rejection rate;
- false-acceptance count;
- false-rejection count;
- unauthorized-propagation rate into MQTT/Node-RED/database/Fabric;
- processing time from gateway reception to ChirpStack accept/reject when timestamps permit.

Required criterion: **zero false acceptance and zero unauthorized propagation**; all legitimate controls should be processed.

### S2 — Application-layer duplicate/replay methodology gap

Table 3.4 separately proposes resubmitting a previously processed or duplicate sensor record at the application layer. The detailed methodology never specifies its trial count, repetition count, timing, exact duplicate identifier, expected downstream decision, or analysis formula. Until that ambiguity is formally resolved, classify S2 as **BLOCKED_BY_METHODOLOGY** rather than PASS/FAIL/INVALID. Preserve any available duplicate-prevention evidence, but do not promote opportunistic deduplication observations into counted S2 research data.

At minimum, a later formal specification must define before execution: the canonical record/identifier to duplicate, how many control and duplicate trials are required, which layer must demonstrably receive the duplicate, whether rejection or idempotent recognition is expected, which database/Fabric state must remain unchanged, the timing boundary if a decision-time metric is required, and the numerator/denominator for any duplicate-rejection or unauthorized-propagation rate.

## Flooding / DoS

Run two independent flood types:

1. MQTT invalid-connection flooding;
2. invalid application-message flooding.

For each: normal `0/s`, moderate `10/s`, high `50/s`; 5 minutes each; 3 repetitions; 5-minute recovery observation after every run. Legitimate sensor traffic continues every 15 seconds (≈20 legitimate readings per five-minute window).

A short pilot may adjust a rate only if the proposed rate causes immediate failure or no measurable resource effect. **After the pilot, freeze the selected moderate/high rates for all repetitions.**

Required measures for every run:

- invalid-traffic rejection rate;
- legitimate-message delivery rate;
- legitimate end-to-end latency;
- valid-message throughput;
- average and maximum CPU utilization;
- average and maximum memory utilization;
- network RX/TX bandwidth;
- service availability;
- unauthorized database/Fabric record count;
- recovery time from flood stop until latency/resource behavior returns to the predefined normal range.

Report mean + standard deviation for latency, throughput, CPU, memory, bandwidth, and recovery time; frequencies/percentages for delivery, rejection, availability, and unauthorized records.

Required security behavior: invalid traffic is rejected, no invalid message becomes a valid DB/Fabric record, legitimate traffic continues, and there is no sustained service failure after recovery. A service crash, unauthorized record, or sustained legitimate-processing failure is a flooding-related security failure.

## Data integrity

### I1 — Application-layer alteration

10 unchanged controls + 10 deliberately altered records after the initial hash but before valid storage.

Expected: unchanged hashes match and pass; altered hashes mismatch and the altered record is blocked/quarantined, not stored/submitted as valid.

### I2 — Post-storage database tampering

10 unchanged stored controls + 10 controlled post-storage value changes after the original hash has been committed.

Expected: unchanged DB hash matches Fabric; each modified DB record recomputes to a different hash and triggers integrity detection.

I1/I2 metrics:

- integrity-verification rate;
- tamper-detection rate;
- false-positive count;
- false-negative count;
- unauthorized-storage count;
- verification time.

Use frequencies/percentages for decisions and mean + standard deviation for verification time.

Required criterion: **zero false negatives and zero unauthorized storage**; all unchanged records match, all deliberately altered records mismatch.

### I3 — Blockchain duplicate / overwrite integrity

Create 10 valid, confirmed baseline integrity anchors with unique `trace_id` values. Then:

- duplicate condition: resubmit each of the 10 using the same `trace_id` and same hash;
- overwrite condition: resubmit each of the same 10 `trace_id` values with a deliberately different hash using an otherwise authorized identity.

After every attempt, query world state and prove the original hash remains unchanged.

Metrics:

- duplicate-rejection rate;
- overwrite-rejection rate;
- original-hash preservation rate;
- unauthorized state-change count.

Expected behavior: duplicate creates are rejected, conflicting overwrites are rejected, and each original integrity anchor remains unchanged.

## Traceability

### T1 — Individual record trace

10 known readings. Each trial must reconstruct the reading from its original LoRaWAN/application evidence through the database record and corresponding Fabric evidence.

### T2 — Device-history reconstruction

10 non-overlapping sequences of 5 consecutive readings each. Reconstruct all five in the correct order and link each to its blockchain hash/transaction.

Required trace fields include at least:

- trace identifier;
- Device EUI;
- LoRaWAN frame counter;
- sensor type/value/unit;
- event timestamp;
- gateway identifier;
- database record identifier;
- SHA-256 hash;
- Fabric transaction identifier;
- Fabric commit timestamp or block reference.

Metrics:

- trace-retrieval success rate;
- record-completeness rate;
- database–blockchain linkage rate;
- chronological-order accuracy;
- missing-record count;
- duplicate-record count;
- individual trace-retrieval time;
- device-history reconstruction time.

Use frequencies/percentages for retrieval/completeness/linkage/order and counts; mean + standard deviation for retrieval/reconstruction time.

Required criterion: complete retrieval and correct linkage of all tested records; no expected record missing, duplicated, or placed in the wrong order.

## Universal evidence and classification rules

For every formal run/trial retain enough raw evidence to answer:

1. What exact experimental condition was intentionally created?
2. Was the condition proven to have reached the component/layer being tested?
3. What result was expected before the test?
4. What actually happened?
5. Which raw log/CSV/database/Fabric record proves it?
6. Which numerator and denominator produced every reported rate?
7. Which timestamps define every reported latency/recovery interval?

Classification:

- **PASS** — valid condition, expected behavior, complete evidence;
- **FAIL** — valid condition, unexpected behavior; retain it as research data;
- **INVALID** — intended condition or required evidence was not achieved; retain and rerun under a new ID;
- **BLOCKED** — an explicitly required external fixture/authorization is unavailable before the test begins.

Never delete failed/invalid attempts to improve results. Screenshots are supporting evidence only; raw logs, counters, exports, hashes, and transaction evidence are authoritative.

## Audit of current project manuals against the new chapter

The existing test track already covers much of the new methodology, but the following mismatches must be corrected before the affected counted test is executed:

| Area | Current project state | Required action |
|---|---|---|
| P1 baseline | Recorder boundary corrected in source | `summarize-run.py` now derives formal PDR from unique accepted target-device ChirpStack `deduplication_id`s across both HA ChirpStack logs divided by captured scheduled `SENSOR_TX` attempts; a scheduled source-side send failure remains in the denominator. Exact source→DB delivery remains separate. Fresh connected validation is still required; the source↔DB timing gate remains required for true sensor→DB latency. |
| P2 Fabric performance/overhead | Formal procedure written | Use `execution/02a-fabric-performance-overhead.md`; remaining work is reproducible load generation, commit/block-size capture, and rehearsal against the commissioned Fabric path. |
| R1 Internet interruption | Formal procedure written | Use `execution/08a-internet-interruption-recovery.md`; rehearse and freeze the exact external-Internet injection method against live topology. It cannot be run while the sensor/gateway are intentionally offline. |
| R2 Fabric consistency/recovery | Formal procedure written | Use `execution/08b-fabric-consistency-reconciliation.md`; retain the same ten pending records and query-before-resubmission evidence. Rehearse the Fabric-unavailability fixture before counted testing. |
| A1 authentication | Substantially aligned | Keep 90 attempts and response/state-change metrics. |
| A2 endorsement policy | Formal procedure written | Use `execution/03a-fabric-endorsement-policy.md`; a Fabric-team-approved controlled missing-endorsement fixture is still required before counted testing. |
| S1 replay/spoofing | Substantially aligned | Keep gateway-reception validity gate. |
| S2 application-layer duplicate/replay | Chapter-internal methodology gap | Keep explicitly `BLOCKED_BY_METHODOLOGY` until the methodology supplies a count, injection procedure, expected decision, metrics, and pass rule; do not substitute I3 or ordinary DB deduplication silently. |
| F1/F2 flooding | Substantially aligned | Keep 18 runs, fixed rates after pilot, explicit bandwidth + recovery metrics. |
| I1/I2 integrity | Substantially aligned | Keep 40 application/post-storage attempts. |
| I3 blockchain duplicate/overwrite | Formal procedure written | Use `execution/05a-blockchain-duplicate-overwrite.md`; rehearse the dedicated fixture namespace and ledger-query evidence path before counted testing. |
| T1/T2 traceability | Substantially aligned | Keep 20 trials / 60 records and complete-linkage criteria. |

Until the affected execution manuals are reconciled, **this file supersedes their conflicting test counts, conditions, and metric requirements**. It does not supersede current live infrastructure details.

## Recorder / observability implications

The research recorder already captures much of the required raw material: source transmissions, gateway and ChirpStack evidence, database exports, Fabric outbox state, service logs, CPU/memory, and network counters. Before formal testing, verify or add explicit derivations/fixtures for the newly authoritative gaps:

- Fabric workload generator and 1/15 s, 1, 5, 10 TPS labels;
- Fabric submission/commit timestamps and valid-commit status;
- transaction size and block size;
- with-vs-without-Fabric latency/CPU/memory comparison;
- Internet-interruption phase markers and connectivity-state proof;
- explicit PENDING/VERIFIED/FAILED reconciliation evidence and per-record hashes;
- endorsement-policy violation/recovery evidence;
- blockchain duplicate/overwrite attempts and original-hash preservation;
- an explicit S2 application-layer duplicate/replay fixture and summary schema **only after** its methodology is formally resolved;
- network bandwidth as RX/TX raw counters plus derived Mbps;
- metric numerator/denominator columns in every summary so percentages remain auditable;
- the formal P1 PDR extractor is implemented in `summarize-run.py`: unique accepted target-device `deduplication_id`s across both HA ChirpStack logs / captured scheduled `SENSOR_TX` attempts; a scheduled source-side send failure remains in the denominator. It withholds missing or impossible observation boundaries rather than normalizing them; validate it on a fresh connected counted run before final Chapter IV use. The exact source→database percentage remains database delivery/correlation only.

Grafana/testing-monitor panels are observation aids. Formal results must be derived from sealed raw evidence and reproducible calculations, not copied visually from a dashboard.
