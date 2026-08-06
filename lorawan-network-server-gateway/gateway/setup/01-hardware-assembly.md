# Gateway 1. Assemble the Raspberry Pi 4B and RAK5146 SPI

Run this assembly procedure at an anti-static workbench with all power sources disconnected. This guide details the hardware assembly, RF safety protocols, GPIO pin mapping, power budgeting, and physical diagnostic checks for constructing an industrial-grade LoRaWAN gateway using a Raspberry Pi 4B host and a RAK5146 SPI Concentrator module.

---

## 1. System Architecture & Overview

The gateway architecture separates real-time radio signal processing from high-level network protocol management:

- **Host Single Board Computer (SBC)**: Raspberry Pi 4B (4GB or 8GB recommended). Manages system services, container execution (ChirpStack Concentratord, MQTT Forwarder, Docker runtime), system logging, and network backhaul (Ethernet/Cellular/Wi-Fi).
- **LoRaWAN Concentrator**: RAK5146 SPI module equipped with Semtech SX1303 baseband processor and dual SX1250 RF transceivers. Capable of simultaneous multi-channel reception (8 channels + 1 high-speed FSK + 1 LoRa service channel) and fine-timestamping for Time-Difference-of-Arrival (TDoA) geolocation.
- **Interface Adapter**: RAK2287/RAK5146 Pi HAT. Adapts the mini-PCIe mechanical form factor of the RAK5146 to the 40-pin GPIO header of the Raspberry Pi 4B, routing SPI lines, power rails, and hardware reset GPIOs.

> [!WARNING]
> **Electrical Interface vs. Physical Socket:**
> The RAK5146 module uses a physical mPCIe form factor connector, but it **is not a PCIe or mSATA device**. The signals routed through the mPCIe connector pins are strictly SPI, power, and low-level control GPIOs. Plugging a RAK5146 SPI module into a laptop or standard PC motherboard mPCIe slot will fail and may cause permanent hardware damage.

---

## 2. Required Parts & Pre-assembly Inspection

| Component | Technical Specification / Requirement | Operational Justification |
|---|---|---|
| **Host Board** | Raspberry Pi 4B (Model B, 2GB/4GB/8GB) | Provides sufficient RAM and processing overhead for containerized gateway middleware. |
| **Concentrator Module** | RAK5146 **SPI** Variant (SX1303) | Must match host interface (SPI). Do not substitute USB or mSATA variants. |
| **Interface HAT** | RAK2287 / RAK5146 Pi HAT (Rev 1.x or 2.x) | Routes SPI bus, 3.3V/5V power rails, and GPIO17 concentrator reset line. |
| **LoRa Antenna** | 50-ohm Omni-directional (e.g., 3 dBi - 6 dBi) | Must be tuned precisely to regional band (e.g., 902-928 MHz US915 / AU915 or 863-870 MHz EU868). |
| **RF Pigtail** | u.FL (IPEX MHF1) to SMA-Female (RG178/RG316) | Connects fragile concentrator u.FL port to rugged enclosure bulkhead. |
| **GNSS Antenna** | Active 3.3V LNA Patch / Magnetic Puck (Optional) | Provides GPS/GLONASS precision timing (1PPS) for Class B/C devices and TDoA. |
| **Power Supply** | Official RPi 5.1V / 3.0A USB-C Supply (15.3W) | Prevents under-voltage dips during simultaneous RPi CPU burst and RF transmission. |
| **Storage Media** | Industrial High-Endurance microSD Card (pSLC/MLC) | Prevents flash memory wear and corruption from continuous system logging and Docker storage drivers. |
| **Cooling & Enclosure** | Aluminum Standoffs, Active Fan / Passive Heatsinks | Prevents thermal throttling under continuous 100% duty cycle downlinks in warm ambient climates. |

---

## 3. Detailed Hardware Assembly Workflow

### Step 1: Verify Hardware Variants & RF Channel Plans

Before mounting any component, inspect physical labels on the hardware:

```text
Host SBC:            Raspberry Pi 4B (Revision 1.2 or higher)
Concentrator Label:  RAK5146-SPI-915 (or RAK5146-SPI-868)
Interface Protocol:  SPI (Verify silkscreen shows "SPI" not "USB")
Regional Frequency:  US915 / AU915 / AS923 / EU868 (Must match local radio regulations)
Antenna Frequency:   Tuned matching band (e.g., 902–928 MHz for US915/AU915)
```

> [!IMPORTANT]
> **Do Not Infer Frequency Variants:**
> Never guess the RF channel plan from software or generic labels like "AS923" or "US915". Inspect the hardware silkscreen and barcode model number on the RAK5146 shielding can. Utilizing an incorrect frequency module creates severe impedance mismatch and violates telecommunications regulations.

---

### Step 2: Install RAK5146 Concentrator onto the Pi HAT

1. **ESD Grounding**: Wear an anti-static wrist strap or touch a grounded metallic enclosure before touching the RAK5146 board.
2. **Socket Insertion**: Insert the RAK5146 mPCIe edge connector into the mPCIe socket on the Pi HAT at a **30-degree shallow angle**.
3. **Seating**: Press down gently on the top edge of the module until it rests flat against the standoff mounting holes.
4. **Fastening**: Secure the module using two M2 x 4mm retaining screws. Tighten until snug; do not over-torque to avoid flexing the mPCIe adapter PCB.
5. **Level Inspection**: Verify visually that the module is seated fully and sits parallel to the HAT PCB surface.

---

### Step 3: Connect RF Pigtail Cables (LoRa & GNSS)

> [!CAUTION]
> **Fragile u.FL Connectors:**
> Micro u.FL (IPEX) connectors are rated for only ~30 to 50 insertion/extraction cycles. Misalignment during pressing will permanently deform the center pin receptacle.

1. **Connector Alignment**: Place the u.FL connector vertically above the **LoRa** silkscreen connector on the RAK5146 module.
2. **Engagement**: Press straight down with your thumb or flat end of a plastic spudger until you hear and feel a sharp tactile "click". **Do not twist or rotate** the connector while applying downward pressure.
3. **Cable Routing**: Route the thin RG178/RG316 pigtail cable smoothly around standoffs. Ensure it is not pinched under PCBs or strained by the outer enclosure lid.
4. **GNSS Pigtail (Optional)**: If installing a GNSS antenna, attach a second u.FL pigtail exclusively to the connector labelled **GNSS** / **GPS**. 

---

### Step 4: Mount the Pi HAT onto the Raspberry Pi 4B Header

#### GPIO Pin Mapping Matrix

The RAK Pi HAT routes power, SPI communication, and control GPIOs directly through the Raspberry Pi 40-pin header:

| RPi 40-Pin Header | Signal Name | Function | Destination on RAK5146 |
|---|---|---|---|
| **Pin 2 & 4** | `5V` | Main System Power Rail | HAT Voltage Regulators |
| **Pin 1 & 17** | `3.3V` | Low-Voltage Power Rail | Concentrator Logic / Reset Pullup |
| **Pin 6, 9, 14, 20, 25, 30, 34, 39** | `GND` | Ground Reference | Common System Ground |
| **Pin 19 (GPIO 10)** | `SPI0_MOSI` | Master Out Slave In | SX1303 Data Input |
| **Pin 21 (GPIO 9)** | `SPI0_MISO` | Master In Slave Out | SX1303 Data Output |
| **Pin 23 (GPIO 11)** | `SPI0_SCLK` | Serial Clock | SX1303 Bus Clock |
| **Pin 24 (GPIO 8)** | `SPI0_CE0` | Chip Enable 0 | SX1303 SPI Slave Select |
| **Pin 11 (GPIO 17)** | `GPIO 17` | Hardware Reset | SX1303 Concentrator Reset |

#### Mounting Procedure:

1. **Standoff Installation**: Thread four 11mm M2.5 brass standoffs into the corner mounting holes of the Raspberry Pi 4B.
2. **Header Alignment**: Carefully align the 40-pin female connector of the Pi HAT over all 40 pins of the Raspberry Pi header. Ensure no pins are offset or bent.
3. **Press Fitting**: Apply even downward pressure on both edges of the female header until the HAT rests flush on the brass standoffs.
4. **Mechanical Lock**: Fasten the HAT to the standoffs using four M2.5 x 6mm screws.
5. **Short Circuit Inspection**: Check visually that metal components (such as USB connector shells or Ethernet jack shields on the Pi) do not make contact with any solder pads on the underside of the Pi HAT.

---

### Step 5: RF Safety & Antenna Attachment

> [!CAUTION]
> **PA Burnout Hazard:**
> Never apply power to the Raspberry Pi or launch ChirpStack Concentratord / packet forwarder without a matched 50-ohm LoRa antenna attached to the SMA bulkhead port. Operating the RF transmitter into an open circuit (missing antenna) reflects 100% of RF power back into the SX1250 Power Amplifier (PA), resulting in thermal destruction of the RF front-end within milliseconds.

1. **Screw Termination**: Screw the high-gain omni antenna onto the SMA female bulkhead connector until finger-tight.
2. **Torque**: Hand-tighten securely; if using an SMA wrench, torque to no more than 0.5–0.8 Nm (4.5–7 in-lbs).
3. **Positioning**: For indoor bench testing, keep the antenna oriented vertically and separated by at least 2 meters from LoRaWAN end-devices to prevent receiver saturation (RSSI > -40 dBm).

---

## 4. Power & Thermal Diagnostic Protocols

### Step 6: Verify Power Supply Stability & Thermal Health (`vcgencmd`)

Under-voltage is the leading root cause of corrupted SPI transfers, mysterious concentrator resets, and microSD card corruption.

Once booted into Gateway OS via SSH, run the following diagnostic commands to check host power stability and core temperature:

```bash
# Verify vcgencmd utility availability
command -v vcgencmd || echo "vcgencmd not installed on standard OS"

# Execute hardware diagnostic checks
vcgencmd get_throttled
vcgencmd measure_temp
```

#### Interpreting `vcgencmd get_throttled` Bitmask

The hexadecimal response string (e.g., `0x50005` or `0x0`) maps to hardware flags:

| Bit Flag | Hexadecimal Value | Condition Meaning | Operational Impact |
|---|---|---|---|
| **Bit 0** | `0x00001` | Under-voltage detected **currently** | **CRITICAL:** Power supply voltage is below 4.63V. SPI communication will fail. |
| **Bit 1** | `0x00002` | ARM frequency capped **currently** | CPU speed reduced to protect power rail. Packet handling delayed. |
| **Bit 2** | `0x00004` | Currently throttled | CPU speed reduced due to high temperature or severe under-voltage. |
| **Bit 3** | `0x00008` | Soft temperature limit active | Temperature exceeded 60°C. Throttling threshold approaching. |
| **Bit 16** | `0x10000` | Under-voltage **has occurred** since boot | Transient voltage dip occurred during high CPU/RF load. Cable or power supply is marginal. |
| **Bit 17** | `0x20000` | ARM frequency capping **has occurred** | Frequency throttling triggered previously since power-on. |
| **Bit 18** | `0x40000` | Throttling **has occurred** | Throttling event triggered previously since power-on. |
| **Bit 19** | `0x80000` | Soft temperature limit **has occurred** | Thermal spike recorded previously since power-on. |

> [!TIP]
> **Healthy System Benchmark:**
> A properly powered and cooled gateway MUST report `get_throttled=0x0` during active packet transmission and receive tests. If bit 0 or 16 is set (`0x1` or `0x10000`), immediately replace the power supply and USB-C cable with an official 5.1V / 3.0A unit before altering software configuration.

---

## 5. Gateway Hardware Asset Inventory Ledger

Record the verified hardware parameters in the asset registry before placing the gateway into production service. These values are mandatory for selecting the correct ChirpStack Concentratord configuration profile and calculating Equivalent Isotropically Radiated Power (EIRP) compliance:

```text
======================================================================
                  GATEWAY HARDWARE ASSET LEDGER
======================================================================
Gateway Asset ID:          __________________________________________
Host SBC Serial Number:    __________________________________________
Raspberry Pi Model/RAM:    RPi 4B - [ ] 2GB  [ ] 4GB  [ ] 8GB
Pi HAT Model & Revision:   RAK2287/RAK5146 HAT Rev: _________________
Concentrator Part Number:  RAK5146-SPI-______________________________
Concentrator Serial Number:__________________________________________
Semtech Transceiver Chip:  SX1303 Baseband + Dual SX1250 RF Front-End
Interface Protocol:        SPI (SPI0 CE0)
Concentrator Reset Line:   GPIO 17 (Pin 11)
Frequency Band / Plan:     [ ] US915  [ ] AU915  [ ] EU868  [ ] AS923
Antenna Model & Gain:      _____________________ dBi (50-ohm SMA)
RF Pigtail Insertion Loss: _____________________ dB @ Frequency
Power Supply Model / Spec: Official RPi 5.1V / 3.0A (15.3W USB-C)
Enclosure / Cooling Type:  [ ] Indoor IP30   [ ] Outdoor IP67 (PoE)
Inspection Date & Tech:    ____________________ / ____________________
======================================================================
```

### Verification Checklist Before Proceeding to Gateway OS Installation

- [x] RAK5146 SPI module is seated in mPCIe slot and fastened with dual M2 screws.
- [x] u.FL RF pigtail connected securely to LoRa port with clean tactile snap.
- [x] 40-pin GPIO header seated squarely on Raspberry Pi with 11mm brass standoffs installed.
- [x] LoRa omni-directional antenna attached to SMA connector BEFORE applying power.
- [x] Official 5.1V/3.0A power supply connected; `vcgencmd get_throttled` returns `0x0`.
- [x] Hardware asset ledger completed with verified serial numbers and GPIO pin mappings.

