# Sensor Assembly 1 - Build the Two RAK4631 Base Nodes

Do this before installing any Agriculture Kit sensor module.

## Target architecture

```text
             EMU-01                              SEC-02

      LoRa antenna                        LoRa antenna
           │                                   │
           ▼                                   ▼
    ┌───────────────┐                    ┌───────────────┐
    │ RAK4631       │                    │ RAK4631       │
    │ Core A        │                    │ Core B        │
    └───────┬───────┘                    └───────┬───────┘
            │ CPU slot                           │ CPU slot
    ┌───────▼───────┐                    ┌───────▼───────┐
    │ RAK19001      │                    │ RAK19007      │
    │ 6 Sensor      │                    │ 4 Sensor      │
    │ 2 IO          │                    │ 1 IO          │
    └───────────────┘                    └───────────────┘
```

Permanent assignment:

```text
EMU-01 = RAK19001 + Core A
SEC-02 = RAK19007 + Core B
```

### Core-label note: RAK4630 marking is normal

The complete WisBlock Core board is documented by RAKwireless as **RAK4631**, but its main radio/MCU component is the **RAK4630** stamp module. If the installed shield/module visibly says `RAK4630`, do not treat that as a different sensor-core architecture. If it is the WisBlock Core board that plugs directly into the base and is programmable in Arduino IDE as `WisBlock Core RAK4631 Board`, use it exactly as documented here.

Record both names when helpful:

```text
WisBlock Core board: RAK4631
visible radio/MCU module marking: RAK4630
MCU: nRF52840
LoRa transceiver: SX1262
```

Do not swap the cores after credentials are later provisioned.

---

# Step 1 - Prepare the work area

Put these on a non-conductive table:

```text
2 x RAK4631
1 x RAK19001
1 x RAK19007
2 x correct LoRa antennas
WisBlock M1.2 x 3 mm screws
precision screwdriver
2 x known-good USB-C data cables
labels + marker
```

Keep these disconnected:

```text
USB-C
battery
solar
```

**Expected result:** all parts visible and no board powered.

---

# Step 2 - Identify and label the permanent roles

Read the board silkscreen instead of identifying parts by appearance alone.

Write:

```text
RAK19001 + RAK4631 Core A = EMU-01 FULL SENSOR NODE
RAK19007 + RAK4631 Core B = SEC-02 VERIFY / SECURITY
```

Apply the physical labels now.

Recommended labels:

```text
EMU-01 - LEGITIMATE FULL SENSOR NODE
SEC-02 - SECURITY - NO LEGIT EMU-01 KEYS
```

---

# Step 3 - Inspect the CPU connectors

For EMU-01 and then SEC-02:

1. confirm all power is disconnected;
2. find the base-board slot labeled CPU/Core;
3. inspect both WisConnectors for bent contacts, debris, or damage;
4. hold the RAK4631 by the PCB edges;
5. dry-fit alignment visually before pressing anything;
6. make sure the mounting holes naturally line up.

**Stop if:** the holes only align when the core is pushed sideways. That means the connector is not correctly aligned.

---

# Step 4 - Install Core A on the RAK19001

1. Place the RAK19001 flat on the table.
2. Locate its CPU slot.
3. Hold Core A over the CPU WisConnector.
4. Align the two connectors directly over each other.
5. Confirm the mounting holes line up.
6. Press evenly over the connector area.
7. Look from the side: the RAK4631 should sit parallel to the base.
8. Install the correct retaining screw(s).
9. Tighten only enough to hold the board securely.
10. Confirm the `EMU-01` label is visible.

Do not use the screw to force an unseated WisConnector together.

---

# Step 5 - Install Core B on the RAK19007

The RAK19007 used by SEC-02 has one CPU slot, four Sensor slots labeled **A-D**, and one IO slot. At this step install only the core; the exact B-copy sensor positions are frozen later in [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md).

Repeat the same core-install procedure:

1. RAK19007 remains unpowered;
2. identify the connector explicitly labeled CPU/Core;
3. visually identify Sensor A-D and the IO slot now so they are not confused with the CPU connector later;
4. align Core B over the CPU connector;
5. press evenly at the connector;
6. confirm it sits level and parallel to the base;
7. secure with the correct screw(s);
8. confirm the `SEC-02` label is visible;
9. leave Sensor A-D and IO empty until Sensor Assembly 2B instructs you to populate them.

---

# Step 6 - Connect the LoRa antennas

The RAK4631 has labeled RF connectors. Use the connector labeled for **LoRa**, not the BLE connector.

For each board:

```text
antenna cable
     │
     ▼
   [IPEX]
     │
     ▼
RAK4631 LoRa RF connector
```

Procedure:

1. keep the board unpowered;
2. inspect the tiny IPEX socket and plug;
3. center the plug directly above the socket;
4. press straight down;
5. do not twist the plug while pressing;
6. route the cable with no sharp bend at the connector;
7. make sure later sensor boards cannot pinch the cable.

**Pass:** antenna plug is centered, flat, and does not lift with light cable movement.

**Stop if:** the plug will not seat with gentle straight pressure. Re-align it; do not crush the connector.

---

# Step 7 - Do not install battery/solar for bench setup

Use USB-C later for:

```text
stable bench power
firmware upload
serial logs
sensor verification
```

Battery/solar introduces extra variables and is not required for initial sensor setup.

---

# Step 8 - Mechanical acceptance

Check every line before continuing:

```text
[ ] EMU-01 uses RAK19001
[ ] SEC-02 uses RAK19007
[ ] Core A/Core B assignments recorded
[ ] both RAK4631 modules are in CPU slots
[ ] both cores are completely seated and level
[ ] retaining screws installed
[ ] no loose screw/debris under either board
[ ] LoRa antennas connected to LoRa RF connectors
[ ] antenna leads are not pinched
[ ] physical role labels are visible
[ ] USB/battery/solar remain disconnected
```

## Record the base-node baseline

```text
EMU-01 base: RAK19001
EMU-01 core: RAK4631 Core A
EMU-01 antenna marking:

SEC-02 base: RAK19007
SEC-02 core: RAK4631 Core B
SEC-02 antenna marking:
```

Do not record AppKeys in this hardware record.

## Next

Continue to [02-assemble-agriculture-sensors.md](02-assemble-agriculture-sensors.md).
