# LoRaWAN Research Test Manual

This manual contains only the Chapter 3 tests, measurements, acceptance rules, and released operator commands.

`chapters/Zacarias_Chapter3.pdf` controls **what must be tested and measured**. Verified live infrastructure controls **how the test is executed**. Stale architecture details from Chapter 3 are not used as implementation instructions.

## Rules used for every test

- Keep the raw evidence used to calculate every result.
- Keep the numerator and denominator for every percentage.
- Keep the start and end timestamps for every latency and recovery measurement.
- Report time in ms or s, bandwidth in Mbps, transaction/block size in bytes, throughput in records/s or TPS, CPU and memory in %, and counts as integers.
- Keep gateway and server resource measurements separate.
- Grafana and the research cockpit are for live observation. Final values come from the recorded run evidence.
- `PASS` means the intended condition occurred and the expected result was proven.
- `FAIL` means the intended condition occurred but the result was wrong.
- `INVALID` means the intended condition or required evidence was not achieved; retain the attempt and repeat it with a new ID.
- `BLOCKED` means a required fixture, authorization, or methodology is unavailable before the test starts.
- A code block appears in this manual only when the complete test action is currently `READY`. If a test is not ready, its measurements stay here but no placeholder code is shown.

## Test status

| Test | Required work | Current operator status |
|---|---|---|
| PRE | Full technical preflight | READY |
| P1 | Normal-operation performance | READY |
| P2 | Fabric performance and overhead | HARNESS REQUIRED |
| R1 | Internet interruption and recovery | CAPTURE READY; outage orchestrator not released |
| R2 | Fabric unavailability and reconciliation | HARNESS REQUIRED |
| A1 | Authentication and access control | CAPTURE READY; complete 90-trial orchestrator not released |
| A2 | Endorsement-policy enforcement | HARNESS REQUIRED |
| S1 | LoRaWAN replay and spoofing | CAPTURE READY; complete attack orchestrator not released |
| S2 | Application duplicate/replay | METHODOLOGY REQUIRED |
| F1 | MQTT invalid-connection flooding | CAPTURE READY; calibrated commissioning rerun required |
| F2 | Invalid application-message flooding | CAPTURE READY; calibrated commissioning rerun required |
| I1 | Application-layer alteration | HARNESS REQUIRED |
| I2 | Post-storage database tampering | HARNESS REQUIRED |
| I3 | Blockchain duplicate/overwrite | HARNESS REQUIRED |
| T1 | Individual record traceability | CAPTURE READY; complete scoring orchestrator not released |
| T2 | Five-record history reconstruction | CAPTURE READY; complete scoring orchestrator not released |

# PRE - Full technical preflight

Run this immediately before a formal test group. It checks the current recorder/tooling state, counted firmware archive, workstation/cloud/gateway timing, required sensor USB identities, database role, evidence-service readiness, gateway LTE production route, and a recent full-stack control.

```powershell
python .\test\automation\research-manual\run_test.py PRE
```

When prompted, type `EXECUTE`. Do not start counted work if PRE fails.

# P1 - Normal-operation performance

**Design**

- 3 runs.
- 30 minutes per run.
- EMU-01 sends one legitimate uplink every 15 s.
- About 120 scheduled transmissions per run.
- No intentional attack, outage, flood, or service failure.

**Measure**

- Packet-delivery rate: `unique legitimate uplinks accepted by ChirpStack / scheduled EMU-01 transmission attempts x 100`.
- End-to-end latency for each matched reading: `T_database_storage - T_sensor_transmission` when the clock/correlation gate proves that boundary is valid.
- Mean, sample SD, minimum, and maximum latency.
- System throughput: `unique legitimate readings stored / test duration`.
- Fabric transaction success rate: `valid committed / submitted x 100`.
- Gateway CPU average and maximum.
- Gateway memory average and maximum.
- Server CPU average and maximum per participating server.
- Server memory average and maximum per participating server.

**Required evidence**

EMU-01 source transmissions, ChirpStack acceptance, database rows, Fabric/outbox result, resource samples, run timestamps, and the sealed run checksum manifest.

**Operator block**

The released command runs one counted 30-minute repetition. It waits for a joined successful EMU-01 warm-up transmission before opening the formal clock, captures the closed source/ChirpStack/database window, allows bounded downstream Fabric settlement after the window closes, then fails unless the recorded source, PDR, calibrated latency, outbox, and Fabric-confirmation boundaries all validate.

```powershell
python .\test\automation\research-manual\run_test.py P1
```

When running directly, type `EXECUTE` and choose repetition `1`, `2`, or `3`; keep PowerShell alive through the entire 30-minute run, Fabric settlement (up to 420 seconds), and sealing. **For `jervis-hijo` one-shot work, do not run this foreground 30-minute command in `relai_exec`: the MCP owner can expire before the recorder finishes.** Use the tested Windows-detached operator instead: `py -3 test/automation/research-manual/p1_durable.py start --repetition 1` (choose 1, 2, or 3 as appropriate). The command immediately returns the durable run folder and PID. Check `py -3 test/automation/research-manual/p1_durable.py status` and `chapter4-results/_operator-p1-durable/<session>/operator-console.txt`; the session's `result.json` must contain a completed status and exit code before judging results. Never launch another P1 while `_recorder-active.json` exists. Preserve the terminal/operator exit code. Verify exactly 120 in-window source attempts, calibrated sensor-to-DB timing, unique ChirpStack acceptance, database correlation, and the Fabric-confirmed outbox. A run is valid only if its clean sealed run status, operator exit and post-run P1 validator all pass. If an operator session is interrupted, check recorder ownership; use `research_recorder.py recover` only once the owner is dead, preserve original `stop-errors.txt` and `run-status.txt`, and do not relabel `RECORDED_WITH_ERRORS` as a clean counted P1 repetition. The actual 2026-09-22 interrupted P1 run is recorded in `test/automation/research-manual/P1-LIVE-AUDIT-20260922.md`.

**Fabric recovery note.** The commissioned LoRaWAN-side contract remains `10.104.0.7:7051` / `peer1.hrc.local` / `hrc-channel` / `hrc-evidence` / `lorawan-gateway-evidence`. The Fabric team repaired peer1 catch-up by enabling `CORE_PEER_GOSSIP_STATE_ENABLED=true`; no LoRaWAN endpoint, TLS name, channel, chaincode, or source namespace changed. The repair is currently live-qualified but must also remain present in the Fabric deployment manifest; reapplying an older peer1 manifest without this setting can recreate stale-ledger commit-status delays.

# P2 - Fabric performance and overhead

**Design**

- Valid workloads: 1 transaction every 15 s, 1 TPS, 5 TPS, and 10 TPS.
- 5 minutes per workload.
- 3 repetitions per workload = 12 with-Fabric workload runs.
- Compare the same processing workload with and without Fabric.
- Chapter 3 does not prescribe the number of no-Fabric comparison runs. Freeze the comparison design before counted execution and do not select it after seeing results.

**Measure**

- Commit latency per transaction: `T_commit - T_submission`.
- Mean and sample SD of commit latency.
- Transaction throughput: `valid committed / duration_seconds` TPS.
- Transaction success rate: `valid committed / submitted x 100`.
- Average transaction size in bytes.
- Average block size in bytes.
- Average and maximum CPU utilization.
- Average and maximum memory utilization.
- Additional latency: `L_with_Fabric - L_without_Fabric`.
- Percentage latency increase: `(L_with_Fabric - L_without_Fabric) / L_without_Fabric x 100`.
- CPU overhead: `CPU_with_Fabric - CPU_without_Fabric`.
- Memory overhead: `Memory_with_Fabric - Memory_without_Fabric`.

**Required result**

Use only valid transactions for the performance workload and retain submission, commit, block, transaction-size, and resource evidence.

**Operator block**

Not released. The valid-record load generator and commit/block-size collector must pass together before a command is added here.

# R1 - Internet interruption and recovery

**Design**

- 3 repetitions.
- Each repetition is 30 min normal + 60 min proven external-Internet interruption + 30 min recovery.
- EMU-01 remains at the 15 s cadence for the full 120 minutes.
- The intended fault is external-Internet loss while the local system remains powered and observable.

**Measure for normal, interruption, and recovery phases separately**

- Local service availability.
- Delivery rate: `successfully received/stored legitimate readings / transmitted readings x 100`.
- Data-loss count.
- Duplicate-record count.
- Database-blockchain consistency rate.
- End-to-end latency.
- Chronological-order accuracy using sequence/frame-counter/timestamp evidence.
- Recovery time from restoration until normal external connectivity returns.
- Mean and sample SD for latency and recovery measurements where applicable.

**Required result**

Essential local monitoring continues during the interruption and normal connectivity returns without database-blockchain inconsistency. Do not report queued or pending Fabric work as a committed blockchain record.

**Operator block**

Not released. The exact external-Internet outage/restore action must be rehearsed and controlled by one complete harness first.

# R2 - Fabric unavailability and reconciliation

**Design**

1. 10 normal records reach valid confirmed Fabric state.
2. While Fabric is unavailable, create 10 additional valid records; these remain locally stored and pending, with no false commit.
3. Restore Fabric and reconcile those **same 10** pending records.

**Measure**

- Pending-record identification rate: `correctly pending outage records / 10 x 100`.
- Recovery success rate: `pending records successfully reconciled / pending records requiring reconciliation x 100`.
- Post-recovery hash-consistency rate: `matching recovered DB/Fabric hashes / recovered verified records x 100`.
- False-verification count.
- Orphan database-record count.
- Missing blockchain-record count.
- Duplicate blockchain-record count.
- Conflicting-hash count.
- Failed-reconciliation count.
- Remaining-pending count.
- Recovery time from Fabric restoration until all recoverable records reach a final state.

**Required result**

100% pending identification, 0 false verification, 100% recovery of valid pending records, 100% post-recovery hash consistency, and 0 missing or duplicate valid blockchain anchors.

**Operator block**

Not released. Query-before-resubmission, exact-ten record freezing, and same-record reconciliation must be one proven harness first.

# A1 - Authentication and access control

**Design: 90 attempts**

LoRaWAN, 10 trials each:

- Correct registered OTAA credentials -> allow.
- Registered identity with incorrect AppKey -> reject.
- Unregistered DevEUI -> reject/not activated.

MQTT, 10 trials each:

- Authorized account to allowed test topic -> accept.
- Incorrect password -> reject connection.
- Limited account to prohibited topic -> deny publish.

Fabric, 10 trials each:

- Authorized writer -> valid commit.
- Valid identity without writer permission -> reject; world state unchanged.
- Invalid/untrusted identity -> reject; world state unchanged.

**Measure**

- Authorized success rate.
- Unauthorized rejection rate.
- False-acceptance count.
- False-rejection count.
- Correct-decision rate.
- Response time by layer with mean and sample SD.
- Unauthorized state-change count.

**Required result**

0 false acceptance and 0 unauthorized state change. A LoRaWAN rejection counts only when gateway reception of the attempted request/frame is proven.

**Operator block**

Not released. The complete 9-condition x 10-trial fixture is not yet one commissioned action.

# A2 - Fabric endorsement-policy enforcement

**Design: 30 attempts**

- 10 valid transactions with required endorsement available.
- 10 controlled missing-required-endorsement attempts.
- 10 valid transactions after endorsement availability is restored.

**Measure**

- Endorsement-policy enforcement rate.
- Normal valid-transaction success rate.
- Post-restoration success rate.
- Unauthorized state-change count.
- Response time by condition.

**Required result**

100% enforcement during policy violation, 0 unauthorized state changes, and valid commits resume after restoration.

**Operator block**

Not released. A Fabric-team-approved missing-endorsement fixture and world-state pre/post proof are required first.

# S1 - LoRaWAN replay and spoofing

**Design: 40 counted attempts**

Replay:

- 10 legitimate controls.
- 10 old-frame replay attacks, each counted only after the gateway proves RF reception.

Spoofing:

- 10 genuine controls.
- 10 forged/invalid-MIC attacks, each counted only after the gateway proves RF reception.

**Measure**

- Replay-rejection rate.
- Spoofing-rejection rate.
- False-acceptance count.
- False-rejection count.
- Unauthorized-propagation rate into application/database/Fabric.
- Gateway-reception-to-decision time when the timestamps permit it.

**Required result**

All legitimate controls are processed; all received attack frames are rejected before application processing; 0 false acceptance; 0 attack-generated valid database/Fabric record.

**Operator block**

Not released. Capture, attack transmission, gateway-reception proof, and downstream absence checks must become one complete harness first.

# S2 - Application-layer duplicate/replay

Chapter 3 lists this test but does not define a standalone trial count, duration, exact injection boundary, metric formula, or acceptance rule.

**Status**

`METHODOLOGY REQUIRED`. Do not invent counted results and do not substitute I3 or ordinary database deduplication. The methodology must first define the duplicate identifier, control/attack counts, tested layer, expected downstream behavior, state-change rule, and metric numerator/denominator.

# F1 - MQTT invalid-connection flooding

**Design**

- 0 invalid connections/s, 10/s, and 50/s.
- 5 minutes per condition.
- 3 repetitions per condition = 9 load runs.
- 5-minute recovery after every run.
- Legitimate EMU-01 traffic continues at 15 s cadence.
- Flood only the isolated test listener, never the production gateway listener.

**Measure**

- Invalid-connection rejection rate.
- Legitimate-message delivery rate.
- Legitimate end-to-end latency.
- Valid-message throughput.
- Average and maximum CPU.
- Average and maximum memory.
- RX and TX bandwidth in Mbps.
- Service availability.
- Unauthorized database/Fabric record count.
- Recovery time after load stops.

**Required result**

Invalid traffic is rejected, legitimate traffic continues, no invalid request creates valid state, and no sustained service failure remains after recovery.

**Operator block**

Not released. The 0/10/50 s^-1 rejection and cleanup paths passed, but the earlier five-second pilot did not prove legitimate EMU-01 delivery inside the flood window. Re-release requires a calibrated cloud-UTC commissioning rerun long enough to include the 15-second legitimate traffic cadence.

# F2 - Invalid application-message flooding

**Design**

- 0 invalid messages/s, 10/s, and 50/s.
- 5 minutes per condition.
- 3 repetitions per condition = 9 load runs.
- 5-minute recovery after every run.
- Legitimate EMU-01 traffic continues at 15 s cadence.
- Malformed data is published only to the isolated validation test path.

**Measure**

- Invalid-message rejection rate.
- Legitimate-message delivery rate.
- Legitimate end-to-end latency.
- Valid-message throughput.
- Average and maximum CPU.
- Average and maximum memory.
- RX and TX bandwidth in Mbps.
- Service availability.
- Unauthorized database/Fabric record count.
- Recovery time after load stops.

**Required result**

Malformed test messages never become valid database/Fabric records, legitimate traffic continues, and the service returns to the normal range after recovery.

**Operator block**

Not released. The complete isolated malformed-message harness is implemented, but the commissioning rerun must first prove that its flood-window queries use the recorder-calibrated cloud UTC boundary and that legitimate EMU-01 delivery is observed inside each sufficiently long rehearsal window. The earlier five-second rehearsal proved rejection and cleanup behavior but used workstation UTC for the database window and is therefore not sufficient for release.

# I1 - Application-layer alteration

**Design: 20 attempts**

- 10 unchanged controls.
- 10 deliberately altered records after the initial experimental hash and before valid storage.

**Measure**

- Integrity-verification rate.
- Tamper-detection rate.
- False-positive count.
- False-negative count.
- Unauthorized-storage count.
- Verification time with mean and sample SD.

**Required result**

All unchanged controls match and pass; all altered records mismatch and are blocked/quarantined; 0 false negatives; 0 altered records stored/submitted as valid.

**Operator block**

Not released. The controlled post-hash/pre-storage alteration fixture must be reproducible and reversible first.

# I2 - Post-storage database tampering

**Design: 20 attempts**

- 10 unchanged stored controls with confirmed original Fabric evidence.
- 10 controlled post-storage value changes; restore each record after its trial.

**Measure**

- Integrity-verification rate.
- Tamper-detection rate.
- False-positive count.
- False-negative count.
- Unauthorized-storage/state count as applicable.
- Verification time with mean and sample SD.

**Required result**

All unchanged records match the original evidence; every modified record recomputes to a different digest using the same production canonicalization rules; 0 false negatives.

**Operator block**

Not released. A reviewed read-only current-row canonical verifier plus controlled tamper/restore fixture is required first.

# I3 - Blockchain duplicate and overwrite integrity

**Design**

- Create and read back 10 valid baseline anchors.
- Submit 10 same-ID/same-hash duplicate attempts.
- Submit 10 same-ID/different-hash overwrite attempts.

**Measure**

- Duplicate-rejection rate.
- Overwrite-rejection rate.
- Original-hash preservation rate.
- Unauthorized state-change count.

**Required result**

Duplicate creates and conflicting overwrites are rejected and every original baseline hash remains unchanged.

**Operator block**

Not released. A dedicated synthetic mutation namespace and approved submit/query helpers are required first.

# T1 - Individual record traceability

**Design**

- 10 known readings.
- Each reading is reconstructed from original source/LoRaWAN evidence through the database and its corresponding Fabric evidence.

**Required trace fields**

Trace identifier, Device EUI, LoRaWAN frame counter, source sequence, sensor value and unit, event timestamp, gateway identifier, database record identity, SHA-256 digest, Fabric transaction identifier, and commit timestamp or block reference.

**Measure**

- Trace-retrieval success rate.
- Record-completeness rate.
- Database-Fabric linkage rate.
- Missing-record count.
- Duplicate-record count.
- Individual retrieval time with mean and sample SD.

**Required result**

Complete retrieval and correct database-Fabric linkage for all tested records, with no expected record missing or duplicated.

**Operator block**

Not released. Full ten-record automatic completeness/linkage scoring must be commissioned first.

# T2 - Device-history reconstruction

**Design**

- 10 non-overlapping sequences.
- 5 consecutive readings per sequence = 50 records.
- Together with T1, traceability covers 20 trials and 60 records.

**Measure**

- Record-completeness rate.
- Database-Fabric linkage rate.
- Chronological-order accuracy.
- Missing-record count.
- Duplicate-record count.
- History reconstruction time with mean and sample SD.

**Required result**

All five designated readings in every sequence are retrieved, correctly linked, and in the original source order; no expected record is substituted with a nearby reading.

**Operator block**

Not released. Automatic 10 x 5 source-to-database-to-Fabric reconstruction/scoring must be commissioned first.

# Completion checklist

- P1: 3 valid 30-minute runs.
- P2: 12 valid with-Fabric workload runs plus the frozen no-Fabric comparison design.
- R1: 3 valid 120-minute runs with proven 30/60/30 phase boundaries.
- R2: 10 normal + 10 outage records + reconciliation of those same 10.
- A1: 90 counted attempts.
- A2: 30 counted attempts.
- S1: 40 counted attempts; every attack attempt must have proven gateway reception.
- S2: methodology must be formally resolved before counted work.
- F1/F2: 18 five-minute load runs total plus 18 five-minute recovery observations.
- I1/I2: 40 attempts total.
- I3: 10 baseline anchors + 20 mutation attempts.
- T1/T2: 20 trials covering 60 records.
- Every final reported value must be reproducible from retained raw evidence.

