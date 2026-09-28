# etcd — Three-Member Commissioned Installation and Recovery

**Audience:** engineer reproducing or repairing the actual HA coordination service, not the minimal dissertation VM. This expands [etcd operator guide 06](06-etcd.md). Commissioned observations are dated: verify live service, host identities, cluster membership and current backup before action. This document is not a new failover/recovery test.

## 1. Purpose and dependency

Patroni stores its DCS/leader-election state in etcd, **not sensor readings or the SQL database**. The three-member Raft cluster needs **two of three** voting members for quorum. Keeping all three healthy before maintenance permits one member to fail; it does not authorize simultaneously stopping two. PostgreSQL can still have running processes even if Patroni cannot safely elect a writer.

| Server | etcd name | Private IP | client / peer |
|---|---|---|---|
| ULC-01 | etcd-01 | 10.104.0.2 | 2379 / 2380 |
| ULC-02 | etcd-02 | 10.104.0.4 | 2379 / 2380 |
| ULC-03 | etcd-03 | 10.104.0.8 | 2379 / 2380 |

**Important:** the commissioned etcd is `quay.io/coreos/etcd:v3.5.15` under Docker Compose with `network_mode: host` and **private-network HTTP**, not a TLS-enabled etcd deployment. External firewall/host restrictions must keep its API and peer ports private. Never add untested TLS flags to documentation or expose `0.0.0.0:2379` to compensate for a failed peer route. The additional `10.15.0.x` NIC addresses were not the validated HA network.

## 2. Check existing infrastructure before reinstalling

On **each Ubuntu ULC host**:

~~~bash
hostname -f
date -u
ip -4 -br address
df -h /opt/lorawan/etcd
cd /opt/lorawan/etcd
sudo docker compose ps
sudo ss -lntp | grep -E ':(2379|2380)\b' || true
~~~

On an intended running member, run these read-only checks:

~~~bash
sudo docker exec etcd etcdctl --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 endpoint health
sudo docker exec etcd etcdctl --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 endpoint status --write-out=table
sudo docker exec etcd etcdctl --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 member list --write-out=table
~~~

**PASS:** 3/3 endpoints in normal conditions, exactly one Raft leader, intended peer URLs, no stale unexpected member or learner, no restart loops. For a recognized single-node outage 2/3 can still form quorum; restore 3/3 before further maintenance. The leader need not match an old screenshot.

## 3. First-time installation only — distinguish bootstrap from replacement

**Hard stop:** if any member data directory contains existing `member/`, **this is not a first bootstrap**. Do not run a fresh bootstrap recipe or delete files. First record membership and use the approved one-member replacement or full-cluster DR plan. Back up existing `/opt/lorawan/etcd` and verify retention before any destructive action.

### 3.1 Network and prerequisites

On all three hosts confirm their correct `eth1` private addresses, each pair's peer TCP reachability on `2380`, and client `2379` address. Confirm Docker Engine/Compose, healthy time synchronization, adequate storage and firewall rules. A local address alone is not proof that the other two can reach it. Choose the three member identities once; a name is not interchangeable after the Raft cluster is initialized.

### 3.2 Directories and Compose

For a fresh, confirmed-empty member, prepare this layout:

~~~text
/opt/lorawan/etcd/
  docker-compose.yml
  config/etcd.yml
  data/              (mode 0700; persistent)
~~~

Use the actual approved operator/group on the replacement host. The commissioning runbook's tested new-build example for the project operator is:

~~~bash
sudo install -d -m 755 -o opsadmin -g opsadmin /opt/lorawan/etcd
sudo install -d -m 755 -o opsadmin -g opsadmin /opt/lorawan/etcd/config
sudo install -d -m 700 -o opsadmin -g opsadmin /opt/lorawan/etcd/data
stat -c '%a %U:%G %n' /opt/lorawan/etcd/data
~~~

**Do not re-chown a healthy volume from its runtime user to these example IDs.** Inspect live ownership and `docker inspect etcd` first if this is a recovery.

The approved Compose definition for each host:

~~~yaml
services:
  etcd:
    image: quay.io/coreos/etcd:v3.5.15
    container_name: etcd
    restart: unless-stopped
    network_mode: host
    command:
      - /usr/local/bin/etcd
      - --config-file=/etc/etcd/etcd.yml
    volumes:
      - /opt/lorawan/etcd/config/etcd.yml:/etc/etcd/etcd.yml:ro
      - /opt/lorawan/etcd/data:/etcd-data
~~~

### 3.3 Configuring each node without rewriting existing Raft state

Use the following **initial-bootstrap-only template**, changing the three host-specific values according to the table. Put it at `/opt/lorawan/etcd/config/etcd.yml` on a verified new/empty member:

~~~yaml
name: etcd-01
data-dir: /etcd-data
initial-cluster: etcd-01=http://10.104.0.2:2380,etcd-02=http://10.104.0.4:2380,etcd-03=http://10.104.0.8:2380
initial-cluster-state: new
initial-cluster-token: lorawan-etcd-cluster
listen-peer-urls: http://10.104.0.2:2380
initial-advertise-peer-urls: http://10.104.0.2:2380
listen-client-urls: http://10.104.0.2:2379,http://127.0.0.1:2379
advertise-client-urls: http://10.104.0.2:2379
~~~

For ULC-02 replace `name: etcd-01` with `name: etcd-02` and *only* local listen/advertise addresses from `10.104.0.2` to `10.104.0.4`. For ULC-03 use `etcd-03` / `10.104.0.8`. The entire one-line `initial-cluster` list is **identical** on all three. URL settings must be string values, not YAML lists. Earlier commissioning failed when the cluster string was folded with spaces and when a URL string was incorrectly expressed as a YAML array.

Validate on each host before starting:

~~~bash
cd /opt/lorawan/etcd
sudo docker compose config --quiet
sudo grep -E '^(name|initial-cluster|listen-peer-urls|listen-client-urls|advertise-client-urls):' config/etcd.yml
~~~

Start the three *new* members as one planned bootstrap group using `sudo docker compose up -d` on their intended hosts after peer/network validation. The `initial-cluster-state: new` instruction **must never** be used to form a second independent authority while the original etcd cluster still exists. Verify endpoint health/status/member list and Patroni coordination before installing PostgreSQL.

## 4. Safe routine operations

Check bounded logs only on the affected member:

~~~bash
cd /opt/lorawan/etcd
sudo docker compose logs --since=15m --tail=150 etcd
~~~

For one planned member update: prove 3/3 quorum, preserve its data/config/backup, maintain **one** intended member, verify the other two agree on leader, restore the member, verify 3/3 again and one Patroni leader. Do not induce a second outage during recovery.

| Symptom | First failure layer |
|---|---|
| one unreachable client port 2379 | that host's container, bind, disk and private route |
| no leader / 2 members inaccessible | quorum, peer 2380, partition or storage |
| correct process but wrong peer member list | actual active config and existing persisted member state |
| Patroni reports no leader | etcd/DCS first, then Patroni; never force-promote PostgreSQL blindly |
| one restart loop | bounded container logs and data permissions before any volume deletion |

## 5. Backup and disaster recovery boundaries

A verified snapshot is required before cluster-wide changes and destructive recovery. Capture a snapshot from a **healthy authorized endpoint**, record timestamp, endpoint, member list, database revision, file size and SHA-256; copy off all three Droplets under protected retention. The approved etcdctl form, **only if its installed version supports the arguments**, is:

~~~bash
sudo docker exec etcd etcdctl --endpoints=http://127.0.0.1:2379 snapshot save /etcd-data/etcd-snapshot.db
sudo docker exec etcd etcdutl snapshot status /etcd-data/etcd-snapshot.db --write-out=table
~~~

**Caution:** the example saves inside the container's mounted persistent data path and must then be copied off-host promptly. Prefer the repository's approved protected backup wrapper and manifest; do not mistake file existence for a verified off-host restore. An etcd snapshot contains coordination metadata, **not PostgreSQL telemetry or secrets from every other system**. A full rebuild requires consistent PostgreSQL/Patroni backups, PKI, service configuration, gateway checkpoints and identity files as separate protected assets.

There are three different recovery scenarios: restart one healthy retained member; replace one failed member *using authoritative membership and approved remove/add steps*; or recover from quorum loss with an isolated coordinated cluster rebuild/snapshot restoration. The last two are **not** normal service restarts. Do not remove/add IDs, set `initial-cluster-state: new` on running members, copy another member's data directory, or reinitialize from stale metadata simply to clear a health alarm. Complete the dedicated DR plan and restore rehearsal before destructive cluster-wide recovery.

## 6. Completion and publication criteria

**PASS:** 3/3 normal endpoints, one Raft leader, stable peer/client address scope, Patroni DCS healthy, approved backup manifest and one representative PostgreSQL primary-routed SQL operation. A copied 3.5.15 image tag alone does not prove the current image digest is unchanged: collect and preserve actual image ID and pinned replacement artifact before final Word document export.

Source authority: [cloud etcd commissioning](../server/cloud-production/05-etcd-cluster.md), [backup/DR](../server/cloud-production/13-backup-restore-and-disaster-recovery.md) and [operator checklist](06-etcd.md). The comprehensive Word document must incorporate required steps and safe recovery warnings **within the book**, not point the reader to Markdown.
