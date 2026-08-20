# Grafana Monitoring for ChirpStack Telemetry

Use these guides to connect Grafana to the separate PostgreSQL + TimescaleDB telemetry database, build useful dashboards, and configure alerts.

Run Docker and database commands on the LoRaWAN application server from `/opt/lorawan-lab`. Perform Grafana menu and panel actions in a browser connected through the documented SSH tunnel. The browser reaches Grafana; it does not connect directly to PostgreSQL.

~~~text
ChirpStack MQTT
  -> Node-RED telemetry flow
  -> PostgreSQL / TimescaleDB
       |
       +-> Grafana PostgreSQL data source
       |     -> dashboards, variables, alerts
       |
       +-> optional gateway_evidence verification state
             -> Grafana reads status/freshness only
~~~

Grafana is not a LoRaWAN network server and does not receive RF packets. It visualizes data after ChirpStack has accepted, decrypted, decoded, and stored a device uplink. A rendered value is not automatically current or trustworthy; every operational dashboard must expose timestamp, freshness, and no-data state.

When gateway integrity is enabled, Grafana may also display verifier-owned `pending`, `verified`, `evidence_gap`, and `integrity_failure` state plus checkpoint freshness. Grafana never creates or changes that verification result.

## Values used in this guide

| Component | Value |
|---|---|
| Grafana container | grafana |
| Grafana UI | Prefer `http://127.0.0.1:3000` through an SSH tunnel; use direct LAN binding only when approved |
| PostgreSQL service | telemetry-db |
| Database | lorawan_telemetry |
| Grafana database role | telemetry_reader |
| Telemetry schema | telemetry |
| Main table | telemetry.uplinks |
| Optional evidence schema | gateway_evidence, only after the reviewed integration is deployed |
| Evidence access | Read-only approved status/checkpoint views or tables; never raw evidence mutation |

## Guide map

| File | Purpose |
|---|---|
| [01-install-and-connect.md](01-install-and-connect.md) | Add Grafana, configure the PostgreSQL data source, and secure first login |
| [02-build-dashboards.md](02-build-dashboards.md) | Build latest-value, trend, fleet, link-quality, and battery panels |
| [03-alerting-and-operations.md](03-alerting-and-operations.md) | Create alert rules, contact points, variables, and operating procedures |
| [04-security-backup-and-updates.md](04-security-backup-and-updates.md) | Protect accounts, tokens, dashboards, and upgrades |
| [05-troubleshooting.md](05-troubleshooting.md) | Diagnose data-source, query, time, and dashboard failures |

## Final checks

- Grafana uses telemetry_reader, never the database administrator, Node-RED writer, gateway-evidence verifier writer, OpenBao role, or Fabric adapter identity.
- The PostgreSQL data source reports a successful connection.
- A real uplink appears in Explore.
- A dashboard displays temperature, humidity, battery, RSSI, and SNR when available.
- Dashboard variables can switch between devices.
- Alerts have documented thresholds and no-data behavior.
- When v2 is enabled, dashboards distinguish telemetry freshness from evidence freshness and do not display pending/gap/failure as verified.

Next: [01-install-and-connect.md](01-install-and-connect.md)
