# Sensor Preflight - Start Here

This folder is the **uncounted acceptance bridge** between sensor setup and the dissertation experiments.

Do not use a successful Arduino upload or one visible ChirpStack packet as proof that the sensor subsystem is test-ready. The preflight proves the complete path in layers and creates a single GO/NO-GO decision before counted execution.

## Where this fits

```text
SENSOR ASSEMBLY / PROGRAMMING
        │
        ▼
all physical sensors verified
        │
        ▼
final EMU-01 firmware flashed
        │
        ▼
LoRaWAN identity + codec configured
        │
        ▼
┌─────────────────────────────────────┐
│        SENSOR PREFLIGHT             │
│                                     │
│  01 hardware + firmware             │
│       ↓                             │
│  02 RF + OTAA + ChirpStack          │
│       ↓                             │
│  03 Node-RED + DB + Fabric          │
│       ↓                             │
│  04 GO / NO-GO transition           │
└──────────────────┬──────────────────┘
                   │ GO only
                   ▼
        COUNTED TEST EXECUTION
```

## Preflight is not research data

Everything in this folder is a readiness check.

```text
preflight packets = uncounted
preflight joins   = uncounted
preflight DB rows = uncounted
preflight Fabric events = uncounted
```

Do not delete normal telemetry history merely to hide preflight packets. Instead save the preflight start/end UTC times and test-sequence range. Counted experiments use their own explicit run boundaries and IDs.

## Required order

1. [01-hardware-firmware-preflight.md](01-hardware-firmware-preflight.md) - prove the physical A-set, final firmware, serial output, 15-second scheduler, and validity bitmap.
2. [02-lorawan-chirpstack-preflight.md](02-lorawan-chirpstack-preflight.md) - prove RAK5146 reception, OTAA, ChirpStack acceptance, payload decoding, and stable consecutive uplinks.
3. [03-application-data-path-preflight.md](03-application-data-path-preflight.md) - prove Node-RED, TimescaleDB, source-to-database equality, and one selected Fabric evidence path.
4. [04-go-no-go-transition.md](04-go-no-go-transition.md) - review all evidence, create the GO/NO-GO record, freeze the sensor state, and transition to counted execution.

Do not skip a file because the same component worked earlier during setup. Setup proves that a component can work; preflight proves that the **frozen final configuration works together**.

## Preflight architecture

```text
PHYSICAL SENSOR SET
  │
  ├─ soil
  ├─ UV
  ├─ barometer
  ├─ VEML7700 light
  ├─ OPT3001 light
  ├─ BME680 environment
  └─ rain
       │
       ▼
┌─────────────────────┐
│ RAK4631 EMU-01      │
│ final frozen build  │
└──────────┬──────────┘
           │
      USB  │  LoRaWAN RF
       │   │
       │   ▼
       │  RAK5146
       │   │
       │   ▼
       │  ChirpStack
       │   │
       │   ▼
       │  Node-RED
       │   │
       │   ▼
       │  TimescaleDB
       │   │
       │   ▼
       └─ compare ──> Fabric evidence
```

The serial source log is the reference for the physical values assigned to each `test_sequence`.

## Evidence folder

Create one dedicated folder on the test laptop/server evidence location:

```text
chapter4-results/_preflight/sensor/
```

Recommended structure:

```text
sensor/
├── preflight-meta.txt
├── 01-hardware-firmware/
│   ├── emu-01-source.log
│   ├── ten-cycle-check.txt
│   └── hardware-checklist.txt
├── 02-lorawan-chirpstack/
│   ├── gateway.log
│   ├── chirpstack.log
│   ├── decoded-uplinks.txt
│   └── join-evidence.txt
├── 03-application-path/
│   ├── db-uplinks.csv
│   ├── source-vs-db.txt
│   └── fabric-evidence.txt
└── 04-go-no-go/
    └── preflight-status.txt
```

Do not save AppKeys, session keys, passwords, private keys, or tokens.

## Hard rule

If any required preflight step fails:

```text
STOP
  ↓
record NO-GO reason
  ↓
repair the responsible layer
  ↓
repeat from the earliest affected preflight manual
```

Do not start a counted experiment and hope the fault disappears.

## Ready to leave this folder

You may enter counted execution only when [04-go-no-go-transition.md](04-go-no-go-transition.md) produces:

```text
SENSOR_PREFLIGHT_STATUS=GO
```

Then continue directly to [../../../execution/01-common-run-preparation.md](../../../execution/01-common-run-preparation.md).
