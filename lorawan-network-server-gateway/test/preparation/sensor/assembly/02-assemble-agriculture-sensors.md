# Sensor Assembly 2 - Install Every Agriculture Kit Sensor

This procedure installs the permanent A-set on EMU-01 and defines the temporary B-set verification profiles for SEC-02.

Power must be **OFF** whenever a module is added, removed, or moved.

---

# Step 1 - Label the two copies

Lay out and label:

```text
SOIL-A / SOIL-B
UV-A / UV-B
BARO-A / BARO-B
LIGHT-VEML-A / LIGHT-VEML-B
LIGHT-OPT-A / LIGHT-OPT-B
ENV-A / ENV-B
RAIN-A / RAIN-B
```

A-set stays on EMU-01.
B-set is verified on SEC-02.

---

# Step 2 - Know which connector family each module uses

```text
SENSOR SLOT modules
  RAK12011  BARO
  RAK12010  LIGHT-VEML
  RAK12019  UV
  RAK1903   LIGHT-OPT
  RAK1906   ENV

IO SLOT modules
  RAK12023  -> RAK12035 SOIL
  RAK12005  -> RAK12030 RAIN
```

Do not mount an IO module in a Sensor slot merely because a connector seems similar.

---

# Step 3 - Use the fixed RAK19001 map and verify it in Pin Mapper

Open [02a-rak19001-fixed-slot-map.md](02a-rak19001-fixed-slot-map.md) and use this permanent assignment:

```text
Sensor A = RAK1903
Sensor B = EMPTY / NA
Sensor C = RAK12019
Sensor D = RAK12011
Sensor E = RAK1906
Sensor F = RAK12010
WisIO 1  = RAK12023 -> RAK12035
WisIO 2  = RAK12005 -> RAK12030
```

Do not improvise a different slot because another connector happens to fit.

Then:

1. open the current WisBlock Pin Mapper;
2. select `RAK19001` and `RAK4631`;
3. enter exactly the A-F and WisIO assignments above;
4. select `NA` / unused for Sensor B;
5. inspect every highlighted pin/conflict indication;
6. require no unresolved conflict;
7. save the accepted mapping as `sensor-pin-map.txt` and, when practical, retain a screenshot/export.

The fixed assignment is designed around these GPIO roles:

```text
WB_IO1 -> RAK1903 interrupt
WB_IO2 -> shared 3V3_S power control
WB_IO3 -> RAK12019 interrupt
WB_IO4 -> RAK12023 soil connector
WB_IO5 -> RAK12011 interrupt/output
WB_IO6 -> RAK12005 rain output
```

RAK1906 and RAK12010 occupy E/F because their normal measurements use I2C without consuming the E/F slot GPIOs that would otherwise collide with `WB_IO4`/`WB_IO6`.

---

# Step 4 - Build the permanent EMU-01 A-set

Permanent layout:

```text
                       RAK19001 / EMU-01

       SENSOR SLOTS                         WISIO SLOTS

  A -> RAK1903 OPT3001                WisIO 1 -> RAK12023 -> SOIL-A RAK12035
  B -> EMPTY / NA                     WisIO 2 -> RAK12005 -> RAIN-A RAK12030
  C -> RAK12019 UV
  D -> RAK12011 BAROMETER
  E -> RAK1906 BME680
  F -> RAK12010 VEML7700

                     CPU -> RAK4631 Core A
                              │
                              └──> LoRa antenna
```

This is now the project baseline, not merely a starting suggestion. The saved Pin Mapper configuration must match it before power-up.

## Step 4A - Install LIGHT-OPT-A / RAK1903 in Sensor A

1. Disconnect all power.
2. Locate Sensor Slot A from the RAK19001 silkscreen.
3. Install RAK1903 in A.
4. Align and fully seat the WisConnector.
5. Install the retaining screw.
6. When the mechanical build permits, use the outward-facing Slot-A orientation so the OPT3001 is not shaded by the base/core.
7. Keep the light-sensitive surface unobstructed.

## Step 4B - Leave Sensor B empty

Do not install a Sensor module in B for the permanent EMU-01 build. Slot B maps the slot GPIO to `WB_IO2`, which this project reserves for `3V3_S` power control.

## Step 4C - Install UV-A / RAK12019 in Sensor C

1. Install RAK12019 specifically in Sensor C.
2. Seat and secure the module.
3. Its interrupt maps to `WB_IO3` in this layout.
4. When mechanically practical, use the outward-facing Slot-C orientation.
5. Keep the UV optical surface clear of cables, tape, antenna leads, and opaque enclosure material.

## Step 4D - Install BARO-A / RAK12011 in Sensor D

1. Install RAK12011 specifically in Sensor D.
2. Seat and secure the module.
3. Its digital output/interrupt maps to `WB_IO5`.
4. Keep its pressure sensing area open to ambient air.

## Step 4E - Install ENV-A / RAK1906 in Sensor E

1. Install RAK1906 specifically in Sensor E.
2. Seat and secure the module.
3. The normal BME680 measurement path uses I2C and does not need the Slot-E `WB_IO4` line.
4. Leave airflow around the sensor.
5. Keep it away from direct MCU/regulator heat as much as the enclosure allows.

## Step 4F - Install LIGHT-VEML-A / RAK12010 in Sensor F

1. Install RAK12010 specifically in Sensor F.
2. Seat the connector fully.
3. Install the screw.
4. Its normal VEML7700 measurement uses I2C and does not need the Slot-F `WB_IO6` line.
5. Keep its optical surface exposed to the intended room/environment light.

Both light sensors are required and remain separate payload fields.

## Step 4G - Install SOIL-A / RAK12023 + RAK12035 in WisIO 1

1. Use project `WisIO Slot 1` on the RAK19001.
2. Seat and screw down RAK12023.
3. Connect **one** RAK12035 probe.
4. Provide cable strain relief.
5. Keep connector electronics dry.

## Step 4H - Install RAIN-A / RAK12005 + RAK12030 in WisIO 2

1. Use project `WisIO Slot 2` on the RAK19001.
2. Seat and secure RAK12005.
3. Attach the RAK12030 sensing pad.
4. Route the pad away from the base electronics.
5. Only the intended sensing pad will receive controlled water during testing.

---

# Step 5 - Inspect the completed EMU-01 assembly

```text
[ ] RAK4631 in CPU slot
[ ] BARO-A installed
[ ] LIGHT-VEML-A installed
[ ] UV-A installed in mapper-approved position
[ ] LIGHT-OPT-A installed
[ ] ENV-A installed
[ ] SOIL-A RAK12023 + one RAK12035 installed
[ ] RAIN-A RAK12005 + RAK12030 installed
[ ] Pin Mapper arrangement saved
[ ] optical sensors unobstructed
[ ] BME680 has airflow
[ ] wet probe/pad separated from main electronics
[ ] LoRa antenna still connected correctly
```

Do not power EMU-01 yet. First complete the pre-power manual.

---

# Step 6 - Build SEC-02 Profile A for B-copy verification

Open [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md) and use its exact RAK19007 map:

```text
           SEC-02 PROFILE A

Sensor A -> LIGHT-OPT-B / RAK1903
Sensor B -> LIGHT-VEML-B / RAK12010
Sensor C -> UV-B / RAK12019
Sensor D -> BARO-B / RAK12011
IO       -> RAK12023 -> one SOIL-B / RAK12035
```

Why Sensor B is VEML-B: `WB_IO2` controls the shared `3V3_S` rail. RAK12010 is powered from `3V3_S` and communicates by I2C without using a sensor interrupt, so it can occupy B without consuming `WB_IO2` as an interrupt. RAK12019 and RAK12011 are placed in C and D, where their interrupt paths use `WB_IO3` and `WB_IO5`.

Procedure:

1. disconnect USB/battery/solar;
2. confirm SEC-02 LoRa antenna remains connected;
3. install exactly A=RAK1903, B=RAK12010, C=RAK12019, D=RAK12011;
4. install SOIL-B RAK12023 in the single IO slot;
5. connect exactly one RAK12035;
6. install all retaining screws;
7. run the complete **SEC-02 Profile A Pin Mapper procedure** in [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md): select `WisBase=RAK19007`, `WisCore=RAK4631`, enter A=RAK1903, B=RAK12010, C=RAK12019, D=RAK12011, and the single IO=RAK12023; set every unused mapper field to `NA`;
8. inspect the mapper output rather than merely confirming that the dropdowns accepted the modules; verify the expected `WB_IO1/2/3/4/5` ownership and investigate every yellow/warning indication;
9. require **no unresolved pin/function conflict**. This matters because physical connector compatibility does not prove that two modules are not trying to use the same GPIO for incompatible functions;
10. save `SEC-02-profile-A-pin-map.txt` plus a screenshot/export when practical;
11. do not power until [03-pre-power-check-and-troubleshooting.md](03-pre-power-check-and-troubleshooting.md) passes.

---

# Step 7 - Convert SEC-02 to Profile B only after Profile A is tested

Do **not** rebuild while powered. After all Profile A readings are saved, follow the full power-off/rebuild procedure in [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md).

```text
           SEC-02 PROFILE B

Sensor A -> ENV-B / RAK1906
Sensor B -> EMPTY
Sensor C -> EMPTY
Sensor D -> EMPTY
IO       -> RAK12005 -> RAIN-B / RAK12030
```

After Profile A readings are saved:

1. disconnect USB, battery, and solar;
2. remove and store all Profile A sensor/IO modules under their B labels;
3. install ENV-B RAK1906 in Sensor A;
4. leave Sensor B-D empty;
5. install RAIN-B RAK12005 in the IO slot;
6. attach RAIN-B RAK12030;
7. secure everything;
8. rerun Pin Mapper and save `SEC-02-profile-B-pin-map.txt`;
9. run the pre-power inspection again;
10. test ENV-B and RAIN-B;
11. save the evidence;
12. after both pass, power off and strip the temporary B sensors so SEC-02 returns to the RAK19007 + Core B + LoRa-antenna security baseline documented in Sensor Assembly 2B.

---

# Step 8 - Handle the interface modules separately

Inventory:

```text
RAK5802  RS485
RAK5801  4-20 mA
RAK13010 SDI-12
```

If no compatible external instrument exists:

```text
module present = yes
physical inspection = pass/fail
external instrument = not supplied
measurement = not applicable
```

Do not manufacture fake values.

If external probes are available, create a separate mapper-approved test profile and record the instrument model and electrical requirements before connecting it.

---

# Final physical state before normal counted tests

```text
EMU-01
  complete A-set remains installed
  final sensor firmware runs continuously

SEC-02
  B-copy verification evidence already completed
  only hardware needed for the security condition remains installed
  never receives EMU-01 legitimate keys
```

## Next

Continue to [03-pre-power-check-and-troubleshooting.md](03-pre-power-check-and-troubleshooting.md).
