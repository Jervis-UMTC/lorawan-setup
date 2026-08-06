# 4. Backup, Security, and Maintenance

Telemetry is operational data. Treat it as recoverable business data even when the system is only a lab deployment.

## 4.1 Database backup

Create a compressed PostgreSQL backup from the telemetry database:

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose exec -T telemetry-db pg_dump -U telemetry_admin -d lorawan_telemetry --format=custom > ~/lorawan-telemetry-$(date +%Y%m%d).dump
~~~

Confirm the backup is non-empty:

~~~bash
ls -lh ~/lorawan-telemetry-*.dump
~~~

Move backups to storage separate from the Raspberry Pi. A backup left on the same SD card does not protect against SD-card failure.

## 4.2 Test backup readability

~~~bash
docker compose exec -T telemetry-db pg_restore --list < ~/lorawan-telemetry-YYYYMMDD.dump
~~~

Replace the date placeholder with the actual filename. Do not restore over the production database for a test. Restore into a separate test database or an isolated host.

## 4.3 Credential rules

- Keep TELEMETRY_DB_ADMIN_PASSWORD outside Git.
- Give Node-RED only telemetry_writer.
- Give Grafana only telemetry_reader.
- Rotate passwords through controlled maintenance windows.
- Never put passwords in Node-RED debug nodes.
- Never put passwords in dashboard SQL.
- Do not publish telemetry-db port 5432 unless there is a documented remote administration need.

## 4.4 Retention and storage

Check the size of both time-series tables periodically:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT hypertable_name, pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) FROM timescaledb_information.hypertables;"
~~~

Retention applies independently to uplinks and normalized measurements. Choose it from the data requirement, not from the largest available SD card. Increase retention only after measuring disk usage and backup time.

## 4.5 Image updates

Before an update, record image names and current versions:

~~~bash
docker compose images telemetry-db
~~~

Pull the selected image:

~~~bash
docker compose pull telemetry-db
~~~

Restart only the telemetry service:

~~~bash
docker compose up -d telemetry-db
~~~

Run the extension and schema checks again after an upgrade. Never delete the timescale-data volume during an image update.

## 4.6 Change management

Record:

- image tag and digest;
- TimescaleDB extension version;
- schema version;
- retention interval;
- backup filename and destination;
- reason for the change; and
- verification result.

Next: [05-troubleshooting.md](05-troubleshooting.md)
