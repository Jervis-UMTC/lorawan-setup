# Execution 6. Traceability

This test uses the current stable event identity as the trace identifier.

## What this test proves

Traceability is not simply "the row exists." It proves that a known EMU-01 reading can be followed through the stored application record and its Fabric evidence using stable identifiers, and that a short history can be reconstructed without missing, duplicate, or reordered records.

## Before starting

1. Run the Execution 01 short preflight.
2. Confirm the integrity-test Node-RED gate and tamper role have been removed.
3. Generate one fresh control reading and confirm its `test_sequence` appears in TimescaleDB.
4. Confirm at least one selected fresh event reaches confirmed Fabric status.
5. Create separate result folders for `single/` and `history/` trials.
6. Start EMU-01 source capture before generating the 60 selected records.

```text
Individual trace:       10 trials / 10 records
History reconstruction: 10 trials / 5 records each = 50 records
Total:                  20 trials / 60 records
```

## Trace identifier used by this implementation

Node-RED already creates a stable `event_key` from ChirpStack `deduplicationId` or the documented deterministic fallback. Do not add a second random ID only for the dissertation.

Use:

```text
trace_id = telemetry.uplinks.event_key
Fabric event key = 'uplink:' + trace_id
```

The outbox also stores `source_event_key`, so the database and Fabric paths remain directly linked.

## Required trace fields

For every tested reading collect:

```text
trace_id / source event key
Device EUI
frame counter
EMU-01 test_sequence
sensor value and unit
event timestamp
gateway EUI
TimescaleDB record identity
SHA-256 digest
Fabric transaction ID
Fabric commit timestamp or block reference
```

## Part A - Individual record trace

### Step A1 - Generate and mark 10 known readings

Do not select arbitrary old rows after the fact. Deliberately mark the ten readings used by this test.

For each selected reading, immediately record:

```text
trial ID
EMU-01 test_sequence
expected physical sensor values from the source log
source-log line/time
```

Let EMU-01 produce 10 legitimate physical-sensor readings. Record `test_sequence` and the complete physical sensor values from the EMU-01 source log for every selected reading.

Wait until each selected reading is stored and, when Fabric-selected, reaches `confirmed`.

### Step A2 - Select one trace ID

Query recent events:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,dev_eui,gateway_id,f_cnt,payload_json FROM telemetry.uplinks WHERE dev_eui='<TEST_DEV_EUI>' ORDER BY time DESC LIMIT 20;"
```

Choose one event key that belongs to the trace trial.

### Step A3 - Retrieve the complete database path

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -v event_key='<TRACE_ID>' \
  -c "SELECT event_key,time,received_at,dev_eui,gateway_id,f_cnt,payload_json FROM telemetry.uplinks WHERE event_key=:'event_key';"
```

Retrieve normalized measurements:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -v event_key='<TRACE_ID>' \
  -c "SELECT metric_name,metric_value,metric_text,metric_bool,unit,quality,time FROM telemetry.measurements WHERE event_key=:'event_key' ORDER BY metric_name;"
```

### Step A4 - Retrieve the Fabric linkage

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -v event_key='<TRACE_ID>' \
  -c "SELECT outbox_id,event_key AS fabric_event_key,source_event_key,observed_at,status,digest_sha256,fabric_tx_id,submitted_at,committed_at FROM telemetry.fabric_outbox WHERE source_event_key=:'event_key';"
```

Use the external Fabric query function supplied by the Fabric team to retrieve the attestation using the Fabric event key or transaction ID.

Verify:

```text
source_event_key = trace_id
Fabric digest = stored outbox digest
Fabric transaction exists and is valid
Device EUI / time / event identity agree with the source row
```

### Step A5 - Measure retrieval time

Use the same timing boundary for all ten trials:

```text
START = immediately before the first database trace query
STOP  = after the corresponding Fabric record has been retrieved and compared
```

Do not include time spent deciding which record to test; the record must already be selected before the timer starts.

Start the timer immediately before the first trace query and stop it after the Fabric record is retrieved and compared.

Record:

```text
successful retrieval yes/no
required fields complete yes/no
DB-Fabric link correct yes/no
retrieval time seconds
```

Repeat for 10 individual records.

---

## Part B - Device history reconstruction

Run 10 separate sequences. Each sequence contains **five consecutive EMU-01 physical-sensor readings** from the same registered device, identified by consecutive deterministic `test_sequence` values.

### Step B1 - Mark the sequence boundaries

Use ten non-overlapping five-reading groups. A five-reading sequence is based on `test_sequence`, not merely a loose time window.

Before the first reading record:

```text
sequence_id
Device EUI
start test_sequence
start frame counter or start UTC
```

After the fifth reading record:

```text
end test_sequence
end frame counter or end UTC
```

Wait for all five readings and their selected Fabric work to settle before querying.

### Step B2 - Query the five database records

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,dev_eui,f_cnt,payload_json FROM telemetry.uplinks WHERE dev_eui='<TEST_DEV_EUI>' AND time >= '<SEQUENCE_START_UTC>' AND time <= '<SEQUENCE_END_UTC>' ORDER BY time,f_cnt;"
```

The result must contain the expected five records for the sequence. If other live readings are in the same time window, filter using the recorded frame-counter range.

### Step B3 - Query all database-to-Fabric links

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT u.event_key,u.time,u.f_cnt,o.event_key AS fabric_event_key,o.digest_sha256,o.fabric_tx_id,o.status,o.committed_at FROM telemetry.uplinks u LEFT JOIN telemetry.fabric_outbox o ON o.source_event_key=u.event_key AND o.observed_at=u.time WHERE u.dev_eui='<TEST_DEV_EUI>' AND u.time >= '<SEQUENCE_START_UTC>' AND u.time <= '<SEQUENCE_END_UTC>' ORDER BY u.time,u.f_cnt;"
```

For Fabric-selected records, query the corresponding ledger entries using the approved Fabric read function.

### Step B4 - Compare with the original EMU-01 transmission log

For each five-record sequence verify:

```text
5 expected readings present
0 missing
0 unexpected duplicate application records
correct chronological order
correct frame-counter order when applicable
correct deterministic `test_sequence` plus source-matching physical values and units
correct source_event_key -> Fabric event link
correct digest and transaction ID
```

Measure total reconstruction time from the first database query until all five ledger links are confirmed.

Repeat for 10 sequences.

## Required CSV fields

```text
trace_test
trial_or_sequence
records_expected
records_retrieved
complete_records
correct_db_fabric_links
correct_chronological_order
missing_records
duplicate_records
retrieval_time_seconds
evidence_reference
```

## After every trace trial

Before starting the next trial:

1. write the result row;
2. save the SQL/query output used as evidence;
3. save the Fabric query reference;
4. compare the retrieved `test_sequence` and values with the EMU-01 source log;
5. classify PASS/FAIL/INVALID;
6. never replace a missing record with a nearby record merely to make a five-reading group complete.

## Pass condition

```text
10/10 individual traces complete
10/10 five-record histories reconstructed
60/60 expected records retrievable
zero missing records
zero duplicate canonical application records
all required DB-Fabric links correct
chronological order correct for every sequence
```

Continue to [Execution 07 - DoS / Flooding](07-dos-flooding.md).
