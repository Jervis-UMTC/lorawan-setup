# Troubleshooting Manual 02: Frame Counter Discrepancy & FCnt Reset Rejection

## 1. Executive Problem Summary

* **Symptom**: Sensor uplinks are visibly detected over the air by `gr-lora-sdr` and recorded by the Gateway, but ChirpStack silently drops them. The ChirpStack Web UI shows no new events.
* **Impact**: Field nodes stop updating telemetry completely after battery swaps, power outages, or device reboots.
* **Primary Root Cause**: A **Frame Counter (`FCnt`) discrepancy**. The end-device rebooted and reset its internal counter to `0`, but ChirpStack expects `FCnt > N` (where $N$ was the last recorded counter before reboot).

---

## 2. Root Cause Analysis & Security Mechanics

LoRaWAN mandates strict Frame Counter tracking to protect against **Replay Attacks**:
1. Every uplink increments `FCntUp` by 1.
2. If an attacker records an uplink at `FCnt = 105` and retransmits it later, ChirpStack rejects it because $105 \le 105$.
3. When a device loses power (battery replacement or solar drop), non-volatile memory (NVM) failure can cause its internal counter to reset to `0`.
4. When the device sends its next frame (`FCnt = 0`), ChirpStack compares `0` against its stored session state (`FCnt = 520`) and discards the packet as a duplicate/replayed attack.

---

## 3. Diagnostic & Inspection Commands

### Step 1: Check ChirpStack Live Logs for FCnt Rejection
Inspect ChirpStack network server logs for Frame Counter errors:
~~~bash
docker logs chirpstack | grep -i "frame counter"
~~~
*Expected Error Line*: `frame counter rolled back, expected: > 520, got: 0` or `invalid FCnt`.

### Step 2: Extract FCnt Difference using Wireshark / TShark
Capture incoming frame headers over UDP port 1700 to view the physical device `FCnt`:
~~~bash
tshark -i eth0 -f "udp port 1700" -Y "lorawan" -T fields -e lorawan.devaddr -e lorawan.fcnt
~~~
Compare the output against the `FCnt` recorded in the ChirpStack device dashboard.

### Step 3: Query Session State in Redis
Query ChirpStack's Redis cache engine to inspect the current stored `FCnt`:
~~~bash
docker exec -it redis redis-cli KEYS "device:session:*"
~~~

---

## 4. Step-by-Step Resolution Blueprint

### Action 1: Re-align Device Session via ChirpStack UI (Quick Field Fix)
1. Log into ChirpStack Web Dashboard (`http://<SERVER-IP>:8080`).
2. Navigate to **Applications** $\rightarrow$ Select Device $\rightarrow$ **Device Data** / **Activation**.
3. Under the **Activation** tab:
   * View current `Uplink frame-counter`.
   * Click **Reset Frame Counters** or manually set `Uplink frame-counter = 0`.
4. Trigger a manual uplink on the node. Telemetry will resume immediately.

### Action 2: Trigger an OTAA Re-Join (Permanent Architecture Fix)
For production devices, use **Over-The-Air Activation (OTAA)** instead of Activation By Personalization (ABP):
1. Upon power reboot, an OTAA device sends a `Join-Request` frame.
2. ChirpStack accepts the `Join-Request`, generates new session keys (`NwkSKey`, `AppSKey`), and **resets the server-side FCnt to 0 automatically**.
3. Configure the node AT setting (e.g. Dragino):
   ~~~text
   AT+NJM=1
   ~~~
   *(NJM=1 sets Join Mode to OTAA)*.

### Action 3: Enable Non-Volatile Memory (NVM) FCnt Persistence on End-Node
If using ABP activation, ensure the node saves `FCnt` to Flash EEPROM before entering deep sleep:
* On Dragino LSN50v2-S31, verify AT setting:
  ~~~text
  AT+FCNTUP
  ~~~
* In C/C++ firmware, save `FCntUp` to non-volatile flash every 10 uplinks.

### Action 4: Relax Frame Counter Validation (Lab Testing Only)
> [!CAUTION]
> Do NOT use this setting in production deployments as it disables replay attack protection.

For isolated test lab environments, disable strict frame counter checks in `chirpstack.toml`:
~~~toml
[network]
skip_fcnt_validation=true
~~~

---

## 5. Verification & Acceptance Criteria

1. **Telemetry Resumption**: New uplink frames appear instantly in the ChirpStack **Device Data** stream.
2. **Log Verification**: `docker logs chirpstack` shows clean packet handling without `frame counter rolled back` errors.
3. **Database Consistency**: `SELECT f_cnt FROM device_up` increases monotonically after every transmission.
