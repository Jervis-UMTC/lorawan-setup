-- Fabric adapter HA: monotonic per-claim lease-generation fencing.
-- Additive migration. Each successful claim increments lease_generation; every
-- worker-owned mutation must match both worker_id and the exact claim generation.

BEGIN;

LOCK TABLE telemetry.fabric_outbox IN SHARE ROW EXCLUSIVE MODE;

ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS lease_generation BIGINT NOT NULL DEFAULT 0;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'fabric_outbox_lease_generation_nonnegative_chk'
      AND conrelid = 'telemetry.fabric_outbox'::regclass
  ) THEN
    ALTER TABLE telemetry.fabric_outbox
      ADD CONSTRAINT fabric_outbox_lease_generation_nonnegative_chk
      CHECK (lease_generation >= 0);
  END IF;
END
$$;

COMMENT ON COLUMN telemetry.fabric_outbox.lease_generation IS
  'Monotonic per-row Fabric adapter claim generation. Incremented on every processing claim and required with worker_id for lease renewal and worker-owned mutations so stale claim instances cannot regain authority.';

GRANT UPDATE (lease_generation) ON telemetry.fabric_outbox TO fabric_adapter;

COMMIT;
