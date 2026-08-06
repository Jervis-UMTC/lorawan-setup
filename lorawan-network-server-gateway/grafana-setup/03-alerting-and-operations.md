# 3. Alerts and Operational Monitoring

Alerts should identify an action, not merely make the dashboard colorful. Build and test one alert at a time.

## 3.1 Alert design rules

- Define the expected sensor reporting interval before defining a missing-data alert.
- Add a pending period so one delayed packet does not page an operator.
- Use a fixed device or explicit query in alert rules; do not depend on dashboard variables.
- Separate warning and critical thresholds.
- Document who receives each notification.
- Test the alert with a controlled condition before relying on it.

Grafana evaluates alert queries without the context of a dashboard viewer's variable selection. Create alert queries that explicitly identify the device or fleet condition. [Grafana alert query guidance](https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/queries-conditions/)

## 3.2 Low-battery alert

Create an alert rule with a PostgreSQL query such as:

~~~sql
SELECT
    device_name,
    battery_v
FROM telemetry.latest_uplinks
WHERE battery_v IS NOT NULL
  AND battery_v < 3.0;
~~~

Use a threshold expression or configure the query to return only violations. Tune 3.0 V from the actual Dragino battery specification.

## 3.3 High-temperature alert

~~~sql
SELECT
    device_name,
    temperature_c
FROM telemetry.latest_uplinks
WHERE temperature_c IS NOT NULL
  AND temperature_c > 35.0;
~~~

The threshold must come from the application requirement. A temperature threshold is not a universal sensor threshold.

## 3.4 Missing-uplink alert

If a sensor should report at least every 20 minutes, start with a wider operational window:

~~~sql
SELECT
    device_name,
    max(time) AS last_seen
FROM telemetry.uplinks
GROUP BY device_name
HAVING max(time) < now() - interval '45 minutes';
~~~

For a battery sensor with a longer interval, use a correspondingly longer grace period. Do not configure missing-data alerts before the sensor's actual interval is known.

## 3.5 Data-source health alert

Grafana cannot alert on a database it cannot query. Monitor the Grafana data source and the telemetry database service separately:

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose ps telemetry-db
~~~

~~~bash
docker compose ps grafana
~~~

For host-level health, also monitor disk space, memory, and container restarts.

## 3.6 Contact points and notification policies

In Grafana:

1. Open **Alerting**.
2. Create a contact point.
3. Test the contact point.
4. Create notification policies by severity.
5. Add labels such as severity, site, and device.
6. Route warning and critical notifications separately.

Do not put passwords or webhook secrets in panel queries. Use Grafana's protected contact-point configuration.

## 3.7 Operational dashboard rows

Add a row named **Data Pipeline Health** containing:

- last telemetry timestamp;
- number of uplinks in the selected range;
- sensors seen in the selected range;
- oldest current sensor timestamp; and
- database or service status supplied by the operations monitoring layer.

Example query:

~~~sql
SELECT
    count(*) AS uplinks,
    count(DISTINCT dev_eui) AS devices,
    max(time) AS newest_event,
    min(time) AS oldest_event
FROM telemetry.uplinks
WHERE $__timeFilter(time);
~~~

## 3.8 No-sensor state

Before the Dragino arrives, an empty dashboard is expected. Do not interpret no telemetry rows as a Grafana failure. Validate the data source with a connection test and validate the pipeline after the first real uplink.

Next: [04-security-backup-and-updates.md](04-security-backup-and-updates.md)
