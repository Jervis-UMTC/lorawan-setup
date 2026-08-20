# 3. Integration Architecture and Reliability

The most important architecture decision is whether the application submits every uplink directly to Fabric or whether it first stores accepted telemetry and submits selected attestations asynchronously.

## 3.1 Recommended pattern: asynchronous adapter

Use this pattern on the application server; the Raspberry Pi gateway never runs Fabric or OpenBao.

Historical v1 remains:

~~~text
ChirpStack application uplink
  -> Node-RED validates and normalizes
  -> TimescaleDB stores telemetry
  -> selected v1 outbox row
  -> Fabric adapter
  -> OpenBao seal
  -> Fabric
~~~

The preferred gateway-verified v2 path adds a verification gate **before sealing**:

~~~text
gateway journal -----------+
                           |
remote gateway MQTT copy --+--> evidence verifier
                           |       |
ChirpStack app event -------+       +-> trusted decoder
                                   +-> compare TimescaleDB
                                   |
                              status = verified
                                   |
                                   v
                            selected v2 outbox row
                                   |
                            Fabric adapter
                                   |
                     canonicalize + hash + OpenBao seal
                                   |
                                Fabric
~~~

Advantages:

- a Fabric outage does not stop sensor ingestion;
- retries can be controlled and audited;
- raw telemetry remains queryable in TimescaleDB;
- the ledger receives only business-significant records;
- the adapter can run on a stronger, protected host;
- duplicate submissions can be made idempotent.

The adapter is normally a separate service owned by the application or Fabric integration team. Do not place Fabric private keys inside a Node-RED flow unless the security team explicitly accepts that design.

Keep the component boundary explicit:

```text
Fabric outbox = PostgreSQL data/state
  "this accepted event still needs Fabric work"

Fabric adapter = running worker/service
  "claim the durable job, seal it through KMS, submit it, and update the job state"
```

The outbox must survive an adapter crash, Fabric outage, KMS outage, and—for v2—an evidence-verification delay. The adapter is replaceable compute; losing the adapter process must not lose the queued event.

For v2, `pending` gateway verification is not an adapter error. The row simply remains ineligible for sealing. `evidence_gap` follows the approved incomplete-evidence policy. `integrity_failure` is a security conflict and must not be retried as though it were a Fabric outage.

For production KMS availability, the adapter uses **one stable OpenBao service endpoint**, not one hard-coded OpenBao node:

```text
Fabric adapter
      |
      v
https://openbao-kms.internal:8200
      |
      +--> OpenBao voter / active
      +--> OpenBao voter / standby
      +--> OpenBao voter / standby
      +--> additional voters for the production target
```

OpenBao Integrated Storage owns Raft replication and leader election. A single KMS node loss should therefore be hidden from the adapter. Only loss of KMS quorum, all reachable nodes becoming sealed, or loss of the stable service endpoint should force the adapter into KMS backoff. Telemetry ingestion still continues because the durable outbox separates it from the adapter.

## 3.2 Direct submission pattern

Direct submission from Node-RED can be acceptable for a small demonstration:

~~~text
MQTT uplink
  -> Node-RED
  -> HTTPS integration API
  -> Fabric adapter
  -> Fabric Gateway
~~~

Do not make Node-RED speak directly to a peer using low-level Fabric administration commands. Put a narrow API in front of Fabric so that identity use, validation, rate limiting, retries, and audit logging are controlled in one place.

## 3.3 What should be submitted?

Choose one of these policies:

| Policy | Fabric volume | Best use |
|---|---:|---|
| Every reading | Very high | Small pilot with few devices |
| Time-window digest | Low | Proof that a historical set was preserved |
| Threshold exception | Low | Compliance or alarm evidence |
| Business transition only | Very low | Custody, inspection, maintenance, ownership |
| Daily or hourly summary | Low | Reporting and settlement evidence |

For the current agricultural pilot, use a time-window digest or exception attestation rather than every temperature sample. For a port, use the ledger for custody, inspection, exception, or approval events and keep high-volume environmental telemetry off-chain.

## 3.4 Optional outbox table

If the application team chooses the outbox pattern, treat the SQL below as a versioned database migration, not an ad hoc console command. Verify the exact database and schema, create and validate a backup, store the migration version with the schema, and define rollback before creating a dedicated table:

~~~sql
CREATE TABLE IF NOT EXISTS telemetry.fabric_outbox (
    outbox_id           BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    event_key           TEXT NOT NULL UNIQUE,
    source_event_key    TEXT NOT NULL,
    observed_at         TIMESTAMPTZ NOT NULL,
    event_type          TEXT NOT NULL,
    schema_version      TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'pending',
    attempts            INTEGER NOT NULL DEFAULT 0,
    next_attempt_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    worker_id           TEXT,
    processing_started_at TIMESTAMPTZ,
    lease_expires_at    TIMESTAMPTZ,
    canonical_json      TEXT,
    digest_sha256       TEXT,
    evidence_signature_alg TEXT,
    evidence_signing_key_id TEXT,
    evidence_signature TEXT,
    evidence_sealed_at  TIMESTAMPTZ,
    fabric_tx_id        TEXT,
    submitted_at        TIMESTAMPTZ,
    committed_at        TIMESTAMPTZ,
    last_error_category TEXT,
    last_error          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fabric_outbox_status_ck CHECK (
      status IN (
        'pending', 'processing', 'submitted_unknown',
        'confirmed', 'failed', 'dead_letter'
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
~~~

Node-RED creates the source reference and event identity in the same transaction as the telemetry insert. For v1, the adapter may then follow the historical application-only source projection. For v2, the adapter must first prove that exactly one matching `gateway_evidence.event_verification` row exists with `status='verified'`; the verifier, not Node-RED or the adapter, owns that status.

Only after the schema-specific source is eligible does the adapter produce one deterministic `canonical_json`, calculate `digest_sha256`, and ask OpenBao Transit to sign the **exact UTF-8 bytes of `canonical_json`** using the non-exportable `lorawan-evidence` P-256 key. The adapter stores the complete OpenBao versioned signature and its derived KMS key-version ID before its first Fabric network call.

The seal fields have one purpose: detect a later attempt to rewrite a pending event while Fabric is unavailable. The deployable baseline combines four controls: the adapter cannot update stored telemetry, its outbox UPDATE grant excludes source-identity columns, a one-way trigger permits an unsealed row to become sealed once but rejects later seal replacement, and the evidence private key is held by OpenBao rather than in the database or adapter filesystem. The adapter recomputes the digest and requires OpenBao Transit verification before every submission or retry.

These controls are meaningful against ordinary application/database credentials, database-only compromise, and accidental corruption. They do **not** make PostgreSQL or the application host an immutable trust boundary: a database superuser or host root can bypass grants/triggers, and a compromised adapter credential with Transit `sign` permission can request signatures over attacker-chosen bytes. Production therefore runs OpenBao/KMS on independently protected infrastructure, preserves KMS audit/recovery evidence, and uses stronger external append-only anchoring or a signing service that enforces event-level policy when privileged multi-system compromise is in scope.

If `telemetry.fabric_outbox` already exists, `CREATE TABLE IF NOT EXISTS` will not add the seal columns. Apply the following as a reviewed schema migration before enabling a seal-aware adapter:

~~~sql
ALTER TABLE telemetry.fabric_outbox
    ADD COLUMN IF NOT EXISTS evidence_signature_alg TEXT,
    ADD COLUMN IF NOT EXISTS evidence_signing_key_id TEXT,
    ADD COLUMN IF NOT EXISTS evidence_signature TEXT,
    ADD COLUMN IF NOT EXISTS evidence_sealed_at TIMESTAMPTZ;
~~~

Before adding the check constraint, verify that no partially populated seal exists:

~~~sql
SELECT outbox_id, event_key
FROM telemetry.fabric_outbox
WHERE canonical_json IS NOT NULL
  AND (
    digest_sha256 IS NULL
    OR evidence_signature_alg IS NULL
    OR evidence_signing_key_id IS NULL
    OR evidence_signature IS NULL
    OR evidence_sealed_at IS NULL
  );
~~~

The query must return zero rows. Also reject legacy or malformed complete-looking seals before migration:

~~~sql
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
~~~

This second query must also return zero rows. Do not re-sign an old row merely to satisfy the new schema. Preserve legacy evidence and migrate it only through an explicit correction/re-attestation procedure.

Then add the constraint once:

~~~sql
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
~~~

Add an index for the worker:

~~~sql
CREATE INDEX IF NOT EXISTS fabric_outbox_pending_idx
    ON telemetry.fabric_outbox (next_attempt_at, outbox_id)
    WHERE status IN ('pending', 'failed');

CREATE INDEX IF NOT EXISTS fabric_outbox_processing_lease_idx
    ON telemetry.fabric_outbox (lease_expires_at, outbox_id)
    WHERE status = 'processing';
~~~

The table is an integration queue, not a replacement for TimescaleDB. Apply the column-level adapter grants and `telemetry.enforce_fabric_outbox_immutability()` trigger from the executable lab guide before relying on the one-time seal property. The worker must claim a row in a short transaction using `FOR UPDATE SKIP LOCKED`, write a worker ID and lease expiry, and commit before contacting Fabric. An expired processing lease provides crash recovery. Do not hold a PostgreSQL row lock while waiting for endorsement or commit status.

## 3.4A Schema-aware worker eligibility

Do not let a generic pending-row query bypass the gateway-evidence gate.

A claim query must be equivalent to:

~~~sql
...
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
...
~~~

This preserves v1 behavior while preventing v2 sealing before verification.

A separate reconciliation/triage query should surface v2 rows whose evidence state becomes `evidence_gap` or `integrity_failure`; leaving those rows invisible in `pending` forever is not an operational solution.

## 3.5 Retry and idempotency rules

Use at-least-once delivery with duplicate protection and a one-time evidence seal:

1. Derive `event_key` from the source event, not from a retry counter.
2. Claim work with an expiring lease and reclaim only expired processing rows.
3. If the row is v2, re-check that its matching gateway-evidence result is still exactly one `verified` record before any new seal is created; if the row is v1, preserve the historical v1 source rule.
4. If the row has no seal, load the approved schema-specific source evidence and create one deterministic canonical JSON representation.
5. Calculate SHA-256 from the exact UTF-8 bytes of that canonical representation.
6. Ask OpenBao Transit `lorawan-evidence/sha2-256` to sign `Base64(canonical UTF-8 bytes)` with `prehashed=false`, preserve the complete versioned response signature, derive `openbao:transit:lorawan-evidence:v<version>`, and persist the complete seal in one database update.
7. If the row is already sealed, **recompute the stored digest, verify the signature-version/key-ID binding, and require OpenBao Transit verify to return valid; never silently regenerate the canonical evidence from mutable telemetry on a retry.** The persisted seal becomes the retry source of truth even if later operational evidence state changes; such a change must trigger incident review rather than silent resealing.
8. Use `event_key` as the chaincode state key or a unique chaincode index.
9. If Fabric reports an already-existing key, query it and compare the digest.
10. Mark the outbox row confirmed only after commit status is valid.
11. Send invalid local seals, gateway-evidence conflicts, permanent failures, and conflicting duplicate digests to `dead_letter` or a dedicated security-conflict path with the reason and operator action.

Never create a new ledger event on every retry simply because the first response timed out. A network timeout does not prove that the transaction was not committed. Move the local record to an explicit `submitted_unknown` state, query by stable event key or transaction ID, and escalate conflicting evidence rather than guessing.

## 3.6 Time and ordering

Keep separate timestamps:

- observed_at: the sensor or ChirpStack event time;
- received_at: when the platform accepted the MQTT event;
- submitted_at: when the adapter submitted the Fabric transaction;
- committed_at: when the adapter received the Fabric commit result.

Fabric transaction order is not a replacement for sensor observation time. Queries must preserve both business time and ledger time.

## 3.7 Deployment boundary

For the Docker lab path, the Raspberry Pi performs gateway functions only. ChirpStack, Node-RED, TimescaleDB, Grafana, OpenBao, and the Fabric adapter run on the single lab server VM. OpenBao is included there to simulate the KMS API, key versioning, policy, seal/unseal, outage, and backup/recovery flow; sharing one VM does not provide production host isolation. Peers, orderers, Fabric CAs, channels, and deployed chaincode belong to the externally operated Fabric network and are not created by this project.

The production adapter belongs on a protected application host. The gateway evidence verifier should run under a different identity and must not possess OpenBao sign authorization or the Fabric client key. This separation prevents the component that declares source evidence valid from also being the component that cryptographically seals and submits it.

OpenBao/KMS must not be a single-node production dependency: use Integrated Storage (Raft) across separate hosts/failure domains, one stable private TLS service endpoint, and enough unsealed voting members to retain quorum. OpenBao recommends five production servers; five voters tolerate two failures, while three voters tolerate one. The application never selects the Raft leader itself.

Require stable power/network, protected machine-authentication credentials, monitored service supervision, controlled access to both OpenBao and the Fabric Gateway, KMS audit/recovery procedures, Raft peer/quorum monitoring, independent snapshots/backups, and a tested active-node failover procedure. With Shamir sealing, every HA member must be unsealed after restart before it can serve as a standby. If auto-unseal is used, protect that unseal dependency independently because losing it can prevent the cluster from recovering.

Do not install peers, orderers, Fabric CAs, or Fabric network administration tooling on the LoRaWAN gateway or lab server. Mount only the dedicated client identity required by the adapter, using the certificate and key supplied for this integration.

Next: [04-data-contract-and-chaincode.md](04-data-contract-and-chaincode.md)
