# Raspberry Pi 4B and RAK5146 Gateway Setup

Follow these manuals in order to build a Raspberry Pi 4B gateway with a RAK5146 SPI concentrator and connect it to an external ChirpStack server.

The completed gateway uses this path:

```text
RAK5146
  -> ChirpStack Concentratord
       |
       +-> delivery: MQTT Forwarder
       |     -> local Mosquitto on 127.0.0.1:1883
       |     -> persistent uplink queue
       |     -> remote MQTT broker over mutual TLS
       |     -> ChirpStack
       |
       +-> evidence: integrity journal
             -> record/segment hash chain
             -> cloud checkpoint + segment upload
```

ChirpStack Gateway OS **Base** is used because the ChirpStack server runs elsewhere. Do not install Gateway OS Full, Raspberry Pi OS, a second packet forwarder, or a local ChirpStack server for this setup.

## How to use these manuals

Each manual starts where the previous one ends. Complete its checks before moving to the next file.

Commands are run in one of these places:

- **Administration workstation** — downloading and flashing the image, copying certificates, and opening the web interface.
- **Gateway web interface** — ChirpStack Gateway OS configuration through LuCI.
- **Gateway SSH shell** — commands run as `root` on the Raspberry Pi.
- **Application server** — broker, certificate, and ChirpStack commands linked from the relevant step.

Replace every value written inside angle brackets before running a command. For example, replace `<GATEWAY_IP>` with the gateway address and `<GATEWAY_EUI>` with the 16-character ID shown by Concentratord.

## Engineering/build-first note

When preparing the full v2 evidence path on a workstation, start the pinned Rust build (`evidence-services/gateway/scripts/dev-build.ps1`) before the physical setup sequence. That build currently validates the journal core and warms the Cargo cache; it does **not** yet produce an installable Gateway OS package. Finish the writer/uploader runtime and package before Step 4A is treated as deployable.

## Setup order

1. [Assemble the Raspberry Pi and RAK5146](01-hardware-assembly.md)
2. [Install ChirpStack Gateway OS Base](02-install-chirpstack-gateway-os.md)
2A. [Build a SIM7600-capable Gateway OS image when the official Base kernel lacks the modem drivers](02a-build-sim7600-capable-gateway-os.md)
3. [Configure Concentratord](03-configure-concentratord.md)
4. [Configure the persistent local MQTT buffer](04-configure-local-mqtt-buffer.md)
4A. [Configure the software-only gateway integrity journal](04a-configure-gateway-integrity-journal.md)
5. [Configure MQTT Forwarder](05-configure-mqtt-forwarder.md)
6. [Verify the complete gateway](06-verify-gateway-os.md)

Before configuring the local MQTT buffer, complete these server-side procedures:

- [Secure the remote MQTT broker](../../server/ha-cluster/11-secure-gateway-mqtt.md)
- [Provision the gateway MQTT identity](../../server/ha-cluster/12-provision-gateway-mqtt-identity.md)

## Values used across the manuals

| Placeholder | Meaning |
|---|---|
| `<GATEWAY_IP>` | Ethernet or Wi-Fi management address of Gateway OS |
| `<GATEWAY_EUI>` | Stable 16-hexadecimal gateway ID reported by Concentratord |
| `<REGION_TOPIC_PREFIX>` | ChirpStack MQTT region prefix (set to `as923` for Philippines AS923 / AS923-1 deployment) |
| `<MQTT_BROKER_FQDN>` | DNS name of the remote MQTT broker |
| `<GATEWAY_OS_IMAGE>` | Official Raspberry Pi 4B Gateway OS Base image filename |
| `<BUFFER_MAX_MESSAGES>` | Maximum number of queued QoS 1 messages |
| `<BUFFER_MAX_BYTES>` | Maximum storage used by queued messages |
| `<BUFFER_AUTOSAVE_SECONDS>` | Mosquitto persistence save interval |
| `<PINNED_JOURNAL_VERSION>` | Reviewed gateway journal implementation/version |
| `<JOURNAL_STORAGE_BUDGET>` | Finite persistent space reserved for unuploaded evidence |
| `<EVIDENCE_INGEST_FQDN>` | Server endpoint that accepts gateway checkpoints/segments |

Do not place private keys, passwords, join keys, or live tokens in these Markdown files.

## Required result

At the end of the sequence:

- the RAK5146 starts with the correct regional channel plan;
- MQTT Forwarder publishes only to the loopback broker;
- the local broker keeps a finite persistent uplink queue;
- the journal independently records the supported Concentratord event path, preserves sequence/hash continuity, and has a finite evidence budget;
- cloud checkpoints anchor the connected history and missing segments upload after recovery;
- the remote bridge authenticates with the gateway certificate;
- uplinks survive a tested WAN outage and drain after recovery;
- stale downlinks are not replayed after a long outage;
- UDP Forwarder remains disabled.
