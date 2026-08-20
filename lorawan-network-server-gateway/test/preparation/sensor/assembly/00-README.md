# WisBlock Agriculture Kit Assembly - Start Here

This folder is the physical and software bring-up path for the two Agriculture Kit RAK4631 nodes.

Do the files in numerical order.

## Folder architecture

```text
assembly/
│
├── 01-assemble-minimum-test-nodes.md
│      RAK4631 + base boards + LoRa antennas
│
├── 02-assemble-agriculture-sensors.md
│      identify A/B sensor sets and install the A-set
│
├── 02a-rak19001-fixed-slot-map.md
│      exact EMU-01 Sensor A-F + WisIO map
│      GPIO ownership + Pin Mapper values
│
├── 02b-rak19007-sec02-fixed-profiles.md
│      exact SEC-02 RAK19007 Sensor A-D + IO maps
│      Profile A / Profile B / final stripped security baseline
│
├── 03-pre-power-check-and-troubleshooting.md
│      mechanical / slot / RF / power gate
│
├── 04-verify-all-sensors.md
│      Arduino IDE + RAK BSP
│      all A/B sensor verification
│      integrated sensor acceptance
│
├── 04a-first-time-arduino-operator-walkthrough.md
│      first-time Arduino IDE clicks
│      guided tests + error meanings + pass/fail gates
│
└── 04b-emu01-sec02-code-reference.md
       authoritative copy/paste Arduino sketches
       EMU-01 + SEC-02 sanity and sensor test code
       no chat-only accepted test code
```

After all assembly/verification stages pass, continue to [../01-configure-rak4631-emulators.md](../01-configure-rak4631-emulators.md) for the final firmware, LoRaWAN provisioning, decoder, and end-to-end acceptance.

If this is your first time using Arduino IDE, use [04a-first-time-arduino-operator-walkthrough.md](04a-first-time-arduino-operator-walkthrough.md) while working through `04-verify-all-sensors.md`. It contains the exact clicks, known-good serial sketch, first two sensor tests, error meanings, and the reason for each gate.

---

# Hardware architecture

## EMU-01 - permanent full sensor node

```text
                              EMU-01

                       ┌─────────────────────────┐
                       │ RAK19001 base           │
                       │                         │
  RAK1903 OPT3001 ────>│ Sensor A  / WB_IO1     │
  EMPTY ──────────────>│ Sensor B  / WB_IO2     │  reserved for 3V3_S control
  RAK12019 UV ────────>│ Sensor C  / WB_IO3     │
  RAK12011 BARO ──────>│ Sensor D  / WB_IO5     │
  RAK1906 BME680 ─────>│ Sensor E  / I2C only   │
  RAK12010 VEML7700 ──>│ Sensor F  / I2C only   │
                       │                         │
  RAK12023 ───────────>│ WisIO 1 / WB_IO4       │──> RAK12035 soil probe
  RAK12005 ───────────>│ WisIO 2 / WB_IO6       │──> RAK12030 rain pad
                       │                         │
                       │ CPU: RAK4631            │──> LoRa antenna
                       │ USB-C                   │<── programming laptop
                       └─────────────────────────┘
```

The full reasoning, mapper entries, GPIO ownership, and installation rules are in [02a-rak19001-fixed-slot-map.md](02a-rak19001-fixed-slot-map.md).

EMU-01 remains fully assembled for normal operation, integrity, traceability, flooding, and resilience tests.

## SEC-02 - second-copy verification and security node

```text
                    SEC-02 / RAK19007

               ┌──────────────────────────────┐
Profile A ---> │ A = OPT-B                    │
               │ B = VEML-B                   │
               │ C = UV-B                     │
               │ D = BARO-B                   │
               │ IO = RAK12023 -> SOIL-B      │
               └──────────────┬───────────────┘
                              │ power OFF before rebuild
                              ▼
               ┌──────────────────────────────┐
Profile B ---> │ A = ENV-B                    │
               │ B/C/D = EMPTY                │
               │ IO = RAK12005 -> RAIN-B      │
               └──────────────┬───────────────┘
                           │ B-copy evidence complete
                           ▼
               ┌────────────────────────┐
Security ----> │ isolated SEC-02 role   │
               │ no EMU-01 legit keys   │
               └────────────────────────┘
```

The RAK19007 has four Sensor slots (A-D) and one IO slot, so the B-set is verified in two frozen profiles. The exact slot reasoning, `WB_IO2` / `3V3_S` rule, assembly sequence, and final stripped security-node baseline are in [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md).

---

# Required direct-sensor inventory

Label both copies before assembly:

```text
2 x RAK12023 + RAK12035  -> soil moisture + soil temperature
2 x RAK12019             -> UV
2 x RAK12011             -> barometric pressure + temperature
2 x RAK12010             -> VEML7700 ambient light
2 x RAK1903              -> OPT3001 ambient light
2 x RAK1906              -> temperature/humidity/pressure/gas resistance
2 x RAK12005 + RAK12030  -> rain/wet state
```

All fourteen direct-sensor assemblies must be functionally exercised during preparation.

## Interface boards

Also inventory:

```text
2 x RAK5802  RS485
2 x RAK5801  4-20 mA
2 x RAK13010 SDI-12
```

These are interfaces to external instruments, not self-contained environmental sensors. If no compatible external instrument is available, record the boards as present/inspected without fabricating a measurement.

---

# Non-negotiable rules

1. Remove USB, battery, and solar power before installing/removing a WisBlock module.
2. Install RAK4631 only in the CPU slot.
3. Use Sensor modules only in mapper-compatible Sensor slots.
4. Use RAK12023 and RAK12005 only in compatible IO slots.
5. Use the project-fixed RAK19001 map in `02a-rak19001-fixed-slot-map.md`, then run the WisBlock Pin Mapper and require no unresolved conflict before freezing the arrangement.
6. Seat the WisConnector first; only then install the retaining screw.
7. Never use a screw to pull a misaligned connector together.
8. Attach the correct LoRa antenna before enabling the radio.
9. Keep RAK4631/base/IO electronics dry; only intended external probe/pad surfaces are exposed.
10. Use USB-C as the default bench power/programming source.

---

# Assembly decision flow

```text
Module identified correctly?
        │
       no ──> STOP / identify part
        │yes
        ▼
Power disconnected?
        │
       no ──> DISCONNECT ALL POWER
        │yes
        ▼
Correct CPU/Sensor/IO slot?
        │
       no ──> STOP / Pin Mapper
        │yes
        ▼
Connector aligned + seated flat?
        │
       no ──> remove and reseat
        │yes
        ▼
Install screw
        │
        ▼
Pre-power inspection
        │
        ▼
USB power + firmware test
```

## Ready-to-leave-this-folder condition

```text
[ ] both base/core nodes assembled
[ ] all A-set sensors installed on EMU-01
[ ] every B-copy exercised on SEC-02 using the frozen Profile A/Profile B maps
[ ] SEC-02 Profile A and Profile B pin maps/readings saved
[ ] SEC-02 temporary B-copy modules removed after acceptance
[ ] SEC-02 security baseline = RAK19007 + Core B + LoRa antenna, Sensor A-D/IO empty
[ ] Arduino/Rak BSP upload works on both cores
[ ] sensor evidence saved
[ ] no unresolved slot/pin/power fault
```

## Official references

- Agriculture Kit: `https://docs.rakwireless.com/product-categories/wisblock/kit7-agriculture/overview/`
- WisBlock quick start: `https://docs.rakwireless.com/product-categories/wisblock/quickstart/`
- RAK4631: `https://docs.rakwireless.com/product-categories/wisblock/rak4631/quickstart/`
- RAK19001: `https://docs.rakwireless.com/product-categories/wisblock/rak19001/quickstart/`
- RAK19007: `https://docs.rakwireless.com/product-categories/wisblock/rak19007/quickstart/`
- RAK12023 soil interface: `https://docs.rakwireless.com/product-categories/wisblock/rak12023/quickstart/`
- RAK12019 UV: `https://docs.rakwireless.com/product-categories/wisblock/rak12019/quickstart/`
- RAK12011 barometer: `https://docs.rakwireless.com/product-categories/wisblock/rak12011/quickstart/`
- RAK12010 VEML7700 light: `https://docs.rakwireless.com/product-categories/wisblock/rak12010/quickstart/`
- RAK1903 OPT3001 light: `https://docs.rakwireless.com/product-categories/wisblock/rak1903/quickstart/`
- RAK1906 BME680 environment: `https://docs.rakwireless.com/product-categories/wisblock/rak1906/quickstart/`
- RAK12005 rain interface: `https://docs.rakwireless.com/product-categories/wisblock/rak12005/quickstart/`
