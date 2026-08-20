# Execution 3. Authentication and Access Control

This test contains **90 counted attempts**:

```text
LoRaWAN: 3 conditions x 10 = 30
MQTT:    3 conditions x 10 = 30
Fabric:  3 conditions x 10 = 30
Total:                       90
```

Run each layer separately and restore the normal configuration before moving to the next layer.

## What this test proves

The three layers answer different questions:

```text
LoRaWAN -> can an end device establish a legitimate network identity?
MQTT    -> can a client authenticate, and is it restricted to allowed topics?
Fabric  -> can an identity perform the requested ledger action?
```

For every condition, write the **expected decision before the attempt**. A rejection is counted only when the attempt actually reached the component making that decision.

## Test folder and result sheet

Create:

```bash
RUN_DIR="$HOME/chapter4-results/authentication"
mkdir -p "$RUN_DIR"/{lorawan,mqtt,fabric}
```

Keep separate CSVs for the three layers so a broker test cannot be confused with a LoRaWAN or Fabric authorization result.

## Part A - LoRaWAN device authentication

### Prepare three conditions

```text
A1 registered DevEUI + correct OTAA credentials
A2 registered DevEUI + incorrect AppKey
A3 unregistered DevEUI
```

Use the two fixed RAK4631 roles from [Sensor Preparation](../preparation/sensor/01-configure-rak4631-emulators.md). EMU-01 is the legitimate full physical-sensor node used for A1. SEC-02 is used for A2/A3 so invalid credentials never require changing the legitimate sensor-node firmware or exposing its root key. Do not overwrite or expose the legitimate root key.

### Before Part A

1. Run the Execution 01 short preflight.
2. Confirm EMU-01 can complete one legitimate join/uplink control.
3. Confirm SEC-02 is available by USB and has only the documented invalid/test fixtures.
4. Start matching gateway and ChirpStack log capture before trial A1-01.
5. Create the LoRaWAN trial CSV and record A1/A2/A3 expected decisions.
6. Use one fixed inter-trial delay for all 30 attempts; the documented approximately 30-second delay is the default.

### For each A1 trial

1. Clear only the test observation window; do not delete device history needed for audit.
2. Restart or command EMU-01 to perform a clean OTAA join using its frozen legitimate profile.
3. Record the JoinRequest time.
4. Confirm ChirpStack generates JoinAccept.
5. Send one uplink after the join.
6. Confirm the uplink reaches the application path.
7. Record allow/reject, response time, and log reference.
8. Wait about 30 seconds before the next join attempt so attempts do not overlap.

Repeat 10 times.

Expected: **allow**.

### For each A2 trial

1. Power off EMU-01, then configure SEC-02 with the registered EMU-01 DevEUI and JoinEUI but the dedicated deliberately incorrect AppKey fixture. SEC-02 must not receive the legitimate AppKey.
2. Trigger OTAA join.
3. Confirm the gateway/ChirpStack observes the request when possible.
4. Confirm no JoinAccept is issued for that invalid credential.
5. Confirm no accepted application data is created.
6. Record the rejection and response time.
7. Wait about 30 seconds.

Repeat 10 times.

Expected: **reject**.

### For each A3 trial

1. Keep EMU-01 out of the invalid-device trial and configure SEC-02 with the dedicated unregistered test DevEUI defined in Sensor Preparation.
2. Trigger OTAA join with test credentials.
3. Confirm the request is observed.
4. Confirm the device is not activated.
5. Confirm no accepted application data appears.
6. Record the rejection and response time.
7. Wait about 30 seconds.

Repeat 10 times.

Expected: **reject**.

### LoRaWAN evidence

For every trial retain:

```text
trial ID
DevEUI condition
JoinRequest observed yes/no
JoinAccept yes/no
accepted uplink yes/no
response time
ChirpStack/gateway log reference
```

A radio transmission that the gateway never receives is not counted as an authentication rejection. Preserve the sanitized SEC-02 AT/serial evidence and the matching gateway/ChirpStack observation for every A2/A3 trial.

---

## Part B - MQTT authentication and authorization

The normal broker intentionally does not publish password-authenticated port `1883` to the LAN. For this experiment create a **temporary test-only listener** reachable only by the test laptop. Remove it when the 30 trials finish.

### Step B1 - Create test identities

On the lab VM:

```bash
cd /opt/lorawan-lab
mkdir -p configuration/mosquitto/auth-test
cp configuration/mosquitto/passwd configuration/mosquitto/auth-test/passwd
cp configuration/mosquitto/acl configuration/mosquitto/auth-test/acl
```

Read the exact Mosquitto image already running in the testbed, then create three temporary test users:

```bash
MOSQUITTO_TEST_IMAGE="$(docker inspect mosquitto --format '{{.Config.Image}}')"
printf 'Using image: %s\n' "$MOSQUITTO_TEST_IMAGE"

docker run --rm -it \
  -v "$PWD/configuration/mosquitto/auth-test:/work" \
  "$MOSQUITTO_TEST_IMAGE" mosquitto_passwd /work/passwd auth_allowed

docker run --rm -it \
  -v "$PWD/configuration/mosquitto/auth-test:/work" \
  "$MOSQUITTO_TEST_IMAGE" mosquitto_passwd /work/passwd auth_limited

docker run --rm -it \
  -v "$PWD/configuration/mosquitto/auth-test:/work" \
  "$MOSQUITTO_TEST_IMAGE" mosquitto_passwd /work/passwd auth_observer
```

Append test ACL rules:

```text
user auth_allowed
topic write test/auth/allowed

user auth_limited
topic write test/auth/limited

user auth_observer
topic read test/auth/allowed
```

`auth_limited` deliberately has no permission for `test/auth/allowed`. `auth_observer` is read-only and is used only to prove whether an allowed marker actually reached the broker topic.

### Step B2 - Back up broker files before temporary changes

On the server:

```bash
cd /opt/lorawan-lab
mkdir -p "$RUN_DIR/mqtt/config-backup"
cp docker-compose.yml "$RUN_DIR/mqtt/config-backup/docker-compose.yml"
cp configuration/mosquitto/mosquitto.conf "$RUN_DIR/mqtt/config-backup/mosquitto.conf"
cp configuration/mosquitto/acl "$RUN_DIR/mqtt/config-backup/base-acl"
sha256sum "$RUN_DIR/mqtt/config-backup/"* > "$RUN_DIR/mqtt/config-backup/sha256.txt"
```

Do not start MQTT trials until these copies exist.

### Step B3 - Add a temporary listener

Add a test-only listener equivalent to:

```conf
listener 1884
protocol mqtt
allow_anonymous false
password_file /mosquitto/config/auth-test/passwd
acl_file /mosquitto/config/auth-test/acl
```

Temporarily add these two read-only mounts to the existing `mosquitto` service:

```yaml
- ./configuration/mosquitto/auth-test/passwd:/mosquitto/config/auth-test/passwd:ro
- ./configuration/mosquitto/auth-test/acl:/mosquitto/config/auth-test/acl:ro
```

Temporarily publish only:

```yaml
- "<LAB_SERVER_IP>:1884:1884"
```

Run `docker compose config --quiet` before restarting the broker.

Restrict the host firewall to the test laptop:

```bash
sudo ufw allow from <TEST_LAPTOP_IP> to any port 1884 proto tcp
```

Restart Mosquitto and verify the normal mTLS listener `8883` still works.

### Step B4 - Start a read-only observer from the test laptop

Use a second test-laptop terminal:

```bash
mkdir -p "$HOME/chapter4-results/authentication/mqtt"
mosquitto_sub -h <LAB_SERVER_IP> -p 1884 \
  -u auth_observer -P '<AUTH_OBSERVER_PASSWORD>' \
  -t 'test/auth/allowed' -v \
  > "$HOME/chapter4-results/authentication/mqtt/observer.log" &
OBSERVER_PID=$!
echo "$OBSERVER_PID"
```

The observer proves whether a marker actually reached the allowed topic. Keep it running for B1-B3.

Before B1-01, publish one harmless observer-check marker with `auth_allowed` and prove the subscriber receives it. Do not count that setup check.

### Condition B1 - authorized account, allowed topic

From the test laptop, publish one unique trial marker:

```bash
mosquitto_pub -h <LAB_SERVER_IP> -p 1884 \
  -u auth_allowed -P '<AUTH_ALLOWED_PASSWORD>' \
  -t 'test/auth/allowed' -m 'mqtt-auth-trial-01' -d
```

Confirm the marker appears exactly once in `observer.log`. Repeat 10 times with unique trial IDs.

Expected: **allow**.

### Condition B2 - incorrect password

```bash
mosquitto_pub -h <LAB_SERVER_IP> -p 1884 \
  -u auth_allowed -P '<INTENTIONALLY_WRONG_PASSWORD>' \
  -t 'test/auth/allowed' -m 'must-not-arrive' -d
```

Confirm the broker rejects the connection and the unique marker does not appear in `observer.log`. Repeat 10 times.

Expected: **reject**.

### Condition B3 - valid limited user, prohibited topic

```bash
mosquitto_pub -h <LAB_SERVER_IP> -p 1884 \
  -u auth_limited -P '<AUTH_LIMITED_PASSWORD>' \
  -t 'test/auth/allowed' -m 'must-be-denied' -d
```

The client may authenticate, but the publish must be denied and the unique marker must not appear in `observer.log`. Repeat 10 times.

Expected: **reject publish**.

### Step B5 - Stop the observer and verify no downstream state changed

On the test laptop:

```bash
kill "$OBSERVER_PID" 2>/dev/null || true
wait "$OBSERVER_PID" 2>/dev/null || true
```

Save broker logs and verify the isolated `test/auth/...` messages did not create telemetry or Fabric records. The MQTT authentication test must not be wired into the normal telemetry-storage path.

### Step B6 - Remove the temporary listener and restore normal state

Because the broker/Compose changes in this part are test-only, restore the exact known-good copies made in Step B2:

```bash
cd /opt/lorawan-lab
cp "$RUN_DIR/mqtt/config-backup/docker-compose.yml" docker-compose.yml
cp "$RUN_DIR/mqtt/config-backup/mosquitto.conf" configuration/mosquitto/mosquitto.conf
cp "$RUN_DIR/mqtt/config-backup/base-acl" configuration/mosquitto/acl
sudo ufw delete allow from <TEST_LAPTOP_IP> to any port 1884 proto tcp
rm -rf configuration/mosquitto/auth-test

docker compose config --quiet
docker compose up -d mosquitto
```

Then:

1. verify normal listener `8883` works;
2. verify the internal application listener works inside the Compose network;
3. verify port `1884` is no longer listening on the host;
4. run one normal EMU-01 uplink and prove it reaches TimescaleDB;
5. retain the observer/broker logs, but do not archive the temporary plaintext test passwords.

Do not leave password-authenticated `1884` open after the experiment.

---

## Part C - Hyperledger Fabric authorization

### Part C hard blocker

Do not start the 30 Fabric attempts until the external Fabric team provides or approves:

```text
authorized writer identity
valid non-writer identity
invalid/untrusted identity fixture
exact submit command/API for the test chaincode function
exact read/query command/API
method for proving commit validity
```

Save these non-secret command templates and identity labels in the Fabric result folder. If any required identity or query method is unavailable, mark Part C **BLOCKED**; do not invent local MSP roles or substitute a database-only result.

This section requires the Fabric team to provide or approve three test identities:

```text
C1 authorized writer
C2 valid identity without writer permission
C3 invalid/untrusted identity or a controlled invalid-certificate fixture
```

Do not invent MSP roles locally and claim they represent the external network policy.

### Before every unauthorized trial

Use a unique synthetic event key and query the intended state before submission. Save the result.

### Condition C1 - authorized writer

1. Submit one synthetic test attestation using the authorized writer.
2. Wait for valid commit status.
3. Save the transaction ID and response time.
4. Query the ledger state and confirm the new test key exists.

Repeat 10 times with unique test keys.

Expected: **allow and commit**.

### Condition C2 - valid identity without writer permission

1. Query the unique test key before submission.
2. Attempt the same submit function using the non-writer identity.
3. Record the authorization error.
4. Query the same key again.
5. Confirm world state is unchanged.

Repeat 10 times.

Expected: **reject with no state change**.

### Condition C3 - invalid/untrusted identity

1. Use the Fabric-team-approved invalid identity/certificate fixture.
2. Attempt the same submit operation.
3. Record connection/identity/transaction rejection.
4. Query the unique test key using an authorized read identity.
5. Confirm no state change.

Repeat 10 times.

Expected: **reject with no state change**.

## Required CSV fields

```text
layer
condition
trial
expected_decision
actual_decision
allowed
rejected
false_acceptance
false_rejection
unauthorized_state_change
response_time_seconds
log_or_tx_reference
```

## Pass condition

```text
90 counted attempts exactly
all authorized controls accepted
all unauthorized/prohibited attempts rejected
zero false acceptance
zero unauthorized state change
raw evidence retained for every trial
```

Continue to [Execution 04 - Replay and Spoofing](04-replay-spoofing.md).
