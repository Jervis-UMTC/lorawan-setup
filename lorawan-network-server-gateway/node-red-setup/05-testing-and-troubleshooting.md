# 5. Testing and Troubleshooting Node-RED

Test the pipeline from left to right:

~~~text
ChirpStack MQTT -> Node-RED MQTT -> JSON parse -> normalization -> PostgreSQL -> Grafana
~~~

## 5.1 Confirm Node-RED is running

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose ps node-red
~~~

~~~bash
docker compose logs --since=10m --tail=100 node-red
~~~

## 5.2 Confirm MQTT publishes uplinks

Run this in the Mosquitto container:

~~~bash
docker compose exec mosquitto mosquitto_sub -h localhost -t 'application/+/device/+/event/up' -v
~~~

No output is normal before a real sensor uplink. Gateway event/stats topics do not prove that an application uplink is available.

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

If msg.payload is a string, add the JSON node. If object is empty, verify the ChirpStack device profile codec and the actual sensor model.

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

Use the parameterized query path. Do not fix a data-type problem by concatenating strings into SQL.

## 5.7 No rows appear in Grafana

Query the database directly:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT count(*), max(time) FROM telemetry.uplinks;"
~~~

If rows exist, fix Grafana. If rows do not exist, fix MQTT or Node-RED.

## 5.8 Pre-arrival synthetic test

Before a sensor arrives, you can test Node-RED and PostgreSQL with a synthetic message injected into the flow. This proves only the application pipeline; it does not prove RF reception, LoRaWAN activation, encryption, or gateway downlink.

Use a fake DevEUI such as 0000000000000000 and clearly label the record as test data. Delete test rows deliberately after verification, or add a test tag/column in a development database.

Do not publish synthetic data to the production ChirpStack application topic unless you intentionally understand the consequences. Prefer an Inject node wired directly to the normalization function.

## 5.9 First real-sensor acceptance

When the Dragino arrives:

1. Verify the exact model and regional band.
2. Register the real device in ChirpStack.
3. Observe a JoinRequest and JoinAccept.
4. Observe a decoded ChirpStack MQTT uplink.
5. Confirm Node-RED inserts one row.
6. Confirm Grafana displays the row.
7. Confirm a later uplink advances the frame counter and last-seen time.

Return to [00-README.md](00-README.md) after the flow is healthy.
