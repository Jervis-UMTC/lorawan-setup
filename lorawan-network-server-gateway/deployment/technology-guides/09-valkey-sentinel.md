# Valkey / Sentinel — Operator Manual

## What these technologies do

Valkey stores ChirpStack's fast shared runtime/cache state. Sentinel monitors the Valkey nodes, elects/promotes a writable primary after an approved failure, and tells the HA routing layer which member is primary.

The deployment uses three Valkey data nodes plus three Sentinels. Sentinel quorum is `2`.

## Current application path

```text
ChirpStack
-> valkey.internal.lorawan.com:16379
-> local HAProxy writable-primary route
-> current Sentinel-elected Valkey primary :6379
```

The current primary can change. Do not force a failback simply to match a dated commissioning note.

## Step 1 — Discover service names instead of guessing

Run on each ULC host:

```bash
for s in valkey redis valkey-server redis-server; do
  systemctl is-active "$s" >/dev/null 2>&1 && echo "data-service=$s"
done
for s in valkey-sentinel redis-sentinel sentinel; do
  systemctl is-active "$s" >/dev/null 2>&1 && echo "sentinel-service=$s"
done
```

If the service is containerized on a future build, inspect the current runtime definition before changing anything.

## Step 2 — Check listeners

```bash
sudo ss -lntp | grep -E ':(6379|26379|16379)\b' || true
```

Expected conceptual ownership:

- Valkey data service: `6379` on intended private address;
- Sentinel: `26379` on intended private address;
- HAProxy writable-primary application endpoint: `16379`.

## Step 3 — Ask each Valkey data node for its role

Use the protected CA and authentication secret already provisioned for the service. Do not place the secret directly in documentation/history. **Do not use `valkey-cli -a <secret>` in real commands:** a command-line argument may be visible to other processes and process inventory collectors. Use the current approved protected privileged authentication harness, and **verify an authenticated PONG/ROLE rather than only CLI exit code**. The original Ubuntu commissioning observed an attempted `VALKEYCLI_AUTH` check return `NOAUTH` despite exit code 0; therefore don't assume that environment-variable loading is supported by the deployed CLI without a verified positive authentication test. If a secure CLI interface is not available, stop and obtain the protected operator procedure instead of exposing secrets through `-a` process arguments or terminal history. The commands below show placeholders to explain the endpoint, **not executable production commands**. Sentinel may have a separate credential from the data service; do not substitute one for the other.

Command shape:

```bash
valkey-cli --tls --cacert <VALKEY_CA> \
  -h <VALKEY_PRIVATE_IP> -p 6379 \
  ROLE
```

**PASS means:** exactly one data node reports primary/master in normal state and the remaining expected nodes report replica/slave relationships consistent with it.

## Step 4 — Check Sentinel quorum and elected primary

Against each Sentinel:

```bash
valkey-cli --tls --cacert <VALKEY_CA> \
  -h <SENTINEL_PRIVATE_IP> -p 26379 \
  SENTINEL CKQUORUM lorawan-valkey
```

Then:

```bash
valkey-cli --tls --cacert <VALKEY_CA> \
  -h <SENTINEL_PRIVATE_IP> -p 26379 \
  SENTINEL GET-MASTER-ADDR-BY-NAME lorawan-valkey
```

**PASS means:** quorum succeeds and Sentinels agree on the current primary address.

## Step 5 — Verify the application HA endpoint reaches the writable primary

Using the protected application secret:

```bash
valkey-cli --tls --cacert <VALKEY_CA> \
  --sni valkey.internal.lorawan.com \
  -h <LOCAL_HAPROXY_PRIVATE_IP> -p 16379 \
  ROLE
```

**PASS means:** the stable application endpoint reports primary/master.

If direct nodes are healthy but `:16379` reaches a replica, fix HAProxy/Sentinel role selection before restarting ChirpStack.

## Step 6 — Check ChirpStack only after the HA endpoint passes

If Valkey is healthy and `:16379` is correct, inspect ChirpStack logs for Valkey reconnect/auth/TLS errors. Do not point ChirpStack directly at a specific Valkey member as a workaround.

## Never run casually

```text
FLUSHALL
FLUSHDB
SENTINEL FAILOVER
manual replica promotion
mass key deletion
```

These are data/failover operations. Use them only under an explicit test, clean-reset, or recovery procedure with the application writers controlled.

## Safe maintenance rule

For one Valkey member:

1. establish the current primary from Sentinel/live `ROLE`;
2. verify the other members and Sentinel quorum;
3. determine whether the target is primary or replica;
4. if maintenance requires a role change, use the dedicated failover procedure rather than improvising;
5. maintain only the intended member;
6. verify it rejoins in the expected role;
7. verify Sentinel quorum;
8. verify `:16379` reports writable primary;
9. verify ChirpStack operation.

Do not repeatedly trigger failover to chase a preferred primary host.

## Troubleshooting map

| Symptom | First check |
|---|---|
| ChirpStack says Valkey unavailable | `:16379` listener/TLS/role |
| `:16379` returns replica | HAProxy/Sentinel primary discovery |
| Sentinels disagree | Sentinel connectivity/config/epoch/quorum |
| one replica stale | replication/network/disk/process |
| no writable primary | quorum/failover state; avoid manual split-brain |
| auth error on only one client | client secret/ACL/TLS identity |

Use bounded service logs after role checks, not before.

## Backup/recovery note

Valkey is not the durable telemetry authority, but its runtime state matters for ChirpStack behavior. Preserve the commissioned persistence/replication settings. Do not restore an arbitrary old RDB over a healthy active cluster without the dedicated recovery procedure.

## Completion checklist

- all intended data services reachable;
- exactly one writable primary;
- expected replicas attached;
- all intended Sentinels reachable;
- Sentinel quorum passes;
- Sentinels agree on primary;
- HAProxy `:16379` reaches that writable primary;
- ChirpStack can use the stable endpoint.

## Complete installation and HA recovery companion

Use [Valkey/Sentinel TLS bootstrap, auth symmetry, role recovery and failover safety](VALKEY-SENTINEL-HA-RECOVERY.md). Do not reset replication or rerun a former primary's initial bootstrap state merely because Sentinel elected another host.

## Detailed runbook

- [`../server/cloud-production/08-mqtt-and-valkey.md`](../server/cloud-production/08-mqtt-and-valkey.md)
- [`../server/cloud-production/15-failover-chaos-and-acceptance-testing.md`](../server/cloud-production/15-failover-chaos-and-acceptance-testing.md)