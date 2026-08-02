# LoRaWAN RF and Security Testing Toolkit

For the incoming RAK5146 SPI / AS923 gateway and WisBlock hardware, use [09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md) for physical assembly and normal gateway/device bring-up. This brief covers the optional RF-security tooling around that operational baseline.

## Executive recommendation

Adopt a layered test bench rather than looking for one tool that does everything:

~~~text
RF / IQ signal
    -> gr-lora_sdr or SDRangel
LoRa PHY payload
    -> LoRa_Craft, LAF, or a small adapter
LoRaWAN fields and security state
    -> Wireshark and ChirpStack event logs
Operational result
    -> replay / spoof detection evidence, packet captures, and a remediation report
~~~

The recommended default stack is:

1. **gr-lora_sdr** for the main GNU Radio PHY path. It is the strongest engineering choice when we need receiver and transmitter control, repeatable flowgraphs, and direct access to LoRa modulation parameters.
2. **SDRangel** as the GUI alternative for operators who need a polished spectrum view and interactive ChirpChat receive/transmit controls.
3. **LoRa_Craft** for Scapy-based inspection and construction of LoRa PHY and LoRaWAN packets after a PHY decoder has produced bytes.
4. **Wireshark** for inspecting packet captures and protocol fields once traffic is represented in a format it can dissect.
5. **LAF** as an optional, passive-first auditing and alerting component. It is explicitly labelled an alpha project and should live in an isolated lab or controlled monitoring segment.
6. **ChirpStack** as the system under test and the source of application-level events, frame-counter decisions, and network-server logs.

This split gives the team a practical path from “is there a LoRa signal?” to “what LoRaWAN frame was it?” to “did the network accept, reject, or alert on it?”

## How this fits the existing repository

The existing documentation already describes the operational LoRaWAN stack. This toolkit adds an RF/protocol test bench around it; it does not replace the deployment and integration guides.

| Existing document | What it provides | How this toolkit uses it |
|---|---|---|
| [01: Master Deployment Guide](./01-master-deployment-guide.md) | Ubuntu VM, Dockerized ChirpStack v4, Milesight gateway, Dragino onboarding, codec, and diagnostics | Provides the private network server and the normal gateway/device baseline. |
| [02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md) | Milesight UG65 direct-AP networking, `192.168.23.0/24`, static VM addressing, and UDP 1700 forwarding | Use it when the RF/security lab is physically attached to the gateway AP rather than the normal LAN. |
| [03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md) | Persistent ChirpStack event storage and SQL queries | Stores the server-side evidence that must be correlated with RF captures and alerts. |
| [04: Grafana Integration Guide](./04-grafana-integration-guide.md) | Dashboards and time-series views over PostgreSQL telemetry | Visualizes frame timing, RSSI/SNR, device intervals, and test outcomes after the events are persisted. |
| [05: Node-RED Integration Guide](./05-node-red-integration-guide.md) | MQTT-driven automation and threshold alerts | Provides an application/operations view of the same events; it is not a PHY decoder. |
| [Hardware checklist](../hardware-checklist.pdf) | Existing project hardware reference | Use it as the starting inventory, then add the SDR/RF safety items below for this test bench. |

The current project hardware maps into the test architecture as follows:

- **Milesight UG65/UG67:** gateway and packet-forwarder under test. It moves LoRaWAN traffic to ChirpStack, but it is not a substitute for an SDR IQ receiver.
- **Dragino LSN50v2-S31:** normal Class A sensor and payload-codec test device. Use a dedicated lab unit or a resettable synthetic device for active security tests; do not experiment against a production sensor.
- **Ubuntu VM and Docker stack:** network-server, gateway bridge, MQTT, PostgreSQL, and Redis foundation described in the existing guides.
- **Grafana and Node-RED:** downstream observability and automation consumers. They become useful after the RF/protocol result has been correlated with a ChirpStack event.
- **New SDR/RF bench:** the additional hardware needed to observe actual LoRa modulation and, when approved, perform controlled TX tests.

The short version is: the existing gateway/device stack proves network behavior; the new SDR bench proves what happened over the air.

## Device and equipment decision

The minimum useful setup depends on the test objective:

| Objective | Required devices/equipment | Not required |
|---|---|---|
| Receive and decode a known LoRa signal | Linux host, band-appropriate SDR receiver, antenna or conducted input, `gr-lora_sdr` or SDRangel | Transmitter, second gateway, PostgreSQL, Grafana, Node-RED |
| Parse LoRaWAN frames | The receive setup plus decoded PHYPayload bytes, LoRa_Craft or an adapter, Python environment | TX hardware and live gateway access |
| Validate ChirpStack acceptance/rejection | Existing private ChirpStack stack, one lab gateway, one lab end-device, MQTT/log access | A second SDR if the test uses gateway-provided packet evidence only |
| Test RF TX/RX behavior | Receive setup plus an approved TX-capable SDR or region-appropriate LoRa transceiver, coax, fixed attenuators, 50-ohm termination, and shielding | Production gateway and production device |
| Test duplicate/replay detection | Private ChirpStack, captured lab frames, LAF or equivalent analyzer, evidence storage | Public LoRaWAN service |
| Test multi-gateway deduplication | One lab device plus two lab gateways or two independent receive paths | TX injection if the device can generate the traffic naturally |

Recommended default: buy or allocate the receive-only SDR and RF safety accessories first. Add TX hardware only after the receive path and private ChirpStack test pass.

## What problem this solves

LoRa and LoRaWAN are related but different layers:

| Layer | Question | Recommended tool | Output |
|---|---|---|---|
| RF and LoRa PHY | Is a signal present, and can it be demodulated? | gr-lora_sdr or SDRangel ChirpChat | IQ samples, demodulated LoRa payload, PHY metadata |
| LoRaWAN packet format | What are the MType, DevAddr, frame counter, port, MIC, and payload fields? | LoRa_Craft / Scapy, with an adapter where needed | Parsed or crafted PHYPayloads |
| Packet capture and evidence | Can a reviewer inspect the exchange and filter relevant fields? | Wireshark | PCAP and display-filter evidence |
| Network behavior | Did the network server accept, reject, decrypt, or route the frame? | ChirpStack UI, MQTT, logs, and LAF | Events, rejection reasons, alerts, database records |

No single component is equally good at all four jobs. Keeping the boundaries explicit makes troubleshooting much faster: an empty Wireshark view does not prove the RF decoder failed, and a decoded PHYPayload does not prove the network server accepted it.

## Tool decisions

### 1. gr-lora_sdr: primary PHY tool

The EPFL Telecommunication Circuits Laboratory project describes gr-lora_sdr as a fully functional GNU Radio implementation of a LoRa transceiver. Its README documents both transmitter and receiver hierarchical blocks, synchronization and carrier-offset correction, CRC verification, soft-decision decoding, and user-selectable spreading factor, coding rate, bandwidth, sync word, header mode, and CRC settings. The project targets GNU Radio 3.10 and includes example flowgraphs and a transmit/receive functionality check.

Use it when the team needs:

- A scriptable and inspectable receive chain.
- A controlled transmit chain for a shielded or cabled lab.
- Repeatable parameter sweeps across spreading factor, bandwidth, coding rate, sync word, header, CRC, and low-data-rate optimisation.
- IQ capture and replay at the signal-processing layer.
- A base for an adapter that emits decoded PHYPayload bytes to Python or UDP.

Important boundary: gr-lora_sdr demodulates LoRa PHY. It does not replace a LoRaWAN network server, application decoder, security monitor, or packet-capture tool.

Primary references:

- [gr-lora_sdr repository and README](https://github.com/tapparelj/gr-lora_sdr)
- [GNU Radio Linux installation guidance](https://wiki.gnuradio.org/index.php/LinuxInstall)
- [LoRaWAN 1.0.4 specification package](https://lora-alliance.org/resource_hub/lorawan-104-specification-package/)

### 2. SDRangel: GUI route

SDRangel is the better first experience for a user who wants a spectrum/waterfall view and an interactive GUI instead of a GNU Radio flowgraph. Its current project advertises LoRa support and its ChirpChat channel family provides LoRa demodulation/modulation controls.

Use it when the team needs:

- Quick visual confirmation that the radio is tuned and seeing energy.
- Interactive receive experiments.
- A GUI transmit path for a cabled or shielded test.
- A convenient operator-facing tool alongside the more scriptable GNU Radio path.

Do not treat the GUI as a replacement for a test record. Record the workspace settings, center frequency, channel offset, sample rate, antenna path, and test timestamp with every capture.

Primary references:

- [SDRangel project site](https://www.sdrangel.org/)
- [SDRangel quick-start and installation wiki](https://github.com/f4exb/sdrangel/wiki/Quick-start)
- [SDRangel source repository](https://github.com/f4exb/sdrangel)

### 3. LoRa_Craft: protocol and packet-construction tool

LoRa_Craft is the public project that should be used when the team needs Scapy-style LoRa PHY and LoRaWAN packet parsing, packet construction, crypto helpers, or a handoff from a decoder to a Python analysis script. Its README documents LoRaWAN 1.0 and 1.1 parsing, uplink and downlink support, PHYPayload handling, and integration with GNU Radio/SDR equipment.

The compatibility caveat matters: the project README describes Python 2 or 3, Scapy, GNU Radio 3.8, and the older gr-lora or gr-lorasdr family. It should therefore be treated as a legacy protocol toolkit until a local adapter has been tested against the current gr-lora_sdr output. The correct architecture is:

~~~text
gr-lora_sdr output
    -> adapter / normalizer
    -> LoRaWAN PHYPayload bytes plus PHY metadata
    -> LoRa_Craft Scapy layers
~~~

Do not claim that the current gr-lora_sdr output is a drop-in replacement for the older UDP or message format without testing it.

Primary reference:

- [PentHertz LoRa_Craft repository and README](https://github.com/PentHertz/LoRa_Craft)

### 4. LoRaPWN: research reference, not an installation target

LoRaPWN is useful for understanding the published attack methodology, but it is not the component to standardize on for a repeatable internal build. Public reporting says the research tool was not released as an installable public project, while LoRa_Craft is the public project on which the research tooling was based or extended.

Use the research material for:

- Threat-model background.
- Test-case design.
- Understanding why key handling, frame counters, join state, and replay detection matter.

Use LoRa_Craft and LAF for the open tooling path, subject to the limitations documented below.

References:

- [Trend Micro research on gauging LoRaWAN communication security](https://www.trendmicro.com/en_us/research/21/b/gauging-lorawan-communication-security-with-lorapwn.html)
- [Public reporting on LoRaPWN availability and LoRa_Craft](https://www.hackster.io/news/trend-micro-finds-lorawan-security-lacking-develops-lorapwn-python-utility-bba60c27d57a)

### 5. LAF: optional audit and detection layer

The IOActive LoRaWAN Auditing Framework is useful for collecting, parsing, analyzing, and testing LoRaWAN traffic. Its current repository describes packet collectors, analyzers, packet parsers, packet crafting, fuzzing helpers, and a database-backed Docker setup. It also exposes alerts such as repeated DevNonce and suspicious address/counter behavior.

LAF is not a production security control. The repository calls itself an alpha version, carries legacy dependency assumptions, and includes both passive analysis and active packet-sending tools. The team should:

- Start with passive collection and analysis only.
- Run it in a lab or a dedicated monitoring segment.
- Use synthetic devices, a private ChirpStack instance, or a cabled/shielded test path.
- Treat every active sender, proxy, fuzzer, brute-forcer, and packet crafter as a separately approved test action.
- Pin the exact commit used in a test report.

Primary reference:

- [IOActive LAF repository and README](https://github.com/IOActive/laf)

### 6. Wireshark: evidence and human inspection

Wireshark is the right place to review protocol captures once they have been converted into a supported packet representation. Its LoRaWAN display-filter reference includes the lorawan protocol fields and version coverage.

Wireshark is not an IQ decoder. It does not replace gr-lora_sdr or SDRangel, and it may not automatically dissect every vendor-specific gateway encapsulation. Keep the original IQ capture and the original gateway/MQTT capture alongside any Wireshark display-filter screenshot or exported PCAP.

Primary reference:

- [Wireshark LoRaWAN display-filter reference](https://www.wireshark.org/docs/dfref/l/lorawan.html)

## Recommended lab architecture

~~~text
                         shielded or cabled RF path
                    +-------------------------------+
                    |                               |
             +------+-----+                   +-----+------+
             |  LoRa TX   |                   |  LoRa RX   |
             | SDRangel  |                   | RTL-SDR /  |
             | or USRP   |                   | USRP / SDR |
             +------+-----+                   +-----+------+
                    |                               |
                    | IQ / LoRa PHY                 |
                    +---------------+---------------+
                                    v
                         gr-lora_sdr or SDRangel
                                    |
                         decoded PHYPayload + metadata
                                    v
                     adapter / LoRa_Craft / Wireshark
                                    |
             +----------------------+----------------------+
             |                                             |
             v                                             v
    private ChirpStack + MQTT                         LAF collector
    network server under test                         and analyzers
             |                                             |
             +----------------------+----------------------+
                                    v
                         test report and evidence
~~~

The production gateway and production devices are intentionally outside this diagram. A production deployment may be observed under an approved passive-monitoring plan, but active injection belongs in a separate test network.

## What the boss should expect to receive

The first delivery should be a repeatable proof of capability, not a promise that every attack can be automated:

1. A receive-only baseline showing a known lab signal, its PHY parameters, and the decoded PHYPayload.
2. A protocol report showing the same PHYPayload parsed into LoRaWAN fields.
3. A Wireshark or equivalent capture that a second engineer can inspect.
4. A private ChirpStack test that demonstrates accepted and rejected frames, including frame-counter and MIC behavior.
5. A replay/spoof detection report from the monitoring path, with timestamps, device identity, frame counter, MIC status, server disposition, and alert disposition.
6. A compatibility record stating the exact tool versions, commits, hardware, region, and test wiring.

## Suggested acceptance criteria

| ID | Acceptance criterion | Evidence |
|---|---|---|
| RF-01 | A known LoRa signal is visible and demodulated with the expected SF/BW/CR/sync settings. | IQ file, flowgraph/workspace, console output |
| RF-02 | A PHY decoder reports CRC status and a stable payload for repeated lab transmissions. | Decoder log and repeated capture |
| PROTO-01 | LoRa_Craft or an adapter parses the decoded PHYPayload without silently changing bytes. | Before/after hex comparison and parser output |
| PROTO-02 | A deliberately invalid-MIC test is rejected by the private network server. | ChirpStack event/log and packet record |
| DET-01 | A repeated lab frame is recorded as a duplicate or replay signal by the selected detection path. | LAF alert or equivalent server-side evidence |
| DET-02 | A frame-counter regression or reset is visible in the report and disposition is documented. | Frame timeline and server result |
| OPS-01 | The full test can be repeated by a second engineer from the Markdown guide. | Re-run checklist and artifacts directory |
| SAFE-01 | No active transmission leaves the shielded/cabled test boundary. | Hardware diagram, attenuation/shielding record, operator sign-off |

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| TX energy reaches a live LoRaWAN network | Interference, unintended device behavior, regulatory exposure | Receive-only first; use a shielded box or conducted path with attenuation; use dummy keys and a private network |
| Legacy tool does not interoperate with current GNU Radio | False conclusion that the whole stack is broken | Keep gr-lora_sdr and LoRa_Craft in separate environments; define and test an adapter contract |
| Captures contain root keys or decrypted payloads | Credential and privacy exposure | Use synthetic lab keys; encrypt storage; redact before sharing; never put real keys in tickets or Git |
| LAF's alpha behavior is mistaken for a prevention control | Missed attacks or false confidence | Treat LAF as evidence and triage support; validate findings against ChirpStack state and raw captures |
| Regional parameters are wrong | No reception, invalid test, or unlawful transmission | Record region and channel plan before testing; use the radio vendor's approved band plan |
| Frame counters and joins are misinterpreted | Wrong security conclusion | Record LoRaWAN version, activation mode, counter policy, reset behavior, and server configuration for every device |

## Decision

Accept the following default workflow:

- **Receive and understand the signal:** gr-lora_sdr.
- **Operate the receive/transmit path interactively:** SDRangel.
- **Parse and construct protocol packets:** LoRa_Craft, behind an explicit adapter when required.
- **Inspect and preserve evidence:** Wireshark plus original IQ and gateway captures.
- **Detect and report suspicious behavior:** ChirpStack server-side controls plus LAF in an isolated, passive-first deployment.

This is a modular toolkit decision. It is intentionally not a claim that any one repository is production-ready as a LoRaWAN intrusion-prevention system.

## Verified source list

The following upstream pages were checked for this document on 2026-08-01:

- [gr-lora_sdr README](https://github.com/tapparelj/gr-lora_sdr)
- [GNU Radio Linux installation](https://wiki.gnuradio.org/index.php/LinuxInstall)
- [SDRangel quick start](https://github.com/f4exb/sdrangel/wiki/Quick-start)
- [SDRangel repository](https://github.com/f4exb/sdrangel)
- [LoRa_Craft README](https://github.com/PentHertz/LoRa_Craft)
- [IOActive LAF README](https://github.com/IOActive/laf)
- [Wireshark LoRaWAN display filters](https://www.wireshark.org/docs/dfref/l/lorawan.html)
- [LoRaWAN 1.0.4 specification package](https://lora-alliance.org/resource_hub/lorawan-104-specification-package/)
- [ChirpStack MQTT integration](https://www.chirpstack.io/docs/chirpstack/integrations/mqtt.html)
- [ChirpStack gateway configuration](https://www.chirpstack.io/docs/gateway-configuration/index.html)
