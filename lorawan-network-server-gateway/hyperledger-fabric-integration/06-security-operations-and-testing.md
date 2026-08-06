# 6. Security, Operations, and Testing

Treat the adapter as a production integration service. It has access to telemetry and a signing identity, so it needs stronger controls than an ordinary dashboard.

## 6.1 Security controls

- Use TLS for the Fabric Gateway connection.
- Validate the server name and trusted CA certificate.
- Use a dedicated client identity with the minimum required attributes.
- Do not use a Fabric admin identity for routine submissions.
- Keep the private key outside Node-RED flow files.
- Restrict access to the adapter host and secret store.
- Rotate certificates before expiry.
- Record who approves identity issuance and revocation.
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
| Fabric unavailable | Telemetry continues and outbox remains pending |
| Commit timeout | Adapter queries before retrying |
| Invalid schema | Adapter rejects before Fabric submission |
| Certificate rotation | New identity works before old identity is revoked |
| Ledger verification | Digest recomputed from TimescaleDB matches Fabric |
| Recovery | Dead-letter events can be replayed safely |

## 6.3 Operational metrics

Track:

- pending outbox count;
- oldest pending event age;
- submission success rate;
- commit invalidation count;
- unknown timeout count;
- duplicate conflict count;
- average Fabric commit latency;
- certificate expiry days;
- adapter restart count;
- database-to-ledger reconciliation mismatches.

Alert when the oldest pending event exceeds the business SLA, when the queue grows continuously, or when a certificate is approaching expiry.

## 6.4 Reconciliation procedure

At a scheduled interval:

1. select confirmed outbox rows;
2. query Fabric by event_key;
3. recompute the digest from the canonical JSON;
4. compare local digest, ledger digest, and transaction ID;
5. record mismatches;
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

## 6.6 Definition of done

Integration is ready for a real pilot when:

- the Fabric team has approved the contract;
- the staging adapter submits and verifies one test attestation;
- raw data remains available in TimescaleDB;
- the same event can be replayed without creating a conflicting record;
- Fabric outage behavior is demonstrated;
- identity rotation is documented;
- the security owner approves the private-key arrangement;
- the business owner approves what the ledger record means;
- production support contacts are known.

Next: [00-README.md](00-README.md)
