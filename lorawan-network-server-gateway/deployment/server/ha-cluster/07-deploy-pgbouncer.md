# Server 7. Deploy PgBouncer

## Goal

Make ChirpStack use a stable pooled endpoint:

```text
ChirpStack -> pgbouncer:6432 -> haproxy:5432 -> current Patroni primary
```

This follows the same ordering as [the cloud HAProxy / PgBouncer design](../cloud-production/08-haproxy-and-pgbouncer.md).

## Step 1 - Create PgBouncer configuration

Create `/opt/lorawan-lab/configuration/pgbouncer/pgbouncer.ini`:

```ini
[databases]
chirpstack = host=haproxy port=5432 dbname=chirpstack

[pgbouncer]
listen_addr = 0.0.0.0
listen_port = 6432
pool_mode = session
max_client_conn = 80
default_pool_size = 10
min_pool_size = 2
reserve_pool_size = 5
reserve_pool_timeout = 5
server_connect_timeout = 5
server_login_retry = 5
server_fast_close = 1
client_login_timeout = 30
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
stats_period = 60
```

Start with session pooling. The reduced pool sizes are intentional for the low-rate full-stack lab: PgBouncer should prevent ChirpStack client connections from turning into dozens of PostgreSQL backends on each database member. Do not switch to transaction pooling until the pinned ChirpStack release has been tested for connection/session behavior.

## Step 2 - Create the SCRAM auth file

Obtain the SCRAM verifier for the `chirpstack` PostgreSQL role through a protected administrator session. Do not store the cleartext password in `userlist.txt`.

Create:

```text
/opt/lorawan-lab/configuration/pgbouncer/userlist.txt
```

Format:

```text
"chirpstack" "<SCRAM-SHA-256-VERIFIER>"
```

Then:

```bash
chmod 640 configuration/pgbouncer/userlist.txt
```

## Step 3 - Add PgBouncer to Compose

The exact image entrypoint and configuration paths vary. Use the paths supported by the pinned image. Example intent:

```yaml
  pgbouncer:
    image: ${PGBOUNCER_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_PGBOUNCER_CPUS}"
    mem_limit: "${LAB_PGBOUNCER_MEM}"
    volumes:
      - ./configuration/pgbouncer/pgbouncer.ini:/etc/pgbouncer/pgbouncer.ini:ro
      - ./configuration/pgbouncer/userlist.txt:/etc/pgbouncer/userlist.txt:ro
    networks: [application]
    depends_on: [haproxy]
```

Do not publish `6432` on the host.

## Step 4 - Start and inspect

```bash
cd /opt/lorawan-lab
. ./.env
docker compose config --quiet
docker compose up -d pgbouncer
docker compose ps pgbouncer
docker compose logs --since=5m --tail=100 pgbouncer
```

## Step 5 - Test the complete database route

```bash
docker run --rm --network lorawan-lab_application "$POSTGRES_CLIENT_IMAGE" \
  psql 'host=pgbouncer port=6432 dbname=chirpstack user=chirpstack sslmode=disable' \
  -c 'SELECT current_database(), inet_server_addr(), pg_is_in_recovery();'
```

Use protected password handling.

Expected:

```text
current_database = chirpstack
pg_is_in_recovery = false
```

## Step 6 - Test with a Patroni leader change

While a client repeatedly opens short connections through `pgbouncer:6432`, stop the current Patroni leader.

Expected sequence:

1. existing server connections may fail;
2. Patroni promotes a replica;
3. HAProxy marks the new primary healthy;
4. PgBouncer opens replacement server connections;
5. new SQL connections succeed without changing the client DSN.

## Verify

The lab database path is ready only when:

- PgBouncer authenticates `chirpstack` with SCRAM;
- `pgbouncer:6432` routes to `haproxy:5432`;
- HAProxy routes only to the current Patroni primary;
- a primary failover does not require a DSN change.

## Next step

Continue with [08-deploy-mosquitto.md](08-deploy-mosquitto.md).
