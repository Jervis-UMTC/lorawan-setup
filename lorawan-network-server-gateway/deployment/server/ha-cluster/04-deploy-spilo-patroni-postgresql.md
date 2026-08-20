# Server 4. Deploy Spilo, Patroni, and PostgreSQL

## Goal

Run three independent Spilo containers, each with its own PostgreSQL data volume, and let Patroni coordinate them through the etcd quorum.

The lab target is:

```text
spilo-1  PostgreSQL + Patroni  ----+
spilo-2  PostgreSQL + Patroni  ----+--> etcd-1 / etcd-2 / etcd-3
spilo-3  PostgreSQL + Patroni  ----+
```

This is the Docker adaptation of [the cloud Spilo / Patroni manual](../cloud-production/07-spilo-patroni-postgresql-cluster.md).

## Before you start

Confirm etcd is healthy:

```bash
cd /opt/lorawan-lab
docker compose exec etcd-1 sh -lc 'ETCDCTL_API=3 etcdctl --endpoints=http://etcd-1:2379,http://etcd-2:2379,http://etcd-3:2379 endpoint health --cluster'
```

Confirm the Spilo image and PostgreSQL major version have been reviewed:

```bash
. ./.env
docker image inspect "$SPILO_IMAGE" --format '{{json .RepoDigests}} {{json .Config.User}}'
```

Do not use `latest` or change PostgreSQL major versions after a data volume has been initialized.

## Step 1 - Create the shared Spilo environment values

Create `/opt/lorawan-lab/configuration/spilo/cluster.env` mode `600`:

```bash
install -m 600 /dev/null configuration/spilo/cluster.env
nano configuration/spilo/cluster.env
```

Use the exact variable names supported by the selected Spilo revision. The values must represent:

```dotenv
SCOPE=lorawan-lab-postgres
PGVERSION=<APPROVED_POSTGRES_MAJOR>
ETCD_HOSTS=etcd-1:2379,etcd-2:2379,etcd-3:2379
PGUSER_SUPERUSER=postgres
PGPASSWORD_SUPERUSER=<LONG_LAB_SUPERUSER_PASSWORD>
PGUSER_STANDBY=standby
PGPASSWORD_STANDBY=<LONG_LAB_REPLICATION_PASSWORD>
PGUSER_ADMIN=lab_admin
PGPASSWORD_ADMIN=<LONG_LAB_ADMIN_PASSWORD>
ALLOW_NOSSL=true
```

`ALLOW_NOSSL=true` is a **single-VM lab transport exception**. Production PostgreSQL traffic follows the TLS requirements in the cloud manual.

Before starting Spilo, compare these names with the checked-out / reviewed Spilo `ENVIRONMENT.rst` and entrypoint. If the selected image uses a different etcd variable format, correct the lab file before starting.

## Step 2 - Add the Spilo services

Merge this pattern into `compose.yml`:

```yaml
  spilo-1:
    image: ${SPILO_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_SPILO_CPUS}"
    mem_limit: "${LAB_SPILO_MEM}"
    hostname: spilo-1
    env_file:
      - ./configuration/spilo/cluster.env
    environment:
      PATRONI_NAME: spilo-1
    volumes:
      - spilo-1-data:/home/postgres/pgroot
    networks: [dcs, database]
    depends_on: [etcd-1, etcd-2, etcd-3]
    stop_grace_period: 2m

  spilo-2:
    image: ${SPILO_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_SPILO_CPUS}"
    mem_limit: "${LAB_SPILO_MEM}"
    hostname: spilo-2
    env_file:
      - ./configuration/spilo/cluster.env
    environment:
      PATRONI_NAME: spilo-2
    volumes:
      - spilo-2-data:/home/postgres/pgroot
    networks: [dcs, database]
    depends_on: [etcd-1, etcd-2, etcd-3]
    stop_grace_period: 2m

  spilo-3:
    image: ${SPILO_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_SPILO_CPUS}"
    mem_limit: "${LAB_SPILO_MEM}"
    hostname: spilo-3
    env_file:
      - ./configuration/spilo/cluster.env
    environment:
      PATRONI_NAME: spilo-3
    volumes:
      - spilo-3-data:/home/postgres/pgroot
    networks: [dcs, database]
    depends_on: [etcd-1, etcd-2, etcd-3]
    stop_grace_period: 2m
```

`PATRONI_NAME` is illustrative when the selected Spilo build exposes that override. Verify the exact supported member-name variable before start. Every member must end up with a distinct Patroni member name.

### Apply the low-memory PostgreSQL profile

A 768 MiB container limit is only safe when PostgreSQL is also tuned for a small lab. After the first Patroni cluster is initialized, apply these **lab targets** through the selected Spilo/Patroni configuration mechanism:

```text
max_connections = 60
shared_buffers = 128MB
work_mem = 2MB
maintenance_work_mem = 64MB
wal_buffers = 8MB
```

Why these values:

- `shared_buffers` is kept small because three PostgreSQL members run at once;
- `work_mem` is per operation, so large values multiply quickly under concurrent queries;
- `max_connections` is kept low because PgBouncer should absorb client fan-out;
- `maintenance_work_mem` is enough for lab migrations without giving each member hundreds of MiB for maintenance work.

Use `patronictl show-config` after applying the settings. Restart members one at a time if Patroni reports `pending_restart`; never restart all three together.

## Step 3 - Start one member first

```bash
docker compose config --quiet
docker compose up -d spilo-1
docker compose logs -f --tail=200 spilo-1
```

Stop following logs after the first member initializes PostgreSQL and acquires the Patroni leader lock.

Verify its REST endpoint from another container on the database network:

```bash
docker compose exec spilo-1 curl -fsS http://127.0.0.1:8008/patroni
```

If the image does not contain `curl`, use the image's documented HTTP diagnostic tool or an ephemeral curl container attached to the `lorawan-lab_database` network.

## Step 4 - Join the second and third members

```bash
docker compose up -d spilo-2
docker compose logs --since=10m --tail=200 spilo-2
```

Wait until `spilo-2` is a streaming replica, then:

```bash
docker compose up -d spilo-3
docker compose logs --since=10m --tail=200 spilo-3
```

Do not start all three blindly when the first member has not initialized correctly.

## Step 5 - Inspect Patroni membership

Use the Patroni tooling included by Spilo:

```bash
docker compose exec spilo-1 patronictl list
```

If the image requires an explicit config path, locate the generated Patroni configuration first and pass it with `-c`.

Expected state:

```text
one Leader / primary
two Replica members
all three members running
replication lag near zero in an idle lab
```

## Step 6 - Create the ChirpStack database

Connect to the current primary through the Patroni leader container only for this bootstrap step:

```bash
docker compose exec spilo-1 psql -U postgres -d postgres
```

If `spilo-1` is not the current primary, use the member Patroni reports as leader.

At the `psql` prompt:

```sql
CREATE ROLE chirpstack LOGIN;
\password chirpstack
CREATE DATABASE chirpstack OWNER chirpstack;
\q
```

Keep the password in the protected lab secret file, not in Markdown or shell history.

## Verify

On the current primary:

```sql
SELECT pg_is_in_recovery();
SELECT application_name, client_addr, state, sync_state, replay_lag
FROM pg_stat_replication
ORDER BY application_name;
```

Expected: `pg_is_in_recovery()` is `false` on the leader and two replica rows are visible.

## Troubleshooting

If all three members initialize separate clusters, stop immediately. Check the common Patroni scope, etcd connectivity, unique member names, and Spilo environment-variable names. Do not try to merge independently initialized PostgreSQL data directories.

## Next step

Continue with [05-verify-postgresql-ha.md](05-verify-postgresql-ha.md).
