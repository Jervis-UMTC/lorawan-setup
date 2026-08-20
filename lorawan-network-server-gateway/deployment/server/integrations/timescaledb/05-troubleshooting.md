# 5. PostgreSQL and TimescaleDB Troubleshooting

Diagnose from the database outward and change one layer at a time. Run the shell commands in this guide on the LoRaWAN application server from `/opt/lorawan-lab`. Before editing, capture the Compose project, image reference, volume name, PostgreSQL and TimescaleDB versions, schema version, free disk, memory, service state, and last 200 relevant log lines. Do not immediately change ChirpStack, Node-RED, and Grafana together.

## 5.1 telemetry-db will not start

~~~bash
docker compose ps telemetry-db
~~~

~~~bash
docker compose logs --since=10m telemetry-db
~~~

A healthy result shows `telemetry-db` running without a restart loop and logs ending in normal PostgreSQL readiness messages. An exited or repeatedly restarting container means the failure is still in image selection, environment, volume compatibility, storage, or startup configuration.

Common causes:

- the environment variable names do not match the Compose file;
- the selected image has no manifest for the application server's CPU architecture;
- the volume contains an incompatible PostgreSQL major version;
- the application server or Docker volume is out of disk space; or
- another service is already publishing the selected host port.

Because this design does not publish telemetry-db port 5432, a host-port conflict should not occur. Verify the rendered Compose configuration rather than assuming that remains true. Never delete, rename, or reinitialize the data volume as a first troubleshooting action.

If logs report an incompatible database major version, **stop here**. Identify the exact volume and current image, restore the previously compatible image, or attach a new empty volume and restore from a validated backup. Do not force-start or delete the original volume.

## 5.2 TimescaleDB extension is unavailable

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'timescaledb';"
~~~

A healthy result returns one `timescaledb` row and its available version. If no row is returned, the selected container does not provide the extension to this PostgreSQL instance. Verify the exact image tag, host architecture, PostgreSQL major version, and volume history. Use a tested TimescaleDB image that matches the existing PostgreSQL major version and the application server architecture. Do not switch major versions in place. Re-run the query after restarting only `telemetry-db` with the corrected image.

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

A healthy result resolves `telemetry-db` to a Compose-network address. A name-resolution failure means Node-RED is on another network or the service name differs; fix the Compose network or hostname before changing database credentials. Do not use localhost from inside the Node-RED container.

## 5.4 Grafana cannot connect

The Grafana PostgreSQL data source must use telemetry-db:5432, not the host's LAN address. Check the Docker DNS name:

~~~bash
docker compose exec grafana getent hosts telemetry-db
~~~

A healthy result resolves `telemetry-db` inside the Grafana container. If DNS works but authentication fails, verify the `telemetry_reader` password and role grants. If DNS fails, correct the Compose network or service name. Do not solve either problem by giving Grafana the administrator role. Verify the fix with Grafana **Save & test** and one read-only query.

## 5.5 Rows exist but dashboards are empty

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT count(*) AS uplinks, (SELECT count(*) FROM telemetry.measurements) AS measurements, (SELECT max(time) FROM telemetry.uplinks) AS last_uplink, (SELECT max(time) FROM telemetry.measurements) AS last_measurement;"
~~~

If both counts are zero, that is expected only before a sensor or synthetic test arrives. After deployment, fix MQTT or Node-RED when uplinks remain zero. If uplinks exist but measurements are zero, inspect the decoded object, model mapping, `LORAWAN_REGION_ID`, atomic SQL statement, PostgreSQL-node parameter configuration, and measurement uniqueness index. Do not modify Grafana first.

## 5.6 Disk or memory pressure

~~~bash
df -h
~~~

~~~bash
free -h
~~~

Healthy operation has enough free memory and disk for expected ingestion, queries, backups, and PostgreSQL maintenance. First identify the largest hypertables, old chunks, container logs, and filesystem consumers. Reduce dashboard refresh rates and unnecessary logging. Do not shorten retention or remove indexes without query evidence, a defined retention requirement, and a validated backup. Moving storage to an SSD requires a separate migration and rollback plan; do not copy a live PostgreSQL volume casually.

## 5.7 Permission errors

Inspect grants:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "\dp telemetry.*"
~~~

Grant only the missing permission after identifying the exact failing statement and role. Avoid granting `SUPERUSER`, database ownership, schema ownership, or broad default privileges to Node-RED or Grafana. New sensor metrics do not require new PostgreSQL grants. Re-run the positive writer and negative reader tests after any grant change.

Return to [00-README.md](00-README.md) after the database path is healthy.
