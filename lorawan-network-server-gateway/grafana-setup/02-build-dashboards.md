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
ORDER BY time DESC
LIMIT 1;
~~~

Use the battery chemistry and Dragino documentation to choose thresholds. A generic low-battery threshold is only a starting point.

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

This is the first panel to inspect when an operator asks which sensors are alive.

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

## 2.11 Dashboard refresh

Start with a 1-minute refresh. Do not use a 1-second refresh on a Raspberry Pi unless there is a measured operational need.

Before saving, verify:

- the selected time range contains data;
- the query returns a time column;
- field units are correct;
- empty/null fields do not make the panel misleading; and
- the panel title identifies the device or variable.

Next: [03-alerting-and-operations.md](03-alerting-and-operations.md)
