# Dissertation Testing Track

This directory is the complete operator path for preparing and executing the Chapter III/IV LoRaWAN dissertation experiments.

> **Current methodology authority:** use [ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md](ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md) for the formal research tests, conditions, counts, durations, required metrics, evidence rules, and stated acceptance/security criteria extracted from the new `chapters/Zacarias_Chapter3.pdf`. Architecture/topology/deployment prose in that PDF is not current infrastructure truth; execute those tests against the verified commissioned system.

Use this track for the counted research tests only. Do not add production HA, dashboards, or unrelated services to the measured VM unless the research methodology is intentionally changed.

## Directory structure

```text
test/
├── 00-README.md
├── automation/
│   └── research-recorder/ # supervised evidence capture, preflight, sealing, recovery, summaries
├── preparation/
│   ├── 00-README.md
│   ├── gateway/     # Raspberry Pi 4B + RAK5146
│   ├── server/      # Ubuntu VM + minimum seven-service stack
│   ├── sensor/      # RAK4631 EMU-01 + SEC-02
│   │   ├── assembly/
│   │   └── preflight/   # uncounted final sensor -> ChirpStack -> data-path GO/NO-GO
│   └── tools/       # test laptop + generators + resource logging
└── execution/
    ├── 00-README.md
    ├── 01-common-run-preparation.md
    ├── 02-normal-operation.md
    ├── 03-authentication-access-control.md
    ├── 04-replay-spoofing.md
    ├── 05-data-integrity.md
    ├── 06-traceability.md
    ├── 07-dos-flooding.md
    ├── 08-resilience-recovery.md
    └── 09-results-and-completion.md
```

## What is actually tested

The sensor **measurement values are real physical Agriculture Kit readings**. The packet-accounting sequence is controlled, while the LoRaWAN path remains physical and real:

```text
RAK4631 EMU-01 full physical Agriculture Kit sensor node
  -> real AS923 LoRaWAN RF
  -> Raspberry Pi 4B + RAK5146
  -> Concentratord
  -> MQTT Forwarder
  -> gateway local Mosquitto buffer
  -> mTLS
  -> server Mosquitto
  -> ChirpStack
  -> Node-RED
  -> PostgreSQL / TimescaleDB
  -> Fabric outbox
  -> Fabric adapter
  -> OpenBao
  -> external Hyperledger Fabric
```

`EMU-01` is the legitimate full-sensor OTAA device. It carries one complete Agriculture Kit sensor set and adds deterministic packet-sequence markers to real measurements. `SEC-02` first verifies every second-copy sensor, then becomes the isolated invalid-device/raw-RF security node and must never contain EMU-01's legitimate AppKey or legitimate session keys.

## One-page operator journey

Follow this sequence. Do not jump directly to an experiment.

```text
1. PREPARE GATEWAY 01-03
   Assemble -> Gateway OS -> AS923 Concentratord -> record real Gateway EUI

2. PREPARE SERVER
   Create VM -> deploy minimum seven services -> register that EUI -> issue mTLS identity/ACL

3. FINISH GATEWAY 04-06
   Local buffer -> MQTT Forwarder -> mTLS -> ChirpStack Last seen -> real RF acceptance

4. PREPARE SENSOR NODES
   Assemble two RAK4631 nodes -> install/verify every Agriculture Kit sensor -> keep the complete A-set on EMU-01 -> verify the B-set on SEC-02 -> configure physical-sensor OTAA telemetry -> configure SEC-02 invalid OTAA/raw RF -> prove RAK5146 receives SEC-02

5. PREPARE TEST TOOLS
   Test laptop -> source capture -> flood generators -> server/gateway resource logging

6. SENSOR PREFLIGHT - UNCOUNTED
   Final hardware/firmware -> 10 healthy cycles -> RAK5146 -> OTAA/ChirpStack -> decoder -> Node-RED/TimescaleDB/Fabric -> GO/NO-GO

7. FREEZE THE TESTBED / TRANSITION
   Require SENSOR_PREFLIGHT_STATUS=GO. Record versions/configuration. No unplanned changes inside a repetition group.

8. EXECUTION 01
   Start fresh counted-run IDs, clocks, source/resource captures, and one known-good control.

9. RUN BASELINE
   Three 30-minute normal-operation runs

10. RUN SECURITY / INTEGRITY / TRACEABILITY / FLOODING / RESILIENCE TESTS
   One controlled condition at a time

11. CALCULATE RESULTS
   Raw evidence -> validated trial set -> Chapter IV summaries
```

## Required preparation order

The gateway and server have one deliberate dependency: the server needs the **real Gateway EUI** before it can issue the gateway mTLS identity.

1. Open [preparation/00-README.md](preparation/00-README.md).
2. Complete Gateway 01-03 and record the real Gateway EUI.
3. Complete server preparation and provision that exact EUI in ChirpStack, the broker certificate, and ACL.
4. Return to Gateway 04-06 and complete end-to-end gateway acceptance.
5. Assemble both RAK4631 boards using [preparation/sensor/assembly/00-README.md](preparation/sensor/assembly/00-README.md), then configure EMU-01 and SEC-02.
6. Prepare the separate test laptop and measurement tools.
7. Run the dedicated [sensor preflight](preparation/sensor/preflight/00-README.md) against the frozen gateway/server path.
8. Require `SENSOR_PREFLIGHT_STATUS=GO` and complete the final preparation gate.
9. Enter [execution/01-common-run-preparation.md](execution/01-common-run-preparation.md) for fresh counted-run capture.

For full-stack counted testing, do not start until every preparation item passes. The intentionally narrower LoRaWAN security exception is defined only in [execution/00-README.md](execution/00-README.md) and may proceed only when `LORAWAN_TRACK_STATUS=GO`; do not widen that exception to Fabric-dependent experiments.

Use [automation/research-recorder/README.md](automation/research-recorder/README.md) for the accepted automated evidence-capture workflow. Preserve recorder outputs under `chapter4-results/`; smoke, interrupted, failed, and invalid runs are evidence and are not cache directories.

## Minimum test VM

```text
Physical host: 8 GiB RAM / 8 CPU threads
Test VM:       5 GiB RAM / 4 vCPU / 50 GiB SSD-backed disk
OS:            Ubuntu Server 24.04 LTS, no desktop GUI
```

The minimum server stack is exactly:

```text
Mosquitto
Valkey
ChirpStack
PostgreSQL / TimescaleDB
Node-RED
OpenBao
Fabric adapter
```

## Authoritative experiment inventory

The new Zacarias Chapter 3 expands the formal test set. The concise inventory below is mandatory; use the source-of-truth document for full metric definitions and evidence rules.

```text
P1  End-to-end normal operation:             3 x 30-minute runs
P2  Fabric performance/overhead:             4 workloads x 3 repetitions = 12 x 5-minute runs
R1  External-Internet interruption/recovery: 3 x 2-hour runs (30 normal + 60 outage + 30 recovery)
R2  Fabric consistency/reconciliation:       10 control + 10 Fabric-unavailable; reconcile the same 10 pending
A1  Authentication/access control:            90 attempts
A2  Fabric endorsement-policy enforcement:   30 attempts
S1  LoRaWAN replay/spoofing:                  40 counted attempts
S2  Application-layer duplicate/replay:       listed by Chapter 3 Table 3.4, but count/procedure/metrics are unspecified -> methodology resolution required
F1/F2 DoS/flooding:                           18 x 5-minute load runs + 5-minute recovery after each
I1/I2 Application/post-storage integrity:     40 attempts
I3  Blockchain duplicate/overwrite:           10 baseline anchors + 10 duplicate + 10 overwrite attempts
T1/T2 Traceability:                           20 trials / 60 records
```

Do not collapse `R1` and `R2`: Internet interruption and Fabric unavailability/reconciliation are separate experiments. Likewise, `P2`, `A2`, and `I3` are required formal tests and must not be omitted simply because older execution indexes did not list them. `S2` is a chapter-internal methodology gap: it is explicitly listed but not defined in the later procedure, so it must remain visible and unresolved rather than being silently dropped or assigned invented counts.

## The rule for every counted trial

Every trial must answer all five questions:

```text
1. What exact condition did we intentionally create?
2. How do we prove the condition actually reached the layer being tested?
3. What was the expected decision before the trial started?
4. What did the system actually do?
5. Which raw file/log/record proves the result?
```

If question 2 cannot be proven, the trial is **INVALID**, not PASS. If evidence for question 5 is missing, the trial is **INVALID** and must be rerun.

## Evidence rule

Preserve the EMU-01 source log, timestamps, stable identifiers, gateway/ChirpStack decision evidence, database exports, Fabric evidence, and required CPU/memory samples. Screenshots may support a result but must not replace raw logs or CSV/database evidence.
