# 3. Connect and Verify the Generic Telemetry Database

You can complete this verification with zero sensor rows. The goal is to prove that the database, roles, hypertables, views, and generic measurements path are ready for the first real device.

## 3.1 Check the service health

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose ps telemetry-db
~~~

~~~bash
docker compose logs --since=10m --tail=100 telemetry-db
~~~

## 3.2 Verify the extension and hypertables

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"
~~~

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT hypertable_schema, hypertable_name, num_dimensions FROM timescaledb_information.hypertables WHERE hypertable_schema = 'telemetry' ORDER BY hypertable_name;"
~~~

The expected hypertables are:

~~~text
telemetry.uplinks
telemetry.measurements
~~~

## 3.3 Verify retention policies

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT job_id, proc_name, schedule_interval, config FROM timescaledb_information.jobs WHERE proc_name = 'policy_retention';"
~~~

There should be a retention job for each time-series table. If a job is absent, do not assume old rows will be deleted.

## 3.4 Verify roles

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "\du"
~~~

Confirm that telemetry_writer and telemetry_reader exist. Do not expose the administrator password in terminal screenshots.

## 3.5 Test writer access without creating permanent sensor data

Use a transaction that rolls back:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "BEGIN; SET LOCAL ROLE telemetry_writer; INSERT INTO telemetry.uplinks (event_key, time, domain, device_id, dev_eui, payload_json) VALUES ('permission-test', now(), 'test', 'test-device', '0000000000000000', '{}'::jsonb); INSERT INTO telemetry.measurements (time, event_key, domain, device_id, dev_eui, metric_name, metric_value, unit) VALUES (now(), 'permission-test', 'test', 'test-device', '0000000000000000', 'test_metric', 1.0, 'unit'); ROLLBACK;"
~~~

This proves that Node-RED can insert both the generic event and a normalized metric. It leaves no fake sensor record behind.

## 3.6 Test reader access

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SET ROLE telemetry_reader; SELECT count(*) AS uplinks, (SELECT count(*) FROM telemetry.measurements) AS measurements FROM telemetry.uplinks;"
~~~

The result may be zero and that is expected before sensor deployment.

The reader should not be able to insert:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "BEGIN; SET LOCAL ROLE telemetry_reader; INSERT INTO telemetry.measurements (time, event_key, dev_eui, metric_name, metric_value, unit) VALUES (now(), 'reader-test', '0000000000000000', 'test_metric', 1.0, 'unit'); ROLLBACK;"
~~~

The second command should fail with a permission error. That failure proves the writer and reader roles are separated.

## 3.7 Verify the generic views

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT * FROM telemetry.latest_uplinks LIMIT 5;"
~~~

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT * FROM telemetry.latest_measurements LIMIT 5;"
~~~

Both views may return zero rows until a device sends an uplink.

## 3.8 Query any future metric

This query works for temperature, humidity, soil moisture, CO2, vibration, door state, water level, or another approved metric:

~~~sql
SELECT
    time,
    device_id,
    asset_id,
    metric_name,
    metric_value,
    metric_text,
    metric_bool,
    unit,
    quality
FROM telemetry.measurements
WHERE metric_name = 'REPLACE_WITH_METRIC_NAME'
  AND time > now() - INTERVAL '24 hours'
ORDER BY time DESC;
~~~

Do not assume a new sensor can populate temperature_c or humidity_percent. Those are optional convenience columns; the measurements table is the generic path.

## 3.9 Check query plans after real data arrives

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "EXPLAIN (ANALYZE, BUFFERS) SELECT time, metric_value FROM telemetry.measurements WHERE dev_eui = 'REPLACE_WITH_REAL_DEVEUI' AND metric_name = 'REPLACE_WITH_METRIC_NAME' AND time > now() - interval '24 hours' ORDER BY time DESC;"
~~~

Use the real device EUI only on the Pi. Do not put credentials in the query.

## 3.10 Useful operational queries

~~~sql
SELECT count(*) AS uplink_rows,
       min(time) AS first_event,
       max(time) AS last_event
FROM telemetry.uplinks;
~~~

~~~sql
SELECT count(*) AS measurement_rows,
       count(DISTINCT dev_eui) AS devices,
       count(DISTINCT metric_name) AS metric_types,
       min(time) AS first_measurement,
       max(time) AS last_measurement
FROM telemetry.measurements;
~~~

~~~sql
SELECT dev_eui,
       metric_name,
       unit,
       max(time) AS last_seen
FROM telemetry.measurements
GROUP BY dev_eui, metric_name, unit
ORDER BY last_seen DESC;
~~~

Next: [04-backup-security-and-maintenance.md](04-backup-security-and-maintenance.md)
