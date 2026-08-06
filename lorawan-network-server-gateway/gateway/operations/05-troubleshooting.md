# Operations 5. Troubleshooting the Buffered Gateway

Troubleshoot the lowest failing layer first. Do not reflash the gateway or change the radio region as a first response. Unless a section says otherwise, run shell commands over SSH on the Raspberry Pi gateway.

Use one known device uplink while testing. A healthy result at one layer proves only that layer; for example, an MQTT connection does not prove the RAK5146 is receiving the correct RF channels.

## 1. Gateway does not boot or cannot be reached

**What appears to be failing:** the Raspberry Pi, Gateway OS, Ethernet/Wi-Fi path, or management addressing.

**Most likely causes:** inadequate power, a failed or corrupted SD card, no network link, a changed DHCP address, or the wrong image for the Raspberry Pi 4B.

From the commissioning workstation, check the router or DHCP server for the gateway lease, then test the observed address:

```bash
ping <GATEWAY_IP_ADDRESS>
ssh root@<GATEWAY_IP_ADDRESS>
```

A healthy gateway has a stable lease, responds on the management network, and opens LuCI or SSH. No lease usually points to power, boot media, or link state. A lease with no SSH response points to addressing, firewall, or a partially booted system.

The smallest safe fix is to verify the power supply and cable, reseat the SD card with power removed, and test the approved Gateway OS Base image on a spare card. Preserve the original card for log or configuration recovery. Verify the fix by rebooting once and confirming that the same management address is reachable again.

## 2. Concentratord has no stable Gateway ID

**What appears to be failing:** the service that owns the RAK5146 concentrator.

Run on the gateway:

```sh
monit status
uci show chirpstack-concentratord
logread -e chirpstack-concentratord
```

A healthy result shows the Concentratord service running, the SX1302/SX1303 chipset and RAK5146 shield selected, the confirmed channel plan, and one stable 16-hexadecimal Gateway ID.

Interpret abnormal output before changing anything:

```text
wrong shield or chipset -> RAK5146 profile mismatch
SPI or reset error      -> HAT seating, power, reset mapping, or hardware fault
calibration loop        -> frequency variant, clock, profile, or hardware problem
Gateway ID changes      -> unstable concentrator identity or hardware state
```

For a profile mismatch, correct only the observed chipset, shield, or channel-plan value in **ChirpStack > Concentratord**. For SPI, reset, or hardware errors, power down before reseating the HAT. Do not repeatedly change the Gateway EUI in ChirpStack. Verify the fix by rebooting and confirming the same Gateway ID appears without restart or calibration loops.

## 3. MQTT Forwarder cannot publish to the local broker

**What appears to be failing:** the gateway-local hop from MQTT Forwarder to Mosquitto.

Run on the gateway:

```sh
uci show chirpstack-mqtt-forwarder
logread -e chirpstack-mqtt-forwarder
logread -e mosquitto
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Healthy configuration uses `tcp://127.0.0.1:1883`, Protobuf, backend `concentratord`, QoS 1, and a Mosquitto listener bound only to `127.0.0.1:1883`.

Abnormal results mean:

```text
connection refused     -> Mosquitto is stopped, invalid, or listening on another port
WAN broker configured  -> MQTT Forwarder bypasses the persistent local buffer
QoS is not 1           -> the local broker does not provide the intended durable acknowledgement
0.0.0.0 or LAN listener-> the local broker is exposed beyond the gateway
```

Validate the Mosquitto configuration before restarting it, then correct only the local address, listener, or QoS setting that differs. Verify with one real uplink: MQTT Forwarder logs should stop reporting connection errors and Mosquitto should receive the regional gateway event topic.

## 4. Local broker receives messages but the remote bridge is offline

**What appears to be failing:** DNS, route/4G, system time, TLS identity, broker ACLs, or the remote MQTT service.

Run on the gateway:

```sh
logread -e mosquitto
nslookup <MQTT_BROKER_FQDN>
ip route
date -u
df -h /etc/mosquitto/data
ls -l /etc/mosquitto/data/mosquitto.db
```

Healthy output shows the broker name resolving to the intended endpoint, a usable default route, correct UTC time, sufficient free space, a persistent `mosquitto.db`, and successful bridge authentication for both `gw-up-<GATEWAY_EUI>` and `gw-down-<GATEWAY_EUI>`.

Use the first matching failure:

```text
DNS or route failure -> WAN path unavailable; repair DNS, APN, or route and leave the queue running
unknown CA or hostname -> wrong trust file or certificate SAN; install the intended CA and hostname
client rejected -> expired/wrong certificate, EKU, CN, or private-key mismatch
not authorized -> certificate identity, Gateway EUI, region prefix, or ACL mismatch
queue grows -> remote service is unavailable or draining more slowly than new traffic arrives
queue limit reached -> the outage exceeded finite capacity and some delivery may be lost
```

Never disable certificate verification to make the bridge connect. Correct the endpoint, trust, certificate/key pair, or exact topic ACL. Verify by observing the bridge reconnect, the queue shrink without deleting `mosquitto.db`, and a new real uplink appear at the remote broker.

## 5. Remote broker receives gateway events but ChirpStack does not

**What appears to be failing:** the server-side MQTT-to-ChirpStack path.

Run the relevant broker and ChirpStack log commands on the application server, not on the gateway. Confirm the active ChirpStack region MQTT backend subscribes to the same case-sensitive region prefix emitted by Gateway OS and uses the intended broker identity and trust files.

A healthy result shows the broker accepting the gateway event topic and ChirpStack updating the registered Gateway EUI's last-seen time. If the broker has the topic but ChirpStack remains silent, the likely cause is a region-prefix, backend, credential, or Protobuf mismatch.

Make the smallest correction to the ChirpStack region configuration or broker ACL, restart only the affected service, and verify with a fresh uplink. Do not add ChirpStack Gateway Bridge; this architecture sends Concentratord Protobuf topics directly to ChirpStack's MQTT region backend.

## 6. Duplicate application or telemetry rows

**What appears to be failing:** downstream idempotency, not gateway transport.

QoS 1 and reconnects can legitimately redeliver the same event. Check that Node-RED uses ChirpStack `deduplicationId` or the documented stable fallback event key and that the TimescaleDB unique indexes exist.

A healthy replay leaves one uplink row and one row per normalized metric for the event key. More than one row means the application or database duplicate guard is missing or uses an unstable key. Fix the event-key or unique-index path and replay the same sanitized event again. Do not reduce gateway QoS to hide duplicate storage.

## 7. Buffered messages disappear after reboot

**What appears to be failing:** Mosquitto persistence or the selected storage path.

Run on the gateway before and after a controlled reboot:

```sh
df -h /etc/mosquitto/data
mount | grep -E ' /tmp |/etc/mosquitto/data'
ls -l /etc/mosquitto/data/mosquitto.db
logread -e mosquitto
```

Healthy behavior keeps the data path on persistent storage, saves a non-empty database with the intended owner, and reopens the queue after restart. A missing database, tmpfs path, ownership error, or repeated persistence warning means the queue is not durable.

Correct the path, permissions, or persistence setting without deleting the only queue database. Verify with the documented WAN-loss, reboot, reconnect, and drain test. Do not claim durable buffering until a real event survives that sequence.

## 8. A stale downlink transmits after recovery

**What appears to be failing:** downlink session cleanup or an unintended broker queue.

Confirm the downlink bridge uses `cleansession true` and the command topic direction is `in 0`. Check that no second client session, retained message, or automation path is publishing the old command.

Healthy behavior drops commands whose Class A receive window has passed. Any stale transmission means automation must remain disabled. Remove the unintended persistent session or retained command, reconnect, then test with a harmless device command whose receive window and result can be observed.

## 9. RF uplinks or downlinks fail while MQTT is connected

**What appears to be failing:** the radio, device registration, or LoRaWAN scheduling layer.

Compare the antenna band and connection, RAK5146 frequency variant, Concentratord channel plan, ChirpStack region, device profile, device regional variant, OTAA root-key reference, frame counters, class, receive windows, gateway time, FPort, and legal transmit limits.

Healthy commissioning shows a JoinRequest, JoinAccept, a later data uplink, and—when required—a safe downlink in the expected receive window. A connected MQTT bridge with no RF event means backhaul is healthy but radio or device settings are not. Correct the first mismatched region, profile, key reference, or antenna condition and repeat one join/uplink test.

## 10. UDP Forwarder traffic appears

**What appears to be failing:** the supported architecture has been bypassed.

Run on the gateway:

```sh
uci show chirpstack-udp-forwarder
monit status
```

Healthy output has no UDP server configured and the UDP Forwarder disabled. Remove only the unintended UDP server entries, disable the service, and verify that MQTT Forwarder continues delivering a real uplink through the local broker.

## 11. A Gateway OS or package upgrade causes a regression

Preserve the failed image reference, Mosquitto data and configuration, certificates, UCI configuration, and relevant logs. Do not overwrite the only known-good SD card.

Restore the previously tested image and configuration on spare media, boot it with the same RAK5146, and repeat Gateway ID, region, local publish, WAN outage, reboot, queue drain, OTAA uplink, and safe downlink checks. A successful rollback must restore behavior, not merely start the services.
