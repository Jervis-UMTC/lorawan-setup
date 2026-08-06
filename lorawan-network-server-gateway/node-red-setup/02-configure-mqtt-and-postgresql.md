# 2. Configure MQTT and PostgreSQL Connections

Use Node-RED's built-in MQTT nodes and a PostgreSQL palette node. The standard MQTT nodes are sufficient for ChirpStack events; a special ChirpStack node is optional and is not required for telemetry storage.

## 2.1 Install the PostgreSQL palette node

In the Node-RED editor:

1. Open the menu.
2. Select **Manage palette**.
3. Open **Install**.
4. Search for node-red-contrib-postgresql.
5. Install it.
6. Restart Node-RED if requested.

The node supports parameterized queries through msg.params, which is required for safe sensor inserts. [node-red-contrib-postgresql documentation](https://flows.nodered.org/node/node-red-contrib-postgresql)

## 2.2 Configure the MQTT input node

Add an **mqtt in** node:

~~~text
Broker: mosquitto
Port: 1883
Topic: application/+/device/+/event/up
QoS: 0
Output: a parsed JSON object, or a string followed by a JSON node
~~~

The topic is case-sensitive. Do not subscribe only to gateway stats topics when building a sensor telemetry flow.

Node-RED containers must use mosquitto as the broker hostname. Do not use localhost; inside a container, localhost points to the Node-RED container itself. [Node-RED MQTT connection guidance](https://cookbook.nodered.org/mqtt/connect-to-broker)

## 2.3 Add a JSON parser node when required

If the MQTT input produces a string:

1. Place a **json** node after mqtt in.
2. Configure it to convert the payload to an object.
3. Connect it to a **debug** node temporarily.
4. Deploy.

The debug output should show deviceInfo, time, fPort, object, data, and possibly rxInfo. Remove or disable verbose debug output after testing because raw payloads may contain sensitive operational metadata.

## 2.4 Configure the PostgreSQL connection node

Create a PostgreSQL configuration node with:

~~~text
Host: telemetry-db
Port: 5432
Database: lorawan_telemetry
User: telemetry_writer
Password: the telemetry_writer password
SSL: disabled for the private Docker network unless TLS is intentionally configured
~~~

The Node-RED database connection is not the same as the ChirpStack connection:

| Service | Database | Role |
|---|---|---|
| chirpstack | chirpstack | ChirpStack operational state |
| telemetry-db | lorawan_telemetry | telemetry_writer for Node-RED |

## 2.5 Do not use string-built SQL

Unsafe pattern:

~~~text
INSERT INTO telemetry.uplinks (device_name) VALUES ('" + msg.payload.deviceName + "')
~~~

Safe pattern:

~~~text
SQL uses $1, $2, and so on.
Node-RED puts values in msg.params.
The PostgreSQL node binds the values separately.
~~~

Parameterized queries protect the database from malformed or malicious payload text and handle quoting correctly.

## 2.6 Deploy a minimal observation flow

Before adding database writes, deploy:

~~~text
mqtt in -> json -> debug
~~~

Use the status indicator on the MQTT node:

- connected: broker connection is active;
- disconnected: hostname, port, credentials, or broker availability problem;
- no messages: no sensor uplink has arrived, topic is wrong, or ChirpStack MQTT integration is not publishing.

Next: [03-build-telemetry-flow.md](03-build-telemetry-flow.md)
