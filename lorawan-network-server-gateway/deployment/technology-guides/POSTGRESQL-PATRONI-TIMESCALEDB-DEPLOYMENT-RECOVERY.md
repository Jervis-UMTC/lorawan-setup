# PostgreSQL / Patroni / TimescaleDB — Rebuild, Operations and Recovery

**Scope:** commissioned three-ULC cloud, not a single-VM tutorial. This expands [operator guide 07](07-postgresql-patroni-timescaledb.md). The actual current primary/replica roles must always come from live Patroni/SQL, never from a historical document. No live schema migration or failover was performed to prepare this chapter.

## 1. Explain the data and role boundaries

~~~text
etcd-01/02/03, quorum 2 of 3
  -> Patroni coordination across ULC-01/02/03
  -> exactly one writable PostgreSQL primary + two streaming replicas
  -> each host's HAProxy :15432 (primary only) and PgBouncer :6432
  -> ChirpStack / Node-RED / evidence / Fabric adapter read-write clients
  -> read-only Grafana on approved route
~~~

PostgreSQL contains two different logical databases: `chirpstack` for network-server users, profiles, device sessions and LoRaWAN state, and `lorawan_telemetry` for normalized uplinks/measurements, evidence metadata and durable Fabric outbox. TimescaleDB is an **extension inside PostgreSQL**, not another server. `telemetry.uplinks` and `telemetry.measurements` are time-series/hypertable objects; `telemetry.fabric_outbox` remains an ordinary transactional table. The independent gateway journal and verifier determine evidence eligibility. Merely finding a `pending` outbox row with zero attempts is not evidence of adapter failure.

## 2. Commissioned deployment inventory

| Item | Commissioned fact / verify |
|---|---|
| Servers | ULC-01 10.104.0.2; ULC-02 10.104.0.4; ULC-03 10.104.0.8 |
| Container | `spilo` on each node, Patroni managed, host network and private PostgreSQL port `5432`, private REST `8008` |
| Image publication | `ghcr.io/jervis-org/spilo/spilo-18-walg309-ospatched@sha256:6bf45913616f2e524555973bfdd34bae1607a709dc3548ab25c8b32a454a9519` |
| Image original validation | Private GHCR immutable digest matched on all three, linux/amd64, numeric postgres UID/GID 101:103 |
| Later documented PostgreSQL/TimescaleDB | PostgreSQL 18.6 / TimescaleDB 2.29.2; re-check `SELECT version()` and `pg_extension` on live primary and all promotion candidates |
| Host persistent storage | `/srv/spilo/pgdata` -> container `/home/postgres/pgdata` |
| Env | `/etc/lorawan-cloud/spilo/spilo.env`, root-owned mode 0600 |
| Server PKI | `/etc/lorawan-pki/postgres/`, certificate/key/CA with protected ownership |
| Clients | TLS/SCRAM through local PgBouncer `:6432` then local HAProxy primary `:15432` |
| Other database route | `:15433` replica/test route if commissioned; never send writes there |

**Reproducibility caveat:** the original immutable image inspection described PostgreSQL 18.3/TimescaleDB OSS 2.26.2, whereas *later* operator-guide records say 18.6/2.29.2. A version string or an unchanged image tag alone does **not** prove how the later package/extension upgrade was applied; read live `docker image inspect`, `SELECT version()` and `SELECT extversion FROM pg_extension` plus approved upgrade/rollback records. Do not assume a backup built against newer binaries can be started by the older original image without a compatibility plan.

## 3. Read-only preflight and health on each host

~~~bash
hostname -f
date -u
df -h /srv/spilo/pgdata
ls -ldn /srv/spilo/pgdata
sudo stat -c '%a %U:%G %n' /etc/lorawan-cloud/spilo/spilo.env
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -i spilo || true
sudo ss -lntp | grep -E ':(5432|8008|6432|15432)\b' || true
sudo docker exec -e LC_ALL=C spilo patronictl -c /run/postgres.yml list
~~~

**PASS:** etcd quorum already healthy, one Patroni leader and the expected replicas without critical lag/restarts, private binds, persistent storage free, host numeric ownership expected for the **running** image. A running Postgres process is not safe promotion evidence. Use a current Patroni list and explicit SQL role checks before a change.

With an already-authorized read-only SQL connection via the normal client route, run:

~~~sql
SELECT now() AT TIME ZONE 'UTC' AS utc_time,
       inet_server_addr() AS backend,
       pg_is_in_recovery() AS is_replica;
SELECT datname FROM pg_database
 WHERE datname IN ('chirpstack','lorawan_telemetry')
 ORDER BY datname;
~~~

For writable-primary routed clients the first row must be `is_replica = false`. On an intentionally queried replica, `true` is expected. If Patroni and SQL disagree, stop writes and diagnose routing/role selection; don't force-promote another node.

Connect to `lorawan_telemetry` for:

~~~sql
SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';
SELECT hypertable_schema, hypertable_name
 FROM timescaledb_information.hypertables
 WHERE hypertable_schema='telemetry'
 ORDER BY 1,2;
SELECT time,dev_eui,metric_name,metric_value,metric_text,metric_bool,unit,quality
 FROM telemetry.measurements ORDER BY time DESC LIMIT 20;
SELECT status,count(*) FROM telemetry.fabric_outbox GROUP BY status ORDER BY status;
~~~

**Interpretation:** existence of extension/hypertables proves schema availability, not fresh sensor receipt. A *known new* real device event should produce canonical uplink and matching measurements with correct units/quality and a stable event identity; dashboard panels are not the database authority.

## 4. Commissioning and controlled rebuild

### 4.1 Preconditions before a new cluster or replacement

1. Prove actual etcd membership 3/3 and current Patroni DCS health. On a replacement, **do not** re-bootstrap a second Spilo scope against a live cluster.
2. Select an image with verified digest **and runtime PostgreSQL/TimescaleDB compatibility**; capture exact approved package/extension versions, source/build recipe and rollback artifact. The image reference above is historical original commissioning authority, not permission to downgrade newer live data.
3. Recover PKI and shared cluster-role secrets securely from approved backup/OpenBao paths; do not commit the protected env or substitute default passwords.
4. Confirm VPC `eth1` routing, clock, firewalls, private listen addresses, storage and WAL space.
5. Confirm the system's restore goal: new empty cluster, rejoin one lost replica, re-create current primary, or isolated whole-cluster recovery. These **need different procedures**.

### 4.2 Host storage and identities

The selected commissioned image used numeric UID 101 / GID 103 *inside* the container. Host account *names* may misleadingly resolve those IDs as unrelated OS users, so use numeric inspection and the current image's `id postgres` rather than blindly changing ownership.

A **new empty volume only** may be created with:

~~~bash
sudo install -d -m 700 -o 101 -g 103 /srv/spilo/pgdata
sudo install -d -m 700 -o root -g root /etc/lorawan-cloud/spilo
sudo install -d -m 750 -o root -g 103 /etc/lorawan-pki/postgres
~~~

Do not run these as a repair over a populated data directory with another image UID. Preserve exact numeric ownership, filesystem/mount and byte-level backup first.

The protected `spilo.env` has the approved path pair `PGROOT=/home/postgres/pgdata/pgroot` and `PGDATA=/home/postgres/pgdata/pgroot/data`. Both must change together if a *future design* migrates paths. `SCOPE=lorawan-postgres-ha` and `ETCD3_HOSTS='"10.104.0.2:2379","10.104.0.4:2379","10.104.0.8:2379"'` remain a shared cluster contract. Set explicit per-container hostname `ulc-01`/`ulc-02`/`ulc-03` plus `SPILO_PROVIDER=local`; relying on a random Docker ID creates wrong Patroni member identities. `PG_CONNECT_ADDRESS` and `RESTAPI_CONNECT_ADDRESS` must use the **corresponding node's** private `:5432/:8008`.

**Subtle TLS-only configuration:** `ALLOW_NOSSL=` is intentionally the **empty string** for this pinned Spilo template; `ALLOW_NOSSL=false` is nonempty and evaluated truthy by its Mustache rendering, risking an unintended non-TLS policy. Verify the rendered effective PostgreSQL configuration, not only env text. Do not invent etcd TLS flags while deployed etcd remains private-network HTTP. Keep PostgreSQL TLS CA, server certificate and key in approved private `/etc/lorawan-pki/postgres/`, with the actual image user able to read the key and other host users unable to do so.

### 4.3 Reproduce the service definition safely

Inspect the existing commissioned Compose definition before writing a replacement. Required structural invariants:

~~~yaml
services:
  spilo:
    image: ghcr.io/jervis-org/spilo/spilo-18-walg309-ospatched@sha256:6bf45913616f2e524555973bfdd34bae1607a709dc3548ab25c8b32a454a9519
    container_name: spilo
    hostname: ulc-01
    network_mode: host
    restart: unless-stopped
    env_file:
      - /etc/lorawan-cloud/spilo/spilo.env
    volumes:
      - /srv/spilo/pgdata:/home/postgres/pgdata
      - /etc/lorawan-pki/postgres:/run/postgres-certs:ro
~~~

**Template only:** change hostname appropriately for ULC-02/03 and preserve any current resource limits, security options, logging, runtime overrides and image compatible with the live PGDATA. Do not write over the real Compose file based solely on this abbreviated demonstration. Confirm `docker compose config --quiet`, private listener overrides and correct local ETCD3_HOSTS before any first start.

### 4.4 First installation versus adding a member

An *entirely empty authorized* cluster first starts its nominated seed node, proves one Patroni leader/database, then brings up other members one at a time and verifies replication/role/lag. A **lost replica** is restored/reinitialized only after identifying its DCS membership, current primary and backup requirements; do not erase an existing member to make it rejoin. A **lost primary** is not rebuilt as a competing writer: check surviving Patroni leadership and rejoin it in the correct role with the approved procedure. Database schema/extension creation is done exactly once through the current primary.

Do not perform a wholesale dump restore, schema recreation, `pg_resetwal` or an arbitrary Patroni promotion while a surviving cluster is servicing applications. A full cluster restore requires controlled workload fencing, RPO/RTO decisions, a consistent database image or logical dumps and reviewed member/DCS reconstitution.

## 5. TimescaleDB and transactional event semantics

After a compatible database upgrade, verify every promotion-eligible node has the extension binaries/library needed by the recorded schema version; run `SELECT extversion FROM pg_extension WHERE extname='timescaledb';` against `lorawan_telemetry` and inspect `shared_preload_libraries` where relevant. A working node on an old extension version is not automatically a safe failover target.

Application MQTT delivery can repeat. The single active Node-RED writer and SQL constraints/transaction must preserve one canonical uplink + normalized measurements for the stable event ID and correct outbox association, even on redelivery. Node-RED cannot set gateway verifier-owned status or forge finalized Fabric bytes. To investigate `pending, attempts=0`, check immutable `finalized_payload` and independently owned v2 `verified` eligibility before touching Fabric worker state.

## 6. Backup, restore and disaster recovery

**HA replication ≠ backup:** logical deletion, malicious updates and some corruption replicate. Distinguish the **Phase 13A** pre-cutover fast-path backup, **13S** interim server-only snapshot, and **13B** final fully commissioned recovery set. The last is not automatically complete merely because 13S exists. The full recovery package must cover PostgreSQL both databases, extension/schema versions, owners/roles, protected credential inventory, PKI, Spilo image digest, Compose/env references, etcd snapshot, client HA routes, evidence/Fabric metadata and gateway continuity. No plaintext passwords/keys in a general-purpose archive.

An authorized administrator on the **current primary** creates protected logical backups using the installed compatible tools; illustrative shape:

~~~bash
umask 077
# Use approved root/admin connection and protected backup directory.
# pg_dump -Fc -d chirpstack -f <PROTECTED_CHIRPSTACK_DUMP>
# pg_dump -Fc -d lorawan_telemetry -f <PROTECTED_TELEMETRY_DUMP>
~~~

The commented forms are *deliberately not runnable* until the actual connection, output paths and correct running image/tool versions have been discovered. Verify both dump catalogs with `pg_restore --list`, byte counts/hashes, owner/global objects separately as required, off-host copy and retention. For a controlled **isolated** restore, require the TimescaleDB extension, correct owners/grants, schema objects/hypertables, known row samples and representative query; a file's existence is not a restore PASS.

Never restore a database snapshot that moves Fabric outbox/evidence records backwards while the external HRC ledger and gateway checkpoint have advanced without a reconciliation design. Choose the authoritative recovery boundary and fence affected writers first.

## 7. Failure/rollback decision tree

| Symptom | Inspect first | Avoid |
|---|---|---|
| no Patroni leader | etcd quorum/DCS, private REST and member status | forced PG promote |
| one replica behind | disk/WAL/network/cert/replication slot, bounded logs | switchover to stale replica |
| good leader, app cannot SQL | local PgBouncer :6432 -> HAProxy :15432, SCRAM/TLS | altering leader |
| wrong backend role | HAProxy Patroni leader health/route, primary-only SQL | hardcoded DB leader IP |
| Timescale query fails after promotion | extension binary/version and preload on promoted member | deleting hypertable |
| duplicate telemetry | MQTT redelivery, Node-RED identity/constraints | lowering QoS |
| pending Fabric outbox | exact finalized bytes and v2 verifier eligibility | manual status rewriting |
| rollback after major/schema change | compatible tested snapshot + workload fence | older image over new PGDATA |

## 8. Acceptance

Normal operation: etcd 3/3, one Patroni leader and expected streaming replicas, TLS/SCRAM route through PgBouncer/HAProxy to `pg_is_in_recovery() = false`, both logical DBs, correct extension/hypertables, one real source event persisted with safe deduplication and clear outbox/verifier states. Destructive recovery/host failover acceptance is a separate approved experiment and should not be repeated during docs-only work.

See [original Spilo commissioning and exact approved image/env](../server/cloud-production/06-spilo-patroni-postgresql-cluster.md), [pool/router layer](../server/cloud-production/07-haproxy-and-pgbouncer.md), [backup source](../server/cloud-production/13-backup-restore-and-disaster-recovery.md). For the final standalone Word document, embed complete procedures and verified commands with their host context, rather than linking to Markdown.
