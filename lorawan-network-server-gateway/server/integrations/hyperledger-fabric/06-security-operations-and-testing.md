# 6. Security, Operations, and Testing

Treat the adapter as a production integration service. It has access to telemetry and a signing identity, so it needs stronger controls than an ordinary dashboard. A running process, successful proposal, returned transaction ID, or submitted request does not prove a valid ledger commit.

## 6.1 Security controls

- Use TLS for the Fabric Gateway connection.
- Validate the server name and trusted CA certificate.
- Use a dedicated client identity with the minimum required attributes.
- Do not use a Fabric admin identity for routine submissions.
- Keep the private key outside Node-RED flow files.
- Restrict access to the adapter host and secret store.
- Rotate certificates before expiry.
- Define the protected identity-issuance and revocation path, including who can perform each action and how the adapter is updated.
- Separate development, staging, and production channels or networks.
- Do not put LoRaWAN root keys on Fabric.
- Encrypt backups containing outbox data or identity material.
- Apply retention rules to off-chain evidence.

Fabric identities use certificates and private keys, and channel or chaincode policies determine what those identities can do. A valid certificate alone is not permission to invoke every transaction.

## 6.2 Test levels

| Test | Expected result |
|---|---|
| TLS connection | Adapter verifies the correct Gateway endpoint |
| Identity check | Fabric recognizes the expected MSP and role |
| Contract evaluation | Contract version and query are returned |
| Valid submission | Transaction commits and returns a transaction ID |
| Duplicate same digest | No conflicting second record |
| Duplicate different digest | Transaction rejected and operator alerted |
| Fabric unavailable | Telemetry continues and outbox remains pending or failed with backoff |
| Worker crash | Expired processing lease is reclaimed without duplicate ledger state |
| Commit timeout | Adapter moves to submitted_unknown and queries before retrying |
| Invalid schema | Adapter rejects before Fabric submission |
| Certificate rotation | New identity works before old identity is revoked |
| Ledger verification | Digest recomputed from TimescaleDB matches Fabric |
| Recovery | Dead-letter events can be replayed safely |

## 6.3 Operational metrics

Track:

- pending and failed outbox count;
- oldest retry-eligible event age;
- active and expired processing lease count;
- submitted-unknown count and oldest age;
- submission success rate;
- commit invalidation count;
- unknown timeout count;
- duplicate conflict count;
- average Fabric commit latency;
- certificate expiry days;
- adapter restart count;
- database-to-ledger reconciliation mismatches.

Alert when the oldest retry-eligible event exceeds the business SLA, when a processing lease expires, when submitted-unknown rows are not reconciled, when the queue grows continuously, or when a certificate is approaching expiry.

## 6.4 Reconciliation procedure

At a scheduled interval:

1. select confirmed outbox rows;
2. query Fabric by event_key;
3. recompute the digest from the canonical JSON;
4. compare local digest, ledger digest, and transaction ID;
5. write each mismatch to a reconciliation result with the event key, local digest, ledger digest, and transaction ID;
6. investigate rather than silently overwriting data.

The result should be a report that a reviewer can understand without inspecting application logs.

## 6.5 Failure response

| Failure | First action | Do not do |
|---|---|---|
| Gateway unavailable | Keep telemetry ingestion running; pause retries with backoff | Drop pending events |
| TLS error | Verify endpoint, CA, and server name | Disable certificate validation |
| Permission denied | Ask Fabric team to inspect MSP and policy | Use an admin identity |
| Chaincode rejection | Inspect contract validation and payload | Retry unchanged forever |
| Duplicate conflict | Preserve both evidence records and escalate | Overwrite the old digest |
| Unknown commit | Query by event key or transaction ID | Immediately create a new event |
| Key compromise | Revoke and replace identity | Continue using the key |
| Database failure | Restore or fail over according to database runbook | Mark events confirmed |

## 6.6 Verify the pilot path

Use one sanitized staging event and keep its event key and transaction ID so every layer can be compared. The integration is ready for a pilot when:

1. the Fabric team and application team use the same contract version, canonicalization test vectors, transaction names, and endorsement behavior;
2. the staging adapter submits the event, receives a valid commit status, queries it back, and recomputes the same digest from TimescaleDB evidence;
3. the raw and canonical off-chain data remain available and the same event can be replayed without creating a conflicting ledger entry;
4. a Fabric outage leaves telemetry ingestion running and the outbox pending with bounded backoff;
5. an adapter crash releases through lease expiry without producing duplicate ledger state;
6. a simulated commit timeout enters `submitted_unknown` and is reconciled before retry;
7. the client identity can be rotated and the old identity revoked without using an administrator certificate;
8. the private key remains outside Node-RED, source control, logs, and dashboard exports;
9. the business meaning of the attestation, the response to conflicts, and the support path are understood by the teams operating the pilot.

A returned transaction ID without valid commit status or a matching query/digest is a failed acceptance result.

Next: [00-README.md](00-README.md)
