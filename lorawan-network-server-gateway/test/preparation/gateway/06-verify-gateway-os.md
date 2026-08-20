# Gateway 6. Verify Gateway OS and MQTT Delivery

This is the final gateway acceptance procedure for the dissertation test track. Verify the delivery path one layer at a time:

```text
RAK5146 -> Concentratord -> MQTT Forwarder -> local Mosquitto -> mTLS -> server Mosquitto -> ChirpStack
```

The checks must prove that:

- the RAK5146 is using the correct radio configuration;
- MQTT Forwarder publishes to the local broker;
- the local broker reaches the remote broker with the gateway certificate;
- uplinks remain queued during a WAN outage;
- the queue survives a gateway reboot;
- queued uplinks drain after connectivity returns;
- old downlink commands are not replayed after the outage;

Run the outage and reboot tests in staging or during an approved maintenance window.

## Before you begin

Have these values ready:

```text
Gateway address: <GATEWAY_IP>
Gateway EUI: <GATEWAY_EUI>
Region topic prefix: <REGION_TOPIC_PREFIX>
Remote broker: <MQTT_BROKER_FQDN>:8883
Expected queue free-space reserve: <BUFFER_FREE_SPACE_RESERVE_BYTES>
```

For the real radio tests, use an approved OTAA device configured for the same region and channel plan as the gateway and ChirpStack server.

When the gateway or device has not yet been registered in ChirpStack, complete the relevant sections of [Register and test the gateway](../../../deployment/gateway/operations/01-register-and-test.md), then return to the traffic tests in this manual.

## Fast triage: gateway is missing or Last seen never updates

Use these checkpoints in order. Stop at the first failing layer instead of changing several settings at once.

1. **Radio / concentrator** — Concentratord is running on the SX1302/SX1303 RAK5146 path, `/dev/spidev0.0` initializes, and its startup log reports the real EUI.
2. **Gateway registration** — the exact 16-hex EUI is manually present in ChirpStack. Missing from the list means **not registered**; present with **Last seen: Never** means registered but no gateway event has been successfully processed yet.
3. **MQTT Forwarder** — `event/stats` reaches `tcp://127.0.0.1:1883` under `as923/gateway/<GATEWAY_EUI>/...` with Protobuf / JSON disabled.
4. **Local broker** — Mosquitto listens only on `127.0.0.1:1883`, Forwarder is connected, and persistence writes `mosquitto.db`.
5. **TLS** — `openssl s_client` returns `Verify return code: 0 (ok)` for the DNS name used by the bridge.
6. **MQTT authentication / ACL** — a gateway-certificate `mosquitto_pub` returns `CONNACK (0)` and `PUBACK (... RC:0)` on its own allowed state topic.
7. **Bridge** — both `gw-up-<GATEWAY_EUI>` and `gw-down-<GATEWAY_EUI>` stay healthy and receive `PINGRESP`.
8. **Server broker** — a direct broker subscription sees `as923/gateway/<GATEWAY_EUI>/event/stats`.
9. **ChirpStack 4.9 configuration** — container is running with no TOML parse errors, `[network] enabled_regions` includes `as923`, the active region file uses v4 `[[regions]]`, MQTT backend is explicitly enabled, and broker credentials/topic prefix match.
10. **ChirpStack UI** — only after checkpoints 1-9 pass should **Last seen** become recent. Then proceed to a real RF device uplink.

Do these checks before changing the Gateway EUI, region, or reinstalling anything.

On the gateway:

```sh
logread -e chirpstack-concentratord | tail -n 100
uci show chirpstack-mqtt-forwarder
ls -l /etc/mosquitto/certs/
logread -e mosquitto | tail -n 80
logread -e chirpstack-mqtt-forwarder | tail -n 80
```

On the server VM:

```bash
cd /opt/lorawan-lab
docker compose ps mosquitto chirpstack
docker compose logs --since=10m --tail=200 mosquitto chirpstack
```

Interpret the result in this order:

1. The ChirpStack gateway record must already exist and use the exact 16-hex EUI reported by Concentratord.
2. MQTT Forwarder must point to `tcp://127.0.0.1:1883`, not directly to server port `8883`.
3. The gateway client key must be readable by Mosquitto; a `root:root` key with mode `0600` will prevent the bridge from authenticating.
4. The remote bridge must authenticate to the server on TCP `8883`, and the broker certificate SAN must match the exact IP or DNS name used by the bridge.
5. A real local event must appear under `as923/gateway/<GATEWAY_EUI>/event/#` before ChirpStack can update **Last seen**.
6. If the remote broker receives that event but ChirpStack still does not update, compare the server `as923` region/topic prefix and the registered Gateway EUI.

## Step 1: Verify Gateway OS and network access

Run over SSH:

```sh
cat /etc/os-release
uname -a
date -u
ip addr
ip route
nslookup <MQTT_BROKER_FQDN>
monit status
ps w | grep '[m]osquitto'
```

Confirm that:

- the expected ChirpStack Gateway OS Base release is running;
- the UTC date and time are correct;
- the intended backhaul interface has an address;
- a default route exists;
- the remote broker name resolves to the expected address;
- Concentratord and MQTT Forwarder remain running;
- the local Mosquitto process is running;

Fix network or time problems before testing TLS. An incorrect clock can make a valid certificate appear expired or not yet valid.

## Step 2: Verify the effective gateway configuration

Run:

```sh
logread -e chirpstack-concentratord | tail -n 100
uci show chirpstack-concentratord
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
```

Check the saved values against the setup:

- Concentratord uses the RAK5146 SX1302/SX1303 profile.
- The configured channel plan is the exact approved regional variant.
- The active SX1302/SX1303 startup log reports the expected 16-hexadecimal Gateway EUI; ignore inactive SX1301 `gateway_id` values.
- MQTT Forwarder uses the Concentratord backend.
- MQTT Forwarder connects to `tcp://127.0.0.1:1883`.
- MQTT Forwarder uses QoS 1 and the fixed `gw-fwd-<GATEWAY_EUI>` client ID when supported by the installed release.
- The MQTT topic prefix is `<REGION_TOPIC_PREFIX>`.
- UDP Forwarder has no enabled remote server.

Inspect both active broker files without displaying the private key:

```sh
grep -E '^(persistence|persistence_location|persistence_file|autosave_interval|max_queued_messages|max_queued_bytes|listener|protocol|allow_anonymous|include_dir)' \
  /etc/mosquitto/mosquitto.conf

grep -E '^(connection |address |remote_clientid|cleansession|bridge_cafile|bridge_certfile|bridge_keyfile|bridge_insecure|topic )' \
  /etc/mosquitto/conf.d/bridge.conf
```

Confirm that:

- persistence is enabled;
- message and byte limits are finite;
- the listener is `1883 127.0.0.1`;
- both bridge addresses use the verified DNS name `<MQTT_SERVER_NAME>:8883` (lab: `lora-test-server:8883`) unless the certificate SAN explicitly contains the IP used;
- `bridge_insecure` is `false`;
- event and state topics go out at QoS 1;
- command topics come in at QoS 0;
- the uplink bridge uses a persistent session;
- the downlink bridge uses a clean session.

## Step 3: Verify queue storage and permissions

Run:

```sh
df -h /etc/mosquitto/data
mount
ls -ld /etc/mosquitto/data /etc/mosquitto/certs
ls -l /etc/mosquitto/data
ls -l /etc/mosquitto/certs
```

Pass this step only when:

- `/etc/mosquitto/data` is on persistent writable storage;
- the path is not under `/tmp` or another temporary filesystem;
- the `mosquitto` user can write the data directory;
- the private key is not world-readable;
- current free space is greater than the configured reserve.

The `mosquitto.db` file can be absent before Mosquitto has saved any persistent state. It should appear or change after the outage test creates queued messages.

## Step 3A: Compare the gateway with the off-device security baseline

The buffer setup manual created `<GATEWAY_EUI>-mqtt-security-baseline.txt` on the administration workstation. This step independently recalculates the broker-configuration hash and certificate fingerprints and compares them with that approved off-device record.

On the gateway, create a fresh comparison file:

```sh
umask 077
{
  printf 'gateway_eui=%s\n' '<GATEWAY_EUI>'
  printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sha256sum /etc/mosquitto/mosquitto.conf /etc/mosquitto/conf.d/bridge.conf
  openssl x509 -in "/etc/mosquitto/certs/<GATEWAY_EUI>.crt" -noout -fingerprint -sha256 -serial -dates
  openssl x509 -in /etc/mosquitto/certs/ca.crt -noout -fingerprint -sha256 -subject -issuer
} > /tmp/gateway-mqtt-security-current.txt
cat /tmp/gateway-mqtt-security-current.txt
```

On the administration workstation, copy the current values:

```bash
scp root@<GATEWAY_IP>:/tmp/gateway-mqtt-security-current.txt \
  ./<GATEWAY_EUI>-mqtt-security-current.txt
```

Compare everything except the intentionally changing capture timestamp:

```bash
grep -v '^captured_utc=' ./<GATEWAY_EUI>-mqtt-security-baseline.txt \
  > /tmp/gateway-mqtt-baseline.normalized

grep -v '^captured_utc=' ./<GATEWAY_EUI>-mqtt-security-current.txt \
  > /tmp/gateway-mqtt-current.normalized

diff -u \
  /tmp/gateway-mqtt-baseline.normalized \
  /tmp/gateway-mqtt-current.normalized
```

Pass condition: `diff` prints nothing and returns exit status `0`.

If it prints a difference, **stop gateway acceptance** and identify the exact changed configuration line or certificate. Do not overwrite the baseline just because the current gateway is online. For an intentional configuration change or certificate rotation, first complete the relevant setup procedure and all validation tests, document the approved change, then capture a new baseline from the known-good state.

Clean up temporary comparison files after review:

```bash
rm -f \
  /tmp/gateway-mqtt-baseline.normalized \
  /tmp/gateway-mqtt-current.normalized \
  ./<GATEWAY_EUI>-mqtt-security-current.txt
```

On the gateway:

```sh
rm -f /tmp/gateway-mqtt-security-current.txt
```

This baseline detects later configuration/certificate drift. It does not prove that `mosquitto.db` message contents were never modified by a privileged attacker.

## Step 4: Verify the loopback MQTT listener

Run:

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

The listener must be:

```text
127.0.0.1:1883
```

Fail this step when the listener is bound to `0.0.0.0`, `[::]`, a LAN address, or a WAN address. The local listener permits anonymous access only because it is restricted to loopback.

## Step 5: Verify a local gateway event

Open an SSH session and subscribe to the local event topic:

```sh
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t '<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/#' -v
```

Generate one uplink from the approved test device.

A message must appear under the expected region prefix and Gateway EUI. The payload uses Protobuf and may not be readable as text. The topic and message arrival are the important checks.

Press `Ctrl+C` after the message arrives.

When no local event appears, troubleshoot Concentratord, the device channel plan, MQTT Forwarder, and the loopback broker before checking the remote TLS bridge.

## Step 6: Verify the remote broker connection

Do not rely on empty `docker logs mosquitto` output to prove that no traffic arrived. Container stdout and MQTT topic delivery are different checks.

On the server VM, first prove any gateway topic reaches the broker:

```bash
cd /opt/lorawan-lab
sudo timeout 45 docker exec mosquitto mosquitto_sub \
  -h 127.0.0.1 \
  -p 1883 \
  -u chirpstack \
  -P chirpstack_pass \
  -t 'as923/gateway/#' \
  -v \
  -d \
  -C 1
```

Then prove a live stats packet for this EUI:

```bash
sudo timeout 45 docker exec mosquitto mosquitto_sub \
  -h 127.0.0.1 \
  -p 1883 \
  -u chirpstack \
  -P chirpstack_pass \
  -t 'as923/gateway/<GATEWAY_EUI>/event/stats' \
  -v \
  -C 1
```

The payload is Protobuf and can look binary. The successful lab packet exposed the Gateway EUI and metadata such as model `rak_5146`, Concentratord `4.7.1`, and MQTT Forwarder `4.6.0`.

After topic delivery is proven, inspect application logs if needed:

```sh
docker compose logs --since=5m --tail=200 mosquitto chirpstack
```

Confirm that:

- `gw-up-<GATEWAY_EUI>` connects with the gateway certificate;
- `gw-down-<GATEWAY_EUI>` connects with the same gateway identity;
- the broker accepts event and state writes only for this Gateway EUI;
- the broker allows command reads only for this Gateway EUI;
- ChirpStack receives the regional gateway event topic.

Also confirm in the ChirpStack web interface that the registered gateway's **last seen** time updates after the test uplink.

### Verify cross-gateway isolation

When a second test Gateway EUI is available, attempt to publish or subscribe outside this gateway's allowed topic path using the first gateway certificate. The remote broker must deny the request.

Do not weaken the ACL when this test fails. Correct the certificate identity, topic path, or per-gateway ACL rule.

## Step 7: Verify normal LoRaWAN traffic

Use the approved OTAA test device.

1. Power-cycle or reset the device so it performs a fresh join when appropriate.
2. Confirm that OTAA succeeds.
3. Send one uplink with a known payload or device frame counter.
4. Confirm that ChirpStack shows the expected Gateway EUI for the received uplink.
5. Confirm that the application receives one canonical record for the uplink.
6. Schedule one harmless Class A downlink.
7. Confirm that the device receives the downlink in the expected receive window.

QoS 1 can redeliver an MQTT message after a reconnect. The application or database must prevent one radio uplink from creating duplicate canonical records.

## Step 8: Verify WAN-outage buffering

Disconnect only the gateway's WAN path. Keep the Raspberry Pi, RAK5146, Concentratord, MQTT Forwarder, and local Mosquitto running.

Before disconnecting WAN, run:

```sh
stat -c 'size=%s modified=%y' /etc/mosquitto/data/mosquitto.db 2>/dev/null || \
  ls -l /etc/mosquitto/data

df -h /etc/mosquitto/data
```

Then perform the test:

1. Disconnect the gateway WAN or block only the route to the remote broker.
2. Keep an SSH session through a separate management path when possible.
3. Generate a known number of real uplinks.
4. Confirm that the local `mosquitto_sub` test still receives the gateway event topics.
5. Confirm that ChirpStack does not receive the outage uplinks yet.
6. Check `/etc/mosquitto/data/mosquitto.db` again. It should be created or increase after Mosquitto saves the queued state.
7. Confirm that free space remains above `<BUFFER_FREE_SPACE_RESERVE_BYTES>`.
8. Restore WAN connectivity.
9. Confirm that the uplink bridge reconnects.
10. Confirm that all expected uplinks reach ChirpStack and the application.
11. Confirm that the local queue stops growing after it drains.

The delivered MQTT count can include QoS 1 redelivery. Validate the application result using unique device identifiers and frame counters rather than assuming every MQTT delivery is unique.

Continuous queue growth after WAN recovery means the remote DNS, route, TLS, certificate, broker ACL, topic prefix, or ChirpStack subscription is still failing.

## Step 9: Verify queue persistence across reboot

Repeat this test while the WAN remains unavailable:

1. Generate several uplinks and confirm that the local queue grows.
2. Reboot the gateway cleanly:

   ```sh
   reboot
   ```

3. Wait for Gateway OS to return.
4. Reconnect over SSH.
5. Confirm that Concentratord, MQTT Forwarder, and Mosquitto restart.
6. Confirm that `/etc/mosquitto/data/mosquitto.db` still exists and contains the queued state.
7. Generate another uplink while WAN is still unavailable.
8. Restore WAN connectivity.
9. Confirm that both the pre-reboot and post-reboot uplinks reach ChirpStack.
10. Confirm that the application retains one canonical record per real uplink.

The buffer is not persistent when messages queued before reboot disappear.

## Step 10: Verify that stale downlinks are not replayed

The downlink bridge uses QoS 0 and a clean session so old commands are not intentionally retained.

1. Disconnect the gateway WAN.
2. Attempt one harmless test downlink through ChirpStack.
3. Allow the downlink and its receive window to expire.
4. Restore WAN connectivity.
5. Confirm that the expired downlink is not transmitted after recovery.
6. Send a new Class A downlink after the next uplink.
7. Confirm that the new downlink succeeds.

Stop and correct the downlink bridge when an expired command is transmitted after reconnecting.

## Troubleshooting by failing layer

### Concentratord has no stable Gateway EUI

Return to [03-configure-concentratord.md](03-configure-concentratord.md). Check the RAK5146 profile, SPI assembly, power, and exact channel plan.

### Local MQTT receives no gateway event

Check MQTT Forwarder's backend, loopback address, QoS, topic prefix, client ID, and packet filters. Do not change the remote broker yet.

### Local events work but the remote broker receives nothing

Check gateway DNS, UTC time, bridge certificate files, certificate/key match, broker hostname, and remote ACL.

### The remote broker receives events but ChirpStack does not update

Compare `<REGION_TOPIC_PREFIX>` with the regions enabled on the ChirpStack server. Confirm the exact Gateway EUI registration and the broker topic subscription.

### The queue does not grow during an outage

Confirm that MQTT Forwarder publishes at QoS 1, the uplink bridge has `cleansession false`, persistence is enabled, and the persistence directory is writable by `mosquitto`.

### The queue grows during normal connectivity

The bridge is not successfully delivering. Check route, DNS, time, TLS, certificate identity, broker ACL, and topic prefix in that order.

### Queued messages disappear after reboot

Confirm that `/etc/mosquitto/data` is persistent, Mosquitto can write it, and the service stops cleanly during a normal reboot. Recheck the persistence settings and autosave interval.

### An old downlink is transmitted after reconnecting

Confirm that the downlink bridge uses `cleansession true`, the command topic is `in 0`, and no second MQTT or UDP path is retaining commands.

## Final acceptance

The gateway is ready for normal operation when all of these are true:

- Gateway OS Base boots with correct time and network access.
- Concentratord initializes the RAK5146 with the approved channel plan.
- The Gateway EUI remains stable.
- MQTT Forwarder publishes Protobuf messages to `127.0.0.1:1883` at QoS 1.
- Local Mosquitto listens only on loopback.
- Both remote bridges authenticate with the gateway certificate.
- The remote ACL restricts access to this Gateway EUI.
- The current broker configuration and certificate fingerprints match the approved off-device baseline.
- A real OTAA join, uplink, and safe Class A downlink succeed.
- Uplinks remain buffered during WAN loss.
- The queue survives a clean gateway reboot.
- Buffered uplinks drain after WAN recovery.
- Duplicate MQTT delivery does not create duplicate canonical application records.
- Expired downlinks are not replayed.
- Configured queue limits are finite and preserve the required free-space reserve.
- UDP Forwarder remains disabled.

Continue with [Gateway operations](../../../deployment/gateway/operations/01-register-and-test.md) for registration, routine tests, backup, recovery, and troubleshooting.
