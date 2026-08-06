# LoRaWAN Gateway and Server Documentation

This repository separates the physical gateway from the services that process its traffic:

```text
gateway/ -> Raspberry Pi 4B, RAK5146, Gateway OS, RF, buffering, and field operations
server/  -> MQTT ingress, ChirpStack, cloud, databases, integrations, and server operations
```

Start with [DOCUMENTATION-MAP.md](DOCUMENTATION-MAP.md) and follow the build order instead of configuring individual services in isolation.

## Supported architecture

```text
LoRaWAN device
  -> RAK5146 SPI on Raspberry Pi 4B
  -> ChirpStack Gateway OS Base
  -> ChirpStack Concentratord
  -> ChirpStack MQTT Forwarder, QoS 1
  -> local loopback Mosquitto
  -> finite persistent uplink queue
  -> Mosquitto bridge over mutual TLS
  -> server or cloud MQTT broker
  -> ChirpStack
```

The local Mosquitto broker is the uplink store-and-forward layer. It queues gateway `event` and `state` messages on persistent storage while the WAN or remote broker is unavailable, then forwards them after connectivity returns.

Downlink commands are not intentionally stored for later replay. LoRaWAN receive windows are time-sensitive, so the bridge uses a non-persistent downlink connection and QoS 0 for command topics.

## First-time LoRaWAN concepts

These terms appear throughout the manuals:

- **LoRaWAN region**: the frequency channels, data rates, transmit limits, and regional behavior used by the radio network. The selected region must agree with the country authorization, RAK5146 hardware variant, antenna, Concentratord channel plan, MQTT topic prefix, ChirpStack region, and end-device profile.
- **Gateway EUI or Gateway ID**: the gateway's 64-bit identifier, normally shown as 16 hexadecimal characters by Concentratord. ChirpStack registration, MQTT topics, and the gateway certificate identity use this exact value.
- **Device EUI**: the end device's 64-bit identifier, also written as 16 hexadecimal characters. It identifies the device in ChirpStack; it is not an encryption key and should not be replaced with a device name or asset number.
- **Concentratord**: the Gateway OS service that owns and controls the RAK5146 concentrator. Only one radio service may own the hardware at a time.
- **MQTT**: a publish/subscribe protocol. A broker receives messages on named **topics** and delivers them to authorized subscribers. This project uses local plaintext MQTT only on loopback port `1883` and remote MQTT over TLS on port `8883`.
- **MQTT Forwarder**: the Gateway OS process that reads packets from Concentratord and publishes ChirpStack Protobuf messages. It sends only to the local broker in this architecture.
- **ChirpStack Gateway Bridge**: a protocol-conversion service used by other gateway backends. It is not used for this RAK5146 path because current releases no longer include the Concentratord backend, and it is not a durable outage queue.
- **ChirpStack**: the LoRaWAN network-server platform that handles gateway traffic, joins, device sessions, frame counters, MAC commands, scheduling, applications, and integrations. It runs on the server, not on this gateway.
- **Device profile**: the ChirpStack definition of a device's LoRaWAN region, MAC version, class, capabilities, and payload-codec behavior. Choose it from the exact device model, firmware, and regional variant.
- **OTAA**: Over-the-Air Activation. The device sends a join request and ChirpStack uses its root keys to create session keys. A successful join must be followed by a real uplink before commissioning is complete.
- **Payload codec**: code that converts encrypted application payload bytes, after ChirpStack decrypts them, into named values such as temperature or battery voltage. The codec must match the exact device model and firmware payload format.
- **Certificates**: public-key credentials used here for mutual TLS between the gateway bridge connection and the remote MQTT broker. The certificate identifies the gateway; the matching private key must remain secret.

## Gateway Bridge decision

Do not add the current ChirpStack Gateway Bridge to the gateway for the RAK5146 data path. Current Gateway Bridge releases removed the Concentratord backend; ChirpStack MQTT Forwarder is the supported Concentratord client on Gateway OS.

The Gateway Bridge is not the selected buffering component. Use the open-source Mosquitto broker and its persistent outgoing bridge queue instead.

## Folder map

| Folder | Purpose |
|---|---|
| [gateway/](gateway/00-README.md) | Gateway setup, uplink buffer, RAK5146 references, field operations, and retired gateway manuals |
| [server/](server/00-README.md) | Lab and cloud server deployment, MQTT PKI, ChirpStack, databases, dashboards, and integrations |

## Gateway rules

- Use the official ChirpStack Gateway OS **Base** image for Raspberry Pi 4B.
- Configure RAK5146 through **ChirpStack > Concentratord**.
- Keep UDP Forwarder disabled.
- Configure MQTT Forwarder to publish to `tcp://127.0.0.1:1883`, not directly to the WAN broker.
- Use QoS 1 from MQTT Forwarder to the local broker.
- Use a finite persistent Mosquitto bridge queue for gateway uplinks and state.
- Use a unique gateway certificate for the bridge connection to `ssl://<MQTT_BROKER_FQDN>:8883`.
- Keep the local MQTT listener bound only to loopback.
- Size and test the queue against real uplink rate, message size, storage capacity, and SD-card endurance.
- Treat buffered delivery as at-least-once; integrations must remain idempotent.
- Do not install Raspberry Pi OS, Docker, LoRa Basics Station, Gateway OS Full, a second packet forwarder, or a local ChirpStack Network Server on the gateway.

## Values used by later steps

Keep only values that another step or recovery procedure needs:

| Value | Why it must be retained |
|---|---|
| Gateway management IP or hostname | Used to reopen LuCI and SSH after network changes |
| Confirmed LoRaWAN region and channel plan | Compared across radio hardware, Gateway OS, MQTT topics, ChirpStack, and devices |
| Gateway EUI | Used for ChirpStack registration, certificate identity, client IDs, and MQTT ACLs |
| Device EUI and root-key reference | Used to register and rejoin the end device without placing keys in documentation |
| Remote MQTT FQDN, port, CA, and certificate reference | Used to rebuild and troubleshoot the secure bridge |
| Mosquitto configuration path, queue path, and finite limits | Used to inspect storage growth and reproduce buffering behavior |
| Encrypted backup location and factory-image reference | Used to recover the gateway without overwriting the only known-good copy |

Software versions, image digests, and configuration hashes are useful when they identify a tested rollback state. They do not need separate operator, approval, or paperwork fields.

## Acceptance standard

Documentation is not runtime proof. Final acceptance requires the exact Gateway OS release to boot, Concentratord to initialize the RAK5146, the local broker to persist and replay real uplinks across WAN loss and reboot, mutual TLS and ACL isolation to pass, and real OTAA, uplink, and safe downlink tests to succeed.
