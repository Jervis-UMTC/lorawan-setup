# 1. Deploy the Separate TimescaleDB Service

This stage adds a second database service for telemetry. It does not replace the PostgreSQL service used by ChirpStack.

## 1.1 Verify the existing Compose project

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose ps
~~~

The existing services should be stable before adding another database. In particular, do not use the telemetry database to hide a failing ChirpStack PostgreSQL service.

## 1.2 Back up the Compose manifest

~~~bash
cp docker-compose.yml docker-compose.yml.before-timescaledb
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

Open the actual Compose file on the Raspberry Pi:

~~~bash
nano docker-compose.yml
~~~

Add this service under services:

~~~yaml
  telemetry-db:
    image: timescale/timescaledb:latest-pg14
    restart: unless-stopped
    environment:
      POSTGRES_DB: $TELEMETRY_DB_NAME
      POSTGRES_USER: $TELEMETRY_DB_ADMIN_USER
      POSTGRES_PASSWORD: $TELEMETRY_DB_ADMIN_PASSWORD
      TIMESCALEDB_TELEMETRY: "off"
    volumes:
      - timescale-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $TELEMETRY_DB_ADMIN_USER -d $TELEMETRY_DB_NAME"]
      interval: 10s
      timeout: 5s
      retries: 12
~~~

The image keeps PostgreSQL 14 compatibility with the existing project. The Timescale image publishes PostgreSQL-specific tags instead of one floating latest tag. For production, record and pin the exact tested image digest after confirming that it supports the Pi's arm64 platform. [Timescale Docker image information](https://hub.docker.com/r/timescale/timescaledb/)

Do not publish port 5432 for this internal-only database. Node-RED and Grafana connect through the Docker service name telemetry-db.

## 1.5 Add the named volume

Under the existing top-level volumes section, add:

~~~yaml
volumes:
  postgresqldata:
  redisdata:
  timescale-data:
~~~

Preserve all existing volume names. A volume name is part of the data identity; renaming it can make an existing database appear to have disappeared.

## 1.6 Validate the Compose file

~~~bash
docker compose config
~~~

If Compose reports a missing variable, YAML indentation error, or duplicate service, fix it before starting the service.

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

Wait until the health check passes before creating the schema.

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
