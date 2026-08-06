# Node-RED Telemetry Pipeline

Use these guides to place Node-RED between ChirpStack application MQTT events and the separate PostgreSQL/TimescaleDB telemetry database.

Run Docker and database commands on the LoRaWAN application server from `/opt/chirpstack-docker`. Perform Node-RED editor actions in a browser connected through the documented SSH tunnel. Commands that begin with `docker compose exec` run a process inside the named container; do not run them on the Raspberry Pi gateway.

Node-RED is responsible for:

- subscribing to decoded ChirpStack uplink events;
- validating identifiers, timestamps, fields, units, and ranges;
- deriving a stable event key for retry-safe storage;
- writing one canonical uplink and its normalized measurements to TimescaleDB;
- preserving the decoded object for fields that are not yet normalized;
- optionally producing alerts and carefully controlled downlinks.

It is not responsible for LoRaWAN radio configuration, gateway registration, OTAA session management, or ChirpStack's internal database.

## Read in this order

1. [01-deploy-node-red.md](01-deploy-node-red.md) — Add the persistent Node-RED service and secure the editor.
2. [02-configure-mqtt-and-postgresql.md](02-configure-mqtt-and-postgresql.md) — Configure application MQTT and the telemetry database connection.
3. [03-build-telemetry-flow.md](03-build-telemetry-flow.md) — Build the validation, deduplication, and TimescaleDB insert flow.
4. [04-automation-and-downlinks.md](04-automation-and-downlinks.md) — Add alerts and gated downlink automation only after ingestion is reliable.
5. [05-testing-and-troubleshooting.md](05-testing-and-troubleshooting.md) — Test with isolated synthetic input, then accept a real device uplink.

## Data path

```text
LoRaWAN sensor
  -> RAK5146 gateway
  -> ChirpStack
  -> application/+/device/+/event/up
  -> Node-RED validation and mapping
  -> telemetry.uplinks
  -> telemetry.measurements
  -> Grafana PostgreSQL data source
```

The MQTT topic is case-sensitive. It carries ChirpStack **application** uplinks after network-server processing; gateway `event` topics are a different Protobuf interface and should not be decoded by this flow.

The database target is the Compose service `telemetry-db`, not the core ChirpStack PostgreSQL service. Keeping them separate prevents dashboard retention, schema changes, or analytical queries from damaging ChirpStack control-plane state.

## Prerequisites

Complete these first:

- [Register the gateway and verify a real OTAA uplink](../../../gateway/operations/01-register-and-test.md).
- [Deploy the separate TimescaleDB telemetry database](../timescaledb/00-README.md).

Deploy [Grafana](../grafana/00-README.md) after Node-RED is writing verified telemetry.

The example mapping is tailored to Dragino S31/S31B decoded fields `TempC_SHT31`, `Hum_SHT31`, and `BatV`. Confirm the exact model, firmware payload revision, codec output, units, reporting interval, and stale-data behavior before using the flow with another device.

## Values needed during setup

| Value | Source | Used for |
|---|---|---|
| ChirpStack application MQTT topic and credentials | ChirpStack integration and broker ACL | Node-RED MQTT input |
| Device EUI normalization and stable event-key rule | ChirpStack event contract | Deduplication and database uniqueness |
| `telemetry-db` writer credentials | TimescaleDB role procedure | Parameterized inserts |
| Node-RED credential secret and editor password | Generated during Node-RED deployment | Protecting stored credentials and the editor |
| Device codec fields and units | Verified real uplink or vendor payload specification | Validation and normalized measurements |

Do not expose MQTT, PostgreSQL, or the Node-RED editor to the public internet. Keep internal services on the Compose network, bind the editor to loopback by default, use separate least-privilege identities, and back up Node-RED and TimescaleDB independently.

Next: [01-deploy-node-red.md](01-deploy-node-red.md)
