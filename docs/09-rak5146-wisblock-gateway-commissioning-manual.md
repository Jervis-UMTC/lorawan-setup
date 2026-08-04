# RAK5146 + Raspberry Pi 4 All-In-One Gateway & ChirpStack v4 Master Setup Manual

This is the definitive, step-by-step, zero-guesswork manual for commissioning the **Raspberry Pi 4 Model B + RAK5146 SPI Gateway** and deploying an **All-In-One Local ChirpStack v4 Network Server** on the same Raspberry Pi 4 (Region: **AS923**).

```text
==================================================================================================
                 STANDALONE ALL-IN-ONE SYSTEM ARCHITECTURE (RASPBERRY PI 4)
==================================================================================================

 [Sub-GHz Outdoor Antenna (900-930 MHz) + Active GPS Antenna]
                            |
                            v
 [RAK5146 SPI Concentrator Card (SX1303 ASIC) + WisLink Pi HAT]
                            | Native SPI (/dev/spidev0.0)
                            v
 +-----------------------------------------------------------------------------------------------+
 | RASPBERRY PI 4 MODEL B (ALL-IN-ONE HOST COMPUTER)                                             |
 |                                                                                               |
 |  [ChirpStack Concentratord SX1303 Daemon]                                                     |
 |       | UDP Port 1700 on 127.0.0.1 (Loopback)                                                 |
 |       v                                                                                       |
 |  [Docker Container: ChirpStack Gateway Bridge]                                                |
 |       | MQTT on 127.0.0.1:1883 (Topic: as923/gateway/...)                                     |
 |       v                                                                                       |
 |  [Docker Stack: Mosquitto <-> ChirpStack v4 LNS <-> PostgreSQL / Redis]                       |
 |       | HTTP Port 8080                                                                        |
 |       v                                                                                       |
 |  [Web UI Dashboard] ---> Accessible at http://<PI_IP_ADDRESS>:8080                             |
 +-----------------------------------------------------------------------------------------------+
==================================================================================================
```

---

## 0. Non-Negotiable Safety & Hardware Rules

> [!CAUTION]
> **RULE 1: ANTENNAS FIRST, POWER LAST**
> **NEVER APPLY POWER TO THE RASPBERRY PI 4 UNTIL BOTH LORA AND GPS ANTENNAS ARE CONNECTED TO THE SMA BULKHEADS.** Powering the RAK5146 concentrator without RF termination will permanently burn out the SX1303 power amplifier within milliseconds.

> [!IMPORTANT]
> **RULE 2: VERIFY HARDWARE CARD LABELS**
> Check the physical label on your RAK5146 card. It **MUST** state **SPI** and **900–928 MHz (AS923/US915)**.
> - If it says **868 MHz** or **USB**, STOP. Software cannot change physical RF SAW filters.

> [!WARNING]
> **RULE 3: USE OFFICIAL 5V/3A POWER SUPPLY**
> Running Docker, PostgreSQL, Redis, ChirpStack v4, and the LoRa concentrator on a single Pi 4 requires clean, stable power. Use the official **5.1V / 3.0A USB-C Power Adapter**. Generic phone chargers cause under-voltage throttling (`0x50005`) and SD card corruption.

---

## 1. Verified Hardware Component Checklist

Verified from [hardware-checklist.pdf](../hardware-checklist.pdf):

| Component | Verified Hardware Model | Role in All-In-One Architecture |
| :--- | :--- | :--- |
| **Gateway & Server Host** | **Raspberry Pi 4 Model B** (4GB or 8GB RAM recommended) | Host computer running Docker, ChirpStack v4 Server, PostgreSQL, Redis, and Concentratord daemon locally. |
| **LoRa Concentrator** | **RAK5146 SPI Card** (Semtech SX1303, 900–928 MHz) | Listens on 8 channels simultaneously; hardware timestamping (TDoA). |
| **Interface HAT** | **WisLink Pi HAT** | Connects RAK5146 mPCIe SPI lines directly to Raspberry Pi 4 GPIO header. |
| **Antennas** | **Sub-GHz Outdoor Omni (900-930 MHz) + Active GPS** | Broadcasts/receives LoRa signals across farm terrain; precise GPS timing. |
| **RF Jumpers** | **2x u.FL / IPEX to SMA Female Pigtails** | Adapts micro u.FL connectors on RAK5146 to external SMA female bulkheads. |
| **Power Adapter** | **Official 5V / 3A (5.1V/3.0A) USB-C Supply** | Supplies continuous electrical power during radio & CPU load spikes. |
| **Storage** | **32GB / 64GB High Endurance microSD Card** | Holds Raspberry Pi OS, Docker images, and PostgreSQL database volumes. |

---

### 1.1 Official RAK5146 Datasheet & Hardware Specification

Extracted directly from the official **RAK5146 WisLink LoRaWAN Concentrator Datasheet**:

#### 1. Hardware Architecture & Transceivers
* **Baseband ASIC:** Semtech **SX1303** (Emulates 8x8 parallel LoRa demodulation paths, 8x SF5-SF12 & 8x SF5-SF10 demodulators, 1x high-speed LoRa demodulator, 1x (G)FSK demodulator).
* **RF Front-End Transceivers:** 2x Semtech **SX1250** (handles 50 $\Omega$ RF signal processing & digital filtering).
* **Listen Before Talk (LBT):** Semtech **SX1261 / SX126X** (integrated LBT engine).
* **GPS / GNSS Chipset:** Onboard **ZOE-M8Q** (Provides NMEA sentences over UART and generates 1PPS hardware timing pulse connected to SX1303 and mPCIe Pin 19 for Fine Timestamping / TDoA geolocation).
* **Form Factor:** Standard 52-pin mini-PCIe card (30 mm x 50.96 mm x 5.5 mm, weight 16.3 g).

#### 2. mPCIe 52-Pin Signal & WisLink Pi HAT Mapping

| mPCIe Pin No. | RAK5146 Signal Name | Signal Type | Description | WisLink Pi HAT Connection |
| :--- | :--- | :--- | :--- | :--- |
| **Pin 2, 24, 39, 41, 52** | `3V3` / `3.3Vaux` | Power Input | Module 3.3V DC Power Supply (3.0V – 3.6V DC) | Pi 4 3.3V Rail (Header Pins 1, 17) |
| **Pin 4, 9, 15, 18, 21, 26, 27, 29, 34, 35, 37, 40, 43, 50** | `GND` | Ground | System Ground | Pi 4 GND (Header Pins 6, 9, 14, 20, 25, 30, 34, 39) |
| **Pin 22** | `PERST#` / `SX1303_RESET` | Digital Input | Active HIGH reset signal ($\ge 100$ ns pulse) | **Pi 4 GPIO 17** (Header Pin 11) |
| **Pin 19** | `RESERVED` / `PPS` | Digital Output | GPS 1PPS Time Pulse Output | SX1303 Internal Timestamp Engine |
| **Pin 31** | `PETn0` / `PI_UART_TX` | Digital Input | Host UART TX $\rightarrow$ ZOE-M8Q GPS RX | **Pi 4 GPIO 14 / TXD0** (Header Pin 8) |
| **Pin 33** | `PETp0` / `PI_UART_RX` | Digital Output | ZOE-M8Q GPS TX $\rightarrow$ Host UART RX | **Pi 4 GPIO 15 / RXD0** (Header Pin 10) |
| **Pin 45** | `HOST_SCK` | Digital Input | SPI Clock (SCK) | **Pi 4 GPIO 11 / SPI0_SCLK** (Header Pin 23) |
| **Pin 47** | `HOST_MISO` | Digital Output | SPI Master In Slave Out (MISO) | **Pi 4 GPIO 9 / SPI0_MISO** (Header Pin 21) |
| **Pin 49** | `HOST_MOSI` | Digital Input | SPI Master Out Slave In (MOSI) | **Pi 4 GPIO 10 / SPI0_MOSI** (Header Pin 19) |
| **Pin 51** | `HOST_CSN` | Digital Input | SPI Chip Select (CS0) | **Pi 4 GPIO 8 / SPI0_CE0_N** (Header Pin 24) |

#### 3. Onboard LED Definitions
* **`D1` (Red):** `TX_ON` (Illuminates when the gateway is transmitting LoRa RF packets).
* **`D2` (Blue):** `RX_ON` (Illuminates when LoRa packets are received).
* **`D3` (Green):** `CONFIG / POWER_OK` (Power & configuration status indicator).

#### 4. Hardware Model Variant Table (PID)

| Model Variant | Frequency Range | Interface | GPS | LBT | Product ID (PID) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RAK5146-115** *(Verified Card)* | **9XX MHz** (US915 / AS923 / AU915 / KR920) | **SPI** | **Yes (ZOE-M8Q)** | No | **`516010`** |
| **RAK5146-110** | 9XX MHz | SPI | No | No | `516023` |
| **RAK5146-126** | 9XX MHz | USB | Yes | Yes | `516013` |
| **RAK5146-215** | 8XX MHz (EU868 / RU864 / IN865) | SPI | Yes | No | `515011` |

#### 5. Electrical & RF Operating Parameters
* **Operating Supply Voltage:** $3.3\text{ V DC} \pm 0.3\text{ V}$
* **Max TX Current Draw:** $512\text{ mA}$ @ $+27\text{ dBm}$ Output Power
* **RX Mode Current Draw:** $81.6\text{ mA}$
* **Maximum RF Output Power:** $+27\text{ dBm}$
* **Receive Sensitivity:** Down to $-139\text{ dBm}$ @ SF12, BW 125 kHz
* **RF Impedance:** $50\ \Omega$ (via Hirose U.FL-R-SMT connector)

---

## 2. Phase 1: Physical Hardware Assembly (Power Disconnected)

Perform all physical assembly on a dry, anti-static surface with power disconnected.

```text
WisLink Pi HAT mPCIe Slot          RAK5146 Board           SMA Bulkheads
+-----------------------+     +--------------------+     +--------------+
| Insert at 30° Angle   |---->| Fasten 2x M2 Screws|---->| Attach Pigtail|
+-----------------------+     +--------------------+     +--------------+
                                                                |
Raspberry Pi 4 GPIO Header                                      v
+-----------------------+                         +---------------------+
| Press HAT down flush  |<------------------------| Thread Both Antennas|
+-----------------------+                         +---------------------+
```

### Step 1: Install RAK5146 Card on WisLink Pi HAT
1. Place the WisLink Pi HAT on an anti-static surface.
2. Insert the RAK5146 mini-PCIe card into the HAT mPCIe socket at a 30-degree angle.
3. Press down gently until flush against standoffs and secure with two M2.0 screws.

### Step 2: Attach Micro Coaxial Pigtails (u.FL / IPEX)
1. Align u.FL pigtail 1 vertically over the connector labeled **LORA** (or **RF0**) on the RAK5146 card. Press straight down until you feel a light click.
2. Align pigtail 2 over the connector labeled **GPS** and press down until it clicks.

### Step 3: Mount HAT on Raspberry Pi 4
1. Screw four 11mm M2.5 brass standoffs into the Raspberry Pi 4 mounting holes.
2. Align the 40-pin connector on the HAT with the Pi 4 GPIO header. Press down evenly until no gold pins are visible. Fasten with M2.5 screws.

### Step 4: Thread External Antennas (CRITICAL)
1. Hand-tighten the 900–930 MHz outdoor LoRa fiberglass antenna onto the SMA female bulkhead connected to the **LORA** pigtail.
2. Screw the active GPS antenna onto the SMA female bulkhead connected to the **GPS** pigtail.

---

### 3.1 OS Image Selection: Why RAK Docs Use Desktop/Pre-built Images vs. Raspberry Pi OS Lite

> [!NOTE]
> **Why RAK Official Docs Reference Raspberry Pi OS with Desktop or RAK Pre-built Images**:
> 1. **Beginner Bench Setup**: RAK's official quickstart guides assume developers will plug an HDMI monitor, keyboard, and mouse directly into the Pi 4 to configure settings via a desktop GUI.
> 2. **Legacy Script Dependencies**: Older RAK setup scripts (`rak_common_for_gateway`) relied on Python GUI libraries pre-installed in the Desktop edition.
> 3. **RAK Pre-built WisGate OS**: RAK also provides custom pre-flashed OpenWrt images with their `gateway-config` web portal.
> 
> **Why Raspberry Pi OS Lite (64-bit) is Recommended for All-In-One Gateways**:
> - **RAM & CPU Efficiency**: Lite uses only ~150 MB RAM compared to ~600 MB for Desktop (which wastes 450 MB+ RAM running background display managers like X11/Wayland). This leaves maximum memory for Docker, ChirpStack v4, PostgreSQL, and Redis.
> - **Headless Production Standard**: Gateways run as headless network appliances managed via SSH and Web UI.
> 
> *(Note: You CAN use **Raspberry Pi OS (64-bit) with Desktop** if you want an HDMI monitor interface. Both OS versions use identical SPI kernel drivers and Docker commands).*

### 3.2 Flash OS with Raspberry Pi Imager v2.0.10
1. Insert a 32GB or 64GB Class 10 High Endurance microSD card into your PC.
2. Open **Raspberry Pi Imager v2.0.10**.
3. Select Device: **Raspberry Pi 4**.
4. Select OS: **Raspberry Pi OS (Other)** -> **Raspberry Pi OS Lite (64-bit)** *(or Raspberry Pi OS 64-bit Desktop if HDMI monitor is attached)*.
5. Select target SD Card storage.
6. Click **Edit Settings** (or **Customisation**):
   - **Hostname Tab**: Set hostname to `rak-pi4-gateway` (resolves as `rak-pi4-gateway.local`).
   - **User Tab**: Set Username `pi` and your secure Password.
   - **Wi-Fi Tab**: Select **SECURE NETWORK**, enter SSID `IT`, and enter your Wi-Fi Password.
   - **Remote access / SSH authentication Tab**:
     - Toggle **`Enable SSH`** switch to **ON** (active maroon toggle switch).
     - Select radio button **`Use password authentication`**.
   - **Raspberry Pi Connect Tab**: **LEAVE DISABLED (OFF)**. *(Headless OS; disabling Pi Connect prevents unnecessary cloud background daemons from consuming RAM/CPU).*
7. Click **SAVE**, then click **NEXT** / **YES** to write the card.

### Step 2: First Boot & SSH Access
1. Insert the flashed microSD card into the Raspberry Pi 4.
2. Connect Ethernet cable (or rely on configured Wi-Fi network `IT`).
3. Plug in the official 5V/3A USB-C power supply.
4. Wait 60 seconds, then SSH into the Pi 4 from your terminal:
   ```bash
   ssh pi@rak-pi4-gateway.local   # or ssh pi@<PI_IP_ADDRESS>
   ```

### Step 3: Enable SPI Kernel Overlay & GPIO 17 Reset Script
Execute this block of commands on the Raspberry Pi 4:

```bash
# 1. Update OS packages and install core tools required for Pi OS Lite barebones
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git build-essential raspi-config python3 curl net-tools tcpdump gpg ca-certificates

# 2. Enable SPI interface in kernel
sudo raspi-config nonint do_spi 0

# 3. Disable serial console on UART to free port for GPS module
sudo raspi-config nonint do_serial 2
echo "dtoverlay=miniuart-bt" | sudo tee -a /boot/firmware/config.txt
sudo systemctl disable hciuart

# 4. Create RAK5146 GPIO 17 hardware reset script
sudo tee /usr/local/bin/reset_rak_gateway.sh > /dev/null << 'EOF'
#!/usr/bin/env bash
RESET_PIN=17
echo "Toggling RAK5146 Concentrator Reset on GPIO ${RESET_PIN}..."
if [ -d /sys/class/gpio/gpio${RESET_PIN} ]; then
    echo "${RESET_PIN}" > /sys/class/gpio/unexport 2>/dev/null || true
fi
echo "${RESET_PIN}" > /sys/class/gpio/export 2>/dev/null || true
echo "out" > /sys/class/gpio/gpio${RESET_PIN}/direction
echo "1" > /sys/class/gpio/gpio${RESET_PIN}/value
sleep 0.1
echo "0" > /sys/class/gpio/gpio${RESET_PIN}/value
sleep 0.1
echo "${RESET_PIN}" > /sys/class/gpio/unexport 2>/dev/null || true
echo "Reset pulse delivered successfully."
EOF

sudo chmod +x /usr/local/bin/reset_rak_gateway.sh

# 5. Create boot systemd reset service to guarantee hardware reset on startup
sudo tee /etc/systemd/system/rak-gateway-reset.service > /dev/null << 'EOF'
[Unit]
Description=RAK5146 Concentrator Hardware Reset
Before=chirpstack-concentratord-sx1302.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/reset_rak_gateway.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable rak-gateway-reset.service

# 6. Reboot to apply kernel overlays and systemd service
sudo reboot
```

#### 3.3 Deep Technical Rationale: Why Every Command in Step 3 is Mandatory

| Command / Component | Why It Is Technically Mandatory | What Fails If Omitted |
| :--- | :--- | :--- |
| **`sudo raspi-config nonint do_spi 0`** | By default, Linux disables the SPI hardware peripheral on the Broadcom BCM2711 SoC to save power. This command writes `dtparam=spi=on` into `/boot/firmware/config.txt` to load the `spidev` kernel module on boot. | `/dev/spidev0.0` will not exist. Concentratord / Semtech HAL will fail immediately with `lgw_connect failure: failed to open SPI device`. |
| **`sudo raspi-config nonint do_serial 2`** | Disables the Linux interactive TTY login console on UART (`/dev/ttyAMA0` / GPIO 14 & 15) while keeping hardware serial active. | Linux will send OS shell login prompts (`raspberrypi login:`) to the GPS module, and read incoming GPS NMEA sentences as invalid shell commands, corrupting GPS parsing. |
| **`echo "dtoverlay=miniuart-bt"` & `systemctl disable hciuart`** | By default, Raspberry Pi 4 attaches Bluetooth to the high-performance PL011 UART (`/dev/ttyAMA0`) and assigns mini-UART (`/dev/ttyS0`) to GPIO pins. Mini-UART lacks hardware flow control and changes baud rate whenever CPU frequency scales. This overlay moves Bluetooth to mini-UART and assigns PL011 UART directly to the GPS pin header. | GPS NMEA data streams will suffer bit errors and packet drops whenever the Pi 4 CPU throttles or scales frequency, breaking GPS PPS timing and TDoA precision. |
| **`reset_rak_gateway.sh` (GPIO 17 Pulse)** | The Semtech SX1303 baseband chip on the RAK5146 concentrator requires a physical HIGH-to-LOW reset pulse on its reset line (hardwired to Pi GPIO 17 via WisLink Pi HAT) before SPI registers can be initialized. | The SX1303 stays in an uninitialized sleep state after boot. SPI read operations return corrupted data (`0x00` or `0xFF`), causing driver crashes during startup. |

---

### Step 4: Verification After Reboot
SSH back in (`ssh pi@rak-pi4-gateway.local`) and verify SPI device nodes:

```bash
ls -l /dev/spidev0.*
```
*Expected Output*:
```text
crw-rw---- 1 root spi 153, 0 Aug 4 08:00 /dev/spidev0.0
crw-rw---- 1 root spi 153, 1 Aug 4 08:00 /dev/spidev0.1
```

---

## 4. Phase 3: Install Docker & Deploy Local ChirpStack v4 Stack

Deploy the complete ChirpStack v4 server stack directly on the Raspberry Pi 4 using Docker Compose.

### Step 1: Install Docker Engine & Docker Compose
Run the official automated Docker installer script:

```bash
# Download and execute official Docker installer
curl -fsSL https://get.docker.com | sudo sh

# Add 'pi' user to docker group
sudo usermod -aG docker pi

# Apply group changes
newgrp docker

# Verify Docker version
docker --version
docker compose version
```

### Step 2: Create ChirpStack Docker Directory Structure
Create project directory `/opt/chirpstack-docker`:

```bash
sudo mkdir -p /opt/chirpstack-docker/configuration/chirpstack
sudo mkdir -p /opt/chirpstack-docker/configuration/chirpstack-gateway-bridge
sudo chown -R pi:pi /opt/chirpstack-docker
cd /opt/chirpstack-docker
```

### Step 3: Create Gateway Bridge Configuration
Create `/opt/chirpstack-docker/configuration/chirpstack-gateway-bridge/chirpstack-gateway-bridge.toml`:

```toml
sudo tee /opt/chirpstack-docker/configuration/chirpstack-gateway-bridge/chirpstack-gateway-bridge.toml > /dev/null << 'EOF'
[general]
log_level="info"

[integration.mqtt]
server="tcp://mosquitto:1883"
event_topic_template="as923/gateway/{{ .GatewayID }}/event/{{ .EventType }}"
command_topic_template="as923/gateway/{{ .GatewayID }}/command/{{ .CommandType }}"

[backend.semtech_udp]
ip_arg="0.0.0.0"
port=1700
EOF
```

### Step 4: Create ChirpStack Server Configuration
Create `/opt/chirpstack-docker/configuration/chirpstack/chirpstack.toml`:

```toml
sudo tee /opt/chirpstack-docker/configuration/chirpstack/chirpstack.toml > /dev/null << 'EOF'
[logging]
level="info"

[postgresql]
dsn="postgres://chirpstack:chirpstack@postgres/chirpstack?sslmode=disable"

[redis]
url="redis://redis:6379"

[network]
enabled_regions=["as923"]

[integration]
enabled=["mqtt"]

[integration.mqtt]
server="tcp://mosquitto:1883"
json=true
EOF
```

### Step 5: Create Production `docker-compose.yml`
Create `/opt/chirpstack-docker/docker-compose.yml`:

```yaml
sudo tee /opt/chirpstack-docker/docker-compose.yml > /dev/null << 'EOF'
services:
  chirpstack:
    image: chirpstack/chirpstack:4
    command: -c /etc/chirpstack
    restart: unless-stopped
    volumes:
      - ./configuration/chirpstack:/etc/chirpstack
    ports:
      - "8080:8080"
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
      - ./configuration/chirpstack-gateway-bridge:/etc/chirpstack-gateway-bridge
    depends_on:
      - mosquitto

  mosquitto:
    image: eclipse-mosquitto:2
    restart: unless-stopped
    ports:
      - "1883:1883"
    command: mosquitto -c /mosquitto-no-auth.conf

  postgres:
    image: postgres:14-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_USER=chirpstack
      - POSTGRES_PASSWORD=chirpstack
      - POSTGRES_DB=chirpstack
    volumes:
      - postgresqldata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redisdata:/data

volumes:
  postgresqldata:
  redisdata:
EOF
```

### Step 6: Launch Local ChirpStack Stack
Start all database, broker, bridge, and network server containers:

```bash
cd /opt/chirpstack-docker
docker compose up -d
```

Verify that all 5 containers are running:
```bash
docker compose ps
```
*Expected Output*: `chirpstack`, `chirpstack-gateway-bridge`, `mosquitto`, `postgres`, and `redis` all show status **running**.

---

## 5. Phase 4: Install Concentratord & Route to Localhost

### Step 1: Install ChirpStack Concentratord Daemon on Pi 4
Install the Concentratord SX1302/SX1303 driver package:

```bash
curl -s https://artifacts.chirpstack.io/key/chirpstack.key | sudo gpg --dearmor -o /usr/share/keyrings/chirpstack.gpg
echo "deb [signed-by=/usr/share/keyrings/chirpstack.gpg] https://artifacts.chirpstack.io/packages/4.x/deb stable main" | sudo tee /etc/apt/sources.list.d/chirpstack.list

sudo apt-get update
sudo apt-get install -y chirpstack-concentratord-sx1302
```

### Step 2: Configure Concentratord to Forward to Localhost (`127.0.0.1:1700`)
Edit `/etc/chirpstack-concentratord/sx1302/concentratord.toml`:

```bash
sudo tee /etc/chirpstack-concentratord/sx1302/concentratord.toml > /dev/null << 'EOF'
[concentratord]
gateway_id="0000000000000000"

[gateway]
model="rak_2287"

[gateway.model_config]
spidev="/dev/spidev0.0"
reset_pin=17
channel_plan="AS923"
EOF
```

Restart Concentratord daemon service:
```bash
sudo systemctl restart chirpstack-concentratord-sx1302
```

### Step 3: Derive Unique 64-Bit Gateway EUI
Execute this command to derive your Gateway EUI from the Pi 4 `eth0` MAC address:

```bash
MAC=$(cat /sys/class/net/eth0/address | tr -d ':')
GATEWAY_EUI=$(echo "${MAC:0:6}fffe${MAC:6:6}" | tr '[:lower:]' '[:upper:]')
echo "============================================="
echo "YOUR LOCAL GATEWAY EUI: ${GATEWAY_EUI}"
echo "============================================="
```
**Write down this 16-character Gateway EUI** (e.g. `B827EBFFFE94C0B2`).

---

## 6. Phase 5: Register Gateway in ChirpStack UI & End-to-End Verification

### Step 1: Access Local ChirpStack Web UI
Open your web browser and navigate to:
```text
http://<PI_IP_ADDRESS>:8080   (or http://rak-pi4-gateway.local:8080)
```
- **Default Username**: `admin`
- **Default Password**: `admin`

*(Change default password immediately under Settings -> Password).*

### Step 2: Add Gateway in Web UI
1. In ChirpStack Web UI, navigate to **Gateways** -> Click **+ Add Gateway**.
2. Fill in details:
   - **Name**: `RAK5146-Pi4-Local-Gateway`
   - **Gateway ID (EUI)**: Paste your 16-character EUI (e.g. `B827EBFFFE94C0B2`).
   - **Stats Interval**: `30` seconds.
3. Click **Submit**.

### Step 3: End-to-End Gateway Verification Checks

#### Check A: Web UI Connection Status
In Web UI under **Gateways**, click your gateway and verify:
- **Last Seen**: Displays `A few seconds ago` with a green indicator.

#### Check B: Loopback Packet Capture
On the Raspberry Pi 4, inspect local UDP port 1700 traffic:
```bash
sudo tcpdump -ni lo port 1700
```
*Expected Output*: Continuous packet exchange between `127.0.0.1:1700` and `127.0.0.1`.

#### Check C: Service Daemon Log Inspection
On the Raspberry Pi 4, inspect Concentratord daemon logs:
```bash
sudo journalctl -u chirpstack-concentratord-sx1302 -f -o cat
```
*Expected Log Output*:
```text
INFO: concentrator started successfully
INFO: [up] PULL_ACK received in response to PULL_DATA
INFO: [stat] gateway statistics successfully forwarded to network server
```

---

## 7. Standalone All-In-One Diagnostic & Troubleshooting Matrix

### 7.1 Comprehensive Diagnostic Matrix

| Symptom / Error | Verification Test / Diagnosis | Exact Solution |
| :--- | :--- | :--- |
| **`ssh: Connection refused` on Port 22** | Raspberry Pi 4 is online at `169.254.x.x` or DHCP IP, but SSH service is disabled | **10-Second SD Card Headless Fix**: Eject SD card, plug into PC, create a blank file named `ssh` (no extension) and `userconf.txt` in root `boot` drive. Re-insert & power on. Or re-flash SD card ensuring `Enable SSH` toggle is **ON** in Imager. |
| **SD Card Partition Missing on Windows PC** | Windows fails to assign a drive letter to `boot` (FAT32) or prompts *"You must format the disk"* | **Disk Management Fix**: Open `diskmgmt.msc`, right-click the small FAT32 `boot` partition (~256MB) -> **Change Drive Letter and Paths** -> Add drive letter (e.g., `E:`). **Never click format on the `rootfs` partition!** |
| **Windows Network Bridge Error / No Internet** | Wi-Fi 802.11 MAC restrictions block layer-2 network bridge, or ICS service is disabled | **Windows ICS Fix**: Delete existing `Network Bridge` in `ncpa.cpl`. Enable Internet Connection Sharing (ICS) on Wi-Fi adapter. If checkbox disabled, set `Internet Connection Sharing` service to **Automatic** in `services.msc`. |
| **Pi 4 Unreachable / Cannot Ping** | Wi-Fi SSID mismatch or wrong static IP subnet | **Fix**: Re-flash SD card with exact Wi-Fi SSID and password matching your laptop's current network. **OR** plug an Ethernet cable into the Pi 4 for direct wired network access. |
| **Web UI http://<PI_IP>:8080 Unreachable** | `docker compose ps` | Run `cd /opt/chirpstack-docker && docker compose up -d`. Verify port 8080 is open. |
| **`lgw_connect failure` on Pi 4** | `sudo /usr/local/bin/reset_rak_gateway.sh` | Ensure SPI enabled (`raspi-config nonint do_spi 0`). Re-seat mPCIe card. |
| **Gateway Offline in Local Web UI** | `docker compose logs chirpstack-gateway-bridge` | Verify Gateway EUI matches `eth0` MAC derivation. Restart Concentratord daemon (`sudo systemctl restart chirpstack-concentratord-sx1302`). |
| **Docker Containers Resetting / OOM** | `free -m` | Check power supply! Use official 5.1V/3A supply. Ensure 4GB/8GB Pi 4 is used. |

---

### 7.2 Windows Internet Connection Sharing (ICS) vs. Network Bridge Guide

If connecting the Raspberry Pi to a Windows PC via Ethernet cable to share the PC's Wi-Fi internet connection:

1. **Why Bridge Fails on Wi-Fi:** Standard Wi-Fi adapters (802.11) do not support Layer-2 packet bridging without WDS mode. Attempting to bridge Wi-Fi + Ethernet in `ncpa.cpl` creates an error or cuts off internet access.
2. **Proper ICS Configuration Steps:**
   - Press `Win + R`, type `ncpa.cpl`, press Enter.
   - If a **Network Bridge** adapter exists, right-click and **Delete** it.
   - Right-click **Wi-Fi** connection -> **Properties** -> **Sharing** tab.
   - Check *"Allow other network users to connect through this computer's Internet connection"*.
   - Under *Home networking connection*, select your **Ethernet** adapter -> Click **OK**.
3. **If ICS Checkbox is Disabled or Throws Service Error:**
   - Press `Win + R`, type `services.msc`, press Enter.
   - Locate **Internet Connection Sharing (ICS)** (`SharedAccess`).
   - Double-click -> Change **Startup type** to **Automatic** -> Click **Start**.

---

### 7.3 SD Card Recovery & Headless User Configuration

If the SD card partition does not appear in Windows File Explorer:

1. **Assign Drive Letter in Disk Management:**
   - Press `Win + X` -> Select **Disk Management** (`diskmgmt.msc`).
   - Locate the SD Card disk at the bottom.
   - Right-click the small FAT32 partition (~256MB to 512MB) named `boot` or `bootfs`.
   - Select **Change Drive Letter and Paths...** -> **Add** -> Assign drive letter `E:` or `F:`.
2. **Headless `userconf.txt` Creation:**
   - Open drive `E:` (`boot`).
   - Create a text file named `userconf.txt` containing the following exact line to create user `pi` with password `raspberry`:
     ```text
     pi:$6$c70VzhamVzEkjf0z$il14FrbdDpfiSFhLUBINITVQFUazwT.6v72ikiICMVJRvy36LjNPrpBxijTU5dKsKCXng57hWf5W49E10vfuK1
     ```
   - Create a blank file named `ssh` (no extension).
   - Eject the SD card and boot the Raspberry Pi. You can now SSH directly using `ssh pi@<PI_IP_ADDRESS>` or `ssh pi@rak-pi4-gateway.local`.

