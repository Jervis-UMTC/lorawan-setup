# Volume 03: Raspberry Pi 4 & RAK5146 Gateway Engineering Handbook

## Executive Summary & Educational Purpose

This handbook covers the hardware assembly, embedded Linux kernel configuration, RF front-end engineering, packet forwarder integration, and offline edge resilience of a **LoRaWAN Base Station Gateway** constructed with a **Raspberry Pi 4 Model B** and a **RAK5146 SPI LoRaWAN Concentrator Card** (powered by the **Semtech SX1302 / SX1303** baseband chip). Designed for hardware systems engineers and network deployment teams, this text details GPIO pinouts, SPI bus timing, RF coaxial cable losses, outdoor antenna physics, systemd daemons, and offline Access Point (AP) routing.

---

## 1. Hardware Architecture & System Topology

Commercial base stations must handle high-density RF packet traffic across 8 parallel channels while operating reliably in harsh outdoor agricultural environments.

```text
+-----------------------------------------------------------------------------------+
|                        RAK5146 SPI LoRaWAN Concentrator Card                      |
|  • Semtech SX1302 / SX1303 Baseband Processor (8 Parallel RF Channels)            |
|  • Dual SX1250 RF Front-End Transceivers (Sub-GHz 868 / 915 MHz)                  |
|  • SX1303 Listen-Before-Talk (LBT) & Fine Timestamping (GPS Time Sync)            |
|  • mPCIe Form Factor -> RAK2287/RAK5146 Pi HAT Adapter Shield                      |
|  • u.FL RF Connector -> N-Type Bulkhead Connector -> LMR-400 Coaxial Cable        |
+-----------------------------------------------------------------------------------+
                                         │
                                         │ 40-Pin GPIO Interface (SPI Bus 0 + Reset Pin)
                                         v
+-----------------------------------------------------------------------------------+
|                            Raspberry Pi 4 Model B                                 |
|  • Broadcom BCM2711 Quad-core ARM Cortex-A72 @ 1.5 GHz                            |
|  • 4GB LPDDR4 SDRAM                                                               |
|  • Gigabit Ethernet (RJ45 PoE) + Dual-band 2.4/5GHz Wi-Fi (AP Mode Broadcast)     |
|  • 32GB High-Endurance Industrial MicroSD (Ubuntu Server OS / Docker Engine)      |
+-----------------------------------------------------------------------------------+
```

---

## 2. Pinout Configuration & SPI Bus Binding

The RAK5146 concentrator communicates with the Raspberry Pi host over the Serial Peripheral Interface (SPI) bus using standard 40-pin GPIO headers.

| RAK5146 Signal Name | Raspberry Pi Hardware Function | 40-Pin Header Number | Wiring Description |
| :--- | :--- | :--- | :--- |
| **3V3** | 3.3V Power Rail | Pin 1 / Pin 17 | Main DC Power (Peak Consumption 500 mA) |
| **GND** | System Ground | Pin 6 / Pin 9 / Pin 14 | Common Ground Reference |
| **SPI_MOSI** | GPIO 10 (SPI0_MOSI) | Pin 19 | Master Out Slave In Data Line |
| **SPI_MISO** | GPIO 9 (SPI0_MISO) | Pin 21 | Master In Slave Out Data Line |
| **SPI_SCLK** | GPIO 11 (SPI0_SCLK) | Pin 23 | Serial Clock Line (up to 10 MHz) |
| **SPI_CS0** | GPIO 8 (SPI0_CE0_N) | Pin 24 | Chip Enable 0 (Concentrator SPI Select) |
| **SX1302_RESET**| GPIO 17 (GPIO_GEN0) | Pin 11 | Hardware Pulse Reset Control Pin |

### Enabling SPI Interface in Raspberry Pi OS / Ubuntu Kernel

```bash
# 1. Append SPI overlay to boot configuration
echo "dtparam=spi=on" | sudo tee -a /boot/config.txt

# 2. Load spidev kernel module
sudo modprobe spidev

# 3. Verify character device node creation
ls -l /dev/spidev0.0 /dev/spidev0.1

# Expected Output:
# crw-rw---- 1 root spi 153, 0 Jul 31 08:00 /dev/spidev0.0
```

---

## 3. SX1302 Packet Forwarder Installation & Configuration

The **SX1302 Packet Forwarder** is a background C daemon that receives raw I/Q radio data over SPI, demodulates up to 8 LoRa channels simultaneously, constructs Semtech UDP packets, and forwards them to ChirpStack over IP.

### Step-by-Step Compilation

```bash
# 1. Install build dependencies
sudo apt update && sudo apt install -y build-essential git

# 2. Clone SX1302 HAL & Packet Forwarder repository
git clone https://github.com/Lora-net/sx1302_hal.git
cd sx1302_hal

# 3. Build binaries for Raspberry Pi ARM architecture
make clean
make

# 4. Test SPI reset script and read concentrator EUI64
sudo ./util_chip_id/chip_id -u -d /dev/spidev0.0
# Expected Output: EUI64: 0x0016c000189b98f (Confirms SPI hardware link)
```

### Complete Production `global_conf.json` Template (AU915 Sub-band 2)

```json
{
  "SX1302_conf": {
    "spidev_path": "/dev/spidev0.0",
    "reset_gpio": 17,
    "radio_0": {
      "enable": true,
      "type": "SX1250",
      "freq": 916800000,
      "rssi_offset": -215.0,
      "tx_enable": true
    },
    "radio_1": {
      "enable": true,
      "type": "SX1250",
      "freq": 917600000,
      "rssi_offset": -215.0,
      "tx_enable": false
    },
    "chan_multiSF_0": { "enable": true, "radio": 0, "if": -400000 },
    "chan_multiSF_1": { "enable": true, "radio": 0, "if": -200000 },
    "chan_multiSF_2": { "enable": true, "radio": 0, "if": 0 },
    "chan_multiSF_3": { "enable": true, "radio": 0, "if": 200000 },
    "chan_multiSF_4": { "enable": true, "radio": 1, "if": -400000 },
    "chan_multiSF_5": { "enable": true, "radio": 1, "if": -200000 },
    "chan_multiSF_6": { "enable": true, "radio": 1, "if": 0 },
    "chan_multiSF_7": { "enable": true, "radio": 1, "if": 200000 }
  },
  "gateway_conf": {
    "gateway_ID": "F94C0B123456789A",
    "server_address": "192.168.23.137",
    "serv_port_up": 1700,
    "serv_port_down": 1700,
    "keepalive_interval": 10
  }
}
```

---

## 4. Outdoor RF Antenna Engineering & Coaxial Losses

A base station's coverage area is dictated by antenna Gain, Height Above Ground (HAG), Voltage Standing Wave Ratio (VSWR), and Coaxial Cable Loss.

```text
+-----------------------------------------------------------------------------------+
|                            EIRP Output Power Calculation                          |
|   EIRP (dBm) = Tx Power (dBm) - Cable Loss (dB) + Antenna Gain (dBi)             |
+-----------------------------------------------------------------------------------+
```

### Coaxial Cable Loss Comparison at 915 MHz

| Cable Type | Outer Diameter | Attenuation per 10 Meters @ 915 MHz | Flexibility / Bend Radius | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **RG-58** | 4.95 mm | **-5.2 dB** (70% power lost in heat!) | Very High / Flexible | ❌ Avoid for RF runs > 1m |
| **LMR-240**| 6.10 mm | **-2.5 dB** (43% power loss) | Medium | ⚠️ Suitable for short runs (< 3m) |
| **LMR-400**| 10.29 mm | **-1.3 dB** (25% power loss) | Low / Stiff | ✅ **Recommended for Outdoor Masts** |

> [!CAUTION]
> **Lightning Protection**: Outdoor base stations mounted on tall towers MUST include a coaxial **Gas Discharge Tube (GDT) Surge Arrestor** grounded directly to an 8-foot earth grounding rod with 6 AWG copper wire.

---

## 5. Offline Access Point (AP) Edge Resilience

In remote agricultural fields lacking cellular internet coverage, the gateway can broadcast its own Wi-Fi Access Point (`Gateway_F94C0B`), allowing field agronomists to connect tablets directly to inspect live crop health on-site.

```text
[ Agronomist Field Tablet ]
           │
           │ Wi-Fi AP Link (SSID: Gateway_F94C0B / Static IP: 192.168.23.150)
           v
[ Raspberry Pi 4 Base Station ] ──(SPI)──> [ RAK5146 Concentrator ]
           │                                          ^
           │ Local Docker Microservices               │ LoRa Sub-GHz RF
           v                                          │
[ ChirpStack Server / Grafana UI ] <------------------+ [ Field Sensors ]
```

---

## 6. Systemd Packet Forwarder Service Unit (`/etc/systemd/system/packet-forwarder.service`)

```ini
[Unit]
Description=SX1302 LoRaWAN Packet Forwarder Daemon
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/sx1302_hal/packet_forwarder
ExecStartPre=/opt/sx1302_hal/packet_forwarder/reset_lgw.sh start 17
ExecStart=/opt/sx1302_hal/packet_forwarder/lora_pkt_fwd -c /opt/sx1302_hal/packet_forwarder/global_conf.json
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---
*Maintained under project `lorawan-setup/technology-docs`.*
