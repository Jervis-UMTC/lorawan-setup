# 7. Spilo, Patroni, and PostgreSQL Cluster

## 7.1 Goal and boundary

Create a three-member PostgreSQL cluster managed exclusively by Patroni and packaged in a reviewed Spilo image.

For this **tiny HA proof of concept**, the same PostgreSQL cluster stores both:

```text
chirpstack
lorawan_telemetry
```

`lorawan_telemetry` is the Timescale-enabled telemetry database. The POC removes only the **separate TimescaleDB server**, not the TimescaleDB feature. The same pinned TimescaleDB extension build must be available on PostgreSQL/Patroni-1, -2, and -3 before any member is considered promotion-eligible.

Use Timescale hypertables for `telemetry.uplinks` and `telemetry.measurements`. Keep `telemetry.fabric_outbox` as an ordinary PostgreSQL table in the same database because it is a transactional work queue rather than time-series storage.

PostgreSQL replication provides availability, not protection against logical deletion. For the POC, keep at least a logical dump before destructive tests; production-grade WAL/object-storage recovery is a later sizing/design step.

## 7.2 Select a compatible Spilo image

Spilo combines PostgreSQL and Patroni. Its maintainers recommend building reviewed images from source because public images are not released on a regular cadence.

Identify the Spilo source commit, PostgreSQL major/minor, Patroni version, **TimescaleDB extension version/build**, build tag, registry, immutable image digest, base-image digest, successful build/scan result, and rollback digest. Keep them with the database-volume and backup references because a PostgreSQL data directory can be opened only by a compatible major version and a failed rollout must return every member to a known image.

**Stop here. Do not bootstrap** from `latest`, an unscanned image, or an image whose PostgreSQL major version does not match the data-volume lifecycle.

## 7.3 Build and inspect the image

Use a controlled CI runner. Illustrative flow:

```bash
git clone https://github.com/zalando/spilo.git
cd spilo
git checkout <APPROVED_SPILO_COMMIT>
git status --short --branch
git show --stat --oneline HEAD
```

Inspect the Dockerfile, build scripts, installed PostgreSQL/Patroni versions, entrypoint, default users, environment settings, and the selected commit's TimescaleDB build arguments. Spilo supports TimescaleDB in its image build, but the **exact supported PostgreSQL/TimescaleDB combination is commit-dependent**; do not infer it from an old release note.

Build from the documented `postgres-appliance` directory for the selected commit. A typical build keeps TimescaleDB enabled and selects only the PostgreSQL major deliberately:

```bash
cd postgres-appliance
docker build \
  --build-arg PGVERSION=<APPROVED_POSTGRES_MAJOR> \
  --tag <REGISTRY>/<PROJECT>/spilo:<VERSIONED_TAG> .
```

If the selected commit exposes `TIMESCALEDB_APACHE_ONLY`, `TIMESCALEDB_TOOLKIT`, or other Timescale-related build args, record their values in the software worksheet. Do not change license/feature variants accidentally between nodes.

Before pushing the image, prove the Timescale control/library files exist inside **this exact build** using paths discovered from the image rather than assumed host paths:

```bash
docker run --rm --entrypoint bash \
  <REGISTRY>/<PROJECT>/spilo:<VERSIONED_TAG> \
  -lc 'set -e; pg_config --version; \
       find /usr/share/postgresql -path "*/extension/timescaledb.control" -print; \
       find /usr/lib/postgresql -name "timescaledb*.so" -print'
```

The command must print the PostgreSQL version plus TimescaleDB extension/library files for the intended major. **Stop here** if it prints no TimescaleDB control/library files or the PostgreSQL major is wrong.

Run tests and scan the image. Push it, obtain the repository digest, sign it when the organization supports image signing, and deploy **the same digest** on all three members.

## 7.4 Host storage preparation

The minimum test profile uses each Droplet's included SSD; it does **not** require a separate block volume. First verify the root filesystem and free space:

```bash
lsblk -o NAME,SIZE,FSTYPE,UUID,MOUNTPOINTS
df -h /
findmnt /
```

Keep PostgreSQL data under a dedicated host path such as `/srv/spilo` on that node's own root SSD. If a block volume is added later because measurements require it, verify the exact device and persistent mount before moving data. Example directory layout:

```bash
sudo install -d -m 700 -o 101 -g 103 /srv/spilo/pgroot
sudo install -d -m 700 -o root -g root /etc/lorawan-cloud/spilo
sudo install -d -m 750 -o root -g <SPILO_GROUP> /etc/lorawan-pki/postgres
sudo install -d -m 750 -o root -g <SPILO_GROUP> /etc/lorawan-pki/etcd-client
```

Container UID/GID values depend on the built image. Inspect them and use the exact values; do not copy the example ownership blindly.

Verify the selected filesystem survives reboot and the `/srv/spilo` path has the expected ownership before writing PostgreSQL data.

## 7.5 Protect the environment file

Create `/etc/lorawan-cloud/spilo/spilo.env` mode `600`. Required categories include:

```dotenv
SCOPE=<PG_SCOPE>
PGVERSION=<APPROVED_POSTGRES_MAJOR>
PGROOT=/home/postgres/pgroot

ETCD_HOSTS="<ETCD_1>:2379","<ETCD_2>:2379","<ETCD_3>:2379"
ETCD_CACERT=/run/etcd-client/ca.crt
ETCD_CERT=/run/etcd-client/client.crt
ETCD_KEY=/run/etcd-client/client.key

PGUSER_SUPERUSER=postgres
PGPASSWORD_SUPERUSER=<LOAD_FROM_SECRET_STORE>
PGUSER_STANDBY=standby
PGPASSWORD_STANDBY=<LOAD_FROM_SECRET_STORE>
PGUSER_ADMIN=<NAMED_ADMIN_ROLE>
PGPASSWORD_ADMIN=<LOAD_FROM_SECRET_STORE>

SSL_CA_FILE=/run/postgres-certs/ca.crt
SSL_CERTIFICATE_FILE=/run/postgres-certs/server.crt
SSL_PRIVATE_KEY_FILE=/run/postgres-certs/server.key
ALLOW_NOSSL=false
```

The minimal HA POC intentionally does **not** require WAL-G, object-storage endpoints, or cloud backup access keys. Do not populate fake `WALG_*` / `AWS_*` values merely because a production Spilo example contains them. Add those variables later only when the production backup/PITR profile is intentionally enabled and tested.

Confirm exact variable names against the checked-out Spilo `ENVIRONMENT.rst` and built entrypoint. Spilo documents insecure example default passwords; override every credential explicitly.

Use one identical `SCOPE` and etcd endpoint list on all members. Use unique member identity/hostname values where the image requires them.

## 7.6 Container definition

A per-node Compose pattern:

```yaml
services:
  spilo:
    image: <REGISTRY>/<PROJECT>/spilo@sha256:<APPROVED_DIGEST>
    container_name: spilo
    network_mode: host
    restart: unless-stopped
    env_file:
      - /etc/lorawan-cloud/spilo/spilo.env
    volumes:
      - /srv/spilo/pgroot:/home/postgres/pgroot
      - /etc/lorawan-pki/postgres:/run/postgres-certs:ro
      - /etc/lorawan-pki/etcd-client:/run/etcd-client:ro
    stop_grace_period: 2m
```

Host networking simplifies stable private addresses for PostgreSQL 5432 and Patroni REST 8008, but makes firewall correctness critical. Inspect the image's expected capabilities, health checks, and paths before deployment.

Validate without printing expanded secrets:

```bash
sudo docker compose -f /etc/lorawan-cloud/spilo/compose.yml config --quiet
sudo docker pull <PINNED_IMAGE_REFERENCE>
sudo docker image inspect <PINNED_IMAGE_REFERENCE> --format '{{json .RepoDigests}}'
```

## 7.7 Bootstrap order

1. Prove etcd quorum and TLS from every database node.
2. Confirm all three Spilo data directories are empty for a new cluster.
3. Start PostgreSQL/Patroni on `ha-01` and watch it acquire the initial leader lock and initialize PostgreSQL.
4. Verify PostgreSQL and Patroni before starting the next node.
5. Start PostgreSQL/Patroni on `ha-02`; wait until it is a streaming replica.
6. Start PostgreSQL/Patroni on `ha-03`; wait until it is a streaming replica.
7. Do not start all nodes blindly and ignore conflicting bootstrap logs.

```bash
sudo docker compose -f /etc/lorawan-cloud/spilo/compose.yml up -d
sudo docker logs --since=10m --tail=300 spilo
curl --cacert <PATRONI_CA_IF_ENABLED> https://<DB_PRIVATE_IP>:8008/patroni
```

Patroni REST protection depends on the pinned configuration. Keep the API private and use TLS/authentication where supported.

## 7.8 Cluster inspection

Use `patronictl` from a protected administrative environment with the exact DCS/TLS configuration:

```bash
patronictl -c <PATRONI_CONFIG> list <PG_SCOPE> --extended
```

Expected:

- one primary with leader lock;
- two streaming replicas;
- one timeline;
- no pending restart unless planned;
- acceptable receive/replay lag;
- distinct member names and private addresses.

Database checks:

```sql
SELECT pg_is_in_recovery();
SELECT current_setting('server_version');
SELECT application_name, client_addr, state, sync_state,
       write_lag, flush_lag, replay_lag
FROM pg_stat_replication
ORDER BY application_name;
```

Run the replication query on the primary.

## 7.9 Patroni dynamic configuration

Inspect before editing:

```bash
patronictl -c <PATRONI_CONFIG> show-config <PG_SCOPE>
```

Review values such as:

```yaml
loop_wait: 10
retry_timeout: 10
ttl: 30
maximum_lag_on_failover: <POC_APPROVED_BYTES>
postgresql:
  use_pg_rewind: true
  use_slots: true
  parameters:
    max_connections: 40
    shared_buffers: 128MB
    work_mem: 2MB
    maintenance_work_mem: 32MB
    shared_preload_libraries: 'timescaledb'
    wal_level: replica
    hot_standby: "on"
    password_encryption: scram-sha-256
    ssl: "on"
```

These are intentionally small POC starting values for the 2-GiB nodes. PgBouncer keeps application concurrency from becoming an oversized PostgreSQL connection budget. If the pinned image or measured workload needs more memory, change one value at a time and record why.

The Patroni timing relationship and minimum values vary by version; validate the resulting configuration with the pinned Patroni release.

### Replication mode decision

For asynchronous mode, define an accepted RPO and `maximum_lag_on_failover`.

For synchronous mode, decide whether writes may block when no synchronous standby is available. Change mode through Patroni's cluster configuration, not by editing `synchronous_standby_names` manually.

Perform load and failure tests for the selected mode.

## 7.10 PostgreSQL TLS and `pg_hba`

Require TLS for application, replication, backup, and administrative connections unless a documented private-network exception is approved.

Allow only exact VPC sources and named roles. Conceptual rules:

```text
hostssl replication <REPLICATION_ROLE> <POSTGRES_SUBNET> scram-sha-256
hostssl <CHIRPSTACK_DB> <CHIRPSTACK_ROLE> <APP_SUBNET> scram-sha-256
hostssl postgres <MONITOR_ROLE> <MONITOR_SUBNET> scram-sha-256
```

Do not use `trust`, broad `0.0.0.0/0`, or application superusers.

## 7.11 Create both POC databases and roles

Connect through the verified primary path. Create the ChirpStack database first:

```sql
CREATE ROLE chirpstack LOGIN;
\password chirpstack
CREATE DATABASE chirpstack OWNER chirpstack;
```

Then create the telemetry database on the **same Patroni cluster**:

```sql
CREATE ROLE telemetry_admin LOGIN;
\password telemetry_admin
CREATE DATABASE lorawan_telemetry OWNER telemetry_admin;
```

Inside `lorawan_telemetry`, create separate runtime identities for the small POC:

```sql
CREATE ROLE telemetry_writer LOGIN;
CREATE ROLE telemetry_reader LOGIN;
CREATE ROLE fabric_adapter LOGIN;
```

Set their passwords using `\password` or the approved secret workflow; do not put live passwords in Markdown or shell history.

Why separate logical databases/roles even in a tiny POC: it preserves the future security and ownership boundaries without paying for another database service.

Create separate roles for monitoring, migrations, and PgBouncer administration only when needed by the POC.

## 7.12 Enable TimescaleDB inside the Patroni cluster

TimescaleDB is a PostgreSQL extension, so there is no fourth database server. However, every Patroni member must have a compatible TimescaleDB library available locally before that member may be promoted.

### Step 1 - prove the extension files exist on all three members

Run against each PostgreSQL member directly over the private network using an administrative connection:

```sql
SELECT name, default_version
FROM pg_available_extensions
WHERE name = 'timescaledb';
```

Pass only when all three members report `timescaledb` and the intended build is compatible with the pinned PostgreSQL major. Record the image/package version for each node. A replica with missing or mismatched TimescaleDB binaries is **not promotion-ready**.

### Step 2 - preload TimescaleDB consistently

Keep `timescaledb` in `shared_preload_libraries` through Patroni-managed PostgreSQL configuration on all members. If another required preload library already exists, append TimescaleDB; do not overwrite the existing list.

After the controlled restart required by the pinned PostgreSQL/Timescale version, verify on every member:

```sql
SHOW shared_preload_libraries;
```

### Step 3 - enable the extension only in `lorawan_telemetry`

Connect through the verified writable-primary path:

```sql
\c lorawan_telemetry
CREATE EXTENSION IF NOT EXISTS timescaledb;

SELECT extname, extversion
FROM pg_extension
WHERE extname = 'timescaledb';
```

Do not enable TimescaleDB in the `chirpstack` database unless a real ChirpStack requirement appears. ChirpStack remains an ordinary PostgreSQL database.

### Step 4 - create the real telemetry schema

Reuse the generic multi-sensor schema from [../integrations/timescaledb/02-create-telemetry-schema.md](../integrations/timescaledb/02-create-telemetry-schema.md), adapting only the connection command because this cloud POC connects through PgBouncer/HAProxy instead of a standalone `telemetry-db` container.

Required POC shape:

```text
lorawan_telemetry [TimescaleDB]
  telemetry.uplinks       -> hypertable
  telemetry.measurements  -> hypertable
  telemetry.device_registry
  telemetry.latest_uplinks
  telemetry.latest_measurements
  telemetry.fabric_outbox -> ordinary PostgreSQL table
```

Use the hypertable creation syntax supported by the **pinned TimescaleDB version**. Keep uniqueness rules compatible with the time partition column. Do not enable a destructive retention policy until the intended retention period and backup boundary are approved.

### Step 5 - prove Timescale survives PostgreSQL failover

Before the first full host-failure test, perform a controlled Patroni switchover and then query through the unchanged PgBouncer endpoint:

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'timescaledb';

SELECT hypertable_schema, hypertable_name
FROM timescaledb_information.hypertables
ORDER BY 1, 2;
```

Pass when the promoted primary reports the same TimescaleDB extension and both telemetry hypertables without reinstalling or recreating anything.

## 7.13 POC backup boundary

Do not add paid object storage merely to prove the HA topology unless the test specifically includes disaster recovery.

Before destructive tests, take logical dumps of both databases and copy them off the target Droplet, for example to the administration workstation:

```text
chirpstack.dump
lorawan_telemetry.dump
```

This is enough for the HA POC rollback boundary. WAL-G, continuous WAL archiving, PITR, and production retention remain future deployment work.

HA and backup are still different concepts: three PostgreSQL replicas do not protect against an accidental `DELETE` replicated to all three nodes.

## 7.14 Protect Patroni ownership

Disable any host `postgresql.service` that could start the same data directory outside Patroni:

```bash
systemctl list-unit-files | grep -i postgres
```

Do not disable an unidentified unit until its paths are inspected. The completion state must have one owner for PostgreSQL lifecycle: Patroni inside Spilo.

## 7.15 Planned switchover

Before production, test:

```bash
patronictl -c <PATRONI_CONFIG> switchover <PG_SCOPE>
```

Select a candidate deliberately, schedule the operation, and watch:

- old primary demotion;
- new primary promotion;
- HAProxy endpoint change;
- PgBouncer server-connection replacement and HAProxy primary-routing behavior;
- ChirpStack retries and recovery;
- zero unexpected duplicate or lost test records according to the selected replication mode.

## 7.16 Failed replica recovery

Do not delete the data directory as a first response. Diagnose disk, network, timeline, WAL availability, and logs.

When reinitialization is approved and the node is confirmed to be a replica:

```bash
patronictl -c <PATRONI_CONFIG> reinit <PG_SCOPE> <FAILED_REPLICA_NAME>
```

This is destructive to that replica's local data. Confirm the target twice and preserve incident evidence first.

## 7.17 Final checks

- All three members use the same approved image digest and PostgreSQL major version.
- One primary and two streaming replicas are visible through Patroni and SQL.
- Database and Patroni ports are private-only.
- `chirpstack` and `lorawan_telemetry` both exist on the same Patroni cluster.
- The same pinned TimescaleDB extension build is available on all three PostgreSQL members.
- `timescaledb` is enabled in `lorawan_telemetry`, not in `chirpstack`.
- `telemetry.uplinks` and `telemetry.measurements` are Timescale hypertables; `telemetry.fabric_outbox` is an ordinary PostgreSQL table.
- A Patroni switchover preserves the extension and hypertables without reinstalling them.
- Application roles use TLS and separate credentials.
- Planned switchover succeeds through PgBouncer and HAProxy without application DSN edits for ChirpStack, Node-RED, Grafana, or the Fabric adapters.
- Logical POC dumps exist before destructive failure tests.
- No standalone service can start PostgreSQL outside Patroni.

Next: [08-haproxy-and-pgbouncer.md](08-haproxy-and-pgbouncer.md)
