# LoRaWAN Protocol and Security Testing Setup Guide

This guide builds the software-driven protocol and security testing toolchain described in [06: LoRaWAN RF and Security Testing Toolkit](./06-lorawan-rf-security-toolkit-brief.md). It is designed for an authorized lab using the **Milesight UG65 Gateway**, **Dragino LSN50v2 end-devices**, and **ChirpStack v4 Network Server**.

> [!NOTE]
> **No SDR Hardware Required**: This operational setup captures Semtech UDP packet forwarder datagrams on UDP port 1700 directly between the gateway and ChirpStack, providing full protocol dissection, cryptographic integrity checking, and frame analysis in **Wireshark & TShark**.

---

## 1. Scope and Operating Rules

### 1.1 In Scope
- Capturing live Semtech UDP port 1700 datagrams on the lab network (`192.168.23.0/24`).
- Dissecting LoRaWAN `PHYPayload` structures in Wireshark and TShark.
- Validating Message Integrity Codes (`MIC`) using synthetic session keys.
- Decrypting AES-128-CTR application payloads using `NwkSKey` and `AppSKey`.
- Auditing Frame Counter (`FCnt`) progression for replay attack resistance.
- Correlating network packet evidence with ChirpStack logs and PostgreSQL events.

### 1.2 Out of Scope
- Intercepting or attempting to decrypt production/third-party LoRaWAN network traffic.
- Injecting unauthorized frames into public LoRaWAN gateways or commercial network servers.
- Testing with live production keys, customer credentials, or real end-device identities.

---

## 2. Layer Model & Architecture

~~~text
+--------------------------------+
|  Dragino LSN50v2 Sensor Node   |
+---------------+----------------+
                | Over-The-Air LoRa RF
                v
+---------------+----------------+
|   Milesight UG65 Gateway AP    | (IP: 192.168.23.150)
+---------------+----------------+
                | Semtech UDP Packet Forwarder (UDP Port 1700)
                v
+---------------+----------------+
|    Wireshark / TShark Tap      | (Live Packet Tap & Dissector)
+---------------+----------------+
                | Decoded PCAP & Evidence
                v
+---------------+----------------+
| ChirpStack v4 Network Server   | (Ubuntu VM: 192.168.23.137)
+--------------------------------+
~~~

### Diagnostic Layer Guide
1. **Transport Layer (UDP 1700)**: If Wireshark shows no UDP packets on port 1700, verify the gateway Packet Forwarder settings in the Milesight Web UI (`192.168.23.150`) and confirm static IP connectivity.
2. **Protocol Dissection**: If Wireshark displays raw UDP payload hex but does not dissect `lorawan`, verify that the LoRaWAN dissector plugin is enabled.
3. **Cryptographic Validation**: If `lorawan.mic_verified` returns `False`, verify that the device `NwkSKey` or `AppKey` matches the lab session configuration.
4. **Server Disposition**: If Wireshark displays a valid frame but ChirpStack drops it, check ChirpStack container logs for frame counter regression (`FCnt`) or DevAddr mismatches.

---

## 3. Host Setup & Environment

### 3.1 Install Prerequisites
On the Ubuntu VM or Host machine:

~~~bash
sudo apt update
sudo apt install -y wireshark tshark tcpdump mosquitto-clients python3 python3-pip git
~~~

### 3.2 Configure Wireshark Non-Root Captures
To allow user-level packet capture without `sudo`:

~~~bash
sudo dpkg-reconfigure wireshark-common
sudo usermod -aG wireshark $USER
newgrp wireshark
~~~

### 3.3 Create Workspace Structure

~~~bash
mkdir -p ~/lorawan-lab/captures/pcap
mkdir -p ~/lorawan-lab/captures/reports
mkdir -p ~/lorawan-lab/keys
~~~

---

## 4. Wireshark & TShark Protocol Security Workflow

### 4.1 Live Packet Capture via Command Line (TShark)
To record UDP port 1700 traffic between the Milesight gateway (`192.168.23.150`) and ChirpStack (`192.168.23.137`):

~~~bash
tshark -i eth0 -f "udp port 1700" \
  -w ~/lorawan-lab/captures/pcap/lorawan-security-$(date -u +%Y%m%d_%H%M%S).pcap
~~~

### 4.2 Standard Wireshark Display Filters

| Display Filter | Purpose / Security Audit Role |
|---|---|
| `lorawan` | Isolate all parsed LoRaWAN traffic |
| `lorawan.mtype == 0` | Join-Request frames |
| `lorawan.mtype == 1` | Join-Accept frames |
| `lorawan.mtype == 2` | Unconfirmed Data Uplink frames |
| `lorawan.mtype == 4` | Confirmed Data Uplink frames |
| `lorawan.devaddr == 01:02:03:04` | Filter frames by synthetic DevAddr |
| `lorawan.mic_verified == True` | Highlight valid Message Integrity Codes |
| `lorawan.mic_verified == False` | Identify corrupted or tampered frames |
| `lorawan.fcnt` | Track Frame Counter progression for replay audits |

### 4.3 Configuring Key Decryption in Wireshark
To enable automatic payload decryption (`FRMPayload`):

1. Open Wireshark and load your `.pcap` capture file.
2. Navigate to **Edit $\rightarrow$ Preferences $\rightarrow$ Protocols $\rightarrow$ LoRaWAN**.
3. Under **Keys**, enter your lab device session keys:
   - **NwkSKey**: `2B7E151628AED2A6ABF7158809CF4F3C` (Example 32-hex key)
   - **AppSKey**: `2B7E151628AED2A6ABF7158809CF4F3C`
4. Click **OK**.
5. Apply display filter `lorawan.frmpayload_decrypted` to view plaintext hex/ASCII contents.

---

## 5. Security Testing Execution Stages

### Stage 1: Baseline Packet Capture
- [ ] Connect host laptop to Milesight Gateway AP (`Gateway_F94C0B`).
- [ ] Launch `tshark` capture on `udp port 1700`.
- [ ] Trigger a Dragino sensor transmission.
- [ ] Confirm `lorawan` packet structure is dissected cleanly in Wireshark.

### Stage 2: MIC Cryptographic Integrity Verification
- [ ] Inspect `lorawan.mic` field in Wireshark.
- [ ] Confirm `lorawan.mic_verified == True` when using valid session keys.
- [ ] Verify ChirpStack logs accept the uplink frame.

### Stage 3: Frame Counter (FCnt) & Replay Audit
- [ ] Observe `lorawan.fcnt` progression across sequential uplinks.
- [ ] Test server behavior when duplicate or out-of-sequence frame counters are transmitted.
- [ ] Confirm ChirpStack drops replayed frames with a frame counter error.

### Stage 4: Server & Event Correlation
- [ ] Subscribe to live ChirpStack MQTT uplink events:
  ~~~bash
  mosquitto_sub -h localhost -t "application/+/device/+/event/up" -v
  ~~~
- [ ] Correlate MQTT event timestamps with Wireshark PCAP timestamps and PostgreSQL event logs.

---

## 6. References & Documentation Links

- [01: Master Deployment Guide](./01-master-deployment-guide.md)
- [02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md)
- [10: Wireshark LoRaWAN Security Handbook](../technology-docs/10-wireshark-lorawan-security-handbook.md)
- [Wireshark LoRaWAN Display Filter Reference](https://www.wireshark.org/docs/dfref/l/lorawan.html)
