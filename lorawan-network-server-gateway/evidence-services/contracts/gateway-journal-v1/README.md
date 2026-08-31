# gateway-journal-v1

This contract freezes the **logical gateway observation record** and the exact bytes used for its record hash. The commissioned Concentratord uplink adapter is now separately frozen by `concentratord-uplink-correlation-v1`: its exact upstream commits, `gw.proto` bytes/tags, semantic cross-path digest, and Rust decoder are pinned. A real captured gateway fixture is still required before physical capture acceptance is claimed.

## Record body

Every `gateway-journal-v1` record body contains exactly these keys. Nullable keys are always present and use JSON `null` when unavailable.

```json
{
  "journal_version": "gateway-journal-v1",
  "gateway_id": "0016c001f139a1cb",
  "boot_id": "boot-fixture-1",
  "sequence": 1,
  "captured_at": "2000-01-01T00:00:01.000Z",
  "source": "concentratord",
  "source_event_sha256": null,
  "phy_payload_base64": "AQI=",
  "frequency_hz": 923200000,
  "rssi_dbm": -72,
  "snr_db": 8.5,
  "gateway_context_base64": null,
  "previous_record_hash": "GENESIS"
}
```

Rules:

- `gateway_id` is canonical lowercase 16-hex.
- `sequence` is the gateway-local monotonic journal sequence, not LoRaWAN FCnt. The Rust implementation starts at `1` and never silently resets or renumbers it.
- `captured_at` is UTC RFC 3339 with exactly millisecond precision.
- `source` is exactly `concentratord` for this version.
- `phy_payload_base64` is canonical RFC 4648 Base64 and must decode to non-empty exact PHYPayload bytes.
- `source_event_sha256`, when present for the commissioned uplink adapter, is the lowercase 64-hex `concentratord-uplink-correlation-v1` semantic digest. It is deliberately **not** the SHA-256 of raw ZeroMQ `gw.Event` bytes because MQTT Forwarder unwraps and re-encodes the contained `gw.UplinkFrame`.
- `gateway_context_base64`, when present, is canonical RFC 4648 Base64 of `gw.UplinkRxInfo.context` from the pinned schema. It is `null` when that bytes field is empty.
- `previous_record_hash` is either the exact literal `GENESIS` for the first record in a new journal lineage or the preceding record's lowercase 64-hex hash.

## Hash bytes

The record hash is:

```text
record_hash = lowercase_hex(
  SHA256(
    UTF8(RFC8785(record_body))
  )
)
```

`record_hash` is outside `record_body` and is therefore not part of its own preimage.

The wrapper representation used by the segment contract is:

```json
{
  "record_body": { "...": "..." },
  "record_hash": "<64 lowercase hex>"
}
```

## Fixed independent vector

For the record body shown above, the exact RFC 8785 UTF-8 text is:

```text
{"boot_id":"boot-fixture-1","captured_at":"2000-01-01T00:00:01.000Z","frequency_hz":923200000,"gateway_context_base64":null,"gateway_id":"0016c001f139a1cb","journal_version":"gateway-journal-v1","phy_payload_base64":"AQI=","previous_record_hash":"GENESIS","rssi_dbm":-72,"sequence":1,"snr_db":8.5,"source":"concentratord","source_event_sha256":null}
```

Expected SHA-256:

```text
443014973b6eab5a01b75f9715470cffdabb05318ac19620c60c5b20fe0e4823
```

This vector was reproduced independently with Node.js by hashing the explicit canonical UTF-8 string, not by calling the Rust implementation. It intentionally keeps `source_event_sha256` and `gateway_context_base64` null so the original record/segment regression vectors remain stable; adapter-specific vectors live in `concentratord-uplink-correlation-v1`.

## Trust boundary

This contract proves deterministic journal bytes after an observation has been converted into the typed record fields. `concentratord-uplink-correlation-v1` now proves the exact pinned `gw.Event`/`gw.UplinkFrame` field projection with a synthetic independent wire vector and compiled Rust tests. It still does **not** prove physical gateway capture. Final acceptance requires one real `ipc:///tmp/concentratord_event` uplink from the commissioned Concentratord 4.7.1 runtime and the corresponding MQTT `event/up` payload to produce the same semantic correlation digest through the reviewed implementation.
