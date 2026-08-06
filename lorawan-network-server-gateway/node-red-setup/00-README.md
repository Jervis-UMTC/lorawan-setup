# Node-RED Telemetry Pipeline

This folder documents the Node-RED layer between ChirpStack MQTT and the separate PostgreSQL/TimescaleDB telemetry database.

Node-RED is responsible for:

- subscribing to decoded ChirpStack uplink events;
- validating and normalizing Dragino telemetry;
- writing a stable relational record into TimescaleDB;
- preserving the full decoded object for future fields;
- optionally producing alerts and controlled downlinks.

It is not responsible for LoRaWAN radio configuration, gateway registration, or ChirpStack's internal database.

## Recommended order

1. [01-deploy-node-red.md](01-deploy-node-red.md) — Add the persistent Node-RED service to the existing Compose stack.
2. [02-configure-mqtt-and-postgresql.md](02-configure-mqtt-and-postgresql.md) — Configure MQTT, install the PostgreSQL node, and verify container DNS.
3. [03-build-telemetry-flow.md](03-build-telemetry-flow.md) — Build the MQTT-to-Timescale flow and map Dragino S31/S31B fields.
4. [04-automation-and-downlinks.md](04-automation-and-downlinks.md) — Add alerting and carefully gated downlink automation.
5. [05-testing-and-troubleshooting.md](05-testing-and-troubleshooting.md) — Test without a sensor, then accept the first real uplink.

## Data path

~~~text
Dragino sensor
  -> RAK5146 gateway
  -> ChirpStack Gateway Bridge
  -> ChirpStack MQTT event
  -> Node-RED validation and mapping
  -> telemetry.uplinks hypertable
  -> Grafana PostgreSQL data source
~~~

The MQTT topic used by the flow is:

~~~text
application/+/device/+/event/up
~~~

The database target is the Compose service telemetry-db, not the core ChirpStack PostgreSQL service. Keep these databases separate so dashboard retention and application writes cannot damage ChirpStack's control-plane data.

## Prerequisites

Complete these first:

- [08-first-device-and-test-uplink.md](../08-first-device-and-test-uplink.md)
- [../postgresql-timescale-setup/00-README.md](../postgresql-timescale-setup/00-README.md)
- [../grafana-setup/00-README.md](../grafana-setup/00-README.md) after data is arriving

The Node-RED function example is tailored to the Dragino S31/S31B decoded fields TempC_SHT31, Hum_SHT31, and BatV. Confirm the actual decoded object in ChirpStack before using it with another Dragino model.

## Operational rule

Do not expose MQTT, PostgreSQL, or the Node-RED editor directly to the public internet. Keep them on the Docker network or trusted LAN, use unique credentials, and back up the Node-RED volume and the TimescaleDB database separately.

Next: [01-deploy-node-red.md](01-deploy-node-red.md)
