# Troubleshooting Manual 03: MIC Mismatch & Cryptographic Failure

## 1. Executive Problem Summary

* **Symptom**: ChirpStack logs "invalid MIC", "MIC mismatch", or "authentication failed"; `Join-Request` packets are received by the gateway but rejected by the server; data uplinks are discarded without payload decoding.
* **Impact**: End-nodes fail to join the network or remain completely unauthenticated; no application data reaches database or dashboard.
* **Primary Root Cause**: Mismatch between the cryptographic keys (`AppKey`, `NwkKey`, `NwkSKey`, `AppSKey`), byte endianness error on `DevEUI`/`JoinEUI`, or a LoRaWAN Specification version mismatch (1.0.3 vs 1.0.4 vs 1.1).

---

## 2. Root Cause Analysis & Cryptography

Every LoRaWAN frame contains a 4-byte **Message Integrity Code (MIC)** appended to the end of the `PHYPayload`:
$$\text{MIC} = \text{AES-128-CMAC}(K, B_0 \parallel \text{PHYPayload}[0..N-5])$$
Where $K$ is `NwkSKey` (for data frames) or `AppKey`/`NwkKey` (for Join-Requests).

A MIC failure occurs when:
1. **Wrong Root Keys**: `AppKey` configured in ChirpStack does not match the 128-bit key burned into the end-node firmware.
2. **LoRaWAN Version Misalignment**: LoRaWAN 1.0.x uses a single `AppKey`. LoRaWAN 1.1 splits this into `AppKey` (for `AppSKey`) and `NwkKey` (for `FNwkSIntKey`/`SNwkSIntKey`). Selecting LoRaWAN 1.1 for a 1.0.3 node causes MIC calculation failure.
3. **DevEUI Endianness Swap**: `DevEUI` typed in reverse byte order (Big-Endian vs Little-Endian, e.g. `A84041380189B98F` vs `8FB98901384140A8`).

---

## 3. Diagnostic & Inspection Commands

### Step 1: Check ChirpStack Logs for MIC Errors
~~~bash
docker logs chirpstack | grep -i -E "mic|authentication|invalid"
~~~
*Expected Output*: `invalid MIC, dev_eui: a84041380189B98f, calculated: 0xa1b2c3d4, expected: 0x99887766`.

### Step 2: Validate MIC Cryptography via Wireshark
1. Capture raw frames using `tcpdump` on UDP 1700:
   ~~~bash
   tcpdump -i eth0 -w /tmp/mic_test.pcap port 1700
   ~~~
2. Open `/tmp/mic_test.pcap` in Wireshark.
3. Configure keys under **Preferences** $\rightarrow$ **Protocols** $\rightarrow$ **LoRaWAN**:
   * Add `DevAddr`, `NwkSKey`, `AppSKey`.
4. Inspect the Wireshark tree under `lorawan.mic`:
   * If Wireshark highlights MIC in **Red**, the key or calculation parameters are incorrect.

---

## 4. Step-by-Step Resolution Blueprint

### Action 1: Verify & Re-Burn Root Keys (`AppKey`)
1. Query the node's burned keys via serial AT commands (e.g. Dragino LSN50v2-S31):
   ~~~text
   AT+KEY=?
   ~~~
   *Response*: `KEY: FD 7A 9B 94 88 C1 23 45 67 89 AB CD EF 01 23 45`

2. Copy the exact 32-character hex string to ChirpStack:
   * Go to **ChirpStack UI** $\rightarrow$ **Applications** $\rightarrow$ **Devices** $\rightarrow$ Select Device $\rightarrow$ **Keys (OTAA)**.
   * Paste the 32-character hex string into `Application key (AppKey)`.
   * Click **Save Device Keys**.

### Action 2: Align Device Profile LoRaWAN Version
1. Identify node firmware spec version (Dragino LSN50v2-S31 is **LoRaWAN 1.0.3**).
2. Go to **ChirpStack UI** $\rightarrow$ **Device Profiles** $\rightarrow$ Select Profile.
3. Verify settings:
   * **MAC version**: Select `LoRaWAN 1.0.3` (Do NOT select `1.1.x` unless firmware explicitly supports it).
   * **Regional parameters revision**: Select `RP001 Regional Parameters 1.0.3a` or `RP002`.

### Action 3: Resolve DevEUI / JoinEUI Endianness (MSB vs LSB)
If Join-Requests fail silently:
* Check if software expects **MSB (Most Significant Byte)** or **LSB (Least Significant Byte)**.
* **ChirpStack UI expects MSB**: `A8 40 41 38 01 89 B9 8F`.
* If node utility outputs `8F B9 89 01 38 41 40 A8`, reverse the byte pairs before entering into ChirpStack.

### Action 4: Clean Device Re-Activation
1. In ChirpStack, click **Re-activate Device** or force a new Join.
2. Press the physical **RESET** button on the Dragino end-node or issue:
   ~~~text
   AT+JOIN
   ~~~

---

## 5. Verification & Acceptance Criteria

1. **Successful Join**: ChirpStack logs show `device joined, dev_eui: a84041380189b98f`.
2. **Wireshark MIC Validation**: `lorawan.mic_verified == True` in Wireshark protocol breakdown.
3. **Payload Decryption**: Decrypted application payload fields appear in `lorawan.frmpayload_decrypted`.
