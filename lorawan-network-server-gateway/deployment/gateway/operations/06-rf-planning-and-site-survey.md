# RF Planning, Antennas, and Site Survey

Use this guide to estimate link margin, select an antenna and cable, check Fresnel clearance, identify nearby interference, and document the installation site. Calculations are planning inputs, not guaranteed coverage.

---

## 1. Link budget and propagation

The reliability of a LoRaWAN gateway deployment depends on maintaining a positive **Link Margin**. The link margin determines whether a field node's transmitted signal can overcome path loss and arrive at the gateway receiver above its sensitivity threshold.

### 1.1 Received Power Equation (Friis Transmission Equation)

$$P_{RX} = P_{TX} + G_{TX} - L_{TX} - FSPL + G_{RX} - L_{RX}$$

Where:
- $P_{RX}$: Received Signal Power at Gateway Concentrator (dBm)
- $P_{TX}$: Field Node Transmit Power (typically +14 dBm to +22 dBm)
- $G_{TX}$: Transmitter Antenna Gain (dBi)
- $L_{TX}$: Transmitter Coaxial Cable & Connector Loss (dB)
- $FSPL$: Free Space Path Loss (dB)
- $G_{RX}$: Gateway Antenna Gain (dBi)
- $L_{RX}$: Gateway Coaxial Cable & Connector Loss (dB)

### 1.2 Free Space Path Loss (FSPL) Formula

$$FSPL (dB) = 20 \log_{10}(d) + 20 \log_{10}(f) + 32.44$$

Where:
- $d$: Distance between node and gateway in kilometers ($\text{km}$)
- $f$: RF Operating Frequency in megahertz ($\text{MHz}$)

#### Example: 923 MHz over 5 km in free space
$$FSPL = 20 \log_{10}(5) + 20 \log_{10}(923) + 32.44$$
$$FSPL = 13.98 + 59.30 + 32.44 = 105.72 \text{ dB}$$

### 1.3 Receiver Sensitivity Formula
The minimum receivable RF signal level ($S$) for an SX1302/SX1303 baseband receiver is calculated as:

$$S = -174 + 10 \log_{10}(BW) + NF + SNR_{\text{min}}$$

For LoRa SF12 at 125 kHz Bandwidth ($BW = 125000 \text{ Hz}$), with Noise Figure $NF = 6 \text{ dB}$ and $SNR_{\text{min}} = -20 \text{ dB}$:
$$S = -174 + 50.96 + 6 + (-20) = -137.04 \text{ dBm}$$

---

## 2. Antenna gain, pattern, polarization, and VSWR

```text
                       ANTENNA RADIATION PATTERN COMPARISON

    LOW GAIN (3 dBi) - Spherical Pattern        HIGH GAIN (8 dBi) - Flattened Pancake Pattern
          (Ideal for Hilly Terrain)                  (Ideal for Flat Plains / Long Range)

                 .---.                                      .-------------.
               /       \                                  (                 )
              |    *    |  <-- Gateway                   (        *        )  <-- Gateway
               \       /                                  (                 )
                 '---'                                      '-------------'
```

### 2.1 Antenna Gain (dBi vs dBd)
- $\text{dBi}$: Decibels relative to an theoretical isotropic radiator (radiates equally in all 3D directions).
- $\text{dBd}$: Decibels relative to a half-wave dipole antenna.
- **Conversion Formula**: $dBi = dBd + 2.15$

### 2.2 Gain vs Terrain Matching Matrix
- **3 dBi - 5 dBi Omni Antenna**: Best for hilly, mountainous, or urban environments with high elevation variation. Energy is radiated in a broad spherical beam, capturing signals from both valleys and elevated ground.
- **8 dBi - 12 dBi Omni Antenna**: Best for flat rural plains, agricultural fields, or coastal monitoring. Compresses RF energy into a tight horizontal pancake pattern, maximizing long-range horizon reach.

> [!CAUTION]
> **Over-Gain Warning**: Installing a high-gain (12 dBi) antenna on a high tower in a hilly area creates a "blind spot" directly beneath the tower. Field nodes located close to the base of the tower will fall outside the vertical beam pattern.

### 2.3 Voltage Standing Wave Ratio (VSWR)
VSWR measures how effectively RF power is transferred from the concentrator module into the antenna without reflecting back.

| VSWR Value | Return Loss (dB) | Reflected Power (%) | Operational Status |
| :--- | :--- | :--- | :--- |
| **1.0 : 1** | $\infty$ | 0 % | Ideal reference |
| **1.2 : 1** | 20.8 dB | 0.8 % | Very good |
| **1.5 : 1** | 14.0 dB | 4.0 % | Common acceptance target |
| **2.0 : 1** | 9.5 dB | 11.3 % | Investigate cable, connectors, and antenna |
| **> 3.0 : 1**| < 6.0 dB | > 25.0 % | Stop transmit testing and correct the RF path |

---

## 3. Coaxial-cable loss near 900 MHz

Coaxial cable quality directly impacts gateway performance. High cable losses waste transmit power and degrade receiver sensitivity.

| Coaxial Cable Model | Outer Diameter | Attenuation per 10m @ 900 MHz | Attenuation per 30m @ 900 MHz | Flexibility & Usage |
| :--- | :--- | :--- | :--- | :--- |
| **RG-174** | 2.8 mm | 9.8 dB loss | 29.4 dB loss | Internal pigtails only (< 30 cm) |
| **RG-58** | 5.0 mm | 4.5 dB loss | 13.5 dB loss | Short bench test jumpers (< 2 m) |
| **LMR-200** | 4.9 mm | 2.9 dB loss | 8.7 dB loss | Short mast runs (< 5 m) |
| **LMR-400** | 10.3 mm | **1.28 dB loss** | **3.84 dB loss** | **Primary Outdoor Tower Cable Standard** |
| **LMR-600** | 15.0 mm | **0.86 dB loss** | **2.58 dB loss** | Long commercial tower runs (> 20 m) |

---

## 4. Fresnel-zone clearance

The 1st Fresnel Zone is an elliptical region surrounding the direct line-of-sight path between node and gateway. If obstacles (trees, buildings, ground terrain) intrude into this zone by more than 20%, severe RF diffraction fading occurs.

```text
                                FRESNEL ZONE CLEARANCE

                                     _ . - - - . _
                                 . '               ' .
                               /      Fresnel R1       \
       +-------+              |       (Max Radius)      |              +-------+
       | Node  |==============|============*============|==============|Gateway|
       +-------+              |   Line-of-Sight Path    |              +-------+
                               \                       /
                                 ' .               . '
                                     ' - - - - - '
```

### 4.1 Fresnel Radius Formula at Midpoint

$$R_1 = 8.65 \sqrt{\frac{d_1 \cdot d_2}{f_{\text{GHz}} \cdot (d_1 + d_2)}}$$

Where:
- $R_1$: First Fresnel zone radius in meters ($\text{m}$)
- $d_1, d_2$: Distances from obstacle to node and gateway in kilometers ($\text{km}$)
- $f_{\text{GHz}}$: Frequency in gigahertz (e.g., $0.923 \text{ GHz}$)

#### Calculation Example (10 km Total Distance, Obstacle at 5 km Midpoint):
$$R_1 = 8.65 \sqrt{\frac{5 \cdot 5}{0.923 \cdot (5 + 5)}} = 8.65 \sqrt{\frac{25}{9.23}} = 8.65 \sqrt{2.708} = 8.65 \cdot 1.645 = 14.23 \text{ meters}$$

Planning target: keep most of the first Fresnel zone clear. The exact acceptance margin depends on terrain, reliability target, foliage, and measured field performance.

---

## 5. Nearby transmitters and filtering

When a RAK gateway is installed on a commercial cell tower, nearby **4G/5G LTE transmitters** (especially LTE Band 8 / Band 5 operating in 850-900 MHz) can overload the SX1250 RF front-end transceivers, causing receiver desensitization ("desense") and packet drops.

```text
       +-----------------------------------------------------------------------+
       |                      RF INTERFERENCE MITIGATION                       |
       |                                                                       |
       |  [Omni Antenna] --> [Outdoor Bandpass Cavity Filter] --> [Gateway]    |
       |                            (Pass: 915-928 MHz)                        |
       |                            (Reject: < 900 MHz & > 935 MHz by > 40dB)  |
       +-----------------------------------------------------------------------+
```

- **Solution**: Install an inline **High-Q SAW or Cavity Bandpass Filter** tuned specifically to your regional sub-band (e.g., passband 915-928 MHz for US915/AS923, passband 863-870 MHz for EU868) between the outdoor antenna and the gateway.

---

## 6. Perform the site survey

### Step 1: Describe the radio path

At the proposed gateway location, note antenna height, mounting point, terrain, nearby structures, vegetation, and expected device locations. These observations explain later dead zones and help choose antenna gain and height.

Healthy evidence is a plausible line-of-sight or diffraction path to the service area. Major metal obstructions, changing container stacks, or heavy foliage mean coverage must be proven with repeated field tests rather than a desktop estimate.

### Step 2: Verify power and backhaul

Test the actual power source, UPS runtime when required, and the real Ethernet or 4G path to the MQTT endpoint. Measure normal latency, packet loss, DNS behavior, and a controlled outage/recovery.

The backhaul is healthy when it remains stable during radio activity and the local MQTT queue drains after recovery. Reconnect loops, power warnings, or a queue that never drains must be fixed before permanent mounting.

### Step 3: Measure the antenna system

With suitable RF equipment, measure the complete antenna, connector, pigtail, and cable path in the approved operating band. Compare VSWR and insertion loss with the antenna and cable requirements.

Stop transmit testing when the result indicates a damaged cable, wrong-band antenna, poor connector, water ingress, or excessive reflected power. Correct the RF path before compensating with higher transmit power.

### Step 4: Check interference and installation safety

Survey the approved band for persistent interference and strong nearby transmitters. Have a qualified installer verify grounding, lightning/surge protection, cable entry, weather sealing, mast loading, and local electrical requirements.

### Step 5: Run representative field uplinks

Send repeated uplinks from representative near, far, obstructed, and edge-of-coverage locations. Compare RSSI, SNR, data rate, retries, received-versus-expected messages, and behavior across time and site conditions.

A successful survey demonstrates adequate margin and repeatability for the required reporting interval. A single received packet is not coverage evidence; abnormal loss or unstable link metrics require placement, antenna, filtering, or gateway-count changes followed by another test.
