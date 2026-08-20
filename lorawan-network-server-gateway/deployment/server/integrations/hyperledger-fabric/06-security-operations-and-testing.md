# 6. Security, Operations, and Testing

Treat the adapter as a production integration service. It has access to telemetry and a signing identity, so it needs stronger controls than an ordinary dashboard. A running process, successful proposal, returned transaction ID, or submitted request does not prove a valid ledger commit.

## 6.1 Security controls

- Use TLS for the Fabric Gateway connection.
- Validate the server name and trusted CA certificate.
- Use a dedicated Fabric client identity with the minimum required attributes.
- Do not use a Fabric admin identity for routine submissions.
- Use a **different** OpenBao Transit `ecdsa-p256` key for the off-chain seal; never reuse the Fabric client key as the evidence key.
- Configure the Transit key as non-exportable with plaintext backup disabled. The adapter receives only AppRole credentials and short-lived sign/verify tokens, never the evidence private key.
- Keep the Fabric private key, OpenBao root token, unseal/recovery material, AppRole SecretID, and runtime OpenBao token outside Node-RED, PostgreSQL, source control, ordinary `.env` values, logs, dashboards, and ledger state.
- Give the adapter OpenBao policy rights only to `transit/sign/lorawan-evidence/sha2-256` and `transit/verify/lorawan-evidence/sha2-256`; it must not create, rotate, export, back up, or delete KMS keys.
- In production, run OpenBao/KMS on independently protected infrastructure with TLS and protected recovery material. Use Integrated Storage (Raft) with five voting OpenBao servers as the production target unless a reviewed risk decision accepts a three-voter minimum. Spread voters across separate failure domains, expose one stable private KMS endpoint to the adapter, and keep every Shamir-based standby unsealed. The single-VM Docker lab proves workflow, not host-root isolation or KMS HA.
- Make outbox source identity immutable, give the adapter column-level UPDATE rights only, and make a completed evidence seal one-way through the database trigger documented in the lab setup.
- For v2, run the gateway evidence verifier under a separate identity. Node-RED and the Fabric adapter must not have permission to set `gateway_evidence.event_verification.status='verified'`; the verifier must not have OpenBao sign permission or the Fabric client key.
- Protect checkpoint and journal-segment evidence from overwrite. Preserve server receipt metadata and conflicting checkpoints for incident review instead of replacing them.
- Treat PostgreSQL-superuser/host-root compromise as outside what a database trigger alone can resist; use an external append-only signer/anchor when that privileged threat must be detected.
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
| RFC 8785 startup vectors | Pinned canonicalizer produces the approved canonical bytes and digest exactly for every enabled schema; v2 is disabled until its separate reviewed vector exists |
| OpenBao KMS self-test | Transit `lorawan-evidence` signs exact bytes and verifies the returned versioned signature |
| Persisted seal verification | Stored canonical JSON recomputes to the stored digest and OpenBao returns `valid=true` for the stored versioned signature |
| One-byte tamper test | OpenBao returns `valid=false` when the exact signed bytes are changed |
| One-way seal trigger | A rolled-back attempt to modify a completed seal is rejected |
| Valid submission | Transaction commits and returns a transaction ID only after local-seal verification |
| Duplicate same digest | No conflicting second record |
| Duplicate different digest | Transaction rejected and operator alerted |
| Fabric unavailable | Telemetry continues and outbox remains pending/failed/unknown with backoff; an existing digest/signature seal does not change during recovery |
| One OpenBao voter fails with quorum intact | Stable KMS endpoint remains usable; another unsealed node becomes active; adapter configuration does not change |
| OpenBao quorum unavailable or reachable nodes sealed | Telemetry continues; Fabric adapter backs off and does not submit an unverified/unsealed event |
| Invalid local seal | Adapter fails closed before a Fabric transaction is created |
| Worker crash | Expired processing lease is reclaimed without duplicate ledger state |
| Commit timeout | Adapter moves to submitted_unknown and queries before retrying |
| Invalid schema | Adapter rejects before Fabric submission |
| v2 pending verification | Adapter does not claim/seal the row; telemetry remains available |
| v2 evidence gap | Row follows explicit gap policy and is never mislabeled gateway-verified |
| Journal record/segment tamper | Verifier rejects the changed chain and v2 sealing remains blocked |
| Checkpoint rollback/conflict | Server preserves accepted anchor, raises security conflict, and v2 promotion freezes |
| Journal vs remote MQTT payload mismatch | Verifier returns `integrity_failure`; adapter never creates a v2 seal |
| Trusted decoder vs Node-RED mismatch | Verifier returns `integrity_failure`; v2 Fabric submission is blocked |
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
- invalid-local-seal count;
- unsupported evidence-schema/signature-algorithm count;
- current OpenBao Transit key version used for new seals;
- OpenBao AppRole/login failures, Transit sign failures, and Transit verify failures;
- OpenBao stable-endpoint availability;
- active OpenBao node and leader-change count;
- expected versus healthy/unsealed Raft voters;
- Raft quorum-risk/quorum-loss state;
- OpenBao sealed/unavailable duration;
- evidence seal creation latency and age of oldest unsealed eligible row;
- average Fabric commit latency;
- Fabric client-certificate expiry days;
- evidence-key rotation/activation status;
- adapter restart count;
- database-to-ledger reconciliation mismatches;
- v2 rows waiting for gateway verification and oldest waiting age;
- gateway-evidence `evidence_gap` and `integrity_failure` counts by reason;
- checkpoint conflict/rollback count;
- journal-to-MQTT correlation failures/ambiguities;
- trusted-decoder mismatch count.

Alert when the oldest retry-eligible event exceeds the business SLA, when a processing lease expires, when submitted-unknown rows are not reconciled, when an eligible row remains unsealed unexpectedly, when any local seal fails verification, when an unexpected signing-key ID appears, when the queue grows continuously, or when a Fabric certificate/evidence-key rotation deadline is approaching.

## 6.4 Reconciliation procedure

At a scheduled interval:

1. select confirmed outbox rows and load the stored canonical JSON, digest, signature algorithm, OpenBao key ID, complete versioned signature, and Fabric transaction ID;
2. recompute SHA-256 from the exact stored canonical UTF-8 bytes;
3. verify that the recomputed digest equals `digest_sha256`;
4. parse the key version from the complete versioned signature and prove it matches `evidence_signing_key_id`;
5. send `Base64(canonical UTF-8 bytes)` plus the complete stored signature to the OpenBao Transit verify endpoint for `lorawan-evidence/sha2-256` and require `valid=true`;
6. **stop reconciliation for that row and raise a security mismatch** if the digest, key-version binding, or KMS verification fails; do not query Fabric as though the local evidence were trustworthy;
7. query Fabric by `event_key` only after the local seal verifies;
8. compare local digest, ledger digest, immutable seal metadata, and transaction ID;
9. write each mismatch to a reconciliation result with the event key, local digest, ledger digest, signing-key ID, local-seal result, and transaction ID;
10. investigate rather than silently overwriting or resealing data.

The result should be a report that a reviewer can understand without inspecting application logs.

## 6.5 Failure response

| Failure | First action | Do not do |
|---|---|---|
| Gateway unavailable | Keep telemetry ingestion running; preserve pending evidence/outbox state and distinguish delivery outage from evidence outage | Drop pending events or invent verification |
| TLS error | Verify endpoint, CA, and server name | Disable certificate validation |
| Permission denied | Ask Fabric team to inspect MSP and policy | Use an admin identity |
| Chaincode rejection | Inspect contract validation and payload | Retry unchanged forever |
| Duplicate conflict | Preserve both evidence records and escalate | Overwrite the old digest |
| v2 gateway evidence pending | Leave the row unsealed/ineligible until required evidence arrives | Ask the adapter or Node-RED to mark it verified |
| v2 evidence gap | Follow the reviewed gap policy and preserve the reason/source references | Treat missing proof as verified |
| v2 integrity failure | Freeze v2 promotion, preserve journal/MQTT/decoder evidence, and investigate the conflicting layer | Reseal from whichever source looks convenient |
| Conflicting/rollback checkpoint | Preserve both request evidence and the previously accepted anchor; investigate gateway history | Delete the newer anchor to make the chain fit |
| Invalid local evidence seal | Preserve the row, stop Fabric submission, verify key ID/digest/signature and investigate tampering or corruption | Recalculate the row and generate a replacement signature |
| Attempted reseal rejected by trigger | Preserve database/audit evidence and investigate the caller | Disable the trigger to make the update pass |
| Unknown commit | Query by event key or transaction ID after local-seal verification | Immediately create a new event |
| Fabric client-key compromise | Revoke/replace the Fabric identity and investigate submitted transactions | Continue using the key |
| One OpenBao voter unavailable | Verify stable endpoint, HA status, and Raft peers; allow an unsealed standby to take over; restore/rejoin the failed voter without changing adapter configuration | Point the adapter manually at whichever node appears active |
| OpenBao quorum unavailable/reachable nodes sealed | Keep telemetry ingestion running, back off Fabric work, restore quorum/unseal KMS through the approved procedure, then verify stored seals before resuming | Bypass KMS verification or fall back to a local private key |
| AppRole credential compromise | Revoke/replace the AppRole SecretID or role, inspect OpenBao audit evidence, and determine the possible unauthorized-signing window | Promote the adapter token to KMS administration |
| OpenBao Transit key/admin compromise | Stop new sealing, preserve historical rows/signatures, rotate under an approved incident procedure, and determine the compromise window | Rewrite old seals with a new version |
| Database failure | Restore or fail over according to database runbook and re-verify seals after restore | Mark events confirmed |

## 6.6 Verify the pilot path

Use one sanitized staging event and keep its event key and transaction ID so every layer can be compared. The integration is ready for a pilot when:

1. the Fabric team and application team use the same supported schema versions, transaction names, digest/seal metadata fields, and endorsement behavior; v1 retains its existing RFC 8785 vector and any enabled v2 path has a separately reviewed fixed v2 vector;
2. OpenBao reports the expected non-exportable `ecdsa-p256` Transit key, the adapter policy is limited to sign/verify, and the KMS exact-byte/tampered-byte self-tests pass without private-key export;
3. for a v2 pilot, one real staging event first reaches gateway-evidence `verified`: journal chain extends the accepted cloud checkpoint, the remote gateway MQTT event matches uniquely, the ChirpStack application lineage is unique, and the trusted decoder agrees with TimescaleDB;
4. the staging adapter seals that eligible event through OpenBao, stores the complete versioned signature and derived key-version ID, re-reads it, recomputes the same digest, receives `valid=true` from Transit verify, submits it, receives a valid Fabric commit status, and queries the same digest back;
5. a one-byte change to a temporary copy of canonical evidence fails signature verification;
6. a rolled-back database test proves the one-way trigger rejects modification of an already completed seal;
7. isolated gateway-evidence negative fixtures prove record tamper, deletion/reorder, checkpoint conflict, journal/MQTT mismatch, and trusted-decoder mismatch cannot produce a verified v2 seal;
8. the raw and canonical off-chain data remain available and the same event can be replayed without creating a conflicting ledger entry;
9. a Fabric outage leaves telemetry ingestion running, preserves the exact pre-existing digest/key-ID/signature tuple, and uses bounded backoff;
10. an adapter crash releases through lease expiry without producing duplicate ledger state or a replacement evidence seal;
11. a simulated commit timeout enters `submitted_unknown`, verifies the local seal, and is reconciled before retry;
12. an intentionally invalid local seal in an isolated fixture is rejected before any Fabric transaction ID exists;
13. the Fabric client identity can be rotated and the old identity revoked without using an administrator certificate;
14. OpenBao key rotation creates a new key version for future seals, historical signatures still verify through their recorded versions, and no old row is rewritten;
15. a production-like OpenBao HA test proves that stopping the active voter does not require changing `OPENBAO_ADDR`, an unsealed standby takes over, Transit sign/verify still succeeds through the stable endpoint, and the failed voter can rejoin;
16. a total OpenBao quorum/sealed-unavailable test proves MQTT, ChirpStack, Node-RED, and TimescaleDB continue while the Fabric adapter fails closed and later resumes after KMS recovery;
17. the Fabric private key, OpenBao private evidence key, root token, unseal/recovery material, AppRole SecretID, and short-lived runtime token remain outside inappropriate stores/logs;
18. the business meaning of the attestation, the response to conflicts, and the support path are understood by the teams operating the pilot.

A returned transaction ID without valid commit status or a matching query/digest is a failed acceptance result.

Next: [00-README.md](00-README.md)
