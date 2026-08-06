# Operations 3. Gateway Buffer and Availability Tests

Run these tests in staging or during a maintenance window where temporary telemetry interruption is acceptable. Capture timestamps, frame counters, queue database size, broker logs, and application row counts because those values distinguish retained uplinks from loss or duplicate processing.

## Test 1: Normal reboot

```sh
reboot
```

Pass when Concentratord, MQTT Forwarder, and local Mosquitto restart; Gateway ID is unchanged; the loopback listener remains private; both remote bridges reconnect; UDP Forwarder stays disabled; and a fresh uplink reaches ChirpStack.

## Test 2: WAN interruption with buffering

1. Note `/etc/mosquitto/data/mosquitto.db` size and the last accepted device frame counter as the baseline.
2. Disconnect only WAN or 4G.
3. Keep RAK5146, Concentratord, MQTT Forwarder, and local Mosquitto running.
4. Generate a known number of real uplinks.
5. Confirm local publishes continue and the persistence database changes.
6. Confirm the remote broker receives no new events during the outage.
7. Restore WAN.
8. Verify all expected unique uplinks drain.

Compare disconnect detection, bridge retry interval, outage duration, queued count, drain duration, duplicate MQTT deliveries, unique application records, and stale/offline transition with the outage design. Queue growth without later drain means the remote path is still unhealthy; more application rows than unique events means deduplication is incomplete.

## Test 3: Gateway reboot during WAN outage

Buffer real uplinks while WAN is unavailable, then reboot the gateway cleanly.

Pass when the queue survives reboot and drains after WAN recovery. Failure means the selected storage path or persistence behavior is not durable.

## Test 4: Remote broker restart

```sh
cd /opt/chirpstack-docker
docker compose restart mosquitto
docker compose logs -f mosquitto chirpstack
```

Pass when the local queue retains events during the restart, both bridge connections reconnect automatically, queued event/state traffic drains, and a later fresh downlink succeeds.

## Test 5: ChirpStack restart

Restart ChirpStack while leaving both brokers available. Verify remote MQTT remains healthy, events are processed after ChirpStack reconnects, and any duplicates remain idempotent downstream.

## Test 6: Invalid gateway certificate

In staging, replace only the bridge certificate with an untrusted or mismatched test certificate.

Expected:

- remote broker rejects both bridge connections;
- local event/state messages accumulate in the finite queue;
- no gateway event reaches ChirpStack;
- restoring the valid certificate drains the queue;
- cross-gateway access remains denied.

Use a verified rollback bundle.

## Test 7: Queue limit and storage pressure

Generate enough staging messages to approach, but not exhaust, the configured queue limits.

Verify warnings or drops are visible, the free-space reserve remains intact, the filesystem stays writable, and the runbook explains how to identify which messages were lost. Silent drops or a read-only filesystem are failures even when the broker process remains running.

## Test 8: Stale-downlink prevention

During WAN loss, create only a non-hazardous test downlink. It must fail or expire and must not transmit after recovery. A new downlink created after recovery must work.

## Test 9: Remote endpoint failover

Test the exact load-balancer or broker design. A load balancer does not create shared Mosquitto sessions or queue state. Measure reconnect, loss, duplicates, and certificate handling.

## Final acceptance

- Uplink queue survives WAN loss and gateway reboot.
- Queue drains within the target and application rows remain unique.
- Queue limits protect storage.
- Invalid certificates and cross-gateway topics are rejected.
- Stale downlinks are not replayed.
- No UDP fallback starts.
