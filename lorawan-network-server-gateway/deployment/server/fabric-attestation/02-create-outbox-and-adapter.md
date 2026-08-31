# Fabric 2. Create the Outbox and Deploy the Adapter

The outbox separates telemetry ingestion from blockchain availability. Node-RED creates a queue item in the same PostgreSQL statement as the telemetry row. A separate adapter claims the item, creates canonical evidence, submits it through Fabric Gateway, waits for commit status, and records the result.

Before running commands, keep the two components separate:

| Component | Implemented as | Owns | Must survive |
|---|---|---|---|
| Fabric outbox | `telemetry.fabric_outbox` PostgreSQL table | durable job identity, processing state, immutable evidence seal, retry/commit result | adapter crash, KMS outage, Fabric outage, application restart |
| Fabric adapter | separate long-running service/container | claim jobs, load evidence, call OpenBao, call Fabric, classify errors, update outbox state | it is replaceable compute; restarting it must not lose jobs |

The implementation order is therefore:

```text
1. create and protect the outbox table
2. make Node-RED create selected outbox rows atomically with telemetry
3. give the adapter a least-privilege database role
4. implement lease-based worker claiming
5. seal evidence through OpenBao and persist the seal
6. verify the persisted seal, then submit to Fabric
7. update only the outbox state after the real Fabric result
```

Do not merge these responsibilities into Node-RED. Node-RED owns ingestion and the atomic enqueue operation; the adapter owns asynchronous KMS/Fabric work. For v2, the separate gateway-evidence verifier owns source verification. If the verifier, adapter, KMS, or Fabric stops, the telemetry transaction must still complete and the outbox row must remain durable; v2 simply remains ineligible for sealing until the evidence policy allows it.

The canonical watcher/service topology is documented in [`gateway-integrity/04-service-architecture-and-runtime-contract.md`](../integrations/gateway-integrity/04-service-architecture-and-runtime-contract.md). In that architecture, the Fabric Adapter **does not watch Concentratord, journal files, or gateway MQTT topics**. It watches only durable eligible outbox work and reads verifier-owned `gateway_evidence.event_verification` state for v2. This prevents the signer/submission process from becoming the authority that decides whether its own source evidence is trustworthy.

This repository does not currently contain a completed adapter image. Treat `<PINNED_FABRIC_ADAPTER_IMAGE>` as an unresolved input, not an image that already exists.

## Step 1: Back up the telemetry database

Follow the [TimescaleDB backup and restore procedure](../integrations/timescaledb/04-backup-security-and-maintenance.md). Verify the telemetry dump catalog, checksum, off-host copy, and isolated restore path before applying the schema migration.

**Stop here. Do not continue until the telemetry database backup is readable.**

### Cloud Spilo client-path correction

On the cloud HA deployment, PostgreSQL client utilities are authoritative inside the commissioned `spilo` container. Do not assume the Ubuntu host has a versioned PostgreSQL client installed merely because `/usr/bin/pg_restore` is a `pg_wrapper` shim. When validating a host-owned custom-format dump on `ulc-03`, stream it to the PostgreSQL 18.6 client in `spilo`:

```bash
sudo docker exec spilo pg_restore --version
sudo docker exec -i spilo pg_restore --list < "$TELEMETRY_DUMP" >/dev/null
```

A host `pg_wrapper` error requesting `postgresql-client-<version>` is a harness/tool-location failure if the checksum has already passed; it is not evidence that the dump is corrupt. Do not install a duplicate host client as an ad-hoc workaround unless the deployment design explicitly changes.



### Current cloud test-scope backup exception - 2026-08-27

For the current cloud commissioning sequence, the newer project-wide HA-preserving test-scope decision explicitly defers the **off-host copy and isolated-restore rehearsal** until the dedicated failure/recovery boundary. This does not waive rollback protection and does not claim Phase 13A disaster-recovery completion.

Before the first `fabric_outbox` schema mutation, re-verify the preserved fresh local custom-format backup at `/home/opsadmin/backups/phase13a-20260827T032756Z` on `ulc-03`: `lorawan_telemetry.dump` must still parse with `pg_restore --list`, `sha256sum -c SHA256SUMS` must pass, and the live preflight must still show the same pre-outbox database baseline (`TimescaleDB 2.29.2`, the six commissioned telemetry objects, `measurements,uplinks` as the only telemetry hypertables, and `telemetry.fabric_outbox` absent). Use this exception only for the current non-destructive setup migration. Preserve the backup directory. Off-host verification and isolated restore remain required before later destructive recovery/failure work.

## Step 2: Create the outbox table

Open the telemetry database as `telemetry_admin` and run:

```sql
CREATE TABLE IF NOT EXISTS telemetry.fabric_outbox (
    outbox_id             BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    event_key             TEXT NOT NULL UNIQUE,
    source_event_key      TEXT NOT NULL,
    observed_at           TIMESTAMPTZ NOT NULL,
    event_type            TEXT NOT NULL,
    schema_version        TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending',
    attempts              INTEGER NOT NULL DEFAULT 0,
    next_attempt_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    worker_id             TEXT,
    processing_started_at TIMESTAMPTZ,
    lease_expires_at      TIMESTAMPTZ,
    canonical_json        TEXT,
    digest_sha256         TEXT,
    evidence_signature_alg TEXT,
    evidence_signing_key_id TEXT,
    evidence_signature TEXT,
    evidence_sealed_at    TIMESTAMPTZ,
    fabric_tx_id          TEXT,
    submitted_at          TIMESTAMPTZ,
    committed_at          TIMESTAMPTZ,
    last_error_category   TEXT,
    last_error            TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fabric_outbox_status_ck CHECK (
      status IN (
        'pending','processing','submitted_unknown',
        'confirmed','failed','dead_letter'
      )
    ),
    CONSTRAINT fabric_outbox_digest_ck CHECK (
      digest_sha256 IS NULL OR digest_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT fabric_outbox_seal_ck CHECK (
      (canonical_json IS NULL
       AND digest_sha256 IS NULL
       AND evidence_signature_alg IS NULL
       AND evidence_signing_key_id IS NULL
       AND evidence_signature IS NULL
       AND evidence_sealed_at IS NULL)
      OR
      (canonical_json IS NOT NULL
       AND canonical_json <> ''
       AND digest_sha256 IS NOT NULL
       AND evidence_signature_alg = 'OPENBAO-TRANSIT-ECDSA-P256-SHA2-256'
       AND evidence_signing_key_id ~ '^openbao:transit:lorawan-evidence:v[1-9][0-9]*$'
       AND evidence_signature ~ '^[^:]+:v[1-9][0-9]*:.+$'
       AND evidence_sealed_at IS NOT NULL)
    ),
    CONSTRAINT fabric_outbox_processing_ck CHECK (
      status <> 'processing'
      OR (
        worker_id IS NOT NULL
        AND processing_started_at IS NOT NULL
        AND lease_expires_at IS NOT NULL
      )
    )
);
```

When an earlier draft of the table already exists, add the lease and evidence-seal fields without dropping data:

```sql
ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS worker_id TEXT;
ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ;
ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;
ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS evidence_signature_alg TEXT;
ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS evidence_signing_key_id TEXT;
ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS evidence_signature TEXT;
ALTER TABLE telemetry.fabric_outbox
  ADD COLUMN IF NOT EXISTS evidence_sealed_at TIMESTAMPTZ;
```

Inspect existing constraints before adding the processing constraint to an existing table:

```sql
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'telemetry.fabric_outbox'::regclass
ORDER BY conname;
```

Do not add the constraint while an existing `processing` row lacks lease data. Repair or return those rows to `pending` under an approved recovery procedure first.

After the invalid-row check returns zero, add the constraint only when it is absent:

```sql
SELECT count(*) AS invalid_processing_rows
FROM telemetry.fabric_outbox
WHERE status = 'processing'
  AND (
    worker_id IS NULL
    OR processing_started_at IS NULL
    OR lease_expires_at IS NULL
  );

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'telemetry.fabric_outbox'::regclass
      AND conname = 'fabric_outbox_processing_ck'
  ) THEN
    ALTER TABLE telemetry.fabric_outbox
      ADD CONSTRAINT fabric_outbox_processing_ck CHECK (
        status <> 'processing'
        OR (
          worker_id IS NOT NULL
          AND processing_started_at IS NOT NULL
          AND lease_expires_at IS NOT NULL
        )
      );
  END IF;
END
$$;
```

**Stop here. Do not run the `DO` block** while `invalid_processing_rows` is non-zero.

Before enforcing the evidence seal on an existing table, prove that there is no partially populated seal:

```sql
SELECT outbox_id, event_key, status,
       canonical_json IS NOT NULL AS has_canonical_json,
       digest_sha256 IS NOT NULL AS has_digest,
       evidence_signature_alg IS NOT NULL AS has_signature_alg,
       evidence_signing_key_id IS NOT NULL AS has_key_id,
       evidence_signature IS NOT NULL AS has_signature,
       evidence_sealed_at IS NOT NULL AS has_sealed_at
FROM telemetry.fabric_outbox
WHERE canonical_json IS NOT NULL
   OR digest_sha256 IS NOT NULL
   OR evidence_signature_alg IS NOT NULL
   OR evidence_signing_key_id IS NOT NULL
   OR evidence_signature IS NOT NULL
   OR evidence_sealed_at IS NOT NULL;
```

For every returned row, all six `has_*` columns must have the same value. If a row is only partly sealed, **stop and preserve it for investigation**; do not manufacture missing security fields merely to make the constraint pass.

Now detect complete-looking rows that came from an older local-key draft or contain malformed OpenBao metadata:

```sql
SELECT outbox_id, event_key, status,
       evidence_signature_alg,
       evidence_signing_key_id,
       left(evidence_signature, 32) AS signature_prefix
FROM telemetry.fabric_outbox
WHERE canonical_json IS NOT NULL
  AND (
    canonical_json = ''
    OR evidence_signature_alg <> 'OPENBAO-TRANSIT-ECDSA-P256-SHA2-256'
    OR evidence_signing_key_id !~ '^openbao:transit:lorawan-evidence:v[1-9][0-9]*$'
    OR evidence_signature !~ '^[^:]+:v[1-9][0-9]*:.+$'
  );
```

This query must return zero rows before the new constraint is installed. If it returns anything, preserve those rows and determine which earlier implementation created them. **Do not silently re-sign historical evidence with OpenBao just to make a migration pass.** A replacement attestation, when business governance permits one, must be explicit and traceable to the original record.

Then replace the seal constraint with the exact baseline rule:

```sql
ALTER TABLE telemetry.fabric_outbox
  DROP CONSTRAINT IF EXISTS fabric_outbox_seal_ck;

ALTER TABLE telemetry.fabric_outbox
  ADD CONSTRAINT fabric_outbox_seal_ck CHECK (
    (canonical_json IS NULL
     AND digest_sha256 IS NULL
     AND evidence_signature_alg IS NULL
     AND evidence_signing_key_id IS NULL
     AND evidence_signature IS NULL
     AND evidence_sealed_at IS NULL)
    OR
    (canonical_json IS NOT NULL
     AND canonical_json <> ''
     AND digest_sha256 IS NOT NULL
     AND evidence_signature_alg = 'OPENBAO-TRANSIT-ECDSA-P256-SHA2-256'
     AND evidence_signing_key_id ~ '^openbao:transit:lorawan-evidence:v[1-9][0-9]*$'
     AND evidence_signature ~ '^[^:]+:v[1-9][0-9]*:.+$'
     AND evidence_sealed_at IS NOT NULL)
  );
```

This check prevents a half-written evidence seal. It does not make PostgreSQL immutable; authenticity comes from recomputing the digest, binding the stored OpenBao key-version ID to the complete versioned signature, and receiving `valid=true` from OpenBao Transit for the exact stored canonical bytes.

### Make event identity and a completed seal one-way

The adapter must be able to create a seal once, but a routine application/database credential must not be able to erase that seal and ask the adapter to sign a replacement later. Add a trigger that freezes the source identity for every outbox row and freezes all seal fields after `canonical_json` becomes non-null:

```sql
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

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS fabric_outbox_immutability_trg
  ON telemetry.fabric_outbox;

CREATE TRIGGER fabric_outbox_immutability_trg
BEFORE UPDATE ON telemetry.fabric_outbox
FOR EACH ROW
EXECUTE FUNCTION telemetry.enforce_fabric_outbox_immutability();
```

Test the trigger later with a rolled-back transaction; do not edit a real sealed row for demonstration. This trigger and column-level grants protect against ordinary application/database credentials. A PostgreSQL superuser or host root can bypass database controls; resistance to that stronger threat requires an external append-only signing/anchoring service or equivalent hardware-backed trust design.

Create the worker indexes:

```sql
CREATE INDEX IF NOT EXISTS fabric_outbox_work_idx
  ON telemetry.fabric_outbox (next_attempt_at, outbox_id)
  WHERE status IN ('pending','failed');

CREATE INDEX IF NOT EXISTS fabric_outbox_processing_lease_idx
  ON telemetry.fabric_outbox (lease_expires_at, outbox_id)
  WHERE status = 'processing';

CREATE INDEX IF NOT EXISTS fabric_outbox_status_created_idx
  ON telemetry.fabric_outbox (status, created_at DESC);
```

`canonical_json`, `digest_sha256`, and all four evidence-seal fields remain null until the adapter constructs and seals the approved canonical evidence. The adapter must populate the complete seal before its first Fabric network call.

## Step 3: Create the adapter database role

```sql
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='fabric_adapter') THEN
    CREATE ROLE fabric_adapter LOGIN;
  END IF;
END
$$;

\password fabric_adapter

GRANT USAGE ON SCHEMA telemetry TO fabric_adapter;
GRANT SELECT ON telemetry.uplinks, telemetry.measurements TO fabric_adapter;
GRANT SELECT ON telemetry.fabric_outbox TO fabric_adapter;

-- Remove any broad UPDATE grant left by an earlier draft, then grant only the
-- columns the worker is allowed to mutate. Source identity is intentionally absent.
REVOKE UPDATE ON telemetry.fabric_outbox FROM fabric_adapter;
GRANT UPDATE (
  status,
  attempts,
  next_attempt_at,
  worker_id,
  processing_started_at,
  lease_expires_at,
  canonical_json,
  digest_sha256,
  evidence_signature_alg,
  evidence_signing_key_id,
  evidence_signature,
  evidence_sealed_at,
  fabric_tx_id,
  submitted_at,
  committed_at,
  last_error_category,
  last_error,
  updated_at
) ON telemetry.fabric_outbox TO fabric_adapter;

GRANT INSERT, SELECT ON telemetry.fabric_outbox TO telemetry_writer;
GRANT USAGE, SELECT
  ON SEQUENCE telemetry.fabric_outbox_outbox_id_seq
  TO telemetry_writer;

GRANT SELECT ON telemetry.fabric_outbox TO telemetry_reader;
```

The adapter can read selected telemetry and update only the operational/seal columns named above. It cannot modify stored uplinks, measurements, the Fabric event key, source event key, observation time, event type, or schema version. The one-way trigger additionally prevents a completed seal from being replaced through the normal database path. Grafana remains read-only.

When the [Gateway Integrity](../integrations/gateway-integrity/00-README.md) schema has been installed for v2, add **read-only** access to the verifier result only:

```sql
GRANT USAGE ON SCHEMA gateway_evidence TO fabric_adapter;
GRANT SELECT ON gateway_evidence.event_verification TO fabric_adapter;
```

Do not grant `INSERT`, `UPDATE`, or `DELETE` on the verifier result to `fabric_adapter`. Do not run these grants before the reviewed gateway-integrity schema exists just to make a placeholder configuration look complete.

## Step 4: Queue selected events atomically in Node-RED

Use the parameterized telemetry insert in [`server/integrations/node-red/03-build-telemetry-flow.md`](../integrations/node-red/03-build-telemetry-flow.md).

The current Node-RED telemetry flow already returns `event_key, time` from the `inserted_uplink` CTE. Verify that is still true; do not change it back to `RETURNING 1`.

Add this data-modifying CTE before the final measurements insert:

```sql
, queued_fabric AS (
  INSERT INTO telemetry.fabric_outbox (
    event_key,
    source_event_key,
    observed_at,
    event_type,
    schema_version
  )
  SELECT
    'uplink:' || event_key,
    event_key,
    time,
    'lorawan_uplink_accepted',
    'telemetry-attestation-v1'
  FROM inserted_uplink
  WHERE $25::boolean
  ON CONFLICT (event_key) DO NOTHING
  RETURNING outbox_id
)
```

The current telemetry function uses parameters `$1` through `$24`. Append **one** reviewed Fabric-policy boolean as parameter `$25`; do not renumber or overwrite any existing telemetry parameter. For the lab, set `$25` true only for one test device or one explicit Inject-node test. Do not submit every production sample by default.

The SQL above deliberately queues `telemetry-attestation-v1` and remains the executable compatibility baseline while the new gateway verifier images do not yet exist.

Keep selection policy outside the shared flow so A/B remain byte-identical. The cloud runtime passes `FABRIC_SELECTED_DEV_EUI` through the protected host environment. Until a real staging device is approved, the reserved value `0000000000000000` selects only the documented pre-arrival synthetic fixture. When hardware returns, replace that protected environment value on both Node-RED candidates with the approved lowercase 16-hexadecimal staging DevEUI.

Before building the parameter array, validate and derive the policy value:

```javascript
const fabricSelectedDevEui = String(env.get('FABRIC_SELECTED_DEV_EUI') || '0000000000000000').trim().toLowerCase();
if (!/^[0-9a-f]{16}$/.test(fabricSelectedDevEui)) {
    node.error('FABRIC_SELECTED_DEV_EUI must be exactly 16 hexadecimal characters');
    return null;
}
const fabricSelected = devEui === fabricSelectedDevEui;
// Append fabricSelected as parameter $25 after the existing metrics parameter.
```

Verify the deployed function has exactly 25 parameters during commissioning. **Stop here** if the parameter count or position differs; an incorrect parameter position can queue the wrong event or break the atomic SQL statement.

PostgreSQL executes a data-modifying CTE once as part of the surrounding statement. If the statement fails, the telemetry row, measurements, and outbox insert roll back together.

### Step 4A: Switch a fresh staging event to v2 only after gateway verification exists

Do **not** change the v1 CTE to v2 until all of these exist and pass their own tests:

```text
reviewed gateway journal implementation
reviewed evidence-ingest implementation
reviewed read-only gateway MQTT evidence collector
reviewed evidence verifier
pinned trusted decoder
reviewed telemetry-attestation-v2 canonicalization test vector
gateway_evidence database schema/result table
```

For a fresh staging event, the enqueue statement may then select:

```sql
    'telemetry-attestation-v2'
```

instead of v1. Do not reuse the same outbox `event_key` to create both v1 and v2 records; the stable key is unique. Decide which schema the pilot event represents before enqueue.

Node-RED still only enqueues the work. It does not insert or update the verifier status.

## Step 5: Claim work with a lease

The adapter must not hold a database transaction open while waiting for Fabric. Claim one row, commit the claim, then perform the network call.

Use a short transaction with a statement equivalent to:

```sql
WITH candidate AS (
  SELECT outbox_id
  FROM telemetry.fabric_outbox
  WHERE
    (status IN ('pending','failed') AND next_attempt_at <= now())
    OR
    (status = 'processing' AND lease_expires_at <= now())
  ORDER BY
    COALESCE(lease_expires_at, next_attempt_at),
    outbox_id
  FOR UPDATE SKIP LOCKED
  LIMIT 1
)
UPDATE telemetry.fabric_outbox AS o
SET
  status = 'processing',
  worker_id = $1,
  processing_started_at = now(),
  lease_expires_at = now() + $2::interval,
  attempts = attempts + 1,
  updated_at = now()
FROM candidate AS c
WHERE o.outbox_id = c.outbox_id
RETURNING o.*;
```

Use a configured worker ID and lease interval. Commit this transaction before contacting Fabric.

The query above is the v1-compatible baseline because it does not depend on a gateway-evidence table. **After v2 is enabled**, replace the candidate eligibility rule with the schema-aware gate:

```sql
WITH candidate AS (
  SELECT o.outbox_id
  FROM telemetry.fabric_outbox AS o
  WHERE (
      (o.status IN ('pending','failed') AND o.next_attempt_at <= now())
      OR (o.status = 'processing' AND o.lease_expires_at <= now())
    )
    AND (
      o.schema_version <> 'telemetry-attestation-v2'
      OR EXISTS (
        SELECT 1
        FROM gateway_evidence.event_verification AS v
        WHERE v.source_event_key = o.source_event_key
          AND v.observed_at = o.observed_at
          AND v.status = 'verified'
      )
    )
  ORDER BY COALESCE(o.lease_expires_at, o.next_attempt_at), o.outbox_id
  FOR UPDATE OF o SKIP LOCKED
  LIMIT 1
)
UPDATE telemetry.fabric_outbox AS o
SET status = 'processing',
    worker_id = $1,
    processing_started_at = now(),
    lease_expires_at = now() + $2::interval,
    attempts = attempts + 1,
    updated_at = now()
FROM candidate AS c
WHERE o.outbox_id = c.outbox_id
RETURNING o.*;
```

This prevents a v2 row from reaching OpenBao merely because it is `pending`. Build a separate operator query/dashboard for v2 rows blocked by `pending`, `evidence_gap`, or `integrity_failure`; otherwise an evidence incident can look like an ordinary quiet queue.

The lease must be longer than the normal submission-and-commit timeout but short enough for controlled crash recovery. Do not invent one fixed interval for every environment; measure normal and worst-case commit latency first.

State updates must clear the claim fields:

```text
confirmed          -> set transaction ID and committed_at; clear worker and lease
failed             -> set next_attempt_at and error category; clear worker and lease
submitted_unknown  -> preserve transaction evidence; clear worker and lease; reconcile before retry
dead_letter        -> preserve error and operator action; clear worker and lease
```

An expired `processing` lease can be reclaimed. A `submitted_unknown` row must not be picked up by the normal retry query.

## Step 6: Implement the adapter contract

Follow [`server/integrations/hyperledger-fabric/05-application-implementation.md`](../integrations/hyperledger-fabric/05-application-implementation.md).

Load source evidence using both the preserved source event key and observation time. The adapter query must be equivalent to this and must return exactly one row:

```sql
SELECT
  o.outbox_id,
  o.event_key AS fabric_event_key,
  o.source_event_key,
  o.observed_at,
  o.event_type,
  o.schema_version,
  u.received_at,
  u.application_id,
  u.device_id,
  u.device_model,
  u.decoder_version,
  u.dev_eui,
  u.gateway_id,
  u.region,
  u.f_port,
  u.f_cnt,
  u.confirmed,
  u.raw_data,
  u.payload_json
FROM telemetry.fabric_outbox AS o
JOIN telemetry.uplinks AS u
  ON u.event_key = o.source_event_key
 AND u.time = o.observed_at
WHERE o.outbox_id = $1;
```

Zero rows means the application source evidence is missing. More than one row means the application source uniqueness assumptions are broken. Either result is a permanent stop for that event; do not guess which telemetry row to attest.

For v2, the implementation must additionally load exactly one matching `gateway_evidence.event_verification` row with `status='verified'` and project the fixed `gateway_evidence` fields documented in the reusable data contract. A verifier row is never accepted from Node-RED parameters or MQTT message properties.

Required behavior:

1. claim one eligible row using the lease transaction and commit the claim;
2. reject an unsupported `schema_version` before sealing or submitting;
3. for v2, require the matching gateway-evidence result to be `verified` before sealing; defer pending, follow the gap policy for `evidence_gap`, and treat `integrity_failure` as a permanent security conflict;
4. for an unsealed row, load the fixed v1 source projection or the fixed v2 application + verifier-owned gateway-evidence projection;
5. build the exact schema-specific canonical evidence object documented in `04-data-contract-and-chaincode.md`;
5. canonicalize with the pinned RFC 8785 JCS implementation;
6. encode the canonical JSON as UTF-8 and calculate SHA-256 over those exact bytes;
7. authenticate to OpenBao using the adapter AppRole credentials and ask Transit `lorawan-evidence/sha2-256` to sign `Base64(canonical UTF-8 bytes)` with `prehashed=false` and ASN.1 ECDSA marshaling;
8. preserve the complete versioned OpenBao signature, derive `openbao:transit:lorawan-evidence:v<version>` from its version tag, and store `canonical_json`, `digest_sha256`, `evidence_signature_alg`, `evidence_signing_key_id`, `evidence_signature`, and `evidence_sealed_at` together before the first Fabric network call;
9. re-read the persisted seal, recompute its digest, verify that the signature version matches the stored KMS key ID, and require OpenBao Transit verify to return `valid=true` for the exact stored canonical bytes;
10. for an already sealed row, verify the stored seal and **do not rebuild it from current telemetry**;
11. submit through Fabric Gateway using the stable event key and the already-verified seal metadata;
12. wait for valid commit status and mark `confirmed` only after a valid commit;
13. move an uncertain post-submission result to `submitted_unknown`;
14. query the ledger before deciding whether an unknown result may be retried;
15. verify the same stored seal before every retry or reconciliation request;
16. use bounded exponential backoff with jitter for transient failures without changing the event key or seal;
17. cap retry delay and maximum attempts using reviewed configuration;
18. move invalid local seals, conflicting duplicate digests, permanent failures, or exhausted failures to `dead_letter` or the implementation's explicit security-conflict path.

For transient failures, use a delay equivalent to `min(MAX_DELAY, BASE_DELAY * 2^attempt) + jitter`, with configured bounds rather than an infinite retry loop. Authorization errors, invalid schema, conflicting duplicate digests, and other permanent failures should not be retried as transient network errors.

`CreateAttestation`, `ReadAttestation`, and the other contract names in these guides are examples of project contract names, not built-in Fabric functions. Replace them with the exact function names supplied by the Fabric team.

Do not place Fabric signing code, the Fabric client private key, OpenBao AppRole credentials, OpenBao root token, or OpenBao unseal/recovery material in Node-RED. The evidence private key remains inside OpenBao and must never be mounted into the adapter.

### Required read-only verification mode for the dissertation integrity test

The reviewed adapter implementation, or a companion tool built from the **same v1 canonicalization library**, must provide a read-only test mode that can:

1. load one selected current `telemetry.uplinks` source row using `source_event_key` + `observed_at`;
2. build the normal `telemetry-attestation-v1` canonical evidence projection;
3. apply the same timestamp/null rules and RFC 8785 canonicalization as production;
4. calculate and print/return the current-source SHA-256;
5. **not** request a new OpenBao signature;
6. **not** update the outbox;
7. **not** submit anything to Fabric.

This mode is required by [Execution 05 - Data Integrity](../../../test/execution/05-data-integrity.md) to prove that a source row modified after its original Fabric commitment no longer reconstructs to the original Fabric digest. It must pass the same fixed v1 canonicalization test vector before use. Do not substitute `sha256sum` over arbitrary PostgreSQL JSON; that would test a different byte representation from the production evidence contract.

The exact CLI/API name is implementation-defined. Do not begin counted post-storage integrity trials until this read-only verification behavior exists and has been reviewed.

## Step 7: Prepare the adapter image, runtime identity, and OpenBao credentials

**Stop here if the adapter source or reviewed image does not exist.** The Compose example below cannot create the missing implementation.

Set the exact reviewed image reference and inspect its declared user. Keep the image reference with the adapter configuration because the runtime UID/GID and application behavior must match during restore:

```bash
export FABRIC_ADAPTER_IMAGE='<PINNED_FABRIC_ADAPTER_IMAGE>'
docker pull "$FABRIC_ADAPTER_IMAGE"
docker image inspect --format '{{json .Config.User}}' "$FABRIC_ADAPTER_IMAGE"
```

Obtain the numeric runtime UID and GID from the reviewed image build or its documentation. Do not guess them. When the image has a POSIX shell and the runtime user is resolvable inside the image, confirm the numeric values independently:

```bash
docker run --rm --entrypoint sh "$FABRIC_ADAPTER_IMAGE" -c \
  'printf "uid=%s gid=%s\n" "$(id -u)" "$(id -g)"'
```

The displayed UID/GID must match the reviewed image documentation. **Stop here** on a mismatch; file permissions for both private identities depend on the real runtime group.

Set the reviewed numeric values in the current administration shell before running the ownership commands below:

```bash
export FABRIC_ADAPTER_UID='<NUMERIC_RUNTIME_UID>'
export FABRIC_ADAPTER_GID='<NUMERIC_RUNTIME_GID>'
case "$FABRIC_ADAPTER_UID" in ''|*[!0-9]*) echo 'FABRIC_ADAPTER_UID must be numeric'; exit 1 ;; esac
case "$FABRIC_ADAPTER_GID" in ''|*[!0-9]*) echo 'FABRIC_ADAPTER_GID must be numeric'; exit 1 ;; esac
printf 'adapter uid=%s gid=%s\n' "$FABRIC_ADAPTER_UID" "$FABRIC_ADAPTER_GID"
```

### Prepare the OpenBao AppRole files for the adapter runtime

Complete [Fabric 1B. Deploy the OpenBao Evidence KMS](01-deploy-openbao-kms.md) first. That procedure creates:

```text
/opt/lorawan-lab/secrets/openbao-approle/role_id
/opt/lorawan-lab/secrets/openbao-approle/secret_id
```

OpenBao owns the P-256 evidence private key. **There must be no `/run/evidence-signing/private.pem` and no evidence private-key file anywhere in the adapter configuration.**

Change only the AppRole-file group so the reviewed adapter runtime can read the credentials:

```bash
sudo chown -R root:"${FABRIC_ADAPTER_GID}" \
  /opt/lorawan-lab/secrets/openbao-approle
sudo chmod 0750 /opt/lorawan-lab/secrets/openbao-approle
sudo chmod 0440 /opt/lorawan-lab/secrets/openbao-approle/role_id
sudo chmod 0440 /opt/lorawan-lab/secrets/openbao-approle/secret_id
sudo find /opt/lorawan-lab/secrets/openbao-approle -maxdepth 1 \
  -printf '%m %u:%g %p\n'
```

Required result: the directory is `750`; both files are owner/group read-only; the group equals `${FABRIC_ADAPTER_GID}`. Stop if either file is writable by the adapter group or readable by unrelated users.

Verify the KMS itself is unsealed before starting the adapter:

```bash
docker compose exec \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  openbao bao status
```

Pass only when `Initialized` is true and `Sealed` is false. Do not use the OpenBao root token for normal adapter startup.

Add protected values to `/opt/lorawan-lab/.env`:

```dotenv
FABRIC_ADAPTER_IMAGE=<PINNED_FABRIC_ADAPTER_IMAGE>
FABRIC_ADAPTER_UID=<NUMERIC_RUNTIME_UID>
FABRIC_ADAPTER_GID=<NUMERIC_RUNTIME_GID>
FABRIC_ADAPTER_DB_PASSWORD=<REPLACE_WITH_FABRIC_ADAPTER_DB_PASSWORD>
FABRIC_MSP_ID=<FABRIC_MSP_ID>
FABRIC_CHANNEL=<FABRIC_CHANNEL_NAME>
FABRIC_CHAINCODE=<FABRIC_CHAINCODE_NAME>
FABRIC_CONTRACT=<FABRIC_CONTRACT_NAME>
EVIDENCE_SIGNATURE_ALG=OPENBAO-TRANSIT-ECDSA-P256-SHA2-256
OPENBAO_ADDR=http://openbao:8200
OPENBAO_TRANSIT_MOUNT=transit
OPENBAO_TRANSIT_KEY=lorawan-evidence
```

`OPENBAO_ADDR=http://openbao:8200` is allowed only in this one-VM lab because the endpoint exists solely on the Docker-internal `kms` network. Production must use the approved HTTPS KMS endpoint and trusted TLS configuration. Do **not** put the AppRole RoleID, SecretID, runtime OpenBao token, root token, or unseal shares into `.env`.

```bash
chmod 600 /opt/lorawan-lab/.env
```

Make the imported lab identity readable by that numeric group and no broader:

```bash
sudo chown -R root:${FABRIC_ADAPTER_GID} /opt/fabric-adapter/crypto
sudo find /opt/fabric-adapter/crypto -type d -exec chmod 750 {} \;
sudo find /opt/fabric-adapter/crypto -type f -exec chmod 640 {} \;
```

## Step 8: Add the adapter service

```yaml
  fabric-adapter:
    image: ${FABRIC_ADAPTER_IMAGE}
    user: "${FABRIC_ADAPTER_UID}:${FABRIC_ADAPTER_GID}"
    restart: unless-stopped
    cpus: "${LAB_FABRIC_ADAPTER_CPUS}"
    mem_limit: "${LAB_FABRIC_ADAPTER_MEM}"
    environment:
      DB_HOST: telemetry-db
      DB_PORT: "5432"
      DB_NAME: lorawan_telemetry
      DB_USER: fabric_adapter
      DB_PASSWORD: ${FABRIC_ADAPTER_DB_PASSWORD}
      FABRIC_GATEWAY_ENDPOINT: <FABRIC_GATEWAY_ENDPOINT>
      FABRIC_TLS_SERVER_NAME: <FABRIC_TLS_SERVER_NAME>
      FABRIC_TLS_ROOT_CERT: /run/fabric/tls/ca.crt
      FABRIC_MSP_ID: ${FABRIC_MSP_ID}
      FABRIC_CERT_PATH: /run/fabric/identity/cert.pem
      FABRIC_KEY_PATH: /run/fabric/identity/key.pem
      FABRIC_CHANNEL: ${FABRIC_CHANNEL}
      FABRIC_CHAINCODE: ${FABRIC_CHAINCODE}
      FABRIC_CONTRACT: ${FABRIC_CONTRACT}
      FABRIC_SUBMIT_FUNCTION: <FABRIC_SUBMIT_FUNCTION>
      FABRIC_QUERY_FUNCTION: <FABRIC_QUERY_FUNCTION>
      EVIDENCE_SIGNATURE_ALG: ${EVIDENCE_SIGNATURE_ALG}
      OPENBAO_ADDR: ${OPENBAO_ADDR}
      OPENBAO_TRANSIT_MOUNT: ${OPENBAO_TRANSIT_MOUNT}
      OPENBAO_TRANSIT_KEY: ${OPENBAO_TRANSIT_KEY}
      OPENBAO_APPROLE_ROLE_ID_FILE: /run/openbao-approle/role_id
      OPENBAO_APPROLE_SECRET_ID_FILE: /run/openbao-approle/secret_id
    volumes:
      - /opt/fabric-adapter/crypto:/run/fabric:ro
      - /opt/lorawan-lab/secrets/openbao-approle:/run/openbao-approle:ro
    depends_on:
      telemetry-db:
        condition: service_healthy
      openbao:
        condition: service_started
    networks: [telemetry, application, kms]
```

Do not publish an adapter port unless a health endpoint is part of the reviewed implementation. A health endpoint must expose no credentials, payloads, connection profile, or private-key path.

## Step 9: Verify permissions and startup

```bash
sudo find /opt/fabric-adapter/crypto -maxdepth 3 -printf '%m %u:%g %p\n'
sudo find /opt/lorawan-lab/secrets/openbao-approle -maxdepth 1 -printf '%m %u:%g %p\n'
docker compose config --quiet
docker compose up -d fabric-adapter
docker compose ps fabric-adapter
docker compose logs --since=5m --tail=200 fabric-adapter
```

Verify inside the running container that the configured UID can read the Fabric client identity and the AppRole files without printing their contents:

```bash
docker compose exec fabric-adapter sh -c \
  'id && test -r /run/fabric/identity/key.pem && test -r /run/fabric/identity/cert.pem && test -r /run/fabric/tls/ca.crt && test -r /run/openbao-approle/role_id && test -r /run/openbao-approle/secret_id && test ! -e /run/evidence-signing/private.pem'
```

Run that command only when the reviewed image contains a POSIX shell. Otherwise use the image's documented diagnostic command.

Startup must fail closed when AppRole login, Transit sign/verify, or the RFC 8785 test vector fails. Logs must not print the Fabric private key, AppRole SecretID, OpenBao client token, database password, or complete raw payload. A running container is not proof of a valid KMS seal or Fabric commit; complete the next guide.

### Recorded cloud Fabric outbox database preflight - 2026-08-27

**PASS / READ ONLY.** The ulc-03-driven preflight dynamically found exactly one Patroni leader: `ulc-01` / `10.104.0.2`; `ulc-02` and `ulc-03` were replicas. All three Spilo containers were running with `RestartCount=0`, all three members reported PostgreSQL `18.6`, `lorawan_telemetry` remained owned by `telemetry_admin`, schema `telemetry` remained owned by `telemetry_admin`, and TimescaleDB remained `2.29.2`. Each member saw all six commissioned telemetry objects and exactly the two telemetry hypertables `measurements,uplinks`.

`telemetry.fabric_outbox` was absent on all three members. `fabric_adapter` remained a LOGIN role with a SCRAM verifier, but its pre-outbox object-access boundary was still closed: no `USAGE` on schema `telemetry` and no `SELECT` on `uplinks`, `measurements`, or `device_registry`. The operator wrapper returned `FABRIC_OUTBOX_READONLY_PREFLIGHT=PASS`, `FABRIC_OUTBOX_PREFLIGHT_OPERATOR_EXIT=0`, and the ulc-03 login shell survived. The repeated container `LC_ALL=en_US.utf-8` / Perl locale warning remains the previously recorded non-blocking hygiene issue.

Decision: the outbox migration starts from a clean first-install state, so do not run legacy-row repair logic. Before mutation, revalidate the preserved 2026-08-27 local logical backup under the current test-scope backup exception. Then create the ordinary PostgreSQL outbox table, exact constraints, worker indexes, one-way immutability trigger, and documented column-level ACLs in one controlled primary transaction; verify replication to both replicas before enabling Node-RED outbox enqueue. Do not deploy or issue runtime credentials for the still-unimplemented Fabric adapter image.

### Recorded corrected cloud backup/catalog gate - 2026-08-27

**PASS / READ ONLY.** The corrected cloud gate used PostgreSQL 18.6 `pg_restore` inside the running local `spilo` container rather than the host Ubuntu `pg_wrapper`. All preserved Phase 13A checksums passed; the `lorawan_telemetry.dump` catalog parsed successfully with 129 entries; the catalog had no `fabric_outbox`; and the live database still had no `telemetry.fabric_outbox`. No database mutation occurred. `FABRIC_OUTBOX_CORRECTED_PREFLIGHT=PASS`; `FABRIC_OUTBOX_CORRECTED_PREFLIGHT_EXIT=0`. The next cloud action is the first real migration on the dynamically discovered Patroni primary. Do not repeat the backup/catalog gate unless the preserved dump or its checksum files change.

### PostgreSQL 18 constraint-catalog verification note

Cloud production currently runs PostgreSQL 18.6. PostgreSQL 18 stores column `NOT NULL` specifications as `pg_constraint` rows with `contype='n'`. Therefore a first-install verifier must **not** assert that `SELECT count(*) FROM pg_constraint WHERE conrelid='telemetry.fabric_outbox'::regclass` equals six. For the current 25-column baseline, the expected catalog result is eleven `n` rows plus six non-`n` constraints, for seventeen total rows. Verify the intended application constraint set using `contype <> 'n'` (or the explicit `c/p/u` types) and require exactly:

```text
fabric_outbox_digest_ck
fabric_outbox_event_key_key
fabric_outbox_pkey
fabric_outbox_processing_ck
fabric_outbox_seal_ck
fabric_outbox_status_ck
```

A post-commit wrapper failure caused only by the old six-total-row assertion is a harness failure. Do not rerun `CREATE TABLE` after `OUTBOX_DDL_ACL_TRANSACTION=PASS`; continue with read-only structure/replication validation and the rollback-only ACL/immutability probes.

### Recorded cloud Fabric outbox schema commissioning - 2026-08-27

**COMPLETE / PASS.** The outbox was created once on the active Patroni primary and replicated to all three PostgreSQL members. PostgreSQL 18 reports `17` total `pg_constraint` rows for this table because `11` column `NOT NULL` rules are stored as `contype='n'`; the six intended non-NOT-NULL constraints are exactly `fabric_outbox_digest_ck`, `fabric_outbox_event_key_key`, `fabric_outbox_pkey`, `fabric_outbox_processing_ck`, `fabric_outbox_seal_ck`, and `fabric_outbox_status_ck`. The table has exactly 25 columns, three documented worker indexes, one `fabric_outbox_immutability_trg`, and is not a Timescale hypertable. Table/function ownership remains `telemetry_admin`.

ACL acceptance passed on all three members. `fabric_adapter` can read `telemetry.uplinks`, `telemetry.measurements`, and `telemetry.fabric_outbox`; it cannot insert/delete outbox rows and can update only the documented worker, seal, Fabric-result, error, and `updated_at` columns. `telemetry_writer` can enqueue/read and use the identity sequence but cannot update; `telemetry_reader` is read-only. Rollback-only functional probes proved writer enqueue, allowed adapter state update, denied adapter source-identity update, source-identity trigger enforcement, completed-evidence-seal immutability, and zero persisted commissioning rows.

Cloud status: `FABRIC_OUTBOX_SCHEMA_COMMISSIONING=PASS`. Do not recreate the table. Keep Node-RED outbox enqueue disabled until Phase 12A. The Fabric adapter runtime remains blocked until a reviewed implementation/image exists.
