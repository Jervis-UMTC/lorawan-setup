# PostgreSQL and TimescaleDB Telemetry Storage

Use these guides to build the TimescaleDB-backed telemetry schema. There are **two deployment shapes**:

- local/single-host lab: a separate `telemetry-db` PostgreSQL + TimescaleDB service;
- cloud HA POC: TimescaleDB is installed as an extension on all three Patroni/PostgreSQL members and enabled in the separate logical database `lorawan_telemetry` inside that HA cluster.

Before applying changes, identify which profile you are using and verify PostgreSQL/Timescale versions, database roles, retention policy, and backup state.

Unless a step explicitly opens a `psql` prompt or names another host, run shell commands on the LoRaWAN application server from `/opt/lorawan-lab`. This is the Compose directory created by the server lab procedure; use the actual active Compose directory when adapting the integration to another deployment.

The **logical telemetry database and permissions** remain separate from the ChirpStack database. In the local lab they may also be separate PostgreSQL services; in the cloud HA POC they share one Patroni cluster:

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

## Why keep a separate telemetry database boundary?

The documented ChirpStack deployment uses PostgreSQL for network-server state and enables MQTT integration. Its operational database stores tenants, applications, device profiles, keys, sessions, and frame-counter state. It should not be treated as a stable public telemetry schema for dashboards.

The separate `lorawan_telemetry` database boundary provides:

- an explicit application-owned telemetry schema;
- time-series compression and retention options;
- read-only access for Grafana;
- telemetry write access only for Node-RED;
- a separate `gateway_evidence` schema for the least-privilege verifier/index state when the gateway-integrity integration is enabled;
- simpler backups and restores; and
- protection for ChirpStack when analytical queries become expensive.

The `gateway_evidence` schema is not a per-sensor schema and does not replace `telemetry.uplinks` or `telemetry.measurements`. Large journal segments and captured raw gateway-event objects remain in the protected evidence store; PostgreSQL keeps their hashes, references, lineage, and status.

## Multi-sensor design

Do not create a PostgreSQL schema for every sensor model. This design uses:

- one telemetry SQL schema;
- one generic uplinks hypertable with one row per ChirpStack event;
- one measurements hypertable with one row per decoded metric;
- a device registry for model, decoder, site, zone, and asset assignment;
- payload_json for fields that have not yet been promoted to reporting columns.

This means the database can be prepared before any sensor arrives. An empty table is a valid and expected state.

## Values used in this guide

| Component | Value |
|---|---|
| Host | Application server running the Compose stack |
| Compose directory | `/opt/lorawan-lab` on the application server |
| MQTT broker hostname | mosquitto |
| MQTT port inside Docker | 1883 |
| Telemetry database hostname | telemetry-db |
| Telemetry database port inside Docker | 5432 |
| Database | lorawan_telemetry |
| Telemetry writer | Node-RED |
| Evidence verifier | Separate least-privilege role; updates only gateway-evidence result/state |
| Reader | Grafana |
| Sensor data status | No real sensor rows required during installation |
| Timezone policy | Store timestamps in UTC; display local time in Grafana |

## Guide map

| File | Purpose |
|---|---|
| [01-deploy-timescaledb.md](01-deploy-timescaledb.md) | Local-lab only: add a separate TimescaleDB service; cloud HA uses Timescale inside Patroni instead |
| [02-create-telemetry-schema.md](02-create-telemetry-schema.md) | Create roles, generic multi-sensor tables, hypertables, indexes, views, and retention |
| [03-connect-and-verify.md](03-connect-and-verify.md) | Verify connections, permissions, inserts, and query performance |
| [04-backup-security-and-maintenance.md](04-backup-security-and-maintenance.md) | Backups, restores, credentials, upgrades, retention, and hardening |
| [05-troubleshooting.md](05-troubleshooting.md) | Diagnose database, extension, permission, and performance failures |

## Verify the completed database

- TimescaleDB starts automatically with the Compose stack.
- The telemetry database has the TimescaleDB extension enabled.
- The schema accepts new sensor metrics without a new PostgreSQL schema.
- Node-RED can atomically insert one uplink event and its approved normalized measurements as the telemetry writer role.
- When gateway integrity is enabled, the independent verifier can write only the `gateway_evidence` lineage/result fields it owns and cannot rewrite telemetry values.
- Duplicate event and metric retries do not create extra rows.
- A v2 Fabric-selected event can be joined uniquely to one `gateway_evidence.event_verification` result by source event key and observation time.
- Grafana can query telemetry as a read-only role.
- Both time-series tables are partitioned by UTC event time.
- Retention is deliberate and documented.
- A tested backup exists before sensor deployment.

## Important rule

Never point Grafana or Node-RED at the ChirpStack core database or give either service the telemetry administrator role. Use the dedicated telemetry database, keep port 5432 internal to the Compose network, and use the least-privilege roles described here.

Do not give Node-RED permission to mark gateway evidence `verified`, and do not give the gateway-evidence verifier permission to sign through OpenBao or submit to Fabric. See [Gateway Integrity](../gateway-integrity/00-README.md).

Next: [01-deploy-timescaledb.md](01-deploy-timescaledb.md)
