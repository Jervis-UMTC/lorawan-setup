# evidence-ingest-api-v1

This is the cloud-facing transport contract for gateway journal checkpoints and closed journal segments.

## Trust boundary

The application handler never trusts a caller-supplied gateway identity header. An `IdentityProvider` must supply a verified machine identity. The first implementation includes direct TLS client-certificate identity using a verified chain, `clientAuth` EKU, and a certificate Common Name that is exactly one 16-hex Gateway EUI. A future HAProxy/shared-443 adapter must be separately reviewed before trusting proxy-forwarded certificate metadata.

For every request:

```text
verified client Gateway EUI == path Gateway EUI == body Gateway EUI
```

Any mismatch is rejected before durable acceptance.

## Routes and methods

```text
POST /v1/gateways/<GATEWAY_EUI>/checkpoints
PUT  /v1/gateways/<GATEWAY_EUI>/segments/<SEGMENT_ID>
GET  /livez
GET  /readyz
```

Checkpoint and segment requests use `Content-Type: application/json` and are subject to the configured body-size limit.

## Checkpoint request

```json
{
  "checkpoint_version": "gateway-checkpoint-v1",
  "gateway_id": "0016c001f139a1cb",
  "segment_id": 53,
  "last_sequence": 53000,
  "last_record_hash": "<64-lowercase-hex>",
  "segment_hash": "<64-lowercase-hex>",
  "created_at": "2000-01-01T00:10:00Z"
}
```

The service computes `checkpoint_digest` from semantic fields, not raw JSON key order:

```text
ASCII("gateway-checkpoint-v1")
0x00
lowercase_gateway_eui
0x00
base10(segment_id)
0x00
base10(last_sequence)
0x00
lowercase(last_record_hash)
0x00
lowercase(segment_hash)
0x00
UTC_RFC3339Nano(created_at)
```

Then:

```text
checkpoint_digest = lowercase_hex(SHA256(exact_bytes_above))
```

The repository uniqueness boundary remains `(gateway_id,last_sequence)`. Same semantic digest is idempotent; same identity with different semantic content is a security conflict. A new checkpoint whose `last_sequence` is lower than an already accepted checkpoint for that gateway is rejected as a checkpoint regression unless a separate explicit incident-recovery procedure is invoked. The production PostgreSQL repository must enforce the duplicate/conflict/regression decision atomically per gateway; a plain unique constraint is not sufficient by itself.

Fixed checkpoint-digest vector:

```text
gateway_id=0016c001f139a1cb
segment_id=1
last_sequence=2
last_record_hash=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
segment_hash=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
created_at=2000-01-01T00:10:00Z
checkpoint_digest=fde615a8eb264090d324fe5642e0992748de9cc4f2d73cbd8f43459e12792903
```

The expected digest was independently constructed with PowerShell from the exact NUL-separated byte contract.

## Segment request envelope

The upload API does not need to understand the still-separately-versioned internal record serialization in order to preserve exact closed-segment bytes. The uploader sends the exact closed-segment object as base64 plus the footer/header metadata used for indexing:

```json
{
  "segment_version": "gateway-journal-segment-v1",
  "gateway_id": "0016c001f139a1cb",
  "segment_id": 53,
  "first_sequence": 52001,
  "last_sequence": 53000,
  "record_count": 1000,
  "previous_segment_hash": "<GENESIS-for-segment-1-or-64-lowercase-hex-prior-segment-hash>",
  "final_record_hash": "<64-lowercase-hex>",
  "segment_hash": "<64-lowercase-hex>",
  "object_sha256": "<64-lowercase-hex>",
  "object_base64": "<exact-closed-segment-bytes>"
}
```

For this contract, `segment_id`, `first_sequence`, `last_sequence`, and checkpoint `last_sequence` are positive signed-64-bit values. Segment `1` requires exact predecessor token `GENESIS`; `GENESIS` is rejected on every later segment, whose predecessor is the previous lowercase 64-hex segment hash.

The ingest service:

1. validates identity/path/basic metadata;
2. base64-decodes the exact object bytes;
3. recomputes and requires `object_sha256` equality;
4. writes raw bytes create-if-absent at stable logical ref `segments/<gateway_id>/<segment_id>.segment`;
5. only after raw-store acceptance attempts metadata acceptance;
6. returns success only after both raw storage and metadata acceptance succeed.

If metadata persistence fails after raw creation, the immutable object is left in place. A retry reuses it; the service never deletes potentially useful evidence to simulate transactionality across two durable systems.

The **verifier**, not ingest, later parses every record, verifies the frozen `gateway-journal-v1` / `gateway-journal-segment-v1` byte contract and hash chain, and sets `verify_status`.

Successful `200`/`201` responses now follow [`evidence-ingest-receipt-v1`](../evidence-ingest-receipt-v1/README.md). They bind the accepted Gateway EUI, segment/sequence identity, checkpoint digest or segment/object hashes, and the original persisted server acceptance time into a stable SHA-256 `receipt_id`. Exact retries return the same original server time and receipt ID. The receipt hash is not a signature; HTTPS/mTLS authenticates the server response. The current Rust source validates/stores receipt state but still exposes no local-evidence retirement/delete path.

## HTTP outcomes

```text
201 Created -> request caused a durable checkpoint/segment layer to be newly created; returns evidence-ingest-receipt-v1
200 OK      -> exact idempotent retry converged to existing identity; returns the same original receipt identity/time
400         -> malformed/version/hash/body/path request
401         -> no verified machine identity
403         -> verified identity does not match requested Gateway EUI
409         -> same durable identity conflicts, or checkpoint would regress accepted history
413         -> request exceeds body limit
415         -> unexpected content type
503         -> readiness dependency unavailable
500         -> other persistence/internal error; no false acceptance
```
