# I2 — Post-storage integrity: offline code qualification

## Current live-schema qualification — 2026-09-21 (supersedes hardware-offline assumption below)

Gateway-01 and EMU-01 are presently connected, but genuine Fabric-confirmed EMU-01 rows use `telemetry-attestation-v2` (independently verified from R2 live outbox evidence). The v1-only Go source recomputation and Python scorer in this file are **valid CODE_ONLY synthetic contracts, not live-v2 I2 measurement tools**. Current v2 requires verified gateway lineage in `BuildEvidence`; the HRC anchor digest is calculated from immutable `finalized_payload` bytes, not a newly recomputed canonical JSON string. The precise, non-destructive upgrade and rollback requirements are in `test/automation/research-manual/I2-LIVE-READINESS-20260921.md`. Do not mutate live production telemetry using these v1 commands or assert a v1 synthetic PASS is an actual I2 trial. Added explicit v2 fail-closed regression to the I2 unit suite (26/26 CODE_ONLY_PASS). The original historical v1 design below is retained for comparison, not as current publication guidance.

## Scope

User's gateway and sensors are offline. I2's 10 unchanged controls and 10 post-storage tamper trials can be **code-only rehearsed with synthetic EMU-01 readings**, but no synthetic sample may be counted in Chapter 4. I2 tests *post-commit change detection*: the original immutable Fabric seal must be obtained and independently queried before any selected database-row mutation. After changing only `temperature_c` by +10 Cel in a dedicated row, recompute the current SOURCE evidence using **the production v1 fabricadapter BuildEvidence + CanonicalizeEvidence**, compare it to the original Fabric anchor, restore that exact row and independently verify restoration. Never hash arbitrary PostgreSQL JSON as a substitute for the production RFC 8785 canonical evidence. I1's temporary Node-RED hash is unrelated.

## One-command code-only test

From `lorawan-network-server-gateway` root:

```powershell
py -3 test/automation/offline_test.py I2
```

The isolated I2 suite tests the frozen v1 digest against the Go production startup vector, 10+10 synthetic condition shape, exact source snapshot SHA-256 joins, changed-temperature and unchanged-other-field requirements, signed sealed outbox / Fabric before-and-after references, rejected missing evidence and deliberate restoration failures. Full project code-only suite: `py -3 test/automation/run_offline_qualification.py`.

### New read-only production-reuse companion

Source: `evidence-services/cloud/cmd/research-i2-current-source/main.go`. The command takes a JSON **read-only source/outbox SQL snapshot file**, invokes the actual Fabric adapter's `SelfTest`, `BuildEvidence`, and `CanonicalizeEvidence` functions, and writes the current-source exact canonical JSON string plus SHA-256. It has **no database driver, Fabric Gateway client, OpenBao client, signing, or mutation methods**. The supplied snapshot must carry `source_query_ref`, `outbox_query_ref`, `event_key`, `source_event_key`, `schema_version=telemetry-attestation-v1`, `event_type=lorawan_uplink_accepted`, `observed_at`, and a `source` object with `received_at`, nullable application/device/model/decoder/gateway/region, `dev_eui`, `f_port`, `f_cnt`, `confirmed`, `raw_data_base64`, `payload_json` and actual convenience-column `temperature_c`. It refuses snapshots whose selected `temperature_c` column disagrees with the decoded payload's `temperature_c`. The chosen immutable outbox identity and observed timestamp are taken from their read-only snapshot, not manufactured at comparison time.

Go 1.25.0 was installed **outside the repository** at `%LOCALAPPDATA%\\lorawan-toolchains\\go1.25.0\\go\\bin\\go.exe`. The read-only helper passed **5/5 direct Go unit tests**; the production adapter's frozen v1 canonicalization and null/time builder tests passed, and the P2 Go command compiled. The Python-to-real-Go baseline/tampered/restored cross-language integration passed **three phases**. From `evidence-services/cloud`, using this toolchain on this workstation:

```powershell
& "$env:LOCALAPPDATA\\lorawan-toolchains\\go1.25.0\\go\\bin\\go.exe" test ./cmd/research-i2-current-source
& "$env:LOCALAPPDATA\\lorawan-toolchains\\go1.25.0\\go\\bin\\go.exe" run ./cmd/research-i2-current-source --input "<read-only-snapshot.json>" --output "<different-recomputed.json>"
```

Cross-language synthetic check from repo root: `py -3 test/automation/integrity/test_i2_go_integration.py --go "$env:LOCALAPPDATA\\lorawan-toolchains\\go1.25.0\\go\\bin\\go.exe"`.

The output `qualification=READ_ONLY_SNAPSHOT_RECOMPUTE_NOT_LIVE_ATTESTATION` and `counted_research=false`. A local file snapshot is NOT proof it represents the true current database state: independent query logs/source-of-truth and the extraction procedure require live review.

### Independent I2 evidence scorer

`test/automation/integrity/i2_evidence.py` accepts the original sealed canonical JSON/hash, signature/key references and confirmed outbox/Fabric TxID; independently referenced pre/post Fabric ledger state; each phase's exact source-snapshot input bytes paired with the Go helper output and its SHA-256; the sealed outbox post readback; and a restored current-source recomputation. The source event ID and event_key are distinct and preserved. It verifies 1-10 trial pairs offline, exactly 10 unchanged and 10 tampered when marked formal, and unique source identities/sequences. The synthetic fixtures use the adapter's literal frozen v1 startup vector as a trusted cross-check before changing simple test scalar fields; they are **not evidence of a live canonicalization run**.

- `INVALID`: missing/mismatched source snapshots or read-only query refs; before-state not a confirmed original seal; tamper did not modify only selected `temperature_c` by +10 Cel; unsupported evidence schema; inconsistent origin/digest.
- `FAIL`: a structurally valid changed source hashes equal the original (undetected tamper), an unchanged source differs, restored current source does not match original, a sealed outbox or Fabric anchor is independently proven changed, or unexpected Fabric commits occur.
- `PASS`: original and unchanged source match; tampered current-source canonical digest differs while original Fabric/outbox remains unchanged; restored source matches the original, with references for each observation.

The scorer does **not** verify Fabric signatures or independently dereference its input's query references; it **always** reports `counted_research=false` even for a supplied formal export.

```powershell
py -3 test/automation/integrity/i2_evidence.py --evidence "<i2-evidence.json>" --output "<separate-validation.json>"
```

## Live release gates — outstanding

This section is not a production mutation command. Before a counted operator command is released: inspect current schema, choose 10 reserved EMU-01 records with original confirmed Fabric evidence, save a verified DB backup and per-row restore copies, restrict a temporary SQL role to the selected rows, prove read-only production v1 recomputation matches baseline, freeze exact source IDs/manifest hashes, rehearse one control and one tamper with immediate restoration and independent Fabric/outbox queries, run 10+10 formal trials, restore all rows and remove/revoke the role. Do not alter immutable outbox data or resubmit to Fabric to make a mismatched source pass. Keep `run_test.py I2` as `HARNESS_REQUIRED` until live commissioning passes.

**Next hardware-offline code-only test:** I3 10 baseline + 10 same-hash duplicate + 10 conflicting-hash overwrite ledger checks.
