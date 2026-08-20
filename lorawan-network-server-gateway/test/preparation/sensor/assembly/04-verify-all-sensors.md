# Sensor Assembly 4 - Install Arduino IDE, Program RAK4631, and Verify Every Sensor

This is the **software bring-up manual**. It starts with a clean laptop and ends with all direct sensors proven functional.

**First time using Arduino IDE?** Keep [04a-first-time-arduino-operator-walkthrough.md](04a-first-time-arduino-operator-walkthrough.md) open beside this file. It gives the exact menu clicks, the known-good TinyUSB/Serial sanity sketch, the RAK1903 and RAK12010 test sketches, what successful compile/upload output means, and troubleshooting for the exact `Serial`/TinyUSB and missing-library errors seen during lab bring-up.

The standard RAK4631 is programmed through the RAKwireless Arduino BSP. Arduino IDE is used during setup, firmware upload, and serial inspection; it does not need to remain open during the actual LoRaWAN experiment.

## Programming architecture

```text
                   SETUP LAPTOP

       ┌────────────────────────────┐
       │ Arduino IDE                │
       │ + RAKwireless Arduino BSP  │
       │ + sensor libraries/examples│
       └─────────────┬──────────────┘
                     │ USB-C
                     ▼
              ┌─────────────┐
              │ RAK4631     │
              │ application │
              └──────┬──────┘
                     │ I2C/GPIO/IO via WisBlock base
          ┌──────────┼──────────┬───────────┐
          ▼          ▼          ▼           ▼
        soil        UV       pressure    other sensors
                     │
                     ▼
              Serial Monitor
              confirms readings
```

---

# Step 1 - Create the evidence folder

On the setup/test laptop create:

```text
chapter4-results/_device-baseline/sensors/
```

Recommended files:

```text
arduino-environment.txt
EMU-01-full-sensor-map.txt
EMU-01-sensor-readings.csv
SEC-02-profile-A-readings.csv
SEC-02-profile-B-readings.csv
soil-calibration-notes.txt
rain-dry-wet-dry.txt
sensor-pin-map.txt
sensor-firmware-build.txt
```

Never put AppKeys/session keys in these files.

---

# Step 2 - Install Arduino IDE

1. Download Arduino IDE from the official Arduino distribution for your operating system.
2. Install it normally.
3. On Windows, use the normal Arduino installer rather than relying on a Microsoft Store build when third-party BSP installation causes problems.
4. Start Arduino IDE.

**Pass:** Arduino IDE opens without an installation error.

---

# Step 3 - Add the RAKwireless board package URL

In Arduino IDE:

1. Open `File -> Preferences` (or the equivalent Settings/Preferences menu on the installed Arduino IDE version).
2. Find `Additional Boards Manager URLs`.
3. Add this RAKwireless Arduino BSP index:

```text
https://raw.githubusercontent.com/RAKwireless/RAKwireless-Arduino-BSP-Index/main/package_rakwireless_index.json
```

4. If another board URL already exists, add the RAK URL as an additional entry instead of deleting the existing one.
5. Save/close Preferences.
6. Restart Arduino IDE if the new board package does not immediately appear.

---

# Step 4 - Install the RAKwireless BSP

1. Open `Tools -> Board -> Boards Manager`.
2. Search for `RAKwireless` or `RAK`.
3. Install the RAKwireless board package used for the standard RAK4631.
4. Record the installed package/BSP version in `arduino-environment.txt`.
5. Close Boards Manager.

Do not update this BSP in the middle of a counted experiment group.

---

# Step 5 - Select the RAK4631 board

Choose the board corresponding to:

```text
WisBlock Core RAK4631 Board
```

The exact Arduino menu nesting can change by IDE/BSP version; the selected board name is what matters.

Record:

```text
Arduino IDE version:
RAKwireless BSP version:
selected board: WisBlock Core RAK4631 Board
```

---

# Step 6 - Connect EMU-01 and identify its port

1. Confirm EMU-01 passed the pre-power inspection.
2. Connect only EMU-01 by USB-C data cable.
3. Open `Tools -> Port`.
4. Note the new serial port that appeared after connecting the board.
5. Select that port.
6. Record the port temporarily in your setup notes.

On Linux the port is commonly under `/dev/ttyACM*` or `/dev/ttyUSB*`; on Windows it appears as a COM port. Do not hard-code a port number because it can change after reset/bootloader mode.

**Stop if:** no new port appears. Return to the USB troubleshooting section in the previous manual.

---

# Step 7 - Prove firmware upload before touching sensor code

Use [04b-emu01-sec02-code-reference.md](04b-emu01-sec02-code-reference.md) as the authoritative copy/paste source for the EMU-01 and SEC-02 Arduino sketches. Do not accept a test that depends on a sketch existing only in chat history. If working code changes during troubleshooting, update the code-reference MD before treating the new result as the baseline.

For a first-time operator, follow [04a-first-time-arduino-operator-walkthrough.md](04a-first-time-arduino-operator-walkthrough.md), Parts 5-8, for the click-by-click process and explanations. The code reference provides the actual sketch that prints `EMU-01 is alive` / `SEC-02 is alive`; the walkthrough explains the three separate gates:

```text
Verify ✓
   ↓
Can the laptop build RAK4631 firmware?
   ↓ PASS
Upload →
   ↓
Can DFU write it to the physical RAK4631?
   ↓ PASS
Serial Monitor @ 115200
   ↓
Did the RAK4631 boot and execute the sketch?
```

For the lab BSP, the beginner guide also records the observed fix for linker errors containing `Adafruit_USBD_CDC` / `Serial`: add `#include <Adafruit_TinyUSB.h>` to the sketch. Treat that as a BSP-specific compatibility fix, not a reason to change hardware.

If upload fails because the normal port cannot enter the bootloader:

```text
1. close any Serial Monitor holding the port
2. double-click the base-board reset button
3. select the bootloader/new port if it changed
4. upload again
```

Do not continue to sensor debugging until `EMU-01 is alive` repeats in Serial Monitor.

---

# Step 8 - Repeat the upload sanity test on SEC-02

1. Disconnect EMU-01.
2. Connect SEC-02 in its current verification profile.
3. identify/select SEC-02's port;
4. upload the same basic known-good sketch;
5. prove it runs;
6. record success.

**Pass condition:** both RAK4631 cores independently accept an Arduino sketch.

---

# Step 9 - Install/use the sensor libraries and examples

Use the current RAKwireless examples/module quick-starts for the installed direct sensors.

For a first-time operator, start with the two guided I2C tests in [04a-first-time-arduino-operator-walkthrough.md](04a-first-time-arduino-operator-walkthrough.md):

```text
1. RAK1903 / OPT3001 in Sensor A
2. RAK12010 / VEML7700 in Sensor F
```

These are intentionally first because both produce an easy physical light-response check. The guide also explains that `fatal error: Light_VEML7700.h: No such file or directory` means the RAKWireless VEML7700 library is missing; it is a compile-time library problem, not a failed physical sensor.

Test one sensor type at a time before blaming the integrated application.

For each sensor test:

```text
1. select correct RAK4631 board
2. select correct USB port
3. open/copy the module's RAK example
4. install any library requested by that example
5. compile
6. upload
7. open Serial Monitor
8. verify initialization succeeds
9. capture a real reading/state transition
10. save the reading in the evidence folder
```

Record library versions used by the accepted build.

---

# Step 10 - Verify SOIL-A and SOIL-B

For each RAK12023 + RAK12035 pair:

1. confirm one probe is connected;
2. upload/run the soil sensor test firmware;
3. start with the probe clean/dry and record a reference;
4. place the probe in the selected soil/sample medium;
5. record soil moisture;
6. record soil temperature;
7. perform/record the calibration method used for the test medium;
8. confirm values change plausibly;
9. save A-copy evidence;
10. repeat for SOIL-B while SEC-02 is in Profile A.

Pass when moisture and temperature both return without initialization failure.

---

# Step 11 - Verify UV-A and UV-B

For each RAK12019:

1. upload/run the UV example/test;
2. record an ambient reading;
3. safely change the sensor's light/UV exposure;
4. record another reading;
5. verify the sensor responds;
6. record whether the firmware exposes a calculated UV index or another vendor-defined UV value;
7. save both A/B evidence.

Do not call a raw value `UV index` unless the selected driver actually returns UV index.

---

# Step 12 - Verify BARO-A and BARO-B

For each RAK12011:

1. initialize the driver;
2. record barometric pressure;
3. record sensor temperature;
4. confirm values are not error/sentinel values;
5. save A/B evidence.

Keep these fields separate from the RAK1906 pressure/temperature fields.

---

# Step 13 - Verify both VEML7700 light modules

For LIGHT-VEML-A and LIGHT-VEML-B:

```text
room light -> record lux
shade sensor -> record lux
brighter safe light -> record lux
```

The direction of change must make sense.

Final field name:

```text
light_veml7700_lux
```

---

# Step 14 - Verify both OPT3001 light modules

Repeat the same room/shade/brighter-light procedure for RAK1903 A/B.

Final field name:

```text
light_opt3001_lux
```

Do not overwrite one light sensor's value with the other in firmware.

---

# Step 15 - Verify ENV-A and ENV-B / RAK1906

For each RAK1906/BME680:

1. initialize the driver;
2. for first use, perform the documented initial burn-in/stabilization procedure;
3. on later starts, allow a short stabilization period before freezing a baseline;
4. record temperature;
5. record humidity;
6. record pressure;
7. record gas resistance;
8. save A/B evidence.

Use separate fields:

```text
environment_temperature_c
environment_humidity_percent
environment_pressure_pa
environment_gas_resistance_ohm
```

---

# Step 16 - Verify RAIN-A and RAIN-B

For each RAK12005 + RAK12030 pair:

```text
DRY
  │ record
  ▼
small controlled water exposure on pad
  │ record WET
  ▼
fully dry pad
  │ record
  ▼
DRY again
```

Keep RAK12005/base/RAK4631 electronics dry.

Pass only when the dry/wet/dry state transition is reproducible.

---

# Step 17 - Run EMU-01 with all A-set sensors simultaneously

After individual tests pass, upload an integrated **sensor bring-up sketch** that initializes all seven sensor types together.

The test loop should print one record containing:

```text
test_sequence
soil_moisture_percent
soil_temperature_c
uv_index or documented UV value
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
```

Integrated architecture:

```text
setup()
  │
  ├─ init SOIL
  ├─ init UV
  ├─ init BARO
  ├─ init VEML
  ├─ init OPT
  ├─ init ENV
  └─ init RAIN
       │
       ▼
loop/sample cycle
       │
       ├─ read all sensors
       ├─ set/clear validity bits
       └─ print one serial record
```

Run at least ten consecutive sample cycles.

A sensor failure must clear its validity bit; do not silently reuse an old value and mark it valid.

---

# Step 18 - Verify all B-copy sensors on SEC-02

Use the exact physical profiles in [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md). Do not move a module while USB, battery, or solar power is connected.

Profile A is:

```text
Sensor A = RAK1903 / LIGHT-OPT-B
Sensor B = RAK12010 / LIGHT-VEML-B
Sensor C = RAK12019 / UV-B
Sensor D = RAK12011 / BARO-B
IO       = RAK12023 -> SOIL-B / RAK12035
```

Profile A must prove:

```text
LIGHT-OPT-B      -> plausible lux + cover/uncover response
LIGHT-VEML-B     -> plausible lux + cover/uncover response
UV-B             -> valid UVI calculation + controlled response evidence
BARO-B           -> pressure + temperature return without init failure
SOIL-B           -> moisture + temperature + recorded calibration/response
```

Save:

```text
SEC-02-profile-A-pin-map.txt
SEC-02-profile-A-readings.csv
```

Then close Serial Monitor, disconnect all power, and rebuild exactly to Profile B:

```text
Sensor A = RAK1906 / ENV-B
Sensor B = EMPTY
Sensor C = EMPTY
Sensor D = EMPTY
IO       = RAK12005 -> RAIN-B / RAK12030
```

Profile B must prove:

```text
ENV-B  -> temperature + humidity + pressure + gas resistance after stabilization
RAIN-B -> dry -> wet -> dry response; wet only the RAK12030 sensing pad
```

Save:

```text
SEC-02-profile-B-pin-map.txt
SEC-02-profile-B-readings.csv
```

After all seven B-copy sensor assemblies pass, power SEC-02 off and remove the temporary sensor/IO modules. The hardware returns to the stripped security baseline:

```text
RAK19007 + RAK4631 Core B + LoRa antenna
Sensor A-D = EMPTY
IO = EMPTY
```

Only after this B-copy gate is complete may the later SEC-02 RUI3/security conversion begin.

---

# Step 19 - Record the programming/sensor baseline

Save:

```text
Arduino IDE version
RAKwireless BSP version
selected RAK4631 board package
sensor library versions
fixed RAK19001 slot map: A=RAK1903, B=NA, C=RAK12019, D=RAK12011, E=RAK1906, F=RAK12010, WisIO1=RAK12023, WisIO2=RAK12005
fixed RAK19007 Profile A map: A=RAK1903-B, B=RAK12010-B, C=RAK12019-B, D=RAK12011-B, IO=RAK12023+RAK12035-B
fixed RAK19007 Profile B map: A=RAK1906-B, B/C/D=NA, IO=RAK12005+RAK12030-B
SEC-02 final security baseline: Sensor A-D=EMPTY, IO=EMPTY, Core B + LoRa antenna remain
Pin Mapper screenshot/export and conflict result for EMU-01 and both SEC-02 profiles
A/B sensor labels
individual sensor evidence
integrated 10-cycle EMU-01 log
```

Do not store LoRaWAN root/session keys.

---

# Sensor acceptance gate

Do not move to final LoRaWAN firmware until:

```text
[ ] Arduino can upload reliably to EMU-01
[ ] Arduino can upload reliably to SEC-02
[ ] SOIL-A and SOIL-B passed
[ ] UV-A and UV-B passed
[ ] BARO-A and BARO-B passed
[ ] LIGHT-VEML-A and B passed
[ ] LIGHT-OPT-A and B passed
[ ] ENV-A and ENV-B passed after stabilization
[ ] RAIN-A and B passed dry/wet/dry
[ ] EMU-01 initializes all seven sensor types together
[ ] ten integrated EMU-01 sample cycles captured
[ ] sensor validity reporting works
[ ] library/BSP versions recorded
```

Then continue to [../01-configure-rak4631-emulators.md](../01-configure-rak4631-emulators.md).

## Official references

- RAK4631 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak4631/quickstart/`
- WisBlock quick start: `https://docs.rakwireless.com/product-categories/wisblock/quickstart/`
- RAKwireless Arduino BSP index: `https://raw.githubusercontent.com/RAKwireless/RAKwireless-Arduino-BSP-Index/main/package_rakwireless_index.json`
- Individual sensor-module quick-start pages listed in the assembly README.
