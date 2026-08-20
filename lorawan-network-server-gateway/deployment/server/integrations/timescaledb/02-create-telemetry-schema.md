# 2. Create the Generic Telemetry Schema and Hypertables

This is a schema-first setup. It is valid to complete every step before a sensor exists. Before changing an existing database, verify the exact service, database, schema version, current rows, image version, and backup readability. Do not insert permanent fake sensor data just to make the tables non-empty.

The design accepts different sensor models without a new PostgreSQL schema for each one:

~~~text
telemetry.uplinks
  one row per ChirpStack uplink event

telemetry.measurements
  one row per decoded metric, such as temperature, humidity,
  soil_moisture, co2, vibration, door_state, or water_level

telemetry.device_registry
  device model, decoder, site, zone, and asset assignment

payload_json
  complete decoded object for fields not yet standardized
~~~

## 2.1 Open the database shell

Choose the connection path for the active deployment.

**Local lab profile:**

~~~bash
cd /opt/lorawan-lab
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry
~~~

**Cloud HA POC:** connect through its stable PgBouncer/HAProxy path to `lorawan_telemetry`, for example:

~~~bash
psql 'host=pgbouncer.internal.<DOMAIN> port=6432 dbname=lorawan_telemetry user=telemetry_admin sslmode=require'
~~~

Run the following SQL at the `lorawan_telemetry` prompt. Keep a transcript that excludes passwords. **Stop here. Do not continue** if the prompt shows another database, the active service is uncertain, or the backup has not been validated.

## 2.2 Enable the TimescaleDB extension

~~~sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
~~~

Confirm the extension:

~~~sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'timescaledb';
~~~

## 2.3 Create least-privilege roles

Create one writer role for Node-RED and one reader role for Grafana without placing passwords in the SQL transcript:

~~~sql
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telemetry_writer') THEN
        CREATE ROLE telemetry_writer LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telemetry_reader') THEN
        CREATE ROLE telemetry_reader LOGIN;
    END IF;
END
$$;

\password telemetry_writer
\password telemetry_reader
~~~

The `\password` prompts avoid writing cleartext passwords into SQL history. Use independent values from the approved secret store. If a role already exists, confirm its current owners and consumers before rotating its password in a controlled maintenance window.

## 2.4 Create the telemetry schema

~~~sql
CREATE SCHEMA IF NOT EXISTS telemetry;
~~~

## 2.5 Create the generic uplinks table

This table stores one row for each accepted ChirpStack event. The optional `temperature_c`, `humidity_percent`, and `battery_v` columns are compatibility/convenience columns. For the current EMU-01 payload-v2 flow, Node-RED maps `environment_temperature_c`, `environment_humidity_percent`, and `battery_v` into those columns when appropriate. Every other physical sensor field belongs in `telemetry.measurements` and the complete decoded object remains in `payload_json`.

~~~sql
CREATE TABLE IF NOT EXISTS telemetry.uplinks (
    event_key           TEXT NOT NULL,
    time                TIMESTAMPTZ NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    domain              TEXT,
    site_id             TEXT,
    zone_id             TEXT,
    asset_id            TEXT,
    application_id      TEXT,
    application_name    TEXT,
    device_id           TEXT,
    device_name         TEXT,
    dev_eui             TEXT NOT NULL,
    device_model        TEXT,
    decoder_version     TEXT,
    gateway_id          TEXT,
    region              TEXT,
    f_port              INTEGER,
    f_cnt               BIGINT,
    confirmed           BOOLEAN,
    rssi_dbm            INTEGER,
    snr_db              DOUBLE PRECISION,
    temperature_c       DOUBLE PRECISION,
    humidity_percent    DOUBLE PRECISION,
    battery_v           DOUBLE PRECISION,
    payload_json        JSONB NOT NULL,
    raw_data            TEXT,
    mqtt_topic          TEXT
);
~~~

The common metadata and payload are separated from the metric values. A CO2, soil-moisture, vibration, door-state, or water-level sensor can use the same uplinks table.

## 2.6 Add generic columns when an earlier empty table already exists

If the earlier version of this guide already created telemetry.uplinks, do not drop it. Run these non-destructive additions. They are especially suitable now because no real sensor data exists.

~~~sql
ALTER TABLE telemetry.uplinks ADD COLUMN IF NOT EXISTS domain TEXT;
~~~

~~~sql
ALTER TABLE telemetry.uplinks ADD COLUMN IF NOT EXISTS site_id TEXT;
~~~

~~~sql
ALTER TABLE telemetry.uplinks ADD COLUMN IF NOT EXISTS zone_id TEXT;
~~~

~~~sql
ALTER TABLE telemetry.uplinks ADD COLUMN IF NOT EXISTS asset_id TEXT;
~~~

~~~sql
ALTER TABLE telemetry.uplinks ADD COLUMN IF NOT EXISTS device_model TEXT;
~~~

~~~sql
ALTER TABLE telemetry.uplinks ADD COLUMN IF NOT EXISTS decoder_version TEXT;
~~~

The convenience columns may remain nullable. Do not add a new SQL column for every EMU-01 or future sensor metric; use the generic measurements table for the full metric set.

## 2.7 Create the generic measurements table

This table stores one normalized row per measurement. It supports numeric, text, and boolean values.

~~~sql
CREATE TABLE IF NOT EXISTS telemetry.measurements (
    measurement_id     BIGINT GENERATED BY DEFAULT AS IDENTITY,
    time                TIMESTAMPTZ NOT NULL,
    event_key           TEXT NOT NULL,
    domain              TEXT,
    site_id             TEXT,
    zone_id             TEXT,
    asset_id            TEXT,
    device_id           TEXT,
    dev_eui             TEXT NOT NULL,
    metric_name         TEXT NOT NULL,
    metric_value        DOUBLE PRECISION,
    metric_text         TEXT,
    metric_bool         BOOLEAN,
    unit                TEXT NOT NULL,
    quality             TEXT NOT NULL DEFAULT 'measured',
    source_field        TEXT,
    payload_json        JSONB,
    CONSTRAINT measurements_quality_ck
        CHECK (quality IN ('measured', 'estimated', 'missing', 'invalid')),
    CONSTRAINT measurements_value_ck
        CHECK (
            (quality IN ('measured', 'estimated')
                AND num_nonnulls(metric_value, metric_text, metric_bool) = 1)
            OR
            (quality IN ('missing', 'invalid')
                AND num_nonnulls(metric_value, metric_text, metric_bool) <= 1)
        )
);
~~~

Examples:

~~~text
temperature      -> metric_value = 24.7, unit = Cel
soil_moisture    -> metric_value = 41.2, unit = '%'
door_state       -> metric_bool = true, unit = boolean
equipment_state  -> metric_text = 'running', unit = state
~~~

Do not use `metric_name` as a SQL column name. It is data, so new sensors can introduce new metric names without a table migration. Use an explicit unit string for every metric, including dimensionless or boolean values.

For a pre-existing table, check for missing units before enforcing the constraint:

~~~sql
SELECT count(*) AS measurements_without_unit
FROM telemetry.measurements
WHERE unit IS NULL;
~~~

**Stop here. Do not set the column `NOT NULL`** while that count is non-zero. Resolve each row from the approved metric dictionary, then apply:

~~~sql
ALTER TABLE telemetry.measurements
    ALTER COLUMN unit SET NOT NULL;
~~~

Node-RED should insert one row into measurements for each approved decoded metric. The current EMU-01 mapping normalizes the Agriculture Kit payload-v2 fields and uses `sensor_validity_bitmap` so invalid sensor groups are not mislabeled as measured values. It may also populate the three compatibility columns described above. Until a real sensor event is available, verify the generic SQL path with the rollback test in [03-connect-and-verify.md](03-connect-and-verify.md).

## 2.8 Create the device registry

The registry separates radio identity from business identity:

~~~sql
CREATE TABLE IF NOT EXISTS telemetry.device_registry (
    dev_eui             TEXT PRIMARY KEY,
    device_id           TEXT,
    device_name         TEXT,
    domain              TEXT,
    site_id             TEXT,
    zone_id             TEXT,
    asset_id            TEXT,
    device_model        TEXT,
    decoder_name        TEXT,
    decoder_version     TEXT,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen          TIMESTAMPTZ,
    last_seen           TIMESTAMPTZ,
    notes               TEXT
);
~~~

Update this registry when a device is assigned to a site, zone, or asset. A device EUI should not be treated as the permanent business identity because a sensor can be replaced or reassigned.

## 2.9 Convert time-series tables into hypertables

This is mandatory for the cloud HA POC because TimescaleDB is part of the deployment feature set, even when only a few sensor records are expected.

~~~sql
SELECT create_hypertable(
    'telemetry.uplinks',
    'time',
    if_not_exists => TRUE
);
~~~

~~~sql
SELECT create_hypertable(
    'telemetry.measurements',
    'time',
    if_not_exists => TRUE
);
~~~

Store event times in UTC. TimescaleDB partitions both time-series tables by time, making recent queries and retention management practical.

## 2.10 Add indexes

Before creating uniqueness constraints on an existing database, check for conflicts:

~~~sql
SELECT event_key, time, count(*)
FROM telemetry.uplinks
GROUP BY event_key, time
HAVING count(*) > 1;

SELECT event_key, metric_name, unit, time, count(*)
FROM telemetry.measurements
GROUP BY event_key, metric_name, unit, time
HAVING count(*) > 1;
~~~

Both queries must return zero rows. **Stop here. Do not create a unique index** while duplicates exist. Preserve the conflicting rows, determine whether they are identical retries or materially different observations, back up the database, and use an approved reconciliation procedure.

~~~sql
CREATE UNIQUE INDEX IF NOT EXISTS uplinks_event_key_time_uq
    ON telemetry.uplinks (event_key, time);
~~~

~~~sql
CREATE INDEX IF NOT EXISTS uplinks_device_time_idx
    ON telemetry.uplinks (dev_eui, time DESC);
~~~

~~~sql
CREATE INDEX IF NOT EXISTS uplinks_asset_time_idx
    ON telemetry.uplinks (asset_id, time DESC);
~~~

~~~sql
CREATE INDEX IF NOT EXISTS measurements_device_metric_time_idx
    ON telemetry.measurements (dev_eui, metric_name, time DESC);
~~~

~~~sql
CREATE INDEX IF NOT EXISTS measurements_asset_metric_time_idx
    ON telemetry.measurements (asset_id, metric_name, time DESC);
~~~

~~~sql
CREATE INDEX IF NOT EXISTS measurements_event_time_idx
    ON telemetry.measurements (event_key, time DESC);
~~~

~~~sql
CREATE UNIQUE INDEX IF NOT EXISTS measurements_event_metric_unit_time_uq
    ON telemetry.measurements (event_key, metric_name, unit, time);
~~~

The two unique indexes are the database backstop for at-least-once Node-RED delivery. Do not add a GIN index on `payload_json` until a real query need has been measured.

## 2.11 Create generic latest-value views

~~~sql
CREATE OR REPLACE VIEW telemetry.latest_uplinks AS
SELECT DISTINCT ON (dev_eui)
    dev_eui,
    device_id,
    device_name,
    domain,
    site_id,
    zone_id,
    asset_id,
    device_model,
    gateway_id,
    time,
    temperature_c,
    humidity_percent,
    battery_v,
    rssi_dbm,
    snr_db,
    payload_json
FROM telemetry.uplinks
ORDER BY dev_eui, time DESC;
~~~

~~~sql
CREATE OR REPLACE VIEW telemetry.latest_measurements AS
SELECT DISTINCT ON (dev_eui, metric_name, unit)
    dev_eui,
    device_id,
    device_name,
    domain,
    site_id,
    zone_id,
    asset_id,
    metric_name,
    metric_value,
    metric_text,
    metric_bool,
    unit,
    quality,
    time
FROM telemetry.measurements
ORDER BY dev_eui, metric_name, unit, time DESC;
~~~

Grafana can query latest_measurements for any metric without requiring a new dashboard table for every sensor model.

## 2.12 Configure retention

Retention deletes old chunks automatically and is therefore a data-destruction policy. Confirm the approved retention period, legal or operational hold requirements, off-host backup, and restore test before enabling it. The following **30-day example** must be replaced when the approved interval differs:

~~~sql
SELECT add_retention_policy(
    'telemetry.uplinks',
    INTERVAL '30 days',
    if_not_exists => TRUE
);
~~~

~~~sql
SELECT add_retention_policy(
    'telemetry.measurements',
    INTERVAL '30 days',
    if_not_exists => TRUE
);
~~~

After applying retention, query `timescaledb_information.jobs` and verify the scheduled interval and table in the returned configuration. Keep that output with the backup and retention policy because it identifies when deletion will run. **Stop here. Do not enable retention** if deletion is not authorized, a legal hold exists, or the only copy of old data is on this database.

## 2.13 Grant permissions

~~~sql
GRANT USAGE ON SCHEMA telemetry
    TO telemetry_writer, telemetry_reader;
~~~

~~~sql
GRANT INSERT, SELECT
    ON telemetry.uplinks, telemetry.measurements
    TO telemetry_writer;
~~~

~~~sql
GRANT SELECT
    ON telemetry.uplinks,
       telemetry.measurements,
       telemetry.device_registry,
       telemetry.latest_uplinks,
       telemetry.latest_measurements
    TO telemetry_reader;
~~~

~~~sql
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA telemetry
    TO telemetry_writer;
~~~

The writer can insert telemetry and normalized measurements. Registry changes should normally be performed by an administrator or a controlled management flow.

## 2.14 Store the schema version in the database

~~~sql
CREATE TABLE IF NOT EXISTS telemetry.schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    description TEXT NOT NULL
);
~~~

~~~sql
INSERT INTO telemetry.schema_version (version, description)
VALUES (3, 'Generic multi-sensor schema with atomic event-metric deduplication, registry, views, and retention')
ON CONFLICT (version) DO NOTHING;
~~~

The row lets Node-RED, backup restores, and later migrations identify the expected schema without relying on a filename or memory. Query the table after applying the SQL; a missing version row means the migration was not completed even when the tables exist.

## 2.15 Confirm that the empty state is valid

~~~sql
SELECT count(*) AS uplinks_before_sensors
FROM telemetry.uplinks;
~~~

~~~sql
SELECT count(*) AS measurements_before_sensors
FROM telemetry.measurements;
~~~

Both results may be zero. That means the schema is empty, not that every permission, duplicate rule, retention job, or application flow is correct. Complete the verification guide before declaring the database ready.

## 2.16 Exit the database shell

~~~sql
\q
~~~

Next: [03-connect-and-verify.md](03-connect-and-verify.md)
