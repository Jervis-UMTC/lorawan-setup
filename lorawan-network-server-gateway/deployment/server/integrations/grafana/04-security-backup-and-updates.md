# 4. Grafana Security, Backups, and Updates

Grafana exposes sensor data and operational state. Protect it as an internal management application.

## 4.1 Account separation

Use separate accounts for:

- administrator: manages data sources, users, plugins, and server settings;
- operator: views dashboards and acknowledges operational alerts;
- viewer: read-only dashboard access.

Disable anonymous access and public dashboard sharing unless a deliberate access-control design exists.

## 4.2 Network exposure

Keep Grafana port 3000 restricted to the management network. Do not expose telemetry-db port 5432 to the LAN unless remote PostgreSQL administration is required.

The Grafana data source uses telemetry-db:5432 over the internal Docker network. The browser does not need to reach PostgreSQL directly.

## 4.3 Data-source credentials

Grafana should use telemetry_reader. If the password is changed:

1. change the PostgreSQL role password in a controlled window;
2. update the Grafana data source;
3. select **Save & test**; and
4. confirm one dashboard query.

Never use telemetry_writer or telemetry_admin for the Grafana data source.

## 4.4 Export dashboards

For each important dashboard:

1. Open the dashboard and select **Dashboard settings**.
2. Use **JSON model** or **Export**.
3. Save the JSON outside the Grafana volume in the protected configuration backup.
4. Keep the Grafana version and data-source UID with the export because imports can depend on plugin behavior and the data-source reference.
5. Test one exported dashboard in a disposable Grafana instance or after an isolated volume restore.

Do not export a file containing secret data-source credentials.

## 4.5 Back up the Grafana volume

List the project volumes:

~~~bash
docker volume ls
~~~

Identify the exact volume first:

~~~bash
docker volume ls --format '{{.Name}}' | grep 'grafana-data'
~~~

**Stop here. Do not continue** if more than one candidate exists or the volume cannot be tied to the active Compose project.

Stop only Grafana before copying its SQLite database:

~~~bash
docker compose stop grafana
~~~

Create the archive with restrictive permissions. Replace `<GRAFANA_VOLUME>` with the verified volume name:

~~~bash
umask 077
docker run --rm -v <GRAFANA_VOLUME>:/data:ro -v "$PWD:/backup" alpine \
  tar czf /backup/grafana-data-$(date +%Y%m%d-%H%M%S).tgz -C /data .
~~~

Confirm the archive is non-empty and listable before restarting Grafana:

~~~bash
ls -lh grafana-data-*.tgz
tar tzf "$(ls -1t grafana-data-*.tgz | head -1)" | head
~~~

Start Grafana again:

~~~bash
docker compose start grafana
~~~

Dashboard JSON exports are still required; a volume archive is a recovery backup, not a substitute for versioned dashboard files.

## 4.6 Update procedure

Before updating, export the dashboards, back up Grafana and telemetry data, capture the current immutable image reference, verify free disk space, and choose a maintenance window that allows the previous image and volume backup to be restored.

Show current images:

~~~bash
docker compose images grafana
~~~

Pull and restart Grafana:

~~~bash
docker compose pull grafana
~~~

~~~bash
docker compose up -d grafana
~~~

Never delete the Grafana or TimescaleDB volumes during an update. After restart, verify login, data-source health, one dashboard query, one alert rule, and the running image digest. A failed migration or plugin incompatibility should trigger restoration of the previous image and Grafana backup, not deletion of the volume.

Next: [05-troubleshooting.md](05-troubleshooting.md)
