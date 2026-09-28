# A2 endorsement-policy evidence — offline checker

This is **only the evidence contract and code-level scorer** for the Fabric-team-owned A2 experiment. It never contacts Fabric, changes policies, submits transactions, connects to a gateway, or receives sensor data. An offline PASS means an externally supplied JSON export is *internally consistent*, **not** that external ledger facts or authorization have been independently verified. The operator-manual A2 command remains `HARNESS_REQUIRED` until the Fabric team provides, reviews and commissions a controlled missing-endorsement fixture.

## Independent A2 code-only command

From the `lorawan-network-server-gateway` repository root:

```powershell
py -3 test/automation/offline_test.py A2
```

This runs the contract and the synthetic A2 scorer regression suite, including fake successful/failed policy outcomes, invalid evidence, and preservation of unexpected acceptance as FAIL. It cannot contribute Chapter 4 trial counts. The general offline suite is `py -3 test/automation/run_offline_qualification.py`.

## Fabric-side evidence handoff

LoRaWAN owns the common `run_id + trial_id + source_record_id + payload_sha256` join and sealed run/record manifests (see `test/FABRIC-SYNCHRONIZED-TEST-CONTRACT.md`). The Fabric team must independently verify both manifest sidecars, return its signed/exported evidence and supply an A2 JSON object with:

- Top-level: `test_id="A2"`, `run_id`, `formal` boolean, `attempts_per_condition` (10 formal; 1–10 commissioning), `evidence_origin="FABRIC_SIDE"` only for an actual Fabric run, `authenticated_source_system_id="lorawan-gateway-evidence"`, `run_manifest_sha256`, `record_manifest_sha256`, `policy_ref`, `policy_sha256`, `approved_fixture_ref`, `fixture_namespace`, `required_endorser`, `violation_injection_ref`, `restoration_proof_ref`, and a `conditions` object.
- The `conditions` object has exactly `NORMAL`, `ENDORSEMENT_VIOLATION`, and `RESTORED` arrays, with equal count and ordered attempts 1..N. All trial/source IDs and world-state keys must be unique across all conditions; keys must begin `fixture_namespace + ":"`.
- Each trial: `condition`, `attempt`, `trial_id`, `source_record_id`, `world_state_key`, `payload_sha256`, `authenticated_source_system_id`, `policy_sha256`, `identity_authorized=true`, `record_schema_valid=true`, `unrelated_fabric_outage=false`, `required_endorsements_satisfied` (true normal/restored, false violation), `endorsement_probe_ref`, `attempt_ref`, `response_ref`, finite nonnegative `response_time_ms`, `normalized_status`, `failure_category` and `fabric_tx_id` as applicable.
- Each trial's `pre` and `post` are independently queried objects of `{"key": "<world_state_key>", "exists": <boolean>, "state_sha256": "<64 hex if exists, otherwise null>", "query_ref": "<retained query evidence reference>"}`. These are observations of *Fabric world state*, not arbitrary re-hashes of PostgreSQL or the application's experimental I1 hash.
- NORMAL/RESTORED: fresh `pre.exists=false`, committed `post.exists=true`, 64-hex Fabric TxID, and an `expected_world_state_sha256` that equals the **independently retrieved** post-state hash.
- ENDORSEMENT_VIOLATION: prove an otherwise schema-valid, authorized attempt missing a required endorsement. A correct rejection has `normalized_status="REJECTED"`, `failure_category="MISSING_REQUIRED_ENDORSEMENT"`, and *identical pre/post world-state existence and hash*. If a valid violating transaction commits or changes state, retain the result as FAIL; never reclassify a proven failure as INVALID to improve the percentage.

If required endorsement was not demonstrably missing, the policy decision came from an unrelated authorization/error path, or either query is unavailable, classify the attempt INVALID rather than counting it as a rejected attack. A normal/restored valid attempt unexpectedly rejected is FAIL. The scorer produces counts, per-condition response-time means and sample SD, and an unauthorized-state-change count.

Once a genuine Fabric-side JSON export exists, validate **without overwriting source evidence**:

```powershell
py -3 test/automation/authentication/a2_fabric_endorsement_evidence.py --evidence "<fabric-side-a2-evidence.json>" --output "<separate-a2-validation.json>"
```

The scorer still outputs `counted_research=false` and `requires_fabric_provenance_review=true`, even when the external export declares formal mode. A reviewer must verify the underlying Fabric query/proposal/commit records, policy signature, sidecars, and synchronized manifest IDs separately. The scorer does not validate external references by dereferencing them, so its PASS cannot on its own release the formal A2 experiment.

**Next code-only qualification:** I1 application-layer pre/post-hash and quarantine evidence, then I2 canonical-source verifier, then I3 duplicate/overwrite ledger-state validator. All remain unreleased for counted use.
