# Sensor Preflight 1 - Hardware and Final Firmware

This preflight proves that the **final frozen EMU-01 hardware and firmware** are healthy before checking the network.

Do not modify sensor slots, libraries, payload layout, or firmware during this preflight unless a fault is found. If you modify them, restart the affected preflight from the beginning.

## Target state

```text
EMU-01
  RAK19001
    │
    ├─ RAK4631 Core A + LoRa antenna
    ├─ SOIL-A
    ├─ UV-A
    ├─ BARO-A
    ├─ LIGHT-VEML-A
    ├─ LIGHT-OPT-A
    ├─ ENV-A
    └─ RAIN-A

firmware
  payload version = 2
  payload length  = 46 bytes
  interval        = 15 seconds
  healthy validity bitmap = 0x007F
```

## Step 1 - Create the preflight record

Create:

```text
chapter4-results/_preflight/sensor/preflight-meta.txt
```

Record non-secret values:

```text
preflight start UTC
EMU-01 DevEUI
RAK19001 / RAK4631 identifiers
firmware/source hash
Arduino BSP version
payload version
payload length
configured interval
approved AS923 plan label
sensor Pin Mapper revision/screenshot reference
```

Do not copy the AppKey into this file.

## Step 2 - Inspect the frozen hardware

With EMU-01 powered off, verify:

```text
[ ] RAK4631 is seated in CPU slot
[ ] LoRa antenna is connected to the LoRa RF connector
[ ] Sensor A = RAK1903
[ ] Sensor B = EMPTY / NA
[ ] Sensor C = RAK12019
[ ] Sensor D = RAK12011
[ ] Sensor E = RAK1906
[ ] Sensor F = RAK12010
[ ] WisIO 1 = RAK12023 + one RAK12035
[ ] WisIO 2 = RAK12005 + RAK12030
[ ] mapper GPIO roles are WB_IO1=OPT INT, WB_IO2=3V3_S, WB_IO3=UV INT, WB_IO4=SOIL, WB_IO5=BARO INT, WB_IO6=RAIN
[ ] all retaining screws are present
[ ] no cable is pinched
[ ] optical sensors are unobstructed
[ ] BME680 has reasonable airflow
[ ] main electronics are dry
[ ] soil/rain external elements are safely routed
```

**NO-GO if:** the physical layout does not match the frozen sensor map.

### SEC-02 security-baseline check

By normal preflight, the B-copy verification profiles should already be complete and their temporary sensors removed. Unless the specific upcoming security fixture explicitly requires another module, require:

```text
[ ] SEC-02 base = RAK19007
[ ] SEC-02 core = RAK4631 Core B
[ ] Sensor A = EMPTY
[ ] Sensor B = EMPTY
[ ] Sensor C = EMPTY
[ ] Sensor D = EMPTY
[ ] IO slot = EMPTY
[ ] LoRa antenna attached
[ ] Profile A and Profile B B-copy evidence already saved
[ ] no EMU-01 legitimate AppKey/session keys present on SEC-02
```

If B-copy verification is not complete, return to [../assembly/02b-rak19007-sec02-fixed-profiles.md](../assembly/02b-rak19007-sec02-fixed-profiles.md) before security preflight.

## Step 3 - Power by USB-C and observe startup

1. Connect EMU-01 to the test laptop with the known-good USB-C data cable.
2. Open the serial terminal at the baud rate used by the final firmware.
3. Reset/restart EMU-01 once.
4. Capture the complete startup sequence.
5. Save it under:

```text
chapter4-results/_preflight/sensor/01-hardware-firmware/emu-01-source.log
```

Require startup evidence that the expected sensor drivers initialize.

**NO-GO if:** the board repeatedly resets, disappears from USB, reports a required sensor initialization failure, or shows abnormal hardware behavior.

## Step 4 - Allow sensor stabilization

Before judging the final readings:

1. allow the RAK1906/BME680 stabilization procedure defined in the sensor setup manual;
2. ensure the soil calibration used by the final firmware is loaded/recorded;
3. make sure the rain pad is in its intended starting state;
4. leave the node stationary enough that troubleshooting is not confused by unnecessary handling.

Do not begin the ten-cycle check while a known stabilization requirement is still active.

## Step 5 - Capture ten consecutive final-firmware cycles

Observe **ten consecutive scheduled cycles** without changing the hardware.

For every cycle record/check:

```text
test_sequence
sensor_uptime_ms
soil_moisture_percent
soil_temperature_c
UV field
barometer_pressure_pa
barometer_temperature_c
light_veml7700_lux
light_opt3001_lux
environment_temperature_c
environment_humidity_percent
environment_pressure_pa
environment_gas_resistance_ohm
rain_wet
sensor_validity_bitmap
send_started / send result indicator
```

The purpose is not to demand identical physical values. The purpose is to prove that every required field is being sampled and associated with the correct sequence.

## Step 6 - Check the validity bitmap

For a healthy complete sample:

```text
bit 0 soil  = 1
bit 1 UV    = 1
bit 2 BARO  = 1
bit 3 VEML  = 1
bit 4 OPT   = 1
bit 5 ENV   = 1
bit 6 RAIN  = 1

0x007F = all required sensor groups valid
```

All ten normal preflight cycles should show `0x007F` unless you are intentionally troubleshooting a sensor fault.

**NO-GO if:** a required validity bit repeatedly clears or the firmware silently reuses stale data as valid.

## Step 7 - Check the 15-second scheduler

Compare the source timestamps/uptime values for the ten cycles.

Expected pattern:

```text
seq N       around T0
seq N+1     around T0 + 15 s
seq N+2     around T0 + 30 s
...
```

Minor execution/timestamp granularity is expected, but the schedule must not progressively stretch because of sensor-read time.

**NO-GO if:** the interval drifts substantially or the device misses scheduled cycles before the network is even considered.

## Step 8 - Check sequence continuity

For the ten-cycle window require:

```text
N
N+1
N+2
N+3
...
N+9
```

No duplicate sequence number and no unexplained reset to an earlier sequence is allowed.

A deliberate reboot before the preflight window is acceptable if it is recorded. An unexplained reboot inside the window is NO-GO.

## Step 9 - Record hardware/firmware PASS

Create:

```text
chapter4-results/_preflight/sensor/01-hardware-firmware/ten-cycle-check.txt
```

Record:

```text
first sequence
last sequence
10/10 cycles observed = yes/no
all validity bitmaps = 0x007F yes/no
15-second scheduling stable = yes/no
unexpected reset = yes/no
hardware map matches baseline = yes/no
result = PASS | NO-GO
notes
```

## Exit condition

Continue to [02-lorawan-chirpstack-preflight.md](02-lorawan-chirpstack-preflight.md) only when:

```text
hardware = PASS
final firmware = PASS
10 consecutive full-sensor cycles = PASS
```
