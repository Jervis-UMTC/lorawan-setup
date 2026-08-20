# Server 6. Deploy HAProxy for the Patroni Primary

## Goal

Give downstream services one stable PostgreSQL primary endpoint:

```text
haproxy:5432 -> current Patroni primary
```

HAProxy chooses the backend by checking Patroni `/primary`, not by assuming `spilo-1` is always the leader.

## Step 1 - Create the HAProxy configuration

Create `/opt/lorawan-lab/configuration/haproxy/haproxy.cfg`:

```haproxy
global
    log stdout format raw local0
    maxconn 128

defaults
    log global
    mode tcp
    option tcplog
    timeout connect 5s
    timeout client 60s
    timeout server 60s
    timeout check 5s

frontend postgres_primary
    bind *:5432
    default_backend patroni_primary

backend patroni_primary
    option httpchk GET /primary
    http-check expect status 200
    default-server inter 2s fall 3 rise 2 on-marked-down shutdown-sessions
    server spilo-1 spilo-1:5432 check port 8008
    server spilo-2 spilo-2:5432 check port 8008
    server spilo-3 spilo-3:5432 check port 8008
```

The cloud deployment can use TLS/authenticated Patroni REST checks. This single-host lab keeps the Patroni REST network internal to Docker.

## Step 2 - Add HAProxy to Compose

```yaml
  haproxy:
    image: ${HAPROXY_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_HAPROXY_CPUS}"
    mem_limit: "${LAB_HAPROXY_MEM}"
    volumes:
      - ./configuration/haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro
    networks: [database, application]
    depends_on: [spilo-1, spilo-2, spilo-3]
```

Do not publish HAProxy PostgreSQL port `5432` on the VM host. PgBouncer reaches it through the Docker network.

## Step 3 - Validate configuration

```bash
cd /opt/lorawan-lab
. ./.env
docker run --rm \
  -v "$PWD/configuration/haproxy/haproxy.cfg:/usr/local/etc/haproxy/haproxy.cfg:ro" \
  "$HAPROXY_IMAGE" \
  haproxy -c -V -f /usr/local/etc/haproxy/haproxy.cfg
```

Expected: configuration is valid.

## Step 4 - Start HAProxy

```bash
docker compose up -d haproxy
docker compose ps haproxy
docker compose logs --since=5m --tail=100 haproxy
```

## Step 5 - Verify primary routing

Use a PostgreSQL client container on the application network or the PgBouncer image if it includes `psql`:

```bash
docker run --rm --network lorawan-lab_application "$POSTGRES_CLIENT_IMAGE" \
  psql 'host=haproxy port=5432 dbname=chirpstack user=chirpstack sslmode=disable' \
  -c 'SELECT inet_server_addr(), pg_is_in_recovery();'
```

Provide the password through a protected `.pgpass`, temporary environment variable, or interactive prompt. Do not put it directly in the command line.

Expected: `pg_is_in_recovery` is `false`.

## Step 6 - Verify HAProxy follows failover

Record the current leader, stop it, wait for Patroni promotion, then repeat the query through `haproxy:5432`.

The server address should change to the promoted member and `pg_is_in_recovery()` must still be `false`.

Restart the old member and verify the cluster returns to one leader plus two replicas.

## Troubleshooting

If HAProxy reports all backends down while Patroni is healthy, test `http://spilo-N:8008/primary` from the HAProxy network and verify the selected Patroni version's `/primary` endpoint semantics.

## Next step

Continue with [07-deploy-pgbouncer.md](07-deploy-pgbouncer.md).
