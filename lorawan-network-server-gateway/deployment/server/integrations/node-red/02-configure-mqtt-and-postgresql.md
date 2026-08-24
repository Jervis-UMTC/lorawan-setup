# 2. Configure MQTT and PostgreSQL Connections

Use Node-RED's built-in MQTT nodes and a PostgreSQL palette node. The standard MQTT nodes are sufficient for ChirpStack events; a special ChirpStack node is optional and is not required for telemetry storage.

## 2.1 Install the PostgreSQL palette node

Before changing the palette, export the current flows and back up the Node-RED volume. In the Node-RED editor:

1. Open the menu and select **Manage palette**.
2. Note the current Node-RED and installed-node versions so the flow can be rolled back if the palette change fails.
3. Open **Install** and search for `node-red-contrib-postgresql`.
4. Select a reviewed version whose parameterized-query behavior has been checked; do not install an unknown moving release during commissioning.
5. Install it and restart Node-RED if requested.
6. Confirm the expected version is listed and the existing flows still load.

The selected node version must support parameterized queries through `msg.params`, which is required for safe sensor inserts. Verify its documented query and parameter property names against the installed version before building the flow. [node-red-contrib-postgresql documentation](https://flows.nodered.org/node/node-red-contrib-postgresql)

## 2.2 Configure the MQTT input node

Choose the profile **before** creating the broker configuration.

### Single-host lab

~~~text
Broker: mosquitto
Port: 1883
Username: node_red
Topic: application/+/device/+/event/up
QoS: 0
~~~

### Three-Droplet cloud HA POC

Run Node-RED on `ha-03` and map `mqtt-ha.internal.<DOMAIN>` to `ha-03`'s private IP. The local HAProxy `:18883` listener then follows Mosquitto-1 preferred / Mosquitto-2 backup.

~~~text
Broker: mqtt-ha.internal.<DOMAIN>
Port: 18883
TLS: enabled
CA: MQTT CA
Client certificate/key: Node-RED workload identity
Topic: application/+/device/+/event/up
QoS: 0
Output: parsed JSON, or string followed by a JSON node
~~~

The Node-RED MQTT certificate Common Name must match the read-only broker ACL identity created in the cloud MQTT manual. It receives application uplinks but no gateway-command or application-command write permission.

The topic is case-sensitive. Do not subscribe to gateway `event` topics when building the application telemetry flow.

Do not use `localhost` for either profile; inside a container, localhost points to the Node-RED container itself. [Node-RED MQTT connection guidance](https://cookbook.nodered.org/mqtt/connect-to-broker)

## 2.3 Add a JSON parser node when required

If the MQTT input produces a string:

1. Place a **json** node after mqtt in.
2. Configure it to convert the payload to an object.
3. Connect it to a **debug** node temporarily.
4. Deploy.

The debug output should show `deviceInfo`, `time`, `fPort`, `object`, `data`, and possibly `rxInfo`. Limit debug output to the current test device, redact identifiers when exporting evidence, and remove or disable verbose debug nodes after testing because payloads and location metadata may be sensitive.

## 2.4 Configure the PostgreSQL connection node

Choose the matching database profile.

### Single-host lab

~~~text
Host: telemetry-db
Port: 5432
Database: lorawan_telemetry
User: telemetry_writer
SSL: private lab policy
~~~

### Three-Droplet cloud HA POC

~~~text
Host: pgbouncer.internal.lorawan.com
Port: 6432
Database: lorawan_telemetry
User: telemetry_writer
SSL: enabled with hostname/CA verification
CA: internal PgBouncer/PostgreSQL trust bundle required by the cloud design
~~~

Map `pgbouncer.internal.lorawan.com` to `ha-03`'s private IP for the Node-RED container. PgBouncer then uses local HAProxy `:15432` to follow the current Patroni primary.

**Stop here. Do not build the write flow** until a read-only connection test and a rollback insert as `telemetry_writer` succeed through this exact endpoint.

The Node-RED database connection is not the same role/database as ChirpStack:

| Consumer | Database | Role |
|---|---|---|
| ChirpStack | `chirpstack` | `chirpstack` |
| Node-RED | `lorawan_telemetry` | `telemetry_writer` |

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

Use the status indicator on the MQTT node. A connected indicator proves only that the broker session exists; it does not prove that ChirpStack publishes the expected application topic or that payloads are decoded correctly:

- connected: broker connection is active;
- disconnected: hostname, port, credentials, or broker availability problem;
- no messages: no sensor uplink has arrived, topic is wrong, or ChirpStack MQTT integration is not publishing.

Next: [03-build-telemetry-flow.md](03-build-telemetry-flow.md)
