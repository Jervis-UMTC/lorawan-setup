# 3. Testing, Monitoring, and Software-Only Limitations

Use a staging gateway and approved test device. Never alter the only copy of production evidence to demonstrate tamper detection.

## 3.1 Capture a baseline

Before fault injection record:

```text
Gateway EUI
Gateway OS release
journal implementation version/hash
last local sequence and record hash
last closed segment ID/hash
latest accepted server checkpoint
MQTT bridge state
remote gateway-event collector state
ChirpStack gateway freshness
one accepted application event key
trusted decoder version
latest verification result
```

Do not begin destructive tests when the baseline is already degraded.

## 3.2 Normal connected-path test

Generate one known uplink.

Expected lineage:

```text
sensor
 -> RAK5146
 -> Concentratord
    -> journal record
    -> MQTT Forwarder
 -> local Mosquitto
 -> remote MQTT
 -> gateway MQTT evidence collector
 -> ChirpStack
 -> application event
 -> trusted decoder
 -> TimescaleDB comparison
 -> verification = verified
```

Pass only when one unambiguous lineage exists.

## 3.3 WAN outage and recovery

Disconnect only gateway WAN/backhaul. Keep radio and the Pi powered.

Generate a known set of uplinks.

During outage expect:

```text
Mosquitto queue        grows
journal sequence       grows
journal segments       continue locally
server checkpoint      does not falsely advance
remote gateway events  do not arrive yet
```

Restore WAN.

Pass when:

- MQTT queue drains;
- missing journal segments upload;
- uploaded history extends the last pre-outage checkpoint;
- captured remote gateway events match the journal;
- ChirpStack application events correlate uniquely;
- trusted decoder comparison succeeds;
- final state becomes `verified`;
- duplicate MQTT delivery does not duplicate telemetry/evidence identity.

## 3.4 Reboot during outage

While WAN remains disconnected:

1. generate several uplinks;
2. confirm queue and journal growth;
3. reboot cleanly;
4. generate more uplinks;
5. restore WAN.

Pass when:

- Mosquitto retains queued work;
- journal sequence continues;
- a new boot ID appears;
- hash continuity crosses the reboot;
- server reconciliation accepts both sides of the reboot boundary.

## 3.5 One-byte journal tamper test

Modify one byte in a **copied staging segment**.

Expected:

```text
recomputed record hash != stored record hash
```

Pass when the verifier returns `integrity_failure` and does not rewrite the object.

## 3.6 Record deletion test

Remove one complete record from an isolated fixture.

Pass when sequence/previous-hash checks reject the chain.

Use these classifications carefully:

```text
contradictory chain bytes -> integrity_failure
required whole segment unavailable -> evidence_gap
```

## 3.7 Record reorder test

Swap two complete records in a copied fixture.

Pass when sequence/hash links reject the fixture.

## 3.8 Checkpoint rollback test

First accept a checkpoint at sequence `5000`.

Then present older history ending at `4500` as current.

Pass when the server refuses to move accepted history backward and raises a rollback/security conflict.

Never fix this alert by deleting the newer checkpoint.

## 3.9 Conflicting checkpoint test

Submit the same `(gateway_id,last_sequence)` with a different hash.

Pass when the second request is rejected and the first accepted checkpoint remains unchanged.

## 3.10 Gateway journal vs MQTT mismatch

Use an isolated fixture:

```text
journal PHYPayload digest = A
remote MQTT PHYPayload digest = B
```

Pass when Stage A returns `integrity_failure`.

This models alteration after the journal split and before/inside the remote delivery path.

## 3.11 Node-RED alteration test

Use one staging event whose trusted decoder returns a known value, for example:

```text
27.3 C
```

In an isolated Node-RED test flow/fixture, intentionally store a different normalized value.

Pass when:

- gateway/MQTT lineage can still be valid;
- trusted decoder comparison fails;
- verification becomes `integrity_failure`;
- v2 Fabric sealing/submission is blocked.

Restore the approved flow after the test.

## 3.12 Journal storage-pressure test

In staging, temporarily reduce the evidence budget enough to reach warning/critical behavior without filling the OS filesystem.

Pass when:

- thresholds alert;
- the emergency filesystem reserve survives;
- evidence loss is explicit;
- affected events become `evidence_gap`;
- old unuploaded evidence is not silently overwritten and later described as continuous.

## 3.13 Delivery failure vs journal survival

If the MQTT delivery state is unavailable while the journal remains valid:

```text
journal may still prove what its path observed
but missing MQTT/application lineage prevents a full verified application event
```

Classify the missing downstream evidence appropriately. The journal does not replace delivery.

## 3.14 Journal failure vs MQTT survival

Stop the journal service while MQTT remains healthy.

Expected:

- telemetry delivery continues;
- journal failure alerts;
- affected evidence-selected events remain pending and later become `evidence_gap` under policy;
- v2 Fabric path does not pretend the events were gateway-verified.

This is the default availability-first behavior.

## 3.15 Residual full-root/offline threat

The software-only design cannot completely prevent this theoretical sequence:

```text
server checkpoint at 5000
WAN disconnects
attacker gains full gateway root
attacker rewrites 5001..5900
attacker rebuilds an internally consistent software hash chain
WAN reconnects
```

Independent sensor signatures, another gateway/witness, TPM/secure element, or hardware monotonic state can reduce this threat. The baseline Raspberry Pi software journal cannot make it disappear.

## 3.16 Gateway monitoring

Monitor:

```text
journal service state/restarts
current sequence
open segment ID
last closed segment ID/hash
age since successful checkpoint
unuploaded segment count/bytes
journal storage percent
hash/recovery errors
uploader errors/retries
Mosquitto queue size/limits/free-space reserve
bridge reconnect and drain rate
```

## 3.17 Server monitoring

Monitor:

```text
checkpoint ingest success/conflicts
oldest checkpoint age per gateway
uploaded segment backlog
segment verification failures
gateway MQTT collector lag
unmatched journal records
unmatched gateway MQTT events
pending verification age
evidence_gap count
integrity_failure count
trusted-decoder mismatch count
verifier processing latency
```

## 3.18 Fabric-gate monitoring

Monitor separately:

```text
v2 events waiting for gateway verification
v2 events blocked by evidence_gap
v2 integrity/security conflicts
oldest verified-but-not-sealed event
```

Do not hide evidence backlog inside ordinary Fabric `pending` counts.

## 3.19 Alert priorities

| Condition | Priority | First response |
|---|---|---|
| Journal down while MQTT healthy | High | Restore journal; mark first unjournaled time/sequence as evidence gap |
| Journal storage critical | High | Restore upload path; protect OS reserve; do not blindly delete unuploaded segments |
| Conflicting checkpoint | Critical | Freeze evidence promotion for the gateway and investigate rollback/compromise |
| Record/segment hash mismatch | Critical | Preserve objects; stop v2 evidence promotion; investigate tampering/corruption |
| Journal vs remote MQTT payload mismatch | Critical | Isolate lineage; inspect gateway/forwarder/broker path |
| Trusted decoder vs TimescaleDB mismatch | Critical | Freeze affected evidence; inspect Node-RED flow/version/source bytes |
| Checkpoint stale while gateway online | High | Inspect uploader/auth/API separately from MQTT |
| Evidence gap | High/business-defined | Attempt recovery; never call it verified |

## 3.20 Acceptance matrix

The integration is ready only when:

- normal connected uplinks become `verified`;
- WAN outage/recovery verifies without sequence loss;
- reboot and reboot-during-outage preserve chain continuity;
- one-byte changes are rejected;
- deletion/reorder fixtures are rejected;
- checkpoint rollback/conflict is rejected;
- journal vs remote MQTT mismatch is rejected;
- trusted decoder vs Node-RED/TimescaleDB mismatch is rejected;
- storage overflow creates explicit `evidence_gap` while preserving OS reserve;
- v2 Fabric evidence is not sealed until verification is `verified`;
- dashboards distinguish pending, gap, and failure;
- the residual full-root/offline limitation is documented and accepted or mitigated.
