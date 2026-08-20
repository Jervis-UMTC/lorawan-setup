# Execution 7. DoS / Flooding

Run flooding only against the isolated test listener and test topic described here.

## What this test proves

This test asks whether legitimate EMU-01 telemetry continues while the server rejects controlled invalid traffic, how performance changes as invalid load increases, and whether the testbed returns to the normal range afterward.

Do not interpret high CPU alone as failure. The important outcomes are legitimate delivery/latency, rejection of invalid traffic, unauthorized storage, service availability, and recovery.

## Before changing Mosquitto

1. Run the Execution 01 short preflight.
2. Confirm the three baseline runs are complete; they define the normal comparison range.
3. Confirm EMU-01 is stable at 15 seconds and SEC-02 is idle.
4. Back up `docker-compose.yml`, Mosquitto configuration, Mosquitto ACL, and the current Node-RED test flow.
5. Record hashes of those backups.
6. Do not proceed until one ordinary EMU-01 event reaches the normal path.

Create the configuration backup before editing anything:

```bash
cd /opt/lorawan-lab
FLOOD_CFG_BACKUP="$HOME/chapter4-results/flooding/_config-before"
mkdir -p "$FLOOD_CFG_BACKUP"
cp docker-compose.yml "$FLOOD_CFG_BACKUP/docker-compose.yml"
cp configuration/mosquitto/mosquitto.conf "$FLOOD_CFG_BACKUP/mosquitto.conf"
cp configuration/mosquitto/acl "$FLOOD_CFG_BACKUP/mosquitto-acl"
sha256sum "$FLOOD_CFG_BACKUP/"* > "$FLOOD_CFG_BACKUP/sha256.txt"
```

Export the current Node-RED flow from the editor and save it in the same `_config-before` folder. The experiment does not begin until the backups are readable.

## Required design

Two test areas:

```text
1. MQTT invalid-connection flooding
2. Invalid application-message flooding
```

Each has:

```text
normal:   0 invalid requests/s
moderate: 10 invalid requests/s
high:     50 invalid requests/s
```

Each condition runs for 5 minutes and is repeated 3 times.

```text
2 test areas x 3 conditions x 3 repetitions = 18 runs
5-minute recovery after every run
```

The legitimate RAK4631 EMU-01 continues its frozen physical-sensor payload v2 every 15 seconds, with a deterministic `test_sequence`, so about 20 legitimate readings are expected per five-minute run. SEC-02 is not used during flooding.

## 1. Create a temporary isolated flood listener

Do not flood the normal gateway mTLS listener.

Create a test-only password/ACL set under:

```text
/opt/lorawan-lab/configuration/mosquitto/flood-test/
```

Create one `flood_publisher` user using the exact Mosquitto image already running in the testbed:

```bash
cd /opt/lorawan-lab
mkdir -p configuration/mosquitto/flood-test
: > configuration/mosquitto/flood-test/acl
MOSQUITTO_TEST_IMAGE="$(docker inspect mosquitto --format '{{.Config.Image}}')"
printf 'Using image: %s\n' "$MOSQUITTO_TEST_IMAGE"
docker run --rm -it \
  -v "$PWD/configuration/mosquitto/flood-test:/work" \
  "$MOSQUITTO_TEST_IMAGE" mosquitto_passwd -c /work/passwd flood_publisher
```

Its only publish permission is:

```text
user flood_publisher
topic write test/flood/invalid
```

Write those two lines to `configuration/mosquitto/flood-test/acl`.

Add a temporary listener such as:

```conf
listener 1885
protocol mqtt
allow_anonymous false
password_file /mosquitto/config/flood-test/passwd
acl_file /mosquitto/config/flood-test/acl
```

Temporarily add the test files to the existing Mosquitto volumes:

```yaml
- ./configuration/mosquitto/flood-test/passwd:/mosquitto/config/flood-test/passwd:ro
- ./configuration/mosquitto/flood-test/acl:/mosquitto/config/flood-test/acl:ro
```

Publish host port `1885` only on the lab/test interface:

```yaml
- "<LAB_SERVER_IP>:1885:1885"
```

Permit it through UFW only from the test laptop:

```bash
sudo ufw allow from <TEST_LAPTOP_IP> to any port 1885 proto tcp
```

Run `docker compose config --quiet`, restart Mosquitto, and verify normal `8883` gateway mTLS still works before starting counted runs.

## 2. Give the normal Node-RED test identity temporary read permission

The invalid-message condition must actually exercise Node-RED validation. Temporarily add **read-only** permission for the existing `node_red` account to subscribe to:

```text
test/flood/invalid
```

Keep its existing normal application-topic permission. Do not grant Node-RED write permission to the flood topic and do not grant the flood user access to production gateway/application topics.

Save the changed ACL as part of the experiment configuration evidence. Before restarting Mosquitto, verify the `node_red` block still retains its normal application-topic permission and has only the additional temporary **read** permission for `test/flood/invalid`.

## 3. Add the temporary Node-RED flood-test input

Create a test branch:

```text
MQTT in: test/flood/invalid
  -> JSON parse attempt
  -> validation function
       |-> invalid counter / test log
       +-> valid path only when all production-required fields pass
```

Do not connect malformed test messages directly to an unrestricted SQL node. The validation path must reject them before valid telemetry/Fabric storage.

Keep the normal ChirpStack application MQTT input running at the same time.

## 4. Prepare the traffic generator

Use the two scripts from [Test Tools Preparation](../preparation/tools/01-prepare-test-tools.md):

```text
connection_flood.py       -> repeated new MQTT connections with wrong password
invalid_message_stream.py -> authenticated invalid JSON stream to test/flood/invalid
```

Keep the final rates fixed at `10/s` and `50/s` after the pilot. Record the generator's reported attempt/message count and compare it with Mosquitto/Node-RED evidence. Do not accept a run that substantially misses the selected rate.

### Invalid application payload examples

Rotate among controlled malformed records such as:

```json
{"missing":"device identity"}
```

```json
{"dev_eui":"not-a-valid-eui","value":35}
```

```json
{"dev_eui":"0000000000000001","time":"not-a-time","value":35}
```

```json
{"dev_eui":"0000000000000001","time":"2000-01-01T00:00:00Z","value":"wrong-type"}
```

These messages stay on `test/flood/invalid`; they are not forged ChirpStack gateway/application topics.

## 5. Pilot the rates once

Before final runs:

1. verify `10/s` produces a visible but manageable increase in broker/Node-RED work;
2. verify `50/s` does not immediately destroy the testbed;
3. verify EMU-01 still produces the expected `test_sequence` every 15 seconds;
4. verify resource capture works;
5. freeze the rates.

Do not change rates between the three repetitions.

## Part A - MQTT connection flooding

Run in this order:

```text
A-normal-1
A-normal-2
A-normal-3
A-moderate-1
A-moderate-2
A-moderate-3
A-high-1
A-high-2
A-high-3
```

### Normal condition

For five minutes generate no invalid connection attempts. Keep EMU-01 running in the exact same firmware/configuration used by the flooding conditions.

### Moderate condition

For five minutes generate approximately:

```text
10 invalid connections/s x 300 s = 3000 attempts
```

Each attempt uses the temporary listener and an intentionally incorrect password. Run:

```bash
cd "$HOME/lorawan-test-tools"
./connection_flood.py \
  --host <LAB_SERVER_IP> --port 1885 \
  --rate 10 --seconds 300 \
  --user flood_publisher --password '<INTENTIONALLY_WRONG_PASSWORD>' \
  | tee <RUN_DIR>/generator-count.txt
```

For the high condition change only `--rate 50`.

### High condition

For five minutes generate approximately:

```text
50 invalid connections/s x 300 s = 15000 attempts
```

### For every run

Use this exact run card:

1. complete the Execution 01 short preflight;
2. create a unique `RUN_ID` and `RUN_DIR`;
3. reset only the temporary flood counters/log markers used by the test branch;
4. start EMU-01 source capture if it is not already active;
5. start server and gateway resource/network capture;
6. record the first expected EMU-01 `test_sequence`;
7. record start UTC;
8. run the selected traffic for exactly five minutes;
9. keep EMU-01 active for the full five-minute window;
10. record flood-window end UTC and stop the generator;
11. **do not stop resource capture yet**;
12. observe the system for exactly five recovery minutes;
13. record recovery-window end UTC;
14. stop resource capture;
15. save generator count, Mosquitto/Node-RED evidence, EMU-01 source log, legitimate telemetry export, resource CSVs, and server logs;
16. confirm no invalid request created a valid database/Fabric record;
17. compare legitimate delivery/latency/resource use with the corresponding normal baseline;
18. mark the run PASS, FAIL, or INVALID.

A normal `0/s` run still uses the same five-minute flood window plus five-minute recovery observation so the timing structure is identical.

## Part B - Invalid application-message flooding

Use the same nine-run order for `B-normal`, `B-moderate`, and `B-high`.

Moderate:

```text
10 invalid messages/s x 300 s = 3000 messages/run
```

High:

```text
50 invalid messages/s x 300 s = 15000 messages/run
```

Publish using `flood_publisher` only to `test/flood/invalid`.

Moderate run:

```bash
cd "$HOME/lorawan-test-tools"
./invalid_message_stream.py --rate 10 --seconds 300 \
  2><RUN_DIR>/generator-count.txt \
  | mosquitto_pub -h <LAB_SERVER_IP> -p 1885 \
      -u flood_publisher -P '<FLOOD_PUBLISHER_PASSWORD>' \
      -t 'test/flood/invalid' -q 0 -l
```

For the high condition change only `--rate 50`.

For each run verify:

```text
Node-RED receives the test-topic load
validation rejects malformed messages
normal EMU-01 physical-sensor flow and deterministic sequence continue
invalid test messages do not create valid telemetry rows
invalid test messages do not create Fabric outbox/Fabric records
```

## 6. Collect the required measures

For each of 18 runs record:

```text
valid messages expected
valid messages delivered/stored
invalid attempts generated
invalid attempts rejected
legitimate end-to-end latency
valid-message throughput
mean/max CPU
mean/max memory
network before/after counters
service availability
unauthorized records
recovery time
```

Define the recovery threshold **before** final runs using the completed baseline data. Recovery time starts when the five-minute flood generator stops and ends when legitimate latency/resource behavior returns to that predefined normal range and no flood-attributable backlog remains.

If the system has not recovered by the end of the five-minute observation, record `recovery_time > 300 s` / not recovered within observation rather than inventing a shorter value.

## 7. Remove test exposure and restore the baseline configuration

After all flooding evidence is saved, restore the exact pre-test broker/Compose files:

```bash
cd /opt/lorawan-lab
cp "$FLOOD_CFG_BACKUP/docker-compose.yml" docker-compose.yml
cp "$FLOOD_CFG_BACKUP/mosquitto.conf" configuration/mosquitto/mosquitto.conf
cp "$FLOOD_CFG_BACKUP/mosquitto-acl" configuration/mosquitto/acl
sudo ufw delete allow from <TEST_LAPTOP_IP> to any port 1885 proto tcp
rm -rf configuration/mosquitto/flood-test

docker compose config --quiet
docker compose up -d mosquitto
```

Then restore the saved known-good Node-RED flow from `_config-before`, deploy it, and verify:

```text
port 1885 is no longer listening
node_red no longer has temporary test/flood/invalid permission
normal gateway mTLS 8883 still works
normal application subscription still works
one new EMU-01 control reaches TimescaleDB and the normal Fabric path
```

Do not archive the flood-publisher password with the Chapter IV results.

## Pass condition

A final run is valid when the intended traffic rate occurred, EMU-01 remained active on the frozen 15-second schedule with the full physical-sensor payload and deterministic sequence markers, and raw logs/resource evidence exist.

Security success requires:

```text
invalid traffic rejected
zero invalid valid-database records
zero invalid Fabric transactions
legitimate readings continue through the system
no sustained service failure after the recovery window
```

Continue to [Execution 08 - Resilience and Recovery](08-resilience-recovery.md).
