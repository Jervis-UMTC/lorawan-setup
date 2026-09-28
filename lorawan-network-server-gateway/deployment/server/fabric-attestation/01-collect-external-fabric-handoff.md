# Fabric 1. HRC External Fabric Handoff

## Purpose

This repository operates only the LoRaWAN-side Fabric client. The HRC team owns the Fabric organizations, peers, orderers, CAs, channel, and chaincode lifecycle. Do not create a replacement Fabric network from this project.

For the commissioned cloud deployment, the handoff is **complete for ULC-01**. This file records the current contract and the checks required for another adapter host or a future environment. The authoritative cross-team handoff is also summarized in [`../integrations/hyperledger-fabric/02-fabric-network-handoff.md`](../integrations/hyperledger-fabric/02-fabric-network-handoff.md).

## Current commissioned HRC boundary

```text
Fabric Gateway endpoint:       10.104.0.7:7051
TLS server name:               peer1.hrc.local
MSP ID:                        HrcMSP
Channel:                       hrc-channel
Chaincode:                     hrc-evidence
Contract namespace:            empty/default
Authenticated source identity: lorawan-gateway-evidence
Submit function:               CreateSourceBoundAnchor
Query function:                QuerySourceBoundAnchor
Digest verify function:        VerifySourceBoundDigest
Transient exact-payload key:   hrc.exact_payload
```

ULC-01 is the enabled continuous writer with a dedicated non-admin adapter identity. ULC-02 remains `FABRIC_ADAPTER_ENABLED=false` until its separate HA ownership/fencing acceptance gate passes. Do not enable ULC-02 merely for availability.

The old K3s `ClusterIP` `10.43.25.198:7051` is not a ULC production endpoint. The legacy functions `CreateAnchor`, `QueryAnchor`, `QueryAnchorByRecordID`, and `VerifyDigest` are forbidden for the commissioned adapter identity and must not be restored from older documentation.

## Current Task 37 source-bound contract

The submit transaction is:

```text
CreateSourceBoundAnchor(
  SourceRecordID,
  sourceType,
  producer,
  producedAt,
  schemaVersion
)
```

The exact immutable payload is **not** a positional argument. The adapter supplies the existing `telemetry.fabric_outbox.finalized_payload` bytes through Fabric transient data:

```text
hrc.exact_payload = finalized_payload exact bytes
```

The current Go implementation treats those bytes as authoritative. It must not rebuild them from JSONB, structs, maps, Node-RED values, `telemetry.uplinks.raw_data`, or another projection. The payload must be valid JSON, non-empty, and no larger than the HRC maximum accepted by the adapter.

The adapter computes SHA-256 over those exact bytes for local verification and later compares the HRC record against the same digest and payload length. HRC binds the authenticated source namespace to the Fabric client identity; `AuthenticatedSourceSystemID` is therefore not a caller-controlled positional argument in `CreateSourceBoundAnchor`.

The LoRaWAN mapping is:

```text
SourceRecordID = telemetry.fabric_outbox.source_event_key
sourceType     = telemetry.fabric_outbox.event_type
producer       = normalized DevEUI from the accepted source row
producedAt     = observed_at in UTC RFC3339Nano
schemaVersion  = telemetry.fabric_outbox.schema_version
exact payload  = telemetry.fabric_outbox.finalized_payload bytes
```

For `telemetry-attestation-v2`, a matching verifier-owned `gateway_evidence.event_verification` row must be `verified` before the normal worker can claim the row.

## Read and verification transactions

After submission, use:

```text
QuerySourceBoundAnchor(SourceRecordID)
VerifySourceBoundDigest(SourceRecordID, observedDigest)
```

`QuerySourceBoundAnchor` must return a source-bound record whose authenticated source ID, source record ID, digest, payload length, source type, producer, produced timestamp, and schema version all match the exact prepared anchor. `VerifySourceBoundDigest` must return `MATCH` for SHA-256 of the same immutable `finalized_payload` bytes.

Do not locally mark an event confirmed merely because endorsement succeeded, an orderer accepted a transaction, or a transaction ID exists. The production adapter persists the prepared transaction and signed commit-status request before orderer submission so an uncertain result can be reconciled after restart without inventing a new transaction.

## Dedicated client identity

Each enabled writer must use a dedicated least-privilege non-admin Fabric client certificate/key provisioned through the protected handoff channel. Never use an HRC administrator identity or a benchmark/test writer identity for the LoRaWAN adapter.

Keep private keys out of Git, Markdown, Node-RED, Grafana, PostgreSQL, normal chat, and ordinary logs. Verify a provisioned certificate and key bind to the same public key without printing private material:

```bash
CERT_PUB=$(openssl x509 -in <CLIENT_CERT> -pubkey -noout \
  | openssl pkey -pubin -outform DER | sha256sum | awk '{print $1}')
KEY_PUB=$(openssl pkey -in <CLIENT_KEY> -pubout -outform DER \
  | sha256sum | awk '{print $1}')
test "$CERT_PUB" = "$KEY_PUB"
unset CERT_PUB KEY_PUB
```

Inspect only public certificate metadata:

```bash
openssl x509 -in <CLIENT_CERT> -noout \
  -subject -issuer -serial -dates -fingerprint -sha256
```

## Network and TLS verification

For a new adapter host, prove the restricted TCP path and then verify TLS identity. A TCP connection alone does not prove certificate trust, MSP authorization, channel access, endorsement, or chaincode behavior.

```bash
openssl s_client \
  -connect 10.104.0.7:7051 \
  -servername peer1.hrc.local \
  -verify_hostname peer1.hrc.local \
  -CAfile <FABRIC_TLS_ROOT_CA_CERT> \
  -verify_return_error </dev/null
```

Pass only when certificate verification returns code 0. Never disable hostname or CA verification to make the route work.

## Activation acceptance

Before enabling a new production writer, prove all of the following:

1. The private Gateway route is reachable from the intended host.
2. TLS validates to `peer1.hrc.local` with the pinned HRC root CA.
3. The dedicated non-admin client certificate/key are present, protected, and matched.
4. MSP/channel/chaincode/default-contract values match the commissioned HRC handoff.
5. Submit/query/verify functions are the source-bound Task 37 API above.
6. The row already has immutable non-empty `finalized_payload`; v2 also has verifier status `verified`.
7. The adapter prepares and durably records the transaction ID, endorsed transaction bytes, and signed commit-status request before submitting to the orderer.
8. Commit status is successful/VALID.
9. `QuerySourceBoundAnchor(SourceRecordID)` exactly matches the prepared anchor.
10. `VerifySourceBoundDigest(SourceRecordID, sha256(finalized_payload))` returns `MATCH`.
11. Only then is the local outbox row marked `confirmed`.

If commit status or post-commit verification is uncertain, preserve the transaction material and reconcile before any resubmission. A stale peer ledger can make client commit-status waiting appear hung even when endorsement and orderer submission succeeded, so isolate endorsement, submission, peer ledger delivery, and commit-status waiting as separate layers.

## Current status and remaining HA boundary

The one-record Task 37 qualification and continuous ULC-01 writer commissioning are already complete; do not repeat the historical qualification candidate just to reconfirm documentation. The next Fabric infrastructure boundary is ULC-02 ownership/fencing acceptance. Until that gate is deliberately passed, ULC-02 must remain write-disabled.

The September 17 research backlog is not evidence that this handoff reverted. The live diagnostic found the ULC-01 adapter healthy while recent v2 rows remained unclaimed with `attempts=0`; the worker claim predicate requires `finalized_payload IS NOT NULL` and, for v2, verifier status `verified`. Diagnose the upstream finalization/eligibility state before chasing Fabric or OpenBao failures.

## Record for a future environment

Record only non-secret values:

```text
Environment:
Fabric Gateway endpoint:
TLS server name:
TLS root CA SHA-256:
MSP ID:
Channel:
Chaincode:
Contract namespace:
Authenticated source identity:
Submit function:
Query function:
Verify function:
Transient exact-payload key:
Client certificate subject/serial/SHA-256/expiry:
Protected private-key location reference:
Endorsement requirements:
Rotation contact:
Support contact:
```

Next: [`02-create-outbox-and-adapter.md`](02-create-outbox-and-adapter.md)
