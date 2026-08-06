# Raspberry Pi 4 + RAK5146 Hardware Assembly

Use this guide to check the parts, assemble a **Raspberry Pi 4 Model B**, **RAK5146 SPI concentrator**, and **WisLink Pi HAT**, and verify power and cooling before software setup. Confirm every connector and pin label against the exact hardware revision in hand.

---

## 1. Hardware stack

```text
+-----------------------------------------------------------------------------------+
|                        GATEWAY HARDWARE STACK EXPLOSION                           |
|                                                                                   |
|  [Sub-GHz Fiberglass Omni Antenna (900-930 MHz)]   [Active GPS Antenna]           |
|                         \                                 /                       |
|                          +---------------+---------------+                        |
|                                          |                                        |
|                          [2x u.FL to SMA Female Pigtails]                         |
|                                          |                                        |
|                                          v                                        |
|                    [RAK5146 SPI Concentrator Card (SX1303)]                       |
|                                          | mini-PCIe Socket                       |
|                                          v                                        |
|                    [WisLink Pi HAT Adapter Board]                                 |
|                                          | 40-Pin GPIO Header                     |
|                                          v                                        |
|                    [Raspberry Pi 4 Model B Single Board Computer]                 |
|                                          | USB-C Port                             |
|                                          v                                        |
|                    [Official 5.1V / 3.0A (15.3W) Power Adapter]                   |
+-----------------------------------------------------------------------------------+
```

### 1.1 RAK5146 and SX1303
The RAK5146 uses the Semtech SX1303 baseband. The comparison below is background information; purchasing and configuration decisions must follow the exact RAK5146 datasheet and regional variant.

| Specification / Feature | Semtech SX1301 (Legacy) | Semtech SX1302 (Modern) | Semtech SX1303 (Advanced ASIC - RAK5146) |
| :--- | :--- | :--- | :--- |
| **RAK Modules** | RAK2245, RAK7243 | RAK2287, RAK7268 V2 | **RAK5146 SPI (Specified in Checklist)** |
| **Power Consumption** | High (~4.5 W, runs hot) | Low (~1.5 W peak) | **Low (~1.6 W peak)** |
| **Processing Engine** | Dual FPGA Emulation | Dedicated Hardware ASIC | **Dedicated Hardware ASIC** |
| **Spreading Factors** | SF7 - SF12 (Fixed) | SF5 - SF12 (Dynamic) | **SF5 - SF12 (Dynamic on all 8 channels)** |
| **Fine Timestamping** | Not Supported | Coarse Timestamping | **Nanosecond Fine Timestamping (TDoA Geolocation)** |
| **Max Throughput** | ~500 packets/sec | ~1500 packets/sec | **~1500 packets/sec** |

---

## 2. Raspberry Pi GPIO and adapter signals

The RAK5146 mini-PCIe card connects to the WisLink Pi HAT, which breaks out the native SPI and UART signals to the Raspberry Pi 4 40-pin GPIO header:

```text
Raspberry Pi 4 Model B (40-Pin Header)        WisLink Pi HAT / RAK5146 mPCIe Socket
+--------------------------------------+      +--------------------------------------+
| 3.3V DC Power            (Pin 1, 17) |----->| Pin 2, 24, 39, 41, 52: 3.3V Power    |
| 5V DC Power              (Pin 2, 4)  |----->| Onboard LDO Voltage Regulator        |
| System Ground            (Pins 6,9..)|----->| Pin 4, 9, 15, 18, 21.. System Ground |
| SPI0 MISO (GPIO 9)       (Pin 21)    |----->| Pin 47: HOST_MISO (Master In)        |
| SPI0 MOSI (GPIO 10)      (Pin 19)    |----->| Pin 49: HOST_MOSI (Master Out)       |
| SPI0 SCLK (GPIO 11)      (Pin 23)    |----->| Pin 45: HOST_SCK  (SPI Clock)        |
| SPI0 CE0  (GPIO 8)       (Pin 24)    |----->| Pin 51: HOST_CSN  (Chip Select 0)    |
| GPIO 17 (Reset Control)  (Pin 11)    |----->| Pin 22: PERST# / SX1303_RESET        |
| GPS 1PPS (Internal Sync) (N/A)       |<-----| Pin 19: RESERVED / PPS (ZOE-M8Q)     |
| UART TX (GPIO 14)        (Pin 8)     |----->| Pin 31: PETn0 / PI_UART_TX (GPS RX)  |
| UART RX (GPIO 15)        (Pin 10)    |<-----| Pin 33: PETp0 / PI_UART_RX (GPS TX)  |
+--------------------------------------+      +--------------------------------------+
```

### 2.1 Diagnostic LEDs
- **`D1` (Red):** `TX_ON` (Flashes during LoRa packet transmission).
- **`D2` (Blue):** `RX_ON` (Flashes upon receiving valid LoRa packets).
- **`D3` (Green):** `CONFIG / POWER_OK` (Remains solid green when 3.3V power is stable).

> [!CAUTION]
> The RAK5146 uses the mini-PCIe form factor for mounting, but the SPI model is not a general PC PCIe or mSATA card. Use the approved RAK adapter and follow its pin mapping.

---

## 3. Assemble the gateway

Perform all physical assembly on an anti-static workbench with power disconnected.

### Step 1: Chassis Standoff Installation
Thread four 11mm M2.5 brass standoffs into the Raspberry Pi 4 mounting holes. Secure from underneath using M2.5 screws.

### Step 2: RAK5146 Concentrator Seating
Insert the RAK5146 mini-PCIe card into the mPCIe socket on the WisLink Pi HAT at a 30-degree angle. Press down gently until flat against the PCB standoffs and secure with two M2.0 retention screws.

### Step 3: Micro Coaxial Pigtail Connection (u.FL / IPEX1)
1. Align u.FL pigtail 1 vertically over the connector labeled **LORA** (or **RF0**) on the RAK5146 board. Press straight down until you feel a light click.
2. Align pigtail 2 over the connector labeled **GPS** and press down until it clicks.

### Step 4: Mount WisLink Pi HAT on Raspberry Pi 4
Align the 40-pin connector on the HAT with the 40-pin GPIO header on the Raspberry Pi 4. Press down evenly until fully seated and no gold pins are visible. Fasten with M2.5 screws.

### Step 5: Connect the antennas
1. Connect the correct-band LoRa antenna to the SMA bulkhead wired to the **LORA** port.
2. Connect the GNSS antenna only when GNSS will be used.
3. Check that the pigtails are not crossed.

> [!WARNING]
> Do not run transmit tests without a matched LoRa antenna or approved RF load. An open or wrong-band RF connection can damage the transmit stage. GNSS is receive-only and is not required for the first uplink test.

---

## 4. Power and cooling

### 4.1 Power Supply Requirements
- **Hardware Stack**: Raspberry Pi 4 Model B (2GB/4GB/8GB) + RAK5146 SPI Concentrator + WisLink Pi HAT + Active GPS + MicroSD Card.
- **Power Adapter**: Official **5.1V / 3.0A (15.3W) USB-C Power Supply**.
- **Voltage drop**: Thin cables and unsuitable phone chargers can cause undervoltage. Use the Raspberry Pi supply or another verified 5.1 V / 3 A supply and confirm `vcgencmd get_throttled` returns `0x0`.

### 4.2 Thermal Dissipation
- The SX1303 concentrator chip and Raspberry Pi 4 CPU generate heat during high packet traffic.
- Ensure the thermal conductive pad is sandwiched between the SX1303 ASIC and the aluminum heatsink of the WisLink Pi HAT.
- If mounting inside an outdoor IP67 enclosure, ensure internal aluminum mounting brackets contact the outer metal enclosure shell to dissipate heat.

## 5. Verify the completed assembly

Before applying power, confirm the RAK5146 is level and secured, the Pi HAT is fully seated, the LoRa pigtail reaches the connector labelled for LoRa RF, and the matched antenna is attached. After Gateway OS is installed, check power and temperature while Concentratord is running and during a safe transmit test.

A healthy assembly initializes without repeated SPI or reset errors and shows no undervoltage or thermal throttling. Repeated radio resets, a non-zero throttling history, an unexpectedly hot enclosure, or no Gateway EUI should be investigated as a hardware, power, seating, or cooling problem before changing software.

Continue with [02-install-chirpstack-gateway-os.md](02-install-chirpstack-gateway-os.md).
