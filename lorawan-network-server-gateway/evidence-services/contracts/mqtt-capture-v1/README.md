# mqtt-capture-v1

`capture_key_sha256` is the deterministic logical identity used to collapse the same remote MQTT gateway event observed by multiple evidence-collector replicas.

## Exact byte construction

For MQTT topic UTF-8 bytes `T` and exact serialized MQTT payload bytes `P`, construct:

```text
ASCII("mqtt-capture-v1")
0x00
uint32_be(len(T))
T
uint64_be(len(P))
P
```

Then:

```text
capture_key_sha256 = lowercase_hex(SHA256(exact_bytes_above))
```

Rules:

- topic is encoded as UTF-8 exactly once;
- payload bytes are used exactly as received, with no JSON parse/re-serialization;
- topic must be non-empty and fit in unsigned 32-bit length;
- payload must be non-empty;
- lengths are unsigned big-endian byte counts, not character counts;
- there is no delimiter ambiguity because both variable fields are length-prefixed;
- duplicate observations with the same topic and payload produce the same key on every replica;
- the database uniqueness constraint on `capture_key_sha256` provides the durable convergence boundary.

Fixed vector:

```text
topic UTF-8:
  as923/gateway/0016c001f139a1cb/event/up

payload UTF-8 bytes:
  {"phyPayload":"AQI="}

capture_key_sha256:
  de1a848838d6d27e02261e0cc37d3478e70dfd5e0e1d381927349dfe803ead74
```

The expected digest was independently constructed from the byte contract using a separate PowerShell SHA-256 calculation. The Go implementation and regression test live in `cloud/internal/mqttcapture/`.
