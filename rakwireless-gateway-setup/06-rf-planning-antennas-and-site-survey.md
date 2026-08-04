# RF Planning, Antenna Physics & Site Survey Engineering Handbook

This handbook provides advanced radio frequency (RF) engineering principles, antenna selection criteria, coaxial cable attenuation loss calculations, Fresnel zone clearance formulas, co-location interference mitigation guidelines, and field site survey procedures for RAKwireless gateway installations.

---

## 1. RF Link Budget & Propagation Fundamentals

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

#### FSPL Example Calculation (923 MHz at 5 km Range):
$$FSPL = 20 \log_{10}(5) + 20 \log_{10}(923) + 32.44$$
$$FSPL = 13.98 + 59.30 + 32.44 = 105.72 \text{ dB}$$

### 1.3 Receiver Sensitivity Formula
The minimum receivable RF signal level ($S$) for an SX1302/SX1303 baseband receiver is calculated as:

$$S = -174 + 10 \log_{10}(BW) + NF + SNR_{\text{min}}$$

For LoRa SF12 at 125 kHz Bandwidth ($BW = 125000 \text{ Hz}$), with Noise Figure $NF = 6 \text{ dB}$ and $SNR_{\text{min}} = -20 \text{ dB}$:
$$S = -174 + 50.96 + 6 + (-20) = -137.04 \text{ dBm}$$

---

## 2. Antenna Selection: Gain, Polarization & VSWR

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
| **1.0 : 1** | $\infty$ | 0 % | Ideal Theoretical Perfection |
| **1.2 : 1** | 20.8 dB | 0.8 % | Excellent Commercial Grade |
| **1.5 : 1** | 14.0 dB | 4.0 % | Standard Acceptable Limit |
| **2.0 : 1** | 9.5 dB | 11.3 % | Marginal performance; excessive reflections |
| **> 3.0 : 1**| < 6.0 dB | > 25.0 % | DANGER: High reflected power; risks thermal damage |

---

## 3. Coaxial Cable Attenuation Loss (915 MHz / 868 MHz)

Coaxial cable quality directly impacts gateway performance. High cable losses waste transmit power and degrade receiver sensitivity.

| Coaxial Cable Model | Outer Diameter | Attenuation per 10m @ 900 MHz | Attenuation per 30m @ 900 MHz | Flexibility & Usage |
| :--- | :--- | :--- | :--- | :--- |
| **RG-174** | 2.8 mm | 9.8 dB loss | 29.4 dB loss | Internal pigtails only (< 30 cm) |
| **RG-58** | 5.0 mm | 4.5 dB loss | 13.5 dB loss | Short bench test jumpers (< 2 m) |
| **LMR-200** | 4.9 mm | 2.9 dB loss | 8.7 dB loss | Short mast runs (< 5 m) |
| **LMR-400** | 10.3 mm | **1.28 dB loss** | **3.84 dB loss** | **Primary Outdoor Tower Cable Standard** |
| **LMR-600** | 15.0 mm | **0.86 dB loss** | **2.58 dB loss** | Long commercial tower runs (> 20 m) |

---

## 4. Fresnel Zone Clearance Calculations

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

*Rule of Thumb*: At least 80% of $R_1$ ($11.38 \text{ meters}$) must remain completely unobstructed by trees or structures.

---

## 5. Cellular Co-Location & Cavity Filter Integration

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

## 6. Pre-Deployment Field Site Survey Checklist

Before permanently securing an outdoor RAK gateway, complete the site assessment protocol:

```text
[ ] 1. Elevation Audit: Measure height above ground level (AGL). Ensure antenna exceeds surrounding rooflines by >= 3 meters.
[ ] 2. Power Resilience: Verify clean AC/PoE source. Test backup battery runtime (UPS) if grid power fluctuates.
[ ] 3. Backhaul Integrity: Run 100 ping tests to LNS server over Ethernet/Cellular. Confirm 0% packet loss and latency < 150ms.
[ ] 4. VSWR Test: Attach portable Anritsu Site Master or NanoVNA to coaxial cable feed. Verify VSWR <= 1.5 at target frequency.
[ ] 5. Spectrum Scan: Run a 10-minute spectrum sweep using an SDR (RTL-SDR / HackRF) to verify zero high-power noise spikes in the 915-928 MHz or 868 MHz band.
[ ] 6. Grounding Audit: Confirm ground wire impedance to earth rod is < 5 Ohms.
```
