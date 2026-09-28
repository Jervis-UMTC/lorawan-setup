# ChirpStack — Operator Manual

## What this technology does

ChirpStack is the LoRaWAN Network Server / application-event source. It validates LoRaWAN protocol/session state, handles OTAA, receives gateway uplinks, schedules downlinks, manages gateways/devices/profiles, and publishes application events consumed by Node-RED.

It is **not** the source-evidence authority. Gateway journal/evidence services remain a separate security lane.

## Current commissioned topology

```text
ULC-01 -> ChirpStack-1
ULC-02 -> ChirpStack-2
both -> same PostgreSQL database through local PgBouncer/HAProxy
both -> Valkey through local HAProxy writable-primary endpoint
both -> cloud MQTT through the commissioned workload route
region -> AS923
host private HTTP -> :18080
public normal path -> HTTPS through Reserved IPv4 / HAProxy
```

Current pinned server build uses ChirpStack `4.19.1`. Verify the deployed image digest before an upgrade rather than relying on this version string alone.

## Step 1 — Confirm both ChirpStack instances exist

Run on ULC-01 and ULC-02:

```bash
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -i chirpstack || true
sudo ss -lntp | grep ':18080\b' || true
```

**PASS means:** one intended ChirpStack instance is running per application node and the commissioned private HTTP listener exists.

If a host has no instance, do not immediately create a second one. Check whether it is an intentional maintenance state and inspect the Compose/service definition first.

## Step 2 — Verify HTTP readiness on each node

Run locally on each application node:

```bash
curl -fsS -o /dev/null -w 'HTTP=%{http_code}\n' http://127.0.0.1:18080/
```

If the commissioned listener is bound only to the VPC address on the current build, use that node's documented `10.104.0.x:18080` address instead.

**PASS means:** HTTP returns `200`.

A healthy UI/API response proves the process is serving; it does not yet prove PostgreSQL, Valkey, MQTT, or LoRaWAN traffic.

## Step 3 — Check recent logs without dumping secrets

First discover the exact container name from Step 1, then:

```bash
sudo docker logs --since=15m --tail=150 <CHIRPSTACK_CONTAINER>
```

Look for repeated PostgreSQL, Valkey, MQTT, region, migration, or panic/restart errors.

Do not paste secret-bearing configuration or tokens into the terminal to troubleshoot a connection error.

## Step 4 — Verify PostgreSQL dependency path

The current client path is:

```text
ChirpStack -> pgbouncer.internal.lorawan.com:6432
-> local PgBouncer
-> local HAProxy :15432
-> current Patroni primary :5432
```

First prove Patroni/PgBouncer independently using the PostgreSQL and HAProxy/PgBouncer guides. If the database path fails, fix that layer before editing ChirpStack.

## Step 5 — Verify Valkey dependency path

The current application endpoint is `valkey.internal.lorawan.com:16379` through local HAProxy. Use [09-valkey-sentinel.md](09-valkey-sentinel.md) to prove that endpoint reaches the current writable Valkey primary.

If the endpoint reports a replica, fix Sentinel/HAProxy routing. Do not hard-code ChirpStack to the currently elected data node.

## Step 6 — Verify MQTT dependency path

Use [04-mosquitto-mqtt.md](04-mosquitto-mqtt.md) to prove the cloud broker/listener and ChirpStack MQTT workload identity are healthy.

The normal gateway topic hierarchy remains under `as923/gateway/<gateway-eui>/...`. A broker TCP connection without a valid subscription/ACL is not enough.

## Step 7 — Verify AS923 consistency

Inspect the effective ChirpStack configuration without printing secret values. Confirm the active region uses the project's **AS923** region configuration and matches:

- Gateway-01 Concentratord region/channel plan;
- MQTT prefix `as923`;
- device profile;
- EMU-01 firmware region/RX settings.

Do not change only the ChirpStack region to make one join test pass.

## Step 8 — Verify the registered gateway

In the ChirpStack UI/API, find Gateway EUI:

```text
0016c001f139a1cb
```

Check:

- gateway exists once;
- recent last-seen/event activity appears after a known real gateway message;
- region/profile assignments are correct;
- no stale duplicate registration is being used.

If gateway MQTT events reach the broker but ChirpStack last-seen does not update, inspect ChirpStack MQTT subscription/ACL/region before touching the radio.

## Step 9 — Verify OTAA layer by layer

For an approved test device, observe one join attempt and answer these questions in order:

1. Did Gateway-01 receive the JoinRequest?
2. Did ChirpStack receive the gateway event?
3. Does the registered DevEUI/JoinEUI match the device?
4. Does protected root-key material match?
5. Did ChirpStack schedule a JoinAccept/downlink?
6. Did the gateway transmit it?
7. Did the device begin post-join uplinks?

Do not regenerate keys merely because step 1 or step 2 failed.

## Step 10 — Verify one real application event

Generate one real uplink from the approved device and confirm:

```text
Gateway RF event
-> cloud MQTT
-> ChirpStack gateway event
-> ChirpStack application event
-> Node-RED
-> telemetry database
```

For counted research work, use the research recorder/test procedure rather than an improvised manual observation.

## Safe configuration/upgrade procedure

1. confirm both nodes are healthy;
2. back up/export current configuration and relevant database state through the documented backup path;
3. pin the new image/version/digest;
4. review release/migration requirements;
5. update one ChirpStack node first;
6. verify HTTP + DB + Valkey + MQTT + one real uplink;
7. only then update the second node;
8. verify coexistence and public path;
9. retain rollback image/config until acceptance is complete.

Do not run competing schema migrations from two nodes simultaneously unless the selected ChirpStack release explicitly supports that workflow.

## Troubleshooting order

| Symptom | Start here |
|---|---|
| Both instances down | host/container/runtime/dependency outage |
| HTTP up, DB errors | PgBouncer/HAProxy/PostgreSQL |
| HTTP up, Valkey errors | Valkey/Sentinel/HAProxy |
| Gateway events at broker but not ChirpStack | MQTT workload identity/subscription/region |
| JoinRequest seen, no JoinAccept | registration/keys/profile/RX/downlink |
| ChirpStack app event exists, no telemetry | Node-RED/application path |
| Telemetry exists, no source evidence | evidence services, not ChirpStack |

## Safe recovery after a ChirpStack failure

1. Confirm whether the failure is limited to ULC-01 or ULC-02, or is shared by both. Read the current container name, image/digest, configuration and bounded recent logs before touching anything.
2. Prove the dependencies in order: PostgreSQL/PgBouncer primary-routed SQL, Valkey writable-primary endpoint, cloud Mosquitto route and correct AS923 subscription. Repair the first failing dependency instead of restarting both ChirpStack nodes.
3. If a single ChirpStack instance is unhealthy while its dependencies and peer are healthy, preserve its current Compose/configuration and restore or restart **only that instance** using the commissioned cloud runbook. Never bring up another copy on an unintended host.
4. Verify HTTP readiness, expected application/gateway configuration, database/Valkey/MQTT reconnection and one approved real application uplink. Check the public ingress route only if that access path was affected.
5. For a broken join/session, compare the exact device registration, protected OTAA material, frame-counter behavior, regional/RX settings and downlink scheduling before making a change. Do not clear device registrations, reset counters, rotate keys or change only one radio layer as a generic repair.
6. For database migration/version recovery, follow the explicit PostgreSQL/ChirpStack compatibility procedure; do not run a second schema migration concurrently or point an older server at an upgraded schema without checking support.

**Recovery PASS:** intended two-node serving boundary restored, dependencies healthy, no immediate error/restart loop, one representative real gateway and application event accepted, no loss of registered identities or bypass of authentication.

## Completion checklist

- both ChirpStack nodes running;
- both private HTTP checks return 200;
- PostgreSQL path healthy;
- Valkey endpoint points to writable primary;
- MQTT subscription/auth path healthy;
- active region is AS923;
- Gateway EUI `0016c001f139a1cb` shows fresh activity;
- one approved OTAA/post-join flow succeeds when that test is required;
- one real application event reaches Node-RED/telemetry.

## Complete deployment and provisioning companion

Start with [ChirpStack two-node deployment, actual registry, AS923, shared dependencies, safe migration and recovery](CHIRPSTACK-DEPLOYMENT-PROVISIONING-RECOVERY.md). It includes the 4.19.1-specific PostgreSQL DSN distinction, top-level AS923 loader path and node-local MQTT identity rules; an older minimal lab server is not the production cloud.

## Detailed runbooks

- [`../server/cloud-production/09-chirpstack-cloud-cluster.md`](../server/cloud-production/09-chirpstack-cloud-cluster.md)
- [`../server/cloud-production/12-gateway-and-device-migration.md`](../server/cloud-production/12-gateway-and-device-migration.md)
- [`../server/cloud-production/17-troubleshooting.md`](../server/cloud-production/17-troubleshooting.md)