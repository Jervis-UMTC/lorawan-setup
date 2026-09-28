# ULC Cloud Runtime — Bootstrap, Network, Host Operations and Recovery

This chapter expands [technology guide 16](16-runtime-and-cloud-platform.md). It describes the **actual** Ubuntu/DigitalOcean/Docker substrate of this project, not a hypothetical cloud architecture. Host installation, package versions, service roles, private IPs and ingress assignments must be rechecked against live machines before applying a change. A docs audit is not a fresh host/HA acceptance.

## 1. Understand the three failure domains

| Host | Historical commissioned VPC IP | Primary roles |
|---|---|---|
| ULC-01 | 10.104.0.2 | ChirpStack-1, cloud broker-1, ingest-1, collector-1, **enabled** Fabric writer, etcd/Patroni/Valkey/OpenBao/SeaweedFS |
| ULC-02 | 10.104.0.4 | ChirpStack-2, cloud broker-2, ingest-2, verifier-1, **disabled** Fabric standby, stopped Node-RED B, HA members |
| ULC-03 | 10.104.0.8 | **active** Node-RED A, Grafana, collector-2, verifier-2, HA members |

Original host floor: Ubuntu Server 24.04 LTS x64, each 1 vCPU / 2 GiB RAM / 50 GiB SSD, all three in one DigitalOcean data center. This survives an appropriately engineered **one-host** failure; it does not prove cross-region DR or prove that 2 GiB remains adequate at a higher sensor rate. Re-measure memory and disk before adding workloads. The current Fabric HRC servers and physical Gateway-01 are separate machines, not fourth/fifth ULC members.

Service topology:
- etcd **Patroni DCS**: 3 voters private HTTP 2379/2380;
- PostgreSQL/Patroni: 1 elected primary plus 2 replicas;
- Valkey: 1 elected primary plus 2 replicas; Sentinel 3 quorum;
- OpenBao: 3 Raft voters;
- SeaweedFS: independent **metadata-etcd** 12379/12380, three storage hosts;
- Mosquitto: preferred/backup **without replicated MQTT sessions**;
- ChirpStack: 2 application instances;
- Node-RED: **one active writer**, fenced other candidate;
- Fabric adapter: **one enabled external writer** until separate fencing acceptance;
- Grafana: single read-only observer.

A Docker green status cannot replace each technology's application and data-path checks.

## 2. Public, private and management networking

~~~text
Gateway LTE -> public FQDN/Reserved IPv4 :8883
            -> current approved HAProxy ingress owner
            -> cloud MQTT :8884 (private)
Gateway evidence uploader -> public HTTPS :443 -> approved ingest backend

East/west:
  ULC VPC 10.104.0.0/20:
  PgBouncer :6432 -> local HAProxy :15432 -> elected Patroni :5432
  ChirpStack local MQTT :18883 -> cloud brokers :8885
  Node-RED local MQTT :18884 -> cloud brokers :8886
  Fabric adapter local KMS :18200 -> OpenBao :8200
  S3 evidence :18443 -> loopback raw S3 :18333
  HRC Fabric peer gateway 10.104.0.7:7051 (peer1.hrc.local)
~~~

Do **not** confuse the public Reserved-IP owner, VPC service listener and Gateway-01's management Ethernet. The provider Reserved IPv4 reassignment authority/control is a **separate gate**; local HAProxy service health does not prove that DigitalOcean will transfer the Reserved IP automatically. Current tracked gateway overlay does **not** guarantee automatic Wi-Fi fallback; production sensor data is intended to use SIM7600 LTE, not management LAN.

## 3. First-time host preparation: what to establish

On a *new, authorized* host, not an already commissioned member:

1. Provision the **approved Ubuntu 24.04 amd64 release**, proper host name, expected capacity and private NIC in the intended VPC/datacenter; record provider Droplet identity and current public/private IPs in the protected inventory.
2. Configure the approved operator account, restricted SSH keys, audited sudo, clock synchronization, DNS/hosts and the cloud firewall. Keep the provider access path available during any host firewall change. Avoid repeating bootstrap root passwords in scripts/docs.
3. Install approved exact Docker Engine/Compose versions from the reviewed package source, ensure persistent Docker daemon startup and verify nonprivileged service users/groups **before** setting volume ownership.
4. Reproduce the documented filesystem structure, protected env/PKI and the immutable image release set. Do not equate an empty `/srv` tree with the ability to restore PostgreSQL, OpenBao and SeaweedFS.
5. Configure host HAProxy/systemd routing and private-firewall boundaries **without opening** etcd, DB, Valkey, object-store raw S3, OpenBao or health/admin ports publicly.
6. Join/recover each stateful component using its **existing-cluster** join/restore procedure if there is surviving state; never form an independent second quorum. Rejoin one component at a time, preserving active-writer fencing.
7. Validate health of every component at its intended interface, then one representative real end-to-end observation. Only perform disruptive failover after a material change to failover behavior or under a separate commissioned acceptance plan.

For an existing host, **do not execute this installation checklist as a generic “reset”**. Inspect first and repair the earliest failing layer. A major OS/daemon upgrade or a new replacement node needs a consistent rollback/backup plan.

## 4. Safe read-only host command block (Ubuntu Bash, EACH ULC)

~~~bash
printf 'HOST=%s\n' "$(hostname -s)"
. /etc/os-release
printf 'OS=%s VERSION=%s ARCH=%s\n' "$ID" "$VERSION_ID" "$(dpkg --print-architecture)"
date -u
ip -4 -br address
ip route
uptime
free -h
df -hT
df -ih
sudo systemctl --failed
sudo systemctl is-active docker
sudo docker version
sudo docker compose version
sudo docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
sudo ss -lntup
~~~

**PASS:** intended host/VPC address, correct pinned OS, no unexpected critical service failure, disk/inode/memory headroom, Docker/Compose functional, no production-private interface on wildcard-public bind. Inspect current published Docker ports separately; a port map can expose a service even when the application listens on a container-local address. These commands reveal runtime and inventory, **not** that a quorum or radio link is healthy.

For a single suspected service, use bounded logs, for example `sudo journalctl -u haproxy --since=-15min --no-pager -n 100` or `sudo docker logs --since=15m --tail=120 <ACTUAL_CONTAINER>` after discovering its real owner. Do not dump giant logs or use `docker system prune --volumes` as a “cleanup”.

## 5. Security/firewall and network troubleshooting

~~~bash
sudo ufw status verbose
sudo nft list ruleset 2>/dev/null | sed -n '1,180p'
sudo ss -lntp
getent ahostsv4 pgbouncer.internal.lorawan.com
getent ahostsv4 mqtt.internal.lorawan.com
~~~

The DigitalOcean **Cloud Firewall** cannot be confirmed by `ufw status` alone. Inspect the provider configuration through approved access and match VPC source/destination policy with the host bind and Docker-published ports. A reachable port does **not** establish mutual TLS, SCRAM, ACL or application readiness. For HAProxy, preserve every pre-existing frontend, including SQL/MQTT/OpenBao/evidence ingress; validate full candidate with `haproxy -c -f /etc/haproxy/haproxy.cfg` before a necessary reload.

A failure on **every** host suggests shared DNS/clock, cloud route, provider issue or dependency/quorum, not coincidentally three bad containers. A failure on one host suggests image/config divergence, bind, disk/permissions or host route first.

## 6. Backup and replacement hard stops

Capture an inventory of active containers with image IDs/digests, actual Compose projects and protected mounts, systemd units, listening sockets and their firewall class, VPC addresses, DNS/FQDN mapping, external Reserved IPv4 owner and off-host backup references. Preserve separately:
- Patroni/PostgreSQL both DBs, roles, schema/Timescale compatibility and WAL;
- etcd Patroni DCS **and separate** Seaweed metadata-etcd snapshots;
- Seaweed raw evidence objects, OpenBao Raft/recovery material, exact KMS/key/identity custody;
- protected PKI/CA leaf chains, gateway journal + cloud checkpoint, Fabric prepared outbox and external HRC ledger reconciliation;
- Node-RED sole-writer bundles, Grafana state, immutably sealed `chapter4-results`.

**HA replication is not backup**, and placing three nodes in one datacenter is not off-site disaster recovery. Restore externally consistent SQL, raw evidence, gateway checkpoint and committed HRC state before restarting external writers. Do not restore an older single volume under newer authoritative identity/ledger state without a recovery plan.

## 7. When the component is accepted

Three intended Ubuntu nodes and private routes present; named listeners scoped; major quorums agree on elected roles; two-node ChirpStack normal path available; one active Node-RED writer and one enabled Fabric writer; actual object-store/PKI dependencies healthy; one *real* RF event traceable to SQL, independent verifier and eligible Fabric result when that boundary is under test. Record which layers were **not** tested and their dated status. A public IPv4 failover requires separate provider-side reassignment proof, not inferred from a working HAProxy process.

Source runbooks: [cloud machine inventory](../server/cloud-production/02a-digitalocean-machine-layout-and-specs.md), [VPC/firewalls](../server/cloud-production/03-digitalocean-vpc-droplets-and-firewalls.md), [host security](../server/cloud-production/04-host-hardening-dns-pki-and-secrets.md), [backup/DR](../server/cloud-production/13-backup-restore-and-disaster-recovery.md).
