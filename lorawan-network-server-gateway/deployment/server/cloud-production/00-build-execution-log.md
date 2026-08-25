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
