# Sensor Assembly 3 - Pre-Power Check and Troubleshooting

Run this procedure **every time** a module is installed, removed, or moved.

## Safety flow

```text
            START
              │
              ▼
     Is all power removed?
        │             │
       no            yes
        │             │
        ▼             ▼
 DISCONNECT USB/   Check core
 battery/solar         │
                       ▼
                Check LoRa antenna
                       │
                       ▼
                Check slot mapping
                       │
                       ▼
                Check connectors
                       │
                       ▼
               Any conflict/fault?
                  │          │
                 yes        no
                  │          │
                  ▼          ▼
                 STOP      USB POWER
```

---

# Step 1 - Confirm zero power

```text
USB-C   = disconnected
battery = disconnected
solar   = disconnected
```

Never add/remove a WisBlock module while energized.

---

# Step 2 - Inspect the RAK4631 and LoRa antenna

For the node being checked:

```text
[ ] RAK4631 is in CPU slot
[ ] core is fully seated and level
[ ] correct retaining screw(s) installed
[ ] no conductive debris below board
[ ] LoRa antenna is on labeled LoRa RF connector
[ ] IPEX plug is centered and seated
[ ] antenna cable is not sharply folded or pinched
```

Keep the LoRa antenna connected even during sensor-only firmware testing because later sketches can enable RF.

---

# Step 3 - Check EMU-01 sensor completeness

Before final integrated testing:

```text
[ ] RAK12023 + RAK12035 soil
[ ] RAK12019 UV
[ ] RAK12011 barometer
[ ] RAK12010 VEML7700 light
[ ] RAK1903 OPT3001 light
[ ] RAK1906 environment
[ ] RAK12005 + RAK12030 rain
```

Confirm the fixed map is present exactly:

```text
Sensor A = RAK1903
Sensor B = EMPTY
Sensor C = RAK12019
Sensor D = RAK12011
Sensor E = RAK1906
Sensor F = RAK12010
WisIO 1  = RAK12023 -> RAK12035
WisIO 2  = RAK12005 -> RAK12030
```

Do not power the node if a module is in a different slot.

---

# Step 4 - Check slot rules

1. Compare every module with `02a-rak19001-fixed-slot-map.md` and the saved Pin Mapper result.
2. Confirm RAK1903 is in Sensor A (`WB_IO1` interrupt role).
3. Confirm Sensor B is empty (`WB_IO2` reserved for `3V3_S`).
4. Confirm RAK12019 is in Sensor C (`WB_IO3` interrupt role).
5. Confirm RAK12011 is in Sensor D (`WB_IO5` interrupt/output role).
6. Confirm RAK1906 is in Sensor E and its normal path uses I2C rather than `WB_IO4`.
7. Confirm RAK12010 is in Sensor F and its normal path uses I2C rather than `WB_IO6`.
8. Confirm RAK12023 is in WisIO 1 with only one RAK12035 and owns the project `WB_IO4` soil role.
9. Confirm RAK12005 is in WisIO 2, connected to RAK12030, and owns the project `WB_IO6` rain role.
10. Confirm the saved Pin Mapper result shows no unresolved conflict.

**Stop if:** the mapper shows a conflict or the physical arrangement differs from the saved map.

---

# Step 5 - Inspect mechanical seating

For every installed module:

```text
connector fully seated?
PCB flat/parallel?
retaining screw installed?
no cable trapped underneath?
no exposed conductor touching another board?
```

If any answer is no, keep power off and correct it.

---

# Step 6 - Check sensor exposure

## Soil

```text
RAK12023 electronics = dry
probe cable = strain relieved
only intended probe section contacts soil
```

## Rain

```text
RAK12005/base/core = dry
RAK12030 pad = external and accessible
```

## Optical sensors

RAK12019, RAK12010, and RAK1903 must not be covered by opaque tape, cables, or enclosure walls.

## RAK1906

Leave reasonable airflow and avoid direct heating by nearby electronics when evaluating ambient measurements.

---

# Step 7 - Use USB-C as the first power source

For setup:

```text
Laptop USB
    │
    ▼
USB-C data cable
    │
    ▼
WisBlock base
    │
    ├─ powers RAK4631/sensors
    └─ provides programming + serial logging
```

Do not add battery/solar during initial bring-up.

---

# Step 8 - First power-up

## EMU-01

1. Keep SEC-02 disconnected.
2. Connect a known-good USB-C **data** cable to EMU-01.
3. Observe the board for the first 30-60 seconds.
4. Check for abnormal heat, smell, smoke, unstable LEDs, or repeated USB disconnects.
5. If abnormal, unplug immediately.
6. If stable, confirm the laptop sees a serial/USB device.
7. Do not start LoRaWAN testing yet; first prove programming and sensors in the next manual.

## SEC-02

SEC-02 has two different frozen B-copy profiles. Never apply the EMU-01 A-F map to the RAK19007.

Before Profile A power-up require:

```text
Sensor A = RAK1903 / LIGHT-OPT-B
Sensor B = RAK12010 / LIGHT-VEML-B
Sensor C = RAK12019 / UV-B
Sensor D = RAK12011 / BARO-B
IO       = RAK12023 -> exactly one RAK12035 / SOIL-B
CPU      = RAK4631 Core B
```

Before Profile B power-up require:

```text
Sensor A = RAK1906 / ENV-B
Sensor B = EMPTY
Sensor C = EMPTY
Sensor D = EMPTY
IO       = RAK12005 -> RAK12030 / RAIN-B
CPU      = RAK4631 Core B
```

For either profile:

1. compare the hardware against [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md);
2. confirm USB, battery, and solar were removed while the profile was assembled;
3. confirm the RAK4631 Core B and every installed module are fully seated and screwed down;
4. confirm the LoRa antenna remains attached;
5. confirm no loose screw/debris is under the board;
6. confirm the accepted profile-specific Pin Mapper result has no unresolved conflict. Do not treat `the workbook opened` or `the module appeared in a dropdown` as a PASS. The operator must have selected `RAK19007` + `RAK4631`, entered the exact active A/B/C/D/IO profile, set unused fields to `NA`, inspected every yellow/warning indication, and compared the resulting `WB_IO` ownership with the expected project map in [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md);
7. confirm the profile-specific text record and, when practical, screenshot/export were saved. **Why:** this gives evidence that logical pin compatibility was checked before power was applied, instead of relying only on the fact that the modules physically fit;
8. for Profile A, keep both optical sensors unobstructed and the soil connector electronics dry;
8. for Profile B, keep the RAK1906 exposed to airflow and route the RAK12030 pad away from all electronics;
9. connect USB-C only;
10. observe for abnormal heat, smell, smoke, unstable LEDs, or repeated USB disconnects for the first 30-60 seconds;
11. unplug immediately if anything abnormal occurs.

After Profile A testing, remove USB and all other power **before** rebuilding Profile B.

---

# Troubleshooting decision tree

```text
USB device missing
    │
    ├─> try known-good DATA cable
    │
    ├─> try another laptop USB port
    │
    ├─> double-check RAK4631 seating
    │
    ├─> remove sensor/IO modules
    │       │
    │       └─> test core + base + antenna only
    │
    └─> add modules back one at a time
```

## Module will not sit flat

1. remove all power;
2. remove the screw;
3. lift close to the connector area;
4. inspect both connectors;
5. align again;
6. press connector fully;
7. install screw only after it sits flat.

## Full sensor build fails after adding one module

Return to the last known-good combination, then check:

```text
Pin Mapper conflict
partial connector seating
damaged module
I2C/address/driver initialization problem
firmware pin conflict
power instability
```

Add the suspect module by itself in a compatible slot to separate hardware failure from integration failure.

## Soil value unrealistic

Check:

```text
one RAK12035 per RAK12023
connector seated
RAK12023 in IO slot
calibration performed
soil temperature also readable
```

## Rain does not change

Perform:

```text
dry -> small controlled water exposure -> fully dry
```

Check the IO module, pad connection, threshold/sensitivity, and firmware input.

## UV/light does not respond

Check:

```text
optical surface uncovered
correct Sensor slot
driver initialized
lighting actually changed
VEML7700 and OPT3001 use separate variables
```

## RAK1906 drifts after power-up

Allow the documented initial burn-in and subsequent stabilization time before using it for the baseline.

## Sensors work but LoRaWAN join fails

Do not troubleshoot the sensors again first. Check the RF/network path:

```text
LoRa antenna correct?
RAK4631 radio variant correct?
plain AS923 configuration matches end-to-end (`LORAMAC_REGION_AS923` + ChirpStack/MQTT `as923`)?
not accidentally using AS923-3 on the sensor?
DevEUI/JoinEUI/AppKey correct?
device profile matches firmware?
gateway online and receiving RF?
```

---

# Pre-programming gate

Continue only when:

```text
[ ] USB power is stable
[ ] laptop detects the RAK4631
[ ] LoRa antenna attached
[ ] all modules mechanically secure
[ ] saved Pin Mapper arrangement matches hardware
[ ] no unresolved electrical/mechanical fault
```

Then continue to [04-verify-all-sensors.md](04-verify-all-sensors.md).
