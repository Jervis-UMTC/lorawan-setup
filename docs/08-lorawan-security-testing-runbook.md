# LoRaWAN Security Testing Runbook

This runbook is the operational companion to the toolkit brief and setup guide. It is designed for a test lead, RF engineer, and network-server operator working together on an authorized private LoRaWAN lab.

For the incoming RAK5146 SPI / AS923 gateway and WisBlock nodes, complete [09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md) and pass its normal gateway/device acceptance gates before running security tests.

## 1. Test record header

Copy this section into every test report and fill it before starting:

~~~text
Test ID:
Test title:
Owner:
Approver:
Start UTC:
End UTC:
Scope:
Region / channel plan:
LoRaWAN version:
Activation mode:
Network server and commit:
Gateway model / ID:
Device model / synthetic DevEUI:
PHY decoder and commit:
Protocol parser and commit:
Wireshark version:
LAF commit:
RF path:
Shielding / attenuation:
Production systems excluded:
Artifacts directory:
~~~

### Repository handoffs

Use the existing deployment manuals for the network baseline, then use the RF documents for the PHY and security test layers. Do not create a second, conflicting copy of the gateway, device, database, dashboard, or Node-RED setup.

| Need | Use this document | Handoff into this runbook |
|---|---|---|
| Deploy or validate the private ChirpStack, gateway bridge, MQTT, PostgreSQL, Redis, and Docker stack | [01: Master Deployment Guide](./01-master-deployment-guide.md) | Record the server version, gateway ID, device profile, and test tenant in the test record. |
| Work from the Milesight gateway's isolated direct AP | [02: Offline Direct-AP Setup Guide](./02-offline-direct-ap-setup-guide.md) | Record the `192.168.23.0/24` path, gateway `192.168.23.150`, VM `192.168.23.137`, and UDP `1700` endpoint when used. |
| Persist and query decoded device events | [03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md) | Correlate database rows with capture timestamps, gateway events, and protocol-analysis artifacts. |
| Visualize telemetry and security-related metrics | [04: Grafana Integration Guide](./04-grafana-integration-guide.md) | Capture dashboard state or query results as supporting evidence; dashboards do not replace raw evidence. |
| Automate MQTT reactions and alerts | [05: Node-RED Integration Guide](./05-node-red-integration-guide.md) | Record flow version and alert output; keep automated actions disabled unless explicitly in scope. |
| Select the tooling and lab architecture | [06: LoRaWAN RF and Security Toolkit Brief](./06-lorawan-rf-security-toolkit-brief.md) | Confirm whether the test is RF/PHY, protocol, network-server, or detection work. |
| Build and verify the RF-to-protocol bench | [07: LoRaWAN RF and Protocol Testing Setup Guide](./07-lorawan-rf-and-protocol-testing-setup-guide.md) | Copy the SDR model, band, antenna/conducted path, decoder, parser, and TX safety details into the test record. |

## 2. Roles

| Role | Responsibility |
|---|---|
| Test lead | Owns scope, approval, stop conditions, and final report |
| RF operator | Controls SDR, antenna/cable path, frequency, gain, and TX state |
| Protocol analyst | Verifies PHYPayload bytes, LoRaWAN fields, MIC/counter expectations |
| Network-server operator | Verifies ChirpStack, MQTT, gateway bridge, and device state |
| Evidence custodian | Preserves IQ, PCAP, logs, configurations, hashes, and redacted copies |

One person may hold multiple roles in a small lab, but the test lead should still perform an independent pre-TX confirmation.

## 3. Stop conditions

Stop immediately if any of the following occurs:

- A transmitter is not confirmed to be behind the approved shielded or attenuated path.
- The selected frequency, power, or region is not the approved test configuration.
- A production DevEUI, JoinEUI, AppKey, NwkKey, AppSKey, or NwkSKey appears in the working set.
- A frame is being accepted by a production network server.
- The device behavior becomes unsafe or an actuator responds unexpectedly.
- Packet volume exceeds the approved rate or duration.
- The operator cannot identify which process currently owns the transmitter.

## 4. Pre-flight checklist

### Lab and authorization

- [ ] Written scope includes the RF band, physical location, gateways, devices, time window, and allowed actions.
- [ ] Private network-server tenant/application/device exists.
- [ ] Synthetic keys and identifiers are documented in a protected local secret store.
- [ ] Production DNS names, gateway addresses, and MQTT credentials are not in the lab configuration.
- [ ] The test lead has a rollback and cleanup plan.

### Hardware

- [ ] SDR model and serial number match the test record.
- [ ] The lab gateway is a documented Milesight UG65/UG67 or an explicitly approved alternative; it is not being treated as an IQ recorder.
- [ ] The lab end-device is a dedicated Dragino LSN50v2-S31 or synthetic test node, with no production identifiers or keys.
- [ ] The RF receiver, antenna/cable path, center frequency, bandwidth, spreading factor, and sample format are recorded.
- [ ] Antenna or conducted cable path is correct.
- [ ] Attenuators and termination are installed and rated for the expected power.
- [ ] If TX is enabled, the approved RF path is connected before the transmitter process starts; shielding, fixed attenuation, and a 50-ohm termination are available where required.
- [ ] No open RF connector is connected to an active TX chain.
- [ ] Receiver gain is low enough to avoid front-end overload.
- [ ] Device region and channel plan match the network-server profile.

### Software

- [ ] gr-lora_sdr or SDRangel version recorded.
- [ ] LoRa_Craft environment is isolated and its commit recorded.
- [ ] Wireshark version recorded.
- [ ] LAF version/commit recorded if used.
- [ ] ChirpStack and gateway bridge logs are being saved.
- [ ] Time synchronization is working on the SDR host, server, gateway, and capture host.

### Evidence

- [ ] Test directory created.
- [ ] Configuration files copied before changes.
- [ ] Empty baseline capture started.
- [ ] Hashing method selected for final artifacts.

## 5. Evidence handling

### 5.1 Naming convention

Use UTC and a stable test ID:

~~~text
<test-id>_<utc>_<layer>_<source>_<short-description>.<extension>
~~~

Examples:

~~~text
LW-001_20260801T031500Z_phy_grlora_sdr_baseline.jsonl
LW-001_20260801T031500Z_iq_rtlsdr_baseline.cf32
LW-001_20260801T031700Z_pcap_gateway_udp1700.pcap
LW-001_20260801T031900Z_server_chirpstack_events.jsonl
LW-001_20260801T032000Z_report_replay-test.md
~~~

### 5.2 Minimum frame record

~~~json
{
  "test_id": "LW-<ID>",
  "timestamp_utc": "<ISO-8601 UTC>",
  "source": "<gr-lora_sdr|sdrangel|gateway|mqtt|laf>",
  "frequency_hz": 0,
  "bandwidth_hz": 0,
  "spreading_factor": 0,
  "coding_rate": "<...>",
  "sync_word": "<...>",
  "crc_ok": true,
  "phy_payload_hex": "<LAB_BYTES>",
  "lorawan_direction": "<uplink|downlink|join|unknown>",
  "dev_eui": "<SYNTHETIC_OR_REDACTED>",
  "dev_addr": "<SYNTHETIC_OR_REDACTED>",
  "fcnt": null,
  "f_port": null,
  "mic_status": "<valid|invalid|not_checked|unknown>",
  "server_disposition": "<accepted|rejected|not_sent|unknown>",
  "alert_disposition": "<raised|not_raised|not_evaluated>"
}
~~~

Do not populate key fields in this record. If a test requires decryption, reference a protected key identifier rather than copying the key into the evidence file.

### 5.3 Hash artifacts

After the test is complete, hash the original files and store the hash list with the report:

~~~bash
sha256sum captures/iq/* captures/decoded/* captures/pcap/* logs/* > reports/<TEST_ID>-sha256sums.txt
~~~

Keep raw artifacts immutable after hashing. Create redacted copies for sharing.

## 6. Test case library

### RF-001: Known-signal receive baseline

**Objective:** Prove that the RF front end and PHY decoder can recover a known frame.

**Setup:** Receive-only or cabled lab signal; known center frequency, BW, SF, coding rate, sync word, header, and CRC.

**Procedure:**

1. Start IQ recording.
2. Start the decoder.
3. Transmit or replay one bounded known-good lab frame.
4. Stop the transmitter and recording.
5. Compare the decoded payload to the expected byte vector.

**Expected result:** Stable payload and expected CRC result.

**Evidence:** IQ file, decoder output, configuration, expected vector, timestamp.

### RF-002: Parameter mismatch

**Objective:** Confirm that the decoder fails clearly when one PHY parameter is wrong.

**Procedure:** Repeat RF-001 while changing exactly one parameter per run.

**Expected result:** No frame, explicit mismatch, or CRC failure. A wrong parameter must not be silently reported as a valid payload.

**Evidence:** One result per parameter with the changed value highlighted.

### RF-003: Low-SNR and clipping boundary

**Objective:** Characterize the usable signal range.

**Procedure:** Vary attenuation or receiver gain in small, documented steps. Do not increase transmit power beyond the approved limit.

**Expected result:** A documented transition between stable decode, intermittent decode, CRC failure, and no decode.

**Evidence:** SNR/RSSI, gain, attenuation, CRC status, packet success rate.

### PROTO-001: PHYPayload round trip

**Objective:** Prove that the adapter and LoRa_Craft preserve bytes.

**Procedure:**

1. Take a decoded PHYPayload from RF-001.
2. Parse it in LoRa_Craft.
3. Serialize the packet if supported.
4. Compare original and serialized bytes.

**Expected result:** Equal bytes or a documented reason for any representation difference, such as an intentionally removed PHY preamble.

**Evidence:** Original hex, parser output, serialized hex, diff.

### PROTO-002: Join and data frame parsing

**Objective:** Verify the parser understands the test's LoRaWAN version and message types.

**Procedure:** Use known lab vectors for JoinRequest, JoinAccept, uplink, and downlink frames.

**Expected result:** Correct message type, identities, direction, frame counter, port, and MIC location.

**Evidence:** Vector source, parser output, version metadata.

### SEC-001: Invalid MIC rejection

**Objective:** Verify that the private network server rejects a frame with an invalid integrity code.

**Procedure:**

1. Begin with a known-good synthetic lab vector.
2. Modify only the MIC or another field without recomputing it.
3. Submit through the isolated test path.
4. Check gateway bridge, ChirpStack logs, MQTT events, and device state.

**Expected result:** No accepted application event for the invalid frame.

**Evidence:** Original frame, modified frame, server log, absence/presence of event, timestamp correlation.

### SEC-002: Frame-counter regression

**Objective:** Verify server behavior when the same session presents an older counter.

**Procedure:** Use a synthetic device and a known lab session. Submit a frame with a lower counter than the last accepted frame, subject to the device profile and server policy.

**Expected result:** Rejection or explicit policy behavior; no silent duplicate application action.

**Evidence:** Counter timeline, server configuration, log/event result.

### DET-001: Duplicate or replay indicator

**Objective:** Check whether the monitoring path identifies repeated traffic.

**Procedure:**

1. Capture one known lab frame.
2. Re-introduce the same frame only within the isolated test path and within the approved bounded test window.
3. Monitor LAF, ChirpStack logs, gateway events, and MQTT.

**Expected result:** The event is either detected and reported, or the absence of detection is documented as a finding. A duplicate must not be described as an attack solely from the alert text.

**Evidence:** Original and repeated frame, timestamps, counter/MIC, server disposition, alert result.

### DET-002: Join-state and DevNonce behavior

**Objective:** Verify the private network's handling of repeated join material and device resets.

**Procedure:** Use a synthetic device and approved test vectors. Observe whether repeated join values are accepted, rejected, or flagged according to the configured LoRaWAN version and server policy.

**Expected result:** The result is compared to the documented version-specific expectation, not to a generic “join accepted” assumption.

**Evidence:** LoRaWAN version, device state, join records, DevNonce timeline, alert result.

### OPS-001: Class A downlink timing

**Objective:** Verify that a queued downlink reaches the lab device at an expected receive window.

**Procedure:**

1. Queue a harmless synthetic test command.
2. Do not reset the device unless reset behavior is the subject of the test.
3. Wait for the next natural uplink.
4. Capture the uplink, downlink scheduling event, RF downlink, and device response.

**Expected result:** The command is delivered or a clear failure reason is recorded.

**Evidence:** Queue record, uplink timestamp, RX window metadata, downlink event, device response.

## 7. Triage workflow for suspicious traffic

When an alert or unexpected event appears, use this order:

~~~text
1. Preserve raw bytes and timestamps
        |
        v
2. Confirm RF/PHY validity and CRC
        |
        v
3. Parse LoRaWAN fields and direction
        |
        v
4. Compare MIC, FCnt, DevNonce, and join state
        |
        v
5. Correlate gateway, ChirpStack, MQTT, and LAF records
        |
        v
6. Decide: duplicate gateway report, device retransmission,
   server behavior, test artifact, or suspicious event
~~~

### 7.1 Questions to answer

- Did more than one gateway receive the same frame?
- Is the PHY CRC valid?
- Is the LoRaWAN MIC valid, and was the correct direction used?
- Is the frame counter new, repeated, lower, or impossible for the session?
- Did the device join or reset before the counter changed?
- Was the frame accepted by ChirpStack or only observed at the RF layer?
- Did the application receive a decoded event?
- Did LAF classify the event, and is that analyzer implemented in the pinned commit?
- Is the apparent duplicate explained by gateway deduplication or retransmission?

### 7.2 Classification labels

Use one primary classification:

- RF_DECODE_FAILURE
- PHY_PARAMETER_MISMATCH
- PROTOCOL_PARSE_FAILURE
- INVALID_MIC
- COUNTER_POLICY_REJECTION
- GATEWAY_DUPLICATION
- DEVICE_RETRANSMISSION
- JOIN_STATE_CHANGE
- LAF_ALERT_UNCORROBORATED
- SUSPICIOUS_REPLAY_INDICATOR
- UNAUTHORIZED_OR_OUT_OF_SCOPE_ACTIVITY

Do not use “attack confirmed” unless the evidence meets the team's incident-response standard.

## 8. Report template

~~~markdown
# LoRaWAN Security Test Report: <TEST_ID>

## Executive result

- Outcome: pass | fail | partial | inconclusive
- Scope:
- Main finding:
- Safety issues:

## Environment

- Region:
- LoRaWAN version:
- Network server:
- Gateway:
- Device:
- PHY decoder:
- Protocol parser:
- LAF:
- Wireshark:
- RF path:

## Test cases

| ID | Result | Evidence | Notes |
|---|---|---|---|
| RF-001 |  |  |  |
| RF-002 |  |  |  |
| PROTO-001 |  |  |  |
| SEC-001 |  |  |  |
| SEC-002 |  |  |  |
| DET-001 |  |  |  |

## Findings

### Finding <N>: <short title>

- Severity:
- Affected layer:
- First observed UTC:
- Reproduction status:
- Evidence:
- Server disposition:
- Alert disposition:
- Impact:
- Recommendation:
- Retest condition:

## Evidence index

- IQ:
- Decoded frames:
- PCAP:
- ChirpStack logs:
- MQTT export:
- LAF output:
- Configuration:
- SHA-256 manifest:

## Cleanup

- Transmitters stopped:
- Test devices reset or removed:
- Synthetic keys destroyed or archived:
- Private server state restored:
- Production systems touched: no | yes, explain
~~~

## 9. Remediation themes

Depending on findings, recommendations may include:

- Keep OTAA/root keys unique per device and out of source control.
- Use the most appropriate current LoRaWAN version supported by the device and server.
- Enable and validate frame-counter checks according to the device's reset and persistence behavior.
- Avoid ABP unless the lifecycle and security trade-offs are explicitly accepted.
- Protect gateway-to-server backhaul with authenticated and encrypted transport where supported.
- Restrict ChirpStack, MQTT, database, and gateway management interfaces to authorized networks.
- Preserve enough gateway metadata and timestamps to distinguish duplicate reception from replay.
- Treat LAF findings as monitoring evidence and validate them against the network-server state.
- Keep RF test equipment and active transmit paths physically isolated from production.

## 10. References

- [LoRaWAN 1.0.4 specification package](https://lora-alliance.org/resource_hub/lorawan-104-specification-package/)
- [gr-lora_sdr](https://github.com/tapparelj/gr-lora_sdr)
- [LoRa_Craft](https://github.com/PentHertz/LoRa_Craft)
- [IOActive LAF](https://github.com/IOActive/laf)
- [Wireshark LoRaWAN display-filter reference](https://www.wireshark.org/docs/dfref/l/lorawan.html)
- [ChirpStack MQTT integration](https://www.chirpstack.io/docs/chirpstack/integrations/mqtt.html)
- [ChirpStack gateway configuration](https://www.chirpstack.io/docs/gateway-configuration/index.html)
- [OWASP IoT Security Verification Standard communication requirements](https://owasp.org/IoT-Security-Verification-Standard-ISVS/en/V4-Communication_Requirements)
