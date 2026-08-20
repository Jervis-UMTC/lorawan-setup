# 4. Data Contract and Chaincode Design

The Fabric team needs a stable contract, not an informal promise that Node-RED will send some JSON. Freeze the contract before chaincode development.

## 4.1 Separate the signed evidence from the ledger envelope

Do not put the digest or digital signature **inside the JSON object that is being hashed and signed**. Doing that creates a circular definition: the digest would depend on a document that already contains the digest.

Use two explicit objects instead:

```text
TimescaleDB source rows
        |
        v
canonical evidence object  <--- this exact object is canonicalized
        |
        +--> RFC 8785 canonical JSON UTF-8 bytes
                 |
                 +--> SHA-256 digest
                 |
                 +--> OPENBAO-TRANSIT-ECDSA-P256-SHA2-256 signature
                              |
                              v
                   Fabric attestation envelope
                   contains event_key + digest +
                   seal metadata, not raw payload
```

### Canonical evidence object

For a single accepted ChirpStack uplink, use an evidence projection with explicit provenance. The following is the baseline contract for this repository; if the Fabric team changes it, change the schema version and provide new test vectors rather than silently changing `telemetry-attestation-v1`:

~~~json
{
  "schema_version": "telemetry-attestation-v1",
  "event_key": "<FABRIC_STABLE_EVENT_KEY>",
  "source_event_key": "<CHIRPSTACK_DEDUPLICATION_OR_DERIVED_EVENT_KEY>",
  "event_type": "lorawan_uplink_accepted",
  "source": {
    "network_server": "chirpstack",
    "application_id": "<APPLICATION_ID>",
    "device_id": "<DEVICE_ID>",
    "device_model": "<DEVICE_MODEL>",
    "dev_eui": "<16_HEX_DEV_EUI>",
    "gateway_id": "<GATEWAY_EUI_OR_NULL>",
    "region": "<CHIRPSTACK_REGION_ID>"
  },
  "lorawan": {
    "f_port": 2,
    "f_cnt": 104,
    "confirmed": false
  },
  "observation": {
    "observed_at": "<CHIRPSTACK_EVENT_TIME_UTC>",
    "received_at": "<APPLICATION_RECEIPT_TIME_UTC>"
  },
  "payload": {
    "raw_data_base64": "<CHIRPSTACK_DATA_FIELD_OR_NULL>",
    "decoded_payload": {},
    "decoder_version": "<REVIEWED_DECODER_VERSION>"
  }
}
~~~

`gateway_id`, RSSI, and SNR are gateway/network observations, not sensor-authenticated application values. Include them in a canonical evidence schema only when the business attestation actually needs those observations, and label them as gateway observations. Do not describe them as cryptographic proof from the sensor.

For `telemetry-attestation-v1`, the source for this object is the **accepted ChirpStack application event stored in TimescaleDB**, not a hash or JSON object supplied by the Raspberry Pi gateway. The LoRaWAN Network Server has already processed the uplink before this application event exists.

Do not retroactively reinterpret v1 as gateway-journal verified. The stronger gateway lineage is introduced only by the separately versioned v2 contract below.

Use the outbox `event_key` (for example `uplink:<source_event_key>`) as `event_key` in both the canonical evidence and Fabric state. Preserve the original telemetry `event_key` separately as `source_event_key`. This makes retries idempotent without losing the exact TimescaleDB source identity.

### Fabric attestation payload plan

The dissertation baseline uses Fabric as an attestation ledger, not as the primary telemetry store. The full raw payload, decoded sensor values, DevEUI, gateway observations, frame counter, and complete canonical evidence stay in TimescaleDB / the protected outbox evidence record. Their integrity is covered by the digest and OpenBao signature.

For the client-to-chaincode call, send only the fields that the adapter must supply and that cannot be derived safely by the ledger:

~~~json
{
  "schema_version": "telemetry-attestation-v1",
  "event_key": "<STABLE_IDEMPOTENCY_KEY>",
  "event_type": "lorawan_uplink_accepted",
  "digest": "<64_LOWERCASE_HEX_CHARACTERS>",
  "seal_algorithm": "OPENBAO-TRANSIT-ECDSA-P256-SHA2-256",
  "seal_key_id": "openbao:transit:lorawan-evidence:v<KEY_VERSION>",
  "seal_signature": "<COMPLETE_OPENBAO_VERSIONED_SIGNATURE>"
}
~~~

This seven-field object is the **planned dissertation transaction input**. If the Fabric SDK or chaincode uses positional string arguments instead of one JSON argument, preserve exactly the same seven values and order them explicitly in the contract documentation. Do not add arbitrary telemetry fields merely because they are available in PostgreSQL.

The ledger may store a richer attestation envelope after chaincode adds authoritative or fixed metadata:

~~~json
{
  "schema_version": "telemetry-attestation-v1",
  "event_key": "<STABLE_IDEMPOTENCY_KEY>",
  "event_type": "lorawan_uplink_accepted",
  "digest_algorithm": "SHA-256",
  "digest": "<64_LOWERCASE_HEX_CHARACTERS>",
  "seal_algorithm": "OPENBAO-TRANSIT-ECDSA-P256-SHA2-256",
  "seal_key_id": "openbao:transit:lorawan-evidence:v<KEY_VERSION>",
  "seal_signature": "<COMPLETE_OPENBAO_VERSIONED_SIGNATURE>",
  "off_chain_store": "timescaledb",
  "submitted_by": "<DERIVED_FABRIC_CALLER_ORGANIZATION>",
  "created_at": "<FABRIC_TRANSACTION_TIME_UTC>"
}
~~~

`digest_algorithm` and `off_chain_store` are contract constants for this baseline and therefore do not need to be caller-controlled. `submitted_by` should be derived from the authenticated Fabric client identity/MSP rather than accepted as a free-form application string. `created_at` should come from the Fabric transaction context or another deterministic chaincode-approved time source rather than the sensor payload. This reduces spoofable metadata and makes the ledger record describe who actually submitted the transaction.

The signature is over the exact RFC 8785 canonical UTF-8 bytes of the **off-chain canonical evidence object**, not over the Fabric payload and not over the printable hexadecimal digest string. The separately stored SHA-256 digest is calculated from those same canonical bytes.

Do not put LoRaWAN application/session/root keys, Fabric private keys, OpenBao credentials, unrestricted personal data, or unrestricted raw telemetry into ledger state or logs. The on-chain record is intentionally small: it is a stable identity plus cryptographic proof that can be checked against the preserved off-chain evidence.

## 4.2 Canonicalization, digest, and evidence seal

This repository uses the following baseline rules for `telemetry-attestation-v1`:

1. Build the exact field projection shown by the approved schema. Do not use `SELECT *` or serialize arbitrary database rows.
2. Convert `observed_at` and `received_at` to UTC RFC 3339 with **exactly millisecond precision**: `YYYY-MM-DDTHH:mm:ss.sssZ`. In Node.js this is the form returned by `new Date(value).toISOString()`. Reject an invalid timestamp; do not use locale-formatted dates or preserve implementation-dependent fractional precision.
3. Include every key shown in the baseline evidence schema. For nullable source fields, write explicit JSON `null`; do not sometimes omit the property. `decoded_payload` must always be a JSON object, using `{}` when the accepted event contains no decoded fields.
4. Canonicalize the resulting JSON according to **RFC 8785, JSON Canonicalization Scheme (JCS)**. Do not use plain `JSON.stringify()` as the cross-language canonicalization contract.
5. Encode the canonical JSON as UTF-8 bytes.
6. Calculate SHA-256 over those exact bytes and store 64 lowercase hexadecimal characters as `digest_sha256`.
7. Base64-encode the exact canonical UTF-8 bytes and send them to OpenBao Transit key `lorawan-evidence` at the `sha2-256` signing endpoint with `prehashed=false` and ASN.1 ECDSA marshaling. OpenBao owns the non-exportable `ecdsa-p256` private key; the adapter must never receive private-key bytes.
8. Store the **complete versioned signature string returned by OpenBao**, including its key-version tag. Do not strip the prefix/version and do not store only the Base64 signature body.
9. Parse the key version from the returned versioned signature and record the deterministic key ID `openbao:transit:lorawan-evidence:v<version>`. Reject a response that does not contain a valid positive key version.
10. Record `OPENBAO-TRANSIT-ECDSA-P256-SHA2-256` as `evidence_signature_alg`, then persist `canonical_json`, digest, algorithm, key ID, complete versioned signature, and seal timestamp together before the first Fabric network call.
11. On every retry, recompute the digest from the stored `canonical_json` and ask OpenBao Transit to verify the **same stored canonical bytes and complete stored signature**. **Do not rebuild a different canonical document from currently mutable telemetry after the event has been sealed.**

The sequence is therefore:

~~~text
approved TimescaleDB source fields
  -> fixed telemetry-attestation-v1 projection
  -> normalize timestamps and null handling
  -> RFC 8785 canonical JSON
  -> exact UTF-8 bytes
       |                    |
       |                    +--> Base64 exact bytes
       |                              |
       |                              v
       |                    OpenBao Transit sign
       |                    ecdsa-p256 + sha2-256
       |                              |
       |                              v
       |                    versioned KMS signature
       +--> SHA-256 --> digest         |
                 |                    |
                 +---------+----------+
                           v
                  persist complete seal
                 |
                 v
          Fabric CreateAttestation
~~~

A successful OpenBao verification proves that the canonical evidence bytes match a signature created by the corresponding historical version of the configured Transit key. The adapter never receives that private key. This still does **not** prove that a physically compromised sensor measured the real world correctly, and it does not make the Raspberry Pi filesystem immutable. A compromised adapter credential that retains Transit `sign` permission can request signatures over attacker-chosen bytes, so the one-way outbox seal, least-privilege OpenBao policy, KMS audit/operations controls, and separation of KMS administration remain part of the trust boundary.

### Required RFC 8785 startup test vector

Every adapter implementation must carry this exact test fixture and refuse to process outbox rows if its canonicalizer or digest differs.

Input object:

~~~json
{
  "schema_version": "telemetry-attestation-v1",
  "event_key": "uplink:test",
  "source_event_key": "test",
  "event_type": "lorawan_uplink_accepted",
  "source": {
    "network_server": "chirpstack",
    "application_id": "test",
    "device_id": "test-device",
    "device_model": "test-model",
    "dev_eui": "0000000000000001",
    "gateway_id": "0000000000000002",
    "region": "as923_3"
  },
  "lorawan": {
    "f_port": 2,
    "f_cnt": 104,
    "confirmed": false
  },
  "observation": {
    "observed_at": "2000-01-01T00:00:00.000Z",
    "received_at": "2000-01-01T00:00:01.000Z"
  },
  "payload": {
    "raw_data_base64": "AQI=",
    "decoded_payload": {
      "battery_v": 3.6,
      "temperature_c": 24.5
    },
    "decoder_version": "test-v1"
  }
}
~~~

Expected RFC 8785 canonical JSON, shown on one line with no trailing newline:

~~~text
{"event_key":"uplink:test","event_type":"lorawan_uplink_accepted","lorawan":{"confirmed":false,"f_cnt":104,"f_port":2},"observation":{"observed_at":"2000-01-01T00:00:00.000Z","received_at":"2000-01-01T00:00:01.000Z"},"payload":{"decoded_payload":{"battery_v":3.6,"temperature_c":24.5},"decoder_version":"test-v1","raw_data_base64":"AQI="},"schema_version":"telemetry-attestation-v1","source":{"application_id":"test","dev_eui":"0000000000000001","device_id":"test-device","device_model":"test-model","gateway_id":"0000000000000002","network_server":"chirpstack","region":"as923_3"},"source_event_key":"test"}
~~~

Expected SHA-256 of the exact UTF-8 bytes above:

~~~text
c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c
~~~

Do not copy the Markdown newline after the displayed canonical text into the bytes being tested. The adapter test fixture should store the expected string as a language string/byte constant and compare both exact bytes and digest.

## 4.2A `telemetry-attestation-v2` gateway-verified contract

`telemetry-attestation-v2` preserves the core v1 business/source/LoRaWAN/observation/payload meaning and adds one **fixed gateway-evidence object**. It is created only after the independent verifier reports `verified`.

Conceptual projection:

~~~json
{
  "schema_version": "telemetry-attestation-v2",
  "event_key": "<FABRIC_STABLE_EVENT_KEY>",
  "source_event_key": "<CHIRPSTACK_EVENT_KEY>",
  "event_type": "lorawan_uplink_accepted",
  "source": {
    "network_server": "chirpstack",
    "application_id": "<APPLICATION_ID>",
    "device_id": "<DEVICE_ID>",
    "device_model": "<DEVICE_MODEL>",
    "dev_eui": "<16_HEX_DEV_EUI>",
    "gateway_id": "<GATEWAY_EUI>",
    "region": "<CHIRPSTACK_REGION_ID>"
  },
  "lorawan": {
    "f_port": 2,
    "f_cnt": 104,
    "confirmed": false
  },
  "observation": {
    "observed_at": "<CHIRPSTACK_EVENT_TIME_UTC>",
    "received_at": "<APPLICATION_RECEIPT_TIME_UTC>"
  },
  "payload": {
    "raw_data_base64": "<CHIRPSTACK_DATA_FIELD_OR_NULL>",
    "decoded_payload": {},
    "decoder_version": "<NODE_RED_MAPPING_VERSION>"
  },
  "gateway_evidence": {
    "status": "verified",
    "verification_id": 12345,
    "gateway_id": "<GATEWAY_EUI>",
    "journal_segment_id": 53,
    "journal_sequence": 52987,
    "journal_record_hash": "<64_LOWERCASE_HEX>",
    "journal_segment_hash": "<64_LOWERCASE_HEX>",
    "checkpoint_id": 812,
    "gateway_event_id": 99123,
    "decoder_id": "<TRUSTED_DECODER_ID>",
    "decoder_version": "<TRUSTED_DECODER_VERSION_OR_CODE_HASH>",
    "raw_app_data_sha256": "<64_LOWERCASE_HEX>",
    "normalized_digest_sha256": "<64_LOWERCASE_HEX>"
  }
}
~~~

Rules:

1. `gateway_evidence.status` is exactly `verified` in v2. Do not create a v2 canonical evidence object containing `pending`, `evidence_gap`, or `integrity_failure` and then describe it as gateway-verified.
2. The verifier row is referenced by stable IDs/hashes; full journal records, segments, and captured gateway-event objects stay off-chain.
3. `gateway_evidence.gateway_id` must agree with the approved source/gateway lineage. A mismatch is a permanent evidence error.
4. The trusted decoder fields refer to the **independent** decoder, not only the Node-RED mapping version in `payload.decoder_version`.
5. `raw_app_data_sha256` is calculated from the accepted raw ChirpStack application `data` bytes used by the trusted decoder.
6. `normalized_digest_sha256` is calculated from the versioned deterministic normalized object produced by the trusted decoder.
7. The adapter loads the gateway-evidence fields from the verifier-owned database state. It must not accept them from an MQTT payload, Node-RED flow property, or arbitrary gateway JSON.
8. Once canonicalized and sealed, v2 follows the same exact-byte OpenBao one-way seal and Fabric retry rules as v1.

### v2 canonicalization test vector is a deployment blocker

The existing v1 startup vector and digest remain unchanged:

~~~text
c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c
~~~

Do **not** copy that digest and call it the v2 vector. Before a v2 adapter is allowed to process real rows, create a reviewed fixed v2 input object, calculate its exact RFC 8785 canonical string and SHA-256 with at least two independent implementations or an approved reference implementation, commit that vector to the adapter tests, and make startup fail on any mismatch.

Until that v2 vector is reviewed and pinned, v2 implementation is incomplete even if the database gate exists.

### v2 Fabric envelope

The ledger envelope keeps the same pattern as v1 but uses:

~~~text
schema_version = telemetry-attestation-v2
~~~

The digest and OpenBao signature still cover the exact canonical **v2 evidence object**, not the Fabric envelope. Chaincode may store compact business fields plus digest/seal metadata; it does not need the full journal.

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

For the dissertation baseline, the submit operation must have an unambiguous equivalent of:

~~~text
CreateAttestation(
  schema_version,
  event_key,
  event_type,
  digest,
  seal_algorithm,
  seal_key_id,
  seal_signature
)
~~~

The function name may differ in the external Fabric environment, but these seven caller-supplied values and their meanings must remain stable unless the contract version is deliberately changed. `submitted_by` must come from the authenticated Fabric client identity, and the ledger timestamp must come from the transaction context rather than additional free-form caller arguments.

The chaincode must reject:

- an empty event key;
- an unsupported schema version; the contract must explicitly list the approved v1/v2 versions rather than accepting arbitrary future strings;
- a v2 record that claims a gateway-evidence status other than `verified` when that field is carried on-chain;
- an unsupported digest or seal algorithm;
- a digest that is not exactly 64 lowercase hexadecimal characters;
- a malformed signing-key ID or empty signature field when the contract requires seal metadata;
- malformed timestamps;
- a duplicate key with a different digest;
- a duplicate key whose digest matches but immutable seal metadata conflicts with the existing attestation;
- a caller that lacks the required role;
- an event outside the allowed business rule.

The ledger can preserve the signature and key ID as attestation metadata, but the baseline chaincode does not possess the off-chain canonical evidence bytes—including the v2 journal/decoder references—and therefore does not claim to independently verify that ECDSA signature. Verification is performed by the adapter before submission and by reconciliation against the preserved off-chain canonical evidence. If governance requires peers to verify the evidence signature themselves, define a separate reviewed contract that gives chaincode the exact signed bytes or a carefully specified pre-hashed signature scheme; do not pretend a signature can be verified from unrelated fields.

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
