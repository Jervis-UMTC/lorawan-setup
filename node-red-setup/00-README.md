# Node-RED MQTT-to-Timescale Telemetry Pipeline

This folder documents Node-RED as the application integration layer between ChirpStack MQTT and the telemetry database.

~~~text
ChirpStack
  -> Mosquitto MQTT topic: application/+/device/+/event/up
  -> Node-RED MQTT input
  -> JSON validation and normalization
  -> PostgreSQL parameterized insert
  -> telemetry.uplinks hypertable
~~~

Node-RED is used here for explicit transformation and automation. ChirpStack remains responsible for LoRaWAN security, activation, MAC behavior, and payload decoding.

## Guide map

| File | Purpose |
|---|---|
| [01-deploy-node-red.md](01-deploy-node-red.md) | Add the persistent Node-RED container and secure its editor |
| [02-configure-mqtt-and-postgresql.md](02-configure-mqtt-and-postgresql.md) | Configure internal Docker connectivity and palette nodes |
| [03-build-telemetry-flow.md](03-build-telemetry-flow.md) | Build the validation, normalization, and parameterized database flow |
| [04-automation-and-downlinks.md](04-automation-and-downlinks.md) | Add alerts, webhooks, and carefully controlled downlinks |
| [05-testing-and-troubleshooting.md](05-testing-and-troubleshooting.md) | Test each pipeline stage and diagnose failures |

## Design rules

- Subscribe to application uplinks, not gateway statistics, for sensor telemetry.
- Parse MQTT JSON before accessing nested fields.
- Use parameterized PostgreSQL queries; never build SQL by concatenating sensor values.
- Validate device identity and payload shape before inserting.
- Keep the raw decoded object as JSONB for future analysis.
- Do not store AppKeys, NwkKeys, or passwords in flow context or debug messages.
- Treat downlink automation as a separate, reviewed path.

## Definition of done

- Node-RED reconnects after a reboot.
- MQTT input shows a connected status.
- A real ChirpStack uplink is accepted and normalized.
- The PostgreSQL insert succeeds without SQL injection risk.
- Duplicate or malformed events are handled deliberately.
- Grafana can query the resulting rows.

Next: [01-deploy-node-red.md](01-deploy-node-red.md)
