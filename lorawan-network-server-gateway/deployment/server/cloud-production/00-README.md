# Minimal 3-Server HA Proof of Concept

Use this folder to build the **smallest practical cloud version of the future LoRaWAN HA architecture**.

Think of it as a **scale model of a bridge**:

- the supports and failure paths are real;
- the traffic is tiny;
- we are proving that the design works before paying for production-sized machines.

This POC is **not capacity sizing for production**. A few sensor uplinks are enough. The important result is that one server can fail and the remaining architecture behaves as designed.

## Deployment sequence and document status

The numbering follows the **actual cloud build sequence**. Phases 5-8 are now backed by live evidence: etcd, PostgreSQL/Patroni/TimescaleDB, HAProxy/PgBouncer, Mosquitto, and Valkey/Sentinel have reached their recorded acceptance boundaries. Phase 9 is the active ChirpStack phase. Files `10+` remain standby/reference slots until the live build reaches them; refine those manuals from current evidence before execution rather than treating old examples as commissioned state.

Status meaning:

- **VALIDATED** — executed on the current three-server build and backed by evidence in `00-build-execution-log.md`.
- **REFERENCE** — architecture or planning information; useful now but not itself a live deployment phase.
- **STANDBY / DRAFT** — not yet live-validated. Re-check and refine it from the real server state before executing it.

| Order | Manual | Status |
|---:|---|---|
| 0 | [00-build-execution-log.md](00-build-execution-log.md) | live evidence log |
| 1 | [01-architecture-decisions-and-scope.md](01-architecture-decisions-and-scope.md) | REFERENCE |
| 2 | [02-capacity-cost-and-ip-plan.md](02-capacity-cost-and-ip-plan.md) + [02a-digitalocean-machine-layout-and-specs.md](02a-digitalocean-machine-layout-and-specs.md) | REFERENCE / recorded baseline |
| 3 | [03-digitalocean-vpc-droplets-and-firewalls.md](03-digitalocean-vpc-droplets-and-firewalls.md) | host-side three-Droplet/east-west foundation evidenced; provider firewall, Reserved IPv4, and public DNS remain externally managed or not yet evidenced |
| 4 | [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md) + [04a-host-security-hardening-execution-runbook.md](04a-host-security-hardening-execution-runbook.md) | VALIDATED host-security checkpoint |
| 5 | [05-etcd-cluster.md](05-etcd-cluster.md) | **CORE DEPLOYMENT VALIDATED** - bootstrap/quorum/status proven; member-loss/recovery rehearsal not yet recorded |
| 6 | [06-spilo-patroni-postgresql-cluster.md](06-spilo-patroni-postgresql-cluster.md) | **DATABASE-LAYER POC VALIDATED - PostgreSQL HA + telemetry schema + HBA/auth + logical backup boundary + controlled ulc-01 -> ulc-02 switchover + promoted-primary DB/Timescale/application-auth gates PASS** |
| 7 | [07-haproxy-and-pgbouncer.md](07-haproxy-and-pgbouncer.md) | **COMPLETE / VALIDATED - HAProxy database routing + three-node PgBouncer TLS/SCRAM commissioning + Patroni failover routing PASS** |
| 8 | [08-mqtt-and-valkey.md](08-mqtt-and-valkey.md) | **CORE SERVICE LAYER COMPLETE / VALIDATED - MQTT TLS broker failover PASS; Valkey/Sentinel HA + dual writable-primary HAProxy routing PASS; ChirpStack MQTT workload identity/ACL commissioning remains a Phase 9 dependency** |
| 9 | [09-chirpstack-cloud-cluster.md](09-chirpstack-cloud-cluster.md) | **ACTIVE - PRE-DEPLOYMENT PREFLIGHT / DEPENDENCY CLOSURE** |
| 10 | [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md) | STANDBY / DRAFT |
| 11 | [11-raspberry-pi-4g-backhaul.md](11-raspberry-pi-4g-backhaul.md) | STANDBY / DRAFT |
| 12 | [12-gateway-and-device-migration.md](12-gateway-and-device-migration.md) | STANDBY / DRAFT |
| 13 | [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md) | STANDBY / DRAFT |
| 14 | [14-observability-alerting-and-logging.md](14-observability-alerting-and-logging.md) + [14a-grafana-cloud-deployment.md](14a-grafana-cloud-deployment.md) | STANDBY / DRAFT |
| 15 | [15-failover-chaos-and-acceptance-testing.md](15-failover-chaos-and-acceptance-testing.md) | STANDBY / DRAFT |
| 16 | [16-operations-upgrades-and-scaling.md](16-operations-upgrades-and-scaling.md) | STANDBY / DRAFT |
| 17 | [17-troubleshooting.md](17-troubleshooting.md) | LIVING DRAFT; keep proven troubleshooting as we go |
| 18 | [18-runbook-and-handoff-checklists.md](18-runbook-and-handoff-checklists.md) | STANDBY / DRAFT |
| 19 | [19-cloud-ha-grafana-deployment-day-runbook.md](19-cloud-ha-grafana-deployment-day-runbook.md) | sequence reference; later phases still STANDBY |
| 20 | [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md) | STANDBY / DRAFT |

**Current stop point:** the database and shared-state layers are commissioned far enough to begin ChirpStack deployment preflight. Phase 6 PostgreSQL/Patroni/TimescaleDB HA is complete, including hardened TLS/SCRAM HBA policy, validated logical backups, and controlled promotion testing. Phase 7 is complete: HAProxy database-primary routing and PgBouncer are commissioned on all three nodes with client TLS, SCRAM authentication, verified backend TLS, and unchanged client endpoints across Patroni leader changes. Phase 8 core shared services are also commissioned. Mosquitto `2.0.18` runs on `ulc-01` and `ulc-02` with TLS backends on `:8884`; the validated HAProxy MQTT TLS passthrough endpoint is currently `10.104.0.2:8883` with certificate identity `mqtt.internal.lorawan.com`, and broker-backend failover has passed. Valkey `7.2.13` runs TLS-only on all three nodes with three TLS Sentinels, quorum `2`, authenticated replication, and dual HAProxy writable-primary endpoints `10.104.0.2:16379` and `10.104.0.4:16379`. The last controlled Valkey failure promoted `ulc-02` (`10.104.0.4`) and both HAProxy endpoints followed automatically; `ulc-01` and `ulc-03` are healthy replicas after recovery. Do not manually fail back. Phase 9 is now ACTIVE, but first ChirpStack start remains blocked until the exact ChirpStack image/config schema is pinned and the remaining MQTT workload-authentication/ACL plus two-app-node MQTT routing boundary is resolved. Public Reserved IPv4/DNS ingress remains a later phase and is not required for the first private ChirpStack canary. The DigitalOcean Cloud Firewall remains externally controlled.

## POC resources

```text
OS on ha-01/02/03: Ubuntu Server 24.04 LTS x64
DigitalOcean image slug: ubuntu-24-04-x64

ha-01  Basic 1 vCPU / 2 GiB / 50 GiB
ha-02  Basic 1 vCPU / 2 GiB / 50 GiB
ha-03  Basic 1 vCPU / 2 GiB / 50 GiB

Target: 1 x DigitalOcean Reserved IPv4, assigned to ha-01 or ha-02 when public ingress is commissioned; not yet evidenced in the execution log
0 x managed Network Load Balancer
```

Use the plain DigitalOcean **Ubuntu 24.04 (LTS) x64** OS image, not a Marketplace/1-Click application image. Pin the exact `ubuntu-24-04-x64` image family on all three hosts; do not write "latest Ubuntu LTS" in the build record because a future rebuild could otherwise select a newer LTS release with different packages and defaults.

The separate single-VM simulation/lab profile may also use Ubuntu, but it has different sizing, networking, firewall, and service-placement instructions. Sharing an OS family does **not** make those VM steps interchangeable with this three-Droplet cloud POC.

The **2-GiB-per-host profile is the minimum full-feature starting floor** for this POC. `512 MiB` and `1 GiB` are not accepted deployment baselines when all documented services are retained, including TimescaleDB, OpenBao, Node-RED/Grafana where assigned, and both Fabric adapter workers. A few sensor messages reduce variable workload; they do not remove the always-on memory cost of the HA control plane.

If a host OOMs or spends significant time swapping during the one-host-failure rehearsal, resize that profile and record the observed minimum. Do not hide a failed sizing experiment, and do not delete a required technology just to make the node fit.

Do not create managed PostgreSQL, managed Valkey, block volumes, dedicated monitoring servers, dedicated MQTT servers, or a separate telemetry database server/service for this POC. When the standby PostgreSQL phase is deployed, the logical `lorawan_telemetry` database is planned to live inside the Patroni cluster.

## Target service placement

The following is the **full intended placement**, not a guarantee that every listed service is already commissioned. At the present checkpoint, etcd, PostgreSQL/Patroni, HAProxy database routing, PgBouncer, Mosquitto on `ulc-01/02`, and Valkey/Sentinel on all three nodes are live-validated. The application databases, TimescaleDB telemetry schema, runtime database roles, hardened PostgreSQL HBA policy, and logical backup boundary are also commissioned. ChirpStack itself is the next active deployment phase. Public ingress, Node-RED/Grafana deployment, OpenBao, Fabric adapters, and final gateway migration remain later work.

```text
ha-01
  etcd-1
  PostgreSQL / Patroni-1
  HAProxy
  PgBouncer
  ChirpStack-1
  Mosquitto-1 preferred
  Valkey-1 + Sentinel-1
  OpenBao-1
  Fabric adapter-1

ha-02
  etcd-2
  PostgreSQL / Patroni-2
  HAProxy
  PgBouncer
  ChirpStack-2
  Mosquitto-2 backup
  Valkey-2 + Sentinel-2
  OpenBao-2
  Fabric adapter-2

ha-03
  etcd-3
  PostgreSQL / Patroni-3
  HAProxy            private DB + internal MQTT routing
  PgBouncer          telemetry/Grafana DB pooling
  Valkey-3 + Sentinel-3
  OpenBao-3
  Node-RED
  Grafana
```

## The main simplification: one PostgreSQL HA cluster

There is **no separate TimescaleDB server/container in this POC**. TimescaleDB stays in the architecture as a PostgreSQL extension installed on every Patroni/PostgreSQL member and enabled in the telemetry database.

The planned Patroni PostgreSQL cluster will store two logical databases:

```text
PostgreSQL / Patroni HA cluster

  chirpstack
    -> ChirpStack operational state

  lorawan_telemetry [TimescaleDB enabled]
    -> telemetry.uplinks hypertable
    -> telemetry.measurements hypertable
    -> telemetry.fabric_outbox ordinary transactional table
```

When that phase is deployed, both databases will be inside the same PostgreSQL cluster, so Patroni replication will carry both across `ha-01`, `ha-02`, and `ha-03`.

For the POC, install the same pinned TimescaleDB extension version on all three PostgreSQL members and enable it in `lorawan_telemetry`. Use Timescale hypertables for time-series telemetry so the POC preserves the intended production data model. Keep `fabric_outbox` as an ordinary PostgreSQL table because it is a transactional work queue, not time-series storage.

## Target full three-server architecture

```text
FIELD
=====

EMU-01 primary multi-sensor telemetry
SEC-02 temporary legitimate verification / security fixture
      |
      | LoRaWAN RF when using the active test profile
      v
+---------------------------------------+
| Raspberry Pi 4B + RAK5146            |
|---------------------------------------|
| Concentratord                         |
| MQTT Forwarder                        |
| local Mosquitto 127.0.0.1:1883       |
| persistent QoS 1 uplink buffer        |
| USB 4G/LTE                            |
+---------------------------------------+
      |
      | mTLS MQTT over 4G/LTE
      v

                  DigitalOcean Reserved IPv4
                    TCP 443 / TCP 8883
                           |
                  automatic API reassignment
                   protected by etcd lock
                        /         \
                       /           \
                      v             v

+=================================================+
| ha-01 | 1 vCPU / 2 GiB / 50 GiB                |
|-------------------------------------------------|
| HAProxy                                         |
| PgBouncer                                       |
| ChirpStack-1                                    |
| Mosquitto-1 [preferred]                         |
| PostgreSQL / Patroni-1                          |
| etcd-1                                          |
| Valkey-1 + Sentinel-1                           |
| OpenBao-1                                       |
| Fabric adapter-1                                |
+=================================================+

+=================================================+
| ha-02 | 1 vCPU / 2 GiB / 50 GiB                |
|-------------------------------------------------|
| HAProxy                                         |
| PgBouncer                                       |
| ChirpStack-2                                    |
| Mosquitto-2 [backup]                            |
| PostgreSQL / Patroni-2                          |
| etcd-2                                          |
| Valkey-2 + Sentinel-2                           |
| OpenBao-2                                       |
| Fabric adapter-2                                |
+=================================================+

+=================================================+
| ha-03 | 1 vCPU / 2 GiB / 50 GiB                |
|-------------------------------------------------|
| HAProxy [private DB + MQTT routes]              |
| PgBouncer                                       |
| PostgreSQL / Patroni-3                          |
| etcd-3                                          |
| Valkey-3 + Sentinel-3                           |
| OpenBao-3                                       |
| Node-RED                                        |
| Grafana                                         |
+=================================================+
```

## HA relationships the completed POC is intended to prove

The etcd, PostgreSQL/Patroni, and Valkey/Sentinel relationships below are now live-validated. MQTT broker-backend failover has also been proven behind the commissioned `ulc-01` HAProxy TLS endpoint, but two-HAProxy-node MQTT application routing and ChirpStack workload authentication/ACLs are not yet closed. ChirpStack and OpenBao relationships remain target behavior until their phases are deployed and tested.

```text
PostgreSQL
  Patroni-1 ----- Patroni-2 ----- Patroni-3
       1 primary + 2 replicas

etcd
  etcd-1 -------- etcd-2 -------- etcd-3
       3 voters / quorum 2

Valkey
  Valkey-1 ------ Valkey-2 ------ Valkey-3
  Sentinel-1 ---- Sentinel-2 ---- Sentinel-3
       1 primary + 2 replicas / Sentinel quorum 2

OpenBao
  OpenBao-1 ----- OpenBao-2 ----- OpenBao-3
       Raft / quorum 2

MQTT
  Mosquitto-1 [preferred] ---- Mosquitto-2 [backup]

ChirpStack
  ChirpStack-1 ---------------- ChirpStack-2

Fabric worker
  adapter-1 ------------------- adapter-2
       same durable PostgreSQL outbox
```

## Planned database connection pattern

After the database-routing phases are deployed, all database clients will use the same pattern:

```text
application
    |
    v
PgBouncer :6432
    |
    v
HAProxy :15432
    |
    v
current Patroni PostgreSQL primary :5432
```

That means:

```text
ChirpStack -> chirpstack database
Node-RED   -> lorawan_telemetry database
Grafana    -> lorawan_telemetry database as read-only user
Adapters   -> lorawan_telemetry.fabric_outbox
```

No client needs to know which PostgreSQL node is currently primary.

## Planned telemetry and Fabric flow

```text
ChirpStack application event
          |
          v
       Node-RED
          |
          | one PostgreSQL transaction
          +----------------------------+
          |                            |
          v                            v
   telemetry row               fabric_outbox row
          |                            |
          |                       lease-based work
          |                       /             \
          |                      v               v
          |                adapter-1       adapter-2
          |                    \             /
          |                     +-----+-----+
          |                           |
          |                           v
          |                  OpenBao 3-node KMS
          |                           |
          |                           v
          |                  external Fabric Gateway
          |                           |
          |                           v
          |                   channel + chaincode
          |                           |
          |                    commit status / tx ID
          |                           |
          +---------------------------+
                                      |
                                      v
                              update fabric_outbox

Grafana reads telemetry from lorawan_telemetry.
```

Fabric or OpenBao failure must **not** cause Node-RED to reject an otherwise valid telemetry insert. The outbox exists specifically so submission can wait and retry.

## What the completed POC must prove

The final pass will require evidence that the **architecture pattern** works:

```text
one host disappears
        |
        v
quorum remains
        |
        v
new PostgreSQL / Valkey roles are selected when necessary
        |
        v
public ChirpStack and MQTT paths recover automatically
        |
        v
no manual IP / DSN edits are needed
```

It does **not** prove production capacity, long-term retention, large fleet throughput, multi-region disaster recovery, or production security/compliance sizing.

## Planned public boundary

These are the intended final exposure rules. They do not mean the standby services are currently listening.

Public through the single Reserved IPv4, which is assigned to one healthy HAProxy app host at a time:

```text
443   ChirpStack UI/API
8883  gateway MQTT mTLS
```

Restricted management:

```text
22    SSH from the administrator source only
```

Private only:

```text
5432   PostgreSQL
6432   PgBouncer
15432  HAProxy PostgreSQL-primary frontend
6379   Valkey
26379  Sentinel
16379  HAProxy Valkey-primary frontend
2379   etcd client
2380   etcd peer
8008   Patroni REST
8080   ChirpStack backend
8884   Mosquitto private TLS backend
18883  HAProxy internal MQTT frontend
1880   Node-RED
3000   Grafana
8200   OpenBao API
8201   OpenBao Raft
18200  HAProxy OpenBao KMS frontend
```

## Manual index

This is a topic index, **not** a second execution order. Use the sequence/status table above to decide what is active.

| File | Use |
|---|---|
| [00-build-execution-log.md](00-build-execution-log.md) | actual commands, failures, fixes, and accepted checkpoints |
| [01-architecture-decisions-and-scope.md](01-architecture-decisions-and-scope.md) | what the POC does and does not claim |
| [02-capacity-cost-and-ip-plan.md](02-capacity-cost-and-ip-plan.md) | capacity, cost, IPs, and software worksheet |
| [02a-digitalocean-machine-layout-and-specs.md](02a-digitalocean-machine-layout-and-specs.md) | exact three-Droplet layout |
| [03-digitalocean-vpc-droplets-and-firewalls.md](03-digitalocean-vpc-droplets-and-firewalls.md) | cloud foundation and networking |
| [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md) | host security plus future service-security guidance |
| [04a-host-security-hardening-execution-runbook.md](04a-host-security-hardening-execution-runbook.md) | live hardening steps and verification evidence |
| [05-etcd-cluster.md](05-etcd-cluster.md) | validated etcd quorum deployment |
| [06-spilo-patroni-postgresql-cluster.md](06-spilo-patroni-postgresql-cluster.md) | validated PostgreSQL/Patroni/TimescaleDB HA deployment and promotion record |
| [07-haproxy-and-pgbouncer.md](07-haproxy-and-pgbouncer.md) | validated HAProxy + PgBouncer database client path |
| [08-mqtt-and-valkey.md](08-mqtt-and-valkey.md) | validated MQTT broker/TLS failover record + completed Valkey/Sentinel HA record; also preserves earlier design/failure history |
| [09-chirpstack-cloud-cluster.md](09-chirpstack-cloud-cluster.md) | **active next phase: ChirpStack preflight, dependency closure, and two-node private deployment** |
| [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md) | standby HAProxy + Reserved-IP public failover plan |
| [11-raspberry-pi-4g-backhaul.md](11-raspberry-pi-4g-backhaul.md) | standby physical-gateway 4G/LTE path |
| [12-gateway-and-device-migration.md](12-gateway-and-device-migration.md) | standby migration/cutover plan |
| [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md) | standby full-stack backup/recovery plan; etcd portion follows validated baseline |
| [14-observability-alerting-and-logging.md](14-observability-alerting-and-logging.md) | standby observability/evidence plan |
| [14a-grafana-cloud-deployment.md](14a-grafana-cloud-deployment.md) | standby Grafana plan |
| [15-failover-chaos-and-acceptance-testing.md](15-failover-chaos-and-acceptance-testing.md) | standby failover tests |
| [16-operations-upgrades-and-scaling.md](16-operations-upgrades-and-scaling.md) | standby operations/upgrade plan |
| [17-troubleshooting.md](17-troubleshooting.md) | living troubleshooting notes, refined as components are deployed |
| [18-runbook-and-handoff-checklists.md](18-runbook-and-handoff-checklists.md) | standby commissioning/handoff plan |
| [19-cloud-ha-grafana-deployment-day-runbook.md](19-cloud-ha-grafana-deployment-day-runbook.md) | full target sequence reference; later phases are not yet validated |
| [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md) | standby KMS + Fabric adapter plan |

## Dissertation-test boundary

This cloud HA POC is a separate architecture experiment. Do not mix its results with the existing counted local-VM resilience experiment unless the research methodology is intentionally revised.
