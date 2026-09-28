# EMU-01 WisBlock — Assembly, Firmware, Payload and Acceptance

Expands [operator guide 18](18-rak4631-wisblock-sensor-firmware.md). **Assembly, flash, radio operation and serial acceptance require real physical EMU-01**. A code compile or synthetic uplink is not a hardware preflight pass. Keep EMU-01 (legitimate sensor) distinct from the separate RAK19007/RUI3 SEC authorized security fixture.

## 1. Board, firmware, LoRaWAN and payload identity

| Property | Commissioned contract |
|---|---|
| Hardware | WisBlock RAK4631 Core A on RAK19001, proper LoRa antenna |
| Firmware | `firmware/EMU01_Agriculture_Node/EMU01_Agriculture_Node.ino` and `payload_v2.h` |
| Credentials | ignored local `emu01_credentials.h`, protected AppKey never published |
| Build | RAK nRF52 BSP 1.3.3; FQBN `rakwireless:nrf52:WisCoreRAK4631Board`; accepted workstation Arduino CLI 1.5.1 at dated commissioning |
| Identity | DevEUI `ac1f09fffe296d29`, JoinEUI `0000000000000000` |
| Radio | **plain AS923**, OTAA, Class A, ADR, unconfirmed uplink |
| Packet | 46-byte payload-v2; immutable field order/version and independent decoder |
| Battery | USB-only `battery_mv=0` = unavailable, **not** 0 V or 0% |

Counted testing and normal production share **all** properties except the explicitly frozen cadence profile. RAK4630 on the metal module is compatible with the complete WisBlock RAK4631 board naming.

## 2. Fixed RAK19001 sensor map

| Slot | Board and signal |
|---|---|
| Sensor A | RAK1903 OPT3001 light, WB_IO1 |
| Sensor B | RAK12010 VEML7700 light, I²C-only; WB_IO2 remains shared 3V3_S power enable |
| Sensor C | RAK12019 LTR390 UV, WB_IO3 |
| Sensor D | RAK12011 barometer/temperature, WB_IO5 |
| Sensor E | RAK1906 BME680 environment, I²C-only; WB_IO4 reserved for soil |
| Sensor F | **EMPTY/reserve**, WB_IO6 reserved for rain |
| WisIO 1 | RAK12023 -> RAK12035 soil probe, WB_IO4 |
| WisIO 2 | RAK12005 -> RAK12030 rain pad, WB_IO6 |
| CPU | RAK4631 Core A plus correct LoRa antenna |

**Assembly:** unplug USB, battery and solar; verify silkscreen and part numbers; seat the CPU and each connector squarely before tightening screws, never use a screw to pull a misaligned connector together. Attach antenna before RF. Leave light sensors exposed, barometer vented, electronics dry, intended external pads/probes in their measurement environment. Run the official WisBlock Pin Mapper for the actual board/modules, retain its output and stop on any revision/pin conflict. Never move sensors when powered. A physically fitting part may still conflict with the shared WB_IO2 switched rail, soil IO4 or rain IO6.

Second-copy sensors were temporarily exercised on a different board, RAK19007, in Profile A and B during preparation; **remove them from SEC** before security testing. This does not change the permanent EMU-01 slot map.

## 3. Windows firmware preflight (PowerShell)

Assume cwd is the directory containing `lorawan-network-server-gateway`:

~~~powershell
$S = '.\lorawan-network-server-gateway\firmware\EMU01_Agriculture_Node'
Get-ChildItem $S -Name
Get-FileHash "$S\EMU01_Agriculture_Node.ino" -Algorithm SHA256
Get-FileHash "$S\payload_v2.h" -Algorithm SHA256
Test-Path "$S\emu01_credentials.h"
Get-CimInstance Win32_SerialPort | Select-Object DeviceID,Description,PNPDeviceID
Get-ChildItem "$env:LOCALAPPDATA","$env:USERPROFILE" -Filter arduino-cli.exe -Recurse -ErrorAction SilentlyContinue |
  Select-Object -First 10 FullName
~~~

Resolve the actual Arduino CLI executable, then inspect `version`, `core list` and `lib list`. Required libraries: SX126x-Arduino, ClosedCube_OPT3001, Light_VEML7700, Adafruit LPS2X, Adafruit Unified Sensor, Adafruit BME680, RAK12019_LTR390 and RAK12035_SoilMoisture. The correct board choice is **WisBlock Core RAK4631 Board**. A missing `LoRaWan-RAK4630.h` is an SX126x-Arduino/toolchain problem, not ChirpStack OTAA failure. Do not show credential file contents in recorded shells. Do not change BSP/libraries during the counted study.

A USB cable must carry data; identify the **physical** EMU serial port before upload. Stop recorder/Serial Monitor ownership when a DFU action requires the port. A DFU COM number may change after reset—rediscover rather than blindly retry the old port. Compile PASS ≠ upload PASS ≠ radio PASS. Programmed DFU must actually report `Device programmed.` and the application must print its accepted banner at **115200 baud**.

## 4. Two non-interchangeable profiles

| Use | Compile macro | Local sampling | Nominal uplink | Jitter |
|---|---|---:|---:|---:|
| Production | `EMU01_COUNTED_TEST_PROFILE=0` (default) | 60 s | 300 s | ±15 s |
| Formal Chapter IV | `EMU01_COUNTED_TEST_PROFILE=1` | 15 s | 15 s | 0 |

Production boot must identify `EMU01_TRAFFIC_PROFILE=PRODUCTION_5MIN` with 60000/300000/15000 ms timing. Counted boot must show `EMU01_TRAFFIC_PROFILE=COUNTED_TEST_15S` and 15000/15000/0 ms. Archive full source/config/compiler/BSP/firmware-image SHA-256 before formal runs and **reuse exact approved counted image**. Changing macro mid-series is a configuration change, not a silent repair.

## 5. Full physical acceptance, with each layer's proof

1. Require ten full cycles `valid=0x007F`. If not, troubleshoot the specific module, GPIO power/I²C or cable **before** LoRaWAN.
2. Inspect source `SENSOR_TX` sequence, uptime, values, validity, `join=1` and `send_status=0`. These are source attempts and constitute the research transmission denominator, not the gateway receipt count.
3. Observe actual Gateway-01/RAK5146 AS923 RF reception and exact Gateway EUI `0016c001f139a1cb`. Commissioned channels include 923200000 and 923400000 Hz; inspect actual firmware, profile and RX settings for full equivalence. Do not substitute AS923-3.
4. Prove OTAA JoinRequest, legitimate JoinAccept and accepted post-join uplinks, not only powered board or modem registration. Keep AppKey secret while checking correct identity.
5. Match **ten** consecutively accepted post-join application payloads with ten reconstructed 46-byte source payloads, not approximate time-only match; no selected codec errors.
6. Prove Node-RED/TimescaleDB rows with correct 13 measurement fields, units and quality; when full-stack readiness is required, independently verify gateway evidence/Fabric eligibility. Two matching uplinks are a **quick smoke**, not full acceptance.

Telemetry fields: soil moisture %, soil temperature °C, UV index, barometer pressure Pa/temperature °C, VEML7700 light lx, OPT3001 light lx, BME680 ambient temperature °C/humidity %/pressure Pa/gas resistance Ω, rain wet Boolean, and battery voltage V only with validated positive real battery measurement. Invalid sensor groups remain in raw provenance but normalized rows have nullable value and `quality=invalid`, not fabricated numeric zero.

Broader testbed PRE (requires **both** EMU and SEC) may be run from Windows repo parent:

~~~powershell
$R = '.\lorawan-network-server-gateway\test\automation\research-recorder\research_recorder.py'
python $R status
python $R preflight --require-emu --require-sec
~~~

EMU-only electrical preflight is narrower and must be reported as such. This command is not a claim that every experiment has formal READY status.

## 6. Safe restore and diagnosis

After counted study, finalize/seal recorder, rebuild/restore default production binary on the **positively identified EMU**, verify `PRODUCTION_5MIN` boot banner and fresh OTAA/application event. Preserve failed runs and accepted study binary; do not leave 15-second profile indefinitely.

No serial -> USB/driver/DFU/port owner; no full-valid sensors -> module/rail; no join -> protected DevEUI/JoinEUI/AppKey and AS923 RX/channel; join but no app -> radio/forwarder/session; app but no DB -> Node-RED/SQL; DB but no evidence -> independent journal/witness/raw object/verifier; eligible but no ledger -> governed Fabric adapter. Never reset OTAA frame counters, delete gateway journal, disable MIC verification or spoof healthy readings to make a test pass.

Maintenance provenance: [physical RAK19001 slot map](../../test/preparation/sensor/assembly/02a-rak19001-fixed-slot-map.md), [firmware README](../../firmware/EMU01_Agriculture_Node/README.md), [sensor preparation](../../test/preparation/sensor/01-configure-rak4631-emulators.md). Final Word document must print this map and operative steps within its own pages.
