# PostgreSQL and TimescaleDB Telemetry Storage

This folder documents a separate PostgreSQL + TimescaleDB database for long-term LoRaWAN telemetry from multiple sensor models.

The database is intentionally separate from the PostgreSQL database used internally by ChirpStack:

~~~text
LoRaWAN sensor
  -> RAK5146
  -> ChirpStack
  -> MQTT JSON uplink event
  -> Node-RED
  -> telemetry-db
  -> generic uplink hypertable
  -> measurements hypertable
~~~

## Why use a separate telemetry database?

The current ChirpStack deployment uses PostgreSQL for network-server state and enables MQTT integration. Its operational database stores tenants, applications, device profiles, keys, sessions, and frame-counter state. It should not be treated as a stable public telemetry schema for dashboards.

The separate telemetry database provides:

- an explicit application-owned schema;
- time-series compression and retention options;
- read-only access for Grafana;
- write access only for Node-RED;
- simpler backups and restores; and
- protection for ChirpStack when analytical queries become expensive.

## Multi-sensor design

Do not create a PostgreSQL schema for every sensor model. This design uses:

- one telemetry SQL schema;
- one generic uplinks hypertable with one row per ChirpStack event;
- one measurements hypertable with one row per decoded metric;
- a device registry for model, decoder, site, zone, and asset assignment;
- payload_json for fields that have not yet been promoted to reporting columns.

This means the database can be prepared before any sensor arrives. An empty table is a valid and expected state.

## Current deployment assumptions

| Component | Value |
|---|---|
| Host | Raspberry Pi 4B |
| ChirpStack directory | ~/chirpstack-docker |
| MQTT broker hostname | mosquitto |
| MQTT port inside Docker | 1883 |
| Telemetry database hostname | telemetry-db |
| Telemetry database port inside Docker | 5432 |
| Database | lorawan_telemetry |
| Writer | Node-RED |
| Reader | Grafana |
| Sensor data status | No real sensor rows required during installation |
| Timezone policy | Store timestamps in UTC; display local time in Grafana |

## Guide map

| File | Purpose |
|---|---|
| [01-deploy-timescaledb.md](01-deploy-timescaledb.md) | Add a separate TimescaleDB service with persistent storage |
| [02-create-telemetry-schema.md](02-create-telemetry-schema.md) | Create roles, generic multi-sensor tables, hypertables, indexes, views, and retention |
| [03-connect-and-verify.md](03-connect-and-verify.md) | Verify connections, permissions, inserts, and query performance |
| [04-backup-security-and-maintenance.md](04-backup-security-and-maintenance.md) | Backups, restores, credentials, upgrades, retention, and hardening |
| [05-troubleshooting.md](05-troubleshooting.md) | Diagnose database, extension, permission, and performance failures |

## Definition of done

- TimescaleDB starts automatically with the Compose stack.
- The telemetry database has the TimescaleDB extension enabled.
- The schema accepts new sensor metrics without a new PostgreSQL schema.
- Node-RED can insert telemetry as the writer role.
- Grafana can query telemetry as a read-only role.
- Both time-series tables are partitioned by UTC event time.
- Retention is deliberate and documented.
- A tested backup exists before sensor deployment.

## Important rule

Never point Grafana or Node-RED at the ChirpStack core database using the administrative ChirpStack password. Use the dedicated telemetry database and least-privilege roles described here.

Next: [01-deploy-timescaledb.md](01-deploy-timescaledb.md)
