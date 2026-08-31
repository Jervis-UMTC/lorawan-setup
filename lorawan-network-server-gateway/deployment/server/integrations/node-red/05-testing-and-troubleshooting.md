# 5. Testing and Troubleshooting Node-RED

Test the pipeline from left to right. First identify the deployment profile:

```text
single-host lab               -> /opt/lorawan-lab, mosquitto, telemetry-db
three-Droplet cloud HA POC    -> ulc-03 ACTIVE + ulc-02 STANDBY,
                                  /etc/lorawan-cloud/node-red on both,
                                  node-local mqtt.internal.lorawan.com:18884,
                                  node-local pgbouncer.internal.lorawan.com:6432
```

Use the Node-RED editor through the documented SSH tunnel. Capture the exact flow revision, Node-RED image, palette versions, region environment value, test event key, and timestamps before changing anything:

~~~text
ChirpStack MQTT -> Node-RED MQTT -> JSON parse -> normalization -> PostgreSQL -> Grafana
~~~

## 5.1 Confirm Node-RED is running

Single-host lab:

~~~bash
cd /opt/lorawan-lab
docker compose ps node-red
docker compose logs --since=10m --tail=100 node-red
~~~

Cloud HA POC - run these on the **currently active** Node-RED host:

~~~bash
cd /etc/lorawan-cloud/node-red
sudo docker compose --env-file node-red.env ps node-red
sudo docker compose --env-file node-red.env logs --since=10m --tail=100 node-red
sudo ss -lntp | grep ':1880'
~~~

For the cloud profile, the editor must remain bound to loopback rather than the public VPC/Internet interface. On the standby host, `docker compose ps` must show Node-RED stopped and `:1880` must not be listening.

Healthy active output shows the container running without a restart loop and logs without settings, credential-secret, palette, or flow-load errors. **If both hosts show a running Node-RED ingestion container, treat that as split-brain and stop/fence one before troubleshooting anything else.**

If Node.js reports `Ignoring extra certs from /run/pgbouncer/ca.crt` with `Permission denied`, do not change PgBouncer PKI modes. Verify the host has `/etc/lorawan-pki/node-red-pgbouncer/ca.crt` as `0640 root:node-red-secrets`, that its SHA-256 matches `/etc/lorawan-pki/pgbouncer/ca.crt`, and that Compose mounts the dedicated Node-RED copy to `/run/pgbouncer/ca.crt`. Recreate only the affected Node-RED container after correcting the mount so `NODE_EXTRA_CA_CERTS` is readable at process startup.

## 5.2 Confirm MQTT publishes application uplinks

Single-host lab:

~~~bash
docker compose exec mosquitto mosquitto_sub -h localhost -t 'application/+/device/+/event/up' -v
~~~

Cloud HA POC from the candidate host being validated, using that host's **Node-RED read-only MQTT client identity**:

~~~bash
mosquitto_sub \
  -h mqtt.internal.lorawan.com -p 18884 \
  --cafile /etc/lorawan-pki/mqtt/ca.crt \
  --cert /etc/lorawan-pki/node-red-mqtt/client.crt \
  --key /etc/lorawan-pki/node-red-mqtt/client.key \
  -t 'application/+/device/+/event/up' -v
~~~

A healthy test prints the case-sensitive application uplink topic and one JSON event after EMU-01 transmits. No output is normal before a real sensor uplink; after a known accepted uplink, it means the ChirpStack application integration, HAProxy/Mosquitto route, ACL/certificate, or topic is wrong. Gateway event/stats topics do not prove that an application uplink is available.

## 5.3 Confirm Node-RED resolves its actual dependencies

Single-host lab:

~~~bash
docker compose exec node-red getent hosts mosquitto
docker compose exec node-red getent hosts telemetry-db
~~~

Cloud HA POC:

~~~bash
cd /etc/lorawan-cloud/node-red
sudo docker compose --env-file node-red.env exec node-red getent hosts mqtt.internal.lorawan.com
sudo docker compose --env-file node-red.env exec node-red getent hosts pgbouncer.internal.lorawan.com
~~~

In the cloud profile both logical names must resolve to the **current candidate's own private IP**: `10.104.0.8` on ulc-03 or `10.104.0.4` on ulc-02. That host then provides the local MQTT HAProxy and PgBouncer paths. Do not point the standby at ulc-03; that would make ulc-03 failure take down both the active instance and the standby's dependencies.

## 5.4 MQTT node is disconnected

Check the active profile:

```text
lab
  broker = mosquitto:1883
  private Compose authentication/ACL

cloud
  broker = mqtt.internal.lorawan.com:18884
  mTLS + hostname/CA verification enabled
  MQTT CA + Node-RED client certificate/key readable
  logical name resolves to the current Node-RED host's private HAProxy
  HAProxy sees at least one healthy Mosquitto :8886 backend
```

For both profiles verify the topic is exactly `application/+/device/+/event/up` and Node-RED has reloaded the intended broker configuration.

Lab logs:

~~~bash
docker compose logs --since=10m --tail=100 mosquitto
~~~

Cloud logs/checks:

~~~bash
# ha-03
sudo journalctl -u haproxy --since '10 min ago' --no-pager

# ha-01/ha-02 broker host as appropriate
sudo docker compose -f /etc/lorawan-cloud/mosquitto/compose.yml logs --since=10m --tail=100
~~~

A TLS error should be fixed at the CA/name/client-certificate layer. Do not disable verification to make the MQTT node turn green.

## 5.5 Messages arrive but the function drops them

Connect a debug node before the function and inspect:

- msg.payload type;
- deviceInfo.devEui;
- time;
- fPort;
- object;
- rxInfo; and
- msg.topic.

Healthy debug output contains a parsed object, a 16-hexadecimal Device EUI, a valid event time, and the decoded fields expected for the exact sensor model. If `msg.payload` is a string, add the JSON node. If `object` is empty, verify the ChirpStack device-profile codec and actual sensor model. If the Device EUI or time is missing, correct the source event contract rather than weakening the validation function.

## 5.6 PostgreSQL insert fails

First inspect Node-RED's catch-node error and container log.

Single-host lab database log:

~~~bash
docker compose logs --since=10m --tail=100 telemetry-db
~~~

Cloud HA POC checks on `ha-03`:

~~~bash
cd /etc/lorawan-cloud/node-red
sudo docker compose --env-file node-red.env logs --since=10m --tail=100 node-red
sudo systemctl status pgbouncer haproxy --no-pager -l
~~~

Then query Patroni/PgBouncer using the cloud troubleshooting manual if the error is connection/read-only related.

Common errors:

| Error | Likely cause |
|---|---|
| permission denied | telemetry_writer lacks INSERT or schema USAGE |
| relation does not exist | schema was not created or wrong table name |
| invalid input syntax | normalization did not convert a field correctly |
| column does not exist | Node-RED query and database schema are out of sync |
| connection refused | lab: `telemetry-db` unhealthy/wrong name; cloud: local PgBouncer/HAProxy route unhealthy or wrong mapping |

A healthy insert creates one `telemetry.uplinks` row and the expected normalized measurement rows, with no catch-node error. Use the parameterized query path. Correct the exact role, schema, column, type conversion, or hostname reported by the error, then replay the same sanitized event once. Do not fix a data-type problem by concatenating strings into SQL.

## 5.7 No rows appear in Grafana

Query the database through the profile's normal read path.

Single-host lab:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT count(*), max(time) FROM telemetry.uplinks;"
~~~

Cloud HA POC:

~~~bash
psql 'host=pgbouncer.internal.lorawan.com port=6432 dbname=lorawan_telemetry user=telemetry_reader sslmode=verify-full' \
  -c "SELECT count(*), max(time) FROM telemetry.uplinks;"
~~~

Also query `telemetry.measurements`. If uplinks exist but measurements do not, fix the EMU-01 payload-v2 mapping, uniqueness index, or atomic SQL statement before Grafana. If neither table has rows, fix MQTT or Node-RED before touching Grafana.

## 5.8 Pre-arrival synthetic test

Before a sensor arrives, you can test Node-RED and PostgreSQL with a synthetic message injected into the flow. This proves only the application pipeline; it does not prove RF reception, LoRaWAN activation, encryption, or gateway downlink.

Use the reserved fake DevEUI `0000000000000000`, a unique `deduplicationId`, and obviously synthetic values. The cloud runtime defaults `FABRIC_SELECTED_DEV_EUI` to this all-zero fixture identity, so the same pre-arrival test can also prove the missing atomic `telemetry + fabric_outbox` enqueue path without selecting ordinary application events. When a real staging DevEUI is approved later, replace only the protected environment value on both Node-RED candidates. Prefer a development database. In this shared POC database, record the exact test event key and remove only those synthetic rows after all Node-RED/Grafana verification is complete; confirm target counts before every delete.

Do not publish synthetic data to the production ChirpStack application topic. Prefer an Inject node wired directly to the normalization function. Synthetic success proves JSON parsing, mapping, permissions, duplicate handling, database writes, atomic outbox enqueue, and the server-side Grafana read path; it does not prove RF, LoRaWAN activation, key validity, gateway delivery, or downlink behavior.

## 5.9 EMU-01 real-sensor acceptance

Use the frozen EMU-01 Agriculture Kit payload-v2 profile as the primary project acceptance device:

1. verify the final EMU-01 hardware/firmware baseline is frozen;
2. verify ChirpStack uses the Agriculture Kit payload-v2 codec and expects 46 bytes/version 2;
3. observe a real JoinRequest and JoinAccept;
4. observe a decoded application MQTT uplink containing `test_sequence`, `sensor_validity_bitmap`, and all expected physical sensor fields;
5. compare at least one selected `test_sequence` against the serial source record;
6. confirm Node-RED inserts one canonical uplink row and the reviewed measurement rows;
7. verify invalid sensor bits become invalid/null normalized values rather than stale values labeled measured;
8. replay the same sanitized event and prove row counts do not increase;
9. confirm Grafana displays selected `metric_name` values with timestamps/freshness;
10. confirm a later real uplink advances `test_sequence`, LoRaWAN frame counter, last-seen time, and measurement timestamps as expected;
11. confirm both light sensors remain distinct and the complete decoded object remains in `payload_json`;
12. confirm debug nodes are disabled and no root keys or database passwords appear in retained evidence.

SEC-02's temporary 6-byte RAK12011 legitimate test is a separate mapping. After B-copy verification it returns to the security-fixture role and must not be treated as the permanent multi-sensor telemetry baseline.

## 5.10 Gateway-evidence trusted-decoder acceptance

Run this only after the reviewed [Gateway Integrity](../gateway-integrity/00-README.md) verifier implementation exists.

Choose one real staging uplink and record:

```text
source event key
observed time
raw ChirpStack application data digest
Node-RED decoder version
Node-RED normalized metrics
trusted decoder ID/version or code hash
trusted normalized-result digest
verification ID/status
```

Pass when the independent trusted decoder consumes the accepted raw application bytes and produces the same approved normalized values stored by Node-RED/TimescaleDB.

### Negative test

Use an isolated fixture or staging-only flow branch. Keep the same raw application bytes but intentionally change one Node-RED normalized value before storage, for example:

```text
trusted decoder = 27.3 C
Node-RED row    = 80.0 C
```

Pass only when:

- gateway journal and remote MQTT lineage can remain otherwise valid;
- the verifier reports `integrity_failure` for the application comparison;
- a `telemetry-attestation-v2` outbox row is not sealed/submitted as verified;
- the test does not cause the verifier to rewrite either source to make them agree.

Restore the approved Node-RED flow after the fixture.

## 5.11 Evidence-state troubleshooting

If telemetry appears in TimescaleDB but v2 Fabric work does not start, inspect the gateway-evidence status before changing Node-RED:

```text
pending
  -> required journal/MQTT/application/trusted-decode counterpart still waiting

evidence_gap
  -> required proof is unavailable; recover evidence or follow gap policy

integrity_failure
  -> contradictory evidence exists; investigate, do not retry by changing values

verified
  -> inspect the Fabric outbox/adapter gate next
```

A healthy Node-RED flow is not proof that gateway evidence is healthy.

Return to [00-README.md](00-README.md) after the flow is healthy.
