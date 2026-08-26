# 12A. Node-RED -> TimescaleDB Telemetry Application Layer

> **Status: REQUIRED PRE-TEST SETUP / DRAFT.** Execute this only after the public MQTT path, physical gateway normal path, and the Phase 13A backup/restore safety checkpoint are ready. This phase commissions the application ingestion path. It does **not** inject broker, database, host, LTE, or Fabric failures; those belong to Phase 15.

## 12A.1 Goal

Make Node-RED the controlled application transformation layer **before** telemetry reaches the database:

```text
LoRaWAN sensor
  -> Gateway
  -> MQTT
  -> ChirpStack
  -> application/+/device/+/event/up
  -> Node-RED
       validate
       normalize
       derive stable event_key
       build parameterized SQL
  -> one PostgreSQL statement / transaction
       -> telemetry.uplinks
       -> telemetry.measurements
       -> optional telemetry.fabric_outbox row
  -> COMMIT
```

Node-RED is not the database, KMS, Fabric adapter, or cryptographic trust anchor. It must never sign evidence or wait synchronously for Hyperledger Fabric.

## 12A.2 Preconditions

Before any Node-RED mutation, prove:

```text
Phase 9 ChirpStack two-node commissioning = PASS
Phase 10 public ingress normal path = commissioned
Phase 11 physical gateway normal MQTT path = commissioned
Phase 13A database backup + isolated restore rehearsal = PASS
Patroni = 1 primary + 2 streaming replicas
lorawan_telemetry exists with TimescaleDB enabled
telemetry_writer and telemetry_reader authentication paths = PASS
ulc-03 local PgBouncer :6432 and HAProxy :15432 = healthy
one real staging device/gateway can produce an accepted ChirpStack application uplink
```

If the deployment is a migration, Phase 12 must also have made the cloud ChirpStack path authoritative before Node-RED writes production-like telemetry.

## 12A.3 Commission a dedicated private Node-RED MQTT route on ulc-03

Do not use the obsolete `mqtt-ha.internal.<DOMAIN>` placeholder and do not pin Node-RED to ulc-01 or ulc-02.

The commissioned ChirpStack `:18883` frontends on ulc-01/02 terminate at the dedicated username/password `:8885` workload listeners and are **not** the Node-RED mTLS route. Keep them unchanged.

For Node-RED, commission a separate private HAProxy frontend on ulc-03:

```text
Node-RED
  -> mqtt.internal.lorawan.com:18884
  -> ulc-03 HAProxy 10.104.0.8:18884
  -> preferred Mosquitto-1 10.104.0.2:8884
  -> backup    Mosquitto-2 10.104.0.4:8884
```

Why `:18884`: the existing `:8884` broker listener already uses client-certificate authentication and is the correct place for a read-only Node-RED workload identity. A distinct ulc-03 frontend avoids confusing it with the already-commissioned ChirpStack `:18883` password-auth route.

### Broker identity and ACL

Create one Node-RED **ingestion** client certificate under the MQTT client CA. Its broker ACL is only:

```text
user <NODE_RED_MQTT_IDENTITY>
topic read application/+/device/+/event/up
```

Do not grant gateway-event reads or application/gateway command writes to this identity.

Before changing either broker, inspect the current `:8884` listener and ACL. Add the Node-RED identity to the gateway-facing mTLS ACL on one broker at a time, validate Mosquitto configuration off-path, activate one broker, prove the existing gateway identities still work, then repeat on the second broker. Do **not** deliberately stop the healthy broker to test failover here.

### ulc-03 HAProxy shape

Add only after both `:8884` backends accept the Node-RED certificate:

```haproxy
frontend node_red_mqtt_tls
    bind 10.104.0.8:18884
    mode tcp
    default_backend node_red_mqtt_brokers

backend node_red_mqtt_brokers
    mode tcp
    option tcp-check
    server mqtt-ulc01 10.104.0.2:8884 check
    server mqtt-ulc02 10.104.0.4:8884 check backup
```

Validate with `haproxy -c` before reload. After reload, prove TLS through `10.104.0.8:18884` using SNI/hostname `mqtt.internal.lorawan.com` and the Node-RED client certificate. Prove that `application/+/device/+/event/up` is readable and an intentionally forbidden command publication is denied.

No public listener is created on ulc-03.

## 12A.4 Database route from Node-RED

Node-RED uses:

```text
pgbouncer.internal.lorawan.com:6432
  -> ulc-03 10.104.0.8:6432
  -> local HAProxy :15432
  -> current Patroni primary
  -> lorawan_telemetry
```

Use `telemetry_writer` only. Keep hostname/CA verification enabled. Do not use `telemetry_admin`, `postgres`, or the ChirpStack role.

Before starting Node-RED, prove a rollback-only insert/duplicate test through this exact path using the procedures in:

- `../integrations/timescaledb/02-create-telemetry-schema.md`
- `../integrations/timescaledb/03-connect-and-verify.md`

The required Timescale objects are:

```text
telemetry.uplinks        hypertable
telemetry.measurements   hypertable
telemetry.device_registry
telemetry.latest_uplinks
telemetry.latest_measurements
```

`telemetry.fabric_outbox` is an ordinary PostgreSQL table and is created/protected before Fabric selection is enabled.

## 12A.5 Deploy Node-RED on ulc-03

Use the cloud profile in:

- `../integrations/node-red/01-deploy-node-red.md`
- `../integrations/node-red/02-configure-mqtt-and-postgresql.md`
- `../integrations/node-red/03-build-telemetry-flow.md`

Required cloud substitutions:

```text
Node-RED host:              ulc-03 / 10.104.0.8
Editor listener:            127.0.0.1:1880 only
MQTT host:                  mqtt.internal.lorawan.com
MQTT port:                  18884
MQTT TLS:                   mTLS, hostname/CA verification enabled
MQTT topic:                 application/+/device/+/event/up
Database host:              pgbouncer.internal.lorawan.com
Database port:              6432
Database:                   lorawan_telemetry
Database role:              telemetry_writer
```

Container host mappings:

```text
mqtt.internal.lorawan.com       -> 10.104.0.8
pgbouncer.internal.lorawan.com  -> 10.104.0.8
```

Pin the Node-RED image and PostgreSQL palette version. Protect the Node-RED credential secret and database/MQTT credentials outside Git. Require authenticated editor access through an SSH tunnel; never publish the editor publicly as a troubleshooting shortcut.

## 12A.6 Prove MQTT before database writes

Deploy only:

```text
mqtt in -> json -> debug
```

Send one real staging-device uplink through the normal gateway/ChirpStack path.

For the EMU-01 payload-v2 baseline, require the expected application event to contain the reviewed fields such as:

```text
payload_version = 2
test_sequence
sensor_validity_bitmap
approved decoded sensor values
```

The MQTT node being “connected” is not enough. A real current application event must arrive.

## 12A.7 Enable validation/normalization and atomic telemetry writes

Use the reviewed function/SQL in `../integrations/node-red/03-build-telemetry-flow.md`.

The order is:

```text
ChirpStack event
  -> validate DevEUI/time/payload version
  -> normalize approved decoded values/units
  -> derive stable event_key
  -> parameterized SQL
  -> INSERT uplink
  -> INSERT normalized measurements
  -> COMMIT
```

Invalid sensor-validity groups must not be mislabeled as measured stale values. Preserve the complete decoded object in `payload_json` while normalized metrics go into `telemetry.measurements`.

Do not decode the LoRaWAN binary payload a second time in Node-RED when ChirpStack has already run the approved codec.

## 12A.8 Prove retry safety before Fabric selection

Deliberately replay the **same application event** through the Node-RED flow without changing its stable identity.

Pass when database uniqueness rules leave:

```text
exactly one canonical telemetry.uplinks row
exactly one row per normalized metric identity
no second canonical application record
```

This is an application idempotency verification, not a service-failure injection.

## 12A.9 Create and protect the Fabric outbox, then enable one selected event

Before Node-RED can enqueue Fabric work, complete the outbox schema/permissions/immutability portion of:

`../fabric-attestation/02-create-outbox-and-adapter.md`

Node-RED may then add the reviewed outbox CTE to the **same PostgreSQL statement**:

```text
BEGIN-equivalent single statement
  telemetry.uplinks
  telemetry.measurements
  selected telemetry.fabric_outbox
COMMIT
```

For the first commissioning proof, select only the approved staging device/event. Do not send every sample to Fabric merely because the queue exists.

Node-RED stores only the source identity and queue request. It does **not** create `canonical_json`, calculate the production evidence digest, sign with OpenBao, or mark Fabric confirmation.

## 12A.10 Normal-path pass condition

Phase 12A passes only when all are true:

```text
ulc-03 private Node-RED MQTT HAProxy route :18884 exists and is private
Node-RED mTLS identity can read only approved application uplinks
Node-RED editor is authenticated and loopback-only
telemetry_writer connects through local PgBouncer/HAProxy with TLS verification
one real staging uplink reaches Node-RED
Node-RED validates/normalizes the event before database storage
one canonical uplink + reviewed measurements are stored
replaying the same event does not create duplicates
one selected event can atomically create a fabric_outbox row
Fabric/KMS are not called synchronously from Node-RED
```

Do **not** stop Mosquitto, Patroni, PgBouncer, HAProxy, Node-RED, ulc-03, or the gateway in this phase. Those failure cases belong to Phase 15 after all pre-test components are commissioned.

Next setup phase: [14a-grafana-cloud-deployment.md](14a-grafana-cloud-deployment.md).
