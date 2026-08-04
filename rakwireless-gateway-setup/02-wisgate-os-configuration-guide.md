# WisGate OS Configuration & Administration Manual

This manual provides exhaustive operational instructions for commercial RAKwireless indoor and outdoor gateways (RAK7249, RAK7289, RAK7268, RAK7240) running **WisGate OS 1** and **WisGate OS 2** (OpenWrt-based operating systems).

---

## 1. Operating System Overview (WisGate OS 1 vs WisGate OS 2)

RAKwireless commercial gateways run a custom industrial firmware built upon OpenWrt Linux:

- **WisGate OS 1 (Legacy OpenWrt 18.06)**: Uses LuCI Web UI and legacy gateway daemons. Standard on older RAK7249/7240 models.
- **WisGate OS 2 (Modern Industrial OS)**: Complete architectural rewrite featuring a responsive Vue.js frontend, enhanced security containers, granular role-based access, automated failover routing, modular plugin architecture, and native Basic Station LNS/CUPS support.

---

## 2. Initial Setup & Network Access

By default, factory-fresh RAK gateways broadcast a Wi-Fi Access Point (AP) for initial out-of-the-box configuration.

```text
Factory Default AP SSID : RAK7289_XXXX (or RAK7268_XXXX / WisGate_XXXX)
Default Wi-Fi Password  : No password (Open) or rakwireless
Default Web UI URL      : http://192.168.230.1  (or http://192.168.10.1 on legacy firmware)
Default Ethernet IP     : 192.168.10.10 (ETH port set to Static IP) or DHCP Client
Default Credentials     : Username: root
                          Password: root (WisOS 1) / Prompted to set custom password on first login (WisOS 2)
```

```text
+-----------------------------------------------------------------------------------+
|                           INITIAL GATEWAY ACCESS FLOW                             |
|                                                                                   |
|  [Power Gateway via PoE/DC]                                                       |
|             |                                                                     |
|             v                                                                     |
|  [Connect Laptop to Wi-Fi SSID: RAK7289_XXXX] or [Ethernet Cable to ETH Port]     |
|             |                                                                     |
|             v                                                                     |
|  [Open Web Browser -> Nav to http://192.168.230.1]                                |
|             |                                                                     |
|             v                                                                     |
|  [First Login: Force Password Change -> Select Target LoRa Region (AS923/US915)]  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Web Interface Administration (WisGate OS 2)

### 3.1 Initial Configuration Wizard
1. **Password Enforcement**: Upon first login, WisGate OS 2 forces the administrator to set a strong password (minimum 8 characters, requiring uppercase, lowercase, numbers, and special characters).
2. **Channel Plan Selection**: Select the regional RF plan corresponding to your hardware purchase (e.g., `AS923-1`, `US915 Sub-band 2`, or `EU868`).
3. **Mode Selection**: Choose between **Packet Forwarder Mode** (bridges RF packets to an external network server like ChirpStack or TTN) or **Built-in Network Server Mode** (runs an embedded ChirpStack instance directly inside the gateway).

---

## 4. SSH CLI Administration & UCI Command System

WisGate OS utilizes OpenWrt's **UCI (Unified Configuration Interface)** system to store and manipulate network, wireless, and packet forwarder settings via the SSH command-line interface.

### 4.1 Connecting via SSH
```bash
ssh root@192.168.230.1
```

### 4.2 Essential UCI Commands

```bash
# View complete active system configuration
uci show

# Display network interface settings
uci show network

# Display LoRa packet forwarder configuration
uci show lora

# Change LAN IP address to static 192.168.1.50
uci set network.lan.ipaddr='192.168.1.50'
uci commit network
/etc/init.d/network restart

# Inspect kernel logs and packet forwarder logs
logread -f

# Inspect system status and process tree
top
```

---

## 5. Network Backhaul Configuration & Auto-Failover

WisGate OS supports multi-WAN connectivity with automatic link failover across **Ethernet WAN**, **Wi-Fi Client (Station)**, and **4G LTE Cellular**.

```text
                        +----------------------------+
                        |  Multi-WAN Priority Engine |
                        +--------------+-------------+
                                       |
       +-------------------------------+-------------------------------+
       | Priority 1                    | Priority 2                    | Priority 3
       v                               v                               v
+--------------+               +---------------+               +---------------+
| Ethernet WAN |               | Wi-Fi Client  |               | 4G LTE Modem  |
| (PoE Cable)  |               | (Campus AP)   |               | (Quectel EG25)|
+-------+------+               +-------+-------+               +-------+-------+
        |                              |                               |
        +------------------------------+-------------------------------+
                                       | Ping Health Check (8.8.8.8)
                                       v
                     +----------------------------------+
                     | Active IP Route to LNS Server    |
                     +----------------------------------+
```

### 5.1 Ethernet WAN Configuration (Web UI)
Navigate to **Network -> Interfaces -> WAN**:
- **Protocol**: Select `DHCP Client` for automatic IP allocation, or `Static Address` for static IP assignment.
- **VLAN Tagging**: If deploying on an enterprise isolated VLAN, enable 802.1Q tagging and specify the VLAN ID (e.g., `VLAN 100`).

### 5.2 4G LTE Cellular Configuration
Navigate to **Network -> Cellular**:
- **Modem State**: Enable Cellular Interface.
- **APN (Access Point Name)**: Enter your cellular carrier's APN (e.g., `internet`, `m2m.telecom`, `telstra.m2m`).
- **Authentication**: Set to `None`, `PAP`, or `CHAP` as specified by your SIM provider.
- **PIN Code**: Enter the SIM PIN if lock is enabled.
- **Dual SIM Failover (RAK7249/RAK7289)**: Select primary SIM slot (SIM 1) and backup SIM slot (SIM 2). Configure ping drop threshold (e.g., 3 failed pings to `1.1.1.1` triggers SIM switch).

---

## 6. Packet Forwarder Mode Configuration

### 6.1 Configuring Semtech UDP Packet Forwarder
Navigate to **LoRaWAN Gateway -> Mode Configuration -> Semtech UDP Packet Forwarder**:

```text
Server Address : 192.168.1.100 (IP address of ChirpStack Gateway Bridge / Server)
Server Port Up : 1700
Server Port Down: 1700
Push ACK Enable: Enabled
Keep-Alive Interval: 10 seconds
```

### 6.2 Configuring Semtech Basic Station (LNS Protocol)
Navigate to **LoRaWAN Gateway -> Mode Configuration -> Basic Station**:

```text
URI Mode        : LNS Server
Server URI      : wss://lora.example.com:3001  (WebSocket over TLS)
Authentication  : TLS Server Authentication and Client Authentication (mTLS)
CA Certificate  : Paste Root CA Certificate (ca.crt)
Client Cert     : Paste Gateway Client Certificate (gateway.crt)
Client Key      : Paste Gateway Private Key (gateway.key)
```

---

## 7. Firmware Upgrade & TFTP Disaster Recovery

### 7.1 Web UI Sysupgrade
1. Download the latest `.bin` firmware file from the official RAKwireless Download Center (`downloads.rakwireless.com`).
2. Navigate to **System -> Firmware -> Image Upgrade**.
3. Uncheck **Keep Settings** if migrating across major versions (e.g., WisOS 1 to WisOS 2).
4. Upload the image and click **Proceed**. Do not remove power during the 5-minute flash sequence.

### 7.2 Bootloader TFTP Recovery (Emergency Unbrick)
If power fails during a firmware flash and the gateway fails to boot:

```text
1. Set Laptop Ethernet IP to static: 192.168.1.99 / Subnet: 255.255.255.0
2. Launch a TFTP Server utility (e.g., Tftpd64) on the laptop.
3. Place the official firmware file renamed to 'recovery.bin' in the TFTP root folder.
4. Connect Ethernet cable between Laptop and Gateway ETH port.
5. Hold down the Gateway Hardware Reset button using a pin.
6. Apply 12V DC power while holding the reset button for 15 seconds.
7. The bootloader (U-Boot) will request 'recovery.bin' via TFTP (192.168.1.1), flash the image, and reboot automatically.
```
