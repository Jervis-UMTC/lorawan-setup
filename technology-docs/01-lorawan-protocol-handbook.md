# Volume 01: LoRa & LoRaWAN Protocol Engineering Handbook

## Executive Summary & Educational Purpose

This handbook serves as an exhaustive, textbook-level reference guide to **LoRa** (Physical Layer Modulation) and **LoRaWAN** (Media Access Control Protocol Layer). Designed for wireless systems engineers, embedded hardware developers, and agronomists constructing long-range Internet of Things (IoT) field networks, this text covers radio frequency (RF) signal physics, Chirp Spread Spectrum (CSS) mathematics, link budget equations, frame header structures, cryptographic key exchanges, device classes, MAC command sets, and agricultural radio propagation modeling.

---

## 1. OSI Layer Architecture: LoRa vs. LoRaWAN

In wireless networking, confusing **LoRa** with **LoRaWAN** is a common mistake. They operate at distinct layers of the Open Systems Interconnection (OSI) model:

```text
+-----------------------------------------------------------------------------------+
|                        OSI Layer 7: Application Layer                             |
|  • Soil Moisture Telemetry, Disease Prediction Algorithms, Grafana Scoreboards    |
+-----------------------------------------------------------------------------------+
                                         │
                                         v
+-----------------------------------------------------------------------------------+
|                        OSI Layer 2: Data Link / MAC Layer                         |
|                                    (LoRaWAN)                                      |
|  • Standardized by the LoRa Alliance®                                             |
|  • MAC Header Processing, Frame Counters, Adaptive Data Rate (ADR)                |
|  • OTAA / ABP Activation, AES-128 Encryption (NwkSKey, AppSKey)                   |
|  • Receive Window Scheduling (Class A / Class B / Class C)                        |
+-----------------------------------------------------------------------------------+
                                         │
                                         v
+-----------------------------------------------------------------------------------+
|                         OSI Layer 1: Physical RF Layer                            |
|                                     (LoRa)                                        |
|  • Proprietary Modulation Technique Developed by Semtech                          |
|  • Chirp Spread Spectrum (CSS) Frequency Shifts                                   |
|  • Sub-GHz ISM Bands (868 MHz / 915 MHz / 923 MHz)                               |
|  • Spreading Factors (SF7 to SF12), Bandwidth (125/250/500 kHz), Coding Rate     |
+-----------------------------------------------------------------------------------+
                                         │
                                         v
+-----------------------------------------------------------------------------------+
|                         RF Hardware Transceiver Layer                             |
|  • Semtech SX1261, SX1262, SX1276 (End-Nodes) / SX1302, SX1303 (Gateways)          |
+-----------------------------------------------------------------------------------+
```

---

## 2. Chirp Spread Spectrum (CSS) Modulation & Physics

LoRa is built on **Chirp Spread Spectrum (CSS)** modulation, a technique historically reserved for military radar due to its high immunity to multipath fading, Doppler shifts, and narrow-band in-band interference.

### 2.1 CSS Frequency Dynamics

In CSS, data bits are not transmitted on fixed discrete frequencies (like FSK). Instead, digital symbols are encoded using linear frequency-modulated pulses called **chirps**, whose frequency ramps continuously over time across a dedicated channel Bandwidth ($BW$).

```text
 Frequency (f)
  ^
  |      Upchirp (Preamble)               Data Encoded Symbol Chirp
f_max |     /     /     /               |       /|
  |    /     /     /                |      / |  (Frequency Wrap)
  |   /     /     /                 |     /  |
  |  /     /     /                  |    /   |
f_min | /     /     /                   |   /    |
  +-----------------------------------------------------------------> Time (t)
```

1. **Raw Upchirp**: A continuous linear sweep from minimum frequency ($f_{min}$) to maximum frequency ($f_{max}$). Used in the **Preamble** for packet synchronization.
2. **Raw Downchirp**: A continuous sweep from $f_{max}$ down to $f_{min}$. Used in the frame header to signal the end of the preamble.
3. **Symbol Chirp**: A shifted upchirp that starts at an intermediate frequency, ramps to $f_{max}$, wraps instantly around to $f_{min}$, and continues ramping up to its starting frequency. The starting frequency offset encodes the symbol value.

### 2.2 Mathematical Derivations of CSS Parameters

#### 1. Spreading Factor ($SF$)
The Spreading Factor defines how many raw chips represent a single information symbol:
$$SF \in \{7, 8, 9, 10, 11, 12\}$$
The number of chips per symbol ($N_{chips}$) is given by:
$$N_{chips} = 2^{SF}$$
* For $SF=7$, $N_{chips} = 2^7 = 128\text{ chips/symbol}$.
* For $SF=12$, $N_{chips} = 2^{12} = 4,096\text{ chips/symbol}$.

#### 2. Symbol Duration ($T_s$)
The duration of a single LoRa symbol ($T_s$) depends strictly on $SF$ and the channel Bandwidth ($BW$):
$$T_s = \frac{2^{SF}}{BW}$$

#### 3. Nominal Bit Rate ($R_b$)
Taking into account Forward Error Correction (FEC) defined by Coding Rate ($CR \in \{1, 2, 3, 4\}$, representing code rates $\frac{4}{5}, \frac{4}{6}, \frac{4}{7}, \frac{4}{8}$):
$$R_b = SF \cdot \left( \frac{BW}{2^{SF}} \right) \cdot \left( \frac{4}{4 + CR} \right)$$

### 2.3 Comprehensive Spreading Factor Performance Matrix

Assuming standard $BW = 125\text{ kHz}$ and $CR = \frac{4}{5}$:

| Spreading Factor | Chips / Symbol | Symbol Duration ($T_s$) | Bit Rate ($R_b$) | Receiver Sensitivity Threshold | Time-on-Air (20 Byte Payload) | Energy Consumption Factor |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SF7** | 128 | $1.024\text{ ms}$ | $5.47\text{ kbps}$ | $-123.0\text{ dBm}$ | $61.7\text{ ms}$ | $1.0\times$ (Base) |
| **SF8** | 256 | $2.048\text{ ms}$ | $3.12\text{ kbps}$ | $-126.0\text{ dBm}$ | $113.2\text{ ms}$ | $1.8\times$ |
| **SF9** | 512 | $4.096\text{ ms}$ | $1.76\text{ kbps}$ | $-129.0\text{ dBm}$ | $205.8\text{ ms}$ | $3.3\times$ |
| **SF10** | 1024 | $8.192\text{ ms}$ | $0.98\text{ kbps}$ | $-132.0\text{ dBm}$ | $370.7\text{ ms}$ | $6.0\times$ |
| **SF11** | 2048 | $16.384\text{ ms}$ | $0.54\text{ kbps}$ | $-134.5\text{ dBm}$ | $741.4\text{ ms}$ | $12.0\times$ |
| **SF12** | 4096 | $32.768\text{ ms}$ | $0.29\text{ kbps}$ | $-137.0\text{ dBm}$ | $1,318.9\text{ ms}$ | $21.3\times$ |

---

## 3. Link Budget & Radio Propagation Mathematics

The **Link Budget** quantifies the total attenuation a radio signal can endure between transmitter and receiver while maintaining reliable decoding.

### 3.1 Total Link Budget Equation

$$\text{Link Budget (dB)} = P_{tx} + G_{tx} - S_{rx} + G_{rx}$$

Where:
* $P_{tx}$ = Transmitter Output Power ($\text{dBm}$) (e.g. $+14\text{ dBm}$ for EU868, $+20\text{ dBm}$ for US915).
* $G_{tx}$ = Transmitter Antenna Gain ($\text{dBi}$) (e.g. $+2\text{ dBi}$).
* $S_{rx}$ = Receiver Sensitivity ($\text{dBm}$) (e.g. $-137\text{ dBm}$ at SF12).
* $G_{rx}$ = Receiver Gateway Antenna Gain ($\text{dBi}$) (e.g. $+6\text{ dBi}$).

$$\text{Maximum Link Budget (SF12)} = 20 + 2 - (-137) + 6 = 165\text{ dB}$$

A 165 dB link budget allows LoRaWAN signals to penetrate deep underground basements, dense foliage, and travel over 15 kilometers in open terrain.

### 3.2 Path Loss Models in Agricultural Fields

#### 1. Friis Free Space Path Loss (FSPL) Model
Used for unobstructed line-of-sight propagation above flat fields:
$$\text{FSPL (dB)} = 20 \log_{10}(d) + 20 \log_{10}(f) + 32.44$$
* $d$ = Distance between transmitter and receiver ($\text{km}$).
* $f$ = Operating frequency ($\text{MHz}$).

#### 2. Modified Hata-Okumura Model for Rural Vegetation
In dense agricultural crops (e.g. corn, sugarcane, orchards), path loss increases due to foliage scattering ($L_{foliage}$):
$$L_{total} = \text{FSPL} + A \cdot f^{0.2} \cdot d^{0.4} \cdot \theta_{canopy}$$
* $A$ = Specific attenuation coefficient of green leaf water content ($\approx 0.2\text{ dB/m}$).
* $\theta_{canopy}$ = Total path length inside crop canopy ($\text{meters}$).

---

## 4. LoRaWAN Bit-Level Frame Format & Headers

Every LoRaWAN packet transmitted over the air follows a strict binary frame structure:

```text
+-----------------------------------------------------------------------------------+
|                                 LoRa Physical Frame                               |
|  [ Preamble (8-12 Symbols) ] [ Physical Header (PHDR) ] [ PHDR_CRC ] [ PHYPayload ]|
+-----------------------------------------------------------------------------------+
                                                                            │
                                                                            v
+-----------------------------------------------------------------------------------+
|                                 PHYPayload Breakdown                              |
|  [ MHDR (1 Byte) ] [ MACPayload (7 to 230 Bytes) ] [ MIC (4 Bytes - AES-CMAC) ]   |
+-----------------------------------------------------------------------------------+
                                   │
                                   v
+-----------------------------------------------------------------------------------+
|                                MACPayload Breakdown                               |
|  [ FHDR (7-22 Bytes) ] [ FPort (1 Byte) ] [ FRMPayload (0-222 Bytes Encrypted) ]  |
+-----------------------------------------------------------------------------------+
     │
     v
[ DevAddr (4 B) ] [ FCtrl (1 B) ] [ FCnt (2 B) ] [ FOpts (0-15 B MAC Commands) ]
```

### 4.1 MAC Header (MHDR) Field Definition (1 Byte)

```text
 Bits:  7   6   5  |  4   3   2  |  1   0
       [ MType    ] [ RFU       ] [ Major ]
```

* **MType (Bits 7..5)**: Defines Message Type:
  * `000`: `JoinRequest`
  * `001`: `JoinAccept`
  * `010`: `UnconfirmedDataUp` (Sensor uplink without ACK request)
  * `011`: `UnconfirmedDataDown`
  * `100`: `ConfirmedDataUp` (Sensor uplink requesting ACK)
  * `101`: `ConfirmedDataDown`
  * `110`: `RejoinRequest`
* **Major (Bits 1..0)**: Protocol Version (`00` = LoRaWAN R1).

---

## 5. Security & Cryptographic Key Management

LoRaWAN employs end-to-end 128-bit AES encryption to ensure data confidentiality, mutual authentication, and replay protection.

```text
                                [ Root Keys (Hardcoded in Hardware) ]
                                          • AppKey (128-bit)
                                          • NwkKey (128-bit)
                                                   │
                                        (OTAA Join Protocol)
                                                   │
                                                   v
                                [ Dynamic Session Keys Generated ]
                                                   │
                ┌──────────────────────────────────┴──────────────────────────────────┐
                ▼                                                                     ▼
   [ Network Session Key (NwkSKey) ]                                    [ Application Session Key (AppSKey) ]
   • Used by Network Server (ChirpStack)                                • Used by Application Layer
   • Encrypts & Verifies MAC Commands                                   • Encrypts FRMPayload User Bytes
   • Calculates 4-Byte MIC (AES-128-CMAC)                               • Prevents Network Server from
   • Verifies Frame Counters (FCnt)                                       reading private sensor payload
```

### 5.1 Message Integrity Code (MIC) Calculation

To prevent packet tampering, every LoRaWAN frame ends with a 4-byte `MIC` calculated over `MHDR | MACPayload` using AES-CMAC with `NwkSKey`:

$$B_0 = 0x49 \ |\  0x00^4 \ |\ \text{Dir} \ |\ \text{DevAddr} \ |\ \text{FCnt} \ |\ 0x00 \ |\ \text{len(msg)}$$
$$\text{cmac} = \text{AES128\_CMAC}(NwkSKey, B_0 \ |\ \text{msg})$$
$$\text{MIC} = \text{cmac}[0..3]$$

---

## 6. Detailed MAC Command Reference

LoRaWAN allows the Network Server to manage node radio parameters dynamically over the air using **MAC Commands** transmitted in `FOpts` or `FPort=0`.

| CID | Command Name | Transmitted By | Short Description |
| :---: | :--- | :---: | :--- |
| `0x02` | `LinkCheckReq` | End-Node | Node tests connectivity to network. |
| `0x02` | `LinkCheckAns` | Network Server | Returns demodulation margin (dB) and gateway count. |
| `0x03` | `LinkADRReq` | Network Server | Requests node to change Spreading Factor, TX Power, and Enabled Channels. |
| `0x03` | `LinkADRAns` | End-Node | Confirms whether Channel Mask, Data Rate, and Power were accepted. |
| `0x04` | `DutyCycleReq` | Network Server | Limits maximum aggregate duty cycle of node. |
| `0x05` | `RxParamSetupReq` | Network Server | Sets RX2 window frequency and Data Rate. |
| `0x06` | `DevStatusReq` | Network Server | Requests node's battery status and demodulation SNR. |
| `0x07` | `NewChannelReq` | Network Server | Creates or modifies a new radio channel frequency. |

---

## 7. LoRaWAN Class A, B, and C Operational Timings

```text
CLASS A TIMING DIAGRAM:
TX Uplink       RX1 Window                       RX2 Window
   |-------|    |---|                            |---|
   |       |~~~~~~~~|                            |---|
   |-------| 1.0s   |---|                         2.0s
           (Receive Delay 1)                      (Receive Delay 2)

CLASS C TIMING DIAGRAM:
TX Uplink       Continuous RX Window Open (99% Duty Cycle)
   |-------|=========================================================================>
   |       | Open RX Window Continuous Listening for Downlinks
   |-------|
```

---

## 8. Summary Checklist for Farm Deployment Engineers

1. ✅ **Channel Plan Alignment**: Verify nodes match regional frequencies (AU915 Sub-band 2 / US915 / EU868).
2. ✅ **Activation**: Use **OTAA** for dynamic session key generation.
3. ✅ **Antenna Elevation**: Position Gateway antenna at least 8 to 10 meters above foliage to clear the 1st Fresnel zone.
4. ✅ **Enable ADR**: Activate Adaptive Data Rate in ChirpStack to auto-optimize SF7-SF12 transmission power.

---
*Maintained under project `lorawan-setup/technology-docs`.*
