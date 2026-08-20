# Operations 5. Troubleshooting the Buffered Gateway

Troubleshoot the lowest failing layer first. Do not reflash the gateway or change the radio region as a first response. Unless a section says otherwise, run shell commands over SSH on the Raspberry Pi gateway.

Use one known device uplink while testing. A healthy result at one layer proves only that layer; for example, an MQTT connection does not prove the RAK5146 is receiving the correct RF channels.

## Last seen: Never — checkpoint flow

When the gateway is registered but ChirpStack shows **Last seen: Never**, use these checkpoints in order and stop at the first failure:

1. **Radio / Concentratord** — active SX1302/SX1303 process is running, RAK5146 initializes on `/dev/spidev0.0`, and `logread -e chirpstack-concentratord | tail -n 100` reports the real `Gateway ID retrieved` EUI. Ignore inactive SX1301 gateway IDs.
2. **Gateway registration** — that exact 16-hex EUI is manually registered in ChirpStack. Missing from the list means not registered; present with Last seen Never means registered but no gateway event has been processed yet.
3. **MQTT Forwarder** — backend is Concentratord, server is `tcp://127.0.0.1:1883`, topic prefix matches the region, JSON is disabled, and TLS fields are empty.
4. **Local Mosquitto** — listener is only `127.0.0.1:1883`, Forwarder connects, and persistent state can be saved to `mosquitto.db`.
5. **TLS** — `openssl s_client` verifies CA, hostname, server certificate, and the gateway client certificate/key with return code `0`.
6. **MQTT authentication / ACL** — a certificate-authenticated `mosquitto_pub` receives `CONNACK (0)` and `PUBACK (... RC:0)` on the gateway's own allowed topic.
7. **Two bridges** — `gw-up-<GATEWAY_EUI>` and `gw-down-<GATEWAY_EUI>` remain connected; normal keepalive `PINGRESP` messages are present.
8. **Server broker** — direct `mosquitto_sub` against the broker sees `<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/stats`. Binary Protobuf output is normal.
9. **ChirpStack configuration** — ChirpStack is running without TOML errors; `enabled_regions` contains the region; the active v4 region file uses `[[regions]]`, enables the MQTT backend, and has matching topic prefix/broker credentials. Keep backup TOMLs outside the mounted ChirpStack config directory.
10. **ChirpStack UI** — Last seen becomes recent. Only now move to real RF-device join/uplink testing.

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

Never disable certificate verification to make the bridge connect. Correct the endpoint, trust, certificate/key pair, or exact topic ACL.

Isolate the connection in three layers:

```sh
# A. TCP only
nc -w 3 <MQTT_BROKER_FQDN> 8883 </dev/null
echo $?

# B. TLS, hostname, CA, and client-certificate verification
openssl s_client \
  -connect <MQTT_BROKER_FQDN>:8883 \
  -servername <MQTT_BROKER_FQDN> \
  -verify_hostname <MQTT_BROKER_FQDN> \
  -verify_return_error \
  -CAfile /etc/mosquitto/certs/ca.crt \
  -cert /etc/mosquitto/certs/<GATEWAY_EUI>.crt \
  -key /etc/mosquitto/certs/<GATEWAY_EUI>.key \
  </dev/null

# C. MQTT authentication + write ACL
mosquitto_pub \
  -h <MQTT_BROKER_FQDN> -p 8883 \
  --cafile /etc/mosquitto/certs/ca.crt \
  --cert /etc/mosquitto/certs/<GATEWAY_EUI>.crt \
  --key /etc/mosquitto/certs/<GATEWAY_EUI>.key \
  -i gw-cert-test-<GATEWAY_EUI> \
  -t '<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/test' \
  -m 'mtls-auth-test' -q 1 -d
```

Interpret them separately: TCP exit `0` proves only route/port; TLS must report verification return code `0`; MQTT `CONNACK (0)` proves authentication and `PUBACK (... RC:0)` proves the ACL allowed publication. Verify the final bridge fix by observing reconnect, queue drain without deleting `mosquitto.db`, and a new gateway event at the remote broker.

## 5. Remote broker receives gateway events but ChirpStack does not

**What appears to be failing:** the server-side MQTT-to-ChirpStack path.

Run this isolation test on the application server before relying on container stdout logs:

```bash
sudo timeout 45 docker exec mosquitto mosquitto_sub \
  -h 127.0.0.1 -p 1883 \
  -u chirpstack -P <CHIRPSTACK_MQTT_PASSWORD> \
  -t '<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/stats' \
  -v -C 1
```

A received Protobuf packet proves the gateway bridge reached the server broker even when `docker logs mosquitto --since 5m` is empty. Broker topic delivery and application stdout logging are different evidence.

Then confirm the active ChirpStack region MQTT backend subscribes to the same case-sensitive region prefix emitted by Gateway OS and uses the intended broker identity. A healthy result shows ChirpStack updating the registered Gateway EUI's last-seen time. If the broker has the topic but ChirpStack remains silent, check ChirpStack process health, TOML parse errors, `enabled_regions`, v4 `[[regions]]`, explicit MQTT backend enablement, topic prefix, credentials, and Protobuf handling.

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

## 11. Integrity journal does not advance

**What appears to be failing:** the independent Concentratord evidence path, not necessarily MQTT delivery.

Check the reviewed journal service status, its configured read-only Concentratord interface, persistent evidence directory, current sequence, open segment, and journal-specific logs/metrics using the implementation's documented diagnostics.

Healthy behavior shows a new sequence for a known real uplink while MQTT Forwarder independently publishes the corresponding local event.

Interpret the failure by layer:

```text
Concentratord healthy, MQTT healthy, journal stopped
  -> journal implementation/service/permission fault

journal process running, sequence unchanged
  -> source subscription/interface or filter fault

sequence advances, writes fail
  -> evidence storage/permissions/free-space fault
```

Do not point the journal at Mosquitto merely to make its counter move. Repair the independent source path and mark the unjournaled interval as an evidence gap.

## 12. Journal hash or sequence continuity fails

A complete record with an invalid hash, a broken previous-hash link, an unexplained sequence reset, or a segment-hash conflict is not routine log corruption.

Preserve the files and current storage image before attempting repair. Compare against the latest server checkpoint and the server's independently captured gateway MQTT events. Do not renumber records, recalculate a replacement chain in place, or delete the conflicting checkpoint.

Use:

```text
missing required object with no contradictory bytes -> evidence_gap
proven hash/payload/rollback conflict               -> integrity_failure
```

## 13. Cloud checkpoint is stale but MQTT is healthy

**What appears to be failing:** the evidence uploader/authentication/API path.

Check independently:

```text
DNS/route to evidence endpoint
TLS hostname and CA
per-gateway upload identity
latest local closed segment
unuploaded segment count/bytes
latest accepted server checkpoint age
API rejection/conflict logs
```

Do not treat healthy MQTT as proof that evidence upload works. Restore the uploader and verify the next accepted checkpoint extends the previous server anchor.

## 14. Journal and remote MQTT payload disagree

Freeze v2 evidence promotion for the affected lineage. Preserve:

```text
journal segment/object
remote MQTT captured event/object
Gateway EUI
PHYPayload digests
uplink/context identifiers
timestamps
forwarder/broker versions and logs
```

A payload conflict after the Concentratord split can indicate journal corruption, MQTT Forwarder/delivery-path alteration, wrong correlation, or compromise. Do not let Node-RED choose which copy is authoritative. Use the server verifier's deterministic matching contract.

## 15. Gateway evidence storage approaches its limit

Restore the evidence upload path before the emergency OS reserve is threatened. Do not delete the oldest unuploaded segment simply to clear the alarm.

If retention is genuinely exhausted, preserve the last valid sequence/hash and report the affected interval as `evidence_gap`. Mosquitto may still deliver telemetry; that does not restore missing evidence.

## 16. A Gateway OS or package upgrade causes a regression

Preserve the failed image reference, Mosquitto data and configuration, certificates, UCI configuration, and relevant logs. Do not overwrite the only known-good SD card.

Restore the previously tested image and configuration on spare media, boot it with the same RAK5146, and repeat Gateway ID, region, local publish, journal source/sequence/hash checks, cloud checkpoint/segment upload, WAN outage, reboot, queue drain, server reconciliation, OTAA uplink, and safe downlink checks. A successful rollback must restore behavior, not merely start the services.
