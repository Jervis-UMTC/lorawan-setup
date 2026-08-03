# Enterprise LoRaWAN Infrastructure Deployment & Operations Manual
### Complete Technical Guide: ChirpStack v4, Milesight Gateways, and Dragino LSN50v2 Sensors

---

## 📌 Executive Summary & Master Architecture

This document serves as an exhaustive, production-grade technical manual for deploying, configuring, operating, and troubleshooting an enterprise-grade **LoRaWAN (Long Range Wide Area Network)** environment. 

The architecture is built upon the **ChirpStack v4** open-source network server stack running in containerized microservices on an **Ubuntu Server Virtual Machine**, interfaced with an industrial **Milesight LoRaWAN Gateway** via the **Semtech UDP Packet Forwarder Protocol**, and servicing **Dragino LSN50v2-S31** environmental telemetry end-nodes utilizing **Over-The-Air Activation (OTAA)**.

```text
+-----------------------------------------------------------------------------------+
|               1. Physical & RF Layer (Dragino LSN50v2-S31 End-Nodes)             |
|  • DevEUI: A84041380189B98F | Class A | OTAA Key Authentication               |
+-----------------------------------------------------------------------------------+
                                         |
                                         | LoRa Chirp Spread Spectrum (CSS) RF
                                         v
+-----------------------------------------------------------------------------------+
|                    2. Edge & Gateway Layer (Milesight Gateway)                    |
|  • Static IP: 192.168.23.150 | Bridged Network Adapter                            |
|  • Semtech UDP Packet Forwarder (Target: Port 1700)                               |
+-----------------------------------------------------------------------------------+
                                         |
                                         | Semtech UDP Packets (UDP Port 1700)
                                         v
+-----------------------------------------------------------------------------------+
|       3. ChirpStack Network Server Stack (Ubuntu VM: 192.168.1.137)               |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  | ChirpStack Gateway Bridge (UDP 1700 Listener -> MQTT Protobuf Converter)   |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v Publish Uplink (MQTT)                   |
|  +-----------------------------------------------------------------------------+  |
|  | Mosquitto MQTT Broker (TCP Port 1883 Topic Manager)                         |  |
|  +-----------------------------------------------------------------------------+  |
|                                         |                                         |
|                                         v Deliver Uplink                          |
|  +-----------------------------------------------------------------------------+  |
|  | ChirpStack v4 Core Server (Network + Application Server + Web UI: 8080)     |  |
|  +-----------------------------------------------------------------------------+  |
|                         |                               |                         |
|                         v                               v                         |
|  +------------------------------+             +--------------------------------+  |
|  | PostgreSQL 14 Database       |             | Redis 7 Cache Engine           |  |
|  | (State, Keys & Metadata)     |             | (Session State & Frame Counters)|  |
|  +------------------------------+             +--------------------------------+  |
+-----------------------------------------------------------------------------------+
                                         |
                                         | HTTP Dashboard / Webhooks / MQTT
                                         v
+-----------------------------------------------------------------------------------+
|                 4. Application & Integration Layer                                |
|  • ChirpStack Web Dashboard (http://192.168.1.137:8080)                          |
|  • JavaScript Payload Decoder (Translates Hex Bytes -> JSON Telemetry)            |
|  • External Integrations (HTTP Webhooks, InfluxDB, Grafana)                       |
+-----------------------------------------------------------------------------------+
```

---

## 📖 Table of Contents

1. [Deep-Dive Technical Fundamentals](#1-deep-dive-technical-fundamentals)
2. [Phase I: Hypervisor Setup & Ubuntu Server Provisioning](#2-phase-i-hypervisor-setup--ubuntu-server-provisioning)
3. [Phase II: Network Topology & Gateway Bridging Configuration](#3-phase-ii-network-topology--gateway-bridging-configuration)
4. [Phase III: Milesight Gateway Packet Forwarder Setup](#4-phase-iii-milesight-gateway-packet-forwarder-setup)
5. [Phase IV: ChirpStack Docker Infrastructure Deployment](#5-phase-iv-chirpstack-docker-infrastructure-deployment)
6. [Phase V: ChirpStack Web UI Administration & Multi-Tenant Setup](#6-phase-v-chirpstack-web-ui-administration--multi-tenant-setup)
7. [Phase VI: Device Profile & Regional Parameter Engineering](#7-phase-vi-device-profile--regional-parameter-engineering)
8. [Phase VII: End-Node Onboarding & OTAA Key Security](#8-phase-vii-end-node-onboarding--otaa-key-security)
9. [Phase VIII: Payload Codec Architecture & JavaScript Parsers](#9-phase-viii-payload-codec-architecture--javascript-parsers)
10. [Phase IX: Packet Verification, Frame Tracing & Diagnostics](#10-phase-ix-packet-verification-frame-tracing--diagnostics)
11. [Phase X: Production Troubleshooting & Runbook](#11-phase-x-production-troubleshooting--runbook)

---

## 1. Deep-Dive Technical Fundamentals

### 1.1 LoRa vs. LoRaWAN Protocol Breakdown
* **LoRa (Physical Layer)**: A proprietary Chirp Spread Spectrum (CSS) radio modulation technique developed by Semtech. It operates in unlicensed Sub-GHz ISM bands (868 MHz in Europe, 915 MHz in the Americas, 923 MHz in Asia). It provides high link budget and resistance to interference at the cost of low data throughput (250 bps to 5.5 kbps).
* **LoRaWAN (MAC Layer)**: An open media access control protocol maintained by the LoRa Alliance. It defines channel access rules, device classes, frame formats, encryption standards (AES-128), and network architecture.

```text
+-------------------------------------------------------------------+
|                     Application Layer (JSON)                      |
+-------------------------------------------------------------------+
|               LoRaWAN MAC Layer (Class A, B, C)                   |
|        Security: NwkSKey (MIC Auth) & AppSKey (Payload Enc)       |
+-------------------------------------------------------------------+
|           LoRa Modulation Layer (CSS Sub-GHz ISM Band)            |
+-------------------------------------------------------------------+
|           Physical Hardware (Transceivers SX1276/SX1302)          |
+-------------------------------------------------------------------+
```

### 1.2 LoRaWAN Device Classes

| Device Class | Downlink Latency | Power Consumption | Typical Use Case |
| :--- | :--- | :--- | :--- |
| **Class A (All Devices)** | High (Downlink only following an Uplink RX1/RX2 window) | **Extremely Low** (Years on battery) | Battery-powered sensors (e.g. Dragino LSN50v2) |
| **Class B (Beacon)** | Medium (Scheduled periodic receive windows synchronized by Gateway Beacons) | **Low** | Battery-powered actuators, smart meters |
| **Class C (Continuous)** | **Zero** (Receiver remains active constantly except during transmission) | **High** (Requires mains power) | Mains-powered streetlights, immediate relays |

### 1.3 Semtech UDP Packet Forwarder Protocol
The gateway converts analog LoRa RF chirps into `PUSH_DATA` UDP datagrams containing JSON payloads defined by the Semtech protocol standard.

#### Packet Forwarder Frame Structure:
* **Protocol Version** (1 byte): `0x02`
* **Random Token** (2 bytes): Identifies matching `PUSH_ACK` responses.
* **Identifier** (1 byte): `0x00` (`PUSH_DATA`), `0x01` (`PUSH_ACK`), `0x02` (`PULL_DATA`), `0x03` (`PULL_RESP`), `0x04` (`PULL_ACK`).
* **Gateway EUI** (8 bytes): Unique MAC-derived identifier.
* **JSON Payload**: Contains RF metadata (`stat`, `rxpk`, `txpk`).

---

## 2. Phase I: Hypervisor Setup & Ubuntu Server Provisioning

### 2.1 VirtualBox Hardware Configuration
Launch Oracle VM VirtualBox and click **New**. Enter the parameters below:

```text
+-------------------------------------------------------------------+
|                     Virtual Machine Specification                 |
+-------------------------------------------------------------------+
| Name                : lorawan                                     |
| OS Type             : Linux / Ubuntu (64-bit)                     |
| Base Memory (RAM)   : 4096 MB (Recommended: 4096 - 8192 MB)       |
| Processors (vCPUs)  : 2 Cores (Recommended: 2 - 4 Cores)           |
| Execution Cap       : 100%                                        |
| Disk Type           : VDI (VirtualBox Disk Image)                 |
| Storage Allocation  : Dynamically Allocated                       |
| Hard Disk Capacity  : 50.00 GB                                    |
| Graphics Controller : VMSVGA (32 MB Video Memory)                 |
+-------------------------------------------------------------------+
```

> ⚠️ **CRITICAL**: Ensure **Unattended Install** is **unchecked**. Unattended installation bypasses manual network and user profile setup, which causes SSH server setup failures.

### 2.2 Ubuntu Server Operating System Installation Steps
1. Boot the `lorawan` VM from the downloaded Ubuntu Server ISO image.
2. Select **Try or Install Ubuntu Server**.
3. Choose Language: `English` -> Keyboard Layout: `English (US)`.
4. Choose Installation Type: `Ubuntu Server` (Standard minimal server footprint).
5. Network Connections: Leave DHCP active (we will configure Bridging in VirtualBox later).
6. Configure Storage: Select `Use an entire disk` (Ensure `Set up this disk as an LVM group` is selected).
7. Profile Configuration:
   * **Your name**: `batman`
   * **Your server's name**: `lorawan`
   * **Pick a username**: `batman`
   * **Choose a password**: `batman123!@#`
   * **Confirm your password**: `batman123!@#`
8. OpenSSH Setup: Check `[X] Install OpenSSH server` (Do not import SSH identity keys).
9. Featured Server Snaps: Do NOT select any pre-configured snaps (Docker will be installed manually via official Docker repositories).
10. Wait for installation to complete, select **Reboot Now**, and unmount the virtual ISO drive.

---

## 3. Phase II: Network Topology & Gateway Bridging Configuration

### 3.1 Network Adapter Modes Comparison

```text
NAT Mode (Default - Isolated):
+--------------------+            +------------------+
| Ubuntu VM          |---(Out)--->| Host Machine     |
| (IP: 10.0.2.15)    |<--(NO)-----| (Local Subnet)   |
+--------------------+            +------------------+
         ^                                 ^
         |                                 |
         +-------(NO Incoming Port 1700)---+---- Milesight Gateway

Bridged Mode (Required for LoRaWAN):
+--------------------+            +--------------------+            +-------------------+
| Ubuntu VM          |<---------->| Local Router /     |<---------->| Milesight Gateway |
| (IP: 192.168.1.137)|  Bridged   | Network Switch     |   Network  | (IP: 192.168.1.X) |
+--------------------+  Subnet    +--------------------+   Traffic  +-------------------+
                                           ^
                                           |
                                     Host Machine
```

### 3.2 Setting Up Bridged Adapter in VirtualBox
1. Shut down or suspend the `lorawan` VM.
2. Select the VM in VirtualBox Manager and click **Settings (Ctrl+S)**.
3. Select **Network** tab -> **Adapter 1**.
4. Change **Attached to**: `Bridged Adapter`.
5. Under **Name**, select your physical active network card (e.g., `Intel(R) Wi-Fi 6 AX201` or `Realtek PCIe GbE Family Controller`).
6. Expand **Advanced** -> Change **Promiscuous Mode**: `Allow All`.
7. Ensure **Cable Connected** is checked.
8. Click **OK** and boot the VM.

### 3.3 Verifying Server Network State
Log into the VM shell and inspect IP assignment using either of the following commands:

```bash
# Method 1: Print internal and bridged IP addresses (Capital 'I')
hostname -I

# Method 2: Detailed network interface listing
ip a
```
* **Output Example (`hostname -I`)**:
  ```text
  192.168.1.137 172.17.0.1 172.18.0.1
  ```
* **Note**: 
  * `192.168.1.137` is your physical network bridged IP address assigned by your local router/DHCP.
  * `172.17.0.1` and `172.18.0.1` are internal Docker bridge subnets.
### 3.4 Configuring Permanent Static IP & Default Gateway via Netplan

To ensure your server retains a fixed IP address and default gateway route across reboots:

#### 1. Disable Cloud-Init Network Auto-Generation
Prevent Ubuntu's cloud-init from overwriting custom network files upon reboot:
```bash
sudo nano /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
```
Insert line:
```yaml
network: {config: disabled}
```

#### 2. Configure Netplan Static IP (`192.168.1.137` or `192.168.23.137`)
Open `/etc/netplan/01-netcfg.yaml`:
```bash
sudo nano /etc/netplan/01-netcfg.yaml
```
Write configuration:
```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    enp0s3:
      dhcp4: no
      dhcp6: no
      addresses:
        - 192.168.1.137/24
      routes:
        - to: default
          via: 192.168.1.1
      nameservers:
        addresses:
          - 1.1.1.1
          - 8.8.8.8
```

#### 3. Test & Apply Configuration Permanently
```bash
sudo chmod 600 /etc/netplan/*.yaml
sudo netplan try
sudo netplan apply
```

---

### 3.5 One-Command Netplan Mode Switcher Automation (`set-dhcp.sh` & `set-static.sh`)

To conveniently toggle between **DHCP (for NAT / Home Internet Access)** and **Static IP (for Gateway Connection)** with a single command:

1. **Create DHCP File** (`/etc/netplan/01-dhcp.yaml`):
   ```yaml
   network:
     version: 2
     renderer: networkd
     ethernets:
       enp0s3:
         dhcp4: true
   ```
2. **Create Static File** (`/etc/netplan/02-static.yaml.bak`):
   ```yaml
   network:
     version: 2
     renderer: networkd
     ethernets:
       enp0s3:
         dhcp4: no
         addresses:
           - 192.168.23.137/24
         routes:
           - to: default
             via: 192.168.23.150
   ```
3. **Create Executable Switcher Scripts**:
   * **`set-dhcp.sh`**:
     ```bash
     #!/bin/bash
     sudo mv /etc/netplan/02-static.yaml /etc/netplan/02-static.yaml.bak 2>/dev/null
     sudo mv /etc/netplan/01-dhcp.yaml.bak /etc/netplan/01-dhcp.yaml 2>/dev/null
     sudo netplan apply
     echo "Switched to DHCP Mode:" && hostname -I
     ```
   * **`set-static.sh`**:
     ```bash
     #!/bin/bash
     sudo mv /etc/netplan/01-dhcp.yaml /etc/netplan/01-dhcp.yaml.bak 2>/dev/null
     sudo mv /etc/netplan/02-static.yaml.bak /etc/netplan/02-static.yaml 2>/dev/null
     sudo netplan apply
     echo "Switched to Static IP Mode:" && hostname -I
     ```
   * **Make Executable**:
     ```bash
     sudo chmod +x /usr/local/bin/set-dhcp.sh /usr/local/bin/set-static.sh
     ```

Execute `set-dhcp.sh` when using NAT/Internet and `set-static.sh` when connecting to the Gateway.

---

## 4. Phase III: Milesight Gateway Packet Forwarder Setup

### 4.1 Connecting to Gateway Management Web Interface
1. Power ON your Milesight LoRaWAN Gateway (UG65 / UG67).
2. Connect your host machine's Wi-Fi adapter to the gateway's broadcasted Wi-Fi Access Point (SSID: `Gateway_F94C0B` or similar).
3. Open a browser and navigate to the default Web Interface address:
   ```http
   http://192.168.23.150
   ```
4. Authenticate using default administrator credentials:
   * **Username**: `admin`
   * **Password**: `password`
   * *(Change the default password upon initial login if prompted).*

### 4.2 Gateway Multi-Destination Semtech UDP Configuration
1. In the Milesight navigation sidebar, navigate to **Packet Forwarder -> Multi-Destination**.
2. Locate the **Multi-Destination Table** and click the **+ Add** button.
3. Fill out the forwarder parameters:

```text
+-------------------------------------------------------------------+
|              Milesight Packet Forwarder Parameters                |
+-------------------------------------------------------------------+
| Enable         : [X] Enabled (Checked)                            |
| Type           : Semtech                                          |
| Server Address : 192.168.1.137 (Bridged IP of Ubuntu VM)          |
| Port Up        : 1700 (UDP inbound port on ChirpStack Bridge)     |
| Port Down      : 1700 (UDP outbound port for Downlink / Join)    |
| Description    : Primary ChirpStack v4 Server Connection          |
+-------------------------------------------------------------------+
```

4. Click **Save** and **Apply**.
5. Copy down the **Gateway EUI** displayed on the Status page (e.g., `24E124FFFEO159C3`). You will need this EUI to register the Gateway in ChirpStack.

### 4.3 Gateway Boot-Up & Packet Forwarder Re-Enablement Operational Gotcha
> ⚠️ **IMPORTANT**: Upon booting or power-cycling the Milesight Gateway, it may fail to automatically re-establish the active UDP session with ChirpStack Gateway Bridge, leaving the Gateway status as **Offline** in ChirpStack Web UI.
> 
> **Resolution Procedure**:
> 1. Log into the Milesight Gateway Web Admin UI (`http://192.168.23.150` or `http://192.168.1.150`).
> 2. Navigate to **Packet Forwarder -> Multi-Destination**.
> 3. Click **Save & Apply** (or toggle **Enable** off and on, then click **Save & Apply**).
> 4. The gateway will immediately re-initialize the Semtech UDP packet forwarder socket and resume streaming packets to ChirpStack on UDP Port `1700`, returning the gateway status to **Online**.


---

## 5. Phase IV: ChirpStack Docker Infrastructure Deployment

The deployment utilizes Docker Compose to manage 5 containerized microservices:

```text
+-----------------------------------------------------------------------------------+
|                    Ubuntu Linux Host (Docker Engine Daemon)                       |
|                                                                                   |
|  +-----------------------------------------------------------------------------+  |
|  |                 Docker Compose Stack: chirpstack-docker                     |  |
|  |                                                                             |  |
|  |  +-----------------------------------+     +-----------------------------+  |  |
|  |  | chirpstack-gateway-bridge:4       |<===>| eclipse-mosquitto:2         |  |  |
|  |  | (Listens: UDP 1700)               | MQTT| (Message Bus: TCP 1883)     |  |  |
|  |  +-----------------------------------+     +-----------------------------+  |  |
|  |                                                         ^                   |  |
|  |                                                         | MQTT              |  |
|  |  +-----------------------------------+                  v                   |  |
|  |  | chirpstack:4 (Core Network Server)|<=================+                   |  |
|  |  | (Web UI Dashboard: TCP 8080)      |                                      |  |
|  |  +-----------------------------------+                                      |  |
|  |             |                   |                                           |  |
|  |             v SQL               v Key-Value Cache                           |  |
|  |  +-----------------------+ +-----------------------+                        |  |
|  |  | postgres:14-alpine    | | redis:7-alpine        |                        |  |
|  |  | (PostgreSQL TCP 5432) | | (Redis Cache TCP 6379) |                        |  |
|  |  +-----------------------+ +-----------------------+                        |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### 5.1 Installing Official Docker Engine & Docker Compose
Log into your Ubuntu VM terminal and run the following setup commands:

```bash
# Step 1: Update system package cache and install prerequisites
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git apt-transport-https ca-certificates software-properties-common gnupg net-tools

# Step 2: Create directory for Docker APT repository keyrings
sudo mkdir -p /etc/apt/keyrings

# Step 3: Download Docker's official GPG signing key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null

# Step 4: Add official Docker repository to APT sources
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Step 5: Install Docker Engine, CLI, Containerd, Buildx, and Compose Plugin
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Step 6: Start and enable Docker service daemon
sudo systemctl start docker
sudo systemctl enable docker

# Step 7: Add current user to docker group to execute commands without sudo
sudo usermod -aG docker $USER
```

### 5.2 Cloning Repository & Validating Configuration
```bash
# Clone official ChirpStack Docker deployment repository
git clone https://github.com/chirpstack/chirpstack-docker.git
cd chirpstack-docker

# Review configuration files
ls -la configuration/
```

### 5.3 Complete Infrastructure docker-compose.yml Reference
Below is the full operational `docker-compose.yml` manifest file used for deployment:

```yaml
version: '3.8'

services:
  chirpstack:
    image: chirpstack/chirpstack:4
    command: -c /etc/chirpstack
    restart: unless-stopped
    volumes:
      - ./config/chirpstack:/etc/chirpstack
      - ./lorawan-devices:/opt/lorawan-devices
    ports:
      - "8080:8080"
    environment:
      - POSTGRESQL_EQUAL_SECRET=chirpstack
      - REDIS_EQUAL_SECRET=chirpstack
    depends_on:
      - postgres
      - redis
      - mosquitto

  chirpstack-gateway-bridge:
    image: chirpstack/chirpstack-gateway-bridge:4
    restart: unless-stopped
    ports:
      - "1700:1700/udp"
    volumes:
      - ./config/chirpstack-gateway-bridge:/etc/chirpstack-gateway-bridge
    environment:
      - INTEGRATION__MQTT__EVENT_TOPIC_TEMPLATE=eu868/gateway/{{ .GatewayID }}/event/{{ .EventType }}
      - INTEGRATION__MQTT__COMMAND_TOPIC_TEMPLATE=eu868/gateway/{{ .GatewayID }}/command/{{ .CommandType }}
    depends_on:
      - mosquitto

  mosquitto:
    image: eclipse-mosquitto:2
    restart: unless-stopped
    ports:
      - "1883:1883"
    volumes:
      - ./config/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf

  postgres:
    image: postgres:14-alpine
    restart: unless-stopped
    volumes:
      - ./configuration/postgresql/initdb:/docker-entrypoint-initdb.d
      - postgresqldata:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=chirpstack
      - POSTGRES_USER=chirpstack
      - POSTGRES_PASSWORD=chirpstack

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redisdata:/data

volumes:
  postgresqldata:
  redisdata:
```

### 5.4 Starting Stack & Verifying Container Health
```bash
# Launch stack in detached background mode
sudo docker compose up -d

# Verify all containers are running cleanly
sudo docker compose ps
```

*Expected Terminal Output*:
```text
NAME                                         IMAGE                               COMMAND                  SERVICE                     STATUS              PORTS
chirpstack-docker-chirpstack-1               chirpstack/chirpstack:4             "/chirpstack -c /etc…"   chirpstack                  running             0.0.0.0:8080->8080/tcp
chirpstack-docker-chirpstack-gateway-bridge  chirpstack-gateway-bridge:4         "/chirpstack-gateway…"   chirpstack-gateway-bridge   running             0.0.0.0:1700->1700/udp
chirpstack-docker-mosquitto-1                eclipse-mosquitto:2                 "/docker-entrypoint.…"   mosquitto                   running             0.0.0.0:1883->1883/tcp
chirpstack-docker-postgres-1                 postgres:14-alpine                  "docker-entrypoint.s…"   postgres                    running             5432/tcp
chirpstack-docker-redis-1                    redis:7-alpine                      "docker-entrypoint.s…"   redis                       running             6379/tcp
```

---

## 6. Phase V: ChirpStack Web UI Administration & Multi-Tenant Setup

### 6.1 Accessing Dashboard
Open your web browser and navigate to:
```http
http://192.168.1.137:8080
```
*(Replace `192.168.1.137` with your VM's bridged IP).*

**Default Credentials**:
* **Username**: `admin`
* **Password**: `admin`

> 🔒 **Security Notice**: Immediately upon first login, navigate to **User -> Change Password** to update the default administrative credentials.

```text
+-------------------------------------------------------------------+
|               ChirpStack v4 Administrative Hierarchy             |
+-------------------------------------------------------------------+
| [Tenant: ChirpStack] (Default Root Organization)                  |
|    |                                                              |
|    +---> [Gateways]                                               |
|    |        +---> Milesight-Gateway (EUI: 24E124FFFEO159C3)       |
|    |                                                              |
|    +---> [Device Profiles]                                        |
|    |        +---> Test (EU868 / MAC 1.0.3 / OTAA)                 |
|    |                                                              |
|    +---> [Applications]                                           |
|             +---> IoT-App                                         |
|                    +---> Devices                                  |
|                             +---> Sensor-03 (DevEUI: A84041...)   |
+-------------------------------------------------------------------+
```

### 6.2 Step-by-Step Gateway Onboarding
1. In the ChirpStack sidebar menu, navigate to **Gateways**.
2. Click **+ Add Gateway**.
3. Fill out the Gateway Metadata form:
   * **Name**: `Milesight-Gateway`
   * **Description**: `Milesight Industrial UG65 LoRaWAN Gateway`
   * **Gateway ID (EUI)**: Enter physical Gateway EUI (e.g. `24E124FFFEO159C3`).
   * **Stats interval (secs)**: `30`
4. Click **Submit**.

### 6.3 Verifying Gateway Online Status
1. Navigate back to **Gateways**.
2. Inspect the **Status** column for `Milesight-Gateway`.
3. If the packet forwarder is working, the status will show **Online** with an active **Last Seen** timestamp.

---

## 7. Phase VI: Device Profile & Regional Parameter Engineering

A **Device Profile** defines operational radio parameters, frequency band definitions, MAC version, and Adaptive Data Rate (ADR) algorithms.

### 7.1 Creating the Device Profile
1. In ChirpStack Web UI, navigate to **Device Profiles -> Add Device Profile**.
2. Fill in the **General** tab options:

```text
+-------------------------------------------------------------------+
|                  Device Profile Field Configuration               |
+-------------------------------------------------------------------+
| Name                                : Test                        |
| Description                         : Dragino LSN50v2 Sensor      |
| Region                              : EU868                       |
| MAC version                         : 1.0.3                       |
| Regional parameters revision        : A                           |
| ADR algorithm                       : Default ADR algorithm       |
| Flush queue on activate             : Enabled                     |
| Uplink interval (secs)              : 3600                        |
| Device-status request frequency     : 1                           |
| RX1 Delay                           : 0                           |
| RX1 data rate offset                : 0                           |
| RX2 data rate                       : 0                           |
| RX2 frequency (Hz)                  : 869525000                   |
+-------------------------------------------------------------------+
```

3. Click **Submit**.

---

## 8. Phase VII: End-Node Onboarding & OTAA Key Security

Over-The-Air Activation (OTAA) establishes a secure 128-bit key exchange between the device and network server.

```text
Dragino LSN50v2 Sensor            Milesight Gateway             ChirpStack v4 Server
       |                                  |                              |
  (1)  |--- JoinRequest (RF Chirp) ------>|                              |
       |    (DevEUI, AppEUI, DevNonce)    |                              |
       |                                  |--- (2) UDP PUSH_DATA -------->|
       |                                  |        (Encapsulated Join)   |
       |                                  |                              |
       |                                  |                      [Validates AppKey & MIC]
       |                                  |                      [Generates AppNonce]
       |                                  |                      [Derives NwkSKey/AppSKey]
       |                                  |                              |
       |                                  |<-- (3) UDP PULL_RESP --------|
       |                                  |        (Encapsulated Accept) |
  (4)  |<-- JoinAccept (RX1/RX2 Window)---|                              |
       |                                  |                              |
 [Derives Keys locally]                   |                              |
 [Device is JOINED!]                      |                              |
       |                                  |                              |
  (5)  |--- UnconfirmedDataUp (Encrypted)->|                              |
       |                                  |--- (6) UDP PUSH_DATA -------->|
       |                                  |        (Encrypted Telemetry) |
       |                                  |                              |
       |                                  |                      [Decrypts with AppSKey]
       |                                  |                      [Runs JavaScript Codec]
```

### 8.1 Registering the Application & Device
1. Navigate to **Applications -> Add Application**.
   * **Name**: `IoT-App`
   * **Description**: `Smart Agriculture Environmental Monitoring`
2. Click **Submit**.
3. Open `IoT-App` -> Click **Devices** tab -> Click **+ Add Device**.
4. Configure Device identity settings:
   * **Name**: `Sensor-03`
   * **Description**: `Dragino LSN50v2-S31 Temperature & Humidity Sensor`
   * **Device EUI (DevEUI)**: `A84041380189B98F`
   * **JoinEUI / AppEUI**: `A840410000000101` (Default across Dragino sensors)
   * **Device Profile**: `Test`
   * **Frame-counter validation**: `Enabled`
5. Click **Submit**.

### 8.2 Entering OTAA Security Keys
1. In `Sensor-03` page, click on the **OTAA Keys** tab.
2. Enter the device's 128-bit Application Key:
   * **Application Key**: `FD7A9B9425B4328A8281C59A84E3F3A3`
3. Click **Submit**.

### 8.3 Class A Device Downlink Mechanics & OTAA Queue Flushing Gotcha

The Dragino LSN50v2-S31 is a **Class A** LoRaWAN device by default. Understanding Class A downlink mechanics is essential for reliable device management:

* **Class A Reception Windows**: Class A end-nodes sleep to preserve battery life. A Class A node can **only** receive downlink commands during two short reception windows (RX1 and RX2) immediately following an uplink packet transmission.
* **Queuing Commands**: When you send a downlink command in ChirpStack, the command is placed in a **Downlink Queue** until the next uplink arrives from the sensor.
* **Hardware Reset Gotcha (OTAA Session Reset)**:
  * Manually opening the sensor casing and pressing the hardware `RESET` button forces an immediate hardware reboot and **OTAA Re-Join** (`JoinRequest`).
  * ⚠️ **CRITICAL GOTCHA**: Upon receiving a new `JoinRequest`, ChirpStack re-authenticates the device, generates fresh session keys (`NwkSKey`, `AppSKey`), and **flushes (drops) all pending queued downlink commands**.
  * **Result**: If you queue a command (e.g. setting the uplink interval to 1 minute via hex `0100003C`) and then immediately press the physical `RESET` button, the queued downlink **WILL BE DROPPED** during the OTAA re-join and will NOT take effect!
* **Correct Operational Downlink Workflow**:
  1. Queue the downlink payload command in ChirpStack Web UI or via API/MQTT.
  2. **Do NOT press the hardware RESET button**.
  3. Allow the device to transmit its **naturally scheduled uplink**.
  4. ChirpStack attaches the queued downlink payload to the RX1/RX2 window response following the natural uplink, and the command is successfully received and executed by the sensor.

### 8.4 Dragino LSN50v2-S31 Downlink Command Code Reference Table

Downlinks are sent on **FPort 2** (or specified FPort) as hexadecimal binary commands.

| Command Function | FPort | Hex Payload | Byte Breakdown & Format | Description & Operational Example |
| :--- | :---: | :--- | :--- | :--- |
| **Set Uplink Interval (TDC)** | `2` | `0100003C` | Byte 0: `0x01` (TDC Command)<br/>Bytes 1-3: 24-bit unsigned int (Seconds) | Sets telemetry uplink interval.<br/>• `0100003C` = 60s (1 minute)<br/>• `0100001E` = 30s<br/>• `01000258` = 600s (10 minutes)<br/>• `01000E10` = 3600s (1 hour) |
| **Software System Reboot** | `2` | `04FF` | Byte 0: `0x04`<br/>Byte 1: `0xFF` | Reboots sensor MCU without erasing stored configurations. |
| **Factory Data Reset (FDR)** | `2` | `04FE` | Byte 0: `0x04`<br/>Byte 1: `0xFE` | Restores factory default settings and forces OTAA re-join. |
| **Query Firmware & TDC Status** | `2` | `2601` | Byte 0: `0x26`<br/>Byte 1: `0x01` | Triggers sensor to send status frame on FPort 5 containing firmware version, frequency band, sub-band, and TDC interval. |

#### Step-by-Step Procedure: Queuing 1-Minute Interval Command (`0100003C`)
1. In ChirpStack Web UI, navigate to **Applications -> IoT-App -> Devices -> Sensor-03**.
2. Click the **Queue** tab.
3. Set **FPort**: `2`.
4. Set **Confirmed**: `Disabled` (unconfirmed downlink).
5. Enter **Payload (Hex)**: `0100003C`.
6. Click **Submit Queue**.
7. **Do NOT press hardware RESET button**. Wait for the sensor to naturally send its next uplink frame. The downlink will be transmitted in RX1/RX2, and subsequent uplinks will arrive every 60 seconds.


---

## 9. Phase VIII: Payload Codec Architecture & JavaScript Parsers

End-nodes transmit raw hexadecimal binary payloads to preserve battery life and minimize airtime. The **Payload Codec** decodes raw bytes into structured JSON objects.

### 9.1 Dragino LSN50v2-S31 Byte Specification

```text
+------+------+------+------+------+------+------+------+
| Byte0| Byte1| Byte2| Byte3| Byte4| Byte5| Byte6| Byte7|
+------+------+------+------+------+------+------+------+
|  BatV (mV)  | Flags|  TempC (SHT31) |   Hum (SHT31) | Alarm|
+------+------+------+------+------+------+------+------+
```

### 9.2 Complete JavaScript Codec Implementation
In ChirpStack Web UI, navigate to **Device Profiles -> Test -> Codec**. Select **JavaScript functions** and paste the production code below:

```javascript
function decodeUplink(input) {
        return { 
            data: Decode(input.fPort, input.bytes, input.variables)
        };   
}

function datalog(i,bytes){
  var aa= parseFloat(((bytes[3+i]<<24>>16 | bytes[4+i])/10).toFixed(1));
  var bb= parseFloat(((bytes[5+i]<<8 | bytes[6+i])/10).toFixed(1));
  var cc= getMyDate((bytes[7+i]<<24 | bytes[8+i]<<16 | bytes[9+i]<<8 | bytes[10+i]).toString(10));
  var string='['+aa+','+bb+','+cc+']'+',';  
  
  return string;
}

function getzf(c_num){ 
  if(parseInt(c_num) < 10)
    c_num = '0' + c_num; 

  return c_num; 
}

function getMyDate(str){ 
  var c_Date;
  if(str > 9999999999)
    c_Date = new Date(parseInt(str));
  else 
    c_Date = new Date(parseInt(str) * 1000);
  
  var c_Year = c_Date.getFullYear(), 
  c_Month = c_Date.getMonth()+1, 
  c_Day = c_Date.getDate(),
  c_Hour = c_Date.getHours(), 
  c_Min = c_Date.getMinutes(), 
  c_Sen = c_Date.getSeconds();
  var c_Time = c_Year +'-'+ getzf(c_Month) +'-'+ getzf(c_Day) +' '+ getzf(c_Hour) +':'+ getzf(c_Min) +':'+getzf(c_Sen); 
  
  return c_Time;
}

function Decode(fPort, bytes, variables) {
  //LSN50_v2_S31_S31B Decode   
  if(fPort==0x02)
  {
    var decode = {};
    var mode=(bytes[6] & 0x7C)>>2;
    if(mode==0)
    {
      decode.BatV=(bytes[0]<<8 | bytes[1])/1000;
      decode.EXTI_Trigger=(bytes[6] & 0x01)? "TRUE":"FALSE";
      decode.Door_status=(bytes[6] & 0x80)? "CLOSE":"OPEN";     
      decode.TempC_SHT31= parseFloat(((bytes[7]<<24>>16 | bytes[8])/10).toFixed(1));
      decode.Hum_SHT31=parseFloat(((bytes[9]<<8 | bytes[10])/10).toFixed(1));
      decode.Data_time= getMyDate((bytes[2]<<24 | bytes[3]<<16 | bytes[4]<<8 | bytes[5]).toString(10));         
    }
    else if(mode==31)
    {
      decode.SHTEMP_MIN= bytes[7]<<24>>24;
      decode.SHTEMP_MAX= bytes[8]<<24>>24;
      decode.SHHUM_MIN= bytes[9];
      decode.SHHUM_MAX= bytes[10];         
    }
     decode.Node_type="LSN50-S31";
    if(bytes.length==11)
      return decode;
  }
  else if(fPort==3)  
  {
    for(var i=0;i<bytes.length;i=i+11)
    {
      var data= datalog(i,bytes);
      if(i=='0')
        data_sum=data;
      else
        data_sum+=data;
    }
    return{
	Node_type:"LSN50-S31",
    DATALOG:data_sum
    };    
  }
  else if(fPort==5)
  {
  	var freq_band;
  	var sub_band;
  	
    if(bytes[0]==0x01)
        freq_band="EU868";
  	else if(bytes[0]==0x02)
        freq_band="US915";
  	else if(bytes[0]==0x03)
        freq_band="IN865";
  	else if(bytes[0]==0x04)
        freq_band="AU915";
  	else if(bytes[0]==0x05)
        freq_band="KZ865";
  	else if(bytes[0]==0x06)
        freq_band="RU864";
  	else if(bytes[0]==0x07)
        freq_band="AS923";
  	else if(bytes[0]==0x08)
        freq_band="AS923_1";
  	else if(bytes[0]==0x09)
        freq_band="AS923_2";
  	else if(bytes[0]==0x0A)
        freq_band="AS923_3";
  	else if(bytes[0]==0x0F)
        freq_band="AS923_4";
  	else if(bytes[0]==0x0B)
        freq_band="CN470";
  	else if(bytes[0]==0x0C)
        freq_band="EU433";
  	else if(bytes[0]==0x0D)
        freq_band="KR920";
  	else if(bytes[0]==0x0E)
        freq_band="MA869";
  	
    if(bytes[1]==0xff)
      sub_band="NULL";
	  else
      sub_band=bytes[1];

	  var firm_ver= (bytes[2]&0x0f)+'.'+(bytes[3]>>4&0x0f)+'.'+(bytes[3]&0x0f);
	  
	  var tdc_time= bytes[4]<<16 | bytes[5]<<8 | bytes[6];
	  
  	return {
      FIRMWARE_VERSION:firm_ver,
      FREQUENCY_BAND:freq_band,
      SUB_BAND:sub_band,
      TDC_sec:tdc_time,
  	}
  }
}
```

---

## 10. Phase IX: Packet Verification, Frame Tracing & Diagnostics

### 10.1 Inspecting Live LoRaWAN Frames
1. In ChirpStack Web UI, open **Applications -> IoT-App -> Devices -> Sensor-03**.
2. Click the **LoRaWAN Frames** tab.
3. Power cycle the Dragino sensor. You will observe the following packet trace:

```text
+-------------------+-----------------+-------+----------+--------------------+
| Time              | Frame Type      | FCnt  | FPort    | DevAddr            |
+-------------------+-----------------+-------+----------+--------------------+
| 13:40:12.102      | JoinRequest     | -     | -        | -                  |
| 13:40:12.450      | JoinAccept      | -     | -        | 01145C2A           |
| 13:40:15.820      | UnconfirmedData | 0     | 2        | 01145C2A           |
+-------------------+-----------------+-------+----------+--------------------+
```

### 10.2 Inspecting Decoded JSON Telemetry Events
Click the **Events** tab -> Select the **Up** event to verify parsed JSON data:

```json
{
  "deduplicationId": "7c520a22-d7a1-424c-8f2a-3c7b55aa3379",
  "time": "2026-07-29T05:40:15.820Z",
  "deviceInfo": {
    "tenantId": "52f9b807-2c11-4286-805f-10102d66cb55",
    "applicationId": "79e520a22-d7a1-424c-8f2a-3c7b55aa3379",
    "applicationName": "IoT-App",
    "deviceName": "Sensor-03",
    "devEui": "a84041380189b98f"
  },
  "devAddr": "01145c2a",
  "fCnt": 0,
  "fPort": 2,
  "data": "DIBpS3VLEAE=",
  "object": {
    "Alarm": "FALSE",
    "BatV": 3.664,
    "Door_status": "OPEN",
    "EXTI_Trigger": "FALSE",
    "Hum_SHT31": "49.2",
    "Node_type": "LSN50-S31",
    "TempC_SHT31": "28.8"
  }
}
```

---

## 11. Phase X: Production Troubleshooting & Runbook

### 11.1 Diagnostic Matrix

| Failure Mode | Root Cause Analysis | Diagnostic Command & Fix Procedure |
| :--- | :--- | :--- |
| **`hostname -I` returns blank/nothing** | 1. Connected to Gateway AP (`Gateway_F94C0B`) which doesn't issue DHCP leases to bridged VMs.<br/>2. VirtualBox Wi-Fi bridging frame drop.<br/>3. Linux network interface DHCP lease timeout. | • **Option A (Recommended)**: Connect Gateway via Ethernet & Host via Wi-Fi to your main router (`192.168.1.x`).<br/>• **Option B (Direct AP)**: Assign static IP to VM interface:<br/>`sudo ip addr add 192.168.23.137/24 dev enp0s3`<br/>`sudo ip link set enp0s3 up`<br/>• **Option C**: Force DHCP renew: `sudo dhclient -v`. |
| **Gateway status "Offline" after boot** | 1. Gateway packet forwarder failed to auto-bind after boot.<br/>2. Incorrect IP in Packet Forwarder.<br/>3. UDP 1700 blocked by UFW firewall. | • Open Gateway Web UI (`192.168.23.150`), navigate to **Packet Forwarder -> Multi-Destination**, and click **Save & Apply**.<br/>• Run `hostname -I` in VM to re-verify IP address.<br/>• Run `sudo ufw allow 1700/udp`.<br/>• Run `docker compose restart chirpstack-gateway-bridge`. |
| **Queued Downlink Dropped / Not Accepted** | 1. Manual hardware RESET button pressed, triggering OTAA Join which flushes pending queue.<br/>2. Class A device sleeping and downlink expired. | • **Do NOT press hardware RESET button** after queuing commands.<br/>• Re-queue downlink payload (`0100003C` on FPort 2) in ChirpStack and wait for the **naturally scheduled uplink** to deliver the downlink. |
| **JoinRequest seen, but no JoinAccept** | 1. Invalid AppKey in OTAA Keys tab<br/>2. Gateway Downlink transmission failed<br/>3. RX1/RX2 delay mismatch | • Re-enter 128-bit AppKey in ChirpStack.<br/>• Inspect Gateway Bridge logs: `docker compose logs chirpstack-gateway-bridge`.<br/>• Check `Port Down` is set to `1700` in Gateway UI. |
| **No Data Up events received** | 1. DevEUI mismatch<br/>2. Device frequency channel out-of-band | • Verify DevEUI sticker label against ChirpStack entry.<br/>• Reset device to factory defaults using Dragino AT commands. |
| **Raw Hex visible, Object empty** | 1. Payload Codec missing<br/>2. JavaScript syntax error in Codec | • Re-apply JavaScript decoder script under Device Profile -> Codec tab.<br/>• Check ChirpStack server logs for JS runtime exceptions: `docker compose logs chirpstack`. |

### 11.2 Essential Diagnostic CLI Commands

```bash
# 1. Inspect live UDP packet flow on Port 1700
sudo tcpdump -i any udp port 1700 -n -X

# 2. Monitor real-time ChirpStack server logs
sudo docker compose logs -f chirpstack

# 3. Monitor Gateway Bridge traffic logs
sudo docker compose logs -f chirpstack-gateway-bridge

# 4. Subscribe to raw Mosquitto MQTT LoRaWAN topics
mosquitto_sub -h localhost -p 1883 -v -t "eu868/#"
```

### 11.3 Systemd Automated Boot Service
To ensure ChirpStack microservices launch automatically whenever the Ubuntu Server VM reboots:

1. Create a systemd unit file:
   ```bash
   sudo nano /etc/systemd/system/chirpstack-docker.service
   ```
2. Paste the unit configuration (adjust working directory path to your user home):
   ```ini
   [Unit]
   Description=ChirpStack LoRaWAN Docker Compose Service Stack
   Requires=docker.service
   After=docker.service network-online.target
   Wants=network-online.target

   [Service]
   Type=oneshot
   RemainAfterExit=yes
   WorkingDirectory=/home/batman/chirpstack-docker
   ExecStart=/usr/bin/docker compose up -d
   ExecStop=/usr/bin/docker compose down
   TimeoutStartSec=0

   [Install]
   WantedBy=multi-user.target
   ```
3. Enable and start the systemd service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable chirpstack-docker.service
   sudo systemctl start chirpstack-docker.service
   ```

---

## 🔗 Sequential Technical Documentation Index

| Sequence | Document | Focus Area | Description |
| :---: | :--- | :--- | :--- |
| **Home** | **[Master Overview (README)](./README.md)** | **Architecture Hub** | Master documentation hub, system bill of materials, network topology, and cheat sheet. |
| **01** | **[01: Master Deployment Guide](./01-master-deployment-guide.md)** | **Foundation & Stack Setup** | 10-part manual covering hypervisor setup, Ubuntu VM provisioning, online Docker installation, and ChirpStack stack launch. |
| **02** | **[02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md)** | **Offline Direct AP Mode** | Complete guide for operating when connected directly to `Gateway_F94C0B` Wi-Fi AP with bridged Wi-Fi NIC and static IP. |
| **03** | **[03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md)** | **Database Event Persistence** | Guide for creating `chirpstack_integration` DB, configuring DSN in `chirpstack.toml`, and running telemetry SQL queries. |
| **04** | **[04: Grafana Integration Guide](./04-grafana-integration-guide.md)** | **Visualization & Dashboards** | Guide for containerizing Grafana (`:3000`), connecting PostgreSQL Data Source (`postgres:5432`), and building dashboards. |
| **05** | **[05: Node-RED Integration Guide](./05-node-red-integration-guide.md)** | **Flow Automation & Alerts** | Guide for containerizing Node-RED (`:1880`), installing ChirpStack nodes, and building threshold alert flows. |
| **06** | **[06: LoRaWAN RF and Security Toolkit Brief](./06-lorawan-rf-security-toolkit-brief.md)** | **Tool Selection & Architecture** | Decision brief for RF/PHY decoding, protocol crafting, packet inspection, network-server behavior, and replay/spoof detection. |
| **07** | **[07: LoRaWAN RF and Protocol Testing Setup Guide](./07-lorawan-rf-and-protocol-testing-setup-guide.md)** | **RF-to-Protocol Test Bench** | Setup and verification path for gr-lora-sdr, Wireshark, and ChirpStack testing and security testing integration. |
| **08** | **[08: LoRaWAN Security Testing Runbook](./08-lorawan-security-testing-runbook.md)** | **Authorized Test Operations** | Pre-flight checks, evidence handling, test cases, stop conditions, triage, and reporting. |
| **09** | **[09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md)** | **Incoming Hardware Commissioning** | RAK5146 SPI/AS923 gateway assembly, packet-forwarder setup, WisBlock node programming, OTAA onboarding, and acceptance gates. |
| **Ref** | **[Dragino JS Decoder](./codecs/dragino-lsn50v2-s31-decoder.js)** | **Payload Codec** | Production JavaScript parser for decoding temperature, humidity, and battery voltage bytes. |

---
*End of Enterprise Operations Manual. Document maintained under `lorawan-setup/docs`.*
