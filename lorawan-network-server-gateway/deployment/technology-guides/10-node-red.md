# Node-RED — Operator Manual

## What this technology does

Node-RED is the application normalization and persistence layer between ChirpStack application MQTT events and PostgreSQL/TimescaleDB. It validates the decoded application event, derives a stable event identity, writes the canonical uplink plus normalized measurements, and performs the reviewed telemetry/outbox transaction logic.

Node-RED is **not** allowed to declare gateway evidence `verified`, sign with OpenBao, or submit to Fabric.

## Current commissioned topology

```text
ULC-03 -> Node-RED A -> ACTIVE
ULC-02 -> Node-RED B -> STAGED / STOPPED / FENCED
```

Only one subscriber/writer is allowed to be active at a time.

Current cloud paths:

```text
MQTT:
Node-RED -> mqtt.internal.lorawan.com:18884
         -> node-local HAProxy
         -> Mosquitto mTLS listener :8886

Database:
Node-RED -> pgbouncer.internal.lorawan.com:6432
         -> node-local PgBouncer/HAProxy
         -> current Patroni primary
         -> lorawan_telemetry
```

Application subscription:

```text
application/+/device/+/event/up
```

Do not feed gateway Protobuf `as923/gateway/.../event/...` messages directly into the application-decoding flow.

## Rule zero — prove there is only one active writer

Before starting, restarting, or promoting Node-RED, inspect **both** candidates.

On ULC-03 and ULC-02:

```bash
if [ -d /etc/lorawan-cloud/node-red ]; then
  cd /etc/lorawan-cloud/node-red
  sudo docker compose --env-file node-red.env ps
else
  echo 'NODE_RED_PATH_NOT_FOUND=/etc/lorawan-cloud/node-red; inspect current container mounts/Compose labels before recreating'
fi
```

**Normal commissioned result:** ULC-03 is the active Node-RED A runtime. ULC-02 is staged but not running as an active subscriber/writer.

**Hard stop:** if both are actively subscribing/writing, do not restart both. Fence one according to the HA runbook and then check for duplicate side effects.

## Step 1 — Check the active container and recent logs

On the active host:

```bash
cd /etc/lorawan-cloud/node-red
sudo docker compose --env-file node-red.env ps
sudo docker compose --env-file node-red.env logs --since=15m --tail=150 node-red
```

If the Compose service name has deliberately changed, discover it from the current project with `sudo docker compose --env-file node-red.env config --services` rather than guessing.

**PASS means:** the active service is running without a restart loop and there is no repeating MQTT, PostgreSQL, flow exception, or credential error.

## Step 2 — Verify the MQTT dependency before editing a flow

Confirm the local HAProxy Node-RED route exists:

```bash
sudo ss -lntp | grep ':18884\b' || true
```

Then use the Mosquitto manual to prove the Node-RED workload identity can subscribe to the intended application topic through the commissioned TLS/mTLS route.

If ChirpStack is publishing application events but Node-RED is not receiving them, inspect:

1. `:18884` HAProxy route;
2. Mosquitto `:8886` backend;
3. Node-RED MQTT client certificate/identity;
4. ACL/subscription topic;
5. Node-RED connection configuration.

Do not broaden the broker ACL to `#` merely to make the flow connect.

## Step 3 — Verify the database dependency

Confirm local PgBouncer exists:

```bash
sudo ss -lntp | grep ':6432\b' || true
```

Use the PostgreSQL/PgBouncer manuals to prove a protected `telemetry_writer`-equivalent connection can reach the current Patroni primary through the normal route.

Do not point Node-RED directly at today's PostgreSQL leader.

## Step 4 — Verify one recent telemetry row independently of Node-RED

Using a read-only PostgreSQL role, query:

```sql
SELECT time, dev_eui, metric_name, metric_value, metric_text, metric_bool, unit, quality
FROM telemetry.measurements
ORDER BY time DESC
LIMIT 20;
```

**PASS means:** recent rows are present after a known approved device event and their values/timestamps are plausible.

The database query is the authoritative persistence check. A green Node-RED node in the editor is not proof that the transaction committed.

## Step 5 — Verify stable event identity / duplicate safety

For a known uplink, confirm only one canonical application event row exists for its stable natural/event identity according to the current schema.

If MQTT redelivery creates a second database row, treat that as an idempotency defect. Do not solve it by weakening MQTT QoS or deleting rows manually.

## Step 6 — Verify normalized measurements

For the same known event:

1. confirm the canonical `telemetry.uplinks` row exists;
2. confirm expected `telemetry.measurements` rows exist;
3. compare timestamp/device identity/test sequence with the source application event;
4. verify units and quality fields are populated according to the reviewed mapping.

For EMU-01, use the frozen payload-v2 mapping. Do not silently feed SEC-02's different temporary payload format through the EMU-01 decoder.

## Step 7 — Understand the Fabric outbox boundary correctly

Node-RED/SQL may create selected durable outbox work according to the reviewed current transaction path, but an outbox row by itself is **not permission to submit to Fabric**.

For the current v2 path, Fabric claim eligibility additionally requires:

```text
immutable finalized_payload exists
AND
matching gateway_evidence.event_verification.status = verified
```

Do not manually change `pending` to another state, fabricate `verified`, fill `finalized_payload` by reconstructing JSON, or insert a replacement outbox row to make the queue drain.

Use the Fabric Adapter manual to diagnose queue state after the telemetry transaction is proven.

## Step 8 — Verify evidence ownership was not crossed

Node-RED must not possess credentials or SQL permissions that let it:

- set verifier-owned evidence rows to `verified`;
- call OpenBao Transit sign;
- access Fabric client private keys;
- submit Fabric transactions.

If a flow contains any of those authorities, stop and review the deployment because the trust separation has been broken.

## Safe flow-change procedure

1. prove which Node-RED candidate is active;
2. keep the standby fenced;
3. export/back up the current approved flow/runtime configuration using the Node-RED runbook;
4. identify the smallest node/function/subflow to change;
5. test with a non-destructive fixture when possible;
6. deploy the change on the active candidate only after syntax/configuration review;
7. observe one known application event;
8. verify the committed database row independently;
9. verify duplicate/idempotency behavior if event identity logic changed;
10. verify evidence/Fabric authority boundaries remain unchanged;
11. update/stage the standby through the active/passive runbook only after the active revision passes.

Do not edit both candidates independently and assume they remain equivalent.

## Planned failover rule

Promotion is a **fenced active/passive operation**:

```text
prove A is stopped/fenced
-> prove its MQTT session/writer is no longer active
-> start/promote B
-> verify B MQTT + DB path
-> verify one representative real operation
```

Never start B first and then stop A later.

Use the dedicated active/passive HA guide for the exact promotion/failback procedure.

## Troubleshooting map

| Symptom | First check |
|---|---|
| ChirpStack event exists, Node-RED sees nothing | MQTT `18884/8886`, identity, ACL, topic |
| Node-RED receives event, no DB row | validation/function error, PgBouncer/DB, transaction rollback |
| Uplink row exists, measurements absent | normalization/mapping/schema path |
| duplicate telemetry rows | stable event key + unique constraints + retry path |
| telemetry exists, outbox absent | current selection/transaction policy; do not fabricate row |
| outbox exists but not claimed | finalized payload + verifier eligibility + adapter state |
| two writers active | HA fencing failure; stop duplicate authority safely |

## Safe recovery and rollback

1. Determine the **current single authorized writer** from both ULC-03 and ULC-02 before any start/restart. The normal documented placement is A active on ULC-03 and B fenced on ULC-02; a deliberate approved failover can change this.
2. If the active container or flow is failing, preserve its deployed flow, protected runtime configuration, exact image/version, and recent bounded logs. Prove MQTT application messages and the PgBouncer writable-primary route separately before treating Node-RED as the failing layer.
3. For a failed flow deployment, restore the last reviewed flow/configuration on the current owner, then validate one known event's canonical uplink and complete normalized measurement transaction directly in the database. Do not patch the database or manufacture a missing outbox/verifier result to disguise the flow failure.
4. If the entire active host is lost, use the dedicated fenced active/passive procedure: prove A is stopped or decisively fenced, prove no active subscriber/writer remains, then promote B with its approved identical flow/image and protected identity. Never run the two as simultaneous independent writers.
5. After recovery, verify exactly one authorized MQTT subscriber/writer, valid database primary routing, correct event idempotency under redelivery, and unchanged evidence/Fabric privilege separation. Do not use a successful HTTP health response alone as recovery acceptance.

**Rollback PASS:** the intended single-writer boundary and last accepted flow are restored, a representative real event is stored exactly once, and the standby remains fenced unless explicitly promoted.

## Completion checklist

- ULC-03 active writer is healthy unless an approved failover deliberately moved ownership;
- ULC-02 standby remains fenced when not owner;
- exactly one active application subscriber/writer exists;
- MQTT route `:18884 -> :8886` works;
- database route `:6432` works;
- one real approved application event produces one canonical telemetry record;
- normalized measurement rows match the reviewed mapping;
- duplicate delivery does not create duplicate authoritative telemetry;
- Node-RED cannot create verifier authority or Fabric/OpenBao authority.

## Complete installation and recovery companion

Use [Node-RED ingestion, verified payload-v2 field mapping, runtime file/secret layout and fenced A/B recovery](NODE-RED-INGESTION-HA-RECOVERY.md). This explains why the live cloud uses `/etc/lorawan-cloud/node-red` rather than the old lab `/opt/lorawan-lab`, and why Node-RED's QoS 0 subscription is not lossless under a stopped-writer promotion.

## Detailed guides

- [`../server/integrations/node-red/00-README.md`](../server/integrations/node-red/00-README.md)
- [`../server/integrations/node-red/06-active-passive-ha.md`](../server/integrations/node-red/06-active-passive-ha.md)
- [`../server/cloud-production/12a-node-red-timescale-telemetry.md`](../server/cloud-production/12a-node-red-timescale-telemetry.md)