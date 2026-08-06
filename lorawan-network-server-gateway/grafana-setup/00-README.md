# Grafana Monitoring for ChirpStack Telemetry

This folder documents Grafana dashboards and alerting over the separate PostgreSQL + TimescaleDB telemetry database.

~~~text
ChirpStack MQTT
  -> Node-RED telemetry flow
  -> PostgreSQL / TimescaleDB
  -> Grafana PostgreSQL data source
  -> dashboards, variables, alerts
~~~

Grafana is not a LoRaWAN network server and does not receive RF packets. It visualizes data after ChirpStack has accepted, decrypted, and decoded a device uplink.

## Current deployment assumptions

| Component | Value |
|---|---|
| Grafana container | grafana |
| Grafana UI | http://<raspberry-pi-ip>:3000 |
| PostgreSQL service | telemetry-db |
| Database | lorawan_telemetry |
| Grafana database role | telemetry_reader |
| Telemetry schema | telemetry |
| Main table | telemetry.uplinks |

## Guide map

| File | Purpose |
|---|---|
| [01-install-and-connect.md](01-install-and-connect.md) | Add Grafana, configure the PostgreSQL data source, and secure first login |
| [02-build-dashboards.md](02-build-dashboards.md) | Build latest-value, trend, fleet, link-quality, and battery panels |
| [03-alerting-and-operations.md](03-alerting-and-operations.md) | Create alert rules, contact points, variables, and operating procedures |
| [04-security-backup-and-updates.md](04-security-backup-and-updates.md) | Protect accounts, tokens, dashboards, and upgrades |
| [05-troubleshooting.md](05-troubleshooting.md) | Diagnose data-source, query, time, and dashboard failures |

## Definition of done

- Grafana uses telemetry_reader, never the database administrator.
- The PostgreSQL data source reports a successful connection.
- A real uplink appears in Explore.
- A dashboard displays temperature, humidity, battery, RSSI, and SNR when available.
- Dashboard variables can switch between devices.
- Alerts have documented thresholds and no-data behavior.

Next: [01-install-and-connect.md](01-install-and-connect.md)
