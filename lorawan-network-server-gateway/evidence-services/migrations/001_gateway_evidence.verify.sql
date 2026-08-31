\set ON_ERROR_STOP on

DO $$
DECLARE
  base_table_count integer;
  evidence_role_count integer;
BEGIN
  IF to_regnamespace('gateway_evidence') IS NULL THEN
    RAISE EXCEPTION 'gateway_evidence schema missing';
  END IF;

  SELECT count(*) INTO base_table_count
  FROM information_schema.tables
  WHERE table_schema = 'gateway_evidence'
    AND table_type = 'BASE TABLE'
    AND table_name IN ('checkpoints','segments','mqtt_gateway_events','event_verification');
  IF base_table_count <> 4 THEN
    RAISE EXCEPTION 'expected 4 gateway_evidence base tables, found %', base_table_count;
  END IF;

  SELECT count(*) INTO evidence_role_count
  FROM pg_roles
  WHERE rolname IN ('gateway_evidence_ingestor','gateway_evidence_collector','gateway_evidence_verifier')
    AND rolcanlogin = false;
  IF evidence_role_count <> 3 THEN
    RAISE EXCEPTION 'evidence role-shell gate failed';
  END IF;

  IF NOT has_schema_privilege('gateway_evidence_ingestor', 'gateway_evidence', 'USAGE') THEN
    RAISE EXCEPTION 'ingestor schema USAGE missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'telemetry'
      AND table_name = 'uplinks'
      AND column_name IN ('gateway_uplink_id','gateway_frequency_hz','gateway_context_base64')
    GROUP BY table_schema, table_name
    HAVING count(*) = 3
  ) THEN
    RAISE EXCEPTION 'telemetry uplink gateway-correlation provenance columns missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_trigger t
    JOIN pg_class c ON c.oid = t.tgrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'gateway_evidence'
      AND c.relname = 'checkpoints'
      AND t.tgname = 'checkpoints_monotonic_before_insert'
      AND NOT t.tgisinternal
      AND t.tgenabled <> 'D'
  ) THEN
    RAISE EXCEPTION 'checkpoint monotonicity trigger missing or disabled';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'gateway_evidence'
      AND c.relname IN ('checkpoints','segments','mqtt_gateway_events','event_verification')
      AND con.contype = 'c'
      AND pg_get_constraintdef(con.oid) LIKE '%[0-9A-Fa-f]%'
  ) THEN
    RAISE EXCEPTION 'Gateway EUI constraints must require canonical lowercase hex';
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'gateway_evidence'
      AND c.relname = 'segments'
      AND con.conname = 'segment_previous_hash_ck'
      AND con.contype = 'c'
      AND pg_get_constraintdef(con.oid) LIKE '%GENESIS%'
      AND pg_get_constraintdef(con.oid) LIKE '%segment_id = 1%'
  ) THEN
    RAISE EXCEPTION 'segment GENESIS/predecessor-hash constraint missing';
  END IF;
  IF NOT has_column_privilege('gateway_evidence_ingestor', 'gateway_evidence.checkpoints', 'gateway_id', 'INSERT') THEN
    RAISE EXCEPTION 'ingestor checkpoint INSERT missing';
  END IF;
  IF NOT has_column_privilege('gateway_evidence_ingestor', 'gateway_evidence.segments', 'object_sha256', 'INSERT') THEN
    RAISE EXCEPTION 'ingestor segment INSERT missing';
  END IF;
  IF has_column_privilege('gateway_evidence_ingestor', 'gateway_evidence.segments', 'verify_status', 'INSERT') THEN
    RAISE EXCEPTION 'ingestor must not author segment verification status';
  END IF;
  IF has_column_privilege('gateway_evidence_ingestor', 'gateway_evidence.segments', 'verify_status', 'UPDATE') THEN
    RAISE EXCEPTION 'ingestor must not update segment verification status';
  END IF;

  IF NOT has_column_privilege('gateway_evidence_collector', 'gateway_evidence.mqtt_gateway_events', 'capture_key_sha256', 'INSERT') THEN
    RAISE EXCEPTION 'collector capture INSERT missing';
  END IF;
  IF NOT has_column_privilege('gateway_evidence_collector', 'gateway_evidence.mqtt_gateway_events', 'correlation_digest_sha256', 'INSERT') THEN
    RAISE EXCEPTION 'collector correlation-digest INSERT missing';
  END IF;
  IF NOT has_column_privilege('gateway_evidence_collector', 'gateway_evidence.mqtt_gateway_events', 'gateway_context_base64', 'INSERT') THEN
    RAISE EXCEPTION 'collector gateway-context INSERT missing';
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'gateway_evidence'
      AND c.relname = 'mqtt_gateway_events'
      AND con.conname = 'mqtt_projection_ck'
      AND con.contype = 'c'
  ) THEN
    RAISE EXCEPTION 'MQTT uplink all-or-none projection constraint missing';
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_indexes
    WHERE schemaname = 'gateway_evidence'
      AND tablename = 'mqtt_gateway_events'
      AND indexname = 'mqtt_gateway_events_uplink_lookup_idx'
      AND indexdef LIKE '%gateway_context_base64%'
      AND indexdef LIKE '%correlation_digest_sha256 IS NOT NULL%'
  ) THEN
    RAISE EXCEPTION 'MQTT deterministic uplink lookup index missing';
  END IF;
  IF has_table_privilege('gateway_evidence_collector', 'gateway_evidence.mqtt_gateway_events', 'UPDATE')
     OR has_table_privilege('gateway_evidence_collector', 'gateway_evidence.mqtt_gateway_events', 'DELETE') THEN
    RAISE EXCEPTION 'collector must not mutate accepted MQTT evidence';
  END IF;

  IF NOT has_column_privilege('gateway_evidence_verifier', 'gateway_evidence.event_verification', 'source_event_key', 'INSERT') THEN
    RAISE EXCEPTION 'verifier discovery INSERT missing';
  END IF;
  IF has_column_privilege('gateway_evidence_verifier', 'gateway_evidence.event_verification', 'status', 'INSERT') THEN
    RAISE EXCEPTION 'verifier must not insert pre-authored verification status';
  END IF;
  IF NOT has_column_privilege('gateway_evidence_verifier', 'gateway_evidence.event_verification', 'status', 'UPDATE') THEN
    RAISE EXCEPTION 'verifier status UPDATE missing';
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'gateway_evidence'
      AND c.relname = 'event_verification'
      AND con.conname = 'verification_verified_projection_ck'
      AND pg_get_constraintdef(con.oid) LIKE '%journal_record_hash IS NOT NULL%'
      AND pg_get_constraintdef(con.oid) LIKE '%gateway_event_id IS NOT NULL%'
      AND pg_get_constraintdef(con.oid) LIKE '%normalized_digest_sha256 IS NOT NULL%'
  ) THEN
    RAISE EXCEPTION 'verified event projection completeness constraint missing';
  END IF;
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint con
    JOIN pg_class c ON c.oid = con.conrelid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'gateway_evidence'
      AND c.relname = 'event_verification'
      AND con.conname = 'verification_terminal_reason_ck'
  ) THEN
    RAISE EXCEPTION 'terminal verification reason constraint missing';
  END IF;
  IF has_column_privilege('gateway_evidence_verifier', 'gateway_evidence.event_verification', 'source_event_key', 'UPDATE') THEN
    RAISE EXCEPTION 'verifier must not rewrite source_event_key';
  END IF;
  IF NOT has_column_privilege('gateway_evidence_verifier', 'gateway_evidence.segments', 'verify_status', 'UPDATE') THEN
    RAISE EXCEPTION 'verifier segment-status UPDATE missing';
  END IF;
  IF NOT has_table_privilege('gateway_evidence_verifier', 'telemetry.fabric_outbox', 'SELECT') THEN
    RAISE EXCEPTION 'verifier outbox discovery SELECT missing';
  END IF;
  IF NOT has_table_privilege('gateway_evidence_verifier', 'telemetry.uplinks', 'SELECT')
     OR NOT has_table_privilege('gateway_evidence_verifier', 'telemetry.measurements', 'SELECT') THEN
    RAISE EXCEPTION 'verifier telemetry comparison SELECT missing';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telemetry_reader') THEN
    IF NOT has_table_privilege('telemetry_reader', 'gateway_evidence.checkpoint_status', 'SELECT')
       OR NOT has_table_privilege('telemetry_reader', 'gateway_evidence.verification_status', 'SELECT') THEN
      RAISE EXCEPTION 'telemetry_reader evidence-view SELECT missing';
    END IF;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'fabric_adapter') THEN
    IF NOT has_table_privilege('fabric_adapter', 'gateway_evidence.event_verification', 'SELECT') THEN
      RAISE EXCEPTION 'fabric_adapter verifier-result SELECT missing';
    END IF;
    IF has_table_privilege('fabric_adapter', 'gateway_evidence.event_verification', 'INSERT')
       OR has_table_privilege('fabric_adapter', 'gateway_evidence.event_verification', 'UPDATE')
       OR has_table_privilege('fabric_adapter', 'gateway_evidence.event_verification', 'DELETE') THEN
      RAISE EXCEPTION 'fabric_adapter must be read-only on verifier results';
    END IF;
  END IF;
END
$$;

SELECT 'EVIDENCE_DB_MIGRATION_VERIFY=PASS' AS result;
