# 8. PgBouncer and HAProxy Core Service Routing

## 8.1 Purpose

The tiny HA POC runs PgBouncer and the private PostgreSQL HAProxy frontend on **all three hosts**. `ha-01` and `ha-02` also carry the public ChirpStack/MQTT routing roles behind the movable Reserved IPv4. `ha-03` additionally carries the private MQTT `:18883` route used by Node-RED; it is never a Reserved-IP public-ingress candidate.

```text
local database client
    -> pgbouncer.internal.<DOMAIN>:6432
    -> PgBouncer on this host
    -> postgres-ha.internal.<DOMAIN>:15432
    -> HAProxy on this host
    -> current Patroni primary on private TCP/5432

Clients include:
  ha-01 ChirpStack-1 + Fabric adapter-1
  ha-02 ChirpStack-2 + Fabric adapter-2
  ha-03 Node-RED + Grafana
```

`6432` is the stable local pool endpoint. `15432` is the local HAProxy PostgreSQL-primary endpoint and avoids colliding with PostgreSQL `5432` on the same Droplet. Map the logical service names to the current host's private VPC IP for each local client/container.

This gives every database client the same failover shape without another database router. `ha-03` is not a public Reserved-IP candidate; its HAProxy instance is reused only for private database routing and, in Section 9, the private Node-RED MQTT route.

HAProxy on `ha-01` and `ha-02` also provides the stable private OpenBao KMS route used by the two Fabric adapter workers:

```text
Fabric adapter on this app host
    -> openbao-kms.internal.<DOMAIN>:18200
    -> HAProxy on this app host
    -> one initialized, unsealed OpenBao-1/2/3 API backend on private TCP/8200
```

The KMS frontend stays in TCP mode so application TLS remains end-to-end to OpenBao. OpenBao Integrated Storage handles active/standby behavior and request forwarding inside the three-member cluster; HAProxy's job is only to keep one stable client endpoint and avoid routing to an unusable backend.

## 8.2 Preconditions

- Patroni cluster has one primary and healthy replicas.
- Patroni REST endpoints are reachable from all three hosts on private port 8008.
- PostgreSQL TLS certificates and CA are installed.
- HAProxy and PgBouncer versions are pinned and supported.
- ChirpStack database role exists.
- Maximum PostgreSQL connections and application concurrency are approved.
- Before enabling the KMS frontend, OpenBao-1/2/3 exist as one initialized Integrated Storage/Raft cluster, all intended usable members are unsealed, and their API certificates validate the approved private KMS identity.

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
    bind <THIS_HOST_PRIVATE_IP>:15432
    default_backend patroni_primary

backend patroni_primary
    option httpchk GET /primary
    http-check expect status 200
    default-server inter 2s fall 3 rise 2 on-marked-down shutdown-sessions
    server ha-01 <HA01_PRIVATE_IP>:5432 check port 8008
    server ha-02 <HA02_PRIVATE_IP>:5432 check port 8008
    server ha-03 <HA03_PRIVATE_IP>:5432 check port 8008

frontend postgres_replicas
    bind <THIS_HOST_PRIVATE_IP>:15433
    default_backend patroni_replicas

backend patroni_replicas
    balance roundrobin
    option httpchk GET /replica?lag=<APPROVED_MAX_REPLICA_LAG>
    http-check expect status 200
    default-server inter 3s fall 3 rise 2
    server ha-01 <HA01_PRIVATE_IP>:5432 check port 8008
    server ha-02 <HA02_PRIVATE_IP>:5432 check port 8008
    server ha-03 <HA03_PRIVATE_IP>:5432 check port 8008
```

Patroni `/primary` returns HTTP 200 only for the member that is primary and owns the leader lock. Replica checks can include a maximum lag. Verify endpoint semantics against the pinned Patroni version.

If Patroni REST uses TLS or authentication, configure HAProxy accordingly; do not disable REST protection to simplify health checks.

### OpenBao KMS frontend

Add a private TCP frontend on each adapter host:

```haproxy
frontend openbao_kms
    mode tcp
    bind <THIS_HOST_PRIVATE_IP>:18200
    default_backend openbao_nodes

backend openbao_nodes
    mode tcp
    balance roundrobin
    option httpchk GET /v1/sys/health?standbyok=true
    http-check expect status 200
    default-server inter 2s fall 3 rise 2

    # Client traffic remains raw TLS pass-through because the server lines do
    # not enable `ssl` for normal proxied traffic. `check-ssl` encrypts only
    # the HAProxy health check.
    server openbao-1 <HA01_PRIVATE_IP>:8200 check check-ssl verify required ca-file /etc/lorawan-pki/openbao/ca.crt check-sni openbao-kms.internal.<DOMAIN>
    server openbao-2 <HA02_PRIVATE_IP>:8200 check check-ssl verify required ca-file /etc/lorawan-pki/openbao/ca.crt check-sni openbao-kms.internal.<DOMAIN>
    server openbao-3 <HA03_PRIVATE_IP>:8200 check check-ssl verify required ca-file /etc/lorawan-pki/openbao/ca.crt check-sni openbao-kms.internal.<DOMAIN>
```

Validate that the pinned HAProxy version supports the shown `check-ssl` and `check-sni` syntax before reload. If it differs, adapt only the syntax, not the behavior: the health check must use HTTPS, verify the OpenBao CA/name, call `/v1/sys/health?standbyok=true`, and accept only an initialized/unsealed usable backend.

Do **not** accept plain TCP-connect-only health as the final KMS test. OpenBao's health endpoint can distinguish initialized/unsealed active or standby nodes from sealed/uninitialized nodes.

Why standby is valid here: an unsealed OpenBao HA standby can forward requests to the active node. A sealed node is not usable redundancy and must not be considered a healthy adapter backend.

## 8.5 Validate HAProxy before reload

```bash
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sudo systemctl status haproxy --no-pager -l
sudo ss -lntp | grep -E ':(15432|15433|18200|18883)\b'
```

The PostgreSQL HAProxy listeners bind only to each host's private interface. The OpenBao KMS listener exists only on `ha-01/02`, also private. Section 9 adds private MQTT `:18883` on all three hosts. None of these private listeners is exposed directly to the Internet.

Check each Patroni endpoint directly from the current host:

```bash
for host in <DB_01_PRIVATE_IP> <DB_02_PRIVATE_IP> <DB_03_PRIVATE_IP>; do
  printf '%s ' "$host"
  curl -sS -o /dev/null -w '%{http_code}\n' "http://$host:8008/primary"
done
```

Exactly one should return `200`. Adapt for HTTPS and client certificates when enabled.

## 8.6 PostgreSQL routing test

```bash
psql 'host=postgres-ha.internal.<DOMAIN> hostaddr=<THIS_HOST_PRIVATE_IP> port=15432 dbname=postgres user=<MONITOR_ROLE> sslmode=verify-full' \
  -c "SELECT inet_server_addr(), pg_is_in_recovery();"
```

Expected: `pg_is_in_recovery = false`.

For the replica frontend:

```bash
psql 'host=postgres-ha.internal.<DOMAIN> hostaddr=<THIS_HOST_PRIVATE_IP> port=15433 dbname=postgres user=<MONITOR_ROLE> sslmode=verify-full' \
  -c "SELECT inet_server_addr(), pg_is_in_recovery();"
```

Expected: `true`. Do not send ChirpStack writes to the replica endpoint.

## 8.7 PgBouncer baseline

Create `/etc/pgbouncer/pgbouncer.ini` and protect the authentication material.

```ini
[databases]
chirpstack = host=postgres-ha.internal.<DOMAIN> port=15432 dbname=chirpstack
lorawan_telemetry = host=postgres-ha.internal.<DOMAIN> port=15432 dbname=lorawan_telemetry

[pgbouncer]
listen_addr = <THIS_HOST_PRIVATE_IP>
listen_port = 6432
unix_socket_dir = /run/postgresql

pool_mode = session

# Tiny POC starting limits. These are intentionally small because PostgreSQL
# itself starts with max_connections=40 and only a few sensors are active.
max_client_conn = 50
default_pool_size = 3
min_pool_size = 0
reserve_pool_size = 1
reserve_pool_timeout = 5
max_db_connections = 8

server_connect_timeout = 5
server_login_retry = 5
server_lifetime = 3600
server_idle_timeout = 300
server_fast_close = 1
client_login_timeout = 30
query_wait_timeout = 15

server_tls_sslmode = verify-full
server_tls_ca_file = /etc/lorawan-pki/postgres/ca.crt

client_tls_sslmode = require
client_tls_cert_file = /etc/lorawan-pki/pgbouncer/server.crt
client_tls_key_file = /etc/lorawan-pki/pgbouncer/server.key

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

## 8.9 POC pool sizing

Do not size PgBouncer for the future fleet yet. The POC starts with `default_pool_size=3`, `reserve_pool_size=1`, and `max_db_connections=8` on each host while PostgreSQL starts at `max_connections=40`.

Why so small: a few sensors do not need dozens of simultaneous database server sessions. PgBouncer is present to prove the future connection-pooling boundary, not to generate artificial connection load.

Watch `SHOW POOLS` during failover. If clients wait under the actual POC workload, increase the pool gradually and record the reason. Do not raise PostgreSQL and PgBouncer limits preemptively.

## 8.10 Start and validate PgBouncer

```bash
sudo pgbouncer -t /etc/pgbouncer/pgbouncer.ini 2>/dev/null || true
sudo systemctl restart pgbouncer
sudo systemctl status pgbouncer --no-pager -l
sudo ss -lntp | grep ':6432'
```

Use the validation option supported by the installed version; inspect `pgbouncer --help` first.

Test both logical databases through the local pool:

Use the shared certificate name for hostname verification while forcing the connection to this host's private IP:

```bash
psql 'host=pgbouncer.internal.<DOMAIN> hostaddr=<THIS_HOST_PRIVATE_IP> port=6432 dbname=chirpstack user=chirpstack sslmode=verify-full sslrootcert=/etc/lorawan-pki/pgbouncer/ca.crt' \
  -c "SELECT current_database(), inet_server_addr(), pg_is_in_recovery();"

psql 'host=pgbouncer.internal.<DOMAIN> hostaddr=<THIS_HOST_PRIVATE_IP> port=6432 dbname=lorawan_telemetry user=telemetry_reader sslmode=verify-full sslrootcert=/etc/lorawan-pki/pgbouncer/ca.crt' \
  -c "SELECT current_database(), inet_server_addr(), pg_is_in_recovery();"
```

Run the tests appropriate to each host: ChirpStack on `ha-01/02`; telemetry clients on `ha-03`; adapter outbox access on `ha-01/02`. PgBouncer stays on the host's restricted private interface. Its server connection through HAProxy to PostgreSQL must use verified TLS.

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

1. confirm PgBouncer is healthy on all three hosts;
2. observe `SHOW POOLS`;
3. perform Patroni switchover;
4. allow each local HAProxy to select the new primary;
5. issue `RECONNECT chirpstack;` or `RECONNECT lorawan_telemetry;` only if old server connections remain;
6. verify a ChirpStack DB query, one Node-RED telemetry insert, and one Grafana read through the unchanged endpoints;
7. when the reviewed Fabric adapter is deployed, also verify one adapter outbox query; otherwise verify the outbox directly and record adapter execution as BLOCKED.

## 8.13 Failover validation

During a staging primary failure:

- HAProxy must mark the old primary down;
- one replica must be promoted by Patroni;
- HAProxy must route new connections only to the promoted primary;
- ChirpStack must reconnect through HAProxy; if PgBouncer is enabled, it must discard or replace broken server connections;
- ChirpStack must retry and recover without manual DSN changes;
- the test transaction sequence must match the selected RPO mode.

## 8.14 Final checks

- The private PostgreSQL HAProxy frontend and PgBouncer validate on all three hosts.
- Public ChirpStack/MQTT HAProxy routing remains only on `ha-01/02`, with public listeners bound to each host's anchor IP and reached through the single Reserved IPv4.
- Exactly one PostgreSQL primary is routed by every local `15432` frontend.
- Both `chirpstack` and `lorawan_telemetry` exist in PgBouncer.
- PgBouncer uses the intentionally small POC limits and shows no sustained client wait under the few-sensor workload.
- Patroni changes recover without editing ChirpStack, Node-RED, or Grafana database endpoints; when Fabric adapters are deployed, their endpoint remains unchanged too.

Next: [09-mqtt-and-valkey.md](09-mqtt-and-valkey.md)
