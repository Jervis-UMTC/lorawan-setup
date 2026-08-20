# Server 13. Failure and Recovery Tests

## Goal

Prove the single-VM Docker lab behaves correctly when individual services or containers fail.

Run these tests only after a real gateway and real test device can produce an accepted ChirpStack uplink and TimescaleDB storage is working.

## Before you start

Run on the **lab server VM**:

```bash
cd /opt/lorawan-lab
. ./.env
docker compose ps
docker compose exec spilo-1 patronictl list
docker compose exec etcd-1 sh -lc 'ETCDCTL_API=3 etcdctl --endpoints=http://etcd-1:2379,http://etcd-2:2379,http://etcd-3:2379 endpoint health --cluster'
```

Confirm one fresh real uplink before injecting a failure.

Do not test two failures at once unless that exact combined failure is the test objective.

## Test 0 - Confirm the full-stack resource budget is healthy

Run before the failure tests:

```bash
free -h
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true
```

Pass:

- no container is in a restart loop because of memory pressure;
- the kernel has not OOM-killed a lab service;
- the VM has about 1 GiB or more `available` memory before fault injection;
- a service is not sitting above roughly 85% of its memory limit while idle.

If this fails, do not delete a technology. First check PostgreSQL connection counts, PgBouncer pools, TimescaleDB workers, runaway Node-RED flows, Grafana query ranges, and unexpected traffic.

## Test 1 - Stop one etcd member

```bash
docker compose stop etcd-3
```

Verify the remaining quorum:

```bash
docker compose exec etcd-1 sh -lc 'ETCDCTL_API=3 etcdctl --endpoints=http://etcd-1:2379,http://etcd-2:2379 endpoint health --cluster'
docker compose exec spilo-1 patronictl list
```

Pass:

- two etcd members remain healthy;
- Patroni still has one leader;
- PostgreSQL writes continue.

Restore:

```bash
docker compose start etcd-3
```

Do not stop a second etcd member until all three are healthy again.

## Test 2 - Stop the PostgreSQL leader

Find the current leader:

```bash
docker compose exec spilo-1 patronictl list
```

Stop that exact container:

```bash
docker compose stop <CURRENT_SPILO_LEADER>
```

Watch promotion:

```bash
docker compose exec spilo-2 patronictl list
```

Then test the application database route through PgBouncer:

```bash
docker run --rm --network lorawan-lab_application "$POSTGRES_CLIENT_IMAGE" \
  psql 'host=pgbouncer port=6432 dbname=chirpstack user=chirpstack sslmode=disable' \
  -c 'SELECT inet_server_addr(), pg_is_in_recovery();'
```

Pass:

- one replica promotes;
- `pg_is_in_recovery()` is `false` through PgBouncer;
- no ChirpStack DSN edit is required;
- a new real uplink is accepted after recovery.

Restore the old leader:

```bash
docker compose start <OLD_SPILO_LEADER>
```

Verify it returns as a replica.

## Test 3 - Restart HAProxy

```bash
docker compose restart haproxy
docker compose logs --since=2m --tail=100 haproxy
```

Pass: PgBouncer reconnects and a new SQL connection succeeds.

## Test 4 - Restart PgBouncer

```bash
docker compose restart pgbouncer
docker compose logs --since=2m --tail=100 pgbouncer
```

Pass: ChirpStack reports only transient database connection errors and recovers without a configuration change.

## Test 5 - Restart Valkey

```bash
docker compose restart valkey
docker compose logs --since=2m --tail=100 valkey chirpstack
```

Generate a fresh uplink after Valkey returns.

Pass: ChirpStack reconnects and processes the uplink.

## Test 6 - Stop server Mosquitto and verify gateway buffering

On the server VM:

```bash
docker compose stop mosquitto
```

Generate several real device uplinks while the broker is stopped.

On the gateway, confirm its local Mosquitto persistence file grows or changes as documented in:

[Gateway 6 - Verify Gateway OS, MQTT buffering, and integrity](../../gateway/setup/06-verify-gateway-os.md)

Restore:

```bash
docker compose start mosquitto
```

Pass:

- gateway mTLS bridge reconnects;
- queued uplinks drain;
- downstream storage keeps one canonical event row per real uplink;
- stale downlink commands are not replayed;
- the gateway integrity journal continued sequencing while the broker was unavailable;
- the server checkpoint did not falsely advance while its evidence upload path was unreachable;
- after recovery, missing journal segments upload and extend the previous accepted checkpoint;
- the read-only server gateway-MQTT evidence copy can be correlated with the drained events when the reviewed v2 integrity implementation is enabled.

## Test 6A - Gateway evidence verifier unavailable

Run this only after the reviewed gateway-integrity server implementation exists. Stop or isolate **only** the verifier role; do not stop MQTT, ChirpStack, Node-RED, or TimescaleDB.

Generate one normal telemetry event and one v2-selected event.

Pass:

- MQTT, ChirpStack, Node-RED, and TimescaleDB continue;
- gateway journal/checkpoint ingestion may continue independently if those roles are still healthy;
- the v2 event remains unsealed/ineligible while verification is unavailable;
- no OpenBao sign request or Fabric transaction is created merely because the verifier is down;
- after verifier recovery, the event is processed only if its full lineage reaches `verified`.

## Test 6B - Gateway evidence conflict

Use isolated/copy fixtures, not the only production-like evidence. Inject either a journal-vs-remote-MQTT payload conflict or a trusted-decoder-vs-TimescaleDB mismatch.

Pass:

- verification becomes `integrity_failure`;
- the conflict is preserved for investigation;
- v2 Fabric promotion stops;
- telemetry ingestion remains independently available;
- no component rewrites one source to make the conflict disappear.

## Test 7 - Restart ChirpStack

```bash
docker compose restart chirpstack
docker compose logs --since=3m --tail=200 chirpstack
```

Pass:

- PostgreSQL connection returns through PgBouncer;
- Valkey reconnects;
- Mosquitto reconnects;
- region configuration loads;
- real uplink processing resumes.

## Test 8 - Restart TimescaleDB

```bash
docker compose restart telemetry-db
docker compose logs --since=3m --tail=100 telemetry-db node-red
```

Pass: Node-RED exposes the database failure instead of silently reporting success, then resumes storage after TimescaleDB returns.

If application MQTT events can arrive while telemetry storage is unavailable, document the accepted buffering/retry behavior. Do not pretend Node-RED memory is a durable database queue unless it has been explicitly designed and tested as one.

## Test 9 - Restart Node-RED

```bash
docker compose restart node-red
docker compose logs --since=3m --tail=100 node-red
```

Pass: editor authentication remains enabled, credentials decrypt correctly, and a new real uplink reaches TimescaleDB.

## Test 10 - Restart Grafana

```bash
docker compose restart grafana
docker compose logs --since=3m --tail=100 grafana
```

Pass: dashboards return and Grafana still uses `telemetry_reader` only.

## Test 11 - Fabric endpoint outage

Do not stop external Fabric infrastructure yourself.

Either coordinate a staging outage with the Fabric team or block only the adapter's route to `<FABRIC_GATEWAY_ENDPOINT>`.

Generate selected Fabric-eligible telemetry.

Pass:

- MQTT continues;
- ChirpStack continues;
- Node-RED continues;
- TimescaleDB continues storing telemetry;
- Fabric outbox jobs remain pending/failed/submitted_unknown according to failure point;
- retry delay increases according to bounded exponential backoff;
- no telemetry row is deleted or rolled back because Fabric is unavailable.

Restore the adapter route. The queue must drain without duplicate ledger state.

## Test 12 - OpenBao KMS restart and sealed state

This is intentionally a **total-KMS-outage simulation**, because the single-VM lab has only one OpenBao server. It proves that evidence sealing is an independent dependency of Fabric submission, not a dependency of telemetry ingestion. It does **not** prove production OpenBao HA.

In production, run an additional HA acceptance test against the stable KMS endpoint: stop only the current active OpenBao voter while quorum remains, prove another already-unsealed voter becomes active, prove Transit sign/verify continues through the unchanged service address, then restore/rejoin the failed voter. A configuration change to `OPENBAO_ADDR` during this test is a failure.

Confirm OpenBao is unsealed, then restart only OpenBao:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status
docker compose restart openbao
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status || true
```

The Shamir lab must report `Sealed: true` after restart. Generate one normal telemetry uplink and one Fabric-selected test uplink.

Pass while OpenBao is sealed:

- MQTT and ChirpStack continue;
- Node-RED and TimescaleDB continue storing telemetry;
- selected outbox work is preserved but cannot complete a new seal or the required Transit verification;
- the Fabric adapter backs off and releases/reclaims leases normally;
- no Fabric transaction bypasses KMS verification;
- no local evidence-private-key fallback exists.

Recover with two different OpenBao unseal shares entered at the hidden prompts:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status
```

Pass recovery only when OpenBao is unsealed, the adapter obtains fresh AppRole authorization, the preserved event is sealed/verified through Transit, and eligible Fabric work resumes without changing an existing seal. Complete the exact-byte checks in [Fabric 3](../fabric-attestation/03-test-and-reconcile.md).

## Test 13 - Fabric adapter crash after claim

Use the test procedure in [Fabric 3](../fabric-attestation/03-test-and-reconcile.md).

Pass:

- the claimed row stays `processing` until lease expiry;
- another worker does not reclaim early;
- the expired lease is reclaimable;
- attempts increment;
- `submitted_unknown` is never retried by the normal pending/failed worker.

## Final verification

After all tests:

```bash
docker compose ps
docker compose exec spilo-1 patronictl list
docker compose exec etcd-1 sh -lc 'ETCDCTL_API=3 etcdctl --endpoints=http://etcd-1:2379,http://etcd-2:2379,http://etcd-3:2379 endpoint health --cluster'
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status
```

OpenBao must be initialized and unsealed before the final Fabric verification.

Then verify one new real uplink, one telemetry row, and one safe Class A downlink.

When the reviewed gateway-integrity implementation is enabled, also verify one fresh accepted cloud checkpoint, one uploaded/verified journal segment, one unique journal-to-remote-MQTT/application lineage, one trusted-decoder comparison, and one final `verified` result. If v2 Fabric is enabled, prove the corresponding event was verified before its OpenBao seal was created.

## Next step

Continue with [14-backup-and-restore.md](14-backup-and-restore.md).
