# 3. Create the Minimum DigitalOcean HA Foundation

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

## 3.1 Resources to create

```text
1 VPC
3 Droplets
1 DigitalOcean Reserved IPv4
cloud firewalls
DNS records
```

No managed Network Load Balancer, Managed Valkey, Managed PostgreSQL, dedicated role Droplets, or block volumes are required initially.

Create them in this order:

```text
1. VPC
2. ha-01 / ha-02 / ha-03 in that VPC and same datacenter/region
3. record actual VPC IPs, ha-01/ha-02 Droplet IDs, and ha-01/ha-02 anchor IPs
4. cloud firewall rules
5. create one Reserved IPv4 and assign it immediately to ha-01
6. later, after public HAProxy listeners are healthy on both app hosts, prove manual Reserved-IP reassignment
7. enable the etcd-locked automatic failover agent
8. point public DNS at the Reserved IPv4
```

**Why:** the cluster manuals need real private IPs, while the self-managed public-ingress manual needs the Droplet IDs and anchor addresses. The Reserved IP may be created early, but do not enable automatic reassignment until etcd and both HAProxy candidates are healthy.

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

## 3.3 Example private IP plan

The project may keep the existing VPC example `10.60.0.0/20`.

Example assignments:

```text
ha-01  10.60.1.11
ha-02  10.60.1.12
ha-03  10.60.1.13
```

Do not hard-code these example IPs until the provider-assigned VPC addresses are recorded.

Immediately record the real values in the operator worksheet from [02-capacity-cost-and-ip-plan.md](02-capacity-cost-and-ip-plan.md). From each host, verify the intended VPC interface/address is present with:

```bash
ip -br address
ip route
```

**Stop here** if two hosts show duplicate addresses, the expected VPC route is missing, or a service document is still using the example `10.60.1.x` addresses.

## 3.4 One Reserved IPv4 for self-managed public ingress

Create one DigitalOcean Reserved IPv4 and assign it to `ha-01` initially. Do **not** create a managed Network Load Balancer.

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

Follow [03a-self-managed-public-ingress.md](03a-self-managed-public-ingress.md) for the exact anchor-IP, `doctl`, health-check, systemd, manual-move, and automatic-failover procedure.

## 3.5 Firewall model

### Public / Reserved-IP-facing

Allow only what is required:

```text
TCP 22   SSH from approved administration sources
TCP 443  public HTTPS to ha-01/ha-02; HAProxy listens only on each host's anchor IP
TCP 8883 public MQTT TLS to ha-01/ha-02; HAProxy listens only on each host's anchor IP
```

The firewall permits the public service ports on the two app Droplets, but HAProxy must bind those ports to the DigitalOcean **anchor IP**, not `0.0.0.0` and not the normal public Droplet IP. This keeps the Reserved IPv4 as the intended public service address.

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
8884/tcp  HAProxy -> Mosquitto-1/2 private TLS backend
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

Keep the exact allowed source addresses/subnets in the firewall record.

Apply firewall rules in two passes:

1. **before service installation:** SSH from the approved admin CIDR plus VPC east-west traffic needed for bootstrap;
2. **after each service is installed:** narrow its source rule to the exact consumers listed above and verify the port is not reachable from an unapproved source.

After every firewall edit, keep the existing SSH session open and test a second SSH session before closing the first. This prevents a typo from becoming an avoidable lockout.

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

The MQTT server certificate must be valid for `mqtt.<DOMAIN>` and the broker must validate the gateway client certificate.

Internal etcd certificates use private host identities according to [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md). For the local HAProxy service aliases used by containerized ChirpStack, include these logical names in the corresponding backend server certificates:

```text
pgbouncer.internal.<DOMAIN>    -> SAN on the PgBouncer certificates on ha-01, ha-02, and ha-03
postgres-ha.internal.<DOMAIN>  -> SAN on every PostgreSQL member certificate
valkey-ha.internal.<DOMAIN>    -> SAN on every Valkey server certificate
mqtt-ha.internal.<DOMAIN>      -> SAN on both Mosquitto server certificates
openbao-kms.internal.<DOMAIN>  -> SAN on all three OpenBao server certificates
```

Inside ChirpStack-1 and ChirpStack-2, map `pgbouncer.internal.<DOMAIN>`, `valkey-ha.internal.<DOMAIN>`, and `mqtt-ha.internal.<DOMAIN>` to that app host's private VPC IP. On `ha-03`, map `pgbouncer.internal.<DOMAIN>` and `mqtt-ha.internal.<DOMAIN>` to the `ha-03` private VPC IP so Node-RED uses the local HAProxy MQTT route and Node-RED/Grafana use local PgBouncer. Each PgBouncer maps/uses `postgres-ha.internal.<DOMAIN>` for its local HAProxy backend. Fabric adapter-1 and adapter-2 use `openbao-kms.internal.<DOMAIN>:18200`, mapped to that adapter host's local HAProxy frontend, which reaches the three OpenBao nodes over private TLS. This keeps stable names while PgBouncer, HAProxy, Patroni, Sentinel, MQTT routing, or the OpenBao active node changes.

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

Continue with [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md), then [06-etcd-cluster.md](06-etcd-cluster.md).