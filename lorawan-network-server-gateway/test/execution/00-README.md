# Counted Test Execution

Use this folder only after the preparation relevant to the selected experiment scope has passed. The **full-stack** Chapter IV track requires the dedicated [sensor preflight](../preparation/sensor/preflight/00-README.md) to produce `SENSOR_PREFLIGHT_STATUS=GO`. A deliberately narrower **LoRaWAN-only** track may begin earlier when `LORAWAN_TRACK_STATUS=GO`; that scoped exception authorizes only Execution 03 Part A (LoRaWAN authentication) and Execution 04 (LoRaWAN replay/spoofing). It does not authorize the final normal-operation baseline or any Fabric-dependent result.

The manuals are deliberately repetitive at the important points. That is intentional: every experiment tells you what state the system must be in, what to start, what to change, what to record, what makes a trial invalid, and how to restore the testbed afterward.

### Dissertation-source rule

The current research-test authority is [../ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md](../ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md), derived from the new `chapters/Zacarias_Chapter3.pdf`. Use that source for the **experiment questions, conditions, trial/run counts, durations, measurements, analysis rules, and stated acceptance/security criteria**. Disregard stale architecture/topology/service-placement prose in the chapter. Execute the required tests against the commissioned system that actually exists, using current runbooks and verified live state for implementation. Older Chapter III/IV/V drafts are historical context only when they conflict with the new source-of-truth.

## Counted-test EMU-01 traffic profile

The counted Chapter IV runs intentionally use a **15-second normal-uplink cadence profile** to provide enough observations inside the defined 5-minute, 30-minute, and 2-hour windows. This is an experiment-only timing profile, not the accepted production scheduler.

Freeze these properties across every counted run:

```text
payload = EMU-01 physical-sensor payload-v2, exactly 46 bytes
radio = plain AS923, OTAA, Class A
source identity = the same legitimate EMU-01 identity
normal counted cadence = 15 seconds
production cadence = 60-second local sampling + nominal 5-minute uplinks +/-15 seconds
SEC-02 = separate security fixture; never shares EMU-01 root/session keys
```

Before counted run 1, compile the tracked source with `EMU01_COUNTED_TEST_PROFILE=1`. Its **only intended behavioral difference from production is timing**. Require the boot banner `EMU01_TRAFFIC_PROFILE=COUNTED_TEST_15S`, sample/normal intervals `15000 ms`, and jitter `0`. Archive source/config hash, exact build settings, BSP/toolchain versions, and compiled artifact SHA-256. Reuse that exact artifact for every 15-second counted run. After the series, rebuild/upload the default profile (`EMU01_COUNTED_TEST_PROFILE=0`), require the `PRODUCTION_5MIN` boot banner, and re-run the lightweight normal-path check.

The source sequence remains the independent delivery/ordering marker; physical sensor values are allowed to vary naturally.

## Execution order

The existing numbered manuals are being reconciled to the new Zacarias Chapter 3 matrix. Until every affected manual is updated, the source-of-truth controls any conflicting count, condition, duration, metric, or outage definition.

1. [01-common-run-preparation.md](01-common-run-preparation.md) - freeze configuration, define run IDs, start/stop captures, collect logs, and classify VALID/INVALID runs.
2. [02-normal-operation.md](02-normal-operation.md) - **P1**: 3 x 30-minute normal-operation baseline runs. Formal PDR uses the ChirpStack acceptance boundary; exact source-to-database delivery is a separate metric.
3. [02a-fabric-performance-overhead.md](02a-fabric-performance-overhead.md) - **P2**: 1 tx/15 s, 1 TPS, 5 TPS, and 10 TPS for 5 minutes x 3 repetitions, plus the pre-registered matched no-Fabric controls needed for the overhead calculation.
4. [03-authentication-access-control.md](03-authentication-access-control.md) - **A1**: 90 attempts across LoRaWAN, MQTT, and Fabric identity/authorization.
5. [03a-fabric-endorsement-policy.md](03a-fabric-endorsement-policy.md) - **A2**: 10 normal + 10 missing-endorsement violation + 10 post-restoration attempts, with ledger pre/post-state proof.
6. [04-replay-spoofing.md](04-replay-spoofing.md) - **S1**: 40 legitimate/replay/invalid-MIC attempts; attack frames count only after proven gateway reception.
7. **S2** - application-layer duplicate/replay remains `BLOCKED_BY_METHODOLOGY`: Chapter 3 lists it but does not define its trial count, exact procedure, metric formula, or pass rule. Do not invent a counted S2 result or silently substitute I3/database deduplication.
8. [05-data-integrity.md](05-data-integrity.md) - **I1/I2**: 40 application-layer and post-storage integrity trials.
9. [05a-blockchain-duplicate-overwrite.md](05a-blockchain-duplicate-overwrite.md) - **I3**: 10 baseline anchors + 10 duplicate attempts + 10 conflicting-overwrite attempts, with post-attempt ledger/hash proof.
10. [06-traceability.md](06-traceability.md) - **T1/T2**: 20 trials covering 60 records and DB-to-Fabric linkage.
11. [07-dos-flooding.md](07-dos-flooding.md) - **F1/F2**: 18 five-minute runs plus five-minute recovery observation after every run.
12. [08a-internet-interruption-recovery.md](08a-internet-interruption-recovery.md) - **R1**: 3 x 2-hour external-Internet interruption runs (30 min normal + 60 min outage + 30 min recovery), implemented against the commissioned topology rather than the stale architecture.
13. [08b-fabric-consistency-reconciliation.md](08b-fabric-consistency-reconciliation.md) - **R2**: 10 controls + 10 records created during Fabric unavailability, then reconcile those same 10 with query-before-resubmission evidence.
14. [09-results-and-completion.md](09-results-and-completion.md) - calculate Chapter IV metrics from retained raw evidence and enforce the complete dataset checklist.

`08-resilience-recovery.md` remains only a legacy Fabric-endpoint-isolation reference. It is not the counted R1 Internet-interruption procedure.

## Before starting the first counted test

For the complete Chapter IV stack, confirm the full-stack preflight file exists:

```text
chapter4-results/_preflight/sensor/04-go-no-go/preflight-status.txt
```

and contains:

```text
SENSOR_PREFLIGHT_STATUS=GO
```

For the scoped LoRaWAN-only security track, the full-stack file may remain `NO-GO` only for a downstream external dependency. Instead require `chapter4-results/_preflight/sensor/04-go-no-go/lorawan-track-status.txt` to contain `LORAWAN_TRACK_STATUS=GO`. That scoped GO authorizes only Execution 03 Part A (30 LoRaWAN authentication attempts) and Execution 04 (40 replay/spoofing attempts); it does not authorize the final normal-operation baseline or any result requiring a real Fabric submit/query/commit.

Then complete Execution 01 once for the selected scope, and run its short run-level preflight again before every experiment group.

The readiness gates and run-level precheck have different purposes:

```text
full sensor preflight = prove the entire sensor/network/application/Fabric configuration is test-ready
LoRaWAN track gate    = prove the independent RF/LoRaWAN security path is test-ready
Execution 01          = start fresh evidence and prove the selected scope is healthy immediately before a counted run
```

Do not reuse preflight packets/log windows as counted research data. Do not start a counted run because the UI merely "looks healthy." Use the readiness gate appropriate to the selected experiment scope plus a fresh known-good control uplink and working evidence capture immediately before the experiment group.

## Universal run pattern

Every experiment uses this order:

```text
A. PRECHECK
   Verify services, clocks, gateway, EMU-01, and evidence tools.

B. IDENTIFY
   Create unique RUN_ID / TRIAL_ID and record expected outcome before action.

C. CAPTURE
   Start source, server, gateway, resource, and experiment-specific evidence.

D. APPLY ONE CONDITION
   Baseline, invalid credential, replay, tamper, flood, or WAN loss.
   Do not combine conditions.

E. PROVE THE CONDITION HAPPENED
   Example: replay counts only when RAK5146 received the replay frame.

F. OBSERVE
   Record actual accept/reject/store/commit/recovery behavior.

G. STOP AND EXPORT
   Stop captures at the defined boundary and export raw evidence.

H. CLASSIFY
   PASS = expected behavior occurred and evidence is complete.
   FAIL = condition was validly applied but expected behavior did not occur.
   INVALID = the intended condition/evidence was not achieved; rerun separately.

I. RESTORE
   Return the testbed to the documented normal state before the next condition.
```

## Standard result folder pattern

Use one directory per measured run or discrete trial group:

```text
chapter4-results/<group>/<run_id>/
  run-meta.txt
  start-utc.txt
  end-utc.txt
  emu-01-source.log
  server.log
  gateway.log
  docker-stats.csv
  gateway-resource.csv
  network-before.txt
  network-after.txt
  trial-results.csv        # when the experiment uses discrete trials
  uplinks.csv              # when applicable
  fabric.csv               # when applicable
  run-status.txt
  notes.txt
```

Not every test needs every file, but never omit evidence required by its manual.

## Universal trial fields

For every counted discrete trial retain at least:

```text
trial_id
layer
test_condition
expected_result
actual_result
start_utc
end_utc
device_eui
frame_counter_or_event_key
test_sequence_when_applicable
gateway_received
application_reached
database_changed
fabric_tx_id
response_or_verification_time
trial_status = PASS | FAIL | INVALID
log_reference
notes
```

## PASS, FAIL, and INVALID are different

**PASS:** the intended condition reached the layer being tested, the system behaved as expected, and evidence is complete.

**FAIL:** the intended condition reached the layer being tested, but the system behaved contrary to the expected result. Keep the failure; do not silently rerun until it disappears.

**INVALID:** the intended condition was not actually created or could not be proven. Examples: gateway never received the attack RF frame, load generator missed the required rate, required service crashed for an unrelated reason, timestamp correlation failed, or evidence capture was lost. Rerun the invalid attempt with a new trial ID and keep the invalid record in the audit trail.

## Configuration discipline

Inside one repetition group, do not change:

```text
firmware
container images
Node-RED flow logic
schemas
credentials used by the condition
AS923 plan
EMU-01 payload contract / 15-second interval
flood rates
WAN-interruption method
measurement interval
```

If a change is necessary, stop the group, document the change, repeat the **Execution 01 short run-level preflight**, and restart that repetition group with new IDs. Rerun the full sensor preflight only when the change affects the frozen sensor hardware/firmware, payload/codec, RF/AS923 path, or normal application mapping.

## Result discipline

Keep raw files unchanged. Create calculated/cleaned summaries separately under `chapter4-results/summaries/`. Every Chapter IV value must be reproducible from retained raw evidence.
