# Troubleshooting Manual 07: Sensor Battery Drain & High Time-on-Air

## 1. Executive Problem Summary

* **Symptom**: Field sensors (e.g. Dragino LSN50v2-S31) experience rapid battery depletion, dying within 2 to 4 months instead of achieving their rated 3 to 5-year battery life; low battery voltage warnings (`BatV < 2.8V`) appear in telemetry.
* **Impact**: Field maintenance costs escalate due to frequent battery replacements; sensors stop logging telemetry unexpectedly.
* **Primary Root Cause**: End-node locked at **SF12 / Maximum TX Power** due to disabled ADR, excessive **Confirmed Uplink retransmissions**, or failure to enter MCU **Deep Sleep mode** (high baseline current).

---

## 2. Root Cause Analysis & Power Physics

A LoRaWAN sensor's battery capacity ($Q_{battery}$, e.g. 8500 mAh LiMnO2) is consumed across two operational states:

$$\text{Total Energy} = (I_{sleep} \cdot t_{sleep}) + (I_{tx} \cdot t_{tx}) + (I_{rx} \cdot t_{rx})$$

1. **SF12 Time-on-Air Overhead**: At SF12, transmitting a 20-byte payload consumes **1,318 ms** at $120\text{ mA}$ active TX current. At SF7, the same transmission takes **61 ms**. Transmitting at SF12 consumes **21.6 times more battery energy per packet**.
2. **Confirmed Uplink Retry Loops**: If a node uses Confirmed Uplinks (`ACK required`) and the gateway fails to send an ACK, the node retransmits the frame up to **8 times at maximum power**, rapidly draining the battery.
3. **Deep Sleep Failure**: If an external sensor probe (e.g., RS485 soil NPK probe) leaves its power regulator ON during sleep, the node draws $15\text{ mA}$ continuously instead of $3\text{ \mu A}$ deep sleep current. The battery dies in 23 days!

---

## 3. Diagnostic & Inspection Commands

### Step 1: Query Battery Voltage & SF History in PostgreSQL
~~~sql
SELECT 
    dev_eui,
    created_at,
    (object->>'BatV')::numeric AS battery_volts,
    (dr->'lora'->>'spreadingFactor')::int AS sf
FROM device_up
WHERE dev_eui = decode('a84041380189b98f', 'hex')
ORDER BY created_at DESC
LIMIT 50;
~~~
*Diagnostic Threshold*: If `battery_volts` drops by $> 0.1\text{V}$ per week, or SF remains stuck at `12`, intervene immediately.

### Step 2: Measure Physical Sleep Current via Digital Multimeter / Profiler
Connect a multimeter in series with the Dragino battery connector:
* **Active TX Current**: $90\text{ mA}$ to $130\text{ mA}$ (Normal during 100ms chirp).
* **Deep Sleep Current Target**: **$2\text{ \mu A}$ to $5\text{ \mu A}$**.
* *Fault State*: If multimeter reads $> 1\text{ mA}$ continuously during sleep, the MCU or sensor probe is failing to sleep.

---

## 4. Step-by-Step Resolution Blueprint

### Action 1: Enable ADR to Shift Node to SF7 / Low TX Power
Enable Adaptive Data Rate to allow ChirpStack to optimize Spreading Factor and reduce power output:
1. Verify AT command on Dragino node:
   ~~~text
   AT+ADR=1
   ~~~
2. Once ADR evaluates signal quality, node shifts from SF12 ($1,318\text{ ms}$) $\rightarrow$ SF7 ($61\text{ ms}$), extending battery life by **$+400\%$**.

### Action 2: Convert Confirmed Uplinks to Unconfirmed Uplinks
Avoid battery-draining ACK retry loops:
1. Change uplink type from Confirmed to Unconfirmed via AT command:
   ~~~text
   AT+CFM=0
   ~~~
   *(CFM=0 sets Unconfirmed mode; node transmits once and immediately sleeps without waiting for ACKs)*.

### Action 3: Increase Uplink Sampling Interval
Adjust transmission frequency to match agronomic requirements:
* Change uplink interval from 2 minutes to **15 or 30 minutes**:
  ~~~text
  AT+TDC=900000
  ~~~
  *(TDC=900000 sets Transmission Data Cycle to 900,000 milliseconds = 15 minutes)*.

### Action 4: Power-Gated External Sensor Interfaces
Ensure external RS485 Modbus probes or SHT31 temperature sensors are powered from the node's **switched 3.3V VEXT output pin** rather than unswitched battery power:
* In firmware, toggle `VEXT_ON` before reading sensor, then set `VEXT_OFF` before entering `board_sleep()`.

---

## 5. Verification & Acceptance Criteria

1. **Sleep Current Verification**: Measured node sleep current drops to **$< 5\text{ \mu A}$**.
2. **Spreading Factor**: Node operates at **SF7 / SF8** under ChirpStack ADR control.
3. **Battery Voltage Curve**: `BatV` stabilizes and exhibits $< 0.05\text{V}$ drop over 30 days.
