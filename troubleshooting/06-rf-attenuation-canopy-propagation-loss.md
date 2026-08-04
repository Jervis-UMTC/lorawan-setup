# Troubleshooting Manual 06: RF Attenuation & Canopy Propagation Loss

## 1. Executive Problem Summary

* **Symptom**: Telemetry signal drops significantly as crops grow taller in summer; RSSI falls below $-120\text{ dBm}$; SNR drops to negative values ($-10\text{ dB}$ to $-18\text{ dB}$); packet loss exceeds 20% in dense orchards or sugarcane fields.
* **Impact**: Field coverage shrinks; remote sensors become unreachable during peak crop growth seasons.
* **Primary Root Cause**: **Vegetation Path Loss & Foliage RF Absorption**. Water molecules inside plant leaves absorb Sub-GHz 868/915 MHz RF signals, while dense crop stalks block the **Fresnel Zone**.

---

## 2. Root Cause Analysis & RF Physics

### 1. Foliage Attenuation Equation
Radio signals passing through dense crop canopy suffer exponential power decay according to the Modified Hata-Okumura Vegetation model:
$$L_{total} = \text{FSPL} + A \cdot f^{0.2} \cdot d^{0.4} \cdot \theta_{canopy}$$
Where:
* $A \approx 0.2\text{ dB/m}$ (specific attenuation of green leaf water content).
* $\theta_{canopy}$ = distance traveled inside crop leaves (in meters).
* A 50-meter path through dense corn canopy adds **$10\text{ dB}$ to $15\text{ dB}$ of extra attenuation** beyond free space path loss!

### 2. Fresnel Zone Obstruction
If the lower $60\%$ of the 1st **Fresnel Zone** radius ($R_1$) is blocked by crop stalks or ground terrain, signal cancellation occurs:
$$R_1 = 8.65 \sqrt{\frac{d_{km}}{f_{GHz}}}$$
At $d = 2\text{ km}$ and $f = 0.915\text{ GHz}$, $R_1 = 4.14\text{ meters}$. If the gateway antenna is mounted only 2 meters above ground, the Fresnel zone is completely blocked!

---

## 3. Diagnostic & Inspection Commands

### Step 1: Query RSSI & SNR Trends in PostgreSQL
Execute SQL to track signal strength degradation across crop growth cycles:
~~~sql
SELECT 
    dev_eui,
    DATE_TRUNC('day', created_at) AS day,
    AVG((metadata->>'rssi')::numeric) AS avg_rssi,
    AVG((metadata->>'snr')::numeric) AS avg_snr,
    COUNT(*) AS uplink_count
FROM device_up
WHERE dev_eui = decode('a84041380189b98f', 'hex')
GROUP BY dev_eui, day
ORDER BY day DESC;
~~~
*Diagnostic Threshold*: RSSI $< -122\text{ dBm}$ or SNR $< -12\text{ dB}$ signals impending link failure.

### Step 2: Measure RF Energy via gr-lora-sdr Spectrum Analyzer
Launch `gr-lora-sdr` or GNU Radio Companion (`gnuradio-companion`) with an SDR receiver to observe carrier offset and noise floor:
~~~bash
python3 ~/lorawan-lab/gr-lora-sdr/examples/rx_forwarder.py --freq 915000000 --sf 10 --bw 125000
~~~

---

## 4. Step-by-Step Resolution Blueprint

### Action 1: Elevate Gateway Antenna Above Canopy Height (Primary Fix)
Mount the gateway outdoor antenna (e.g. Milesight UG65 / RAK5146 fiberglass antenna) on a dedicated mast or tower:
* **Minimum Antenna Height**: $\ge 6\text{ meters}$ above the maximum expected mature crop canopy height.
* Elevating an antenna from 2m to 8m clears 100% of the 1st Fresnel Zone, instantly improving RSSI by **$+12\text{ dB}$ to $+18\text{ dB}$**.

### Action 2: Upgrade to High-Gain Fiber-Glass Omni-Directional Antenna
Replace internal stock rubber duck antennas with an outdoor fiberglass antenna:
* **Recommended Gain**: $+6\text{ dBi}$ or $+8\text{ dBi}$ outdoor omni-directional antenna tuned to 868–930 MHz.
* **Cable Loss Reduction**: Use low-loss **LMR-400 coaxial cable** for runs over 3 meters (LMR-400 has only $0.13\text{ dB/m}$ loss at 900 MHz compared to $0.45\text{ dB/m}$ for RG-58).

### Action 3: Adjust Spreading Factor via ADR or Manual Setting
If antenna elevation is constrained:
1. Increase node Spreading Factor from SF7 to **SF10 or SF12** for distant sensors.
2. Receiver sensitivity threshold improves from $-123\text{ dBm}$ (SF7) down to **$-137\text{ dBm}$ (SF12)**, yielding a **$14\text{ dB}$ link budget boost**.
3. Configure via Dragino AT command:
   ~~~text
   AT+SF=12,125000
   ~~~

### Action 4: Correct Antenna Polarization Alignment
Ensure all end-node antennas and gateway antennas are oriented vertically ($90^\circ$ perpendicular to the ground). A polarization mismatch (vertical gateway antenna vs. horizontal node antenna lying flat in mud) causes an instant **$-20\text{ dB}$ signal loss**!

---

## 5. Verification & Acceptance Criteria

1. **RSSI Improvement**: Average node RSSI increases above **$-105\text{ dBm}$**.
2. **SNR Recovery**: Average SNR rises to positive values ($> +3\text{ dB}$).
3. **Zero Canopy Packet Drops**: 24-hour telemetry packet loss drops to **0%**.
