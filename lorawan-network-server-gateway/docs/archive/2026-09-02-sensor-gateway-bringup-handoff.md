# Historical Sensor + Gateway Bring-Up Handoff - 2026-09-02

**Original working title:** `Tomorrow - Sensor + Gateway Bring-Up`.

**Historical reference only.** This file preserves the physical bring-up procedure and acceptance context used for the 2026-09-02 session. Current research operation now starts from `test/00-README.md`, `test/automation/research-recorder/README.md`, and the selected `test/execution/` manual; later accepted state is recorded in `deployment/server/cloud-production/00-current-server-continuation-checkpoint.md`.

## Frozen baseline

- Gateway OS: use the already accepted flash-ready image/release and its recorded checksum. Do not rebuild unless integrity verification fails.
- Gateway radio/server region: plain **AS923** / MQTT prefix `as923`.
- EMU-01: RAK19001 + RAK4631 Core A, fixed sensor map A=RAK1903, B=RAK12010, C=RAK12019, D=RAK12011, E=RAK1906, F=empty/reserve, WisIO1=RAK12023+RAK12035, WisIO2=RAK12005+RAK12030.
- Firmware: `firmware/EMU01_Agriculture_Node/`.
- Payload: v2, exactly 46 bytes, big-endian, healthy validity `0x007F`.
- LoRaWAN: OTAA, Class A, ADR enabled, unconfirmed normal telemetry; final production scheduler samples locally every 60 seconds and sends nominal 5-minute uplinks with DevEUI-derived initial staggering and ±15-second jitter, plus randomized/rate-limited rain-event uplinks.
- **Production scheduler physical acceptance - 2026-09-02: PASS.** EMU-01 DevEUI `ac1f09fffe296d29` was compiled/flashed with RAKwireless nRF BSP `1.3.3` for `rakwireless:nrf52:WisCoreRAK4631Board`; Arduino DFU reported `Device programmed`. Fresh OTAA RF occurred at `06:08:33 UTC`, Gateway-01 emitted the join-accept at `06:08:38`, and the first application uplink arrived at `06:11:25`, matching the firmware's `165.919 s` DevEUI-derived initial phase. The next normal uplink arrived at `06:16:39`, an observed `314 s` interval inside the configured `285-315 s` jitter window. The old 15-second application cadence is no longer active in this production image.
- Gateway Evidence followed the new production traffic: segment 30 closed at `06:16`; public Evidence ingest returned explicit segment and checkpoint receipts for segment 30 / last journal sequence 581 at `06:16:29 UTC`; segment 31 then opened for subsequent traffic, and writer/uploader/IPC-guard processes remained running.
- Credentials: local/protected only. Never put AppKey in Git/evidence/chat.
- **Security-node RUI3 preparation - 2026-09-02: PASS.** The second RAK4631 plugged in and operator-labelled `SEC-01` is the single security-node role historically named `SEC-02` in the project manuals. It was converted from the Arduino firmware family to official RUI3 `3.4.2-rui3_22q1_update.112`, corrected from the factory EU868 default to `BAND=8` / AS923-1, and proved able to switch LoRaWAN -> P2P -> LoRaWAN without transmitting. It is parked at LoRaWAN + OTAA + Class A, `NJS=0`, all-zero DevEUI, with no AppKey installed and no join/replay/P2P transmission performed. Before tomorrow's RF security fixture, physically confirm RAK19007 + Core B, empty Sensor/IO slots unless the chosen fixture explicitly requires hardware, and LoRa antenna attached; then load only the specific test identity/parameters required by that experiment.
- **Fabric adapter server-side readiness - 2026-09-02: PASS up to external handoff.** Both immutable workers are deployed in fail-closed standby, database access is verify-full proven through all three PgBouncer nodes, separate OpenBao AppRole identities pass sign/verify through the HA KMS endpoint, and protected adapter env/runtime paths are staged. The current 509 outbox rows remain pending with zero attempts. Do not spend sensor-test time recommissioning the adapter. Real ledger activation waits only for the other Fabric system's Gateway/TLS/MSP/channel/chaincode/function handoff, after which the existing enable preflight is the activation gate.

## Gate 0 - Before power

1. Confirm LoRa antennas are attached to gateway and EMU-01 before radio operation.
2. Confirm gateway hardware matches the flashed-image target.
3. Confirm EMU-01 physical slot map matches the frozen map and Pin Mapper record has no unresolved conflict.
4. Keep RAK12023/RAK12005 electronics dry; only intended soil/rain sensing surfaces may contact moisture.
5. Confirm EMU-01's local `emu01_credentials.h` exists and contains its own identity, not SEC-02 credentials.

**STOP** on wrong hardware, wrong sensor map, missing antenna, exposed secret, or unresolved mapper conflict.

## Gate 1 - Gateway reuse / clean-flash gate

**Current Gateway-01 status, 2026-09-02: commissioned and reboot-proven.** Do not reflash the currently working gateway merely to repeat this gate. Its writable overlay was deliberately reset after stale state was discovered on the reused microSD, then it was rebuilt from the accepted SquashFS plus protected external identities. Post-reboot live state passed: RAK5146, Gateway EUI `0016c001f139a1cb`, `AS923/as923`, MQTT Forwarder QoS 1 to loopback Mosquitto, two public MQTT mTLS bridge sockets, Evidence writer/uploader + `/readyz`, permanent Ethernet management `192.168.20.11/24`, Wi-Fi backhaul, and ChirpStack `Last seen`.

For the current hardware, perform only the lightweight reuse check before touching sensor firmware:

1. Confirm RAK5146 is active on plain AS923 and Gateway EUI remains `0016c001f139a1cb`.
2. Confirm MQTT Forwarder is enabled with prefix `as923`, broker `tcp://127.0.0.1:1883`, and QoS `1`.
3. Confirm Mosquitto and both gateway-evidence services are running; require two established MQTT bridge sockets and Evidence `/readyz` over the installed mTLS identity.
4. Confirm ChirpStack shows a recent Gateway-01 `Last seen`.
5. SIM7600 enumeration is a separate physical-backhaul check. If the modem is not physically enumerating, continue on the already-proven Wi-Fi normal path; do not alter the LoRa region or a healthy cloud path.

For a future **new/reused-card flash**, verify the accepted image checksum, boot locally, and run `deployment/gateway/automation/commission-clean-overlay.sh preflight` before restoring secrets. A fresh provisioning target must not already contain production bridge/evidence keys or commissioning relay host overrides. If those appear before provisioning, treat that as stale writable OverlayFS state; preserve required recovery material, deliberately reset the writable overlay, reboot, then provision through the protected clean-overlay procedure. Never assume a compact factory-image write erased the expanded overlay area on reused media.

**GATEWAY_READY=YES.** The live reuse checks passed and real EMU-01 payload-v2 traffic has now exercised the post-reset Evidence path. Gateway writer/uploader operation, public Evidence mTLS, checkpoint/segment receipts, and trusted-decoder verification are physically proven. During final sensor assembly, repeat only the lightweight live checks needed to confirm nothing changed; do not recommission the gateway.

## Gate 2 - Compile and flash EMU-01

1. Arduino target: `WisBlock Core RAK4631 Board`.
2. Use pinned/proven sensor libraries and `SX126x-Arduino`; do not opportunistically upgrade libraries.
3. Compile `firmware/EMU01_Agriculture_Node/EMU01_Agriculture_Node.ino` with local `emu01_credentials.h`.
4. Record Arduino IDE, BSP, library versions, source revision/hash, build date in `chapter4-results/_device-baseline/EMU-01-firmware.txt`.
5. Upload only to the physically labelled EMU-01 Core A.
6. Reboot and capture Serial at 115200.

**STOP** on compiler error. Fix the first compiler/API mismatch against the already-proven library versions; do not change payload-v2 or radio profile to work around it.

## Gate 3 - Local sensor acceptance

Capture enough `SENSOR_TX` output to prove the production scheduler and sensor reads without reverting to the obsolete bench cadence. Require:

- sequence increments once per telemetry cycle;
- local sensor sampling remains approximately 60 seconds; normal network uplinks follow the proven nominal 5-minute schedule with per-cycle ±15-second jitter (285-315 seconds), while rain-transition event uplinks are separately randomized/rate-limited;
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
5. Require repeated 46-byte `UnconfirmedDataUp` frames on the production schedule: normal uplinks nominally every 5 minutes with ±15-second jitter. Treat additional rain-transition event uplinks separately; do not mistake them for cadence drift.
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
