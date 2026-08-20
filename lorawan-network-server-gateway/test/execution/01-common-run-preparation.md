# Execution 1. Common Run Preparation and Evidence Capture

This is the operating procedure used before every counted experiment. Complete the full setup once, then repeat the short preflight and capture steps for each experiment group.

## 1. Freeze the test configuration

Do not change images, flows, schemas, credentials, region settings, payload format, or test rates between repetitions of the same experiment.

On the server VM:

```bash
cd /opt/lorawan-lab
mkdir -p "$HOME/chapter4-results/_configuration"
docker compose config > "$HOME/chapter4-results/_configuration/compose-baseline.yml"
docker compose config --images > "$HOME/chapter4-results/_configuration/image-list.txt"
sha256sum \
  "$HOME/chapter4-results/_configuration/compose-baseline.yml" \
  "$HOME/chapter4-results/_configuration/image-list.txt" \
  > "$HOME/chapter4-results/_configuration/configuration.sha256"
```

Also record non-secret values in `testbed-baseline.txt` from the preparation manual:

```text
Gateway EUI
EMU-01 Device EUI
SEC-02 hardware identity
EMU-01/SEC-02 pinned firmware versions
payload-contract version
AS923 sub-band/channel plan
Gateway OS version
Node-RED flow revision
TimescaleDB schema revision
Fabric contract/adapter version
```

## 2. Create the complete result tree once

```bash
mkdir -p "$HOME/chapter4-results"/{baseline,authentication,replay-spoofing,integrity,traceability,flooding,resilience,summaries,_invalid,_safety-backup}
```

Never overwrite a previous valid or invalid run. Use a new ID when rerunning.

## 3. Use unambiguous IDs

Recommended IDs:

```text
baseline-run-01
auth-lorawan-A1-01
replay-R01
spoof-S01
integrity-app-control-01
trace-single-01
flood-connection-high-01
resilience-run-01
```

A rerun of an invalid attempt gets a new suffix, for example:

```text
replay-R01-invalid
replay-R01-rerun-01
```

Do not delete the invalid attempt's evidence.

## 4. Confirm clocks before the experiment group

On the server VM:

```bash
date -u
timedatectl status
```

On the gateway:

```sh
date -u
```

On the test laptop:

```bash
date -u
```

The EMU-01 serial log is authoritative for scheduled `test_sequence`, sampled physical sensor values, sensor validity state, and source transmission attempts. Use an EMU-01/laptop timestamp for sensor-to-database latency only when the timestamp point and clock relationship have been explicitly verified. Otherwise report a clearly named gateway/ChirpStack-to-database latency.

## 5. Short preflight before every experiment group

### Server VM

```bash
cd /opt/lorawan-lab
free -h
docker compose ps
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true
```

Pass only when the seven required services are running and no required service is crash-looping or OOM-killed.

### Gateway

```sh
monit status
logread -e chirpstack-concentratord | tail -50
logread -e chirpstack-mqtt-forwarder | tail -50
logread -e mosquitto | tail -50
```

Confirm the expected Gateway EUI, radio service, local broker, and forwarder are healthy.

### EMU-01

Confirm from the source log/serial terminal:

```text
correct firmware/build
correct DevEUI
correct AS923 band
joined = yes
payload version = 2
sensor validity bitmap = 0x007F
15-second schedule active
test_sequence increasing normally
```

### SEC-02

Keep SEC-02 idle unless the experiment explicitly uses it. Confirm it does not contain legitimate EMU-01 root/session keys.

## 6. Run one known-good control before the group

Generate one real EMU-01 uplink and prove it reaches the normal path.

On the server:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,dev_eui,gateway_id,f_cnt,payload_json->>'test_sequence' AS test_sequence FROM telemetry.uplinks ORDER BY time DESC LIMIT 5;"

docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT source_event_key,status,digest_sha256,fabric_tx_id,submitted_at,committed_at FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 5;"
```

Fabric-dependent experiments require at least one selected control event with `status='confirmed'` and valid external commit evidence.

If this control fails, stop. Repair the normal path before starting a security/failure experiment.

## 7. Create the run directory and metadata

For each measured run:

```bash
GROUP='<GROUP>'
RUN_ID='<RUN_ID>'
RUN_DIR="$HOME/chapter4-results/$GROUP/$RUN_ID"
mkdir -p "$RUN_DIR"
```

Create a run metadata file before applying the test condition:

```bash
cat > "$RUN_DIR/run-meta.txt" <<EOF
run_id=$RUN_ID
group=$GROUP
expected_condition=<DESCRIBE_CONDITION>
expected_result=<DESCRIBE_EXPECTED_RESULT>
gateway_eui=<GATEWAY_EUI>
test_dev_eui=<EMU01_DEV_EUI>
payload_version=2
sensor_validity_expected=0x007F
emu_interval_seconds=15
EOF
```

Do not put secrets in `run-meta.txt`.

## 8. Start server resource and network capture

Record the start time first:

```bash
RUN_START_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "$RUN_START_UTC" | tee "$RUN_DIR/start-utc.txt"
ip -s link > "$RUN_DIR/network-before.txt"
```

Start server/container sampling every five seconds:

```bash
(
  printf 'timestamp,container,cpu,memory,memory_percent\n'
  while true; do
    ts="$(date -Ins)"
    docker stats --no-stream \
      --format "$ts,{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}}"
    sleep 5
  done
) > "$RUN_DIR/docker-stats.csv" &
RESOURCE_LOG_PID=$!
printf '%s\n' "$RESOURCE_LOG_PID" > "$RUN_DIR/docker-stats.pid"
```

## 9. Start gateway resource capture when required

Use the logger prepared in [Test Tools Preparation](../preparation/tools/01-prepare-test-tools.md):

```sh
/tmp/resource-log.sh /tmp/<RUN_ID>-gateway-resource.csv &
echo $! > /tmp/gateway-resource.pid
```

After the run, stop it and copy the CSV into `RUN_DIR` from the test laptop or server over the management LAN.

Keep gateway and server measurements as separate series.

## 10. Start EMU-01 source capture

Use the serial capture procedure from [Sensor Preparation](../preparation/sensor/01-configure-rak4631-emulators.md) on the test laptop.

Before starting the counted condition, verify the output file is growing and contains the expected next `test_sequence` values.

Save the final file as:

```text
<RUN_DIR>/emu-01-source.log
```

If the serial capture fails during a run whose denominator depends on source attempts, mark that run INVALID.

## 11. Start experiment-specific evidence

Depending on the manual, this may include:

```text
trial-results.csv
gateway raw-frame/log capture
Mosquitto observer/subscriber log
Node-RED quarantine/debug evidence
Fabric query evidence
load-generator count
WAN route state
```

Start it **before** applying the condition.

## 12. Apply exactly one test condition

Do not combine tests. Examples:

```text
wrong AppKey only
replay only
invalid MIC only
one controlled data alteration
one flood type/rate only
WAN loss only
```

Record the exact time the condition starts when timing matters.

## 13. Stop capture at the defined boundary

At the end of the run:

```bash
RUN_END_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf '%s\n' "$RUN_END_UTC" | tee "$RUN_DIR/end-utc.txt"

kill "$RESOURCE_LOG_PID" 2>/dev/null || true
wait "$RESOURCE_LOG_PID" 2>/dev/null || true
ip -s link > "$RUN_DIR/network-after.txt"
```

Stop the gateway resource logger when used:

```sh
kill "$(cat /tmp/gateway-resource.pid)" 2>/dev/null || true
rm -f /tmp/gateway-resource.pid
```

## 14. Export server logs for the exact window

Use the recorded start time:

```bash
docker compose logs --since "$RUN_START_UTC" \
  mosquitto chirpstack node-red telemetry-db openbao fabric-adapter \
  > "$RUN_DIR/server.log"
```

Save the matching gateway log window as `gateway.log`. Do not copy private keys or secret values into result folders.

## 15. Standard discrete-trial CSV

For experiments made of individual attempts, create a header before the first trial:

```bash
printf '%s\n' 'trial_id,layer,test_condition,expected_result,actual_result,start_utc,end_utc,device_eui,frame_counter_or_event_key,test_sequence,gateway_received,application_reached,database_changed,fabric_tx_id,response_or_verification_time,trial_status,log_reference,notes' \
  > "$RUN_DIR/trial-results.csv"
```

Append one row immediately after each trial while evidence is fresh.

## 16. Decide VALID / FAIL / INVALID before leaving the run

A run/trial is **INVALID** when any of these occur:

- the attack/test packet never reached the layer whose decision is being measured;
- EMU-01 stopped/reset/departed from the 15-second schedule for an unrelated reason;
- a required service restarted or was OOM-killed for an unrelated reason;
- the generator produced the wrong rate/credentials/fixture;
- timestamps required for the metric cannot be correlated;
- configuration changed during the repetition group;
- required raw evidence was not saved.

Write one of:

```text
PASS
FAIL
INVALID - <reason>
```

to:

```text
<RUN_DIR>/run-status.txt
```

Do not convert an INVALID test into PASS because the system happened not to accept anything.

## 17. Restore normal state before the next condition

After experiments that temporarily change MQTT listeners, ACLs, Node-RED flows, database roles, test flags, or WAN routing, follow that manual's restore section and then repeat the short preflight.

The next counted condition starts only after one normal EMU-01 control uplink succeeds again.

## 18. Safety backup before integrity testing

Before controlled database tampering:

```bash
mkdir -p "$HOME/chapter4-results/_safety-backup"
docker compose exec -T telemetry-db \
  pg_dump -U telemetry_admin -d lorawan_telemetry -Fc \
  > "$HOME/chapter4-results/_safety-backup/lorawan_telemetry.dump"
sha256sum "$HOME/chapter4-results/_safety-backup/lorawan_telemetry.dump" \
  > "$HOME/chapter4-results/_safety-backup/lorawan_telemetry.dump.sha256"
pg_restore -l "$HOME/chapter4-results/_safety-backup/lorawan_telemetry.dump" \
  > "$HOME/chapter4-results/_safety-backup/catalog.txt"
```

Pass only when the dump exists, its checksum is recorded, and `pg_restore -l` reads the catalog successfully.
