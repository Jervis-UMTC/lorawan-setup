# Complete Offline Direct Gateway AP Setup Guide
## Milesight UG65 Gateway (`Gateway_F94C0B`) & ChirpStack v4 Docker Stack

This guide provides an **exhaustive, production-grade, step-by-step procedure** for deploying and operating the **ChirpStack v4 LoRaWAN Stack** on an Ubuntu Server Virtual Machine in an **offline direct Access Point (AP) topology**.

When your host machine connects directly to the Milesight UG65 Gateway's Wi-Fi Access Point (`Gateway_F94C0B`), internet access will be unavailable. This manual covers online pre-requisites, hypervisor bridged network interface selection, Wi-Fi association, Ubuntu static IP and default gateway configuration, route verification, Docker microservices deployment, and gateway packet forwarder integration.

---

## 📌 Master Network Topology & Subnet Map

In Direct AP Mode, the Milesight UG65 Gateway operates as a standalone Wi-Fi Access Point on the `192.168.23.0/24` subnet.

```text
+---------------------------------------------------------------------------------------+
|                    Milesight UG65 Gateway AP (SSID: Gateway_F94C0B)                   |
|                               Gateway IP: 192.168.23.150                              |
|                    Semtech UDP Listener Target IP: 192.168.23.137                      |
+---------------------------------------------------------------------------------------+
        ^                                           |
        | Wi-Fi Association                         | Semtech UDP Packets
        | (Subnet: 192.168.23.0/24)                 | (UDP Uplink/Downlink Port 1700)
        v                                           v
+------------------------------------+      +-------------------------------------------+
|            Host Laptop             |      |             Ubuntu Server VM              |
|  Connected to: Gateway_F94C0B      |======|  VirtualBox Bridged Adapter               |
|  Host IP: 192.168.23.X (via DHCP)  | (VLAN|  Attached to: Host Wireless/Wi-Fi NIC    |
+------------------------------------+ Bridge|  STATIC IP: 192.168.23.137/24             |
|  Host Web Browser Access:          |      |  DEFAULT GATEWAY: 192.168.23.150          |
|  • Milesight UI: 192.168.23.150    |      +-------------------------------------------+
|  • ChirpStack UI: 192.168.23.137:8080|    |  ChirpStack v4 Docker Microservices:      |
+------------------------------------+      |  • Gateway Bridge (UDP 1700 Listener)     |
                                            |  • Mosquitto MQTT Broker (TCP 1883)       |
                                            |  • ChirpStack Core & Web UI (TCP 8080)    |
                                            |  • PostgreSQL 14 & Redis 7 DB Engines     |
                                            +-------------------------------------------+
```

### Subnet Assignment Reference Table

| Device / Interface | Role | IP Address / Netmask | Gateway / Listener |
| :--- | :--- | :--- | :--- |
| **Milesight UG65 Gateway** | Access Point & Packet Forwarder | `192.168.23.150 / 24` | AP DHCP Server & Web Admin |
| **Ubuntu Server VM** | ChirpStack LoRaWAN Network Server | `192.168.23.137 / 24` | Default Gateway: `192.168.23.150` |
| **Host Laptop Wi-Fi NIC** | Virtual Machine Host & Operator | `192.168.23.X / 24` (DHCP) | Gateway: `192.168.23.150` |
| **ChirpStack Gateway Bridge** | UDP Packet Receiver | `192.168.23.137` | UDP Port `1700` |
| **ChirpStack Web Dashboard** | Management Console | `192.168.23.137` | TCP Port `8080` |

---

## 🧠 DEEP TECHNICAL BACKING EXPLANATIONS & NETWORKING MECHANICS

### 1. Why Is VirtualBox Bridged Adapter Required (vs. NAT or Host-Only)?
* **NAT (Network Address Translation)**: Under NAT, VirtualBox creates an isolated internal network (`10.0.2.0/24`) and acts as a router/firewall. Incoming UDP datagrams transmitted by the Milesight Gateway on port 1700 to the host laptop's IP (`192.168.23.X`) are dropped by the host OS kernel because no NAT port forwarding entry exists for the VM's internal `10.0.2.15` address.
* **Host-Only Mode**: Creates a private software loopback network between the Host OS and VM. The VM is completely disconnected from physical hardware (including the host's Wi-Fi adapter), preventing communication with external devices like the Milesight Gateway.
* **Bridged Adapter**: Inserts VirtualBox’s NDIS filter driver into the host's physical network stack. The VM becomes a peer host on the `192.168.23.0/24` physical Wi-Fi network, obtaining direct layer-2 Ethernet MAC access to send and receive UDP 1700 frames.

### 2. Why Select the Physical Wireless/Wi-Fi NIC Name?
Hypervisors require explicit binding to a specific physical network interface card (NIC):
* Binding VirtualBox Bridged Adapter to an inactive Ethernet LAN card (`Realtek PCIe GbE...`) creates a bridge to a physical port with no cable attached (`Link Down`), causing all VM packet transmissions to fail silently.
* Binding explicitly to the **Host's Active Wireless Card** (e.g. `Intel(R) Wi-Fi 6 AX201`) forces VirtualBox to transmit virtual VM frames over the active IEEE 802.11 radio link connected to `Gateway_F94C0B`.

### 3. Why Set Promiscuous Mode to `Allow All` on Wi-Fi Bridges?
Wi-Fi access points (802.11 standards) validate MAC addresses in frame headers. By default, host wireless NIC drivers drop incoming Wi-Fi frames whose destination MAC address does not match the host laptop's physical Wi-Fi card.
* Setting **Promiscuous Mode** to `Allow All` instructs the VirtualBox virtual switch to intercept all broadcast and unicast Ethernet frames received on the physical Wi-Fi link and pass them directly to the Ubuntu VM's virtual NIC (`enp0s3`), regardless of destination MAC address.

### 4. Why Configure Static IP `192.168.23.137` & Default Gateway `192.168.23.150`?
* **DHCP Absence in Offline AP Mode**: The Milesight Gateway AP's internal DHCP server is configured to assign leases to connected Wi-Fi clients (your laptop), but standard Wi-Fi MAC bridging often prevents DHCP `DISCOVER` packets originating from virtual MAC addresses (the VM) from receiving a lease. Assigning static IP `192.168.23.137` guarantees immediate, predictable layer-3 binding.
* **Default Gateway Route (`192.168.23.150`)**: Linux kernel routing requires a default route (`0.0.0.0/0 via 192.168.23.150`). Without a default gateway, Linux netstack drops any outgoing packet where the destination IP falls outside immediate netmask matches or when handling multi-interface return traffic.

---

## ⚠️ STEP 0: ONLINE PREREQUISITES (Execute Before Disconnecting Internet)

Because connecting to the Milesight Gateway AP (`Gateway_F94C0B`) drops external internet connectivity, **you MUST execute these commands while connected to an internet-enabled Wi-Fi or Ethernet network**.

### 0.1 Update System Packages & Install Dependencies
Inside your Ubuntu Server VM terminal:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git apt-transport-https ca-certificates software-properties-common net-tools iputils-ping traceroute bridge-utils
```

### 0.2 Install Docker Engine & Docker Compose Plugin
```bash
# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc > /dev/null

# Set up repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker packages
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable and start Docker service
sudo systemctl enable --now docker
```

### 0.3 Clone ChirpStack Repository & Pre-Pull Container Images
```bash
# Clone official ChirpStack Docker environment
cd ~
git clone https://github.com/chirpstack/chirpstack-docker.git
cd chirpstack-docker

# Pre-download all required microservice images into local Docker storage cache
sudo docker compose pull
```

### 0.4 Verify Cached Docker Images
```bash
sudo docker images
```
*Confirm that all five required microservices are stored locally*:
* `chirpstack/chirpstack:4`
* `chirpstack/chirpstack-gateway-bridge:4`
* `eclipse-mosquitto:2`
* `postgres:14-alpine`
* `redis:7-alpine`

---

## 🌐 STEP 1: HYPERVISOR BRIDGED NETWORK ADAPTER CONFIGURATION

To allow the Milesight Gateway and host laptop to communicate directly with the Ubuntu VM on the `192.168.23.0/24` layer-2 network, the VM's virtual network interface must be explicitly bridged to the **Host's Wireless/Wi-Fi Network Card**.

### 1.1 Open VirtualMachine Network Settings
1. Open **Oracle VM VirtualBox Manager** (or VMware Workstation).
2. Ensure your Ubuntu VM (`lorawan`) is powered down or saved (or edit live settings if supported).
3. Select the VM -> Click **Settings** (or `Ctrl+S`).
4. Click on **Network** in the left sidebar.

### 1.2 Configure Network Adapter 1
Configure the adapter properties as follows:
* **Enable Network Adapter**: `[X] Checked`
* **Attached to**: Select **`Bridged Adapter`** (Do NOT select NAT, Host-Only, or Internal Network).
* **Name**: Select your **Host Laptop's Physical Wireless/Wi-Fi Network Interface Name**.
  * *Examples of valid Wi-Fi Adapter names*:
    * `Intel(R) Wi-Fi 6 AX201 160MHz`
    * `Realtek 8822CE Wireless LAN 802.11ac PCI-E NIC`
    * `Qualcomm FastConnect 6900 Wi-Fi 6E Dual Station`
  * ⚠️ **CRITICAL ERROR TO AVOID**: Do **NOT** select your Ethernet/LAN NIC (e.g., `Realtek PCIe GbE Family Controller`) or virtual adapters (`VirtualBox Host-Only Ethernet Adapter`, `vEthernet`). You MUST select the wireless card that will connect to the Milesight AP.

### 1.3 Configure Advanced Adapter Settings
Expand the **Advanced** drop-down menu:
* **Adapter Type**: `Intel PRO/1000 MT Desktop (82540EM)` (or `VirtIO Network` for high throughput).
* **Promiscuous Mode**: Select **`Allow All`** (or `Allow VMs`). This allows the VM to receive packets sent directly to its static MAC/IP address over the bridged Wi-Fi link.
* **MAC Address**: Leave default generated value.
* **Cable Connected**: `[X] Checked`.

Click **OK** to save settings.

```text
+--------------------------------------------------------------------------+
|                      VirtualBox Network Settings                         |
+--------------------------------------------------------------------------+
| [X] Enable Network Adapter                                               |
| Attached to : Bridged Adapter                                            |
| Name        : Intel(R) Wi-Fi 6 AX201 160MHz  <-- (Host Wireless Card)    |
| Advanced:                                                                |
|   Promiscuous Mode : Allow All                                           |
|   Cable Connected  : [X] Checked                                         |
+--------------------------------------------------------------------------+
```

---

## 📶 STEP 2: CONNECT HOST LAPTOP TO MILESIGHT GATEWAY WI-FI AP

Now you may transition from your home/office network to the Milesight UG65 Access Point.

1. On your Windows/Host machine, open the Wi-Fi network selection menu in the system tray.
2. Locate the SSID broadcasted by the Milesight Gateway:
   * **SSID Name**: **`Gateway_F94C0B`** (or `Milesight_XXXXXX` depending on factory sticker).
3. Click **Connect**.
   * *Default Wi-Fi Password (if prompted)*: `12345678` (or check label under gateway).
4. **Expected Host Behavior**:
   * Windows will show: *"Connected, no internet"* or *"No internet, open"*.
   * **This is completely normal and expected** because the Milesight AP is operating offline without a WAN uplink.

---

## 💻 STEP 3: CONFIGURE STATIC IP & DEFAULT GATEWAY IN UBUNTU TERMINAL

This section provides an **exhaustive, technical guide** for configuring a static IP address (`192.168.23.137`) and default gateway (`192.168.23.150`) on Ubuntu Server, ensuring the configuration **remains 100% permanent across system reboots, hypervisor resets, and interface toggles**.

---

### 3.1 Architecture of Ubuntu Server Networking (Netplan & `systemd-networkd`)

Modern Ubuntu Server (v18.04 LTS through v24.04 LTS) does NOT use legacy `/etc/network/interfaces` or `ifconfig`. Instead, it uses **Netplan** as an abstraction generator that configures the underlying **`systemd-networkd`** back-end renderer.

```text
+-------------------------------------------------------------------------------+
|                       User Configuration File                                 |
|                       /etc/netplan/01-netcfg.yaml                             |
+-------------------------------------------------------------------------------+
                                       |
                                       | Executed via: sudo netplan apply
                                       v
+-------------------------------------------------------------------------------+
|                        Netplan Generator Engine                               |
|        Generates: /run/systemd/network/10-netplan-enp0s3.network             |
+-------------------------------------------------------------------------------+
                                       |
                                       | Reloads System Service
                                       v
+-------------------------------------------------------------------------------+
|                      systemd-networkd Core Daemon                             |
|        Applies Kernel Link State, Static IP & Default Gateway Routes           |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                       Linux Kernel Network Subsystem                          |
|    Interface: enp0s3 | IP: 192.168.23.137/24 | Default Gateway: 192.168.23.150   |
+-------------------------------------------------------------------------------+
```

---

### 3.2 Step 1: Prevent Cloud-Init Overwrites Across Reboots (CRITICAL)

On Ubuntu Server ISO installations, the `cloud-init` package frequently regenerates `/etc/netplan/50-cloud-init.yaml` upon reboot, overwriting your custom static IP and reverting the interface to DHCP.

**To permanently lock your custom network configuration**:

1. Open (or create) the cloud-init network configuration override file:
   ```bash
   sudo nano /etc/cloud/cloud.cfg.d/99-disable-network-config.cfg
   ```
2. Insert the following single line:
   ```yaml
   network: {config: disabled}
   ```
3. Save (`Ctrl + O`, `Enter`) and exit (`Ctrl + X`).

---

### 3.3 Step 2: Detect Active Network Interface Name

Run the Linux IP link tool to inspect all detected hardware network devices:

```bash
ip -br link
```
*Expected Output*:
```text
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 
enp0s3           UP             08:00:27:fa:9c:0b <BROADCAST,MULTICAST,UP,LOWER_UP> 
docker0          DOWN           02:42:1a:89:b3:4c <NO-CARRIER,BROADCAST,MULTICAST,UP> 
```

Identify your active Ethernet interface:
* Common naming conventions: **`enp0s3`** (VirtualBox), `eth0`, `ens33` (VMware), or `enp1s0`.

---

### 3.4 Step 3: Configure Permanent Netplan YAML (`01-netcfg.yaml`)

#### 1. Open Netplan Configuration File
```bash
sudo nano /etc/netplan/01-netcfg.yaml
```
*(If `/etc/netplan/50-cloud-init.yaml` exists, you can edit that file directly or remove it and use `01-netcfg.yaml`)*.

#### 2. Write the Complete Static IP & Default Gateway Schema
Paste the following exact Netplan v2 configuration block:

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    enp0s3:
      dhcp4: no
      dhcp6: no
      addresses:
        - 192.168.23.137/24
      routes:
        - to: default
          via: 192.168.23.150
      nameservers:
        addresses:
          - 192.168.23.150
          - 1.1.1.1
```

> ⚠️ **STRICT NETPLAN FORMATTING & SYNTAX RULES**:
> 1. **No Tabs Allowed**: Netplan parser strictly rejects tab characters. Use **2 spaces** per indentation level.
> 2. **`dhcp4: no` & `dhcp6: no`**: Explicitly disables DHCP background daemon requests on `enp0s3`.
> 3. **`addresses: [192.168.23.137/24]`**: Assigns static IPv4 address `192.168.23.137` with Class C subnet mask `255.255.255.0` (`/24`).
> 4. **`routes: - to: default via 192.168.23.150`**: Instructs the Linux kernel to route all out-of-subnet traffic to the **Milesight UG65 Gateway IP (`192.168.23.150`)** as the default gateway.
> 5. **`nameservers: addresses: [192.168.23.150]`**: Points local system DNS resolution (`systemd-resolved`) to the gateway.

#### 3. Set Strict File Permissions
Netplan requires configuration files to be readable only by root (`0600` permissions):
```bash
sudo chmod 600 /etc/netplan/*.yaml
```

---

### 3.5 Step 4: Safely Test & Apply Permanent Configuration

#### 1. Safely Test Configuration (Rollback Protection)
Run `netplan try` before committing. If syntax is invalid or connectivity drops, Netplan will automatically revert changes after 120 seconds:
```bash
sudo netplan try
```
*If prompt appears*: Press `Enter` to accept and confirm the configuration.

#### 2. Apply Configuration
```bash
sudo netplan apply
```

#### 3. Restart Network Daemon Services
```bash
sudo systemctl restart systemd-networkd
```

---

### 3.6 Ephemeral CLI Commands vs. Permanent Netplan Persistence

Understanding the distinction between temporary terminal commands and permanent Netplan configuration:

| Network Property | Method A: Ephemeral CLI (`ip` tool) | Method B: Permanent Netplan (`/etc/netplan/`) |
| :--- | :--- | :--- |
| **Command Syntax** | `sudo ip addr add 192.168.23.137/24 dev enp0s3`<br/>`sudo ip route add default via 192.168.23.150 dev enp0s3` | Edit `/etc/netplan/01-netcfg.yaml`<br/>Run `sudo netplan apply` |
| **Execution Speed** | Immediate (Instant kernel socket update) | 1 - 2 seconds (Generates systemd network unit) |
| **Reboot Persistence** | ❌ **LOST ON REBOOT** (Stored in volatile RAM) | ✅ **PERMANENT** (Persists indefinitely across reboots) |
| **Use Case** | Quick emergency debugging or live testing | Production deployments & server provisioning |

---

### 3.7 Step 5: One-Command Netplan Mode Switcher Automation (`set-dhcp.sh` & `set-static.sh`)

To switch conveniently between **DHCP (for NAT / Home Internet Access)** and **Static IP (for Milesight Gateway AP Connection)**, create two separate Netplan configuration files and automate swapping them using one-command bash scripts.

#### 1. Create the DHCP Configuration File (`01-dhcp.yaml`)
Create file `/etc/netplan/01-dhcp.yaml`:
```bash
sudo nano /etc/netplan/01-dhcp.yaml
```
Paste content (replace `enp0s3` with your interface name):
```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    enp0s3:
      dhcp4: true
      dhcp6: no
```

#### 2. Create the Static IP Configuration File (`02-static.yaml.bak`)
Create file `/etc/netplan/02-static.yaml.bak`:
```bash
sudo nano /etc/netplan/02-static.yaml.bak
```
Paste content (adjust static IP and gateway to match your network):
```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    enp0s3:
      dhcp4: no
      dhcp6: no
      addresses:
        - 192.168.23.137/24
      routes:
        - to: default
          via: 192.168.23.150
      nameservers:
        addresses:
          - 192.168.23.150
          - 1.1.1.1
```

#### 3. Create Automation Scripts for One-Command Toggling

##### Script 1: `set-dhcp.sh` (For NAT / Internet Connection)
Create `/usr/local/bin/set-dhcp.sh`:
```bash
sudo nano /usr/local/bin/set-dhcp.sh
```
Paste commands:
```bash
#!/bin/bash
# Switch Ubuntu VM interface to DHCP (for NAT / Internet Access)
echo "[+] Switching Netplan to DHCP Mode (Internet Access)..."
sudo mv /etc/netplan/02-static.yaml /etc/netplan/02-static.yaml.bak 2>/dev/null
sudo mv /etc/netplan/01-dhcp.yaml.bak /etc/netplan/01-dhcp.yaml 2>/dev/null
sudo chmod 600 /etc/netplan/*.yaml 2>/dev/null
sudo netplan apply
echo "[✓] Network mode set to DHCP. Current IP:"
hostname -I
```

##### Script 2: `set-static.sh` (For Milesight Gateway AP Connection)
Create `/usr/local/bin/set-static.sh`:
```bash
sudo nano /usr/local/bin/set-static.sh
```
Paste commands:
```bash
#!/bin/bash
# Switch Ubuntu VM interface to Static IP (for Milesight Gateway AP Mode)
echo "[+] Switching Netplan to Static IP Mode (Milesight Gateway AP)..."
sudo mv /etc/netplan/01-dhcp.yaml /etc/netplan/01-dhcp.yaml.bak 2>/dev/null
sudo mv /etc/netplan/02-static.yaml.bak /etc/netplan/02-static.yaml 2>/dev/null
sudo chmod 600 /etc/netplan/*.yaml 2>/dev/null
sudo netplan apply
echo "[✓] Network mode set to Static IP (192.168.23.137 -> 192.168.23.150). Current IP:"
hostname -I
```

##### Make Scripts Executable
```bash
sudo chmod +x /usr/local/bin/set-dhcp.sh /usr/local/bin/set-static.sh
```

Now you can simply execute `set-dhcp.sh` or `set-static.sh` from any terminal directory to instantly toggle your network mode!

---

## 🔬 STEP 4: VERIFY LOCAL NETWORK ROUTING & CONNECTIVITY

Before launching Docker, run these mandatory diagnostic commands to confirm network layer-2 and layer-3 integrity:

### 4.1 Check Assigned IP Address
```bash
hostname -I
```
*Expected Output*:
```text
192.168.23.137 172.17.0.1 172.18.0.1
```

### 4.2 Inspect System Routing Table
```bash
ip route show
```
*Expected Output*:
```text
default via 192.168.23.150 dev enp0s3 proto static 
192.168.23.0/24 dev enp0s3 proto kernel scope link src 192.168.23.137 
```
*Verify that `default via 192.168.23.150` is active!*

### 4.3 Ping Milesight Gateway (`192.168.23.150`)
```bash
ping -c 4 192.168.23.150
```
*Expected Output*:
```text
PING 192.168.23.150 (192.168.23.150) 56(84) bytes of data.
64 bytes from 192.168.23.150: icmp_seq=1 ttl=64 time=1.82 ms
64 bytes from 192.168.23.150: icmp_seq=2 ttl=64 time=1.45 ms
--- 192.168.23.150 ping statistics ---
4 packets transmitted, 4 received, 0% packet loss, time 3004ms
```

### 4.4 Verify ARP Resolution
```bash
ip neigh
```
*Verify that `192.168.23.150 dev enp0s3 lladdr xx:xx:xx:xx:xx:xx REACHABLE` appears.*

---

## ⚙️ STEP 5: MILESIGHT UG65 GATEWAY PACKET FORWARDER SETUP

1. Open a browser on your Host Laptop (connected to `Gateway_F94C0B`).
2. Navigate to the Milesight Gateway Web Management Interface:
   ```http
   http://192.168.23.150
   ```
3. Log in with standard administrator credentials:
   * **Username**: `admin`
   * **Password**: `password` (or your customized admin password).
4. Navigate to **Packet Forwarder** -> **Multi-Destination**.
5. Click **+ Add** (or edit existing destination) and configure the following parameters:

```text
+-----------------------------------------------------------------------+
|              Milesight Packet Forwarder Configuration                 |
+-----------------------------------------------------------------------+
| Enable                 : [X] Checked                                  |
| Server Type            : Semtech                                      |
| Server Address         : 192.168.23.137  <-- (Static IP of Ubuntu VM) |
| Port Up                : 1700                                         |
| Port Down              : 1700                                         |
| Location / Description : Offline Local ChirpStack Bridge              |
+-----------------------------------------------------------------------+
```

6. Click **Save** and **Apply**.

---

## 🐳 STEP 6: LAUNCH CHIRPSTACK DOCKER STACK (OFFLINE MODE)

In the Ubuntu VM terminal, launch your containerized ChirpStack infrastructure:

### 6.1 Navigate to Docker Directory
```bash
cd ~/chirpstack-docker
```

### 6.2 Spin Up Container Microservices
```bash
# Launch container stack without downloading new images (--no-build flag optional)
sudo docker compose up -d
```

### 6.3 Check Microservice Container Status
```bash
sudo docker compose ps
```
*Confirm that all five microservices show state `Up` or `running`*:

```text
NAME                                       COMMAND                  SERVICE                  STATUS
chirpstack-docker-chirpstack-1             "/usr/bin/chirpstack…"   chirpstack               running (healthy)
chirpstack-docker-chirpstack-gateway-bridge-1 "/usr/bin/chirpstack…" gateway-bridge          running
chirpstack-docker-mosquitto-1              "/docker-entrypoint.…"   mosquitto                running
chirpstack-docker-postgres-1               "docker-entrypoint.s…"   postgres                 running
chirpstack-docker-redis-1                  "docker-entrypoint.s…"   redis                    running
```

### 6.4 Verify Gateway Bridge UDP 1700 Listening State
```bash
sudo netstat -tulpn | grep 1700
# OR
sudo ss -ulpn | grep 1700
```
*Expected Output*:
```text
udp  0  0 0.0.0.0:1700  0.0.0.0:*  docker-proxy
```

---

## 🌐 STEP 7: CHIRPSTACK WEB UI ACCESS & ONBOARDING

### 7.1 Access ChirpStack Dashboard
On your host laptop web browser, navigate to:
```http
http://192.168.23.137:8080
```
Log in with default ChirpStack credentials:
* **Username**: `admin`
* **Password**: `admin`

---

### 7.2 Onboard Milesight UG65 Gateway
1. Navigate to **Gateways** in the left menu -> Click **Add Gateway**.
2. Fill out gateway parameters:
   * **Name**: `Milesight-UG65-Offline`
   * **Description**: `Local AP Mode Gateway`
   * **Gateway ID (EUI)**: Enter the 16-character hexadecimal Gateway EUI found on the physical sticker of the UG65 (or under Gateway Status in Milesight UI).
   * **Stats interval (secs)**: `30`
3. Click **Submit**.
4. Verify that the status indicator transitions to **Never** -> **Online** (once stats or telemetry ping arrives).

---

### 7.3 Create Device Profile, Application, and End-Node
1. **Device Profile**:
   * Navigate to **Device Profiles** -> **Add Device Profile**.
   * **Name**: `Dragino-LSN50v2-Profile`
   * **Region**: `EU868` (or `US915` / `AS923` matching hardware).
   * **MAC Version**: `1.0.3`
   * **Regional Parameters Revision**: `RP001-1.0.3`
   * **Codec**: Select **JavaScript functions**.
   * Paste payload decoder function from `docs/codecs/dragino-lsn50v2-s31-decoder.js`.
   * Click **Submit**.

2. **Application**:
   * Navigate to **Applications** -> **Add Application**.
   * **Name**: `Smart-Agriculture-Offline`
   * Click **Submit**.

3. **Device Onboarding (OTAA)**:
   * Select `Smart-Agriculture-Offline` -> **Devices** -> **Add Device**.
   * **Name**: `LSN50v2-Sensor-01`
   * **Device EUI (DevEUI)**: Enter node DevEUI (e.g., `A84041380189B98F`).
   * **JoinEUI / AppEUI**: Enter `A840410000000101` (standard across Dragino sensor fleet).
   * **Device Profile**: `Dragino-LSN50v2-Profile`
   * Click **Submit**.
   * Under **OTAA Keys**, enter **Application Key (AppKey)**: `FD7A9B9425B4328A8281C59A84E3F3A3`.
   * Click **Submit**.

---

### 7.4 Downlink Command Queueing, Class A Mechanics & OTAA Flushing Gotcha

When sending downlink configuration commands (such as changing the uplink transmission interval) to Class A end-nodes like the Dragino LSN50v2-S31 in offline AP mode:

* **Class A Downlink Window**: The Dragino sensor sleeps between transmissions. Downlink commands queued in ChirpStack are transmitted **only** during the RX1/RX2 reception windows immediately following an uplink packet.
* **⚠️ Physical Reset & OTAA Queue Flushing Gotcha**:
  * Opening the sensor housing and pressing the hardware `RESET` button forces an immediate hardware reboot and **OTAA Re-Join** (`JoinRequest`).
  * When ChirpStack processes the `JoinRequest`, it generates new security session keys and **flushes (clears) all pending queued downlinks**.
  * **Result**: Pressing the reset button to "force" receiving a queued command (e.g. hex `0100003C` for 1-minute interval) **will cause the command to be dropped and discarded**!
* **Correct Downlink Workflow**:
  1. Queue the downlink hex command code in ChirpStack (`Applications -> Devices -> Queue`).
  2. **Do NOT press the physical RESET button**.
  3. Wait for the sensor's **naturally scheduled uplink**. ChirpStack will attach the downlink to the RX1/RX2 window, and the sensor will accept and apply the settings.

### 7.5 Dragino LSN50v2-S31 Downlink Command Reference Table

| Function | FPort | Hex Payload | Breakdown & Format | Notes / Operational Purpose |
| :--- | :---: | :--- | :--- | :--- |
| **Set Uplink Interval (TDC)** | `2` | `0100003C` | Byte 0: `0x01` (TDC Code)<br/>Bytes 1-3: 24-bit integer (Seconds) | Sets transmission period.<br/>• `0100003C` = 60s (1 min)<br/>• `0100001E` = 30s<br/>• `01000258` = 600s (10 min)<br/>• `01000E10` = 3600s (1 hour) |
| **Software MCU Reboot** | `2` | `04FF` | Byte 0: `0x04`<br/>Byte 1: `0xFF` | Reboots sensor MCU (retains persistent AT settings). |
| **Factory Data Reset (FDR)** | `2` | `04FE` | Byte 0: `0x04`<br/>Byte 1: `0xFE` | Clears stored settings, restores defaults, and re-joins via OTAA. |
| **Query Status & TDC** | `2` | `2601` | Byte 0: `0x26`<br/>Byte 1: `0x01` | Triggers sensor to reply on FPort 5 with firmware version, sub-band, and TDC. |


---

## 🔍 COMPREHENSIVE TROUBLESHOOTING & RUNBOOK

| Symptom / Error | Root Cause Analysis | Resolution & Verification Command |
| :--- | :--- | :--- |
| **VM cannot ping Gateway (`192.168.23.150`)** | VirtualBox Bridged Adapter bound to wrong physical card (e.g., Ethernet instead of Wi-Fi). | Open VM Settings -> Network -> Bridged Adapter -> Change **Name** to your active **Wireless/Wi-Fi Adapter**. Ensure Promiscuous Mode is `Allow All`. |
| **`hostname -I` does not show `192.168.23.137`** | Netplan configuration syntax error or `netplan apply` not executed. | Check indentation in `/etc/netplan/01-netcfg.yaml`. Run `sudo netplan apply` or temporary CLI commands in Step 3.3. |
| **`ip route show` missing `default via 192.168.23.150`** | Default gateway route omitted in Netplan or flushed. | Add `routes: - to: default via 192.168.23.150` to Netplan, or run `sudo ip route add default via 192.168.23.150 dev enp0s3`. |
| **ChirpStack Gateway shows "Never" / Offline** | Ubuntu UFW firewall blocking UDP port 1700, gateway targeting wrong IP, or gateway packet forwarder socket failed auto-bind after reboot. | Run `sudo ufw allow 1700/udp` in VM. In Milesight UI, confirm Packet Forwarder target IP is `192.168.23.137`. **If gateway rebooted, navigate to Packet Forwarder -> Multi-Destination and click Save & Apply**. |
| **Queued Downlink Dropped / Command Ignored** | User pressed physical RESET button on sensor after queuing downlink, triggering OTAA Join which flushes pending queue. | **Do NOT press hardware RESET button** after queuing downlinks. Re-queue payload (`0100003C` on FPort 2) in ChirpStack and wait for the **naturally scheduled uplink**. |
| **Docker `Error response from daemon` on launch** | Attempted `docker compose pull` without internet connection. | Do NOT run `pull` offline. Execute `sudo docker compose up -d` using pre-cached images. |
| **Host cannot access `192.168.23.137:8080` in browser** | Host Wi-Fi disconnected from `Gateway_F94C0B` AP, or firewall blocking port 8080. | Reconnect Host Wi-Fi to SSID `Gateway_F94C0B`. Run `sudo ufw allow 8080/tcp` inside Ubuntu VM. |

---

## 🔄 STEP 8: NETWORK TRANSITION RUNBOOK (OFFLINE AP <-> ONLINE INTERNET)

When field operations require switching between the offline gateway AP (`Gateway_F94C0B`) and an online Wi-Fi network (for downloading updates, pulling Docker images, or internet browsing):

### 8.1 Reconnecting to Online Wi-Fi Network (DHCP Mode)
1. On Host Laptop, disconnect from `Gateway_F94C0B` and connect to your home/office Wi-Fi (or switch VirtualBox VM adapter to NAT).
2. In Ubuntu VM terminal, run the one-command DHCP toggle script:
   ```bash
   set-dhcp.sh
   ```
3. Verify internet connectivity:
   ```bash
   ping -c 4 google.com
   ```

### 8.2 Switching Back to Offline Gateway AP Mode (Static IP Mode)
1. On Host Laptop, reconnect Wi-Fi to `Gateway_F94C0B` (or switch VirtualBox adapter to Bridged Wi-Fi NIC).
2. In Ubuntu VM terminal, run the one-command Static IP toggle script:
   ```bash
   set-static.sh
   ```
3. Confirm static IP and gateway routing:
   ```bash
   hostname -I              # Should show 192.168.23.137
   ping -c 4 192.168.23.150 # Ping Milesight Gateway
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
| **07** | **[07: LoRaWAN RF and Protocol Testing Setup Guide](./07-lorawan-rf-and-protocol-testing-setup-guide.md)** | **RF-to-Protocol Test Bench** | Setup and verification path for the SDR, PHY decoder, protocol parser, Wireshark, LAF, and ChirpStack integration. |
| **08** | **[08: LoRaWAN Security Testing Runbook](./08-lorawan-security-testing-runbook.md)** | **Authorized Test Operations** | Pre-flight checks, evidence handling, test cases, stop conditions, triage, and reporting. |
| **09** | **[09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md)** | **Incoming Hardware Commissioning** | RAK5146 SPI/AS923 gateway assembly, packet-forwarder setup, WisBlock node programming, OTAA onboarding, and acceptance gates. |
| **Ref** | **[Dragino JS Decoder](./codecs/dragino-lsn50v2-s31-decoder.js)** | **Payload Codec** | Production JavaScript parser for decoding temperature, humidity, and battery voltage bytes. |

---
*Document maintained under `lorawan-setup/docs/02-offline-direct-ap-setup-guide.md`.*
