# Gateway 4A. Configure the Software-Only Integrity Journal

This manual adds a second, lightweight path beside the normal MQTT delivery path.

The gateway now has two different jobs:

```text
DELIVERY PATH
"Make sure the uplink can reach the server later."

EVIDENCE PATH
"Keep enough cryptographic history to detect whether the gateway record changed."
```

The completed shape is:

```text
LoRaWAN sensor
      |
      v
   RAK5146
      |
      v
Concentratord
   /       \
  /         \
 v           v
MQTT       Integrity journal
Forwarder       |
  |             +-> gateway-local sequence
  v             +-> raw PHYPayload / source event
Mosquitto       +-> previous-record hash
  |             +-> SHA-256 record chain
  |             +-> segmented journal files
  |             +-> cloud checkpoint / segment upload
  v
mTLS bridge
  |
  v
remote MQTT
```

Mosquitto remains the **availability buffer**. The journal is the **tamper-evidence record**. Do not merge them into one file or claim that `mosquitto.db` becomes immutable.

### Runtime service boundary: writer vs uploader

Treat evidence recording and evidence upload as two separate long-running responsibilities:

```text
Concentratord
     |
     v
gateway-integrity-journal
     |
     v
local crash-safe hash-chained segments
     |
     v
gateway-journal-uploader
     |
     v
HTTPS + mTLS -> cloud evidence ingest
```

The journal writer must continue to record while WAN is unavailable. The uploader may stop/retry without blocking the writer. A reviewed implementation may use one codebase with separate subcommands, but the runtime responsibilities, failure states, and permissions must remain separable.

The full server-side service topology and trust boundaries are documented in [Gateway Integrity Guide 4](../../server/integrations/gateway-integrity/04-service-architecture-and-runtime-contract.md).

> [!IMPORTANT]
> The repository now contains the tested Rust 1.82 writer/uploader runtime: crash-safe hash-chained persistence, age/count segment rotation, durable fsync-backed receipt state, HTTPS/mTLS upload with server-name/CA/client-identity verification, bounded retry/backoff, restart-idempotent receipt handling, and the pinned optional Concentratord ZeroMQ subscriber. The current default gate passes 28 tests total, format, Clippy and locked build. What remains is target-native `concentratord-zmq` compilation in the Gateway OS/OpenWrt toolchain, package/service definitions and installation, and real gateway IPC/RF acceptance. Do not install unrelated Windows compilers to fabricate target acceptance. Local evidence retirement remains deliberately unimplemented.

---

## 1. Security goal and limitation

The journal is designed to expose:

- changed record bytes;
- missing records in the middle of a sequence;
- reordered records;
- broken record or segment chains;
- rollback older than the latest checkpoint already stored by the server;
- disagreement between the gateway journal and the gateway event later received by the remote MQTT broker;
- evidence loss caused by storage exhaustion.

It does **not** make a software-only Raspberry Pi perfectly resistant to a privileged attacker who gains full root access while the gateway is completely disconnected.

Use this accurate claim:

```text
At or before the latest accepted cloud checkpoint
  -> history is anchored outside the Raspberry Pi.

After that checkpoint while fully offline
  -> history is hash-chained and tamper-evident,
     but full root can potentially rebuild the unanchored tail.
```

A TPM, secure element, device-side signature, or independent witness would be needed to reduce that residual threat further.

---

## 2. Place the journal beside Concentratord

The preferred split is:

```text
                  Concentratord
                   /        \
                  /          \
                 v            v
        MQTT Forwarder     Journal service
```

Do **not** build this:

```text
Concentratord -> MQTT Forwarder -> Mosquitto -> journal
```

The earlier split means the evidence path can still expose a change introduced later in MQTT Forwarder or the delivery path.

### Radio ownership rule

Concentratord remains the only process that controls the RAK5146 SPI hardware.

The journal must consume a **supported read-only Concentratord event/IPC interface for the exact pinned Gateway OS release**. It must not open `/dev/spidev*`, reset the radio, or start another packet forwarder.

Current project target, which must be re-proved on the gateway before compiling/installing the final journal:

```text
Gateway OS release:             ChirpStack Gateway OS 4.12.0 Base
Concentratord package/version:   chirpstack-concentratord-sx1302 4.7.1
Concentratord event IPC:         ipc:///tmp/concentratord_event
Gateway EUI:                     0016c001f139a1cb
Region:                          AS923
Journal implementation language: Rust
```

The compatible source contract is now pinned for implementation review:

```text
Concentratord 4.7.1 commit: 0904a8ddf4eeb3150b4675b35f067865cb68827d
Concentratord chirpstack_api: 4.17.0
MQTT Forwarder 4.6.0 commit: 04e870b4af97bebb278ab29259941fd8b3aad72b
MQTT Forwarder chirpstack_api: 4.18.0
gw.proto SHA-256: 227fda5fd77fb115cb00610fb1ea1fa87c3112d972fc6534342dc7083a6dc12b
Correlation contract: concentratord-uplink-correlation-v1
```

The two published API artifacts contain byte-identical `gw.proto`. Concentratord sends `gw.Event` with `uplink_frame`; MQTT Forwarder publishes the contained `gw.UplinkFrame` on `event/up`. The reviewed adapter therefore correlates semantic fields rather than raw Protobuf bytes. Before deployment still record the final journal executable SHA-256 and, once hardware access returns, capture one real paired Concentratord/MQTT uplink and require the same correlation digest. The journal remains an independent read-only subscriber beside MQTT Forwarder; it is not a second packet forwarder.

Stop if the proposed journal needs direct SPI ownership.

---

## 3. Record source evidence before application decoding

Do not make a decoded value such as this the root journal evidence:

```text
temperature = 27.3 C
```

Preserve the gateway-level source instead. Prefer exact source-event bytes when the pinned Concentratord interface exposes a stable serialized representation. At minimum preserve the exact LoRaWAN `PHYPayload` plus the gateway metadata used for later correlation.

A versioned record body should contain fields equivalent to:

```json
{
  "journal_version": "gateway-journal-v1",
  "gateway_id": "<GATEWAY_EUI>",
  "boot_id": "<RANDOM_BOOT_ID>",
  "sequence": 15001,
  "captured_at": "<UTC_RFC3339_TIME>",
  "source": "concentratord",
  "source_event_sha256": "<64_HEX_OR_NULL>",
  "phy_payload_base64": "<EXACT_PHYPAYLOAD>",
  "frequency_hz": 923200000,
  "rssi_dbm": -72,
  "snr_db": 8.5,
  "gateway_context_base64": null,
  "previous_record_hash": "<64_HEX_OR_GENESIS>"
}
```

Use only fields actually available from the pinned source interface. Do not fabricate metadata. For `gateway-journal-v1`, nullable keys must follow one fixed present-with-`null` rule so different implementations hash the same logical record identically.

### Why preserve PHYPayload?

The journal should be able to say:

```text
"These are the LoRaWAN bytes the gateway evidence path observed."
```

The server can later compare those bytes with the independently captured remote gateway MQTT event, then follow the accepted ChirpStack application event and trusted decoder.

---

## 4. Add a gateway-local sequence

Every journaled uplink receives a monotonically increasing sequence:

```text
15001
15002
15003
15004
```

This is **not** the LoRaWAN frame counter. It orders all observations made by this gateway, across all devices.

Requirements:

1. Recover the next sequence from the last valid local record after restart.
2. Never restart at `1` simply because the journal service restarted.
3. Generate a new random `boot_id` for each boot/session.
4. Continue the hash chain across a normal reboot.
5. If continuity cannot be recovered unambiguously, report a journal recovery fault instead of silently creating a new history.

Example:

```text
sequence 18000 | boot A | hash H18000

reboot

sequence 18001 | boot B | previous_record_hash H18000
```

A new boot ID is normal. An unexplained sequence or chain reset is not.

---

## 5. Hash-chain every record

Use a deterministic cross-language serialization rule. The baseline contract is RFC 8785 JSON Canonicalization Scheme for the record body.

```text
record_hash = SHA256(UTF8(RFC8785(record_body)))
```

`record_body` already includes `previous_record_hash`. Store the current hash outside the body:

```json
{
  "record_body": { "...": "..." },
  "record_hash": "<64_LOWERCASE_HEX>"
}
```

Do not include `record_hash` inside the object being hashed.

The resulting chain is:

```text
record 15001 -> H15001
                  |
record 15002 + H15001 -> H15002
                           |
record 15003 + H15002 -> H15003
```

Changing, deleting, or reordering a complete record must break either its own hash, the next record's link, the sequence, or more than one of these checks.

---

## 6. Rotate into bounded journal segments

Do not create one forever-growing log file.

Use a structure equivalent to:

```text
/etc/gateway-integrity/
  journal/
    segment-00000051.closed
    segment-00000052.closed
    segment-00000053.open
  state/
  upload-state/
```

A segment header records:

```text
segment_version
gateway_id
segment_id
first_sequence
previous_segment_hash
created_at
journal_version
```

A closed segment footer records:

```text
last_sequence
record_count
final_record_hash
closed_at
content_sha256
segment_hash
```

The next segment references the previous `segment_hash`. Segment `1` uses exact sentinel `GENESIS`; later segments require the preceding lowercase 64-hex segment hash.

The byte encoding is now frozen by `../../../evidence-services/contracts/gateway-journal-segment-v1/README.md`: every complete line is RFC 8785 JSON followed by one LF byte; `content_sha256` covers the exact pre-footer JSONL bytes; `segment_hash` covers the documented twelve UTF-8 fields joined by single NUL separators with no trailing NUL; `object_sha256` covers the complete closed object including the footer. Do not substitute normal JSON serialization or another delimiter.

---

## 7. Make the open segment crash-safe

A power interruption must not make the journal guess which complete records existed.

Implementation requirements:

- use the frozen canonical JSONL format: exactly one RFC 8785 object plus one LF per complete line;
- append complete record body + hash as one canonical `kind=record` line;
- flush according to a documented durability interval;
- verify the open segment from its beginning at startup;
- automatically discard only an incomplete final/torn record;
- treat a complete record with an invalid hash as an integrity failure;
- never silently renumber a sequence gap.

Record the chosen flush policy:

```text
<JOURNAL_FLUSH_INTERVAL_SECONDS>
```

A shorter interval reduces power-loss exposure but increases flash writes. Test the real SD/storage device rather than copying one universal value.

---

## 8. Give the journal its own finite storage budget

Mosquitto and the journal must not each assume they own all free disk.

Plan three budgets:

```text
Mosquitto queue budget
Journal evidence budget
Gateway OS emergency free-space reserve
```

Estimate journal need:

```text
required journal bytes
  = peak records per hour
  x maximum offline hours
  x measured bytes per record
  x safety factor
```

Use explicit warning levels, for example:

```text
warning   70% of journal budget
critical  85%
emergency 95%
```

The percentages are a starting policy, not measured capacity. Adjust them from real storage and outage tests.

When evidence storage is exhausted, fail visibly. Do not silently overwrite old unuploaded segments and later claim chain continuity. The server must classify affected events as `evidence_gap`.

---

## 9. Run with least privilege

Use a dedicated identity such as:

```text
gateway-integrity
```

It needs only:

```text
READ    supported Concentratord event interface
WRITE   its journal/state directories
CONNECT outbound to evidence upload endpoint
READ    its own upload credential
```

It should not normally be able to:

```text
edit Mosquitto configuration
administer local MQTT
edit MQTT bridge certificates
control RAK5146 SPI
write arbitrary Gateway OS configuration
run an arbitrary shell for packet processing
```

Likewise, ordinary MQTT Forwarder and Mosquitto service identities should not have write access to journal files.

This reduces ordinary service-compromise impact. It does not defeat gateway root.

---

## 10. Anchor the chain off-device while the WAN is healthy

A local hash is not an independent witness if the attacker can rewrite the same disk.

Periodically send a checkpoint equivalent to:

```json
{
  "checkpoint_version": "gateway-checkpoint-v1",
  "gateway_id": "<GATEWAY_EUI>",
  "segment_id": 53,
  "last_sequence": 53000,
  "last_record_hash": "<64_HEX>",
  "segment_hash": "<64_HEX>",
  "created_at": "<UTC_RFC3339_TIME>"
}
```

Send a checkpoint:

- at a fixed healthy-connectivity interval; and
- immediately after closing a segment.

Target transport:

```text
journal uploader
  -> HTTPS + mutual TLS
  -> gateway evidence ingest endpoint
  -> server stores checkpoint append-only
  -> server returns a receipt binding accepted identity/hash + receipt ID + server_received_at
```

The exact endpoint is defined in the server gateway-integrity guides. `evidence-ingest-receipt-v1` provides the complete accepted identity/hash + original server-time receipt; the Rust uploader validates it, persists it canonically with fsync/rename semantics, and skips already-receipted work after restart. The server production raw-storage and ingest path are commissioned. The uploader still **must not retire local evidence after 200/201** because no reviewed evidence-delete/retirement API exists and final physical reconciliation/retention policy remains a gateway acceptance gate.

The server copy is the anchor. A checkpoint stored only on the Pi is not.

---

## 11. Upload closed segments independently of MQTT

Healthy WAN:

```text
MQTT bridge       -> normal gateway events
journal uploader  -> checkpoints + closed segments
```

WAN outage:

```text
Mosquitto queue grows
Journal grows and rotates locally
No false cloud checkpoint is created
```

WAN recovery:

```text
Mosquitto drains queued events
Journal uploader sends missing segments
Server reconciles both paths
```

Do not delete a closed local segment only because an HTTP request returned `200`. The server response must identify the accepted gateway, segment ID, and expected digest/hash before the configured retention policy permits removal.

---

## 12. Optional file and boot hardening

After the baseline journal works, test whether the exact Gateway OS kernel/filesystem supports `fs-verity` for **closed** journal files. It can strengthen detection of changed file content, but privileged deletion is still possible.

A read-only verified root filesystem or Raspberry Pi secure boot can also reduce persistent software replacement. Treat those as separate image-hardening projects. Do not block the first journal deployment on an untested custom boot chain.

---

## 13. Target startup behavior

Use this mental order:

```text
1. persistent storage mounts
2. Concentratord starts and owns the RAK5146
3. journal verifies/reopens its local chain
4. local Mosquitto starts
5. MQTT Forwarder starts
6. WAN comes up
7. Mosquitto bridge reconnects
8. journal uploader resumes checkpoints/segments
```

A journal failure should alert and create an evidence gap, but the default architecture does not stop normal telemetry delivery. Availability and evidence are deliberately separate.

---

## 14. Minimum commissioning and later extended validation

For the **implementation/package gate**, do not wait for physical RF hardware. Feed saved, schema-compatible Concentratord event fixtures through the same journal parsing path. Minimum proof is: one valid fixture creates one monotonic sequence and expected record hash; a short fixture sequence preserves `previous_record_hash`; a small staging threshold proves segment-chain continuity; and process restart does not rewrite already-closed history.

When physical gateway access returns, repeat only the first normal-path check with one real uplink before claiming gateway commissioning. Reboot/WAN/torn-tail/tamper/deletion cases remain **extended Guide 3 / Phase 15 validation**, not mandatory setup ceremony.

### Test A - one fixture now / one real uplink later

Pass when:

- the saved Concentratord fixture, or later the corresponding real gateway event, is accepted through the pinned event contract;
- exactly one new gateway journal sequence appears;
- the journal contains the expected Gateway EUI and raw PHYPayload/source evidence;
- recomputing the record hash matches the stored hash.

### Test B - short chain continuity

Use a short saved fixture sequence during package validation; when hardware is available, a few real uplinks are sufficient.

Pass when every record's `previous_record_hash` equals the preceding recomputed record hash.

### Test C - segment rotation

Use a deliberately small staging segment threshold.

Pass when:

- the old segment closes;
- its footer is complete;
- the new segment references the previous segment hash;
- normal operation never modifies the closed segment.

### Extended Test D - clean reboot

Generate records, reboot, then generate more.

Pass when:

- sequence continues;
- boot ID changes;
- the first post-reboot record references the last pre-reboot hash.

### Extended Test E - torn-tail recovery

In staging, interrupt the journal while the current segment is being written.

Pass when startup removes only an incomplete final record. A previously complete invalid record must stop normal evidence continuity and raise an error.

### Extended Test F - WAN outage

Disconnect only WAN/backhaul.

Pass when:

- Mosquitto queue grows;
- journal continues locally;
- closed segments remain stored;
- the server checkpoint does not falsely advance.

### Extended Test G - WAN recovery

Restore connectivity.

Pass when:

- Mosquitto drains;
- missing segments upload;
- a new checkpoint extends the latest server anchor;
- server verification reports continuity.

### Extended Test H - tamper a copy

Copy one closed staging segment and alter one byte in the copy only.

Pass when the server verifier rejects the modified copy.

### Extended Test I - deleted-record fixture

Use an isolated copied fixture with one record removed.

Pass when sequence/hash verification reports the gap and does not rebuild or renumber it.

---

## 15. Completion checklist

- [ ] Concentratord remains the sole RAK5146 owner.
- [ ] MQTT delivery still uses local Mosquitto at QoS 1.
- [ ] Journal consumes a supported read-only Concentratord interface independently of MQTT Forwarder.
- [ ] Every recorded uplink gets one gateway sequence and deterministic record hash.
- [ ] Record and segment hash chains verify.
- [ ] Reboot recovery preserves sequence/hash continuity.
- [ ] Journal storage is finite and separate from the OS reserve.
- [ ] Checkpoints are stored off-device during healthy connectivity.
- [ ] Closed segments upload through authenticated encrypted transport.
- [ ] Evidence overflow creates a visible gap instead of silent overwrite.
- [ ] Operators understand the full-root/offline residual risk.

## Next step

Continue with [05-configure-mqtt-forwarder.md](05-configure-mqtt-forwarder.md), then prove both paths in [06-verify-gateway-os.md](06-verify-gateway-os.md).


## Implemented Gateway OS package state - 2026-09-01

The journal is implemented in the accepted Gateway OS image as `gateway-evidence 0.1.0-r2`. Both ARM executables and procd services are present. The writer is enabled with an `S99` boot link; the uploader has no boot link and UCI `enabled '0'`. Journal state is `/etc/gateway-evidence/journal`, receipts are `/etc/gateway-evidence/receipts`, and the configured gateway EUI is `0016c001f139a1cb`.

The uploader's `enable` action is guarded during package/image construction (`IPKG_INSTROOT`) and only creates runtime rc.d links when its UCI section is explicitly enabled. The factory image leaves `ingest_url` blank and contains no files under the evidence TLS paths. Provision the CA/client certificate/key separately before enabling upload.

Independent factory-SquashFS inspection confirmed the binaries, dedicated users/groups, boot defaults, persistent paths, and absence of embedded evidence TLS material. Real Concentratord IPC capture and a real accepted upload receipt remain post-flash commissioning checks, not image-build blockers.
