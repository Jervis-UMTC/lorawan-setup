# 8. Dragino Sensor Troubleshooting

Troubleshoot in order. The first question is always: **did ChirpStack receive any RF frame from this device?**

## 8.1 The gateway or ChirpStack is not healthy

Check the services:

~~~bash
sudo systemctl status ttn-gateway --no-pager -l
~~~

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose ps
~~~

Check recent gateway logs:

~~~bash
sudo journalctl -u ttn-gateway -n 100 --no-pager
~~~

Check the bridge:

~~~bash
docker compose logs --since=5m --tail=100 chirpstack-gateway-bridge
~~~

Fix the gateway path first using [10-troubleshooting.md](../10-troubleshooting.md). A sensor cannot join through an offline gateway.

## 8.2 No JoinRequest appears

Likely causes:

- dead, missing, or incorrectly installed battery;
- wrong button/reset procedure;
- sensor is asleep and has not reached its next scheduled transmission;
- sensor is not a LoRaWAN model;
- sensor firmware uses another regional band;
- sensor is too far away or shielded;
- gateway antenna or RF path issue; or
- sensor is transmitting on channels the gateway is not configured to receive.

Actions:

1. Move the sensor close to the gateway for the first test.
2. Check the battery with the sensor's specified procedure.
3. Confirm the exact band from the label or vendor tool.
4. Perform only the documented reset/join action.
5. Observe the gateway and bridge logs while the action occurs.
6. Wait through the documented reporting interval before repeating the test.

Credentials cannot fix a frame that never reaches the gateway.

## 8.3 JoinRequest appears but JoinAccept does not

This proves the RF uplink path is working. Concentrate on provisioning and downlink:

- DevEUI in ChirpStack matches the sensor exactly;
- JoinEUI/AppEUI matches the sensor when required;
- AppKey is correct and has no missing leading zero;
- NwkKey is correct if the device is LoRaWAN 1.1;
- device profile is OTAA;
- MAC version and Regional Parameters revision match the sensor;
- profile region is AS923-3; and
- gateway has a working downlink path.

Do not change the AppKey repeatedly without recording which value is currently in the sensor. If credentials are uncertain, use the Dragino provisioning tool/manual to establish a known pair, then update ChirpStack once.

## 8.4 JoinAccept appears but the device does not become active

The gateway may have scheduled a downlink, but the sensor may not have received it during its receive window.

Check:

- antenna connection and gateway transmit path;
- sensor battery and physical placement;
- region and RX parameters;
- sensor clock and join timing;
- packet-forwarder downlink errors; and
- whether another process is using the concentrator.

Keep the sensor close to the gateway for this test. A sensor can sometimes transmit an uplink successfully while the downlink margin is insufficient.

## 8.5 Device joins but sends no application data

This usually means activation succeeded but the sensor is waiting for its scheduled report.

- check the configured reporting interval;
- wait for the next scheduled uplink;
- use the documented sensor reset/report button if it provides an immediate test uplink;
- confirm the device is not in a sleep or storage mode; and
- check that the physical probe or input is connected.

For an S31/S31B, the vendor default reporting interval is commonly around 20 minutes, but the actual value can be changed.

## 8.6 Uplink is present but has a decryption or MIC error

This is normally a provisioning or session-state problem:

- wrong AppKey or NwkKey;
- wrong DevEUI or JoinEUI;
- wrong LoRaWAN version/profile;
- stale activation after changing keys; or
- frame-counter state after restoring or reusing a device.

Confirm the keys and profile against the physical sensor. Avoid deleting and recreating devices as a first reaction; preserve the event history until the cause is understood.

## 8.7 Uplink is decrypted but not decoded

The network is working. Check the application layer:

- exact model is confirmed;
- correct codec is attached to the device profile;
- the codec is written for ChirpStack v4's decodeUplink interface;
- the fPort matches the codec's supported port;
- the bytes are not from a different firmware payload revision; and
- the codec saved without a JavaScript syntax error.

For S31/S31B, use [dragino-lsn50v2-s31-decoder.js](../../docs/codecs/dragino-lsn50v2-s31-decoder.js). For a different Dragino model, remove the S31 codec and obtain the correct decoder.

## 8.8 Decoded values are wrong

Typical causes:

- wrong Dragino model selected;
- wrong port interpreted as a normal data port;
- S31 and another sensor codec mixed together;
- signed temperature bytes interpreted as unsigned;
- timestamp unit or timezone misunderstood;
- sensor input wiring is wrong; or
- payload specification changed with firmware.

Compare raw bytes, fPort, firmware version, and vendor payload documentation. Do not change byte order until the payload specification proves that the byte order is wrong.

## 8.9 Device works near the gateway but not at its installation site

This is an RF/site problem rather than a ChirpStack enrollment problem. Check:

- antenna placement and connector tightness;
- metal, concrete, water, foliage, and greenhouse structure;
- gateway height and line of sight;
- sensor orientation;
- channel occupancy and interference; and
- link metrics such as RSSI and SNR over several uplinks.

Move the sensor temporarily to an intermediate location to find whether the failure follows distance or a particular obstruction.

## 8.10 Sensor stops after a firmware update or key change

Treat a firmware update as a new compatibility event:

1. record the new firmware version;
2. re-check the regional sub-band;
3. re-check LoRaWAN version and payload format;
4. verify keys were not reset or regenerated;
5. verify the ChirpStack profile; and
6. perform a fresh join if the vendor requires it.

Do not assume that a firmware update preserves the same payload codec or regional behavior.

Next: [09-device-inventory-template.md](09-device-inventory-template.md)
