# Gateway 6. Verify Gateway OS, MQTT Buffering, and Integrity

This procedure verifies both gateway paths one layer at a time:

```text
delivery -> MQTT Forwarder -> Mosquitto -> remote MQTT

evidence -> integrity journal -> hash chain -> cloud checkpoint/segment upload
```

Neither path is considered proven merely because its process is running.

A service showing as running is not enough. The checks must prove that:

- the RAK5146 is using the correct radio configuration;
- MQTT Forwarder publishes to the local broker;
- the local broker reaches the remote broker with the gateway certificate;
- uplinks remain queued during a WAN outage;
- the queue survives a gateway reboot;
- queued uplinks drain after connectivity returns;
- old downlink commands are not replayed after the outage;
- the journal records the same real uplink source independently of MQTT Forwarder;
- sequence and record/segment hashes remain continuous across normal operation and reboot;
- a WAN outage does not stop local journaling or create a false server checkpoint;
- recovery uploads missing segments and extends the last accepted off-device checkpoint;
- the server can reconcile journal evidence with the delivered remote gateway MQTT event.

Run the outage and reboot tests in staging or during an approved maintenance window.

## Before you begin

Have these values ready:

```text
Gateway address: <GATEWAY_IP>
Gateway EUI: <GATEWAY_EUI>
Region topic prefix: <REGION_TOPIC_PREFIX>
Remote broker: <MQTT_BROKER_FQDN>:8883
Expected queue free-space reserve: <BUFFER_FREE_SPACE_RESERVE_BYTES>
Journal implementation/version: <PINNED_JOURNAL_VERSION>
Journal storage budget: <JOURNAL_STORAGE_BUDGET>
Evidence ingest endpoint: https://<EVIDENCE_INGEST_FQDN>
```

For the real radio tests, use an approved OTAA device configured for the same region and channel plan as the gateway and ChirpStack server.

When the gateway or device has not yet been registered in ChirpStack, complete the relevant sections of [Register and test the gateway](../operations/01-register-and-test.md), then return to the traffic tests in this manual.

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
- when the reviewed journal implementation has been installed, its service and uploader are healthy without repeatedly restarting.

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
- The successful active SX1302/SX1303 startup log reports the expected 16-hexadecimal Gateway EUI; ignore inactive SX1301 `gateway_id` values.
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
- both bridge addresses use `<MQTT_BROKER_FQDN>:8883`;
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
  openssl x509 -in /etc/mosquitto/certs/<GATEWAY_EUI>.crt -noout -fingerprint -sha256 -serial -dates
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

## Step 5A: Verify one journal record for the same real uplink

Complete this step only after the reviewed journal implementation described in [Gateway 4A](04a-configure-gateway-integrity-journal.md) has been built, pinned, and installed.

Generate one fresh real uplink while observing both the local MQTT event and the journal's documented status/inspection interface.

Record, without exposing unrestricted payloads in ordinary logs:

```text
Gateway EUI
journal sequence
boot ID
PHYPayload or approved PHYPayload digest
record hash
previous-record hash
current segment ID
```

Pass when:

- exactly one new journal sequence corresponds to the known uplink;
- the Gateway EUI is correct;
- the journal source is the supported Concentratord event interface, not a copy taken after Node-RED or ChirpStack;
- recomputing the versioned record hash produces the stored hash;
- the record references the preceding valid hash;
- MQTT Forwarder still produces the normal local event independently.

If the journal implementation has no safe command/API for inspecting and verifying a staging record, **stop deployment and add one to the reviewed implementation**. Do not parse undocumented binary files with an improvised production script.

## Step 6: Verify the remote broker connection

Empty broker container stdout does not prove that no MQTT traffic arrived. Verify the topic directly first:

```bash
sudo timeout 45 docker exec mosquitto mosquitto_sub \
  -h 127.0.0.1 -p 1883 \
  -u chirpstack -P <CHIRPSTACK_MQTT_PASSWORD> \
  -t '<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/stats' \
  -v -C 1
```

A binary-looking Protobuf payload is normal. If this succeeds while ChirpStack still shows `Last seen: Never`, the gateway bridge path is proven and troubleshooting moves to ChirpStack region/backend configuration and exact EUI registration.

Then inspect application stdout if needed:

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

## Step 8A: Verify the journal during WAN outage and recovery

Run this together with Step 8 so the same real test uplinks exercise both paths.

Before WAN loss, capture the latest accepted server checkpoint:

```text
checkpoint gateway ID
checkpoint sequence
checkpoint record hash
checkpoint segment hash
server receipt ID/time
```

Then disconnect only WAN/backhaul and generate the known test uplinks.

During the outage pass only when:

- journal sequence continues increasing;
- the current segment continues to append/rotate within its configured budget;
- closed unuploaded segments remain local;
- the cloud checkpoint does **not** advance while the gateway cannot reach the evidence endpoint;
- Mosquitto and the journal use separate storage budgets and the OS free-space reserve remains safe.

After WAN returns, verify through the server-side procedures in [Gateway Integrity](../../server/integrations/gateway-integrity/00-README.md):

1. missing closed segments upload;
2. their first chain link extends the last accepted pre-outage anchor;
3. record and segment hashes verify;
4. the independently captured remote MQTT gateway events match the journal records;
5. a new checkpoint is accepted only after continuity is established;
6. unresolved missing evidence is reported as `evidence_gap` and contradictory evidence as `integrity_failure`.

Do not mark outage telemetry gateway-verified merely because Mosquitto successfully drained it.

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

## Step 9A: Verify journal continuity across reboot

Perform this during the same controlled WAN-outage reboot test when possible.

Before reboot record:

```text
last journal sequence
last record hash
boot ID
open/last closed segment
```

After reboot:

1. verify the journal recovers the last valid complete record;
2. verify the boot ID changes;
3. verify the next sequence continues instead of resetting;
4. generate a fresh uplink;
5. verify its `previous_record_hash` references the last valid pre-reboot chain state;
6. restore WAN and prove the server accepts continuity across the reboot boundary.

Only an incomplete final/torn record may be discarded automatically. A previously complete record with an invalid hash is an integrity incident, not normal crash cleanup.

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

## Step 11: Verify queue limits without filling the SD card

Perform this only in staging.

1. Confirm the configured `max_queued_messages` and `max_queued_bytes` values.
2. Confirm the current free-space reserve.
3. Disconnect WAN.
4. Generate controlled test traffic until the configured queue limit is approached.
5. Confirm that storage use remains bounded.
6. Confirm that the filesystem does not become full or read-only.
7. Restore WAN and verify that retained messages drain.
8. Identify which messages were retained or dropped using device frame counters.

The correct behavior is bounded loss at the configured limit while preserving the gateway filesystem. An unlimited queue or a full SD card is a failed result.

## Step 12: Verify backup and restore

Use a spare microSD card so the working gateway card remains untouched.

1. Flash the same approved Gateway OS Base factory image.
2. Restore the latest protected LuCI backup.
3. Confirm that the Mosquitto configuration and certificate files are present.
4. Confirm the private-key permissions.
5. Boot the restored gateway with the RAK5146 installed.
6. Confirm that the Gateway EUI and channel plan match the original gateway.
7. Confirm that both MQTT bridges authenticate.
8. Repeat one local uplink, one remote uplink, one safe downlink, and one short WAN-outage test.

A backup is not proven until it has restored a working gateway on separate media.

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
- Queue limits protect the SD card.
- A protected backup restores successfully to spare media.
- UDP Forwarder remains disabled.
- The journal independently records the supported Concentratord source path and record/segment hashes verify.
- Journal sequence/hash continuity survives a clean reboot.
- WAN loss preserves both the Mosquitto queue and local journal within separate finite budgets.
- Recovery uploads missing journal segments and extends the last accepted cloud checkpoint.
- Server reconciliation can distinguish `verified`, `evidence_gap`, and `integrity_failure`.
- Operators understand that the cloud-anchored history is stronger than a local checksum, but the software-only unanchored offline tail is not claimed to be unforgeable against full gateway root compromise.

Continue with [Gateway operations](../operations/01-register-and-test.md) for registration, routine tests, backup, recovery, and troubleshooting.
