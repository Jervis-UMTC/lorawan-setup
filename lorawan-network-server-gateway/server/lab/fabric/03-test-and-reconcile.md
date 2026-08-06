# Fabric 3. Test Commits, Failures, and Reconciliation

Run these tests only after a real telemetry uplink is stored and the telemetry database backup is readable.

## Test 1: Verify the contract before submission

From the adapter or an approved Fabric sample application, evaluate `GetContractVersion` and `ReadAttestation` against the Fabric Gateway.

Pass condition:

- TLS validates the Org1 peer;
- the client identity belongs to the expected MSP;
- the channel and chaincode resolve;
- the returned contract version matches `telemetry-attestation-v1`.

## Test 2: Queue one selected uplink

Trigger one approved test-device uplink or sanitized Inject-node event with the Fabric policy enabled.

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT outbox_id,event_key,status,attempts,created_at FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 10;"
```

Pass condition: one new row appears as `pending`. Replaying the same source event does not create another outbox row.

## Test 3: Confirm a real Fabric commit

Watch the adapter:

```bash
docker compose logs -f --tail=100 fabric-adapter
```

Then query:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,status,digest_sha256,fabric_tx_id,submitted_at,committed_at,last_error_category FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 10;"
```

Pass condition:

- status becomes `confirmed`;
- `digest_sha256` contains 64 lowercase hexadecimal characters;
- `fabric_tx_id` is recorded;
- `committed_at` is after `submitted_at`;
- querying Fabric by event key returns the same digest.

A transaction ID without valid commit status is not a pass.

## Test 4: Recompute the digest

Export the stored `canonical_json` for one confirmed lab event to a protected temporary file, calculate SHA-256, and compare it with both the outbox and ledger digest.

```bash
umask 077
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -c "SELECT canonical_json FROM telemetry.fabric_outbox WHERE event_key='<TEST_EVENT_KEY>'" \
  > /tmp/fabric-attestation.json
sha256sum /tmp/fabric-attestation.json
rm -f /tmp/fabric-attestation.json
```

The exact byte representation must be the canonical bytes used by the adapter. Do not pretty-print or reserialize before hashing.

## Test 5: Stop Fabric and preserve telemetry

On the Fabric VM, stop the peer or the complete disposable test network without deleting volumes. Then send new test uplinks.

Pass condition:

- Node-RED continues storing telemetry;
- outbox jobs remain pending, failed, or submitted_unknown according to the failure point;
- no telemetry row is marked invalid merely because Fabric is unavailable;
- the adapter backs off instead of retrying continuously.

Start Fabric again. The queue should drain without duplicate ledger state.

## Test 6: Duplicate and unknown-commit behavior

Submit the same event key and digest again.

Pass condition: the chaincode returns the existing matching attestation or rejects the duplicate in a documented idempotent way.

Simulate a client timeout after submission. The adapter must set `submitted_unknown`, query the ledger, and only retry when the stable event key is absent.

A duplicate key with a different digest must become a conflict requiring operator review.

## Test 7: Recover an expired processing lease

Use a reviewed test-only pause or failure-injection hook that stops the adapter immediately after the database claim and before Fabric submission. When the adapter has no such hook, block its route to the Fabric VM, observe the row enter `processing`, then stop the adapter. Do not rely on racing a normal fast submission.

Do not edit the row immediately. Wait until the configured lease expiry, restore the blocked route when used, restart the adapter, and inspect:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,status,worker_id,processing_started_at,lease_expires_at,attempts FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 10;"
```

Pass condition:

- the abandoned row is not reclaimed before `lease_expires_at`;
- it becomes eligible after lease expiry;
- a new claim increments `attempts` and records the current worker;
- no duplicate ledger state is created;
- `submitted_unknown` rows remain outside the normal retry path.

## Test 8: Grafana visibility

Verify the dashboard shows:

- pending, processing, confirmed, failed, submitted_unknown, and dead-letter counts;
- oldest pending age and expired processing leases;
- commit latency;
- latest error category;
- telemetry freshness independent of Fabric status.

Grafana is an operational view, not proof of ledger correctness. Keep the database query, Fabric query, digest comparison, and transaction ID as acceptance evidence.

## Final acceptance

The simulation passes only when:

- a real uplink is stored and visualized;
- one selected event is committed to Fabric;
- the ledger digest matches canonical off-chain evidence;
- replay is idempotent;
- Fabric outage does not block telemetry;
- recovery drains the queue;
- a crashed worker is recovered through lease expiry;
- invalid identity or TLS fails closed;
- Grafana exposes queue delay and failures;
- credentials and private keys remain outside flows, dashboards, logs, and Git.
