# 5. Application Implementation Handoff

This guide describes the **current LoRaWAN Fabric adapter implementation boundary**. The HRC team operates the Fabric network; this repository owns the outbox worker, OpenBao evidence seal, Fabric Gateway client, retry/reconciliation state, and HA fencing on the LoRaWAN side.

Authoritative implementation paths:

- `evidence-services/cloud/internal/fabricadapter/repository.go`
- `evidence-services/cloud/internal/fabricadapter/worker.go`
- `evidence-services/cloud/internal/fabricadapter/fabric.go`
- `evidence-services/cloud/deploy/`
- [`02-fabric-network-handoff.md`](02-fabric-network-handoff.md)

The older eight-argument `CreateAnchor` design is retired for production. Do not copy it from historical commissioning notes.

## 5.1 Current HRC contract

The commissioned Task 37 API is:

```text
CreateSourceBoundAnchor(
  SourceRecordID,
  sourceType,
  producer,
  producedAt,
  schemaVersion
)

transient:
  hrc.exact_payload = exact finalized_payload bytes

QuerySourceBoundAnchor(SourceRecordID)
VerifySourceBoundDigest(SourceRecordID, observedDigest)
```

Current connection identity:

```text
FABRIC_GATEWAY_ENDPOINT=10.104.0.7:7051
FABRIC_TLS_SERVER_NAME=peer1.hrc.local
FABRIC_MSP_ID=HrcMSP
FABRIC_CHANNEL=hrc-channel
FABRIC_CHAINCODE=hrc-evidence
FABRIC_CONTRACT=
FABRIC_AUTHENTICATED_SOURCE_SYSTEM_ID=lorawan-gateway-evidence
```

The authenticated source namespace is bound to the dedicated Fabric client identity. It is not supplied as a caller-controlled positional argument to `CreateSourceBoundAnchor`.

## 5.2 Claim eligibility

The normal worker must not touch every `pending` row. The current repository claim predicate requires:

```text
status is pending/failed and next_attempt_at <= now()
  OR an expired processing lease with no Fabric transaction ID

AND finalized_payload IS NOT NULL

AND, for telemetry-attestation-v2:
    matching gateway_evidence.event_verification.status = verified
```

This matters operationally. `pending + attempts=0` can mean the row is **not claimable yet**; it does not by itself mean Fabric, OpenBao, or the adapter is failing.

As of the September 17 research diagnosis, a large set of recent EMU-01 v2 rows was verified but still unclaimed. The immediate investigation boundary is the upstream durable finalization path that populates `finalized_payload` or another claim prerequisite. Do not chase Fabric Gateway transaction errors until claim eligibility is proven.

## 5.3 Exact payload boundary

`telemetry.fabric_outbox.finalized_payload` is an immutable `BYTEA` containing the exact finalized JSON artifact emitted at the upstream acceptance boundary.

The adapter must:

1. require at least one byte;
2. reject payloads larger than the current HRC maximum of 1,048,576 bytes;
3. require valid JSON bytes;
4. preserve those exact bytes without reserialization;
5. calculate SHA-256 over those exact bytes;
6. submit those same bytes only through transient key `hrc.exact_payload`.

Do **not** reconstruct the Fabric payload from JSONB, Go structs, maps, Node-RED values, `telemetry.uplinks.raw_data`, or an independently regenerated canonical projection. Even a semantically equivalent JSON reserialization is a different byte string and therefore a different digest.

The Fabric anchor metadata is built from stable database/source state:

```text
SourceRecordID = source_event_key
sourceType     = event_type
producer       = normalized DevEUI
producedAt     = observed_at UTC RFC3339Nano
schemaVersion  = schema_version
digest         = SHA-256(finalized_payload exact bytes)
payloadLength  = octet length of finalized_payload
```

For v2, the independent gateway verification must still be `verified` before submission.

## 5.4 Local OpenBao evidence seal

The Fabric exact-payload boundary does not remove the local evidence seal. The adapter continues to protect its reviewed canonical evidence with OpenBao Transit and stores the seal fields in `telemetry.fabric_outbox`.

The adapter must:

- use the commissioned OpenBao Transit key and least-privilege AppRole;
- preserve the complete versioned OpenBao signature;
- retain the derived signing-key version ID;
- recompute and verify the stored local seal before a Fabric attempt/reconciliation where required;
- never export or mount the OpenBao evidence private key into the adapter;
- never substitute a local signing key if OpenBao is unavailable.

Keep the Fabric client private key and OpenBao AppRole/evidence-signing boundary separate. Neither belongs in Node-RED, Grafana, PostgreSQL data fields, Git, or ordinary logs.

## 5.5 Durable prepare-before-submit transaction flow

The current Fabric client deliberately separates endorsement/preparation from orderer submission.

```text
claim eligible row with lease
        |
        v
validate exact finalized_payload
        |
        v
verify required v2 gateway evidence
        |
        v
verify/persist local OpenBao evidence seal
        |
        v
CreateSourceBoundAnchor proposal
  five positional args
  + transient hrc.exact_payload
        |
        v
endorse proposal
        |
        v
persist BEFORE submit:
  transaction ID
  endorsed transaction bytes
  signed commit-status request
  returned record ID
        |
        v
submit prepared transaction to orderer
        |
        v
recover/wait for commit status
        |
        v
QuerySourceBoundAnchor(SourceRecordID)
        |
        v
VerifySourceBoundDigest(SourceRecordID, sha256(finalized_payload))
        |
        v
mark confirmed
```

The prepare step is safety-critical. If the process or network fails after orderer acceptance, the worker can restore the same prepared transaction and signed commit-status request after restart instead of generating a different transaction blindly.

Any error after entering the submit stage is conservatively treated as an unknown outcome until authoritative reconciliation proves the ledger state.

## 5.6 Confirmation requirements

A local row becomes `confirmed` only after the adapter has enough authoritative evidence to prove the source-bound anchor.

The post-submit checks must establish:

- commit status is successful with Fabric validation code 0/VALID;
- `QuerySourceBoundAnchor(SourceRecordID)` returns the expected source namespace and source record ID;
- returned digest equals SHA-256 of the exact `finalized_payload` bytes;
- returned payload length equals the exact byte length;
- source type, producer, produced timestamp, and schema version match;
- `VerifySourceBoundDigest(SourceRecordID, observedDigest)` returns `MATCH`.

Proposal success, endorsement, a transaction ID, or orderer submission alone is not confirmation.

A peer can also lag behind the orderer/other peers. If commit waiting appears hung, separate these layers during diagnosis:

```text
proposal / endorsement
orderer submission
ledger commit/delivery to the selected peer
client CommitStatus wait
post-commit query/digest verification
```

Do not immediately resubmit an identical event just because commit-status waiting timed out.

## 5.7 Reconciliation and retries

The outbox uses explicit durable states rather than treating a database transaction ID as proof of ledger success. Current implementation states include normal pending/processing flow plus reconciliation/attention states appropriate to an uncertain submission.

Reconciliation should prefer the existing durable transaction material and ledger reads before any new submission:

1. if a transaction ID and signed commit-status request exist, recover commit status;
2. query the source-bound anchor by `SourceRecordID`;
3. compare all immutable anchor fields;
4. require `VerifySourceBoundDigest(...)=MATCH`;
5. mark confirmed when the existing anchor is authoritative and matches;
6. treat a conflicting anchor as a permanent security conflict;
7. resubmit only when the previous outcome is proven absent/appropriate for retry and the implementation's retry policy allows it.

Transient failures use bounded backoff and persisted `next_attempt_at`; do not sleep while holding a database transaction or row lock. Expired processing leases are reclaimable only under the repository's fenced predicates.

## 5.8 HA ownership boundary

Current cloud posture:

```text
ULC-01: Fabric adapter enabled continuous writer
ULC-02: Fabric adapter installed/staged but FABRIC_ADAPTER_ENABLED=false
ULC-03: no Fabric adapter worker
```

Do not turn on ULC-02 simply because ULC-01 is unavailable. The second writer requires the reviewed ownership/fencing acceptance defined in `evidence-services/cloud/packaging/FABRIC-HA-FENCING.md`. The goal is failover without two workers simultaneously believing they own the same external side effect.

The base Compose profile is intentionally fail-closed. ULC-01 becomes a writer only through the explicit enabled overlay after the activation preflight passes.

## 5.9 Configuration and secrets

Use the deployment templates under `evidence-services/cloud/deploy/`; do not maintain a second hand-written production `.env` contract in this guide.

At minimum the runtime configuration must preserve:

```text
private Fabric Gateway endpoint and TLS server name
HrcMSP / hrc-channel / hrc-evidence / empty contract
CreateSourceBoundAnchor / QuerySourceBoundAnchor / VerifySourceBoundDigest
transient key hrc.exact_payload
source identity lorawan-gateway-evidence
dedicated Fabric client certificate/key paths
OpenBao stable service endpoint and protected AppRole files
stable worker identity and processing/retry bounds
```

Never store real Fabric private keys, OpenBao SecretIDs/tokens, recovery material, LoRaWAN root keys, or active passwords in this repository documentation.

## 5.10 Logging and observability

Useful structured fields include:

- outbox ID and stable event/source record key;
- schema version;
- worker ID and lease generation;
- payload length and payload SHA-256, but not unrestricted payload contents;
- gateway verification ID/status for v2;
- OpenBao signing-key version ID and local-seal verification result;
- Fabric transaction ID and HRC record ID;
- prepare, submit, commit-status, query, and verify timestamps/results;
- retry count, next attempt, and error category.

Do not log private keys, tokens, complete sensitive payloads, unrestricted personal data, or secret-mounted file contents.

## 5.11 Current troubleshooting order

For a row that is not reaching Fabric, inspect from the failing layer outward:

```text
1. Is the row selected for Fabric at all?
2. Is finalized_payload non-null and valid exact JSON bytes?
3. For v2, is gateway evidence verified?
4. Is next_attempt_at due and is there a valid/reclaimable lease state?
5. Is the adapter enabled and healthy on the owning host?
6. Does the local OpenBao seal/sign/verify path pass?
7. Does Fabric proposal/endorsement pass?
8. Does orderer submission pass?
9. Does commit status resolve on the selected peer?
10. Does source-bound query + digest verification match?
```

This order prevents an upstream eligibility problem from being misdiagnosed as a blockchain outage.

References:

- [`02-fabric-network-handoff.md`](02-fabric-network-handoff.md)
- [`../../fabric-attestation/01-collect-external-fabric-handoff.md`](../../fabric-attestation/01-collect-external-fabric-handoff.md)
- [`../../cloud-production/20-openbao-and-fabric-adapter.md`](../../cloud-production/20-openbao-and-fabric-adapter.md)
- Fabric Gateway client model: https://hyperledger-fabric.readthedocs.io/en/latest/gateway.html

Next: [`06-security-operations-and-testing.md`](06-security-operations-and-testing.md)
