# I1 application integrity — hardware-offline code qualification

**Scope:** I1 is the temporary Node-RED application-layer experimental gate, not the production Fabric/OpenBao evidence-signing path. The frozen study rule is **10 unchanged controls + 10 deliberately altered temperature readings**. All 20 formal trials eventually require powered EMU-01, an approved and backed-up Node-RED test flow, independent DB/outbox inspection, safe quarantine wiring, and post-test flow restoration. None of that was commissioned in the hardware-offline code run.

## One command to qualify I1 implementation offline

Run from the `lorawan-network-server-gateway` repository root:

```powershell
py -3 test/automation/offline_test.py I1
```

The I1-only runner executes research-contract checks and I1 Python evidence-score tests. One Python test executes the **actual** JavaScript Function-node script in a mocked Node.js VM: 13 separate Node.js test cases check normal versus quarantined output, one-shot arm/disarm, DevEUI scoping, exact hashes, no input mutation, and fail-closed malformed input/crypto/flag behavior. No Node-RED, USB, gateway, sensor, SQL, broker or Fabric endpoint is accessed. For all offline suites use `py -3 test/automation/run_offline_qualification.py`. The summary is explicitly marked `counted_research=false`.

## Files and data contract

- `integrity/i1_node_red_gate.function.js` — exact two-output Node-RED test Function body; paste into an isolated **test-only** flow only after reviewing that its output 1 reaches normal validated processing and output 2 reaches **only** quarantine/debug/file; configure Node.js `crypto` via Node-RED `functionGlobalContext`.
- `integrity/test_i1_node_red_gate.cjs` — 13 direct JavaScript VM regressions.
- `integrity/i1_evidence.py` and `integrity/test_i1_evidence.py` — offline scorer and negative-condition tests. It does not query production services.
- CLI for *already captured* evidence (output path must be distinct from source):
  ```powershell
  py -3 test/automation/integrity/i1_evidence.py --evidence "<i1-evidence.json>" --output "<i1-validation.json>"
  ```

The gate constructs exactly: `test_id`, `dev_eui`, `f_cnt`, `sensor_type`, `sensor_value`, `unit`, `event_time`. The selected sensor is decoded `temperature_c` (physical environment temperature compatibility field) in Cel. It records the **exact UTF-8 JSON strings and SHA-256** before and after optional **+10 Cel** mutation. It uses `JSON.stringify` for the I1 experimental control; these hashes must NEVER be described as RFC 8785 or the Fabric attestation digest. The message also records `test_sequence`, `altered`, `match`, `status`, and observation UTC. Non-EMU traffic is passed through unchanged. Missing/malformed EMU trial evidence or missing crypto is quarantined, not stored as a valid reading. The arm flag is consumed before processing a target message, including malformed messages, so one click cannot silently affect later EMU readings.

The scorer accepts an I1 JSON evidence object: `test_id="I1"`, boolean `formal`, `attempts_per_condition` (10 formal), valid flow export SHA-256/reference and test gate SHA-256, and `conditions` with exactly `UNCHANGED` and `ALTERED` arrays. Each trial has unique `source_test_id` and `test_sequence`, ordered condition/attempt, recorded `gate` object, `gate_observation_ref`, `verification_time_ms`, and independent `pre_storage` and `post_storage` read-only query counts/references for both `uplinks` and `outbox`. Normal controls require `storage_ref`; altered trials require `quarantine_ref` and zero post-storage uplinks/outbox. Before every trial, the chosen source identity must be absent in both tables, or attribution is INVALID. A retained query reference is evidence metadata; the scorer does **not** dereference it or independently attest to an external DB/Fabric query.

The scorer recomputes both SHA-256 values from the recorded exact UTF-8 strings; requires only `sensor_value` to vary; requires the altered value to differ by +10 Cel; rejects duplicated source IDs/sequences and malformed/missing observation fields. For a **valid** alteration that the gate allowed, or one independently proven stored/forwarded, the result is FAIL, not INVALID. Missing query/quarantine/flow provenance is INVALID. Even an externally marked formal export returns `counted_research=false` and `qualification=SUPPLIED_EVIDENCE_VALIDATION_ONLY`, because actual hardware, node wiring and production-path observation have not been independently reviewed.

## Live commissioning gate (still pending)

Back up the real Node-RED flow and database, inspect the effective decoder schema and isolated test wiring, freeze the flow export SHA-256, verify 1 unchanged and 1 armed rehearsal on actual EMU-01 messages, prove quarantine **cannot** write to TimescaleDB/Fabric, verify all 20 planned trials and real DB/Fabric readbacks, and restore the known-good flow with a subsequent normal sensor operation. Until this succeeds, `run_test.py I1` remains `HARNESS_REQUIRED`; neither the temporary gate nor the offline scorer is a released counted operator command.

**Next code-only test:** I2 read-only production-v1 canonical source reconstruction and post-storage integrity comparison, then I3.
