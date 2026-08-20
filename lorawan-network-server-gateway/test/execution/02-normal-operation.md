# Execution 2. Normal-Operation Performance

Use this test to establish the baseline before security, flooding, or outage experiments.

## Required design

```text
Runs:             3
Duration per run: 30 minutes
EMU-01 interval:  15 seconds
Expected readings: about 120 per run
Attack traffic:   none
Service failures: none
WAN interruption: none
```

## What this test proves

This is the reference condition for every later comparison. It answers:

```text
When nothing is intentionally wrong, how reliably and quickly does legitimate EMU-01 data travel through the system, and how much resource does the testbed use?
```

Do not treat this as a warm-up. These three runs are counted research data.

## Before run 1

Complete [Execution 01 - Common Run Preparation](01-common-run-preparation.md), then confirm:

```text
[ ] gateway acceptance passed
[ ] server seven-service stack passed
[ ] EMU-01 is joined and stable at 15 seconds
[ ] SEC-02 is idle/off
[ ] EMU-01 serial capture works
[ ] server resource capture works
[ ] gateway resource capture works when required by the research table
[ ] one control event reached TimescaleDB
[ ] one selected control event has confirmed Fabric evidence
[ ] no flood listener or integrity-test flow is enabled
[ ] no WAN block is active
```

If any item fails, repair it before starting the 30-minute clock.

## 1. Preflight

Repeat the short preflight from Execution 01 immediately before each of the three runs.

Confirm one normal EMU-01 physical-sensor uplink can reach:

```text
Gateway -> ChirpStack -> Node-RED -> TimescaleDB -> Fabric outbox -> OpenBao -> Fabric confirmed
```

Do not begin a counted run when one layer is already failing.

## 2. Record the physical sensor transmission source

Use the EMU-01 serial evidence log from [Sensor Preparation](../preparation/sensor/01-configure-rak4631-emulators.md) as the primary transmission-source record. The packet-delivery denominator is the number of scheduled legitimate EMU-01 transmission attempts in the counted window, cross-checked against `test_sequence` and the LoRaWAN frame-counter evidence.

Before each run record:

```text
run_id
EMU-01 Device EUI
EMU-01 firmware/build identifier
payload contract = Agriculture Kit physical-sensor v2 (46 bytes)
first expected test_sequence
first expected frame counter
sensor-node interval = 15 s
run start UTC
```

The EMU-01 sensor source log is authoritative for sequence assignment, sampled physical values, and sensor validity, but not automatically for cross-host UTC latency. If the chosen EMU-01 timestamp point is not proven synchronized/correlated with the server, do not invent sensor-to-database latency. Use a clearly named gateway/ChirpStack-to-database latency instead and document that change in the results.

## 3. Start result capture

```bash
RUN_ID=baseline-run-1
RUN_DIR="$HOME/chapter4-results/baseline/$RUN_ID"
mkdir -p "$RUN_DIR"
date -u +%Y-%m-%dT%H:%M:%SZ | tee "$RUN_DIR/start-utc.txt"
```

Start the resource logger from [Execution 01](01-common-run-preparation.md).

Save initial database counts:

```bash
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -c "SELECT count(*) FROM telemetry.uplinks;" \
  > "$RUN_DIR/uplink-count-before.txt"

docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -c "SELECT count(*) FROM telemetry.fabric_outbox;" \
  > "$RUN_DIR/outbox-count-before.txt"
```

## 4. Run for exactly 30 minutes

Use the following operator sequence for **each** run:

```text
1. Create RUN_ID and RUN_DIR.
2. Start EMU-01 serial source capture.
3. Start server resource/network capture.
4. Start gateway resource capture when required.
5. Save database/outbox counts before the run.
6. Confirm the next EMU-01 sequence is visible.
7. Record RUN_START_UTC.
8. Start the 30-minute counted window.
9. Do not touch the testbed during the window except to observe non-invasively.
10. At 30 minutes record RUN_END_UTC.
11. Stop all captures.
12. Export uplinks/Fabric/log evidence.
13. Check duplicates, source-sequence continuity, service restarts, and OOM evidence.
14. Mark the run PASS, FAIL, or INVALID before moving to the next run.
```

Allow only registered EMU-01 in its frozen normal firmware/mode and the normal authorized services to operate. SEC-02 must remain idle/powered off.

Do not during the run:

- change Node-RED flows;
- restart containers;
- run database backup/restore;
- run attack generators;
- disconnect the WAN;
- run any unrelated infrastructure or dashboard workload.

Record any EMU-01 `send_started=0`, reset, rejoin, or other source-side transmission failure separately. Do not remove it from the transmission denominator simply because no database row resulted.

## 5. Stop capture

At the end:

```bash
date -u +%Y-%m-%dT%H:%M:%SZ | tee "$RUN_DIR/end-utc.txt"
```

Stop the resource logger and save logs using [Execution 01](01-common-run-preparation.md).

## 6. Export the accepted uplinks

Replace the placeholders with the exact run boundaries:

```bash
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At -F ',' \
  -c "SELECT event_key,time,received_at,dev_eui,gateway_id,f_cnt,payload_json->>'test_sequence' AS test_sequence,rssi_dbm,snr_db FROM telemetry.uplinks WHERE dev_eui='<TEST_DEV_EUI>' AND time >= '<RUN_START_UTC>' AND time < '<RUN_END_UTC>' ORDER BY time;" \
  > "$RUN_DIR/uplinks.csv"
```

Check duplicates:

```bash
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,count(*) FROM telemetry.uplinks WHERE dev_eui='<TEST_DEV_EUI>' AND time >= '<RUN_START_UTC>' AND time < '<RUN_END_UTC>' GROUP BY event_key,time HAVING count(*) > 1;" \
  > "$RUN_DIR/duplicate-check.txt"
```

Required result: zero duplicate rows.

## 7. Export Fabric results

```bash
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At -F ',' \
  -c "SELECT event_key,status,digest_sha256,fabric_tx_id,submitted_at,committed_at FROM telemetry.fabric_outbox WHERE created_at >= '<RUN_START_UTC>' AND created_at < '<RUN_END_UTC>' ORDER BY created_at;" \
  > "$RUN_DIR/fabric.csv"
```

A transaction counts as successful only when `status='confirmed'` and the commit is valid. A transaction ID by itself is not success.

## 8. Calculate the required measures

### Packet-delivery rate

```text
PDR = unique legitimate packets accepted by ChirpStack
      ------------------------------------------------ x 100
                  legitimate transmission attempts from EMU-01
```

Use unique frame counters/event identities. Do not count a duplicate MQTT delivery twice.

### End-to-end latency

For each matched record:

```text
latency = database storage time - trustworthy/correlated EMU-01 transmission time
```

Match by Device EUI plus frame counter or another stable record identifier.

Report:

```text
mean
standard deviation
minimum
maximum
```

### Fabric transaction success rate

```text
TSR = valid confirmed Fabric transactions
      ----------------------------------- x 100
            Fabric transactions submitted
```

### System throughput

```text
throughput = unique accepted/stored EMU-01 records / 30 minutes
```

Report records per minute.

### CPU and memory

Use `docker-stats.csv` from the run. Report server-container utilization and, when collected, gateway CPU/memory separately. Do not describe server-VM resource use as Raspberry Pi resource use.

## 9. Validate the run before repeating

Do not assume `120` is the denominator merely because 30 minutes elapsed. Use the EMU-01 source log to count the scheduled transmission attempts that actually fall inside the recorded run window.

Before marking the run valid, compare:

```text
source attempts from EMU-01
unique ChirpStack/application records
unique TimescaleDB rows
Fabric submissions
confirmed Fabric commits
missing test_sequence values
duplicate event keys/frame counters
unexpected service restarts/OOM events
```

A source-side send failure remains part of the transmission-attempt denominator when it was a scheduled attempt. An MQTT redelivery must not be counted as a second LoRaWAN packet.

Write the classification to `run-status.txt`.

## 10. Repeat

Repeat the entire procedure as:

```text
baseline-run-1
baseline-run-2
baseline-run-3
```

Keep the configuration unchanged.

## Pass condition

A baseline run is valid when:

```text
run lasted 30 minutes
EMU-01 interval remained 15 seconds and payload/firmware stayed frozen
no attack/outage was introduced
no required service restarted unexpectedly
no OOM kill occurred
uplink evidence exists
Fabric evidence exists for selected events
resource evidence exists
no duplicate canonical application rows exist
```

After all three valid runs, continue to [Execution 03](03-authentication-access-control.md).
