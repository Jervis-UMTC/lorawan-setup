# Documentation Map

Use this page to choose the correct procedure and carry the required values from one step to the next.

## Repository layout

```text
gateway/
  setup/       -> current Gateway OS installation and uplink-buffer procedure
  operations/  -> registration, outage tests, migration, backup, troubleshooting
  rak5146/     -> reusable RAK5146-specific procedures
  references/  -> hardware PDFs and checklists
  archive/     -> retired non-deployable gateway manuals

server/
  lab/          -> host-simulated application environment
  cloud/        -> cloud deployment and availability
  integrations/ -> TimescaleDB, Node-RED, Grafana, Fabric, and transfer guides
  archive/      -> retired non-deployable server manuals
```

## Supported gateway data path

```text
RAK5146
  -> Concentratord
  -> MQTT Forwarder, QoS 1
  -> local Mosquitto on 127.0.0.1:1883
  -> persistent finite uplink queue
  -> mutual-TLS Mosquitto bridge
  -> remote MQTT broker
  -> ChirpStack
```

Current ChirpStack Gateway Bridge is not used on the gateway because its Concentratord backend was removed. The persistent local MQTT broker provides uplink buffering.

## Build order

1. [Review the gateway domain](gateway/00-README.md) to understand the radio and buffering boundary.
2. [Assemble the gateway](gateway/setup/01-hardware-assembly.md) and confirm the RAK5146 regional variant and antenna.
3. [Install Gateway OS Base](gateway/setup/02-install-chirpstack-gateway-os.md) and keep the management address and rollback image reference.
4. [Configure Concentratord](gateway/setup/03-configure-concentratord.md) and obtain the stable Gateway EUI and region topic prefix.
5. [Prepare the server MQTT broker](server/lab/setup/03-secure-gateway-mqtt.md) on the server that will receive gateway traffic.
6. [Provision the gateway MQTT certificate](server/lab/setup/04-provision-gateway-mqtt-identity.md) using the Gateway EUI from Concentratord.
7. [Configure the persistent local uplink buffer](gateway/setup/04-configure-local-mqtt-buffer.md) and set finite queue limits from the expected outage and traffic rate.
8. [Configure MQTT Forwarder for the local broker](gateway/setup/05-configure-mqtt-forwarder.md) using the same region prefix and Gateway EUI.
9. [Verify buffering and Gateway OS](gateway/setup/06-verify-gateway-os.md), including WAN loss, reboot, queue drain, duplicate handling, and stale-downlink behavior.
10. [Register the gateway and test LoRaWAN](gateway/operations/01-register-and-test.md) with a real OTAA device.

## Values to carry between procedures

| Value | Obtained from | Used later by |
|---|---|---|
| Gateway management IP or hostname | DHCP lease, router, or commissioning network | LuCI, SSH, backup, and troubleshooting |
| Confirmed region and channel plan | Local authorization plus the RAK5146/device variants | Concentratord, MQTT topic prefix, ChirpStack region, and device profile |
| Gateway EUI | Concentratord after the RAK5146 initializes | Certificate issuance, MQTT ACLs, client IDs, and ChirpStack gateway registration |
| Remote MQTT endpoint | Server or cloud broker deployment | Gateway Mosquitto bridge configuration and connectivity tests |
| Gateway CA/certificate/private-key file references | Server-side certificate procedure | Gateway runtime installation and certificate rotation |
| Queue path and finite limits | Buffer sizing and Gateway OS storage inspection | Outage monitoring, overflow response, backup, and restore |
| Device EUI and protected root-key reference | Device label, vendor provisioning record, or secure inventory | ChirpStack device registration and OTAA testing |
| Encrypted backup location | Gateway and database backup procedures | Recovery, upgrades, and migration rollback |

Do not copy live private keys, root keys, passwords, or tokens into the manuals or test records.

## Server starting points

| Goal | Guide |
|---|---|
| Host-simulated lab | [server/lab/00-README.md](server/lab/00-README.md) |
| Cloud deployment | [server/cloud/00-README.md](server/cloud/00-README.md) |
| TimescaleDB | [server/integrations/timescaledb/00-README.md](server/integrations/timescaledb/00-README.md) |
| Node-RED | [server/integrations/node-red/00-README.md](server/integrations/node-red/00-README.md) |
| Grafana | [server/integrations/grafana/00-README.md](server/integrations/grafana/00-README.md) |
| Hyperledger Fabric | [server/integrations/hyperledger-fabric/00-README.md](server/integrations/hyperledger-fabric/00-README.md) |

## How to verify completion

A running service proves only that one process started. Verify the path in layers: radio initialization, local MQTT publication, persistent queue behavior, remote mutual TLS and ACLs, ChirpStack gateway activity, OTAA, decoded uplink, integration storage, and a safe Class A downlink. Keep the exact backup or rollback reference for any configuration that would be difficult to recreate.
