# I3 — Fabric duplicate and conflicting-overwrite integrity: offline qualification

## Scope / result interpretation

This I3 implementation is an **offline-only supplied-evidence scorer** for HRC `CreateSourceBoundAnchor`, `QuerySourceBoundAnchor`, and exact SHA-256 payloads. Its synthetic fixture uses mock EMU-01 temperature records and a dedicated `i3-synthetic:` source-record namespace. It does **not** submit any transaction, query a live Fabric peer, alter the LoRaWAN PostgreSQL database or touch the user's gateway/sensors. All results have `counted_research=false`; claims about actual Fabric commits require independent HRC evidence provenance and commissioning.

Research methodology: 10 baseline anchor creations, then 10 same-exact-payload attempts on those ten keys, then 10 deliberately conflicting-exact-payload attempts on those SAME keys. Report **10 baseline fixtures separately from 20 mutation attempts**. Do not relabel 30 synthetic fixtures as collected research samples.

## Streamlined I3-only command

From `lorawan-network-server-gateway` repository root:

```powershell
py -3 test/automation/offline_test.py I3
```

This runs the frozen research contract plus the standalone I3 scorer regressions. The consolidated code-only runner is `py -3 test/automation/run_offline_qualification.py`. The I3 scorer is `test/automation/integrity/i3_ledger_evidence.py` and its regression tests are `test/automation/integrity/test_i3_ledger_evidence.py`.

To validate a **supplied** evidence export without modifying the input file:

```powershell
py -3 test/automation/integrity/i3_ledger_evidence.py --evidence "<i3-fabric-export.json>" --output "<separate-i3-validation.json>"
```

This is a reviewer aid, not a live test launcher. Reference strings alone are not proof that ledger data is authentic; externally inspect signed/sealed Fabric exports and read-only query/commit traces.

## Fabric-side handoff contract

Use the shared `test/FABRIC-SYNCHRONIZED-TEST-CONTRACT.md`: the same sealed run and record manifest hashes, exact `source_record_id` and payload bytes, and `authenticated_source_system_id=lorawan-gateway-evidence` across the LoRaWAN and HRC actors. Required top-level keys: `test_id=I3`, `run_id`, `formal`, `attempts_per_phase`, `fixture_namespace=i3-synthetic`, `authenticated_source_system_id`, `run_manifest_sha256`, `record_manifest_sha256`, `fabric_export_ref`, and `phases` with exactly `BASELINE`, `DUPLICATE_SAME_HASH`, `CONFLICTING_OVERWRITE`. For formal exports, all three arrays have exactly ten ordered entries; trial IDs and baseline source record IDs must be unique, and the same ten source record IDs must recur at corresponding indexes in both attack phases.

The baseline row includes `attempt`, `trial_id`, `source_record_id`, exact `exact_payload_base64`, `payload_sha256`, complete expected `anchor`, independently observed `pre_query` (found=false, record_count=0) and `post_query` (found=true, record_count=1), and terminal `response` (status=COMMITTED, outcome=CREATE, 64-hex Fabric transaction ID). All phases include `unrelated_fabric_outage=false`. Each attack row has its own complete request/response, exact payload/hash, and independently observed pre/post ledger queries.

HRC anchor fields are **exactly** `record_id`, `authenticated_source_system_id`, `source_record_id`, `digest_algorithm=sha256`, `digest`, `payload_length`, `source_type`, `producer`, `produced_at`, and `schema_version`. Query envelopes include `query_ref`, `authenticated_source_system_id`, `source_record_id`, `found`, `record_count`, and full `anchor` when found. The **Fabric team must supply and document independent evidence for record_count/uniqueness**: the ordinary HRC single-record `QuerySourceBoundAnchor` response alone does not establish that no additional ledger record/history entry exists. Do not invent or infer count=1 from a single anchor query. Every response includes `request_ref`, `response_ref`, exact source/payload identity, terminal `status`, typed `outcome`, and nonnegative finite `response_time_ms`.

The production HRC response decoder accepts `CREATE` and `IDEMPOTENT_RETRY`. The duplicate same-**bytes** case should normally return `COMMITTED/IDEMPOTENT_RETRY`, preserve the same original record, and create no additional anchor. An explicit `REJECTED/REJECTED_DUPLICATE` is accepted only when supported by `failure_category=DUPLICATE_ANCHOR`, `decision_source=CHAINCODE` and independently unchanged ledger state; it is a possible normalized Fabric-team export category, **not** a claim that current HRC chaincode emits that category. The conflicting overwrite case requires a different exact payload and digest, `REJECTED/REJECTED_CONFLICT`, `failure_category=CONFLICTING_ANCHOR`, `decision_source=CHAINCODE` and unchanged queried world state.

**Duplicate effective-prevention count and literal duplicate-rejection count are distinct.** An idempotent retry is safe but must NOT be silently counted as a literal client rejection. The scorer reports both counts, conflict-rejection count, original-hash preservation, unauthorized-state-change count, response-time mean and sample SD.

- INVALID: baseline absence not independently proven; wrong/missing identity, payload bytes, digest, or transaction evidence; incomplete post-query; unrelated Fabric outage; duplicate phase not same exact bytes; conflict phase not different bytes; wrong/missing rejection attribution.
- FAIL: independently proven baseline valid creation not committed, duplicate attempt creates an extra record or mutates the original, conflicting attempt commits or changes/deletes the anchor despite rejection, or accepted duplicate outcome is not genuinely idempotent.
- PASS: baseline created and queried; same-bytes retry has the HRC expected idempotent outcome (or separately proven explicit duplicate rejection), conflicting overwrite rejected by chaincode; original anchor stays exactly identical before/after every attempted mutation and record multiplicity stays one.

Even a perfectly self-consistent supplied formal JSON returns `counted_research=false` and `requires_fabric_provenance_review=true`. The actual I3 test launcher remains `HARNESS_REQUIRED` until Fabric agrees on an approved dedicated test fixture, implements the real attempt/query/export actor, and the full loop is live-rehearsed with the shared manifests and read-only verification.
