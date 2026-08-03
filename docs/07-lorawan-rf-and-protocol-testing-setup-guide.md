# LoRaWAN RF and Protocol Testing Setup Guide

This guide builds the layered toolchain described in [06: LoRaWAN RF and Security Testing Toolkit](./06-lorawan-rf-security-toolkit-brief.md). For the incoming RAK5146 SPI / AS923 gateway and WisBlock node, complete [09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md) first; an SDR is an additional PHY-observation path, not a replacement for the gateway.

It is written for an authorized test lab, a private ChirpStack deployment, and a cabled or shielded RF path. The guide deliberately separates receive, decode, packet analysis, monitoring, and active transmission so that each step can be verified independently.

## 1. Scope and operating rules

### 1.1 In scope

- Observing and demodulating known LoRa signals.
- Capturing IQ and decoded packet evidence.
- Parsing LoRaWAN PHYPayloads in a Python/Scapy workflow.
- Inspecting protocol captures in Wireshark.
- Collecting and analyzing private-lab traffic with LAF.
- Validating server behavior against known-good, invalid, duplicate, and out-of-sequence lab frames.

### 1.2 Out of scope

- Transmitting on a live network without written authorization.
- Attempting to access devices, gateways, or networks that are not owned or explicitly in scope.
- Testing with real application keys, network keys, customer payloads, or production device identities.
- Treating a detected duplicate as proof of an attack without checking gateway duplication, device retransmission, server state, and capture timestamps.

### 1.3 Non-negotiable safety controls

1. Start with receive-only hardware and receive-only flowgraphs.
2. Use a private test network with synthetic identifiers and generated test keys.
3. For any transmitter, use a shielded enclosure or a conducted cable path with appropriate attenuation and termination.
4. Confirm that the selected frequency and power settings are legal for the test location and hardware.
5. Keep a physical RF block diagram in the test record.
6. Make active operations opt-in and operator-confirmed. Never leave a fuzzer, repeater, proxy, or transmitter running unattended.
7. Preserve original evidence before changing filters, decoders, or server configuration.

## 2. Where this guide starts and ends

This guide assumes the operational LoRaWAN stack is already available or is being built from the existing repository manuals.

| If you need to... | Start with... | Then use this guide for... |
|---|---|---|
| Install ChirpStack, the gateway bridge, MQTT, PostgreSQL, and Redis | [01: Master Deployment Guide](./01-master-deployment-guide.md) | Connecting RF/protocol evidence to the private server and MQTT events |
| Connect the VM directly to the Milesight gateway AP | [02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md) | Capturing or testing traffic on the `192.168.23.0/24` lab path without changing the AP networking instructions |
| Persist and query server events | [03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md) | Correlating SQL records with IQ, decoded frames, and security alerts |
| Build dashboards | [04: Grafana Integration Guide](./04-grafana-integration-guide.md) | Visualizing the RF/protocol test results after they are available as ChirpStack events |
| Automate MQTT alerts | [05: Node-RED Integration Guide](./05-node-red-integration-guide.md) | Feeding approved test outcomes into operational automation |
| Check the original project inventory | [Hardware checklist](../hardware-checklist.pdf) | Adding the SDR, RF path, and evidence-storage items listed below |

Do not repeat the existing gateway, database, dashboard, or Node-RED installation if those guides have already been completed. This guide adds the over-the-air observation and authorized security-testing layer.

## 3. The layer model

~~~text
RF / IQ
  |  center frequency, sample rate, antenna, gain
  v
LoRa PHY
  |  SF, BW, coding rate, sync word, header, CRC, payload bytes
  v
LoRaWAN PHYPayload
  |  MType, DevAddr/JoinEUI/DevEUI, FCnt, FPort, FRMPayload, MIC
  v
Network-server behavior
  |  join state, frame-counter policy, MIC verification, decryption, routing
  v
Application and detection evidence
     ChirpStack events, MQTT, Wireshark, LAF, report
~~~

The most common diagnostic mistake is to jump between layers. Use the following rule:

- No energy: check antenna, frequency, gain, cable, and device state.
- Energy but no LoRa decode: check region, bandwidth, spreading factor, sample rate, sync word, frequency error, and CRC.
- LoRa payload but no LoRaWAN parse: check byte framing, PHY header removal, packet direction, and the adapter contract.
- LoRaWAN parse but no server event: check gateway forwarder, gateway bridge, network-server identity, MIC, keys, frame counters, and regional configuration.

## 4. Recommended lab equipment

### 4.1 Minimum receive-only setup

- Linux host, preferably Ubuntu 22.04 or 24.04 for the GNU Radio path. The existing [01: Master Deployment Guide](./01-master-deployment-guide.md) uses an Ubuntu VM, so the SDR must be physically accessible to the VM through USB passthrough or be connected to a host-side SDR service.
- A supported SDR receiver such as an RTL-SDR-class device. An RTL-SDR is receive-only; it cannot perform the TX acceptance tests below.
- A band-appropriate antenna, or a conducted cable input from a lab transmitter/recording source.
- Correct adapters and coax for the SDR and antenna connectors.
- USB extension and stable power if the receiver is sensitive to host noise.
- Host storage for IQ recordings; IQ files can become large quickly.
- Private ChirpStack and gateway components if the test includes server behavior. Reuse the Docker stack from [01: Master Deployment Guide](./01-master-deployment-guide.md) rather than creating a second network server.

### 4.2 Full project-aligned lab setup

For this repository's current deployment, the complete lab has the following roles:

| Role | Device or service | Required for | Existing documentation / note |
|---|---|---|---|
| Network-server host | Windows host with Ubuntu VM, or native Ubuntu x86_64 host | All ChirpStack-backed tests | [01: Master Deployment Guide](./01-master-deployment-guide.md) |
| Gateway | Milesight UG65 or UG67 | Gateway-to-ChirpStack tests | [01: Master Deployment Guide](./01-master-deployment-guide.md), [02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md) |
| End-device | Dragino LSN50v2-S31 or a dedicated synthetic lab node | Join, uplink, downlink, codec, and server behavior | Use the existing codec in `codecs/` and a non-production device |
| RF receiver | RTL-SDR-class receiver, USRP, or another supported SDR | Actual RF/PHY observation | New requirement covered by this guide |
| RF transmit source | Approved TX-capable SDR, or region-appropriate LoRa transceiver board | Controlled TX/RX tests only | Optional; keep behind attenuation/shielding |
| RF safety path | Band-appropriate antenna, coax, fixed attenuators, 50-ohm termination, shielding or enclosure | Any active TX test | New requirement; do not omit it |
| Packet/protocol workstation | Python environment with LoRa_Craft or adapter | PHY-to-LoRaWAN parsing | Keep separate from the current GNU Radio environment |
| Evidence workstation | Wireshark, tcpdump, storage, UTC time source | Capture and reporting | New requirement; use synthetic/redacted data |
| Observability services | MQTT, PostgreSQL, Grafana, Node-RED | Server correlation and alerting | [03](./03-postgres-integration-guide.md), [04](./04-grafana-integration-guide.md), [05](./05-node-red-integration-guide.md) |

The Milesight gateway and Dragino sensor are enough to prove normal LoRaWAN operation, but they are not enough to prove raw PHY behavior. The SDR receiver is the key additional device for the “see the actual signal” requirement.

### 4.3 Minimum configurations by test type

| Test type | Minimum configuration |
|---|---|
| RF visibility & PHY testing | Host + SDR receiver + antenna/cable + `gr-lora-sdr` |
| Protocol capture & security testing | RF visibility setup + `gr-lora-sdr` + `Wireshark` + capture storage |
| Normal ChirpStack application flow | Existing Milesight gateway + Dragino node + ChirpStack stack from docs 01/02 |
| RF-to-ChirpStack correlation | RF visibility setup + `gr-lora-sdr` + existing gateway/server stack + synchronized timestamps |
| Invalid MIC or security test | Private ChirpStack + dedicated lab device/session + `Wireshark` protocol inspection |
| Controlled RF replay/spoof security test | Full RF setup with `gr-lora-sdr` TX/RX + `Wireshark` + shielding/attenuation + private server |
| Multi-gateway duplicate test | One lab device + two gateways or two independent receive paths + PostgreSQL/Grafana evidence |

### 4.4 What is optional

- A second gateway for multi-gateway deduplication and location/correlation tests.
- A second SDR receiver for independent confirmation.
- A region-appropriate LoRa transceiver board based on an RFM95, SX1276, or SX1262 family, with a host controller and approved firmware.
- An RN2483-family or equivalent serial LoRa transceiver for point-to-point lab experiments, subject to regional SKU and firmware compatibility.
- A shielded RF enclosure if a fully conducted cable path is not practical.
- A separate capture laptop if the Ubuntu VM host cannot sustain IQ recording and the Docker stack at the same time.

### 4.5 Do not count these as substitutes

- A Milesight gateway is not a general-purpose IQ recorder.
- ChirpStack's LoRaWAN event is not proof that every RF signal was received.
- Wireshark is not a LoRa demodulator.
- PostgreSQL, Grafana, and Node-RED provide persistence, visualization, and automation; they do not recover LoRa bits.
- A transmit-capable LoRa board without a shielded/attenuated path is not a safe lab setup.

### 4.6 Hardware checklist before ordering or wiring

- [ ] The SDR covers the selected regional band.
- [ ] The antenna and connectors match the SDR and band.
- [ ] The TX device is region-appropriate and has a documented power setting.
- [ ] The cable path includes fixed attenuation and a suitable 50-ohm termination.
- [ ] A shielded enclosure is available if any energy could radiate.
- [ ] The host has enough storage for planned IQ captures.
- [ ] USB passthrough or host-side SDR access has been tested with the Ubuntu VM.
- [ ] A dedicated lab gateway and end-device are identified.
- [ ] Test keys and identifiers are synthetic.
- [ ] The gateway-to-server path is either the normal LAN path from doc 01 or the direct AP path from doc 02.

### 4.7 Transmit-capable setup

For controlled TX experiments, use hardware supported by `gr-lora-sdr` and approved for the test band. `gr-lora-sdr` documents testing with USRP-to-USRP and with commercial LoRa transceivers based on RFM95, SX1276, and SX1262 families. TX capability and legal operating limits are hardware-specific.

Do not assume an RTL-SDR can transmit. It is normally a receive-only device. A transceiver board also needs a host controller, firmware, regional configuration, and a safe RF path.

### 4.8 Hardware record

Record this before the first capture:

| Field | Example value |
|---|---|
| Region / band | EU868, US915, AS923, or approved local plan |
| Center frequency | <LAB_FREQUENCY_HZ> |
| Bandwidth | 125000 Hz, or the test value |
| Spreading factor | SF7 to SF12, or the test value |
| Coding rate | 4/5, or the test value |
| Sync word | <LAB_SYNC_WORD> |
| SDR model and serial | <MODEL> / <SERIAL> |
| Antenna / cable path | <ANTENNA_OR_ATTENUATED_CABLE> |
| TX power | <LAB_TX_POWER> or receive-only |
| Shielding / attenuation | <ENCLOSURE_OR_ATTENUATOR_CHAIN> |
| Device identities | Synthetic lab identities only |
| LoRaWAN version and activation | <VERSION> / OTAA or ABP |
| ChirpStack version | <VERSION> |
| Tool commit IDs | Record each repository commit |

## 5. Host setup

### 5.1 Use separate environments

Keep the current GNU Radio 3.10 path separate from the legacy LoRa_Craft path. A clean layout is:

~~~text
~/lorawan-lab/
├── gr-lora-sdr/       # primary PHY testing path (gr-lora-sdr)
├── wireshark/         # Wireshark PCAPs & security analysis evidence
├── captures/
│   ├── iq/
│   ├── decoded/
│   ├── pcap/
│   └── reports/
└── notes/
~~~

Do not install every project into one global Python environment. It makes it difficult to tell whether a failure is caused by the code, GNU Radio version, Scapy version, or a conflicting dependency.

### 5.2 GNU Radio installation

Start with the current GNU Radio binary installation for the operating system. The GNU Radio project recommends package-manager or binary installation for most users and documents current Debian/Ubuntu packages on its Linux installation page.

For Ubuntu:

~~~bash
sudo apt update
sudo apt install -y gnuradio gnuradio-dev git cmake build-essential python3 python3-dev python3-venv
~~~

Verify the baseline before adding gr-lora-sdr:

~~~bash
gnuradio-config-info --version
gnuradio-companion --version
python3 --version
cmake --version
~~~

If the distribution package is missing a dependency required by the gr-lora-sdr build, follow the project's own prerequisites and the GNU Radio installation guide. Do not mix a system GNU Radio ABI with a different Conda GNU Radio environment unless the active environment is explicit.

### 5.3 SDR access and permissions

For USB SDRs:

1. Install the vendor or distribution udev rules where required.
2. Confirm the device appears before starting GNU Radio or gr-lora-sdr.
3. Record the serial number so the wrong receiver cannot silently be selected.
4. Keep the SDR disconnected from any other application that may claim the USB interface.

Typical checks are:

~~~bash
lsusb
rtl_test -t
~~~

'rtl_test' is only applicable to RTL-SDR devices. Use the hardware vendor's discovery command for USRP, bladeRF, LimeSDR, or other devices.

## 6. Install and verify gr-lora-sdr

### 6.1 Why this is the primary path

`gr-lora-sdr` is the primary tool for testing and security testing at the RF/PHY layer. The project describes `gr-lora-sdr` as a GNU Radio 3.10 out-of-tree module with both TX and RX hierarchical blocks. It exposes spreading factors, coding rates, explicit or implicit header mode, payload length, sync word, CRC verification, low-data-rate optimisation, and soft-decision decoding.

### 6.2 Clone the repository

~~~bash
cd ~/lorawan-lab
git clone https://github.com/tapparelj/gr-lora_sdr.git gr-lora-sdr
cd gr-lora-sdr
git rev-parse HEAD
~~~

Save the commit ID in the test record. For a repeatable team build, pin a known-good commit rather than silently tracking the moving default branch.

### 6.3 Recommended Conda build

The upstream README provides a Conda environment for GNU Radio 3.10 and the module. If Conda is already approved on the host:

~~~bash
conda env create -f environment.yml
conda activate gr310
~~~

Then build into the active environment:

~~~bash
mkdir -p build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX="$CONDA_PREFIX"
make -j"$(nproc)"
make install
cd ..
~~~

If the module is installed into a system prefix instead, use the appropriate privileged install step and refresh the dynamic linker cache as described by the upstream README. Avoid using sudo inside a Conda environment unless the install target is intentionally system-wide.

### 6.4 Alternative Conda package path

The project also documents a Conda package:

~~~bash
conda create -n gr310-lora python=3.10
conda activate gr310-lora
conda install -c tapparelj -c conda-forge gnuradio-lora_sdr
~~~

Treat this as an alternative to the source build, not a second install layered on top of it. Confirm the package's GNU Radio version and hardware bindings before using it for a team baseline.

### 6.5 Verify the GNU Radio blocks

Start GNU Radio Companion inside the environment where the module was installed:

~~~bash
conda activate gr310
gnuradio-companion
~~~

Confirm that the LoRa transmit and receive blocks appear in the block list. If they do not:

1. Confirm the active Python and GNU Radio executables:

   ~~~bash
   which python3
   which gnuradio-companion
   gnuradio-config-info --prefix
   ~~~

2. Confirm the install prefix contains the module's Python and GRC files.
3. Follow the project's documented PYTHONPATH, LD_LIBRARY_PATH, and GRC local-block-path troubleshooting.
4. Do not immediately rebuild with a different compiler or a second GNU Radio version; record the first error.

### 6.6 Run the upstream functionality check

From the repository root, follow the upstream example:

~~~bash
python3 examples/tx_rx_functionality_check.py
~~~

Use the hardware and wiring expected by that example. If the host is receive-only, use the example flowgraphs in examples/ with a known external lab signal instead of claiming that the TX/RX test passed.

### 6.7 First receive-only experiment

Start with a known-good lab transmitter or an IQ file. Configure the receive flowgraph with the exact metadata from the transmitter:

| Parameter | Must match |
|---|---|
| Center frequency | Yes, within the receiver's frequency error tolerance |
| Bandwidth | Yes |
| Spreading factor | Yes for a single-SF decoder |
| Coding rate | Yes if the flowgraph requires it explicitly |
| Sync word | Yes unless the flowgraph is intentionally configured to ignore it |
| Header mode | Yes |
| CRC setting | Yes, or explicitly record that CRC is being ignored |
| Low-data-rate optimisation | Yes where required by the symbol time |
| Sample rate and decimation | Must support the selected signal bandwidth |

Record the following output for every decoded frame:

~~~text
timestamp_utc=<...>
frequency_hz=<...>
bandwidth_hz=<...>
spreading_factor=<...>
coding_rate=<...>
sync_word=<...>
header_mode=<explicit|implicit>
crc_status=<ok|fail|not_checked>
payload_hex=<...>
~~~

The exact console format is flowgraph-specific. The metadata contract above is the important part for later analysis.

### 6.8 Safe transmit/receive loopback

For an active test:

~~~text
TX SDR or LoRa transceiver
    -> fixed attenuator chain / coax
    -> RX SDR
~~~

Before enabling TX:

- Verify the antenna connector is not connected to an open or incompatible load.
- Verify the attenuation is sufficient for the receiver input.
- Start at the lowest approved TX power.
- Confirm the test frequency and regional plan.
- Use a synthetic payload and synthetic device identity.
- Have a second person confirm the path if the hardware can radiate.

The first TX acceptance test should prove only that the receiver recovers the expected bytes and CRC. It should not inject the frame into a production gateway or network server.

## 7. Optional GUI spectrum path

While **gr-lora-sdr** and **Wireshark** form the primary standardized testing toolchain, operators requiring a visual spectrum/waterfall display can optionally use SDRangel for interactive spectrum observation before capturing traffic for `Wireshark` inspection.

Do not mix SDRangel's bundled dependencies with a hand-built GNU Radio environment as a way to fix a GNU Radio problem. Treat SDRangel and GNU Radio as separate environments.

### 7.2 Receive workflow

1. Start SDRangel with the receive device attached.
2. Select the correct SDR and verify its serial number.
3. Set the center frequency and sample rate to cover the test channel.
4. Start the receiver and confirm the spectrum/waterfall has the expected noise floor.
5. Add the **ChirpChat** LoRa demodulator channel.
6. Set the channel offset, bandwidth, spreading factor, coding rate, preamble, sync word, header, CRC, and low-data-rate optimisation to the transmitter's values.
7. Enable output logging or packet forwarding if the selected build exposes it.
8. Save the SDRangel workspace and copy the configuration into the test artifacts.

The control labels can change between SDRangel releases. Record the application version and rely on the current plugin readme/UI help for exact field semantics.

### 7.3 Transmit workflow

1. Build the receive-only path first.
2. Add a transmitter only after the cabled/shielded path is verified.
3. Add the ChirpChat modulator.
4. Use a synthetic payload and the same PHY metadata as the receiver.
5. Verify the output with a second receiver or the cabled receiver.
6. Stop the transmitter immediately after the acceptance capture.

The GUI is helpful for interactive experiments, but a scriptable gr-lora-sdr flowgraph is usually easier to reproduce in CI-like regression tests.

## 8. LoRa_Craft protocol path

### 8.1 Understand the compatibility boundary

LoRa_Craft's public README lists GNU Radio 3.8 and older gr-lora families. The primary team workflow uses `gr-lora-sdr` for PHY decoding and `Wireshark` for protocol dissection and security testing.

Use one of these two paths:

#### Path A: legacy compatibility experiment

Use the exact GNU Radio and older decoder combination documented by LoRa_Craft in a separate VM so it cannot disturb the current `gr-lora-sdr` installation.

#### Path B: current PHY plus adapter

Use gr-lora-sdr for RF/PHY decoding, then export or pass the raw LoRaWAN PHYPayload and metadata to Wireshark for protocol and security inspection.

Path B is the recommended team architecture because the PHY decoder and protocol parser can be upgraded independently.

### 8.2 Clone and isolate

~~~bash
cd ~/lorawan-lab
git clone https://github.com/PentHertz/LoRa_Craft.git
cd LoRa_Craft
git rev-parse HEAD
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

The repository is older than the current GNU Radio and Python packaging ecosystem. If dependency installation fails, do not force it into the main environment. Capture the failure, inspect requirements.txt, and either use the legacy VM path or create a compatibility container with a pinned Python/GNU Radio version.

### 8.3 Legacy receive/decode flow

The LoRa_Craft README describes this sequence:

1. Generate the required hierarchical blocks from the lora_txrxdecode.grc and lora_rechan.grc flowgraphs.
2. Run the LoRa_MultiSF_decode_to_UDP.grc flowgraph with a supported SDR source.
3. Run the LoRa_Craft decoder script to parse packets arriving on the expected socket.

Because names, paths, and GNU Radio APIs may differ in a modern checkout, verify every file exists before starting:

~~~bash
find . -maxdepth 3 -type f \( -name '*.grc' -o -name '*Decode*.py' \) -print
python3 LoRa_PHYDecode-NG.py --help
~~~

If the parser has no help option, run it only with a saved lab capture or a known local UDP test source. Do not point it at a production gateway port while experimenting.

### 8.4 Define the adapter contract

The adapter between `gr-lora-sdr` and protocol inspectors should preserve bytes and add metadata. A JSON-lines or length-prefixed binary format is easier to replay than an undocumented socket stream:

~~~json
{
  "timestamp_utc": "<ISO-8601 UTC>",
  "frequency_hz": 0,
  "bandwidth_hz": 125000,
  "spreading_factor": 7,
  "coding_rate": "4/5",
  "sync_word": "<LAB_SYNC_WORD>",
  "direction": "uplink",
  "crc_ok": true,
  "phy_payload_hex": "<LAB_PHYPAYLOAD_HEX>"
}
~~~

Adapter acceptance tests:

- The PHYPayload hex string is byte-for-byte identical to the decoder output.
- A CRC failure is not rewritten as a valid frame.
- Direction is explicit; do not infer uplink/downlink from a guessed address.
- The adapter records one frame boundary per record.
- A malformed record is rejected and logged, not silently truncated.
- The adapter can replay a saved file without RF hardware.

### 8.5 Parse a known lab PHYPayload

Start with a known packet from the repository examples or a private lab capture. Never paste a production packet or key into a shared shell history.

Conceptually, the Scapy flow is:

~~~python
from binascii import unhexlify
from layers.loraphy2wan import LoRa

phy_payload_hex = "<LAB_PHYPAYLOAD_HEX>"
packet = LoRa(unhexlify(phy_payload_hex))
packet.show()
~~~

The exact import path and field names are repository-version-specific. The test is successful only if the parsed bytes round-trip without changing the original PHYPayload.

### 8.6 Construct a packet for the lab only

LoRa_Craft documents Scapy construction and helper functions for MIC checks, join-accept encryption/decryption, data-payload decryption, and packet generation. These functions require correct keys and LoRaWAN state. Use them only with synthetic lab keys and a private test server.

The expected workflow is:

1. Define the packet fields in the Scapy layer.
2. Serialize the packet.
3. Compare the serialized bytes with the intended test vector.
4. Calculate or validate the MIC using the lab key and the correct LoRaWAN version/direction.
5. Send only through the shielded/cabled lab path.
6. Record the server's accept/reject decision and the frame counter state.

Do not use a packet crafter to “see what happens” on a live gateway. A correctly formed packet can still trigger a real downlink, join, counter change, or application action.

### 8.7 RN2483-based lab transmission

The LoRa_Craft README shows an RN2483 controller path for point-to-point transmission. This is a radio-modulation path, not automatically a complete LoRaWAN network-server session. The device SKU, regional firmware, frequency, bandwidth, spreading factor, coding rate, and payload framing must match the lab plan.

Before using an RN2483-style device:

- Confirm the regional SKU and legal band.
- Put the device behind the same shielded or attenuated path used for the SDR.
- Use a dummy lab payload.
- Confirm the serial device path and firmware version.
- Verify that point-to-point mode is intended; do not confuse it with a production LoRaWAN join.

If a real LoRaWAN packet is transmitted, the private network server must be the only authorized receiver in the test path and the packet must use synthetic device identities and keys.

## 9. Wireshark evidence & security testing path

### 9.1 Wireshark for protocol inspection and security testing

Wireshark is the primary protocol analyzer for security testing. It is appropriate for inspecting captured packets, gateway backhaul traffic, checking Message Integrity Codes (MIC), analyzing frame counter progressions, and auditing security behaviors. Combine Wireshark PCAPs with `gr-lora-sdr` demodulated payloads to perform end-to-end security verification.

### 9.2 Install and capture

Use the official [Wireshark download page](https://www.wireshark.org/download.html) or the approved OS package. For a server-side Semtech UDP capture, a common evidence command is:

~~~bash
sudo tcpdump -i any -s 0 -w captures/pcap/lab-semtech-udp-$(date -u +%Y%m%dT%H%M%SZ).pcap udp port 1700
~~~

Do not assume that seeing UDP/1700 means the inner LoRaWAN PHYPayload will be automatically dissected. Preserve the PCAP anyway, and use the decoded payload from the PHY/protocol path as the canonical byte record.

### 9.3 Useful display filters

Start with the documented protocol filter:

~~~text
lorawan
~~~

Then use the current [LoRaWAN display-filter reference](https://www.wireshark.org/docs/dfref/l/lorawan.html) for the exact field names supported by the installed Wireshark version. Save the Wireshark version with the capture because field availability changes across releases.

### 9.4 Key and privacy handling

- Prefer captures that contain encrypted application payloads and no keys.
- If decryption is required, use synthetic lab keys.
- Store decrypted exports separately from raw captures.
- Do not commit keys, decrypted payloads, or customer identifiers to this repository.
- Redact DevEUI, JoinEUI, gateway IDs, and payload data before sharing outside the authorized team.

### 9.5 Evidence bundle

For every test, store:

~~~text
captures/
├── iq/<timestamp>-<device>-<params>.cf32 or vendor format
├── decoded/<timestamp>-frames.jsonl
├── pcap/<timestamp>-gateway.pcap
├── logs/<timestamp>-chirpstack.log
├── logs/<timestamp>-laf.log
├── config/<timestamp>-flowgraph.json
└── reports/<timestamp>-test-summary.md
~~~

## 10. LAF installation and passive-first use

### 10.1 What LAF is

The current IOActive repository describes LAF as an alpha LoRaWAN auditing framework. It includes collectors, analyzers, parsers, packet tools, fuzzing helpers, and a Docker Compose setup with a database and pgAdmin.

Use it as a supporting audit and alerting tool, not as the primary decoder or production prevention layer.

### 10.2 Docker installation

~~~bash
cd ~/lorawan-lab
git clone --recurse-submodules https://github.com/IOActive/laf.git
cd laf
git rev-parse HEAD
docker compose up --build
~~~

The upstream README documents a Docker path to avoid manually installing the older Python, Go, and database dependencies. If the repository expects the legacy docker-compose command rather than docker compose, use the Compose version approved for the lab and record it in the report.

Do not expose the default pgAdmin or database ports beyond localhost or the isolated lab network. Change development credentials before any shared use.

### 10.3 Local installation caveat

The repository's local instructions assume older Python and Go dependencies and include a Go shared-library build. Use the local path only when the team needs the packet tools outside the container and has pinned the dependency versions. Otherwise, use the Docker path for the analyzer experiment.

### 10.4 Passive collection

LAF documents collectors for MQTT and Semtech packet-forwarder traffic. Start with a copy of lab traffic:

1. Create a private ChirpStack application and a synthetic device.
2. Subscribe to the private MQTT stream or mirror a private packet-forwarder path.
3. Feed the collector only lab traffic.
4. Confirm that packets are persisted before enabling analyzers.
5. Run parse and analysis options separately.

The exact collector filename can differ between the repository tree and older README text. Check the checkout before running:

~~~bash
find auditing/datacollectors -maxdepth 1 -type f -print
find auditing/analyzers -maxdepth 1 -type f -print
~~~

For MQTT visibility, ChirpStack documents the default uplink topic shape:

~~~bash
mosquitto_sub -h <LAB_MQTT_HOST> -p 1883 \
  -t 'application/<APPLICATION_ID>/device/+/event/up' -v
~~~

The topic is case-sensitive, and the application ID is not the AppEUI/JoinEUI. See the [ChirpStack MQTT integration documentation](https://www.chirpstack.io/docs/chirpstack/integrations/mqtt.html).

### 10.5 Run parse and analysis without brute forcing

The LAF README documents LafProcessData.py options for analysis, parsing, and brute-forcing. Start with analysis and parsing only:

~~~bash
python3 auditing/analyzers/LafProcessData.py -a -p
~~~

Do not enable -b or any key-search option by default. If an authorized lab test specifically requires key-strength validation, create a separate scope document that names:

- The synthetic device and test keys.
- The exact key corpus.
- The allowed time and compute budget.
- The expected output and cleanup method.
- The person who approved the test.

### 10.6 Interpreting LAF alerts

Treat an LAF alert as a lead that must be correlated with raw and server evidence. Examples include:

- Repeated DevNonce for a device.
- Multiple device identities sharing a DevAddr.
- Counter reset without a corresponding join.
- Duplicate packets with identical or suspicious integrity fields.

For each alert, record:

~~~text
alert_id=<...>
first_seen_utc=<...>
last_seen_utc=<...>
device_or_address=<...>
packet_ids=<...>
gateway_ids=<...>
fcnt_values=<...>
mic_status=<valid|invalid|unknown>
chirpstack_disposition=<accepted|rejected|unknown>
operator_interpretation=<...>
~~~

The repository documents some analyses as TODO or alpha-quality. Do not report a missing alert as proof that the network is safe.

## 11. ChirpStack integration points

This repository already contains a separate ChirpStack deployment manual. Use this section only to connect the testing tools to that stack.

### 11.1 Gateway backhaul

For a Semtech UDP packet-forwarder deployment, ChirpStack documents UDP port 1700 as the default gateway bridge port. The gateway and bridge must agree on the destination host and uplink/downlink port. Capture and proxy changes should be made only on the private lab path.

Reference: [ChirpStack gateway configuration](https://www.chirpstack.io/docs/gateway-configuration/index.html).

### 11.2 MQTT events

ChirpStack publishes JSON events over MQTT. For an uplink application:

~~~bash
mosquitto_sub -h <LAB_MQTT_HOST> -p 1883 \
  -t 'application/<APPLICATION_ID>/device/+/event/up' -v
~~~

Use this to correlate:

- devEui and devAddr.
- fCnt and fPort.
- dr and radio metadata.
- data and decoded object values.
- rxInfo gateway data.
- The server event timestamp.

Do not treat the MQTT event as a substitute for the RF capture. It represents a server-side event generated by ChirpStack, not every signal the antenna saw.

### 11.3 Downlink behavior

For Class A lab devices, a downlink is normally sent in the receive window following an uplink. Test queued commands on a synthetic device and record the exact uplink/downlink timeline. Do not use a physical reset as a shortcut during a queued-downlink experiment unless the test explicitly covers join/reset behavior.

## 12. Test sequence

Run the following in order. Each stage should be independently passable.

### Stage 0: baseline and isolation

- [ ] Private application, device, gateway, and synthetic keys exist.
- [ ] Regional plan and channel list are recorded.
- [ ] RF path is shielded or conducted through attenuation.
- [ ] Production gateway and devices are not in the path.
- [ ] Repository commits and tool versions are recorded.

### Stage 1: PHY receive

- [ ] Waterfall shows the expected signal.
- [ ] PHY decoder locks with expected SF/BW/CR/sync settings.
- [ ] CRC status is recorded.
- [ ] Repeated frames produce stable payload bytes.
- [ ] One IQ file and one decoded JSONL file are saved.

### Stage 2: PHY parameter negative tests

Change one parameter at a time:

- [ ] Wrong center frequency.
- [ ] Wrong bandwidth.
- [ ] Wrong spreading factor.
- [ ] Wrong sync word.
- [ ] Wrong header mode.
- [ ] CRC failure or corrupted sample.
- [ ] Low-SNR capture.

Expected result: the decoder should fail clearly, report a bad CRC, or produce no frame. It should not silently present a corrupted frame as valid.

### Stage 3: protocol parse

- [ ] Parse a known JoinRequest test vector.
- [ ] Parse a known JoinAccept test vector.
- [ ] Parse a known uplink data frame.
- [ ] Parse a known downlink data frame.
- [ ] Verify direction explicitly.
- [ ] Verify the original and re-serialized bytes match where applicable.
- [ ] Keep keys out of the default test vector unless decryption is the subject of the test.

### Stage 4: server disposition

Using the private ChirpStack network:

- [ ] Known-good join is accepted.
- [ ] Known-good uplink is accepted and decoded.
- [ ] Invalid MIC is rejected.
- [ ] Frame-counter regression is rejected or handled according to the configured policy.
- [ ] Duplicate gateway reports are deduplicated as expected.
- [ ] A normal Class A downlink is delivered in the expected receive window.

### Stage 5: detection

- [ ] Passive LAF collector receives a lab packet stream.
- [ ] Parser and analyzer results are saved.
- [ ] A repeated or out-of-sequence lab test creates an alert or a documented “not detected” result.
- [ ] The same event is correlated with ChirpStack logs and MQTT events.
- [ ] The report distinguishes “signal observed,” “packet parsed,” “server accepted,” and “alert raised.”

### Stage 6: controlled active test

Only after the previous stages pass:

- [ ] Operator approval recorded.
- [ ] Test window recorded.
- [ ] Shielding/attenuation checked again.
- [ ] Test uses synthetic keys and identities.
- [ ] One packet or one bounded test case is run.
- [ ] Transmitter is stopped and disconnected after the test.
- [ ] Server and device state are restored or destroyed according to the test plan.

## 13. Troubleshooting matrix

| Symptom | Likely layer | Checks |
|---|---|---|
| No spectrum activity | RF/front end | Antenna/cable, center frequency, gain, USB device, regional band, transmitter power |
| Spectrum activity but no decoder output | PHY | BW, SF, sync word, sample rate, frequency offset, header, CRC, low-data-rate optimisation |
| Decoder output changes every run | PHY/capture | Clipping, overload, low SNR, dropped samples, timestamp alignment, wrong decimation |
| Decoder payload is stable but LoRa_Craft parse fails | Adapter/protocol | Remove preamble/header as required, preserve PHYPayload boundaries, confirm byte order and version |
| LoRa_Craft imports fail | Legacy environment | Python version, Scapy version, GNU Radio 3.8 compatibility, missing submodules, separate venv |
| Wireshark shows UDP but not LoRaWAN | Encapsulation | Verify the capture contains a supported LoRaWAN representation; export decoded PHYPayload separately |
| LAF starts but no records appear | Collector/database | Confirm collector port/topic, DB connection, container logs, file paths, and lab traffic |
| LAF reports no alert | Detection/coverage | Check analyzer options and version; correlate raw capture and ChirpStack; alpha code may not implement the case |
| ChirpStack sees no uplink | Gateway/server | UDP 1700 path, gateway ID, region, gateway bridge logs, MQTT connection, application/device identity |
| ChirpStack rejects a known lab frame | Protocol/server | MIC key, direction bit, frame counter, DevAddr, session state, LoRaWAN version, network-server policy |
| Downlink never arrives | Device timing | Class A receive windows, next uplink, RX1/RX2 settings, gateway downlink capability, queued command state |

## 14. Cleanup and rollback

At the end of an active test:

1. Stop `gr-lora-sdr` transmitters and GNU Radio TX flowgraphs.
2. Confirm the RF power output is zero.
3. Save all Wireshark PCAPs and flowgraph logs to the test directory.

## 15. References

- [gr-lora-sdr repository](https://github.com/tapparelj/gr-lora_sdr)
- [Wireshark LoRaWAN display-filter reference](https://www.wireshark.org/docs/dfref/l/lorawan.html)
- [SDRangel repository](https://github.com/f4exb/sdrangel)
- [LoRa_Craft README](https://github.com/PentHertz/LoRa_Craft)
- [IOActive LAF README](https://github.com/IOActive/laf)
- [ChirpStack MQTT integration](https://www.chirpstack.io/docs/chirpstack/integrations/mqtt.html)
- [ChirpStack gateway configuration](https://www.chirpstack.io/docs/gateway-configuration/index.html)
- [LoRaWAN 1.0.4 specification package](https://lora-alliance.org/resource_hub/lorawan-104-specification-package/)
