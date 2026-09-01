# evidence-ingest-receipt-v1

This contract freezes the success acknowledgement returned by `gateway-evidence-ingest` after a checkpoint or closed segment has reached its accepted durable metadata boundary.

The receipt is designed for **idempotent uploader acknowledgement**. It binds the accepted gateway/artifact identity, the relevant evidence digest(s), and the original server acceptance time. It is not a digital signature.

## Trust boundary

The response is authenticated in transit by the reviewed HTTPS/mTLS server connection. `receipt_id` is an unkeyed SHA-256 integrity identifier so Go and Rust can independently prove that the response fields belong together. Anyone with arbitrary gateway-root access can rewrite local receipt state and recompute an unkeyed hash; therefore this receipt does not replace TLS, remote server evidence, or the later verifier.

The Rust gateway source now validates and durably persists canonical receipt state and the HTTPS/mTLS uploader is implemented; SeaweedFS S9 and the cloud ingest path are commissioned. This contract **still does not authorize deletion or retirement of local evidence**. That destructive policy remains disabled until a reviewed retention/delete policy exists and one normal physical-gateway reconciliation path proves the complete lifecycle.

## Common response fields

Every successful checkpoint or segment response is JSON with:

```json
{
  "status": "accepted",
  "created": true,
  "receipt_version": "evidence-ingest-receipt-v1",
  "artifact_type": "segment",
  "gateway_id": "0016c001f139a1cb",
  "segment_id": 1,
  "last_sequence": 2,
  "segment_hash": "<64-lowercase-hex>",
  "object_sha256": "<64-lowercase-hex>",
  "receipt_id": "<64-lowercase-hex>",
  "server_received_at": "2000-01-01T00:00:05.000Z"
}
```

Rules:

- `status` is exactly `accepted`.
- `receipt_version` is exactly `evidence-ingest-receipt-v1`.
- `artifact_type` is exactly `checkpoint` or `segment`.
- `gateway_id` is canonical lowercase 16-hex.
- `segment_id` and `last_sequence` are positive signed-64-bit-compatible integers.
- `server_received_at` is the **original persisted server acceptance timestamp**, formatted UTC with exactly millisecond precision.
- an exact idempotent retry returns the same identity/digest fields, the same `server_received_at`, and therefore the same `receipt_id`.
- `created` is deliberately **not** part of the receipt hash. It is only a response hint indicating whether this request caused a durable layer to be newly created. A retry/recovery path may legitimately differ in `created` without changing the accepted receipt identity.

## Checkpoint receipt

Checkpoint responses additionally contain:

```text
checkpoint_digest = required
segment_hash       = absent
object_sha256      = absent
```

`receipt_id` is SHA-256 over these exact UTF-8 fields separated by one NUL byte (`0x00`) with no trailing NUL:

```text
evidence-ingest-receipt-v1
checkpoint
lowercase_gateway_id
base10(segment_id)
base10(last_sequence)
checkpoint_digest
<empty field>
server_received_at
```

Then:

```text
receipt_id = lowercase_hex(SHA256(exact_preimage_bytes))
```

The empty field preserves the same eight-field framing used by the segment receipt.

## Segment receipt

Segment responses contain:

```text
checkpoint_digest = absent
segment_hash       = required
object_sha256      = required
```

`receipt_id` is SHA-256 over:

```text
evidence-ingest-receipt-v1
segment
lowercase_gateway_id
base10(segment_id)
base10(last_sequence)
segment_hash
object_sha256
server_received_at
```

with the same single-NUL separator and no trailing NUL.

## Independent fixed vectors

The vectors below use the already-frozen two-record `gateway-journal-segment-v1` fixture:

```text
gateway_id        = 0016c001f139a1cb
segment_id        = 1
last_sequence     = 2
last_record_hash  = 0fbfe1314ab5a7c779ff4872048a02dffa77b2c9c97826f1a62bedf6a070297f
segment_hash      = 722638f91ff762185aff7c002044911226661c0efc8b70ce71b22a7f168bae90
object_sha256     = 9f34ad301bc0b1b806e2cb0c39a4baaa7509e79b8822f7f367a08720835403f1
checkpoint_time   = 2000-01-01T00:00:04.000Z
server_received_at = 2000-01-01T00:00:05.000Z
```

Expected values:

```text
checkpoint_digest     = 3f7cc53ee0161e73389a8db5764082aa2b293b53f2187023c2107fa1ba935d36
checkpoint_receipt_id = 99e21a0f3fb156e5b9b0b553235698852eb624deb138b74da64e54615ea1333c
segment_receipt_id    = a5a6378baffe6a4b58aa82bc3875e5534c7964669c2a213e37e47768720930fb
```

These three values were independently reproduced with Node.js from the documented NUL-separated fields. Rust tests pin the same values, and Go handler tests pin both receipt IDs.

## Retry ordering

For checkpoints, the server first checks the exact durable identity `(gateway_id,last_sequence)`. If that exact identity already exists with the same semantic digest, the server returns its original receipt even if a newer checkpoint was accepted later. Only a **new, previously unseen** checkpoint behind the latest accepted sequence is classified as regression.

This distinction matters during WAN recovery: replaying an already-accepted old request must be idempotent, while introducing new stale history must still fail closed.

## Local receipt state

The Rust `UploadReceiptState` keeps checkpoint and segment receipts in separate maps keyed by `segment_id`. It accepts an exact repeated receipt and rejects conflicting receipt bytes for an already-recorded identity. The current source exposes no delete, prune, retire, unlink, or evidence-removal operation based on that state.
