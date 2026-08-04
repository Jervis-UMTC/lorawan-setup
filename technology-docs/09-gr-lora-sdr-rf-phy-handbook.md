# gr-lora-sdr GNU Radio RF & PHY Demodulation Handbook

> [!WARNING]
> **Hardware Prerequisite & Optional Status**: `gr-lora-sdr` requires external Software Defined Radio (SDR) hardware (e.g., RTL-SDR, HackRF, or USRP) or pre-recorded `.iq` sample files. If SDR hardware is not present in your setup, refer to [10: Wireshark LoRaWAN Security Handbook](./10-wireshark-lorawan-security-handbook.md) and [07: LoRaWAN Protocol and Security Testing Setup Guide](../docs/07-lorawan-rf-and-protocol-testing-setup-guide.md) for the active, software-only Wireshark packet capture toolchain.

## 1. Executive Summary & Overview

`gr-lora-sdr` is an open-source, fully functional GNU Radio 3.10 out-of-tree (OOT) module developed by the EPFL Telecommunication Circuits Laboratory. It provides a complete Software Defined Radio (SDR) implementation of the LoRa Physical (PHY) layer, supporting both receiver (RX) and transmitter (TX) chains.

Within this repository's operational architecture, `gr-lora-sdr` serves as an optional tool for low-level RF signal acquisition, modulation/demodulation, parameter sweeps, and physical-layer security testing when an SDR hardware receiver is connected. Unlike commercial LoRaWAN gateways (such as the Milesight UG65) which process received packets through hardware ASICs (SX1302/SX1303 chipsets) and output pre-parsed Semtech UDP frames, `gr-lora-sdr` operates directly on raw In-phase/Quadrature (IQ) radio frequency samples. This granular control allows engineers to:


- Inspect and analyze raw LoRa RF signals over the air (OTA) or across conducted coaxial cables.
- Demodulate non-standard or custom LoRa PHY payloads where spreading factor (SF), bandwidth (BW), coding rate (CR), or preamble settings differ from default network parameters.
- Conduct controlled RF transmission and security replay experiments in shielded lab environments.
- Export raw decoded `PHYPayload` bytes and signal metadata (RSSI, SNR, carrier frequency offset) to downstream protocol analysis engines such as Wireshark and ChirpStack.

---

## 2. Technical Architecture & PHY Layer Specifications

### 2.1 Block Architecture Overview

`gr-lora-sdr` provides C++ C++ / Python hierarchical blocks for GNU Radio 3.10. The system processing flow is divided into distinct receive and transmit pipelines:

~~~text
========================================================================================
                               RECEIVE (RX) PIPELINE
========================================================================================
 [ SDR Source / IQ File ]
           |
           v
 [ Clock & Frequency Synchronization ]  --> Corrects Carrier Frequency Offset (CFO) & Sampling Clock Offset (SCO)
           |
           v
 [ De-chirping & FFT ]                  --> Multiplies IQ by down-chirp & computes FFT to extract symbol bins
           |
           v
 [ Gray Demapping & De-interleaving ]   --> Maps FFT peak indices to Gray-coded bits and de-interleaves matrix
           |
           v
 [ Hamming FEC Decoding ]               --> Decodes Hamming(8,4), Hamming(7,4), Hamming(6,4), or Hamming(5,4)
           |
           v
 [ De-whitening / De-scrambling ]       --> XORs payload with LoRa pseudo-random whitening sequence
           |
           v
 [ Payload CRC & Header Parsing ]       --> Validates PHY Header CRC and Payload CRC (if present)
           |
           v
 [ Raw Byte Output / Message Port ]     --> Emits decoded PHYPayload hex bytes & metadata (SF, BW, CR, RSSI)

========================================================================================
                              TRANSMIT (TX) PIPELINE
========================================================================================
 [ Raw Bytes Input / Message Port ]
           |
           v
 [ Whitening / Scrambling ]            --> Applies LoRa pseudo-random whitening sequence to payload bytes
           |
           v
 [ Hamming FEC Encoding ]               --> Adds Hamming redundancy bits according to selected Coding Rate (CR)
           |
           v
 [ Interleaving & Gray Mapping ]        --> Interleaves matrix and maps binary words to Gray-coded symbols
           |
           v
 [ Modulator & Chirp Generator ]        --> Synthesizes continuous-phase up-chirps modulated by symbol values
           |
           v
 [ Preamble & Sync Word Insertion ]     --> Prepends programmable preamble chirps, sync chirps, and frame sync
           |
           v
 [ SDR Sink / IQ File / Transmitter ]
========================================================================================
~~~

### 2.2 Configurable Modulation Parameters

`gr-lora-sdr` exposes the full set of LoRa Physical layer parameters:

| Parameter | Identifier | Supported Options | Description & Impact |
|---|---|---|---|
| **Spreading Factor** | `SF` | SF7, SF8, SF9, SF10, SF11, SF12 | Number of chips per symbol ($2^{SF}$). Higher SF increases receiver sensitivity and range, but decreases data rate and increases time-on-air (ToA). |
| **Bandwidth** | `BW` | 125 kHz, 250 kHz, 500 kHz | Signal bandwidth. 125 kHz is standard for AS923 / EU868 / US915 uplinks. |
| **Coding Rate** | `CR` | CR 4/5 (1), CR 4/6 (2), CR 4/7 (3), CR 4/8 (4) | Forward Error Correction (FEC) rate. Higher CR adds redundancy to recover corrupted bits in noisy environments. |
| **Sync Word** | `Sync Word` | `0x12` (Private), `0x34` (Public LoRaWAN) | Frame synchronization byte. Standard public LoRaWAN networks use `0x34`; private RF networks use `0x12` or custom values. |
| **Header Mode** | `Header` | Explicit (Variable), Implicit (Fixed) | Explicit mode includes a physical header specifying payload length, CR, and payload CRC. Implicit mode omits the header for fixed-length transmissions. |
| **Payload CRC** | `CRC` | Enabled (True), Disabled (False) | Appends a 2-byte CRC to the payload. Uplink frames typically require Payload CRC; downlinks omit it. |
| **Low Data Rate Opt** | `LDRO` | Auto, Enabled, Disabled | Mandatory when symbol duration exceeds 16ms (e.g., SF11/12 at 125 kHz) to mitigate frequency drift. |

---

## 3. System Requirements & Prerequisites

### 3.1 Supported Operating Systems
- **Ubuntu 22.04 LTS (Jammy Jellyfish)** or **Ubuntu 24.04 LTS (Noble Numbat)** x86_64
- **GNU Radio 3.10.x** (Native system build or Conda build)

### 3.2 System Dependencies
The following packages must be installed prior to compiling `gr-lora-sdr`:

~~~bash
sudo apt update
sudo apt install -y \
    gnuradio \
    gnuradio-dev \
    git \
    cmake \
    build-essential \
    g++ \
    libboost-all-dev \
    libvolk2-dev \
    libuhd-dev \
    pybind11-dev \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    wireshark \
    tshark \
    rtl-sdr \
    librtlsdr-dev
~~~

---

## 4. Installation & Build Guide

### 4.1 Method A: Native System Build (Recommended for Ubuntu Hosts)

Execute the following commands to build and install `gr-lora-sdr` into the system path:

~~~bash
# 1. Create workspace directory
mkdir -p ~/lorawan-lab
cd ~/lorawan-lab

# 2. Clone repository
git clone https://github.com/tapparelj/gr-lora_sdr.git gr-lora-sdr
cd gr-lora-sdr

# 3. Create build directory
mkdir build
cd build

# 4. Configure with CMake
cmake ..

# 5. Compile with multi-core parallelism
make -j"$(nproc)"

# 6. Install to system prefix (/usr/local)
sudo make install

# 7. Refresh dynamic linker bindings
sudo ldconfig
~~~

### 4.2 Method B: Conda Environment Build (Recommended for Isolated Environments)

If using Anaconda or Miniconda:

~~~bash
# 1. Create directory and clone
mkdir -p ~/lorawan-lab
cd ~/lorawan-lab
git clone https://github.com/tapparelj/gr-lora_sdr.git gr-lora-sdr
cd gr-lora-sdr

# 2. Create and activate Conda environment using project manifest
conda env create -f environment.yml
conda activate gr310

# 3. Build inside active Conda environment
mkdir build
cd build
cmake .. -DCMAKE_INSTALL_PREFIX="$CONDA_PREFIX"
make -j"$(nproc)"
make install
~~~

---

## 5. Verification & Troubleshooting Blueprint

### 5.1 Verification Checklist

1. **Python Binding Test**:
   Verify that Python can import the compiled C++ bindings:
   ~~~bash
   python3 -c "import lora_sdr; print('gr-lora-sdr C++ bindings loaded successfully!')"
   ~~~

2. **Upstream Functionality Check**:
   Run the loopback functionality check script:
   ~~~bash
   cd ~/lorawan-lab/gr-lora-sdr
   python3 examples/tx_rx_functionality_check.py
   ~~~

### 5.2 Common Issues & Resolutions

#### Issue 1: `gr-lora-sdr` Blocks Missing in GNU Radio Companion (GRC)
- **Symptom**: Opening `gnuradio-companion` shows no "LoRa" or "lora_sdr" category in the block tree.
- **Root Cause**: GRC search path does not include `/usr/local/share/gnuradio/grc/blocks`.
- **Resolution**: Create or edit `~/.gnuradio/config.conf`:
  ~~~ini
  [grc]
  local_blocks_path = /usr/local/share/gnuradio/grc/blocks
  ~~~

#### Issue 2: `QApplication / QWidget` Qt Initialization Error
- **Symptom**: Launching GRC yields `Fatal Python error: Aborted` or `Must create QApplication before QWidget`.
- **Root Cause**: Conflict between system Qt libraries and Conda Qt packages.
- **Resolution**: Run GRC explicitly using system Python:
  ~~~bash
  conda deactivate
  /usr/bin/gnuradio-companion
  ~~~

#### Issue 3: `ImportError: libgnuradio-lora_sdr.so: cannot open shared object file`
- **Symptom**: Python script fails on import with missing shared library.
- **Root Cause**: System dynamic linker cache has not registered `/usr/local/lib`.
- **Resolution**:
  ~~~bash
  echo "/usr/local/lib" | sudo tee /etc/ld.so.conf.d/gnuradio.conf
  sudo ldconfig
  ~~~

---

## 6. SDR Hardware Setup & Safety Controls

### 6.1 Hardware Device Discovery
Connect your SDR receiver/transceiver via USB and verify device recognition:

- **RTL-SDR**:
  ~~~bash
  rtl_test -t
  ~~~
- **Ettus USRP**:
  ~~~bash
  uhd_find_devices
  uhd_usrp_probe
  ~~~
- **HackRF One**:
  ~~~bash
  hackrf_info
  ~~~

### 6.2 Mandatory RF Safety Rules for Transmission
When performing transmit experiments with `gr-lora-sdr`:

1. **Conducted Cable Path**: Connect the SDR TX output directly to the receiver or gateway via coaxial cables with inline 50-ohm attenuators (minimum 20dB - 30dB attenuation). Never transmit directly into an amplifier or open port.
2. **Shielded Box Enclosure**: If radiating over the air, place the TX SDR and lab node inside a Faraday RF shielding box to prevent unintended interference with public operational LoRaWAN networks.
3. **Dummy Keys & Synthetic Identifiers**: Never use production `AppKey`, `NwkSKey`, or Join EUIs during active RF tests.

---

## 7. Python Scriptable Receive & Transmit Workflows

### 7.1 Scriptable LoRa Receiver Script

Save the following code as `~/lorawan-lab/scripts/lora_rx_receiver.py`:

~~~python
#!/usr/bin/env python3
import time
from gnuradio import gr, blocks, osmosdr
import lora_sdr

class LoRaReceiver(gr.top_block):
    def __init__(self, freq=923.2e6, sf=7, bw=125e3, cr=1, gain=30):
        super(LoRaReceiver, self).__init__("LoRa RX Receiver")

        # SDR Source (RTL-SDR / HackRF / USRP)
        self.src = osmosdr.source(args="numchan=1")
        self.src.set_sample_rate(1e6)
        self.src.set_center_freq(freq, 0)
        self.src.set_gain(gain, 0)

        # gr-lora-sdr Receiver Block
        self.lora_rx = lora_sdr.lora_sdr_rx(
            samp_rate=1e6,
            bw=int(bw),
            sf=sf,
            cr=cr,
            has_crc=True,
            impl_head=False,
            ldro=False,
            sync_word=0x34 # 0x34 for Public LoRaWAN
        )

        # Message Debug Sink (Prints decoded bytes to console)
        self.msg_sink = blocks.message_debug()

        # Connect Block Graph
        self.connect(self.src, self.lora_rx)
        self.msg_connect((self.lora_rx, "out"), (self.msg_sink, "print"))

if __name__ == "__main__":
    print("[+] Starting gr-lora-sdr RX Flowgraph (923.2 MHz, SF7, BW125kHz)...")
    tb = LoRaReceiver()
    tb.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[-] Stopping Receiver Flowgraph...")
        tb.stop()
        tb.wait()
~~~

### 7.2 Scriptable Controlled Transmit Script

Save the following code as `~/lorawan-lab/scripts/lora_tx_transmitter.py`:

~~~python
#!/usr/bin/env python3
import time
import pmt
from gnuradio import gr, blocks, osmosdr
import lora_sdr

class LoRaTransmitter(gr.top_block):
    def __init__(self, freq=923.2e6, sf=7, bw=125e3, cr=1, tx_gain=10):
        super(LoRaTransmitter, self).__init__("LoRa TX Transmitter")

        # gr-lora-sdr Transmitter Block
        self.lora_tx = lora_sdr.lora_sdr_tx(
            samp_rate=1e6,
            bw=int(bw),
            sf=sf,
            cr=cr,
            has_crc=True,
            impl_head=False,
            ldro=False,
            sync_word=0x34
        )

        # SDR Sink (HackRF / USRP / LimeSDR)
        self.sink = osmosdr.sink(args="numchan=1")
        self.sink.set_sample_rate(1e6)
        self.sink.set_center_freq(freq, 0)
        self.sink.set_gain(tx_gain, 0)

        self.connect(self.lora_tx, self.sink)

    def send_phy_payload(self, hex_payload):
        payload_bytes = bytes.fromhex(hex_payload)
        pmt_msg = pmt.cons(pmt.PMT_NIL, pmt.init_u8vector(len(payload_bytes), list(payload_bytes)))
        self.lora_tx.to_basic_block()._post(pmt.intern("in"), pmt_msg)
        print(f"[+] Transmitted PHYPayload ({len(payload_bytes)} bytes): {hex_payload}")

if __name__ == "__main__":
    print("[+] Initializing gr-lora-sdr TX Flowgraph...")
    tb = LoRaTransmitter()
    tb.start()
    time.sleep(1)

    # Example Synthetic Uplink Frame (MType=Unconfirmed Data Up, DevAddr=01020304)
    test_frame = "4004030201000100018593a2b1"
    tb.send_phy_payload(test_frame)

    time.sleep(2)
    tb.stop()
    tb.wait()
    print("[+] Transmission Complete.")
~~~

---

## 8. Summary & Reference Matrix

`gr-lora-sdr` delivers the raw physical-layer visibility required for serious RF security auditing and signal validation. Combined with Wireshark for protocol dissection, it forms the foundation of this repository's security testing methodology.

- **Primary Repository**: [github.com/tapparelj/gr-lora_sdr](https://github.com/tapparelj/gr-lora_sdr)
- **Toolkit Brief**: [06: LoRaWAN RF and Security Toolkit Brief](../docs/06-lorawan-rf-security-toolkit-brief.md)
- **Setup Guide**: [07: LoRaWAN RF and Protocol Testing Setup Guide](../docs/07-lorawan-rf-and-protocol-testing-setup-guide.md)
- **Security Runbook**: [08: LoRaWAN Security Testing Runbook](../docs/08-lorawan-security-testing-runbook.md)
