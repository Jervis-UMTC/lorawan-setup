# Chapter 7 — EMU-01 WisBlock Sensor Assembly and Firmware

EMU-01 is the legitimate agricultural sensor node. It uses a RAK4631 Core A on a RAK19001 WisBlock Base. It uses the Arduino/nRF52 firmware family. It transmits the project's 46-byte payload-v2 over plain AS923 LoRaWAN.

SEC-01 is a different security-test node. SEC-01 uses RUI3 on RAK19007. **Do not flash EMU-01 firmware onto SEC-01. Do not copy EMU-01 keys to SEC-01.**

## 7.1 Identify the correct hardware before power

Prepare these parts:

- RAK19001 WisBlock Base.
- RAK4631 Core A.
- The LoRa antenna for the installed RAK4631 frequency range.
- RAK1903 OPT3001 light sensor.
- RAK12010 VEML7700 light sensor.
- RAK12019 LTR390 UV sensor.
- RAK12011 barometer / temperature sensor.
- RAK1906 BME680 environment sensor.
- RAK12023 with RAK12035 soil probe.
- RAK12005 with RAK12030 rain pad.
- A known-good USB-C data cable.

The RAK19001 supplies power and interconnects the WisBlock Core and modules. It has one Core slot, six Sensor slots, and two IO slots. RAKwireless requires modules to be fixed with their screws. The RAK4631 must have an antenna attached before LoRa transmission.

<!-- EMU_RAK19001_VENDOR -->

**Figure 7.1. RAK19001 reference board.** Use the silkscreen and slot labels to identify the actual base before assembly.

Before you touch any module:

1. Disconnect USB.
2. Disconnect the battery.
3. Disconnect the solar input.
4. Wait until board LEDs are off.
5. Check the RAK19001 and RAK4631 labels.
6. Check that no conductive debris or loose screw is under the board.

**STOP:** Do not move a WisBlock module while the base has power.

## 7.2 Assemble the fixed EMU-01 slot map

Use this exact permanent map:

| Position | Project module | Function / reserved line |
| --- | --- | --- |
| Core | RAK4631 Core A | LoRaWAN + MCU |
| Sensor A | RAK1903 OPT3001 | light / WB_IO1 |
| Sensor B | RAK12010 VEML7700 | light / I2C; WB_IO2 remains shared 3V3_S enable |
| Sensor C | RAK12019 LTR390 | UV / WB_IO3 |
| Sensor D | RAK12011 | barometer + temperature / WB_IO5 |
| Sensor E | RAK1906 BME680 | environment / I2C; WB_IO4 reserved for soil |
| Sensor F | EMPTY | reserve; WB_IO6 reserved for rain |
| WisIO 1 | RAK12023 -> RAK12035 | soil moisture + temperature / WB_IO4 |
| WisIO 2 | RAK12005 -> RAK12030 | rain / water detection / WB_IO6 |

<!-- EMU_SLOT_MAP -->

**Figure 7.2. EMU-01 fixed project slot map.** Do not copy a generic WisBlock example layout over this map.

Assemble the board:

1. Seat RAK4631 squarely in the Core connector.
2. Install its retaining screw.
3. Seat each Sensor module in the listed Sensor slot.
4. Seat RAK12023 in WisIO 1.
5. Connect RAK12035 to RAK12023.
6. Seat RAK12005 in WisIO 2.
7. Connect RAK12030 to RAK12005.
8. Leave Sensor F empty.
9. Tighten module screws only after each connector is fully aligned.
10. Keep optical sensors exposed to ambient light.
11. Keep the BME680 and barometer vented.
12. Keep electronics dry.
13. Put only the intended soil and rain probes in the measurement environment.

Do not use a screw to pull a misaligned connector together.

## 7.3 Attach the LoRa antenna before USB power

RAKwireless states that operating the RAK4631 radio without its antenna can damage the RF section.

<!-- EMU_RAK4631_ANTENNA -->

**Figure 7.3. RAK4631 antenna label reference.** Match the LoRa connector on the actual Core. Do not confuse it with BLE.

1. Find the LoRa antenna mark on the RAK4631 label.
2. Align the IPEX/u.FL connector straight above the socket.
3. Press the connector straight down.
4. Check that it is fully seated.
5. Route the pigtail without a sharp bend.
6. Keep the antenna attached for all firmware and LoRaWAN tests.

Do not power EMU-01 if the LoRa connector is uncertain.

## 7.4 Connect USB and identify EMU-01

Use USB-C for initial setup. Do not connect battery or solar during the first firmware check.

Connect a known-good USB data cable. Windows can assign a different COM number after reset or DFU.

On the research workstation, open **Windows PowerShell**:

~~~powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Description,PNPDeviceID
~~~

<!-- EMU_SERIAL_PORT_REAL -->

**Screen 7A. Actual read-only serial-port identity snapshot.** EMU-01 was COM11 and SEC-01 was COM16 at this snapshot. Rediscover the ports every time.

For the verified project hardware:

- EMU-01 USB identity: VID 239A / PID 8029.
- SEC-01 USB identity: VID 1915 / PID 521F.

**PASS:** Windows shows the expected EMU-01 USB identity.

**STOP:** If board identity is uncertain, disconnect it. Do not flash by COM number alone.

## 7.5 Check the firmware files and protected credentials

From the Windows directory that contains the repository:

~~~powershell
$S = '.\lorawan-network-server-gateway\firmware\EMU01_Agriculture_Node'
Get-ChildItem $S -Name
Get-FileHash "$S\EMU01_Agriculture_Node.ino" -Algorithm SHA256
Get-FileHash "$S\payload_v2.h" -Algorithm SHA256
Test-Path "$S\emu01_credentials.h"
Get-Item "$S\emu01_credentials.h" | Select-Object FullName,Length,LastWriteTime
~~~

**PASS:**

- EMU01_Agriculture_Node.ino exists.
- payload_v2.h exists.
- emu01_credentials.h exists and is non-empty.
- The credential file remains local and protected.

Do **not** run Get-Content on emu01_credentials.h in a recorded terminal.

Do **not** copy EMU-01's AppKey into this manual.

## 7.6 Check Arduino CLI, the RAK core, and libraries

The accepted project build used:

| Item | Accepted value |
| --- | --- |
| Arduino CLI | 1.5.1 at the accepted build |
| RAK nRF52 core | 1.3.3 |
| FQBN | rakwireless:nrf52:WisCoreRAK4631Board |

Find Arduino CLI without assuming its path:

~~~powershell
Get-ChildItem "$env:LOCALAPPDATA","$env:USERPROFILE" -Filter arduino-cli.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 10 FullName
~~~

Run the discovered executable:

~~~powershell
& '<FULL-PATH-TO-arduino-cli.exe>' version
& '<FULL-PATH-TO-arduino-cli.exe>' core list
& '<FULL-PATH-TO-arduino-cli.exe>' lib list
~~~

The project dependencies include:

- SX126x-Arduino
- ClosedCube OPT3001
- Light_VEML7700
- Adafruit LPS2X
- Adafruit Unified Sensor
- Adafruit BME680
- RAK12019_LTR390
- RAK12035_SoilMoisture

**PASS:** Arduino CLI runs. The RAK nRF52 core is present. The required libraries are present.

Do not update the BSP or libraries during a counted experiment series.

If compilation reports LoRaWan-RAK4630.h missing, repair SX126x-Arduino first. That error is not a ChirpStack or OTAA failure.

## 7.7 Select the correct firmware profile

Production and counted testing use the same sensor identity, payload, region, and keys. Only the timing profile changes.

| Use | Compile profile | Local sample | Normal uplink | Jitter |
| --- | --- | ---: | ---: | ---: |
| Production | default / EMU01_COUNTED_TEST_PROFILE=0 | 60 s | 300 s | +/-15 s |
| Counted research | accepted archived EMU01_COUNTED_TEST_PROFILE=1 build | 15 s | 15 s | 0 s |

The normal operator build is **production**.

The accepted counted-test artifact is already archived with its build record. Do not improvise new compiler flags during a formal test.

For the accepted counted build, the archived record identifies:

- source SHA-256 dc6fab2b6e9934074360a9223f4786d27a9b1db7cf0a68c05d00ff573fcc4424
- HEX SHA-256 f7ab95071e7c8ad4e14c9b2ad0a7ce2c46c696b9cf2bb73f340634ba2e6ff78f
- upload package SHA-256 c1f09de8eb6d8e00bbdd432765db90c66eaa87a530f490e54d04558e81bbd6b1

Do not treat those archived hashes as the hash of a newly edited production source file.

## 7.8 Compile production firmware

Select this board:

**WisBlock Core RAK4631 Board**

FQBN:

**rakwireless:nrf52:WisCoreRAK4631Board**

A compile PASS proves source and toolchain compatibility. It does not prove upload, sensor operation, OTAA, or radio reception.

If you use Arduino IDE, select the same WisBlock Core RAK4631 Board. RAKwireless documents the Arduino BSP as the correct software family for non-RUI3 RAK4631.

Before you upload:

1. Confirm the physical board is EMU-01.
2. Confirm the LoRa antenna is attached.
3. Close Serial Monitor.
4. Pause any recorder that owns the EMU serial port.
5. Rediscover the current application or DFU COM port.

## 7.9 Upload and handle DFU port changes

Upload the compiled firmware to the positively identified EMU-01.

A successful RAK DFU upload must report:

**Device programmed.**

If the application COM port disappears:

1. Wait for Windows to enumerate the DFU port.
2. Run the serial-port discovery command again.
3. Select the new port.
4. Retry only after you identify the same physical EMU-01.

Do not blindly retry an old COM number.

Do not open a second serial owner while the research recorder owns EMU-01.

## 7.10 Verify the boot profile at 115200 baud

Open the current EMU-01 application port at **115200 baud**.

Production must report approximately:

~~~text
EMU01_TRAFFIC_PROFILE=PRODUCTION_5MIN
sample interval = 60000 ms
normal interval = 300000 ms
jitter = 15000 ms
~~~

The counted profile must report:

~~~text
EMU01_TRAFFIC_PROFILE=COUNTED_TEST_15S
sample interval = 15000 ms
normal interval = 15000 ms
jitter = 0 ms
~~~

**STOP:** If the profile is wrong, do not start a research run.

## 7.11 Verify all sensors before LoRaWAN

Wait for complete sensor cycles.

The healthy validity bitmap is:

**valid=0x007F**

If the validity bitmap differs:

1. Stop at the sensor layer.
2. Check the fixed slot map.
3. Check module seating and screws.
4. Check the shared 3V3_S power control.
5. Check the relevant I2C or IO line.
6. Check the external soil/rain cable.
7. Do not change ChirpStack.

A sensor fault is not repaired by changing LoRaWAN keys.

## 7.12 Read the source transmission line

A healthy joined transmission has:

**join=1**

and:

**send_status=0**

<!-- EMU_SENSOR_SOURCE_REAL -->

**Screen 7B. Actual EMU-01 source capture from an accepted operator check.** It is a historical reference. Use the current run's recorder for current evidence.

The SENSOR_TX sequence is the source-attempt authority for research counting. Do not replace it with the number of gateway frames.

battery_mv=0 is the current USB-only sentinel. It means battery voltage is unavailable. It does not mean 0 V or 0%.

## 7.13 Verify OTAA in the correct order

EMU-01 uses:

- plain AS923
- OTAA
- Class A
- ADR enabled
- unconfirmed normal uplinks
- DevEUI ac1f09fffe296d29
- JoinEUI 0000000000000000

Keep the AppKey protected.

Verify this order:

1. EMU-01 sends a JoinRequest.
2. Gateway-01 receives the RF frame.
3. ChirpStack validates the device identity and key.
4. ChirpStack sends JoinAccept.
5. EMU-01 reports joined.
6. EMU-01 sends an application uplink.
7. ChirpStack shows the new device event.

If OTAA fails, compare DevEUI, JoinEUI, protected AppKey, AS923, RX settings, and downlink path.

Never print the AppKey while you compare it.

Do not switch regions to force a join.

## 7.14 Verify the 46-byte payload-v2

Payload-v2 is exactly **46 bytes**.

A change to field order or field size requires a new payload version. It also requires decoder, Node-RED, database, and research-correlation updates.

The normalized measurement set includes:

- soil moisture %
- soil temperature °C
- UV index
- barometer pressure Pa
- barometer temperature °C
- VEML7700 light lx
- OPT3001 light lx
- BME680 ambient temperature °C
- BME680 humidity %
- BME680 pressure Pa
- BME680 gas resistance ohm
- rain wet Boolean
- battery voltage only when a real positive battery measurement is validated

Invalid sensor groups remain in raw provenance. Do not convert an invalid measurement to a fabricated numeric zero.

## 7.15 Perform quick end-to-end acceptance

From the Windows repository parent:

~~~powershell
$R = '.\lorawan-network-server-gateway\test\automation\research-recorder\research_recorder.py'
python $R status
python $R preflight --require-emu --require-sec
~~~

This project-wide preflight requires both EMU-01 and SEC-01. It is broader than an EMU-only firmware check.

Two consecutive successful SENSOR_TX attempts are only a quick connectivity smoke check.

Full EMU-01 hardware acceptance requires:

1. ten complete cycles with valid=0x007F;
2. a real OTAA JoinRequest and JoinAccept;
3. at least ten consecutive post-join application uplinks;
4. ten exact source-payload versus ChirpStack payload comparisons;
5. the required Node-RED / TimescaleDB result;
6. the required evidence / Fabric eligibility result when full-stack acceptance is in scope.

Do not mark full sensor acceptance from two transmissions.

## 7.16 Restore production after counted testing

After the counted series:

1. Finalize the research recorder.
2. Restore or build the default production firmware.
3. Upload it to the positively identified EMU-01.
4. Check EMU01_TRAFFIC_PROFILE=PRODUCTION_5MIN.
5. Check the 60000 / 300000 / 15000 ms timing.
6. Verify OTAA or the retained legitimate session.
7. Verify one normal-path uplink.
8. Record the restoration.

Do not leave the 15-second counted profile running indefinitely.

## 7.17 Troubleshoot the first failing layer

| Symptom | First check |
| --- | --- |
| missing library/header | Arduino library or BSP |
| compile PASS, upload FAIL | current COM / DFU / bootloader |
| Device programmed. but no serial | application COM / 115200 baud / reset |
| valid is not 0x007F | module seating / power / I2C / IO |
| sensors healthy, OTAA fails | DevEUI / JoinEUI / protected AppKey / AS923 |
| OTAA succeeds, no uplink | send status / antenna / RF |
| gateway receives, no application event | ChirpStack device/profile/session |
| application event exists, no database row | Node-RED / SQL path |
| wrong cadence | wrong firmware profile |
| COM busy | Serial Monitor / recorder ownership |
| COM changed after reset | rediscover the port |

Do not erase credentials as a generic fix.

Do not reset frame counters to make a test pass.

Do not disable LoRaWAN security.

Do not move sensors while powered.

## 7.18 Chapter completion checklist

- [ ] EMU-01 RAK19001 and RAK4631 Core A identified.
- [ ] Fixed sensor slot map matches Figure 7.2.
- [ ] LoRa antenna attached before RF.
- [ ] Current EMU COM identity discovered.
- [ ] Protected credential file exists but is not exposed.
- [ ] Accepted core and required libraries verified.
- [ ] Correct production or approved counted profile selected.
- [ ] Firmware upload reports Device programmed.
- [ ] Boot profile matches the intended timing.
- [ ] Sensor validity is valid=0x007F.
- [ ] join=1 and send_status=0 appear during a healthy joined transmission.
- [ ] Plain AS923 and OTAA identity match Chapter 6.
- [ ] A new ChirpStack application event appears for the authorized sensor.
- [ ] Production profile is restored after counted testing.

## References for this chapter

RAKwireless RAK4631 Quick Start Guide:
https://docs.rakwireless.com/product-categories/wisblock/rak4631/quickstart/

RAKwireless RAK19001 Product Overview:
https://docs.rakwireless.com/product-categories/wisblock/rak19001/overview/

RAKwireless RAK19001 Quick Start Guide:
https://docs.rakwireless.com/product-categories/wisblock/rak19001/quickstart/
