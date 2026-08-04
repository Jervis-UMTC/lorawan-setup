# Smart Agriculture Technology Documentation Library

Welcome to the **Smart Agriculture IoT & LoRaWAN Technical Documentation Library**. This folder contains 8 dedicated, in-depth technical handbooks—one for each core technology powering our end-to-end Smart Agriculture infrastructure.

---

## 📚 Handbook Catalog & Master Index

Each document below is a self-contained, educational handbook providing theoretical foundations, physical layer specs, protocol architectures, configuration code snippets, real-world farm deployment strategies, and troubleshooting guides.

| Volume | Handbook File | Core Technology | Primary Focus Area |
| :---: | :--- | :--- | :--- |
| **01** | **[01-lorawan-protocol-handbook.md](./01-lorawan-protocol-handbook.md)** | **LoRaWAN & LoRa Physical Layer** | Sub-GHz RF physics, Chirp Spread Spectrum (CSS) modulation, Spreading Factors (SF7–SF12), Adaptive Data Rate (ADR), OTAA/ABP security, regional frequency channels, and canopy penetration dynamics. |
| **02** | **[02-chirpstack-v4-handbook.md](./02-chirpstack-v4-handbook.md)** | **ChirpStack v4 Network Server** | Open-source LoRaWAN server architecture, Gateway Bridge (Semtech UDP → MQTT conversion), Core Network Server, Redis caching, gRPC/REST APIs, device profiles, JavaScript codecs, and webhooks. |
| **03** | **[03-raspberry-pi-gateway-handbook.md](./03-raspberry-pi-gateway-handbook.md)** | **Raspberry Pi 4 & RAK5146 Gateway** | Single-board computer edge configuration, RAK5146 SPI LoRaWAN Concentrator card (Semtech SX1302/SX1303), outdoor antenna RF engineering, Semtech UDP packet forwarder, and offline Access Point (AP) mode. |
| **04** | **[04-postgresql-timescaledb-handbook.md](./04-postgresql-timescaledb-handbook.md)** | **PostgreSQL & TimescaleDB** | Relational & time-series database design, `event_up` telemetry schemas, JSONB payload extraction functions, B-tree/GIN indexing, time-series aggregations, and data retention policies. |
| **05** | **[05-grafana-dashboards-handbook.md](./05-grafana-dashboards-handbook.md)** | **Grafana Scoreboards & Analytics** | Real-time visual analytics, PostgreSQL data source binding, time-series graphs, threshold gauges, disease risk heatmaps, alerting rules, and executive farm dashboard UX design. |
| **06** | **[06-node-red-automation-handbook.md](./06-node-red-automation-handbook.md)** | **Node-RED Rule Engine** | Flow-based visual programming, MQTT subscription pipelines, sub-second threshold event evaluation, automated SMS alert dispatching, and physical solenoid irrigation valve actuation. |
| **07** | **[07-rakwireless-npk-sensing-handbook.md](./07-rakwireless-npk-sensing-handbook.md)** | **RAKwireless & RS485 Soil NPK** | RAKwireless WisBlock modular ecosystem (RAK4631 Nordic MCU + RAK19007 baseboard), RS485 Modbus RTU protocol, Soil NPK sensor chemistry (Nitrogen N, Phosphorus P, Potassium K), and precision fertilization ROI. |
| **08** | **[08-hyperledger-fabric-blockchain-handbook.md](./08-hyperledger-fabric-blockchain-handbook.md)** | **Hyperledger Fabric Blockchain** | Enterprise permissioned blockchain architecture, channel configuration, chaincode (smart contracts), tamper-proof telemetry logging, and organic certification supply chain transparency. |
| **09** | **[09-gr-lora-sdr-rf-phy-handbook.md](./09-gr-lora-sdr-rf-phy-handbook.md)** | **gr-lora-sdr GNU Radio Module** | Optional Software Defined Radio (SDR) LoRa PHY implementation (requires external SDR hardware) for low-level IQ sample capture, de-chirping/FFT, and parameter sweeps. |
| **10** | **[10-wireshark-lorawan-security-handbook.md](./10-wireshark-lorawan-security-handbook.md)** | **Wireshark & Protocol Analysis** | Primary standalone security analysis engine. Deep-packet inspection, native LoRaWAN dissectors, Semtech UDP 1700 captures, display filters, cryptographic key decryption (`NwkSKey`/`AppSKey`), replay audits, and TShark CLI automation. |
| **Ref** | **[Field Troubleshooting Catalog](../troubleshooting/README.md)** | **Field Remediation** | 8 modular field troubleshooting manuals covering signal collisions, FCnt drops, MIC mismatches, Class B/C downlink latency, offline AP backhaul, canopy attenuation, battery drain, and regional frequency mismatches. |

---

## 🏗️ System Architecture & Data Flow Overview

```text
+-----------------------------------------------------------------------------------+
|                           1. FIELD LAYER (SENSORS & NODES)                        |
|   • RAKwireless WisBlock (RAK4631 Nordic MCU + Solar Charging)                    |
|   • RAKwireless Industrial RS485 Soil NPK Sensor (Nitrogen, Phosphorus, Potassium)|
|   • Microclimate Canopy Sensors (Temp, Relative Humidity, Soil Moisture, EC)      |
+-----------------------------------------------------------------------------------+
                                         |
                                         | LoRa Sub-GHz Radio (868 MHz / 915 MHz / AU915)
                                         v
+-----------------------------------------------------------------------------------+
|                        2. EDGE GATEWAY LAYER (BASE STATION)                       |
|   • Raspberry Pi 4 Base Station (Quad-core ARM, 4GB RAM)                          |
|   • RAK5146 SPI LoRaWAN Concentrator Card (Semtech SX1302/SX1303, Outdoor Fiber Antenna)
|   • Semtech UDP Packet Forwarder (Port 1700)                                      |
|   • Offline Wi-Fi AP Mode Broadcast (Field Tablet Diagnostics)                    |
+-----------------------------------------------------------------------------------+
                                         |
                                         | Semtech UDP Packets (UDP 1700)
                                         v
+-----------------------------------------------------------------------------------+
|                    3. NETWORK SERVER & BROKER LAYER (UBUNTU VM)                   |
|   • ChirpStack Gateway Bridge (UDP 1700 -> MQTT Topic Converter)                  |
|   • Mosquitto MQTT Message Broker (Port 1883)                                     |
|   • ChirpStack v4 Core Server (Deduplication, Frame Counter, OTAA Activation)     |
|   • JavaScript Payload Decoders (Raw Bytes -> Structured JSON Telemetry)          |
|   • Redis 7 (Session Cache) & PostgreSQL 14 (Metadata & State)                   |
+-----------------------------------------------------------------------------------+
                                         |
                       +-----------------+-----------------+
                       |                                   |
                       v                                   v
+------------------------------------+   +------------------------------------+
| 4. DATABASE & VISUALIZATION LAYER  |   |   5. AUTOMATION & ACTUATION LAYER  |
| • PostgreSQL / TimescaleDB         |   | • Node-RED Flow Engine             |
|   (JSONB Event Persistence)        |   |   (Sub-second Rule Monitoring)     |
| • Grafana Dashboards               |   | • Solenoid Valve Relays            |
|   (Gauges, Trends, Disease Risk)   |   |   (Automated Irrigation Trigger)   |
| • Hyperledger Fabric Ledger        |   | • SMS / Twilio / Email Alerts      |
|   (Immutable Organic Traceability) |   |   (24/7 Digital Farm Watchman)     |
+------------------------------------+   +------------------------------------+
```

---

## 💡 How to Use These Handbooks

1. **For System Engineers & Hardware Builders**: Start with **Volume 01 (LoRaWAN)**, **Volume 03 (Raspberry Pi Gateway)**, and **Volume 07 (RAKwireless & NPK)**.
2. **For Software Developers & System Integrators**: Focus on **Volume 02 (ChirpStack v4)**, **Volume 04 (PostgreSQL)**, and **Volume 06 (Node-RED)**.
3. **For Agronomists, Analysts & Auditors**: Deep dive into **Volume 05 (Grafana Analytics)** and **Volume 08 (Hyperledger Fabric)**.

---
*Maintained under project `lorawan-setup/technology-docs` for enterprise Smart Agriculture IoT deployments.*
