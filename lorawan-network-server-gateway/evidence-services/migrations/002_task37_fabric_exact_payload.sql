-- Task 37: exact finalized JSON payload retention + restart-safe Fabric transaction material.
-- Additive migration. Never backfill finalized_payload from JSONB or telemetry columns:
-- legacy rows do not possess the authoritative exact-byte artifact and remain ineligible.

BEGIN;

LOCK TABLE telemetry.fabric_outbox IN SHARE ROW EXCLUSIVE MODE;

ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS finalized_payload BYTEA,
  ADD COLUMN IF NOT EXISTS fabric_record_id TEXT,
  ADD COLUMN IF NOT EXISTS fabric_prepared_tx BYTEA,
  ADD COLUMN IF NOT EXISTS fabric_commit_status_request BYTEA;

ALTER TABLE telemetry.fabric_outbox
  DROP CONSTRAINT IF EXISTS fabric_outbox_finalized_payload_size_chk;

ALTER TABLE telemetry.fabric_outbox
  ADD CONSTRAINT fabric_outbox_finalized_payload_size_chk
  CHECK (
    finalized_payload IS NULL
    OR octet_length(finalized_payload) BETWEEN 1 AND 1048576
  );

COMMENT ON COLUMN telemetry.fabric_outbox.finalized_payload IS
  'Immutable exact UTF-8 finalized normalized telemetry JSON bytes accepted upstream for HRC Task 37; never reconstruct from JSONB/columns.';
COMMENT ON COLUMN telemetry.fabric_outbox.fabric_record_id IS
  'HRC record_id returned by the endorsed CreateSourceBoundAnchor response and persisted before submit.';
COMMENT ON COLUMN telemetry.fabric_outbox.fabric_prepared_tx IS
  'Exact endorsed Fabric transaction bytes persisted before first orderer submit for crash-safe same-tx recovery.';
COMMENT ON COLUMN telemetry.fabric_outbox.fabric_commit_status_request IS
  'Signed Fabric Gateway commit-status request persisted with txid before first orderer submit.';

-- The adapter intentionally has relation-level SELECT but column-scoped UPDATE.
-- Grant only the new durable transaction-material columns it must populate.
GRANT UPDATE (fabric_record_id, fabric_prepared_tx, fabric_commit_status_request)
  ON telemetry.fabric_outbox TO fabric_adapter;

CREATE OR REPLACE FUNCTION telemetry.enforce_fabric_outbox_immutability()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.event_key IS DISTINCT FROM OLD.event_key
     OR NEW.source_event_key IS DISTINCT FROM OLD.source_event_key
     OR NEW.observed_at IS DISTINCT FROM OLD.observed_at
     OR NEW.event_type IS DISTINCT FROM OLD.event_type
     OR NEW.schema_version IS DISTINCT FROM OLD.schema_version THEN
    RAISE EXCEPTION 'fabric outbox source identity is immutable for outbox_id=%', OLD.outbox_id;
  END IF;

  -- A legacy row may transition NULL -> exact bytes only through a deliberately
  -- authorized migration, but once bytes exist they can never be replaced.
  IF OLD.finalized_payload IS NOT NULL
     AND NEW.finalized_payload IS DISTINCT FROM OLD.finalized_payload THEN
    RAISE EXCEPTION 'fabric outbox finalized payload is immutable for outbox_id=%', OLD.outbox_id;
  END IF;

  IF OLD.canonical_json IS NOT NULL AND (
       NEW.canonical_json IS DISTINCT FROM OLD.canonical_json
       OR NEW.digest_sha256 IS DISTINCT FROM OLD.digest_sha256
       OR NEW.evidence_signature_alg IS DISTINCT FROM OLD.evidence_signature_alg
       OR NEW.evidence_signing_key_id IS DISTINCT FROM OLD.evidence_signing_key_id
       OR NEW.evidence_signature IS DISTINCT FROM OLD.evidence_signature
       OR NEW.evidence_sealed_at IS DISTINCT FROM OLD.evidence_sealed_at
     ) THEN
    RAISE EXCEPTION 'fabric outbox evidence seal is immutable for outbox_id=%', OLD.outbox_id;
  END IF;

  -- Once a Task 37 transaction identity is durable, no retry path may replace
  -- it with a newly prepared Create transaction.
  IF OLD.fabric_tx_id IS NOT NULL AND (
       NEW.fabric_tx_id IS DISTINCT FROM OLD.fabric_tx_id
       OR NEW.fabric_record_id IS DISTINCT FROM OLD.fabric_record_id
       OR NEW.fabric_prepared_tx IS DISTINCT FROM OLD.fabric_prepared_tx
       OR NEW.fabric_commit_status_request IS DISTINCT FROM OLD.fabric_commit_status_request
     ) THEN
    RAISE EXCEPTION 'fabric outbox prepared transaction is immutable for outbox_id=%', OLD.outbox_id;
  END IF;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS fabric_outbox_immutability_trg
  ON telemetry.fabric_outbox;

CREATE TRIGGER fabric_outbox_immutability_trg
BEFORE UPDATE ON telemetry.fabric_outbox
FOR EACH ROW
EXECUTE FUNCTION telemetry.enforce_fabric_outbox_immutability();

-- Prove the selected transport representation is byte-preserving. This does not
-- manufacture qualification data; it validates PostgreSQL encode/decode itself.
DO $$
DECLARE
  original BYTEA := convert_to('{"task37":"byte-preserving","unicode":"µ"}', 'UTF8');
  roundtrip BYTEA;
BEGIN
  roundtrip := decode(encode(original, 'base64'), 'base64');
  IF roundtrip IS DISTINCT FROM original THEN
    RAISE EXCEPTION 'base64 byte-preserving round-trip failed';
  END IF;
END
$$;

COMMIT;
