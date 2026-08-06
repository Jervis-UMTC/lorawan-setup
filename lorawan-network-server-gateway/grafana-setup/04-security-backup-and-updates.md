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

1. Open the dashboard.
2. Open **Dashboard settings**.
3. Use **JSON model** or **Export**.
4. Save the export outside the Grafana volume.
5. Record the Grafana version and data-source UID.

Do not export a file containing secret data-source credentials.

## 4.5 Back up the Grafana volume

List the project volumes:

~~~bash
docker volume ls
~~~

Stop only Grafana before copying its SQLite database:

~~~bash
docker compose stop grafana
~~~

Copy the data directory to a backup archive:

~~~bash
docker run --rm -v chirpstack-docker_grafana-data:/data -v "$PWD:/backup" alpine tar czf /backup/grafana-data-$(date +%Y%m%d).tgz -C /data .
~~~

The exact volume prefix may differ if the Compose project name differs. Confirm the volume name with docker volume ls before running the copy command.

Start Grafana again:

~~~bash
docker compose start grafana
~~~

Dashboard JSON exports are still required; a volume archive is a recovery backup, not a substitute for versioned dashboard files.

## 4.6 Update procedure

Before updating:

- export dashboards;
- back up Grafana and telemetry data;
- record the current image tags;
- verify free disk space; and
- schedule a maintenance window.

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

Never delete the Grafana or TimescaleDB volumes during an update.

Next: [05-troubleshooting.md](05-troubleshooting.md)
