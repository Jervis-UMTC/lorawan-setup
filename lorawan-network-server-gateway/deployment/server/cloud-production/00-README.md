# Minimal 3-Server HA Proof of Concept

Use this folder to build the **smallest practical cloud version of the future LoRaWAN HA architecture**.

Think of it as a **scale model of a bridge**:

- the supports and failure paths are real;
- the traffic is tiny;
- we are proving that the design works before paying for production-sized machines.

This POC is **not capacity sizing for production**. A few sensor uplinks are enough. The important result is that one server can fail and the remaining architecture behaves as designed.

## Deployment sequence and document status

The numbering identifies the component manuals, but after Phase 9 the **dependency order is authoritative**. The core cloud HA stack through ChirpStack is commissioned; Phase 13A fast-path backup, OpenBao 3-node KMS normal path, the Fabric outbox database layer, Node-RED A/B server runtime, and Grafana server-only staging are also commissioned. Physical-gateway-dependent acceptance is temporarily deferred. There is no remaining Grafana server mutation to perform while the gateway is unavailable. Intentional host, process, broker, database, KMS, Fabric, or LTE failures remain reserved for Phase 15.

Status meaning:

- **VALIDATED** — executed on the current three-server build and backed by evidence in `00-build-execution-log.md`.
- **REFERENCE** — architecture or planning information; useful now but not itself a live deployment phase.
- **STANDBY / DRAFT** — not yet live-validated. Re-check and refine it from the real server state before executing it.

| Order | Manual | Status |
|---:|---|---|
| 0 | [00-current-server-continuation-checkpoint.md](00-current-server-continuation-checkpoint.md) + [00-build-execution-log.md](00-build-execution-log.md) | **READ CHECKPOINT FIRST** for current state; execution log preserves detailed history |
| 1 | [01-architecture-decisions-and-scope.md](01-architecture-decisions-and-scope.md) | REFERENCE |
| 2 | [02-capacity-cost-and-ip-plan.md](02-capacity-cost-and-ip-plan.md) + [02a-digitalocean-machine-layout-and-specs.md](02a-digitalocean-machine-layout-and-specs.md) | REFERENCE / recorded baseline |
| 3 | [03-digitalocean-vpc-droplets-and-firewalls.md](03-digitalocean-vpc-droplets-and-firewalls.md) | host-side three-Droplet/east-west foundation evidenced; provider firewall, Reserved IPv4, and public DNS remain externally managed or not yet evidenced |
| 4 | [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md) + [04a-host-security-hardening-execution-runbook.md](04a-host-security-hardening-execution-runbook.md) | VALIDATED host-security checkpoint |
| 5 | [05-etcd-cluster.md](05-etcd-cluster.md) | **CORE DEPLOYMENT VALIDATED** - bootstrap/quorum/status proven; member-loss/recovery rehearsal not yet recorded |
| 6 | [06-spilo-patroni-postgresql-cluster.md](06-spilo-patroni-postgresql-cluster.md) | **DATABASE-LAYER POC VALIDATED - PostgreSQL HA + telemetry schema + HBA/auth + logical backup boundary + controlled ulc-01 -> ulc-02 switchover + promoted-primary DB/Timescale/application-auth gates PASS** |
| 7 | [07-haproxy-and-pgbouncer.md](07-haproxy-and-pgbouncer.md) | **COMPLETE / VALIDATED - HAProxy database routing + three-node PgBouncer TLS/SCRAM commissioning + Patroni failover routing PASS** |
| 8 | [08-mqtt-and-valkey.md](08-mqtt-and-valkey.md) | **CORE SERVICE LAYER COMPLETE / VALIDATED - MQTT TLS broker failover PASS; Valkey/Sentinel HA + dual writable-primary HAProxy routing PASS; ChirpStack MQTT workload identity/ACL commissioning remains a Phase 9 dependency** |
| 9 | [09-chirpstack-cloud-cluster.md](09-chirpstack-cloud-cluster.md) | **COMPLETE / PASS - two private ChirpStack nodes, dependency paths, coexistence, reciprocal single-instance survival, and clean rejoin proven** |
| 10 | [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md) | **HOST-SIDE BOUNDARY PASS / EXTERNAL INPUTS PENDING** - provider Reserved IPv4/firewall/public DNS/public PKI remain externally controlled or unevidenced |
| 11 | [11-raspberry-pi-4g-backhaul.md](11-raspberry-pi-4g-backhaul.md) + [11A current continuation checkpoint](11a-phase11-continuation-checkpoint.md) | **HARDWARE-DEFERRED REQUIRED SETUP** - resume when the physical gateway is available; do not infer completion from server state |
| 12 | [12-gateway-and-device-migration.md](12-gateway-and-device-migration.md) | **HARDWARE-DEFERRED REQUIRED SETUP** - authoritative gateway/device cutover or fresh provisioning waits for Phase 11 physical access |
| 12A | [12a-node-red-timescale-telemetry.md](12a-node-red-timescale-telemetry.md) | **SERVER APPLICATION COMMISSIONING PASS / REAL-RF ACCEPTANCE DEFERRED** - atomic telemetry + outbox enqueue and replay were proven synthetically; A remains active/healthy and B fenced; do not repeat until real gateway/EMU-01 acceptance |
| 13 | [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md) | **13A FAST-PATH PASS / 13S SERVER-ONLY SNAPSHOT ACTIVE / 13B FINAL LATER** - current server exports/backup tooling may be pre-staged now; final full-stack snapshot waits for remaining dependencies |
| 14A | [14a-grafana-cloud-deployment.md](14a-grafana-cloud-deployment.md) | **SERVER-ONLY STAGING COMPLETE / PASS; REAL-DATA ACCEPTANCE DEFERRED** - Grafana 13.2.0 runs loopback-only with strict-TLS `telemetry_reader` datasource and provisioned dashboard; real-reading freshness acceptance waits for hardware |
| 20 | [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md) | **OPENBAO + OUTBOX + ADAPTER SOURCE/BUILD PASS / FABRIC EXECUTION BLOCKED** - KMS/audit, outbox, adapter source/tests, four-binary build lock, and standby wiring are prepared; immutable OCI deployment plus the real external Fabric handoff/credential activation remain |
| 14 | [14-observability-alerting-and-logging.md](14-observability-alerting-and-logging.md) | **14S SERVER-ONLY HARNESS PASS / FINAL PHASE 14 AFTER 13B** - `SERVER_ONLY_EVIDENCE_HARNESS=PASS` for the commissioned server baseline; do not repeat it without relevant state change, but rerun the final healthy baseline after all required dependencies are commissioned |
| 14B | [14b-pre-test-commissioning-gate.md](14b-pre-test-commissioning-gate.md) | **HARD GO/NO-GO** - all setup must pass before Phase 15 |
| 15 | [15-failover-chaos-and-acceptance-testing.md](15-failover-chaos-and-acceptance-testing.md) | **FIRST FAILURE-INJECTION PHASE** |
| 16 | [16-operations-upgrades-and-scaling.md](16-operations-upgrades-and-scaling.md) | STANDBY / DRAFT |
| 17 | [17-troubleshooting.md](17-troubleshooting.md) | LIVING DRAFT; keep proven troubleshooting as we go |
| 18 | [18-runbook-and-handoff-checklists.md](18-runbook-and-handoff-checklists.md) | STANDBY / DRAFT |
| 19 | [19-cloud-ha-grafana-deployment-day-runbook.md](19-cloud-ha-grafana-deployment-day-runbook.md) | sequence reference; later phases still STANDBY |


**Parallel-safe OpenBao exception:** the OpenBao-only infrastructure subphase in [20A](20a-openbao-three-node-ha-deployment.md) may be commissioned while Phase 11 is compiling because it does not require gateway traffic, Node-RED, Grafana, the Fabric adapter image, or the external Fabric handoff. This exception does not move full Phase 20 ahead of Phase 12A/14A; it only removes idle time by preparing the independent 3-node KMS normal path.

**Authoritative pre-test order:** normal dependency order remains `Phase 10 -> Phase 11 -> Phase 13A -> Phase 12 -> Phase 12A -> Phase 14A -> Phase 20 -> Phase 13B -> Phase 14 -> Phase 14B -> Phase 15`. The numbering is retained for existing filenames; dependency order wins. **Server-first hardware-unavailable exception:** cloud-only work may be prepared or commissioned early when it does not require gateway traffic and does not weaken a later gate. Under that exception, Phase 13A fast backup, OpenBao 20A, the Fabric outbox database layer, Node-RED server runtime, and Grafana server staging may proceed while Phase 11/12 and real-uplink acceptance wait for physical access. Early server staging never converts a hardware-dependent or external-provider gate into PASS. The runtime application path remains `ChirpStack -> Node-RED -> TimescaleDB -> Grafana`; Fabric work remains asynchronous through `telemetry.fabric_outbox`.

**Current continuation boundary:** the commissioned server stack includes etcd, PostgreSQL/Patroni/TimescaleDB, HAProxy/PgBouncer, Mosquitto, Valkey/Sentinel, two-node ChirpStack, Phase 13A fast-path backup/off-host transport, the three-node OpenBao/KMS path including its audit prerequisite, the Fabric outbox database layer, Node-RED A/B with A active and B fenced on the atomic-outbox revision, and Grafana on `ulc-03`. The Node-RED synthetic atomic-outbox/replay proof and Grafana synthetic datasource/read-path proof are complete, their exact fixtures were cleaned, and the reserved synthetic identity is back to zero. Phase 13S and Phase 14S are PASS and must not be repeated. The gateway/security evidence **source implementation boundary is now complete enough for deployment**: ingest, collector, verifier/trusted decoder, verifier-owned `verified` promotion, S3 backend, Fabric adapter, frozen v1/v2 canonical vectors, four locked Linux/amd64 binaries, scratch packaging validation, and three-host deployment/standby wiring exist. The next server-first boundary is operational commissioning: build/push/pin four OCI images, provision the durable evidence store, apply `gateway_evidence` migration/login identities and PgBouncer refresh, issue Evidence PKI/MQTT identities, commission private replicas/shared-443 routing, and stage adapter-1/2 disabled. Fabric execution remains blocked only by immutable image deployment plus the real external Fabric handoff and deliberate SecretID/identity activation. Physical Gateway Phases 11/12 plus real EMU-01 Phase 12A/14A remain deferred; provider-owned Reserved IPv4/firewall/public DNS/public PKI remain external. Final Phase 13B/14, Phase 14B, and Phase 15 remain blocked until their actual dependencies are commissioned.

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

The following is the **full intended placement**, not a guarantee that every listed evidence/Fabric service is already commissioned. Current live server evidence covers etcd, PostgreSQL/Patroni/TimescaleDB, HAProxy/PgBouncer, Mosquitto, Valkey/Sentinel, two-node ChirpStack, OpenBao 3/3, the Fabric outbox schema, Node-RED A/B atomic-outbox runtime with exactly one active instance, and Grafana on `ulc-03`. Evidence/Fabric source/build work now matches the placement below; the remaining server work is image/storage/DB/PKI/network commissioning. Fabric adapter-1/2 may be deployed in fail-closed standby before the external handoff, but ledger submission remains disabled until the explicit activation preflight and credential boundary pass. Public provider ingress and physical gateway cutover remain separate external/hardware boundaries.

```text
ha-01 / ulc-01
  etcd-1
  PostgreSQL / Patroni-1
  HAProxy
  PgBouncer
  ChirpStack-1
  Mosquitto-1 preferred
  Valkey-1 + Sentinel-1
  OpenBao-1
  gateway-evidence-ingest-1 target
  gateway-mqtt-evidence-collector-1 target
  Fabric adapter-1 target

ha-02 / ulc-02
  etcd-2
  PostgreSQL / Patroni-2
  HAProxy
  PgBouncer
  ChirpStack-2
  Mosquitto-2 backup
  Valkey-2 + Sentinel-2
  OpenBao-2
  Node-RED B standby / fenced except during promotion
  gateway-evidence-ingest-2 target
  gateway-evidence-verifier-1 + trusted decoder target
  Fabric adapter-2 target

ha-03 / ulc-03
  etcd-3
  PostgreSQL / Patroni-3
  HAProxy            private DB + internal MQTT routing
  PgBouncer          telemetry/Grafana DB pooling
  Valkey-3 + Sentinel-3
  OpenBao-3
  Node-RED A active
  Grafana            non-critical visualization; single instance acceptable
  gateway-mqtt-evidence-collector-2 target
  gateway-evidence-verifier-2 + trusted decoder target

external / independently durable
  raw gateway-evidence object storage target
  must survive one Droplet loss; not two local folders
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
| [09-chirpstack-cloud-cluster.md](09-chirpstack-cloud-cluster.md) | completed two-node private ChirpStack commissioning and recovery evidence |
| [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md) | active public-ingress setup; automatic host-loss takeover deferred to Phase 15 |
| [11-raspberry-pi-4g-backhaul.md](11-raspberry-pi-4g-backhaul.md) | required physical-gateway/LTE/persistent-buffer normal-path setup |
| [12-gateway-and-device-migration.md](12-gateway-and-device-migration.md) | required migration or fresh cloud cutover setup |
| [12a-node-red-timescale-telemetry.md](12a-node-red-timescale-telemetry.md) | required Node-RED-before-database application ingestion setup |
| [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md) | Phase 13A pre-cutover and 13B final pre-test recovery boundaries |
| [14-observability-alerting-and-logging.md](14-observability-alerting-and-logging.md) | final healthy-baseline evidence harness before testing |
| [14a-grafana-cloud-deployment.md](14a-grafana-cloud-deployment.md) | required Grafana setup after real Node-RED telemetry exists |
| [14b-pre-test-commissioning-gate.md](14b-pre-test-commissioning-gate.md) | hard go/no-go before Phase 15 |
| [15-failover-chaos-and-acceptance-testing.md](15-failover-chaos-and-acceptance-testing.md) | first intentional failure-injection phase |
| [16-operations-upgrades-and-scaling.md](16-operations-upgrades-and-scaling.md) | standby operations/upgrade plan |
| [17-troubleshooting.md](17-troubleshooting.md) | living troubleshooting notes, refined as components are deployed |
| [18-runbook-and-handoff-checklists.md](18-runbook-and-handoff-checklists.md) | standby commissioning/handoff plan |
| [19-cloud-ha-grafana-deployment-day-runbook.md](19-cloud-ha-grafana-deployment-day-runbook.md) | full target sequence reference; later phases are not yet validated |
| [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md) | required OpenBao/Fabric setup before full-feature testing despite file number |

## Dissertation-test boundary

This cloud HA POC is a separate architecture experiment. Do not mix its results with the existing counted local-VM resilience experiment unless the research methodology is intentionally revised.
