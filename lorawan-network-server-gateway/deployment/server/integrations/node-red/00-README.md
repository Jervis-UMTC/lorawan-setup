# Node-RED Telemetry Pipeline

Use these guides to place Node-RED between ChirpStack application MQTT events and the **logically separate** PostgreSQL/TimescaleDB telemetry database.

There are two deployment profiles:

```text
single-host lab
  MQTT host: mosquitto:1883
  DB host:   telemetry-db:5432

three-Droplet cloud HA POC
  MQTT host: <COMMISSIONED_NODE_RED_MQTT_ROUTE> over TLS
  TLS name:  mqtt.internal.lorawan.com unless a later phase issues a different broker service identity
  DB host:   pgbouncer.internal.lorawan.com:6432 -> HAProxy -> Patroni primary
  DB name:   lorawan_telemetry with TimescaleDB enabled
```

The cloud POC does **not** create a separate TimescaleDB server; it keeps `lorawan_telemetry` as a Timescale-enabled logical database inside the Patroni cluster.

> **Current cloud route:** Phase 12A defines Node-RED on `ulc-03` using `mqtt.internal.lorawan.com:18884` mapped to `10.104.0.8`. That private HAProxy frontend routes to the two existing Mosquitto mTLS `:8884` backends. The ingestion client certificate has read-only `application/+/device/+/event/up` permission. Do not use the obsolete `mqtt-ha.internal.<DOMAIN>:18883` design or the ChirpStack-specific `:18883 -> :8885` route.

Unless a section explicitly says **cloud HA POC**, the older Docker examples assume the single-host lab at `/opt/lorawan-lab`. Perform Node-RED editor actions in a browser connected through the documented SSH tunnel. Commands that begin with `docker compose exec` run a process inside the named container; do not run them on the Raspberry Pi gateway.

Node-RED is responsible for:

- subscribing to decoded ChirpStack uplink events;
- validating identifiers, timestamps, fields, units, and ranges;
- deriving a stable event key for retry-safe storage;
- writing one canonical uplink and its normalized measurements to TimescaleDB;
- preserving the decoded object and raw application `data` needed for later comparison;
- optionally producing alerts and carefully controlled downlinks.

It is not responsible for LoRaWAN radio configuration, gateway registration, OTAA session management, ChirpStack's internal database, or declaring gateway-integrity evidence `verified`.

For `telemetry-attestation-v2`, Node-RED is deliberately **not the sole evidence authority**. The independent [Gateway Integrity](../gateway-integrity/00-README.md) verifier links the gateway journal to the captured remote gateway MQTT event and accepted ChirpStack application event, runs a pinned trusted decoder outside Node-RED, compares that result with TimescaleDB, and writes the verification state.

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
  -> telemetry.uplinks + telemetry.measurements
       |
       +-> Grafana PostgreSQL data source
       |
       +-> gateway-integrity verifier comparison
              -> trusted decoder vs stored normalized values
              -> pending / verified / evidence_gap / integrity_failure
              -> v2 Fabric eligibility only when verified
```

The MQTT topic is case-sensitive. It carries ChirpStack **application** uplinks after network-server processing; gateway `event` topics are a different Protobuf interface and should not be decoded by this flow.

In the single-host lab, the database target is the Compose service `telemetry-db`. In the cloud HA POC, the target is the logical database `lorawan_telemetry` through local PgBouncer/HAProxy. In both profiles, Node-RED must never write to ChirpStack's `chirpstack` database.

## Prerequisites

Complete these first:

- [Register the gateway and verify a real OTAA uplink](../../../gateway/operations/01-register-and-test.md).
- Prepare the TimescaleDB telemetry profile from [TimescaleDB Telemetry Storage](../timescaledb/00-README.md): single-host lab uses `telemetry-db`; the cloud HA POC enables TimescaleDB in `lorawan_telemetry` on the Patroni cluster.
- For gateway-verified v2 evidence, complete the [Gateway Integrity](../gateway-integrity/00-README.md) contracts and reviewed server implementation before enabling v2 Fabric selection.

Deploy [Grafana](../grafana/00-README.md) after Node-RED is writing accepted telemetry. A normal Node-RED database row is application-accepted telemetry; it becomes gateway-verified evidence only after the independent verifier passes.

The primary project mapping is the frozen **EMU-01 Agriculture Kit payload v2**: 46 bytes decoded by ChirpStack into `test_sequence`, `sensor_validity_bitmap`, soil, UV, barometer, both light sensors, environmental values, rain state, and battery. The Node-RED flow preserves the complete decoded object and normalizes those reviewed fields. SEC-02's temporary 6-byte RAK12011 verification payload is a different mapping and must not be silently fed into the EMU-01 flow.

## Values needed during setup

| Value | Source | Used for |
|---|---|---|
| ChirpStack application MQTT topic and credentials | ChirpStack integration and broker ACL | Node-RED MQTT input |
| Device EUI normalization and stable event-key rule | ChirpStack event contract | Deduplication and database uniqueness |
| `telemetry_writer` credentials and the selected DB endpoint (`telemetry-db` lab or PgBouncer cloud) | TimescaleDB role procedure / cloud HA runbook | Parameterized inserts |
| Node-RED credential secret and editor password | Generated during Node-RED deployment | Protecting stored credentials and the editor |
| Device codec fields and units | Verified real uplink or vendor payload specification | Validation and normalized measurements |

Do not expose MQTT, PostgreSQL, or the Node-RED editor to the public internet. Keep internal services on the Compose network, bind the editor to loopback by default, use separate least-privilege identities, and back up Node-RED and TimescaleDB independently.

Next: [01-deploy-node-red.md](01-deploy-node-red.md)
