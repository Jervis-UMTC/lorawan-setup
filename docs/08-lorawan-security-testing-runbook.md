# LoRaWAN Infrastructure Security Audit Runbook

This runbook provides standardized operational tactics and step-by-step procedures for conducting security analysis, posture evaluations, and vulnerability auditing of **our owned LoRaWAN infrastructure** (Milesight UG65 Gateway, Dragino LSN50v2 Sensors, ChirpStack v4 Network Server, PostgreSQL, and Node-RED stack).

> [!IMPORTANT]
> **Internal Infrastructure Security Audit Scope**: All tactics and test cases herein evaluate confidentiality, cryptographic integrity, anti-replay protections, and transport security across **our private network deployment**. Operations are conducted using non-disruptive network packet taps (`TShark`/`tcpdump`), protocol dissectors, synthetic test packet generation over UDP Port 1700, and ChirpStack container log auditing.

---

## 1. Test Record & Infrastructure Header

Copy this section into every internal security audit report before execution:

~~~text
Audit ID: INFRA-SEC-<YYMMDD>-<NUMBER>
Audit Title: Operational LoRaWAN Infrastructure Security Audit
Auditor / Operator: Smart Agriculture Engineering Team
Approver: Test Lead / Operations Manager
Target Gateway: Milesight UG65 (IP: 192.168.23.150 / Gateway EUI: 24E124FFFEO159C3)
Target Network Server: ChirpStack v4 Ubuntu VM (IP: 192.168.23.137)
Target Sensor Nodes: Dragino LSN50v2-S31 (Class A, OTAA)
LoRaWAN Protocol Version: 1.0.3 / 1.0.4
Capture Engine: Wireshark & TShark (Interface: eth0, Filter: udp port 1700)
Evidence Artifacts Path: ~/lorawan-lab/captures/pcap/
SHA-256 Manifest: ~/lorawan-lab/captures/pcap/manifest-sha256.txt
~~~

---

## 2. Infrastructure Security Audit Architecture

Our security analysis methodology targets four critical pillars of LoRaWAN network security:

```text
+-----------------------------------------------------------------------------------+
|                        INTERNAL NETWORK SECURITY AUDIT PILLARS                     |
|                                                                                   |
|  1. Confidentiality Audit  --> Over-the-air & UDP 1700 payload AES-128 encryption  |
|  2. Integrity Audit        --> Cryptographic MIC validation & tampering detection |
|  3. Anti-Replay Audit      --> Uplink/Downlink FCnt & OTAA DevNonce tracking       |
|  4. Gateway Transport Audit--> Gateway EUI authentication & bridge protection      |
+-----------------------------------------------------------------------------------+
```

---

## 3. Tactical Pre-Flight Checklist

### Environment & Network Isolation
- [ ] Host laptop connected to Milesight UG65 Gateway Access Point (`Gateway_F94C0B`).
- [ ] Static IP `192.168.23.137` active on Ubuntu VM with Layer-2 connectivity to `192.168.23.150`.
- [ ] ChirpStack v4 Docker stack verified healthy (`docker compose ps`).
- [ ] Synthetic lab session keys (`NwkSKey`, `AppSKey`) logged in secure local vault.

### Tooling & Environment Initialization
- [ ] `Wireshark` and `TShark` installed with non-root capture privileges (`dumpcap -D`).
- [ ] Python 3 installed with `scapy` for packet generation testing.
- [ ] Evidence directory initialized:
  ~~~bash
  mkdir -p ~/lorawan-lab/captures/pcap/ ~/lorawan-lab/scripts/
  ~~~

---

## 4. Real-World Security Analysis Tactics & Test Cases

### SEC-001: Gateway Transport Interception & Protocol Field Auditing
**Tactical Objective:** Intercept Semtech UDP port 1700 traffic between the gateway and network server, verifying protocol framing, `Gateway EUI` binding, and header field integrity.

**Procedure:**
1. Execute `TShark` on the active network interface to capture gateway traffic:
   ~~~bash
   tshark -i eth0 -f "udp port 1700" -w ~/lorawan-lab/captures/pcap/sec-001-baseline.pcap
   ~~~
2. Trigger an uplink transmission from a Dragino LSN50v2 sensor node.
3. Extract key fields using command-line `TShark` field filters:
   ~~~bash
   tshark -r ~/lorawan-lab/captures/pcap/sec-001-baseline.pcap \
       -Y "lorawan" \
       -T fields \
       -e frame.time \
       -e lorawan.mtype \
       -e lorawan.devaddr \
       -e lorawan.fcnt \
       -e lorawan.mic
   ~~~

**Expected Result:**
- `TShark` parses `MType` (e.g. `2` for Unconfirmed Data Uplink), `DevAddr`, `FCnt`, and 4-byte `MIC`.
- Raw UDP packet contains Semtech protocol header bytes (`Protocol Version: 0x02`, `Token`, `PUSH_DATA: 0x00`, and `Gateway EUI`).

---

### SEC-002: Message Integrity Code (MIC) Validation & Transit Tamper Audit
**Tactical Objective:** Verify that any transit modification of frame control header (`FCtrl`), frame counter (`FCnt`), MAC payload (`FRMPayload`), or options (`FOpts`) causes immediate MIC validation failure and server-side packet drop.

**Procedure:**
1. Open baseline PCAP in Wireshark and configure lab `NwkSKey` under **Edit $\rightarrow$ Preferences $\rightarrow$ Protocols $\rightarrow$ LoRaWAN**.
2. Confirm Wireshark marks the valid frame as `lorawan.mic_verified == True`.
3. Create a python test script (`~/lorawan-lab/scripts/inject_mic_tamper.py`) to inject a altered byte into a captured datagram:
   ~~~python
   import socket, json, base64

   # Load valid Semtech UDP PUSH_DATA packet captured from gateway
   server_address = ('192.168.23.137', 1700)
   sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

   # Sample UDP packet with altered payload byte to simulate transit tampering
   # 12-byte header + JSON payload containing rxpk data
   header = bytes([0x02, 0x12, 0x34, 0x00]) + bytes.fromhex("24E124FFFE0159C3")
   payload_json = {
       "rxpk": [{
           "tmst": 12345678, "chan": 0, "rfch": 0, "freq": 923.2,
           "stat": 1, "modu": "LORA", "datr": "SF7BW125", "codr": "4/5",
           "lsnr": 9.5, "rssi": -45, "size": 17,
           "data": "QAECAwSABQACBQAAAAAAAAD=" # Corrupted Base64 PHYPayload byte
       }]
   }
   packet = header + json.dumps(payload_json).encode('utf-8')
   sock.sendto(packet, server_address)
   print("[+] Injected tampered datagram to ChirpStack Gateway Bridge.")
   ~~~
4. Execute tamper test script:
   ~~~bash
   python3 ~/lorawan-lab/scripts/inject_mic_tamper.py
   ~~~
5. Monitor ChirpStack network server logs:
   ~~~bash
   docker logs chirpstack --tail 50 | grep -i -E "mic|invalid|error"
   ~~~

**Expected Result:**
- Wireshark dissector flags `lorawan.mic_verified == False`.
- ChirpStack logs `validate mic error: invalid mic` and immediately drops the frame without forwarding to MQTT.

---

### SEC-003: Payload Encryption & Confidentiality Audit
**Tactical Objective:** Audit `FRMPayload` confidentiality to ensure unencrypted application telemetry is not exposed over-the-air or across network backhaul without `AppSKey`.

**Procedure:**
1. Inspect captured frame in `TShark` without providing session keys:
   ~~~bash
   tshark -r ~/lorawan-lab/captures/pcap/sec-001-baseline.pcap \
       -Y "lorawan.fport > 0" \
       -T fields -e lorawan.frmpayload
   ~~~
2. Verify that raw ciphertext bytes are displayed and unreadable as plain ASCII/sensor text.
3. Configure `AppSKey` in Wireshark preferences (**Edit $\rightarrow$ Preferences $\rightarrow$ Protocols $\rightarrow$ LoRaWAN**) or pass to `TShark`:
   ~~~bash
   tshark -r ~/lorawan-lab/captures/pcap/sec-001-baseline.pcap \
       -o "lorawan.appskey:2B7E151628AED2A6ABF7158809CF4F3C" \
       -Y "lorawan.frmpayload_decrypted" \
       -T fields -e lorawan.frmpayload_decrypted
   ~~~

**Expected Result:**
- Payload remains completely confidential ciphertext when `AppSKey` is absent.
- Loading the correct 128-bit `AppSKey` allows exact recovery of sensor telemetry bytes matching the Dragino LSN50v2 payload codec output.

---

### SEC-004: Frame Counter (FCnt) Replay Resilience Audit
**Tactical Objective:** Audit ChirpStack anti-replay protection by injecting previously valid, captured uplink frames with stale frame counters ($FCnt \le FCnt_{last}$).

**Procedure:**
1. Record a valid sensor uplink frame where server state is at $FCnt = 15$.
2. Allow sensor to send additional uplinks so ChirpStack session state advances to $FCnt = 16$.
3. Create a replay test script (`~/lorawan-lab/scripts/replay_frame.py`) to re-transmit the $FCnt = 15$ datagram:
   ~~~python
   import socket

   server_address = ('192.168.23.137', 1700)
   sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

   # Raw Semtech UDP datagram recorded at FCnt = 15
   replayed_packet = bytes.fromhex("0212340024E124FFFE0159C3...") # Full UDP byte string
   sock.sendto(replayed_packet, server_address)
   print("[+] Re-injected stale FCnt=15 frame to ChirpStack.")
   ~~~
4. Run the replay test script:
   ~~~bash
   python3 ~/lorawan-lab/scripts/replay_frame.py
   ~~~
5. Check ChirpStack container logs for anti-replay enforcement:
   ~~~bash
   docker logs chirpstack --tail 50 | grep -i -E "frame counter|fcnt|rollback"
   ~~~

**Expected Result:**
- ChirpStack logs `frame counter rolled back` or `FCnt 15 <= 16`.
- ChirpStack drops the packet and does not issue an MQTT application message.

---

### SEC-005: OTAA Join-Request DevNonce Replay Audit
**Tactical Objective:** Verify server prevention of OTAA activation replay attacks by re-submitting previously used `DevNonce` values.

**Procedure:**
1. Capture an OTAA `JoinRequest` packet (`lorawan.mtype == 0`) and record its 2-byte `DevNonce`.
2. Allow device activation to complete successfully and log new session keys.
3. Re-inject the identical `JoinRequest` UDP datagram over port 1700 to ChirpStack.
4. Inspect ChirpStack server logs:
   ~~~bash
   docker logs chirpstack --tail 50 | grep -i "devnonce"
   ~~~

**Expected Result:**
- ChirpStack identifies `DevNonce` reuse, logging `validate devnonce error: devnonce has already been used`.
- The server drops the replayed activation request and refuses to issue a `JoinAccept`.

---

### SEC-006: Gateway EUI Authentication & Impersonation Audit
**Tactical Objective:** Audit ChirpStack Gateway Bridge security behavior when an unauthorized entity attempts to inject traffic using an unregistered or spoofed `Gateway EUI`.

**Procedure:**
1. Generate a synthetic `PUSH_DATA` packet containing an unregistered Gateway EUI (`0000000000000000`):
   ~~~python
   import socket, json

   sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
   fake_eui_header = bytes([0x02, 0x99, 0x88, 0x00]) + bytes.fromhex("0000000000000000")
   json_payload = {"rxpk": [{"freq": 923.2, "modu": "LORA", "datr": "SF7BW125", "data": "QAECAwS..."}]}
   sock.sendto(fake_eui_header + json.dumps(json_payload).encode('utf-8'), ('192.168.23.137', 1700))
   ~~~
2. Check ChirpStack Gateway Bridge container logs:
   ~~~bash
   docker logs chirpstack-gateway-bridge --tail 50 | grep -i -E "gateway|unregistered|eui"
   ~~~

**Expected Result:**
- ChirpStack Gateway Bridge drops datagrams originating from unregistered Gateway EUIs or flags unauthenticated connection attempts.

---

## 5. Security Hardening & Remediation Protocols

Based on audit outcomes, enforce the following hardening rules across production environments:

1. **Root Key Protection**:
   - Assign unique, cryptographically random `AppKey` / `NwkKey` values per end-device during manufacturing/provisioning.
   - Never re-use default root keys across multiple sensor nodes.
2. **LoRaWAN 1.0.4 / 1.1 Specification Enforcement**:
   - Configure ChirpStack device profiles to enforce strict `DevNonce` tracking and 32-bit Frame Counters (`FCnt`).
3. **Gateway Access Control**:
   - Restrict incoming UDP port 1700 traffic at the host firewall (`ufw`) to authorized gateway IP addresses (`192.168.23.150`).
4. **Transport Encryption**:
   - Secure gateway-to-bridge communications using TLS (e.g. MQTT with TLS or Semtech Basics Station over WebSockets/TLS `wss://`).
   - Wrap internal MQTT broker communications in TLS (`mqtts://`).

---

## 6. Audit Evidence Management & Forensics Hashing

1. Compute SHA-256 hashes for all PCAP captures and log dumps:
   ~~~bash
   sha256sum ~/lorawan-lab/captures/pcap/*.pcap > ~/lorawan-lab/captures/pcap/manifest-sha256.txt
   ~~~
2. Archive `.pcap` captures, script outputs, hash manifests, and server logs for compliance reporting.

---

## 7. References & Linked Documentation

- [01: Master Deployment Guide](./01-master-deployment-guide.md)
- [02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md)
- [06: LoRaWAN Security Toolkit Brief](./06-lorawan-rf-security-toolkit-brief.md)
- [10: Wireshark LoRaWAN Security Handbook](../technology-docs/10-wireshark-lorawan-security-handbook.md)
- [Wireshark LoRaWAN Display Filter Reference](https://www.wireshark.org/docs/dfref/l/lorawan.html)
