# 1. Evidence Contract and Cloud Checkpoints

This guide freezes the logical evidence contract. Implementations may use different languages, but they must not silently change the bytes or matching rules while keeping the same version identifier.

## 1.1 Keep three evidence stages separate

```text
Gateway journal record
  "what the gateway evidence path recorded"

Remote gateway MQTT event
  "what the delivery path delivered to the server"

ChirpStack application event
  "what the Network Server accepted and exposed to the application"
```

A strong result links all three. It does not pretend they are the same serialization.

## 1.2 Gateway journal record

Version:

```text
gateway-journal-v1
```

Record body equivalent to:

```json
{
  "journal_version": "gateway-journal-v1",
  "gateway_id": "0000000000000001",
  "boot_id": "<RANDOM_BOOT_ID>",
  "sequence": 15001,
  "captured_at": "2000-01-01T00:00:00.000Z",
  "source": "concentratord",
  "source_event_sha256": null,
  "phy_payload_base64": "AQI=",
  "frequency_hz": 923200000,
  "rssi_dbm": -72,
  "snr_db": 8.5,
  "gateway_context_base64": null,
  "previous_record_hash": "<64_HEX_OR_GENESIS>"
}
```

Hash rule:

```text
record_hash = SHA256(UTF8(RFC8785(record_body)))
```

The wrapper stores the body and current hash separately. Nullable keys follow one fixed present-with-`null` rule for this version.

## 1.3 What this proves

A valid uploaded chain proves internal consistency with the earlier accepted checkpoint and with the bytes supplied for verification.

It does not prove:

- physical sensor calibration;
- that a person did not spoof the physical sensor;
- sensor-origin authenticity for gateway-generated RSSI/SNR;
- uniqueness of an unanchored offline tail against a full-root attacker who controls the entire Raspberry Pi while disconnected.

## 1.4 Segment contract

Version:

```text
gateway-journal-segment-v1
```

Required header:

```text
segment_version
gateway_id
segment_id
first_sequence
previous_segment_hash
created_at
journal_version
```

Required footer:

```text
last_sequence
record_count
final_record_hash
closed_at
segment_hash
```

Every record hash and previous-record link must verify. The next segment must reference the preceding segment hash.

Freeze the exact segment-hash byte encoding in the implementation specification. A format version cannot depend on implementation-specific object ordering or ambiguous concatenation.

## 1.5 Checkpoint contract

Version:

```text
gateway-checkpoint-v1
```

Example:

```json
{
  "checkpoint_version": "gateway-checkpoint-v1",
  "gateway_id": "0000000000000001",
  "segment_id": 53,
  "last_sequence": 53000,
  "last_record_hash": "<64_HEX>",
  "segment_hash": "<64_HEX>",
  "created_at": "2000-01-01T00:10:00.000Z"
}
```

The server adds receipt metadata:

```text
checkpoint_receipt_id
server_received_at
client_identity
request/correlation ID
checkpoint_digest
```

Preserve gateway time and server receipt time separately.

## 1.6 Why the checkpoint is the off-device anchor

Example:

```text
server already accepted:
sequence 5000
hash ABC123

WAN goes down

gateway creates:
5001 -> 5002 -> ... -> 5900
```

After recovery, the uploaded chain must extend `ABC123`.

The gateway cannot rewrite history before sequence 5000 without contradicting evidence already stored off-device.

The remaining software-only risk begins after the last accepted anchor.

## 1.7 Checkpoint acceptance rules

Reject:

- unknown/disabled gateway identity;
- unsupported version;
- malformed hash or Gateway EUI;
- sequence or segment regression relative to accepted history, except through an explicit incident-recovery procedure;
- the same `(gateway_id,last_sequence)` with a different hash;
- an oversized request or unexpected content type.

Exact duplicate retry with the same identity and hashes may be idempotent.

Same identity + different digest is a **security conflict**.

## 1.8 Capture remote gateway MQTT evidence independently

Run a dedicated server identity that subscribes read-only to approved gateway event topics before ChirpStack application processing:

```text
<REGION_TOPIC_PREFIX>/gateway/+/event/#
```

It must not have permission to publish gateway `event` topics.

For each uplink preserve:

```text
broker receipt time
MQTT topic
gateway ID
exact serialized gateway event bytes when practical
serialized-event SHA-256
PHYPayload bytes or SHA-256
available uplink identifier/context
frequency / RSSI / SNR used for matching
collector version
```

This copy is independent of Node-RED and the ChirpStack application integration.

## 1.9 Stage A: journal vs remote gateway MQTT

Compare:

```text
journal record
      VS
captured remote gateway event
```

Prefer exact serialized-source digest when both sides intentionally preserve the same representation. Otherwise compare the exact PHYPayload plus the approved gateway/context fields required by the pinned matching contract.

Outcomes:

```text
one exact match       -> continue
no match yet          -> pending
no match after expiry -> evidence_gap
conflicting payload   -> integrity_failure
multiple candidates   -> ambiguous; never guess
```

## 1.10 Stage B: gateway event vs ChirpStack application event

Then link:

```text
verified gateway event
  -> ChirpStack processing
  -> application uplink event
```

Prefer a direct documented correlation identifier from the exact pinned ChirpStack release.

If unavailable, use a reviewed composite using fields that survive processing, for example:

```text
gateway ID
DevAddr/session identity
frame counter
FPort
bounded event-time window
radio/context metadata when needed
```

Never match on timestamp alone. The result must be unique.

## 1.11 Stage C: trusted decoding vs Node-RED storage

For evidence-selected events, run a pinned decoder **outside Node-RED** against the accepted raw ChirpStack application `data` bytes.

Preserve:

```text
decoder ID
decoder version/code hash
raw application-data SHA-256
trusted normalized result
trusted normalized-result SHA-256
```

Then compare the approved normalized fields with TimescaleDB.

Example:

```text
trusted decoder = 27.3 C
TimescaleDB     = 80.0 C

result = integrity_failure
```

This makes Node-RED a processor, not the sole authority for values that later reach Fabric.

## 1.12 Verification states

| State | Meaning |
|---|---|
| `pending` | Waiting for a required segment, MQTT counterpart, application event, or trusted decode |
| `verified` | Required chain, anchor continuity, delivery match, network lineage, and trusted decode checks passed |
| `evidence_gap` | Required evidence is missing/unavailable/ambiguous, but contradictory bytes were not proven |
| `integrity_failure` | Hash conflict, rollback conflict, payload mismatch, broken chain, or trusted decode/storage mismatch |
| `not_required` | Policy does not require gateway evidence for this event |

Do not collapse `evidence_gap` into `integrity_failure`. Missing proof and contradictory proof require different response.

## 1.13 Fabric schema versioning

Do not silently change historical `telemetry-attestation-v1`.

Use a new journal-aware contract:

```text
telemetry-attestation-v2
```

`v2` adds compact gateway-verification references/hashes to the canonical evidence. Full journal segments remain off-chain.

Next: [02-server-verifier-and-reconciliation.md](02-server-verifier-and-reconciliation.md)
