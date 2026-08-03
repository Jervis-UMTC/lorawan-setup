# LoRaWAN & ChirpStack v4 Enterprise Infrastructure Documentation

Welcome to the comprehensive technical documentation repository for the **End-to-End LoRaWAN Network Infrastructure** deployed with **ChirpStack v4**, **Milesight LoRaWAN Gateways**, and **Dragino LSN50v2-S31 End-Nodes**.

This documentation suite provides exhaustive installation steps, architectural specifications, networking topologies, configuration templates, payload codec reference code, and troubleshooting runbooks for operating a production-ready LoRaWAN network server on containerized Linux environment.

---

## 🏛️ System Architecture & Network Topology

The architecture leverages a 4-tier model designed for low-power long-range sensor telemetry transmission, edge forwarder conversion, MQTT message broker encapsulation, state management, and payload decoding.

```text
+-----------------------------------------------------------------------------------+
|                        Tier 1: Field Layer (End-Nodes)                            |
|  • Dragino LSN50v2-S31 Sensor (DevEUI: A84041380189B98F / AppKey: FD7A9B94...)    |
|  • Additional LoRaWAN End-Nodes (Class A / Class B / Class C)                     |
+-----------------------------------------------------------------------------------+
                                         |
                                         | LoRa RF (868 MHz / 915 MHz / 923 MHz)
                                         v
+-----------------------------------------------------------------------------------+
|                      Tier 2: Edge & Gateway Layer                                 |
|  • Milesight LoRaWAN Gateway (UG65 / UG67)                                        |
|  • Semtech UDP Packet Forwarder                                                   |
+-----------------------------------------------------------------------------------+
                                         |
                                         | Semtech UDP Packets (UDP Port 1700)
                                         v
+-----------------------------------------------------------------------------------+
|       Tier 3: Network Server Infrastructure (Ubuntu VM - Bridged IP)              |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | ChirpStack Gateway Bridge (UDP Port 1700 Listener -> MQTT Converter)         |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | Mosquitto MQTT Broker (TCP Port 1883 Message Bus)                           |  |
|  +-----------------------------------------------------------------------------+  |
|                                         ^                                         |
|                                         v                                         |
|  +-----------------------------------------------------------------------------+  |
|  | ChirpStack v4 Core Server (HTTP Dashboard Port 8080 & gRPC API)            |  |
|  +-----------------------------------------------------------------------------+  |
|                         |                               |                         |
|                         v                               v                         |
|  +------------------------------+             +--------------------------------+  |
|  | PostgreSQL 14 Database       |             | Redis 7 Cache Engine           |  |
|  | (Persistent State & Metadata)|             | (Session State & Deduplication)|  |
|  +------------------------------+             +--------------------------------+  |
+-----------------------------------------------------------------------------------+
                                         |
                                         | HTTP (Port 8080) / MQTT / Webhooks
                                         v
+-----------------------------------------------------------------------------------+
|                   Tier 4: Application & Integration Layer                         |
|  • ChirpStack Web Dashboard (http://<VM-IP>:8080)                                 |
|  • External Integrations (HTTP Webhooks, InfluxDB, Grafana dashboards)            |
+-----------------------------------------------------------------------------------+
```

---

## 📄 Repository & Documentation Structure

```text
lorawan-setup/
└── docs/
    ├── README.md                               # Master Overview & Sequential Reading Index
    ├── 01-master-deployment-guide.md           # [Step 1] Master LoRaWAN Infrastructure Deployment Guide
    ├── 02-offline-direct-ap-setup-guide.md     # [Step 2] Offline Direct Gateway AP Setup Guide
    ├── 03-postgres-integration-guide.md        # [Step 3] PostgreSQL Event Persistence & Integration Guide
    ├── 04-grafana-integration-guide.md         # [Step 4] Grafana Real-Time Visualization & Dashboard Guide
    ├── 05-node-red-integration-guide.md        # [Step 5] Node-RED Flow Automation & Webhook Integration Guide
    ├── configs/                                # Standard Configuration Templates
    │   ├── docker-compose.yml                  # Docker Compose Stack Manifest
    │   ├── chirpstack.toml                     # Core ChirpStack v4 Configuration File
    │   └── chirpstack-gateway-bridge.toml      # Gateway Bridge UDP/MQTT Converter Config
    └── codecs/                                 # Payload Codecs & Parsers
        └── dragino-lsn50v2-s31-decoder.js      # Dragino LSN50v2-S31 JavaScript Decoder
```

---

## 📖 Sequential Documentation Reading Index

The original 01-05 path documents the existing Milesight/Dragino deployment. Documents 06-08 add RF/security work, while document 09 is the separate incoming RAK5146/WisBlock commissioning path.

Follow these guides sequentially from **01** to **09** to build, configure, persist, visualize, automate, security-test, and commission the incoming RAK/WisBlock hardware:

| Sequence | Document | Focus Area | Description |
| :---: | :--- | :--- | :--- |
| **01** | **[01: Master Deployment Guide](./01-master-deployment-guide.md)** | **Foundation & Stack Setup** | Master operations manual covering hypervisor setup, Ubuntu VM provisioning, online Docker installation, gateway packet forwarding, ChirpStack web management, OTAA security keys, and JavaScript payload parsing. |
| **02** | **[02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md)** | **Offline Direct AP Mode** | Complete guide for operating when connected directly to `Gateway_F94C0B` Wi-Fi AP without internet access. Covers hypervisor bridged Wi-Fi NIC selection, static IP (`192.168.23.137`), netplan, default gateway routes (`192.168.23.150`), and pre-cached Docker images. |
| **03** | **[03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md)** | **Database Event Persistence** | Guide for creating the `chirpstack_integration` database, configuring DSN in `chirpstack.toml`, inspecting `event_up` schemas, and executing JSONB SQL queries for telemetry extraction. |
| **04** | **[04: Grafana Integration Guide](./04-grafana-integration-guide.md)** | **Visualization & Dashboards** | Guide for containerizing Grafana (`:3000`), connecting PostgreSQL Data Source (`postgres:5432`), writing `$__timeFilter` SQL queries, and constructing live telemetry gauges and trend charts. |
| **05** | **[05: Node-RED Integration Guide](./05-node-red-integration-guide.md)** | **Flow Automation & Alerts** | Guide for containerizing Node-RED (`:1880`), installing `@chirpstack/node-red-contrib-chirpstack` palette nodes, subscribing to MQTT uplinks (`mosquitto:1883`), and triggering threshold alerts. |
| **06** | **[06: LoRaWAN RF and Security Toolkit Brief](./06-lorawan-rf-security-toolkit-brief.md)** | **Tool Selection & Architecture** | Boss-facing decision brief establishing gr-lora-sdr and Wireshark for RF PHY decoding, protocol dissection, packet inspection, and security testing. |
| **07** | **[07: LoRaWAN RF and Protocol Testing Setup Guide](./07-lorawan-rf-and-protocol-testing-setup-guide.md)** | **RF-to-Protocol Test Bench** | Comprehensive setup and verification path for gr-lora-sdr and Wireshark testing and security testing integration. |
| **08** | **[08: LoRaWAN Security Testing Runbook](./08-lorawan-security-testing-runbook.md)** | **Authorized Test Operations** | Pre-flight checks, evidence handling, gr-lora-sdr and Wireshark security test cases, triage workflow, stop conditions, and reporting template for a private lab. |
| **09** | **[09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md)** | **Incoming Hardware Commissioning** | Arrival acceptance, RAK5146 SPI/AS923 gateway assembly, packet-forwarder setup, WisBlock node programming, OTAA onboarding, and end-to-end acceptance gates. |
| **Ref** | **[Docker Compose Configuration](./configs/docker-compose.yml)** | **Infrastructure Manifest** | Full `docker-compose.yml` service definition for ChirpStack, Gateway Bridge, Mosquitto, PostgreSQL, Redis, Grafana, and Node-RED. |
| **Ref** | **[ChirpStack Config](./configs/chirpstack.toml)** | **Core Server Config** | Configuration parameters for PostgreSQL, Redis, MQTT topics, and region profiles. |
| **Ref** | **[Gateway Bridge Config](./configs/chirpstack-gateway-bridge.toml)** | **Packet Forwarder Config** | UDP listener parameters and MQTT output topic mapping. |
| **Ref** | **[Dragino JS Decoder](./codecs/dragino-lsn50v2-s31-decoder.js)** | **Payload Codec** | Production JavaScript parser for decoding temperature, humidity, and battery voltage bytes. |

---

## 🛠️ System Specifications & Bill of Materials

### 1. Hardware Requirements
* **Gateway**: Milesight UG65 / UG67 Industrial LoRaWAN Gateway (Semtech SX1302/SX1303 chipset).
* **End-Node**: Dragino LSN50v2-S31 Temperature & Humidity Sensor (SHT31 probe, 868MHz / 915MHz).
* **Host Platform**: Physical Host Machine with Virtualization enabled (Intel VT-x / AMD-V), minimum 8GB RAM, 100GB Disk.
* **RF Security Test Bench (Optional)**: A band-appropriate SDR receiver, antenna or conducted RF path, storage for IQ captures, and a dedicated Linux analysis environment. Add an approved TX-capable SDR or regional LoRa transceiver only for authorized, isolated tests; see [07: RF and Protocol Testing Setup Guide](./07-lorawan-rf-and-protocol-testing-setup-guide.md).
* **Incoming RAK/WisBlock Commissioning Path**: Raspberry Pi 4, RAK5146 SPI concentrator for AS923/900-928MHz, RAK5146 WisLink Pi HAT, 900-930MHz LoRa antenna, active GPS antenna, two u.FL/IPEX-to-SMA-family pigtails, 5V/3A USB-C supply, high-endurance microSD, Ethernet, RAK4631, RAK19007 or RAK19001, one compatible sensor, and a matching node antenna; see [09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md).

### 2. Software Requirements
* **Hypervisor**: Oracle VM VirtualBox v7.0+ or VMware Workstation / Pro.
* **Operating System**: Ubuntu Server 22.04 LTS or 24.04 LTS (x86_64).
* **Runtime**: Docker Engine v24.0+ & Docker Compose v2.20+.
* **LoRaWAN Server**: ChirpStack Network Server v4.x.

### 3. Network Ports & Protocols

| Service | Protocol | Port | Source | Destination | Purpose |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Semtech UDP Forwarder** | UDP | `1700` | Gateway | Gateway Bridge | Forwarding raw LoRa RF frames |
| **ChirpStack Web UI & API** | TCP | `8080` | Web Browser / Client | ChirpStack Server | Web dashboard and REST/gRPC API |
| **Mosquitto MQTT Broker** | TCP | `1883` | Gateway Bridge / Apps | Mosquitto Broker | Internal publish/subscribe bus |
| **PostgreSQL Database** | TCP | `5432` | ChirpStack Server | PostgreSQL | Persistent data storage |
| **Redis Cache** | TCP | `6379` | ChirpStack Server | Redis | State caching and deduplication |
| **OpenSSH Server** | TCP | `22` | Host / Admin CLI | Ubuntu VM | Remote Linux administration |

### 4. Essential Operational Field Gotchas & Best Practices

* ⚡ **Gateway Post-Boot Packet Forwarder Fix**: If the gateway reboots and remains **Offline** in ChirpStack, log into the Milesight Gateway Web UI (`http://192.168.23.150`), navigate to **Packet Forwarder -> Multi-Destination**, and click **Save & Apply** to re-bind the UDP 1700 forwarder session.
* ⚠️ **Class A Downlink & OTAA Queue Flushing Gotcha**: The Dragino LSN50v2-S31 is a Class A device. Queued downlink commands (e.g. `0100003C` on FPort 2 for 1-minute uplink interval) are held by ChirpStack until the sensor's **next natural uplink**. **DO NOT press the physical RESET button on the sensor after queuing** — pressing reset forces an OTAA `JoinRequest`, which flushes (drops) all pending queued downlinks!
* 📋 **Dragino LSN50v2-S31 Downlink Command Reference**:
  * **Set Uplink Interval (TDC)**: FPort `2`, Hex `0100003C` (60s / 1 min), `0100001E` (30s), `01000258` (10 min), `01000E10` (1 hour).
  * **Software System Reboot**: FPort `2`, Hex `04FF`.
  * **Factory Reset (FDR)**: FPort `2`, Hex `04FE`.
  * **Query Status/Firmware**: FPort `2`, Hex `2601` (replies on FPort 5).

---

## ⚡ Quick-Start Command Cheat Sheet

```bash
# 1. Check IP address assigned to Bridged Adapter
hostname -I

# 2. Verify UDP 1700 status on host/VM
sudo netstat -nulp | grep 1700

# 3. Clone ChirpStack Docker repository
git clone https://github.com/chirpstack/chirpstack-docker.git
cd chirpstack-docker

# 4. Start ChirpStack microservices stack
sudo docker compose up -d

# 5. Monitor real-time logs across all containers
sudo docker compose logs -f

# 6. Subscribe to raw MQTT LoRaWAN frames
sudo apt install -y mosquitto-clients
mosquitto_sub -h localhost -p 1883 -v -t "eu868/#"

# 7. One-Command Netplan Mode Switchers (DHCP vs Static IP)
set-dhcp.sh    # Switch to DHCP (for NAT / Home Internet access)
set-static.sh  # Switch to Static IP (for Milesight Gateway AP connection)
```

---
*Maintained under project `lorawan-setup` for enterprise Smart Agriculture & IoT deployments.*
