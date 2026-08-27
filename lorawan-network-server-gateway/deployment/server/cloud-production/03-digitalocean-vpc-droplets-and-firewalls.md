# 3. Create the Minimum DigitalOcean HA Foundation

> **Evidence boundary:** the three active Droplets and their host-observed `10.104.0.0/20` east-west path are evidenced in the live build log. The current operator is not authorized to modify or verify the DigitalOcean Cloud Firewall. This repository also does not currently contain execution evidence that the Reserved IPv4 or public DNS has been commissioned. Provider-side items below are therefore target/handoff guidance until the account owner confirms them.

This guide creates the **three-Droplet minimum HA test environment** defined in [02a-digitalocean-machine-layout-and-specs.md](02a-digitalocean-machine-layout-and-specs.md).

Run provider-console/API actions from the administration workstation. Run Linux commands only after SSHing to the named Droplet. Do not paste secrets into this Markdown or a shared terminal transcript.

Before provisioning, fill this non-secret worksheet:

```text
DigitalOcean region:
Host OS image/release: Ubuntu Server 24.04 LTS x64
DigitalOcean image slug: ubuntu-24-04-x64
VPC CIDR:
SSH public-key fingerprint:
Administrator source CIDR:
DOMAIN:
chirpstack.<DOMAIN>:
mqtt.<DOMAIN>:
ha-01 planned name:
ha-02 planned name:
ha-03 planned name:
```

**Stop here. Do not create resources** while the region, VPC CIDR, administrator source, or domain ownership is uncertain. Changing these after quorum services are built creates avoidable rework.

## 3.1 Foundation state and remaining provider-owned resources

The host-side foundation already evidenced by this build is:

```text
3 active Ubuntu 24.04 LTS Droplets
ulc-01 / ha-01
ulc-02 / ha-02
replacement ulc-03 / ha-03
host-observed east-west network on eth1
```

The intended full provider-side target also includes:

```text
1 DigitalOcean Reserved IPv4
provider cloud-firewall policy
public DNS records
```

Those provider-side items are **not claimed as completed here**. The DigitalOcean Cloud Firewall is controlled by the account owner/boss, and the current operator must not change it. Reserved-IP and public-DNS commissioning belongs to the later public-ingress phase unless the provider owner supplies evidence that it already exists.

No managed Network Load Balancer, Managed Valkey, Managed PostgreSQL, dedicated role Droplets, or block volumes are required initially.

**Why:** separating host evidence from provider-control-plane assumptions prevents the manual from reporting a firewall, Reserved IP, DNS record, or provider VPC object that the current operator has not actually verified.

## 3.2 Droplets

Create:

```text
ha-01
  Ubuntu Server 24.04 LTS x64
  image slug: ubuntu-24-04-x64
  Basic 1 vCPU / 2 GiB / 50 GiB

ha-02
  Ubuntu Server 24.04 LTS x64
  image slug: ubuntu-24-04-x64
  Basic 1 vCPU / 2 GiB / 50 GiB

ha-03
  Ubuntu Server 24.04 LTS x64
  image slug: ubuntu-24-04-x64
  Basic 1 vCPU / 2 GiB / 50 GiB
```

Choose **OS -> Ubuntu 24.04 (LTS) x64**, image slug `ubuntu-24-04-x64`, not a Docker/Marketplace/1-Click image. We want the same plain host baseline on every quorum member and will install/pin Docker and the application stack ourselves. Do not select Ubuntu 22.04 or 26.04 for only one node; mixed OS releases create unnecessary package/runtime drift.

Before creating the Droplets, resolve and record the public image metadata from the current DigitalOcean catalog:

```bash
doctl compute image get ubuntu-24-04-x64 \
  --format ID,Name,Distribution,Slug,Created \
  --no-header
```

Record the numeric image ID and `Created` value in the worksheet. **Why:** `ubuntu-24-04-x64` is the stable selection name used by these manuals, while the numeric ID proves which provider image build was actually selected for this commissioning run. Do not copy a historical numeric image ID from documentation; resolve it at provisioning time.

Put all three in the same DigitalOcean VPC and region.

Create one host, record its actual size and addresses, then create the next. After all three exist, verify the provider shows exactly the intended three hosts before installing quorum services.

Use tags such as:

```text
lorawan-ha
lorawan-test
```

Record the exact Droplet size slugs from the control panel/API at creation time instead of copying a historical slug blindly.

## 3.3 Operationally validated east-west IP plan

The current active hosts were validated from Linux itself on `eth1`:

```text
ulc-01 / ha-01  10.104.0.2/20
ulc-02 / ha-02  10.104.0.4/20
ulc-03 / ha-03  10.104.0.8/20
```

Cross-node ICMP succeeded and TCP `2380` was proven between hosts before etcd bootstrap. These are therefore the operational HA/east-west addresses used by the current build. The old `10.60.x.x` values were design examples only and are removed so they cannot be copied into live service configuration.

The provider control-plane object itself has **not** been independently inspected by the current operator. Do not turn the host-observed result into a claim about DigitalOcean console state. Record any future provider confirmation separately.

Verify the host view with:

```bash
ip -br address
ip route
```

**Stop here** if a rebuilt host does not have its documented `10.104.0.x/20` address, the route disappears, or cross-node reachability no longer matches the execution log.

## 3.4 One Reserved IPv4 for self-managed public ingress

**STANDBY / provider-owned step:** the target design uses one DigitalOcean Reserved IPv4 assigned to `ha-01` initially, with no managed Network Load Balancer. The current repository does not contain execution evidence that this Reserved IPv4 has been commissioned, so do not mark it complete until the provider owner/current authorized operator supplies that evidence.

The public shape is:

```text
chirpstack.<DOMAIN> ----+
                       +--> Reserved IPv4
mqtt.<DOMAIN> ----------+        |
                                 v
                        ha-01 OR ha-02
                         anchor-address
                            HAProxy
                         /         \
                     :443         :8883
                 ChirpStack       MQTT TLS pass-through
```

The address is active/passive and belongs to one Droplet at a time. Automatic movement is implemented by the failover agent on `ha-01/02`, using an etcd distributed lock plus the DigitalOcean Reserved-IP API.

Do not point DNS at a normal Droplet public IPv4. Both public DNS names point to the Reserved IPv4.

The Reserved-IP failover design is parked in [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md). It is **standby** until the application/MQTT paths and provider-side prerequisites are ready; do not execute it during the foundation or etcd phase.

## 3.5 Target firewall model - provider-owner handoff

The DigitalOcean Cloud Firewall state is currently **unknown to this operator and externally managed**. The rules below describe the intended least-privilege policy for the provider-account owner; they are not instructions for the current operator to modify the cloud firewall.

### Public / Reserved-IP-facing

When the provider-owned firewall phase becomes active, allow only what is required:

```text
TCP 22   SSH from approved administration sources
TCP 443  public HTTPS to ha-01/ha-02; HAProxy listens only on each host's anchor IP
TCP 8883 public MQTT TLS to ha-01/ha-02; HAProxy listens only on each host's anchor IP
```

If the provider owner enables these rules later, HAProxy must still bind the public service ports to the DigitalOcean **anchor IP**, not `0.0.0.0` and not the normal public Droplet IP. The firewall policy and the application bind policy are separate controls; neither should be assumed from the other.

Do not expose directly:

```text
1883 MQTT plaintext
5432 PostgreSQL
6379 Valkey
26379 Valkey Sentinel
2379 etcd client
2380 etcd peer
8008 Patroni REST
8080 ChirpStack backend
8884 Mosquitto private TLS backend
1880 Node-RED
3000 Grafana
8200 OpenBao API private TLS
8201 OpenBao Raft/cluster traffic
18200 HAProxy stable OpenBao KMS frontend
```

### Private VPC rules

Allow only between the hosts/services that need them:

```text
2379/tcp  etcd client traffic from Patroni/admin nodes
2380/tcp  etcd peer traffic ha-01 <-> ha-02 <-> ha-03
5432/tcp  PostgreSQL replication and HAProxy DB routing
8008/tcp  Patroni health checks
6379/tcp  Valkey data/replication traffic
26379/tcp Sentinel communication
8883/tcp  Reserved-IP public path -> anchor HAProxy MQTT frontend on ha-01/ha-02
8884/tcp  existing gateway-facing HAProxy -> Mosquitto-1/2 private TLS backend
8886/tcp  ulc-03 Node-RED HAProxy -> Mosquitto-1/2 dedicated mTLS backend
8080/tcp  HAProxy -> ChirpStack backends
6432/tcp  local approved DB clients -> PgBouncer frontend
15432/tcp PgBouncer -> local HAProxy PostgreSQL-primary frontend
15433/tcp approved admin/monitor -> HAProxy PostgreSQL-replica test frontend
16379/tcp local app-container -> HAProxy Valkey-primary frontend
18883/tcp local app-container -> HAProxy internal MQTT frontend
8200/tcp  Fabric adapters/approved admins -> OpenBao API backends
8201/tcp  OpenBao-1 <-> OpenBao-2 <-> OpenBao-3 Raft/cluster traffic
18200/tcp Fabric adapter -> local HAProxy OpenBao KMS frontend
<FABRIC_GATEWAY_PORT>/tcp outbound from Fabric adapter-1/2 to the external Fabric Gateway only
```

Keep the exact allowed source addresses/subnets in the provider-owner firewall record when that information becomes available.

Provider-owner handoff sequence:

1. confirm the actual DigitalOcean VPC/firewall objects and current rules in the provider control plane;
2. preserve the currently working SSH path before any restriction is applied;
3. add only the rules required by services that are actually deployed;
4. verify each permitted path and an unapproved-source rejection;
5. record the result in `00-build-execution-log.md` rather than assuming it succeeded.

The current operator does not perform these provider-side edits.

## 3.6 Service placement reminder

```text
ha-01
  etcd-1
  PostgreSQL/Patroni-1
  HAProxy
  PgBouncer
  ChirpStack-1
  Mosquitto-1
  Valkey-1 + Sentinel-1
  OpenBao-1
  Fabric adapter-1

ha-02
  etcd-2
  PostgreSQL/Patroni-2
  HAProxy
  PgBouncer
  ChirpStack-2
  Mosquitto-2
  Valkey-2 + Sentinel-2
  OpenBao-2
  Fabric adapter-2

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

Telemetry and `fabric_outbox` live in `lorawan_telemetry` on the Patroni PostgreSQL cluster. TimescaleDB is enabled there as an extension on the same three PostgreSQL members; no separate TimescaleDB server or public port is added.

## 3.7 Storage

Use the included SSDs first.

For the test workload, PostgreSQL HA already keeps database copies on three different Droplet root disks. Do not buy three block volumes merely to say storage is separate.

Required safeguards:

```text
bounded Docker logs
disk-free monitoring
logical dumps of `chirpstack` and `lorawan_telemetry` copied off the target Droplets before destructive tests
configuration exports
OpenBao recovery/snapshot evidence appropriate to the POC
```

A block volume can be added later if measured data growth or disk pressure requires it.

## 3.8 Initial host verification

On each Droplet:

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

Expected baseline:

```text
all hosts: Ubuntu 24.04 LTS (noble), x86_64/amd64
ha-01: 1 vCPU, about 2 GiB RAM, about 50 GiB root SSD
ha-02: 1 vCPU, about 2 GiB RAM, about 50 GiB root SSD
ha-03: 1 vCPU, about 2 GiB RAM, about 50 GiB root SSD
```

Stop if one host was accidentally created from a different OS image. Rebuild it before quorum bootstrap rather than carrying a mixed host baseline into Patroni/etcd/OpenBao troubleshooting.

Do not begin quorum bootstrap if hostname, private IP, DNS, or time configuration is uncertain.

## 3.9 DNS and certificates

Public certificate names:

```text
chirpstack.<DOMAIN>
mqtt.<DOMAIN>
```

Certificate names must match what clients actually verify. Later execution refined several placeholders from this early infrastructure design. The commissioned identities currently relevant to ChirpStack are:

```text
pgbouncer.internal.lorawan.com -> PgBouncer certificates on all three nodes
postgres-ha.internal           -> PostgreSQL member certificates used behind PgBouncer/HAProxy
valkey.internal.lorawan.com    -> every commissioned Valkey server certificate
mqtt.internal.lorawan.com      -> commissioned Mosquitto broker certificates
openbao-kms.internal.lorawan.com  -> future OpenBao service identity
```

For containerized ChirpStack, map `pgbouncer.internal.lorawan.com` and `valkey.internal.lorawan.com` to that application host's private VPC IP so the local PgBouncer/HAProxy paths are used. The old `mqtt-ha.internal.<DOMAIN>:18883` local-per-host target was never commissioned. Phase 9 instead closed ChirpStack MQTT redundancy with `mqtt.internal.lorawan.com:18883` mapped locally on `ulc-01/02` to HAProxy `:18883 -> Mosquitto :8885`. Phase 12A separately adds Node-RED on `ulc-03` using `mqtt.internal.lorawan.com:18884 -> HAProxy -> Mosquitto :8886` dedicated mTLS backends. Phase 10 public MQTT keeps TLS pass-through and therefore reissues broker certificates to retain `mqtt.internal.lorawan.com` while adding the real public `mqtt.<DOMAIN>` SAN. Each PgBouncer maps/uses `postgres-ha.internal` for its local HAProxy backend. Future Fabric adapters use `openbao-kms.internal.lorawan.com:18200` only after that service is commissioned.

## 3.10 Why not two Droplets?

With two etcd voters:

```text
normal: 2/2
lose one host: 1/2
majority required: 2
result: no safe quorum
```

With three:

```text
normal: 3/3
lose one host: 2/3
majority required: 2
result: quorum survives
```

That is the reason three machines are the absolute minimum for this HA test. It is not an arbitrary architecture preference.

Continue with [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md), then [05-etcd-cluster.md](05-etcd-cluster.md).