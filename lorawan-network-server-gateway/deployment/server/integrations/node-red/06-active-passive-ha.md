# 6. Active/Passive Node-RED HA

This guide defines the cloud Node-RED availability contract for the three-Droplet deployment. It does not change the single-host lab profile.

## 6.1 Goal

Keep exactly one ingestion processor active while maintaining a ready second copy that can take over after the active Node-RED process or host is lost.

```text
NORMAL

ulc-03 / 10.104.0.8
  Node-RED A = ACTIVE
  mqtt.internal.lorawan.com      -> 10.104.0.8:18884
  pgbouncer.internal.lorawan.com -> 10.104.0.8:6432

ulc-02 / 10.104.0.4
  Node-RED B = STANDBY / container stopped
  mqtt.internal.lorawan.com      -> 10.104.0.4:18884
  pgbouncer.internal.lorawan.com -> 10.104.0.4:6432

MQTT backends
  ulc-01:8886 preferred
  ulc-02:8886 backup

Database
  local PgBouncer :6432
    -> local HAProxy :15432
    -> current Patroni primary
```

The **single-active invariant** is mandatory. Never start B while A may still be consuming `application/+/device/+/event/up`. Ordinary MQTT subscribers would both receive the uplink and create avoidable duplicate work. Database uniqueness remains a safety backstop, not the HA coordination mechanism.

## 6.2 Why the standby is stopped

A stopped standby is simpler and safer than two always-running Node-RED instances:

- it cannot accidentally subscribe and process the same uplink;
- it does not consume steady-state Node-RED RAM/CPU on ulc-02;
- it can still be pre-staged with the exact image, flows, settings, palette versions, CA files, and protected environment;
- promotion is explicit and auditable.

This is active/passive availability, not active/active load sharing. If automatic election is added later, it must preserve the same fence-before-start rule and be proven under Phase 15 before it is described as automatic HA.

## 6.3 Files and configuration that must match

Both candidates must use the same reviewed application revision:

```text
Node-RED image digest
flows.json / approved flow export
flows_cred.json when used
settings.js
package.json and locked palette versions
LORAWAN_REGION_ID
NODE_RED_CREDENTIAL_SECRET
telemetry schema/event_key contract
```

`NODE_RED_CREDENTIAL_SECRET` must match if the encrypted credential file is shared between candidates. Store it through the same protected secret-handling procedure on both hosts; never commit it to Git.

Do **not** copy a live `/srv/node-red/data` tree while A is running. Build a versioned deployment bundle from an approved quiescent/exported state, validate its hashes, then install the same bundle on both candidates. Keep host-specific secrets outside that bundle.

## 6.4 Identities

Use separate MQTT client certificates and keys:

```text
Node-RED A / ulc-03: node-red-ingest
Node-RED B / ulc-02: node-red-ingest-standby
```

Both broker ACL entries are read-only:

```text
topic read application/+/device/+/event/up
```

The two Node-RED broker configurations also need distinct MQTT client IDs. Never copy A's private key onto B merely to make failover easier.

The current `telemetry_writer` database role remains the least-privilege application writer for this POC. Both candidates connect only through their local PgBouncer/HAProxy path with TLS verification.

## 6.5 Dependency requirement on both hosts

Before claiming the standby is ready, prove:

```text
ulc-03:18884 -> ulc-01/02:8886
ulc-02:18884 -> ulc-01/02:8886
ulc-03:6432  -> local :15432 -> Patroni primary
ulc-02:6432  -> local :15432 -> Patroni primary
```

This is why B runs on ulc-02 instead of depending on ulc-03 remotely. Loss of ulc-03 must remove only A, not B's MQTT or database access path.

## 6.6 Normal state check

Run on both candidates and record the result before any failover test:

```bash
cd /etc/lorawan-cloud/node-red
sudo docker compose --env-file node-red.env ps node-red
sudo ss -lntp | grep ':1880' || true
```

Expected:

```text
ulc-03: node-red running; 127.0.0.1:1880 listening
ulc-02: node-red stopped; no :1880 listener
```

If both are running, stop and investigate immediately. Do not continue with an uplink test in a split-brain state.

## 6.7 Promotion: A -> B

Use short, sequential gates. Do not batch promotion with unrelated infrastructure changes.

1. Confirm A is failed or deliberately stop A. If the host is only partially reachable, explicitly fence the Node-RED container/service before proceeding.
2. Prove B's local `:18884` MQTT route and `:6432` database route are healthy.
3. Confirm B has the approved deployment revision and its own MQTT certificate/key.
4. Confirm A is not running.
5. Start B.
6. Verify B's editor remains loopback-only, MQTT connects, and PostgreSQL connects through local PgBouncer.
7. Send a **fresh** staging uplink and prove exactly one canonical telemetry row is created.
8. Record B as the active instance. Do not automatically restart A when its host returns.

Example start on B after the fence gate:

```bash
cd /etc/lorawan-cloud/node-red
sudo docker compose --env-file node-red.env up -d node-red
sudo docker compose --env-file node-red.env ps node-red
sudo ss -lntp | grep '127.0.0.1:1880'
```

## 6.8 Failback: B -> A

Failback uses the same stop-before-start rule:

1. Rejoin/recover ulc-03 without starting Node-RED A.
2. Update A to the exact approved flow/image/settings revision currently active on B.
3. Validate A's local MQTT and database routes.
4. Stop B and prove its `:1880` listener is gone.
5. Start A.
6. Send one fresh uplink and prove exactly one telemetry row.
7. Return B to stopped standby state.

Do not perform a rolling overlap where both A and B run for convenience.

## 6.9 QoS and data-loss boundary

The current Node-RED application subscription is QoS 0. Therefore active/passive HA improves recovery from a Node-RED/host outage but **does not guarantee replay of uplinks published while no Node-RED subscriber is active**.

```text
A fails
  -> promotion window
     -> QoS-0 uplinks may be missed
  -> B starts
     -> fresh uplinks resume
```

The two Mosquitto brokers provide backend availability, but this project has not proven replicated MQTT client-session queues between them. Do not claim that a persistent session on one broker is automatically available on the other.

If the final production requirement is zero-loss ingestion, add a durable pre-processing queue or another reviewed at-least-once design and test broker/session failover explicitly. The existing `event_key` and database unique indexes remain necessary to make later at-least-once delivery retry-safe.

## 6.10 Phase 15 acceptance

Active/passive Node-RED passes only when all are true:

```text
A and B use the same pinned application revision
A and B have separate MQTT private keys/client identities
A and B each have a working local :18884 MQTT route
A and B each have a working local :6432 database route
normal state has exactly one active Node-RED
A failure is fenced before B starts
B processes a fresh post-promotion uplink exactly once
A can rejoin as stopped standby
controlled failback again preserves exactly one active instance
resource test passes on ulc-02 while B is active
promotion gap / any QoS-0 loss is measured and recorded
```

Do not claim automatic failover unless an actual automatic fencing/election mechanism is implemented and tested. Manual fenced promotion is still a valid active/passive topology, but its RTO includes operator detection and promotion time.

Next: return to [Phase 12A](../../cloud-production/12a-node-red-timescale-telemetry.md) for commissioning or [Phase 15](../../cloud-production/15-failover-chaos-and-acceptance-testing.md) for failure acceptance.

### Standby secret-group runtime boundary

Each candidate uses a host-local `node-red-secrets` group for its own MQTT client private key. The Node-RED container receives only that group's numeric GID through Compose `group_add`; do not add the host login user to the secret group. Keep each key `0640 root:node-red-secrets`, its directory `0750 root:node-red-secrets`, and the Node-RED data directory numeric `1000:1000` mode `0700`. `NODE_RED_SECRET_GID` is host-specific protected deployment metadata and is not part of the shared flow bundle. The same secret group also protects the candidate-local PgBouncer public-CA copy at `/etc/lorawan-pki/node-red-pgbouncer/ca.crt` (`0640 root:node-red-secrets`, directory `0750`). Its bytes must match the commissioned `/etc/lorawan-pki/pgbouncer/ca.crt` on that host; do not grant the container membership in the host `postgres` group.

### Repository-backed shared runtime layer

The canonical shared runtime layer is now `deployment/server/integrations/node-red/runtime/`. Keep `compose.yml`, `settings.js`, `package.json`, and `package-lock.json` identical on A and B. The exact dependency lock SHA-256 is `89289e301cab799ac7e85e2fbe2fc40b34ff195e799313a4f720c642397ba85e`. Host-local `node-red.env` supplies the private IP, secret-group GID, unique MQTT client ID, and protected secrets; it is not part of the shared bundle. `flows.json` is now generated from the reviewed telemetry mapping and exact pinned MQTT/TLS/PostgreSQL node contracts. Keep the same flow file on A and B; activation remains gated by dependency/runtime validation and the single-active rule.
