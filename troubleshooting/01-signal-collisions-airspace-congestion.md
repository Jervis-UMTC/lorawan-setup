# Troubleshooting Manual 01: Signal Collisions & Airspace Congestion

## 1. Executive Problem Summary

* **Symptom**: Telemetry packet loss spikes during peak farm operating hours; ChirpStack event logs show missing frame sequence numbers; devices experience frequent uplink retransmissions.
* **Impact**: Critical microclimate data is lost; battery consumption increases due to retransmissions; network capacity degrades as node density grows.
* **Primary Root Cause**: Radio frequency collisions occurring when multiple end-nodes transmit simultaneously on the same frequency channel using the same Spreading Factor (SF).

---

## 2. Root Cause Analysis & Physics

LoRaWAN uses an **ALOHA-based random access channel model**. When two nodes transmit on the same channel frequency (e.g. 915.2 MHz) at the same time:
1. **Same Spreading Factor (Non-Orthogonal Collision)**: If both nodes use SF7, the radio chirps overlap directly. Unless one signal is at least $6\text{ dB}$ stronger (the Capture Effect), both packets are corrupted and lost.
2. **High Time-on-Air (ToA)**: Nodes locked at SF12 take **1,318 ms** to transmit 20 bytes, compared to **61 ms** at SF7. A single SF12 node occupies the channel 21.6 times longer than an SF7 node, multiplying collision probability.
3. **Synchronized Transmissions**: Nodes configured with fixed timer loops (e.g., exactly every 15:00 minutes) wake up at the exact same second, causing synchronized packet collisions.

---

## 3. Diagnostic & Inspection Commands

### Step 1: Detect Radio Collisions in ChirpStack Logs
Inspect ChirpStack Gateway Bridge logs for CRC errors and dropped frames:
~~~bash
docker logs chirpstack-gateway-bridge | grep -E "crc_error|dropped|collision"
~~~

### Step 2: Inspect Time-on-Air & SF Distribution via SQL
Execute a PostgreSQL query against the ChirpStack database to analyze the Spreading Factor distribution across active devices:
~~~sql
SELECT 
    (dr->'lora'->>'spreadingFactor')::int AS sf,
    COUNT(*) AS total_uplinks,
    AVG((metadata->>'rssi')::numeric) AS avg_rssi,
    AVG((metadata->>'snr')::numeric) AS avg_snr
FROM device_up
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY sf
ORDER BY sf;
~~~
*Diagnostic Threshold*: If $> 30\%$ of uplinks are at SF11 or SF12, the network is at severe risk of signal collisions.

### Step 3: Observe Channel Spectrum via gr-lora-sdr / Wireshark
Capture raw RF traffic in Wireshark or GRC to observe overlapping chirps:
~~~bash
tshark -i eth0 -f "udp port 1700" -Y "lorawan" -T fields -e frame.time -e lorawan.devaddr -e lorawan.fcnt
~~~

---

## 4. Step-by-Step Resolution Blueprint

### Action 1: Enable & Aggressively Tune Adaptive Data Rate (ADR)
Ensure ADR is enabled on both the Network Server and end-nodes.

1. **Verify ChirpStack ADR Configuration**:
   In `chirpstack.toml`, verify that the ADR algorithm is enabled:
   ~~~toml
   [network]
   adr_plugins=["default"]
   ~~~

2. **Verify Node ADR Flag**:
   Ensure end-nodes (e.g. Dragino LSN50v2-S31) transmit with `ADR = 1`. Check AT status:
   ~~~text
   AT+ADR=1
   ~~~

### Action 2: Add Transmission Jitter (Randomized Offset)
Modify the firmware uplink scheduling code to add $\pm 15$ to $30$ seconds of random jitter to uplink timers:
~~~c
// Example C code for node uplink scheduler
uint32_t base_interval_sec = 900; // 15 minutes
int32_t jitter_sec = (rand() % 60) - 30; // Random offset between -30s and +30s
uint32_t next_tx_delay = base_interval_sec + jitter_sec;
~~~

### Action 3: Compress Telemetry Payloads
Replace uncompressed JSON strings with packed 11-byte hex binary payloads.
* **Bad Payload (JSON)**: `{"temp": 24.5, "hum": 68.2}` (35 bytes $\rightarrow$ ToA = 113 ms at SF8)
* **Good Payload (Binary Hex)**: `0x0B8E1802AA` (5 bytes $\rightarrow$ ToA = 41 ms at SF8)

### Action 4: Enable Listen-Before-Talk (LBT) for AS923 / KR920
On Dragino nodes operating in AS923 or KR920 bands, enable hardware carrier sense:
~~~text
AT+LBT=1
~~~

### Action 5: Expand Gateway Multi-Channel Capacity
Ensure the gateway (e.g. Milesight UG65 / RAK5146) is configured for 8 multi-channels across sub-bands rather than single-channel operation. Verify `global_conf.json`:
~~~json
"chan_multiSF_0": { "enable": true, "radio": 0, "if": -400000 },
"chan_multiSF_1": { "enable": true, "radio": 0, "if": -200000 },
"chan_multiSF_2": { "enable": true, "radio": 0, "if": 0 },
"chan_multiSF_3": { "enable": true, "radio": 0, "if": 200000 }
~~~

---

## 5. Verification & Acceptance Criteria

1. **Time-on-Air Reduction**: Average node ToA drops below **100 ms** (SF7/SF8 majority).
2. **Packet Success Rate**: Telemetry packet loss drops below **1%** in PostgreSQL queries.
3. **Collision Verification**: Zero CRC corruption spikes observed in `docker logs chirpstack-gateway-bridge`.
