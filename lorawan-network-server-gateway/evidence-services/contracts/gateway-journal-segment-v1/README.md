# gateway-journal-segment-v1

This contract freezes the exact closed-segment byte format and all segment hashes for gateway journal evidence.

## Exact file format

A segment is UTF-8 JSON Lines. Every complete line is:

```text
RFC8785(object) + single LF byte 0x0a
```

No CRLF, blank line, whitespace padding, alternate key order, or non-canonical JSON representation is accepted.

The line order is exactly:

```text
1 x header
1..N x record
1 x footer                 # closed segment only
```

An open segment has no footer. Startup recovery may discard only bytes after the last complete LF when the final line is torn. Every already-complete line must still parse, be canonical, and pass its hash/sequence checks. A complete invalid record is an integrity failure, not normal crash cleanup.

## Header

```json
{
  "segment_version": "gateway-journal-segment-v1",
  "gateway_id": "0016c001f139a1cb",
  "segment_id": 1,
  "first_sequence": 1,
  "previous_segment_hash": "GENESIS",
  "created_at": "2000-01-01T00:00:00.000Z",
  "journal_version": "gateway-journal-v1"
}
```

`previous_segment_hash` is exactly `GENESIS` only for the first accepted segment lineage; otherwise it is the previous segment's lowercase 64-hex `segment_hash`.

## Record lines

Each record line has this logical shape:

```json
{
  "kind": "record",
  "record_body": { "...gateway-journal-v1...": "..." },
  "record_hash": "<64 lowercase hex>"
}
```

The record body and record hash follow `../gateway-journal-v1/README.md`. Record sequences must be contiguous and each `previous_record_hash` must equal the preceding recomputed record hash.

## Footer and hash layers

Before the footer is appended, calculate:

```text
content_sha256 = SHA256(exact header-LF + exact record-LF bytes)
```

The segment hash preimage is the following UTF-8 fields separated by a single NUL byte (`0x00`), with **no trailing NUL**:

```text
segment_version
NUL gateway_id
NUL base10(segment_id)
NUL base10(first_sequence)
NUL previous_segment_hash
NUL created_at
NUL journal_version
NUL base10(last_sequence)
NUL base10(record_count)
NUL final_record_hash
NUL closed_at
NUL content_sha256
```

Then:

```text
segment_hash = lowercase_hex(SHA256(segment_hash_preimage))
```

The canonical footer contains:

```json
{
  "last_sequence": 2,
  "record_count": 2,
  "final_record_hash": "<record-2 hash>",
  "closed_at": "2000-01-01T00:00:03.000Z",
  "content_sha256": "<pre-footer exact-byte digest>",
  "segment_hash": "<semantic segment digest>"
}
```

After appending `RFC8785(footer-line-object) + LF`, calculate:

```text
object_sha256 = lowercase_hex(SHA256(exact complete closed-segment bytes))
```

The three layers have different purposes:

```text
record_hash     -> canonical observation + record-chain integrity
content_sha256  -> exact pre-footer JSONL bytes
segment_hash    -> segment identity/lineage/footer semantics + content digest
object_sha256   -> exact complete uploaded object, including footer
```

## Fixed two-record vector

Fixture identity:

```text
gateway_id            0016c001f139a1cb
segment_id            1
first_sequence         1
previous_segment_hash GENESIS
created_at             2000-01-01T00:00:00.000Z
record 1 captured_at   2000-01-01T00:00:01.000Z
record 2 captured_at   2000-01-01T00:00:02.000Z
closed_at              2000-01-01T00:00:03.000Z
PHYPayload Base64      AQI=
frequency_hz           923200000
rssi_dbm               -72
snr_db                 8.5
```

Expected hashes:

```text
record_1_sha256 = 443014973b6eab5a01b75f9715470cffdabb05318ac19620c60c5b20fe0e4823
record_2_sha256 = 0fbfe1314ab5a7c779ff4872048a02dffa77b2c9c97826f1a62bedf6a070297f
content_sha256  = 48f043a5b36df29eeac3848331aac65258a3c31866667982341386f306e67d4e
segment_sha256  = 722638f91ff762185aff7c002044911226661c0efc8b70ce71b22a7f168bae90
object_sha256   = 9f34ad301bc0b1b806e2cb0c39a4baaa7509e79b8822f7f367a08720835403f1
```

These values were independently reproduced with Node.js from explicitly constructed canonical JSONL strings and the documented NUL-separated segment preimage. The Rust tests must match all five values exactly.

## Upload boundary

`object_sha256` is the digest of the bytes sent as `object_base64` to evidence ingest. The server must preserve those exact decoded bytes in the durable raw evidence store before accepting metadata. Local gateway retention must not be retired merely because an HTTP request returned 200/201; a separately frozen server receipt/acknowledgement contract is required before destructive local cleanup is enabled.
