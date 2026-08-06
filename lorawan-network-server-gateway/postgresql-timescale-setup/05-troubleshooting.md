# 5. PostgreSQL and TimescaleDB Troubleshooting

Diagnose from the database outward. Do not immediately change ChirpStack, Node-RED, and Grafana at the same time.

## 5.1 telemetry-db will not start

~~~bash
docker compose ps telemetry-db
~~~

~~~bash
docker compose logs --since=10m telemetry-db
~~~

Common causes:

- the environment variable names do not match the Compose file;
- the selected image has no arm64 manifest;
- the volume contains an incompatible PostgreSQL major version;
- the Pi is out of disk space; or
- another service is already publishing the selected host port.

Because this design does not publish telemetry-db port 5432, a host-port conflict should not occur. Never delete the data volume as a first troubleshooting action.

## 5.2 TimescaleDB extension is unavailable

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'timescaledb';"
~~~

If no row is returned, the wrong image is running. Use a TimescaleDB image tag that matches the required PostgreSQL major version and supports arm64.

## 5.3 Node-RED cannot connect

Confirm the service name and internal port:

~~~bash
docker compose exec node-red getent hosts telemetry-db
~~~

The Node-RED PostgreSQL configuration must use:

~~~text
Host: telemetry-db
Port: 5432
Database: lorawan_telemetry
User: telemetry_writer
SSL: disabled for the private Docker network, unless TLS is intentionally configured
~~~

Do not use localhost from inside the Node-RED container.

## 5.4 Grafana cannot connect

The Grafana PostgreSQL data source must use telemetry-db:5432, not the host's LAN address. Check the Docker DNS name:

~~~bash
docker compose exec grafana getent hosts telemetry-db
~~~

If DNS works but authentication fails, verify the telemetry_reader password and role grants. Do not solve this by giving Grafana the administrator role.

## 5.5 Rows exist but dashboards are empty

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT count(*) AS uplinks, (SELECT count(*) FROM telemetry.measurements) AS measurements, (SELECT max(time) FROM telemetry.uplinks) AS last_uplink, (SELECT max(time) FROM telemetry.measurements) AS last_measurement;"
~~~

If both counts are zero, that is expected before a sensor arrives. After deployment, fix Node-RED or MQTT first when uplinks remain zero. If uplinks exist but measurements are zero, the generic metric-mapping part of the Node-RED flow is missing or rejecting fields.

## 5.6 Disk or memory pressure

~~~bash
df -h
~~~

~~~bash
free -h
~~~

Reduce dashboard refresh rates, shorten retention, reduce indexes, and move database storage to an SSD if the Pi's SD card is under sustained write load.

## 5.7 Permission errors

Inspect grants:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "\dp telemetry.*"
~~~

Grant only the missing permission. Avoid granting SUPERUSER or broad database ownership to Node-RED or Grafana. New sensor metrics do not require new PostgreSQL grants.

Return to [00-README.md](00-README.md) after the database path is healthy.
