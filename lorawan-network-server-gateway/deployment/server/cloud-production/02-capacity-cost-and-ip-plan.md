# 2. Tiny POC Capacity, Cost, and IP Plan

This worksheet is for the **scale-model HA POC**, not future production sizing.

## 2.1 Starting resources

Use three identical small Basic Droplets:

| Host | OS image | vCPU | RAM | Included SSD | POC role |
|---|---|---:|---:|---:|---|
| `ha-01` | Ubuntu Server 24.04 LTS x64 (`ubuntu-24-04-x64`) | 1 | 2 GiB | 50 GiB | app/core A + Fabric adapter-1 |
| `ha-02` | Ubuntu Server 24.04 LTS x64 (`ubuntu-24-04-x64`) | 1 | 2 GiB | 50 GiB | app/core B + Fabric adapter-2 |
| `ha-03` | Ubuntu Server 24.04 LTS x64 (`ubuntu-24-04-x64`) | 1 | 2 GiB | 50 GiB | quorum + Node-RED + Grafana |

Also create one DigitalOcean Reserved IPv4 and keep it assigned to `ha-01` or `ha-02`. Do **not** create a managed Network Load Balancer for this POC.

Why identical small nodes: we are trying to discover the **actual minimum that can run the complete architecture with a few sensor messages**, not pre-pay for expected future traffic. All technologies stay; only capacity and concurrency are reduced.

### 2.1A Full-feature RAM feasibility boundary

Use this as the planning decision before provisioning:

| RAM per host | Full-feature use | Decision |
|---:|---|---|
| 512 MiB | OS plus the complete HA service set cannot retain credible working/failover headroom | **Reject** |
| 1 GiB | may boot selected services with aggressive tuning, but app hosts and the Node-RED/Grafana host have too little failover margin when every feature is included | **Reject as deployment baseline** |
| 2 GiB | deliberately tight but realistic enough to execute the complete few-sensor HA POC and measure the real floor | **Starting minimum** |
| 4 GiB | fallback when measured 2-GiB runs OOM, repeatedly swap, or cannot complete failover | **Resize only when evidence requires it** |

The 2-GiB choice is not a claim that every process has fixed memory use. PostgreSQL worker activity, Go runtimes, Node.js/Grafana heaps, replication, TLS, OpenBao Raft, Fabric activity, and the Ubuntu host baseline can spike. The acceptance test therefore measures the surviving hosts during actual failover. Any previous RAM result collected on Debian is historical only and must not be used to declare the Ubuntu build passed.

If a node OOMs during failover, resize and record the result. That is useful POC evidence; removing a required feature to make the node fit is not an acceptable sizing fix.

## 2.2 Record before provisioning

```text
DigitalOcean region:
VPC CIDR:
ha-01 private IP:
ha-02 private IP:
ha-03 private IP:
ha-01 Droplet ID:
ha-02 Droplet ID:
ha-01 anchor IPv4:
ha-02 anchor IPv4:
Reserved IPv4:
Domain:
MQTT FQDN: mqtt.<DOMAIN>
ChirpStack FQDN: chirpstack.<DOMAIN>
SSH source CIDR:
Gateway EUI:
```

Do not put passwords, AppKeys, private keys, SIM PINs, or API tokens here.

### 2.2A Provisioning evidence collected on 2026-08-20

All three provisioned Droplets have now been inspected. Their provider hostnames are already consistent (`ulc-01`, `ulc-02`, `ulc-03`), so the safest operational choice is to **keep those hostnames stable** and use `ha-01`, `ha-02`, and `ha-03` as documentation/logical role aliases instead of renaming live hosts later.

Proposed role mapping, to be used unless the deployment owner explicitly changes it before quorum configuration:

```text
ulc-01 -> logical ha-01
ulc-02 -> logical ha-02
ulc-03 -> logical ha-03
```

Actual baseline inventory:

```text
ulc-01
  Provider: DigitalOcean
  OS: Ubuntu 24.04.4 LTS (Noble)
  Kernel before initial hardening patch: 6.8.0-124-generic
  Kernel after initial patch/reboot: 6.8.0-138-generic
  Patch/reboot status: PASS on 2026-08-20
  Architecture: x86-64
  vCPU: 1
  RAM: 1.9 GiB
  Swap: none
  Root filesystem: ext4, approximately 48 GiB usable, approximately 46 GiB free
  Public IPv4: 143.198.205.54/20 on eth0
  Additional eth0 address: 10.15.0.5/16
  Candidate cluster/VPC IPv4: 10.104.0.2/20 on eth1
  Default route: eth0 via 143.198.192.1

ulc-02
  Provider: DigitalOcean
  OS: Ubuntu 24.04.4 LTS (Noble)
  Kernel before initial hardening patch: 6.8.0-124-generic
  Architecture: x86-64
  vCPU: 1
  RAM: 1.9 GiB
  Swap: none
  Root filesystem: ext4, approximately 48 GiB usable, approximately 46 GiB free
  Public IPv4: 165.22.253.127/20 on eth0
  Additional eth0 address: 10.15.0.7/16
  Candidate cluster/VPC IPv4: 10.104.0.4/20 on eth1
  Default route: eth0 via 165.22.240.1

ulc-03 (replacement Droplet after retirement of the original host)
  Provider: DigitalOcean
  OS: Ubuntu 24.04.4 LTS (Noble)
  Kernel before initial hardening patch: 6.8.0-124-generic
  Kernel after initial patch/reboot: 6.8.0-138-generic
  Patch/reboot status: PASS on 2026-08-20
  Architecture: x86-64
  vCPU: 1
  RAM: 1.9 GiB
  Swap: none
  Root filesystem: ext4, approximately 48 GiB usable, approximately 46 GiB free
  Public IPv4: 159.223.50.57/20 on eth0
  Additional eth0 address: 10.15.0.6/16
  Candidate cluster/VPC IPv4: 10.104.0.8/20 on eth1
  Default route: eth0 via 159.223.48.1

All three:
  Time: UTC, synchronized, NTP active
  Unexpected application listeners: none
  SSH baseline: TCP/22 listening on all IPv4 and IPv6 addresses before hardening
  Failed systemd units: 0
```

The active-host addresses `10.104.0.2/20`, `10.104.0.4/20`, and `10.104.0.8/20` are treated as the **candidate VPC/east-west addresses** until the DigitalOcean VPC view confirms that `10.104.0.0/20` is the intended project VPC. The retired original `ulc-03` address `10.104.0.3/20` must not be reused in quorum/service configuration. Once the provider VPC is confirmed, use the active exact addresses for east-west configuration; do not replace them with the example `10.60.1.x` addresses elsewhere in the manuals.

### 2.2B Record the software baseline

Fill this before deployment and update it only through a documented change/upgrade procedure:

```text
Host OS image/release: Ubuntu Server 24.04 LTS x64
DigitalOcean image slug: ubuntu-24-04-x64
DigitalOcean image numeric ID used at creation:
DigitalOcean image Created timestamp:
Kernel release after initial patch/reboot:
Docker/container runtime:

etcd version:
Spilo source commit/image digest:
PostgreSQL major/minor:
Patroni version:
TimescaleDB extension version/build:
HAProxy version:
PgBouncer version:
Mosquitto image/version/digest:
Valkey image/version/digest:
ChirpStack image/version/digest:
OpenBao version/image digest:
Node-RED image/version/digest:
Node-RED PostgreSQL palette/node version:
Grafana image/version/digest:
Fabric adapter image digest: REQUIRED for full-feature PASS; currently BLOCKED until reviewed implementation exists
```

Also record configuration hashes for files that must be identical or intentionally coordinated across hosts, such as ChirpStack common/region files, HAProxy routing, Mosquitto ACL policy, and OpenBao policies.

**Why:** after a failover, version drift can look like an HA bug. Reproducing the exact tested scale model requires knowing both the topology and the software baseline.

## 2.3 Service placement

```text
ha-01
  PostgreSQL/Patroni-1 + etcd-1
  HAProxy + PgBouncer
  ChirpStack-1
  Mosquitto-1
  Valkey-1 + Sentinel-1
  OpenBao-1
  Fabric adapter-1 target placement; runtime only after readiness gate

ha-02
  PostgreSQL/Patroni-2 + etcd-2
  HAProxy + PgBouncer
  ChirpStack-2
  Mosquitto-2
  Valkey-2 + Sentinel-2
  OpenBao-2
  Fabric adapter-2 target placement; runtime only after readiness gate

ha-03
  PostgreSQL/Patroni-3 + etcd-3
  HAProxy + PgBouncer
  private internal MQTT route for Node-RED
  Valkey-3 + Sentinel-3
  OpenBao-3
  Node-RED
  Grafana
```

## 2.4 Shared database layout

```text
Patroni PostgreSQL cluster
  |
  +-- chirpstack
  |
  +-- lorawan_telemetry [TimescaleDB enabled]
        +-- telemetry.uplinks hypertable
        +-- telemetry.measurements hypertable
        +-- telemetry.fabric_outbox ordinary table
```

No standalone TimescaleDB container is required.

The TimescaleDB extension **is required**. Install the same pinned extension build on all three PostgreSQL/Patroni members and enable it in `lorawan_telemetry`.

## 2.5 Keep memory intentionally small

The point is to avoid production-sized defaults.

Start PostgreSQL with conservative values such as:

```text
max_connections       40
shared_buffers        128MB
work_mem              2MB
maintenance_work_mem  32MB
```

PgBouncer exists specifically so a tiny PostgreSQL process does not need a large connection budget.

Keep the other POC services at low concurrency and low retention. Do not enable heavy debug logging.

A small host swap file may be used as an emergency cushion for non-OpenBao processes, but sustained swapping means the node is too small and should be resized rather than declared healthy. Because every host runs OpenBao, follow [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md): OpenBao itself must not page secrets into ordinary unencrypted swap.

## 2.6 Storage

Each 2-GiB Basic Droplet includes enough root SSD for this tiny POC and a few sensor records.

Do not add block volumes initially.

The same PostgreSQL replication already carries both databases across three host disks.

For destructive tests, at minimum copy a logical dump/config snapshot to the administration workstation. Production backup design is a later concern.

## 2.7 Ports

Public:

```text
443   ChirpStack through Reserved IPv4 -> current HAProxy owner
8883  gateway MQTT mTLS through Reserved IPv4 -> current HAProxy owner
22    restricted SSH on Droplet management addresses
```

Private:

```text
5432   PostgreSQL
6432   PgBouncer
15432  HAProxy PostgreSQL-primary frontend
6379   Valkey
26379  Sentinel
16379  HAProxy Valkey-primary frontend
2379   etcd client
2380   etcd peer
8008   Patroni
8080   ChirpStack backend
8884   Mosquitto private TLS backend
18883  HAProxy internal MQTT
1880   Node-RED
3000   Grafana
8200   OpenBao API
8201   OpenBao Raft
18200  HAProxy OpenBao KMS
```

## 2.8 POC cost floor

Planning values checked on 2026-08-20:

```text
3 x Basic 1 vCPU / 2 GiB  = $36/month
1 x assigned Reserved IPv4 = $0/month
managed Network LB          = $0/month (not used)
                              ---------
POC infrastructure floor   = $36/month
```

The Reserved IPv4 must remain assigned to one Droplet. Under the current DigitalOcean pricing model, an assigned Reserved IPv4 is free while an unassigned Reserved IPv4 is billable.

Not included:

```text
tax
DNS/domain
LTE plan
backup/object storage
external Fabric infrastructure
```

The old 4/4/8-GiB profile is no longer the default for this POC.

## 2.9 Capacity acceptance

The POC passes sizing only when all three normal-state hosts are healthy, every required deployed feature is running in its documented placement, and each one-host-failure test completes without an OOM kill or sustained swap-bound behavior.

For the **full-feature final PASS**, adapter-1 and adapter-2 must also be deployed from a reviewed implementation and included in the memory/failover evidence. If the adapter implementation is still unavailable, the 2-GiB infrastructure sizing can be measured provisionally, but the overall full-feature POC status remains **BLOCKED**.

Run on each host before and during failure tests:

```bash
free -h
df -h /
uptime
command -v vmstat >/dev/null && vmstat 1 5 || true
docker stats --no-stream
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true
```

`vmstat`/load evidence matters because these are shared-CPU Droplets: a host can miss failover timing because of CPU contention even when it never OOMs. Do not invent a fixed CPU percentage threshold; the decisive result is whether the documented functional failover and recovery checks complete successfully.

If 2 GiB fails, increase memory only as much as needed and record that as the measured POC minimum.

Next: [02a-digitalocean-machine-layout-and-specs.md](02a-digitalocean-machine-layout-and-specs.md).
