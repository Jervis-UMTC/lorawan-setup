# 8. HAProxy and PgBouncer on the Application Nodes

## 8.1 Purpose

Each ChirpStack node runs its own HAProxy and PgBouncer:

```text
ChirpStack -> PgBouncer 127.0.0.1:6432
PgBouncer -> HAProxy 127.0.0.1:5432
HAProxy -> current Patroni primary on private TCP/5432
```

This design avoids a shared database-router virtual IP. The public load balancer removes a failed application node, while the surviving node keeps an independent database connection path.

## 8.2 Preconditions

- Patroni cluster has one primary and healthy replicas.
- Patroni REST endpoints are reachable from both app nodes on private port 8008.
- PostgreSQL TLS certificates and CA are installed.
- PgBouncer and HAProxy versions are pinned and supported.
- ChirpStack database role exists.
- Maximum PostgreSQL connections and application concurrency are approved.

## 8.3 Install and inspect

```bash
haproxy -vv
pgbouncer --version
systemctl cat haproxy
systemctl cat pgbouncer
```

Use supported distribution packages or pinned artifacts that match the operating-system release. Keep the observed HAProxy and PgBouncer versions with the package source and previous package reference because configuration directives and rollback behavior can differ between releases.

## 8.4 HAProxy configuration

Back up `/etc/haproxy/haproxy.cfg`, then configure private database frontends. Replace IPs and certificate behavior with the approved design.

```haproxy
global
    log /dev/log local0
    log /dev/log local1 notice
    user haproxy
    group haproxy
    daemon
    maxconn <HAPROXY_MAX_CONNECTIONS>

    ssl-default-bind-options ssl-min-ver TLSv1.2
    ssl-default-server-options ssl-min-ver TLSv1.2

defaults
    log global
    mode tcp
    option tcplog
    timeout connect 5s
    timeout client 60s
    timeout server 60s
    timeout check 5s

frontend postgres_primary
    bind 127.0.0.1:5432
    default_backend patroni_primary

backend patroni_primary
    option httpchk GET /primary
    http-check expect status 200
    default-server inter 2s fall 3 rise 2 on-marked-down shutdown-sessions
    server db-01 <DB_01_PRIVATE_IP>:5432 check port 8008
    server db-02 <DB_02_PRIVATE_IP>:5432 check port 8008
    server db-03 <DB_03_PRIVATE_IP>:5432 check port 8008

frontend postgres_replicas
    bind 127.0.0.1:5433
    default_backend patroni_replicas

backend patroni_replicas
    balance roundrobin
    option httpchk GET /replica?lag=<APPROVED_MAX_REPLICA_LAG>
    http-check expect status 200
    default-server inter 3s fall 3 rise 2
    server db-01 <DB_01_PRIVATE_IP>:5432 check port 8008
    server db-02 <DB_02_PRIVATE_IP>:5432 check port 8008
    server db-03 <DB_03_PRIVATE_IP>:5432 check port 8008
```

Patroni `/primary` returns HTTP 200 only for the member that is primary and owns the leader lock. Replica checks can include a maximum lag. Verify endpoint semantics against the pinned Patroni version.

If Patroni REST uses TLS or authentication, configure HAProxy accordingly; do not disable REST protection to simplify health checks.

## 8.5 Validate HAProxy before reload

```bash
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sudo systemctl status haproxy --no-pager -l
sudo ss -lntp | grep -E ':(5432|5433)\b'
```

Both listeners should be loopback-only.

Check each Patroni endpoint directly from the app node:

```bash
for host in <DB_01_PRIVATE_IP> <DB_02_PRIVATE_IP> <DB_03_PRIVATE_IP>; do
  printf '%s ' "$host"
  curl -sS -o /dev/null -w '%{http_code}\n' "http://$host:8008/primary"
done
```

Exactly one should return `200`. Adapt for HTTPS and client certificates when enabled.

## 8.6 PostgreSQL routing test

```bash
psql 'host=127.0.0.1 port=5432 dbname=postgres user=<MONITOR_ROLE> sslmode=require' \
  -c "SELECT inet_server_addr(), pg_is_in_recovery();"
```

Expected: `pg_is_in_recovery = false`.

For the replica frontend:

```bash
psql 'host=127.0.0.1 port=5433 dbname=postgres user=<MONITOR_ROLE> sslmode=require' \
  -c "SELECT inet_server_addr(), pg_is_in_recovery();"
```

Expected: `true`. Do not send ChirpStack writes to the replica endpoint.

## 8.7 PgBouncer baseline

Create `/etc/pgbouncer/pgbouncer.ini` and protect the authentication material.

```ini
[databases]
chirpstack = host=127.0.0.1 port=5432 dbname=chirpstack

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
unix_socket_dir = /run/postgresql

pool_mode = session
max_client_conn = <APPROVED_MAX_CLIENT_CONNECTIONS>
default_pool_size = <APPROVED_POOL_SIZE>
min_pool_size = <APPROVED_MIN_POOL_SIZE>
reserve_pool_size = <APPROVED_RESERVE_POOL_SIZE>
reserve_pool_timeout = 5
max_db_connections = <APPROVED_DB_CONNECTION_CAP>

server_connect_timeout = 5
server_login_retry = 5
server_lifetime = 3600
server_idle_timeout = 600
server_fast_close = 1
client_login_timeout = 30
query_wait_timeout = <APPROVED_QUEUE_TIMEOUT>

server_tls_sslmode = verify-full
server_tls_ca_file = /etc/lorawan-pki/postgres/ca.crt

auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt

admin_users = <PGBOUNCER_ADMIN_ROLE>
stats_users = <PGBOUNCER_STATS_ROLE>

log_connections = 1
log_disconnections = 1
log_pooler_errors = 1
stats_period = 60
```

Start with session pooling because it preserves connection-level behavior. Transaction pooling can reduce server connections further but may break applications that rely on session state, temporary tables, advisory locks, certain prepared-statement behavior, or `SET` persistence. Enable it only after ChirpStack version-specific staging tests.

## 8.8 Authentication choices

### Option A: protected auth file

Use SCRAM verifier strings, not plaintext passwords. Keep `/etc/pgbouncer/userlist.txt` mode `640` or stricter and owned by the PgBouncer service group.

Rotation sequence:

1. change PostgreSQL role secret in a controlled window;
2. update the PgBouncer verifier atomically;
3. run `RELOAD`;
4. reconnect affected pools;
5. verify application recovery;
6. remove old secret from the approved store.

### Option B: `auth_query`

Use a dedicated non-login or tightly restricted authentication role and a reviewed `SECURITY DEFINER` function owned by a trusted administrator. The function must have a fixed `search_path`, expose only username and password verifier, and grant execution only to the PgBouncer auth role.

Do not grant the PgBouncer process general access to `pg_shadow`, superuser, or application tables.

## 8.9 Pool sizing

The total possible server connections across both app nodes must fit below PostgreSQL `max_connections` after reserving capacity for:

- Patroni and replication;
- administration and emergency access;
- migrations;
- monitoring and backups;
- other databases or roles;
- connection spikes during failover.

Example calculation:

```text
PostgreSQL max_connections
- replication and Patroni reserve
- admin/migration reserve
- monitoring/backup reserve
= application connection budget

application budget / 2 application nodes
= maximum PgBouncer server connections per node
```

Do not set `max_client_conn` without raising and validating OS file-descriptor limits. PgBouncer may require more file descriptors than the client limit because it also holds server connections.

## 8.10 Start and validate PgBouncer

```bash
sudo pgbouncer -t /etc/pgbouncer/pgbouncer.ini 2>/dev/null || true
sudo systemctl restart pgbouncer
sudo systemctl status pgbouncer --no-pager -l
sudo ss -lntp | grep ':6432'
```

Use the validation option supported by the installed version; inspect `pgbouncer --help` first.

Application test:

```bash
psql 'host=127.0.0.1 port=6432 dbname=chirpstack user=chirpstack sslmode=disable' \
  -c "SELECT current_database(), inet_server_addr(), pg_is_in_recovery();"
```

The local PgBouncer hop is loopback; PostgreSQL TLS is enforced on PgBouncer's server connection.

## 8.11 Administration and metrics

Connect to the virtual `pgbouncer` database with the stats/admin role:

```sql
SHOW VERSION;
SHOW CONFIG;
SHOW DATABASES;
SHOW POOLS;
SHOW CLIENTS;
SHOW SERVERS;
SHOW STATS;
```

Alert when:

- `cl_waiting` remains above zero;
- `maxwait` increases;
- server login failures occur;
- pools approach `max_db_connections`;
- frequent server disconnects follow database failover;
- file descriptors or memory approach limits.

## 8.12 Planned database maintenance

For a controlled Patroni switchover:

1. confirm both app-node pools are healthy;
2. observe `SHOW POOLS`;
3. perform Patroni switchover;
4. allow HAProxy to select the new primary;
5. issue `RECONNECT chirpstack;` if old server connections remain;
6. use `WAIT_CLOSE chirpstack;` where supported;
7. verify fresh writes from both ChirpStack nodes.

`PAUSE` and `RESUME` can drain connections for planned database restarts, but pausing both app nodes makes the service unavailable. Coordinate one application node at a time.

## 8.13 Failover validation

During a staging primary failure:

- HAProxy must mark the old primary down;
- one replica must be promoted by Patroni;
- HAProxy must route new connections only to the promoted primary;
- PgBouncer must discard or replace broken server connections;
- ChirpStack must retry and recover without manual DSN changes;
- the test transaction sequence must match the selected RPO mode.

## 8.14 Final checks

- HAProxy configuration validates on both app nodes.
- Exactly one primary is routed on local 5432.
- Replica endpoint rejects primary and excessive-lag replicas as designed.
- PgBouncer listens only on loopback and authenticates with SCRAM.
- Connection budgets fit PostgreSQL with reserves.
- Planned and unplanned Patroni changes recover without editing ChirpStack DSNs.

Next: [09-mqtt-and-valkey.md](09-mqtt-and-valkey.md)
