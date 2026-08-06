# 3. Integration Architecture and Reliability

The most important architecture decision is whether the application submits every uplink directly to Fabric or whether it first stores accepted telemetry and submits selected attestations asynchronously.

## 3.1 Recommended pattern: asynchronous adapter

Use this pattern for the Raspberry Pi deployment:

~~~text
MQTT uplink
  -> Node-RED validates and normalizes
  -> TimescaleDB stores the telemetry
  -> outbox record is created for selected events
  -> Fabric adapter reads pending outbox rows
  -> adapter canonicalizes and hashes the record
  -> adapter submits to Fabric Gateway
  -> adapter waits for commit status
  -> adapter records transaction ID and status
~~~

Advantages:

- a Fabric outage does not stop sensor ingestion;
- retries can be controlled and audited;
- raw telemetry remains queryable in TimescaleDB;
- the ledger receives only business-significant records;
- the adapter can run on a stronger, protected host;
- duplicate submissions can be made idempotent.

The adapter is normally a separate service owned by the application or Fabric integration team. Do not place Fabric private keys inside a Node-RED flow unless the security team explicitly accepts that design.

## 3.2 Direct submission pattern

Direct submission from Node-RED can be acceptable for a small demonstration:

~~~text
MQTT uplink
  -> Node-RED
  -> HTTPS integration API
  -> Fabric adapter
  -> Fabric Gateway
~~~

Do not make Node-RED speak directly to a peer using low-level Fabric administration commands. Put a narrow API in front of Fabric so that identity use, validation, rate limiting, retries, and audit logging are controlled in one place.

## 3.3 What should be submitted?

Choose one of these policies:

| Policy | Fabric volume | Best use |
|---|---:|---|
| Every reading | Very high | Small pilot with few devices |
| Time-window digest | Low | Proof that a historical set was preserved |
| Threshold exception | Low | Compliance or alarm evidence |
| Business transition only | Very low | Custody, inspection, maintenance, ownership |
| Daily or hourly summary | Low | Reporting and settlement evidence |

For the current agricultural pilot, use a time-window digest or exception attestation rather than every temperature sample. For a port, use the ledger for custody, inspection, exception, or approval events and keep high-volume environmental telemetry off-chain.

## 3.4 Optional outbox table

If the application team chooses the outbox pattern, create a dedicated table rather than mixing Fabric state into every telemetry row:

~~~sql
CREATE TABLE IF NOT EXISTS telemetry.fabric_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    canonical_json TEXT NOT NULL,
    digest_sha256 TEXT NOT NULL,
    payload_reference TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fabric_tx_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at TIMESTAMPTZ,
    last_error TEXT,
    CONSTRAINT fabric_outbox_status_ck
        CHECK (status IN ('pending', 'submitted', 'confirmed', 'failed', 'dead_letter'))
);
~~~

Add an index for the worker:

~~~sql
CREATE INDEX IF NOT EXISTS fabric_outbox_pending_idx
    ON telemetry.fabric_outbox (next_attempt_at, outbox_id)
    WHERE status IN ('pending', 'failed');
~~~

The table is an integration queue, not a replacement for TimescaleDB. The worker must use a transaction or a clear reconciliation process so that an outbox row is never falsely marked confirmed before Fabric commit status is received.

## 3.5 Retry and idempotency rules

Use at-least-once delivery with duplicate protection:

1. Derive event_key from the source event, not from a retry counter.
2. Create one deterministic canonical JSON representation.
3. Calculate the digest from the canonical representation.
4. Use event_key as the chaincode state key or a unique chaincode index.
5. If Fabric reports an already-existing key, query it and compare the digest.
6. Mark the outbox row confirmed only after commit status is valid.
7. Send permanent failures to dead_letter with the reason and operator action.

Never create a new ledger event on every retry simply because the first response timed out. A network timeout does not prove that the transaction was not committed.

## 3.6 Time and ordering

Keep separate timestamps:

- observed_at: the sensor or ChirpStack event time;
- received_at: when the platform accepted the MQTT event;
- submitted_at: when the adapter submitted the Fabric transaction;
- committed_at: when the adapter received the Fabric commit result.

Fabric transaction order is not a replacement for sensor observation time. Queries must preserve both business time and ledger time.

## 3.7 Deployment boundary

The Raspberry Pi is suitable for the gateway, ChirpStack, Node-RED, and local telemetry storage. The Fabric adapter may run on the Pi for a lab pilot, but production deployment should consider a separate protected host with:

- stable power and network;
- encrypted secret storage;
- monitored service supervision;
- controlled access to the Fabric Gateway;
- an independent backup and logging path.

Do not install peers, orderers, or a Fabric CA on the LoRaWAN gateway merely because the gateway is already running Linux. Those are separate network-governance responsibilities.

Next: [04-data-contract-and-chaincode.md](04-data-contract-and-chaincode.md)
