# Execution 4. LoRaWAN Replay and Spoofing

Perform this only on the isolated/authorized LoRaWAN test environment.

## Required design

```text
Replay:
  10 new legitimate control uplinks
  10 received replays of older accepted uplinks

Spoofing:
  10 genuine control uplinks
  10 received forged uplinks with invalid MIC

Total counted attempts: 40
```

An attack transmission counts only when the gateway actually receives the RF frame.

## Equipment

```text
RAK4631 EMU-01 registered full physical-sensor OTAA node
RAK5146 gateway
RAK4631 SEC-02 raw-RF security test node
ChirpStack gateway/frame logging
server MQTT/application/database/Fabric logs
```

Keep normal frame-counter validation enabled. Do not disable security checks to make the attack easier.

## What this test proves

Replay and spoofing are separate conditions:

```text
Replay   -> exact old legitimate LoRaWAN bytes are transmitted again after the legitimate counter has advanced.
Spoofing -> a frame looks like the legitimate device at the address level but cannot authenticate because its MIC is invalid.
```

The gateway is not the security decision point. It may receive both frames. The security result is whether ChirpStack turns them into accepted application uplinks.

## Before the first counted attempt

1. Run the Execution 01 preflight.
2. Confirm EMU-01 is joined and stable.
3. Confirm SEC-02 contains no legitimate AppKey/session keys.
4. Perform one **uncounted** raw-RF rehearsal from SEC-02 and prove RAK5146 reception.
5. Confirm gateway evidence exposes enough information to save the raw PHYPayload and RF parameters from a legitimate uplink.
6. Create `replay-spoofing/trial-results.csv`.
7. Keep the gateway and ChirpStack log captures running for the complete 40-attempt group.

If step 4 or 5 fails, the counted test is blocked.

## Part A - Replay test

### Step A1 - Create a replay trial folder and capture one legitimate uplink

For each replay trial create a separate folder, for example:

```text
replay-R01/
replay-R02/
...
replay-R10/
```

For each trial:

1. Let EMU-01 send a new legitimate physical-sensor uplink and record its deterministic `test_sequence`.
2. Confirm the gateway receives it.
3. Confirm ChirpStack accepts it.
4. Confirm it reaches Node-RED and TimescaleDB.
5. When selected for Fabric, confirm the normal outbox/Fabric result.
6. Record:

```text
raw PHYPayload
DevAddr
frame counter
frequency
data rate / spreading factor / bandwidth
reception time
gateway EUI
source event key
```

Save the capture only in the protected test-result directory.

This legitimate message is the control for that replay trial.

### Step A2 - Advance the legitimate frame counter

Allow EMU-01 to transmit at least three additional uplinks. Confirm both `test_sequence` and the LoRaWAN frame counter advance beyond the captured value.

This makes the captured frame clearly old.

### Step A3 - Retransmit the captured frame

Using SEC-02 in the raw LoRa P2P transmit mode prepared in [Sensor Preparation](../preparation/sensor/01-configure-rak4631-emulators.md), retransmit the **same captured LoRaWAN PHYPayload bytes** using the captured/legal RF parameters required for the gateway to receive it.

Transmit in a quiet gap between EMU-01's scheduled 15-second uplinks when practical so an RF collision does not make the trial ambiguous. Do not stop frame-counter validation or change ChirpStack settings.

Do not rebuild, decrypt, re-encrypt, or modify the replay PHYPayload. Do not alter ChirpStack frame-counter settings. SEC-02 must not contain EMU-01's legitimate AppKey or session keys.

### Step A4 - Prove RF reception

Check the gateway/gateway-frame evidence.

If the RAK5146 did not receive the replay transmission, mark the attempt **invalid and repeat it**. A missed RF transmission is not replay rejection.

### Step A5 - Prove downstream rejection

For a valid received replay, verify all of these:

```text
gateway received replay = yes
new ChirpStack application uplink = no
MQTT/Node-RED accepted event = no
new TimescaleDB row from replay = no
new Fabric transaction from replay = no
```

Record the ChirpStack rejection/retransmission evidence and decision time when timestamps permit.

Repeat until there are **10 legitimate controls and 10 received replay attempts**.

---

## Part B - Spoofing / invalid-MIC test

### Step B1 - Generate a genuine control uplink

For each trial, let EMU-01 transmit its normal physical-sensor payload and retain the deterministic `test_sequence` as part of the control evidence.

Confirm:

```text
gateway receives
ChirpStack authenticates
application event exists
TimescaleDB record exists
```

Repeat for 10 genuine controls.

### Step B2 - Prepare a forged frame

For every spoofing trial, retain both values/files:

```text
original captured PHYPayload
modified spoofing PHYPayload
```

The modified fixture must preserve the controlled legitimate device address while changing protected bytes or the MIC such that the original legitimate MIC is no longer valid. Do not recompute a valid MIC and do not provision SEC-02 with the legitimate session key.

Before transmission, record which byte/field was intentionally changed and verify the final MIC was not replaced with a newly valid MIC.

Use the controlled spoofing fixture plus SEC-02 raw transmit mode to create/transmit a test uplink that:

```text
uses the legitimate device address for the controlled test device
contains controlled modified MACPayload / encrypted application bytes representing forged content
uses a MIC that was not recomputed with the legitimate session key
uses RF parameters the gateway can receive
```

SEC-02 must not contain EMU-01's legitimate network session key. The purpose is to prove that a frame that looks like the device at the address level still fails LoRaWAN authentication. Because an outsider without the session keys cannot encrypt a chosen meaningful application value correctly, do not claim that SEC-02 produced a valid semantic temperature/soil reading; claim only the controlled address-impersonation / modified-frame condition that ChirpStack must reject.

### Step B3 - Transmit and prove gateway reception

Transmit the forged frame in the authorized test environment.

If the gateway does not record reception, do not count the attempt. Correct RF parameters and repeat.

### Step B4 - Prove ChirpStack rejection

For each received forged frame verify:

```text
gateway reception = yes
ChirpStack accepted application uplink = no
MIC/authentication rejection evidence = yes
MQTT/Node-RED accepted event = no
TimescaleDB row = no
Fabric transaction = no
```

Repeat until **10 received forged attempts** are recorded.

## Database check

For every attack trial, use its time range, DevEUI, frame-counter/source identity, or controlled test marker to confirm no corresponding accepted row was inserted.

Example inspection:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,dev_eui,f_cnt FROM telemetry.uplinks WHERE dev_eui='<TEST_DEV_EUI>' ORDER BY time DESC LIMIT 30;"
```

Also inspect recent outbox rows:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,status,fabric_tx_id,created_at FROM telemetry.fabric_outbox ORDER BY created_at DESC LIMIT 30;"
```

## Required CSV fields

```text
test
condition
trial
control_test_sequence
gateway_received
chirpstack_accepted
chirpstack_rejected
reached_mqtt_node_red
database_record_created
fabric_transaction_created
false_acceptance
false_rejection
decision_time_seconds
evidence_reference
```

## After each attack trial

Before moving to the next trial:

1. write the CSV row immediately;
2. save the matching gateway reception reference;
3. save the matching ChirpStack decision reference;
4. query the database/outbox for accidental propagation;
5. classify the attempt PASS, FAIL, or INVALID;
6. if INVALID, keep the evidence and rerun under a new attempt ID;
7. confirm a normal EMU-01 uplink still succeeds before continuing if the failure might indicate a broken testbed rather than attack rejection.

## Pass condition

```text
40 counted attempts exactly
all legitimate controls accepted
all 10 received replay frames rejected before application processing
all 10 received invalid-MIC frames rejected before application processing
zero attack-created database rows
zero attack-created Fabric transactions
```

Continue to [Execution 05 - Data Integrity](05-data-integrity.md).
