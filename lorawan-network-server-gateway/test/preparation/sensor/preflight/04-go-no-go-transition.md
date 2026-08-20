# Sensor Preflight 4 - GO / NO-GO and Transition to Counted Tests

This is the final sensor readiness gate.

Do not fix hardware, reflash firmware, edit the codec, or change Node-RED while filling out this page. If something is wrong, record **NO-GO**, repair it, and rerun the affected preflight.

## Transition architecture

```text
PREPARATION
   │
   ├─ assembly complete
   ├─ every A/B sensor verified
   ├─ final EMU-01 firmware frozen
   └─ SEC-02 security role prepared
          │
          ▼
SENSOR PREFLIGHT
   │
   ├─ hardware/firmware PASS
   ├─ OTAA/RAK5146/ChirpStack PASS
   └─ Node-RED/DB/Fabric PASS
          │
          ▼
      GO / NO-GO
       │       │
      GO     NO-GO
       │       │
       │       └──> repair -> repeat affected preflight
       ▼
COUNTED EXECUTION
   │
   └─ Execution 01 common run preparation
```

## Step 1 - Review Preflight 1

Require:

```text
[ ] frozen hardware map matches EMU-01
[ ] LoRa antenna installed correctly
[ ] ten consecutive source cycles captured
[ ] sequence continuity passed
[ ] 15-second scheduler passed
[ ] all normal validity bitmaps = 0x007F
[ ] no unexplained reset
```

## Step 2 - Review Preflight 2

Require:

```text
[ ] RAK5146 gateway healthy
[ ] correct real Gateway EUI confirmed
[ ] frozen plain AS923 plan unchanged end-to-end (`LORAMAC_REGION_AS923` / `as923`)
[ ] OTAA JoinRequest observed at gateway/ChirpStack
[ ] JoinAccept / activation succeeded
[ ] EMU-01 reports joined
[ ] at least ten consecutive post-join uplinks evaluated
[ ] ChirpStack codec has zero errors for selected uplinks
[ ] source-to-decoder comparisons passed
```

## Step 3 - Review Preflight 3

Require:

```text
[ ] seven required server services healthy
[ ] five selected sequences stored in TimescaleDB
[ ] zero unexpected canonical duplicates
[ ] source-to-payload_json field comparison passed
[ ] both light sensors remain separate
[ ] validity bitmap preserved
[ ] selected Fabric event linked correctly
[ ] required Fabric commit/evidence condition passed
[ ] preflight start/end boundaries recorded
```

## Step 4 - Confirm security-node readiness

SEC-02 is not used as the normal legitimate sensor source, but it must be ready before the test track starts.

Require:

```text
[ ] every B-copy sensor was already functionally verified using the frozen RAK19007 Profile A/Profile B maps
[ ] SEC-02 Profile A pin-map + readings evidence exists
[ ] SEC-02 Profile B pin-map + readings evidence exists
[ ] normal SEC-02 hardware baseline is RAK19007 + Core B + LoRa antenna
[ ] Sensor A = EMPTY
[ ] Sensor B = EMPTY
[ ] Sensor C = EMPTY
[ ] Sensor D = EMPTY
[ ] IO slot = EMPTY
[ ] SEC-02 contains no EMU-01 legitimate AppKey
[ ] SEC-02 contains no legitimate EMU-01 session keys
[ ] wrong-AppKey/unregistered fixture is prepared as documented
[ ] raw LoRa/P2P security mode is available when required
[ ] one uncounted raw-RF rehearsal has already been proven at RAK5146, if the security preparation manual requires it
```

The assembly source of truth for the two temporary B-copy profiles and the stripped security baseline is [../assembly/02b-rak19007-sec02-fixed-profiles.md](../assembly/02b-rak19007-sec02-fixed-profiles.md).

Do not run a counted replay/spoof test if raw-RF reception has never been rehearsed successfully.

## Step 5 - Confirm evidence tools before transition

Before GO, confirm the test laptop/server can create the evidence required by Execution 01:

```text
EMU-01 serial capture works
server resource logger works
gateway resource logger works
UTC clocks can be inspected/correlated
result directories are writable
```

This is a readiness check only; Execution 01 will start fresh captures for the counted run.

## Step 6 - Create the status file

Create:

```text
chapter4-results/_preflight/sensor/04-go-no-go/preflight-status.txt
```

Use this template:

```text
SENSOR_PREFLIGHT_STATUS=GO|NO-GO
preflight_completed_utc=<UTC>
EMU01_DEV_EUI=<non-secret DevEUI>
gateway_eui=<real Gateway EUI>
firmware_hash=<hash>
payload_version=2
payload_length=46
normal_interval_seconds=15
last_preflight_test_sequence=<N>
preflight_1_hardware_firmware=PASS|FAIL
preflight_2_lorawan_chirpstack=PASS|FAIL
preflight_3_application_path=PASS|FAIL
sec02_ready=yes|no
evidence_tools_ready=yes|no
notes=<short explanation>
```

Do not store any secret credential in this file.

## GO decision

Write:

```text
SENSOR_PREFLIGHT_STATUS=GO
```

only when every required check above passes.

A GO means:

```text
we have proven the final sensor hardware
+
we have proven the final firmware
+
we have proven the RF/gateway path
+
we have proven OTAA and ChirpStack decoding
+
we have proven the application/database path
+
we have proven the required Fabric evidence path
+
we can now measure experiments instead of debugging setup
```

## NO-GO decision

Use `NO-GO` whenever a required layer fails or evidence is missing.

Examples:

```text
validity bitmap not 0x007F
unexplained RAK4631 reset
JoinRequest not received by RAK5146
OTAA credentials/profile reject legitimate EMU-01
codec error
source value differs from DB without defined rounding rule
required DB row missing
required Fabric verification incomplete
SEC-02 contains the wrong credentials
required evidence logger not working
```

Do not reinterpret NO-GO as a failed dissertation trial. Preflight failures are setup defects and are repaired before counted testing begins.

## Step 7 - Freeze the transition point

When status is GO:

1. record the final preflight end UTC;
2. record the last preflight `test_sequence`;
3. stop any temporary preflight-only log viewers/captures;
4. do **not** delete the preflight evidence;
5. do not change firmware, payload, sensor map, codec, AS923 plan, or normal Node-RED mapping;
6. leave EMU-01 in its normal final operating state;
7. keep SEC-02 idle until a security experiment calls for it.

## Step 8 - Transition directly to counted test preparation

Next open:

[Execution 01 - Common Run Preparation](../../../execution/01-common-run-preparation.md)

Execution 01 creates the **fresh run ID, start time, evidence capture, and known-good control** for the counted experiment. The preflight evidence is not reused as counted data.

The transition is:

```text
preflight-status.txt = GO
          │
          ▼
Execution 01 short preflight + fresh capture
          │
          ▼
Execution 02 baseline
          │
          ▼
remaining counted experiments
```
