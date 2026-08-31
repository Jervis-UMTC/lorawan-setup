# verifier-runtime-v1

This contract defines the current `gateway-evidence-verifier` source boundary. It implements durable v2 discovery, HA worker leasing, deterministic application/trusted-decoder validation, deterministic application-to-MQTT reception correlation, exact raw MQTT object re-verification, exact closed-journal object verification through the matching segment, and accepted-checkpoint validation. It deliberately **does not** implement any SQL path that writes `status='verified'`.

## Discovery authority

Only the verifier creates verification work. It scans durable `telemetry.fabric_outbox` rows whose schema is exactly `telemetry-attestation-v2` and idempotently ensures one:

```text
gateway_evidence.event_verification(source_event_key, observed_at)
```

row exists. Inserts rely on the database default `status='pending'` and `ON CONFLICT (source_event_key, observed_at) DO NOTHING`. Node-RED and the Fabric adapter do not create verifier authority rows.

## HA claim contract

Both verifier replicas use the same PostgreSQL queue:

```text
status = pending
next_attempt_at <= now()
lease missing/expired
FOR UPDATE SKIP LOCKED
worker_id + lease_expires_at + attempts
```

The short claim transaction commits before application reads, object-store reads, decoding, or correlation. A stale worker may update/release work only while `status='pending' AND worker_id=<its own id>`; otherwise it receives a lease-lost error.

## Application-side deterministic stage

For one claimed source identity the verifier requires exactly one v2 outbox/uplink source row, strict-decodes `telemetry.uplinks.raw_data` as Base64 application bytes, runs the pinned trusted decoder, and compares the expected 13 normalized metrics against `telemetry.measurements`.

The approved operational mapper identity remains:

```text
agriculture-kit-payload-v2-node-red-v1
```

The trusted decoder identity is separate:

```text
decoder_id      = emu01-agriculture-kit-payload-v2
decoder_version = trusted-decoder-go-v1
```

Numeric comparisons use a tiny floating-point tolerance only after metric name/unit/source-field/quality/type have matched exactly. Boolean values and null/invalid semantics match exactly.

For v2 correlation, the application row also preserves the same first ChirpStack reception already used for `gateway_id`, RSSI, and SNR:

```text
gateway_id
gateway_uplink_id
gateway_frequency_hz
gateway_context_base64
rssi_dbm
snr_db
```

These fields come from `integration.UplinkEvent.rxInfo[0]` plus `txInfo.frequency`; ChirpStack 4.18 preserves the original `gw.UplinkRxInfo.uplink_id`. Missing provenance remains `pending`; malformed present provenance fails closed. Timestamp-only matching is prohibited.

## MQTT witness verification

The PostgreSQL lookup uses the deterministic reception tuple rather than a time window:

```text
gateway_id + uplink_id + frequency_hz + gateway_context_base64
```

The stored row is only an index. Before accepting it, the verifier reopens the immutable MQTT object, recomputes the object SHA-256 and `mqtt-capture-v1` capture key, validates the exact gateway `event/up` topic, decodes the raw bytes again with the pinned `gw.UplinkFrame` parser, and recomputes `concentratord-uplink-correlation-v1`.

The decoded Gateway EUI, uplink ID, PHYPayload digest, frequency, RSSI, SNR, gateway context, and semantic correlation digest must agree with the stored witness and the application reception provenance. Zero candidates remain pending; multiple deterministic candidates or conflicting immutable content fail closed.

## Journal object and checkpoint verification

For the MQTT semantic correlation digest, the verifier searches only the indexed closed segments for the same Gateway EUI. A textual digest occurrence is a prefilter, never proof.

The candidate segment must pass the complete `gateway-journal-segment-v1` contract from its raw object bytes:

```text
exact object SHA-256 and store metadata
strict canonical JSONL
header/version/Gateway-EUI validation
record canonical bytes + record_hash recomputation
contiguous sequence
previous_record_hash chain
content_sha256 recomputation
segment_hash recomputation
footer/record-set agreement
metadata-to-object equality
```

For a record in segment N, the verifier then reopens and fully verifies **every segment object 1..N**, not only their PostgreSQL rows. Cross-segment checks require:

```text
segment 1: first_sequence=1 and GENESIS segment/record predecessor
segment N>1: previous_segment_hash = verified segment N-1 segment_hash
segment N>1: first_sequence = verified segment N-1 last_sequence + 1
segment N>1 first record previous_record_hash = verified segment N-1 final_record_hash
```

The matched record must contain the exact MQTT `source_event_sha256` and independently match Gateway EUI, PHYPayload, frequency, RSSI, SNR, and gateway-context bytes.

The accepted checkpoint is loaded for the matched segment's final sequence. Its version, Gateway EUI, segment ID, final sequence, final record hash, and segment hash must equal the independently verified segment. The verifier also recomputes the frozen `gateway-checkpoint-v1` NUL-separated digest from the stored gateway-created timestamp and requires exact `checkpoint_digest` equality.

Missing still-arriving segment/checkpoint evidence remains pending. Ambiguous or conflicting immutable evidence fails closed.

## Verifier-owned verified transition

This source version contains the explicit `CompleteVerified` authority path. It is not a generic status setter: the worker invokes it only after application provenance, MQTT witness, complete journal-object lineage, checkpoint recomputation, trusted decoding, and stored telemetry comparison all succeed.

The PostgreSQL update persists the complete lineage projection and writes `status='verified'` in the same operation only when the target row is still `pending`, still owned by the same verifier worker, and its lease remains valid. It clears the lease and records `verified_at`; lease loss prevents a stale worker from authoring the terminal state. The database verified-row invariant below remains mandatory.

This closes the **source authority** blocker without fabricating live evidence. A real `verified` acceptance claim still requires:

```text
production replicated raw-object backend
live reviewed migration + verifier identity/least-privilege credentials
two commissioned verifier replicas
reviewed live Node-RED provenance schema/flow
one real Concentratord 4.7.1 + MQTT Forwarder 4.6.0 paired gateway event
one full physical-gateway reconciliation through the commissioned services
```

Until those deployment/hardware gates pass, source/build tests may prove the transition logic but must not be reported as a real verified gateway event.

## Database verified-row invariant

The migration requires any future `status='verified'` row to contain:

```text
gateway_id
journal_segment_id
journal_sequence
journal_record_hash
journal_segment_hash
checkpoint_id
gateway_event_id
decoder_id
decoder_version
raw_app_data_sha256
normalized_digest_sha256
verified_at
```

A verified row cannot carry `reason_code`; non-verified terminal states require one and cannot carry `verified_at`.

## Build identity and readiness

`trusteddecoder.PackageDigest` is the SHA-256 of a canonical manifest containing the sorted production trusted-decoder Go source filenames and each file's SHA-256. The reproducible build computes this identity **before** linking and injects it into the verifier with Go `-ldflags -X`. The verifier binary and OCI image retain their own separate artifact digests, so decoder identity has no circular self-hash dependency. Production verifier startup rejects an unset or malformed decoder digest and executes the frozen trusted-decoder fixture before entering the work loop.

Verifier readiness also requires both PostgreSQL and the configured evidence object store to be readable. The filesystem backend is guarded development/smoke only; production uses the reviewed S3-compatible backend and still requires a commissioned durable provider whose failure domain survives one Droplet loss.
