# Gateway 6. Verify Gateway OS and Uplink Buffering

A running service is not proof of durable buffering. Verify the radio, local broker, persistent queue, remote bridge, ChirpStack, and recovery separately.

## Step 1: Verify image and services

```sh
cat /etc/os-release
uname -a
monit status
uci show chirpstack-concentratord
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
opkg list-installed | grep '^mosquitto'
```

Pass when the observed Gateway OS Base release and installed services match the tested configuration retained during setup, all required services remain running, and UDP Forwarder has no active server. A version mismatch or restart loop means later test results cannot be compared reliably.

## Step 2: Verify persistent storage

```sh
df -h /etc/mosquitto/data
mount
ls -ld /etc/mosquitto/data /etc/mosquitto/certs
ls -l /etc/mosquitto/data
```

Pass when the queue is on persistent writable storage, is not under `/tmp`, has the required free-space reserve, and private-key permissions remain restrictive.

## Step 3: Verify local MQTT

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
logread -e chirpstack-mqtt-forwarder
logread -e mosquitto
```

Pass when:

- MQTT Forwarder uses `tcp://127.0.0.1:1883` at QoS 1;
- Mosquitto listens only on loopback;
- local event and state publishes succeed;
- no LAN or WAN listener exists on 1883.

## Step 4: Verify remote mutual TLS and ACLs

On the remote broker host:

```sh
docker compose logs --since=10m --tail=300 mosquitto chirpstack
```

Required evidence:

- both `gw-up-<GATEWAY_EUI>` and `gw-down-<GATEWAY_EUI>` authenticate with the expected gateway certificate;
- the certificate identity equals `<GATEWAY_EUI>`;
- event and state writes are allowed only for that Gateway ID;
- command reads are allowed only for that Gateway ID;
- another gateway's topics are denied.

## Step 5: Verify normal real traffic

Use an approved OTAA device.

Pass when:

- OTAA succeeds;
- a real uplink passes through MQTT Forwarder, local Mosquitto, remote Mosquitto, and ChirpStack;
- the expected Gateway ID and frame counter are visible;
- a safe Class A downlink is scheduled and produces the expected device result.

## Step 6: Verify WAN-outage buffering

Perform in staging or an approved maintenance window.

1. Note the current Mosquitto database size and the last accepted device frame counter so queue growth and later delivery can be compared.
2. Disconnect only the gateway WAN path. Keep power, Concentratord, MQTT Forwarder, and local Mosquitto running.
3. Generate a known number of real uplinks.
4. Confirm local publishes continue and `/etc/mosquitto/data/mosquitto.db` is created or updated.
5. Confirm the remote broker and ChirpStack do not receive those uplinks during the outage.
6. Restore WAN connectivity.
7. Confirm the outgoing bridge drains the queued uplinks.
8. Compare expected frame counters, ChirpStack deduplication identifiers, application rows, and broker logs.

QoS 1 is at-least-once. Duplicate MQTT delivery is acceptable only when Node-RED and the database uniqueness rules keep one canonical application record.

## Step 7: Verify reboot persistence during outage

While the WAN is still unavailable in staging:

1. generate buffered uplinks;
2. note the queue database checksum and size so persistence can be compared after reboot;
3. reboot the gateway cleanly;
4. verify local Mosquitto restarts and retains the queue;
5. generate another real uplink;
6. restore WAN;
7. verify all expected unique uplinks drain.

Do not claim persistent buffering if queued messages disappear across reboot.

## Step 8: Verify stale downlinks are not replayed

The downlink bridge uses a clean session and QoS 0.

During a controlled outage, queue only a non-hazardous test downlink through ChirpStack. It must fail or expire according to ChirpStack behavior and must not be transmitted after WAN recovery as a delayed command.

A later fresh Class A downlink must still work.

## Step 9: Verify queue limits and overflow behavior

In staging, test the configured message and byte limits without exhausting the SD card. Observe the first warning or dropped-message event, remaining free space, oldest and newest retained frame counters, alert delivery, and recovery action.

A healthy result keeps the configured free-space reserve and reports the limit condition. Silent storage growth, a read-only filesystem, or unclear loss boundaries means the queue sizing or monitoring is not ready. The gateway must protect the filesystem instead of allowing an unbounded queue to fill storage.

## Step 10: Verify backup and restore

Restore the approved Gateway OS image, configuration, Mosquitto certificates, queue configuration, and service state to a spare SD card.

Pass when the restored gateway preserves the intended Gateway ID and RF plan, authenticates with the approved certificate, buffers a new outage test, and completes a fresh OTAA/uplink/downlink sequence.

## Final acceptance

- The tested image, package versions, rollback configuration, and finite queue limits can be identified.
- RAK5146 initializes with the confirmed legal RF settings.
- MQTT Forwarder publishes to loopback at QoS 1.
- Local broker persistence survives WAN loss and reboot.
- Remote mTLS and per-gateway ACL isolation pass.
- Buffered uplinks drain with downstream duplicate protection.
- Stale downlink commands are not replayed.
- Queue overflow protects storage and produces an actionable alert.
- UDP Forwarder remains disabled.
