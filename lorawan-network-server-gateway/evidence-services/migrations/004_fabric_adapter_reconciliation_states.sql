-- Fabric adapter timeout/reconciliation state compatibility migration.
--
-- Keep both legacy and current names during the rollout so the previous
-- production image remains a valid rollback target while the hardened writer
-- is qualified. No evidence rows are rewritten or deleted by this migration.

BEGIN;

ALTER TABLE telemetry.fabric_outbox
  DROP CONSTRAINT IF EXISTS fabric_outbox_status_ck;

ALTER TABLE telemetry.fabric_outbox
  ADD CONSTRAINT fabric_outbox_status_ck
  CHECK (
    status IN (
      'pending',
      'processing',
      'submitted_unknown',
      'reconciling',
      'confirmed',
      'failed',
      'dead_letter',
      'needs_attention'
    )
  );

COMMIT;
