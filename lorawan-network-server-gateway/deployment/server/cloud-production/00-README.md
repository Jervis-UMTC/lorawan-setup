# Minimal 3-Server HA Proof of Concept

Use this folder to build the **smallest practical cloud version of the future LoRaWAN HA architecture**.

Think of it as a **scale model of a bridge**:

- the supports and failure paths are real;
- the traffic is tiny;
- we are proving that the design works before paying for production-sized machines.

This POC is **not capacity sizing for production**. A few sensor uplinks are enough. The important result is that one server can fail and the remaining architecture behaves as designed.

## Start here

Read in this order:

1. [02a-digitalocean-machine-layout-and-specs.md](02a-digitalocean-machine-layout-and-specs.md) — exact POC machines and why three are still required
2. [03-digitalocean-vpc-droplets-and-firewalls.md](03-digitalocean-vpc-droplets-and-firewalls.md) — VPC, Droplets, Reserved IP, firewall
3. [04a-host-security-hardening-execution-runbook.md](04a-host-security-hardening-execution-runbook.md) — harden each freshly provisioned host and record every command/verification before the application stack is installed
4. [03a-self-managed-public-ingress.md](03a-self-managed-public-ingress.md) — self-managed HAProxy + Reserved-IP public failover
5. [18-cloud-ha-grafana-deployment-day-runbook.md](18-cloud-ha-grafana-deployment-day-runbook.md) — build and failover order
6. [05-raspberry-pi-4g-backhaul.md](05-raspberry-pi-4g-backhaul.md) — physical gateway 4G/LTE path
7. [19-openbao-and-fabric-adapter.md](19-openbao-and-fabric-adapter.md) — OpenBao and external Fabric integration

## POC resources

```text
OS on ha-01/02/03: Ubuntu Server 24.04 LTS x64
DigitalOcean image slug: ubuntu-24-04-x64

ha-01  Basic 1 vCPU / 2 GiB / 50 GiB
ha-02  Basic 1 vCPU / 2 GiB / 50 GiB
ha-03  Basic 1 vCPU / 2 GiB / 50 GiB

1 x DigitalOcean Reserved IPv4, always assigned to ha-01 or ha-02
0 x managed Network Load Balancer
```

Use the plain DigitalOcean **Ubuntu 24.04 (LTS) x64** OS image, not a Marketplace/1-Click application image. Pin the exact `ubuntu-24-04-x64` image family on all three hosts; do not write "latest Ubuntu LTS" in the build record because a future rebuild could otherwise select a newer LTS release with different packages and defaults.

The separate single-VM simulation/lab profile may also use Ubuntu, but it has different sizing, networking, firewall, and service-placement instructions. Sharing an OS family does **not** make those VM steps interchangeable with this three-Droplet cloud POC.

The **2-GiB-per-host profile is the minimum full-feature starting floor** for this POC. `512 MiB` and `1 GiB` are not accepted deployment baselines when all documented services are retained, including TimescaleDB, OpenBao, Node-RED/Grafana where assigned, and both Fabric adapter workers. A few sensor messages reduce variable workload; they do not remove the always-on memory cost of the HA control plane.

If a host OOMs or spends significant time swapping during the one-host-failure rehearsal, resize that profile and record the observed minimum. Do not hide a failed sizing experiment, and do not delete a required technology just to make the node fit.

Do not create managed PostgreSQL, managed Valkey, block volumes, dedicated monitoring servers, dedicated MQTT servers, or a separate telemetry database server/service for this POC. The logical `lorawan_telemetry` database still exists inside the Patroni cluster.

## Service placement

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

The existing Patroni PostgreSQL cluster stores two logical databases:

```text
PostgreSQL / Patroni HA cluster

  chirpstack
    -> ChirpStack operational state

  lorawan_telemetry [TimescaleDB enabled]
    -> telemetry.uplinks hypertable
    -> telemetry.measurements hypertable
    -> telemetry.fabric_outbox ordinary transactional table
```

Because both databases are inside the same PostgreSQL cluster, Patroni replication carries both across `ha-01`, `ha-02`, and `ha-03`.

For the POC, install the same pinned TimescaleDB extension version on all three PostgreSQL members and enable it in `lorawan_telemetry`. Use Timescale hypertables for time-series telemetry so the POC preserves the intended production data model. Keep `fabric_outbox` as an ordinary PostgreSQL table because it is a transactional work queue, not time-series storage.

## Full three-server architecture

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

## HA relationships we are actually proving

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

## One database connection pattern

All database clients use the same idea:

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

## Telemetry and Fabric flow

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

## What this POC proves

A pass means we have evidence that the **architecture pattern** works:

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

## Public boundary

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

## Detailed manuals

| File | Use |
|---|---|
| [01-architecture-decisions-and-scope.md](01-architecture-decisions-and-scope.md) | what the POC does and does not claim |
| [02-capacity-cost-and-ip-plan.md](02-capacity-cost-and-ip-plan.md) | tiny starting size and cost |
| [03-digitalocean-vpc-droplets-and-firewalls.md](03-digitalocean-vpc-droplets-and-firewalls.md) | cloud resources/network |
| [04a-host-security-hardening-execution-runbook.md](04a-host-security-hardening-execution-runbook.md) | live hardening steps, verification evidence, and execution log |
| [03a-self-managed-public-ingress.md](03a-self-managed-public-ingress.md) | HAProxy + Reserved-IP public failover |
| [06-etcd-cluster.md](06-etcd-cluster.md) | etcd quorum |
| [07-spilo-patroni-postgresql-cluster.md](07-spilo-patroni-postgresql-cluster.md) | shared PostgreSQL HA cluster |
| [08-haproxy-and-pgbouncer.md](08-haproxy-and-pgbouncer.md) | stable database path |
| [09-mqtt-and-valkey.md](09-mqtt-and-valkey.md) | MQTT + Valkey/Sentinel |
| [10-chirpstack-cloud-cluster.md](10-chirpstack-cloud-cluster.md) | two ChirpStack instances |
| [13a-grafana-cloud-deployment.md](13a-grafana-cloud-deployment.md) | tiny Grafana setup |
| [14-failover-chaos-and-acceptance-testing.md](14-failover-chaos-and-acceptance-testing.md) | failover tests |
| [18-cloud-ha-grafana-deployment-day-runbook.md](18-cloud-ha-grafana-deployment-day-runbook.md) | actual POC deployment order |
| [19-openbao-and-fabric-adapter.md](19-openbao-and-fabric-adapter.md) | KMS + Fabric adapter path |

## Dissertation-test boundary

This cloud HA POC is a separate architecture experiment. Do not mix its results with the existing counted local-VM resilience experiment unless the research methodology is intentionally revised.
