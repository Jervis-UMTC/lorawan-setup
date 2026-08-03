# LoRaWAN RF and Security Testing Toolkit

For the incoming RAK5146 SPI / AS923 gateway and WisBlock hardware, use [09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md) for physical assembly and normal gateway/device bring-up. This brief covers the RF and security testing tooling built on **gr-lora-sdr** and **Wireshark** around that operational baseline.

## Executive recommendation

Adopt a standardized test bench centered on **gr-lora-sdr** and **Wireshark** for testing and security testing:

~~~text
RF / IQ signal & LoRa PHY
    -> gr-lora-sdr (GNU Radio SDR receiver and transmitter)
LoRaWAN fields & security testing
    -> Wireshark (packet capture and protocol dissection)
Operational result & security verification
    -> ChirpStack event logs, packet captures, and remediation reports
~~~

The recommended default stack is:

1. **gr-lora-sdr** for the primary GNU Radio PHY path. It is the core engineering choice for receiver/transmitter control, repeatable flowgraphs, and direct access to LoRa modulation parameters.
2. **Wireshark** for packet capture (PCAP) inspection, protocol field analysis, MIC verification, and security testing once traffic is captured or converted.
3. **ChirpStack** as the system under test and the source of application-level events, frame-counter decisions, and network-server security logs.

This architecture gives the team a clear, standardized path from "is there a LoRa signal?" to "what LoRaWAN frame was it?" to "did the network server accept, reject, or flag the security test?"

## How this fits the existing repository

The existing documentation describes the operational LoRaWAN stack. This toolkit adds an RF/protocol test bench using **gr-lora-sdr** and **Wireshark**; it does not replace the deployment and integration guides.

| Existing document | What it provides | How this toolkit uses it |
|---|---|---|
| [01: Master Deployment Guide](./01-master-deployment-guide.md) | Ubuntu VM, Dockerized ChirpStack v4, Milesight gateway, Dragino onboarding, codec, and diagnostics | Provides the private network server and the normal gateway/device baseline. |
| [02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md) | Milesight UG65 direct-AP networking, `192.168.23.0/24`, static VM addressing, and UDP 1700 forwarding | Use it when the RF/security testing lab is physically attached to the gateway AP rather than the normal LAN. |
| [03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md) | Persistent ChirpStack event storage and SQL queries | Stores server-side evidence correlated with gr-lora-sdr captures and Wireshark PCAPs. |
| [04: Grafana Integration Guide](./04-grafana-integration-guide.md) | Dashboards and time-series views over PostgreSQL telemetry | Visualizes frame timing, RSSI/SNR, device intervals, and test outcomes after events are persisted. |
| [05: Node-RED Integration Guide](./05-node-red-integration-guide.md) | MQTT-driven automation and threshold alerts | Provides an application/operations view of security test events. |
| [Hardware checklist](../hardware-checklist.pdf) | Existing project hardware reference | Use it as the starting inventory, then add the SDR/RF safety items below for testing. |

The current project hardware maps into the test architecture as follows:

- **Milesight UG65/UG67:** gateway and packet-forwarder under test. It moves LoRaWAN traffic to ChirpStack.
- **Dragino LSN50v2-S31:** normal Class A sensor and payload-codec test device.
- **Ubuntu VM and Docker stack:** network-server, gateway bridge, MQTT, PostgreSQL, and Redis foundation.
- **SDR & Wireshark bench:** `gr-lora-sdr` for observing/transmitting LoRa PHY modulation and `Wireshark` for inspecting PCAPs and evaluating protocol security.

## Device and equipment decision

The setup for testing and security testing relies on:

| Objective | Required devices/equipment | Not required |
|---|---|---|
| Receive and decode LoRa signals | Linux host, band-appropriate SDR receiver, antenna/conducted input, `gr-lora-sdr` | Production network access |
| Parse LoRaWAN frames & security testing | The receive setup plus `Wireshark` for packet dissection and security inspection | Public LoRaWAN network |
| Validate ChirpStack acceptance/rejection | Existing private ChirpStack stack, lab gateway, end-device, Wireshark PCAPs, server logs | A second SDR if gateway packet logs suffice |
| Test RF TX/RX behavior | `gr-lora-sdr` TX flowgraphs, approved TX-capable SDR, coax, fixed attenuators, 50-ohm termination, shielding | Production gateway/device |
| Test duplicate/replay detection | Private ChirpStack, captured frames via `gr-lora-sdr` & `Wireshark`, server logs | Public LoRaWAN service |

## What problem this solves

LoRa and LoRaWAN are divided into clear testing layers:

| Layer | Question | Recommended tool | Output |
|---|---|---|---|
| RF and LoRa PHY | Is a signal present, and can it be demodulated/transmitted? | gr-lora-sdr | IQ samples, demodulated LoRa payload, PHY metadata |
| LoRaWAN protocol & security testing | What are the MType, DevAddr, frame counter, port, MIC, and payload fields? | Wireshark | PCAPs, parsed fields, security analysis evidence |
| Network behavior | Did the network server accept, reject, decrypt, or route the frame? | ChirpStack UI, MQTT, logs | Events, rejection reasons, database records |

## Tool decisions

### 1. gr-lora-sdr: primary PHY & RF testing tool

`gr-lora-sdr` (GNU Radio out-of-tree module) is the primary tool for LoRa PHY reception, signal demodulation, parameter configuration, and controlled transmission testing. It provides receiver and transmitter hierarchical blocks, synchronization, carrier-offset correction, CRC verification, and configurable spreading factors, coding rates, bandwidths, sync words, and header modes.

Use it when the team needs:
- Scriptable and inspectable receive and transmit chains for testing.
- Repeatable parameter sweeps across spreading factor, bandwidth, coding rate, and sync word.
- IQ capture and replay at the PHY signal-processing layer.
- Primary RF PHY payload generation for security testing.

Primary references:
- [gr-lora-sdr repository](https://github.com/tapparelj/gr-lora_sdr)
- [GNU Radio Linux installation guidance](https://wiki.gnuradio.org/index.php/LinuxInstall)
- [LoRaWAN 1.0.4 specification package](https://lora-alliance.org/resource_hub/lorawan-104-specification-package/)

### 2. Wireshark: primary protocol inspection & security testing tool

`Wireshark` is the primary tool for LoRaWAN packet capture (PCAP) inspection, protocol field analysis, and security testing. With native LoRaWAN display filters (`lorawan`), engineers can dissect frame headers, check Message Integrity Codes (MIC), track frame counters (FCnt), and analyze packet timing for security audits.

Use it when the team needs:
- Inspection and verification of captured LoRaWAN frame fields (MType, DevAddr, FCnt, FPort, MIC).
- Security testing of replay attempts, invalid MICs, and malformed headers.
- Standardized PCAP evidence collection for security reporting.

Primary reference:
- [Wireshark LoRaWAN display-filter reference](https://www.wireshark.org/docs/dfref/l/lorawan.html)

### 3. ChirpStack: system under test & security log provider

ChirpStack serves as the system under test for evaluating network server security behavior, frame counter policies, MIC validation, and device join security.

## Recommended lab architecture

~~~text
                         shielded or cabled RF path
                    +-------------------------------+
                    |                               |
              +-----+------+                  +-----+------+
              |  LoRa TX   |                  |  LoRa RX   |
              | gr-lora-sdr|                  | RTL-SDR /  |
              |  or USRP   |                  | USRP / SDR |
              +-----+------+                  +-----+------+
                    |                               |
                    | IQ / LoRa PHY                 |
                    +---------------+---------------+
                                    v
                               gr-lora-sdr
                                    |
                         decoded PHYPayload + metadata
                                    v
                                Wireshark
                                    |
              +---------------------+---------------------+
              |                                           |
              v                                           v
     private ChirpStack + MQTT                       Wireshark PCAP
     network server under test                       security evidence
              |                                           |
              +---------------------+---------------------+
                                    v
                         test report and evidence
~~~

## What the boss should expect to receive

1. A receive-only baseline from `gr-lora-sdr` showing a known lab signal and decoded PHYPayload.
2. A Wireshark protocol security capture showing parsed LoRaWAN fields, MIC status, and frame counters.
3. A private ChirpStack security test log demonstrating accepted vs. rejected frames.
4. A replay/spoofing test report generated using `gr-lora-sdr` and `Wireshark` packet analysis.

## Suggested acceptance criteria

| ID | Acceptance criterion | Evidence |
|---|---|---|
| RF-01 | A known LoRa signal is demodulated via `gr-lora-sdr` with expected SF/BW/CR settings. | IQ file, flowgraph log, console output |
| RF-02 | `gr-lora-sdr` reports stable payload CRC status for lab transmissions. | Decoder log and repeated capture |
| SEC-01 | `Wireshark` inspects captured frames and verifies MType, DevAddr, FCnt, and MIC fields. | Wireshark PCAP and screenshot evidence |
| SEC-02 | A deliberately invalid-MIC test generated for testing is rejected by ChirpStack. | ChirpStack event/log and Wireshark record |
| SEC-03 | A repeated lab frame is flagged as a duplicate/replay attempt during security testing. | Server log and Wireshark PCAP evidence |

## Verified source list

- [gr-lora-sdr repository](https://github.com/tapparelj/gr-lora_sdr)
- [GNU Radio Linux installation](https://wiki.gnuradio.org/index.php/LinuxInstall)
- [Wireshark LoRaWAN display filters](https://www.wireshark.org/docs/dfref/l/lorawan.html)
- [LoRaWAN 1.0.4 specification package](https://lora-alliance.org/resource_hub/lorawan-104-specification-package/)
- [ChirpStack MQTT integration](https://www.chirpstack.io/docs/chirpstack/integrations/mqtt.html)
