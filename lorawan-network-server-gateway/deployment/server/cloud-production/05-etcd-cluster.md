# 5. Three-Member etcd Cluster

> **Status: CORE DEPLOYMENT VALIDATED.** The Docker Compose configuration, three-member bootstrap, failure corrections, member reachability, leader election, and final 3/3 endpoint status were actually tested on `ulc-01`, `ulc-02`, and `ulc-03`. The later snapshot, planned maintenance, member replacement, quorum-loss recovery, monitoring, and optional TLS-hardening sections are operational guidance and have **not** yet been live-rehearsed unless a later execution-log entry says otherwise.

## 5.1 Role and current deployment

etcd is the distributed coordination store used by Patroni for leader election and PostgreSQL cluster state. It is not the application database and must not be used as a general telemetry key-value store.

The tested cloud POC runs one etcd member on each HA host:

| Physical host | Logical role | etcd member | East-west IP | Client | Peer |
|---|---|---|---|---|---|
| `ulc-01` | `ha-01` | `etcd-01` | `10.104.0.2` | `2379/tcp` | `2380/tcp` |
| `ulc-02` | `ha-02` | `etcd-02` | `10.104.0.4` | `2379/tcp` | `2380/tcp` |
| `ulc-03` | `ha-03` | `etcd-03` | `10.104.0.8` | `2379/tcp` | `2380/tcp` |

The validated server image is `quay.io/coreos/etcd:v3.5.15`. etcd runs with Docker Compose and `network_mode: host` so it can bind directly to the stable `eth1` east-west addresses.

A running process on one host is not enough. A three-member etcd cluster needs a majority of two members to elect a leader and commit changes.

```text
                   etcd quorum

          etcd-01       etcd-02       etcd-03
        10.104.0.2     10.104.0.4     10.104.0.8
             \            |            /
              \-----------+-----------/
                         Raft

                 2 of 3 = quorum
```

## 5.2 Network decision proven during deployment

Do not use the `10.15.0.x` addresses for HA traffic.

The hosts have additional addresses on `eth0`:

```text
ulc-01  10.15.0.5/16
ulc-02  10.15.0.7/16
ulc-03  10.15.0.6/16
```

Cross-node pings to these addresses failed. `ip neigh show` and `arp -n` showed unresolved or failed neighbors, so the `10.15.0.0/16` path was rejected for cluster traffic.

The `eth1` addresses were then tested:

```text
ulc-01  10.104.0.2/20
ulc-02  10.104.0.4/20
ulc-03  10.104.0.8/20
```

Cross-node ICMP succeeded, and TCP peer traffic was proven with `nc` on port `2380`. These are therefore the operationally validated east-west addresses for etcd and the following HA services.

**Why this check comes before etcd:** a member can have a valid local IP and route while still being unable to reach its peers. etcd would then loop through elections and never reach quorum.

The operator is not authorized to change the DigitalOcean Cloud Firewall. Do not change it from this procedure. UFW also remains a separate controlled host-hardening task. The current etcd listeners bind only to the `10.104.0.x` east-west addresses plus local loopback for the client API; they must never be changed to `0.0.0.0` on these public hosts.

## 5.3 Preconditions

Before the first bootstrap, confirm all of the following:

- `ulc-01`, `ulc-02`, and `ulc-03` resolve to the intended east-west addresses through `/etc/hosts`;
- `10.104.0.2`, `10.104.0.4`, and `10.104.0.8` can reach each other;
- TCP `2380` works between hosts;
- Docker Engine and the Compose plugin work on all three hosts;
- Docker host networking exists;
- time is synchronized;
- `/opt/lorawan/etcd/data` is empty on every member for a brand-new cluster;
- member names and IPs are fixed before first startup.

Useful checks:

```bash
hostname
ip -4 -br address
ip route
ping -c 3 10.104.0.2
ping -c 3 10.104.0.4
ping -c 3 10.104.0.8
docker --version
docker compose version
docker network ls
```

For a new cluster, stop here if a data directory already contains `member/` and its origin is not understood.

## 5.4 Directory layout

The tested layout is:

```text
/opt/lorawan/etcd
├── config
│   └── etcd.yml
├── data
└── docker-compose.yml
```

The live evidence confirms this directory layout and the final `data` mode correction to `700`, but it does not preserve one authoritative original `chown/install` command for every directory. Do not invent historical ownership from the final screenshot.

For a fresh rebuild, first inspect the intended operator/group, then create the layout deliberately. With `opsadmin` as the deployment operator, one reproducible baseline is:

```bash
sudo install -d -m 755 -o opsadmin -g opsadmin /opt/lorawan/etcd
sudo install -d -m 755 -o opsadmin -g opsadmin /opt/lorawan/etcd/config
sudo install -d -m 700 -o opsadmin -g opsadmin /opt/lorawan/etcd/data
stat -c '%a %U:%G %n' /opt/lorawan/etcd /opt/lorawan/etcd/config /opt/lorawan/etcd/data
```

Treat those ownership commands as the **rebuild baseline**, not a claim about the exact original creation command. The proven security correction is that `data` must be mode `700`.

**Why `data` is mode `700`:** etcd warned when the data directory was group/world accessible. The database contains Raft state and cluster metadata and does not need general host-user access.

## 5.5 Docker Compose definition

Create the same Compose file on every node. `sudo tee` is used because shell redirection does not inherit `sudo` privileges.

```bash
sudo tee /opt/lorawan/etcd/docker-compose.yml >/dev/null <<'EOF'
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
EOF
```

Validate it before startup:

```bash
cd /opt/lorawan/etcd
docker compose config
```

The output must show the config bind mount targeting `/etc/etcd/etcd.yml`, the data bind mount targeting `/etcd-data`, and `network_mode: host`.

## 5.6 etcd configuration - `ulc-01`

Create the file exactly as one etcd configuration document. Do not put a `services:` block here; that belongs only in `docker-compose.yml`.

```bash
sudo tee /opt/lorawan/etcd/config/etcd.yml >/dev/null <<'EOF'
name: etcd-01

data-dir: /etcd-data

initial-cluster: etcd-01=http://10.104.0.2:2380,etcd-02=http://10.104.0.4:2380,etcd-03=http://10.104.0.8:2380
initial-cluster-state: new
initial-cluster-token: lorawan-etcd-cluster

listen-peer-urls: http://10.104.0.2:2380
initial-advertise-peer-urls: http://10.104.0.2:2380

listen-client-urls: http://10.104.0.2:2379,http://127.0.0.1:2379
advertise-client-urls: http://10.104.0.2:2379
EOF
```

## 5.7 etcd configuration - `ulc-02`

```bash
sudo tee /opt/lorawan/etcd/config/etcd.yml >/dev/null <<'EOF'
name: etcd-02

data-dir: /etcd-data

initial-cluster: etcd-01=http://10.104.0.2:2380,etcd-02=http://10.104.0.4:2380,etcd-03=http://10.104.0.8:2380
initial-cluster-state: new
initial-cluster-token: lorawan-etcd-cluster

listen-peer-urls: http://10.104.0.4:2380
initial-advertise-peer-urls: http://10.104.0.4:2380

listen-client-urls: http://10.104.0.4:2379,http://127.0.0.1:2379
advertise-client-urls: http://10.104.0.4:2379
EOF
```

## 5.8 etcd configuration - `ulc-03`

```bash
sudo tee /opt/lorawan/etcd/config/etcd.yml >/dev/null <<'EOF'
name: etcd-03

data-dir: /etcd-data

initial-cluster: etcd-01=http://10.104.0.2:2380,etcd-02=http://10.104.0.4:2380,etcd-03=http://10.104.0.8:2380
initial-cluster-state: new
initial-cluster-token: lorawan-etcd-cluster

listen-peer-urls: http://10.104.0.8:2380
initial-advertise-peer-urls: http://10.104.0.8:2380

listen-client-urls: http://10.104.0.8:2379,http://127.0.0.1:2379
advertise-client-urls: http://10.104.0.8:2379
EOF
```

## 5.9 Configuration rules that must match before first startup

On all three nodes, this line must be identical and kept on one physical YAML line:

```yaml
initial-cluster: etcd-01=http://10.104.0.2:2380,etcd-02=http://10.104.0.4:2380,etcd-03=http://10.104.0.8:2380
```

Only these node-specific values change:

```text
ulc-01 -> name etcd-01 -> 10.104.0.2
ulc-02 -> name etcd-02 -> 10.104.0.4
ulc-03 -> name etcd-03 -> 10.104.0.8
```

Verify each file:

```bash
cat /opt/lorawan/etcd/config/etcd.yml
grep -E 'name:|initial-cluster:|listen-peer-urls:|initial-advertise-peer-urls:|listen-client-urls:|advertise-client-urls:' \
  /opt/lorawan/etcd/config/etcd.yml
```

**Why the single-line `initial-cluster` matters here:** during the live bootstrap, the folded YAML form produced spaces before later member names in the parsed string. `etcd-02` and `etcd-03` then failed with `couldn't find local name ... in the initial cluster configuration`. The single-line form removes that ambiguity and is the tested form.

Also keep URL-valued settings as strings. In etcd `v3.5.15`, using YAML arrays such as:

```yaml
advertise-client-urls:
  - http://10.104.0.2:2379
```

caused startup to fail with:

```text
json: cannot unmarshal array into Go struct field configYAML.advertise-client-urls of type string
```

## 5.10 Clean initial bootstrap

For a brand-new cluster, all three active data directories must be empty before the successful bootstrap.

If a previous failed bootstrap already wrote member state, stop the containers first:

```bash
cd /opt/lorawan/etcd
docker compose down
```

Before deleting anything, prove all three etcd containers are stopped and inspect the exact data state on each node:

```bash
cd /opt/lorawan/etcd
docker compose ps
sudo find /opt/lorawan/etcd/data -mindepth 1 -maxdepth 2 -printf '%M %U:%G %p\n'
```

Only if this is a **brand-new failed initial bootstrap**, no application depends on this etcd state, and a full rebootstrap has been explicitly accepted, remove only the failed etcd member state:

```bash
sudo rm -rf -- /opt/lorawan/etcd/data/member
sudo test ! -e /opt/lorawan/etcd/data/member
sudo chmod 700 /opt/lorawan/etcd/data
sudo stat -c '%A %a %U:%G %n' /opt/lorawan/etcd/data
sudo find /opt/lorawan/etcd/data -mindepth 1 -maxdepth 1 -print
```

Do **not** use a wildcard such as `/opt/lorawan/etcd/data/*` in the reusable procedure. Removing only the known etcd `member` directory avoids deleting unrelated files that may later share the parent path. Once an accepted cluster contains real coordination state, do not use this initial-bootstrap reset at all; use etcd membership/snapshot/recovery procedures instead.

Bootstrap the static three-member cluster **sequentially for observability**. Simultaneous startup is not required because every member already has the complete `initial-cluster` list.

1. On `ulc-01`, start `etcd-01` and inspect it:

   ```bash
   cd /opt/lorawan/etcd
   docker compose up -d
   docker logs etcd --tail 80
   ```

   Expected: `etcd-01` knows all three members but cannot form quorum by itself. Election/pre-vote retries while the other two peers are down are expected.

2. On `ulc-02`, start `etcd-02` and inspect both nodes. With two of three voters available, the cluster can now reach quorum and elect a leader.

   ```bash
   cd /opt/lorawan/etcd
   docker compose up -d
   docker logs etcd --tail 80
   ```

3. On `ulc-03`, start `etcd-03` and inspect it:

   ```bash
   cd /opt/lorawan/etcd
   docker compose up -d
   docker logs etcd --tail 80
   ```

   Expected: the third member joins the already-quorate cluster and restores full three-member redundancy.

**Why sequential startup:** it lets the operator distinguish the expected one-member no-quorum state from the two-member quorum transition and the final third-member join. Starting all three nearly simultaneously is also valid for a correctly configured static cluster, but it is not a requirement and gives less useful bootstrap evidence.

## 5.11 Why a failed bootstrap must be cleaned before retrying

etcd is stateful. The data directory contains the member ID, cluster ID, Raft log, snapshots, and peer membership.

```text
configuration file             data directory
       |                            |
       | first startup              | remembers identity
       +--------------------------->|
                                    |
                                    v
                              member / Raft state
```

Changing `etcd.yml` after a failed first start does not rewrite the old member identity. During the live setup this produced messages such as `server has been already initialized` and continued bootstrap failures.

Therefore, during **initial deployment only**, a failed bootstrap is recovered by stopping all three members, correcting every configuration file, clearing all three failed data directories, and then bootstrapping again.

After the cluster is accepted and contains real state, **never use this cleanup procedure**. Normal maintenance and member replacement use the member APIs and snapshots instead.

## 5.12 Troubleshooting notes from the live deployment

### Docker Compose YAML accidentally used as etcd YAML

The first `/opt/lorawan/etcd/config/etcd.yml` contained a Docker `services:` definition. etcd therefore did not receive the intended member configuration and started with default/localhost values during the early attempt.

Keep the responsibilities separate:

```text
docker-compose.yml       -> Docker container lifecycle
config/etcd.yml          -> etcd daemon configuration
data/                     -> etcd persistent Raft state
```

### `advertise-client-urls` array error

Symptom:

```text
failed to verify flags
json: cannot unmarshal array into Go struct field configYAML.advertise-client-urls of type string
```

Fix: use comma-separated string values, not YAML arrays, for the URL fields in this pinned version.

### Member name not found

Symptom:

```text
couldn't find local name "etcd-02" in the initial cluster configuration
```

or the same error for `etcd-03`.

Fix: make `initial-cluster` a single exact line with no spaces after commas, verify the local `name:` matches exactly, then clean failed bootstrap data before retrying.

### Peer `connection refused`

Symptom:

```text
dial tcp 10.104.0.4:2380: connect: connection refused
```

This means the network path reached the target host but no healthy etcd peer was listening yet. During bootstrap, check the target container logs instead of immediately treating this as a VPC failure.

### Repeated elections / request timeout

A single member of the intended three-member cluster cannot get a majority. Logs can show repeated `starting a new election`, `MsgPreVote`, or publish timeouts until at least one other configured peer becomes available.

## 5.13 Health and quorum validation

From an administrative host with a compatible `etcdctl`, run:

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint status \
  --write-out=table
```

Also record:

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint health

ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  member list \
  --write-out=table
```

The successful deployment on 2026-08-21 showed all three endpoints on etcd `3.5.15`, one leader, two followers, no learners, matching Raft term/index progression, and no endpoint errors. At that checkpoint `etcd-02` (`10.104.0.4`) was the leader. The leader is allowed to change later; health depends on quorum, not on a particular node remaining leader.

Healthy acceptance requires:

- exactly three expected members;
- all three client endpoints respond;
- exactly one leader;
- two followers;
- no unexpected learner;
- no endpoint errors;
- Raft term/index values progress normally.

## 5.14 Current transport security boundary

The tested POC currently uses HTTP for etcd client and peer transport **only on the validated `10.104.0.0/20` east-west network**. This is the configuration that was actually bootstrapped and tested.

This is not the same as application-level authentication or transport encryption. Do not expose `2379` or `2380` through a public listener, and do not claim that an unverified DigitalOcean firewall protects them.

The current HTTP-only transport is an **accepted POC checkpoint, not a production transport-security sign-off**. Before this environment is called production-ready, resolve this explicitly: either deploy and validate etcd transport TLS (cluster CA, unique member certificates/SANs, Patroni client trust, controlled rollout, rollback) or record an approved security exception with compensating controls. Do not silently carry the POC HTTP setting into production, and do not mix `http://` and `https://` values during a bootstrap attempt.

> **Not yet rehearsed:** sections 5.15 through 5.19 are operational guidance. No execution-log entry currently proves snapshot restore, member replacement, quorum-loss recovery, or the monitoring procedure has been exercised.

## 5.15 Snapshots

Create a snapshot from a healthy endpoint and keep it outside the etcd data directory:

```bash
install -d -m 700 ~/backups/etcd
umask 077
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379 \
  snapshot save ~/backups/etcd/etcd-$(date +%Y%m%d-%H%M%S).db
```

Validate with a compatible `etcdutl` when available and record a checksum:

```bash
etcdutl snapshot status ~/backups/etcd/<SNAPSHOT_FILE> --write-out=table
sha256sum ~/backups/etcd/<SNAPSHOT_FILE>
```

Copy accepted snapshots off-host. A snapshot contains coordination state and should be handled as protected infrastructure data.

## 5.16 Normal maintenance

After the successful bootstrap, do not empty `/opt/lorawan/etcd/data` during a normal restart or upgrade.

Before stopping one member:

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint health
```

Proceed only when the other two members are healthy. Maintain one member at a time and prove quorum again before touching the next member.

## 5.17 Failed member replacement

Do not copy another live member's data directory.

Safe outline:

1. prove the failed member cannot unexpectedly return with its old data;
2. snapshot the healthy cluster;
3. remove the failed member with `etcdctl member remove <MEMBER_ID>`;
4. add the replacement with `etcdctl member add` and its exact peer URL;
5. use the member-add output to construct the replacement configuration with `initial-cluster-state: existing`;
6. start the replacement with an empty data directory;
7. verify member list and endpoint health before Patroni depends on it.

Do not remove a member when quorum is already lost without following the version-specific disaster-recovery procedure.

## 5.18 Quorum loss

Three members tolerate one unavailable member. Two unavailable members mean no majority.

When quorum is lost:

- freeze unrelated changes;
- preserve member data and logs;
- determine whether members are down or network-partitioned;
- restore connectivity first when possible;
- use a validated snapshot only when normal quorum recovery is impossible;
- verify etcd and Patroni state before allowing PostgreSQL writes.

## 5.19 Monitoring

Collect and alert on:

- leader changes;
- endpoint health;
- proposal failures;
- fsync/backend commit latency;
- database size/quota use;
- peer RTT;
- expected member count;
- snapshot age.

## 5.20 Final checks

- `etcd-01`, `etcd-02`, and `etcd-03` form one three-member cluster.
- All three use the `10.104.0.x` east-west addresses.
- `2379` and `2380` are not deliberately bound to public addresses.
- One leader and two followers are visible in `endpoint status`.
- No learner or endpoint error remains.
- The initial bootstrap mistakes and recovery sequence are recorded in the execution log.
- Future restarts preserve the accepted data directories.

Next standby phase when work resumes: [06-spilo-patroni-postgresql-cluster.md](06-spilo-patroni-postgresql-cluster.md).
