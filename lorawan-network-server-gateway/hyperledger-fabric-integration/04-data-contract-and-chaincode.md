# 4. Data Contract and Chaincode Design

The Fabric team needs a stable contract, not an informal promise that Node-RED will send some JSON. Freeze the contract before chaincode development.

## 4.1 Canonical attestation example

This is an example contract. The Fabric team must approve the final field names and validation rules:

~~~json
{
  "schema_version": "telemetry-attestation-v1",
  "event_key": "dev-eui|frame-counter|observed-time|gateway-id",
  "event_type": "sensor_window_attested",
  "source": {
    "gateway_id": "2ccf67fffe0abee3",
    "network_server": "chirpstack",
    "application_id": "agriculture",
    "device_id": "dragino-s31-01"
  },
  "asset": {
    "asset_id": "farm-block-a-greenhouse-01",
    "asset_type": "greenhouse"
  },
  "window": {
    "start": "2026-08-05T03:00:00Z",
    "end": "2026-08-05T04:00:00Z",
    "sample_count": 60
  },
  "summary": {
    "temperature_c_min": 22.1,
    "temperature_c_max": 27.4,
    "temperature_c_avg": 24.7,
    "humidity_percent_avg": 71.2
  },
  "evidence": {
    "database": "lorawan_telemetry",
    "reference": "telemetry-window:2026-08-05T03:00:00Z/2026-08-05T04:00:00Z",
    "digest_algorithm": "SHA-256",
    "digest": "REPLACE_WITH_SHA256_DIGEST"
  },
  "submitted_by": "REPLACE_WITH_ORGANIZATION",
  "created_at": "2026-08-05T04:01:00Z"
}
~~~

Do not put the raw payload, LoRaWAN application session keys, device root keys, or personal data into the public transaction payload.

## 4.2 Canonicalization and hashing

All parties must produce the same digest. Agree on:

- UTF-8 encoding;
- exact field names;
- omission versus explicit null values;
- number representation;
- timestamp format and precision;
- array ordering;
- object-key ordering;
- whitespace handling;
- digest algorithm;
- whether the digest covers the evidence locator.

The safest implementation is to use a standards-based canonical JSON library selected by the application team. Do not calculate a digest from a JavaScript object using an unspecified serializer and assume another language will produce the same bytes.

Illustrative sequence:

~~~text
selected rows
  -> fixed field projection
  -> UTC timestamp normalization
  -> canonical JSON serialization
  -> SHA-256
  -> Fabric CreateAttestation transaction
~~~

## 4.3 Suggested chaincode transactions

Ask the Fabric team whether the contract will expose functions equivalent to:

| Function | Purpose |
|---|---|
| CreateAttestation | Create a new event if event_key does not exist |
| ReadAttestation | Return the current attestation by event key |
| VerifyAttestation | Compare a supplied digest with the committed digest |
| ListAssetAttestations | Query the history for an authorized asset |
| RecordException | Register a threshold or compliance exception |
| ApproveAttestation | Add an organization approval when the workflow requires it |
| GetContractVersion | Report the deployed contract schema |

The chaincode must reject:

- an empty event key;
- an unsupported schema version;
- malformed timestamps;
- an invalid digest;
- a duplicate key with a different digest;
- a caller that lacks the required role;
- an event outside the allowed business rule.

## 4.4 State-key and correction model

Prefer immutable attestation records:

~~~text
state key: attestation:<event_key>
original record: immutable
correction: new transaction referencing the original
status: corrected, superseded, rejected, or voided
~~~

Do not overwrite a historical measurement without leaving a correction record. Off-chain data can be corrected under the retention and governance policy, but the chain should retain the relationship between the original attestation and its correction.

## 4.5 Endorsement policy questions

The policy must follow the business process:

- Does the submitting organization alone attest source ingestion?
- Must an independent auditor endorse a quality record?
- Must both producer and buyer endorse a custody transfer?
- Should a port operator and shipping line both endorse a handover?
- Can the network continue if one organization is offline?
- Is the policy different for a correction or rejection?

Fabric endorsement policies specify which organizations must endorse a transaction. They are not the same as user-interface permissions or the application's local authorization rules.

## 4.6 Private data decision

Use a private data collection or a separate channel only when the organizations need a shared ledger workflow but should not see the same business fields. Keep raw sensor data off-chain even when private data is available. Private collections still create operational, backup, membership, and retention responsibilities.

Examples:

| Data | Public channel | Private collection |
|---|---:|---:|
| Attestation ID and digest | Usually suitable | Usually unnecessary |
| Exact commercial price | No | Potentially |
| Supplier identity | Depends on governance | Potentially |
| Raw sensor payload | No | Usually keep off-chain |
| Inspection decision | Depends on process | Potentially |

References:

- [Fabric chaincode lifecycle](https://hyperledger-fabric.readthedocs.io/en/latest/chaincode_lifecycle.html)
- [Endorsement policies](https://hyperledger-fabric.readthedocs.io/en/latest/endorsement-policies.html)
- [Private data architecture](https://hyperledger-fabric.readthedocs.io/en/latest/private-data-arch.html)

Next: [05-application-implementation.md](05-application-implementation.md)
