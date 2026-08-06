# LoRaWAN Gateway on Raspberry Pi 4B + RAK5146 (with a self-hosted ChirpStack server)

This is a from-scratch build guide: a bare Raspberry Pi 4B running Raspberry Pi OS **Lite**, a RAK5146 concentrator, and a full ChirpStack v4 LoRaWAN network server running *on the same Pi* in Docker. By the end, one single board is both your gateway and your network server — good for a home/lab network, a field pilot, or learning how the whole stack fits together.

## How this guide is organized

Work through the files in order the first time. After that, they're reference docs — jump to whichever stage you're touching.

| File | What it covers |
|---|---|
| [01-hardware-assembly.md](01-hardware-assembly.md) | Parts list, mounting the RAK5146 on the Pi HAT, antennas, power |
| [02-flash-raspberry-pi-os.md](02-flash-raspberry-pi-os.md) | Flashing Raspberry Pi OS Lite (64-bit) and getting SSH access |
| [03-system-preparation.md](03-system-preparation.md) | raspi-config, static IP, swap, basic hardening |
| [04-lora-concentrator-setup.md](04-lora-concentrator-setup.md) | Installing the RAK5146 driver/packet forwarder, the GPIO fix it usually needs, reading the Gateway EUI |
| [05-docker-installation.md](05-docker-installation.md) | Installing Docker Engine + Compose on 64-bit Pi OS |
| [06-chirpstack-server-deployment.md](06-chirpstack-server-deployment.md) | Deploying the ChirpStack v4 stack with Docker Compose |
| [07-connect-gateway-to-chirpstack.md](07-connect-gateway-to-chirpstack.md) | Wiring the packet forwarder to the local ChirpStack Gateway Bridge, registering the gateway |
| [08-first-device-and-test-uplink.md](08-first-device-and-test-uplink.md) | Tenant, application, device profile, device, and watching your first uplink |
| [dragino-sensor-setup/00-README.md](dragino-sensor-setup/00-README.md) | Complete Dragino end-device onboarding, codec, testing, and troubleshooting guide |
| [postgresql-timescale-setup/00-README.md](postgresql-timescale-setup/00-README.md) | Telemetry PostgreSQL and TimescaleDB storage, schema, retention, backups, and operations |
| [grafana-setup/00-README.md](grafana-setup/00-README.md) | Grafana PostgreSQL data source, dashboards, variables, alerts, and security |
| [node-red-setup/00-README.md](node-red-setup/00-README.md) | MQTT-to-Timescale telemetry flow, automation, downlinks, and troubleshooting |
| [hyperledger-fabric-integration/00-README.md](hyperledger-fabric-integration/00-README.md) | Fabric integration architecture, handoff requirements, data contracts, security, and testing |
| [horizontal-technology-transfer/00-README.md](horizontal-technology-transfer/00-README.md) | How to reuse the agriculture platform for ports and other domains |
| [09-autostart-persistence-hardening.md](09-autostart-persistence-hardening.md) | Boot persistence, backups, firewall, password hygiene, updates |
| [10-troubleshooting.md](10-troubleshooting.md) | The specific failures this stack is known for, and their fixes |

## Architecture

```
 LoRaWAN end devices
        │  RF (sub-GHz)
        ▼
 RAK5146 concentrator (SX1303)
        │  SPI, via RAK2287/RAK5146 Pi HAT (40-pin header)
        ▼
 Raspberry Pi 4B ── Raspberry Pi OS Lite (64-bit)
   │
   ├─ lora_pkt_fwd  (Semtech UDP packet forwarder, installed by rak_common_for_gateway)
   │       │  UDP 1700 (localhost)
   │       ▼
   ├─ Docker: chirpstack-gateway-bridge  ──┐
   │                                       │ MQTT (mosquitto container)
   ├─ Docker: mosquitto                  ◄─┘
   ├─ Docker: chirpstack (core LNS)  ── PostgreSQL, Redis (Docker)
   │       │
   │       ▼
   └─ Web UI: http://<pi-ip>:8080
```

The concentrator talks to the Pi over SPI. The Pi runs the classic Semtech-style packet forwarder as a native process (not containerized — it needs direct SPI/GPIO access), which forwards LoRa packets over UDP to a ChirpStack Gateway Bridge container on the same machine. Everything else — Gateway Bridge, ChirpStack core, Mosquitto, PostgreSQL, Redis — runs in Docker.

## What you'll end up with

- A working LoRaWAN gateway based on the RAK5146/SX1303
- A self-hosted ChirpStack v4 network server, application server, and Gateway Bridge, all on the Pi
- A registered gateway and at least one test device receiving uplinks

## Assumptions made in this guide (change these if they don't fit you)

- **Region/frequency plan**: LoRaWAN frequency plans are set by national regulators, and this matters for both legal compliance and whether your devices will actually talk to your gateway. Based on your general location (Philippines), the LoRa Alliance-designated plan is **AS923-3**. Philippine regulatory guidance on this has had some inconsistency historically, so treat this as a starting point to confirm, not gospel — every place this matters, the guide tells you where to change it if your region is different or if you confirm a different plan applies.
- **OS**: Raspberry Pi OS Lite **64-bit**, and specifically the **Bookworm** (Debian 12) release rather than the newer Trixie (Debian 13). Both work, but the RAK5146's driver stack has more known mileage on Bookworm — see [02](02-flash-raspberry-pi-os.md) for why, and how to use Trixie anyway if you'd rather.
- **ChirpStack version**: v4 (the current major version), deployed via the official `chirpstack/chirpstack-docker` Compose stack.
- **No LTE backhaul** — this guide assumes Ethernet or Wi-Fi to your existing network, not the RAK5146's LTE variant.

## Before you start

Read the parts list in [01-hardware-assembly.md](01-hardware-assembly.md) first — a couple of items (antenna band, power supply amperage) are easy to get wrong when ordering.
