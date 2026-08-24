# 15. POC Failover and Acceptance Tests

> **Status: STANDBY / DRAFT.** Do not run full-stack failure tests until every dependency named by a test is deployed and individually accepted. Refine each failure procedure from the live architecture immediately before testing.

This file proves the **small HA model**, not production capacity.

Use one staging gateway/device. Inject one failure at a time and restore full health before the next test.

For every run create a unique identifier such as:

```text
HA-YYYYMMDD-<TEST>-R<NUMBER>
```

Record all timestamps in UTC.

Define the main LoRaWAN recovery time consistently:

```text
RTO start = timestamp immediately before the fault is injected
RTO end   = timestamp when the first NEW post-fault staging-device uplink is
            accepted through the surviving ChirpStack path
```

Record database-role recovery, MQTT reconnect, UI/API recovery, and outbox recovery separately rather than mixing them into one number.

### Standard test loop

Use this sequence for **every** failure scenario:

1. create the run ID and UTC start record;
2. capture the full healthy baseline below;
3. send one pre-fault real uplink and record its `test_sequence`/event key;
4. inject exactly one named failure;
5. record the exact fault timestamp and action;
6. observe quorum/role changes without manually forcing a second failure;
7. send fresh post-fault uplinks until the first one is accepted;
8. record RTO and any duplicates/gaps/reconnects;
9. restore the failed process/member/host;
10. wait for **3/3 quorum/replica redundancy where applicable** and confirm no pending repair;
11. send one post-restore uplink;
12. capture memory/OOM evidence and sanitized logs;
13. close the run only after the system is back at the normal baseline.

**Do not continue to the next test from a degraded state.** A second failure while a quorum group is still at `2/3` changes the experiment into a two-failure scenario.

## 15.1 Baseline before every failure

Capture:

```text
real uplink succeeds
both ChirpStack instances healthy
etcd 3/3
Patroni 1 primary + 2 replicas
both databases present: chirpstack + Timescale-enabled lorawan_telemetry
TimescaleDB extension version recorded; uplinks + measurements hypertables visible
Valkey primary + 2 replicas
3 Sentinels
Mosquitto-1 + Mosquitto-2 healthy
Reserved IPv4 owner recorded
public-ingress failover timer healthy on ha-01/ha-02
both HAProxy anchor listeners pass local health
OpenBao 3/3 healthy/unsealed
Fabric adapter state = healthy pair for a full-feature run; if the reviewed implementation is missing, mark the overall run BLOCKED before fault injection
host memory / swap / OOM log
```

Do not inject a failure from an already degraded baseline.

Useful baseline commands include the exact version-specific equivalents of:

```bash
# every cloud host
free -h
uptime
command -v vmstat >/dev/null && vmstat 1 5 || true
docker stats --no-stream
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true

# etcd administration host - current validated transport baseline
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint health

# If etcd transport TLS is deliberately deployed and validated before these tests,
# update this command to the matching tested https endpoints and CA/client credentials.

# PostgreSQL administration host
patronictl -c <PATRONI_CONFIG> list <PG_SCOPE> --extended

# PgBouncer on each client host
psql '<PGBOUNCER_ADMIN_DSN>' -c 'SHOW POOLS;'
```

Also record Valkey/Sentinel, Mosquitto, OpenBao, and Fabric-outbox states using their component manuals. Do not print secrets into the evidence bundle.

## 15.2 Lose ha-01

Fault injection procedure:

1. confirm `ha-02` and `ha-03` are healthy and redundancy is 3/3 before the test;
2. deliberately assign the Reserved IPv4 to `ha-01`, verify public HTTPS/MQTT health, and confirm `ha-02` is a healthy standby ingress candidate;
3. record whether `ha-01` currently owns the PostgreSQL primary, Valkey primary, active OpenBao role, preferred Mosquitto, or any live outbox lease;
4. from the provider console or the host, power off **ha-01 only** using the approved POC fault method;
5. do not manually promote PostgreSQL, Valkey, or the Reserved IP unless automatic failover itself is the thing being diagnosed;
6. watch the `ha-02` public-ingress agent take the etcd lock and reassign the Reserved IPv4;
7. send a fresh staging-device uplink and measure recovery;
8. after evidence is captured, power `ha-01` back on and wait for every colocated member/service to rejoin before closing the test. The Reserved IP should remain on `ha-02` until an operator deliberately moves it later.

Expected:

```text
Reserved IPv4 automatically moves to ha-02
DNS remains unchanged
ChirpStack-2 serves
Mosquitto-2 is available
etcd remains 2/3
OpenBao remains 2/3
Patroni remains/promotes a primary
Valkey remains/promotes a primary
adapter-2 remains only when the conditional Fabric execution scope is deployed
real uplink recovers
```

Record recovery time and memory on `ha-02`/`ha-03`.

Restore `ha-01` and wait for full replication/quorum before continuing.

## 15.3 Lose ha-02

Use the same host-loss procedure as 15.2, but first deliberately assign the Reserved IPv4 to **ha-02**, prove `ha-01` is a healthy ingress candidate, then power off **ha-02 only**. Record its current roles before failure because the PostgreSQL/Valkey primary may have moved during earlier tests.

Expected: the Reserved IPv4 automatically reassigns to `ha-01`, DNS remains unchanged, and quorum groups remain at 2/3.

Restore `ha-02`, wait for full membership/replication, and send a post-restore uplink before continuing.

## 15.4 Lose ha-03

Before fault injection, prove one telemetry row is committed and identify any existing eligible outbox row. Then power off **ha-03 only**.

Expected:

```text
etcd remains 2/3
OpenBao remains 2/3
PostgreSQL remains available on ha-01/ha-02
chirpstack database remains
Timescale-enabled lorawan_telemetry remains
telemetry hypertables remain
fabric_outbox remains
Valkey remains available/promotable
ChirpStack + MQTT continue
existing fabric_outbox remains; deployed adapter-1/2 may continue eligible work
Node-RED pauses
Grafana pauses
```

This test specifically proves that telemetry/outbox **storage** is no longer a single `ha-03` service.

Restore `ha-03`, wait for PostgreSQL/etcd/Valkey/OpenBao membership to return to 3/3, then restart/verify Node-RED and Grafana. Send a new uplink and prove telemetry ingestion resumes before the next test.

## 15.5 Planned PostgreSQL switchover

Use Patroni to move the primary deliberately.

Expected:

```text
HAProxy follows new primary
PgBouncer reconnects server connections
ChirpStack keeps same DB endpoint
Node-RED keeps same DB endpoint
Grafana keeps same DB endpoint
deployed Fabric adapters keep same DB endpoint; otherwise the outbox itself remains available
```

Verify both databases after the switchover. In `lorawan_telemetry`, also verify the TimescaleDB extension version and query `timescaledb_information.hypertables`; `telemetry.uplinks` and `telemetry.measurements` must still be present as hypertables.

## 15.6 Unplanned PostgreSQL primary loss

Stop only the current PostgreSQL/Patroni primary process or its host as planned.

Pass when:

```text
one replica promotes
only one writable primary exists
clients reconnect automatically
real uplink can be processed
Timescale-enabled lorawan_telemetry is writable again
Timescale hypertables are queryable on the promoted primary
```

## 15.7 Valkey primary loss

Stop the current Valkey primary.

Pass when Sentinel promotes a replica and ChirpStack recovers without endpoint edits.

## 15.8 Preferred Mosquitto loss

Stop **Mosquitto-1 only**, not HAProxy and not the whole `ha-01` host. This isolates broker-service failover from host failover.

Before stopping it, verify all HAProxy instances select Mosquitto-1 as preferred and the physical gateway has a healthy cloud bridge.

Pass when:

```text
gateway reconnects to backup path
gateway local QoS 1 queue protects bounded uplinks
new real uplink reaches ChirpStack
```

Restore Mosquitto-1, prove HAProxy returns to the intended preferred/backup ordering, and verify the gateway local queue is back at its normal drained state.

## 15.9 One ChirpStack process loss

Stop ChirpStack-1 only.

Pass when ChirpStack-2 processes a fresh real uplink and the public UI/API path still works through the unchanged Reserved IPv4. A single ChirpStack process loss should normally be handled by HAProxy backend routing without moving the Reserved IP.

## 15.10 One OpenBao member loss

Stop one OpenBao member.

Pass when:

```text
2/3 quorum remains
stable KMS endpoint still signs/verifies
adapter does not need a local fallback key
```

Restore 3/3.

## 15.11 One Fabric adapter loss

First check the adapter implementation readiness gate in [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md).

If the reviewed adapter implementation/image is absent, mark this test **BLOCKED** and do not substitute Node-RED or an invented container.

If it is deployed:

1. create one eligible POC outbox job;
2. record its lease owner/state;
3. stop adapter-1 only;
4. wait for the documented lease expiry/reclaim condition;
5. prove adapter-2 claims/processes the job without simultaneous ownership.

Do not accept simultaneous ownership of one live lease.

## 15.12 External Fabric outage

If the adapter implementation is absent, the full reconcile/drain part of this test is **BLOCKED**. You may still prove that Node-RED can commit telemetry + an outbox row without a live Fabric path.

When adapters are deployed, block only the adapter path to the external Fabric Gateway.

Send a fresh real **EMU-01 payload-v2** uplink and record its `test_sequence`/event key.

Expected:

```text
ChirpStack continues
Node-RED continues
telemetry row commits
fabric_outbox row commits
outbox waits/accumulates
no false confirmed status
```

Restore Fabric connectivity.

Pass when the adapter reconciles uncertain submissions and the outbox drains without conflicting duplicate state.

## 15.13 4G outage

Disconnect the test gateway's LTE backhaul without changing RF settings, Gateway EUI, MQTT configuration, or local Mosquitto data. Do not stop the gateway-local broker; the purpose is to test its persistent queue.

Expected:

```text
gateway remains running
local Mosquitto queue grows
cloud last-seen becomes stale
no stale downlink is replayed
after LTE returns, queue drains and fresh uplinks resume
```

This is a gateway-buffer test, not the same experiment as the local-VM dissertation WAN interruption.

## 15.14 2-GiB resource test

During each failure run:

```bash
free -h
uptime
command -v vmstat >/dev/null && vmstat 1 5 || true
docker stats --no-stream
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true
```

The 2-GiB shared-CPU profile fails if an essential surviving service is OOM-killed, the node becomes unusably swap-bound, or CPU contention prevents the documented functional failover/recovery criteria from completing under the few-sensor workload.

If that happens, resize and repeat the same test. The resize result is part of the POC finding.

## 15.15 Acceptance matrix

| Test | Required POC result |
|---|---|
| `ha-01` loss | Reserved IPv4 moves automatically to `ha-02`, DNS stays unchanged, `ha-02` path carries LoRaWAN, quorum groups survive |
| `ha-02` loss | after deliberately starting with the Reserved IPv4 on `ha-02`, it moves automatically to `ha-01` with DNS unchanged |
| `ha-03` loss | LoRaWAN + PostgreSQL/outbox survive; Node-RED/Grafana may pause |
| PG switchover | all DB clients keep same endpoint |
| PG primary loss | one new primary, no manual DSN change |
| Valkey primary loss | Sentinel promotion works |
| Mosquitto-1 loss | gateway reconnects to backup service |
| ChirpStack-1 loss | ChirpStack-2 processes fresh uplink; Reserved IPv4 does not needlessly move |
| OpenBao member loss | KMS works at 2/3 |
| adapter-1 loss | **Required for full-feature PASS:** adapter-2 continues eligible work after valid lease recovery; missing reviewed adapter implementation makes the overall full-feature result BLOCKED |
| external Fabric outage | **Required for full-feature PASS:** telemetry/outbox commit continues, queued work waits safely, then reconciles/drains after Fabric recovery |
| LTE outage | local gateway queue drains after recovery |
| 2-GiB resource floor | no essential OOM during accepted tests |

## 15.16 What passing means

Passing means:

> the small cloud model demonstrates the future HA architecture's important failure relationships with every required full-feature runtime component included.

A `BLOCKED` Fabric adapter test is useful partial infrastructure evidence, but it is **not** a final full-feature PASS. The overall POC remains BLOCKED until the reviewed adapter is deployed and its loss/outage/reconciliation tests pass.

It does not mean the same 2-GiB machines should be used for the final deployment.

Next: [16-operations-upgrades-and-scaling.md](16-operations-upgrades-and-scaling.md).
