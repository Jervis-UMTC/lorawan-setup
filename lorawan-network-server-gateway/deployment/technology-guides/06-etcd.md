# etcd — Operator Manual

## What this technology does

etcd is the three-member distributed coordination store used by Patroni and other tightly scoped HA coordination logic. It is **not** the telemetry database.

A Patroni/PostgreSQL process can be running while safe leader election is impossible if etcd quorum is lost.

## Current commissioned topology

| Host | Member | Client URL | Peer URL |
|---|---|---|---|
| ULC-01 | `etcd-01` | `http://10.104.0.2:2379` | `http://10.104.0.2:2380` |
| ULC-02 | `etcd-02` | `http://10.104.0.4:2379` | `http://10.104.0.4:2380` |
| ULC-03 | `etcd-03` | `http://10.104.0.8:2379` | `http://10.104.0.8:2380` |

The commissioned etcd transport is private-network HTTP. Do not invent TLS flags until an etcd TLS migration is actually deployed.

Current Compose layout is under `/opt/lorawan/etcd`; persistent data is under `/opt/lorawan/etcd/data`.

## Step 1 — Check container state on all three nodes

Run on each ULC host:

```bash
cd /opt/lorawan/etcd
sudo docker compose ps
```

**PASS means:** the intended `etcd` container is running with no restart loop.

One running member is not quorum proof. Continue.

## Step 2 — Check all endpoint health from one approved node

```bash
sudo docker exec etcd etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint health
```

**PASS means:** all three endpoints report healthy in normal state.

During an approved single-member failure, two healthy voting members can still provide quorum, but restore 3/3 before another fault.

## Step 3 — Check endpoint status and leader

```bash
sudo docker exec etcd etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint status --write-out=table
```

Check:

- exactly one current Raft leader;
- all intended members reachable;
- no obviously divergent/lagging revision;
- no unexplained errors.

The leader can legitimately change. Do not force it back to a node just to match an old screenshot.

## Step 4 — Verify member list

```bash
sudo docker exec etcd etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  member list --write-out=table
```

**PASS means:** the expected three members exist, with the correct peer URLs. There should be no unexplained stale/learner member.

## Step 5 — Verify network/listener exposure

On each host:

```bash
sudo ss -lntp | grep -E ':(2379|2380)\b'
```

The intended etcd service must remain on the private east-west addresses/loopback defined by the deployment. Do not expose etcd on `0.0.0.0` or a public interface to simplify troubleshooting.

## Step 6 — Verify Patroni sees a stable DCS before database actions

On a PostgreSQL host, use the Patroni guide to verify one leader and the expected members. If Patroni leadership is ambiguous, return to etcd health before attempting switchover/promotion.

Never force-promote PostgreSQL to work around etcd quorum loss.

## Safe maintenance rule

For planned work on one etcd member:

1. prove current 3/3 health;
2. prove which member/host you are touching;
3. ensure the other two are healthy and mutually reachable;
4. stop/maintain only one member;
5. verify surviving quorum before further work;
6. restore the member;
7. verify 3/3 endpoint health/status/member list;
8. verify Patroni DCS/leader stability.

Do not maintain two voting members at once.

## Snapshot/backup rule

Before destructive etcd recovery or cluster-wide changes, create and verify the snapshot using the recovery runbook. A file existing on disk is not enough; record its creation time, size/hash, and restore procedure.

Use [`../server/cloud-production/13-backup-restore-and-disaster-recovery.md`](../server/cloud-production/13-backup-restore-and-disaster-recovery.md) for the approved backup/recovery boundary.

## Troubleshooting order

| Symptom | Inspect first |
|---|---|
| One member down, two healthy | failed host/container/network; preserve quorum |
| No leader / writes fail cluster-wide | network partition, two-member loss, disk/full/corruption |
| Member cannot join peers | `10.104.0.x:2380` reachability and member URL/config |
| Client cannot query one node | `2379`, local/container state, bind address |
| Patroni no leader despite PostgreSQL running | etcd quorum/DCS first |

Useful bounded logs on a member:

```bash
cd /opt/lorawan/etcd
sudo docker compose logs --since=15m --tail=150 etcd
```

## Recovery hard stop

Do **not** delete `/opt/lorawan/etcd/data`, start a member with `initial-cluster-state: new`, remove/re-add members, or restore a snapshot into the live cluster because one health check failed. Those are recovery operations and can destroy quorum/state when used casually.

## Completion checklist

- three intended members present;
- normal state endpoint health is 3/3;
- exactly one Raft leader;
- private listener exposure only;
- Patroni DCS state is stable;
- no unexplained stale member;
- current backup/recovery path is known before destructive work.

## Complete installation and recovery companion

Use [etcd three-member bootstrap, quorum, maintenance and protected recovery](ETCD-BOOTSTRAP-QUORUM-RECOVERY.md) for the exact commissioned private-network membership, Compose/bootstrap distinction and recovery hard stops. Rebooting a retained member is not the same procedure as recreating an entire Raft cluster.

## Detailed runbooks

- [`../server/cloud-production/05-etcd-cluster.md`](../server/cloud-production/05-etcd-cluster.md)
- [`../server/cloud-production/13-backup-restore-and-disaster-recovery.md`](../server/cloud-production/13-backup-restore-and-disaster-recovery.md)