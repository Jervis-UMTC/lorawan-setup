# Sensor Preflight 2 - LoRaWAN, Gateway, and ChirpStack

This preflight proves the radio/network-server path for the **same final EMU-01 build** accepted in Preflight 1.

## Path under test

```text
EMU-01 final sensor cycle
        │
        ▼
46-byte LoRaWAN application payload
        │
        ▼
physical AS923 RF
        │
        ▼
RAK5146
        │
        ▼
Concentratord / MQTT forwarding
        │
        ▼
ChirpStack
        │
        ├─ OTAA identity accepted
        ├─ frame counter valid
        ├─ MIC valid
        └─ payload v2 decoder succeeds
```

A serial `send_started=1` line proves only that the node attempted transmission. It does **not** prove RAK5146 reception or ChirpStack acceptance.

## Step 1 - Confirm gateway/server readiness

Before touching EMU-01, confirm the normal gateway and server preparation already passed.

On the gateway:

```sh
monit status
logread -e chirpstack-concentratord | tail -n 50
logread -e chirpstack-mqtt-forwarder | tail -n 50
logread -e mosquitto | tail -n 50
```

Confirm:

```text
[ ] concentratord is healthy
[ ] MQTT forwarder is healthy
[ ] local Mosquitto is healthy
[ ] expected real Gateway EUI is present
[ ] frozen plain AS923 plan is still configured
[ ] gateway, MQTT prefix, ChirpStack region, device profile, and EMU-01 all agree on plain AS923
```

On the server VM:

```bash
cd /opt/lorawan-lab
docker compose ps
```

Confirm at least the normal MQTT/ChirpStack path is healthy before attempting a join.

## Step 2 - Confirm the ChirpStack device record

In ChirpStack, verify the registered EMU-01 entry uses the intended:

```text
device name = dissertation-emu-01
DevEUI = <LEGIT_DEV_EUI>
JoinEUI/AppEUI = <LEGIT_JOIN_EUI>
activation = OTAA
device class = A
region/profile = plain AS923 (`LORAMAC_REGION_AS923`; ChirpStack/MQTT `as923`)
LoRaWAN MAC/profile version = matches frozen firmware
codec = Agriculture Kit payload v2
```

Do not expose the AppKey in screenshots or evidence files.

**NO-GO if:** the firmware and ChirpStack profile disagree about region, LoRaWAN version, or identity.

## Step 3 - Start evidence capture before the join

Save the preflight UTC start time.

Capture/retain:

```text
EMU-01 serial source log
gateway radio/forwarder log window
ChirpStack device-event/log window
```

Evidence location:

```text
chapter4-results/_preflight/sensor/02-lorawan-chirpstack/
```

## Step 4 - Force/observe a clean OTAA join

Use the frozen firmware's normal restart/join behavior.

Expected sequence:

```text
EMU-01
  │ JoinRequest
  ▼
RAK5146 receives RF
  │
  ▼
ChirpStack receives JoinRequest
  │ credentials/profile accepted
  ▼
JoinAccept generated
  │
  ▼
EMU-01 reports joined
```

Record the join UTC window and relevant non-secret IDs.

### Required proof

```text
[ ] EMU-01 attempted JoinRequest
[ ] RAK5146/gateway path observed the request
[ ] ChirpStack observed the JoinRequest
[ ] JoinAccept/activation succeeded
[ ] EMU-01 reports joined
```

**NO-GO if:** EMU-01 claims a join but the network evidence cannot be correlated, or if a JoinRequest never reaches the gateway.

## Step 5 - Observe at least ten consecutive post-join uplinks

After the successful join, let EMU-01 run normally for at least ten scheduled uplinks.

For each selected sequence record:

```text
test_sequence
source timestamp
source validity bitmap
gateway reception observed yes/no
ChirpStack uplink accepted yes/no
frame counter
decoder success yes/no
```

Do not count a gateway miss as a ChirpStack rejection. If the gateway did not receive an uplink, record it as an RF/path problem for preflight troubleshooting.

## Step 6 - Verify decoder output

For the ten selected uplinks require:

```text
payload_version = 2
payload length accepted = 46 bytes
test_sequence decoded correctly
sensor_validity_bitmap decoded correctly
all expected physical sensor fields present
no codec error
```

Compare the source serial line and decoded object for at least three of the ten sequences field by field.

Expected mapping:

```text
EMU source seq N
      │
      └───────────────┐
                      ▼
ChirpStack decoded seq N

source physical values
      │ scaling/packing
      ▼
decoded physical values
```

Small differences are allowed only when exactly explained by the fixed x100/integer packing rule.

## Step 7 - Check frame/sequence progression

Across the ten accepted uplinks verify:

```text
application test_sequence increases by 1 per scheduled cycle
LoRaWAN frame counter progresses normally
no duplicate decoded application record for one RF uplink
```

Do not require `test_sequence` to equal the LoRaWAN frame counter; they serve different purposes.

## Step 8 - Save ChirpStack preflight result

Create:

```text
chapter4-results/_preflight/sensor/02-lorawan-chirpstack/chirpstack-preflight.txt
```

Record:

```text
OTAA join = PASS/NO-GO
RAK5146 JoinRequest reception proven = yes/no
10 scheduled post-join sequences observed = yes/no
number received at gateway
number accepted by ChirpStack
codec errors = 0/<count>
source-to-decoder comparisons passed = yes/no
unexpected rejoin/reset = yes/no
result = PASS | NO-GO
```

## If this preflight fails

Use the layer where evidence stops:

```text
serial shows TX, gateway sees nothing
  -> RF / antenna / frequency / AS923 / gateway reception

gateway sees frame, ChirpStack does not
  -> forwarding / MQTT / ChirpStack integration

ChirpStack sees JoinRequest, join fails
  -> DevEUI / JoinEUI / AppKey / device profile / MAC settings

uplink accepted, decoder fails
  -> payload version / length / codec / packing
```

Fix only the responsible layer, then repeat this preflight. If firmware/payload code changes, repeat Preflight 1 first.

## Exit condition

Continue to [03-application-data-path-preflight.md](03-application-data-path-preflight.md) only when OTAA and the consecutive ChirpStack uplink check pass.
