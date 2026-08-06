# Server Documentation

This folder contains the services that receive, process, store, and visualize LoRaWAN traffic away from the physical Gateway OS appliance.

## Folders

| Folder | Purpose |
|---|---|
| [lab/](lab/00-README.md) | Host-simulated ChirpStack, MQTT, telemetry, and Fabric lab |
| [cloud/](cloud/00-README.md) | Cloud architecture, availability, security, migration, and recovery |
| [integrations/](integrations/node-red/00-README.md) | TimescaleDB, Node-RED, Grafana, Hyperledger Fabric, and technology-transfer guides |
| [archive/](archive/05-docker-installation.md) | Retired non-deployable server manuals |

## Service roles

- **Remote MQTT broker** accepts gateway connections over mutual TLS and applies exact topic ACLs. It receives gateway `event` and `state` messages and carries live `command` topics back toward the gateway.
- **ChirpStack** is the LoRaWAN network-server platform. It processes joins, sessions, frame counters, MAC behavior, device profiles, applications, payload codecs, and integrations.
- **PostgreSQL and Redis/Valkey** hold ChirpStack operational state. They are not the application telemetry database.
- **TimescaleDB** stores the application-owned telemetry schema used by Node-RED and Grafana.
- **Node-RED** validates, normalizes, deduplicates, and writes application events. It may publish carefully controlled downlinks through a separate identity.
- **Grafana** reads telemetry through a read-only database role and must show data freshness rather than only the last value.

## Gateway ingress boundary

The remote server receives mutually authenticated MQTT connections from the gateway's local Mosquitto bridge:

```text
Gateway local persistent broker
  -> ssl://<MQTT_BROKER_FQDN>:8883
  -> remote broker
  -> ChirpStack region MQTT backend
```

`<MQTT_BROKER_FQDN>` is the DNS name on the broker certificate. TCP `8883` is the gateway-facing TLS listener. Plaintext MQTT `1883` remains internal to trusted container or loopback networks and must not be published for gateway access.

The gateway certificate identity is restricted to its own Gateway EUI in event, state, and command topics. The current architecture does not deploy a server-side ChirpStack Gateway Bridge and does not use Semtech UDP.

A healthy server path is proven by a real gateway update and device uplink, not only by open ports or running containers.
