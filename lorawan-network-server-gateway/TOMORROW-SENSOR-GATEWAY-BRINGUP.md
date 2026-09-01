# Tomorrow - Sensor + Gateway Bring-Up

**Use this file as the operator entry point.** Do not reconstruct tomorrow's procedure from old continuation checkpoints.

## Frozen baseline

- Gateway OS: use the already accepted flash-ready image/release and its recorded checksum. Do not rebuild unless integrity verification fails.
- Gateway radio/server region: plain **AS923** / MQTT prefix `as923`.
- EMU-01: RAK19001 + RAK4631 Core A, fixed sensor map A=RAK1903, B=empty, C=RAK12019, D=RAK12011, E=RAK1906, F=RAK12010, WisIO1=RAK12023+RAK12035, WisIO2=RAK12005+RAK12030.
- Firmware: `firmware/EMU01_Agriculture_Node/`.
- Payload: v2, exactly 46 bytes, big-endian, healthy validity `0x007F`.
- LoRaWAN: OTAA, Class A, unconfirmed, 15-second monotonic application cadence.
- Credentials: local/protected only. Never put AppKey in Git/evidence/chat.

## Gate 0 - Before power

1. Confirm LoRa antennas are attached to gateway and EMU-01 before radio operation.
2. Confirm gateway hardware matches the flashed-image target.
3. Confirm EMU-01 physical slot map matches the frozen map and Pin Mapper record has no unresolved conflict.
4. Keep RAK12023/RAK12005 electronics dry; only intended soil/rain sensing surfaces may contact moisture.
5. Confirm EMU-01's local `emu01_credentials.h` exists and contains its own identity, not SEC-02 credentials.

**STOP** on wrong hardware, wrong sensor map, missing antenna, exposed secret, or unresolved mapper conflict.

## Gate 1 - Flash and boot the gateway

1. Verify the accepted image checksum against its release record.
2. Flash that image using the documented gateway image procedure.
3. Boot with console/local access available.
4. Verify no boot-loop, filesystem, or service-start failure.
5. Verify RAK5146 is detected and the packet-forwarder/gateway service uses plain AS923.
6. Verify gateway EUI/identity is the intended production identity after protected configuration is restored.
7. Verify SIM7600 is detected if cellular is part of tomorrow's path; cellular failure does not justify changing LoRa region/configuration.
8. Verify local MQTT/evidence services and public broker/evidence endpoint reachability according to the current deployment runbooks.
9. In ChirpStack, require the gateway to show a recent `Last seen` before touching sensor firmware.

**GATEWAY_READY=YES** only after RAK5146 + AS923 + gateway identity + ChirpStack last-seen are all good.

## Gate 2 - Compile and flash EMU-01

1. Arduino target: `WisBlock Core RAK4631 Board`.
2. Use pinned/proven sensor libraries and `SX126x-Arduino`; do not opportunistically upgrade libraries.
3. Compile `firmware/EMU01_Agriculture_Node/EMU01_Agriculture_Node.ino` with local `emu01_credentials.h`.
4. Record Arduino IDE, BSP, library versions, source revision/hash, build date in `chapter4-results/_device-baseline/EMU-01-firmware.txt`.
5. Upload only to the physically labelled EMU-01 Core A.
6. Reboot and capture Serial at 115200.

**STOP** on compiler error. Fix the first compiler/API mismatch against the already-proven library versions; do not change payload-v2 or radio profile to work around it.

## Gate 3 - Local sensor acceptance

Capture at least ten consecutive `SENSOR_TX` cycles. Require:

- sequence increments once per telemetry cycle;
- cadence approximately 15 seconds without cumulative delay drift;
- `valid=0x7F`/`0x007F` every healthy cycle;
- soil, UV, barometer, both light sensors, BME680 environment, and rain are plausible and responsive;
- soil uses the accepted calibration dry=560, wet=328;
- `battery_mv=0` is accepted only for the documented USB-only sentinel;
- no stale sample is marked valid after a failed read.

**STOP** if validity is not `0x007F`; fix the sensor layer before network troubleshooting.

## Gate 4 - OTAA and payload-v2

1. Confirm EMU-01 device profile is plain AS923, Class A, and matches the actual LoRaWAN MAC/regional-parameters version of the pinned firmware library.
2. Confirm ChirpStack has the 46-byte payload-v2 decoder from `test/preparation/sensor/01-configure-rak4631-emulators.md`.
3. Reset EMU-01 while watching Serial, gateway frames, and ChirpStack.
4. Require `JoinRequest -> JoinAccept -> application uplink`.
5. Require repeated 46-byte `UnconfirmedDataUp` frames near the 15-second application cadence.
6. Compare ten consecutive Serial sequences against ChirpStack decoded values, including all physical fields and validity bitmap.

**STOP** on mismatch. If Serial is correct but decoded data is wrong, fix codec/mapping; do not recalibrate a healthy sensor to fit a decoder bug.

## Gate 5 - Application/evidence lineage

For one accepted sequence, prove the same sequence/value lineage:

`EMU-01 Serial -> RAK5146 -> ChirpStack -> Node-RED -> TimescaleDB -> Grafana`

Then verify the independent evidence/trusted-decoder path required by the current server deployment. Use real EMU-01 traffic; do not substitute previous synthetic tests for this hardware gate.

External Hyperledger Fabric ledger activation and provider Reserved-IP failover are separate acceptance items. They must be recorded honestly but do not invalidate a healthy local RF/telemetry path.

## Gate 6 - SEC-02 cleanup

Before converting SEC-02 to its security fixture, finish its remaining legitimate-node check: several consecutive decoded RAK12011 pressure/temperature frames must match Serial. Then retire/rotate the temporary legitimate credential. Never reuse EMU-01's AppKey/session state.

## Final sensor preflight

Run `test/preparation/sensor/preflight/00-README.md` and its linked checks against the now-frozen final system. Counted execution may begin only when the procedure produces:

`SENSOR_PREFLIGHT_STATUS=GO`

## Fast fault isolation

- Gateway not last-seen -> gateway/network path; do not alter sensors.
- Sensor validity != `0x007F` -> sensor/firmware layer; do not alter ChirpStack.
- JoinRequest at gateway but not device -> identity/profile routing.
- JoinRequest at ChirpStack but no JoinAccept -> OTAA key/JoinEUI/profile/region.
- Raw 46 bytes correct but decoded values wrong -> codec/scaling.
- ChirpStack correct but DB missing -> Node-RED/application path.
- DB correct but evidence missing -> evidence service/Fabric boundary.
