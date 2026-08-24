# 1. Deploy the Separate TimescaleDB Service - Local Lab Profile

Use this procedure only for the **local/single-host lab profile**, where telemetry runs as a separate `telemetry-db` service.

For the three-server cloud HA POC, **do not deploy this extra container**. Instead install the same pinned TimescaleDB extension build on all three Patroni/PostgreSQL members and enable it in `lorawan_telemetry`; follow [../../cloud-production/06-spilo-patroni-postgresql-cluster.md](../../cloud-production/06-spilo-patroni-postgresql-cluster.md).

## 1.1 Verify the existing Compose project

~~~bash
cd /opt/lorawan-lab
~~~

~~~bash
docker compose ps
~~~

The existing services should be stable before adding another database. Inspect `docker compose config --services`, `docker compose config --images`, current volumes, and free disk space so the new service does not reuse an unexpected volume or exhaust the host. Do not use the telemetry database to hide a failing ChirpStack PostgreSQL service.

## 1.2 Back up the Compose manifest

~~~bash
cp compose.yml compose.yml.before-timescaledb
~~~

Do not run docker compose down with the -v option. Removing volumes can destroy the existing ChirpStack database.

## 1.3 Create private database variables

~~~bash
nano .env
~~~

Add these variables with private values:

~~~dotenv
TELEMETRY_DB_ADMIN_USER=telemetry_admin
TELEMETRY_DB_ADMIN_PASSWORD=REPLACE_WITH_A_LONG_UNIQUE_PASSWORD
TELEMETRY_DB_NAME=lorawan_telemetry
~~~

Restrict the file:

~~~bash
chmod 600 .env
~~~

The administrative password is used only to initialize the separate database. Node-RED and Grafana will receive different roles later.

## 1.4 Add the TimescaleDB service

Open the actual Compose file on the application server:

~~~bash
nano compose.yml
~~~

Add this service under services:

~~~yaml
  telemetry-db:
    image: ${TIMESCALEDB_IMAGE}
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${TELEMETRY_DB_NAME}
      POSTGRES_USER: ${TELEMETRY_DB_ADMIN_USER}
      POSTGRES_PASSWORD: ${TELEMETRY_DB_ADMIN_PASSWORD}
      TIMESCALEDB_TELEMETRY: "off"
    volumes:
      - telemetry-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \"$$POSTGRES_USER\" -d \"$$POSTGRES_DB\""]
      interval: 10s
      timeout: 5s
      retries: 12
    networks: [telemetry]
~~~

Set `TIMESCALEDB_IMAGE` in `/opt/lorawan-lab/.env` to an exact tested tag or immutable digest from the `timescale/timescaledb` non-HA image family that declares the required PostgreSQL major version and supports the server CPU architecture. This guide mounts `/var/lib/postgresql/data`; the `timescale/timescaledb-ha` image uses a different data path and must not be substituted without changing and validating the volume mount. Keep the exact image reference with the database backup and volume identity before first start because PostgreSQL-major compatibility is required for restore. Do not use a floating tag for a recoverable deployment. [Timescale Docker image information](https://hub.docker.com/r/timescale/timescaledb/)

Do not publish port 5432 for this internal-only database. Node-RED and Grafana connect through the Docker service name telemetry-db.

## 1.5 Add the named volume

The canonical lab topology already declares the top-level volume:

~~~yaml
volumes:
  telemetry-data:
~~~

If you are adapting this guide outside the canonical lab, add `telemetry-data:` under the existing top-level `volumes:` block without replacing other volume entries. A volume name is part of the data identity; if `telemetry-data` already exists, identify its Compose project, PostgreSQL major version, and backup state before attaching it. Initialization environment variables do not reset credentials or database names in a non-empty PostgreSQL volume.

**Stop here. Do not continue** if the volume identity is uncertain, the existing major version differs from the selected image, or no recoverable backup exists.

## 1.6 Validate the Compose file

~~~bash
docker compose config --quiet
docker compose config --images
grep -nE 'telemetry-db|5432|telemetry-data|ports:|host_ip:' compose.yml
~~~

`docker compose config --quiet` must exit without an error. `docker compose config --images` must show the exact pinned image selected for `telemetry-db`. The source-file inspection must show the intended service and volume without a host-published database port. If any result differs, fix the variable, indentation, service name, volume, or port declaration before starting the service. Avoid printing the fully rendered Compose file to an unprotected terminal because it can expand values from `.env`.

## 1.7 Start TimescaleDB

~~~bash
docker compose up -d telemetry-db
~~~

~~~bash
docker compose ps telemetry-db
~~~

~~~bash
docker compose logs --since=5m --tail=100 telemetry-db
~~~

Wait until the health check passes and the container remains stable without restart loops before creating the schema. Repeated initialization, password errors, or an incompatible-data-directory message usually means the wrong volume or PostgreSQL major is attached; stop and identify the volume rather than deleting it. A healthy container proves PostgreSQL readiness only; it does not prove the TimescaleDB extension, schema, roles, retention, or backups are correct.

## 1.8 Verify the database engine

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c 'SELECT version();'
~~~

Verify that the TimescaleDB extension is available:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT name, default_version FROM pg_available_extensions WHERE name = 'timescaledb';"
~~~

Do not continue if the extension is unavailable. The container image or architecture tag is wrong for the host.

Next: [02-create-telemetry-schema.md](02-create-telemetry-schema.md)
