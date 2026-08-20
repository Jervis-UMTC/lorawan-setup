# 6. Three-Member etcd Cluster

## 6.1 Role and safety boundary

etcd is the distributed configuration store used by Patroni for leader election and cluster state. It is not the PostgreSQL database and must not be used as a general application key-value store.

A healthy etcd process on one node does not prove quorum. Patroni requires a functioning majority of members.

## 6.2 Topology decision

Choose one profile:

### Co-located profile

In the minimum HA test profile, `ha-01`, `ha-02`, and `ha-03` each run one etcd member and one Spilo/Patroni member.

Advantages: fewer hosts and simpler private networking.

Risk: database host maintenance or failure removes a PostgreSQL member and an etcd vote together. Use separate etcd data storage and monitor disk latency.

### Dedicated profile

`dcs-01`, `dcs-02`, and `dcs-03` run etcd only.

Advantages: independent coordination failure domain and cleaner resource isolation.

Cost: three additional hosts and operational responsibility.

## 6.3 Preconditions

- three stable private IPs and names;
- unique member names;
- low-latency private connectivity;
- synchronized time;
- one unique peer/server certificate and key per member;
- one Patroni client certificate and key;
- private firewall rules for 2379 and 2380;
- approved pinned etcd version compatible across all members;
- empty, dedicated data directories for a new cluster.

**Stop here. Do not bootstrap** if a member name/IP is uncertain, certificate SANs do not match, or any data directory contains an unidentified cluster.

## 6.4 Install and pin etcd

Use the distribution package only when its supported version matches the cluster plan. Otherwise download the official release artifact, verify its checksum or signature, and install it through configuration management.

Keep the exact `etcd` and `etcdctl` versions, official source, verified artifact hash, binary path, service user, and data directory with the cluster configuration. These values determine configuration compatibility, service ownership, snapshot tooling, and rollback. Do not continue when the client and server versions are unexpectedly different or the data directory belongs to an unidentified cluster.

Verify:

```bash
etcd --version
etcdctl version
```

Do not mix etcd major/minor versions during initial bootstrap.

If the selected distribution package created the `etcd` service account, verify it. If an official binary/archive was installed directly, create the system account explicitly before using it as a file owner:

```bash
if ! getent group etcd >/dev/null; then
  sudo groupadd --system etcd
fi

if ! getent passwd etcd >/dev/null; then
  sudo useradd \
    --system \
    --gid etcd \
    --home-dir /var/lib/etcd \
    --shell /usr/sbin/nologin \
    etcd
fi

id etcd
```

**Why:** copying `etcd`/`etcdctl` binaries does not itself guarantee that an `etcd` user and group exist. The directory commands below would otherwise fail or end up with the wrong owner.

## 6.5 Directory and certificate permissions

```bash
sudo install -d -m 700 -o etcd -g etcd /var/lib/etcd
sudo install -d -m 750 -o root -g etcd /etc/etcd
sudo install -d -m 750 -o root -g etcd /etc/lorawan-pki/etcd
```

Install each member's private key so only root and the etcd service group can read it. Verify the unit's effective user before selecting ownership.

## 6.6 Member configuration

Create `/etc/etcd/etcd.yml` independently on each node. This example is for the first member on `ha-01`; replace every placeholder with the recorded three-host values.

```yaml
name: <ETCD_MEMBER_1_NAME>
data-dir: /var/lib/etcd

listen-peer-urls: https://<ETCD_MEMBER_1_PRIVATE_IP>:2380
initial-advertise-peer-urls: https://<ETCD_MEMBER_1_PRIVATE_IP>:2380
listen-client-urls: https://<ETCD_MEMBER_1_PRIVATE_IP>:2379,https://127.0.0.1:2379
advertise-client-urls: https://<ETCD_MEMBER_1_PRIVATE_IP>:2379

initial-cluster: >-
  <ETCD_MEMBER_1_NAME>=https://<ETCD_MEMBER_1_PRIVATE_IP>:2380,
  <ETCD_MEMBER_2_NAME>=https://<ETCD_MEMBER_2_PRIVATE_IP>:2380,
  <ETCD_MEMBER_3_NAME>=https://<ETCD_MEMBER_3_PRIVATE_IP>:2380
initial-cluster-state: new
initial-cluster-token: <UNIQUE_ETCD_CLUSTER_TOKEN>

client-transport-security:
  cert-file: /etc/lorawan-pki/etcd/server.crt
  key-file: /etc/lorawan-pki/etcd/server.key
  client-cert-auth: true
  trusted-ca-file: /etc/lorawan-pki/etcd/ca.crt
  auto-tls: false

peer-transport-security:
  cert-file: /etc/lorawan-pki/etcd/peer.crt
  key-file: /etc/lorawan-pki/etcd/peer.key
  client-cert-auth: true
  trusted-ca-file: /etc/lorawan-pki/etcd/ca.crt
  auto-tls: false

logger: zap
log-level: info
```

Check the installed version's configuration schema. If a configuration file is supplied, etcd ignores command-line and environment settings; do not assume an environment override took effect.

## 6.7 systemd unit

Use the package unit when available and inspect it first:

```bash
systemctl cat etcd
```

A minimal custom unit pattern is:

```ini
[Unit]
Description=etcd distributed configuration store
After=network-online.target
Wants=network-online.target

[Service]
User=etcd
Group=etcd
ExecStart=/usr/local/bin/etcd --config-file=/etc/etcd/etcd.yml
Restart=on-failure
RestartSec=5s
LimitNOFILE=65536
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=strict
ReadWritePaths=/var/lib/etcd

[Install]
WantedBy=multi-user.target
```

Validate sandboxing against the actual certificate and data paths before enabling it.

## 6.8 Bootstrap sequence

1. Validate all three configuration files and certificates.
2. Confirm all three data directories are empty and correctly owned.
3. Start the three members within the same controlled change window.
4. Do not change `initial-cluster-state` or member lists independently after bootstrap.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now etcd
sudo systemctl status etcd --no-pager -l
sudo journalctl -u etcd -n 100 --no-pager
```

## 6.9 Health and quorum validation

Set protected client variables in the current shell without saving keys in history:

```bash
export ETCDCTL_API=3
export ETCDCTL_ENDPOINTS='https://<ETCD_1>:2379,https://<ETCD_2>:2379,https://<ETCD_3>:2379'
export ETCDCTL_CACERT=/etc/lorawan-pki/etcd/ca.crt
export ETCDCTL_CERT=/etc/lorawan-pki/etcd/client.crt
export ETCDCTL_KEY=/etc/lorawan-pki/etcd/client.key
```

Then:

```bash
etcdctl endpoint health --cluster
etcdctl endpoint status --cluster --write-out=table
etcdctl member list --write-out=table
```

Healthy evidence requires:

- exactly three expected members;
- all endpoints healthy;
- one leader;
- matching cluster IDs;
- no learner left unexpectedly;
- acceptable database size and raft index progression.

## 6.10 Authentication and access

Mutual TLS limits transport clients but does not automatically define etcd RBAC policy. Decide whether to enable etcd authentication after verifying Patroni client behavior with the pinned versions.

Never expose 2379 or 2380 publicly. Patroni control certificates must not be installed on application nodes unless those nodes directly query etcd for an approved reason.

## 6.11 Snapshots

Create snapshots from a healthy endpoint using a protected location:

```bash
install -d -m 700 ~/backups/etcd
umask 077
etcdctl --endpoints=https://<HEALTHY_ETCD_PRIVATE_IP>:2379 \
  snapshot save ~/backups/etcd/etcd-$(date +%Y%m%d-%H%M%S).db
```

Validate:

```bash
etcdutl snapshot status ~/backups/etcd/<SNAPSHOT_FILE> --write-out=table
sha256sum ~/backups/etcd/<SNAPSHOT_FILE>
```

Copy snapshots off-host and encrypt them. etcd snapshots contain cluster coordination data and may reveal service structure.

## 6.12 Member maintenance

Before stopping one member:

```bash
etcdctl endpoint health --cluster
etcdctl endpoint status --cluster --write-out=table
```

Proceed only when the other two are healthy. Stop, update, and return one member at a time. Verify quorum before touching the next.

## 6.13 Failed member replacement

Do not copy another live member's data directory.

Safe outline:

1. prove the failed member will not return with its old data unexpectedly;
2. snapshot the healthy cluster;
3. remove the failed member with `etcdctl member remove <MEMBER_ID>`;
4. add a replacement with `etcdctl member add` using the new peer URL;
5. use the exact generated `initial-cluster` and `initial-cluster-state: existing` values;
6. start the replacement with an empty data directory;
7. verify member list, endpoint health, and Patroni connectivity.

**Stop here. Do not remove a member** when quorum is already lost without following the version-specific disaster-recovery procedure.

## 6.14 Quorum loss

With three members, one failure is tolerated. Two unavailable members means no majority. Do not force a PostgreSQL promotion by deleting Patroni state or starting PostgreSQL outside Patroni.

When quorum is lost:

- freeze unrelated changes;
- preserve all member data directories and logs;
- determine whether members are down or only partitioned;
- recover connectivity when possible;
- select a validated etcd snapshot only when normal quorum recovery is impossible;
- follow the official version-specific snapshot restore procedure on a new cluster;
- verify Patroni state before allowing writes.

## 6.15 Monitoring

Collect and alert on:

- leader changes;
- endpoint health;
- proposal failures;
- fsync and backend commit latency;
- database size and quota usage;
- network peer RTT;
- member count;
- snapshot age;
- certificate expiry.

## 6.16 Final checks

- Three expected members form one TLS-protected cluster.
- Quorum remains healthy when one member is stopped in staging.
- Patroni client certificate can read/write its namespace.
- Public scans cannot reach 2379 or 2380.
- Snapshot creation, status validation, off-host copy, and a version-compatible restore rehearsal succeed.

Next: [07-spilo-patroni-postgresql-cluster.md](07-spilo-patroni-postgresql-cluster.md)
