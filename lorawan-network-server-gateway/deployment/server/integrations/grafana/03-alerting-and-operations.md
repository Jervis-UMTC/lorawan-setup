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
  AND battery_v > 0
  AND battery_v < <APPROVED_LOW_BATTERY_V>;
~~~

Replace `<APPROVED_LOW_BATTERY_V>` with the threshold approved for the actual EMU-01 battery pack/power configuration before enabling the rule. `battery_v = 0` is a documented USB-only sentinel in the project payload and must not trigger a false low-battery alert.

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
    r.device_name,
    r.dev_eui,
    max(u.time) AS last_seen
FROM telemetry.device_registry AS r
LEFT JOIN telemetry.uplinks AS u
    ON u.dev_eui = r.dev_eui
WHERE r.active = true
GROUP BY r.device_name, r.dev_eui
HAVING max(u.time) IS NULL
    OR max(u.time) < now() - interval '45 minutes';
~~~

For a battery sensor with a longer interval, use a correspondingly longer grace period. The registry-based query also detects an active device that has never produced a row. Do not configure missing-data alerts before the sensor's actual interval, maintenance windows, and no-data behavior are approved.

## 3.5 Data-source health alert

Grafana cannot alert on a database it cannot query. Monitor the Grafana data source and the telemetry database service separately:

~~~bash
cd /opt/lorawan-lab
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
- database or service status supplied by the operations monitoring layer;
- when v2 is enabled, gateway evidence counts by state, oldest pending age, and latest checkpoint age.

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

## 3.7A Gateway evidence alerts

Add these only after the gateway-integrity schema/services are deployed and proven.

### Integrity-failure alert

Contradictory proof is high/critical severity:

~~~sql
SELECT
    gateway_id,
    source_event_key,
    observed_at,
    reason_code
FROM gateway_evidence.event_verification
WHERE status = 'integrity_failure'
  AND updated_at > now() - interval '15 minutes';
~~~

### Evidence-gap alert

Missing proof is different from contradictory proof:

~~~sql
SELECT
    gateway_id,
    source_event_key,
    observed_at,
    reason_code
FROM gateway_evidence.event_verification
WHERE status = 'evidence_gap'
  AND updated_at > now() - interval '15 minutes';
~~~

Choose warning/critical behavior from the business evidence requirement. Never automatically convert a gap into verified state after an alert timeout.

### Old pending-verification alert

Alert when pending age exceeds the documented normal reconciliation window. A short pending period during queue/journal recovery is expected; an indefinitely pending v2 event is not.

### Stale-checkpoint alert

Alert when a gateway is otherwise online/fresh but its latest accepted checkpoint is older than the configured evidence-anchor interval plus operational grace period. This isolates evidence-uploader/API problems from MQTT problems.

## 3.8 No-sensor state

Before EMU-01 is commissioned into the telemetry path, an empty dashboard is expected. Do not interpret no telemetry rows as a Grafana failure, and do not configure an empty result as `OK` without an explicit reason. Validate the data source with a connection test and validate the pipeline after the first real EMU-01 payload-v2 uplink.

Next: [04-security-backup-and-updates.md](04-security-backup-and-updates.md)
