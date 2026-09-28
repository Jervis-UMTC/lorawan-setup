# Research Automation — Safe Operator Workflow, Formal Matrix, Metrics and Sealed Evidence

Companion to [technology guide 19](19-research-recorder-and-test-automation.md). The researcher must be able to tell apart (a) a **successful code-only/synthetic rehearsal**, (b) a **real non-counted physical rehearsal**, (c) a **released READY formal operator interface**, and (d) a **completed, valid counted Chapter IV trial**. They are not synonyms. The requirements below come from the current Zacarias Chapter 3 authority; current system implementation and live tests decide how each experiment is performed. This Markdown may become a fully printed appendix of the comprehensive Word document.

## 1. Locate the right Windows workstation and artifacts

Windows PowerShell commands below assume cwd is the parent directory of `lorawan-network-server-gateway`. The actual Python entry points are:

~~~text
test/automation/research-manual/run_test.py
test/automation/research-manual/ensure_ready.py
test/automation/research-recorder/research_recorder.py
test/automation/research-recorder/verify-run-reproducibility.py
test/automation/research-recorder/summarize-run.py
test/automation/research-recorder/summarize-study.py
test/automation/research-recorder/research_cockpit.py
test/automation/research-recorder/sec02_replay.py
~~~

A restricted recorder SSH key (`%USERPROFILE%\.ssh\id_ed25519_research_recorder`) must be **forced-command only**, not an unrecorded administrator shell. At the 2026-09-21 08:09 UTC read-only checkpoint, ULC-01's **deployed** wrapper reported `research-recorder-server-v10`, ULC-02 and ULC-03 reported `research-recorder-server-v8`, and Gateway-01 reported `research-recorder-gateway-v3`. Source v7/v5 notes are historical. Determine required verb compatibility per host instead of asserting the whole fleet runs one wrapper version. Install `pyserial==3.5` from the project's pinned requirements file if needed; do not weaken workstation PowerShell policy or use an old open-shell SSH key.

**Three different authorities:**
1. `test/ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md`: **experiment conditions/counts/measurements**;
2. verified live config/deployment: **machine/service method**;
3. immutable `chapter4-results/<group>/<run-id>/`: **what actually occurred in that trial**.

Grafana and the separate research cockpit `http://127.0.0.1:8765/` are operational observation, **not** substitute trial truth.

## 2. One test at a time; exact readiness semantics

At generated UTC **2026-09-21T06:38:17Z**, the repository's `CURRENT-READINESS.md` reported technical gate PASS, LTE invariant PASS, live PRE PASS, recorder CLEAN, archived counted firmware PASS. **Only PRE and P1 were released READY**. The newer same-day `CONTINUATION.md` reports real non-counted S1 physical replay/spoof **2/2 received and not accepted**, F1/F2 bounded real cloud load rehearsals and R2 blocked by an undeployed restricted helper; **none of these is a formal counted trial or READY release**. Read fresh generated status again before actual work; do not present an old snapshot as live “today”.

Status meanings:
- `READY`: complete approved one-block operator action, **still requires its current live gates**.
- `CAPTURE_READY`: capture exists; full experiment action/proof unfinished.
- `HARNESS_REQUIRED`: a required actor/orchestrator or live acceptance absent.
- `METHODOLOGY_REQUIRED`: Chapter 3 itself lacks a formally defined experiment.

From **Windows PowerShell**:

~~~powershell
$Root = '.\lorawan-network-server-gateway'
$R = "$Root\test\automation\research-recorder\research_recorder.py"
$Runner = "$Root\test\automation\research-manual\run_test.py"
Get-Content "$Root\test\automation\research-manual\CURRENT-READINESS.md"
Get-Content "$Root\test\automation\research-manual\OVERSIGHT-STATUS.md"
python $R status
python $Runner --help
~~~

`--help` proves a command interface exists, **not readiness nor test success**. For full real technical gate, use the reviewed `ensure_ready.py` according to its actual `--help` and protect other running recorder sessions; `--skip-live-pre` can only label its technical gate SKIPPED, never PASS. If run is interrupted and lock/active state exists, use `python $R status` and `python $R recover` only after determining no owned child process is still live; **do not delete** `_recorder-active.json` or lock to clear the screen.

**Released PRE command, from repository root (Windows):**

~~~powershell
python .\test\automation\research-manual\run_test.py PRE
~~~

**Released P1 command, from repository root (Windows), only after PRE/profile/clock gate and a current READY result:**

~~~powershell
python .\test\automation\research-manual\run_test.py P1
~~~

The two blocks above are **the only** published formal operator actions at this checkpoint. Do not paste `run_test.py S1` or `run_test.py F2` as though its status were READY. Non-counted operator harness commissioning is governed separately and may be allowed by its own safety/fixture gate.

## 3. Formal Chapter III test matrix — preserve actual design

| ID | Required conditions and counted scope |
|---|---|
| P1 | 3 × 30 min, legitimate EMU uplink every 15 s (about 120 attempts per run), no deliberate outage/attack |
| P2 | Four loads: 1 transaction / 15 s, 1 TPS, 5 TPS, 10 TPS; 5 min per load ×3 repetitions =12 Fabric workload runs; **pre-freeze** matched no-Fabric comparison design |
| R1 | 3 × 2 h: 30 min normal + 60 min **external Internet** outage + 30 min recovery, real 15 s source cadence |
| R2 | 10 normal controls, 10 *same identified new records* while Fabric isolated, then reconcile those 10; R2 is **not** R1 |
| A1 | 9 conditions ×10 =90 LoRaWAN/MQTT/Fabric authentication/authorization attempts |
| A2 | 10 valid +10 missing-endorsement-policy violation +10 valid after restoration |
| S1 | 10 genuine replay controls,10 **gateway-received** exact-old-frame replays,10 genuine spoof controls,10 **gateway-received** forged/invalid-MIC attacks =40 |
| S2 | Application replay/duplicate named in table but missing count/procedure/metric/acceptance; **methodology blocked** until adviser/research plan resolves it |
| F1,F2 | Each 0,10,50 invalid attempts/s; 5 min ×3 repeats per rate, **5 min recovery after each run** (18 total load runs) |
| I1,I2 | Each 10 unchanged and10 altered records; 40 combined application/post-storage attempts |
| I3 | Establish10 valid baseline anchors, submit10 same-ID same-hash duplicates and10 same-ID conflicting-hash overwrites; report baseline vs attacks |
| T1 | 10 individual-record traceability trials |
| T2 | 10 sequences ×5 consecutive readings =50 records; T1/T2 total20 trials covering60 records |

A shorter 30-second real F1/F2 rehearsal is **not** the formal 300-second ×3-repetition matrix. S1 2/2 physical rehearsal is **not** the 40-attempt protocol. R2 private Fabric endpoint isolation must affect *only* the adapter's governed external path; no permanent firewall or broker changes, and its target helper deployment must be proven before a trial.

## 4. Timing, denominators and units

Clock gate: source `SENSOR_TX` is timestamped at Windows capture; database/ChirpStack/ULC use server UTC. Recorder v9 calibrates workstation-to-ULC-01 before/after a formal window and fails if drift exceeds **0.100 s**. Cloud inter-host midpoint probes must agree within **0.250 s**; preserve actual calibration data (a large fixed workstation offset is acceptable only when calibrated and stable). Do not “fix” raw timestamps in `chapter4-results` after collection.

| Metric | Exact meaning and output unit |
|---|---|
| Formal PDR | **Unique legitimate ChirpStack-accepted uplinks ÷ captured scheduled SENSOR_TX source attempts ×100%**; preserve numerator, denominator and eligible run window |
| Source→DB delivery | byte-exact `raw_data` matches ÷ eligible comparable source attempts ×100%; **different numerator from PDR** |
| Sensor→DB latency | cloud-UTC DB storage time minus **clock-calibrated sensor transmission time**; seconds or ms with unit; invalid if clock gate fails |
| App→DB delay | `received_at - time` as source-defined event time, shown ms; not RF propagation and not necessarily Fabric latency |
| System throughput | successfully processed/stored readings ÷ measured seconds = records/s |
| Fabric success rate | valid authoritative **committed** transactions ÷ submitted transactions ×100%; proposal ack or TXID alone is not commit |
| Fabric commit latency | authoritative commit time minus submission time, ms |
| CPU | used processing share %, preserve average/max and host/container capacity context |
| RAM | used MiB / total MiB **plus** %, average/max over sampled interval |
| Network | RX/TX byte-counter deltas ÷ elapsed seconds ×8 /1,000,000 = Mbps; never raw “%” without a capacity |
| RF | RSSI dBm, SNR dB, frequency Hz/MHz, SF and bandwidth Hz/kHz with labels |
| Delivery/consistency | % with exact numerator/denominator; duplicates/loss counts separately |
| Transaction/block size | bytes or explicitly converted KiB |
| Traceability | fraction meeting all required source→DB→Fabric matches; keep IDs/hashes/elapsed times |

Unbounded duplicate MQTT QoS 1 observations with the **same gateway uplink ID** are transport redelivery, not extra radio attempts. Same PHY SHA-256 with a **new uplink ID** is an RF repeat candidate; source frame-counter/test-sequence duplication is a separate downstream anomaly. Matching only by approximate timestamp is never byte-exact PDR/delivery proof. Do not hide missing streams by computing percent over remaining successful rows.

## 5. Normal recorder workflow without a second owner

Before a released counted test, positively identify EMU/SEC COM ports, accepted 15-second EMU firmware image and SEC parked state, gateway LTE-only production route, full ready/clock gate, current PostgreSQL/Fabric/evidence roles and no active recorder process. Keep the foreground recorder session open. Mark deliberate reset, cable and fault times using `python $R mark --message '<SANITIZED_ACTION>'`, and pause/resume USB ownership only for the relevant device using `python $R serial-pause --device emu` / `serial-resume --device emu` (or `sec`).

Normal Ctrl+C triggers finalization: stop collector processes, export exact-window DB and service evidence, calculate derived metrics, hash the entire manifest and make raw files read-only. The recorder's terminal state `RECORDED_UNCLASSIFIED` does **not** constitute research PASS. Assign PASS/FAIL/INVALID/BLOCKED after observing the evidence against the frozen acceptance criteria.

Typical run root:

~~~text
chapter4-results/<group>/<run-id>/
  raw/       original serial/gateway/ULC captures, service logs, SQL exports
  metadata/  run-meta.json, evidence-status-start/end, SHA256SUMS.csv
  derived/   run-summary.json, run-summary.csv, trial statistics
~~~

Use unique run IDs, keep failed attempts/invalid runs, never modify raw files or reorder source timestamps. A no-serial `--skip-serial` smoke cannot produce a valid PDR denominator or count as a formal P1/R1 sensor trial.

## 6. Verify a sealed run without touching originals

From **the repository root**, replace the placeholder with a real fully finalized path:

~~~powershell
python .\test\automation\research-recorder\verify-run-reproducibility.py .\chapter4-results\smoke\RUN_ID
~~~

The checker validates manifest path safety, file byte lengths and SHA-256, all raw files sealed, necessary derived/meta files, and runs summarizer **twice in a temporary copy**. JSON must match except relocated run_dir and CSV bytes match exactly. This proves deterministic recomputation of **recorded inputs**, not statistical repeatability of physical RF or a trial method that was never commissioned.

The 2026-09-18 historical P1 rehearsal reported 62 sealed files checked and 4/4 source-vs-ChirpStack events, but it was **non-counted**. More recent S1/F1/F2 results also remain non-counted with their own manifests.

## 7. Failure classification, visibility and restoration

| Failure | Correct handling |
|---|---|
| COM occupied | find recorder/Serial Monitor owner; pause only approved source |
| gate reports clock drift | measure PDC/workstation/cloud/Gateway, fix authoritative source, rerun before *new* counted trial |
| one restricted SSH collector denied | check wrapper version, permitted verb, proper credential; never replace with unrestricted SSH |
| active marker after interruption | `status` then reviewed `recover`, no deleting lock or modifying raw |
| RF sent but no gateway RX on S1 | classify **invalid attack attempt**, do not add to gateway-received count |
| user receives a Grafana chart with zeros | compare SQL and raw recorder evidence; no-data/USB battery not false zero |
| outbox pending attempts 0 | inspect immutable finalized bytes and verifier eligibility, not automatic dead-letter |
| code suite PASS but no real actor | report code-only/synthetic; no promotion to READY |
| forced-run timeout despite per-window PASS | preserve sealed windows and mark operator command incomplete (as F2 rehearsal), do not fabricate exit 0 |

After the series restore EMU normal five-minute firmware and SEC parked state, remove only explicitly temporary test listeners/Node-RED flood branches after positive verification, and confirm normal gateway LTE, current writer ownership and evidence continuity. Release the complete PDF only with exact counts/durations, units, a printed one-block operator action for **each currently READY test**, explicit non-ready methodology, and no credential/key values.

Source authority: [Chapter III metric contract](../../test/ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md), [readiness checkpoint](../../test/automation/research-manual/CURRENT-READINESS.md), [current research continuation](../../test/automation/research-manual/CONTINUATION.md), [recorder implementation](../../test/automation/research-recorder/README.md).
