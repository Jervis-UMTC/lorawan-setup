# 2. Capacity, Cost, Storage, and IP Plan

## 2.1 Inventory worksheet

Create the deployment inventory before provisioning.

| Placeholder | Example role | Required value |
|---|---|---|
| `<DO_REGION>` | DigitalOcean region | Region approved for latency, law, and service availability |
| `<VPC_CIDR>` | Private subnet | Non-overlapping RFC1918 range |
| `<ENVIRONMENT>` | Environment name | `staging` or `production` |
| `<DOMAIN>` | DNS zone | Organization-controlled domain |
| `<PG_SCOPE>` | Patroni cluster name | Stable unique name |
| `<OBJECT_BUCKET>` | WAL/base backups | Private bucket with lifecycle policy |
| `<GATEWAY_COUNT>` | Current gateways | Verified inventory count |
| `<DEVICE_COUNT>` | Current devices | Verified ChirpStack count |
| `<UPLINKS_PER_SECOND>` | Busy-hour load | Measured or calculated |
| `<RETENTION_DAYS>` | Operational retention | Required history, deletion constraints, and backup policy |

## 2.2 Reference private address plan

The addresses below are examples. Replace them with an approved non-overlapping plan.

```text
VPC:                  10.60.0.0/20
Application nodes:    10.60.1.0/24
PostgreSQL nodes:     10.60.2.0/24
Dedicated etcd:       10.60.3.0/24
Monitoring/admin:     10.60.4.0/24
Reserved growth:      10.60.5.0/24 through 10.60.15.0/24
Gateway management tunnel range: 10.70.0.0/24, only when a management VPN is approved
```

Example host inventory:

| Host | Role | Example private IP | Public IP |
|---|---|---:|---|
| `app-01` | ChirpStack, HAProxy, PgBouncer, MQTT broker/backend | `10.60.1.11` | None or restricted management |
| `app-02` | ChirpStack, HAProxy, PgBouncer, MQTT broker/backend | `10.60.1.12` | None or restricted management |
| `db-01` | Spilo/Patroni/PostgreSQL, optional etcd | `10.60.2.11` | None |
| `db-02` | Spilo/Patroni/PostgreSQL, optional etcd | `10.60.2.12` | None |
| `db-03` | Spilo/Patroni/PostgreSQL, optional etcd | `10.60.2.13` | None |
| `dcs-01..03` | Dedicated etcd in Profile B | `10.60.3.11..13` | None |
| `monitor-01` | Optional monitoring and log aggregation | `10.60.4.11` | None |

Do not use addresses already routed by an office VPN, mobile carrier private APN, customer network, Kubernetes cluster, or another VPC.

## 2.3 Initial sizing method

Do not size from device count alone. Measure or estimate:

- uplinks and downlinks per second at normal and burst load;
- Gateway OS MQTT connection count, reconnect-storm size, broker client count, and message load;
- PostgreSQL transactions, connection count, active working set, and write-ahead log rate;
- Valkey memory, key count, and eviction behavior;
- retention and backup growth;
- dashboard and API query concurrency;
- CPU architecture required by every pinned image.

### Conservative starting ranges

These are planning ranges, not purchase instructions.

| Role | Minimum lab | Initial production review range |
|---|---:|---:|
| Application node | 2 vCPU / 2 GiB | 2 to 4 dedicated vCPU / 4 to 8 GiB |
| PostgreSQL member | 2 vCPU / 4 GiB | 4 dedicated vCPU / 8 to 16 GiB |
| Dedicated etcd member | 1 vCPU / 1 GiB | 2 vCPU / 2 to 4 GiB with fast low-latency disk |
| Monitoring node | 2 vCPU / 4 GiB | Based on retention and scrape volume |
| Managed Valkey | single node for development | HA plan with at least one standby for production |

Use dedicated CPU for sustained database workloads. Shared-CPU instances can be suitable for staging but may introduce noisy-neighbor latency that affects etcd elections and PostgreSQL response time.

## 2.4 Size PostgreSQL storage

Each PostgreSQL member needs an independent persistent volume. Never attach the same PostgreSQL data directory to multiple active members.

Choose the volume and alert thresholds from these inputs:

```text
PostgreSQL major version                 determines data-directory compatibility
Initial data volume per member           current data plus operational headroom
Expected monthly growth                  measured tables, indexes, and retained history
Peak WAL per hour                        measured during busy and maintenance periods
Free-space alert threshold               time needed to respond before writes fail
IOPS and latency requirement             observed database workload and failover target
Filesystem and stable mount path         supported by the host and backup procedure
Backup temporary-space allowance         largest tested dump, base backup, or restore workspace
```

Keep these values with the volume IDs and database backup references because they are needed during expansion, replica replacement, and restore. Leave headroom for WAL spikes, vacuum, index rebuilds, base backups, and failed-replica rebuilds. If measured growth or WAL can consume the response window before an alert is acted on, increase capacity or shorten retention before deployment.

## 2.5 etcd storage and latency

etcd requires low and predictable fsync latency. Do not place its data directory on network filesystems, object storage, or a busy PostgreSQL volume. In the co-located profile, use a separate filesystem path and monitor etcd disk latency independently.

Use three or five voting members. Two members do not provide safe quorum availability: losing either member removes majority.

## 2.6 Object storage estimate

Estimate storage as:

```text
monthly object storage = retained base backups
                       + retained WAL archives
                       + logical exports
                       + protected configuration archives
                       + restore-test copies
```

Define lifecycle transitions and deletion rules so a complete base-backup and WAL restore chain remains available for the stated RPO. Do not expire the last known restorable base backup while retained WAL files still depend on it.

## 2.7 4G data estimate

Measure real Gateway OS MQTT/TLS traffic and protocol overhead. Include:

- MQTT keepalive, gateway events, state messages, and uplinks;
- downlink commands and transmission results;
- TLS handshakes and reconnects;
- monitoring traffic;
- remote administration;
- operating-system and package downloads;
- log uploads.

Apply a reconnect-storm and retransmission margin. Configure carrier data-cap alerts before production.

## 2.8 Cost worksheet

Prices change. Retrieve current prices from the provider when preparing the deployment budget, and keep the date and region with the estimate.

| Item | Quantity | Monthly unit price | Monthly subtotal |
|---|---:|---:|---:|
| Application Droplet | 2 | `<CURRENT_PRICE>` | |
| PostgreSQL Droplet | 3 | `<CURRENT_PRICE>` | |
| Dedicated etcd Droplet, Profile B | 0 or 3 | `<CURRENT_PRICE>` | |
| PostgreSQL block volume | 3 | `<CURRENT_PRICE>` | |
| ChirpStack UI/API load balancer | 1 | `<CURRENT_PRICE>` | |
| MQTT TLS TCP pass-through load balancer or broker endpoint | 1 | `<CURRENT_PRICE>` | |
| Managed Valkey primary/standby | 1 cluster | `<CURRENT_PRICE>` | |
| Object storage and operations | 1 | `<CURRENT_PRICE>` | |
| Snapshots/backups | variable | `<CURRENT_PRICE>` | |
| Monitoring/logging | variable | `<CURRENT_PRICE>` | |
| Public egress and 4G plan | variable | `<CURRENT_PRICE>` | |

Add tax, support, certificate service, domain, SMS/on-call notification, and off-region DR costs.

## 2.9 Capacity acceptance

Before production cutover, prove:

- CPU remains below the approved sustained threshold at expected peak plus margin;
- PostgreSQL disk latency, replication lag, WAL archive delay, and free space remain healthy;
- PgBouncer does not build an increasing client wait queue;
- Gateway OS MQTT and ChirpStack reconnect tests do not exhaust broker file descriptors, connections, or memory;
- Valkey has headroom and no unapproved evictions;
- load-balancer and firewall limits support the intended connections;
- backup duration and restore duration meet the objectives.

Next: [03-digitalocean-vpc-droplets-and-firewalls.md](03-digitalocean-vpc-droplets-and-firewalls.md)
