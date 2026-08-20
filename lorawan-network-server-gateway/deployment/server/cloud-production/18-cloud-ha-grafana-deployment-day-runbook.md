# 18. Absolute-Minimum 3-Server HA POC Runbook

Use this runbook to build a **small scale model of the future deployment**.

The traffic is deliberately tiny. The topology and failover relationships are the things being tested.

### Execution locations used in this runbook

```text
ADMIN  = administration workstation / provider console
H1     = ha-01 shell
H2     = ha-02 shell
H3     = ha-03 shell
GW     = Raspberry Pi gateway shell / Gateway OS UI
BROWSER= workstation browser over the documented SSH tunnel/public endpoint
```

When a detailed component manual says otherwise, follow the component manual's named execution location. Never run a cloud database command on the Raspberry Pi or a Gateway OS command on a Droplet merely because the shell prompt is available.

Before starting, fill the non-secret resource/software worksheet in [02-capacity-cost-and-ip-plan.md](02-capacity-cost-and-ip-plan.md) and complete the certificate/SAN gate in [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md).

## 18.1 Create only these cloud resources

```text
OS on ha-01/02/03: Ubuntu Server 24.04 LTS x64
DigitalOcean image slug: ubuntu-24-04-x64

ha-01  Basic 1 vCPU / 2 GiB / 50 GiB
ha-02  Basic 1 vCPU / 2 GiB / 50 GiB
ha-03  Basic 1 vCPU / 2 GiB / 50 GiB

1 x DigitalOcean Reserved IPv4, initially assigned to ha-01
0 x managed Network Load Balancer
```

Use the plain **Ubuntu 24.04 (LTS) x64** OS image on every Droplet. Pin `ubuntu-24-04-x64`; do not substitute another Ubuntu LTS release during creation. `512 MiB` and `1 GiB` are not the planned full-feature baseline; 2 GiB is the intentionally tight starting floor with every architecture technology retained. Because the OS baseline changed, re-measure the 2-GiB floor on Ubuntu rather than carrying forward Debian RAM results.

Do not create:

```text
standalone TimescaleDB
managed PostgreSQL
managed Valkey
block volumes
dedicated MQTT VM
dedicated monitoring VM
managed Network Load Balancer
Prometheus stack unless a test needs it
```

The 2-GiB size is an experimental starting floor. If a node OOMs during the failover rehearsal, resize and record the real minimum.

## 18.2 Put these services on the three hosts

```text
ha-01
  etcd-1
  PostgreSQL/Patroni-1
  HAProxy
  PgBouncer
  ChirpStack-1
  Mosquitto-1 preferred
  Valkey-1 + Sentinel-1
  OpenBao-1
  Fabric adapter-1 target placement; deploy only after readiness gate

ha-02
  etcd-2
  PostgreSQL/Patroni-2
  HAProxy
  PgBouncer
  ChirpStack-2
  Mosquitto-2 backup
  Valkey-2 + Sentinel-2
  OpenBao-2
  Fabric adapter-2 target placement; deploy only after readiness gate

ha-03
  etcd-3
  PostgreSQL/Patroni-3
  HAProxy private DB + internal MQTT frontends
  PgBouncer
  Valkey-3 + Sentinel-3
  OpenBao-3
  Node-RED
  Grafana
```

## 18.3 What the POC is trying to prove

Think of the test as asking:

```text
Does the small model have the same important structural behavior
that the future larger deployment should have?
```

We care about:

```text
quorum
role promotion
stable endpoints
application failover
broker failover
KMS failover
no manual DSN/IP changes
Fabric worker failover is required for the final full-feature PASS; until the reviewed adapter implementation exists, the overall full-feature result remains BLOCKED
```

We do not care yet about production throughput, months of telemetry retention, or large user counts.

## 18.4 Use one iteration loop

For every layer:

```text
DEPLOY
  -> VERIFY
  -> BREAK ONE THING
  -> VERIFY RECOVERY
  -> RESTORE FULL HEALTH
  -> CONTINUE
```

Never inject the next failure while the previous layer is still degraded.

## 18.5 Foundation

Create:

```text
one VPC
ha-01
ha-02
ha-03
cloud firewall
one Reserved IPv4 initially assigned to ha-01
ha-01/ha-02 Droplet IDs + anchor IPv4 addresses
```

Record the actual private IPs.

On every host:

```bash
hostnamectl
cat /etc/os-release
uname -m
uname -r
nproc
free -h
df -h /
ip -br address
ip route
timedatectl
systemctl --failed
```

Before any step that runs `docker compose`, complete the **Ubuntu Server 24.04 LTS Docker Engine + rotating log-driver procedure** in [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md) on all three Droplets. Verify the OS release gate, numeric DigitalOcean image metadata is recorded, time is synchronized, `docker version`, `docker compose version`, the installed package versions, and that the default logging driver is `local`.

A small host swap file is optional as an emergency cushion for non-OpenBao processes. Do not call sustained swapping a successful size, and do not allow OpenBao to page secrets into ordinary unencrypted swap; follow the OpenBao-specific swap rule in Section 4.

## 18.6 etcd first

Follow [06-etcd-cluster.md](06-etcd-cluster.md).

Required:

```text
3 members
1 leader
3/3 healthy
```

Stop one member.

Pass when the other two still have quorum. Restore 3/3.

## 18.7 PostgreSQL/Patroni

Follow [07-spilo-patroni-postgresql-cluster.md](07-spilo-patroni-postgresql-cluster.md).

Use small POC memory settings:

```text
max_connections       40
shared_buffers        128MB
work_mem              2MB
maintenance_work_mem  32MB
```

Normal state:

```text
1 primary
2 replicas
```

Create both databases:

```text
chirpstack
lorawan_telemetry [TimescaleDB enabled]
```

Before enabling the extension, prove the same pinned TimescaleDB build is available on PostgreSQL/Patroni-1/2/3 and that Patroni-managed `shared_preload_libraries` includes `timescaledb`. Then run `CREATE EXTENSION IF NOT EXISTS timescaledb;` in `lorawan_telemetry` only.

Create separate roles for ChirpStack, telemetry writer/reader, and Fabric adapter.

Take simple logical dumps before destructive tests. Do not add object storage/WAL-G merely to prove HA.

## 18.8 HAProxy + PgBouncer on all three

Follow [08-haproxy-and-pgbouncer.md](08-haproxy-and-pgbouncer.md).

Database path everywhere:

```text
local app
  -> PgBouncer :6432
  -> local HAProxy :15432
  -> current Patroni primary :5432
```

Examples:

```text
ha-01 ChirpStack-1 / adapter-1 when implementation exists
ha-02 ChirpStack-2 / adapter-2 when implementation exists
ha-03 Node-RED / Grafana
```

Prove a planned Patroni switchover and verify all clients keep the same endpoint.

`ha-01` and `ha-02` also carry the public MQTT/ChirpStack and private OpenBao routing roles. `ha-03` carries only the private DB route plus private MQTT `:18883` so Node-RED can follow Mosquitto failover without depending on one app host.

## 18.9 Valkey + Sentinel

Deploy:

```text
ha-01 Valkey-1 + Sentinel-1
ha-02 Valkey-2 + Sentinel-2
ha-03 Valkey-3 + Sentinel-3
```

Normal:

```text
1 Valkey primary
2 replicas
3 Sentinels
quorum 2
```

Stop the primary and prove Sentinel promotes a replica and HAProxy follows it. Restore full redundancy.

## 18.10 MQTT

Deploy:

```text
ha-01 Mosquitto-1 preferred, private TLS backend :8884
ha-02 Mosquitto-2 backup, private TLS backend :8884
```

Both use the same gateway trust/ACL policy. HAProxy owns public `:8883`; Mosquitto uses private backend `:8884`, avoiding a same-host port collision. All three HAProxy hosts expose the private MQTT route `:18883`; only `ha-01/02` expose public `:8883`.

Stop Mosquitto-1 and prove the gateway reconnects to Mosquitto-2 and drains its local QoS 1 buffer. Also prove Node-RED can reconnect through `mqtt-ha.internal.<DOMAIN>:18883`. Restore Mosquitto-1.

Do not claim broker-state replication.

## 18.11 ChirpStack

Deploy:

```text
ha-01 ChirpStack-1
ha-02 ChirpStack-2
```

Both use the same:

```text
region
PostgreSQL endpoint
Valkey endpoint
MQTT endpoint
share_name
secrets
```

Stop ChirpStack-1 and prove ChirpStack-2 still processes a real uplink.

## 18.12 Self-managed public ingress

Follow [03a-self-managed-public-ingress.md](03a-self-managed-public-ingress.md).

Required shape:

```text
chirpstack.<DOMAIN> ----+
                       +--> Reserved IPv4
mqtt.<DOMAIN> ----------+        |
                                 v
                         current owner
                     ha-01 OR ha-02 HAProxy
                       anchor :443/:8883
```

Do these in order:

1. verify the Reserved IPv4 is assigned to `ha-01` initially;
2. verify `ha-01` and `ha-02` anchor IPs and Droplet IDs are recorded;
3. bind public HAProxy `:443` and `:8883` to each host's anchor IP;
4. prove each candidate passes its local HTTPS + MQTT TLS health checks;
5. manually reassign the Reserved IP to `ha-02` and prove both public services without DNS changes;
6. move it back to `ha-01`;
7. install/enable the etcd-locked failover timer on `ha-01/02`;
8. point both public DNS names to the Reserved IPv4;
9. do **not** enable automatic failback.

Keep MQTT TLS pass-through so Mosquitto validates the gateway certificate.

## 18.13 Physical gateway

Required path:

```text
RAK5146
-> MQTT Forwarder
-> gateway-local Mosquitto queue
-> USB 4G/LTE
-> mqtt.<DOMAIN>:8883
-> Reserved IPv4
-> current ha-01/ha-02 HAProxy owner
-> active Mosquitto
-> ChirpStack
```

Prove:

```text
real OTAA
real uplink
one safe downlink
```

## 18.14 Timescale telemetry inside the Patroni cluster

There is no **separate TimescaleDB server**. TimescaleDB runs inside the existing PostgreSQL/Patroni cluster.

Use `lorawan_telemetry` on that cluster and verify:

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'timescaledb';
```

Then create the real telemetry schema using [../integrations/timescaledb/02-create-telemetry-schema.md](../integrations/timescaledb/02-create-telemetry-schema.md), adapting only the connection path for this cluster:

```text
lorawan_telemetry [TimescaleDB]
  telemetry.uplinks       -> hypertable
  telemetry.measurements  -> hypertable
  telemetry.device_registry
  telemetry.latest_uplinks
  telemetry.latest_measurements
  telemetry.fabric_outbox -> ordinary PostgreSQL table
```

The outbox must keep the lease, index, permission, and immutability rules from [../fabric-attestation/02-create-outbox-and-adapter.md](../fabric-attestation/02-create-outbox-and-adapter.md). Do **not** convert the outbox itself into a hypertable.

For this small POC, keep compression/retention conservative. Do not enable a destructive retention policy until the desired interval and backup boundary are explicitly approved.

The important POC rule is:

```text
Node-RED transaction
  -> telemetry row
  -> selected fabric_outbox row
  -> COMMIT
```

Do not let Node-RED call Fabric directly.

## 18.15 Node-RED then Grafana

Run both only on `ha-03`.

Before opening the Node-RED editor, prove its **two real dependencies from ha-03**:

```text
MQTT
Node-RED -> mqtt-ha.internal.<DOMAIN>:18883
         -> local ha-03 HAProxy
         -> Mosquitto-1 preferred / Mosquitto-2 backup

DATABASE
Node-RED -> pgbouncer.internal.<DOMAIN>:6432
         -> local PgBouncer
         -> local HAProxy :15432
         -> current Patroni primary
         -> lorawan_telemetry [TimescaleDB]
```

1. Map both logical names to `ha-03`'s private IP for the Node-RED container.
2. Test MQTT TLS with the Node-RED client certificate and a read-only subscription to `application/+/device/+/event/up`.
3. Test PostgreSQL TLS as `telemetry_writer` through PgBouncer.
4. Run the Timescale rollback insert/duplicate tests from [../integrations/timescaledb/03-connect-and-verify.md](../integrations/timescaledb/03-connect-and-verify.md).
5. Deploy Node-RED using [../integrations/node-red/01-deploy-node-red.md](../integrations/node-red/01-deploy-node-red.md), applying the cloud substitutions in [../integrations/node-red/02-configure-mqtt-and-postgresql.md](../integrations/node-red/02-configure-mqtt-and-postgresql.md).
6. First deploy only `mqtt in -> json -> debug` and prove one real **EMU-01 Agriculture Kit payload-v2** ChirpStack application uplink arrives with `payload_version=2`, `test_sequence`, `sensor_validity_bitmap`, and the expected decoded sensor fields.
7. Then enable the parameterized PostgreSQL writes and prove that EMU-01 uplink produces one canonical `telemetry.uplinks` row plus the reviewed `telemetry.measurements` rows; invalid sensor bits must not be stored as measured stale values.
8. Deliberately replay the same event and prove the uniqueness rules prevent duplicates.
9. Only after Node-RED storage is correct, deploy Grafana using [13a-grafana-cloud-deployment.md](13a-grafana-cloud-deployment.md).

Visible data path:

```text
ChirpStack -> Node-RED -> TimescaleDB hypertables -> Grafana
```

**Stop here. Do not enable Fabric selection** if Node-RED cannot prove retry-safe storage first.

If `ha-03` disappears, Node-RED/Grafana may pause. That is acceptable for this control-plane POC because PostgreSQL/outbox data still exist on the other Patroni members.

## 18.16 OpenBao

Follow [19-openbao-and-fabric-adapter.md](19-openbao-and-fabric-adapter.md).

Deploy:

```text
OpenBao-1 ha-01
OpenBao-2 ha-02
OpenBao-3 ha-03
```

Prove:

```text
3/3 healthy
Transit key works
stop one member
2/3 still works
restore 3/3
```

Keep the signing key non-exportable.

## 18.17 Fabric adapters

Collect the real external Fabric handoff first, then complete the **adapter implementation readiness gate** in [19-openbao-and-fabric-adapter.md](19-openbao-and-fabric-adapter.md).

The repository's detailed adapter reference currently states that a completed reviewed adapter image is not yet present. Therefore:

```text
IF reviewed adapter image/source is absent
  -> STOP adapter deployment here
  -> record the Fabric execution path as BLOCKED
  -> do not invent an image or substitute Node-RED as the adapter

IF reviewed adapter image/source exists
  -> deploy adapter-1 on ha-01
  -> deploy adapter-2 on ha-02
```

Both use the same PostgreSQL HA `lorawan_telemetry.fabric_outbox`, with different worker IDs and lease-safe claiming.

When executable, prove:

```text
one selected outbox job
-> adapter claims
-> OpenBao signs/verifies
-> external Fabric commit
-> tx ID/status returned to outbox
```

Then stop adapter-1 and prove adapter-2 can continue eligible work after valid lease expiry/reclaim.

Block only the external Fabric endpoint and prove telemetry commits continue while the outbox waits.

If the adapter is still missing, other HA tests may continue as partial infrastructure evidence, but every result sheet and the overall commissioning result must mark the **full-feature POC BLOCKED**, not passed. The adapter is not removed from the architecture or from the RAM budget.

## 18.18 Three host-failure tests

Run one at a time.

### Lose ha-01

Expected:

```text
Reserved IPv4 automatically moves to ha-02
DNS unchanged
ChirpStack-2 survives
Mosquitto-2 available
etcd 2/3
OpenBao 2/3
Patroni keeps/promotes primary
Valkey keeps/promotes primary
adapter-2 survives when the conditional Fabric execution scope is deployed
```

### Lose ha-02

Expected mirror through `ha-01`.

### Lose ha-03

Expected:

```text
etcd 2/3
OpenBao 2/3
PostgreSQL available on ha-01/ha-02
lorawan_telemetry + fabric_outbox still available
Valkey remains available/promotable
ChirpStack + MQTT remain available
fabric_outbox remains available; adapter-1/2 remain available only when deployed
Node-RED pauses
Grafana pauses
```

This is better than the previous standalone-Timescale design because losing `ha-03` no longer removes the telemetry/outbox database itself.

## 18.19 Resource acceptance

During every host test capture:

```bash
free -h
uptime
command -v vmstat >/dev/null && vmstat 1 5 || true
docker stats --no-stream
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true
```

Record:

```text
PostgreSQL primary before/after
Valkey primary before/after
active MQTT broker
healthy ChirpStack instance
OpenBao member count
Fabric execution state: worker ID when deployed, otherwise BLOCKED
memory before/during/after
swap use
recovery time
```

2 GiB is accepted only if the host does not OOM, does not remain swap-bound, and the expected failover completes under the few-sensor workload **with every required deployed feature included**. For final full-feature acceptance this includes the real Fabric adapter workers.

## 18.20 POC cost

Planning floor checked on 2026-08-20:

```text
3 x Basic 1 vCPU / 2 GiB  = $36/month
1 x assigned Reserved IPv4 = $0/month
managed Network LB          = $0/month (not used)
                              ---------
POC floor                  = $36/month
```

Keep the Reserved IPv4 assigned to one app Droplet. Leaving an IPv4 reserved but unassigned is billable under the current provider pricing model.

If 2 GiB fails, resize only after observing the failure. The POC exists to discover this boundary.

## 18.21 Final pass

The architecture POC passes when:

- one host at a time can disappear without manual endpoint changes;
- the Reserved IPv4 automatically moves away from a failed current owner to the healthy app host while public DNS stays unchanged;
- a returning app host does not trigger automatic failback/flapping;
- etcd keeps 2/3 quorum;
- Patroni keeps/promotes one PostgreSQL primary;
- both `chirpstack` and Timescale-enabled `lorawan_telemetry` remain available after PostgreSQL failover;
- the promoted PostgreSQL primary exposes the same TimescaleDB extension version and telemetry hypertables;
- Valkey/Sentinel promotes automatically;
- MQTT switches to the backup service path;
- one ChirpStack instance survives an app-host loss;
- OpenBao remains usable at 2/3;
- telemetry + `fabric_outbox` commit remains non-blocking even when Fabric is unavailable;
- **full Fabric execution is required for the final full-feature PASS:** the reviewed adapter implementation is deployed, one worker replaces the other after valid lease recovery, a real external Fabric commit is confirmed, and Fabric outage/reconciliation/drain passes; if the implementation is missing, the overall full-feature POC remains BLOCKED;
- no required host OOMs under the tiny POC traffic;
- the result is documented as a **scale model of future HA**, not production capacity certification.
