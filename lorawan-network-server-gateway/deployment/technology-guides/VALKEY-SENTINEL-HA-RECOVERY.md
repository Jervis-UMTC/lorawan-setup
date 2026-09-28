# Valkey / Sentinel — Three-Node TLS HA Installation and Recovery

**Purpose:** operate the commissioned ChirpStack shared-state cache without confusing it with PostgreSQL telemetry or the cloud MQTT brokers. This expands [operator guide 09](09-valkey-sentinel.md). The cluster has one *current* writable primary, two data replicas and three Sentinels, but the elected primary's host changes. Dated commissioning roles are not current state.

## 1. Architecture and quorum

~~~text
ChirpStack-1 / ChirpStack-2
  -> valkey.internal.lorawan.com:16379 (mapped to own ULC-01/02)
  -> own HAProxy writable-primary route
  -> current Sentinel-elected Valkey primary :6379 TLS
       -> two TLS data replicas :6379
3 Sentinels :26379 TLS -> agree on primary and quorum 2
~~~

Valkey state is **not** a backup of ChirpStack PostgreSQL, and Sentinel is **not** an MQTT broker. A primary can move to ULC-02 or ULC-03. Do not manually revert it to ULC-01 to match the original bootstrap diagram. Two of the three Sentinels are needed for quorum/failover authorization; each data node also requires the *persistent* replication authentication secret, even when currently primary.

## 2. Commissioned inventory

| Item | Approved commissioned contract |
|---|---|
| Data service | Valkey 7.2.13 Ubuntu package, three hosts, `/etc/valkey/valkey.conf` |
| Sentinel | Matching Valkey 7.2.13 Sentinel package, `/etc/valkey/sentinel.conf` (writable runtime topology file) |
| Data TCP | private/loopback `:6379` with `port 0` and `tls-port 6379` |
| Sentinel TCP | private/loopback `:26379` with `port 0` and `tls-port 26379` |
| HAProxy | local `:16379` on ULC-01/02; must route only writable primary |
| TLS identity | `valkey.internal.lorawan.com`, independent CA/key protected under `/etc/lorawan-pki/valkey/` |
| Data password | shared approved replication/app secret or separately reviewed ACL identities |
| Sentinel admin | distinct protected Sentinel secret |
| Quorum | `sentinel monitor lorawan-valkey <BOOTSTRAP_PRIMARY> 6379 2` |
| Persistence | validated current Valkey AOF/RDB settings from runtime; do not overwrite healthy data |

The first commissioning used `10.104.0.2` as bootstrap primary. This is **not** a permanent leader setting. The 2026-08-25 follow-up found that old ULC-01, after Sentinel promotion of ULC-03, could not replicate because persistent `masterauth` had been placed only on former replicas. The corrected contract is **exactly one persistent masterauth directive on every data node**, including a current primary, so it can safely become a replica after failover. Check actual ACL/password policy before reproducing; don't publish auth values.

## 3. Read-only triage without releasing protected secrets

On each ULC host:

~~~bash
hostname -f
date -u
sudo systemctl is-active valkey-server valkey-sentinel
sudo systemctl is-enabled valkey-server valkey-sentinel
sudo ss -lntp | grep -E ':(6379|26379|16379)\b' || true
sudo stat -c '%a %U:%G %n' /etc/valkey/valkey.conf /etc/valkey/sentinel.conf
~~~

Use the approved protected credential-loading procedure for an authenticated `valkey-cli` session, with the proper CA and verified TLS server name. **Stop:** a bare `valkey-cli ROLE` can emit `NOAUTH` while the command wrapper exits zero; checking shell exit code alone is not enough. An earlier Ubuntu package invocation did **not** honor an attempted `VALKEYCLI_AUTH` environment path as expected, while explicit `-a` worked in commissioning but exposes secrets in a process argument. Prefer the current project's secure short-lived privileged harness that handles the secret without printing process arguments; verify it actually receives authenticated `PONG`/`ROLE` before using the result. If no vetted harness is present, do **not** paste the password into shell history, chat, documentation or a world-readable file. This chapter intentionally shows endpoint/argument *shapes*, not executable placeholder-secret commands.

For each **data** node, an authorized TLS CLI must return `ROLE` and `INFO replication`. For each **Sentinel** use:

~~~text
SENTINEL CKQUORUM lorawan-valkey
SENTINEL GET-MASTER-ADDR-BY-NAME lorawan-valkey
SENTINEL MASTER lorawan-valkey
~~~

Expected: three present Sentinels, quorum result `OK`, same current primary IP, one data `master` plus two online replicas, and each app host's local `:16379` returning `ROLE master`. A reachable TCP port proves none of those logical claims by itself. Repeat *only* the failing layer if one check is missing.

## 4. Fresh-install prerequisites — not a recovery procedure

Only for a new approved empty data/cluster: confirm ULC VPC private networking, exact pinned package source/version, free RAM/disk, synchronized clock, service user identities, protected PKI and both approved secrets. Confirm that the existing service/data are **absent**; do not apply these steps over a currently elected primary.

Original setup directory intent:

~~~bash
sudo install -d -m 750 /etc/lorawan-cloud/valkey
sudo install -d -m 750 /etc/lorawan-pki/valkey
sudo install -d -m 700 /srv/valkey/data
sudo install -d -m 750 /srv/valkey/sentinel
~~~

**Before executing on a fresh host**, resolve the actual valkey service UID/GID and packaged persistence paths; the above mode example does not establish the final owner. Install approved `valkey-server` and matching `valkey-sentinel` package versions; inspect the *installed* systemd `ExecStart` and config references (commissioned Sentinel used `/usr/bin/valkey-sentinel /etc/valkey/sentinel.conf --supervised systemd --daemonize no`). Disable/stop Sentinel while staging non-default private TLS/config. Do not start the packaged default which may expose plaintext `26379` and monitor `127.0.0.1 mymaster`.

### 4.1 Data-server configuration shape

Adapt on *each new host* using the actual protected paths and service account. A staged skeleton (placeholders are never runnable literal secrets):

~~~conf
bind 127.0.0.1 <THIS_PRIVATE_IP>
protected-mode yes
port 0
tls-port 6379
tls-cert-file /etc/lorawan-pki/valkey/server.crt
tls-key-file /etc/lorawan-pki/valkey/server.key
tls-ca-cert-file /etc/lorawan-pki/valkey/ca.crt
tls-auth-clients no
tls-replication yes
requirepass <PROTECTED_VALKEY_SECRET>
masterauth <SAME_PROTECTED_VALKEY_SECRET>
appendonly yes
appendfsync everysec
maxmemory 128mb
maxmemory-policy noeviction
~~~

This shows the key commissioned policy, **not the entire installed valkey.conf**; restore actual bind/service settings and health-check ACL details from protected backup. `port 0` disables plaintext, `tls-replication yes` secures replication, and `noeviction` fails visibly instead of silently dropping state under pressure. `tls-auth-clients no` means authenticated *client certificates are not mandated* for all Valkey clients; TLS + password/ACL is still required, and must not be mislabeled full mTLS.

For a *brand-new coordinated cluster only*, set `replicaof 10.104.0.2 6379` on ULC-02 and ULC-03 at initial bootstrap; ULC-01 starts as bootstrap primary. Do **not** reset `replicaof` during an operating HA cluster or after Sentinel has elected another primary. Every node keeps persistent `masterauth` irrespective of current role. Avoid repeating the former-primary rejoin defect.

### 4.2 Sentinel configuration shape

Stage each Sentinel's private addresses, CA/key and distinct admin secret. Its config is writable because Sentinel rewrites known topology during election/rejoin:

~~~conf
bind 127.0.0.1 <THIS_PRIVATE_IP>
protected-mode yes
port 0
tls-port 26379
tls-cert-file /etc/lorawan-pki/valkey/server.crt
tls-key-file /etc/lorawan-pki/valkey/server.key
tls-ca-cert-file /etc/lorawan-pki/valkey/ca.crt
tls-auth-clients no
tls-replication yes
requirepass <PROTECTED_SENTINEL_SECRET>
sentinel monitor lorawan-valkey 10.104.0.2 6379 2
sentinel auth-pass lorawan-valkey <PROTECTED_VALKEY_SECRET>
sentinel down-after-milliseconds lorawan-valkey 5000
sentinel failover-timeout lorawan-valkey 60000
sentinel parallel-syncs lorawan-valkey 1
~~~

The monitored address is the **fresh-cluster bootstrap target**. During normal operation Sentinel rewrites this state; do not re-copy the original config over the live state. Confirm private bind and certificate SAN trust from all three members, plus quorum and future writable-primary HAProxy backend health before authorizing ChirpStack.

## 5. Staged activation without split-brain

1. Confirm no existing cluster/data will be overwritten and that the approved backup/recovery boundary is available.
2. Install/validate private TLS data config on all three, secret/CA permissions and persistent masterauth; start bootstrap primary only, prove authenticated TLS `ROLE master` and no plaintext socket.
3. Start the two intended replicas one at a time; verify `ROLE slave`, selected primary, `master_link_status:up`, connected replica count and a bounded approved test value replicated.
4. Install/review TLS-only Sentinel config on each host, then start/enable **one at a time**, prove exactly three Sentinels discover one another, quorum `2` and consistent primary. Leave the leader wherever election places it.
5. Activate each application's private HAProxy `:16379` frontend and Sentinel-based writable-primary health selection. Test `ROLE master` on both ULC-01 and ULC-02 frontends; do not hard-code the first bootstrap IP.
6. Prove ChirpStack `rediss://valkey.internal.lorawan.com:16379` under the current approved CA/system trust configuration; one real ChirpStack application operation must succeed after commissioning.

The immutable database and normal sensor path do **not** require Valkey keys to be flushed/recreated for service startup.

## 6. Repair at the smallest failing layer

| Symptom | First evidence / next action |
|---|---|
| all Sentinels disagree/no quorum | private 26379 peer network, TLS/auth, service health and epochs before any manual failover |
| replica `master_link_status:down` | authenticated TLS to current master, persistent `masterauth` and Sentinel-determined `replicaof` |
| primary changed after planned outage | leave it elected; verify both healthy replicas and routes, no cosmetic failback |
| `:16379` returns `slave` | HAProxy/Sentinel writable-primary backend selection; don't edit ChirpStack URI |
| only one ChirpStack fails | its local HAProxy, CA, credential and TLS server name |
| memory pressure | role/master count, maxmemory/noeviction and actual load; no silent FLUSHALL |
| no data after restart | AOF/RDB policy and protected backup, not random old RDB copy |
| CLI returns NOAUTH | fix diagnostic authentication, not server startup |

For any data-node maintenance, establish current primary/replica roles and 3/3 Sentinel state, preserve backup and service config, stop at most one intended node, check others' quorum, then wait for recovery to **fully rejoin**. After a material failover change, a controlled failover test may be appropriate; repeating it after an unrelated documentation edit is not.

**Do not casually run:** `FLUSHALL`, `FLUSHDB`, `SENTINEL FAILOVER`, `SLAVEOF/REPLICAOF`, `CONFIG REWRITE` over unknown state, bulk key deletion or a forced service reset.

## 7. Backup/recovery and completeness

Preserve separately the approved package repository/version, `valkey.conf`, **writable** `sentinel.conf`, protected CA/server identities, stored app/replication and Sentinel secrets, current role/epoch/quorum, on-disk AOF/RDB according to retention, HAProxy `:16379` config/health logic, and verified backup hashes/off-host copies. A local RDB is not equivalent to fully tested whole-stack recovery or authoritative SQL telemetry. Never import a stale data file over a healthy elected primary without a controlled restore boundary.

Normal **PASS**: one master/two online replicas, three Sentinels quorum 2, same elected address at all members, data TLS only, current masterauth verified without disclosure, both application HAProxy routes reach master and ChirpStack actually processes a representative event. Document open tests as open; a reboot/failover experiment is not part of a markdown-only audit.

Source references: [commissioning](../server/cloud-production/08-mqtt-and-valkey.md), [controlled failover](../server/cloud-production/15-failover-chaos-and-acceptance-testing.md), [operator guide 09](09-valkey-sentinel.md). The standalone Word document must include the operative protected-credential and recovery procedure within its pages.
