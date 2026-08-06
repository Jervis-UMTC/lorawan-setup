# 5. Grafana Troubleshooting

Follow the pipeline in order:

~~~text
ChirpStack event -> Node-RED insert -> telemetry.uplinks row -> Grafana query -> panel or alert
~~~

## 5.1 Grafana does not open

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose ps grafana
~~~

~~~bash
docker compose logs --since=10m --tail=100 grafana
~~~

If the container is running but the UI is unreachable, check the Raspberry Pi IP address and firewall rule for TCP 3000. Do not expose the port publicly as a first fix.

## 5.2 PostgreSQL data source test fails

Use the internal hostname:

~~~text
telemetry-db:5432
~~~

Common errors:

| Error | Likely cause |
|---|---|
| getaddrinfo failed | Wrong service name or containers are not on the same Compose network |
| password authentication failed | Wrong telemetry_reader password |
| database does not exist | Wrong database name |
| permission denied for schema | Missing USAGE or SELECT grant |
| connection refused | telemetry-db is not healthy |

Verify Docker DNS:

~~~bash
docker compose exec grafana getent hosts telemetry-db
~~~

## 5.3 Data source works but query returns no rows

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT count(*), max(time) FROM telemetry.uplinks;"
~~~

If count is zero, go to the Node-RED troubleshooting guide. If rows exist, check:

- the dashboard time range;
- the schema name telemetry;
- the table or view name;
- the variable value;
- NULL filtering; and
- the selected data source.

## 5.4 Wrong time or no points on the graph

Check the stored timestamps:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT time, received_at, device_name FROM telemetry.uplinks ORDER BY received_at DESC LIMIT 10;"
~~~

Store timestamptz values in UTC. Do not convert timestamps to local strings in Node-RED before inserting.

## 5.5 Dashboard is slow

Use a time filter:

~~~sql
WHERE $__timeFilter(time)
~~~

Avoid SELECT star, unbounded fleet queries, and a one-second refresh interval. Use telemetry.latest_uplinks for summary panels and time_bucket for long historical ranges.

## 5.6 Alert does not fire

Confirm the alert query returns a value in **Explore**, then check:

- query time range;
- pending duration;
- no-data state;
- error state;
- contact point test;
- notification policy labels; and
- whether the query uses a dashboard variable.

Create a separate alert query with explicit device filters if the alert needs device-specific behavior.

Return to [00-README.md](00-README.md) after the Grafana path is healthy.
