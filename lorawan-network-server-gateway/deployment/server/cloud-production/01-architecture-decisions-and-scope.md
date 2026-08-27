# 1. HA POC Architecture Decisions

## 1.1 Goal

Build a **cheap scale model of the future HA deployment**.

We are not sizing for hundreds or thousands of devices. We are proving the relationships between the components using only a few real sensor uplinks.

The acceptance question is:

> If any one of `ha-01`, `ha-02`, or `ha-03` disappears, does the architecture recover without manually editing client IPs, DSNs, or service endpoints?

## 1.2 POC machine profile

Start with three identical small Droplets using the same lean host OS:

```text
OS: Ubuntu Server 24.04 LTS x64
DigitalOcean image slug: ubuntu-24-04-x64

ha-01  1 vCPU / 2 GiB / 50 GiB
ha-02  1 vCPU / 2 GiB / 50 GiB
ha-03  1 vCPU / 2 GiB / 50 GiB
```

This is intentionally aggressive. It is the **minimum full-feature POC starting floor**, not a production recommendation. The POC keeps every documented architecture technology; only capacity, concurrency, cache sizes, worker counts, and traffic are reduced. Because the host baseline is now Ubuntu Server 24.04 LTS, all capacity acceptance must be measured again on that OS; do not reuse memory/headroom measurements from an earlier Debian experiment.

Do not use `512 MiB` or `1 GiB` nodes as the planned full-feature baseline. Those sizes leave too little credible headroom for PostgreSQL/TimescaleDB, Patroni, etcd, OpenBao, Valkey/Sentinel, routing, ChirpStack/MQTT or Node-RED/Grafana, plus the Fabric workers and failover spikes.

Three machines are still non-negotiable because the architecture needs a majority after one host disappears:

```text
3 voters
lose 1
2 remain
2/3 is still a majority
```

## 1.3 Service placement

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
  Fabric adapter-1

ha-02
  etcd-2
  PostgreSQL/Patroni-2
  HAProxy
  PgBouncer
  ChirpStack-2
  Mosquitto-2 backup
  Valkey-2 + Sentinel-2
  OpenBao-2
  Fabric adapter-2

ha-03
  etcd-3
  PostgreSQL/Patroni-3
  HAProxy private DB + internal MQTT routes
  PgBouncer
  Valkey-3 + Sentinel-3
  OpenBao-3
  Node-RED
  Grafana
```

No dedicated telemetry database server exists in this POC.

## 1.4 One PostgreSQL cluster, two databases

The POC deliberately reuses the Patroni cluster:

```text
PostgreSQL HA cluster
  |
  +-- chirpstack
  |     ChirpStack operational state
  |
  +-- lorawan_telemetry [TimescaleDB enabled]
        telemetry.uplinks hypertable
        telemetry.measurements hypertable
        telemetry.fabric_outbox ordinary table
```

Why: the test volume is tiny, so a **separate TimescaleDB server** would add another service lifecycle without helping us prove the HA pattern. But TimescaleDB itself is part of the intended deployment, so we keep the feature by installing the extension on every Patroni member and enabling it in `lorawan_telemetry`.

The POC therefore uses the real telemetry shape: TimescaleDB-backed hypertables for sensor time-series data and ordinary PostgreSQL tables for transactional state such as `telemetry.fabric_outbox`. Capacity is reduced; features are not removed.

## 1.5 Database access decision

Keep PgBouncer because we want the future connection-pooling shape represented in the POC.

Run PgBouncer and a private PostgreSQL HAProxy frontend on all three hosts so local applications can use the same path:

```text
application
  -> local PgBouncer :6432
  -> local HAProxy :15432
  -> current Patroni primary :5432
```

Applications use separate database roles even though they share the PostgreSQL cluster.

## 1.6 PostgreSQL and etcd

Run one Patroni/PostgreSQL member and one etcd member on every Droplet.

Normal state:

```text
PostgreSQL: 1 primary + 2 replicas
etcd:       3 voters
```

After one host loss, etcd keeps `2/3` quorum and Patroni can keep or promote a writable PostgreSQL primary.

The POC deliberately uses small PostgreSQL memory settings and PgBouncer so the database does not preallocate production-sized caches or connection counts.

Phase 12A adds a **separate private** Node-RED MQTT frontend on logical `ha-03` / provider host `ulc-03`: `10.104.0.8:18884 -> Mosquitto :8886`. This is deliberately distinct from the ChirpStack-specific `:18883 -> :8885` routes on `ulc-01/02`. It gives Node-RED a stable Mosquitto-1-preferred/Mosquitto-2-backup mTLS path without pinning it to one app host or exposing `ulc-03` publicly.

## 1.7 Valkey

Use:

```text
3 Valkey data servers
3 Sentinels
Sentinel quorum = 2
```

We are proving primary promotion, not cache scale. Do not add Valkey Cluster sharding.

## 1.8 MQTT

Use two Mosquitto brokers:

```text
ha-01 -> Mosquitto-1 preferred
ha-02 -> Mosquitto-2 backup
```

This proves automatic broker-service failover. It does not pretend that Mosquitto broker state is replicated.

The Raspberry Pi local persistent Mosquitto remains the bounded uplink buffer.

## 1.9 ChirpStack

Run exactly two instances:

```text
ha-01 -> ChirpStack-1
ha-02 -> ChirpStack-2
```

Two is enough to prove Network Server application failover. A third instance would only add load to the POC.

The gateway offline queue is not a substitute for the second ChirpStack instance because it cannot perform OTAA processing or live downlink scheduling.

## 1.10 OpenBao

Run three OpenBao Integrated Storage/Raft members:

```text
OpenBao-1
OpenBao-2
OpenBao-3
quorum = 2
```

For this POC, three members are enough to demonstrate one-node KMS survival. A larger future production KMS can be designed after this proof.

The Fabric adapter never receives an exportable signing private key; it calls OpenBao Transit through the stable private KMS endpoint.

## 1.11 Fabric adapter and outbox

The **target architecture** runs two workers:

```text
ha-01 -> Fabric adapter-1
ha-02 -> Fabric adapter-2
```

The two adapter workers are **required by the full-feature target architecture** and their capacity is included in node sizing. Runtime deployment is still blocked by the reviewed implementation/image readiness gate in [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md). If that implementation is missing, other infrastructure layers may be tested, but the overall full-feature POC remains **BLOCKED**, not passed.

Both read the **same** `telemetry.fabric_outbox` table from `lorawan_telemetry` through the PostgreSQL HA path.

Because that outbox is now in the Patroni cluster, it is no longer tied to `ha-03`.

The flow is asynchronous:

```text
Node-RED
  -> commit telemetry + selected outbox row
  -> adapter claims later
  -> OpenBao sign/verify
  -> external Fabric Gateway
  -> commit result stored back in outbox
```

Fabric/KMS failure must not block an otherwise valid telemetry commit.

## 1.12 Node-RED and Grafana

Keep one Node-RED and one Grafana on `ha-03` because this is a control-plane HA POC, not a full application-platform HA test.

If `ha-03` fails:

```text
LoRaWAN control plane     continues
PostgreSQL databases     continue
existing Fabric outbox   remains available; deployed adapter-1/2 may continue existing work
Node-RED ingestion       pauses
Grafana                   pauses
```

That limitation is acceptable for this POC and must be stated clearly.

## 1.13 Public ingress

Do **not** buy a managed Network Load Balancer for this POC. Reuse HAProxy on `ha-01` and `ha-02` behind one DigitalOcean Reserved IPv4:

```text
chirpstack.<DOMAIN> ----+
                       +--> Reserved IPv4
mqtt.<DOMAIN> ----------+        |
                                 | assigned to one app host
                                 v
                     ha-01 HAProxy OR ha-02 HAProxy
                         |                 |
                  :443 -> ChirpStack      |
                  :8883 -> active Mosquitto
```

The two public HAProxy listeners bind to each Droplet's **anchor IP**, not its VPC IP and not `0.0.0.0`. A small failover agent on `ha-01/02` probes the public service, confirms the candidate is locally healthy, takes an etcd distributed lock, and uses the DigitalOcean API to reassign the Reserved IP when the current owner fails.

The Reserved IP is active/passive and can belong to only one Droplet at a time. There is no automatic failback: after recovery, the returning host becomes a standby candidate until an operator deliberately moves the address later.

See [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md).

## 1.14 POC scope

This POC **does prove** when the corresponding implementation is present:

```text
always executable infrastructure scope:
  one-host quorum survival
  PostgreSQL primary failover
  Valkey primary failover
  public Reserved-IPv4 ownership failover between ha-01/ha-02 with unchanged DNS
  public ChirpStack failover
  MQTT service failover
  OpenBao one-member loss
  shared outbox survives PostgreSQL-primary changes
  no manual client endpoint edits during failover

required full-feature execution gates:
  Fabric worker redundancy -> required for final full-feature PASS; BLOCKED until the reviewed adapter implementation/image exists
  gateway-integrity v2     -> required when v2 is in the selected runtime scope; BLOCKED until reviewed v2 runtime components exist
```

This POC **does not prove**:

```text
production capacity
production RPO/RTO
large device fleets
large telemetry retention
multi-region disaster recovery
full Node-RED HA
full Grafana HA
external Fabric network HA
production compliance/security sizing
survival of two simultaneous Droplet failures
```

## 1.15 Failure tests

Test one failure at a time:

```text
ha-01 loss
ha-02 loss
ha-03 loss
PostgreSQL primary process loss
Valkey primary loss
Mosquitto-1 loss
ChirpStack-1 loss
OpenBao-1 loss
Fabric adapter-1 loss       # only when adapter execution gate is satisfied
external Fabric outage      # full reconcile/drain test only when adapter exists
4G outage and gateway queue drain
```

Restore full redundancy before starting the next failure.

See [19-cloud-ha-grafana-deployment-day-runbook.md](19-cloud-ha-grafana-deployment-day-runbook.md).
