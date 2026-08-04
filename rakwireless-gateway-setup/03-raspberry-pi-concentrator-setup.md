# Raspberry Pi 4 + RAK5146 Gateway Software & Driver Installation Manual

This manual provides an exhaustive, step-by-step guide to installing, configuring, and operating the gateway software on a **Raspberry Pi 4 Model B** equipped with the **RAK5146 SPI Concentrator** (Semtech SX1303) and **WisLink Pi HAT**.

---

## 1. Verified Hardware Checklist

- **Host Computer**: Raspberry Pi 4 Model B (2GB, 4GB, or 8GB RAM).
- **LoRa Concentrator**: RAK5146 SPI Concentrator Card (Semtech SX1303, 900–928 MHz / AS923).
- **Interface HAT**: WisLink Pi HAT (mini-PCIe to 40-pin GPIO adapter).
- **Power**: Official 5.1V / 3.0A USB-C Power Adapter.
- **Storage**: 32GB or 64GB High Endurance microSD card.

---

## 2. Operating System Setup (Lite vs Desktop)

### 2.1 Why RAK Docs Reference Desktop vs. Why We Recommend Lite
- **RAK Official Quickstarts**: Assume beginners plug an HDMI monitor, keyboard, and mouse into the Pi 4 for initial desktop setup.
- **Headless All-In-One Gateway (Lite)**: Uses ~150 MB RAM instead of ~600 MB RAM for Desktop. This saves 450MB+ RAM for Docker, ChirpStack v4, PostgreSQL, and Redis.
- *(Note: Both OS versions use identical SPI drivers, kernel overlays, and Docker packages).*

### 2.2 Flashing MicroSD Card (Raspberry Pi Imager v2.0.10)
1. Insert your 32GB or 64GB High Endurance microSD card into your PC.
2. Launch **Raspberry Pi Imager v2.0.10**.
3. Select Device: **Raspberry Pi 4**.
4. Select OS: **Raspberry Pi OS (Other)** -> **Raspberry Pi OS Lite (64-bit)** (or 64-bit Desktop if using HDMI monitor).
5. Select target SD Card storage.
6. Click **Edit Settings** (or **Customisation**):
   - **Hostname Tab**: Set hostname to `rak-pi4-gateway` (resolves as `rak-pi4-gateway.local`).
   - **User Tab**: Set Username `pi` and your secure Password.
   - **Wi-Fi Tab**: Select **SECURE NETWORK**, enter SSID `IT`, and enter your Wi-Fi Password.
   - **Remote access / SSH authentication Tab**:
     - Toggle **`Enable SSH`** switch to **ON** (active maroon toggle switch).
     - Select radio button **`Use password authentication`**.
   - **Raspberry Pi Connect Tab**: **LEAVE DISABLED (OFF)**. *(Reason: We are installing headless Raspberry Pi OS Lite; disabling Pi Connect prevents unnecessary cloud background daemons from consuming RAM/CPU).*
7. Click **SAVE**, then click **NEXT** / **YES** to write the card.

---

## 3. First Boot & SSH Connection Troubleshooting

### 3.1 First Boot
1. Insert the flashed microSD card into the Raspberry Pi 4.
2. Connect Ethernet cable from local network switch (or rely on configured Wi-Fi `IT`).
3. Plug in the official 5V/3A USB-C power supply.
4. Wait 60 seconds for initial system boot.

### 3.2 Connecting via SSH
Open PowerShell or Terminal and execute:

```powershell
ssh pi@rak-pi4-gateway.local
```

### 3.3 Troubleshooting SSH & Network Connectivity

#### 1. `ssh: Connection refused` or Unreachable Host
- **Root Cause A**: `169.254.x.x` is a Link-Local (APIPA) address assigned to your Windows PC's own network adapter, NOT the Raspberry Pi 4.
- **Fix**: Use `ssh pi@rak-pi4-gateway.local` or run `arp -a` in Windows Command Prompt to locate the real IP address assigned to the Pi.
- **Headless SSH & User Recovery**: If SSH was disabled, insert the SD card into a PC. In the `boot` (FAT32) drive, create an empty file named `ssh` (no extension) and a file named `userconf.txt` containing:
  ```text
  pi:$6$c70VzhamVzEkjf0z$il14FrbdDpfiSFhLUBINITVQFUazwT.6v72ikiICMVJRvy36LjNPrpBxijTU5dKsKCXng57hWf5W49E10vfuK1
  ```
  *(Creates user `pi` with default password `raspberry`)*.

#### 2. SD Card `boot` Partition Not Showing in Windows
- **Fix**: Press `Win + X` -> select **Disk Management** (`diskmgmt.msc`). Right-click the small FAT32 `boot` partition (~256MB) -> **Change Drive Letter and Paths** -> **Add** -> Assign drive letter `E:`.
- ⚠️ **Warning**: Never click "Format" when Windows prompts that the large `rootfs` Linux partition is unreadable.

#### 3. Windows Network Connection Bridging vs Internet Connection Sharing (ICS)
- **Wi-Fi Bridging Limitation**: Windows Network Bridge (`Bridge Connections` in `ncpa.cpl`) fails when bridging Wi-Fi and Ethernet adapters due to 802.11 MAC restrictions.
- **Fix**: Delete existing Network Bridge in `ncpa.cpl`. Enable **Internet Connection Sharing (ICS)** on your Wi-Fi adapter. If the checkbox is grayed out, open `services.msc` and set **Internet Connection Sharing (ICS)** to **Automatic** and click **Start**.

---

## 4. Kernel SPI Enablement & GPIO 17 Reset Script

SSH into the Raspberry Pi 4 and execute this command block:

```bash
# 1. Update OS packages and install core build tools required for Pi OS Lite
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git build-essential raspi-config python3 curl net-tools tcpdump gpg ca-certificates

# 2. Enable Kernel SPI interface
sudo raspi-config nonint do_spi 0

# 3. Disable serial console on UART to free port for GPS module
sudo raspi-config nonint do_serial 2
echo "dtoverlay=miniuart-bt" | sudo tee -a /boot/firmware/config.txt
sudo systemctl disable hciuart

# 4. Install RAK5146 GPIO 17 hardware reset script
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

# 6. Reboot system to apply kernel overlays
sudo reboot
```

### 4.1 Technical Rationale for Step 4 Configuration Commands

| Command / Component | Why It Is Technically Mandatory | What Fails If Omitted |
| :--- | :--- | :--- |
| **`sudo raspi-config nonint do_spi 0`** | By default, Linux disables SPI hardware on the Broadcom BCM2711 SoC. Writes `dtparam=spi=on` into `/boot/firmware/config.txt` to load `spidev` kernel module. | `/dev/spidev0.0` device node will not exist. Concentratord crashes with `lgw_connect failure: failed to open SPI device`. |
| **`sudo raspi-config nonint do_serial 2`** | Disables Linux interactive TTY login console on UART (`/dev/ttyAMA0` / GPIO 14 & 15) while keeping hardware serial interface active for GPS. | Linux sends shell login prompts into the GPS module and attempts to execute incoming GPS NMEA sentences as shell commands, corrupting GPS parsing. |
| **`echo "dtoverlay=miniuart-bt"` & `systemctl disable hciuart`** | Reassigns high-speed PL011 UART (`/dev/ttyAMA0`) to GPIO pins for GPS and moves Bluetooth to mini-UART (`/dev/ttyS0`). Mini-UART lacks flow control and drops bytes when CPU frequency scales. | GPS NMEA streams drop bytes whenever Pi 4 CPU scales frequency, corrupting GPS PPS time sync and TDoA geolocation. |
| **`reset_rak_gateway.sh` (GPIO 17 Pulse)** | Toggles GPIO 17 HIGH (100ms) then LOW (100ms) to deliver a physical reset pulse to the SX1303 baseband ASIC via WisLink Pi HAT pin 11. | SX1303 remains in sleep state post-boot. SPI read operations return corrupted data (`0x00`/`0xFF`), crashing driver startup. |

---

### 4.2 Post-Reboot SPI Verification
Reconnect via SSH and verify SPI device nodes:

```bash
ls -l /dev/spidev0.*
```
*Expected Output*:
```text
crw-rw---- 1 root spi 153, 0 Aug 4 08:00 /dev/spidev0.0
crw-rw---- 1 root spi 153, 1 Aug 4 08:00 /dev/spidev0.1
```

Test concentrator reset pulse:
```bash
sudo /usr/local/bin/reset_rak_gateway.sh
```
*Expected Output*: `Reset pulse delivered successfully.`

---

## 5. Driver Installation (ChirpStack Concentratord SX1302/SX1303)

Install **ChirpStack Concentratord** to manage the RAK5146 SX1303 concentrator:

```bash
# Add ChirpStack apt repository key and source
curl -s https://artifacts.chirpstack.io/key/chirpstack.key | sudo gpg --dearmor -o /usr/share/keyrings/chirpstack.gpg
echo "deb [signed-by=/usr/share/keyrings/chirpstack.gpg] https://artifacts.chirpstack.io/packages/4.x/deb stable main" | sudo tee /etc/apt/sources.list.d/chirpstack.list

# Install daemon package
sudo apt-get update
sudo apt-get install -y chirpstack-concentratord-sx1302
```

Configure `/etc/chirpstack-concentratord/sx1302/concentratord.toml`:

```toml
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

Restart daemon service:
```bash
sudo systemctl restart chirpstack-concentratord-sx1302
```

---

## 6. Gateway EUI Derivation

Derive your unique 64-bit Gateway EUI from the `eth0` MAC address:

```bash
MAC=$(cat /sys/class/net/eth0/address | tr -d ':')
GATEWAY_EUI=$(echo "${MAC:0:6}fffe${MAC:6:6}" | tr '[:lower:]' '[:upper:]')
echo "============================================="
echo "YOUR UNIQUE GATEWAY EUI: ${GATEWAY_EUI}"
echo "============================================="
```
