# 5. Testing and Troubleshooting Node-RED

Test the pipeline from left to right. Run Docker and database commands on the LoRaWAN application server from `/opt/chirpstack-docker`; use the Node-RED editor through the documented SSH tunnel. Capture the exact flow revision, Node-RED image, palette versions, region environment value, test event key, and timestamps before changing anything:

~~~text
ChirpStack MQTT -> Node-RED MQTT -> JSON parse -> normalization -> PostgreSQL -> Grafana
~~~

## 5.1 Confirm Node-RED is running

~~~bash
cd /opt/chirpstack-docker
~~~

~~~bash
docker compose ps node-red
~~~

~~~bash
docker compose logs --since=10m --tail=100 node-red
~~~

Healthy output shows the container running without a restart loop and logs without settings, credential-secret, palette, or flow-load errors. An exited container or repeated startup error means Node-RED itself must be fixed before MQTT or PostgreSQL is changed.

## 5.2 Confirm MQTT publishes uplinks

Run this in the Mosquitto container:

~~~bash
docker compose exec mosquitto mosquitto_sub -h localhost -t 'application/+/device/+/event/up' -v
~~~

A healthy test prints the case-sensitive application uplink topic and one JSON event after the selected device transmits. No output is normal before a real sensor uplink; after a known uplink, it means the ChirpStack application integration, broker ACL, credentials, or topic is wrong. Gateway event and stats topics do not prove that an application uplink is available.

## 5.3 Confirm Node-RED resolves internal services

~~~bash
docker compose exec node-red getent hosts mosquitto
~~~

~~~bash
docker compose exec node-red getent hosts telemetry-db
~~~

If either command fails, the services are not on the same Compose network or the service name is wrong.

## 5.4 MQTT node is disconnected

Check:

- broker host is mosquitto, not localhost;
- port is 1883;
- Mosquitto is running;
- MQTT authentication matches the broker configuration;
- the topic is application/+/device/+/event/up; and
- the Node-RED container has restarted after configuration changes.

~~~bash
docker compose logs --since=10m --tail=100 mosquitto
~~~

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

~~~bash
docker compose logs --since=10m --tail=100 telemetry-db
~~~

Common errors:

| Error | Likely cause |
|---|---|
| permission denied | telemetry_writer lacks INSERT or schema USAGE |
| relation does not exist | schema was not created or wrong table name |
| invalid input syntax | normalization did not convert a field correctly |
| column does not exist | Node-RED query and database schema are out of sync |
| connection refused | telemetry-db is unhealthy or wrong hostname |

A healthy insert creates one `telemetry.uplinks` row and the expected normalized measurement rows, with no catch-node error. Use the parameterized query path. Correct the exact role, schema, column, type conversion, or hostname reported by the error, then replay the same sanitized event once. Do not fix a data-type problem by concatenating strings into SQL.

## 5.7 No rows appear in Grafana

Query the database directly:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT count(*), max(time) FROM telemetry.uplinks;"
~~~

Also query `telemetry.measurements`. If uplinks exist but measurements do not, fix the model mapping, uniqueness index, or atomic SQL statement before Grafana. If neither table has rows, fix MQTT or Node-RED.

## 5.8 Pre-arrival synthetic test

Before a sensor arrives, you can test Node-RED and PostgreSQL with a synthetic message injected into the flow. This proves only the application pipeline; it does not prove RF reception, LoRaWAN activation, encryption, or gateway downlink.

Use a reserved fake DevEUI such as `0000000000000000`, a unique `deduplicationId`, and obviously synthetic values. Prefer a development database. In a shared database, record the exact test event key and remove only those rows after verification; confirm the target counts before every delete.

Do not publish synthetic data to the production ChirpStack application topic. Prefer an Inject node wired directly to the normalization function. Synthetic success proves only JSON parsing, mapping, permissions, duplicate handling, and database writes; it does not prove RF, LoRaWAN activation, key validity, or downlink behavior.

## 5.9 First real-sensor acceptance

When the Dragino arrives:

1. Verify the exact model and regional band.
2. Register the real device in ChirpStack.
3. Observe a JoinRequest and JoinAccept.
4. Observe a decoded ChirpStack MQTT uplink.
5. Confirm Node-RED inserts one uplink row and the expected normalized measurement rows.
6. Replay the same event and prove row counts do not increase.
7. Confirm Grafana displays the value with timestamp and freshness state.
8. Confirm a later real uplink advances the frame counter, last-seen time, and measurement timestamps.
9. Confirm debug nodes are disabled and no root keys or database passwords appear in retained evidence.

Return to [00-README.md](00-README.md) after the flow is healthy.
