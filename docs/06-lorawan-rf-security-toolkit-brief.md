# LoRaWAN RF and Security Testing Toolkit

For the Milesight UG65 gateway and Dragino LSN50v2 end-devices, use [01: Master Deployment Guide](./01-master-deployment-guide.md) for physical bring-up. This decision brief establishes **Wireshark & TShark** and the **Semtech UDP Packet Forwarder (Port 1700)** as the primary, software-only protocol and security analysis toolkit for this operational baseline.

## Executive recommendation

Adopt a standardized test bench centered on **Wireshark / TShark** and the **Milesight Gateway Packet Forwarder** for protocol inspection and security testing:

~~~text
Over-The-Air Transmission (Dragino Node <-> Milesight UG65 Gateway)
    -> Semtech UDP Packet Forwarder (UDP Port 1700 frame transport)
LoRaWAN Protocol Dissection & Security Audit
    -> Wireshark / TShark (Live packet capture, MIC validation, FCnt analysis, AES decryption)
Operational Result & Security Verification
    -> ChirpStack Network Server logs, PostgreSQL event database, and MQTT topic stream
~~~

The recommended stack is:

1. **Wireshark & TShark** as the core security analysis and deep-packet inspection (DPI) engine. It provides native LoRaWAN dissection (`lorawan`), MIC integrity verification (`lorawan.mic_verified`), Frame Counter (`FCnt`) anomaly detection, MAC command breakdown, and AES-128-CTR payload decryption using lab session keys (`NwkSKey` / `AppSKey`).
2. **Milesight Gateway Packet Forwarder (UDP 1700)** as the network packet tap. Capturing UDP port 1700 traffic between the gateway (`192.168.23.150`) and ChirpStack provides complete visibility into raw LoRaWAN `PHYPayload` frames without requiring external Software Defined Radio (SDR) hardware.
3. **ChirpStack v4** as the system under test for evaluating network server security behavior, frame counter reset protection, MIC failure dropping, and device join security.

> [!NOTE]
> **Hardware Independent**: This security testing architecture operates entirely through network packet capturing and software dissection. External SDR hardware (`gr-lora-sdr`) is not required for complete protocol security auditing.

## How this fits the existing repository

The existing documentation describes the operational LoRaWAN stack. This toolkit adds a Wireshark-driven security test bench; it does not replace the deployment and integration guides.

| Existing document | What it provides | How this toolkit uses it |
|---|---|---|
| [01: Master Deployment Guide](./01-master-deployment-guide.md) | Ubuntu VM, Dockerized ChirpStack v4, Milesight gateway, Dragino onboarding, codec, and diagnostics | Provides the private network server and the normal gateway/device baseline. |
| [02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md) | Milesight UG65 direct-AP networking, `192.168.23.0/24`, static VM addressing, and UDP 1700 forwarding | Provides the physical network tap link for Wireshark to capture UDP 1700 traffic on `192.168.23.0/24`. |
| [03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md) | Persistent ChirpStack event storage and SQL queries | Stores server-side security event records correlated with Wireshark PCAP captures. |
| [04: Grafana Integration Guide](./04-grafana-integration-guide.md) | Dashboards and time-series views over PostgreSQL telemetry | Visualizes frame timing, RSSI/SNR, device intervals, and security test outcomes after events are persisted. |
| [05: Node-RED Integration Guide](./05-node-red-integration-guide.md) | MQTT-driven automation and threshold alerts | Provides real-time application and security alert workflows. |
| [Hardware checklist](../hardware-checklist.pdf) | Existing project hardware reference | Hardware inventory reference (Milesight UG65, Dragino LSN50v2, Host Laptop). |

The current project hardware maps into the security architecture as follows:

- **Milesight UG65:** Gateway under test. Transmits Semtech UDP packet forwarder datagrams over UDP port 1700 to ChirpStack Gateway Bridge.
- **Dragino LSN50v2-S31:** Class A telemetry sensor generating OTAA join requests and encrypted uplink frames.
- **Ubuntu VM & Docker Stack:** ChirpStack v4 network server microservices, PostgreSQL, and MQTT broker under test.
- **Wireshark & TShark Bench:** Live packet tap capturing UDP port 1700 datagrams for protocol security inspection and evidence logging.

## Device and equipment decision

The setup for protocol testing and security testing relies on:

| Objective | Required devices/equipment | Not required |
|---|---|---|
| Capture live LoRaWAN frames | Host laptop connected to Milesight AP (`192.168.23.0/24`), Wireshark / `tcpdump` / `tshark` | Software Defined Radio (SDR) hardware |
| Parse LoRaWAN fields & MIC check | Wireshark native LoRaWAN dissector (`lorawan`) | Custom C++ demodulation flowgraphs |
| Decrypt encrypted FRMPayloads | Wireshark LoRaWAN protocol preferences configured with lab `NwkSKey` and `AppSKey` | External decryption scripts |
| Validate ChirpStack security behavior | Private ChirpStack stack, lab gateway, end-device, Wireshark PCAPs, server logs | Production network connectivity |
| Audit FCnt & Replay resilience | Private ChirpStack server, synthetic lab traffic injection or replay, Wireshark PCAP logging | SDR transmitter |

## What problem this solves

LoRaWAN security testing is divided into clear operational layers:

| Layer | Question | Recommended tool | Output |
|---|---|---|---|
| Packet Forwarding Transport | Is the gateway forwarding valid Semtech UDP 1700 frames to ChirpStack? | `tcpdump` / `tshark` | UDP datagram capture, gateway EUI verification |
| LoRaWAN Protocol & Security | What are the MType, DevAddr, FCnt, FPort, MIC, and decrypted FRMPayload bytes? | Wireshark GUI | Parsed fields, MIC validation (`lorawan.mic_verified`), payload breakdown |
| Network Server Security | Did ChirpStack accept, drop, or flag frame anomalies (MIC failure, FCnt regression)? | ChirpStack UI & Docker logs | Audit logs, event topics, database records |

## Tool decisions

### 1. Wireshark & TShark: primary protocol inspection & security engine

`Wireshark` (GUI) and `TShark` (CLI) serve as the primary tools for LoRaWAN packet capture (PCAP) inspection, protocol field analysis, and security auditing. With native LoRaWAN display filters (`lorawan`), engineers can dissect frame headers, check Message Integrity Codes (MIC), track frame counters (FCnt), decrypt payload contents, and analyze MAC commands.

Use it when the team needs:
- Inspection and verification of captured LoRaWAN frame fields (MType, DevAddr, FCnt, FPort, MIC).
- Automated packet capture scripts (`tshark -i eth0 -f "udp port 1700" -w capture.pcap`).
- Validation of MIC integrity (`lorawan.mic_verified == True`).
- Security auditing of replay attempts, invalid MICs, and malformed headers.
- Standardized PCAP evidence collection for security reports.

Primary reference:
- [Wireshark LoRaWAN display-filter reference](https://www.wireshark.org/docs/dfref/l/lorawan.html)

### 2. ChirpStack: system under test & security log provider

ChirpStack serves as the system under test for evaluating network server security behavior, frame counter enforcement, MIC validation, and device join security.

## Recommended lab architecture

~~~text
+------------------------+                     +------------------------+
| Dragino LSN50v2 Sensor |                     |  Milesight UG65 GW     |
| (Over-The-Air Uplinks) |====================>| (Packet Forwarder)     |
+------------------------+       LoRa RF       +-----------+------------+
                                                           |
                                                UDP Port 1700 (Wi-Fi/Ethernet)
                                                           |
                                                           v
                                            +------------------------------+
                                            |   Wireshark / TShark Tap     |
                                            | (Live UDP Packet Dissector)  |
                                            +--------------+---------------+
                                                           |
                                                           v
                                            +------------------------------+
                                            | ChirpStack Network Server VM |
                                            | (System Under Security Test) |
                                            +------------------------------+
~~~

## What the boss should expect to receive

1. A live Wireshark protocol capture showing parsed LoRaWAN fields, EUI addresses, and device session details.
2. Verified Message Integrity Code (MIC) status and payload decryption evidence using lab session keys.
3. A security test report detailing server resilience against replay attempts and invalid frame counter injections.
4. Exported `.pcap` files suitable for compliance auditing and reproducible security verification.

## Suggested acceptance criteria

| ID | Acceptance criterion | Evidence |
|---|---|---|
| SEC-01 | `Wireshark` captures UDP 1700 gateway frames and dissects MType, DevAddr, FCnt, and MIC fields. | Wireshark PCAP and screenshot evidence |
| SEC-02 | `Wireshark` decrypts `FRMPayload` using provided lab `NwkSKey` and `AppSKey` session keys. | Dissected plaintext payload display in Wireshark |
| SEC-03 | A deliberately tampered or invalid-MIC frame is flagged by Wireshark and rejected by ChirpStack. | ChirpStack event log and Wireshark MIC flag |
| SEC-04 | An out-of-sequence or replayed frame counter (FCnt) is identified and dropped by ChirpStack. | Server log and Wireshark PCAP timeline |

## Verified source list

- [Wireshark LoRaWAN display filters](https://www.wireshark.org/docs/dfref/l/lorawan.html)
- [LoRaWAN 1.0.4 specification package](https://lora-alliance.org/resource_hub/lorawan-104-specification-package/)
- [ChirpStack Gateway Bridge Semtech UDP documentation](https://www.chirpstack.io/docs/chirpstack-gateway-bridge/gateways/semtech-udp.html)
- [ChirpStack MQTT integration](https://www.chirpstack.io/docs/chirpstack/integrations/mqtt.html)

