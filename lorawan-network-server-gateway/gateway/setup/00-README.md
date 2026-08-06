# Raspberry Pi 4B + RAK5146 Gateway OS Setup

Use this sequence to build the gateway for the first time. Each guide assumes the previous guide has passed its checks. Perform LuCI actions from an administration workstation, run Gateway OS shell commands over SSH on the Raspberry Pi, and run linked broker or certificate commands on the application server. Each procedure identifies exceptions before the command block.

## Supported architecture

```text
Raspberry Pi 4B
  -> ChirpStack Gateway OS Base
  -> Concentratord configured for RAK5146
  -> MQTT Forwarder, Protobuf and QoS 1
  -> tcp://127.0.0.1:1883
  -> local Mosquitto persistent queue
  -> ssl://<MQTT_BROKER_FQDN>:8883 with mutual TLS
  -> remote Mosquitto and ChirpStack
```

Gateway OS **Base** contains the gateway radio services without a local ChirpStack server. Gateway OS **Full** also includes local server components and therefore does not match this repository's external-server architecture.

Do not install Raspberry Pi OS, Docker, LoRa Basics Station, Gateway OS Full, Semtech UDP, a second packet forwarder, or a local ChirpStack Network Server.

Do not add current ChirpStack Gateway Bridge for the Concentratord path. Its Concentratord backend was removed; MQTT Forwarder plus local Mosquitto is the supported buffered architecture.

## Read in order

1. [Hardware assembly](01-hardware-assembly.md)
2. [Install Gateway OS Base](02-install-chirpstack-gateway-os.md)
3. [Configure Concentratord](03-configure-concentratord.md)
4. [Configure the persistent local MQTT buffer](04-configure-local-mqtt-buffer.md)
5. [Configure MQTT Forwarder](05-configure-mqtt-forwarder.md)
6. [Verify Gateway OS and buffering](06-verify-gateway-os.md)

Before step 4, prepare the remote broker and gateway identity:

- [Secure the remote MQTT broker](../../server/lab/setup/03-secure-gateway-mqtt.md)
- [Provision the gateway certificate](../../server/lab/setup/04-provision-gateway-mqtt-identity.md)

## Values you must choose or obtain

| Value | How to choose or obtain it | Why it is used later |
|---|---|---|
| Gateway OS Base image | Official Raspberry Pi 4B Base factory image for the selected release | Rebuild and rollback |
| RAK5146 variant and interface | Read the module and HAT labels; this project requires SPI | Concentratord hardware profile and legal RF operation |
| Region, sub-band, antenna gain, and cable loss | Confirm from local authorization, hardware variants, and site design | Channel plan and transmit limits |
| Gateway EUI | Read from Concentratord after hardware initialization | MQTT certificate, topics, ACLs, and ChirpStack registration |
| Remote broker FQDN and port | Obtain from the server deployment; TLS uses port `8883` here | Mosquitto bridge destination |
| Gateway certificate files | Obtain from the certificate-provisioning guide for this Gateway EUI | Mutual TLS authentication |
| Queue limits and free-space reserve | Calculate from peak traffic, measured message size, outage target, and storage capacity | Prevent SD-card exhaustion while retaining the intended outage window |
| Backup location | Choose encrypted storage outside the gateway | Recovery after SD-card or configuration failure |

Placeholders such as `<GATEWAY_EUI>` and `<MQTT_BROKER_FQDN>` must be replaced with these observed or assigned values. Do not replace product/version placeholders until the exact installed release has been checked.

## Required acceptance

- Concentratord initializes RAK5146 and reports a stable Gateway EUI.
- MQTT Forwarder publishes to loopback at QoS 1 with a fixed client ID.
- Local Mosquitto listens only on `127.0.0.1:1883`.
- The persistent queue path survives reboot and is not tmpfs.
- The bridge authenticates to the remote broker with the gateway certificate.
- Exact per-gateway ACL isolation passes.
- Real uplinks are buffered during WAN loss and drained after recovery.
- Buffered QoS 1 duplicates do not create duplicate application records.
- Downlink commands created while disconnected are not replayed as stale commands.
- Queue limits, overflow response, reboot, restore, and SD-card free-space behavior are tested.
- UDP Forwarder remains disabled.
