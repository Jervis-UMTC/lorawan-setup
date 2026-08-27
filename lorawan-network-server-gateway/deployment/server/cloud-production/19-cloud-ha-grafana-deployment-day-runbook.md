# 19. Absolute-Minimum 3-Server HA POC Runbook

> **Status: SEQUENCE REFERENCE, NOT EXECUTION AUTHORITY.** The live build has completed through Phase 9 ChirpStack HA and is now in Phase 10 public-ingress setup. Follow each component manual for exact current commands. The mandatory remaining pre-test order is Phase 10 -> 11 -> 13A -> 12 -> 12A -> 14A -> 20 -> 13B -> 14 -> 14B; **Phase 15 is the first intentional failure-injection phase**.

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

## 19.1 Create only these cloud resources

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

## 19.2 Put these services on the three hosts

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

## 19.3 What the POC is trying to prove

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

## 19.4 Separate commissioning from fault testing

The current build uses one strict lifecycle:

```text
DEPLOY ALL REQUIRED COMPONENTS
  -> VERIFY EACH NORMAL PATH
  -> PHASE 13B FINAL BACKUP
  -> PHASE 14 HEALTHY EVIDENCE DRY RUN
  -> PHASE 14B PRE-TEST GATE = PASS
  -> ONLY THEN PHASE 15 BREAKS ONE THING AT A TIME
```

Do not perform host loss, broker loss, database/KMS member loss, LTE outage, adapter loss, or Fabric outage as part of setup. This prevents the baseline from changing while acceptance tests are already being counted.

## 19.5 Foundation

Current host-side evidence:

```text
ha-01 / ulc-01 exists
ha-02 / ulc-02 exists
replacement ha-03 / ulc-03 exists
10.104.0.2 / .4 / .8 host-side east-west reachability is proven
```

Target provider-side resources still require provider-owner evidence before they can be marked complete:

```text
DigitalOcean VPC object/CIDR confirmation
DigitalOcean Cloud Firewall state/rules
one Reserved IPv4 and its owner
ha-01/ha-02 anchor IPv4 addresses and Droplet IDs where needed for ingress
public DNS
```

The current operator is not authorized to change the DigitalOcean Cloud Firewall. Do not turn this reference runbook into an instruction to do so.

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

Docker Engine itself is already evidenced on all three hosts as version `29.7.2` with `overlayfs`, the systemd cgroup driver, and cgroup v2; `docker compose` functionality was also proven during etcd configuration. However, the captured execution log does **not** preserve the exact Compose plugin version, Docker package-source output, or the current default logging driver. Before the next container phase, run the verification in [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md) and record those missing values instead of assuming they were already checked.

A small host swap file is optional as an emergency cushion for non-OpenBao processes. Do not call sustained swapping a successful size, and do not allow OpenBao to page secrets into ordinary unencrypted swap; follow the explicit **OpenBao and swap** rule in [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md).

## 19.6 etcd first

Follow [05-etcd-cluster.md](05-etcd-cluster.md).

Current captured evidence proves:

```text
3 members
1 leader
3/3 endpoint status healthy
```

A deliberate one-member-loss rehearsal is **not recorded as completed** in the current execution log. When failover testing becomes active, stop one member under the controlled procedure in [15-failover-chaos-and-acceptance-testing.md](15-failover-chaos-and-acceptance-testing.md), prove the other two retain quorum, then restore 3/3. Do not mark that resilience test PASS merely from the initial healthy-cluster result.

## 19.7 PostgreSQL/Patroni

Follow [06-spilo-patroni-postgresql-cluster.md](06-spilo-patroni-postgresql-cluster.md).

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

## 19.8 HAProxy + PgBouncer on all three

Follow [07-haproxy-and-pgbouncer.md](07-haproxy-and-pgbouncer.md).

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

`ha-01` and `ha-02` also carry the public MQTT/ChirpStack and private OpenBao routing roles. Logical `ha-03` / provider host `ulc-03` carries the private DB route and, in Phase 12A, the dedicated Node-RED MQTT `:18884 -> Mosquitto :8886` route so Node-RED follows broker failover without depending on one app host.

## 19.9 Valkey + Sentinel

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

## 19.10 MQTT

Deploy:

```text
ha-01 Mosquitto-1 preferred, private TLS backend :8884
ha-02 Mosquitto-2 backup, private TLS backend :8884
```

The live Phase 8B/9 implementation differs from the original target. Gateway mTLS uses Mosquitto `:8884`; ChirpStack uses its dedicated ulc-01/02 `:18883 -> :8885` route. Phase 12A adds the separate Node-RED private route `mqtt.internal.lorawan.com:18884 -> ulc-03 HAProxy -> Mosquitto :8886`. Do not reuse the obsolete `mqtt-ha.internal.<DOMAIN>:18883` placeholder.

Broker-backend failover behind the commissioned ulc-01 HAProxy endpoint has already passed. Gateway QoS-buffer and Node-RED reconnection tests remain later end-to-end tests.

Do not claim broker-state replication.

## 19.11 ChirpStack

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

## 19.12 Self-managed public ingress

Follow [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md).

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

Keep MQTT TLS pass-through so Mosquitto validates the gateway certificate. Before public `mqtt.<DOMAIN>:8883` activation, the broker certificates must be valid for **both** `mqtt.internal.lorawan.com` and the real public `mqtt.<DOMAIN>` name; roll them one broker at a time and preserve internal clients.

## 19.13 Physical gateway

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

## 19.14 Timescale telemetry inside the Patroni cluster

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

## 19.15 Node-RED then Grafana

Run both only on `ulc-03`.

Follow [12a-node-red-timescale-telemetry.md](12a-node-red-timescale-telemetry.md). Before opening the Node-RED editor, prove its **two real local routes from ulc-03**:

```text
MQTT
Node-RED -> mqtt.internal.lorawan.com:18884
         -> ulc-03 HAProxy 10.104.0.8:18884
         -> Mosquitto-1 / Mosquitto-2 :8884 mTLS backends
         -> read-only application-uplink ACL

DATABASE
Node-RED -> pgbouncer.internal.lorawan.com:6432
         -> ulc-03 local PgBouncer
         -> local HAProxy :15432
         -> current Patroni primary
         -> lorawan_telemetry [TimescaleDB]
```

1. Map both logical names to `ulc-03` (`10.104.0.8`) for the Node-RED container.
2. Test MQTT TLS with the Node-RED client certificate and a read-only subscription to `application/+/device/+/event/up`.
3. Test PostgreSQL TLS as `telemetry_writer` through PgBouncer.
4. Run the Timescale rollback insert/duplicate tests from [../integrations/timescaledb/03-connect-and-verify.md](../integrations/timescaledb/03-connect-and-verify.md).
5. Deploy Node-RED using [../integrations/node-red/01-deploy-node-red.md](../integrations/node-red/01-deploy-node-red.md), applying the cloud substitutions in [../integrations/node-red/02-configure-mqtt-and-postgresql.md](../integrations/node-red/02-configure-mqtt-and-postgresql.md).
6. First deploy only `mqtt in -> json -> debug` and prove one real **EMU-01 Agriculture Kit payload-v2** ChirpStack application uplink arrives with `payload_version=2`, `test_sequence`, `sensor_validity_bitmap`, and the expected decoded sensor fields.
7. Then enable the parameterized PostgreSQL writes and prove that EMU-01 uplink produces one canonical `telemetry.uplinks` row plus the reviewed `telemetry.measurements` rows; invalid sensor bits must not be stored as measured stale values.
8. Deliberately replay the same event and prove the uniqueness rules prevent duplicates.
9. Only after Node-RED storage is correct, deploy Grafana using [14a-grafana-cloud-deployment.md](14a-grafana-cloud-deployment.md).

Visible data path:

```text
ChirpStack -> Node-RED -> TimescaleDB hypertables -> Grafana
```

**Stop here. Do not enable Fabric selection** if Node-RED cannot prove retry-safe storage first.

If `ulc-03` later disappears, Node-RED/Grafana may pause. That expected failure behavior is tested in Phase 15; do not stop `ulc-03` during setup.

## 19.16 OpenBao

Follow [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md).

Deploy:

```text
OpenBao-1 ha-01
OpenBao-2 ha-02
OpenBao-3 ha-03
```

Prove during setup:

```text
3/3 healthy/unsealed
stable :18200 endpoint healthy
non-exportable Transit key works
fixed canonicalization/SHA-256 vector works
normal sign/verify works
```

Keep all three members running. One-member-loss / 2-of-3 survival belongs to Phase 15.

## 19.17 Fabric adapters

Collect the real external Fabric handoff first, then complete the **adapter implementation readiness gate** in [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md).

The repository's detailed adapter reference currently states that a completed reviewed adapter image is not yet present. Therefore:

```text
IF reviewed adapter image/source is absent
  -> STOP pre-test commissioning here
  -> Phase 14B = BLOCKED
  -> do not invent an image or substitute Node-RED as the adapter
  -> do not begin counted Phase 15 tests

IF reviewed adapter image/source exists
  -> deploy adapter-1 on ulc-01
  -> deploy adapter-2 on ulc-02
```

Both use the same PostgreSQL HA `lorawan_telemetry.fabric_outbox`, with different worker IDs and lease-safe claiming.

Normal-path setup must prove:

```text
one selected outbox job
-> fixed evidence projection
-> RFC 8785 canonical JSON
-> SHA-256 digest over exact UTF-8 bytes
-> OpenBao versioned signature
-> external Fabric commit
-> tx ID/status returned to outbox
-> read-only digest/signature reconstruction verifies
```

Keep both adapters and Fabric connectivity healthy. Adapter loss and external Fabric outage belong to Phase 15.

Before `19.18`, complete **Phase 13B**, then Phase 14 healthy evidence capture, then require `PRE_TEST_COMMISSIONING_GATE=PASS` from Phase 14B.

## 19.18 Three host-failure tests

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

## 19.19 Resource acceptance

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

## 19.20 POC cost

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

## 19.21 Final pass

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
