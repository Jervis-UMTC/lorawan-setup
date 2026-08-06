# 7. Spilo, Patroni, and PostgreSQL Cluster

## 7.1 Goal and boundary

Create a three-member PostgreSQL cluster managed exclusively by Patroni and packaged in a reviewed Spilo image. The cluster stores ChirpStack network-server state. Telemetry analytics should use a separate database lifecycle when its scale, extensions, retention, or permissions differ.

PostgreSQL replication provides availability, not protection against logical deletion. WAL/base backups and restore tests remain mandatory.

## 7.2 Select a compatible Spilo image

Spilo combines PostgreSQL and Patroni. Its maintainers recommend building reviewed images from source because public images are not released on a regular cadence.

Identify the Spilo source commit, PostgreSQL major/minor, Patroni version, build tag, registry, immutable image digest, base-image digest, successful build/scan result, and rollback digest. Keep them with the database-volume and backup references because a PostgreSQL data directory can be opened only by a compatible major version and a failed rollout must return every member to a known image.

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

Inspect the Dockerfile, build scripts, installed PostgreSQL/Patroni versions, entrypoint, default users, and environment settings. Build from the documented `postgres-appliance` directory for the selected commit:

```bash
cd postgres-appliance
docker build \
  --build-arg PGVERSION=<APPROVED_POSTGRES_MAJOR> \
  --tag <REGISTRY>/<PROJECT>/spilo:<VERSIONED_TAG> .
```

Run tests and scan the image. Push it, obtain the repository digest, sign it when the organization supports image signing, and deploy only by digest.

## 7.4 Host storage preparation

On each database node, identify the exact attached volume:

```bash
lsblk -o NAME,SIZE,FSTYPE,UUID,MOUNTPOINTS
findmnt
```

Mount it at an approved path such as `/srv/spilo`. Example directory layout:

```bash
sudo install -d -m 700 -o 101 -g 103 /srv/spilo/pgroot
sudo install -d -m 700 -o root -g root /etc/lorawan-cloud/spilo
sudo install -d -m 750 -o root -g <SPILO_GROUP> /etc/lorawan-pki/postgres
sudo install -d -m 750 -o root -g <SPILO_GROUP> /etc/lorawan-pki/etcd-client
```

Container UID/GID values depend on the built image. Inspect them and use the exact values; do not copy the example ownership blindly.

Verify reboot mount persistence before writing PostgreSQL data.

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

WALG_S3_PREFIX=s3://<OBJECT_BUCKET>/<ENVIRONMENT>/<PG_SCOPE>
AWS_ENDPOINT=<SPACES_S3_ENDPOINT>
AWS_REGION=<OBJECT_REGION>
AWS_ACCESS_KEY_ID=<SCOPED_BACKUP_ACCESS_KEY>
AWS_SECRET_ACCESS_KEY=<LOAD_FROM_SECRET_STORE>
```

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
3. Start `db-01` and watch it acquire the initial leader lock and initialize PostgreSQL.
4. Verify PostgreSQL and Patroni before starting the next node.
5. Start `db-02`; wait until it is a streaming replica.
6. Start `db-03`; wait until it is a streaming replica.
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
maximum_lag_on_failover: <APPROVED_BYTES>
postgresql:
  use_pg_rewind: true
  use_slots: true
  parameters:
    max_connections: <CAPACITY_PLAN_VALUE>
    shared_buffers: <CAPACITY_PLAN_VALUE>
    wal_level: replica
    hot_standby: "on"
    password_encryption: scram-sha-256
    ssl: "on"
```

The Patroni timing relationship and minimum values vary by version; validate the resulting configuration with the pinned Patroni release. Do not tune memory values beyond host capacity.

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

## 7.11 Create the ChirpStack database and roles

Connect through the verified primary path. Create roles without exposing passwords in SQL history:

```sql
CREATE ROLE chirpstack LOGIN;
\password chirpstack
CREATE DATABASE chirpstack OWNER chirpstack;
```

Create separate roles for PgBouncer authentication, monitoring, backup, and migrations when needed. Grant only required permissions.

Use a separate, controlled role or procedure for ChirpStack schema migrations when the application supports it. The normal runtime role should not automatically receive unrestricted administrative rights.

## 7.12 WAL-G and replica creation

Verify the built Spilo image's WAL-G integration and object-storage endpoint behavior. Required evidence:

- base backup completes;
- new WAL files arrive in object storage;
- object checksums and encryption policy are active;
- a new replica can be initialized from the selected method;
- a point-in-time restore succeeds in isolation.

Do not declare backups healthy from the existence of objects alone.

## 7.13 Protect Patroni ownership

Disable any host `postgresql.service` that could start the same data directory outside Patroni:

```bash
systemctl list-unit-files | grep -i postgres
```

Do not disable an unidentified unit until its paths are inspected. The completion state must have one owner for PostgreSQL lifecycle: Patroni inside Spilo.

## 7.14 Planned switchover

Before production, test:

```bash
patronictl -c <PATRONI_CONFIG> switchover <PG_SCOPE>
```

Select a candidate deliberately, schedule the operation, and watch:

- old primary demotion;
- new primary promotion;
- HAProxy endpoint change;
- PgBouncer reconnect behavior;
- ChirpStack retries and recovery;
- zero unexpected duplicate or lost test records according to the selected replication mode.

## 7.15 Failed replica recovery

Do not delete the data directory as a first response. Diagnose disk, network, timeline, WAL availability, and logs.

When reinitialization is approved and the node is confirmed to be a replica:

```bash
patronictl -c <PATRONI_CONFIG> reinit <PG_SCOPE> <FAILED_REPLICA_NAME>
```

This is destructive to that replica's local data. Confirm the target twice and preserve incident evidence first.

## 7.16 Final checks

- All three members use the same approved image digest and PostgreSQL major version.
- One primary and two streaming replicas are visible through Patroni and SQL.
- Database and Patroni ports are private-only.
- Application roles use TLS and SCRAM with least privilege.
- Planned switchover succeeds through HAProxy/PgBouncer.
- WAL/base backup and isolated restore have been demonstrated.
- No standalone service can start PostgreSQL outside Patroni.

Next: [08-haproxy-and-pgbouncer.md](08-haproxy-and-pgbouncer.md)
