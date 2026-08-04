# Troubleshooting Manual 04: Downlink Latency & Actuator Timeout on Class A Nodes

## 1. Executive Problem Summary

* **Symptom**: Emergency downlink control commands (e.g. `CLOSE_VALVE`, `STOP_PUMP`, `ACTUATE_RELAY`) issued from Node-RED or ChirpStack sit queued indefinitely; actuator fails to respond in real time during field emergencies.
* **Impact**: Crop damage or flooding occurs because water valves or actuators do not close in time when pipe bursts or chemical spills are detected.
* **Primary Root Cause**: **Architectural Misalignment between Device Class and Actuator Requirements**. Attempting to send real-time downlinks to a **Class A** end-node which only listens for downlinks immediately after sending an uplink.

---

## 2. Root Cause Analysis & Class Architecture

LoRaWAN defines 3 operating classes with fundamentally different downlink latency characteristics:

```text
========================================================================================
                         DOWNLINK LATENCY BY LORAWAN CLASS
========================================================================================
 Class A:  [Sleep 99.9%] ──► [Uplink] ──► [RX1] ──► [RX2] ──► [Sleep 99.9%]
           Latency: High (Minutes to Hours — depends on next scheduled uplink)

 Class B:  [Sleep] ──► [Ping Slot] ──► [Sleep] ──► [Ping Slot] ──► [Sleep]
           Latency: Low & Predictable (1 to 8 seconds — synchronized by Gateway Beacons)

 Class C:  [Receiver ON 100% of the time]
           Latency: Immediate (< 100 milliseconds — requires continuous power)
========================================================================================
```

If an actuator (e.g. a water valve) is configured as **Class A** and only sends a status uplink once every 4 hours:
1. When a leak sensor detects a burst, ChirpStack queues the `CLOSE_VALVE` downlink.
2. The Class A valve is sleeping and will **NOT open its receiver until its next uplink 4 hours later**.
3. Water floods the field for 4 hours.

---

## 3. Diagnostic & Inspection Commands

### Step 1: Check Queued Downlinks in ChirpStack
Query queued downlinks via ChirpStack gRPC/REST API or inspect the Web UI:
1. Go to **ChirpStack UI** $\rightarrow$ **Applications** $\rightarrow$ Select Device $\rightarrow$ **Enqueue Downlink**.
2. View **Pending Downlinks**. If commands sit with status `Pending` for minutes/hours, the node is operating in Class A.

### Step 2: Query Stored Device Class in PostgreSQL
~~~sql
SELECT dev_eui, name, device_profile_id, is_disabled 
FROM device 
WHERE dev_eui = decode('a84041380189b98f', 'hex');
~~~
Inspect the linked `device_profile` to verify whether `supports_class_b` or `supports_class_c` is enabled.

---

## 4. Step-by-Step Resolution Blueprint

### Action 1: Convert Actuator Node to Class B (Battery-Powered Actuators)
For battery-operated valves that must respond within seconds:

1. **Enable Class B in ChirpStack Device Profile**:
   * Go to **Device Profiles** $\rightarrow$ Select Profile.
   * Enable **Supports Class-B**.
   * Set **Class-B ping-slot periodicity**: `2 seconds` or `4 seconds`.

2. **Enable Class B on End-Node Firmware**:
   * Configure node via serial AT command (e.g. Dragino LSN50v2):
     ~~~text
     AT+CLASS=B
     ~~~
   * Ensure Gateway has GPS time synchronization enabled to broadcast 128-second Beacons.

### Action 2: Convert Actuator Node to Class C (Mains-Powered Actuators)
For actuators connected to grid power, solar arrays, or heavy machinery:

1. **Enable Class C in ChirpStack Device Profile**:
   * Go to **Device Profiles** $\rightarrow$ Select Profile.
   * Enable **Supports Class-C**.

2. **Configure Node to Class C**:
   * Set AT command on end-node:
     ~~~text
     AT+CLASS=C
     ~~~
   * Downlinks sent to this device will execute in **$< 100\text{ ms}$**.

### Action 3: Configure Threshold-Based Instant Uplinks on Sensors
Ensure the **Leak Sensor** (the trigger device) uses threshold alarms to uplink instantly when a burst occurs:
1. Configure Dragino sensor temperature/humidity or interrupt trigger thresholds:
   ~~~text
   AT+TTRG=2,38
   ~~~
2. Upon threshold violation, the sensor bypasses its 15-minute timer and uplinks in $< 1\text{ second}$.

---

## 5. Verification & Acceptance Criteria

1. **Class B Verification**: Downlink latency for `CLOSE_VALVE` drops to **$< 4\text{ seconds}$**.
2. **Class C Verification**: Downlink latency for `CLOSE_VALVE` drops to **$< 200\text{ ms}$**.
3. **Queue Verification**: Pending downlink queue in ChirpStack clears instantly upon command dispatch.
