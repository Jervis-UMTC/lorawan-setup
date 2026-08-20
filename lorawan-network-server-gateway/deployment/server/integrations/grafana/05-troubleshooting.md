# 5. Grafana Troubleshooting

Follow the pipeline in order. Run Docker and database commands on the LoRaWAN application server from `/opt/lorawan-lab`; use Grafana through the documented SSH tunnel. Capture the dashboard time range, data-source UID, query text, device filter, expected reporting interval, and last known good timestamp before editing anything:

~~~text
ChirpStack event -> Node-RED insert -> telemetry.uplinks row -> Grafana query -> panel or alert
~~~

## 5.1 Grafana does not open

~~~bash
cd /opt/lorawan-lab
~~~

~~~bash
docker compose ps grafana
~~~

~~~bash
docker compose logs --since=10m --tail=100 grafana
~~~

Healthy output shows the Grafana container running without a restart loop and a listener on the intended loopback address. If the container is running but the UI is unreachable, inspect the source Compose port binding, validate it with `docker compose config --quiet`, and check the listener with `sudo ss -lntp`. For a loopback binding, use the documented SSH tunnel. Do not expose the port publicly as a troubleshooting shortcut.

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

Verify Docker DNS from inside Grafana:

~~~bash
docker compose exec grafana getent hosts telemetry-db
~~~

A healthy result returns a Compose-network address and **Save & test** succeeds with `telemetry_reader`. If DNS fails, fix the shared network or service name. If DNS succeeds, correct only the database name, reader password, SSL mode, or missing read grant reported by Grafana.

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

Healthy rows contain plausible UTC `timestamptz` values and Grafana converts them to the selected display zone. A large difference between `time` and `received_at` indicates a device or source timestamp problem; correct the source mapping or clock. Do not convert timestamps to local strings in Node-RED before inserting.

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

A healthy rule returns the expected test value in **Explore**, changes state after the pending period, and reaches the tested contact point. Create a separate alert query with explicit device filters when the rule is device-specific; dashboard variables are not evaluated as a viewer would expect. After the smallest query or policy correction, repeat the controlled alert test and confirm the no-data state.

## 5.7 Gateway telemetry is visible but evidence is pending, gap, or failure

This is not automatically a Grafana or Node-RED failure.

When the gateway-integrity schema exists, inspect the read-only verification row corresponding to the telemetry source key/time and interpret:

```text
pending
  -> journal/MQTT/ChirpStack/trusted-decoder evidence still waiting

evidence_gap
  -> required evidence is unavailable; follow recovery/gap policy

integrity_failure
  -> contradictory evidence exists; investigate immediately

verified
  -> evidence gate passed; if Fabric is still blocked, inspect outbox/adapter/KMS next
```

Check checkpoint freshness and evidence-service alerts before editing panels or Node-RED. Do not change a dashboard value, SQL row, or verification state simply to make the badge green.

Return to [00-README.md](00-README.md) after the Grafana path is healthy.
