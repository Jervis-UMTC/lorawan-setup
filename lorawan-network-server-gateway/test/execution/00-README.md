# Counted Test Execution

Use this folder only after every item in [../preparation/00-README.md](../preparation/00-README.md) passes **and** the dedicated [sensor preflight](../preparation/sensor/preflight/00-README.md) has produced `SENSOR_PREFLIGHT_STATUS=GO`.

The manuals are deliberately repetitive at the important points. That is intentional: every experiment tells you what state the system must be in, what to start, what to change, what to record, what makes a trial invalid, and how to restore the testbed afterward.

## Execution order

1. [01-common-run-preparation.md](01-common-run-preparation.md) - freeze configuration, define run IDs, start/stop captures, collect logs, and classify VALID/INVALID runs.
2. [02-normal-operation.md](02-normal-operation.md) - 3 x 30-minute baseline runs; PDR, latency, TSR, throughput, CPU, memory.
3. [03-authentication-access-control.md](03-authentication-access-control.md) - 90 attempts across LoRaWAN, MQTT, and Fabric authorization.
4. [04-replay-spoofing.md](04-replay-spoofing.md) - 40 legitimate/replay/invalid-MIC attempts; attack frames count only after proven RAK5146 reception.
5. [05-data-integrity.md](05-data-integrity.md) - 40 application-layer and post-storage integrity trials.
6. [06-traceability.md](06-traceability.md) - 20 trials covering 60 records and DB-to-Fabric linkage.
7. [07-dos-flooding.md](07-dos-flooding.md) - 18 five-minute runs plus recovery observations.
8. [08-resilience-recovery.md](08-resilience-recovery.md) - 3 x 2-hour WAN interruption runs.
9. [09-results-and-completion.md](09-results-and-completion.md) - calculate Chapter IV metrics from retained raw evidence.

## Before starting the first counted test

First confirm this file exists from the uncounted sensor-preflight stage:

```text
chapter4-results/_preflight/sensor/04-go-no-go/preflight-status.txt
```

and contains:

```text
SENSOR_PREFLIGHT_STATUS=GO
```

Then complete Execution 01 once, and run its short run-level preflight again before every experiment group.

The two gates have different purposes:

```text
sensor preflight = prove the final sensor/network/application configuration is test-ready
Execution 01     = start fresh evidence and prove the system is still healthy immediately before a counted run
```

Do not reuse preflight packets/log windows as counted research data. Do not start a counted run because the UI merely "looks healthy." You need the earlier sensor GO plus a fresh known-good control uplink and working evidence capture immediately before the experiment group.

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
