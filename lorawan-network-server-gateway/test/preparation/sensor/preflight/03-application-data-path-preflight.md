# Sensor Preflight 3 - Node-RED, TimescaleDB, and Fabric Path

This preflight proves that accepted ChirpStack telemetry continues through the application/data path without changing the sensor meaning or `test_sequence`.

## Path under test

```text
EMU-01 source record
      │
      ▼
RAK5146 / ChirpStack
      │ decoded payload v2
      ▼
Node-RED
      │ mapping/storage logic
      ▼
TimescaleDB
      │
      ├─ telemetry.uplinks
      ├─ payload_json
      └─ Fabric outbox
              │
              ▼
       adapter / OpenBao
              │
              ▼
       Fabric evidence
```

## Step 1 - Confirm required services

On the server VM:

```bash
cd /opt/lorawan-lab
docker compose ps
```

Confirm the required services for the normal path are healthy:

```text
Mosquitto
Valkey
ChirpStack
PostgreSQL / TimescaleDB
Node-RED
OpenBao
Fabric adapter
```

Check for recent resource failure:

```bash
free -h
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true
```

**NO-GO if:** a required service is crash-looping or was OOM-killed during the preflight for an unrelated reason.

## Step 2 - Mark a clean preflight observation window

Record:

```text
APPLICATION_PREFLIGHT_START_UTC=<UTC>
first expected test_sequence=<N>
```

Let EMU-01 continue its normal 15-second operation. Do not reset it merely to start the application preflight.

Select **five consecutive sequences** that are already known to be accepted by ChirpStack.

## Step 3 - Query the recent TimescaleDB uplinks

On the server:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,received_at,dev_eui,gateway_id,f_cnt,payload_json->>'test_sequence' AS test_sequence,payload_json->>'sensor_validity_bitmap' AS validity FROM telemetry.uplinks WHERE dev_eui='<EMU01_DEV_EUI>' ORDER BY time DESC LIMIT 20;"
```

Find the five selected preflight sequences.

For each selected sequence require:

```text
one canonical telemetry.uplinks row exists
test_sequence matches source
DevEUI matches EMU-01
gateway identity matches expected gateway
payload_json exists
sensor validity is represented
```

## Step 4 - Check for duplicate canonical rows

For the preflight observation window use the appropriate time/identity filter and inspect for duplicate canonical application records.

Example pattern:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,count(*) FROM telemetry.uplinks WHERE dev_eui='<EMU01_DEV_EUI>' AND time >= '<APPLICATION_PREFLIGHT_START_UTC>' GROUP BY event_key,time HAVING count(*) > 1;"
```

Expected result:

```text
0 duplicate canonical rows
```

If the query returns rows, investigate before counted testing.

## Step 5 - Compare one source record field by field

Choose one of the five sequences and compare:

```text
EMU-01 serial source
      │
      ├─ test_sequence
      ├─ soil
      ├─ UV
      ├─ barometer
      ├─ VEML light
      ├─ OPT light
      ├─ environment
      ├─ rain
      └─ validity bitmap
      │
      ▼
TimescaleDB payload_json
```

Apply only the documented payload scaling/rounding when comparing values.

Record the comparison in:

```text
chapter4-results/_preflight/sensor/03-application-path/source-vs-db.txt
```

**NO-GO if:** a value changes meaning, a field is overwritten, the two light sensors collapse into one field, or the wrong sequence is associated with a row.

## Step 6 - Confirm Node-RED mapping behavior

Using the stored object and Node-RED evidence/logs, verify the expected convenience fields remain mapped correctly:

```text
temperature_c      <- environment_temperature_c
humidity_percent   <- environment_humidity_percent
battery_v          <- documented battery field/sentinel rule
```

The complete decoded sensor object must remain available in `payload_json` even when convenience columns expose only selected fields.

## Step 7 - Inspect Fabric outbox for the selected event

Choose one preflight event intended to traverse the Fabric path.

Query recent outbox rows:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT source_event_key,status,digest_sha256,fabric_tx_id,submitted_at,committed_at FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 20;"
```

Correlate the selected `event_key`/source event with its outbox row.

Require:

```text
source event key link is correct
outbox row exists
status reaches the expected successful confirmed state
transaction ID/evidence reference is present
commit validity can be verified using the project's approved Fabric verification procedure
```

A transaction ID alone is not sufficient proof of a successful Fabric commit.

If the external Fabric dependency is intentionally unavailable for the research configuration, use the methodology's documented blocked/not-applicable rule rather than pretending a commit occurred. Otherwise Fabric preflight is required.

## Step 8 - Save application-path evidence

Save/export:

```text
chapter4-results/_preflight/sensor/03-application-path/db-uplinks.csv
chapter4-results/_preflight/sensor/03-application-path/source-vs-db.txt
chapter4-results/_preflight/sensor/03-application-path/fabric-evidence.txt
```

Also record:

```text
five selected sequences
five DB rows present = yes/no
duplicate rows = 0/<count>
source-vs-DB field comparison = PASS/NO-GO
Fabric selected event = <event key>
Fabric confirmed/verified = yes/no
required services healthy = yes/no
result = PASS | NO-GO
```

## Step 9 - Mark the end of preflight traffic

Record:

```text
APPLICATION_PREFLIGHT_END_UTC=<UTC>
last preflight test_sequence=<N>
```

These boundaries make it explicit which traffic was preflight and must not be included in counted experiment windows.

## Exit condition

Continue to [04-go-no-go-transition.md](04-go-no-go-transition.md) only when the application/database path passes and the required Fabric evidence condition is satisfied.
