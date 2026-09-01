# gateway_evidence migrations

`001_gateway_evidence.sql` is the reviewed schema used for the live cloud evidence services. It has been applied once to `lorawan_telemetry` and verified across all three Patroni members; retain this file as the reproducible source for rebuild/recovery and do not reapply it to the already-commissioned cluster.

## Forward rule

Apply once to `lorawan_telemetry` through the guarded deployment journey after:

- the production raw-evidence backend is selected/staged;
- the cloud runtime artifacts have compiled/tested and are pinned;
- the exact database roles/credential delivery plan is ready;
- a current Patroni leader is rediscovered;
- the normal pre-mutation schema/grant checks pass.

The migration creates the evidence role shells as `NOLOGIN`. Password/SCRAM material and `LOGIN` activation are a separate protected credential boundary.

All persisted Gateway EUIs use one canonical lowercase 16-hex representation. `gateway_evidence.checkpoints` also owns a `BEFORE INSERT` monotonicity trigger which takes the same `hashtextextended(gateway_id, 0)` advisory transaction lock as the Go repository and rejects a checkpoint whose `last_sequence` is behind already accepted history. The application still classifies exact retry versus same-sequence conflict before insert; the trigger is the final database invariant for callers that bypass application code.

The Rust segment contract freezes positive numbering and the predecessor sentinel. Therefore `segment_id` and segment/checkpoint sequences begin at `1`; segment `1` must use exact `previous_segment_hash='GENESIS'`; every later segment must use a lowercase 64-hex predecessor hash. `001_gateway_evidence.verify.sql` checks that invariant, and the guarded live migration/three-node verification boundary has passed.

`gateway_evidence.event_verification` is fail-closed at the database layer. A `status='verified'` row must carry `verified_at` plus the full gateway/journal/checkpoint/MQTT/decoder/raw/normalized projection; it cannot carry a reason code. Non-verified terminal states require a reason and cannot carry `verified_at`. The current verifier source now contains the lease-fenced complete-lineage `CompleteVerified` path; no live `verified` row is claimed until the production services and one real gateway lineage exercise it.

## Rollback rule

After any real checkpoint, segment, MQTT witness, or verification row exists, this schema is **forward-only evidence history**. Do not implement an automatic destructive down migration that silently drops accepted security evidence.

Before first live data, a failed staging deployment may be rolled back only by an explicitly reviewed operator transaction that proves all `gateway_evidence` tables are empty, removes the staging-only grants/objects, and preserves unrelated telemetry/Fabric state.

The filesystem object-store backend in `cloud/internal/objectstore` is development-only and is not an acceptable production rollback/storage target.
