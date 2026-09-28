# RAK4631 / WisBlock Sensor Firmware — Operator Manual

## What this technology does

EMU-01 is the physical LoRaWAN agriculture node. It uses a RAK4631 core on RAK19001, seven sensor types, the Arduino/nRF52 firmware family, OTAA, Class A, ADR, unconfirmed uplinks, and the project's 46-byte payload-v2.

This manual is for **EMU-01 only**. The separate security node uses RUI3; see [20-rui3-security-node.md](20-rui3-security-node.md).

## Current commissioned baseline

~~~text
Role                  EMU-01
FQBN                  rakwireless:nrf52:WisCoreRAK4631Board
Accepted RAK core     1.3.3
Region                plain AS923
Activation            OTAA
Class                 A
ADR                   enabled
Normal uplink         unconfirmed
Payload               payload-v2 / 46 bytes
DevEUI                ac1f09fffe296d29
JoinEUI               0000000000000000
AppKey                protected local secret; never print/store in docs
~~~

Do not substitute AS923-3. Do not copy EMU-01 credentials to SEC.

## Files

~~~text
firmware/EMU01_Agriculture_Node/
  EMU01_Agriculture_Node.ino
  payload_v2.h
  emu01_credentials.example.h
  emu01_credentials.h
  README.md
~~~

The credentials file is local/protected. Never print it in a recorded terminal.

## Physical sensor set

~~~text
RAK1903                  OPT3001 light
RAK12010                 VEML7700 light
RAK12011                 barometer / temperature
RAK1906                  BME680 environment
RAK12019                 LTR390 UV
RAK12023 + RAK12035      soil moisture / temperature
RAK12005 + RAK12030      rain / water detection
~~~

Use the fixed slot map in the sensor preparation manual. Never move modules while powered.

## Traffic profiles

| Profile | Compile setting | Local sample | Normal uplink | Jitter |
|---|---|---:|---:|---:|
| Production | default / EMU01_COUNTED_TEST_PROFILE=0 | 60 s | 300 s | ±15 s |
| Counted test | EMU01_COUNTED_TEST_PROFILE=1 | 15 s | 15 s | 0 s |

The counted profile changes timing only. Identity, payload, sensors, decoder, radio region and application path remain unchanged.

## Step 1 — Identify the physical board

Before flashing, require:

~~~text
[ ] board is physically identified as EMU-01
[ ] RAK4631 is on the EMU-01 RAK19001 base
[ ] LoRa antenna attached
[ ] seven commissioned sensor types installed
[ ] USB cable supports data
[ ] no recorder/Serial Monitor currently owns the port
~~~

If board identity is uncertain, stop. Do not flash.

## Step 2 — Discover the current serial port

~~~powershell
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Description,PNPDeviceID
~~~

Historical COM numbers are not permanent. DFU can re-enumerate on another port.

## Step 3 — Verify Arduino CLI and RAK core

Arduino CLI 1.5.1 was accepted on the workstation but is not guaranteed to be on PATH.

~~~powershell
Get-ChildItem "$env:LOCALAPPDATA","$env:USERPROFILE" -Filter arduino-cli.exe -Recurse -ErrorAction SilentlyContinue | Select-Object -First 10 FullName
~~~

Run the discovered executable:

~~~powershell
& '<FULL-PATH-TO-arduino-cli.exe>' version
& '<FULL-PATH-TO-arduino-cli.exe>' core list
~~~

**PASS means:** Arduino CLI runs and the RAKwireless nRF52 core is present.

Do not update the BSP during a counted experiment series.

## Step 4 — Verify required libraries

~~~powershell
& '<FULL-PATH-TO-arduino-cli.exe>' lib list
~~~

Accepted dependencies include:

~~~text
SX126x-Arduino
ClosedCube_OPT3001
Light_VEML7700
Adafruit LPS2X
Adafruit Unified Sensor
Adafruit BME680
RAK12019_LTR390
RAK12035_SoilMoisture
~~~

If compilation reports LoRaWan-RAK4630.h missing, repair SX126x-Arduino first. That is not an OTAA or ChirpStack failure.

## Step 5 — Verify credentials exist without exposing them

~~~powershell
$P = '.\lorawan-network-server-gateway\firmware\EMU01_Agriculture_Node'; Test-Path "$P\emu01_credentials.h"; Get-Item "$P\emu01_credentials.h" | Select-Object FullName,Length,LastWriteTime
~~~

**PASS means:** the file exists and is non-empty.

Never use Get-Content on the credentials file in a recorded terminal.

## Step 6 — Hash the source before building

~~~powershell
Get-FileHash .\lorawan-network-server-gateway\firmware\EMU01_Agriculture_Node\EMU01_Agriculture_Node.ino -Algorithm SHA256
Get-FileHash .\lorawan-network-server-gateway\firmware\EMU01_Agriculture_Node\payload_v2.h -Algorithm SHA256
~~~

For counted tests, compare against the accepted build record under chapter4-results/_configuration/emu01-counted-test-15s/.

Do not rebuild the counted artifact during a formal run if the accepted archived artifact already hashes correctly.

## Step 7 — Compile

Select:

~~~text
WisBlock Core RAK4631 Board
rakwireless:nrf52:WisCoreRAK4631Board
~~~

Production uses the default timing profile. Counted tests use EMU01_COUNTED_TEST_PROFILE=1 only through the accepted build procedure.

A compile PASS proves only source/toolchain compatibility. It does not prove upload, sensors, OTAA or RF.

## Step 8 — Upload

Before upload:

~~~text
[ ] antenna attached
[ ] correct physical EMU-01
[ ] Serial Monitor closed
[ ] recorder serial capture paused if a run is active
[ ] current application/DFU COM port selected
~~~

Successful DFU must include:

~~~text
Device programmed.
~~~

If the application port disappears and a DFU port appears, rediscover the port instead of retrying the old COM number.

## Step 9 — Verify boot profile

Open the current application port at 115200 baud.

Production must show approximately:

~~~text
sample interval = 60000 ms
normal interval = 300000 ms
jitter = 15000 ms
~~~

Counted testing must show:

~~~text
EMU01_TRAFFIC_PROFILE=COUNTED_TEST_15S
sample interval = 15000 ms
normal interval = 15000 ms
jitter = 0
~~~

Wrong profile = STOP.

## Step 10 — Verify sensors before LoRaWAN

Healthy full cycles should show:

~~~text
valid=0x007F
~~~

If validity is not 0x007F, troubleshoot sensor power/I2C/module seating before touching ChirpStack.

## Step 11 — Verify source transmission lines

A machine-readable SENSOR_TX line should contain sequence, uptime, sensor values, validity, join state and send status.

Healthy joined transmission:

~~~text
join=1
send_status=0
~~~

The source sequence is the research recorder's source-attempt authority.

## Step 12 — Verify OTAA

Required order:

~~~text
JoinRequest
-> RAK5146 RF reception
-> ChirpStack credential validation
-> JoinAccept
-> EMU-01 reports joined
-> application uplink
~~~

If OTAA fails, compare protected DevEUI, JoinEUI, AppKey and AS923 configuration. Never print the AppKey while comparing.

## Step 13 — Verify the real end-to-end path

~~~powershell
python .\lorawan-network-server-gateway\test\automation\research-recorder\research_recorder.py preflight --require-emu --require-sec
~~~

Two consecutive successful `SENSOR_TX` attempts with matching Gateway-01/ChirpStack evidence are a **quick connectivity smoke check only**. Full EMU-01 hardware/firmware acceptance requires the frozen sensor preflight: ten healthy `valid=0x007F` cycles, OTAA JoinRequest/JoinAccept, at least ten consecutive post-join uplinks without selected codec errors, ten exact Serial-vs-ChirpStack payload comparisons, and the required application/TimescaleDB/evidence/Fabric eligibility outcomes. Do not mark full preflight GO from only two transmissions.

## Step 14 — Restore production after counted tests

After the counted series:

1. stop/finalize the recorder;
2. restore/build the default production profile;
3. upload it;
4. require the production boot profile;
5. verify OTAA/session and one normal-path uplink;
6. record the restoration.

Do not leave the 15-second counted profile running indefinitely.

## Payload-v2 hard rule

Payload-v2 is exactly 46 bytes. Any incompatible field order/size change requires a new payload version plus decoder, Node-RED/application and research-correlation updates.

The USB-only battery sentinel remains battery_mv=0 until a validated real battery voltage source exists.

## Troubleshooting order

| Symptom | First check |
|---|---|
| missing header/library | Arduino library/BSP |
| compile passes, upload fails | COM/DFU/bootloader ownership |
| Device programmed, no serial | application port / baud / reset |
| validity not 0x007F | sensor power/I2C/seating |
| sensors healthy, OTAA fails | DevEUI/JoinEUI/AppKey/AS923 |
| OTAA succeeds, no uplink | send status / antenna / RF |
| gateway receives, no application row | ChirpStack/application layer |
| wrong cadence | wrong firmware profile |
| COM busy | Serial Monitor/orphan recorder child |
| COM changed after reset | rediscover application/DFU port |

## Recovery rules

- never erase credentials as a generic fix;
- never change region to force a join;
- never disable LoRaWAN security;
- never rebuild counted firmware mid-trial;
- preserve failed-run evidence;
- hash accepted archived images before reuse.

## Completion checklist

- correct EMU-01 identified;
- antenna attached;
- toolchain/core/libraries verified;
- protected credentials present but not exposed;
- correct profile boot behavior;
- healthy validity bitmap;
- OTAA joined;
- two successful SENSOR_TX attempts;
- matching AS923 gateway reception;
- matching ChirpStack/application evidence;
- production restored after counted testing.

## Complete assembly, firmware and acceptance companion

Use [EMU-01 WisBlock assembly, slot map, payload-v2, firmware profiles and full hardware acceptance](EMU01-WISBLOCK-ASSEMBLY-FIRMWARE-ACCEPTANCE.md). A compile or two-uplink smoke test is not the same as the ten-cycle/full-path preflight.

## Detailed references

- [Firmware README](../../firmware/EMU01_Agriculture_Node/README.md)
- [Sensor configuration and LoRaWAN bring-up](../../test/preparation/sensor/01-configure-rak4631-emulators.md)
- [First-time Arduino walkthrough](../../test/preparation/sensor/assembly/04a-first-time-arduino-operator-walkthrough.md)
- [Research execution baseline](../../test/execution/00-README.md)
