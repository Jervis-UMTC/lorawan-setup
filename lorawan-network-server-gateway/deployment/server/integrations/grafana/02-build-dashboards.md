# 2. Build Grafana Dashboards

Create the dashboard only after the PostgreSQL data source is working. Start with a small dashboard, verify it with real data, and then add fleet-wide panels.

## 2.1 Create the dashboard

1. Open **Dashboards**.
2. Select **New**.
3. Select **New dashboard**.
4. Add a panel.
5. Select the telemetry PostgreSQL data source.
6. Use **Code** mode for SQL queries.

Set the dashboard time zone deliberately. Store data in UTC and display Asia/Manila or the operator's local zone in Grafana.

## 2.2 Add a device variable

Open **Dashboard settings**, then **Variables**, then **Add variable**.

Use:

~~~text
Name: device_name
Type: Query
Data source: telemetry PostgreSQL
Multi-value: optional
Include All: optional
~~~

Query:

~~~sql
SELECT DISTINCT device_name
FROM telemetry.uplinks
WHERE device_name IS NOT NULL
ORDER BY device_name;
~~~

A variable lets one dashboard switch between sensors without duplicating every panel. [Grafana dashboard variables](https://grafana.com/docs/grafana/latest/visualizations/dashboards/variables/)

## 2.3 Latest temperature panel

Visualization: **Stat** or **Gauge**.

For a single selected device:

~~~sql
SELECT
    time,
    temperature_c
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND temperature_c IS NOT NULL
ORDER BY time DESC
LIMIT 1;
~~~

Recommended field settings:

~~~text
Unit: Celsius
Min: -40
Max: 80
Thresholds: choose values appropriate for the installation
~~~

Do not copy greenhouse thresholds into a cold-storage or outdoor deployment without reviewing the actual operating range.

## 2.4 Latest humidity panel

~~~sql
SELECT
    time,
    humidity_percent
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND humidity_percent IS NOT NULL
ORDER BY time DESC
LIMIT 1;
~~~

Recommended field settings:

~~~text
Unit: Percent 0-100
Min: 0
Max: 100
~~~

## 2.5 Latest battery panel

~~~sql
SELECT
    time,
    battery_v
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND battery_v IS NOT NULL
  AND battery_v > 0
ORDER BY time DESC
LIMIT 1;
~~~

EMU-01 may report the documented `0` battery sentinel while USB-powered, so exclude `battery_v <= 0` from battery-health panels. Before defining a low-battery threshold, record the actual battery pack chemistry, nominal/operating voltage range, and the approved threshold for the deployed power configuration. Do not inherit a threshold from an unrelated sensor model.

## 2.6 Temperature history

Visualization: **Time series**.

~~~sql
SELECT
    time,
    temperature_c
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND $__timeFilter(time)
  AND temperature_c IS NOT NULL
ORDER BY time ASC;
~~~

The $__timeFilter macro makes the panel follow the Grafana time picker. Do not remove it from historical panels.

## 2.7 Humidity and battery history

~~~sql
SELECT
    time,
    humidity_percent
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND $__timeFilter(time)
  AND humidity_percent IS NOT NULL
ORDER BY time ASC;
~~~

~~~sql
SELECT
    time,
    battery_v
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND $__timeFilter(time)
  AND battery_v IS NOT NULL
ORDER BY time ASC;
~~~

Use separate panels for temperature, humidity, and battery because each needs different units and thresholds.

## 2.8 Fleet latest-value table

Visualization: **Table**.

~~~sql
SELECT
    device_name,
    dev_eui,
    time AS last_seen,
    temperature_c,
    humidity_percent,
    battery_v,
    rssi_dbm,
    snr_db
FROM telemetry.latest_uplinks
ORDER BY last_seen DESC;
~~~

This is the first panel to inspect when an operator asks which sensors are alive, but `last_seen` must be interpreted against each device's approved reporting interval. Add value mappings or thresholds that label rows as current, delayed, stale, or never seen.

## 2.9 Gateway link-quality panel

~~~sql
SELECT
    time,
    rssi_dbm,
    snr_db
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND $__timeFilter(time)
ORDER BY time ASC;
~~~

Link metrics are radio observations, not sensor-health scores. Interpret them across multiple uplinks and installation locations.

## 2.10 Downsample long history

For a very long range, aggregate data rather than drawing every row:

~~~sql
SELECT
    date_bin('15 minutes', time, TIMESTAMPTZ '2000-01-01') AS bucket,
    avg(temperature_c) AS temperature_c,
    avg(humidity_percent) AS humidity_percent
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND $__timeFilter(time)
GROUP BY bucket
ORDER BY bucket ASC;
~~~

If date_bin is unavailable on the selected PostgreSQL version, use TimescaleDB time_bucket instead:

~~~sql
SELECT
    time_bucket('15 minutes', time) AS bucket,
    avg(temperature_c) AS temperature_c,
    avg(humidity_percent) AS humidity_percent
FROM telemetry.uplinks
WHERE device_name = '$device_name'
  AND $__timeFilter(time)
GROUP BY bucket
ORDER BY bucket ASC;
~~~

## 2.11 Make freshness visible

Add a table field or stat that shows reading age rather than presenting the last value without context:

~~~sql
SELECT
    device_name,
    dev_eui,
    time AS last_seen,
    now() - time AS reading_age,
    temperature_c,
    humidity_percent,
    battery_v
FROM telemetry.latest_uplinks
ORDER BY time DESC;
~~~

Choose stale thresholds from the device's actual reporting interval and operational grace period. A missing or stale reading must display as unknown or stale, never as a safe value.

## 2.11A Gateway evidence status panel

The cloud POC commissioned this panel on 2026-09-01 after the reviewed [Gateway Integrity](../gateway-integrity/00-README.md) schema existed and `telemetry_reader` was verified to have explicit read-only access to the approved evidence views. For new deployments, keep the same prerequisite.

Visualization: **Table** or **Stat**.

The commissioned cloud dashboard uses the approved read-only view:

~~~sql
SELECT
    observed_at,
    source_event_key,
    gateway_id,
    status,
    reason_code,
    attempts,
    verified_at
FROM gateway_evidence.verification_status
ORDER BY observed_at DESC
LIMIT 20;
~~~

Interpret the values literally:

```text
verified          -> required proof chain passed
pending           -> telemetry exists but proof is still being assembled
evidence_gap      -> required proof is missing/unavailable
integrity_failure -> contradictory evidence exists; investigate
not_required      -> policy did not request gateway evidence
```

Do not map `pending` or `evidence_gap` to green merely because the sensor value looks reasonable.

## 2.11B Gateway checkpoint freshness panel

For operators, show one row per gateway with the latest accepted off-device anchor. The commissioned cloud dashboard uses the approved view:

~~~sql
SELECT
    gateway_id,
    segment_id,
    last_sequence,
    server_received_at,
    checkpoint_age
FROM gateway_evidence.checkpoint_status
ORDER BY gateway_id;
~~~

On `ulc-03`, these two panels are file-provisioned alongside the original four telemetry panels and were loaded by Grafana without a container restart.

A stale checkpoint with fresh MQTT telemetry means the evidence path is degraded independently of delivery.

## 2.12 Dashboard refresh

Start with a 1-minute refresh. Shorter refresh intervals multiply Grafana queries and TimescaleDB work; use them only after measuring query latency, database load, and the actual device reporting interval.

Before saving, verify:

- the selected time range contains data;
- the query returns a time column;
- field units are correct;
- empty/null fields do not make the panel misleading;
- the panel title identifies the device or variable; and
- when v2 evidence is displayed, verification state and checkpoint freshness are not inferred from telemetry freshness.

Next: [03-alerting-and-operations.md](03-alerting-and-operations.md)
