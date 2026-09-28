# Fabric synchronized research-test contract

The LoRaWAN side is the authoritative orchestrator for joint tests. It owns test/run/trial IDs, source-record IDs, exact payload bytes and SHA-256, workload schedules, and phase markers. Fabric must consume the same manifests and return those same identifiers.

Commissioned integration identifiers remain:
- source system: `lorawan-gateway-evidence`
- Gateway endpoint: `10.104.0.7:7051`
- TLS name: `peer1.hrc.local`
- channel: `hrc-channel`
- chaincode: `hrc-evidence`
- create/query/verify semantics: `CreateSourceBoundAnchor`, `QuerySourceBoundAnchor`, `VerifySourceBoundDigest`

## Exchange files

LoRaWAN sends:
- `run-manifest.json` + `.sha256`
- `record-manifest.json` + `.sha256`
- phase marker JSON files when applicable.

Fabric returns:
- `fabric-transactions.ndjson`
- `fabric-summary.json`
- block evidence for P2 when required
- SHA-256 manifest for its export.

Exact correlation key:
`run_id + trial_id + source_record_id + payload_sha256`.

Unknown IDs, wrong hashes, missing required records, unexpected duplicate result rows, or manifest-hash mismatch make the joint evidence INVALID.

## Tests requiring synchronized Fabric evidence

P1: observe real anchors; return commit/TxID/query evidence.
P2: four valid-load rates, 300 seconds, 3 repetitions, matched control for every Fabric run; order is control/Fabric, Fabric/control, control/Fabric for repetitions 1/2/3.
R2: 10 normal, 10 outage, restore and reconcile the exact same 10; query/digest/commit evidence required.
A2: 10 normal, 10 endorsement violation, 10 restored; pre/post world-state proof.
I1/I2: immutable digest/query comparison for controlled alteration/tamper conditions.
I3: 10 baseline, 10 same-hash duplicates, 10 conflicting overwrite attempts; post-attempt query mandatory.
T1/T2: persisted ledger linkage for 10 individual records and 10 non-overlapping five-record histories.

R1 and A1 may use Fabric as downstream/condition-specific evidence. S1/F1/F2 must not be coupled to an active Fabric fault actor. S2 remains BLOCKED_BY_METHODOLOGY.

## Ready handshake

Before counted joint testing:
1. Fabric validates the schemas in `test/automation/fabric-sync/`.
2. Both sides exchange the run-manifest SHA-256.
3. For real sensor tests, LoRaWAN seals the record manifest after exact records exist.
4. Fabric exports a short rehearsal result.
5. LoRaWAN runs `fabric_sync.py verify-fabric-export`.
6. Only exact PASS correlation permits promotion to formal execution.
