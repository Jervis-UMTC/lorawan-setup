# Data 1. Deploy TimescaleDB for Telemetry

Run these steps on the application-server VM in `/opt/chirpstack-docker`.

Keep the ChirpStack PostgreSQL service unchanged. Telemetry uses a separate database, volume, administrator, writer, and reader.

## Step 1: Confirm the base stack

```bash
cd /opt/chirpstack-docker
docker compose ps
docker compose config --services
docker compose config --images
df -h /var/lib/docker
```

Do not add another database while the ChirpStack database is unhealthy or its volume identity is uncertain.

## Step 2: Back up the Compose project

```bash
cp docker-compose.yml docker-compose.yml.before-telemetry
umask 077
cp .env .env.before-telemetry
```

Do not run `docker compose down -v`.

## Step 3: Add private variables

Add to `.env`:

```dotenv
TELEMETRY_DB_ADMIN_USER=telemetry_admin
TELEMETRY_DB_ADMIN_PASSWORD=<REPLACE_WITH_LONG_UNIQUE_PASSWORD>
TELEMETRY_DB_NAME=lorawan_telemetry
```

```bash
chmod 600 .env
```

## Step 4: Add the database service

Merge this service into the active Compose file:

```yaml
  telemetry-db:
    image: <PINNED_TIMESCALEDB_NON_HA_IMAGE>
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${TELEMETRY_DB_NAME}
      POSTGRES_USER: ${TELEMETRY_DB_ADMIN_USER}
      POSTGRES_PASSWORD: ${TELEMETRY_DB_ADMIN_PASSWORD}
      TIMESCALEDB_TELEMETRY: "off"
    volumes:
      - timescale-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U \"$$POSTGRES_USER\" -d \"$$POSTGRES_DB\""]
      interval: 10s
      timeout: 5s
      retries: 12
```

Declare the named volume:

```yaml
volumes:
  timescale-data:
```

Use an exact tested image tag or digest from the `timescale/timescaledb` non-HA image family. This guide mounts `/var/lib/postgresql/data`; the `timescale/timescaledb-ha` image uses a different data path and must not be substituted without changing and validating the volume mount. Do not publish port 5432; Node-RED, Grafana, and the Fabric adapter use the Docker service name `telemetry-db`.

## Step 5: Start and verify the engine

```bash
docker compose config --quiet
docker compose up -d telemetry-db
docker compose ps telemetry-db
docker compose logs --since=5m --tail=100 telemetry-db
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT version(); SELECT name, default_version FROM pg_available_extensions WHERE name='timescaledb';"
```

The service must remain healthy and the TimescaleDB extension must be available.

## Step 6: Create the telemetry schema and roles

Follow these existing guides in order:

1. [`server/integrations/timescaledb/02-create-telemetry-schema.md`](../../integrations/timescaledb/02-create-telemetry-schema.md)
2. [`server/integrations/timescaledb/03-connect-and-verify.md`](../../integrations/timescaledb/03-connect-and-verify.md)
3. [`server/integrations/timescaledb/04-backup-security-and-maintenance.md`](../../integrations/timescaledb/04-backup-security-and-maintenance.md)

Create these separate roles:

```text
telemetry_writer -> Node-RED INSERT and required SELECT
telemetry_reader -> Grafana SELECT only
fabric_adapter   -> outbox processing and selected telemetry SELECT
```

Do not reuse `telemetry_admin` in an application.

## Step 7: Confirm no host database listener

```bash
docker compose config > /tmp/telemetry.rendered.yml
grep -nE 'telemetry-db|5432|published:|host_ip:' /tmp/telemetry.rendered.yml
sudo ss -lntp | grep ':5432' || true
```

Pass condition: `telemetry-db` is reachable inside the Compose network and no new host listener appears on 5432.
