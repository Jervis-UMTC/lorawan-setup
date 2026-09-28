# Runtime and Cloud Platform — Operator Manual

## What this technology does

This layer is the host/runtime substrate underneath the commissioned cloud stack: Ubuntu Server 24.04 LTS, three DigitalOcean Droplets in one private VPC, Docker Engine/Compose, host filesystems, HAProxy/host networking, firewall controls, and the Reserved IPv4 ingress architecture.

It is not a substitute for component-specific HA logic. A healthy Docker daemon does not prove PostgreSQL quorum, ChirpStack health, OpenBao quorum, or Fabric readiness.

## Current commissioned host shape

```text
ULC-01 / 10.104.0.2
  core HA services
  ChirpStack-1 / Mosquitto-1
  evidence ingest-1 / collector-1
  Fabric adapter-1 ENABLED

ULC-02 / 10.104.0.4
  core HA services
  ChirpStack-2 / Mosquitto-2
  Node-RED standby
  evidence ingest-2 / verifier-1
  Fabric adapter-2 DISABLED

ULC-03 / 10.104.0.8
  core HA services
  Node-RED active
  Grafana
  evidence collector-2 / verifier-2
```

The POC uses three separate hosts because quorum-based services must survive one host loss. All three remain in the same DigitalOcean data center; this is host HA, not region/availability-zone DR.

## Public/private network rule

- private east-west service traffic uses the DigitalOcean VPC;
- database, consensus, KMS, evidence object storage, and internal service paths stay on private/loopback listeners as documented;
- the public Reserved IPv4 normal path is commissioned;
- provider-side Reserved IPv4 reassignment/failover acceptance remains a distinct externally managed gate.

Do not open a private service publicly merely to simplify troubleshooting.

## Step 1 — Verify host identity and OS

Run on each ULC host:

```bash
printf 'HOST=%s\n' "$(hostname -s)"
. /etc/os-release
printf 'OS=%s VERSION=%s CODENAME=%s ARCH=%s\n'   "$ID" "$VERSION_ID" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" "$(dpkg --print-architecture)"
ip -br addr
ip route
```

**PASS means:** the host is the intended Ubuntu 24.04 LTS amd64 member and its private VPC identity matches the expected ULC node.

Do not silently replace one member with a different Ubuntu release or architecture.

## Step 2 — Check basic host health before touching containers

```bash
uptime
free -h
df -hT
df -ih
sudo systemctl --failed
sudo journalctl -p err..alert --since=-30min --no-pager | tail -n 120
```

**PASS means:** no unexpected failed unit, OOM/disk/inode emergency, or recent host-level critical error explains the application symptom.

A one-off application failure is not a reason to reboot the server.

## Step 3 — Check Docker/Compose runtime

```bash
sudo systemctl is-active docker
sudo docker version
sudo docker compose version
sudo docker info --format 'server={{.ServerVersion}} driver={{.Driver}} cgroup={{.CgroupVersion}} logging={{.LoggingDriver}}'

sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
sudo docker ps -a --filter status=exited --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
```

**PASS means:** Docker is active, Compose works, intended workloads are running, and there is no unexplained exited/restart-loop container.

Do not prune images, volumes, or build cache until you have identified which artifacts are rollback/recovery assets.

## Step 4 — Check listener exposure

```bash
sudo ss -lntup
```

Compare listeners with the component manuals. In particular:

- PostgreSQL/etcd/OpenBao/private routing must not become wildcard-public accidentally;
- evidence raw S3 remains loopback-only;
- evidence health ports remain loopback/private;
- only approved public ingress listeners are externally exposed.

If a Docker-published port is unexpectedly public, fix the bind/publish configuration; do not rely only on UFW.

## Step 5 — Check firewall state without rewriting it

```bash
sudo ufw status verbose
sudo nft list ruleset 2>/dev/null | sed -n '1,220p'
```

Current hosts have narrow rules needed for local Docker-bridge-to-host service paths. Preserve the commissioned allowances while investigating.

The DigitalOcean provider Cloud Firewall is externally managed and cannot be proven from a local `ufw` listing alone.

## Step 6 — Check private east-west reachability

From each host, test only endpoints relevant to the symptom. For basic VPC reachability:

```bash
for ip in 10.104.0.2 10.104.0.4 10.104.0.8; do
  printf '%s ' "$ip"
  timeout 2 bash -c "cat < /dev/null > /dev/tcp/$ip/22" 2>/dev/null     && echo TCP22_OK || echo TCP22_FAIL
done
```

Use component-specific protocol checks after TCP reachability. Do not infer service health from ping alone.

## Step 7 — Check persistent storage before container recreation

```bash
sudo find /srv -maxdepth 2 -mindepth 1 -type d   -printf '%M %u:%g %p\n' 2>/dev/null | sort | head -n 200

sudo docker inspect $(sudo docker ps -q)   --format '{{.Name}} -> {{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}'   2>/dev/null | sort
```

Before recreating a stateful service, identify its persistent host paths and backup/recovery procedure.

Container recreation is safe only when persistent state and protected configuration are deliberately preserved.

## Step 8 — Check runtime resource pressure

```bash
sudo docker stats --no-stream  --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.PIDs}}'
```

Use measured pressure to decide whether a service is undersized. Do not remove HA replicas or security limits simply to make a 2-GiB host look quiet.

## Safe package/runtime change procedure

1. Prove the actual failing layer first.
2. Identify the exact package/runtime/service to change.
3. Record current package and image versions.
4. Preserve stateful data and rollback material.
5. Change one host or one service candidate at a time.
6. Keep quorum/active-passive ownership intact.
7. Validate configuration before restart/recreate.
8. Restart only the affected component.
9. Verify the service-specific health check.
10. Verify one representative real operation if the change affects data flow.

Do not perform a three-host package upgrade or Docker restart simultaneously.

## Docker image rule

Commissioned workloads should use immutable image digests where the deployment bundle provides them. For an image replacement, record:

```bash
sudo docker inspect <CONTAINER>   --format 'image_id={{.Image}} image_ref={{.Config.Image}}'
```

Do not substitute a mutable `:latest` tag during recovery.

## Backup/recovery boundary

The runtime layer must preserve component-specific recovery assets rather than treating `/var/lib/docker` as the backup.

Examples include PostgreSQL recovery material, OpenBao Raft snapshot/recovery material, SeaweedFS raw objects and metadata recovery, Node-RED/Grafana configuration and persistent data, protected PKI/service env files, exact image/release references, and research evidence archives.

Never delete Docker volumes or `/srv` trees as a generic “clean start.”

## Host-loss rule

When one ULC host fails:

1. Identify which quorum members/active services were on that host.
2. Verify surviving quorum/leader state.
3. Fence any active/passive writer before promotion.
4. Keep clients on stable logical endpoints.
5. Repair/rebuild the lost host from repository + protected configuration + recovery material.
6. Rejoin/reintroduce one component at a time.

A host rebuild must not require editing every client to a new hard-coded IP.

## Troubleshooting map

| Symptom | First check |
|---|---|
| many services fail at once | host resources, Docker, storage, VPC, DNS/time |
| one container exits | its config/dependencies/logs, not host reboot |
| private service unreachable | bind/listener -> firewall -> route -> dependency |
| public path fails but private is healthy | HAProxy/Reserved IPv4/provider boundary |
| disk nearly full | identify owning service/data class before cleanup |
| OOM/restarts | measured container/host memory and limits |
| after recreate data vanished | wrong/missing persistent mount; stop further mutation |
| inconsistent behavior between hosts | image/config/version drift |

## Completion checklist

- all three hosts identify as the intended Ubuntu 24.04 members;
- no unexpected failed systemd units exist;
- Docker and Compose are healthy;
- no unexplained exited/restarting containers exist;
- disk/inode/memory headroom is acceptable;
- listener exposure matches component manuals;
- private VPC reachability is intact;
- protected persistent paths are known before any recreate;
- provider Reserved-IP failover is not falsely claimed from local host health.

## Complete cloud-runtime operations companion

Use [ULC cloud bootstrap, host/network/runtime operations and recovery](ULC-CLOUD-RUNTIME-OPERATIONS-RECOVERY.md) for the commissioned three-host substrate, DigitalOcean/VPC boundaries, container-runtime recovery and host-loss procedure.

## Detailed references

- [`../server/cloud-production/01-architecture-decisions-and-scope.md`](../server/cloud-production/01-architecture-decisions-and-scope.md)
- [`../server/cloud-production/02a-digitalocean-machine-layout-and-specs.md`](../server/cloud-production/02a-digitalocean-machine-layout-and-specs.md)
- [`../server/cloud-production/03-digitalocean-vpc-droplets-and-firewalls.md`](../server/cloud-production/03-digitalocean-vpc-droplets-and-firewalls.md)
- [`../server/cloud-production/04-host-hardening-dns-pki-and-secrets.md`](../server/cloud-production/04-host-hardening-dns-pki-and-secrets.md)
