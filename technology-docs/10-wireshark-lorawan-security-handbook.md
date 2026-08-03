# Wireshark LoRaWAN Security & Protocol Analysis Handbook

## 1. Executive Summary & Overview

`Wireshark` is the industry-standard network protocol analyzer used worldwide for deep-packet inspection, traffic capture, protocol debugging, and security auditing. When paired with its native **LoRaWAN Protocol Dissector**, Wireshark provides comprehensive visibility into over-the-air frame structures, Message Integrity Codes (MIC), Frame Counters (FCnt), MAC Command options, and payload encryption.

Within this repository's security testing architecture, Wireshark operates as the primary **Protocol Analysis and Security Evidence Engine**. While `gr-lora-sdr` handles RF PHY signal reception and demodulation, Wireshark dissects the resulting byte streams and packet captures (PCAP). This enables test leads and security analysts to:

- Inspect raw `PHYPayload` frames captured from gateways (Semtech UDP port 1700) or MQTT backhaul.
- Validate cryptographic integrity by checking Message Integrity Codes (MIC) computed with `NwkSKey`.
- Audit frame counter progression (`FCnt`) to identify replay attacks, counter stalls, or unauthorized resets.
- Decrypt encrypted application payloads (`FRMPayload`) using synthetic lab `AppSKey` session keys.
- Generate immutable `.pcap` evidence bundles for compliance reporting and security audits.

---

## 2. LoRaWAN Frame Dissection Architecture

### 2.1 Packet Representation Hierarchy

Wireshark dissects LoRaWAN traffic across three distinct encapsulation layers:

~~~text
========================================================================================
                          LORA / LORAWAN ENCAPSULATION LAYERS
========================================================================================
 1. Transport Layer (UDP Port 1700 / MQTT Topic)
    ├── Semtech UDP Packet Forwarder Protocol (PULL_DATA, PUSH_DATA, PULL_RESP)
    └── JSON Payload (contain Rxpk / Txpk metadata: RSSI, SNR, Freq, Data, Time)

 2. LoRaWAN Physical Payload Layer (PHYPayload)
    ├── MAC Header (MHDR)                  --> MType (3 bits), Major Version (2 bits)
    ├── MAC Payload (MACPayload) OR Join-Request / Join-Accept
    │   ├── Frame Header (FHDR)            --> DevAddr (4 bytes), FCtrl (1 byte), FCnt (2/4 bytes), FOpts
    │   ├── Frame Port (FPort)             --> 0 (MAC Commands), 1..223 (Application Data)
    │   └── Frame Payload (FRMPayload)     --> Encrypted with AppSKey (Data) or NwkSKey (FPort 0)
    └── Message Integrity Code (MIC)       --> 4-byte AES-128-CMAC signature

 3. Wireshark Dissector & Decryption Engine
    ├── Protocol Dissector (`lorawan`)    --> Parses MHDR, FHDR, FPort, MAC Commands, & MIC
    ├── Cryptographic Engine               --> Evaluates CMAC using NwkSKey & decrypts AES-CTR using AppSKey
    └── Decrypted Payload (`lorawan.frmpayload_decrypted`)
========================================================================================
~~~

### 2.2 Field Structure Specification

| Header Component | Field Name | Width | Purpose & Security Relevance |
|---|---|---|---|
| **MHDR** | `MType` | 3 bits | Message Type: `000` (Join-Req), `001` (Join-Accept), `010` (Unconfirmed Up), `011` (Unconfirmed Down), `100` (Confirmed Up), `101` (Confirmed Down). |
| **MHDR** | `Major` | 2 bits | LoRaWAN Major version (always `00` for LoRaWAN R1). |
| **FHDR** | `DevAddr` | 4 bytes | 32-bit short network address assigned during Join/ABP. |
| **FHDR** | `FCtrl` | 1 byte | Frame Control flags: `ADR`, `ADRACKReq`, `ACK`, `FPending`, `FOptsLen`. |
| **FHDR** | `FCnt` | 2 / 4 bytes | Frame Counter. Crucial for replay prevention; increments per uplink/downlink. |
| **FHDR** | `FOpts` | 0–15 bytes | Transport piggybacked MAC commands (`LinkADRReq`, `DevStatusReq`, etc.). |
| **FPort** | `FPort` | 1 byte | Application port identifier. `0` indicates FOpts MAC payload; `1..223` indicates application payload. |
| **FRMPayload** | `FRMPayload` | Variable | Application payload encrypted using AES-128-CTR with `AppSKey` (or `NwkSKey` if FPort=0). |
| **MIC** | `MIC` | 4 bytes | Cryptographic 32-bit Message Integrity Code computed via AES-128-CMAC over `B0 \| PHYPayload[0..N-5]`. |

---

## 3. Installation & User Permissions Setup

### 3.1 Linux Installation (Ubuntu / Debian)

Install Wireshark and TShark (command-line utility):

~~~bash
sudo apt update
sudo apt install -y wireshark tshark tcpdump
~~~

### 3.2 Non-Root Capture Configuration
To allow packet capturing without running Wireshark as `root`:

~~~bash
# 1. Reconfigure wireshark-common to allow non-superusers
sudo dpkg-reconfigure wireshark-common

# 2. Add your current user to the wireshark group
sudo usermod -aG wireshark $USER

# 3. Apply group changes (or log out and log back in)
newgrp wireshark
~~~

Verify non-root capture permission:
~~~bash
dumpcap -D
~~~

---

## 4. Packet Capture Methodologies

### 4.1 Capturing Gateway UDP Port 1700 Traffic
The Milesight UG65 gateway forwards raw LoRaWAN frames over Semtech UDP Protocol on port `1700`. Capture this backhaul traffic using `tcpdump`:

~~~bash
# Capture UDP 1700 traffic on all interfaces
sudo tcpdump -i any -s 0 -w ~/lorawan-lab/captures/pcap/gateway-udp1700-$(date -u +%Y%m%dT%H%M%SZ).pcap udp port 1700
~~~

### 4.2 Converting Demodulated `gr-lora-sdr` Bytes to PCAP
When capturing frames via `gr-lora-sdr`, use Python with `scapy` to package raw hex bytes into a `.pcap` file for Wireshark inspection:

~~~python
#!/usr/bin/env python3
# Save as ~/lorawan-lab/scripts/hex_to_pcap.py
import sys
from scapy.all import IP, UDP, Raw, wrpcap

def convert_hex_to_pcap(hex_str, output_pcap):
    payload = bytes.fromhex(hex_str)
    # Wrap in dummy UDP packet matching Semtech packet forwarder structure
    pkt = IP(src="192.168.23.150", dst="192.168.23.137") / UDP(sport=1700, dport=1700) / Raw(load=payload)
    wrpcap(output_pcap, pkt)
    print(f"[+] Saved PCAP: {output_pcap}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 hex_to_pcap.py <hex_payload> <output.pcap>")
        sys.exit(1)
    convert_hex_to_pcap(sys.argv[1], sys.argv[2])
~~~

---

## 5. Master Display Filter Reference

Use these standardized Wireshark display filters during protocol analysis and security audits:

| Filter String | Target Description | Example Use Case |
|---|---|---|
| `lorawan` | Filter all LoRaWAN traffic | General protocol inspection |
| `lorawan.mtype == 0` | Filter Join-Request frames | OTAA activation analysis |
| `lorawan.mtype == 1` | Filter Join-Accept frames | OTAA response validation |
| `lorawan.mtype == 2` | Filter Unconfirmed Uplink | Routine telemetry monitoring |
| `lorawan.mtype == 4` | Filter Confirmed Uplink | Reliable transport auditing |
| `lorawan.devaddr == 01:02:03:04` | Filter by synthetic DevAddr | Target device isolation |
| `lorawan.fcnt` | Track Frame Counter | Replay attack audit |
| `lorawan.mic` | Inspect 4-byte CMAC | Integrity checking |
| `lorawan.fport == 1` | Filter by Application Port | Sensor data filtering |
| `lorawan.frmpayload_decrypted` | Filter decrypted payload | Telemetry validation |
| `lorawan.mac.cmd` | Filter MAC commands | Network management audit |

### Advanced Boolean Filters
Combine filters for targeted threat hunting:

- **Isolate Uplinks for a Specific Device**:
  ~~~text
  lorawan.devaddr == 01:02:03:04 && (lorawan.mtype == 2 || lorawan.mtype == 4)
  ~~~
- **Detect Potential Frame Counter Stalls / Replays**:
  ~~~text
  lorawan.devaddr == 01:02:03:04 && lorawan.fcnt <= 10
  ~~~

---

## 6. Cryptographic Decryption Engine Setup

### 6.1 Step-by-Step Wireshark Decryption Setup

Wireshark includes a built-in LoRaWAN dissector capable of decrypting AES-128-CTR application payloads when provided with synthetic lab session keys.

1. Launch Wireshark and open your `.pcap` capture file:
   ~~~bash
   wireshark ~/lorawan-lab/captures/pcap/gateway-udp1700.pcap
   ~~~
2. Navigate to **Edit → Preferences → Protocols → LoRaWAN**.
3. In the LoRaWAN preferences dialog, locate the session key fields:
   - **NwkSKey (Network Session Key)**: Enter the 32-character hex key (e.g., `2B7E151628AED2A6ABF7158809CF4F3C`).
   - **AppSKey (Application Session Key)**: Enter the 32-character hex key (e.g., `2B7E151628AED2A6ABF7158809CF4F3C`).
4. Click **OK** to apply.
5. Apply display filter `lorawan.frmpayload_decrypted` to view decrypted ASCII/Hex bytes directly inside the packet tree.

---

## 7. Security Audit & Vulnerability Testing Workflows

### 7.1 Replay Attack Audit Workflow

**Objective**: Verify whether the private network server detects and rejects replayed uplink frames.

1. **Capture Frame**: Capture a valid unconfirmed uplink using `tcpdump` or `gr-lora-sdr`.
2. **Inspect Counter**: Open PCAP in Wireshark and record `lorawan.fcnt` (e.g., `FCnt = 42`).
3. **Re-transmit Frame**: Use `gr-lora-sdr` transmit script to re-send the exact byte payload over the lab RF path.
4. **Inspect Wireshark PCAP**:
   - Filter `lorawan.devaddr == 01:02:03:04`.
   - Observe two identical packets with `FCnt = 42`.
5. **Correlate Server Logs**:
   - Open ChirpStack server logs (`docker logs chirpstack`).
   - Verify server output: `frame counter rolled back` or `FCnt too low`.
   - Confirm ChirpStack drops the duplicate frame without emitting an MQTT uplink event.

### 7.2 Message Integrity Code (MIC) Tampering Workflow

**Objective**: Verify server rejection of frames with corrupted integrity signatures.

1. **Obtain Frame**: Take a valid 23-byte uplink payload:
   `4004030201000100018593a2b1` (Last 4 bytes `8593a2b1` = MIC).
2. **Mutate MIC**: Change the last byte to `FF`:
   `4004030201000100018593a2FF`.
3. **Transmit & Capture**: Transmit via `gr-lora-sdr` and capture via Wireshark.
4. **Inspect Wireshark**:
   - Wireshark flags MIC verification status as invalid.
5. **Correlate Server Logs**:
   - ChirpStack logs: `validate mic error: invalid mic`.

---

## 8. Command-Line Automated Inspection with TShark

`tshark` allows automated CI/CD security verification scripts to parse `.pcap` files without a GUI.

### 8.1 Extracting Frame Counters and DevAddrs
~~~bash
tshark -r ~/lorawan-lab/captures/pcap/gateway-udp1700.pcap \
    -Y "lorawan" \
    -T fields \
    -e frame.time \
    -e lorawan.devaddr \
    -e lorawan.fcnt \
    -e lorawan.mtype
~~~

### 8.2 Automated Replay Detection Verification Script
Save as `~/lorawan-lab/scripts/audit_replay.sh`:

~~~bash
#!/bin/bash
PCAP_FILE="$1"
if [ -z "$PCAP_FILE" ]; then
    echo "Usage: ./audit_replay.sh <pcap_file>"
    exit 1
fi

echo "[+] Auditing PCAP for duplicate Frame Counters..."
DUPLICATES=$(tshark -r "$PCAP_FILE" -Y "lorawan.fcnt" -T fields -e lorawan.fcnt | sort | uniq -d)

if [ -n "$DUPLICATES" ]; then
    echo "[!] WARNING: Duplicate Frame Counters detected:"
    echo "$DUPLICATES"
else
    echo "[+] SUCCESS: No duplicate Frame Counters found."
fi
~~~

Make executable:
~~~bash
chmod +x ~/lorawan-lab/scripts/audit_replay.sh
~~~

---

## 9. Summary & Reference Matrix

Wireshark is an indispensable component of the LoRaWAN security engineering stack. Combined with `gr-lora-sdr`, it provides verifiable evidence for protocol validation, replay auditing, and integrity testing.

- **Wireshark LoRaWAN Display Filter Reference**: [wireshark.org/docs/dfref/l/lorawan.html](https://www.wireshark.org/docs/dfref/l/lorawan.html)
- **gr-lora-sdr Handbook**: [09: gr-lora-sdr RF PHY Handbook](./09-gr-lora-sdr-rf-phy-handbook.md)
- **Security Testing Runbook**: [08: LoRaWAN Security Testing Runbook](../docs/08-lorawan-security-testing-runbook.md)
