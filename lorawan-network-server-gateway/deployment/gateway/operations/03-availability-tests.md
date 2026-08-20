# Operations 3. Gateway Availability and Integrity Tests

Run these tests in staging or during a maintenance window where temporary telemetry interruption is acceptable. Capture timestamps, frame counters, queue database size, journal sequence/segment/checkpoint state, broker logs, verification status, and application row counts. Delivery evidence and integrity evidence answer different questions and must be measured separately.

## Test 1: Normal reboot

```sh
reboot
```

Pass when Concentratord, MQTT Forwarder, local Mosquitto, and the reviewed journal services restart; Gateway ID is unchanged; the loopback listener remains private; both remote bridges reconnect; journal sequence/hash continuity resumes with a new boot ID; UDP Forwarder stays disabled; and a fresh uplink reaches ChirpStack.

## Test 2: WAN interruption with buffering

1. Note `/etc/mosquitto/data/mosquitto.db` size and the last accepted device frame counter as the baseline.
2. Disconnect only WAN or 4G.
3. Keep RAK5146, Concentratord, MQTT Forwarder, and local Mosquitto running.
4. Generate a known number of real uplinks.
5. Confirm local publishes continue and the persistence database changes.
6. Confirm the remote broker receives no new events during the outage.
7. Restore WAN.
8. Verify all expected unique uplinks drain.
9. Confirm the journal continued sequencing throughout the outage and retained all closed unuploaded segments within its evidence budget.
10. Confirm the server checkpoint did not falsely advance while disconnected.
11. Confirm recovery uploads the missing journal segments and they extend the last pre-outage anchor.
12. Confirm the server correlates the recovered journal records with the drained gateway MQTT events.

Compare disconnect detection, bridge retry interval, outage duration, queued count, drain duration, duplicate MQTT deliveries, unique application records, and stale/offline transition with the outage design. Queue growth without later drain means the remote path is still unhealthy; more application rows than unique events means deduplication is incomplete.

## Test 3: Gateway reboot during WAN outage

Buffer real uplinks while WAN is unavailable, then reboot the gateway cleanly.

Pass when:

- the Mosquitto queue survives reboot and drains after WAN recovery;
- the journal continues from the last valid complete record rather than resetting;
- a new journal boot ID appears;
- the first post-reboot record links to the last valid pre-reboot chain state;
- server reconciliation accepts the chain across the reboot boundary.

Queue loss is an availability failure. Journal chain reset/corruption is an integrity failure. Keep those diagnoses separate.

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

## Test 10: Journal tamper and gap fixtures

Use **copies** of closed staging segments, never the only real evidence object.

Test separately:

1. change one byte in a copied complete record;
2. remove one complete record;
3. swap two complete records;
4. present an older segment/checkpoint lineage than the server's latest accepted anchor.

Pass when the verifier rejects the changed/reordered/rollback evidence. A missing required whole segment with no contradictory bytes is `evidence_gap`; a proven conflicting hash/payload is `integrity_failure`.

## Test 11: Journal storage pressure

Reduce the staging evidence budget enough to approach warning/critical thresholds without filling the OS filesystem.

Pass when the emergency reserve survives, alarms are visible, unuploaded evidence is not silently overwritten, and affected events are explicitly classified as an evidence gap if retention is exhausted.

## Final acceptance

- Uplink queue survives WAN loss and gateway reboot.
- Queue drains within the target and application rows remain unique.
- Queue limits protect storage.
- Invalid certificates and cross-gateway topics are rejected.
- Stale downlinks are not replayed.
- No UDP fallback starts.
- Journal sequence and hash continuity survive normal operation and reboot.
- Cloud checkpoints anchor connected history and do not falsely advance while disconnected.
- Recovery uploads missing segments and reconciles them with drained MQTT events.
- Tamper, deletion, reorder, rollback, and storage-gap fixtures produce the documented verification outcomes.
- The residual full-root/offline software-only limitation is recorded rather than hidden.
