# 2A. Absolute-Minimum 3-Server HA POC Layout

This page is the source of truth for the **cheap HA proof of concept**.

The goal is not to imitate production load. The goal is to imitate production **structure**.

Think of it as a small architectural model:

```text
future system: same roles + much more capacity
POC system:    same roles + only a few sensor messages
```

## 2A.1 Why we still need three Droplets

We can reduce CPU, RAM, storage, and traffic, but we cannot reduce the three **host failure domains** if we want to demonstrate majority-based HA.

```text
3 voters
lose one host
2 voters survive
2/3 majority remains
```

Use:

| Host | OS | Plan | vCPU | RAM | SSD |
|---|---|---|---:|---:|---:|
| `ha-01` | Ubuntu Server 24.04 LTS x64 | Basic | 1 | 2 GiB | 50 GiB |
| `ha-02` | Ubuntu Server 24.04 LTS x64 | Basic | 1 | 2 GiB | 50 GiB |
| `ha-03` | Ubuntu Server 24.04 LTS x64 | Basic | 1 | 2 GiB | 50 GiB |

Use the plain DigitalOcean `ubuntu-24-04-x64` image on all three. Do not mix Ubuntu releases, do not substitute a newer LTS just because it is newer, and do not use a Marketplace image for one member.

This is the experiment floor **with all architecture features retained**. The Fabric adapter allowance belongs on `ha-01/02` even before its reviewed runtime image is available; missing implementation blocks the final full-feature PASS rather than making the machines smaller on paper.

RAM decision:

```text
512 MiB -> reject
1 GiB   -> reject as the full-feature deployment baseline
2 GiB   -> minimum starting point to test
4 GiB   -> resize target only if measured 2-GiB failover fails
```

If 2 GiB cannot survive the planned failure test on **Ubuntu Server 24.04 LTS** without OOM or persistent swap pressure, resize and keep the evidence. Re-run the full resource/failover evidence after this OS change; Debian measurements do not certify the Ubuntu profile.

These are three independent Droplet/host failures, **not three datacenter or region failure domains**. The self-managed Reserved IPv4 can move only among eligible Droplets in the same DigitalOcean datacenter, so this POC proves one-host loss inside that datacenter. It does not prove datacenter outage, availability-zone independence, or multi-region disaster recovery.

## 2A.2 One self-managed public entry point

Use one DigitalOcean Reserved IPv4 and reuse HAProxy on `ha-01` and `ha-02` as the public-ingress candidates:

```text
                Reserved IPv4
                     |
             automatic reassignment
              with etcd lock
              /             \
             v               v
       ha-01 HAProxy     ha-02 HAProxy
       anchor :443       anchor :443
       anchor :8883      anchor :8883
```

DNS for both `chirpstack.<DOMAIN>` and `mqtt.<DOMAIN>` points to the Reserved IP. The address is assigned to only one app Droplet at a time. There is **no managed Network Load Balancer** in the minimum POC.

See [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md).

## 2A.3 Exact machine layout

### ha-01

```text
etcd-1
PostgreSQL / Patroni-1
HAProxy
PgBouncer
ChirpStack-1
Mosquitto-1 preferred
Valkey-1
Sentinel-1
OpenBao-1
Fabric adapter-1
```

### ha-02

```text
etcd-2
PostgreSQL / Patroni-2
HAProxy
PgBouncer
ChirpStack-2
Mosquitto-2 backup
Valkey-2
Sentinel-2
OpenBao-2
Fabric adapter-2
```

### ha-03

```text
etcd-3
PostgreSQL / Patroni-3
HAProxy private database + internal MQTT frontends
PgBouncer
Valkey-3
Sentinel-3
OpenBao-3
Node-RED
Grafana
```

## 2A.4 What we removed to save money/resources

```text
REMOVE from POC
----------------
standalone TimescaleDB container
dedicated telemetry VM
dedicated monitoring VM
managed PostgreSQL
managed Valkey
block volumes
full Prometheus metrics stack
production-size database caches
production-size connection limits
```

Telemetry still uses TimescaleDB. The difference is that TimescaleDB runs as an extension inside the existing Patroni PostgreSQL members instead of as a separate telemetry server.

## 2A.5 Database layout

```text
                  Patroni PostgreSQL

        ha-01           ha-02           ha-03
        PG-1            PG-2            PG-3
          \               |               /
           +--------------+--------------+
                          |
               1 primary + 2 replicas
                          |
            +-------------+-------------+
            |                           |
            v                           v
       chirpstack           lorawan_telemetry [TimescaleDB]
                                      |
                       +--------------+--------------+
                       |              |              |
                       v              v              v
                uplinks hypertable  measurements   fabric_outbox
                                    hypertable     ordinary table
```

A PostgreSQL primary change therefore moves **both** the ChirpStack and telemetry/outbox write paths together.

## 2A.6 Database client path

Run PgBouncer and a private HAProxy PostgreSQL frontend on every host:

```text
local application
      |
      v
PgBouncer :6432
      |
      v
HAProxy :15432
      |
      v
current Patroni primary :5432
```

Examples:

```text
ha-01 ChirpStack-1 -> local PgBouncer
ha-02 ChirpStack-2 -> local PgBouncer
ha-03 Node-RED     -> local PgBouncer
ha-03 Grafana      -> local PgBouncer
ha-03 Node-RED     -> local HAProxy :18884 -> active Mosquitto :8886
ha-01 adapter-1    -> local PgBouncer
ha-02 adapter-2    -> local PgBouncer
```

## 2A.7 HA groups

```text
PostgreSQL / Patroni
  3 members
  1 primary + 2 replicas

etcd
  3 voters
  quorum 2

Valkey
  3 data servers
  1 primary + 2 replicas

Sentinel
  3 voters
  quorum 2

OpenBao
  3 Raft members
  quorum 2

ChirpStack
  2 application instances

Mosquitto
  2 brokers
  preferred + backup

Fabric adapter
  2 workers
  one shared PostgreSQL outbox
```

## 2A.8 Node-RED active/passive; Grafana remains single

Node-RED is now part of the application availability target. Keep one active instance on ha-03/ulc-03 and a **stopped, pre-staged standby** on ha-02/ulc-02. The standby consumes no steady-state Node-RED container memory while stopped, but the resource test must prove ha-02 can carry the extra Node-RED workload after promotion.

```text
normal
  -> Node-RED A active on ha-03
  -> Node-RED B stopped on ha-02
  -> Grafana on ha-03

ha-03 lost
  -> fence/confirm old Node-RED unavailable
  -> promote Node-RED B on ha-02
  -> fresh telemetry processing resumes
  -> Grafana may pause

and
  -> PostgreSQL stays available
  -> existing telemetry/fabric_outbox stay available
  -> adapters on ha-01/ha-02 can keep processing eligible jobs
  -> ChirpStack/MQTT continue
```

Do not run both Node-RED subscribers concurrently. Grafana remains single for the current POC because dashboard interruption does not stop ingestion. Active/passive Node-RED availability and Grafana availability are separate concerns.

## 2A.9 Expected one-host failures

| Failure | POC expectation |
|---|---|
| `ha-01` lost | when ha-01 owns public ingress, Reserved IPv4 automatically moves to ha-02 with DNS unchanged; ha-02 serves ChirpStack; Mosquitto-2 is available; quorum groups remain 2/3; for a full-feature PASS, deployed adapter-2 must also remain able to claim/reconcile eligible outbox work |
| `ha-02` lost | mirror through ha-01; for this test place the Reserved IPv4 on ha-02 first so automatic public-ingress movement is actually exercised |
| `ha-03` lost | LoRaWAN core stays up; Node-RED/Grafana pause; PostgreSQL/outbox still exist on surviving Patroni members |
| PG primary lost | Patroni promotes a replica; all DB clients keep the same PgBouncer endpoint |
| Valkey primary lost | Sentinel promotes; HAProxy follows |
| OpenBao member lost | 2/3 Raft quorum remains |
| adapter-1 lost | **required for full-feature PASS:** deployed adapter-2 claims eligible work after valid lease expiry/reclaim; if the reviewed adapter implementation is unavailable, the overall full-feature POC remains BLOCKED |

Only one failure is injected at a time.

## 2A.10 Cost

Planning floor checked 2026-08-20:

```text
ha-01  1 vCPU / 2 GiB   $12/month
ha-02  1 vCPU / 2 GiB   $12/month
ha-03  1 vCPU / 2 GiB   $12/month
assigned Reserved IPv4    $0/month
managed Network LB        $0/month (not used)
                         ---------
POC floor                $36/month
```

No extra cloud resource is added just for telemetry, PgBouncer, OpenBao, Grafana, or the Fabric adapters.

## 2A.11 When to resize

Do not resize because a production sizing formula says so. Resize only when the POC shows evidence such as:

```text
OOM kill
repeated swap thrashing
PostgreSQL cannot complete failover
ChirpStack repeatedly restarts under normal few-sensor load
OpenBao becomes unhealthy because of host memory pressure
one-host failure makes the surviving application node unusable
```

If 2 GiB fails, move to 4 GiB and record that result. The purpose of the POC is to learn the real floor.

## 2A.12 Build order

Do not maintain a second frozen deployment order in this sizing file. The canonical live order and status are in [00-README.md](00-README.md), while [00-build-execution-log.md](00-build-execution-log.md) records what actually happened.

The completed sequence so far is:

```text
three active Droplets / host baseline
        -> host hardening
        -> Docker runtime + 10.104 east-west validation
        -> three-member etcd bootstrap and quorum
        -> STOP / next technology remains standby
```

The DigitalOcean Cloud Firewall is externally controlled, and Reserved-IP/public-DNS commissioning is not evidenced as a prerequisite that occurred before etcd. Do not rewrite history by placing those provider-side steps into the completed sequence.

When work resumes, activate only the next numbered standby manual, re-check it against the live servers, document the result, then update the canonical sequence/status table.

Continue with [03-digitalocean-vpc-droplets-and-firewalls.md](03-digitalocean-vpc-droplets-and-firewalls.md) for foundation evidence boundaries.
