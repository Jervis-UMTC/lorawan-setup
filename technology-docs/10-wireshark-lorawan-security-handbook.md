# Wireshark LoRaWAN Security & Protocol Analysis Handbook

## 1. Executive Summary & Overview

`Wireshark` is the industry-standard network protocol analyzer used worldwide for deep-packet inspection, traffic capture, protocol debugging, and security auditing. When paired with its native **LoRaWAN Protocol Dissector**, Wireshark provides comprehensive visibility into frame structures, Message Integrity Codes (MIC), Frame Counters (FCnt), MAC Command options, and payload encryption.

Within this repository's security architecture, Wireshark and TShark serve as the primary **Protocol Analysis and Security Evidence Engine**. Capturing Semtech UDP port 1700 packet forwarder traffic between the Milesight UG65 gateway and the ChirpStack network server enables security analysts to:

- Inspect raw `PHYPayload` frames captured live from gateway backhaul traffic.
- Validate cryptographic integrity by verifying Message Integrity Codes (MIC) computed with `NwkSKey`.
- Audit frame counter progression (`FCnt`) to identify replay attacks, counter stalls, or unauthorized resets.
- Decrypt encrypted application payloads (`FRMPayload`) using synthetic lab `AppSKey` session keys.
- Audit resilience against Man-in-the-Middle (MitM) payload modifications and join-request `DevNonce` replays.
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
    ├── Protocol Dissector (`lorawan`)     --> Parses MHDR, FHDR, FPort, MAC Commands, & MIC
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

## 3. Installation & Non-Root Setup

### 3.1 Linux Installation (Ubuntu / Debian)

Install Wireshark and TShark:

~~~bash
sudo apt update
sudo apt install -y wireshark tshark tcpdump
~~~

### 3.2 Non-Root Capture Configuration
To allow packet capturing without running Wireshark as `root`:

~~~bash
# 1. Reconfigure wireshark-common to allow non-superusers
sudo dpkg-reconfigure wireshark-common

# 2. Add current user to the wireshark group
sudo usermod -aG wireshark $USER

# 3. Apply group changes
newgrp wireshark
~~~

Verify non-root capture permission:
~~~bash
dumpcap -D
~~~

---

## 4. Packet Capture Methodology

### 4.1 Capturing Gateway UDP Port 1700 Traffic
The Milesight UG65 gateway forwards raw LoRaWAN frames over Semtech UDP Protocol on port `1700`. Capture this backhaul traffic using `tcpdump` or `tshark`:

~~~bash
# Capture UDP 1700 traffic on all interfaces
sudo tcpdump -i any -s 0 -w ~/lorawan-lab/captures/pcap/gateway-udp1700-$(date -u +%Y%m%dT%H%M%SZ).pcap udp port 1700
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
| `lorawan.mic_verified == False` | Filter failed MIC checks | Transit tampering detection |
| `lorawan.fport == 1` | Filter by Application Port | Sensor data filtering |
| `lorawan.frmpayload_decrypted` | Filter decrypted payload | Telemetry validation |
| `lorawan.mac.cmd` | Filter MAC commands | Network management audit |

---

## 6. Cryptographic Decryption Engine Setup

### 6.1 Step-by-Step Wireshark Decryption Setup

Wireshark includes a built-in LoRaWAN dissector capable of decrypting AES-128-CTR application payloads when provided with synthetic lab session keys.

1. Launch Wireshark and open your `.pcap` capture file:
   ~~~bash
   wireshark ~/lorawan-lab/captures/pcap/gateway-udp1700.pcap
   ~~~
2. Navigate to **Edit $\rightarrow$ Preferences $\rightarrow$ Protocols $\rightarrow$ LoRaWAN**.
3. In the LoRaWAN preferences dialog, enter session key values:
   - **NwkSKey (Network Session Key)**: Enter the 32-character hex key (e.g., `2B7E151628AED2A6ABF7158809CF4F3C`).
   - **AppSKey (Application Session Key)**: Enter the 32-character hex key (e.g., `2B7E151628AED2A6ABF7158809CF4F3C`).
4. Click **OK** to apply.
5. Apply display filter `lorawan.frmpayload_decrypted` to view decrypted ASCII/Hex bytes directly inside the packet tree.

---

## 7. Operational Security Analysis & Audit Workflows

### 7.1 Replay Attack Audit Workflow

**Objective**: Verify whether the private network server detects and rejects replayed uplink frames.

1. **Capture Frame**: Capture a valid uplink frame from the Milesight gateway stream using `tshark`.
2. **Inspect Counter**: Open PCAP in Wireshark and record `lorawan.fcnt` (e.g., `FCnt = 15`).
3. **Simulate Replay**: Re-transmit the exact same Semtech UDP `PUSH_DATA` packet over UDP 1700 to ChirpStack when server state has reached `FCnt = 16`.
4. **Inspect Server Response**: Observe ChirpStack server logs (`docker logs chirpstack`).
5. **Correlate Server Behavior**:
   - Verify server output: `frame counter rolled back` or `FCnt 15 <= 16`.
   - Confirm ChirpStack drops duplicate frames without emitting an MQTT uplink event.

---

### 7.2 Man-in-the-Middle (MitM) Payload Tampering Audit

**Objective**: Verify server rejection of frames modified in transit.

1. **Obtain Frame**: Inspect captured Semtech UDP `PUSH_DATA` datagram.
2. **Mutate Payload Byte**: Flip or alter 1 byte in the base64-encoded `data` field of the UDP payload (simulating an adversary altering sensor telemetry or injecting fake MAC commands).
3. **Send to Server**: Forward the altered datagram over UDP port 1700 to ChirpStack Gateway Bridge.
4. **Inspect Wireshark Dissection**:
   - Wireshark flags `lorawan.mic_verified == False`.
5. **Correlate Server Logs**:
   - ChirpStack logs: `validate mic error: invalid mic`.

---

### 7.3 OTAA Join-Request DevNonce Replay Audit

**Objective**: Verify server prevention of Join-Request replay attacks by reusing `DevNonce` values.

1. **Capture Join-Request**: Isolate Join-Request packet in Wireshark (`lorawan.mtype == 0`) and note the 2-byte `DevNonce`.
2. **Simulate Replay**: Re-inject the identical `JoinRequest` packet over UDP port 1700.
3. **Inspect Server Response**:
   - ChirpStack logs: `validate devnonce error: devnonce has already been used`.
   - Confirm server drops replayed join request without issuing a `JoinAccept`.

---

## 8. Command-Line Automated Inspection & Threat Hunting with TShark

`tshark` allows automated security verification scripts to parse `.pcap` files without a GUI.

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

### 8.2 Threat Hunting for Invalid MICs or Dissector Errors
~~~bash
tshark -r ~/lorawan-lab/captures/pcap/gateway-udp1700.pcap \
    -Y "lorawan.mic_verified == False" \
    -T fields \
    -e frame.number \
    -e frame.time \
    -e lorawan.devaddr \
    -e lorawan.fcnt
~~~

### 8.3 Automated Replay Detection Script (`audit_replay.sh`)
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

## 9. Summary & Reference Links

- **Wireshark LoRaWAN Display Filter Reference**: [wireshark.org/docs/dfref/l/lorawan.html](https://www.wireshark.org/docs/dfref/l/lorawan.html)
- **LoRaWAN Security Testing Runbook**: [08: LoRaWAN Security Testing Runbook](../docs/08-lorawan-security-testing-runbook.md)
