# Agriculture Sensor Setup Manual

Use this file as the **start-to-finish operator manual** for the two RAK4631 boards in the WisBlock Agriculture Kit.

The goal is not only to assemble the hardware. At the end of this procedure:

```text
EMU-01
  = RAK19001 + RAK4631
  + one complete A-set of Agriculture Kit sensors
  + final Arduino firmware
  + legitimate OTAA credentials
  + physical sensor payload every 15 seconds

SEC-02
  = RAK19007 + second RAK4631
  + every B-copy sensor verified during preparation
  + later isolated security-test firmware/configuration
  + NO EMU-01 AppKey or legitimate session keys
```

## Architecture you are building

```text
                         PHYSICAL SENSOR NODE

  Soil ───────────────┐
  UV ─────────────────┤
  Barometer ──────────┤
  VEML7700 light ─────┤
  OPT3001 light ──────┤      USB-C during setup
  BME680 environment ─┤             │
  Rain ───────────────┘             ▼
                           ┌───────────────────┐
                           │ RAK19001          │
                           │ + RAK4631 EMU-01  │
                           └─────────┬─────────┘
                                     │
                                  LoRaWAN
                                     │
                                     ▼
                           ┌───────────────────┐
                           │ RAK5146 Gateway   │
                           └─────────┬─────────┘
                                     │
                                     ▼
                         ChirpStack -> Node-RED
                                     │
                                     ▼
                            TimescaleDB/Fabric
```

Only `test_sequence`, uptime, and the transmission schedule are deterministic. The Agriculture Kit measurements are real physical readings.

---

# Master setup sequence

Follow this order. Do not jump directly to Arduino programming or LoRaWAN joining.

```text
[1] Inventory hardware
        │
        ▼
[2] Assemble both RAK4631 base nodes
        │
        ▼
[3] Install every A-set sensor on EMU-01
        │
        ▼
[4] Pre-power inspection
        │
        ▼
[5] Install Arduino IDE + RAK4631 BSP on laptop
        │
        ▼
[6] Prove laptop can upload to both RAK4631 boards
        │
        ▼
[7] Test every A-copy and B-copy sensor
        │
        ▼
[8] Flash final integrated EMU-01 sensor firmware
        │
        ▼
[9] Register/provision EMU-01 in ChirpStack
        │
        ▼
[10] Join OTAA + verify decoded payload
        │
        ▼
[11] Prove TimescaleDB/Fabric path
        │
        ▼
[12] Freeze firmware + hardware baseline
        │
        ▼
[13] Run sensor preflight against final gateway/server
        │
        ▼
[14] GO -> Execution 01 / NO-GO -> repair and repeat
```

## Manuals used by that sequence

1. [assembly/00-README.md](assembly/00-README.md) - hardware overview and assembly map.
2. [assembly/01-assemble-minimum-test-nodes.md](assembly/01-assemble-minimum-test-nodes.md) - assemble RAK19001/RAK19007 + RAK4631 + antennas.
3. [assembly/02-assemble-agriculture-sensors.md](assembly/02-assemble-agriculture-sensors.md) - prepare the complete A-set and B-copy profiles.
4. [assembly/02a-rak19001-fixed-slot-map.md](assembly/02a-rak19001-fixed-slot-map.md) - fixed EMU-01 RAK19001 A-F/WisIO map, GPIO ownership, Pin Mapper values, and placement rationale.
5. [assembly/02b-rak19007-sec02-fixed-profiles.md](assembly/02b-rak19007-sec02-fixed-profiles.md) - fixed SEC-02 RAK19007 Profile A/Profile B positions, power-off rebuild procedure, B-copy acceptance evidence, and final stripped security-node baseline.
6. [assembly/03-pre-power-check-and-troubleshooting.md](assembly/03-pre-power-check-and-troubleshooting.md) - mandatory inspection before applying power to EMU-01 or either SEC-02 profile.
7. [assembly/04-verify-all-sensors.md](assembly/04-verify-all-sensors.md) - install Arduino IDE/BSP, prove uploads, and test every A/B sensor.
8. [assembly/04a-first-time-arduino-operator-walkthrough.md](assembly/04a-first-time-arduino-operator-walkthrough.md) - first-time Arduino IDE click-by-click companion and troubleshooting explanations.
9. [assembly/04b-emu01-sec02-code-reference.md](assembly/04b-emu01-sec02-code-reference.md) - authoritative copy/paste Arduino sanity and sensor-test sketches for both EMU-01 and SEC-02. No chat-only test sketch is accepted as the project baseline.
10. [01-configure-rak4631-emulators.md](01-configure-rak4631-emulators.md) - flash the final integrated firmware, provision OTAA, and prepare SEC-02 security firmware only after B-copy verification.
11. [preflight/00-README.md](preflight/00-README.md) - use the frozen final sensor node against the real RAK5146/ChirpStack/application path and produce the GO/NO-GO transition into counted testing.

The configuration filename is retained so older links do not break. EMU-01 is a real physical-sensor node, not a synthetic measurement emulator.

---

# Step 1 - Lay out and label the hardware

Before connecting USB:

```text
Core A     -> EMU-01
Core B     -> SEC-02
RAK19001   -> EMU-01
RAK19007   -> SEC-02
```

**RAK4630 / RAK4631 label note:** the WisBlock Core board used by this Agriculture Kit is documented as RAK4631, and the RAK4631 contains a RAK4630 stamp module as its main component. A visible `RAK4630` marking on Core A or Core B is therefore expected. Continue selecting `WisBlock Core RAK4631 Board` in Arduino IDE when using the Arduino-BSP firmware path. The marking does not change the documented EMU-01 or SEC-02 sensor-slot positions.

Label the direct sensors:

```text
SOIL-A / SOIL-B
UV-A / UV-B
BARO-A / BARO-B
LIGHT-VEML-A / LIGHT-VEML-B
LIGHT-OPT-A / LIGHT-OPT-B
ENV-A / ENV-B
RAIN-A / RAIN-B
```

Do not provision cryptographic credentials until the two RAK4631 cores have permanent roles.

**Expected result:** two clearly labeled cores/base boards and fourteen labeled direct-sensor assemblies.

**Stop if:** a core, base board, antenna, sensor pair, or required cable is missing.

---

# Step 2 - Assemble the base nodes

Follow [assembly/01-assemble-minimum-test-nodes.md](assembly/01-assemble-minimum-test-nodes.md).

The result must be:

```text
EMU-01: RAK19001 + Core A + LoRa antenna
SEC-02: RAK19007 + Core B + LoRa antenna
```

The correct LoRa antenna must be attached before RF use.

---

# Step 3 - Install the Agriculture Kit sensors

Follow [assembly/02-assemble-agriculture-sensors.md](assembly/02-assemble-agriculture-sensors.md).

EMU-01 keeps one complete direct-sensor set installed using the fixed project map:

```text
Sensor A -> RAK1903   OPT3001 ambient light
Sensor B -> EMPTY / NA
Sensor C -> RAK12019  UV
Sensor D -> RAK12011  barometer + temperature
Sensor E -> RAK1906   BME680 environment
Sensor F -> RAK12010  VEML7700 ambient light

WisIO 1  -> RAK12023 -> RAK12035 soil probe
WisIO 2  -> RAK12005 -> RAK12030 rain pad
```

Verify this exact assignment in the current WisBlock Pin Mapper and require no unresolved conflict before power-up. See [assembly/02a-rak19001-fixed-slot-map.md](assembly/02a-rak19001-fixed-slot-map.md) for GPIO ownership and placement rationale.

SEC-02 uses two frozen temporary hardware profiles because the RAK19007 has four Sensor slots A-D and one IO slot. Do not improvise positions. Use [assembly/02b-rak19007-sec02-fixed-profiles.md](assembly/02b-rak19007-sec02-fixed-profiles.md): Profile A is `A=RAK1903-B, B=RAK12010-B, C=RAK12019-B, D=RAK12011-B, IO=RAK12023+RAK12035-B`; Profile B is `A=RAK1906-B, B/C/D=EMPTY, IO=RAK12005+RAK12030-B`. Power must be completely removed before changing profiles.

---

# Step 4 - Inspect before power

Follow [assembly/03-pre-power-check-and-troubleshooting.md](assembly/03-pre-power-check-and-troubleshooting.md).

Do not connect USB until all are true:

```text
[ ] RAK4631 seated correctly
[ ] LoRa antenna attached to LoRa connector
[ ] sensor/IO modules seated and screwed down
[ ] no unresolved Pin Mapper conflict
[ ] no loose screw or conductive debris
[ ] soil/rain wet parts separated from main electronics
[ ] optical sensors unobstructed
```

---

# Step 5 - Prepare the programming laptop

The standard RAK4631 can be programmed with Arduino IDE. The laptop is only needed to build/upload firmware and capture serial logs; Arduino IDE is **not** part of the running LoRaWAN infrastructure.

Follow [assembly/04-verify-all-sensors.md](assembly/04-verify-all-sensors.md). If this is your first time using Arduino IDE, use the detailed companion [assembly/04a-first-time-arduino-operator-walkthrough.md](assembly/04a-first-time-arduino-operator-walkthrough.md) and do not skip its gates.

The beginner path is:

```text
install Arduino IDE
      ↓
add RAK BSP URL
      ↓
install RAKwireless board package
      ↓
select WisBlock Core RAK4631 Board
      ↓
identify EMU-01 COM port
      ↓
compile known-good serial sketch
      ↓
Upload -> "Device programmed."
      ↓
Serial Monitor 115200 -> "EMU-01 is alive"
      ↓
RAK1903 guided light test
      ↓
RAK12010 guided light test
      ↓
remaining physical sensors
```

The companion manual explains **why** Compile, Upload, and Serial Monitor are separate tests, how to interpret memory-usage output after a successful compile, how to recover from a changed DFU COM port, how the RAK19001 `3V3_S` sensor-power control is enabled, and how to distinguish a missing Arduino library from a real sensor failure.

**Expected result:** both RAK4631 boards can be independently programmed and can print serial output, and the sensor verification stage begins only after that programming foundation passes.

---

# Step 6 - Verify every physical sensor

Still using [assembly/04-verify-all-sensors.md](assembly/04-verify-all-sensors.md):

```text
A-set: verify individually, then together on EMU-01
B-set: verify in the exact SEC-02 Profile A and Profile B maps in assembly/02b-rak19007-sec02-fixed-profiles.md
```

A sensor counts as used only when it is:

```text
installed
  + initialized by firmware
  + produces a reading/state transition
  + result is saved
```

Do not continue to final LoRaWAN firmware if one required direct sensor is unverified.

---

# Step 7 - Program the final EMU-01 firmware

Follow [01-configure-rak4631-emulators.md](01-configure-rak4631-emulators.md).

The final firmware performs this loop:

```text
Every 15 seconds
      │
      ├─ read soil
      ├─ read UV
      ├─ read barometer
      ├─ read VEML7700 light
      ├─ read OPT3001 light
      ├─ read BME680 environment
      ├─ read rain
      │
      ├─ build validity bitmap
      ├─ add test_sequence + uptime
      ├─ build 46-byte payload v2
      ├─ print source record to USB serial
      └─ send one LoRaWAN uplink
```

A completely valid sensor cycle has validity bits 0-6 set (`0x007F`).

---

# Step 8 - Provision LoRaWAN

For EMU-01 prepare:

```text
DevEUI
JoinEUI/AppEUI
AppKey
frozen lab region = plain AS923 (`LORAMAC_REGION_AS923`, ChirpStack/MQTT `as923`)
Class A / OTAA
```

Do not store the EMU-01 AppKey in Git, screenshots, evidence CSVs, or copy it to SEC-02.

SEC-02 may perform one temporary **legitimate-node** test before security conversion, but it must use its own DevEUI and its own temporary AppKey. Retire that SEC-02 credential after the legitimate-node check and before security-fixture testing.

Register EMU-01 in ChirpStack for the final normal telemetry role and use the LoRaWAN version actually supported by the frozen firmware.

---

# Step 9 - Verify one end-to-end reading

The acceptance path is:

```text
Serial source line
      │
      ▼
RAK4631 uplink
      │
      ▼
RAK5146 receives RF
      │
      ▼
ChirpStack accepts + decodes
      │
      ▼
Node-RED maps fields
      │
      ▼
TimescaleDB stores same test_sequence/values
      │
      ▼
selected event receives Fabric evidence
```

For one sequence, compare the source line and decoded/stored payload field by field.

---

# Step 10 - Freeze the sensor baseline

Record at least:

```text
EMU-01 core/base assignment
SEC-02 core/base assignment
sensor labels and slot map
Arduino IDE version
RAKwireless BSP version
sensor library versions
final firmware/source hash
payload version = 2
payload length = 46 bytes
15-second interval
frozen plain AS923 configuration (`LORAMAC_REGION_AS923`; server/topic `as923`)
EMU-01 DevEUI (non-secret)
ChirpStack device-profile information
```

Do not change firmware/library versions inside a counted experiment group.

---

# Step 11 - Run the dedicated sensor preflight

After setup/configuration passes, do **not** jump directly to counted execution.

Open:

[Sensor Preflight - Start Here](preflight/00-README.md)

The preflight uses the final frozen configuration and proves:

```text
hardware + final firmware
        ↓
10 healthy full-sensor cycles
        ↓
RAK5146 RF reception
        ↓
OTAA + ChirpStack acceptance
        ↓
payload-v2 decoding
        ↓
Node-RED + TimescaleDB equality
        ↓
required Fabric evidence
        ↓
GO / NO-GO
```

Preflight traffic is uncounted and is kept under `chapter4-results/_preflight/sensor/`.

Only a `SENSOR_PREFLIGHT_STATUS=GO` result permits transition to Execution 01.

---

# Mandatory setup acceptance before preflight

```text
[ ] EMU-01 and SEC-02 are physically labeled
[ ] both RAK4631 boards can be programmed by USB
[ ] every A-copy direct sensor works
[ ] every B-copy direct sensor works
[ ] EMU-01 reads all seven direct sensor types together
[ ] RAK1906 stabilization/burn-in requirement completed
[ ] soil calibration method recorded
[ ] rain dry -> wet -> dry behavior proven
[ ] both light sensors use separate field names
[ ] final EMU-01 firmware uploaded
[ ] payload v2 = 46 bytes
[ ] full-sensor validity bitmap = 0x007F before normal counted runs
[ ] EMU-01 joins ChirpStack using OTAA
[ ] source serial values match ChirpStack decoder values
[ ] one reading reaches TimescaleDB
[ ] one selected event reaches valid Fabric evidence
[ ] SEC-02 contains no EMU-01 AppKey/session keys
```

After this setup checklist passes, continue to [preflight/00-README.md](preflight/00-README.md). Do **not** enter counted execution until the preflight GO/NO-GO manual produces `SENSOR_PREFLIGHT_STATUS=GO`.
