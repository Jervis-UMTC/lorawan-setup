# Sensor Assembly 2B - Fixed RAK19007 Profiles for SEC-02

This file freezes the **physical sensor positions for SEC-02** while the second Agriculture Kit sensor copies are being verified.

SEC-02 is not the permanent legitimate telemetry node. During preparation it has three states:

```text
RAK19007 + WisBlock Core B
(RAK4631 carrier/core board containing the RAK4630 radio/MCU module)
        |
        +-> Profile A: prove five B-copy sensor assemblies
        |
        +-> POWER COMPLETELY OFF
        |
        +-> Profile B: prove the remaining two B-copy sensor assemblies
        |
        +-> B-copy evidence complete
                 |
                 v
          strip temporary sensors
                 |
                 v
          SEC-02 security node
```

## RAK4630 versus RAK4631 naming

If the metal/shielded module on Core B is marked `RAK4630`, that is expected. RAKwireless defines the complete WisBlock Core assembly as **RAK4631**: it is a RAK4630 stamp module mounted on the WisBlock expansion PCB with the connectors that plug into the RAK19007. Therefore, a working Agriculture Kit core may visibly say `RAK4630` while Arduino IDE and RAK documentation call the complete board `RAK4631`.

For this project, record the physical marking as `RAK4630` if that is what is printed on the installed module, but continue to use **WisBlock Core RAK4631 Board** as the Arduino board target. This naming difference does not change the SEC-02 Sensor A-D / IO slot map.

Do **not** convert Core B to RUI3 before both B-copy profiles are complete. Keep the same Arduino-compatible firmware path already proven on EMU-01 so the same sensor examples can be reused. The RUI3/security conversion happens later in `../01-configure-rak4631-emulators.md`.

---

# 1. RAK19007 connector layout used by this project

The RAK19007 provides:

```text
1 x CPU slot
1 x IO slot
4 x Sensor slots: A, B, C, D
1 x USB-C connector
battery + solar connectors
```

Always identify the connectors from the **RAK19007 silkscreen on the actual board**. Do not assign a slot from memory or from the physical left/right position alone.

For the sensor modules used in this project, the slot GPIO ownership that matters is:

```text
Sensor A -> WB_IO1 interrupt path
Sensor B -> WB_IO2 interrupt path
Sensor C -> WB_IO3 interrupt path
Sensor D -> WB_IO5 interrupt path

WB_IO2 -> also controls the shared 3V3_S switched sensor rail
IO slot -> exposes the WisBlock IO signals used by RAK12023 / RAK12005
```

The shared `WB_IO2` rule is why this project does **not** put an interrupt-using sensor in Sensor B while 3V3_S devices are active. Sensor B is reserved for RAK12010 in Profile A because RAK12010 uses I2C and 3V3_S but has no sensor interrupt connection.

Relevant module restrictions:

```text
RAK12019 UV      -> supported in C/D on the four-slot RAK19007
RAK12011 BARO    -> supported in A/C/D; do not use B
RAK1903 OPT3001  -> A is used here; interrupt maps to WB_IO1
RAK12010 VEML    -> B is used here; I2C + 3V3_S, no interrupt pin
RAK1906 BME680   -> A is used in Profile B; I2C/VDD only
RAK12023 SOIL    -> IO slot only; uses RAK12035 probe
RAK12005 RAIN    -> IO slot only; uses RAK12030 sensing pad
```

If the current WisBlock Pin Mapper reports a real conflict for the exact installed board/module revisions, stop and resolve it before power-up. Do not improvise a different profile without updating this file.

---

# 2. Run the WisBlock Pin Mapper before applying power

The Pin Mapper is a **design check**, not a firmware upload tool. A WisBlock module can physically fit into a connector and still be a bad combination because two modules may expect the same GPIO for incompatible purposes. The mapper checks the selected WisBase, WisCore, Sensor, and IO modules together so these pin-use conflicts can be found before USB power and before sensor debugging.

For this project the check answers one question:

```text
Does the exact SEC-02 hardware profile have a coherent pin assignment?
        |
       yes
        |
        +--> save evidence and continue to pre-power inspection
        |
       no / uncertain
        |
        +--> STOP; do not power and do not move modules randomly
```

## 2.1 Keep SEC-02 unpowered while doing the mapper check

Before opening the mapper, confirm:

```text
[ ] USB-C disconnected
[ ] battery disconnected
[ ] solar disconnected
[ ] Profile A or Profile B already assembled exactly as documented
[ ] physical slot letters were read from the RAK19007 silkscreen
[ ] LoRa antenna remains attached
```

**Why:** the mapper is intended to validate the proposed hardware arrangement. If hardware is being changed while powered, the software check no longer protects against hot-swapping or a wrong physical slot.

## 2.2 Open the official Pin Mapper correctly

1. Open the official RAKwireless **How To Use the WisBlock IO Pin Mapping Tool** guide.
2. Download the current Pin Mapper workbook in `.xlsx` format from that guide.
3. Save a local copy for this test preparation rather than editing the downloaded master copy directly.
4. Open the workbook in **Microsoft Excel**.
5. If Excel opens it in Protected View, choose **Enable Editing** only after confirming the file came from the official RAKwireless source.
6. Do not delete formulas, overwrite calculated cells, or convert the workbook to another format before the check.

RAKwireless specifically recommends Microsoft Excel because alternative spreadsheet applications may not preserve the workbook's formatting and equations correctly.

**Why:** the mapper is formula-driven. A broken formula or unsupported spreadsheet application could make a bad combination appear acceptable or hide the intended warning formatting.

## 2.3 Select the base and core first

In the mapper dropdown fields select:

```text
WisBase = RAK19007
WisCore = RAK4631
```

If the metal/radio module on the physical core is visibly marked `RAK4630`, still select **RAK4631** in the mapper. In this setup, `RAK4630` is the module mounted on the complete WisBlock Core assembly; the WisBlock board selection used by the mapper and Arduino BSP is RAK4631.

**Why select the base first:** the mapper changes the available slot set according to the chosen WisBase. RAK19007 has four Sensor slots A-D and one IO slot, so selecting the wrong base can display slots that do not exist on SEC-02.

**Why select the core:** the usable GPIO and bus connections ultimately come from the WisBlock Core. The same Sensor arrangement cannot be assumed compatible with every possible Core.

## 2.4 Enter SEC-02 Profile A exactly

For the currently assembled Profile A, select:

```text
WisBase  = RAK19007
WisCore  = RAK4631

Sensor A = RAK1903
Sensor B = RAK12010
Sensor C = RAK12019
Sensor D = RAK12011

IO       = RAK12023
```

The workbook may label the single RAK19007 IO selection as `WisIO`, `WisIO 1`, or another single-IO dropdown depending on the mapper revision. Use the **one IO slot actually presented for RAK19007** and record the label shown by that workbook. Do not populate an extra IO field that the physical RAK19007 does not have.

For every unused field that the mapper still exposes, choose:

```text
NA
```

Do not leave a stale module selection from a previous workbook example.

**Why these exact positions:**

```text
A = RAK1903   -> interrupt role uses WB_IO1
B = RAK12010  -> I2C sensor; does not consume WB_IO2 as an interrupt
C = RAK12019  -> interrupt role uses WB_IO3
D = RAK12011  -> interrupt/output role uses WB_IO5
IO = RAK12023 -> soil interface uses WB_IO4 and the switched 3V3_S rail
```

`WB_IO2` must remain available for the RAK19007 switched `3V3_S` sensor-power control. This is the main reason RAK12010 is deliberately placed in Sensor B instead of putting an interrupt-using sensor there.

## 2.5 Read the mapper result instead of only looking for a green screen

After all dropdowns are selected, inspect the complete pin/result area.

RAKwireless notes that **yellow-highlighted pins may indicate a conflict**. Treat yellow as a warning that must be understood, not as something to ignore and not automatically as proof that the whole profile has failed.

For Profile A, manually confirm the resulting ownership is consistent with:

```text
WB_IO1 -> RAK1903 interrupt
WB_IO2 -> shared 3V3_S power control
WB_IO3 -> RAK12019 interrupt
WB_IO4 -> RAK12023 soil interface
WB_IO5 -> RAK12011 interrupt/output
WB_IO6 -> unused in Profile A

I2C     -> shared by the compatible I2C sensors
```

A **real unresolved conflict** for this project includes any of these conditions:

```text
the same WB_IO pin is required simultaneously for two incompatible functions
RAK12011 is shown trying to consume WB_IO2 in Sensor B
an installed module is not supported in the selected physical slot
mapper compatibility information disappears because a nonexistent slot was populated
selected hardware in the workbook does not match the actual RAK19007 assembly
```

A shared I2C bus by itself is not automatically a conflict; multiple I2C devices are expected to share SDA/SCL when their devices and addresses are compatible. The purpose is to identify incompatible GPIO ownership, not to demand that every module have a completely private bus.

## 2.6 What to do if the mapper warns about something

Do not immediately move modules. Use this sequence:

```text
warning / yellow / unexpected pin
        |
        v
re-check WisBase = RAK19007
        |
        v
re-check WisCore = RAK4631
        |
        v
re-check A/B/C/D/IO dropdown values
        |
        v
set every unused field to NA
        |
        v
compare warning with expected WB_IO1..WB_IO6 ownership
        |
        +--> understood and compatible -> document why
        |
        +--> true/uncertain conflict -> STOP before USB power
```

If a conflict remains uncertain, save a screenshot of the mapper and record the exact highlighted pin/module combination. Do not solve it by trial-and-error hot swapping.

## 2.7 Save Profile A Pin Mapper evidence

When Profile A has no unresolved conflict, save:

```text
chapter4-results/_device-baseline/sensors/SEC-02-profile-A-pin-map.txt
```

Record at minimum:

```text
node=SEC-02
base=RAK19007
core=RAK4631
physical_core_marking=RAK4630_if_present
profile=A
Sensor_A=RAK1903
Sensor_B=RAK12010
Sensor_C=RAK12019
Sensor_D=RAK12011
IO=RAK12023+RAK12035
WB_IO1=RAK1903_INT
WB_IO2=3V3_S_CONTROL
WB_IO3=RAK12019_INT
WB_IO4=RAK12023_SOIL
WB_IO5=RAK12011_INT
WB_IO6=UNUSED
mapper_warning_notes=<NONE or documented understood warning>
mapper_conflicts=NONE
mapper_workbook_version_or_date=<record what is available>
```

Also save a screenshot/export of the completed mapper when practical. The screenshot is useful because it proves the dropdown choices and warning state that produced the text record.

Do **not** write `mapper_conflicts=NONE` merely because the workbook opened successfully. Write it only after the selected modules and pin ownership have been inspected.

## 2.8 Profile B Pin Mapper procedure

After Profile A sensor testing is finished and **all power is removed**, rebuild to Profile B first. Then reopen a clean mapper copy or clear the Profile A selections before entering:

```text
WisBase  = RAK19007
WisCore  = RAK4631

Sensor A = RAK1906
Sensor B = NA
Sensor C = NA
Sensor D = NA

IO       = RAK12005
```

Expected Profile B ownership is:

```text
WB_IO2 -> shared 3V3_S power control
WB_IO6 -> RAK12005 rain digital output
I2C    -> RAK1906 BME680
A/C/D interrupt roles -> unused in this profile
```

Save the result separately as:

```text
chapter4-results/_device-baseline/sensors/SEC-02-profile-B-pin-map.txt
```

Never overwrite the Profile A evidence with Profile B. The two files prove that the two intentionally different SEC-02 hardware configurations were each checked before power-up.

## 2.9 Pin Mapper PASS gate

Only continue to USB power when the active profile can truthfully satisfy:

```text
[ ] WisBase selection matches RAK19007
[ ] WisCore selection matches RAK4631
[ ] every physical Sensor slot matches the mapper dropdown
[ ] the single physical IO module matches the mapper
[ ] unused mapper fields are NA
[ ] expected WB_IO ownership is understood
[ ] every yellow/warning indication was inspected
[ ] no unresolved pin/function conflict remains
[ ] profile-specific text evidence was saved
[ ] screenshot/export retained when practical
```

**Why this gate exists:** it separates mechanical success from electrical/logical compatibility. `Assembly complete` proves the modules are mounted; `Pin Mapper PASS` proves the selected combination is coherent enough to proceed to controlled power-up.

Official Pin Mapper references:

- WisBlock Pin Mapper guide: `https://learn.rakwireless.com/hc/en-us/articles/26743306645143-How-To-Use-the-WisBlock-IO-Pin-Mapping-Tool`
- RAK19007 Quick Start / 3V3_S behavior: `https://docs.rakwireless.com/product-categories/wisblock/rak19007/quickstart/`

---

# 3. Frozen SEC-02 Profile A

Profile A verifies:

```text
LIGHT-OPT-B
LIGHT-VEML-B
UV-B
BARO-B
SOIL-B
```

Use this exact map:

```text
                   RAK19007 / SEC-02 PROFILE A

          SENSOR SLOTS                         IO SLOT

  A -> RAK1903 OPT3001-B                IO -> RAK12023
       ambient light                          |
       INT -> WB_IO1                          +--> RAK12035 SOIL-B

  B -> RAK12010 VEML7700-B                    I2C + WB_IO4
       ambient light
       I2C + 3V3_S only
       NO interrupt on WB_IO2

  C -> RAK12019 UV-B
       LTR390
       INT -> WB_IO3

  D -> RAK12011 BARO-B
       LPS33HW pressure + temperature
       INT -> WB_IO5

  CPU -> RAK4631 Core B
  LoRa RF -> LoRa antenna remains attached
  USB-C -> programming / Serial only during verification
```

Expected project signal ownership:

```text
WB_IO1 = RAK1903 interrupt
WB_IO2 = shared 3V3_S power control
WB_IO3 = RAK12019 interrupt
WB_IO4 = RAK12023 soil connector
WB_IO5 = RAK12011 interrupt/output
WB_IO6 = unused in Profile A
```

## Why this map is frozen

```text
Slot A -> OPT-B
          gives OPT3001 its normal WB_IO1 interrupt path

Slot B -> VEML-B
          safe use of B because RAK12010 has no interrupt pin;
          WB_IO2 stays dedicated to 3V3_S power control

Slot C -> UV-B
          RAK12019 requires a compatible C/D-style slot;
          C gives it WB_IO3

Slot D -> BARO-B
          RAK12011 must not use B;
          D gives it WB_IO5

IO     -> SOIL-B
          RAK12023 is a WisBlock IO module, not a Sensor-slot module;
          one RAK12035 probe only
```

---

# 3. Assemble Profile A step by step

Do not connect USB, battery, or solar while changing modules.

1. Put SEC-02 on a clean, dry, non-conductive surface.
2. Confirm the physical label says `SEC-02` and the base is `RAK19007`.
3. Confirm RAK4631 **Core B** is fully seated in the CPU slot.
4. Confirm the LoRa antenna is attached to the RAK4631 LoRa RF connector. Leave it connected throughout preparation so RF testing is never performed without an antenna later.
5. Locate the RAK19007 Sensor A, B, C, D and IO silkscreen labels.
6. Install `LIGHT-OPT-B / RAK1903` in **Sensor A**.
7. Install `LIGHT-VEML-B / RAK12010` in **Sensor B**.
8. Install `UV-B / RAK12019` in **Sensor C**.
9. Install `BARO-B / RAK12011` in **Sensor D**.
10. Install `SOIL-B / RAK12023` in the single **IO slot**.
11. Connect exactly **one** `SOIL-B / RAK12035` probe to the RAK12023.
12. Secure every installed WisBlock module with the correct retaining screw. The screw holds a seated module; it must never be used to force a connector together.
13. Route the soil cable so it cannot pull on the IO connector.
14. Keep the RAK12023, base board, RAK4631, and cable connector dry. Only the documented sensing area of the RAK12035 is exposed during its controlled wet calibration/response test.
15. Keep both light-sensitive surfaces unobstructed.
16. Inspect the board from the side: all modules must sit level and fully seated.
17. Check for loose screws, metal debris, trapped wires, or a module installed one connector position off.
18. Run the RAK19007 + Profile A arrangement through the current WisBlock Pin Mapper and require no unresolved conflict.
19. Save the accepted map as `SEC-02-profile-A-pin-map.txt` and, when practical, keep a screenshot/export.
20. Only after the pre-power checks in `03-pre-power-check-and-troubleshooting.md` pass may USB-C be connected.

Profile A physical gate:

```text
[ ] A = RAK1903 / OPT-B
[ ] B = RAK12010 / VEML-B
[ ] C = RAK12019 / UV-B
[ ] D = RAK12011 / BARO-B
[ ] IO = RAK12023 + exactly one RAK12035 / SOIL-B
[ ] Core B seated
[ ] LoRa antenna attached
[ ] all screws installed
[ ] no loose conductive material
[ ] main electronics dry
[ ] Pin Mapper has no unresolved conflict
[ ] USB/battery/solar still disconnected
```

### Current lab status - 2026-08-19

Operator confirmed that **SEC-02 Profile A mechanical assembly is complete**. This confirmation means the physical modules have been installed; it does **not** by itself mark the electrical/pre-power gate or Pin Mapper conflict check as passed.

Current transition state:

```text
SEC-02 Profile A mechanical assembly = COMPLETE (operator-confirmed)
Pre-power visual/electrical inspection   = NOT SEPARATELY RECORDED
Pin Mapper conflict result              = PASS (operator-confirmed; no conflict reported)
USB first-power / Core B execution      = PASS (operator-confirmed: `SEC-02 is alive`)
RAK1903-B / Sensor A                    = PASS (operator-confirmed; functional light response good)
RAK12010-B / Sensor B                   = PASS (operator-confirmed; functional light response good)
RAK12011-B / Sensor D                   = PASS (operator-confirmed; 31.68-31.69 C, 1018.59-1018.64 hPa)
RAK12019-B / Sensor C                   = PASS (operator-confirmed; UV functional test passed)
RAK12023 + RAK12035-B / IO              = PASS (operator-confirmed; soil diagnostic/calibration/response good)
SEC-02 Profile A                        = PASS
RAK1906-B / Profile B Sensor A          = PASS (operator-confirmed)
RAK12005 + RAK12030-B / Profile B IO    = PASS (operator-confirmed; dry -> wet -> dry response good)
SEC-02 Profile B                        = PASS (operator-confirmed)
B-copy sensor functional verification   = COMPLETE
Next requested SEC-02 action            = temporary legitimate ChirpStack OTAA + real-sensor uplink using SEC-02-only credentials
Security conversion                      = AFTER the temporary legitimate SEC-02 test
Credential rule                          = never copy EMU-01 AppKey/session keys to SEC-02
```

Do not mark Profile A fully PASS until the remaining checks below are completed and evidence is recorded.

---

# 4. Power and verify Profile A

Use [04b-emu01-sec02-code-reference.md](04b-emu01-sec02-code-reference.md) for every SEC-02 Arduino sanity/sensor sketch. The repository copy is authoritative; do not rely on chat-only code.

Initial power is **USB-C only**. Do not add battery or solar during bench verification.

After the pre-power gate passes:

1. connect a known-good USB-C data cable;
2. verify the laptop detects Core B;
3. upload the known-good Arduino/TinyUSB sanity sketch if Core B has not already passed it;
4. verify the five Profile A sensor assemblies using `04-verify-all-sensors.md`;
5. prove a physical response where applicable instead of accepting a static number only;
6. save readings as `SEC-02-profile-A-readings.csv`;
7. record PASS/FAIL separately for OPT-B, VEML-B, UV-B, BARO-B, and SOIL-B;
8. do not provision EMU-01's AppKey or session keys to perform these local sensor checks.

Profile A is complete only when all five B-copy assemblies have evidence.

---

# 5. Power completely off before Profile B

Do not hot-swap WisBlock modules.

Use this sequence:

```text
close Serial Monitor
      |
disconnect USB-C
      |
confirm battery disconnected
      |
confirm solar disconnected
      |
wait several seconds
      |
remove Profile A modules
      |
build Profile B
```

Keep each removed B-copy labeled so it cannot be confused with the permanent A-set on EMU-01.

---

# 6. Frozen SEC-02 Profile B

Profile B verifies the two remaining B-copy sensing assemblies:

```text
ENV-B
RAIN-B
```

Use this exact map:

```text
                   RAK19007 / SEC-02 PROFILE B

          SENSOR SLOTS                         IO SLOT

  A -> RAK1906 BME680-B                 IO -> RAK12005
       temperature                            |
       humidity                               +--> RAK12030 RAIN-B
       pressure
       gas resistance                         OUT -> WB_IO6
       I2C/VDD only

  B -> EMPTY
  C -> EMPTY
  D -> EMPTY

  CPU -> RAK4631 Core B
  LoRa RF -> LoRa antenna remains attached
  USB-C -> programming / Serial only during verification
```

Profile B expected signal ownership:

```text
WB_IO2 = available for normal 3V3_S control if required
WB_IO6 = RAK12005 rain digital output
A-slot GPIO is not required by RAK1906; BME680 uses I2C/VDD
```

## Assemble Profile B

1. confirm all power is removed;
2. confirm Profile A modules have been removed and stored under their B labels;
3. install `ENV-B / RAK1906` in **Sensor A**;
4. leave Sensor B empty;
5. leave Sensor C empty;
6. leave Sensor D empty;
7. install `RAIN-B / RAK12005` in the **IO slot**;
8. attach `RAIN-B / RAK12030` to the RAK12005;
9. secure RAK1906 and RAK12005 with the correct screws;
10. route the RAK12030 sensing pad away from the RAK19007 electronics;
11. keep RAK12005, RAK19007, RAK4631, and all connectors dry;
12. only the RAK12030 sensing pad is intentionally wetted during the controlled rain test;
13. confirm the RAK1906 has reasonable airflow and is not covered by tape, foam, or a cable;
14. rerun the WisBlock Pin Mapper for Profile B and require no unresolved conflict;
15. save the result as `SEC-02-profile-B-pin-map.txt`;
16. repeat the full pre-power inspection before connecting USB-C.

Profile B physical gate:

```text
[ ] A = RAK1906 / ENV-B
[ ] B = EMPTY
[ ] C = EMPTY
[ ] D = EMPTY
[ ] IO = RAK12005 + RAK12030 / RAIN-B
[ ] Core B seated
[ ] LoRa antenna attached
[ ] all installed modules screwed down
[ ] rain pad separated from electronics
[ ] BME680 exposed to airflow
[ ] Pin Mapper has no unresolved conflict
[ ] USB/battery/solar still disconnected
```

---

# 7. Power and verify Profile B

After the Profile B pre-power gate passes:

1. connect USB-C only;
2. verify Core B still enumerates normally;
3. test `ENV-B / RAK1906` with the same accepted BME680 procedure used for the A-copy;
4. allow the required stabilization/burn-in behavior instead of judging the first reading immediately;
5. test `RAIN-B / RAK12005 + RAK12030` using a controlled `dry -> wet -> dry` response;
6. wet only the RAK12030 sensing pad;
7. dry the pad after the wet phase and prove the signal returns to dry;
8. save readings as `SEC-02-profile-B-readings.csv`;
9. mark ENV-B and RAIN-B independently PASS/FAIL.

Do not start the security-node conversion until both pass.

---

# 8. B-copy acceptance record

Before stripping SEC-02, require:

```text
[ ] LIGHT-OPT-B passed
[ ] LIGHT-VEML-B passed
[ ] UV-B passed
[ ] BARO-B passed
[ ] SOIL-B moisture + temperature passed
[ ] ENV-B temperature + humidity + pressure + gas passed
[ ] RAIN-B dry/wet/dry passed
[ ] Profile A pin map saved
[ ] Profile A readings saved
[ ] Profile B pin map saved
[ ] Profile B readings saved
[ ] no B-copy was silently substituted with an A-copy
```

These readings prove that the second physical copies are functional before SEC-02 changes role. They are not counted dissertation telemetry from EMU-01.

---

# 9. Convert the hardware to the SEC-02 security baseline

Only after the B-copy acceptance record is complete:

1. close Serial Monitor;
2. disconnect USB-C;
3. confirm battery and solar are disconnected;
4. remove `ENV-B / RAK1906` from Sensor A;
5. remove `RAIN-B / RAK12005 + RAK12030` from the IO slot;
6. store all B-copy sensors under their labels;
7. leave Sensor A empty;
8. leave Sensor B empty;
9. leave Sensor C empty;
10. leave Sensor D empty;
11. leave the IO slot empty;
12. keep RAK4631 Core B installed;
13. keep the LoRa antenna attached;
14. label the assembly `SEC-02 - SECURITY - NO LEGIT EMU-01 KEYS`.

Final security hardware baseline:

```text
RAK19007 / SEC-02

CPU      = RAK4631 Core B
Sensor A = EMPTY
Sensor B = EMPTY
Sensor C = EMPTY
Sensor D = EMPTY
IO       = EMPTY
LoRa RF  = LoRa antenna attached
```

This stripped baseline minimizes variables during later invalid-OTAA and raw-LoRa/P2P security fixtures. A security experiment may add only the hardware explicitly required by that experiment.

After this hardware state is recorded, continue to the SEC-02 security preparation in `../01-configure-rak4631-emulators.md`. If the security fixture requires RUI3, conversion occurs **now**, after B-copy verification, not before.

Never provision SEC-02 with EMU-01's legitimate AppKey or legitimate session keys.

---

# 10. Troubleshooting map

```text
Core B does not enumerate over USB
        |
        +-> remove power
        +-> verify RAK4631 seating
        +-> try known-good USB-C data cable
        +-> test Core B with all Sensor/IO modules removed

one Profile A sensor fails to initialize
        |
        +-> verify exact A/B/C/D position
        +-> verify 3V3_S is enabled where required
        +-> verify I2C address / library / example
        +-> reseat only after power is removed
        +-> rerun Pin Mapper; do not move modules randomly

UV-B fails
        |
        +-> confirm RAK12019 is in C, not A/B

BARO-B fails / slot conflict
        |
        +-> confirm RAK12011 is in D, never B

SOIL-B fails
        |
        +-> confirm RAK12023 is in IO, not Sensor slot
        +-> confirm one RAK12035 only
        +-> inspect cable / dry connector / calibration state

RAIN-B does not change
        |
        +-> confirm RAK12005 is in IO
        +-> confirm RAK12030 is connected
        +-> read WB_IO6
        +-> wet only the sensing pad

Profile works until modules are changed
        |
        +-> suspect hot-swap / partial seating / wrong rebuilt slot
        +-> power fully off and rebuild from the frozen map
```

---

# 11. Official hardware references

- RAK19007 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak19007/datasheet/`
- RAK19007 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak19007/quickstart/`
- RAK1903 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak1903/datasheet/`
- RAK12010 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12010/datasheet/`
- RAK12019 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12019/datasheet/`
- RAK12011 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12011/datasheet/`
- RAK1906 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak1906/datasheet/`
- RAK12023 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak12023/quickstart/`
- RAK12005 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak12005/quickstart/`

## Next

Run [03-pre-power-check-and-troubleshooting.md](03-pre-power-check-and-troubleshooting.md) for the currently installed SEC-02 profile, then use [04-verify-all-sensors.md](04-verify-all-sensors.md) to collect the B-copy evidence.
