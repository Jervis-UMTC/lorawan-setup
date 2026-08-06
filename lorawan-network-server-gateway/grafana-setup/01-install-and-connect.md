# 1. Install Grafana and Connect to TimescaleDB

Grafana should be attached to the telemetry database, not the ChirpStack operational database.

## 1.1 Confirm the telemetry database exists

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose ps telemetry-db
~~~

If telemetry-db is not healthy, complete the [PostgreSQL and TimescaleDB guide](../postgresql-timescale-setup/00-README.md) first.

## 1.2 Add Grafana to the actual Compose file

~~~bash
nano docker-compose.yml
~~~

Add one Grafana service under services:

~~~yaml
  grafana:
    image: grafana/grafana-oss:latest
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: $GRAFANA_ADMIN_USER
      GF_SECURITY_ADMIN_PASSWORD: $GRAFANA_ADMIN_PASSWORD
      GF_USERS_ALLOW_SIGN_UP: "false"
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      - telemetry-db
~~~

If Grafana already exists, keep one service and add the telemetry-db dependency and persistent volume rather than creating a duplicate.

## 1.3 Declare the Grafana volume

Add this to the top-level volumes section:

~~~yaml
volumes:
  grafana-data:
~~~

Never remove the existing Grafana volume during a routine update. It contains dashboards, users, data-source definitions, and alert rules.

## 1.4 Add Grafana credentials to the private environment file

~~~bash
nano .env
~~~

Use a password that is different from the TimescaleDB and telemetry-role passwords:

~~~dotenv
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=REPLACE_WITH_A_LONG_UNIQUE_PASSWORD
~~~

~~~bash
chmod 600 .env
~~~

The environment password initializes a new Grafana database. If the Grafana volume already contains an account, change the password in the Grafana UI instead.

## 1.5 Start Grafana

~~~bash
docker compose config
~~~

~~~bash
docker compose up -d grafana
~~~

~~~bash
docker compose ps grafana
~~~

~~~bash
docker compose logs --since=5m --tail=100 grafana
~~~

Open the UI:

~~~text
http://<raspberry-pi-ip>:3000
~~~

Sign in with the private admin credentials, then change the password if the first-start environment was temporary.

## 1.6 Create the PostgreSQL data source

In Grafana:

1. Open **Connections**.
2. Open **Data sources**.
3. Select **Add data source**.
4. Select **PostgreSQL**.
5. Configure:

~~~text
Host: telemetry-db:5432
Database: lorawan_telemetry
User: telemetry_reader
Password: the telemetry_reader password
SSL mode: disable for the private Docker network
PostgreSQL version: match the telemetry database
Default database: lorawan_telemetry
~~~

6. Select **Save & test**.

The data source must report a successful connection before dashboard work begins.

## 1.7 Verify Grafana can read the schema

Use **Explore**, select the PostgreSQL data source, and run:

~~~sql
SELECT
    time,
    device_name,
    temperature_c,
    humidity_percent,
    battery_v
FROM telemetry.uplinks
ORDER BY time DESC
LIMIT 20;
~~~

No rows is expected until a sensor sends data. A permission or connection error is not expected.

## 1.8 Use the correct data source boundary

Grafana should not use:

- the ChirpStack core database;
- the ChirpStack administrator role;
- the telemetry writer role;
- MQTT as a dashboard database; or
- a hard-coded sensor password in a panel query.

Grafana needs only SELECT access to telemetry tables and views. [Grafana PostgreSQL data source concepts](https://grafana.com/docs/grafana/latest/datasources/)

Next: [02-build-dashboards.md](02-build-dashboards.md)
