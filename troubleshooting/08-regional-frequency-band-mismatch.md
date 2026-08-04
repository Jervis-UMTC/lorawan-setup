# Troubleshooting Manual 08: Regional Frequency Band Mismatch

## 1. Executive Problem Summary

* **Symptom**: `gr-lora-sdr` or an SDR spectrum analyzer clearly detects strong raw LoRa RF chirps over the air, but the Gateway packet forwarder discards frames, or ChirpStack drops incoming packets with "frequency not supported" or "unknown region".
* **Impact**: End-nodes fail to onboard or join; no telemetry is decoded; gateway logs show unhandled frequency channels.
* **Primary Root Cause**: **Mismatch in Regional Frequency Band Parameters or Sub-Band Channel Masks** across the end-node, Gateway Concentrator (`global_conf.json`), and ChirpStack Network Server configuration (`chirpstack.toml`).

---

## 2. Root Cause Analysis & Frequency Specifications

LoRaWAN defines strict regional radio parameter specifications (e.g. **US915**, **EU868**, **AU915**, **AS923-1/2/3/4**, **IN865**):

```text
========================================================================================
                          REGIONAL FREQUENCY MAPPING SPECS
========================================================================================
 Region    Frequency Range     Uplink Channels       Default Bandwidth & SF
 ──────    ───────────────     ───────────────       ──────────────────────
 EU868     863 – 870 MHz       8 Multi-Channels      125 kHz (SF7 to SF12)
 US915     902 – 928 MHz       64 Channels + 8 500k  125 kHz / 500 kHz (SF7 to SF10)
 AS923-1   920 – 923.4 MHz     8 Multi-Channels      125 kHz (SF7 to SF12)
 AU915     915 – 928 MHz       64 Channels + 8 500k  125 kHz / 500 kHz (SF7 to SF10)
========================================================================================
```

Common configuration errors:
1. **US915 / AU915 Sub-Band Mismatch**: US915 defines 64 channels divided into 8 Sub-Bands (8 channels each). If the Milesight UG65 gateway listens on **Sub-Band 2 (Channels 8–15, 903.9–905.3 MHz)**, but the Dragino node transmits on **Sub-Band 1 (Channels 0–7, 902.3–903.7 MHz)**, the gateway will never hear 7 out of 8 packets!
2. **AS923 Frequency Plan Mismatches**: AS923 has 4 sub-variants (AS923-1, AS923-2, AS923-3, AS923-4) with different channel frequency offsets.

---

## 3. Diagnostic & Inspection Commands

### Step 1: Detect Carrier Frequency in gr-lora-sdr / GRC
Inspect raw RF center frequency of node uplinks using an SDR receiver:
~~~bash
python3 ~/lorawan-lab/gr-lora-sdr/examples/rx_forwarder.py --freq 915000000 --sf 7 --bw 125000
~~~
Observe whether the FFT peak occurs at `915.2 MHz`, `903.9 MHz`, `868.1 MHz`, or `923.2 MHz`.

### Step 2: Inspect ChirpStack Region Logs
~~~bash
docker logs chirpstack | grep -i -E "region|frequency|channel"
~~~
*Expected Error*: `no channel found for frequency: 902300000` or `invalid frequency for band AS923`.

### Step 3: Inspect Gateway Packet Forwarder `global_conf.json`
Log into gateway (`192.168.23.150`) and inspect radio center frequencies (`radio_0` and `radio_1`):
~~~bash
cat /etc/packet_forwarder/global_conf.json | grep -A 5 "radio_0"
~~~

---

## 4. Step-by-Step Resolution Blueprint

### Action 1: Align US915 / AU915 Sub-Band Channel Mask on End-Node
For US915 or AU915 networks, force the end-node to restrict transmissions to **Sub-Band 2** (Channels 8–15):

1. Connect to Dragino sensor via serial AT commands:
   ~~~text
   AT+CHE=2
   ~~~
   *(CHE=2 configures Sub-Band 2: 903.9 MHz to 905.3 MHz)*.
2. Verify node channel mask query:
   ~~~text
   AT+CHS=?
   ~~~

### Action 2: Align Gateway Concentrator `global_conf.json` (Milesight / RAK5146)
Configure gateway radio frequencies in `/etc/packet_forwarder/global_conf.json`:
~~~json
"radio_0": {
    "enable": true,
    "type": "SX1250",
    "freq": 904300000,
    "rssi_offset": -166.0
},
"radio_1": {
    "enable": true,
    "type": "SX1250",
    "freq": 905100000,
    "rssi_offset": -166.0
}
~~~

### Action 3: Configure Regional Band in `chirpstack.toml`
Ensure the Network Server matches the exact regional frequency profile in `chirpstack.toml`:

~~~toml
[network]
enabled_regions=["us915_2"]  # Configures US915 Sub-Band 2

[regions.us915_2]
description="US915 Sub-Band 2"
region="us915"
sub_band=2
~~~

For AS923 (Philippines / SE Asia):
~~~toml
[network]
enabled_regions=["as923"]

[regions.as923]
description="AS923-1"
region="as923"
~~~

---

## 5. Verification & Acceptance Criteria

1. **Gateway Frequency Matching**: Gateway logs show `PUSH_DATA` with 100% matched channel indices.
2. **ChirpStack Log Acceptance**: `docker logs chirpstack` shows clean frame processing without `no channel found` errors.
3. **End-to-End Uplinks**: Telemetry uplinks appear in PostgreSQL `device_up` with correct `frequency` values recorded.
