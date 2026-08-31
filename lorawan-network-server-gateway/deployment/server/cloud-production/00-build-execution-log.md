# Cloud Production Build Execution Log

## Purpose

This document records the actual server provisioning, hardening, validation, problems, fixes, and decisions made during the live HA LoRaWAN cloud deployment.

This is the evidence source for the final DOCX. Keep it aligned with what was actually executed. Do not replace failed steps with a cleaner fictional history; record the failure and the correction so the final manual explains why the corrected sequence matters.

---

# Phase 1 - Server Provisioning Baseline

## Active servers

| Node | Public IPv4 | eth0 secondary | HA east-west IPv4 | Role |
|---|---|---|---|---|
| `ulc-01` | `143.198.205.54` | `10.15.0.5/16` | `10.104.0.2/20` | HA node 1 |
| `ulc-02` | `165.22.253.127` | `10.15.0.7/16` | `10.104.0.4/20` | HA node 2 |
| `ulc-03` | `159.223.50.57` | `10.15.0.6/16` | `10.104.0.8/20` | HA node 3 |

The original `ulc-03` Droplet was retired and replaced. Its old `10.104.0.3` address must not be reused in quorum or service configuration.

Operating system and resources observed on the active nodes:

```text
Ubuntu 24.04.4 LTS
Kernel after patch/reboot: 6.8.0-138-generic
1 vCPU
~1.9 GiB RAM
~48 GiB usable root filesystem
No swap
```

---

# Phase 2 - System Updates

Completed on all three active nodes:

- full apt upgrade;
- kernel update;
- reboot where required;
- package database check;
- systemd failed-unit check.

Verification included:

```bash
uname -r
sudo dpkg --audit
systemctl --failed
```

Result:

```text
Kernel: 6.8.0-138-generic
Failed systemd units: 0
```

Automatic reboot remains disabled so clustered services are not restarted unexpectedly by unattended upgrades.

---

# Phase 3 - SSH Security Hardening

Completed on all nodes.

Effective policy:

```text
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PubkeyAuthentication yes
UsePAM yes
MaxAuthTries 3
LoginGraceTime 30
```

Validated with:

```bash
sudo sshd -t
sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication|kbdinteractiveauthentication|permitemptypasswords|pubkeyauthentication|maxauthtries|logingracetime|usepam'
```

Fresh Ed25519 key-only logins succeeded. Password-only SSH attempts were rejected.

---

# Phase 4 - Administrative User Access

The primary operator account `jervis` was verified with sudo access.

A separate `opsadmin` access path was also created with a separate Ed25519 identity for another device. The original private key was not reused as the second-device identity.

Why: separate identities can be revoked independently if one device is lost or replaced.

---

# Phase 5 - Password Quality

Installed on all nodes:

```text
libpam-pwquality
```

Verified PAM hook:

```text
password requisite pam_pwquality.so retry=3
```

Project drop-in:

```text
/etc/security/pwquality.conf.d/99-lorawan.conf
minlen = 16
```

Permissions:

```text
0644 root:root
```

This policy protects future local/sudo password changes even though SSH password authentication is disabled.

---

# Phase 6 - Automatic Security Updates

Verified on all active nodes:

```text
unattended-upgrades installed
APT periodic package-list refresh enabled
APT unattended upgrade enabled
unattended-upgrades.service active + enabled
automatic reboot not enabled
```

---

# Phase 7 - SSH Logging and Fail2ban

`systemd-journald` and SSH journal events were verified before Fail2ban installation.

Observed Internet scan traffic included invalid usernames, root probes, protocol mismatches, and unsupported key algorithms. No successful unauthorized login was observed in the reviewed evidence.

Fail2ban SSH jail deployed on all three nodes:

```ini
[sshd]
enabled = true
backend = systemd
maxretry = 5
findtime = 10m
bantime = 10m
ignoreip = 127.0.0.1/8 ::1 203.177.194.77
```

The configuration was tested with:

```bash
sudo fail2ban-client -t
sudo fail2ban-client status sshd
```

A second SSH session remained usable after activation.

---

# Phase 8 - AppArmor, Time, and Persistent Logs

The detailed pasted evidence is strongest for `ulc-01`; later completion on the other active hosts was operator-confirmed. Do not invent identical AppArmor profile counts or command output for hosts whose full terminal evidence was not preserved.

Verified/accepted controls:

```text
AppArmor: active/enabled on the accepted host-hardening baseline
Time: UTC with NTP synchronization accepted
Journald: active with persistent journal storage accepted
```

On `ulc-01`, the captured evidence explicitly showed AppArmor active/enabled, UTC/NTP synchronized, `/var/log/journal` present, and a previous boot visible with `sudo journalctl --list-boots`. Other-host completion is retained as operator-confirmed unless detailed evidence is added later.

---

# Phase 9 - Firewall Boundary

The operator is **not authorized to modify the DigitalOcean Cloud Firewall**. No cloud-firewall change is part of this execution log.

Host state during the build:

```text
UFW: inactive
nftables: Fail2ban f2b-sshd rules only after Fail2ban activation
```

Do not describe nftables as empty after Fail2ban is installed.

UFW was intentionally not enabled during the remote-only commissioning sequence because there is no independent DigitalOcean recovery-console path available to the operator. This avoids turning a firewall mistake into an unrecoverable SSH lockout.

The cluster services are instead bound to their required interfaces/addresses while host-firewall rollout remains a separate controlled task.

---

# Phase 10 - East-West Network Validation

## 10.1 Rejected `10.15.0.0/16` path

Initial tests used the `eth0` secondary addresses:

```text
ulc-01 10.15.0.5
ulc-02 10.15.0.7
ulc-03 10.15.0.6
```

Each host could ping itself, but cross-node pings failed with `Destination Host Unreachable`.

`ip neigh show` and `arp -n` showed failed/incomplete neighbor resolution for the other nodes.

Conclusion:

```text
10.15.0.0/16 is not used for HA east-west service traffic.
```

## 10.2 Validated `10.104.0.0/20` path

The `eth1` addresses were tested next:

```text
ulc-01 10.104.0.2
ulc-02 10.104.0.4
ulc-03 10.104.0.8
```

Cross-node ICMP succeeded.

The exact etcd peer path was also tested with netcat on TCP `2380`:

```text
ulc-02 -> ulc-01:2380 PASS
ulc-03 -> ulc-02:2380 PASS
```

Decision:

```text
Operational HA/east-west network = 10.104.0.0/20 on eth1
```

The DigitalOcean panel has not been independently inspected by the operator, so the documentation calls this the **operationally validated east-west network**, not a provider-console-confirmed VPC assignment.

---

# Phase 11 - Hostname Resolution

`/etc/hosts` was configured on all three nodes:

```text
10.104.0.2 ulc-01
10.104.0.4 ulc-02
10.104.0.8 ulc-03
```

Hostname resolution and east-west ping tests passed.

---

# Phase 12 - Docker Runtime and Deployment Layout

Docker runtime verified on all three nodes:

```text
Docker Server Version: 29.7.2
Storage Driver: overlayfs
Cgroup Driver: systemd
Cgroup Version: 2
```

Default Docker networks were present:

```text
bridge
host
none
```

`docker compose` functionality was proven during etcd configuration/validation. The captured execution evidence does **not** preserve the exact Compose plugin version, Docker package-source output, or `docker info` logging-driver value. These remain evidence gaps to check before the next container phase; do not backfill them from a planning manual.

Decision: infrastructure containers that need stable host east-west addresses use host networking where the service-specific manual says so.

Deployment directories created on all three nodes:

```text
/opt/lorawan
├── backup
├── chirpstack
├── config
├── etcd
├── haproxy
├── mosquitto
├── patroni
├── postgres
├── secrets
└── valkey
```

etcd-specific structure:

```text
/opt/lorawan/etcd
├── config
│   └── etcd.yml
├── data
└── docker-compose.yml
```

---

# Phase 13 - Three-Member etcd Deployment

## 13.1 Tested service baseline

```text
Image: quay.io/coreos/etcd:v3.5.15
Deployment: Docker Compose
Networking: host
Client: 2379/tcp
Peer: 2380/tcp
```

Members:

```text
etcd-01 -> 10.104.0.2
etcd-02 -> 10.104.0.4
etcd-03 -> 10.104.0.8
```

The successful configuration uses this exact one-line cluster string:

```text
etcd-01=http://10.104.0.2:2380,etcd-02=http://10.104.0.4:2380,etcd-03=http://10.104.0.8:2380
```

## 13.2 Bootstrap issue 1 - Compose YAML mounted as etcd YAML

An early `/opt/lorawan/etcd/config/etcd.yml` contained a Docker `services:` document instead of etcd daemon settings.

Observed effect:

```text
etcd loaded /etc/etcd/etcd.yml but started with default/localhost settings
name=default
localhost:2379
localhost:2380
```

Fix: separate the files:

```text
docker-compose.yml -> Docker lifecycle
config/etcd.yml    -> etcd daemon settings
data/               -> persistent Raft state
```

## 13.3 Bootstrap issue 2 - YAML arrays for URL fields

Using an array form for `advertise-client-urls` caused:

```text
json: cannot unmarshal array into Go struct field configYAML.advertise-client-urls of type string
```

Fix: use string values such as:

```text
advertise-client-urls: http://10.104.0.2:2379
```

## 13.4 Bootstrap issue 3 - folded `initial-cluster` whitespace

The folded multi-line cluster value was parsed with leading spaces before later member names.

Observed errors included:

```text
couldn't find local name "etcd-02" in the initial cluster configuration
couldn't find local name "etcd-03" in the initial cluster configuration
```

Fix: keep `initial-cluster` on one physical line with no spaces after commas.

## 13.5 Bootstrap issue 4 - failed member state persisted

After failed attempts, the data directory already contained `member/` state. Changing YAML did not reset the stored member/cluster identity.

For this **brand-new cluster only**, the historical recovery command that was actually used was:

```bash
cd /opt/lorawan/etcd
docker compose down
sudo rm -rf /opt/lorawan/etcd/data/*
sudo chmod 700 /opt/lorawan/etcd/data
```

This command is preserved here because this file is the execution history. It is **broader than the reusable recovery procedure and must not be copied as the standard reset command**. The corrected runbook in `05-etcd-cluster.md` requires stopping and inspecting all members first and, only for an explicitly accepted failed initial bootstrap with no required state, removing the exact `/opt/lorawan/etcd/data/member` path.

The corrected configs were verified and all three members were then brought online. The operator used multiple terminals during the successful attempt, but simultaneous startup was **not** a technical requirement. A correctly configured static cluster can be started sequentially: member 1 waits without quorum, member 2 provides the 2/3 majority, and member 3 restores full redundancy.

Why this matters: after first startup etcd remembers its member ID, cluster ID, Raft log, and peer membership. A config edit alone does not rewrite that stored state.

**Never use the initial-bootstrap reset after the accepted cluster contains real coordination state.** Established-cluster maintenance/recovery must use membership operations, snapshots, or the version-specific recovery procedure.

## 13.6 Successful quorum validation

The final command was:

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint status \
  --write-out=table
```

Observed result on 2026-08-21:

```text
10.104.0.2:2379  etcd 3.5.15  follower  learner=false  no errors
10.104.0.4:2379  etcd 3.5.15  leader    learner=false  no errors
10.104.0.8:2379  etcd 3.5.15  follower  learner=false  no errors
```

At this checkpoint `etcd-02` was leader. Leader placement is not fixed; etcd may elect another healthy member later.

Accepted state:

```text
3 members
1 leader
2 followers
quorum healthy
```

---

# Current Status

Completed:

- server provisioning;
- Ubuntu patch/reboot baseline;
- SSH hardening;
- independent administrative SSH access;
- password-quality policy;
- unattended security updates without automatic reboot;
- SSH journal verification;
- Fail2ban;
- AppArmor;
- UTC/NTP synchronization;
- persistent journald;
- east-west network validation;
- `/etc/hosts` cluster resolution;
- Docker runtime validation;
- deployment directory layout;
- three-member etcd bootstrap and quorum validation.

Still intentionally not changed or not evidenced as commissioned:

```text
DigitalOcean Cloud Firewall - externally controlled / operator not authorized; current rule state unknown
UFW - inactive pending a safe remote-access/recovery rollout
DigitalOcean Reserved IPv4 - no commissioning evidence captured in this log
public DNS for the future Reserved-IP ingress - no commissioning evidence captured in this log
```

## Phase 6 resumed - PostgreSQL/Patroni pre-bootstrap only

On 2026-08-21 the project resumed after the validated etcd checkpoint, but **no PostgreSQL/Patroni process has been started and no PostgreSQL data directory has been initialized**.

The first Phase 6 action is a read-only three-host preflight. It captures the evidence gaps left by the Docker phase and checks the boundary before any durable database state is created:

```text
exact Docker Compose plugin version
current Docker default logging driver
current memory/root-disk state
running-container inventory
ulc-01/02/03 name resolution
listener ownership for 2379/2380/5432/8008
existing PostgreSQL/Patroni paths, if any
etcd endpoint health as seen from each future database host
```

Why this is a hard stop: the Spilo image determines the real container UID/GID and the supported PostgreSQL/Patroni/TimescaleDB combination. We must not create `/srv/spilo/pgroot`, choose ownership, or bootstrap the cluster from placeholders.

Current Phase 6 state:

```text
06 - Spilo / Patroni / PostgreSQL HA
status: ACTIVE - PRE-BOOTSTRAP PREFLIGHT
PostgreSQL started: NO
Patroni started: NO
PostgreSQL data initialized: NO
Spilo image/digest selected: NO
```

The documented preflight was completed on all three hosts and passed.

Observed on 2026-08-21:

```text
ulc-01  RAM 1.9 GiB, ~394 MiB used, ~1.5 GiB available, root ~45 GiB free
ulc-02  RAM 1.9 GiB, ~413 MiB used, ~1.5 GiB available, root ~45 GiB free
ulc-03  RAM 1.9 GiB, ~417 MiB used, ~1.5 GiB available, root ~45 GiB free

all three:
  kernel 6.8.0-138-generic
  Docker Engine 29.7.2
  Docker Compose v5.5.0
  overlayfs / systemd cgroup driver / cgroup v2
  Docker default logging driver = json-file
  only etcd container running
  5432/tcp absent
  8008/tcp absent
  /opt/lorawan/postgres present and empty
  /opt/lorawan/patroni present and empty
  /srv/spilo absent
  /etc/lorawan-cloud/spilo absent
  all three etcd endpoints healthy from every future database host
```

`2379/2380` were owned only by the local etcd process on the documented private/east-west address, with `2379` also on loopback as designed.

The preflight also showed that each node's own hostname has both the Ubuntu `127.0.1.1` mapping and the explicit `10.104.0.x` mapping. For Patroni this means bind/connect/advertise addresses must be explicitly pinned to the east-west IP and must not be inferred from hostname resolution.

Evidence gap closed: Docker Compose is `v5.5.0` and the current daemon default logging driver is `json-file`. The latter is **not** the planned bounded `local` default; it must be handled before adding Spilo, either per-service or through a separate safe daemon change.

Phase 6 status is now:

```text
06 - Spilo / Patroni / PostgreSQL HA
status: ACTIVE - IMAGE/VERSION SELECTION
preflight: PASS
PostgreSQL started: NO
Patroni started: NO
PostgreSQL data initialized: NO
Spilo image/digest selected: NO
```

Upstream source discovery was then performed from `ulc-03` using Git `2.43.0`. `git ls-remote` against the Spilo `trigger` branch returned candidate source commit:

```text
95139b4de7a33aec1f788ad7bb863c92edbe2ee8
```

This SHA is now the Phase 6 **candidate source checkpoint**. It is not yet an approved image or database version. PostgreSQL major, Patroni version, TimescaleDB build, image digest, and container UID/GID remain unresolved until this exact source is inspected.

The exact SHA was fetched on `ulc-03` into `/home/opsadmin/spilo-review-95139b4de7a3` using a shallow Git fetch and detached checkout. `git rev-parse HEAD` returned exactly:

```text
95139b4de7a33aec1f788ad7bb863c92edbe2ee8
```

Captured commit metadata:

```text
commit_date=2026-07-22T15:27:42+02:00
subject=inject IRSA credentials into wal-g envdir for standby and clone clusters (#1206)
worktree=HEAD (no branch)
```

Source-fetch verification: **PASS**.

The exact checkout was then inspected without building an image. The pinned source reports:

```text
base image tag: ubuntu:22.04
PGVERSION default: 18
PGOLDVERSIONS: 14 15 16 17
Patroni: 4.1.3
TIMESCALEDB_APACHE_ONLY=true
TIMESCALEDB_TOOLKIT=true
ETCD3_HOSTS supported through the generic DCS parser and required for this etcd 3.5 deployment
ETCD_HOSTS also parses, but maps to Patroni's separate legacy `etcd` DCS path and must not be used here
RESTAPI_CONNECT_ADDRESS supported
PG_CONNECT_ADDRESS explicit override supported
```

This does **not** select PostgreSQL 18 yet. It only records the pinned source defaults.

Detailed source inspection then confirmed the build-reproducibility concern rather than closing it:

```text
TimescaleDB package: installed by major-specific package name, no exact package version constraint
Timescale repository: live packagecloud repository
TIMESCALEDB_APACHE_ONLY=true -> OSS package selected
TIMESCALEDB_TOOLKIT=true -> toolkit branch still skipped while APACHE_ONLY=true
Patroni: explicitly pinned to 4.1.3
protobuf: pip install without exact version
pg_view: pulled from moving Git master
base image: mutable ubuntu:22.04 tag
postgres UID/GID: not hard-coded in inspected Spilo source
```

The source generates both Patroni REST and PostgreSQL `connect_address` values from its discovered instance IP when explicit values are absent. Because each host's own name can resolve to both `127.0.1.1` and its `10.104.0.x` address, the deployment must set `RESTAPI_CONNECT_ADDRESS` and `PG_CONNECT_ADDRESS` explicitly per node to the east-west address.

DCS compatibility check: **PASS**. The pinned source lists `etcd3` as a supported Patroni DCS and generically parses `ETCD3_*` variables. `ETCD3_HOSTS` therefore produces the required Patroni `etcd3:` configuration for the existing etcd `3.5.15` v3 cluster. `ETCD_HOSTS` must not be used for this deployment because that prefix maps to Patroni's separate legacy `etcd:` configuration path.

The current upstream comparison image manifest was then inspected remotely without pulling or running the image:

```text
image: ghcr.io/zalando/spilo-18:4.1-p2
OCI index digest: sha256:258a87d34699387f3b6b45d30874c21c6b838ed51c9371ae2a70151d57137990
linux/amd64 manifest: sha256:cfd11c4e237777b03d9867bf53ae33a77980e1826c07d7c053de034dce695392
linux/arm64 manifest: sha256:7c3313a3860f2a95a24f165e4172927fceb693c9a8be25582fac6a9bde8a9bf4
additional unknown/unknown entries: attestation manifests tied to the architecture manifests
Docker buildx: v0.36.1
```

The active DigitalOcean hosts are x86-64, so `sha256:cfd11c4e237777b03d9867bf53ae33a77980e1826c07d7c053de034dce695392` is the runnable comparison manifest relevant to this deployment. This is a discovery/pinning checkpoint only and is **not yet an approved deployment digest**.

The exact amd64 manifest was then pulled on `ulc-03` using the digest, with no Spilo container started and no `/srv/spilo` mount. The pull reported the expected digest and `docker ps` remained unchanged with only the healthy etcd container running.

Observed image metadata/evidence:

```text
logical image size: 628727591 bytes
root filesystem before pull: about 2.8G used
root filesystem after pull: about 4.9G used
PATRONIVERSION environment: 4.1.0
PATH includes: /usr/lib/postgresql/18/bin
PGROOT: /home/postgres/pgdata/pgroot
PGDATA: /home/postgres/pgdata/pgroot/data
image label org.opencontainers.image.version: 22.04
explicit Config.User field: absent
```

The initial formatted `docker image inspect` command stopped with `map has no entry for key "User"`; this is a template/key-presence issue, not proof of an image failure or runtime UID. Runtime identity still requires disposable-container inspection.

Important evidence boundary: the later pinned source commit `95139b4...` declares Patroni `4.1.3`, while this published `spilo-18:4.1-p2` image declares `PATRONIVERSION=4.1.0`. Therefore the source checkout and published binary are **not interchangeable evidence**. Do not infer binary package versions from the source commit.

A disposable network-isolated content inspection was then run against the exact pulled digest with a read-only root filesystem, all Linux capabilities dropped, `no-new-privileges`, no persistent mounts, and `/bin/bash` overriding the normal Spilo entrypoint. The live etcd container remained the only running service before and after.

Observed contents:

```text
OS: Ubuntu 22.04.5 LTS
container identity with overridden entrypoint: root
postgres account: UID 101, GID 103
PostgreSQL: 18.3 (Ubuntu 18.3-1.pgdg22.04+1)
Patroni: 4.1.0
TimescaleDB PG18 loader package: 2.26.2
TimescaleDB PG18 OSS package: 2.26.2
TimescaleDB control default_version: 2.26.2
TimescaleDB Toolkit control file: absent
PGROOT: /home/postgres/pgdata/pgroot
PGDATA: /home/postgres/pgdata/pgroot/data
PGHOME: /home/postgres
```

The image also carries PostgreSQL 14-17 binaries/extensions and older TimescaleDB shared libraries for compatibility, but PostgreSQL 18.3 is first on PATH and the PostgreSQL 18 control file selects TimescaleDB 2.26.2.

Content-inspection result: **PASS**.

The exact published image was then tested again with networking disabled and no persistent mounts. Patroni reported `4.1.0`, Python package metadata also reported `4.1.0`, `patroni.dcs.etcd3` imported successfully, and the included Spilo configurator listed `etcd3` plus the generic `ETCD3_*` parser. Exact-image DCS compatibility: **PASS**.

A disposable PostgreSQL runtime test then initialized PostgreSQL `18.3` under `/tmp`, started it with `shared_preload_libraries=timescaledb`, created the TimescaleDB extension successfully, and reported extension version `2.26.2`. The live service set remained unchanged with etcd only. During extension startup an internal TimescaleDB job logged `functionality not supported under the current "apache" license`; record this as an Apache-only capability boundary, not as a PostgreSQL startup failure.

The hypertable probe did **not** complete because the shell quoting in the test command stripped the SQL string literals and PostgreSQL received `create_hypertable(sensor_probe, by_range(ts))`. PostgreSQL correctly treated `sensor_probe` as an unresolved column and aborted that statement. This is a test-command error, so hypertable support remains **UNPROVEN**, not failed.

A first attempt to rerun the corrected disposable hypertable/retention capability test on `ulc-03` produced only the before/after `docker ps` output and none of the expected `INITDB`, PostgreSQL, or SQL markers. The pasted command text looked mangled, but the later review identified the more specific execution defect: the `docker run` invocation expected `bash -s` to read the here-document from stdin but did not include Docker's `-i` / `--interactive` option. Without `-i`, stdin was not kept attached to the container and `bash -s` received EOF. Classify this attempt as **INCONCLUSIVE / test-delivery defect**, not as a PostgreSQL or TimescaleDB failure. The live service set remained unchanged with only etcd running before and after.

A local replacement test script was then created as `/home/opsadmin/spilo-hypertable-test.sh`, mode `0700`, and verified before execution. `bash -n` returned PASS. Captured SHA-256:

```text
30716e0483f2fcd8a33b6247c2ef2d6065eba8d6595aed590cd7714f185feb5c
```

The numbered script review confirms the critical SQL is intact, including `SELECT create_hypertable('sensor_probe', by_range('ts'));`, the test row uses `'test-device'`, and the verification queries target `timescaledb_information.hypertables` plus `pg_extension`. Script-verification checkpoint: **PASS**.

The verified script was then executed against the exact immutable amd64 image using `docker run --rm -i` with `--network none`, read-only root filesystem, all capabilities dropped, `no-new-privileges`, no persistent mounts, UID/GID `101:103`, and a disposable `/tmp` PostgreSQL data directory. The pre-run SHA-256 check passed.

Observed result:

```text
PostgreSQL 18.3 initdb/start: PASS
TimescaleDB 2.26.2 CREATE EXTENSION: PASS
sensor_probe CREATE TABLE: PASS
create_hypertable('sensor_probe', by_range('ts')): PASS -> (1,t)
insert test-device / 42.5: PASS
readback test-device / 42.5: PASS
timescaledb_information.hypertables: public.sensor_probe, 1 dimension
pg_extension: timescaledb 2.26.2
clean PostgreSQL shutdown: PASS
wrapper exit: TEST_RC=0
live services before/after: etcd only, unchanged
```

During startup, the same internal TimescaleDB background job emitted `functionality not supported under the current "apache" license`. Because the extension, hypertable, insert/read, catalog verification, and clean shutdown all passed, this message is recorded as a **separate Apache-only feature/capability warning**, not a failure of the core TimescaleDB path.

Core PostgreSQL 18.3 + TimescaleDB 2.26.2 hypertable capability: **PASS**.

Next: keep persistent Spilo/Patroni bootstrap blocked while the Apache-only optional-feature boundary is checked separately. The cloud HA POC does not enable destructive retention, but the wider TimescaleDB documentation advertises retention/compression options; probe only the specific optional capabilities the project documents, then decide whether this immutable digest can be approved for the POC with an explicit feature boundary or must be replaced.

A dedicated retention capability script was then created on `ulc-03` as `/home/opsadmin/spilo-retention-capability-test.sh`, mode `0700`, and reviewed before execution. `bash -n` returned PASS. Captured SHA-256:

```text
d0f8abacfae4b8ba1bec93d944f0c9179591bab482d214ae19d7cdf28d44c534
```

The numbered review confirms the exact retained SQL is `SELECT add_retention_policy('sensor_probe', INTERVAL '30 days');`, with the return code captured independently so an unsupported optional capability is reported as a capability limit rather than confused with a core PostgreSQL/TimescaleDB failure. Retention-script verification checkpoint: **PASS**.

The verified retention script was then executed through the same immutable Spilo amd64 image with `docker run --rm -i`, `--network none`, no persistent mounts, read-only root filesystem, UID/GID `101:103`, and disposable `/tmp` PGDATA. The pre-run SHA-256 check passed and the live service set remained the existing etcd container only before and after.

Observed result:

```text
PostgreSQL 18.3 startup: PASS
TimescaleDB 2.26.2 extension: PASS
sensor_probe hypertable creation: PASS
add_retention_policy('sensor_probe', INTERVAL '30 days'): FAIL - unsupported under current apache license
RETENTION_RC=1
probe wrapper TEST_RC=0
live etcd before/after: unchanged
```

The exact server error was `function "add_retention_policy" is not supported under the current "apache" license`, with a hint to use the Timescale-licensed feature set. Classify this as a **confirmed optional-feature capability limit**, not a PostgreSQL, Patroni, or core TimescaleDB failure. The wrapper returned zero intentionally because it distinguishes an unsupported optional capability from a broken database runtime.

Retention-policy API for this immutable Apache-only image: **NOT AVAILABLE**. Core hypertables remain **PASS**. The cloud HA POC intentionally keeps destructive retention disabled, so this does not block the narrow POC database path; however, the wider TimescaleDB manuals must not claim this digest provides retention-policy automation.

A read-only inspection of the same immutable image then confirmed that TimescaleDB 2.26.2 ships SQL definitions for `compress_chunk`, `decompress_chunk`, `add_compression_policy`, `remove_compression_policy`, and `add_columnstore_policy`, with native TimescaleDB 2.26.2 shared objects present. This proves that the compression/columnstore API definitions exist in the installed extension files, but **does not prove they are executable under the Apache-only license**. Runtime compression capability therefore remains UNPROVEN and requires one disposable SQL probe before final image approval. The live service inventory before and after this file inspection remained etcd only.

A dedicated compression capability script was then created on `ulc-03` as `/home/opsadmin/spilo-compression-capability-test.sh`, mode `0700`, and reviewed before execution. `bash -n` returned PASS. Captured SHA-256:

```text
cbe10380a642ff0ddc82f7c0ff1c8fe570c712a6ff15583880382c3cb0856289
```

The numbered review confirms that the script creates a 1-day TimescaleDB hypertable, inserts old and current rows, attempts `ALTER TABLE ... SET (timescaledb.compress, timescaledb.compress_segmentby = 'device_id')`, captures `ENABLE_COMPRESSION_RC`, attempts `compress_chunk()` on an old chunk only when compression enabling succeeds, captures `COMPRESS_CHUNK_RC`, verifies the chunk state, and separately captures the result of `add_compression_policy(..., INTERVAL '7 days')` as `COMPRESSION_POLICY_RC`. Compression-script verification checkpoint: **PASS**.

The verified compression script was then executed through the same immutable Spilo amd64 image with `docker run -i`, `--network none`, no persistent mounts, read-only root filesystem, UID/GID 101:103, and disposable `/tmp` PGDATA. PostgreSQL 18.3 and TimescaleDB 2.26.2 started successfully; a one-day `sensor_probe` hypertable was created with three chunks; then `ALTER TABLE ... SET (timescaledb.compress, timescaledb.compress_segmentby = 'device_id')` failed under the current Apache license with `ENABLE_COMPRESSION_RC=1`. Because compression could not be enabled, no manual `compress_chunk()` call was attempted. `add_compression_policy('sensor_probe', INTERVAL '7 days')` also failed under the current Apache license with `COMPRESSION_POLICY_RC=1`. The wrapper completed with `TEST_RC=0` by design and the live etcd container remained unchanged before and after.

Compression runtime capability for this immutable Apache-only image: **NOT AVAILABLE**. Retention automation is also **NOT AVAILABLE**. Core PostgreSQL 18.3 + TimescaleDB 2.26.2 hypertables remain **PASS**.

Decision boundary: accept this exact amd64 digest as the **functional Spilo candidate for the narrow HA POC**, because the POC requires PostgreSQL/Patroni plus core TimescaleDB hypertables and intentionally leaves destructive retention/compression disabled. Do **not** present it as a full-feature TimescaleDB image for the wider integration manuals. Final deployment approval remains blocked on the separate image-security/provenance gate; do not create persistent Spilo storage or connect Patroni to live etcd until that gate is closed.

Scanner availability checkpoint on `ulc-03`: `docker scout` is not available, and Trivy, Grype, Syft, and Cosign are not installed. The exact Spilo amd64 image remains present locally as image ID `sha256:cfd11c4e237777b03d9867bf53ae33a77980e1826c07d7c053de034dce695392` (reported size 628727591 bytes, linux/amd64), and the live container set remains etcd only. Do not install a scanner package blindly on this 2 GiB production node. Prefer an official scanner container pinned by immutable digest and scan the immutable Spilo digest from the remote registry without mounting `/var/run/docker.sock`; this avoids granting a scanner control of the Docker daemon and keeps the security gate separate from the running cluster.

## 2026-08-22 - Patched Spilo private-registry and pre-bootstrap preparation

The security-hardened patched image was published to the selected private GHCR repository:

```text
ghcr.io/jervis-org/spilo/spilo-18-walg309-ospatched:v1
```

The push completed with registry index digest:

```text
sha256:6bf45913616f2e524555973bfdd34bae1607a709dc3548ab25c8b32a454a9519
```

`docker buildx imagetools inspect` showed a runnable `linux/amd64` manifest plus an associated `unknown/unknown` attestation manifest. The latter is metadata, not a second database platform.

The private image was then pulled/inspected on `ulc-01`, `ulc-02`, and `ulc-03`. All three returned the same GHCR repository digest. Private-registry distribution: **PASS**.

Persistent storage was prepared on all three nodes:

```text
/srv/spilo/pgroot
numeric owner: 101:103
mode: 0700
```

The host account names shown for those numeric IDs may differ from the container's `postgres` name. Numeric verification with `ls -ldn` is authoritative. Storage ownership: **PASS**.

The three nodes also received `/etc/lorawan-cloud/spilo/spilo.env` with `root:root` ownership and mode `0600`. Node-specific PostgreSQL/Patroni connect addresses correctly use `10.104.0.2`, `10.104.0.4`, and `10.104.0.8`.

Bootstrap remains **BLOCKED** for two reasons discovered during review:

1. the first environment-file draft generated independent superuser, replication, and admin passwords on each node; the HA cluster must instead use one shared secret per role across all three members; and
2. the draft secret values were exposed in terminal screenshot evidence, so they are considered compromised and must be replaced before use.

Do not record the exposed values in this repository. Generate new values, keep one secret per role consistent across the three members, and verify consistency without printing the secret text.

Credential correction checkpoint - 2026-08-22: the operator confirmed the exposed draft role passwords were replaced and the replacement superuser, standby, and admin role secrets are now consistent across `ulc-01`, `ulc-02`, and `ulc-03`. The actual secret values are deliberately not recorded here.

TLS variable support checkpoint - 2026-08-22: a disposable, network-isolated, read-only inspection of the exact private-registry digest confirmed that `/scripts/configure_spilo.py` consumes `SSL_CA_FILE`, `SSL_CERTIFICATE_FILE`, `SSL_PRIVATE_KEY_FILE`, `ALLOW_NOSSL`, `PG_CONNECT_ADDRESS`, and `RESTAPI_CONNECT_ADDRESS`. The locale warning from `/bin/bash` during this inspection did not affect that TLS source inspection, but later first-bootstrap evidence showed the missing `en_US` locale is operationally significant for `initdb`; do not treat the warning as globally harmless.

TLS file-handling checkpoint - 2026-08-22: inspection of `write_certificates()` confirmed that when `SSL_PRIVATE_KEY_FILE` already exists and Spilo is not run with overwrite/force behavior, Spilo logs that the private key already exists and returns before generating a dummy certificate or running the later chmod/owner adjustment. This supports pre-creating the PostgreSQL certificate files and mounting them read-only, provided the deployment does not request certificate overwrite.

The PostgreSQL internal root CA was then created on `ulc-03` at `/root/lorawan-pg-ca`. Verified state: CA directory `0700 root:root`, CA private key `0600 root:root`, CA certificate `0644 root:root`; subject and issuer are both `CN = LoRaWAN PostgreSQL Internal CA`; validity is 2026-08-22 through 2036-08-19; SHA-256 fingerprint is `99:00:4B:B3:2D:7D:78:FA:38:61:7C:78:89:6D:7A:7E:FF:9F:A6:10:FC:8F:07:D4:E2:5E:35:25:36:E6:CB:3E`. Root-CA creation: **PASS**.

PostgreSQL logical-name standardization checkpoint - 2026-08-22: the operator standardized the permanent private PostgreSQL verification name as `postgres-ha.internal`. Every PostgreSQL member certificate must include DNS SAN `postgres-ha.internal` plus that member's hostname and private `10.104.0.x` address. Future clients using `sslmode=verify-full` must use this exact logical name. Bootstrap remains blocked until the three unique server certificates are signed, installed, and verified.

PostgreSQL server-certificate issuance on `ulc-03` is now **PASS for all three members**. Each node has a unique RSA-3072 private key and CSR, while every certificate is signed by `CN = LoRaWAN PostgreSQL Internal CA` for 825 days and includes the stable logical SAN `DNS:postgres-ha.internal`.

- `ulc-01`: SANs `DNS:ulc-01`, `DNS:postgres-ha.internal`, `IP Address:10.104.0.2`; CA-chain, hostname, logical-hostname, and IP verification all returned `OK`; private-key/certificate DER public-key SHA-256 match `d0e32da1ec25bc716646afd1f061bbef38bae019f2d542a2f5337a173ffa29f0`.
- `ulc-02`: SANs `DNS:ulc-02`, `DNS:postgres-ha.internal`, `IP Address:10.104.0.4`; all four verification checks returned `OK`; private-key/certificate DER public-key SHA-256 match `333d66141bda84c787868df00d8ed66d099491350577139b52af85f6d8d95ccf`.
- `ulc-03`: SANs `DNS:ulc-03`, `DNS:postgres-ha.internal`, `IP Address:10.104.0.8`; all four verification checks returned `OK`; private-key/certificate DER public-key SHA-256 match `6dc8915e0009b8a118fe3e6a1552229c7330cfb194a79f5a34ba455147e87e02`.

The CA private key remains only under `/root/lorawan-pg-ca` on `ulc-03`; it must **not** be distributed with the server certificates. The next phase is controlled installation of only `ca.crt`, the matching `server.crt`, and the matching `server.key` on each member. PostgreSQL/Patroni bootstrap remains blocked until the installed files and permissions are verified on all three hosts.

Certificate-transfer checkpoint - 2026-08-22: protected transfer copies for `ulc-01` and `ulc-02` were created under `/home/opsadmin/pg-cert-transfer` on `ulc-03`; private keys are mode `0600` and public certificates are mode `0644`. The first direct `scp` attempt from `ulc-03` to `opsadmin@10.104.0.2` reached the SSH service and accepted the host ED25519 fingerprint, but authentication failed with `Permission denied (publickey)`. No certificate files were transferred. This is an SSH-identity issue, not a VPC or certificate problem: the `opsadmin` login is authorized by a separate workstation/device Ed25519 identity, and that private key is intentionally not present on `ulc-03`. Do not copy the workstation administration private key onto a server. Use a short-lived dedicated transfer identity or the trusted administration workstation for the certificate copy, then remove the temporary authorization after installation is verified.

Temporary transfer-identity checkpoint - 2026-08-22: a dedicated Ed25519 key `~/.ssh/pg-cert-transfer` was authorized temporarily for `opsadmin` on `ulc-01` and `ulc-02`. From `ulc-03`, SSH with `-i ~/.ssh/pg-cert-transfer -o IdentitiesOnly=yes` returned hostname `ulc-01` from `10.104.0.2` and hostname `ulc-02` from `10.104.0.4`. Temporary transfer authentication is therefore **PASS** for both remote nodes. After the installed certificate bundles passed verification, the operator confirmed that the temporary transfer key/authorization and transfer copies were cleaned up. Cleanup status: **operator-confirmed PASS**; no private-key material is recorded in this repository.

PostgreSQL TLS installation checkpoint - 2026-08-22: `ulc-01`, `ulc-02`, and `ulc-03` each verified the installed `/etc/lorawan-pki/postgres` bundle. Directory mode is `0750` numeric owner/group `0:103`; `ca.crt` and `server.crt` are `0644 0:0`; `server.key` is `0600 101:103`. Every node verified the common CA fingerprint `99:00:4B:B3:2D:7D:78:FA:38:61:7C:78:89:6D:7A:7E:FF:9F:A6:10:FC:8F:07:D4:E2:5E:35:25:36:E6:CB:3E`, CA chain, node hostname, `postgres-ha.internal`, private VPC IP, expected SANs, and matching installed key/certificate public-key hashes. Installed TLS state is **PASS on all three nodes**. PostgreSQL/Patroni remains intentionally stopped.

PGROOT/PGDATA exact-image checkpoint - 2026-08-22: a disposable read-only `ulc-03` probe started the immutable Spilo image with only `PGROOT=/home/postgres/pgroot` overridden. The effective environment became `PGROOT=/home/postgres/pgroot` while `PGDATA` remained the baked `/home/postgres/pgdata/pgroot/data`. Inspection of `configure_spilo.py` showed that environment values are loaded before `placeholders.setdefault('PGROOT', ...)` and `placeholders.setdefault('PGDATA', ...)`; therefore changing only `PGROOT` does **not** recompute an already-present baked `PGDATA`. The old custom path plan is rejected before bootstrap. Standardize on the image-native pair `PGROOT=/home/postgres/pgdata/pgroot`, `PGDATA=/home/postgres/pgdata/pgroot/data`, and bind `/srv/spilo/pgdata:/home/postgres/pgdata`.

Old-storage emptiness checkpoint - 2026-08-22: `ulc-01`, `ulc-02`, and `ulc-03` each showed `/srv/spilo/pgroot` with numeric ownership `101:103` and returned `PGROOT EMPTY - PASS` from an independent `find -mindepth 1` check. PostgreSQL/Patroni had still never been bootstrapped, so the superseded directory was removed with `rmdir` on each node. `/srv/spilo/pgdata` was then created on all three nodes as mode `0700` numeric `101:103`; every node returned `Old pgroot removed: PASS`. Native host-storage migration: **PASS**.

Environment-path migration checkpoint - 2026-08-22: the protected `/etc/lorawan-cloud/spilo/spilo.env` on `ulc-01`, `ulc-02`, and `ulc-03` was updated from the unsafe custom-path state to the exact-image native pair `PGROOT=/home/postgres/pgdata/pgroot` and `PGDATA=/home/postgres/pgdata/pgroot/data`. Sanitized verification preserved `SCOPE=lorawan-postgres-ha`, `PGVERSION=18`, and at that checkpoint the literal `ALLOW_NOSSL=false` value; the latter was later rejected by the exact-image Mustache semantic check because any non-empty string is truthy. The files remain mode `0600` numeric `0:0`. Node-specific addresses are still correct: `ulc-01` `10.104.0.2:5432` / `10.104.0.2:8008`, `ulc-02` `10.104.0.4:5432` / `10.104.0.4:8008`, and `ulc-03` `10.104.0.8:5432` / `10.104.0.8:8008`. Storage and environment paths are aligned end-to-end; the TLS-policy value still requires the explicit empty-string correction before bootstrap.

Patroni member-name exact-image checkpoint - 2026-08-22: disposable source inspection found no `PATRONI_NAME` reference in `/scripts/configure_spilo.py`. The Patroni template renders `name: '{{instance_data.id}}'`, and `get_instance_metadata()` initializes `instance_data.id` from `socket.gethostname()`. With `SPILO_PROVIDER` unset, `get_provider()` attempts cloud metadata and falls back to the local-Docker provider when metadata is unavailable. The disposable container reported default `HOSTNAME=f895bcfe6e37`, i.e. a transient Docker container ID. Therefore the default container identity is **unsafe for Patroni membership** because recreation could change the member name. Candidate deterministic fix: explicitly set `SPILO_PROVIDER=local` and pin the container hostname per node to `ulc-01`, `ulc-02`, or `ulc-03`; this exact combination must be proven in a disposable container before final Compose and bootstrap. Do not add a guessed `PATRONI_NAME`. PostgreSQL/Patroni remains stopped.

Member-identity probe corrections and final PASS - 2026-08-22: the first direct Python probe used `importlib.util.spec_from_file_location()` to load `/scripts/configure_spilo.py` and failed before calling any Spilo function with `ModuleNotFoundError: No module named 'spilo_commons'`. Repeating with `/scripts` on `PYTHONPATH` fixed the import path, but `get_instance_metadata()` then failed while resolving the pinned hostname under deliberate `--network none`, returning `socket.gaierror: [Errno -3] Temporary failure in name resolution`. Neither failure reached PostgreSQL, Patroni, etcd, or persistent storage. A third isolated probe kept `--network none`, `--read-only`, all capabilities dropped, `no-new-privileges`, `--hostname ulc-03`, and `SPILO_PROVIDER=local`, and monkey-patched only `getaddrinfo()` to return a fake loopback IP while leaving the real `socket.gethostname()` call untouched. The exact immutable image returned `provider = local`, `socket.gethostname() = ulc-03`, `instance_data.id = ulc-03`, and the deliberately fake `instance_data.ip = 127.0.0.1`. Deterministic Patroni member naming is therefore **PASS**: final Compose must pin `hostname:` to the physical node name and set `SPILO_PROVIDER=local`; explicit VPC `PG_CONNECT_ADDRESS` and `RESTAPI_CONNECT_ADDRESS` remain the advertised service addresses.

Compose env-file checkpoint - 2026-08-22: all three protected `spilo.env` files received exactly one `SPILO_PROVIDER`, TLS file path, PGROOT/PGDATA, connect-address, `ETCD3_HOSTS`, and `ALLOW_NOSSL` entry, with file mode still `0600 0:0`. Sanitized values were correct. The first `docker compose ... config --quiet` attempt failed identically on all three nodes at `spilo.env` line 12 with `unexpected character ','` while reading `ETCD3_HOSTS`. Root cause: the value was written using shell-style adjacent quoted fragments (`"host1","host2","host3"`), which is not valid Docker Compose dotenv syntax because the first double quote closes before the comma. The env file was corrected to wrap the complete Spilo host-list representation in outer single quotes: `ETCD3_HOSTS='"10.104.0.2:2379","10.104.0.4:2379","10.104.0.8:2379"'`. After that correction, `docker compose ... config --quiet` returned `Compose syntax: PASS` on `ulc-01`, `ulc-02`, and `ulc-03`. A sanitized `docker compose config --format json` check on every node reported the service environment value exactly as `"10.104.0.2:2379","10.104.0.4:2379","10.104.0.8:2379"`. Compose dotenv decoding is therefore **PASS on all three nodes**.

Exact-image DCS parser inspection - 2026-08-22: read-only inspection of the immutable image confirmed `PATRONI_DCS = ('kubernetes', 'zookeeper', 'exhibitor', 'consul', 'etcd3', 'etcd')`. The generic DCS environment parser splits the variable name at the first underscore with `dcs, param = name.lower().split('_', 1)` and recognizes `etcd3`. For any `*_HOSTS` value, the exact code first checks whether the string already starts with `-` or contains `[`. If neither is true, it wraps the string with `[{0}]` and only then calls `yaml.safe_load(value)`. The current Compose-decoded value `"10.104.0.2:2379","10.104.0.4:2379","10.104.0.8:2379"` therefore is intentionally not standalone YAML; inside the real Spilo function it should first become `["10.104.0.2:2379","10.104.0.4:2379","10.104.0.8:2379"]` and then decode to a Python list. A direct `yaml.safe_load()` probe confirmed the unwrapped string raises `ParserError`, while the bracketed candidate decodes to exactly three endpoint strings. The first isolated `get_dcs_config()` call then failed with `KeyError: 'NAMESPACE'` at line 784 because the test dictionary supplied only `ETCD3_HOSTS`. Normal Spilo placeholder preparation sets `NAMESPACE` before this function runs, defaulting it to `default` when no pod namespace is present, so this is a probe-harness omission rather than evidence of a deployed configuration failure. PostgreSQL/Patroni and persistent storage remained untouched. The corrected read-only probe supplied the normal `NAMESPACE=default` placeholder and called the exact immutable image's `get_dcs_config()` with the deployed Compose-decoded value. It returned `{'etcd3': {'hosts': ['10.104.0.2:2379', '10.104.0.4:2379', '10.104.0.8:2379']}}`; `hosts` was a Python list of exactly three strings and each endpoint matched the intended east-west member. `ETCD3_HOSTS` exact Spilo parser gate: **PASS**. The deployed environment value remains unchanged. PostgreSQL/Patroni remains stopped; next gate is the final live pre-bootstrap check of etcd health, free `5432/8008` listeners, empty `/srv/spilo/pgdata`, validated Compose, and the immutable image before bootstrapping `ulc-01` alone.

Final live PostgreSQL/Patroni pre-bootstrap checkpoint - 2026-08-22: **PASS on all three nodes** for etcd health, listeners, storage emptiness, TLS file state, Compose structure, per-node identity, logging bounds, and immutable image selection. `ulc-01`, `ulc-02`, and `ulc-03` each had only the existing etcd container running. Every host reached all three etcd `3.5.15` endpoints successfully; endpoint status showed one leader (`10.104.0.4` at this checkpoint), two followers, no learners, matching Raft term/index `2/26`, and no errors. Ports `5432` and `8008` were free everywhere. `/srv/spilo/pgdata` was mode `0700` numeric `101:103` and empty on every node. PostgreSQL TLS files retained the expected `0750 0:103`, `0644 0:0`, `0644 0:0`, and `0600 101:103` permissions. `docker compose ... config --quiet` passed on all three nodes; each Compose file pinned the correct physical hostname, host networking, bounded `json-file` rotation (`10m` x `5`), two-minute stop grace period, and the immutable jervis-org OCI index digest `sha256:6bf45913616f2e524555973bfdd34bae1607a709dc3548ab25c8b32a454a9519`. `ulc-03` also retains extra local RepoDigest aliases for the same content digest, including an old `smart-agri` name; this is not selected by Compose and is not a bootstrap blocker, but can be cleaned after the cluster is stable to reduce operator ambiguity.

`ALLOW_NOSSL` exact-image security semantic checkpoint - 2026-08-22: **PASS after correction on all three nodes.** Exact source inspection showed the Spilo Patroni template uses both `{{#ALLOW_NOSSL}}` and inverted `{{^ALLOW_NOSSL}}` Mustache sections, while the image's default is `placeholders.setdefault('ALLOW_NOSSL', '')`. The isolated Pystache test returned `string_false value = 'false' => TRUE_BRANCH`, `empty_string value = '' => FALSE_BRANCH`, and boolean `False => FALSE_BRANCH`. Therefore the earlier non-empty string `ALLOW_NOSSL=false` was rejected and replaced with the explicit empty value `ALLOW_NOSSL=` on `ulc-01`, `ulc-02`, and `ulc-03`. Every node then reported exactly one `ALLOW_NOSSL` entry, `Compose syntax: PASS`, effective `ALLOW_NOSSL = ''`, and `ALLOW_NOSSL empty-string policy: PASS`. This falsey value renders `hostnossl all all all reject` plus the catch-all `hostssl all all all md5` branch. PostgreSQL/Patroni remains stopped.

Exact-image listener-bind checkpoint - 2026-08-22: **BLOCKING correction required before bootstrap.** Read-only inspection of `/scripts/configure_spilo.py` in the immutable image proved that the generated Patroni template uses `restapi.listen: ':{{APIPORT}}'` and `postgresql.listen: '*:{{PGPORT}}'`. The same template separately uses `RESTAPI_CONNECT_ADDRESS` and `PG_CONNECT_ADDRESS` as `connect_address` values. Therefore the already-pinned `10.104.0.x` connect addresses advertise the correct east-west endpoints but do **not** restrict the sockets themselves. With Compose `network_mode: host`, the wildcard listeners would cover every host interface; whether the public ports are reachable from the Internet still depends on external firewall policy, but the service binding itself is too broad for the intended design. PostgreSQL/Patroni remains stopped.

`SPILO_CONFIGURATION` precedence checkpoint - 2026-08-22: **override mechanism proven; render/application still blocked.** The exact immutable image was inspected with `--network none`, read-only root filesystem, all capabilities dropped, `no-new-privileges`, and no persistent mounts. `/scripts/configure_spilo.py` YAML-decodes `SPILO_CONFIGURATION` (falling back to `PATRONI_CONFIGURATION`) into `user_config`, rejects non-dictionary input, copies it, then executes `config = deep_update(user_config_copy, config)`. The exact `deep_update(a, b)` implementation recursively merges dictionaries, keeps list `a` when both sides are lists, and for scalar conflicts returns `a` when it is not `None`. Because `a` is the user configuration, user-supplied `restapi.listen` and `postgresql.listen` values take precedence over the generated wildcard defaults while unspecified generated settings remain intact. This proves `SPILO_CONFIGURATION` is a valid supported path for the listener correction. The first isolated merge/render probe then failed only at the diagnostic line `merged["name"]` with `KeyError: 'name'` after printing `provider = local`; it had not yet printed the listener fields. The corrected read-only probe inspected the template and proved the member identity is nested at `postgresql.name: '{{instance_data.id}}'`, not top-level `name`. With container hostname `ulc-03`, `instance_data.id` rendered as `ulc-03`. The same corrected exact-image merge then printed and asserted `restapi.listen = 10.104.0.8:8008`, `restapi.connect_address = 10.104.0.8:8008`, `postgresql.listen = 10.104.0.8:5432`, `postgresql.connect_address = 10.104.0.8:5432`, and `etcd3.hosts = ['10.104.0.2:2379', '10.104.0.4:2379', '10.104.0.8:2379']`, finishing with `LISTENER OVERRIDE RENDER: PASS`. Therefore the listener override and exact in-memory merge are **PASS**. PostgreSQL/Patroni remains stopped and no persistent mounts were used. The Docker Compose dotenv encoding gate is now **PASS**. On `ulc-03`, a temporary env file containing `SPILO_CONFIGURATION='{"restapi":{"listen":"10.104.0.8:8008"},"postgresql":{"listen":"10.104.0.8:5432"}}'` and a temporary Compose file both validated successfully; `docker compose config --format json` returned the exact compact JSON string, JSON decoding produced `restapi.listen = 10.104.0.8:8008` and `postgresql.listen = 10.104.0.8:5432`, and the probe finished with `SPILO_CONFIGURATION dotenv encoding: PASS`. Temporary files were under `mktemp` storage with a cleanup trap, no live `/etc/lorawan-cloud/spilo/spilo.env` was modified by the probe, and PostgreSQL/Patroni remained stopped. The next listener step is to apply the equivalent per-node value to each protected env file and verify the Compose-decoded value on all three nodes.

Live listener-override application checkpoint - 2026-08-22: **PASS on all three nodes.** The protected `/etc/lorawan-cloud/spilo/spilo.env` on each member now contains exactly one `SPILO_CONFIGURATION` value with the listener addresses mapped from the physical hostname: `ulc-01` uses `10.104.0.2:8008` and `10.104.0.2:5432`, `ulc-02` uses `10.104.0.4:8008` and `10.104.0.4:5432`, and `ulc-03` uses `10.104.0.8:8008` and `10.104.0.8:5432`. `docker compose ... config --quiet` returned `Compose syntax: PASS` on every node, and sanitized JSON decoding returned `LIVE LISTENER OVERRIDE: PASS` on every node. The stray `jervis128662120269.: command not found` shown after the `ulc-03` PASS occurred at the shell prompt after the validation had completed and is not part of the Compose/Spilo test. The wildcard-listener security blocker is therefore closed. PostgreSQL/Patroni remains stopped while the conservative 2-GiB bootstrap parameter path is proven.

2-GiB bootstrap-tuning source checkpoint - 2026-08-22: exact immutable-image inspection shows `/scripts/configure_spilo.py` reads cgroup v1 `memory.limit_in_bytes` or cgroup v2 `memory.max`, caps that against host physical memory, and for the local provider computes `postgresql.parameters.shared_buffers` as one quarter of detected memory. It also computes `postgresql.parameters.max_connections = min(max(100, int(os_memory_mb/30)), 1000)`, so a ~2-GiB node would default to a much larger shared buffer allocation and at least 100 connections unless overridden. The generated `bootstrap.dcs.postgresql.parameters` template explicitly carries `max_connections`, while the generated local `postgresql.parameters` section explicitly carries `shared_buffers`; the inspected template does not explicitly include `work_mem` or `maintenance_work_mem`. Since `SPILO_CONFIGURATION` has already been proven to deep-merge user dictionaries without discarding user-only nested keys, the planned correction is to provide the same conservative values (`max_connections=40`, `shared_buffers=128MB`, `work_mem=2MB`, `maintenance_work_mem=32MB`) under both `bootstrap.dcs.postgresql.parameters` and local `postgresql.parameters`.

2-GiB bootstrap-tuning render checkpoint - 2026-08-22: **PASS in the exact immutable image.** The read-only isolated probe on `ulc-03` first showed the generated defaults before override: local `shared_buffers = 491MB` and bootstrap `max_connections = 100`. It then deep-merged the intended combined `SPILO_CONFIGURATION`. The resulting local `postgresql.parameters` and `bootstrap.dcs.postgresql.parameters` each contained `max_connections = 40`, `shared_buffers = 128MB`, `work_mem = 2MB`, and `maintenance_work_mem = 32MB`. The already-proven private listeners also remained `restapi.listen = 10.104.0.8:8008` and `postgresql.listen = 10.104.0.8:5432`. The probe finished with `2-GIB BOOTSTRAP TUNING RENDER: PASS`. No persistent mounts were used and PostgreSQL/Patroni remained stopped. The subsequent isolated Docker Compose dotenv test on `ulc-03` also **PASSed** with the larger combined JSON: `docker compose ... config --quiet` succeeded, decoded listeners were `10.104.0.8:8008` and `10.104.0.8:5432`, and both decoded parameter maps exactly matched `max_connections = 40`, `shared_buffers = 128MB`, `work_mem = 2MB`, and `maintenance_work_mem = 32MB`. The probe ended with `2-GIB SPILO_CONFIGURATION dotenv: PASS`. Temporary files were isolated under `mktemp` and PostgreSQL/Patroni remained stopped. The subsequent live per-node replacement is **PASS on all three nodes**. `ulc-01`, `ulc-02`, and `ulc-03` each reported `SPILO_CONFIGURATION replacement: PASS`; `/etc/lorawan-cloud/spilo/spilo.env` remained mode `0600` numeric `0:0`; exactly one `SPILO_CONFIGURATION` entry was present; and `docker compose ... config --quiet` returned `Compose syntax: PASS`. Sanitized decoding preserved each node's private listeners (`10.104.0.2`, `10.104.0.4`, or `10.104.0.8` on ports `8008` and `5432`) and showed identical local plus bootstrap parameter maps: `max_connections=40`, `shared_buffers=128MB`, `work_mem=2MB`, and `maintenance_work_mem=32MB`. Every node finished with `LIVE 2-GIB SPILO CONFIGURATION: PASS`. The stray `jervis128662120269.: command not found` shown after the `ulc-03` PASS occurred at the shell prompt after validation completed and is unrelated to Spilo or Compose. PostgreSQL/Patroni remains stopped. The final last-state gate was then run on all three nodes and **PASSed**. On `ulc-01`, `ulc-02`, and `ulc-03`, the only running container was the existing etcd `3.5.15` member. Every node reached all three etcd endpoints successfully. Endpoint status was consistent across the hosts: `10.104.0.4:2379` was leader, `10.104.0.2:2379` and `10.104.0.8:2379` were followers, all three were non-learners, Raft term/index/applied index were `2/35/35`, and the error column was empty. Ports `5432` and `8008` were free on every host. `/srv/spilo/pgdata` was mode `0700` numeric `101:103` and empty on every host. `docker compose ... config --quiet` returned `Compose syntax: PASS` everywhere. **Final pre-bootstrap state: PASS.** First bootstrap was then started on `ulc-01` only; `ulc-02` and `ulc-03` remain stopped until the first member is validated as the initial Patroni/PostgreSQL primary.

First-bootstrap initiation checkpoint - 2026-08-22: `docker compose up -d` on `ulc-01` created and started the pinned Spilo container successfully. The immediate `docker compose ps` sample showed `spilo` `Up Less than a second`. The log sample was empty and `ss` showed no `5432/8008` listeners yet, which is expected to be inconclusive at sub-second startup rather than a failure. Persistent state creation had begun: `/srv/spilo/pgdata/pgroot`, `/srv/spilo/pgdata/pgroot/data`, and `/srv/spilo/pgdata/pgroot/pg_log` existed; `data` showed mode `0700`. Host account names displayed as `messagebus:uuidd` because Ubuntu maps numeric UID/GID `101:103` to unrelated host-side names; the next check must verify numeric ownership directly. **Bootstrap is in progress, not yet PASS.** Do not start `ulc-02` or `ulc-03` until `ulc-01` runtime logs, Patroni leadership, exact private listeners, PostgreSQL parameters, and TLS are validated.

First-bootstrap failure checkpoint - 2026-08-22: the follow-up runtime check on `ulc-01` showed the Spilo container itself still running with `RestartCount=0`, but Patroni's supervised process repeatedly failed during initial cluster creation. Patroni successfully contacted the three-member etcd cluster and identified itself as `ulc-01`; each bootstrap attempt reached `initdb`, which failed with `invalid locale name "en_US.UTF-8"`. Patroni then removed the initialize key after the failed attempt and backed off before retrying. PostgreSQL never opened `5432`, Patroni REST never opened `8008`, `pg_isready` returned no response, and the current `/srv/spilo/pgdata/pgroot/data` path was absent while `/srv/spilo/pgdata/pgroot` and `pg_log` remained numeric `101:103`. This is **not a successful cluster bootstrap**. The retry loop was then stopped cleanly on `ulc-01`: Compose reported the Spilo container `Exited (143)`, ports `5432/8008` were free, and `/srv/spilo/pgdata/pgroot` contained `data.failed` and `pg_log`, both numeric `101:103`. An etcd prefix query for `/service/lorawan-postgres-ha` returned no keys, so no visible Patroni cluster state remains under that prefix after the failed initialization attempts. Exact-image source inspection confirms the root cause: the template renders `locale: {{INITDB_LOCALE}}.UTF-8`, the placeholder defaults `INITDB_LOCALE` to `en_US`, and `locale -a` in the immutable image lists only `C`, `C.utf8`, and `POSIX`. The default therefore renders unavailable `en_US.UTF-8`, exactly matching the runtime failure. The probe environment reported `LANG=''`, `LANGUAGE=''`, and `LC_ALL=C.UTF-8`. Candidate correction `INITDB_LOCALE=C` renders `C.UTF-8` and is now **PROVEN** in the exact immutable image. A disposable, network-isolated, read-only-container test ran PostgreSQL `initdb 18.6` as numeric UID/GID `101:103` against a tmpfs-only `/tmp/pgtest` directory with `--encoding=UTF8 --locale=C.UTF-8 --data-checksums --no-sync`. Initialization completed successfully, `PG_VERSION=18`, and `postgresql.conf` wrote `lc_messages`, `lc_monetary`, `lc_numeric`, and `lc_time` as `C.UTF-8`. The probe ended with `C.UTF-8 PostgreSQL 18 initdb: PASS`. It also identified the final hardened image's current PostgreSQL binary as `18.6 (Ubuntu 18.6-1.pgdg22.04+2)`. Earlier `18.3` entries in this execution log are historical results from the upstream/candidate image before the Ubuntu package-upgrade hardening step; the final patched GHCR digest now runs PostgreSQL 18.6. The locale fix is therefore no longer speculative. Live deployment checkpoint - 2026-08-22: **PASS on all three nodes.** `ulc-01`, `ulc-02`, and `ulc-03` each retained `/etc/lorawan-cloud/spilo/spilo.env` at mode `0600` numeric `0:0`, contained exactly one `INITDB_LOCALE=C` entry, passed `docker compose config --quiet`, and decoded the effective service environment to exactly `INITDB_LOCALE = 'C'`; every node ended with `INITDB_LOCALE live value: PASS`. The stray `jervis128662120269.: command not found` after the `ulc-01` validation occurred at the shell prompt after the PASS and is unrelated to Spilo or Compose. Keep `ulc-02` and `ulc-03` stopped. Retry-cleanup checkpoint - 2026-08-22: **PASS on `ulc-01`.** The Spilo container was confirmed stopped/exited; active `/srv/spilo/pgdata/pgroot/data` was absent; the preserved failed initialization and its `pg_log` were moved without deletion to `/srv/spilo/bootstrap-failures/locale-en_US-20260822-135900/`; and the active `pgroot` then contained neither `data` nor `data.failed`. The archive directory is `0700 root:root`; preserved PostgreSQL-owned content remains numeric `101:103` although Ubuntu renders those IDs as host names such as `messagebus:uuidd`. The Patroni DCS prefix `/service/lorawan-postgres-ha` remained empty, ports `5432/8008` remained free, and Compose still resolved `INITDB_LOCALE = C`. The operator's gate finished with `ULC-01 RETRY CLEANUP GATE: PASS`. The next action is a force-recreate/start on `ulc-01` only so the new container is guaranteed to consume the corrected environment; immediately validate its effective `INITDB_LOCALE`, bootstrap logs, leadership, private listeners, PostgreSQL parameters, and TLS before permitting `ulc-02` or `ulc-03` to start.

First-primary retry checkpoint - 2026-08-22: the cleaned `ulc-01` Spilo service was force-recreated so the new container could not reuse the pre-fix environment. `docker inspect` showed `INITDB_LOCALE=C`. Patroni contacted etcd, identified itself as `ulc-01`, and `initdb` completed successfully with locale `C.UTF-8`, UTF-8 encoding, and data checksums. PostgreSQL 18.6 started and accepted local connections; Patroni REST became reachable in about 10 seconds. Runtime listeners were exactly `10.104.0.2:5432` for PostgreSQL and `10.104.0.2:8008` for Patroni, with no wildcard bind observed. SQL confirmed `pg_is_in_recovery=false`, `server_version=18.6 (Ubuntu 18.6-1.pgdg22.04+2)`, `max_connections=40`, `shared_buffers=128MB`, `work_mem=2MB`, `maintenance_work_mem=32MB`, `ssl=on`, and `lc_messages/lc_monetary/lc_numeric/lc_time=C.UTF-8`. Active `/srv/spilo/pgdata/pgroot/data` is mode `0700` numeric `101:103`. The `initdb` log still printed its own transient defaults (`max_connections=100`, `shared_buffers=128MB`), but the authoritative running settings are the verified Patroni/PostgreSQL values above. The post-bootstrap scripts emitted `LC_ALL=en_US.utf-8` warnings and fell back to `C`; they nevertheless completed enough for PostgreSQL readiness and are a separate environment-hygiene issue. **Do not yet mark the first primary fully validated:** the immediate `/patroni` JSON returned `role=primary` but also `cluster_unlocked=true`. Before starting replicas, recheck after the bootstrap cycle settles, prove the Patroni DCS leader key/lock is present and stable, and perform a real PostgreSQL `sslmode=verify-full` client handshake.

Primary DCS + TLS gate - 2026-08-22: **PASS on `ulc-01`.** After allowing Patroni to settle, `/patroni` reported `state=running`, `role=primary`, server version `180006`, scope `lorawan-postgres-ha`, member name `ulc-01`, and no `cluster_unlocked` flag. `GET /leader` and `GET /primary` both returned HTTP `200`. The etcd prefix contains the expected `config`, `initialize`, `leader`, `members/ulc-01`, and `status` keys; `/service/lorawan-postgres-ha/leader` resolves exactly to `ulc-01`. `patronictl list` shows the single current member `ulc-01` at `10.104.0.2` as `Leader`, `running`, timeline `1`. A real `sslmode=verify-full` PostgreSQL connection using logical certificate identity `postgres-ha.internal`, physical `hostaddr=10.104.0.2`, and `/run/postgres-certs/ca.crt` succeeded with TLS 1.3 and cipher `TLS_AES_256_GCM_SHA384`; SQL returned `server_addr=10.104.0.2/32` and `pg_is_in_recovery=false`. Recent Patroni logs repeatedly report `I am (ulc-01), the leader with the lock`. **DCS leader-lock and runtime TLS verification are closed.** Do not start a replica yet: the same bootstrap log contains Patroni 4.1.0 message `User creation is not be supported starting from v4.0.0. Please use "bootstrap.post_bootstrap" script to create users.` Before admitting `ulc-02`, verify that the configured standby/admin roles exist with the expected attributes, inspect the generated Patroni authentication section without exposing passwords, and confirm effective `pg_hba` is TLS-only for non-local clients. The recurring `LC_ALL=en_US.utf-8` warnings remain a non-blocking container-locale hygiene issue because the actual database locale is already `C.UTF-8` and runtime SQL/TLS are healthy.

Replication-role/generated-config checkpoint - 2026-08-22: **replication path PASS on `ulc-01`; admin-role semantics RESOLVED.** Runtime role inspection showed `postgres` as LOGIN/REPLICATION/SUPERUSER and `standby` as LOGIN/REPLICATION without superuser, `CREATEROLE`, or `CREATEDB`. Sanitized `/run/postgres.yml` inspection resolved `postgresql.authentication.replication.username=standby` and confirmed both replication and superuser passwords are configured, without printing them. Effective non-local HBA includes `hostssl replication standby all md5`, then `hostnossl all all all reject`, plus TLS-only catch-all rules; a real verify-full connection as `standby` succeeded with `tls=true`, and `patronictl list` plus `/leader` continued to show `ulc-01` as healthy leader. Therefore replica authentication is proven. The HBA is TLS-only for non-local traffic but remains broader than the documented final least-privilege target because its source is `all` and its auth token is `md5`; defer tightening until the HA members are stable so first-replica bootstrap is not mixed with an HBA redesign. Direct SQL showed `admin` exists with `LOGIN=false`, `REPLICATION=false`, `SUPERUSER=false`, `CREATEROLE=false`, `CREATEDB=true`, `INHERIT=true`, and no stored password; `cron_admin` is granted to `admin`. Exact-image source inspection explains the Patroni 4.1.0 warning and final role state. `configure_spilo.py` still emits the legacy `bootstrap.users` stanza for `PGUSER_ADMIN` with password/`createrole`/`createdb`, but Patroni 4.1.0 rejects that old user-creation path. `/scripts/post_init.sh` independently forces `admin` to `CREATEDB NOLOGIN NOCREATEROLE NOSUPERUSER NOREPLICATION INHERIT` (or creates `admin CREATEDB`) and grants `cron_admin` to it. Thus the live NOLOGIN role is intentional Spilo post-init behavior, not an incomplete human login. Do not convert it to LOGIN merely to consume `PGPASSWORD_ADMIN`; that protected value is effectively unused for this role in the current Patroni-4 bootstrap path. The Python subprobe intended to print the generated bootstrap-user shape produced no output because `docker exec` was invoked without interactive stdin, but the exact source plus live role/membership evidence is sufficient. `ulc-01` remained Leader/running with `/leader` HTTP `200`. First-replica admission (`ulc-02`) is now the next controlled step.

First-replica admission checkpoint - 2026-08-22: **PASS on `ulc-02`.** The admission gate first re-proved `ulc-01` still owned the Patroni leader endpoint (`/leader` HTTP `200`), all three etcd endpoints were healthy, `5432/8008` were free on `ulc-02`, `/srv/spilo/pgdata` was empty at mode `0700` numeric `101:103`, no stale DCS member key existed for `ulc-02`, and Compose syntax passed. Spilo was then force-recreated on `ulc-02` only. Docker reported hostname `ulc-02`, `INITDB_LOCALE=C`, running state, and `RestartCount=0`. Patroni logged `Lock owner: ulc-01; I am ulc-02`, `trying to bootstrap from leader 'ulc-01'`, `replica has been created using basebackup_fast_xlog`, and `bootstrapped from leader 'ulc-01'`. PostgreSQL became ready after approximately 15 seconds. Runtime listeners were exactly `10.104.0.4:5432` and `10.104.0.4:8008`. `patronictl list` showed `ulc-01` as `Leader/running` and `ulc-02` as `Replica/streaming`, both timeline `1`, with receive/replay LSN `0/3000060` and reported lag `0`. Local SQL on `ulc-02` confirmed `pg_is_in_recovery=true`, PostgreSQL `18.6`, `max_connections=40`, `shared_buffers=128MB`, `work_mem=2MB`, `maintenance_work_mem=32MB`, `ssl=on`, and replay LSN `0/3000060`. Active data paths were `/srv/spilo/pgdata` mode `0700 101:103`, `pgroot` mode `0755 101:103`, and `pgroot/data` mode `0700 101:103`. The one `pg_receivewal` `.partial` rename message occurred during clone startup; because Patroni subsequently reports streaming with zero lag, it is not classified as a replica failure at this checkpoint. The known `LC_ALL=en_US.utf-8` warnings also recur but did not prevent cloning or streaming. Keep `ulc-03` stopped. Next gate: verify `ulc-02` through a real `sslmode=verify-full` client connection and verify the primary-side `pg_stat_replication` row before admitting the second replica.

SSH-session drop investigation - 2026-08-22: **host/HA failure ruled out; operator-shell behavior is the likely cause.** The first attempt at the next `ulc-02` runtime gate was pasted directly into the interactive SSH login and began with `set -euo pipefail`; the SSH session then ended. After reconnecting, `ulc-02` still showed continuous uptime since `2026-08-20 05:55`, no recent kernel OOM/out-of-memory/killed-process evidence, about `536 MiB` memory used and about `1.4 GiB` available, Spilo `running` with `RestartCount=0`, and etcd still running. `patronictl list` continued to show `ulc-01` `Leader/running` and `ulc-02` `Replica/streaming`, with receive/replay LSN advanced to `0/3000168` and lag `0`. Therefore do not count the SSH drop as a 2-GiB capacity failure or replica failure. The likely mechanism is bare `set -e` changing the interactive login shell so a later non-zero command terminates the shell. Future strict paste-and-run checks must wrap `set -euo pipefail` inside a child `bash -s <<'EOF' ... EOF` block. The SSH journal also contained unrelated public-Internet pre-authentication scans against invalid users/root; the operator's sessions were accepted by public key, and those scans are not evidence for this disconnect.

First-replica runtime/TLS/streaming checkpoint - 2026-08-22: **PASS on `ulc-02`.** The retried gate ran inside a child Bash so failure could not terminate the operator's SSH login. `ulc-01 /leader` and `ulc-02 /replica` both returned HTTP `200`; Spilo remained `running`, not restarting, with `RestartCount=0`; `patronictl list` showed `ulc-01` `Leader/running` and `ulc-02` `Replica/streaming`, timeline `1`, receive/replay LSN `0/3000168`, lag `0`. From a verify-full connection to the primary, `pg_stat_replication` showed application `ulc-02`, client `10.104.0.4`, state `streaming`, sync state `async`, the replication session using TLS 1.3 with `TLS_AES_256_GCM_SHA384`, equal sent/write/flush/replay LSN `0/3000168`, and calculated byte lag `0`. A separate `sslmode=verify-full` connection directly to `ulc-02` using logical name `postgres-ha.internal` and `hostaddr=10.104.0.4` returned server address `10.104.0.4`, `pg_is_in_recovery=true`, TLS enabled, TLS 1.3, and the same cipher. `pg_stat_wal_receiver` on `ulc-02` reported `streaming` from `10.104.0.2:5432` using slot `ulc_02`, timeline `1`, latest end LSN `0/3000168`. The child gate exited `0` and the SSH parent shell stayed alive. The first replica is therefore fully validated for role, runtime stability, primary-side streaming, WAL receiver source, and verify-full TLS. `ulc-03` may now be admitted as the second replica under the same controlled one-node-at-a-time process.

Second-replica admission checkpoint - 2026-08-22: **PASS on `ulc-03`.** Before startup, `ulc-01 /leader` and `ulc-02 /replica` both returned HTTP `200`; all three etcd endpoints were healthy; `5432/8008` were free; `/srv/spilo/pgdata` was empty at `0700 101:103`; no stale `members/ulc-03` DCS key existed; Compose syntax passed; and `INITDB_LOCALE=C` remained effective. The `ulc-03` Spilo container was force-recreated with hostname `ulc-03`, running state, `RestartCount=0`, and `INITDB_LOCALE=C`. Patroni logged `Lock owner: ulc-01; I am ulc-03`, `trying to bootstrap from leader 'ulc-01'`, `replica has been created using basebackup_fast_xlog`, and `bootstrapped from leader 'ulc-01'`; PostgreSQL became ready after approximately 10 seconds. Listeners were exactly `10.104.0.8:5432` and `10.104.0.8:8008`. `patronictl list` showed the full three-member cluster on timeline `1`: `ulc-01` `Leader/running`, `ulc-02` `Replica/streaming`, `ulc-03` `Replica/streaming`; both replicas reported receive/replay LSN `0/5000000` and lag `0`. Local SQL on `ulc-03` confirmed `pg_is_in_recovery=true`, PostgreSQL `18.6`, `max_connections=40`, `shared_buffers=128MB`, `work_mem=2MB`, `maintenance_work_mem=32MB`, `ssl=on`, replay LSN `0/5000000`; PGDATA remained `0700 101:103`. Known `LC_ALL=en_US.utf-8` warnings recurred but were non-blocking. `pg_stat_kcache.linux_hz` auto-detected `500000` on this host; do not classify that log line by itself as a failure because the replica reached healthy streaming state. Final cluster-establishment gate remains: primary-side TLS/streaming rows for both replicas, direct verify-full TLS to `ulc-03`, and `ulc-03` WAL receiver source.

PostgreSQL TLS installation checkpoint - 2026-08-22: installation is **PASS on all three nodes**. Each host has `/etc/lorawan-pki/postgres` mode `0750` numeric `0:103`; `ca.crt` and `server.crt` are `0644 0:0`; `server.key` is `0600 101:103`. Every node reports the same CA SHA-256 fingerprint `99:00:4B:B3:2D:7D:78:FA:38:61:7C:78:89:6D:7A:7E:FF:9F:A6:10:FC:8F:07:D4:E2:5E:35:25:36:E6:CB:3E`. CA-chain, physical hostname, logical hostname `postgres-ha.internal`, and node-private-IP verification all returned `OK`. SANs match each intended node, and the installed private-key/certificate public-key hashes match their issuance-time values: `ulc-01` `d0e32da1ec25bc716646afd1f061bbef38bae019f2d542a2f5337a173ffa29f0`, `ulc-02` `333d66141bda84c787868df00d8ed66d099491350577139b52af85f6d8d95ccf`, `ulc-03` `6dc8915e0009b8a118fe3e6a1552229c7330cfb194a79f5a34ba455147e87e02`. TLS is no longer a bootstrap blocker. PostgreSQL/Patroni remains stopped while the `PGROOT`/bind-mount layout is validated against the exact immutable image.

Final three-member PostgreSQL/Patroni gate - 2026-08-22: **PASS; infrastructure cluster established.** Patroni role endpoints returned HTTP `200` for `ulc-01 /leader`, `ulc-02 /replica`, and `ulc-03 /replica`. DCS leader was exactly `ulc-01`, and exactly three Patroni member keys existed. `patronictl list` showed `ulc-01` `Leader/running`, `ulc-02` `Replica/streaming`, and `ulc-03` `Replica/streaming`, timeline `1`, both replicas at receive/replay LSN `0/6000000`, lag `0`. From a verify-full primary connection, `pg_stat_replication` returned exactly `ulc-02|10.104.0.4|streaming|async|TLS` and `ulc-03|10.104.0.8|streaming|async|TLS`, both TLS 1.3 / `TLS_AES_256_GCM_SHA384`, equal sent/write/flush/replay LSN `0/6000000`, byte lag `0`; structural summary `2|1|1`. Physical slots `ulc_02` and `ulc_03` were active. Direct verify-full TLS to `ulc-03` returned server `10.104.0.8`, recovery true, TLS 1.3; its WAL receiver was `streaming` from `10.104.0.2:5432` via slot `ulc_03`. Child gate exit code was `0` and the SSH parent shell remained alive. Phase 6 is not yet complete: logical application databases/roles, TimescaleDB database enablement/schema, backup boundary, and controlled switchover remain.

Database commissioning preflight - 2026-08-22: **PASS on `ulc-01` for discovery.** The only non-template database is `postgres`, UTF8 with `C.UTF-8` collation/ctype. No application database roles exist yet. Existing baseline roles include `postgres` LOGIN/SUPERUSER/REPLICATION, `standby` LOGIN/REPLICATION, and the intentional `admin` NOLOGIN/CREATEDB role. The final hardened live primary reports `pg_available_extensions.timescaledb default_version = 2.29.2` with no installed version in `postgres`; `shared_preload_libraries` includes `timescaledb`. This is a live final-image/package observation and supersedes `2.26.2` only for the current hardened runtime; the earlier `2.26.2` records remain historical upstream/candidate evidence before package-upgrade hardening. Both replicas remained `streaming`, `async`, byte lag `0`. Next: prove TimescaleDB version/preload consistency directly on all three members before creating `chirpstack` and `lorawan_telemetry`.

Three-member TimescaleDB consistency-gate attempt - 2026-08-22: **INCONCLUSIVE / test-comparison defect, not a service failure.** The gate correctly reached `ulc-01` over verify-full TLS and returned `10.104.0.2/32|primary|18.6 (Ubuntu 18.6-1.pgdg22.04+2)|2.29.2|NOT_INSTALLED|preload=yes|version_files=yes`. The script then failed only because it compared PostgreSQL's textual `inet` representation `10.104.0.2/32` against the bare expected address `10.104.0.2`. No database mutation occurred, the child shell exited `1`, and the parent SSH session remained alive. The corrected probe used `host(inet_server_addr())` so PostgreSQL returned the bare address for comparison.

Three-member TimescaleDB consistency gate - 2026-08-22: **PASS.** `ulc-01` returned `10.104.0.2|primary|18.6 (Ubuntu 18.6-1.pgdg22.04+2)|2.29.2|NOT_INSTALLED|preload=yes|version_files=yes`; `ulc-02` returned the same PostgreSQL/TimescaleDB state at `10.104.0.4` with role `replica`; and `ulc-03` returned the same state at `10.104.0.8` with role `replica`. `patronictl list` remained healthy with `ulc-01` `Leader/running`, `ulc-02` and `ulc-03` `Replica/streaming`, timeline `1`, and lag `0`. Primary-side replication inspection returned exactly two `streaming|async` rows, one from `10.104.0.4` and one from `10.104.0.8`, each with calculated byte lag `0`. The child gate exited `0` and the SSH parent shell remained alive. The repeated `LC_ALL=en_US.utf-8` and Perl locale warnings are still recorded as a separate container-locale hygiene issue; they did not prevent this gate from passing.

Decision: all three promotion candidates expose the same final hardened TimescaleDB `2.29.2` package files and preload state. The extension remains intentionally absent from `postgres`.

Live TimescaleDB 2.29.2 functionality probe - 2026-08-22: **PASS.** On current leader `ulc-01`, preflight confirmed `timescale_probe_2292` did not exist. The temporary database was created, `CREATE EXTENSION timescaledb` loaded version `2.29.2`, `probe.sensor_probe` became a one-dimensional hypertable, and one `probe-device|42.5` row was inserted and read successfully. Direct verify-full checks against `ulc-02` and `ulc-03` each returned `timescale_probe_2292|<expected-private-IP>|replica|2.29.2|1|1`, proving the extension state, hypertable metadata, and probe row replicated to both replicas. The temporary database was then dropped on the primary and all three members returned probe-database count `0`. Final `patronictl list` remained `ulc-01 Leader/running`, both replicas `streaming`, timeline `1`, lag `0`; primary-side replication remained `ulc-02|10.104.0.4|streaming|async|0` and `ulc-03|10.104.0.8|streaming|async|0`. The child script exited `0`; SSH remained connected. Locale warnings remain separate non-blocking hygiene evidence.

Decision: the final live PostgreSQL 18.6 / TimescaleDB 2.29.2 HA package set has now passed both three-member consistency and actual disposable-database functionality/replication testing. Permanent `chirpstack` and `lorawan_telemetry` commissioning is now the next bounded Phase 6 step.

Permanent database commissioning structure gate - 2026-08-22: **PASS.** `ulc-01 /leader` returned HTTP `200`; two replicas were still streaming; target-database count and target-role count were both zero before mutation. Five application/ownership role shells were created locked with `NOLOGIN` and no password: `chirpstack`, `telemetry_admin`, `telemetry_writer`, `telemetry_reader`, and `fabric_adapter`. `chirpstack` was created with owner `chirpstack`; `lorawan_telemetry` was created with owner `postgres`. TimescaleDB `2.29.2` was enabled only in `lorawan_telemetry`, and schema `telemetry` was created with owner `telemetry_admin`. `chirpstack` remained an ordinary PostgreSQL database with TimescaleDB extension count `0`.

Replica verification over `sslmode=verify-full` showed both `ulc-02` and `ulc-03` see exactly two target databases, all five target roles, TimescaleDB `2.29.2`, and schema `telemetry` owned by `telemetry_admin`. Final Patroni state remained one leader plus two streaming replicas on timeline `1`; primary-side rows were `ulc-02|10.104.0.4|streaming|async|0` and `ulc-03|10.104.0.8|streaming|async|0`. Child gate exit code was `0`, and the SSH login shell remained alive.

Post-gate ownership review: the structure gate itself passed every assertion it contained, but it created `lorawan_telemetry` without `-O telemetry_admin`, so PostgreSQL correctly left the database owner as `postgres`. The cloud manual's intended ownership model uses `telemetry_admin` as a non-login owner role. Treat this as a bounded commissioning correction, not a replication or TimescaleDB failure. Before credential activation, run `ALTER DATABASE lorawan_telemetry OWNER TO telemetry_admin;` on the verified primary and prove the owner change appears on both replicas.

Telemetry database owner normalization - 2026-08-22: **PASS.** `ulc-01 /leader` returned HTTP `200`. Before mutation, `lorawan_telemetry` was owned by `postgres`, while `telemetry_admin` was confirmed `NOLOGIN` with no password. `ALTER DATABASE lorawan_telemetry OWNER TO telemetry_admin;` succeeded. Primary verification returned `telemetry_admin|telemetry_admin|2.29.2` for database owner, telemetry-schema owner, and TimescaleDB version. Direct verify-full checks on `ulc-02` and `ulc-03` each returned their expected private IP, role `replica`, database owner `telemetry_admin`, schema owner `telemetry_admin`, and TimescaleDB `2.29.2`. Final Patroni state remained one leader plus two streaming replicas; primary-side replication remained `streaming|async|0` for both replicas. The child gate exited `0`, and the SSH login shell stayed alive.

Decision: the permanent database ownership boundary is normalized and replicated. Keep `telemetry_admin` permanently `NOLOGIN` with no application password.

Application credential activation gate - 2026-08-22: **PASS.** `SHOW password_encryption` returned `scram-sha-256`. Before LOGIN activation, the sanitized structural check returned `4|1`: `chirpstack`, `telemetry_writer`, `telemetry_reader`, and `fabric_adapter` were still `NOLOGIN` but each had a SCRAM-SHA-256 verifier, while `telemetry_admin` remained `NOLOGIN` with no password. The database ACL transaction revoked `PUBLIC` CONNECT on both application databases, granted `chirpstack` CONNECT only to `chirpstack`, granted the three telemetry runtime identities CONNECT only to `lorawan_telemetry`, then enabled LOGIN on the four runtime identities. The post-activation structural check again returned `4|1`. The CONNECT matrix returned `chirpstack|t|f`, `fabric_adapter|f|t`, `telemetry_reader|f|t`, and `telemetry_writer|f|t`, with zero matrix errors. Both replicas returned credential structural summary `4|1`. Patroni remained `ulc-01 Leader/running`, `ulc-02 Replica/streaming`, `ulc-03 Replica/streaming`; primary-side replication remained `streaming|async|0` for both replicas. Child gate exit code was `0` and the SSH login shell remained alive.

Decision: credential structure and database-level access boundaries are active and replicated.

Direct runtime-role authentication gate - 2026-08-22: **PASS.** Four independent `psql -W` sessions were opened against the current primary using logical host `postgres-ha.internal`, `hostaddr=10.104.0.2`, and `sslmode=verify-full`; each password was entered only at the hidden prompt and no secret value appeared in the transcript. `chirpstack` returned `chirpstack|chirpstack|10.104.0.2|t|TLSv1.3|TLS_AES_256_GCM_SHA384`. `telemetry_writer`, `telemetry_reader`, and `fabric_adapter` each returned the corresponding runtime role with database `lorawan_telemetry`, server `10.104.0.2`, `ssl=t`, TLSv1.3, and cipher `TLS_AES_256_GCM_SHA384`. The repeated `LC_ALL=en_US.utf-8` / Perl locale warning remains the known separate container-locale hygiene issue and did not prevent authentication.

Decision: the actual entered application secrets are now proven by real SCRAM-authenticated, verify-full TLS sessions.

Telemetry object schema commissioning - 2026-08-22: **PASS.** Preflight on `ulc-01` confirmed the current leader, exactly two streaming replicas, baseline `lorawan_telemetry|telemetry_admin|telemetry_admin|2.29.2`, and zero target telemetry objects. A single transaction under `SET ROLE telemetry_admin` created `telemetry.uplinks`, `telemetry.measurements`, `telemetry.device_registry`, `telemetry.latest_uplinks`, `telemetry.latest_measurements`, and `telemetry.schema_version`; `uplinks` and `measurements` converted successfully into one-dimensional Timescale hypertables. All six named objects are owned by `telemetry_admin`. Schema version `3` was recorded as the generic multi-sensor schema with registry/views and retention explicitly not enabled; `timescaledb_information.jobs` returned zero retention-policy jobs.

Least-privilege checks returned `fabric_adapter|f|f|f|f|f`, `telemetry_reader|t|f|t|f|t`, and `telemetry_writer|t|f|t|t|f`, with zero ACL structural errors. A writer INSERT/SELECT permission probe succeeded inside a rollback-only transaction, and the post-rollback check found zero probe rows. Reader SELECT probes executed without permission errors; because the permanent tables are empty, grouped result sets correctly contained zero rows. Direct replica verification returned `10.104.0.4|replica|2|6|1` on `ulc-02` and `10.104.0.8|replica|2|6|1` on `ulc-03`, proving both hypertables, all six named objects, and the schema-version row replicated. Final Patroni state remained `ulc-01 Leader/running`, both replicas `streaming`, timeline `1`, lag `0`; primary-side replication rows remained `streaming|async|0`. Child gate exit code was `0`, and the SSH login shell remained alive.

Decision: the permanent telemetry object layer and writer/reader ACL boundary are established. Keep `fabric_adapter` without broad telemetry-object access. Logical dumps remain required before later destructive failover/failure tests.

PostgreSQL HBA hardening preflight - 2026-08-22: **PASS / READ ONLY.** Patroni role endpoints returned `200` for `ulc-01 /leader` and both replica endpoints; `patronictl list` remained one leader plus two streaming replicas with zero reported lag. Sanitized verifier inspection showed SCRAM-SHA-256 for `postgres`, `standby`, `chirpstack`, `telemetry_writer`, `telemetry_reader`, and `fabric_adapter`; `admin` and `telemetry_admin` remain passwordless `NOLOGIN`. `/run/postgres.yml` contains the active local `postgresql.pg_hba` list, while both `bootstrap.dcs.postgresql.pg_hba` and current DCS `postgresql.pg_hba` are absent. All three members expose the same effective HBA and zero parse errors: local trust/PAM compatibility rules, `hostssl replication standby all md5`, `hostnossl all all all reject`, broad remote `+zalandos` PAM, and broad `hostssl all all all md5`. Primary-side replication still reports both replicas `streaming|async`, TLSv1.3 / `TLS_AES_256_GCM_SHA384`, calculated byte lag `0`; PostgreSQL listens only on the node's `10.104.0.x` address.

Decision: local Patroni configuration takes precedence for this HBA path, so a DCS-only change is not the right rollout. Persist the new HBA in `SPILO_CONFIGURATION`, mirror it into the currently loaded local Patroni file, and use Patroni local-config reload rather than restarting the container. Roll out as a canary on `ulc-02` first, with rollback copies, while leaving the primary and `ulc-03` untouched until the canary is proven.

First `ulc-02` HBA hardening canary attempt - 2026-08-22: **INCONCLUSIVE / AUTOMATIC ROLLBACK TRIGGERED BEFORE LIVE HBA RELOAD.** The initial HA baseline was healthy: `ulc-01 /leader`, `ulc-02 /replica`, and `ulc-03 /replica` all returned HTTP `200`, and Patroni showed one leader plus two streaming replicas. Root-only rollback evidence was created under `/etc/lorawan-cloud/spilo/hba-rollback-20260822-235341/`. The candidate persistent `SPILO_CONFIGURATION` update succeeded and Compose syntax passed; the decoded target contained 20 rules using explicit `10.104.0.2/32`, `.4/32`, and `.8/32` SCRAM rules plus final TLS/non-TLS rejects. The attempt then failed before `/run/postgres.yml` was mutated: `docker cp` copied `/run/hba-target.json` with restrictive permissions inherited from the host `mktemp` file, and the subsequent in-container Python process raised `PermissionError: [Errno 13] Permission denied: '/run/hba-target.json'`.

Automatic cleanup attempted to restore the saved persistent environment, restored the pre-canary local Patroni config, requested a reload for `ulc-02`, and `ulc-02 /replica` returned HTTP `200`; Patroni still showed `ulc-01` leader with `ulc-02` and `ulc-03` streaming. The cleanup-time `patroni --validate-config /run/postgres.yml -i` printed `name is not defined`; because the running cluster remained healthy and the canary had failed before the live HBA edit/reload point, classify this as a test-harness/validator issue, not a PostgreSQL/Patroni outage. Do not claim HBA hardening passed.

Rollback-verification attempts - 2026-08-23: the first read-only verification was **INCONCLUSIVE / TEST-HARNESS FALSE NEGATIVE** because it used `[ -f "$FILE" ]` as `opsadmin` against a deliberately `0700 root:root` rollback directory. The corrected sudo-based check proves the rollback evidence actually exists: directory `/etc/lorawan-cloud/spilo/hba-rollback-20260822-235341` is `0700 0:0`, and `spilo.env`, `postgres.yml`, and `pg_hba.conf` are each `0600 0:0`. The corrected check then found a real persistent-state mismatch and stopped: current `/etc/lorawan-cloud/spilo/spilo.env` SHA-256 is `da86466be7cc54be3e989a0e8cf070d414aa357cb160526e1fdec69edd879714`, while the pre-canary backup is `006398906b944ddc793802648081097d1f9250f66b36592e6a145c8ed455acad`.

Persistent Spilo env drift diagnosis - 2026-08-23: **RESOLVED / LIVE HBA UNCHANGED; PERSISTENT FILE STILL DRIFTED.** Current and backup `spilo.env` each contain 20 environment keys; none are missing on either side, and only `SPILO_CONFIGURATION` differs. Sanitized decoded comparison proved the non-HBA portions of `SPILO_CONFIGURATION` are exactly equal. The current host file contains the failed candidate 20-rule explicit `/32` SCRAM `postgresql.pg_hba` list, while the pre-canary backup contains no explicit `postgresql.pg_hba` (`count=0`). That zero is the correct pre-canary persistent state: Spilo generated the original 10-rule HBA into local `/run/postgres.yml` at runtime rather than carrying it as a `SPILO_CONFIGURATION` override. The live local Patroni config still reports the original 10 rules, and effective PostgreSQL `pg_hba_file_rules` remains 10 rules with zero parse errors (`10|0|4|0|3` for total|errors|md5|scram|broad-nonreject). HA is healthy: `ulc-01 /leader`, `ulc-02 /replica`, and `ulc-03 /replica` all returned HTTP `200`; both replicas remain streaming with lag `0`; `ulc-02` WAL receiver is `streaming|10.104.0.2|5432|ulc_02`.

Decision: the first canary did **not** activate the candidate HBA in the running database. Only the persistent host env remained on the candidate value, so a future recreate was unsafe until repaired. The prior log statement that automatic cleanup restored the persistent environment was not sufficiently verified and is superseded by this evidence.

Persistent Spilo env repair - 2026-08-23: **PASS on `ulc-02`.** All three Patroni role endpoints were healthy before the repair. The failed 20-rule host file was preserved as root-only evidence at `/etc/lorawan-cloud/spilo/hba-rollback-20260822-235341/spilo.env.failed-20rule-20260823-000801`. The active `/etc/lorawan-cloud/spilo/spilo.env` was atomically restored from the pre-canary backup. Current and backup SHA-256 are both `006398906b944ddc793802648081097d1f9250f66b36592e6a145c8ed455acad`; active file mode/owner is `0600 0:0`. Sanitized decoding confirms the restored persistent `SPILO_CONFIGURATION` has no explicit `postgresql.pg_hba`, matching the actual pre-canary baseline. Compose parsing passes. No PostgreSQL/Patroni reload, restart, or container recreate occurred. Running `/run/postgres.yml` remained at 10 HBA rules; effective PostgreSQL HBA remained `10|0|4|0|3` for total|errors|md5|scram|broad-nonreject; `ulc-02` WAL receiver remained `streaming|10.104.0.2|5432|ulc_02`; final Patroni state stayed one leader plus two streaming replicas with zero reported lag.

Decision: persistent and live HBA state returned to the proven pre-canary baseline before the corrected retry.

Corrected `ulc-02` live HBA hardening canary - 2026-08-23: **PASS.** Baseline role endpoints returned HTTP `200`, with `ulc-01` leader and both replicas streaming. The repaired persistent env still had no explicit `postgresql.pg_hba`. An exact runtime rollback copy was retained at `/run/postgres.yml.hba-canary-20260823-001550`. The live local Patroni configuration was changed to the 20-rule candidate and structurally parsed as member `ulc-02` with 20 HBA rules before reload. `patronictl reload` was accepted. Effective HBA converged to `20|0|0|14|3|3|3|3|2` for total|errors|md5|scram|replication-/32|postgres-/32|chirpstack-/32|telemetry-/32|reject-all. Direct verify-full PostgreSQL access to `10.104.0.4` succeeded over TLSv1.3 / `TLS_AES_256_GCM_SHA384`; standby-role physical replication protocol `IDENTIFY_SYSTEM` succeeded; `sslmode=disable` failed with the expected `pg_hba.conf rejects connection ... no encryption`. `ulc-02 /replica` stayed HTTP `200`, WAL receiver stayed `streaming|10.104.0.2|5432|ulc_02`, and final Patroni membership remained one leader plus two streaming replicas with zero reported lag. The persistent env remained unchanged with no explicit HBA override.

Decision: the 20-rule `/32` TLS + SCRAM HBA policy is proven live on `ulc-02`. Persist that exact already-proven rule list into `ulc-02` `SPILO_CONFIGURATION` next without reloading or recreating the container, then verify persistent/live equality before moving to another member.

First hardened-HBA persistence attempt - 2026-08-23: **INCONCLUSIVE / NO PERSISTENT MUTATION OCCURRED.** HA role endpoints were healthy and the persistent `SPILO_CONFIGURATION` still had no explicit `postgresql.pg_hba`. The live database still reported the proven hardened summary `20|0|0|14|3|3|3|3|2`. The gate then failed while copying the live HBA JSON to a host temporary file: `tee: /tmp/tmp...: Permission denied`. The mutation flag had not yet been set, so the script exited before rewriting `/etc/lorawan-cloud/spilo/spilo.env`; no persistent rollback was necessary, and no PostgreSQL reload, Patroni restart, or container recreate was performed by this attempt. A separate harness defect was also identified: the step-4 stdin-fed Python check used `docker exec` without `-i`, which explains the missing expected validation output. The later SQL structural check still independently proved the live 20-rule HBA remained active.

Corrected hardened-HBA persistence - 2026-08-23: **PASS on `ulc-02`.** The retry first re-proved all three Patroni role endpoints at HTTP `200`, the persistent env at the old no-HBA-override baseline, exact equality of the live local 20-rule HBA to the proven candidate, and effective structural summary `20|0|0|14|3|3|3|3|2`. The live HBA was captured directly into a shell variable instead of a host temp file. A root-only rollback backup was created at `/etc/lorawan-cloud/spilo/hba-persist-20260823-004235/spilo.env`. The exact in-memory live list was then persisted into `SPILO_CONFIGURATION`; Compose parsing passed; the resulting persistent HBA count was `20`; persistent/live exact equality passed; and `/etc/lorawan-cloud/spilo/spilo.env` remained `0600 0:0`. The live database was untouched: post-persistence HBA summary stayed `20|0|0|14|2`, WAL receiver stayed `streaming|10.104.0.2|5432|ulc_02`, and the Spilo container ID/start time/RestartCount were identical before and after (`RestartCount=0`). Final Patroni state remained `ulc-01` Leader/running with `ulc-02` and `ulc-03` Replica/streaming at lag `0`.

Decision: `ulc-02` now has the same proven hardened 20-rule HBA in both live `/run/postgres.yml` and persistent `SPILO_CONFIGURATION`, so a future recreate will not silently revert to the old broad HBA.

Cross-host future-primary replication-auth gate to `ulc-02` - 2026-08-23: **PASS from `ulc-01` and `ulc-03`.** On `ulc-01`, route selection to `10.104.0.4` used `eth1` source `10.104.0.2`; `ulc-02 /replica` returned HTTP `200`; standby-role physical replication over `sslmode=verify-full` succeeded with `IDENTIFY_SYSTEM`, returning cluster system identifier `7676855802088521796`, timeline `1`, WAL position `0/A000000`; the target replica endpoint remained HTTP `200` after the probe. On `ulc-03`, the same gate selected `eth1` source `10.104.0.8` and the same verify-full replication-protocol authentication succeeded with system identifier `7676855802088521796`, timeline `1`, WAL position `0/A000000`; `ulc-02 /replica` again stayed HTTP `200`. Both child scripts exited `0` and both parent SSH sessions stayed alive. The recurring `LC_ALL=en_US.utf-8` warning remains the known non-blocking container-locale hygiene issue.

Decision: hardened `ulc-02` now proves both allowed cross-host replication source rules (`10.104.0.2/32` and `10.104.0.8/32`) in real replication-protocol sessions. From the HBA/authentication perspective it can accept the two remaining Patroni members after a future promotion. Next: roll out the same 20-rule live HBA canary to `ulc-03` while keeping `ulc-01` unchanged as the current leader.

`ulc-03` live HBA hardening canary - 2026-08-23: **PASS.** Baseline checks showed all three Patroni role endpoints at HTTP `200`, with `ulc-01` leader and both replicas streaming at lag `0`. `ulc-03` persistent `SPILO_CONFIGURATION` had no explicit HBA override and effective PostgreSQL HBA was still the original `10|0|4|0|3` structure. A runtime rollback copy was retained at `/run/postgres.yml.hba-canary-20260823-005007`. The exact proven 20-rule candidate was written to live `/run/postgres.yml`, parsed as member `ulc-03` with 20 rules, and reloaded only on `ulc-03`. Effective HBA converged to `20|0|0|14|3|3|3|3|2`. Direct verify-full `postgres` access to `10.104.0.8` returned `10.104.0.8|t|t|TLSv1.3|TLS_AES_256_GCM_SHA384`; standby-role `IDENTIFY_SYSTEM` returned `7676855802088521796|1|0/A000000|`; non-TLS failed with the expected HBA rejection. `ulc-03 /replica` stayed HTTP `200`; WAL receiver stayed `streaming|10.104.0.2|5432|ulc_03`; persistent env remained unchanged with no explicit HBA override; container ID, start timestamp, and `RestartCount=0` were identical before and after. Final Patroni state remained healthy.

Decision: `ulc-03` live HBA canary passed and was ready for persistence without changing the running database.

`ulc-03` hardened-HBA persistence - 2026-08-23: **PASS.** The gate re-proved all three Patroni role endpoints at HTTP `200`, the persistent env at the no-HBA-override baseline, the exact live 20-rule candidate, and effective HBA summary `20|0|0|14|2`. The live HBA was captured in memory, and a root-only rollback copy was retained at `/etc/lorawan-cloud/spilo/hba-persist-20260823-005339/spilo.env`. The exact live rule list was written into persistent `SPILO_CONFIGURATION`; `docker compose config --quiet` passed; persistent HBA count became `20`; persistent/live exact equality passed; and the env remained `0600 0:0`. No PostgreSQL reload, Patroni restart, or container recreate was performed. Effective HBA remained `20|0|0|14|2`, `ulc-03` WAL receiver remained `streaming|10.104.0.2|5432|ulc_03`, and container ID/start timestamp/`RestartCount=0` were unchanged. Final Patroni state remained one leader plus two streaming replicas at lag `0`.

Decision: both replicas now have the proven hardened 20-rule HBA live and persisted.

Cross-host future-primary replication-auth gate to `ulc-03` - 2026-08-23: **PASS from `ulc-01` and `ulc-02`.** On `ulc-01`, route selection to `10.104.0.8` used `eth1` source `10.104.0.2`; `ulc-03 /replica` was HTTP `200`; standby-role physical replication over `sslmode=verify-full` succeeded with `IDENTIFY_SYSTEM`, returning system identifier `7676855802088521796`, timeline `1`, WAL position `0/A000000`; the target remained HTTP `200` after the probe. On `ulc-02`, route selection used `eth1` source `10.104.0.4`; the same SCRAM + verify-full replication-protocol probe returned the same system identifier, timeline, and WAL position; `ulc-03 /replica` stayed HTTP `200`. Both child scripts exited `0` and both parent SSH sessions stayed alive. The recurring `LC_ALL=en_US.utf-8` warning remains the known non-blocking container-locale hygiene issue.

Decision: `ulc-03` now proves both allowed cross-host replication source rules (`10.104.0.2/32` and `10.104.0.4/32`) in real new replication-protocol sessions. Both replicas are live + persistent hardened and future-primary replication-auth ready.

`ulc-01` leader live HBA hardening canary - 2026-08-23: **PASS.** Baseline checks showed `ulc-01 /leader`, `ulc-02 /replica`, and `ulc-03 /replica` all HTTP `200`; local SQL confirmed `ulc-01` was primary; persistent `SPILO_CONFIGURATION` still had no explicit `postgresql.pg_hba`; and effective HBA was the original `10|0|4|0|3`. A runtime rollback copy was retained at `/run/postgres.yml.hba-canary-20260823-010121`. The exact proven 20-rule candidate was installed only in live `/run/postgres.yml`, validated as member `ulc-01`, and reloaded only on the leader. Effective HBA converged to `20|0|0|14|3|3|3|3|2`. The leader endpoint stayed HTTP `200`; verify-full `postgres` auth to `10.104.0.2` returned `10.104.0.2|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`; non-TLS failed with the expected HBA rejection. Both existing replication streams remained TLS `streaming|async` with zero byte lag at the checkpoint, and both replica endpoints stayed HTTP `200`. Persistent env remained unchanged with no HBA override; container ID, start timestamp, and `RestartCount=0` were identical before and after; final Patroni state stayed one leader plus two streaming replicas at lag `0`.

Decision: the hardened rule set is now proven live on all three members, but `ulc-01` is still live-only. Existing replication streams do not prove a fresh authentication against the new leader HBA because HBA is evaluated when the connection is established. Next: run new standby-role `IDENTIFY_SYSTEM` sessions from `ulc-02` and `ulc-03` to `10.104.0.2`; only after both cross-host probes pass should the leader HBA be persisted.

Fresh cross-host replication-auth gate to hardened leader `ulc-01` - 2026-08-23: **PASS from `ulc-02` and `ulc-03`.** On `ulc-02`, route selection to `10.104.0.2` used `eth1` source `10.104.0.4`; the leader endpoint was HTTP `200`; a new standby-role physical-replication connection using SCRAM and `sslmode=verify-full` completed `IDENTIFY_SYSTEM` and returned `7676855802088521796|1|0/A000408|`; `ulc-01 /leader` remained HTTP `200` afterward. On `ulc-03`, route selection used `eth1` source `10.104.0.8`; the same fresh replication-protocol test returned the same system identifier, timeline, and WAL position; the leader again remained HTTP `200`. Both child scripts exited `0` and both parent SSH sessions stayed alive. The recurring `LC_ALL=en_US.utf-8` warning remains the known non-blocking container-locale hygiene issue.

Decision: the explicit `.4/32` and `.8/32` replication SCRAM rules on the hardened leader are now proven with new cross-host authentication sessions. Every PostgreSQL member has therefore been live-hardened and has fresh inbound replication-auth proof from both other member addresses.

`ulc-01` hardened leader HBA persistence - 2026-08-23: **PASS.** Before mutation, all Patroni role endpoints were HTTP `200`, local SQL confirmed `ulc-01` was primary, the protected persistent env had no explicit HBA override, the live local HBA exactly matched the proven 20-rule policy, and effective HBA was `20|0|0|14|2`. A `0700 root:root` rollback directory was created at `/etc/lorawan-cloud/spilo/hba-persist-20260823-010732` with `0600 root:root` `spilo.env`. The exact live rule list was persisted into `SPILO_CONFIGURATION`; Compose parsing passed; persistent HBA count became `20`; persistent/live exact equality passed; and the env remained `0600 0:0`. No PostgreSQL reload, Patroni restart, switchover, or container recreate occurred; container identity/start time/RestartCount were unchanged. Effective HBA stayed `20|0|0|14|2`; primary-side replication still showed `ulc-02` and `ulc-03` streaming over TLSv1.3 / `TLS_AES_256_GCM_SHA384` with zero byte lag at the checkpoint; and final Patroni state remained one leader plus two streaming replicas at lag `0`.

Decision: all three PostgreSQL members now carry the same proven hardened 20-rule HBA both live and persistently, and every member has fresh inbound replication-authentication proof from both other member VPC addresses.

Final three-node HBA parity + TLS/negative gate - 2026-08-23: **PASS on all three members.** `ulc-01`, `ulc-02`, and `ulc-03` each re-proved the three Patroni role endpoints at HTTP `200`; protected `spilo.env` mode/owner `600|0|0`; Compose parsing; exact canonical live 20-rule HBA; persistent HBA count `20`; and persistent/live exact equality. All three effective HBA summaries were exactly `20|0|0|14|3|3|3|3|2|0`, which additionally proves zero broad-address permissive rules remain. Verify-full `postgres` sessions returned the expected node and recovery state over TLSv1.3 / `TLS_AES_256_GCM_SHA384`: `10.104.0.2|f|t|...`, `10.104.0.4|t|t|...`, and `10.104.0.8|t|t|...`. `sslmode=disable` failed on each node with the explicit `pg_hba.conf rejects connection ... no encryption` error. The current leader still had exactly two TLS streaming replicas with structural check `2|1|1` and zero byte lag at the checkpoint; each replica WAL receiver remained streaming from `10.104.0.2:5432` through its expected physical slot. All three local role endpoints remained HTTP `200`; each child gate exited `0`; each SSH login shell stayed alive.

Decision: the HBA rollout is complete at live/persistent parity, SCRAM-only remote allow rules, TLS enforcement, broad-rule rejection, and replication-health layers. Next run one final hidden-prompt application-role authentication check under the hardened policy. After that, establish the logical backup boundary before any Patroni switchover or destructive failure test.

First post-hardening application-role auth attempt - 2026-08-23: **TEST HARNESS FAILURE; APPLICATION AUTH NOT YET TESTED.** The three-node Patroni baseline passed (`ulc-01 /leader`, `ulc-02 /replica`, `ulc-03 /replica` all HTTP `200`). The first ChirpStack probe then ended with `fe_sendauth: no password supplied` before a real password-authentication result was obtained. Root cause is the command wrapper: the script was launched as `bash -s <<'EOF'`, so its stdin was the heredoc containing the script itself, while `read -rsp` also tried to read the password from stdin. The password prompt therefore did not reliably read from the operator terminal. This is not evidence of HBA rejection, a bad SCRAM verifier, or a bad ChirpStack password. Retry the same read-only gate with each hidden password read explicitly from `/dev/tty`; keep the HBA rollout marked PASS and keep application-role post-hardening auth pending until the corrected gate returns real login rows.

Corrected post-hardening application-role authentication gate - 2026-08-23: **PASS.** The retry read each hidden application password directly from `/dev/tty`, avoiding the stdin conflict with the `bash -s` heredoc. HA was healthy before and after the authentication probes: `ulc-01 /leader`, `ulc-02 /replica`, and `ulc-03 /replica` all returned HTTP `200`. Real verify-full sessions against current primary `10.104.0.2:5432` succeeded for all four runtime identities: `chirpstack -> chirpstack`, `telemetry_writer -> lorawan_telemetry`, `telemetry_reader -> lorawan_telemetry`, and `fabric_adapter -> lorawan_telemetry`. Every returned row proved the expected current user/database, primary state (`pg_is_in_recovery=false`), TLS enabled, TLSv1.3, and `TLS_AES_256_GCM_SHA384`; no application password was printed. Final `patronictl list` showed `ulc-01` leader plus `ulc-02` and `ulc-03` streaming on timeline `1`, both at receive/replay LSN `0/A000510` and reported lag `0`. The child gate exited `0`, and the SSH login shell stayed alive.

Decision: HBA hardening and post-hardening runtime application authentication are both closed. The next Phase 6 boundary is a validated custom-format logical dump of `chirpstack` and `lorawan_telemetry`, copied off the target Droplet before controlled Patroni switchover or destructive failure testing.

Server-side POC logical backup gate - 2026-08-23: **PASS on `ulc-01`; off-Droplet copy still pending.** The gate ran only on the current leader and re-proved all Patroni role endpoints at HTTP `200` before and after the dump. Combined application-database size was `18,279,806` bytes; free space under the backup root was `42,795,130,880` bytes versus a conservative required floor of `1,092,021,630` bytes. Custom-format archives were created and successfully parsed by `pg_restore --list`: `chirpstack.dump` was `37,050` bytes with SHA-256 `61095053c9fead75f1fde16a6c0c163fa7064819476b8329bafb53d16a4a61b1`; `lorawan_telemetry.dump` was `59,383` bytes with SHA-256 `5d84dee3d696014a944b39a26191adcfc3803cd0f90ccab144f9340260b28c85`. `SHA256SUMS` was written alongside them. All three files were mode `0600` and owned by `opsadmin`; the timestamped directory is `/home/opsadmin/backups/ha-poc/20260823-013606`. The TimescaleDB dump emitted the expected circular-foreign-key warning for internal `continuous_agg`; this was a full custom-format dump, not a data-only dump, and archive parsing still passed. Final Patroni state remained `ulc-01` leader plus two streaming replicas on timeline `1`, both at receive/replay LSN `0/B000000` with reported lag `0`. Child gate exit code was `0` and the SSH login shell remained alive.

Decision: server-side backup creation is proven, but the POC backup boundary is **not complete** while the only copy still lives on `ulc-01`. Next copy the entire timestamped directory to an independent operator workstation and verify its SHA-256 hashes there before any Patroni switchover or destructive test.

First off-Droplet copy attempt - 2026-08-23: **NO TRANSFER / SSH IDENTITY MISMATCH.** From a Windows operator workstation, `scp` to `opsadmin@143.198.205.54` reached the SSH service but failed immediately with `Permission denied (publickey)`. No backup files were copied or changed. This is an authentication-path problem, not a PostgreSQL, backup-archive, or network-listener failure. The repository already records that `opsadmin` uses a separate Ed25519 identity for another device, while the original workstation identity previously proven against `ulc-01` authenticated as `jervis`. Do not weaken SSH authentication and do not copy administration private keys onto a server. Re-run the transfer from the workstation using the private key that is actually authorized for `opsadmin`, or use the already-proven `jervis` workstation identity with read-only access to the `opsadmin` backup directory only if deliberately granted. The backup boundary remains open until an independent copy exists and both dump hashes match.

Off-Droplet backup copy + SHA-256 verification - 2026-08-23: **PASS.** The complete timestamped backup directory `20260823-013606` was copied from `ulc-01` to the Windows operator workstation at `C:\Users\admin\lorawan-poc-backups\20260823-013606` using the authorized `opsadmin` SSH identity. The copied file sizes exactly matched the server-side evidence: `chirpstack.dump` = `37,050` bytes, `lorawan_telemetry.dump` = `59,383` bytes, and `SHA256SUMS` = `171` bytes. Workstation `Get-FileHash -Algorithm SHA256` returned `61095053c9fead75f1fde16a6c0c163fa7064819476b8329bafb53d16a4a61b1` for `chirpstack.dump` and `5d84dee3d696014a944b39a26191adcfc3803cd0f90ccab144f9340260b28c85` for `lorawan_telemetry.dump`, exactly matching the hashes recorded on `ulc-01`. The workstation gate ended `OFF-DROPLET POC BACKUP HASH GATE: PASS`.

Decision: the POC logical backup boundary is now **COMPLETE**. We now have validated custom-format archives plus an independently stored byte-for-byte verified copy outside the target Droplet. Controlled Patroni switchover testing may proceed; destructive failure testing still requires its own explicit gate and should not be conflated with this planned switchover.

Controlled Patroni switchover `ulc-01 -> ulc-02` - 2026-08-23: **PASS.** Pre-switchover role endpoints were healthy (`ulc-01 /leader`, `ulc-02 /replica`, `ulc-03 /replica` all HTTP `200`); local SQL on `ulc-01` proved it was primary; and `pg_stat_replication` showed exactly two streaming replicas. `patronictl switchover lorawan-postgres-ha --leader ulc-01 --candidate ulc-02 --force` reported `Successfully switched over to "ulc-02"`. During the expected transition, `ulc-01` briefly appeared `Replica/stopped` and its `/replica` endpoint returned `503`; by the third two-second probe it had rejoined and `/replica` returned `200`. Final topology was `ulc-02` Leader/running on timeline `2`, `ulc-01` Replica/running, and `ulc-03` Replica/running; all role endpoints returned HTTP `200`. Local SQL on `ulc-01` changed to `pg_is_in_recovery=true`, and its WAL receiver immediately reported `streaming|10.104.0.4|5432`, proving it reattached to the new primary without reinitialization. The `ulc-01` Spilo container ID, start timestamp, and `RestartCount=0` were identical before and after, so no container restart/recreate occurred. Child gate exit code was `0`, and the SSH login shell remained alive.

Decision: the planned database-layer switchover succeeded. The temporary stopped/503 state on the demoted member was part of the controlled transition and self-recovered within the gate. Next validate the new `ulc-02` primary locally: primary role, TimescaleDB `2.29.2`, both telemetry hypertables/schema metadata, both replication streams, and application database visibility before considering the switchover fully closed.

Promoted-primary validation on `ulc-02` - 2026-08-23: **PASS.** Expected role endpoints were all HTTP `200`; local SQL proved `pg_is_in_recovery=false`; direct verify-full access to `10.104.0.4` returned `10.104.0.4|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`. Database ownership stayed `chirpstack|chirpstack` and `lorawan_telemetry|telemetry_admin`. TimescaleDB in `lorawan_telemetry` remained `2.29.2`; `telemetry.measurements` and `telemetry.uplinks` remained hypertables; all six commissioned telemetry objects were present. A rollback-only write ownership probe successfully created a temporary-named regular table, inserted and read one row, then `ROLLBACK` left the probe object absent. Primary-side replication showed exactly two TLSv1.3 streaming replicas: `ulc-01|10.104.0.2|streaming|async|...|0` and `ulc-03|10.104.0.8|streaming|async|...|0`. Final Patroni state was `ulc-02` Leader/running on timeline `2`, with both replicas streaming on timeline `2` and reported lag `0`; child gate exit code was `0`, and the SSH login shell remained alive.

Decision: promotion preserved PostgreSQL writability, application databases/owners, TimescaleDB `2.29.2`, the telemetry object model, and both replication streams.

Post-promotion application-role authentication on `ulc-02` - 2026-08-23: **PASS.** Hidden-password verify-full sessions to promoted primary `10.104.0.4:5432` succeeded for all four runtime identities: `chirpstack|chirpstack|10.104.0.4|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`, `telemetry_writer|lorawan_telemetry|10.104.0.4|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`, `telemetry_reader|lorawan_telemetry|10.104.0.4|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`, and `fabric_adapter|lorawan_telemetry|10.104.0.4|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`. Primary-side replication remained `ulc-01|10.104.0.2|streaming|async` and `ulc-03|10.104.0.8|streaming|async`. Final Patroni state stayed `ulc-02` Leader/running on timeline `2`, with both replicas streaming on timeline `2` and reported lag `0`; `ulc-02 /leader`, `ulc-01 /replica`, and `ulc-03 /replica` all returned HTTP `200`. Child gate exit code was `0`, and the SSH login shell remained alive.

Decision: Phase 6 database-layer commissioning and planned-switchover validation are now closed. Do not claim application-routing failover yet: HAProxy and PgBouncer are not deployed. Phase 7 starts with a read-only three-host preflight for package versions, existing listeners/services, PostgreSQL/Patroni health, and certificate material before any install/configuration mutation.

Phase 7 first three-host read-only preflight - 2026-08-23: **PARTIAL PASS; NO INSTALL OR SERVICE MUTATION.** On `ulc-01`, `ulc-02`, and `ulc-03`, Patroni remained healthy with `ulc-02` leader on timeline `2` and `ulc-01`/`ulc-03` streaming replicas with reported lag `0`. HAProxy and PgBouncer were absent and their systemd units were not loaded. Every host returned the same package candidates: HAProxy `2.8.16-0ubuntu0.24.04.3` and PgBouncer `1.22.0-1build4`. Planned private database-routing ports `6432`, `15432`, and `15433` were free everywhere. The script then stopped on all three hosts at `FAIL: missing /etc/lorawan-pki/postgres/ca.crt`. This was not evidence that the CA was absent: the test used unprivileged `[ -f ]` while the PostgreSQL PKI directory is intentionally `0750 root:103`.

Phase 7 privileged PKI continuation - 2026-08-23: **PASS on all three nodes.** `opsadmin` numeric groups were `1001 27 100 988`, while `namei` showed `/etc/lorawan-pki/postgres` as `0750 root:103`, confirming the original unprivileged test was a protected-directory traversal false negative. Privileged checks found `ca.crt`, `server.crt`, and `server.key` on every node. Exact protection remained directory `750|0|103`, CA `644|0|0`, certificate `644|0|0`, and key `600|101|103`. Every host returned the commissioned CA fingerprint `99:00:4B:B3:2D:7D:78:FA:38:61:7C:78:89:6D:7A:7E:FF:9F:A6:10:FC:8F:07:D4:E2:5E:35:25:36:E6:CB:3E`; Spilo's read-only `/etc/lorawan-pki/postgres -> /run/postgres-certs` bind was present, the container-visible fingerprint matched the host exactly, and `openssl verify` returned `server.crt: OK`. PgBouncer client-TLS files are genuinely not provisioned, and `/etc/haproxy/haproxy.cfg`, `/etc/pgbouncer/pgbouncer.ini`, and `/etc/pgbouncer/userlist.txt` are absent. All three child gates exited `0`.

Decision: Phase 7 preflight is now **PASS** and no PostgreSQL certificate repair is needed. Proceed with an HAProxy-only canary on `ulc-03`; keep PgBouncer undeployed until its client-facing server identity is issued and verified.

First `ulc-03` HAProxy canary harness attempt - 2026-08-23: **INCONCLUSIVE; NO INSTALL OR SERVICE/CONFIG MUTATION.** Patroni baseline passed, then the child gate exited `141` during package-candidate extraction before any `apt-get install` command ran. The harness used `apt-cache policy haproxy | awk '/Candidate:/ {print $2; exit}'` under `set -euo pipefail`; `awk` exited after finding the candidate, the upstream `apt-cache` process received SIGPIPE, and pipefail propagated exit `141`. This is a test-harness failure, not an HAProxy package/configuration failure. Retry with a candidate parser that consumes the full stream and remove other early-exit `grep -q` pipelines from the canary gate.

Corrected `ulc-03` HAProxy database-routing canary - 2026-08-23: **PASS.** The retry re-proved `ulc-02 /leader`, `ulc-01 /replica`, and `ulc-03 /replica` at HTTP `200`; HAProxy candidate `2.8.16-0ubuntu0.24.04.3`; package absence; and free `15432/15433`. `apt-get -s` showed only new `liblua5.4-0` plus the pinned HAProxy package and no removals. The exact package installed successfully. Ubuntu's package post-install created the HAProxy systemd enablement symlink; the gate then stopped the package-default service before replacing its config. The package-default config was backed up at `/etc/haproxy/phase7-canary-20260823-141310/haproxy.cfg.package-default`. Both off-path and installed configs returned `Configuration file is valid`. The validated canary exposed only `10.104.0.8:15432` and `10.104.0.8:15433`. Primary-route verify-full evidence was `10.104.0.4|10.104.0.8|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`; replica-route evidence was `10.104.0.2|10.104.0.8|t|t|TLSv1.3|TLS_AES_256_GCM_SHA384`. Patroni remained healthy with `ulc-02` leader and both replicas streaming with reported lag `0`. The gate explicitly confirmed HAProxy enabled after runtime validation, but the earlier package-created enablement must not be misrepresented as having happened only at that final step. Future rollouts should `disable --now` immediately after package installation before applying the custom config. Child gate exit code was `0`. PgBouncer was not installed or started, and no PostgreSQL/Patroni configuration was changed.

Decision: the HAProxy-only database-routing design is proven on `ulc-03`. Roll the same pinned/private-only configuration to `ulc-01` next, verify routing/TLS/Patroni health there, then deploy to current leader `ulc-02`. Keep PgBouncer blocked until its client-facing TLS identity is issued and verified.

`ulc-01` HAProxy database-routing rollout - 2026-08-23: **PASS.** Patroni baseline remained `ulc-02` leader with `ulc-01`/`ulc-03` replicas and all expected role endpoints HTTP `200`. The same pinned HAProxy candidate `2.8.16-0ubuntu0.24.04.3` was absent before rollout; `15432/15433` were free; and the apt simulation showed only new `liblua5.4-0` plus HAProxy with no removals. After exact-version installation, the package-created service state was explicitly neutralized: `active=inactive`, `enabled=disabled`. The package-default config was preserved at `/etc/haproxy/phase7-rollout-20260823-142347/haproxy.cfg.package-default`. The node-specific config passed off-path and installed syntax validation, then HAProxy started while still disabled. Exact listeners were `10.104.0.2:15432` and `10.104.0.2:15433`. Primary-route verify-full evidence was `10.104.0.4|10.104.0.2|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`; replica-route evidence was `10.104.0.2|10.104.0.2|t|t|TLSv1.3|TLS_AES_256_GCM_SHA384`, valid because local `ulc-01` is a healthy replica backend. Patroni remained healthy with both replicas streaming and reported lag `0`. HAProxy was enabled only after validation. Child gate exit code was `0`. PgBouncer stayed uninstalled and PostgreSQL/Patroni configuration was not changed.

Decision: HAProxy primary/replica routing is now proven on `ulc-03` and `ulc-01`. Roll out the same pinned private-only behavior to current PostgreSQL leader `ulc-02` next, with Patroni role endpoints checked before and after. PgBouncer remains blocked on its missing client-facing TLS identity.

`ulc-02` current-leader HAProxy database-routing rollout - 2026-08-23: **PASS.** Preflight showed the expected role endpoints HTTP `200`, local `pg_is_in_recovery()=f`, and Spilo container identity `2313de94ee2c5dcc292ac28ea7ae8359fbe31b1ea6ab171276306716cff58762|2026-08-22T14:19:16.323317366Z|0`. HAProxy was absent, `15432/15433` were free, candidate `2.8.16-0ubuntu0.24.04.3` matched the pin, and the apt simulation showed only `liblua5.4-0` plus HAProxy with no removals. After installation the package-created service state was deliberately neutralized to `inactive/disabled`; PostgreSQL was rechecked immediately and remained leader with recovery false. The package-default config was backed up at `/etc/haproxy/phase7-rollout-20260823-143511/haproxy.cfg.package-default`. Off-path and installed syntax checks passed. HAProxy then started while still disabled with exact listeners `10.104.0.4:15432` and `10.104.0.4:15433`. Primary-route verify-full evidence was `10.104.0.4|10.104.0.4|f|t|TLSv1.3|TLS_AES_256_GCM_SHA384`; replica-route evidence was `10.104.0.2|10.104.0.4|t|t|TLSv1.3|TLS_AES_256_GCM_SHA384`. The Spilo container identity was unchanged after rollout. Final Patroni state remained `ulc-02` Leader/running timeline `2`, with `ulc-01` and `ulc-03` streaming and reported lag `0`. HAProxy was enabled only after runtime validation. Child gate exit code was `0`; PgBouncer stayed uninstalled and PostgreSQL/Patroni configuration was unchanged.

Decision: **three-node HAProxy database-routing rollout PASS.** All three hosts now have the pinned private-only HAProxy primary/replica path. Do not claim the complete Phase 7 client path yet because PgBouncer is still absent. The next dependency is PgBouncer client-facing TLS issuance.

PgBouncer logical-name standardization checkpoint - 2026-08-23: the operator fixed the permanent private verification name as `pgbouncer.internal.lorawan.com`. Repository PgBouncer references were updated from the former placeholder to this exact name. Each PgBouncer node certificate must be unique while carrying the shared SAN `DNS:pgbouncer.internal.lorawan.com` plus that node's hostname and VPC IP: `ulc-01` / `10.104.0.2`, `ulc-02` / `10.104.0.4`, and `ulc-03` / `10.104.0.8`. The existing `CN = LoRaWAN PostgreSQL Internal CA` is the approved internal CA for these PgBouncer server identities; its private key remains only on `ulc-03` under `/root/lorawan-pg-ca`. Do not distribute the CA private key and do not install/start PgBouncer until the three issued identities pass chain, hostname, logical-name, IP, and key/certificate-match checks.

PgBouncer CA read-only inventory on `ulc-03` - 2026-08-23: **PASS.** `/root/lorawan-pg-ca` remained `0700 root:root`. The inventory identified `/root/lorawan-pg-ca/ca.crt` as the commissioned `CN = LoRaWAN PostgreSQL Internal CA`, valid from `Aug 22 11:07:50 2026 GMT` through `Aug 19 11:07:50 2036 GMT`, with the commissioned SHA-256 fingerprint `99:00:4B:B3:2D:7D:78:FA:38:61:7C:78:89:6D:7A:7E:FF:9F:A6:10:FC:8F:07:D4:E2:5E:35:25:36:E6:CB:3E`. The CA certificate public-key SHA-256 was `2da3b7630e38a1e80469c4d5d1f1c4ac9f1125fb47d6c5a4c2d411960340a2f9`; `/root/lorawan-pg-ca/ca.key` produced the same public-key hash and was the only matching private key. Existing `ulc-01`, `ulc-02`, and `ulc-03` PostgreSQL node keys produced their previously recorded distinct hashes and correctly did not match the CA. No private-key contents were printed, no file was created or modified, child gate exit code was `0`, and the SSH shell remained alive. Decision: exact CA certificate/key paths are now re-proven; PgBouncer certificate staging/issuance is the next bounded step.

Corrected PgBouncer three-node TLS certificate issuance - 2026-08-23: **PASS.** On `ulc-03`, the corrected gate used the exact CA public-key SHA-256 `2da3b7630e38a1e80469c4d5d1f1c4ac9f1125fb47d6c5a4c2d411960340a2f9`, confirmed PgBouncer was still absent, preserved the existing `ca.srl` SHA-256 `966208f925453dbbfa43947a1ad8051097569f3c765cba0ed217b48a8dfe54e6`, and created root-only staging directory `/root/lorawan-pg-ca/pgbouncer-issuance-20260823-150532`. Three unique RSA-3072 node keys were generated and each certificate was signed by `CN = LoRaWAN PostgreSQL Internal CA` for 825 days with `serverAuth`, a random 128-bit serial, and exact SANs `DNS:pgbouncer.internal.lorawan.com`, `DNS:<node>`, and the node's `10.104.0.x` VPC IP. `ulc-01` serial/fingerprint/key-hash: `7C5887FBE0338797CAAC8230AD7D89F8`, `A4:EC:DF:86:30:68:29:88:0F:52:05:0A:E1:B7:E5:F9:3E:B3:4A:72:72:81:96:40:BC:10:7A:EC:94:D2:6D:E1`, `ba76dd9cde0722cb1377446837cfd6f29fffc38550b42a63667c9f2fd8787fc5`; `ulc-02`: `16F56AB3A41FF77DB93EE38EE377164D`, `3B:25:17:30:2B:FB:26:7D:49:F7:C5:24:C5:B0:47:F6:BF:D1:88:64:8D:FD:0E:05:9B:ED:08:32:A1:50:02:EA`, `3dcd2400c7ed3936aa3fb5aa0360c4e3c366153d597edbc20ec6243ec09c68cf`; `ulc-03`: `058F982D16D50B7AE8FF266ACFFBCBBE`, `BC:50:50:8D:FC:60:37:5E:E8:B6:A0:3B:93:41:D7:AB:53:CB:BD:C7:E1:86:3B:1D:FD:AD:D8:94:9E:45:7F:6E`, `4784b3d7c22993eb5e5577b136962a29902d504f59aae71cc2c9de733ab0a716`. All chain, `sslserver` purpose, shared logical hostname, node hostname, node IP, and key/certificate-match checks returned PASS. Unique key/fingerprint/serial counts were all `3`; `ca.srl` remained byte-for-byte unchanged. No CA private key entered a node bundle, PgBouncer stayed uninstalled, HAProxy/PostgreSQL/Patroni were unchanged, child exit code was `0`, and the SSH shell remained alive.

Decision: **PgBouncer three-node TLS issuance boundary PASS.** Next use `ulc-03` for a package/TLS-install canary: apt-simulate and install pinned PgBouncer, neutralize package auto-start/enable state, inspect the real service user/group and packaged config paths, install only the already-verified local `ulc-03` TLS bundle with service-readable/private-key-safe permissions, and keep PgBouncer stopped until its configuration/authentication gate is ready.

First PgBouncer TLS issuance attempt - 2026-08-23: **INCONCLUSIVE / NO CERTIFICATE MUTATION.** The gate again proved the CA directory `0700 0:0`, `ca.crt` `0644 0:0`, `ca.key` `0600 0:0`, the commissioned CA fingerprint, and identical CA certificate/key public-key SHA-256 `2da3b7630e38a1e80469c4d5d1f1c4ac9f1125fb47d6c5a4c2d411960340a2f9`. It then exited `1` because the harness constant accidentally omitted the final `9` from that expected hash. The failure occurred before the staging-directory creation step, so no PgBouncer node private key, CSR, certificate, staging bundle, package, service, HAProxy configuration, or PostgreSQL/Patroni state was changed. Correct only the expected hash and rerun the issuance gate.

PgBouncer exact-package read-only inspection on `ulc-03` - 2026-08-23: **PASS.** The staged `ulc-03` certificate fingerprint remained `BC:50:50:8D:FC:60:37:5E:E8:B6:A0:3B:93:41:D7:AB:53:CB:BD:C7:E1:86:3B:1D:FD:AD:D8:94:9E:45:7F:6E` and verified for `pgbouncer.internal.lorawan.com`. PgBouncer was still absent and `6432` remained free before and after inspection. `apt-cache policy` returned pinned candidate `1.22.0-1build4`; `apt-get -s` showed PgBouncer plus `postgresql-common`, `postgresql-client-common`, `ssl-cert`, `libcares2`, `libevent-2.1-7t64`, and related Perl/JSON dependencies, with no removals. The exact `.deb` was downloaded and extracted only under a temporary off-path directory. Package metadata confirmed amd64 `1.22.0-1build4`. The packaged systemd unit is `/usr/lib/systemd/system/pgbouncer.service` with `User=postgres`, no explicit `Group=`, and `ExecStart=/usr/sbin/pgbouncer /etc/pgbouncer/pgbouncer.ini`. Declared conffiles include `/etc/pgbouncer/pgbouncer.ini` and `/etc/pgbouncer/userlist.txt`. The `postinst` contains `deb-systemd-helper`/`deb-systemd-invoke` logic that enables new installations and attempts service start/restart, so the actual install canary must suppress service starts before package configuration. No package, TLS file, or service was installed/started during this inspection; child exit code was `0` and the SSH shell remained alive.

`ulc-03` PgBouncer package + local TLS install canary - 2026-08-23: **PASS.** Baseline Patroni endpoints were all HTTP `200`; HAProxy remained active with exact private listeners `10.104.0.8:15432` and `10.104.0.8:15433`; Spilo identity before the gate was `7e1c213d1694f37aa08bf2a996a64947b207df5ca9c4366ff0debfab8f2bb123|2026-08-22T14:32:18.26248358Z|0`. The staged `ulc-03` certificate fingerprint `BC:50:50:8D:FC:60:37:5E:E8:B6:A0:3B:93:41:D7:AB:53:CB:BD:C7:E1:86:3B:1D:FD:AD:D8:94:9E:45:7F:6E` and key public hash `4784b3d7c22993eb5e5577b136962a29902d504f59aae71cc2c9de733ab0a716` re-verified before installation. A temporary `policy-rc.d` returned `101`; package configuration therefore did not start `ssl-cert.service`, `postgresql.service`, or `pgbouncer.service`. Exact PgBouncer `1.22.0-1build4` installed with ten new packages total, including `postgresql-common 257build1.1`, `postgresql-client-common 257build1.1`, and `ssl-cert 1.1.2ubuntu1`. PgBouncer was `inactive` but package-enabled immediately after install, then explicitly disabled to `inactive/disabled`; the temporary package policy was restored/removed.

The real host service identity is `uid=110(postgres) gid=114(postgres) groups=114(postgres),113(ssl-cert)`; systemd still has `User=postgres` and no explicit `Group=`. `pg_lsclusters` showed no host PostgreSQL cluster. Package-default configuration was preserved under `/etc/pgbouncer/phase7-package-default-20260823-151910`; packaged modes were `0640 postgres:postgres` for `pgbouncer.ini` and `userlist.txt`, `0644 root:root` for `/etc/default/pgbouncer`. The verified local TLS bundle was installed under `/etc/lorawan-pki/pgbouncer`: directory `0750 root:postgres`; `ca.crt`, `server.crt`, and `server.key` each `0640 root:postgres`. The `postgres` service identity can read all three files; `opsadmin` failed the `server.key` read test with exit `1`. Installed certificate chain, service hostname, node hostname/IP, fingerprint, and key/certificate public hashes all re-verified. PgBouncer remained inactive/disabled with no `6432` listener. Spilo identity after the gate exactly matched before; HAProxy stayed active and all Patroni endpoints remained HTTP `200`. Child gate exit code was `0` and SSH shell remained alive.

Decision: **ulc-03 package + local TLS install canary PASS.** Do not start/configure PgBouncer yet.

`ulc-03` PgBouncer dependency-service collateral check - 2026-08-23: **PASS.** PgBouncer remained `inactive/disabled` with no `:6432` listener. `postgresql.service` was `loaded/inactive/enabled`, `Type=oneshot`, and inspection showed it is only the PostgreSQL meta-service whose `ExecStart=/bin/true`; `pg_lsclusters` returned none, no `postgresql@*.service` instance was loaded or running, and `/etc/postgresql` contained only the top-level package-created directory. `ssl-cert.service` was likewise `loaded/inactive/enabled`, `Type=oneshot`; its unit only generates the default snakeoil keypair when `/etc/ssl/private/ssl-cert-snakeoil.key` does not exist. The temporary `/usr/sbin/policy-rc.d` was absent after restoration. PgBouncer TLS permissions remained `0750 root:postgres` for `/etc/lorawan-pki/pgbouncer` and `0640 root:postgres` for `ca.crt`, `server.crt`, and `server.key`; the `postgres` service identity still passed the private-key read test. HAProxy remained active with exact listeners `10.104.0.8:15432` and `10.104.0.8:15433`, while `ulc-02 /leader`, `ulc-01 /replica`, and `ulc-03 /replica` all remained HTTP `200`. Child gate exit code was `0` and the SSH shell remained alive.

Decision after collateral inspection: the enabled `postgresql.service` and `ssl-cert.service` units are package scaffolding, not active competing services, but neither is needed at boot in this architecture. Spilo owns PostgreSQL and PgBouncer uses the commissioned node certificate rather than snakeoil TLS.

`ulc-03` PgBouncer dependency-service hygiene - 2026-08-23: **PASS.** `systemctl disable --now postgresql.service ssl-cert.service` removed both package-created boot symlinks. Final states were `postgresql.service active=inactive enabled=disabled` and `ssl-cert.service active=inactive enabled=disabled`. No package was uninstalled and no unit was masked. `pg_lsclusters` remained empty and no running `postgresql@*.service` instance existed. The existing snakeoil key `/etc/ssl/private/ssl-cert-snakeoil.key` was preserved and inventoried as `0640 root:ssl-cert`; it is not used by the commissioned PgBouncer TLS path. PgBouncer remained `inactive/disabled` with no `:6432` listener. Its TLS directory remained `0750 root:postgres`, the three TLS files remained `0640 root:postgres`, and the service identity still passed the private-key read test. HAProxy stayed active with exact `10.104.0.8:15432` and `10.104.0.8:15433` listeners. `ulc-02 /leader`, `ulc-01 /replica`, and `ulc-03 /replica` all remained HTTP `200`. Spilo identity remained exactly `7e1c213d1694f37aa08bf2a996a64947b207df5ca9c4366ff0debfab8f2bb123|2026-08-22T14:32:18.26248358Z|0`. Child gate exit code was `0` and the SSH shell remained alive.

Decision: **ulc-03 package/dependency hygiene boundary PASS.** Recheck the two disabled package units after future package upgrades. PgBouncer is still intentionally stopped. Next run a read-only logical-name/SCRAM-verifier preflight before creating `userlist.txt` or activating any PgBouncer configuration.

## 2026-08-24 to 2026-08-25 - Phase 7 and Phase 8 completion checkpoint

The detailed step-by-step evidence remains in [07-haproxy-and-pgbouncer.md](07-haproxy-and-pgbouncer.md) and [08-mqtt-and-valkey.md](08-mqtt-and-valkey.md). This checkpoint records only the final boundaries needed to resume work safely.

**Phase 7 database client path: COMPLETE / PASS.** PgBouncer `1.22.0-1build4` is commissioned on ulc-01, ulc-02, and ulc-03, active and enabled, with client TLS using `pgbouncer.internal.lorawan.com`, SCRAM authentication for the four commissioned application roles, backend verify-full TLS, and local HAProxy primary routing. A controlled Patroni leader change was followed without changing the application endpoint, restarting PostgreSQL, or restarting PgBouncer.

**Phase 8B MQTT core infrastructure: PASS with workload-authentication work deferred.** Mosquitto `2.0.18` is active on ulc-01 and ulc-02. The commissioned broker TLS backends listen on `:8884`; the validated HAProxy TLS-passthrough frontend is `10.104.0.2:8883`; the broker certificate identity verified by clients is `mqtt.internal.lorawan.com`. Stopping the ulc-01 broker caused HAProxy to mark that backend DOWN and TLS service continued through ulc-02; restarting ulc-01 returned both backends online. This proves broker/TLS/failover foundation only. The final ChirpStack MQTT workload identity/ACL policy and a redundant two-application-node MQTT routing boundary are not yet commissioned and are explicit Phase 9 preconditions.

**Phase 8C Valkey HA: COMPLETE / PASS.** Valkey `7.2.13` is TLS-only on all three nodes, using certificate identity `valkey.internal.lorawan.com`, authenticated replication, and failover-safe `masterauth` on every node. Three TLS Sentinel members run on `:26379` with quorum `2`. HAProxy exposes writable-primary endpoints `10.104.0.2:16379` and `10.104.0.4:16379`. Health checks use the separate least-privilege `haproxy-health` identity, CA/SNI verification, exact CRLF `AUTH` and `INFO replication`, and `min-recv 64 string role:master`; the main Valkey password is not stored in `haproxy.cfg`.

The final controlled Valkey test started with ulc-03 as primary, stopped only its Valkey service, and left Sentinel running. Sentinel elected ulc-02 (`10.104.0.4`) after seven polling attempts; all three Sentinels agreed. Both HAProxy `:16379` endpoints were briefly unavailable for one polling attempt, then automatically routed only to the new master. Ten consecutive post-failover requests through each endpoint were master-only with zero errors. Pre-failover data survived, a post-failover write/read across both HAProxy endpoints passed, ulc-03 restarted and rejoined ulc-02 as a replica with `master_link_status:up`, final `connected_slaves=2`, and `CKQUORUM` remained healthy. No HAProxy configuration change/reload occurred during the failover and no manual failback was performed.

Current Valkey topology at this checkpoint:

```text
ulc-02 10.104.0.4 = PRIMARY
ulc-01 10.104.0.2 = REPLICA
ulc-03 10.104.0.8 = REPLICA
Sentinel members = 3
quorum = 2
```

**Next active phase: Phase 9 ChirpStack pre-deployment preflight.** Do not start ChirpStack yet. First pin/inspect the exact image and configuration schema, re-prove local PgBouncer and Valkey client paths, inventory live Mosquitto authentication/ACL directives without printing secrets, commission a least-privilege ChirpStack MQTT identity, and close the second application-node MQTT routing gap. Public HTTPS/Reserved-IP work remains Phase 10.

### Phase 13A read-only cloud preflight - 2026-08-27

The Phase 13A cloud-only baseline was re-established while the separate Gateway OS build continued. Patroni returned exactly one leader (`ulc-01`) and two replicas (`ulc-02`, `ulc-03`); all three etcd `/health` endpoints returned healthy; PgBouncer and PostgreSQL primary/replica HAProxy paths were reachable on all three nodes; both private ChirpStack application nodes returned HTTP `200`; PostgreSQL 18.6, both application databases, TimescaleDB 2.29.2, the two telemetry hypertables, schema version 3, and the expected pre-Phase-12A absence of `telemetry.fabric_outbox` were all confirmed; `pg_dump`/`pg_restore` 18.6 are available; and ulc-03 had about 37.6 GB free for backup work.

The first harness incorrectly required `10.104.0.8:16379` and `10.104.0.8:18883`. This is a **preflight-assumption defect, not an infrastructure failure**. The authoritative service placement exposes writable-primary Valkey HAProxy only on the two application nodes (`10.104.0.2:16379`, `10.104.0.4:16379`) and ChirpStack workload MQTT HAProxy only on the two application nodes (`10.104.0.2:18883`, `10.104.0.4:18883`). ulc-03 runs Valkey/Sentinel and control/backup functions but is not a ChirpStack application node. Do not add either frontend to ulc-03 merely to satisfy the discarded harness. With those two invalid checks removed, `PHASE13A_READONLY_PREFLIGHT=PASS`. Next boundary: create fresh Phase 13A logical dumps of `chirpstack` and `lorawan_telemetry`, validate their catalogs and SHA-256, then preserve them off the target Droplets before the isolated restore rehearsal.

### Phase 13A fresh-backup harness correction - 2026-08-27

The first fresh Phase 13A dump wrapper created `/home/opsadmin/backups/phase13a-20260827T032756Z` and then stopped at its first source assertion before creating either database dump. The query returned `|t` for `host(inet_server_addr()), pg_is_in_recovery()`. This is a **harness defect, not a PostgreSQL placement failure**: `docker exec ... psql` used the local Unix-domain socket, for which `inet_server_addr()` is `NULL`, while `pg_is_in_recovery() = true` correctly proves the local ulc-03 member is a replica. No database mutation occurred and no dump was accepted. Correct the retry by checking host identity outside SQL and asserting replica state only; do not require a server IP from a Unix-socket session.
### Phase 13A fresh logical database backup - 2026-08-27

The corrected retry completed successfully on `ulc-03` using the existing empty timestamped directory `/home/opsadmin/backups/phase13a-20260827T032756Z`. The wrapper verified physical host identity outside SQL and confirmed the local PostgreSQL member is a replica with `pg_is_in_recovery() = true`; both required databases were present. Recorded source state was PostgreSQL `18.6`, ChirpStack object counts `1|0|0|0|0` for tenant/application/device_profile/device/gateway, telemetry counts `0|0|0` for uplinks/measurements/device_registry, TimescaleDB `2.29.2`, hypertables `measurements,uplinks`, and `fabric_outbox_count=0`.

Fresh custom-format archives were then created: `chirpstack.dump` about 99 KiB and `lorawan_telemetry.dump` about 58 KiB, alongside the 257-byte `SOURCE-METADATA.txt` and 257-byte `SHA256SUMS`. Both archives passed `pg_restore --list`; `sha256sum -c SHA256SUMS` returned `OK` for both dumps and the metadata file; all four files are owned by `opsadmin` with mode `0600`. The TimescaleDB warning about circular foreign-key constraints on internal `continuous_agg` is the expected warning for a full custom-format TimescaleDB dump and archive parsing still passed. `PHASE13A_BACKUP_RETRY_EXIT=0`. Next boundary is an independent workstation copy of the complete directory followed by destination-side SHA-256 verification; do not delete the server copy yet.

### Testing-first scope correction - 2026-08-27

The operator explicitly prioritized counted-test functionality over long-term disaster-recovery work. Repository review confirmed that `test/` defines a separate minimum dissertation testbed and explicitly excludes production HA middleware and dashboards from the measured VM. Therefore Phase 13 off-Droplet copy/isolated-restore work is deferred while functional test preparation continues. The fresh local 2026-08-27 `chirpstack` and `lorawan_telemetry` custom-format dumps remain preserved as a local rollback aid; no claim of full Phase 13A PASS is made. The active readiness authority for counted testing is now `test/preparation/00-README.md`: physical RAK5146/AS923 gateway and intended backhaul, seven required test services, EMU-01/SEC-02, ChirpStack -> Node-RED -> TimescaleDB, OpenBao/Fabric evidence, and test evidence tooling.

### HA-preserving test-scope correction - 2026-08-27

The previous testing-first note was too aggressive because it could be read as replacing the already-built HA deployment with the separate minimum seven-service dissertation VM. Operator intent is now explicit: **retain all commissioned HA technologies and normal-path routing exactly as deployed**, while avoiding unnecessary repetition of rigorous DR/failover/restore exercises when the stack is already healthy. Patroni/Spilo, etcd, HAProxy, PgBouncer, Valkey/Sentinel, redundant Mosquitto/ChirpStack paths, and other commissioned HA services remain active. Normal test readiness should use lightweight role/health/listener/routing checks plus one real end-to-end uplink/application/evidence control. Destructive failover, off-host restore, isolated restore, and extended recovery drills are deferred to the dedicated failure-injection/recovery boundary unless new failure evidence requires them sooner. The fresh 2026-08-27 logical dumps remain preserved as the current local rollback aid.
### Phase 20A OpenBao HA deployment preparation - 2026-08-27

OpenBao-only infrastructure was prepared as a parallel-safe task while the physical Gateway OS build remained active. No OpenBao service was started and no cloud listener was changed by this documentation step. The cloud KMS service name is standardized as `openbao-kms.internal.lorawan.com`. Current OpenBao release/security review selected `2.6.2`; registry inspection pinned OCI index digest `sha256:11fd73a2102cda9c55d5d881a8c3210303146a7ec1e8ac76f526e175c6d24641` and Linux/amd64 manifest `sha256:e29524ba7c3f20d01f562c481e3eccbad6c91df45a2f2531433da4951e408cff`. The executable cloud runbook is `20a-openbao-three-node-ha-deployment.md`: one private-TLS/Raft voter per ulc-01/02/03, quorum 2, API `:8200`, Raft `:8201`, HAProxy stable endpoint `:18200` on ulc-01/02, dedicated OpenBao CA, exact-once initialization, 3-share/2-threshold Shamir bootstrap, non-exportable `ecdsa-p256` Transit key, least-privilege sign/verify policy, and normal-path sign/verify only. Failure injection is explicitly deferred to Phase 15.

### Phase 20A OpenBao ulc-01 preflight - 2026-08-27

`ulc-01` passed the read-only OpenBao deployment preflight: private address `10.104.0.2`, Docker Server `29.7.2`, Docker Compose `v5.5.0`, free TCP `8200/8201/18200`, HAProxy active, Docker active, about `40G` root-disk free, and about `1.3 GiB` available RAM. `OPENBAO_PREFLIGHT_EXIT=0`. No service/configuration mutation occurred. Next checkpoint: run the same read-only preflight on `ulc-02`; do not begin PKI or OpenBao startup until all three nodes pass.

### Phase 20A OpenBao ulc-02 preflight - 2026-08-27

`ulc-02` passed the read-only OpenBao preflight: correct `10.104.0.4` private address, Docker `29.7.2`, Compose `v5.5.0`, TCP `8200/8201/18200` free, HAProxy and Docker active, about 40 GiB disk available, and about 1.3 GiB memory available. `OPENBAO_PREFLIGHT_EXIT=0`; no mutation occurred.

### Phase 20A OpenBao ulc-03 preflight - 2026-08-27

`ulc-03` read-only OpenBao preflight **PASS**: private IP `10.104.0.8` present; Docker `29.7.2` and Compose `v5.5.0`; TCP `8200/8201` free; HAProxy and Docker active; root filesystem about 36 GiB available; about 1.3 GiB memory available; no swap. `OPENBAO_PREFLIGHT_EXIT=0` and login shell survived. With ulc-01 and ulc-02 already passed, the OpenBao three-node pre-mutation gate is now **3/3 PASS**. No OpenBao service or listener has been created yet. Next mutation boundary: dedicated OpenBao PKI issuance on ulc-03.

### Phase 20A OpenBao PKI issuance - 2026-08-27

**PASS.** `ulc-03` created the dedicated `CN=LoRaWAN OpenBao Internal CA`, verified CA certificate/private-key matching, and issued unique server identities for ulc-01/02/03 from `/root/lorawan-openbao-ca/issuance-20260827T050939Z`. CA certificate SHA-256: `18a8d9960b5a0bc0476e64628bdac0e00069aeae6b6ec7f0c95324fda119af6d`. All three node certificates passed CA chain, serverAuth, shared KMS hostname, node hostname/IP, and key-match checks. Unique certificates/private keys/serials were `3/3/3`; `OPENBAO_PKI_EXIT=0`. CA private key remains restricted to ulc-03.
### Phase 20A OpenBao ulc-03 immutable image canary - 2026-08-27

PASS. `ulc-03` pulled and verified `docker.io/openbao/openbao@sha256:11fd73a2102cda9c55d5d881a8c3210303146a7ec1e8ac76f526e175c6d24641`. RepoDigest matched, platform was `linux/amd64`, CLI reported OpenBao `v2.6.2` commit `dd9c19c37a878cf4a81b18efb8d6f0599c7da923`, and ports `8200/8201` remained free with no OpenBao service started. `OPENBAO_IMAGE_CANARY_EXIT=0`.

### Phase 20A OpenBao three-node immutable image rollout - 2026-08-27

PASS. The pinned OpenBao v2.6.2 OCI digest `sha256:11fd73a2102cda9c55d5d881a8c3210303146a7ec1e8ac76f526e175c6d24641` is present on ulc-01/02/03. ulc-01 and ulc-02 verified linux/amd64, OpenBao UID/GID 100/1000, existing HA services healthy, and no OpenBao runtime state/listeners after pull. ulc-03 had already passed the same image canary. `OPENBAO_IMAGE_3_OF_3=PASS`; `OPENBAO_SERVICE_STARTED=NO`.

### Phase 20A OpenBao TLS/runtime staging - 2026-08-27

`ulc-03`, `ulc-01`, and `ulc-02` each passed dedicated OpenBao TLS/runtime staging. The image runtime identity was `openbao` / UID `100` / GID `1000`; private server keys are mode `0400` owned by that numeric identity, public certificates are root-owned read-only, and `/srv/openbao/data` is mode `0700` owned by `100:1000`. Every node re-verified its CA/hostname/IP/key match, the container identity could read TLS and write Raft storage, and no OpenBao service/listener was started. The enclosing operator block returned `PHASE20A7_EXIT=0`.

### Phase 20A OpenBao configuration/Compose validation - 2026-08-27

- ulc-03: `OPENBAO_NODE_CONFIGURATION=PASS`
- ulc-01: `OPENBAO_NODE_CONFIGURATION=PASS`
- ulc-02: `OPENBAO_NODE_CONFIGURATION=PASS`
- exact image configuration validation: PASS on all three
- Compose model validation: PASS on all three
- OpenBao service started: NO
- operator exit: `PHASE20A89_EXIT=0`
- login shell survived: YES
- next boundary: start ulc-01 only and verify uninitialized/sealed state before initialization

### Phase 20A OpenBao seed-start first attempt - 2026-08-27

**INCOMPLETE / NO START.** Operator output proved only `ULC03_OPENBAO_STOPPED=PASS` and `ULC02_OPENBAO_STOPPED=PASS`, then returned `PHASE20A10_PREINIT_EXIT=0`. No ulc-01 start/TLS/status evidence appeared. Cause: non-interactive SSH consumed the remainder of an outer stdin-fed heredoc. Do not initialize OpenBao from this result. Corrected wrappers must protect SSH stdin and require ulc-01 `Initialized=false` / `Sealed=true` evidence.

### Phase 20A OpenBao seed pre-initialization gate - 2026-08-27

- ulc-01 OpenBao v2.6.2 started successfully.
- TLS health endpoint returned HTTP 501 as expected for an uninitialized node.
- initialized=false, sealed=true, storage_type=raft, ha_enabled=true.
- Container running=true, restart_count=0.
- ulc-02 and ulc-03 remained stopped.
- OPENBAO_SEED_PREINIT_GATE=PASS.
- OPENBAO_INITIALIZATION_EXECUTED=NO.
### Phase 20A operator-shell safety correction - 2026-08-27

During the first one-time-initialization operator attempt, the `ulc-03` SSH login session closed after the block was launched. Do not infer initialization success or failure from the terminal closure alone. Root cause risk identified: `set -euo pipefail` was enabled directly in the interactive login shell, so any later non-zero command could terminate that SSH session. Remaining Phase 20A strict-mode blocks must execute inside child scripts/subshells. Before any initialization retry, perform a read-only recovery check of `ulc-01` initialization state and both the final and temporary bootstrap files without printing their contents.

### Phase 20A initialization recovery timeout correction - 2026-08-27

The first read-only recovery probe stalled at `/v1/sys/init` because the diagnostic curl had no bounded timeout. No initialization mutation is inferred from that stall. Recovery guidance now requires bounded curl/CLI probes and treats timeout as unknown state; operator must not rerun `bao operator init` until bootstrap-file and API state are rechecked.

### Phase 20A initialization recovery attempt 1 - 2026-08-27

- Read-only recovery probe reached `ulc-01`; container state was `openbao_running=true`.
- `/v1/sys/init` probe hung because the diagnostic curl had no hard timeout and was interrupted with `Ctrl+C`.
- Nested SSH exit: `255`. Diagnostic cleanup passed.
- `ulc-02` and `ulc-03` remained stopped.
- Initialization state remains UNKNOWN; do not rerun `bao operator init` until a bounded recovery check proves state.

### Phase 20A initialization recovery attempt 2 - 2026-08-27

- bootstrap final file: absent
- bootstrap temporary file: present, `0600 root:root`, zero bytes, SHA-256 of empty file
- OpenBao container: running, restart count 0
- bounded `bao status`: timeout
- bounded `/v1/sys/init`: timeout
- decision: `UNKNOWN_REQUIRES_REVIEW`; do not rerun `operator init`
- ulc-02 / ulc-03 remained stopped
- next: read-only ulc-01 process/log/Raft-state inspection before any mutation

### Phase 20A initialization recovery attempt 3 - 2026-08-27

Read-only inspection on `ulc-01` found no lingering init/exec process, but Raft state files had been created while the protected init output remained empty. TLS handshake verification passed; the HTTP health probe timed out. Current classification: **partial Raft bootstrap / core unresponsive**. No retry, restart, Raft deletion, unseal, or peer start is authorized yet.

### Phase 20A initialization recovery attempt 4 - 2026-08-27

The recovery-4 evidence proved the first initialization crossed the Raft/security-barrier boundary (`ulc-01` single voter/leader; `shares=3`, `threshold=2`) but returned no bootstrap JSON: the protected temp file stayed zero bytes. OpenBao was not OOM-killed, restart count was zero, resource usage was low, and no kernel/storage error was found. This is therefore a lost-bootstrap-secret event on a new empty OpenBao cluster. Do not retry init against the existing Raft state. Next checkpoint: preserve a root-only forensic archive, stop only OpenBao on ulc-01, reset only its fresh OpenBao Raft data and zero-byte temp file, remove retry_join from the seed config, use Compose command `server` only, restart ulc-01, and require a fresh `initialized=false / sealed=true` gate before reinitialization.

### Phase 20A controlled seed recovery - 2026-08-27

PASS. Archived the unusable partial bootstrap, reset only the fresh OpenBao seed state on ulc-01, removed seed retry_join, corrected Compose to `command: ["server"]`, and returned ulc-01 to `initialized=false`, `sealed=true`, health 501, restart count 0. ulc-02/03 remained stopped. No reinitialization was executed. `PHASE20A_SEED_RECOVERY_EXIT=0`; `LOGIN_SHELL_SURVIVED=YES`.

### Phase 20A second protected initialization - 2026-08-27

PASS: protected transient systemd initialization on ulc-01 completed successfully. Three unique Shamir shares, threshold two, and the initial root token were stored only in root-only `/root/lorawan-openbao-bootstrap/init.json` (SHA-256 `66045a7bd3cd715c198fe2ad1c536bfa535aa96bcab47ddd8abf8b7ea5ad9831`) and were not printed. OpenBao is initialized and sealed; ulc-02/03 remain stopped. Next gate: unseal ulc-01 only.

### Phase 20A.11 OpenBao seed unseal - 2026-08-27

PASS. ulc-01 was unsealed with two distinct Shamir shares read from the protected bootstrap file without printing or copying the shares. Status: initialized=true, sealed=false, HA enabled, health HTTP 200, listeners 8200/8201 present, restart count 0. ulc-02 and ulc-03 remained stopped. PHASE20A11_UNSEAL=PASS; PHASE20A11_UNSEAL_EXIT=0; LOGIN_SHELL_SURVIVED=YES.

### Phase 20A.12 ulc-02 join attempt 1 - 2026-08-27

`ulc-02` started and locally reported initialized/sealed Raft state, but `ulc-01` still listed only itself as a voter. The control step stopped before unseal. No Shamir share was submitted; `ulc-03` remained stopped. Next action: read-only retry_join/log/membership diagnostics.

### Phase 20A.12 Shamir join-order correction - 2026-08-27

The first ulc-02 control assertion expected Raft membership before unseal. OpenBao Shamir join semantics require threshold unseal shares before the encrypted retry_join challenge can complete. The observed `initialized=true`, `sealed=true`, HTTP 503 state is therefore the expected join-pending state. No share had yet been submitted and no cluster damage occurred. Continue by unsealing ulc-02 from ulc-01 protected bootstrap material, then verify exactly two Raft voters.

### Phase 20A.12 ulc-02 unseal attempt 2 - 2026-08-27

ulc-02 was still initialized/sealed join-pending. Share 1 advanced unseal progress to 1; share 2 returned sealed=true with progress reset to 0. The wrapper stopped before any further share submission. ulc-03 remained stopped. State requires log/membership diagnosis before retry.

### Phase 20A.12 post-threshold diagnostic wrapper correction - 2026-08-27

The first post-threshold read-only diagnostic was **INCOMPLETE**: `ssh -n ... bash -s <<HEREDOC` discarded the heredoc because `-n` redirects SSH stdin to `/dev/null`. Only local wrapper markers ran. No OpenBao or Raft state was changed and no additional Shamir share was submitted. Retry with copied remote scripts before deciding whether a second unseal cycle is required.

### Phase 20A.12 ulc-02 join completed - 2026-08-27

PASS: ulc-02 is initialized=true, sealed=false, restart_count=0, and listening on 10.104.0.4:8200/8201. Logs confirm successful Raft join and post-unseal completion. Authoritative leader configuration shows exactly two voters: ulc-01 leader and ulc-02 follower. No second unseal cycle is required. ulc-03 remains stopped.

### Phase 20A.12C ulc-03 join completed - 2026-08-27

PASS: ulc-03 joined the existing OpenBao Raft cluster using retry_join and two protected Shamir shares submitted from ulc-01. Final authoritative membership is exactly three voters with ulc-01 leader and ulc-02/ulc-03 followers. ulc-03 is initialized=true, sealed=false, healthy HTTP 200, restart_count=0, and bootstrap material was not copied to it. `PHASE20A12_ULC03=PASS`; `PHASE20A12_ULC03_EXIT=0`; `LOGIN_SHELL_SURVIVED=YES`.
### Phase 20A.13A Transit bootstrap preflight - 2026-08-27

PASS. Three OpenBao members healthy HTTP 200; authoritative Raft membership 3 voters. Clean admin baseline: transit mount absent, AppRole auth absent, lorawan-evidence key absent, fabric-evidence-signer policy absent, fabric-adapter role absent. No root token printed, no SecretID issued, and no administrative mutation executed. Next mutation is transit mount enable only.

### Phase 20A.13B Transit mount enable - 2026-08-27

- `transit/` precondition: absent.
- Enabled once; verified mount type `transit`.
- `lorawan-evidence`: absent.
- signer policy: absent.
- AppRole auth: absent.
- `fabric-adapter` role: absent.
- SecretID issued: no.
- OpenBao health after mutation: 3/3 HTTP 200.
- Result: `PHASE20A13B_TRANSIT=PASS`, exit `0`, login shell survived.
### Phase 20A.13B accidental rerun refusal - 2026-08-27

- `transit/` already existed as expected from the prior successful 20A.13B step.
- The rerun failed at the precondition assertion before any mutation.
- No Transit mount, key, policy, auth method, AppRole, or SecretID was changed.
- Continue with Phase 20A.13C.

### Phase 20A.13C evidence key creation - 2026-08-27

PASS: `lorawan-evidence` created once as ECDSA P-256 with export disabled, plaintext backup disabled, deletion disabled, version 1. Cluster health remained 3/3. No policy, AppRole, role, SecretID, or rotation performed.

### Phase 20A.13D signer policy creation - 2026-08-27

PASS. Created `fabric-evidence-signer` with exactly two update-only paths for `lorawan-evidence` sign and verify. Verified zero extra paths/capabilities, key remained version 1 and protected, AppRole remained disabled, no SecretID was issued, and OpenBao health stayed 3/3.

### Phase 20A.13E AppRole precondition refusal - 2026-08-27

- Existing `approle/` mount detected before mutation; guard exited nonzero.
- No AppRole enable request was executed by this run.
- Evidence key precondition passed.
- Next action is read-only verification of existing AppRole mount and absence of `fabric-adapter` role before any role creation.
### Phase 20A.13E-R policy verifier schema mismatch - 2026-08-27

- AppRole mount verified: `approle`, `local=false`, built-in OpenBao v2.6.2 plugin.
- `fabric-adapter` role absent; no SecretID issued.
- `lorawan-evidence` key unchanged.
- Read-only policy verification stopped on `KeyError: rules`; no administrative mutation occurred.
- Next action: inspect the actual ACL-policy API response shape read-only, then verify the existing policy without changing it.

### Phase 20A.13E existing AppRole verification - 2026-08-27

PASS. Corrected read-only verification proved the existing `approle/` mount is the built-in OpenBao v2.6.2 AppRole auth method with `local=false`; `fabric-adapter` remains absent; no SecretID was issued; the evidence key and signer policy remain unchanged. No auth mount mutation was performed. The origin of the already-present mount remains unproven and is not asserted.

### Phase 20A.13F fabric-adapter AppRole creation - 2026-08-27

PASS: created and verified `fabric-adapter` with policy `fabric-evidence-signer`, token TTL 1h, max TTL 4h, SecretID TTL 24h, unlimited SecretID uses (`0`), and `bind_secret_id=true`. RoleID exists but was not printed; no SecretID was issued. OpenBao 3/3 health remained HTTP 200.
### Phase 20A.13G final Transit/AppRole acceptance - 2026-08-27

PASS. Final read-only acceptance proved three Raft voters, healthy 3/3 OpenBao nodes, protected Transit key version 1, exact update-only signer policy, valid cluster-wide AppRole, exact `fabric-adapter` role settings, RoleID present but undisclosed, and zero SecretID accessors. `PHASE20A13G_EXIT=0`; Phase 20A.13 is complete.

### Phase 20A.14A ulc-01 HAProxy preflight - 2026-08-27

PASS. `ulc-01` HAProxy remained unchanged and valid at SHA-256 `4b36b3b0b17a8ac438d758dcec291e2f4878c66da090b60e8d07e9003e900808`; the complete existing listener baseline was recorded, `:18200` and OpenBao HAProxy names were free, the staged HAProxy CA matched the OpenBao CA, and TLS health checks to all three OpenBao APIs returned HTTP `200`. No HAProxy reload or file/service mutation occurred. Next: Phase 20A.14B rollback-safe `ulc-01` KMS frontend rollout.

### Phase 20A.14B ulc-01 HAProxy KMS rollout - 2026-08-27

PASS. Baseline config SHA-256 `4b36b3b0b17a8ac438d758dcec291e2f4878c66da090b60e8d07e9003e900808` was preserved in `/etc/haproxy/phase20a14b-20260827T080548Z/haproxy.cfg.before-openbao`. Validated candidate installed as SHA-256 `31d17ede04a05be0b812de3eb602e18656880a7dbd2fc718908d2b63eb7bcf47`. HAProxy reload passed, all prior listeners remained present, exactly one new private KMS listener exists at `10.104.0.2:18200`, TLS hostname verification and repeated stable-path HTTP 200 probes passed, direct OpenBao 3/3 health remained 200, rollback was not executed, and `ulc-02` was not modified. `PHASE20A14B_ULC01=PASS`; `PHASE20A14B_EXIT=0`; login shell survived.
### Phase 20A.14C ulc-02 HAProxy preflight - 2026-08-27

PASS. Read-only preflight recorded HAProxy config SHA-256 `30bdeef9cc99f574d75be9c33fd86359198cec001946eb2d542ebeeb1b891cf3`; preserved listener inventory including `127.0.1.1:15432`; confirmed TCP/18200 and OpenBao HAProxy names free; CA copy matched; `ulc-01:18200` returned 200; direct OpenBao 3/3 returned 200; no mutation occurred.

### Phase 20A.14D ulc-02 HAProxy KMS rollout - 2026-08-27

PASS. Baseline SHA-256 `30bdeef9cc99f574d75be9c33fd86359198cec001946eb2d542ebeeb1b891cf3`; rollback backup `/etc/haproxy/phase20a14d-20260827T082022Z/haproxy.cfg.before-openbao`; final SHA-256 `7b2f1520bb07d10438f65cc08936bc7a331fd685ae23b3974e514def1f0a3f46`. All eight pre-existing `ulc-02` HAProxy listeners, including `127.0.1.1:15432`, remained present; new private KMS listener `10.104.0.4:18200` passed TLS hostname verification and HTTP `200`; both stable KMS frontends passed repeated probes; all three direct OpenBao APIs remained HTTP `200`; rollback not executed. Phase 20A.14 is complete. Server OpenBao work is intentionally paused before Phase 20A.15 while Gateway Phase 11 resumes.

### Server-first continuation / Gateway deferred - 2026-08-27

The operator cannot currently access the physical gateway and explicitly deferred Gateway Phase 11. The commissioned cloud/server stack remains the active work track. Resume from the authoritative OpenBao checkpoint: **Phase 20A.14 is COMPLETE / PASS** and the next server boundary is **Phase 20A.15 local service-name mapping**, followed by **Phase 20A.16 normal-path acceptance**. Do not repeat the completed OpenBao HAProxy rollout unless its configuration or routing changes. Apply Phase 20A.15 sequentially to `ulc-01` and then `ulc-02`, verifying each node before modifying the next. Gateway work remains deferred only; it is not cancelled or marked complete.

### Phase 20A.15 local KMS service-name mapping - 2026-08-27

**PASS.** The complete operator wrapper ran from `ulc-03` and first re-proved SSH identity for both application nodes using the existing root-controlled deployment key. On `ulc-01`, `/etc/hosts` had no prior active mapping for `openbao-kms.internal.lorawan.com`; a rollback copy was created at `/root/phase20a15-ulc-01-20260827T131136Z/hosts.before`, then the stable name was mapped exactly to the local HAProxy address `10.104.0.2`. `getent ahostsv4` resolved only `10.104.0.2`, OpenSSL hostname verification through `:18200` passed, the normal resolver-path OpenBao health request returned HTTP `200`, and HAProxy configuration remained valid. On `ulc-02`, the same guarded sequence created rollback copy `/root/phase20a15-ulc-02-20260827T131138Z/hosts.before`, mapped the shared KMS name exactly to local HAProxy `10.104.0.4`, resolved only `10.104.0.4`, passed TLS hostname verification, returned HTTP `200` through the normal resolver path, and left HAProxy valid. Both per-node gates passed, the enclosing operator returned `PHASE20A15_OPERATOR_EXIT=0`, and the `ulc-03` login shell survived.

Decision: **Phase 20A.15 is COMPLETE / PASS.** The two future adapter/application hosts now use one TLS verification name while each resolves it to its own HAProxy KMS frontend; no mapping points directly at an OpenBao Raft member. Next: Phase 20A.16 normal-path acceptance. Run TLS/health acceptance from both application nodes, then perform exactly one short-lived `fabric-evidence-signer` Transit sign/verify test through the stable `ulc-01` HAProxy endpoint. Do not rotate the Transit key and do not inject failure during this acceptance.


### Phase 20A.16 normal-path acceptance - 2026-08-27

PASS. From ulc-03, both application nodes were verified through their local stable KMS mappings: ulc-01 resolved `openbao-kms.internal.lorawan.com` to `10.104.0.2`, ulc-02 to `10.104.0.4`; both HAProxy configs/listeners were valid, TLS hostname verification passed, and stable-path OpenBao health returned HTTP 200. One short-lived commissioning token on ulc-01 was created with exactly `fabric-evidence-signer` and no default policy; Transit sign passed, verify returned true, key version stayed 1, the token was revoked, final KMS health remained 200, no failure injection occurred, and the ulc-03 operator wrapper exited 0.

### Phase 20A.17 prepared PASS boundary - 2026-08-27

COMPLETE / PASS. The full OpenBao three-node normal-path prepared boundary is satisfied. Keep all three OpenBao members running. `OPENBAO_3_NODE_NORMAL_PATH=PASS`; failure tests remain deferred to Phase 15. Fabric-adapter runtime remains blocked until a reviewed implementation/image and external Fabric handoff exist; no adapter SecretID has been issued. The next productive server-side work can proceed at the telemetry/Fabric outbox boundary without inventing an adapter runtime.

### Fabric outbox database read-only preflight - 2026-08-27

PASS. Driven entirely from `ulc-03`, Patroni discovery returned exactly one leader (`ulc-01` / `10.104.0.2`) and two replicas (`ulc-02`, `ulc-03`). All three Spilo containers were running with restart count 0; PostgreSQL was `18.6`; `lorawan_telemetry` and schema `telemetry` remained owned by `telemetry_admin`; TimescaleDB was `2.29.2`; all six commissioned telemetry objects and exactly the `measurements,uplinks` hypertables were present. `telemetry.fabric_outbox` was absent on all three nodes. `fabric_adapter` remained LOGIN with a SCRAM verifier but had no schema `telemetry` usage and no SELECT on `uplinks`, `measurements`, or `device_registry`. `FABRIC_OUTBOX_READONLY_PREFLIGHT=PASS`; operator exit `0`; no database mutation occurred. The known locale warnings were non-blocking. Next boundary is first-install outbox schema/constraint/index/immutability/ACL commissioning, after revalidating the preserved 2026-08-27 local logical rollback dump. The reviewed Fabric adapter runtime/image remains absent and is not to be invented or deployed.
### Fabric outbox commissioning attempt 1 - host pg_restore harness failure - 2026-08-27

The first Fabric outbox first-install commissioning wrapper stopped during the pre-migration rollback-aid gate before discovering the Patroni leader or executing any SQL mutation. `sha256sum -c` passed for `chirpstack.dump`, `lorawan_telemetry.dump`, and `SOURCE-METADATA.txt`, proving the preserved Phase 13A files remained byte-for-byte intact. The next check invoked host-side `pg_restore --list` on `ulc-03`; Ubuntu `pg_wrapper` returned `No existing cluster is suitable as a default target` / `You must install at least one postgresql-client-<version> package`. This is a **harness/tool-location failure**, not archive corruption and not a PostgreSQL/Patroni failure. `FABRIC_OUTBOX_COMMISSION_OPERATOR_EXIT=1`; `ULC03_LOGIN_SHELL_SURVIVED=YES`. No database mutation occurred and `telemetry.fabric_outbox` remains absent.

Correction: do not install a duplicate PostgreSQL client on the host merely for this gate. Use the already-commissioned PostgreSQL 18.6 utilities inside the local `spilo` container and stream the host-owned custom-format archive to stdin, e.g. `sudo docker exec -i spilo pg_restore --list < "$TELEMETRY_DUMP"`. Re-run only the corrected read-only backup/catalog gate first; proceed to outbox SQL only after it passes.

### Fabric outbox corrected backup/catalog gate - 2026-08-27

**PASS / READ ONLY.** The corrected ulc-03 pre-migration gate revalidated the preserved `/home/opsadmin/backups/phase13a-20260827T032756Z` rollback aid without installing any host PostgreSQL client. `sha256sum -c SHA256SUMS` passed for `chirpstack.dump`, `lorawan_telemetry.dump`, and `SOURCE-METADATA.txt`. The local `spilo` container was running and provided `pg_restore (PostgreSQL) 18.6 (Ubuntu 18.6-1.pgdg22.04+2)`. Streaming `lorawan_telemetry.dump` into `sudo docker exec -i spilo pg_restore --list` parsed the custom-format archive successfully with 129 catalog lines. The catalog contained no `fabric_outbox`, proving the backup remains the intended pre-outbox rollback point. A live read-only SQL check still returned `to_regclass('telemetry.fabric_outbox') IS NULL`; no earlier commissioning mutation exists. `FABRIC_OUTBOX_CORRECTED_PREFLIGHT=PASS`; operator exit `0`; login shell survived. The repeated container locale warnings remain non-blocking hygiene noise. Next boundary: migration-only outbox schema/constraint/index/immutability/ACL commissioning; do not repeat the already-passed backup gate unless the backup files change.

### Fabric outbox commissioning attempt 2 - PostgreSQL 18 constraint-catalog verifier mismatch - 2026-08-27

The first real outbox schema/ACL transaction executed on the dynamically discovered Patroni primary `ulc-01` and **committed successfully**: `PRIMARY_PRE_MIGRATION_GATE=PASS` followed by `OUTBOX_DDL_ACL_TRANSACTION=PASS`. The first post-commit structure read-back returned `telemetry_admin|25|17|3|1|telemetry_admin|0|0` for owner/columns/total-pg_constraint-rows/worker-indexes/trigger/function-owner/hypertable/rows. The wrapper expected six total `pg_constraint` rows and stopped before the ACL and rollback-only functional probes. This is a **post-commit verifier defect; do not rerun the migration**. PostgreSQL 18 stores column `NOT NULL` specifications as first-class `pg_constraint` entries (`contype='n'`). This table has eleven NOT NULL constraints plus the six intended primary-key/unique/check constraints, yielding the observed total of 17. Correct validation must report the PostgreSQL-18 constraint-type distribution and compare only the six non-NOT-NULL constraints (`contype <> 'n'`) against the expected named set. The committed outbox must now be verified read-only on all three members, then the skipped ACL/rollback-only probes may run against the existing table. `FABRIC_OUTBOX_MIGRATION_OPERATOR_EXIT=1` reflects only the stale verifier assertion; the login shell survived.

### Fabric outbox schema commissioning - 2026-08-27

**COMPLETE / PASS.** The first-install `telemetry.fabric_outbox` DDL/ACL transaction had already committed successfully on the dynamically discovered Patroni primary `ulc-01`. The initial post-commit verifier failed only because PostgreSQL 18 represents column `NOT NULL` constraints in `pg_constraint` as `contype='n'`; the live table correctly contained `17` total constraints = `11` NOT NULL + `6` intended application constraints. The corrected PostgreSQL-18-aware acceptance verified the exact 25-column table owned by `telemetry_admin`, 11 NOT NULL columns, six application constraints, three worker indexes, one immutability trigger/function owned by `telemetry_admin`, and confirmed `fabric_outbox` is an ordinary PostgreSQL table rather than a Timescale hypertable.

The committed schema and ACLs were verified on all three Patroni members. `fabric_adapter` has schema usage plus SELECT on `uplinks`, `measurements`, and `fabric_outbox`, no INSERT/DELETE on the outbox, and UPDATE only on the exact 18 worker/seal/result columns. `telemetry_writer` can INSERT/SELECT and use/select the outbox identity sequence but cannot UPDATE; `telemetry_reader` is SELECT-only. Rollback-only functional probes proved `telemetry_writer` can enqueue, `fabric_adapter` can modify only approved operational columns, `fabric_adapter` cannot modify source identity, the source-identity trigger rejects owner-level identity edits, and the completed-seal trigger rejects evidence replacement. All commissioning probe rows rolled back; persisted commissioning rows = `0`. `FABRIC_OUTBOX_SCHEMA_COMMISSIONING=PASS`; `FABRIC_OUTBOX_POSTCOMMIT_OPERATOR_EXIT=0`; the ulc-03 login shell survived.

Decision: the outbox database layer is commissioned and replicated 3/3. Keep Node-RED outbox enqueue disabled until Phase 12A application-path commissioning. The reviewed Fabric adapter runtime/image is still absent and must not be invented or deployed.
### Phase 12A server preflight attempt 1 - PgBouncer CA harness permission stop - 2026-08-27

The first ulc-03-driven Phase 12A server-only read-only preflight proved the control host/deployment key, HAProxy configuration validity, local PgBouncer `10.104.0.8:6432`, and local PostgreSQL HAProxy `10.104.0.8:15432`. It then stopped before any MQTT broker inspection or mutation because the TLS verification command invoked `openssl s_client` as `opsadmin` while referencing `/etc/lorawan-pki/pgbouncer/ca.crt`. The commissioned PgBouncer PKI boundary is deliberately `750 root:postgres` for the directory and `640 root:postgres` for files, so the operator account cannot traverse/read that CA path directly. OpenSSL returned `BIO_new_file: Permission denied`; `PHASE12A_SERVER_PREFLIGHT_OPERATOR_EXIT=1`, and the ulc-03 login shell survived. This is a client-harness privilege mismatch, not PgBouncer TLS failure. No Mosquitto, HAProxy, Node-RED, PKI, or database mutation occurred. Correct the retry by executing only the OpenSSL TLS verification under `sudo` while keeping the protected PKI permissions unchanged.

### Phase 12A PgBouncer raw-TLS harness correction - 2026-08-27

The privileged retry of the ulc-03 PgBouncer TLS probe removed the earlier CA permission error but returned OpenSSL `ssl3_get_record:wrong version number` against `10.104.0.8:6432`. This is **not** a PgBouncer TLS regression. The retry still used raw `openssl s_client` TLS from byte zero; PostgreSQL/PgBouncer first requires a PostgreSQL SSLRequest message and only then upgrades the connection to TLS. No service/config/database mutation occurred. Correct the read-only harness with `openssl s_client -starttls postgres` plus the existing `sudo` CA access, or use the already-proven `psql sslmode=verify-full` client pattern. Do not modify PgBouncer TLS, HAProxy, or PKI permissions in response to this result.

### Phase 12A PgBouncer STARTTLS verification - 2026-08-27

PASS. From `ulc-03`, the protected PgBouncer CA was read under `sudo` without changing ownership or mode, and `openssl s_client -starttls postgres` successfully negotiated the PostgreSQL SSLRequest upgrade to `10.104.0.8:6432`. TLS negotiated as `TLSv1.3` / `TLS_AES_256_GCM_SHA384`; the peer certificate CN was `pgbouncer.internal.lorawan.com`; CA verification returned `OK`; and the verified peer name matched `pgbouncer.internal.lorawan.com`. This closes both earlier harness defects: non-root CA access and raw-TLS use without PostgreSQL STARTTLS. No PgBouncer, HAProxy, PKI, database, or Node-RED mutation occurred. Next: read-only live inventory of Mosquitto `:8884` authentication/ACL state on `ulc-01` and `ulc-02`.

### Phase 12A MQTT :8884 live-auth inventory partial - 2026-08-27

The read-only inventory reached ulc-01 and proved the active `:8884` listener currently uses TLS 1.3 with the commissioned MQTT PKI, `require_certificate false`, and `allow_anonymous false`; no active `use_identity_as_username` directive was observed before the wrapper stopped. The separate `:8885` ChirpStack password/ACL listener remains distinct. This confirms the current ulc-01 `:8884` path is not client-certificate-authenticated, despite older Phase 12A planning language calling it mTLS. Phase 9 had already proven effective anonymous MQTT denial on both brokers by CONNACK `0x05`. The wrapper then exited because an optional-directive `grep` returned no matches under `set -euo pipefail`; no runtime mutation occurred. Correct the parser and inspect ulc-02 before any Node-RED certificate/ACL or broker change.

### Phase 12A MQTT listener-specific inventory and Node-RED design - 2026-08-27

PASS / READ ONLY. Both ulc-01 and ulc-02 reported `per_listener_settings=true`; existing Mosquitto `:8884` is TLS 1.3 with `require_certificate=false`, `allow_anonymous=false`, no `use_identity_as_username`, and no listener-local password/ACL/plugin. Verified TLS without a client certificate succeeded on both with `mqtt.internal.lorawan.com`; `:8886` was free on both. Combined with the prior Phase 9 CONNACK `0x05` proof, the live `:8884` boundary is server TLS plus anonymous denial, not mTLS. No Mosquitto, HAProxy, PKI, or Node-RED mutation occurred. Design decision: preserve `:8884` and ChirpStack `:8885`; use dedicated Node-RED mTLS backends `ulc-01/02:8886` behind ulc-03 HAProxy `:18884`, with client identity `node-red-ingest` and read-only application-uplink ACL. Provider private-firewall documentation now reserves `8886/tcp` only for the ulc-03 Node-RED path to the two brokers. Next: read-only client-certificate issuance preflight on ulc-03 before any PKI or broker mutation.

### Phase 12A Node-RED MQTT PKI preflight broker-check harness stop - 2026-08-27

Read-only Node-RED MQTT PKI preflight steps 1-8 passed on `ulc-03`: commissioned CA ownership/modes, CA identity, CA certificate/private-key public-key match, local MQTT CA hash match, CA serial baseline capture, absence of any existing `CN=node-red-ingest` certificate, and clear `/etc/lorawan-pki/node-red-mqtt` client-identity path. The first `ulc-01` broker trust subcheck then failed only because the remote command sent `awk '{print \$1}'`, causing awk to reject the literal backslash. No broker CA comparison result was produced and no runtime/PKI/configuration mutation occurred. The corrected continuation must parse SSH output locally rather than nesting awk through SSH.

### Phase 12A Node-RED MQTT PKI preflight complete - 2026-08-27

The corrected broker-trust continuation completed the Node-RED MQTT client-PKI preflight as **PASS**. Both `ulc-01` and `ulc-02` returned the commissioned MQTT CA SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`; `:8886` was free on both; existing `:8884` and `:8885` listeners remained present; and the earlier CA boundary, CA certificate/key match, ulc-03 MQTT trust copy, CA serial baseline, unused `node-red-ingest` identity, and clear `/etc/lorawan-pki/node-red-mqtt` target path all remained authoritative PASS. No PKI, Mosquitto, HAProxy, or Node-RED runtime mutation occurred. The next bounded mutation is issuance of exactly one `clientAuth` certificate for CN `node-red-ingest`, retained root-only on `ulc-03` until the Node-RED runtime UID/image boundary is pinned.
### Node-RED MQTT client identity issuance - 2026-08-27

Phase 12A issued the dedicated Node-RED MQTT client identity successfully on `ulc-03`. The protected issuance directory is `/root/lorawan-pg-ca/node-red-ingest-issuance-20260827T142128Z`. The certificate subject is `CN = node-red-ingest`, issuer `CN = LoRaWAN PostgreSQL Internal CA`, serial `324BC014C2EE8779FEF1EC06643C2572`, validity `2026-08-27 14:21:30Z` through `2027-09-28 14:21:30Z`, SHA-256 certificate hash `eb5cc28f5eb89c1586d8aae387b52edfa09e1918e6aa74fae2571d81f4e7e576`, and SHA-256 fingerprint `1D:19:46:EB:F3:BC:74:46:F4:D7:A5:05:FE:D4:14:17:0F:16:1A:45:9C:FC:E4:17:91:28:23:9B:D8:3A:55:4F`. The RSA-3072 key and certificate public-key hashes matched exactly at `51e1578332155e45fb692a4b8e834b2c0545b22a0108b7812dd8228fcd9920d9`. `openssl verify -purpose sslclient` passed, while `-purpose sslserver` failed with `unsuitable certificate purpose`, proving the identity is clientAuth-only. All issuance artifacts remain `0600 root:root`; no client key/certificate was installed into the Node-RED runtime or copied to either broker. The CA serial-file SHA-256 stayed byte-identical at `50df8c462ef9465ab9198284fa1234f0cbfa4f33eb9779ce6d50dd23a618463d`. Mosquitto and HAProxy were unchanged. `PHASE12A_NODE_RED_CLIENT_CERT_ISSUANCE=PASS`. Next boundary: prepare a dedicated `ulc-01:8886` Node-RED mTLS listener off-path before any live Mosquitto restart.

### Server-only documentation and continuation audit - 2026-08-29

A repository-wide scan covered all 163 Markdown files under `lorawan-network-server-gateway`. The audit reconciled the top-level continuation maps with the later execution evidence instead of treating old phase headers as current state. Server evidence now records the commissioned core HA stack, Phase 13A fast-path backup/off-host transport, OpenBao 3-node normal path, `telemetry.fabric_outbox`, and Node-RED A/B runtime with A healthy/active and B fenced/stopped. Physical Gateway Phases 11/12 and the real EMU-01 Node-RED/Timescale acceptance remain intentionally deferred while hardware is unavailable. Provider-owned Reserved IPv4/firewall/public DNS/public PKI also remain external inputs.

The next executable server-only deployment boundary is Grafana on `ulc-03`. Grafana image pinning, runtime identity/data-directory setup, loopback-only startup, strict-TLS `telemetry_reader` data-source validation, and dashboard provisioning may proceed against the commissioned but currently empty telemetry schema. A real latest-reading/freshness proof remains a later hardware-dependent acceptance gate. The audit also confirmed that the repository contains no reviewed non-Markdown Fabric adapter runtime and no reviewed gateway-integrity journal/ingest/collector/verifier runtime; those remain implementation blockers and must not be represented as deployed services.

### Phase 14A Grafana server-only preflight + immutable image pin - 2026-08-29

**PASS / NO SERVICE START.** On `ulc-03`, TCP/3000 was free. Host memory was about 1.9 GiB total with about 1.2 GiB available, no swap, and about 34 GiB free on the root filesystem. The current container snapshot showed approximately Node-RED A `64.6 MiB`, OpenBao `31.13 MiB`, Spilo `164.6 MiB`, and etcd `19.06 MiB`. Node-RED A remained healthy with restart count `0`.

The protected PgBouncer CA source `/etc/lorawan-pki/pgbouncer/ca.crt` remained `root:postgres` mode `0640`, size `1891`, with SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`. Repository inspection found no approved plaintext `telemetry_reader` custody location; PgBouncer has a SCRAM-SHA-256 verifier only. Do not attempt to reverse the verifier. Grafana data-source commissioning therefore requires either approved external recovery of the existing plaintext or a controlled `telemetry_reader` PostgreSQL + three-node PgBouncer rotation before the password is staged in protected Grafana host configuration.

Grafana candidate `grafana/grafana:13.2.0` pulled successfully and resolved to immutable image `grafana/grafana@sha256:3fd54ae1214669f8355f065ec9f6445d5279a3d77095ab048ca045685272429b`. Runtime inspection returned Grafana `13.2.0`, commit `f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b`, numeric runtime identity UID/GID `472:0`, groups `0`, and image `/var/lib/grafana` owner `472:0` mode `0777`. No Grafana container or listener was started. `GRAFANA_SERVER_PREFLIGHT=PASS`, `GRAFANA_SERVER_PREFLIGHT_EXIT=0`, and `ULC03_LOGIN_SHELL_SURVIVED=YES` are authoritative.

Next boundary: resolve the `telemetry_reader` plaintext custody/rotation decision, then create the Grafana data directory/CA-only trust copy/protected environment/Compose configuration from the immutable pin; validate before starting Grafana loopback-only on `127.0.0.1:3000`. The server-only staging may prove strict-TLS read-only schema access while telemetry is empty. Full Phase 14A still waits for a real EMU-01 payload-v2 row and dashboard freshness/latest-reading acceptance.

### New-chat server continuation checkpoint - 2026-08-29

Repository-wide Markdown review was repeated after the Grafana preflight. Current-state headers were reconciled without rewriting historical checkpoint narratives. The authoritative new-chat handoff is now `deployment/server/cloud-production/00-current-server-continuation-checkpoint.md`; read it before resuming setup. It records the commissioned core HA stack, Phase 13A fast backup, OpenBao normal path, Fabric outbox, Node-RED A active/B fenced state, Grafana immutable pin/preflight, true external/hardware/implementation blockers, do-not-repeat gates, and the immediate Grafana credential/staging boundary. No runtime service was changed by this documentation update.

### Phase 14A telemetry_reader controlled rotation COMPLETE / PASS - 2026-08-29

The Grafana database-reader plaintext-custody blocker was closed by a deliberate one-time rotation. A protected 64-hex replacement was generated on `ulc-03` without printing it, the current Patroni leader was rediscovered as `10.104.0.2`, and the existing Spilo superuser path reached that leader over verify-full TLS. `ALTER ROLE telemetry_reader PASSWORD ...` succeeded, followed by a direct verify-full login returning `telemetry_reader|lorawan_telemetry|f`.

PgBouncer verifier refresh then advanced one node at a time from each node's authoritative replicated PostgreSQL SCRAM state. `ulc-03` preserved `/etc/pgbouncer/userlist.txt.before-telemetry-reader-20260829T010150Z` and reloaded in place with PID `789143`; `ulc-02` preserved `/etc/pgbouncer/userlist.txt.before-telemetry-reader-20260829T010816Z` with PID `787012`; `ulc-01` preserved `/etc/pgbouncer/userlist.txt.before-telemetry-reader-20260829T010820Z` with PID `1105819`. In each case the four-role candidate structure passed and unrelated verifiers remained unchanged.

The first `ulc-03` disposable-client verification failed only because the protected CA bind mount was unreadable under the container's default numeric identity; no authentication was attempted. Re-running the exact current Spilo client as numeric `0:0` proved the mounted CA byte-identical to SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`, after which strict verify-full authentication passed. The same rotated credential then passed through `ulc-02` and `ulc-01`. A final three-endpoint gate returned `telemetry_reader|lorawan_telemetry|f` through all `10.104.0.2/.4/.8:6432` endpoints, and Patroni still reported exactly one leader on `.2`. Only then was the pending password promoted to `/root/grafana-bootstrap/telemetry-reader-password` (`0600 root:root`, 65 bytes). `THREE_NODE_PGBOUNCER_READER_AUTH=PASS`, `FINAL_PATRONI_SINGLE_LEADER=PASS`, and `GRAFANA_TELEMETRY_READER_SECRET_PROMOTION=PASS` are authoritative.

### Phase 14A Grafana no-start filesystem/config staging PASS - 2026-08-29

On `ulc-03`, the protected Grafana host layer was staged without creating a Grafana container or listener. `/etc/lorawan-cloud/grafana` is `0750 root:root`; `/srv/grafana/data` is `0700` numeric `472:0`; `/etc/lorawan-pki/grafana-pgbouncer/ca.crt` is a `0640 root:root` public-CA copy whose SHA-256 is the commissioned `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`. A mode-`0600 root:root` `grafana.env` was created containing the immutable image reference plus generated admin and rotated reader credentials without exposing values. The mode-`0640 root:root` Compose definition validates, binds only `127.0.0.1:3000:3000`, mounts the dedicated CA at `/run/pgbouncer/ca.crt`, and maps the PgBouncer logical TLS name to local `10.104.0.8`.

A disposable exact-image process running as Grafana's numeric `472:0` successfully wrote and removed a probe file in `/var/lib/grafana` and read the mounted CA with the expected hash. Final checks still reported `GRAFANA_CONTAINER_PRESENT=NO` and `TCP_3000=FREE`. `GRAFANA_HOST_DIRECTORIES=PASS`, `GRAFANA_PGBOUNCER_CA_COPY=PASS`, `GRAFANA_PROTECTED_ENV=PASS`, `GRAFANA_COMPOSE_VALIDATION=PASS`, `GRAFANA_RUNTIME_FILESYSTEM_ACCESS=PASS`, and `GRAFANA_RUNTIME_CA_ACCESS=PASS` are authoritative.

Before first start, account for Grafana's preinstalled-plugin update behavior without assuming more than the current evidence supports. Current documentation still treats PostgreSQL as bundled/no-install in standard deployments, while the 13.2 source preinstall registry includes `grafana-postgresql-datasource` and generic `preinstall_auto_update` defaults to enabled. Preserve the immutable POC boundary by setting `GF_PLUGINS_PREINSTALL_AUTO_UPDATE=false` in the Grafana runtime environment and record the observed PostgreSQL plugin identity/version after startup. Provisioning continues to use `type: postgres`.

### Phase 14A Grafana server-only staging COMPLETE / PASS - 2026-08-29

The first controlled Grafana activation on `ulc-03` passed every server-only gate. `/api/health` became ready after 23 seconds and reported Grafana `13.2.0`, commit `f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b`. Container state was `running|0|false`, the enforced memory limit was `536870912` bytes, and the only Grafana listener was `127.0.0.1:3000`. `GF_PLUGINS_PREINSTALL_AUTO_UPDATE=false` was present in the running container.

Runtime trust-path checks proved `pgbouncer.internal.lorawan.com -> 10.104.0.8` inside Grafana and CA SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`. The provisioned PostgreSQL datasource resolved to runtime type `grafana-postgresql-datasource`, returned health `OK`, and authenticated over strict verify-full TLS as `telemetry_reader` to `lorawan_telemetry`. A Grafana-executed database query returned `telemetry_reader|lorawan_telemetry|false`, proved SELECT on `telemetry.uplinks` and `telemetry.measurements`, denied INSERT on both, and correctly observed zero rows in both empty telemetry hypertables. The observed PostgreSQL plugin version is `13.0.1`.

The file-provisioned `LoRaWAN Telemetry Overview` dashboard loaded after 11 seconds with four panels. Node-RED A remained `running|0|healthy`, and Patroni stayed one leader on `10.104.0.2` with replicas on `.4` and `.8`. Healthy-state resource snapshot showed Grafana about `286.8 MiB / 512 MiB` and Node-RED about `75.77 MiB / 1.922 GiB`. `GRAFANA_SERVER_STAGING=PASS` is authoritative. `PHASE14A_FULL_PASS=NOT_YET_CLAIMED` remains correct because the physical gateway is unavailable and no real EMU-01 payload-v2 row/freshness correlation has yet been proven.

### Phase 13S-1 three-host preflight stdin-harness stop - 2026-08-29

The first server-only snapshot/tool preflight passed the `ulc-03` control/free-space gate and proved noninteractive SSH plus `sudo -n` access to `ulc-01` and `ulc-02`, then returned to the prompt before Step 3. No host/service/database mutation occurred. Root cause is the wrapper transport, not server state: `sudo bash` was reading the wrapper from a heredoc and the Step 2 SSH clients inherited that same stdin, allowing SSH to consume the unread remainder of the wrapper. Preserve the two PASS gates and resume at probe construction. For heredoc-driven wrappers, use `ssh -n`/`</dev/null` for commands that require no stdin, and redirect SSH from an explicit payload file only when stdin transport is intentional.

### Phase 13S-1 resumed three-host inventory partial PASS - 2026-08-29

The resume-only probe reached all three hosts successfully. All hosts reported Ubuntu 24.04.4 LTS, zero failed units, expected commissioned system services/containers, zero container restart counts/OOM flags, `etcdctl 3.4.30`, PostgreSQL 18.6 backup tools, and OpenBao CLI 2.6.2. `ulc-03` showed Grafana running from the pinned 13.2.0 digest and Node-RED A healthy; `ulc-01/02` showed ChirpStack, Spilo, etcd, and OpenBao running as expected. Patroni still returned one leader on `10.104.0.2` and replicas on `.4`/`.8`.

The per-host probe stopped at the listener section because the multi-line `awk` condition was rejected with `unexpected newline or end of string`. The outer wrapper nevertheless continued and printed `PHASE13S_SERVER_INVENTORY_PREFLIGHT=PASS`; that banner was not authoritative until the missing tail was rerun. No service/database mutation occurred.

### Phase 13S-1 three-host inventory preflight COMPLETE / PASS - 2026-08-29

The corrected tail passed on all three hosts. Required etcd/PostgreSQL/PgBouncer/Patroni/OpenBao/HAProxy listeners were present everywhere they belong; `ulc-01/02` also retained MQTT and ChirpStack listeners, while `ulc-03` retained Node-RED `127.0.0.1:1880`, Grafana `127.0.0.1:3000`, and `10.104.0.8:18884`. Non-secret config metadata/hashes were captured, with protected PgBouncer and Node-RED/Grafana environment files represented by metadata only. Combined with the earlier inventory and Patroni check, `PHASE13S_SERVER_INVENTORY_PREFLIGHT=PASS` is authoritative and no service/database state changed. Next: protected fresh PostgreSQL logical dumps plus etcd snapshot/member evidence.

### Phase 13S-2 PostgreSQL + etcd snapshot COMPLETE / PASS - 2026-08-29

Fresh server-only backups were created under `/home/opsadmin/backups/phase13s-20260829T022146Z` without restarting or reconfiguring any service. `chirpstack.dump` is `101218` bytes and `lorawan_telemetry.dump` is `72384` bytes; both passed custom-format catalog validation. The initial etcd health-count wrapper stopped because etcdctl wrote successful health text to stderr, leaving its stdout-only evidence file empty; all three endpoints had actually printed healthy results. The corrected resume reused the exact database dumps and captured each endpoint with `2>&1`.

All three etcd endpoints then passed health checks. `etcdctl 3.4.30` recorded a three-member etcd `3.5.15` cluster with `etcd-02` (`10.104.0.4`) current leader, no learners, common Raft term `2`, and applied index `1387`. A v3 snapshot from `10.104.0.8:2379` was saved as `etcd.snapshot`, `491552` bytes; snapshot status reported hash `c0b2b3a5`, revision `1326`, `1336` keys, and about `492 kB`. The final nine-file snapshot set is mode `0600 opsadmin:opsadmin` under a mode-`0700 opsadmin:opsadmin` directory, and the complete SHA-256 manifest passed before and after permission normalization. Patroni remained one leader on `.2` and replicas on `.4`/`.8`. `PHASE13S_POSTGRES_ETCD_SNAPSHOT=PASS` is authoritative. Next: add secret-free reconstruction manifests plus Node-RED/Grafana exports; OpenBao Raft snapshot remains a separate privileged sub-boundary.

### Phase 13S-2 fresh PostgreSQL backup PASS / etcd capture harness stop - 2026-08-29

`ulc-03` created `/home/opsadmin/backups/phase13s-20260829T022146Z` after proving local Patroni replica state `true|true`, etcdctl `3.4.30`, and sufficient free space. Fresh custom-format backups were created without rotating or printing any database credential: `chirpstack.dump` is 101218 bytes and `lorawan_telemetry.dump` is 72384 bytes; both passed `pg_restore --list`. `SOURCE_METADATA=PASS`. The recurring locale warning and the known TimescaleDB `continuous_agg` circular-FK warning were non-blocking.

The run stopped before the etcd snapshot because the health parser redirected only stdout. All three `etcdctl endpoint health` operations visibly succeeded with committed proposals, but etcdctl emitted those health messages on stderr, so `etcd-endpoint-health.txt` contained no `is healthy` lines and the count gate returned `0`. Treat this as a harness defect, not an etcd failure. Preserve and reuse the exact fresh dumps; continue only from etcd health/member/status capture through snapshot, hash verification, permissions, and final Patroni regression.

### Phase 13S-3 secret-free reconstruction export COMPLETE / PASS - 2026-08-29

The existing Phase 13S-2 PostgreSQL/etcd snapshot set was first revalidated unchanged. A protected reconstruction tree was then created under `/home/opsadmin/backups/phase13s-20260829T022146Z/reconstruction`. Secret-safe host manifests passed for `ulc-01`, `ulc-02`, and `ulc-03`. Node-RED B was proved fenced and free of `flows_cred.json`; the five reviewed shared runtime files were exported from the stopped standby and matched their authoritative hashes. Grafana Compose plus file-provisioned datasource/dashboard definitions passed secret-leak gates and were exported without `grafana.env`. A deferred/separate-items record explicitly preserves the provider, physical-gateway, Fabric, and gateway-integrity blockers instead of fabricating missing artifacts.

The reconstruction SHA-256 manifest passed for all 15 payload files plus the manifest itself; the original Phase 13S-2 `SHA256SUMS` also still passed. Node-RED A remained `running|0|healthy`, Grafana remained `running|0|false`, and Node-RED B remained fenced. `PHASE13S_RECONSTRUCTION_EXPORT=PASS` is authoritative. The next independent server-only backup boundary is OpenBao Raft snapshotting. Cloud production has not yet created the lab manual's dedicated snapshot-only backup identity, so first create and verify a least-privilege backup policy/AppRole; never use the `fabric-adapter` AppRole for snapshot or restore privileges, and do not retain a reusable backup SecretID in the general archive.

### Phase 13S-4A OpenBao snapshot-only backup identity COMPLETE / PASS - 2026-08-29

All three OpenBao members were initialized and unsealed before and after the bounded administrative change. The `lorawan-evidence` key and `fabric-adapter` role retained their commissioned restrictions, and the Fabric role still had zero SecretID accessors. The new `openbao-raft-snapshot-reader` policy contains only `sys/storage/raft/snapshot` with `read` + `sudo`. The new `openbao-backup` AppRole has only that policy, token TTL 15 minutes, max TTL 30 minutes, SecretID TTL 15 minutes, exactly one permitted SecretID use, and `bind_secret_id=true`. Its RoleID exists but was not printed; zero backup SecretIDs were issued in this step. `PHASE13S_OPENBAO_BACKUP_IDENTITY=PASS`, exit `0`, and the `ulc-03` login shell survived.

Next: mint exactly one ephemeral backup SecretID in memory, authenticate once, require second-login reuse failure, prove snapshot-only token capabilities, create one Raft snapshot, transfer it to the protected 13S directory, revoke the token, and require zero reusable backup SecretIDs afterward. The root token may issue the one-use SecretID but must not perform the snapshot itself.

### Phase 13S-4B OpenBao snapshot attempt stopped after one-use SecretID issuance - 2026-08-29

The first 13S-4B run preserved the existing PostgreSQL/etcd/reconstruction hashes, reverified the backup AppRole, proved zero backup SecretID accessors before issuance, and recorded three Raft voters with `10.104.0.2` leader. It then successfully issued one ephemeral backup SecretID but stopped before AppRole login because the accessor-count parser assumed a JSON object with `data.keys`; OpenBao 2.6.2 returned a top-level JSON list, causing Python `AttributeError: 'list' object has no attribute 'get'`. No Raft snapshot was created. The issued SecretID value was process-local and is lost, while its accessor may remain until the 15-minute TTL expires. Resume by accepting both list/wrapped list response shapes, destroying at most the one orphan accessor (the pre-issuance count was zero), re-proving zero, then minting a fresh one-use SecretID for the snapshot. Preserve the partial evidence transcript rather than treating it as final evidence.

### Phase 13S-4B OpenBao Raft snapshot COMPLETE / PASS - 2026-08-29

The resume observed exactly one orphan backup SecretID accessor from the failed run and destroyed it before issuing anything else. A fresh one-use SecretID then authenticated once; reuse was rejected and its accessor disappeared. The backup token had `read,sudo` only on `sys/storage/raft/snapshot` and was denied Transit sign, Transit verify, and Raft restore. It created a `30236`-byte OpenBao Raft snapshot on the leader (`10.104.0.2`) with SHA-256 `9965f9e904b83d62b07ebb9321af1b4a45a7f2b15fbfdf50d0c7238fac249e68`; the token was explicitly revoked afterward. Backup and Fabric AppRoles both finished with zero SecretID accessors and all three OpenBao nodes remained healthy/unsealed.

The snapshot was copied to `/home/opsadmin/backups/phase13s-20260829T022146Z/openbao.snap`; source/destination hashes matched, remote staging was deleted, and `OPENBAO-SHA256SUMS` verified the final snapshot plus both the final and preserved partial evidence transcripts. Earlier PostgreSQL/etcd and reconstruction manifests still pass. `PHASE13S_OPENBAO_RAFT_SNAPSHOT=PASS` is authoritative.

### Phase 13S-5 final local package COMPLETE / PASS - 2026-08-29

All existing Phase 13S manifests revalidated successfully before packaging. The source tree passed the required-artifact gate, the general-archive secret-filename gate, and the `0600` file / `0700` directory protection gate. A new `SERVER-ONLY-STATUS.txt` explicitly records the interim server-only scope and leaves DigitalOcean/public-ingress, physical-gateway/real-EMU-01, Fabric runtime/handoff/transaction, gateway-integrity, final Phase 13B/14/14B, and Phase 15 unclaimed. `PHASE13S-FULL-SHA256SUMS` covers 30 payload files and passed.

The complete source directory was packaged outside itself as `/home/opsadmin/backups/phase13s-20260829T022146Z.tar.gz`, size `108819` bytes. The gzip/archive-structure gate passed; extraction to a disposable directory followed by the full manifest check also passed. The source transport SHA-256 is `19f2072fdfb4ef41e34442c7cc3949decd62a0cb2cee155bcf734f24121397cc`, stored in `phase13s-20260829T022146Z.tar.gz.sha256`. `PHASE13S_LOCAL_PACKAGE=PASS` is authoritative.

**Streamlined commissioning decision - 2026-08-29:** stop repeating backup/export work once this locally verified package exists. For current non-destructive server preparation, `SERVER_ONLY_SNAPSHOT_EXPORT=PASS` is accepted from the local package evidence above. The previously planned Windows off-host copy is no longer a blocking Phase 13S step; off-host copy and isolated restore rehearsal are deferred to the destructive/failure-testing boundary before Phase 15. Do not rebuild the archive just to rewrite the embedded `SERVER-ONLY-STATUS.txt`, which retains the earlier `NOT_YET_OFFHOST_VERIFIED` wording as historical evidence. Phase 13S is complete for current server-only preparation; final Phase 13B remains unclaimed and must be refreshed after the remaining provider/hardware/Fabric/final-acceptance work.

### Phase 14S server-only healthy evidence partial PASS / Grafana discovery harness stop - 2026-08-29

Run `SERVER-PRESTAGE-20260829T133354Z` was created at `/home/opsadmin/lorawan-ha-evidence/SERVER-PRESTAGE-20260829T133354Z` as a read-only healthy-state evidence capture. Three-host evidence collection passed. etcd was healthy 3/3. Patroni returned exactly one leader on `10.104.0.2` and replicas on `.4` and `.8`. The PostgreSQL/TimescaleDB/outbox read-only structure gate passed, and Node-RED A remained `running|0|healthy` with HTTP 200 while Node-RED B stayed fenced/stopped. `THREE_HOST_EVIDENCE=PASS`, `ETCD_3_MEMBER_HEALTH=PASS`, `PATRONI_1_LEADER_2_REPLICAS=PASS`, `POSTGRES_TIMESCALE_OUTBOX=PASS`, and `NODE_RED_SINGLE_ACTIVE=PASS` are authoritative and must not be rerun only because the next step stopped.

The run stopped at the first Grafana discovery expression with `GRAFANA_CONTAINER=FAIL`. Root cause was the harness, not Grafana: Docker displayed the immutable Grafana image as digest prefix `3fd54ae12146`, so filtering the displayed image string for the word `grafana` produced no container name. A direct diagnostic found the Compose-labeled container `grafana`, state `running`, restart count `0`, `OOMKilled=false`, memory limit `536870912`, and host mapping `127.0.0.1:3000->3000/tcp`. `/api/health` returned database `ok`, Grafana `13.2.0`, commit `f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b`. `GRAFANA_RUNTIME_DISCOVERY=PASS` is authoritative.

The corrected resume preserved the earlier evidence instead of recollecting it. `PASSED_STEPS_1_TO_6_PRESERVED=PASS`, corrected `GRAFANA_HEALTH=PASS`, and `CHIRPSTACK_TWO_NODE_RUNTIME=PASS` all completed. The next OpenBao capture command stopped immediately with `Get "https://127.0.0.1:8200/v1/sys/seal-status": dial tcp 127.0.0.1:8200: connect: connection refused`. This was another harness-address defect: the commissioned OpenBao API listeners are host-private on `10.104.0.2:8200`, `10.104.0.4:8200`, and `10.104.0.8:8200`, and the established CLI pattern explicitly sets `BAO_ADDR` to the node private address plus `BAO_CACERT=/openbao/tls/ca.crt`. No OpenBao health conclusion was reached by the failed localhost command.

The final resume corrected only that address handling. `ulc-01`, `ulc-02`, and `ulc-03` each returned `initialized=true`, `sealed=false`, and `ha_enabled=true`; `OPENBAO_3_NODE_HEALTH=PASS`. The deferred/BLOCKED state record was written for physical gateway, provider ingress, missing Fabric adapter/handoff, and missing gateway-integrity runtimes. The evidence secret scan passed. The complete evidence tree was normalized to mode `0700` directories / `0600` files and hashed successfully; the final set contains 16 files under `/home/opsadmin/lorawan-ha-evidence/SERVER-PRESTAGE-20260829T133354Z`. `DEFERRED_BLOCKED_RECORD=PASS`, `EVIDENCE_SECRET_GATE=PASS`, `EVIDENCE_SHA256=PASS`, and `EVIDENCE_FILESYSTEM_PROTECTION=PASS` are authoritative.

`SERVER_ONLY_EVIDENCE_HARNESS=PASS` is complete. No restart, configuration change, backup, or failure injection occurred. This closes Phase 14S for current server-first preparation; do not rerun it unless relevant server state materially changes. Final Phase 14 remains a later fully commissioned healthy-baseline capture after final Phase 13B.

A first follow-up read of the Phase 14B hard gate incorrectly concluded that no additional independent server-side commissioning remained and labeled `SERVER_ONLY_PREPARATION=COMPLETE`. A broader Markdown/runtime audit corrected that conclusion. The outbox **schema/ACL layer** is commissioned, but the execution log itself previously recorded `Keep Node-RED outbox enqueue disabled until Phase 12A`, and the current reviewed `runtime/flows.json` still wrote only `telemetry.uplinks` + `telemetry.measurements`. Phase 12A.9, the Fabric outbox manual Step 4, and Phase 14B all require one selected event to create telemetry and `fabric_outbox` atomically. The Node-RED testing manual also explicitly provides a pre-arrival synthetic Inject-node path that does not require RF/gateway hardware.

Correction: Phase 13S and 14S remain PASS and must not be repeated, but `SERVER_ONLY_PREPARATION=COMPLETE` is withdrawn. The next productive server-only boundary is to update the reviewed A/B Node-RED runtime with the documented `queued_fabric` CTE and `$25` selection boolean, using protected `FABRIC_SELECTED_DEV_EUI` policy with reserved `0000000000000000` for the synthetic fixture; stage the same revision on active A and stopped B; run one synthetic event plus replay; prove exactly one canonical uplink, reviewed measurement rows, one pending outbox row, and no duplicate increase; then use that temporary row to exercise Grafana before targeted cleanup. Real RF/LoRaWAN acceptance remains hardware-deferred.

The repository candidate was then prepared and statically validated before any live rollout. All three Function nodes in `runtime/flows.json` pass `node --check`; the normalization function contains the required `queued_fabric` CTE, `$25::boolean`, `telemetry-attestation-v1`, and environment-driven `FABRIC_SELECTED_DEV_EUI` selector; the Compose/env template remains secret-free. The commissioned outbox DDL confirms omitted operational fields default safely (`status='pending'`, `attempts=0`, `next_attempt_at=now()`), and the already-proven ACL gives `telemetry_writer` INSERT/SELECT plus identity-sequence use. Candidate canonical LF hashes are `compose.yml=17aade702bf2206e9a4f2177fa8b0f47a7012da431a2adc7d4b064ce0b897730` and `flows.json=476056c5cff951ff46bb48c2eeb0e153b666c8cdc42eab88532fd3bebbcdc753`. These are pre-deployment hashes only; live A/B remain on the prior revision until the standby-first rollout.

### Deep server-security / Fabric / gateway-integrity audit - 2026-08-29

A second repository-wide audit focused on KMS auditing, certificate lifecycle, container hardening, Fabric byte-level logic, future workload identities, image-security coverage, and gateway-integrity trust separation. It found additional hardware-independent server work after the Node-RED outbox proof.

The original host SSH/pwquality/unattended-upgrades/Fail2ban/AppArmor/time/persistent-log baseline remains accepted. UFW remains intentionally inactive because the operator lacks an independent provider-console/recovery path. etcd private HTTP remains an explicit POC exception; converting the live Patroni DCS to TLS is possible but is a high-risk cluster-wide migration and is not part of the fast server-completion track.

Service-security gaps: hardening requires certificate-expiry monitoring but no checker/timer is recorded; Fabric incident response relies on OpenBao KMS audit evidence but no commissioned OpenBao audit device is recorded; only Spilo has a detailed vulnerability/hardening scan; and effective Docker log/resource/security settings are not documented consistently for every live service. These should be inspected/closed without pretending provider firewall or production centralized monitoring exists.

Fabric logic was rechecked. The frozen `telemetry-attestation-v1` canonical UTF-8 fixture exists and its expected SHA-256 is `c2952e8cddc7f39a17522cb49dd3292c9af75c00fdc37172f74bb3dc955f3a5c`; exact-byte hashing can be proven now. The actual RFC 8785 canonicalizer remains part of the missing reviewed adapter implementation and must generate the same bytes in its own startup test. The repository contains no adapter source/Dockerfile/package/runtime image, so live worker deployment remains a real implementation blocker. The OpenBao `fabric-adapter` AppRole still has zero SecretID accessors; preserve that state until a reviewed runtime and credential-delivery design exist, and prefer separate worker identities where practical.

Gateway-integrity was also checked file-by-file. The repository contains only Markdown contracts for the evidence ingest, MQTT collector, verifier, and trusted-decoder services; reviewed executables/images are absent. Although table shapes are documented, deployable service-role ACLs and protected evidence-store implementation are not frozen. Do not create placeholders or mark v2 commissioned.

Authoritative server-first queue is now **evidence-runtime first**: implement and package the missing gateway/security evidence services, migration, trusted decoder, storage interface, PKI/ingress artifacts, and read-only observability; then commission their minimum normal path. OpenBao audit-state closure follows **before any Fabric signing SecretID or Fabric Adapter worker is released**, not before the verifier stack. Certificate-expiry monitoring, Fabric-v1 exact-byte/digest preflight, bounded container-security inventory, and image-security coverage remain later hardware-independent cleanup. Keep all Fabric signing SecretIDs unissued. None substitutes for the missing external Fabric handoff or physical gateway acceptance.

### Node-RED atomic-outbox live pre-mutation gate PASS - 2026-08-29

The first live gate for the atomic telemetry + Fabric outbox revision was read-only and changed no service or file. Node-RED A on `ulc-03` was `running|0|healthy`; Node-RED B on `ulc-02` remained fenced/stopped. Both live candidates still matched the prior flow SHA-256 `02be61d7fafdaa8877b9b6f5cf5ef32f7685730e300d4af55b49aadd76518718` and the same live Compose SHA-256 `5607fddf6a31eea71376d720c2f2f24903818635800a967fa276ca1f21f00934`. Neither live flow contained `telemetry.fabric_outbox`, and neither protected environment contained `FABRIC_SELECTED_DEV_EUI`.

The reserved synthetic DevEUI `0000000000000000` was clean with `0|0|0` rows across `telemetry.uplinks`, `telemetry.measurements`, and joined outbox state. `telemetry.fabric_outbox` exists; `telemetry_writer` has INSERT + SELECT and identity-sequence USAGE; operational defaults remain `attempts=0`, `next_attempt_at=now()`, and `status='pending'`. The recurring locale warning was non-blocking. `NODE_RED_ATOMIC_OUTBOX_PREMUTATION=PASS` is authoritative. No restart or configuration change occurred. Next: transfer and install only the reviewed candidate `compose.yml` + `flows.json` plus protected `FABRIC_SELECTED_DEV_EUI=0000000000000000` on stopped B, validate hashes/Compose/Function syntax, and keep B fenced.

### Node-RED B atomic-outbox candidate staging COMPLETE / PASS - 2026-08-29

The standby-first atomic-outbox rollout completed on `ulc-02` without ever starting Node-RED B. Before mutation, A remained `running|0|healthy`, B was fenced, and B still matched the old flow `02be61d7fafdaa8877b9b6f5cf5ef32f7685730e300d4af55b49aadd76518718` plus old Compose `5607fddf6a31eea71376d720c2f2f24903818635800a967fa276ca1f21f00934`. The reviewed secret-free candidate was reconstructed on `ulc-03`, locally verified as Compose `17aade702bf2206e9a4f2177fa8b0f47a7012da431a2adc7d4b064ce0b897730` and flow `476056c5cff951ff46bb48c2eeb0e153b666c8cdc42eab88532fd3bebbcdc753`, transferred to a protected temporary directory on B, and re-hashed before install.

A temporary rollback copy of B's existing Compose, flow, and protected environment was created only for the mutation window. The candidate then installed with the previous ownership/modes preserved (`compose 0644 root:root`, `flows.json 0644 1000:1000`, env `0600 root:root`). `FABRIC_SELECTED_DEV_EUI=0000000000000000` was staged exactly once. Deployed hashes matched the reviewed candidate; JSON/atomic-outbox structural checks and `docker compose --env-file node-red.env config --quiet` passed; no `flows_cred.json` appeared; and the final fence check still showed no running Node-RED container on B. The rollback copy and remote staging directory were removed after PASS. A remained healthy throughout. No database row was created and no synthetic event was injected. `NODE_RED_B_ATOMIC_OUTBOX_STAGING=PASS` and `NODE_RED_B_ATOMIC_OUTBOX_STAGING_FINAL=PASS` are authoritative. Next: update/recreate A once using these exact already-verified B bytes as the transfer source, then re-prove A healthy and B fenced before synthetic testing.

### Node-RED A atomic-outbox rollout COMPLETE / PASS - 2026-08-29

The A-side rollout used the already verified stopped-B files as source and rechecked the candidate hashes on `ulc-03` before mutation. A was still healthy on the old revision and B was fenced. A's old Compose/flow/env were held only as a temporary rollback state. The candidate Compose and flow plus protected `FABRIC_SELECTED_DEV_EUI=0000000000000000` were installed, `docker compose ... config --quiet` passed, B was re-proven fenced, and A was recreated once. A reached `running|0|healthy` on probe 15 with restart count `0`; `127.0.0.1:1880` remained the only editor listener; MQTT/PgBouncer logical names both resolved to `10.104.0.8`; local routes `:18884` and `:6432` passed; the running container contained the selector; recent logs showed no known CA permission/certificate regression; and final A/B Compose/flow/selector parity passed while B remained stopped.

The one missing validation was then resumed read-only without another restart, recreate, or file mutation. The active runtime is UID/GID `1000:1000` and can read `/run/mqtt/ca.crt`, `/run/mqtt/client.crt`, `/run/mqtt/client.key`, `/run/pgbouncer/ca.crt`, `/data/flows.json`, `/data/settings.js`, `/data/package.json`, and `/data/package-lock.json`. The runtime PgBouncer and MQTT CA files both matched SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`. The all-zero Fabric selector remained present exactly once, B remained fenced, and B still matched candidate Compose `17aade702bf2206e9a4f2177fa8b0f47a7012da431a2adc7d4b064ce0b897730` plus flow `476056c5cff951ff46bb48c2eeb0e153b666c8cdc42eab88532fd3bebbcdc753`. Final A state remained `running|0|healthy`. `NODE_RED_RUNTIME_FILE_ACCESS=PASS`, `NODE_RED_RUNTIME_CA_ACCESS=PASS`, `NODE_RED_A_ATOMIC_OUTBOX_ROLLOUT=PASS`, and `NODE_RED_A_B_ATOMIC_OUTBOX_RUNTIME=PASS` are authoritative. Do not recreate A or repeat deployment staging.

### Node-RED synthetic atomic-outbox + replay proof COMPLETE / PASS - 2026-08-29

The reserved synthetic event `server-synthetic-NODERED-OUTBOX-SYNTH-20260829T152713Z` at `2026-08-29T15:27:13.000Z` was executed without changing the flow, restarting Node-RED, or publishing synthetic MQTT traffic. The harness loaded the exact deployed `Validate + normalize + parameterize` Function body from active A's `/data/flows.json`, used the running container's real environment and installed `pg` driver, and executed the generated parameterized SQL through the commissioned strict-TLS PgBouncer path as `telemetry_writer`. The deployed function produced exactly 25 SQL parameters, thirteen normalized metrics, and selected only the reserved DevEUI `0000000000000000` for Fabric outbox enqueue.

The first execution returned final measurement-insert rowcount `13`; local replica visibility immediately showed exactly `1|13|1` for the named uplink, measurements, and matching Fabric outbox row. The canonical uplink fields matched the fixture, all thirteen measurement rows were distinct and `quality='measured'`, and the outbox row remained `status='pending'`, `attempts=0`, unclaimed, unsealed, and `schema_version='telemetry-attestation-v1'`. Replaying the exact same stable event returned database rowcount `0`; counts stayed `1|13|1`, proving the atomic application path is retry-safe and does not duplicate telemetry or outbox work. A remained `running|0|healthy`; B remained fenced. A secret-free evidence summary and SHA-256 manifest were written under `/home/opsadmin/lorawan-ha-evidence/NODERED-OUTBOX-SYNTH-20260829T152713Z`. `NODE_RED_SYNTHETIC_ATOMIC_OUTBOX=PASS` is authoritative.

Leave this one synthetic row set temporarily in place only for the next Grafana read-path proof. That proof may use Grafana's own provisioned `telemetry_reader` datasource to read the named event and reading age, then delete only this exact synthetic outbox/measurement/uplink set and prove the reserved synthetic identity returns to zero. This remains server-side application commissioning, not RF/LoRaWAN acceptance.

### Grafana synthetic read-path attempt and targeted-cleanup attribution - 2026-08-30

The first Grafana-own-datasource proof revalidated the preserved synthetic evidence summary, found Grafana `running|0|false|536870912`, confirmed only `127.0.0.1:3000`, loaded the protected admin environment without printing credentials, and resolved the provisioned datasource/dashboard exactly as expected: Grafana `13.2.0` commit `f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b`, datasource UID `lorawan-telemetry`, runtime type `grafana-postgresql-datasource`, user `telemetry_reader`, database `lorawan_telemetry`, `pgbouncer.internal.lorawan.com:6432`, `sslmode=verify-full`, dashboard UID `lorawan-overview`, title `LoRaWAN Telemetry Overview`, and the expected four panel titles. The captured console then stopped at the hand-built `/api/ds/query` verifier with `RuntimeError: Expected one base uplink row, got 0`.

A later read-only investigation supersedes the earlier assumption that cleanup had not executed. The next resume found the reserved event already absent. Three-node forensics showed all members on timeline `3`, both replicas streaming at lag `0`, identical exact/reserved counts `0|0|0`, Patroni history only from 2026-08-23/24 (before the synthetic event), and zero Timescale jobs for schema `telemetry`; this rules out replica divergence, a later promotion losing the transaction, and telemetry retention. PostgreSQL statistics on the current primary recorded exactly the matching row lifecycle: `uplinks n_tup_ins=1,n_tup_del=1`, measurement chunk totals `13 inserts,13 deletes`, and `fabric_outbox n_tup_del=1`. `telemetry_writer`, `telemetry_reader`, and `fabric_adapter` have no DELETE privilege; only privileged administrative roles do.

Attribution is strong to the targeted cleanup path from the combined Grafana/cleanup wrapper: `ulc-03` shell history contains the exact `cleanup.sql` body with DELETEs in outbox -> measurements -> uplinks order, and the `ulc-01` sudo journal records `opsadmin` executing `docker exec -i spilo psql -XAtq -v ON_ERROR_STOP=1 -U postgres -d lorawan_telemetry` at `2026-08-29 15:35:09 UTC`, matching that wrapper's primary-side cleanup invocation. The current evidence does not prove why this execution occurred despite the captured verifier traceback, so do not invent shell-control-flow causality; record only that the cleanup transaction was in fact executed and the cluster-wide zero state is explained. `SYNTHETIC_ROWSET_CLEANUP_ATTRIBUTED=PASS`. The original `NODE_RED_SYNTHETIC_ATOMIC_OUTBOX=PASS` remains valid historical evidence because it was recorded before deletion.

### Fresh Grafana synthetic fixture + read-path proof COMPLETE / PASS - 2026-08-30

A new uniquely named fixture `grafana-synthetic-GRAFANA-SYNTH-20260830T000012Z` at `2026-08-30T00:00:12.000Z` was created through the exact deployed Node-RED normalization Function without MQTT publication, flow change, service restart, or configuration change. The reserved all-zero DevEUI baseline was clean before insertion. The application SQL returned rowcount `13`, and replica visibility immediately proved exactly `1|13|1` for uplink, measurements, and pending Fabric outbox.

Grafana remained `running|0|false|536870912`. The actual provisioned dashboard query targets all returned data (`P1=1`, `P2=1`, `P3=6`, `P4=1`). A code-mode datasource probe executed through Grafana as `telemetry_reader` against `lorawan_telemetry` returned exactly one event, thirteen measurements, one pending outbox row, matching `test_sequence=1788048012`, reading age `5` seconds, thirteen rows in `telemetry.latest_measurements`, and one row in `telemetry.latest_uplinks`. Final database counts remained `1|13|1`; Grafana and Node-RED remained healthy. Secret-free evidence plus SHA-256 verification is under `/home/opsadmin/lorawan-ha-evidence/GRAFANA-SYNTH-20260830T000012Z`. `GRAFANA_SYNTHETIC_FIXTURE_AND_READ_PATH=PASS` is authoritative for the server-only Grafana data path.

The separate cleanup-only boundary then revalidated the preserved Grafana evidence, proved the exact fixture still existed as `1|13|1`, confirmed the outbox row was still `pending`, attempts `0`, unclaimed and unsealed, discovered exactly one Patroni primary at `10.104.0.2`, and deleted only that exact event in one transaction using outbox -> measurements -> uplink order. The local replica immediately showed `0|0|0`; the reserved all-zero synthetic identity also returned to `0|0|0`; explicit checks on all three PostgreSQL members returned `0|0|0`. Grafana remained `running|0|false|536870912`, Node-RED A remained `running|0|healthy`, and B remained fenced. Cleanup evidence was added under the same evidence directory without altering the prior read-path manifest. `GRAFANA_SYNTHETIC_CLEANUP_COMPLETE=PASS` is authoritative. Full Phase 14A remains hardware-deferred because this was not a real EMU-01 event.

### Deep gateway-evidence service/readiness audit - 2026-08-29

A further repository-wide trace separated two different meanings of evidence. Phase 14/14S is the operational test-evidence harness (`before/during/after` command output, UTC run IDs, hashes, bounded logs). Gateway-integrity v2 is a separate security service chain: gateway journal/uploader -> HTTPS/mTLS evidence ingest -> protected raw-object storage plus a read-only remote-MQTT witness -> independent verifier/trusted decoder -> `gateway_evidence.*` -> v2 Fabric eligibility. The already-passed Phase 14S harness does not commission the gateway-evidence services.

The contracts are detailed: `gateway_evidence.checkpoints`, `segments`, `mqtt_gateway_events`, and `event_verification`; states `pending`, `verified`, `evidence_gap`, `integrity_failure`, `not_required`; per-gateway evidence-upload PKI; read-only collector ACL; no-overwrite raw-object storage; verifier separation from OpenBao/Fabric; and Grafana evidence-state/checkpoint monitoring. What was missing was one deployment-readiness guide connecting all of those dependencies and the proof required after each step.

`integrations/gateway-integrity/05-preimplementation-readiness-and-deployment-gate.md` now records that package. It freezes the required future implementation artifacts, object-store behavior, migration/grants boundary, collector identity, trusted-decoder/v2-vector requirements, observability, and per-step commissioning evidence. It also identifies two unresolved cloud design gates. First, exact evidence-role placement is not frozen; one role per Droplet (`ingest ulc-01`, `collector ulc-02`, `verifier/decoder ulc-03`) is only an initial measurement candidate until reviewed images and 2-GiB resource evidence exist. Second, Phase 10 already terminates `chirpstack.<DOMAIN>` TLS on each anchor IP `:443`, while v2 also reserves `evidence.<DOMAIN>:443` with per-gateway mTLS. Evidence deployment therefore needs one reviewed shared-443 SNI/multi-certificate/client-certificate strategy (or another approved ingress architecture); a second independent bind on the same anchor `:443` is invalid.

Current evidence result remains `EVIDENCE_CONTRACTS=PASS`, `EVIDENCE_PREIMPLEMENTATION_GATE=ACTIVE`, `GATEWAY_EVIDENCE_RUNTIME=BLOCKED`, and `GATEWAY_EVIDENCE_V2_NORMAL_PATH=NOT_YET_CLAIMED`. The blocker is now explicitly **source/artifact implementation**, not another security-audit preflight. Build the evidence services first. Do not open a placeholder evidence port, create live service credentials/schema solely for appearance, or claim v2 because the operational evidence harness is working.

### Evidence-first implementation priority + streamlined commissioning - 2026-08-30

A full Markdown re-scan reconciled the dependency order. `gateway-evidence-ingest`, `gateway-mqtt-evidence-collector`, `gateway-evidence-verifier`, the trusted decoder, raw-evidence storage interface, `gateway_evidence` migration, evidence PKI/shared-443 artifacts, and read-only evidence observability do **not** require OpenBao signing credentials. The verifier is intentionally forbidden from signing or submitting to Fabric. Therefore these services should be implemented and minimally commissioned before spending another boundary on OpenBao audit-device closure. OpenBao audit evidence remains mandatory before a Fabric signing workload credential is released.

The live commissioning style is also reduced to the minimum useful proof: build/config validation; health/readiness on both replicas; one idempotent ingest retry; one duplicated MQTT observation converging to one `capture_key_sha256`; one verifier work item reaching the expected state with identical trusted-decoder digest on both replicas; and one read-only observability query. Outage/failover, torn-tail, lease-expiry, one-storage-member-loss, tamper/reorder/delete/conflict matrices, and other destructive/security stress cases remain documented for later Guide 3 / Phase 15 validation and are **not** required to get the evidence services installed and working.

### Replicated evidence-service HA + streamlined journey design - 2026-08-29

The gateway-evidence readiness design was tightened so cloud evidence services are not single-instance dependencies. The new target is two active/active ingest replicas, two active/active MQTT evidence collectors, two DB-leased verifier workers with the same pinned trusted-decoder digest, cross-host durable raw evidence storage, the existing 3-node Patroni metadata layer, existing 3-node OpenBao, and later two Fabric Adapter workers. The physical gateway journal/uploader remain one-device crash-safe services because there is only one gateway; duplicating a cloud process does not make the gateway hardware HA.

Balanced measurement candidate: `ulc-01 = ingest-1 + collector-1`, `ulc-02 = ingest-2 + verifier-1/decoder`, `ulc-03 = collector-2 + verifier-2/decoder`. At the existing initial 192-MiB/0.20-CPU per-role guardrail this reserves about 384 MiB / 0.40 CPU of evidence-service budget per host before real measurement. Final placement remains blocked until reviewed images exist and the 2-GiB nodes pass capacity preflight.

Important MQTT correction: the commissioned Mosquitto pair provides backend failover but does not replicate MQTT sessions/queues. Therefore each collector replica must maintain persistent read-only sessions to both broker backends using distinct client IDs/credentials. Deliberate duplicate observations converge through a versioned deterministic `capture_key_sha256`, raw-object create-if-absent behavior, and a database uniqueness constraint. Verifier replicas claim pending work with a short `FOR UPDATE SKIP LOCKED` transaction plus expiring `worker_id` lease and commit the lease before object reads/decoding; a crashed worker's pending row is reclaimable after expiry.

A new operator guide `integrations/gateway-integrity/06-replicated-ha-deployment-journey.md` freezes the setup style: one guarded copy/paste block per trust boundary, canary before replica, internal verification gates, bounded secret-free evidence, one named PASS marker, and resume from the first failed gate without redoing prior PASS work. It covers preflight; replicated storage + DB migration; evidence PKI/shared-443 ingress; ingest replicas; dual-broker collector replicas; verifier/decoder replicas; observability; and the later real v2 lineage. `EVIDENCE_REPLICATION_DESIGN=PASS` is a documentation/design result only; no evidence runtime, credential, schema migration, listener, or live server state was created by this update.

### Evidence-services source foundation tranche - 2026-08-30

The first actual implementation tranche was created under repository root `evidence-services/`; this is no longer a Markdown-only architecture. The cloud foundation is a Go 1.22 module using only the standard library at this boundary. It contains validated environment configuration with a secret-safe public summary, JSON `slog` logging, database capability interfaces/constants, the object-store interface, a filesystem **development/smoke-only** object store, and the deterministic `mqtt-capture-v1` identity implementation. The filesystem store streams SHA-256 while writing, fsyncs and protects the temporary inode, publishes create-if-absent using a hard link, treats an exact duplicate as idempotent, rejects same-ref/different-content as a conflict, rejects traversal/absolute/backslash/NUL refs, resolves root symlinks, checks parent containment, and rejects symlink/non-regular object targets. It is explicitly not evidence of one-Droplet-loss durability.

`mqtt-capture-v1` now has an exact versioned byte contract using `ASCII("mqtt-capture-v1")`, a NUL separator, big-endian topic length + UTF-8 topic bytes, then big-endian payload length + exact serialized payload bytes. An independent PowerShell construction reproduced the fixed vector `de1a848838d6d27e02261e0cc37d3478e70dfd5e0e1d381927349dfe803ead74` for topic `as923/gateway/0016c001f139a1cb/event/up` and payload bytes `{"phyPayload":"AQI="}`. `MQTT_CAPTURE_V1_VECTOR=PASS` is authoritative for this source contract.

The new `migrations/001_gateway_evidence.sql` turns the Guide 2 schema into an executable candidate without touching the live database. It defines the four accepted evidence tables, indexes, checkpoint/verification views, constraints, and three passwordless `NOLOGIN` role shells: `gateway_evidence_ingestor`, `gateway_evidence_collector`, and `gateway_evidence_verifier`. Least privilege is enforced with column-level INSERT/UPDATE where authority matters: the ingestor cannot author segment verification state, the collector cannot rewrite accepted captures, verifier discovery may insert only `(source_event_key, observed_at)` so state defaults to `pending`, and only the verifier receives the documented result/lease/status update columns plus segment `verify_status/verify_error`. Existing `telemetry_reader`, when present at deployment, receives only the approved evidence views; existing `fabric_adapter`, when present, receives SELECT-only verifier results. `001_gateway_evidence.verify.sql` is the matching post-migration ACL/schema gate. The exact first-segment `previous_segment_hash` genesis representation remains deliberately unconstrained until the Rust byte contract is frozen rather than guessed.

Static validation passed `git diff --check`, expected source-tree presence, migration non-destructive/least-privilege policy, the independent MQTT fixed vector, filesystem safety primitives, secret-safe config summary, and the no-external-Go-dependency foundation check. Record these as `EVIDENCE_SOURCE_TREE=PASS`, `EVIDENCE_MIGRATION_STATIC_POLICY=PASS`, `MQTT_CAPTURE_V1_VECTOR=PASS`, and `EVIDENCE_GO_FOUNDATION_STATIC=PASS` only. The repository runner returned `spawn go ENOENT` and `spawn docker ENOENT`; therefore **no `go test ./...`, compiled binary, OCI image, or runtime readiness is claimed**. No Patroni schema, PostgreSQL role/credential, evidence listener, PKI material, or live service was changed.

### Trusted decoder + evidence-ingest core source tranche - 2026-08-30

The next evidence-source tranche implemented two previously missing trust boundaries without touching live servers. `cloud/internal/trusteddecoder` now independently parses the frozen 46-byte, big-endian EMU-01 Agriculture Kit payload-v2 format rather than consuming ChirpStack-decoded JSON. It applies the same documented validity-bit semantics as the accepted telemetry contract while remaining a separate implementation: invalid groups yield `quality=invalid` with null value; battery uses the documented zero sentinel; malformed payload length/version and invalid `rain_wet` encoding are rejected. The normalized result is a versioned `trusted-decoder-normalized-v1` compact JSON object with deterministic top-level/metric ordering. An independent Node implementation decoded the frozen raw vector and reproduced `raw_app_data_sha256=06800936504bb1fa954546c3a6bbde7d3a5f2539590d1f32119b19ae162d7460`, 2074 normalized UTF-8 bytes, and `normalized_digest_sha256=594e6f77e8f8f6058a16250e6b30ba96a6766f5813c323c22d93ed6fec7d6118`. Record `TRUSTED_DECODER_SOURCE_VECTOR_STATIC=PASS`; compilation remains unclaimed.

`contracts/evidence-ingest-api-v1` and `cloud/internal/ingest` now define/implement the checkpoint and closed-segment HTTP core. The handler exposes `/livez`, `/readyz`, `POST /v1/gateways/<EUI>/checkpoints`, and `PUT /v1/gateways/<EUI>/segments/<id>`. Its direct TLS identity provider requires a verified client-certificate chain, explicit `clientAuth` EKU, and one 16-hex Gateway EUI Common Name; the handler requires verified identity == path EUI == body EUI and does not trust an arbitrary forwarded identity header. It enforces JSON content type, bounded bodies, unknown-field rejection, no trailing JSON value, lower-case SHA-256 validation, strict base64 segment bytes, and recomputed object SHA. Segment acceptance writes immutable raw bytes create-if-absent **before** metadata; a metadata failure does not delete the raw evidence object. Exact retries converge, conflicting durable identities return conflict, and checkpoint acceptance rejects a lower `last_sequence` than already accepted history. The production PostgreSQL repository must enforce duplicate/conflict/regression atomically per gateway; the current `MemoryRepository` exists only for unit/local smoke.

The checkpoint semantic digest contract is NUL-separated version/EUI/segment/sequence/hashes/UTC timestamp. Independent PowerShell calculation reproduced fixed digest `fde615a8eb264090d324fe5642e0992748de9cc4f2d73cbd8f43459e12792903`. Static validation passed source presence, trusted-decoder source policy, checkpoint vector, mTLS/body/idempotency/regression guards, raw-store-before-metadata ordering, and expected regression-test coverage. Record `EVIDENCE_INGEST_API_CONTRACT=FROZEN`, `EVIDENCE_INGEST_CORE_STATIC=PASS`, and `EVIDENCE_CHECKPOINT_DIGEST_VECTOR=PASS` only. The first attempted normalized-vector validation failed because a PowerShell validation literal produced different bytes; source was not accepted from that result. A separate Node implementation then reproduced the documented 2074-byte normalized object and expected SHA exactly, after which quote-insensitive source/static gates passed. This is useful evidence that the fixed vector caught a validator-byte mistake rather than being bypassed.

No PostgreSQL repository implementation, executable ingest process, network listener, certificate, live migration, database role/credential, or OCI image was created in this tranche. The repository runner still has no Go/Docker toolchain, so `go test ./...`, a compiled binary, and container startup remain pending.

### PostgreSQL evidence-ingest persistence + executable source tranche - 2026-08-30

The next source boundary completed the production metadata side of `gateway-evidence-ingest` without touching the live Patroni cluster. The new module baseline is Go 1.25 with `github.com/jackc/pgx/v5 v5.10.0` pinned. `internal/database/postgres.go` rejects a missing password, wrong logical PgBouncer host/database, non-verified TLS, TLS-name mismatch, connection fallbacks, and non-SCRAM authentication. Every physical session is validated in pgx `AfterConnect` before it enters the pool: expected database, membership in `gateway_evidence_ingestor`, `pg_is_in_recovery()=false`, and `transaction_read_only=off` are mandatory for ingest. The repository readiness probe repeats the role/writable-primary check as a live regression gate.

`internal/ingest/postgres_repository.go` implements transactional checkpoint and segment metadata acceptance. Both use `pg_advisory_xact_lock(hashtextextended(gateway_id, 0))` so replicated ingest workers serialize decisions for the same gateway while unrelated gateways remain concurrent. Checkpoints classify lower sequence as regression, same sequence/same semantic digest as idempotent retry, same sequence/different digest as conflict, and higher sequence as new history. Segment identity uses the same per-gateway serialization and exact metadata equality for duplicate convergence versus conflict.

The migration was hardened at the same boundary. Every persisted `gateway_id` constraint now accepts only canonical lowercase 16-hex EUI text. `gateway_evidence.checkpoints` owns a `BEFORE INSERT` trigger that takes the same advisory transaction lock and rejects a `last_sequence` behind already accepted history, making monotonicity a database invariant even for callers that bypass the Go repository. The post-migration verification script now requires that trigger to exist/enabled and rejects the former uppercase-permitting Gateway-EUI constraint form.

`cmd/evidence-ingest/main.go` now wires protected configuration -> verified PostgreSQL pool -> PostgreSQL repository -> object store -> direct mTLS HTTP handler with bounded HTTP timeouts and graceful SIGTERM/interrupt shutdown. The development filesystem backend remains fail-closed unless `EVIDENCE_ALLOW_DEV_FILESYSTEM=true` is explicitly set, so it cannot silently become the claimed HA evidence store.

Focused static validation passed `git diff --check`, pgx module pin/source-tree checks, PostgreSQL TLS/SCRAM/per-session trust guards, repository advisory-lock/idempotency/regression structure, canonical lowercase Gateway-EUI constraints, database monotonicity trigger + verification-script gate, and executable wiring. Record `EVIDENCE_POSTGRES_CONNECTION_POLICY_STATIC=PASS`, `EVIDENCE_POSTGRES_REPOSITORY_STATIC=PASS`, `EVIDENCE_DB_CHECKPOINT_INVARIANT_STATIC=PASS`, and `EVIDENCE_INGEST_EXEC_STATIC=PASS`. No live migration, role/credential, certificate, network listener, process, binary, or OCI image was created. Real `go test ./...` remains mandatory before image/runtime promotion.

### Replicated MQTT evidence collector source tranche - 2026-08-30

The read-only gateway-MQTT witness source is now implemented without touching either live Mosquitto broker. `mqtt-collector-runtime-v1` freezes one collector process as two independent MQTT v5 clients: `tls://10.104.0.2:8884` and `tls://10.104.0.4:8884`, both verified as `mqtt.internal.lorawan.com`, each with a unique client ID and dedicated protected authentication. The source rejects alternate backend URLs/TLS names for this version because observing one HAProxy failover endpoint would not prove both physical broker witnesses. The subscription is fixed to `as923/gateway/+/event/#`; no MQTT publish call exists in the collector package.

The module now also pins `github.com/eclipse/paho.golang v0.23.0`. Each client uses a non-clean persistent MQTT v5 session with non-zero session expiry, automatic reconnect, and QoS 1 subscription. The collector preserves the exact PUBLISH topic and exact serialized payload bytes without protobuf parsing/re-serialization. It computes `mqtt-capture-v1`, stores the raw payload at stable create-if-absent ref `mqtt/<capture_key_sha256>.event`, verifies the object SHA-256, then inserts `gateway_evidence.mqtt_gateway_events`. `ON CONFLICT (capture_key_sha256) DO NOTHING` followed by exact authoritative-field comparison makes healthy collector/broker duplicates converge while a same-key mismatch fails closed. Receipt time and collector version are intentionally not conflict fields because replicated observations may differ there.

For received QoS > 0, Paho manual acknowledgement is sent only after raw-object and PostgreSQL persistence both succeed. A persistence failure leaves the packet unacknowledged; a successful retry converges on the same raw object and DB identity. QoS 0 has no protocol ACK. Therefore the collector cannot manufacture outage durability for a gateway publisher still using QoS 0: final offline evidence requires the gateway bridge/publisher to use QoS 1, which remains a later hardware-dependent boundary.

The collector exposes `/healthz`, `/readyz`, and `/metrics`; readiness requires both broker sessions connected/subscribed, no outstanding/fatal capture error, PostgreSQL reachable, and object storage healthy. Its executable uses the existing verified PostgreSQL connection policy with `gateway_evidence_collector` membership and remains fail-closed on the development filesystem backend unless explicitly allowed for smoke tests. No collector credential, Mosquitto ACL, client session, listener, process, database row, or live broker configuration was created.

Static checks passed session topology/config constraints, exact direct backend/TLS identity, secret-safe summaries, raw-object-before-DB ordering, PostgreSQL duplicate/conflict semantics, absence of MQTT publish calls, manual-ACK ordering, health/executable wiring, and contract presence. The final independent vector check initially hashed the wrong bytes because the PowerShell fixture used a single-quoted escaped JSON literal whose backslashes became payload bytes; the source was not changed for that failure. Reconstructing the literal JSON payload bytes correctly reproduced `de1a848838d6d27e02261e0cc37d3478e70dfd5e0e1d381927349dfe803ead74`. Record `EVIDENCE_MQTT_SESSION_CONFIG_STATIC=PASS`, `EVIDENCE_MQTT_DURABLE_CAPTURE_STATIC=PASS`, `EVIDENCE_MQTT_READONLY_ACK_STATIC=PASS`, `EVIDENCE_MQTT_EXEC_HEALTH_STATIC=PASS`, and `MQTT_CAPTURE_V1_VECTOR_RECHECK=PASS`. Real `go test ./...`, binary/image creation, broker ACL/identity commissioning, and four-session runtime proof remain pending.

### Evidence verifier discovery/lease/application stage source tranche - 2026-08-30

`verifier-runtime-v1` and `cloud/internal/verifier` now implement the safe portion of the evidence verifier without pretending the unresolved journal/MQTT correlation exists. Discovery scans only durable `telemetry.fabric_outbox` rows with `schema_version='telemetry-attestation-v2'` and idempotently inserts `(source_event_key, observed_at)` while leaving status to the DB default `pending`. HA workers claim one due item through `FOR UPDATE SKIP LOCKED`, set `worker_id`, lease expiry, and attempts, and commit that short transaction before any application evidence reads. Retry and terminal updates require both `status='pending'` and the same `worker_id`, so an expired/reclaimed stale worker cannot overwrite the new owner.

The first deterministic verification stage loads exactly one v2 outbox/uplink source, strict-decodes `telemetry.uplinks.raw_data` Base64 into the original 46 application bytes, requires the approved Node-RED mapping version `agriculture-kit-payload-v2-node-red-v1`, runs the independent trusted decoder, and compares all 13 stored measurements by DevEUI, metric name, unit, source field, quality, type/null semantics, boolean value, and numeric value with only a tiny post-schema-match floating tolerance. Unit fixtures cover the known-good frozen payload, altered stored measurement, and invalid Base64. The trusted-decoder package now exposes a startup `SelfTest()` over the already-frozen raw/normalized SHA-256 vectors and a `PackageDigest` link-time value; production verifier startup rejects an unset/malformed package digest so the eventual two replicas cannot claim an immutable decoder identity before build bytes are pinned.

Fail-closed behavior is explicit. Missing or ambiguous application source is returned to `pending` with bounded retry because ingestion may still be racing. Deterministic unsupported/malformed/mismatched application evidence may transition only the lease-owned row to `integrity_failure`. A fully consistent application/trusted-decoder stage is also returned to `pending`, with reason `journal_correlation_not_implemented`. There is intentionally no repository method or SQL assignment for `status='verified'`; exact source search confirmed zero `status = 'verified'` assignments in the verifier Go package.

The schema was hardened at the same boundary. A future verified row must contain `verified_at` plus gateway ID, journal segment/sequence/record hash/segment hash, checkpoint ID, MQTT gateway-event ID, decoder ID/version, raw application digest, and normalized digest, and cannot carry a reason. `evidence_gap`, `integrity_failure`, and `not_required` require a reason and cannot carry `verified_at`. The verify SQL now requires these constraints. This makes an incomplete verified projection invalid even if future application code is buggy.

Focused static gates passed discovery/lease structure, commit-before-read wording, lease-owner fencing, strict raw Base64 + trusted-decoder comparison, fixed-fixture test coverage, startup decoder self-test/package-digest gate, verifier executable wiring, and DB verified-projection constraints. The initial validator attempts that searched too broadly for the word `verified` failed because of quoting and the legitimate column name `verified_at`; exact repository search then proved the intended absence of the actual SQL assignment pattern. Record `EVIDENCE_VERIFIER_LEASE_DISCOVERY_STATIC=PASS`, `EVIDENCE_VERIFIER_APPLICATION_STAGE_STATIC=PASS`, `EVIDENCE_VERIFIER_DECODER_RUNTIME_STATIC=PASS`, `EVIDENCE_VERIFIED_DB_INVARIANT_STATIC=PASS`, `EVIDENCE_VERIFIER_TEST_COVERAGE_STATIC=PASS`, and `EVIDENCE_VERIFIER_NO_VERIFIED_PATH=PASS`. No live migration, verifier credential, work row, process, listener, binary, image, OpenBao permission, or Fabric permission was created. Full `verified` lineage remains blocked on actual source-event correlation, not application decoding.

### Rust gateway journal/segment byte-contract tranche - 2026-08-30

Repository inspection found that older manuals repeatedly referred to a "saved Concentratord fixture", but no such fixture/protobuf artifact is actually present in the repository. The implementation therefore did **not** invent a parser for `chirpstack-concentratord-sx1302 4.7.1` / `ipc:///tmp/concentratord_event`. Instead, the already-defined typed observation boundary was implemented first in `evidence-services/gateway/` using Rust/Cargo 1.82.

`gateway-journal-v1` now has exact RFC 8785 record bytes, canonical lowercase Gateway EUI, positive signed-64-bit-compatible sequence, exact uppercase `GENESIS` predecessor token, canonical Base64 rules, real Gregorian UTC millisecond timestamp validation, and SHA-256 over exact canonical UTF-8 bytes. The segment layer freezes canonical JSONL (`RFC8785(object) + LF`), header/record/footer ordering, `content_sha256` over exact pre-footer bytes, a twelve-field NUL-separated semantic `segment_hash` preimage with no trailing NUL, and `object_sha256` over the complete closed file. Startup recovery may discard only an incomplete final line; an already-complete invalid line is an integrity failure. Durable state refuses silent sequence/segment renumbering.

An independent Node.js implementation constructed the canonical fixture strings and reproduced: record 1 `443014973b6eab5a01b75f9715470cffdabb05318ac19620c60c5b20fe0e4823`; record 2 `0fbfe1314ab5a7c779ff4872048a02dffa77b2c9c97826f1a62bedf6a070297f`; pre-footer content `48f043a5b36df29eeac3848331aac65258a3c31866667982341386f306e67d4e`; segment `722638f91ff762185aff7c002044911226661c0efc8b70ce71b22a7f168bae90`; complete object `9f34ad301bc0b1b806e2cb0c39a4baaa7509e79b8822f7f367a08720835403f1`. These values are pinned in Rust tests and language-independent contract MDs.

The unapplied PostgreSQL migration and Go ingest validation were aligned to this frozen boundary: segment/checkpoint numbering starts at `1`; segment `1` requires `previous_segment_hash='GENESIS'`; later segments require a real predecessor hash. No live database was changed. The Rust crate's request projection can build segment/checkpoint API bodies. Local evidence retirement remained deliberately disabled pending a stronger acknowledgement boundary.

### Evidence ingest receipt + uploader acknowledgement tranche - 2026-08-30

`evidence-ingest-receipt-v1` now freezes the checkpoint/segment success acknowledgement without adding another PostgreSQL table. The existing authoritative timestamps are reused: `gateway_evidence.checkpoints.server_received_at` and `gateway_evidence.segments.uploaded_at`. The PostgreSQL repository now returns those persisted timestamps both on first insert and exact retry. Checkpoint retry ordering was also corrected so exact `(gateway_id,last_sequence)` identity is checked before the latest-sequence regression gate: an already-accepted old request remains idempotent even after a newer checkpoint exists, while a previously unseen stale checkpoint is still rejected as regression.

Go responses now bind `receipt_version`, artifact type, Gateway EUI, segment ID, last sequence, the checkpoint digest or segment/object hashes, and the original server time into a NUL-separated SHA-256 `receipt_id`. `created` is intentionally excluded from that digest because it is only a per-request creation hint. Rust independently validates all response identity/hash fields, recomputes the receipt ID, rejects unknown response fields/conflicting stored receipts, and keeps checkpoint/segment acknowledgement maps separately. There is intentionally no Rust delete/prune/retire operation based on receipt state.

An independent Node.js calculation produced checkpoint digest `3f7cc53ee0161e73389a8db5764082aa2b293b53f2187023c2107fa1ba935d36`, checkpoint receipt `99e21a0f3fb156e5b9b0b553235698852eb624deb138b74da64e54615ea1333c`, and segment receipt `a5a6378baffe6a4b58aa82bc3875e5534c7964669c2a213e37e47768720930fb` for the frozen two-record journal fixture and server time `2000-01-01T00:00:05.000Z`. Rust Cargo formatting/tests pass with those values pinned. The receipt hash is not a server signature; HTTPS/mTLS remains the response-authentication boundary. No live DB, listener, gateway file, credential, or evidence row was changed. Local evidence retirement remains blocked until the real HTTP uploader, durable receipt-file persistence, production raw store, and one physical-gateway reconciliation path are commissioned.

### Concentratord / MQTT uplink correlation tranche - 2026-08-30

The earlier journal tranche correctly refused to invent a parser while the compatible schema was unknown. That ambiguity is now closed from immutable upstream evidence without pretending a live capture exists. The commissioned `chirpstack-concentratord-sx1302 4.7.1` tag peels to commit `0904a8ddf4eeb3150b4675b35f067865cb68827d` and locks `chirpstack_api 4.17.0` checksum `1eecb20855db95448fb6bbb26bd56187efca90cfe2b486e205dfdaa98ec38ee1`. MQTT Forwarder `4.6.0` peels to `04e870b4af97bebb278ab29259941fd8b3aad72b` and locks `chirpstack_api 4.18.0` checksum `dc57e0b0e8dca97c85058ded65c5420430cc9d97d65a9cfbee973ce258e93362`. The published 4.17.0 and 4.18.0 artifacts contain byte-identical `proto/chirpstack/gw/gw.proto`, 18,459 bytes, SHA-256 `227fda5fd77fb115cb00610fb1ea1fa87c3112d972fc6534342dc7083a6dc12b`.

Pinned upstream source proves the actual transport shape. Concentratord wraps a `gw::UplinkFrame` as `gw::Event.event.uplink_frame` and sends `event.encode_to_vec()` over the ZeroMQ event socket. MQTT Forwarder decodes `gw::Event`, selects `Event::UplinkFrame`, and with JSON disabled publishes `UplinkFrame.encode_to_vec()` to `<prefix>/gateway/<gateway_id>/event/up`. Raw ZeroMQ and MQTT protobuf bytes therefore must not be compared directly. New contract `concentratord-uplink-correlation-v1` hashes NUL-separated Gateway EUI, uplink ID, PHYPayload SHA-256, frequency, and canonical Base64 gateway context. RSSI/SNR remain evidence values but are excluded from the identity digest to avoid cross-language float-text dependence.

An independent Python wire encoder built a synthetic schema fixture: MQTT `gw.UplinkFrame` SHA-256 `a4abfda57c8137349760020a89ba55274bd6627828de95f655f14013cfb6150b`, Concentratord `gw.Event` SHA-256 `7846aeaf29959211c58060916ef06e3a56283326388f4ee8dc43f5a33d1f2a5d`, and common semantic correlation digest `a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494`. The Rust 1.82 adapter decodes the exact required Protobuf tags, validates Gateway EUI/frequency/RSSI/SNR, maps the digest into `gateway-journal-v1.source_event_sha256`, and cross-checks the synthetic Event and MQTT UplinkFrame. `prost` and `prost-derive` are both pinned to `0.14.3`; this matches the commissioned dependency family and avoids the incompatible Rust-1.85 requirement of `prost-derive 0.14.4`. Cargo formatting and all-target tests pass.

The Go cloud source now has a dependency-free minimal UplinkFrame wire parser for the same pinned fields. `gateway-mqtt-evidence-collector` still writes exact raw MQTT bytes first; only `event/up` is then semantically projected. A malformed uplink or topic/Protobuf Gateway-EUI mismatch fails closed after the immutable raw object is retained. The unapplied migration adds `correlation_digest_sha256` and an all-or-none projection constraint for PHYPayload hash, uplink ID, frequency, RSSI, SNR, and correlation digest. This cloud half remains source/static-only because the repository runner has no Go compiler or `gofmt`; no live migration or service was changed.

The verifier is intentionally unchanged at the authority boundary. It still has no `status='verified'` writer because it lacks the raw journal segment/object reader/index, checkpoint lookup/continuity proof, and one-to-one journal↔MQTT counterpart stage. A real paired Concentratord 4.7.1 + MQTT Forwarder 4.6.0 uplink remains a hardware acceptance gate. The next source boundary is that verifier journal reader/checkpoint/correlation stage, while the HTTP uploader and durable receipt-file persistence may proceed independently without enabling deletion.

### Deterministic application -> MQTT -> journal -> checkpoint verifier tranche - 2026-08-30

The source blocker recorded immediately above is now closed at repository/static level without enabling verifier authority. Exact ChirpStack 4.18 schema/source inspection proves `integration.UplinkEvent.rx_info` carries the same `gw.UplinkRxInfo` used by the gateway path, including `uplink_id`; ChirpStack constructs the application event from `uplink_frame_set.rx_info_set.clone()`. The Node-RED repository candidate therefore preserves the same first reception already used for Gateway EUI/RSSI/SNR by adding nullable `gateway_uplink_id`, `gateway_frequency_hz`, and `gateway_context_base64`. The deployed v1 runtime parameter positions are preserved: `$25` remains the Fabric-selection boolean and the new repository candidate appends provenance as `$26..$28`. This is **not deployed**: the live Node-RED A/B flow and live telemetry schema were not changed in this source tranche.

The MQTT collector source now retains gateway context with the existing uplink ID/frequency/RSSI/SNR/PHYPayload/correlation projection. The unapplied migration enforces an all-or-none semantic projection and adds a deterministic lookup index over `(gateway_id,uplink_id,frequency_hz,gateway_context_base64)` for non-null correlation rows. The verifier does not trust those columns by themselves: it reopens the immutable MQTT object, verifies object-store ref/hash/size and serialized SHA-256, recomputes `mqtt-capture-v1`, validates the gateway `event/up` topic, re-decodes the pinned `gw.UplinkFrame`, recomputes `concentratord-uplink-correlation-v1`, and requires the decoded reception to agree with both the stored MQTT projection and application first-reception provenance. Timestamp/nearest-event matching is absent by design.

New Go verifier source parses `gateway-journal-segment-v1` from exact raw JSONL bytes with strict fields/canonical ordering, record-hash recomputation, contiguous sequence, `previous_record_hash`, content SHA-256, segment-hash, footer agreement, and complete object SHA-256. A matching semantic digest is only a prefilter; the selected record must also match MQTT Gateway EUI, PHYPayload, frequency, RSSI, SNR, and gateway-context bytes. For a match in segment N, the verifier reopens and fully verifies **every segment object 1..N**, requiring segment 1/first record `GENESIS` and exact cross-segment segment-hash, final-record-hash, and sequence continuity. It therefore does not accept a PostgreSQL-only predecessor chain.

Checkpoint acceptance is also re-proven rather than trusted from an ID. The repository loads the accepted checkpoint at the matched segment's final sequence, requires version/Gateway EUI/segment/final-sequence/final-record-hash/segment-hash equality, and recomputes the frozen `gateway-checkpoint-v1` NUL-separated digest from `gateway_created_at`. The published independent vector `fde615a8eb264090d324fe5642e0992748de9cc4f2d73cbd8f43459e12792903` is pinned in verifier test source.

A complete source-level match now fills the gateway/journal/checkpoint/MQTT/decoder/raw/normalized lineage columns but deliberately leaves `status='pending'` with `reason_code='lineage_ready_verified_transition_disabled'`. Exact SQL-source inspection confirms no `status='verified'` assignment exists. Missing not-yet-arrived application provenance, MQTT witness, journal predecessor, or checkpoint stays pending; deterministic malformed/ambiguous/conflicting evidence can become `integrity_failure`. The verifier executable now requires the evidence object store and includes it in readiness.

An independently reconstructed one-record segment-1 vector carrying correlation digest `a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494` produced record hash `55f3ec5893ab80e889b71b74cdeaf58b5140582dc581bb37f28f7120470752f4`, pre-footer content SHA-256 `cdd5bfb3f539b76b9a0abe2ff31b900421915404b2b2a9b0ca1ef4866c5ff6e4`, segment hash `244da3566b01cd6557f8f3303266a7b118afdf065f7516782b3c1bbabafef32d`, and complete object SHA-256 `ba15861a63ea3f294db11322d7279f5f3b676049d661125cd2a2bb6d66ff221b`. Independent Python reconstruction of the literal Go fixture reproduced those hashes. Record `NODE_RED_V2_RECEPTION_PROVENANCE_SOURCE=PASS`, `EVIDENCE_MQTT_CONTEXT_STATIC=PASS`, `EVIDENCE_VERIFIER_JOURNAL_READER_STATIC=PASS`, `EVIDENCE_VERIFIER_CHECKPOINT_DIGEST_STATIC=PASS`, `EVIDENCE_VERIFIER_LINEAGE_SOURCE_STATIC=PASS`, and `EVIDENCE_VERIFIER_NO_VERIFIED_SQL_PATH=PASS` for this source boundary.

The current repository runner still has no Go executable (`spawn go ENOENT`), so **do not claim `go test ./...`, gofmt, a compiled verifier binary, or an OCI image**. No live PostgreSQL migration, Node-RED restart/recreate, evidence credential, listener, verification row, raw-store deployment, gateway install, OpenBao permission, or Fabric permission was created. The next mandatory cloud-runtime gate is a real Go compile/test on an approved build host; production replicated raw storage, live migration/credential/service commissioning, guarded Node-RED provenance rollout, and one real paired gateway event remain separate gates before any reviewed `verified` transition can be enabled.

### Reproducible cloud Go build + interrupted-download recovery tranche - 2026-08-30

The prior Go-toolchain blocker is now superseded. `evidence-services/cloud/scripts/dev-build.ps1` pins Go `1.25.0` to official archive `go1.25.0.windows-amd64.zip` with SHA-256 `89efb4f9b30812eee083cc1770fdd2913c14d301064f6454851428f9707d190b`. The bootstrap is project-local and process-local: no global Go install, admin change, PowerShell-profile mutation, or `go env -w` state is required. Toolchain, module/build cache, GOPATH, and Linux build outputs remain under ignored `evidence-services/cloud/.dev-*` paths.

The connection-interruption path was hardened rather than papered over. The bootstrap now preserves `.partial` archive bytes, uses Windows `curl.exe` range-resume mode, retries transient failures, promotes an already-complete partial without another network request when its pinned checksum matches, and extracts only a checksum-valid completed archive. Rerunning the same documented command therefore resumes interrupted setup instead of starting from zero.

The documented normal build completed with `GO_TOOLCHAIN_CHECKSUM=PASS`, `GO_VERSION=PASS`, `GO_MOD_DOWNLOAD=PASS`, `GO_MOD_VERIFY=PASS`, `GOFMT=PASS`, `GO_TEST=PASS`, `GO_BUILD=PASS`, `GO_LINUX_AMD64_BINARIES=PASS`, and `REPRODUCIBLE_GO_BUILD=PASS`. The three Linux/amd64 outputs were `gateway-evidence-ingest` `15172206` bytes SHA-256 `d8af29ae8a52a6695f68ae426aa7afb88ed11b62a5e623d62ce1b687f2d74e32`, `gateway-mqtt-evidence-collector` `15705853` bytes SHA-256 `ce9949183bc85582b6053d72a8a566a9d3f35483ef641f0235bd469b3d55b30f`, and `gateway-evidence-verifier` `15029018` bytes SHA-256 `f8a4a53dc3aaee1084797a7b0ddb278d3f5e3dcf207341029f385d395ab79447`.

A second `-Offline -ResetToolchain` run removed the extracted compiler, rebuilt Go exclusively from the checksum-verified cached archive, disabled Go proxy/checksum network paths, reran module verification/format/tests/builds, and reproduced the **same three sizes and SHA-256 values**. Record `EVIDENCE_GO_COMPILE_TEST=PASS`, `EVIDENCE_GO_REPRODUCIBLE_BUILD=PASS`, and `EVIDENCE_GO_OFFLINE_RESET_REBUILD=PASS`.

This closes the Go compile/test/reproducibility blocker only. Docker/OCI image packaging, production replicated raw storage, live `gateway_evidence` migration/credentials/listeners, shared-443/Evidence PKI, controlled Node-RED provenance rollout, two-replica service deployment, the real commissioned gateway lineage, and the future reviewed `status='verified'` authority transition remain uncommissioned. No live server/gateway service or credential was changed by this build tranche.

### Current S3-capable binary lock + reproducible deployment-bundle tranche - 2026-08-30

The cloud source subsequently gained the reviewed S3-compatible immutable object-store backend, so the older pre-S3 Linux executable hashes above were correctly treated as stale packaging inputs rather than silently reused. The **current** source was rebuilt twice with the pinned Go 1.25.0 toolchain/dependency cache in `-Offline` mode. Both runs passed `GO_MOD_VERIFY=PASS`, `GOFMT=PASS`, `GO_TEST=PASS`, `GO_BUILD=PASS`, `GO_LINUX_AMD64_BINARIES=PASS`, and `REPRODUCIBLE_GO_BUILD=PASS`, and both produced the same bytes: ingest `18140872` bytes / SHA-256 `b2093b6711885be10dfc84bad0835c2e9880ae42e071097bb1dc2686c2629197`; collector `18548881` / `7a93108fb0c551b5cda52165bdf581607ec0db7879e67de17b21cc4321003330`; verifier `17813788` / `3af488e7d6b4278d8b5c3011918b6b1dfa4ecd85d5654b85d18bf70dbcbc00ec`. `evidence-services/cloud/packaging/binaries.lock` now records these current accepted bytes.

`cloud/packaging/build-images.ps1 -Offline -ValidateOnly` rebuilt from cached locked source, matched all three accepted binary hashes, and passed `OCI_BINARY_LOCK=PASS`, `OCI_DOCKERFILE_STATIC=PASS`, and `OCI_PACKAGING_VALIDATE_ONLY=PASS`. The minimal candidate image remains `FROM scratch`, numeric `65532:65532`, one `/service` executable, no shell/package manager/secrets, with deployment-time read-only rootfs/capability controls. There is still no Docker/Buildx on this repository runner, so **no OCI image ID, registry digest, or image reproducibility claim exists yet**.

Two reproducibility limits are recorded precisely rather than hidden. First, the checksum-pinned Go `-Offline -ResetToolchain` recovery mechanism was proven earlier, but an optional replay against the later S3-capable source was cancelled while generated compiler deletion/extraction took too long; current acceptance therefore rests on two identical offline source builds plus the already-proven pinned/recoverable toolchain mechanism, not a claimed current-tree reset replay. Second, `gateway/rust-toolchain.toml`, `gateway/scripts/dev-build.ps1`, and top-level `evidence-services/scripts/verify-build.ps1` now pin Rust 1.82.0 / rustc commit `f6e511eec7342f59a25f7c0534f1dbea00d01b14`, `Cargo.lock`, project-local caches, and online/offline build gates, but the first **fresh isolated Cargo-cache population** stalled during intermittent internet and was cancelled. Earlier Rust 1.82 compile/test evidence remains valid; do not claim the new empty isolated `.dev-cargo` cache has passed offline replay until it is actually populated.

A reproducible server deployment candidate now exists at `evidence-services/cloud/deploy/`. One `compose.yml` freezes HA placement through host profiles: `ulc-01=ingest,collector`, `ulc-02=ingest,verifier`, `ulc-03=collector,verifier`; every runtime is numeric `65532:65532`, read-only, `cap_drop: ALL`, `no-new-privileges`, PID-limited, initially capped at `192 MiB / 0.20 CPU`, and uses bounded container logs. Ingest publishes only to an explicit private host backend IP/port; collector/verifier health is loopback-only. `release.env.example` requires immutable `image@sha256` references. Role env examples contain placeholders only, production config forces the S3 backend, and live secrets/PKI remain outside Git. Password and client-certificate read-only collector authentication are both represented without pretending one was already commissioned.

`deploy/preflight.sh` is deliberately read-only. It verifies the frozen host/profile/IP mapping, immutable image refs, selected ports are currently free, root ownership/modes of env/certificate inputs, `root:GID-65532 0440` runtime private keys, non-dev S3 configuration, role DSN `verify-full` routing through `pgbouncer.internal.lorawan.com:6432`, collector auth-mode inputs, and `docker compose config --quiet`; it does not pull images, start containers, issue credentials, alter files, or mutate PostgreSQL. Repository validation passed Bash syntax, YAML parsing for the base/mTLS Compose files, secret-safe example checks, security/resource/bind-scope invariants, and `git diff --check`.

Record `EVIDENCE_GO_CURRENT_BINARY_REPRODUCIBILITY=PASS`, `EVIDENCE_OCI_PACKAGING_STATIC=PASS`, and `EVIDENCE_DEPLOYMENT_BUNDLE_SOURCE=PASS`. Live markers remain unchanged: no image digest, S3 service, migration/login credential, Evidence PKI, shared-443 route, Node-RED provenance rollout, or evidence service has been activated.

### Verifier trusted-decoder build-identity correction - 2026-08-30

A deployment audit found that the verifier production entry point correctly rejected an unset `trusteddecoder.PackageDigest`, but the reproducible build did not inject that value. The previous verifier binary therefore remained valid compile/test evidence but was not safe to package as a production-startable artifact. The build now computes a deterministic SHA-256 over a canonical manifest of sorted production `internal/trusteddecoder/*.go` files excluding tests, injects that digest into `trusteddecoder.PackageDigest` with Go `-ldflags -X`, and keeps the verifier binary/OCI image digest as a separate artifact identity to avoid a circular self-hash. Unit coverage now proves unset/malformed digests are rejected and a lowercase SHA-256 is accepted.

The corrected source passed the pinned Go 1.25.0 offline module verification, formatting, tests, host compile, and Linux/amd64 cross-build gate. Ingest and collector bytes remained unchanged. The new accepted verifier is `17814046` bytes / SHA-256 `eb578970a1c2a4660eba9752e8109b160d39f33e8655bd0a6808e73016b265d8`, and `evidence-services/cloud/packaging/binaries.lock` was deliberately advanced only after that build passed. The older verifier `17813788` / `3af488...` remains historical evidence only and must not be packaged for deployment.

### Streamlined evidence deployment correction + first live-preflight boundary - 2026-08-30

The deployment candidate was tightened before server activation rather than discovering these faults after containers were started. Buildx packaging now explicitly targets and verifies `linux/amd64`. Every bridge-network evidence container maps `pgbouncer.internal.lorawan.com` to its own node's private IP so hostname-verified TLS still reaches the local `:6432` PgBouncer path. Initial evidence DB pools are reduced to `2` connections per process for the tiny session-pooled POC. The final staged-config preflight now proves public CA/certificate mounts are actually readable by runtime `65532:65532`, keeps private keys at `root:65532 0440`, requires the node-local PgBouncer mapping, and freezes production collectors to mTLS because the current commissioned broker `:8884` listeners require client certificates. The runbook now explicitly includes the required three-node PgBouncer SCRAM-userlist refresh after new PostgreSQL evidence LOGIN roles are created.

A new `evidence-services/cloud/deploy/host-preflight.sh` provides the fast pre-credential live gate. It is read-only and reports node identity, resource headroom, UID/GID 65532 collision risk, Docker/Compose/Buildx, current container RSS, HAProxy/PgBouncer, Patroni/etcd reachability, broker `:8884` mTLS policy, existing anchor `:443`, and dynamically free ingest/health port suggestions. Bash syntax, YAML parsing, a static no-mutation command gate for this script, the updated offline binary-lock/static-OCI packaging gate, and `git diff --check` all passed. No server service, credential, database row/schema, listener, image, or object-store resource was changed by this repository tranche.

The repository runner then attempted the first live three-host access gate. TCP/22 is reachable on `143.198.205.54`, `165.22.253.127`, and `159.223.50.57`, but the runner has no SSH agent and does not possess the project-recorded workstation private key; the documented `id_ed25519_home_ops` path is absent on this runner. Direct public-key login therefore stopped before any remote command executed. Treat this as an execution-environment credential boundary, not a server failure. Do not copy an administrator private key into the repository or onto a Droplet and do not weaken SSH. The immediate live continuation is to run `host-preflight.sh` from the already-authorized workstation SSH path on ulc-01, ulc-02, and ulc-03, then use its actual Buildx/capacity/port output for the next deployment step.

### Evidence live host preflight - ulc-01 PASS - 2026-08-30

The operator ran the read-only evidence-host preflight on `ulc-01`. Host identity was `ulc-01`, x86_64, one vCPU, with `1967 MiB` RAM total and `1255 MiB` available at capture time; root filesystem usage was `8.4 GiB / 48 GiB` with about `40 GiB` available and no swap. Numeric UID/GID `65532` are both free, so the frozen scratch-container runtime identity does not collide with an existing host account/group.

Docker `29.7.2`, Compose `v5.5.0`, and Buildx `v0.36.1` are installed and usable, making `ulc-01` a valid Buildx-capable candidate subject to the remaining ulc-02/03 capacity comparison. Current containers were `openbao`, `chirpstack`, `spilo`, and `etcd`; observed RSS remained modest (`openbao ~39.6 MiB`, `chirpstack ~33.6 MiB`, `spilo ~158.8 MiB`, `etcd ~31.5 MiB`). HAProxy, PgBouncer, and Mosquitto were all active/enabled and HAProxy configuration validation passed.

PgBouncer listens on `10.104.0.2:6432`; `/etc/pgbouncer/userlist.txt` is `0640 root:postgres`, `612` bytes, and currently contains four entries. This confirms the evidence LOGIN-role rollout must include the already-planned static SCRAM userlist expansion. Patroni role probes were healthy with `ulc-01` leader and `ulc-02/03` replicas. Mosquitto `:8884` is TLS 1.3 with `require_certificate true`, `allow_anonymous false`, `use_identity_as_username true`, and `/etc/mosquitto/gateway.acl`, confirming production collectors must use client-certificate authentication as frozen in the deployment bundle.

The current anchor `10.15.0.5:443` is already occupied by HAProxy, preserving the shared-443/SNI design requirement. Candidate evidence ports `18100` (private ingest backend) and `19100` (loopback health) were both free on ulc-01. No configuration, service, image, listener, credential, database, or filesystem mutation occurred. Record `EVIDENCE_HOST_PREFLIGHT_ULC01=PASS`. Next run the same read-only gate on ulc-02 before freezing shared port choices or selecting the Buildx host.

### Evidence raw-object SeaweedFS live commissioning - 2026-08-31

The self-hosted raw-evidence backend advanced from staged design to a real three-node deployment. SeaweedFS `4.41` / commit `de34a1a87` was frozen as `chrislusf/seaweedfs:4.41@sha256:43b768cd62b00d132439cda881b93fd1adebf1b315e996e794087743821d771d`; its dedicated filer metadata quorum uses `quay.io/coreos/etcd:v3.5.15@sha256:0934690612905554eb61ddefb9faaaecb47c2f6931dbb453e694358092ee8990`. The metadata-etcd cluster is three voters on `12379/12380` and remains fully separate from Patroni DCS etcd `2379/2380`.

SeaweedFS core is healthy on ulc-01/02/03 with explicit custom ports: master `19333` HTTP / `19334` gRPC, volume `18082` HTTP / `18083` gRPC, filer `18888` HTTP / `18889` gRPC, raw S3 `127.0.0.1:18333`, S3 gRPC `18334`, and host HAProxy TLS frontend `18443`. The master and filer custom gRPC ports require SeaweedFS address syntax `10.104.0.2:19333.19334` and `10.104.0.2:18888.18889`; the plain `:19333`/`:18888` form incorrectly derives `29333`/`28888`. Record `SEAWEEDFS_CORE_3_NODE=PASS` and `DERIVED_29333_BUG=FIXED`.

Empirical `010` placement was proven with retained object fid `3,01e3ab96f3`, file `seaweed-replication-proof.cBPQms`, size `89`, SHA-256 `bf981516163ff1e35d6315213458423860be84f0b7fe74269ac8d780577bb5b`. The object had exactly two copies on distinct Droplet racks, satisfying the one-additional-copy same-DC/different-rack model. Record `SEAWEEDFS_REPLICATION_010_EMPIRICAL=PASS`. Bucket `lorawan-evidence` is configured at `/buckets/lorawan-evidence/` with replication `010` and volumeGrowthCount `2` on all filers.

Runtime S3 identities were created separately for ingest, collector, and verifier. Ingest and collector receive read/list/write for `lorawan-evidence`; verifier is read/list only. A previously exposed credential set was retired permanently and must never be reused. The active identical `s3.json` on all three hosts is SHA-256 `310aa8b74145256bae9e15f759bacfc37d590a5b54c08c348c38ea7e0c6371f8`, protected as `0640 root:1000` so the SeaweedFS runtime UID/GID can read it without granting broader host access.

Internal object-store PKI was commissioned with CA CN `LoRaWAN Evidence Object Store Internal CA`, logical SAN `evidence-objects.internal.lorawan.com`, node SANs/VPC IPs, RSA-3072 node keys, RSA-4096 CA, and CA SHA-256 `c1dedc8cc6b58217e955cf763868b429dacdd933bbe7d9ffed147122e9d013fd`. TLS material lives under `/etc/lorawan-pki/evidence-objectstore/` with the private material readable only by the host HAProxy boundary. Record `EVIDENCE_OBJECTSTORE_TLS_BUNDLES=PASS`.

The three-node HAProxy evidence-S3 boundary passed. Each frontend binds only its node VPC address on `18443`, requires TLS >=1.2, allows GET/HEAD, and permits PUT only when exactly one `If-None-Match` header is present and equals `*`. Other methods return `405`; malformed/unconditional PUT returns `428`. Backend health uses HEAD to loopback `127.0.0.1:18333` with logical Host. Anonymous access is rejected, signed requests pass with the intended identities, verifier PUT is denied, and raw S3 remains loopback-only. Retained commissioning refs are `_commissioning/haproxy-ulc01-20260831T055839Z-b59e5e443fc3` SHA `28e297...0cd5` size `115`; `_commissioning/haproxy-ulc02-20260831T060950Z-bdf1fc1c13ed` SHA `6fb404...26bd` size `95`; and `_commissioning/haproxy-ulc03-20260831T061258Z-391894922981` SHA `a315fa...fafc` size `95`. Record `HAPROXY_EVIDENCE_S3_3_NODE=PASS`.

Do **not** yet record full `EVIDENCE_OBJECTSTORE=PASS`. S9 remains intentionally open because the accepted production `gateway-evidence-ingest objectstore-contract-write` plus cross-host `objectstore-contract-verify` must still execute. Discovery proved no accepted ingest binary/image is currently present on ulc-01/02/03. The evidence-service source/binary tree is untracked and therefore is not recoverable by simply cloning `origin/main`; do not substitute an unverified rebuild or weaken the exact binary gate.

### Live `gateway_evidence` PostgreSQL migration COMPLETE / PASS - 2026-08-31

The reviewed migration was applied once on the current Patroni leader after re-proving one leader/two replicas and taking a fresh custom-format pre-mutation backup at `/root/backups/evidence-db-pre-migration/20260831T074754Z/lorawan_telemetry.dump`. Backup SHA-256 is `f9564ffaf8e65e021fa025cd45e70c9472608bfa7b6e4912cc568cc773aa21de`, size `79962`, and `pg_restore --list` passed. The TimescaleDB circular `continuous_agg` foreign-key warning is informational for this full custom-format dump and did not invalidate it.

Repository migration source is `001_gateway_evidence.sql` SHA-256 `bf2a1e3188cf67107872c425064d55fb476d7ea58855510b154f7e869795a8b9`, 15947 bytes / 392 lines; verifier source is `001_gateway_evidence.verify.sql` SHA-256 `e08112fd48cdb6be058f40487ac7fff4d4b60a9647f2e1750cf1ebbd974ed4ae`, 8967 bytes / 204 lines. An initial reformatted pasted transport correctly stopped at the source-hash safety gate before any DB mutation. The reviewed terminal transport copies actually executed later had migration SHA `cd03a10f39dc4e780be5f7c7718596816a199dfaf118d7bd9c3f1c5ce4e1a630` and verifier SHA `fc57361eda4fc7fb20e3148eed421e2f653f38dfc25e00e6dee07dba59adc040`; preserve the distinction rather than claiming those transport copies are byte-identical to repository source.

Migration COMMIT succeeded and the authoritative verifier returned `EVIDENCE_DB_MIGRATION_VERIFY=PASS`. Primary summary was `f|4|3|3`; three-node summaries were ulc-01 `f|4|3|3|6|1`, ulc-02 `t|4|3|3|6|1`, ulc-03 `t|4|3|3|6|1`, representing recovery flag, four base tables, three provenance columns, three NOLOGIN authority roles, six indexes, and one checkpoint trigger. The three passwordless authority roles are `gateway_evidence_ingestor`, `gateway_evidence_collector`, and `gateway_evidence_verifier`. Record `EVIDENCE_DB_MIGRATION=PASS`, `EVIDENCE_DB_PRIMARY_VERIFY=PASS`, `EVIDENCE_DB_3_NODE_REPLICATION=PASS`, `EVIDENCE_NOLOGIN_ROLES=3`, and `PGBOUNCER_CHANGED=NO` at this boundary.

### Evidence PostgreSQL HBA authority rollout COMPLETE / PASS - 2026-08-31

A read-only HBA preflight proved all three PostgreSQL members shared the same original 20-rule hardened HBA, zero parse errors, exactly two final reject rules, and no admission for the new evidence authority groups. Rather than add nine new lines, the existing three `hostssl lorawan_telemetry ... /32 scram-sha-256` rules were widened only in their user field to include `+gateway_evidence_ingestor,+gateway_evidence_collector,+gateway_evidence_verifier` alongside `telemetry_writer,telemetry_reader,fabric_adapter`. The rule count therefore remains 20 and the final deny boundary is unchanged.

Rollout proceeded ulc-03 replica canary -> persistence, ulc-02 replica canary -> persistence, then ulc-01 leader canary -> fresh replication-auth gate -> persistence. Every live/persistent HBA list now hashes to `a943358a884249aaae74b663a81fa6dde2d7c98deeb31f93def8e5bb4aa729f1`. No Spilo container restarted/recreated and no Patroni switchover occurred. ulc-02/03 remained streaming throughout.

Three harness defects were corrected without weakening the gate. First, Patroni reload is asynchronous and may take up to ten seconds, so the fixed canary polls `pg_hba_file_rules` up to 30 seconds instead of sleeping three seconds. Second, the old telemetry user selector is a prefix of the new selector, so persistence verification now parses the HBA user field and compares exact values rather than using substring containment. Third, `pg_stat_replication.client_addr::text` can contain netmask notation, so the leader replication assertion now uses `host(client_addr)`.

Before leader persistence, brand-new `IDENTIFY_SYSTEM` physical-replication sessions were created from both replicas using the existing `standby` secret without printing it, `sslmode=verify-full`, logical name `postgres-ha.internal`, and physical leader `10.104.0.2`. Route checks proved source `10.104.0.4` from ulc-02 and `10.104.0.8` from ulc-03. Both new sessions returned system identifier `7676855802088521796`, timeline `3`, LSN `0/68000000`; continuous streams remained `2|2|2|2|2|2` for count/streaming/source/TLS/application/async. Record `FRESH_REPLICATION_AUTH_TO_ULC01=PASS` and three-node HBA rollout COMPLETE / PASS.

Final persistent env hashes after HBA persistence are ulc-01 `ac28a68f1c202d88c9acb1f3f11d54853f7fd2ac036767ae6a36f000978cd371`, ulc-02 `3454842c5cc638b58837603a09b92681d52b3693677fadc7c3a64e616ad2a646`, and ulc-03 `c15488f119b35b755e33aa045ac58a209d09139cf780435680912dabd16c6d53`. These files differ because their non-HBA node configuration differs; the embedded HBA list itself is identical on all three nodes.

### Evidence LOGIN identity issuance partial stop - 2026-08-31

The six planned workload identities are `evidence_ingest_ulc01`, `evidence_ingest_ulc02`, `evidence_collector_ulc01`, `evidence_collector_ulc03`, `evidence_verifier_ulc02`, and `evidence_verifier_ulc03`, each intended to inherit exactly one matching NOLOGIN authority shell. The issuance block started from `existing_evidence_login_count=0`, re-proved the authority-shell semantics and three-node evidence HBA, and left PgBouncer intentionally unchanged.

The first identity, `evidence_ingest_ulc01`, was created successfully with LOGIN, SCRAM-SHA-256, INHERIT, no superuser/CREATEROLE/CREATEDB/REPLICATION/BYPASSRLS, and exactly one direct membership in `gateway_evidence_ingestor`; structural state returned `t|f|f|f|f|t|f|t|1|t`. Its generated pending credential is protected under `/root/evidence-db-bootstrap/` as `0600 root:root`, 65 bytes, and was not printed.

The immediately following direct `sslmode=verify-full` authentication attempt reached PostgreSQL but stopped with `FATAL: permission denied for database "lorawan_telemetry"` / `DETAIL: User does not have CONNECT privilege.` This is a database-level privilege design stop, not evidence of HBA, TLS, SCRAM, password, or role-membership failure. The block exited at that point, so the remaining five workload LOGIN roles were not created. PgBouncer still has the existing four-entry `0640 root:postgres` static SCRAM userlist and zero evidence entries.

Root-cause review then found the authoritative Phase 6 application-credential activation record: `PUBLIC` CONNECT had deliberately been revoked from `lorawan_telemetry`, with CONNECT granted only to the original `telemetry_writer`, `telemetry_reader`, and `fabric_adapter` runtime roles. The evidence migration added schema/table privileges to its three NOLOGIN authority roles but did not add database CONNECT. This exactly explains why the new role reached PostgreSQL with valid SCRAM/TLS and then received a database CONNECT denial.

First CONNECT-authority harness attempt - 2026-08-31: **HARNESS-ONLY STOP / NO DATABASE ACL MUTATION.** Patroni remained `ulc-01` leader with `ulc-02/03` replicas, `lorawan_telemetry` remained owned by `telemetry_admin`, and all three evidence authority shells remained passwordless `NOLOGIN`. The pre-mutation check of the already-created `evidence_ingest_ulc01` returned `true|false|false|false|false|true|false|true|1|true`, which is semantically the same accepted state as `t|f|f|f|f|t|f|t|1|t`. The harness incorrectly concatenated PostgreSQL boolean values into one text expression, causing PostgreSQL to render them as `true/false` while the shell assertion expected psql's separate-column `t/f` format. The script exited before the CONNECT matrix and before the `GRANT CONNECT` transaction; therefore no database ACL, password, HBA, PgBouncer, PostgreSQL reload, or service state changed. Correct the role-state query to return booleans as separate columns and resume the same CONNECT-authority gate.

Exact resume: re-prove the live CONNECT matrix, then grant `CONNECT ON DATABASE lorawan_telemetry` to `gateway_evidence_ingestor`, `gateway_evidence_collector`, and `gateway_evidence_verifier` as the least-privilege authority layer. Preserve `PUBLIC` CONNECT denial and do not add six individual database grants. After that matrix replicates, re-authenticate the existing `evidence_ingest_ulc01` with its protected pending credential, then rerun the idempotent issuance block in safe-resume mode for the remaining five roles. Do not recreate `evidence_ingest_ulc01`, regenerate/rotate its existing protected password, rerun the migration, or repeat the HBA rollout. Only after all six direct verify-full logins and three-node catalog replication pass should PgBouncer be regenerated from authoritative `pg_authid` and rolled sequentially `ulc-01 -> ulc-02 -> ulc-03`.
