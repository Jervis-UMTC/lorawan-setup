# PostgreSQL / Patroni / TimescaleDB — Operator Manual

## What this technology does

PostgreSQL is the durable relational state layer. Patroni orchestrates one writable PostgreSQL leader plus replicas using etcd. TimescaleDB is an extension inside the `lorawan_telemetry` database; it is **not** a separate server.

## Current commissioned baseline

- ULC-01/02/03 each host one Patroni/PostgreSQL member.
- Current commissioned PostgreSQL build: 18.6.
- Current TimescaleDB extension: 2.29.2.
- One writable leader, two streaming replicas in normal state.
- `chirpstack` database stores ChirpStack state.
- `lorawan_telemetry` stores telemetry, measurements, Fabric outbox, and gateway-evidence metadata.
- Normal clients use PgBouncer/HAProxy rather than pinning the current leader.

## The normal client path

```text
application
-> pgbouncer.internal.lorawan.com:6432
-> local PgBouncer
-> local HAProxy primary route :15432
-> current Patroni leader :5432
```

Do not bypass this path in an application configuration just because you know today's leader IP.

## Step 1 — Establish the authoritative Patroni topology

On any database host:

```bash
sudo docker exec -e LC_ALL=C spilo patronictl -c /run/postgres.yml list
```

**PASS means:** exactly one member is Leader and the other intended members are running replicas without a critical lag/error state.

Do not use an old document to decide which node should be leader. The live Patroni result wins.

## Step 2 — Confirm local PostgreSQL role when needed

On a specific member, use the approved local/admin connection method and run:

```sql
SELECT inet_server_addr(), pg_is_in_recovery();
```

Interpretation:

- `pg_is_in_recovery() = false` -> writable primary/leader candidate;
- `true` -> replica.

Never run a write/cleanup script on a node until you know whether it is the current authoritative leader and whether the script should use the normal HA route instead.

## Step 3 — Verify the normal application route

Use a protected, least-privilege test role/DSN already provisioned on the host. Do **not** paste a password into the command history.

The important SQL is:

```sql
SELECT now() AT TIME ZONE 'UTC' AS utc_time,
       inet_server_addr(),
       pg_is_in_recovery();
```

**PASS means:** the connection through PgBouncer/HAProxy succeeds with TLS verification and lands on `pg_is_in_recovery() = false` for a primary-route client.

If direct member access works but the normal route fails, troubleshoot PgBouncer/HAProxy before changing Patroni.

## Step 4 — Verify both logical databases exist

Through the approved admin/read-only path:

```sql
SELECT datname
FROM pg_database
WHERE datname IN ('chirpstack', 'lorawan_telemetry')
ORDER BY datname;
```

Both databases must exist.

## Step 5 — Verify TimescaleDB extension

Connect to `lorawan_telemetry` and run:

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'timescaledb';
```

**PASS means:** one `timescaledb` row exists with the commissioned version or an intentionally documented upgraded version.

After any Patroni promotion, this must still work on the promoted member.

## Step 6 — Verify required hypertables

```sql
SELECT hypertable_schema, hypertable_name
FROM timescaledb_information.hypertables
WHERE hypertable_schema = 'telemetry'
ORDER BY 1,2;
```

Required time-series objects include:

```text
telemetry.uplinks
telemetry.measurements
```

`telemetry.fabric_outbox` is intentionally an ordinary transactional table, not a hypertable.

## Step 7 — Verify fresh telemetry read path

Use a read-only role:

```sql
SELECT time, dev_eui, metric_name, metric_value, metric_text, metric_bool, unit, quality
FROM telemetry.measurements
ORDER BY time DESC
LIMIT 20;
```

Do not invent a sensor-specific column when the normalized measurements table is the current schema.

## Step 8 — Inspect Fabric outbox separately from adapter health

```sql
SELECT status, count(*)
FROM telemetry.fabric_outbox
GROUP BY status
ORDER BY status;
```

Important rule: `pending` with `attempts=0` is **not automatically a Fabric outage**. Before blaming the adapter, verify the row has immutable `finalized_payload` and, for the v2 path, verifier-owned `status='verified'` eligibility.

Use [15-hyperledger-fabric-adapter.md](15-hyperledger-fabric-adapter.md) for the exact claim/reconciliation rules.

## Step 9 — Check replication/health before maintenance

Use `patronictl list` and the database runbook to inspect replication/lag. If a replica is behind, do not start an unrelated switchover or upgrade until its state is understood.

A PostgreSQL process being `running` does not mean it is safe for promotion.

## Safe schema migration procedure

1. prove etcd 3/3 and one Patroni leader;
2. create/verify the required logical backup or rollback point;
3. use the normal primary-routed connection;
4. inspect migration prerequisites/current schema version;
5. run exactly one reviewed migration path;
6. verify transaction success and expected schema objects;
7. verify replicas remain healthy;
8. verify one representative application operation;
9. retain migration evidence/rollback notes.

Do not manually edit schema on replicas.

## Safe PostgreSQL/Timescale upgrade rule

Database major/extension upgrades require the dedicated runbook. All promotion-eligible members must have compatible PostgreSQL and TimescaleDB builds before a node can safely become primary.

Do not point an older/newer PostgreSQL major at an existing data directory because a container happens to start.

## Backup/recovery rules

- HA replication is availability, not backup.
- Logical deletion replicates too.
- Take/verify backups before destructive testing/migrations.
- Restore into a controlled recovery target first unless the disaster procedure explicitly calls for in-place recovery.
- Re-establish one authoritative leader and healthy replicas before reopening all application writers.

## Troubleshooting order

| Symptom | First check |
|---|---|
| No Patroni leader | etcd quorum + Patroni state |
| Leader healthy, app cannot connect | PgBouncer/HAProxy/TLS/auth |
| One replica lagging | WAL/network/disk/member logs |
| Timescale query fails after promotion | extension/version/preload on promoted member |
| Duplicate telemetry | Node-RED/event idempotency + DB constraints |
| Outbox stuck `pending/0` | finalized payload/verifier eligibility before Fabric |

## Completion checklist

- etcd healthy;
- exactly one Patroni leader;
- expected replicas healthy;
- normal PgBouncer/HAProxy primary route succeeds;
- `chirpstack` and `lorawan_telemetry` exist;
- TimescaleDB loads;
- required hypertables exist;
- representative telemetry read succeeds;
- outbox can be inspected without conflating eligibility with worker failure;
- current backup boundary is known.

## Complete deployment, data and recovery companion

Use [PostgreSQL/Patroni/TimescaleDB commissioned deployment and recovery](POSTGRESQL-PATRONI-TIMESCALEDB-DEPLOYMENT-RECOVERY.md) for the immutable image/storage contract, role-dependent operations, extension compatibility, protection of evidence/outbox state, and backup/restore boundaries. It also distinguishes later reported PostgreSQL/Timescale versions from the original inspected image packages.

## Detailed runbooks

- [`../server/cloud-production/06-spilo-patroni-postgresql-cluster.md`](../server/cloud-production/06-spilo-patroni-postgresql-cluster.md)
- [`../server/cloud-production/07-haproxy-and-pgbouncer.md`](../server/cloud-production/07-haproxy-and-pgbouncer.md)
- [`../server/cloud-production/13-backup-restore-and-disaster-recovery.md`](../server/cloud-production/13-backup-restore-and-disaster-recovery.md)
- [`../server/integrations/timescaledb/00-README.md`](../server/integrations/timescaledb/00-README.md)