# 4. Backup, Security, and Maintenance

Telemetry is operational data. Treat it as recoverable business data even in a lab. A file created by `pg_dump` is not a usable backup until its permissions, size, checksum, catalog, off-host copy, and restore procedure have been verified.

> **Cloud HA POC:** this file's commands target the single-host `telemetry-db` container. Do **not** deploy or operate that container in the three-Droplet cloud POC. Use [../../cloud-production/13-backup-restore-and-disaster-recovery.md](../../cloud-production/13-backup-restore-and-disaster-recovery.md), which backs up the Timescale-enabled `lorawan_telemetry` database through the Patroni/PgBouncer HA path and includes the POC etcd/OpenBao rollback boundary.

## 4.1 Create a protected backup

Create a restricted directory and custom-format dump:

~~~bash
install -d -m 700 ~/backups/telemetry
umask 077
cd /opt/lorawan-lab
BACKUP=~/backups/telemetry/lorawan-telemetry-$(date +%Y%m%d-%H%M%S).dump
docker compose exec -T telemetry-db \
  pg_dump -U telemetry_admin -d lorawan_telemetry --format=custom \
  > "$BACKUP"
~~~

Confirm the file is non-empty and accessible only to the owner:

~~~bash
stat -c '%a %s %n' "$BACKUP"
test -s "$BACKUP"
~~~

Expected mode is `600` or stricter and size is greater than zero. **Stop here. Do not continue** if either check fails.

## 4.2 Validate the backup catalog and checksum

If this is a new shell, resolve the newest backup explicitly and review the path before using it:

~~~bash
BACKUP=$(find ~/backups/telemetry -maxdepth 1 -type f -name 'lorawan-telemetry-*.dump' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
printf '%s\n' "$BACKUP"
test -n "$BACKUP" && test -s "$BACKUP"
~~~

**Stop here. Do not continue** if the path is blank, points outside the protected backup directory, or does not identify the intended backup.

~~~bash
docker compose exec -T telemetry-db pg_restore --list < "$BACKUP" | head -50
sha256sum "$BACKUP" | tee "$BACKUP.sha256"
chmod 600 "$BACKUP.sha256"
~~~

The catalog must list the telemetry schema, tables, and TimescaleDB-related objects expected from the active database. A successful catalog listing proves archive readability, not a full restore.

Copy the dump and checksum to protected storage outside the application server and its virtual disk or host failure domain. Encrypt the backup at rest and in transit. A second file on the same server, volume, or hypervisor datastore is not an independent backup.

## 4.3 Perform an isolated restore test

Schedule this during a maintenance window because restore testing consumes disk, memory, and I/O. Resolve and review the backup again if this is a new shell:

~~~bash
BACKUP=$(find ~/backups/telemetry -maxdepth 1 -type f -name 'lorawan-telemetry-*.dump' -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
printf '%s\n' "$BACKUP"
test -n "$BACKUP" && test -s "$BACKUP"
~~~

Confirm the test database name is unused:

~~~bash
cd /opt/lorawan-lab
docker compose exec telemetry-db psql -U telemetry_admin -d postgres -c "SELECT datname FROM pg_database WHERE datname = 'lorawan_telemetry_restore_test';"
~~~

**Stop here. Do not continue** if a row is returned or the target database cannot be positively identified as disposable.

Create and restore into the isolated database:

~~~bash
docker compose exec telemetry-db createdb -U telemetry_admin -T template0 lorawan_telemetry_restore_test
docker compose exec -T telemetry-db \
  pg_restore -U telemetry_admin -d lorawan_telemetry_restore_test --exit-on-error \
  < "$BACKUP"
~~~

Verify schema version and row counts:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry_restore_test -c "SELECT * FROM telemetry.schema_version ORDER BY version; SELECT count(*) AS uplinks FROM telemetry.uplinks; SELECT count(*) AS measurements FROM telemetry.measurements;"
~~~

After the schema version, row counts, and representative queries match the source, drop only the verified test database:

~~~bash
docker compose exec telemetry-db dropdb -U telemetry_admin lorawan_telemetry_restore_test
~~~

Never test a restore by overwriting `lorawan_telemetry`.

## 4.4 Credential and network rules

- Keep `TELEMETRY_DB_ADMIN_PASSWORD` outside Git and mode-protected.
- Give Node-RED only `telemetry_writer`.
- Give Grafana only `telemetry_reader`.
- Rotate passwords in a controlled window and update one consumer at a time.
- Never put passwords in Node-RED debug nodes, flow exports, dashboard SQL, or screenshots.
- Do not publish telemetry-db port 5432 unless a reviewed remote-administration design requires it.
- Confirm host listeners with `sudo ss -lntp` and Compose bindings after every change.

## 4.5 Retention and storage

Check table size, disk capacity, and retention jobs together:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT hypertable_name, pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) FROM timescaledb_information.hypertables ORDER BY hypertable_name; SELECT job_id, proc_name, schedule_interval, config FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention';"
~~~

~~~bash
df -h
~~~

Retention applies independently to uplinks and normalized measurements. Before shortening it, create and validate a backup, identify the oldest chunks that will become eligible for deletion, confirm deletion is allowed, and understand that rollback requires restoring those chunks from backup. Deleted chunks cannot be recovered from the live database.

## 4.6 Image and extension updates

Before an update, capture the compatibility baseline:

~~~bash
docker compose images telemetry-db
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SHOW server_version; SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'; SELECT * FROM telemetry.schema_version ORDER BY version;"
~~~

Review the selected image's PostgreSQL-major and TimescaleDB upgrade path. Do not attach an existing volume to a different PostgreSQL major version. Create and restore-test a backup, keep the previous image tag or digest as the rollback reference, then update only the telemetry service:

~~~bash
docker compose pull telemetry-db
docker compose up -d telemetry-db
docker compose ps telemetry-db
docker compose logs --since=10m --tail=200 telemetry-db
~~~

Repeat extension, hypertable, role, uniqueness-index, retention-job, and query checks after the update. Never delete `telemetry-data` during an update.

## 4.7 Keep the recovery facts for each database change

With the protected database backup, retain the Compose project and telemetry volume name, old and new image digests, PostgreSQL and TimescaleDB versions, schema version, active retention interval, backup filename/checksum/off-host location, isolated restore result, reason for the change, post-change validation, and exact rollback image or restore procedure.

These facts are needed to attach the correct volume to a compatible image and recover the intended schema. Unrelated operator, approval, or paperwork fields are not required.

Next: [05-troubleshooting.md](05-troubleshooting.md)
