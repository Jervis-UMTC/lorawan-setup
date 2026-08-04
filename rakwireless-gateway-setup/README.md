# RAKwireless LoRaWAN Gateway Setup & Operations Master Guide

Welcome to the comprehensive, foolproof master setup and operational handbook for **RAKwireless LoRaWAN Gateways**, fully integrated with the enterprise smart agriculture system masterplan ([hardware-checklist.pdf](../hardware-checklist.pdf)).

---

## 1. Enterprise System Masterplan Architecture

The system operates on a two-tier private LoRaWAN architecture for agricultural and industrial telemetry:

1. **The Gateway Infrastructure ("The Base Station Tower")**: A central base station powered by a **Raspberry Pi 4 Model B** equipped with a **RAK5146 SPI Concentrator Card (Semtech SX1303)** and **WisLink Pi HAT**. It listens simultaneously on 8 radio channels to capture long-range wireless telemetry from field sensors across a 5–15 km line-of-sight radius and forwards encrypted data to the network server.
2. **The WisBlock Field Sensor Nodes ("The Field Workers")**: Weatherproof, solar-powered multi-sensor field stations deployed directly in crop fields, orchards, and greenhouses to collect real-time soil, microclimate, solar UV, rain, and SDI-12 data.

```text
===================================================================================================
                  COMPLETE TWO-TIER PRIVATE LORAWAN SYSTEM ARCHITECTURE
===================================================================================================

[FIELD SENSOR LEVEL]
 +----------------------+  +----------------------+  +---------------------+  +--------------------+
 | WisBlock Node #1     |  | WisBlock Node #2     |  | WisBlock Node #3    |  | WisBlock Node #N   |
 | (Soil & Microclimate)|  | (Rain & UV Index)    |  | (Weather Station)   |  | (Modbus / SDI-12)  |
 +----------+-----------+  +----------+-----------+  +----------+----------+  +---------+----------+
            |                         |                         |                     |
            +-------------------------+-------------------------+---------------------+
                                      |
                                      | LoRaWAN Radio Signals (AS923 / 900–928 MHz)
                                      | Range: Up to 5–15 km Line-of-Sight
                                      v
[GATEWAY / INFRASTRUCTURE LEVEL - RASPBERRY PI 4 HOST]
 +------------------------------------------------------------------------------------------------+
 | Outdoor High-Gain Fiberglass Antenna (900–930 MHz) + Active GPS Antenna                        |
 +-----------------------------------------------+------------------------------------------------+
                                                 | 2x u.FL to SMA Female Pigtails
                                                 v
 +------------------------------------------------------------------------------------------------+
 | RAK5146 LoRaWAN Concentrator Card (Semtech SX1303 ASIC, SPI Version, 900-928 MHz)             |
 +-----------------------------------------------+------------------------------------------------+
                                                 | mini-PCIe Socket
                                                 v
 +------------------------------------------------------------------------------------------------+
 | RAKwireless WisLink Pi HAT Adapter Board                                                       |
 +-----------------------------------------------+------------------------------------------------+
                                                 | 40-Pin GPIO Header
                                                 v
 +------------------------------------------------------------------------------------------------+
 | Raspberry Pi 4 Model B Single-Board Computer (Gateway Brain)                                   |
 | Powered by Official 5V / 3A USB-C Power Supply                                                |
 +-----------------------------------------------+------------------------------------------------+
                                                 |
                                                 | Ethernet / IP Backhaul (Cat5e / Cat6 Cable)
                                                 v
[APPLICATION & SERVER LEVEL - STANDALONE ALL-IN-ONE OR REMOTE]
 +------------------------------------------------------------------------------------------------+
 | Private ChirpStack v4 Network Server Stack (Dockerized on Pi 4 or Remote Cloud Server)         |
 | - Gateway Bridge (Semtech UDP 1700 or Basic Station LNS wss://)                                |
 | - Network Server & Payload Decoders                                                           |
 | - Visualization Dashboard (PostgreSQL, Grafana, Node-RED Automated Irrigation Rules)          |
 +------------------------------------------------------------------------------------------------+
```

---

## 2. Hardware Specification & Ordering Verification Matrix

This matrix provides the exact hardware breakdown verified from `hardware-checklist.pdf`:

| Hardware Category | Specified Hardware Component | Technical Specifications & Role | Crucial Purchasing & Technical Notes |
| :--- | :--- | :--- | :--- |
| **Gateway SBC** | **Raspberry Pi 4 Model B** | Main host computer (2GB, 4GB, or 8GB RAM). Runs packet forwarder & network routing. | **MUST BE 5V/3A**: Requires official 5.1V/3.0A USB-C power supply to avoid power drops during radio spikes. |
| **LoRa Concentrator** | **RAK5146 Concentrator Module** | High-performance mPCIe card (Semtech SX1303 ASIC). Receives 8 channels simultaneously. | **MUST BE SPI & 900–928 MHz (AS923/US915)**. Do *not* buy 868 MHz or USB variants. |
| **Interface Board** | **WisLink Pi HAT** | Physical bridge connecting RAK5146 mPCIe card to Raspberry Pi 4 GPIO pins. | Includes slot for mPCIe card and hardware brass standoff mounting points. |
| **Outdoor Antenna** | **Sub-GHz Outdoor Antenna** | Fiberglass omnidirectional antenna (900–930 MHz tuned). | **CRITICAL**: NEVER power on the Pi without antenna connected; radio chip will burn out. |
| **GPS Antenna** | **Active GPS Antenna** | GPS positioning antenna (u.FL/SMA connection). | Plugs into GPS port on RAK5146 concentrator card for microsecond time sync. |
| **RF Cabling** | **2x RF Pigtail Cables** | u.FL / IPEX to SMA Female pigtail jumpers. | 1x for LoRa antenna, 1x for GPS antenna. |
| **Gateway Power** | **Official Pi Power Supply** | 5V / 3A USB-C Power Adapter. | Generic phone chargers cause system crashes during packet transmission. |
| **Storage** | **MicroSD Card & Reader** | 32GB or 64GB Class 10 / High Endurance MicroSD card. | High-endurance cards prevent data corruption from continuous log writing. |
| **Backhaul Cable** | **Ethernet Cable** | Cat5e or Cat6 heavy-duty patch cable. | Connects gateway to local router / internet backhaul. |
| **Enclosure** | **Mounting Hardware & Box** | Brass standoffs, M2.5 & M2 screws, IP67 waterproof outdoor box. | Structurally locks components together and seals hardware against weather. |
| **Node Core** | **RAK4631 WisBlock Core** | Nordic nRF52840 MCU + Semtech SX1262 LoRa transceiver. | Executes sensor code, encrypts data, broadcasts over LoRaWAN (AS923). |
| **Node Base** | **RAK19007 / RAK19001 Base** | Standard (4 sensor slots) or Expanded (6 sensor slots) baseboard. | Serves as foundation for field nodes; integrated solar panel & Li-Ion charger. |
| **Node Cellular** | **Select "None"** | Avoid ordering RAK5860/RAK13101 cellular modules. | Gateway handles backhaul; saves ~$54/kit over cellular and avoids SIM fees. |

---

## 3. Directory Navigation Map

```text
rakwireless-gateway-setup/
├── README.md                                   # Master Index & Verified System Architecture (This File)
├── 01-hardware-architecture-and-assembly.md    # Raspberry Pi 4 + RAK5146 Physical Assembly, Pinouts & Power
├── 02-wisgate-os-configuration-guide.md       # Commercial WisGate OS 1/2 & Raspberry Pi 4 OS Administration
├── 03-raspberry-pi-concentrator-setup.md       # Raspberry Pi 4 Model B + RAK5146 Driver & Kernel Setup
├── 04-packet-forwarders-and-protocols.md       # Semtech UDP, Basic Station (LNS/CUPS) & Concentratord
├── 05-network-server-integration.md            # Standalone Local ChirpStack v4 (on Pi 4), Remote & TTN Setup
├── 06-rf-planning-antennas-and-site-survey.md # Link Budget, Antenna Gain, VSWR, Cables & Fresnel Clearance
├── 07-security-hardening-and-vpn.md            # Default Credential Removal, Firewall, WireGuard VPN & mTLS
├── 08-troubleshooting-and-diagnostics.md       # Exhaustive Diagnostic Flowchart, Log Analysis & SSH Fixes
├── templates-and-configs/                      # Production-Grade Configuration Templates
│   ├── global_conf.as923.json                  # Semtech UDP Forwarder JSON (AS923-1)
│   ├── global_conf.us915.json                  # Semtech UDP Forwarder JSON (US915 Sub-band 2)
│   ├── global_conf.eu868.json                  # Semtech UDP Forwarder JSON (EU868)
│   ├── station.conf                            # Semtech Basic Station LNS/CUPS Configuration
│   ├── chirpstack-gateway-bridge.toml          # Gateway-side ChirpStack Bridge TOML Configuration
│   └── rak-gateway.service                     # Systemd Unit File for Automatic Daemon Management
└── scripts/
    └── install-rak-gateway.sh                  # Foolproof 1-Click Automated Installer for Raspberry Pi 4
```

---

## 4. Non-Negotiable Procurement & Deployment Red-Flags

1. **Frequency Matching**: Ensure all LoRa radios (RAK5146 concentrator and RAK4631 core modules) are ordered for **900–928 MHz / AS923**. European frequencies (868 MHz) will not communicate and violate spectrum regulations.
2. **Cellular Variant on Field Kit**: When ordering the WisBlock Agriculture Kit, select **"None"** under cellular modules. Since the gateway handles internet backhaul, adding cellular modules adds unnecessary cost and power consumption.
3. **Gateway Host Interface**: Ensure the RAK5146 card is the **SPI version** to match the WisLink Pi HAT GPIO configuration.
4. **Antenna Termination Mandate**: **NEVER** apply USB-C power to the Raspberry Pi 4 before both the LoRa antenna and active GPS antenna are threaded onto the SMA bulkheads.
