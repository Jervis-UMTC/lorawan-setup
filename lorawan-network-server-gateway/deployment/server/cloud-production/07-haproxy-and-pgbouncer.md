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

## 8.14 Phase 7 validation progress record

Current POC validation progress:

Completed:

- PgBouncer TLS listener validation on `ulc-01`.
- PgBouncer package, TLS, SCRAM, configuration, and runtime validation completed on `ulc-02`.
- SCRAM authentication validation for:
  - `chirpstack`.
  - `fabric_adapter`.
  - `telemetry_reader`.
  - `telemetry_writer`.
- Verified PgBouncer routes successful sessions through the PostgreSQL HAProxy primary endpoint.
- Verified returned backend state is the writable PostgreSQL leader (`pg_is_in_recovery() = false`).
- Verified backend TLS encryption from PgBouncer to PostgreSQL using TLS 1.3.
- Verified PgBouncer idle timeout behavior after the 75-second regression test without connection failure.
- Verified HAProxy 360-second PostgreSQL timeout ordering remains above PgBouncer `server_idle_timeout = 300s`.

Troubleshooting note:

- PgBouncer admin console access is separate from application database users.
- A failed `SHOW POOLS` login does not indicate PostgreSQL failure. It only means the PgBouncer admin identity is not configured or the supplied admin credential is invalid.
- When generating or checking PgBouncer administrative access, perform PostgreSQL role operations against the current Patroni leader only. Running `CREATE ROLE` on a replica will fail with `cannot execute CREATE ROLE in a read-only transaction`.

Next validation:

1. Configure or verify the PgBouncer admin/stats identities.
2. Run `SHOW POOLS`, `SHOW SERVERS`, and `SHOW STATS`.
3. Perform session reuse and failover connection validation before enabling PgBouncer at boot.

Latest ULC-02 commissioning evidence:

- PgBouncer service enabled for boot startup.
- PgBouncer active state verified after enabling.
- Private listener confirmed on `10.104.0.4:6432`.
- Client TLS certificate validation succeeded using the PgBouncer certificate identity.
- TLS negotiation verified with TLS 1.3 and `TLS_AES_256_GCM_SHA384`.
- Application database connectivity validated through PgBouncer for:
  - `chirpstack`.
  - `fabric_adapter`.
  - `telemetry_reader`.
  - `telemetry_writer`.
- PgBouncer backend TLS connections successfully established to PostgreSQL through local HAProxy.
- The observed `server conn crashed? (age=60s)` messages occurred during the idle timeout regression period and were followed by successful reconnections; the 75-second idle regression test completed successfully.

## 8.15 PgBouncer administration console validation

The PgBouncer admin console is not enabled by default. `admin_users` and `stats_users` must be explicitly configured before running `SHOW POOLS`, `SHOW SERVERS`, or `SHOW STATS`.

Application database users and PgBouncer administration users are separate identities.

Before enabling administrative access:

1. Decide the dedicated PgBouncer admin identity.
2. Configure `admin_users` and/or `stats_users` in `pgbouncer.ini`.
3. Reload PgBouncer.
4. Validate only the intended administrative commands.

Do not use PostgreSQL application users as a substitute for PgBouncer admin access.

## 8.16 Multi-node PgBouncer commissioning record

The production-style POC deployment uses one PgBouncer instance on each PostgreSQL HAProxy node.

Commissioning status:

| Node | Private IP | PgBouncer | TLS | SCRAM auth | Backend test |
|---|---|---|---|---|---|
| ulc-01 | 10.104.0.2 | commissioned | verified | verified | passed |
| ulc-02 | 10.104.0.4 | commissioned | verified | verified | passed |
| ulc-03 | 10.104.0.8 | foundation complete | pending | pending | pending |

For each node:

1. Install the pinned PgBouncer package.
2. Keep the service stopped until TLS, authentication, and configuration are installed.
3. Install the node certificate, private key, and CA bundle under `/etc/lorawan-pki/pgbouncer`.
4. Generate `/etc/pgbouncer/userlist.txt` from PostgreSQL SCRAM verifiers.

   Use a direct `docker compose exec spilo psql` extraction when generating the file. Avoid deeply nested shell quoting around SQL because it can silently produce an empty userlist. Validate that exactly four SCRAM entries exist before installation:
   - `chirpstack`
   - `fabric_adapter`
   - `telemetry_reader`
   - `telemetry_writer`

5. Install the local PgBouncer configuration using the node private IP for `listen_addr`.
6. Validate TLS before opening the listener.
7. Test application database login through `6432`.
8. Enable the service only after successful validation.

The ULC-03 foundation stage completed with:

- PgBouncer package installed: `1.22.0-1build4`.
- Service stopped and disabled before commissioning.
- No `:6432` listener exposed.
- Package/runtime identity verified.

The remaining ULC-03 commissioning follows the same validation sequence used by ULC-01 and ULC-02.

## 8.17 Final checks

- The private PostgreSQL HAProxy frontend and PgBouncer validate on all three hosts.
- Public ChirpStack/MQTT HAProxy routing remains only on `ha-01/02`, with public listeners bound to each host's anchor IP and reached through the single Reserved IPv4.
- Exactly one PostgreSQL primary is routed by every local `15432` frontend.
- Both `chirpstack` and `lorawan_telemetry` exist in PgBouncer.
- PgBouncer uses the intentionally small POC limits and shows no sustained client wait under the few-sensor workload.
- Patroni changes recover without editing ChirpStack, Node-RED, or Grafana database endpoints; when Fabric adapters are deployed, their endpoint remains unchanged too.

## 8.17 Phase 7 ULC-03 TLS deployment record

ULC-03 PgBouncer TLS material installation was validated before PgBouncer configuration.

Validation completed:

- Source certificate bundle located from the approved issuance directory.
- `/etc/lorawan-pki/pgbouncer` created with ownership `root:postgres`.
- CA certificate installed.
- PgBouncer server certificate installed.
- PgBouncer private key installed.
- TLS files protected with mode `640`.
- PostgreSQL service account access verified.
- Certificate chain verification passed.
- Certificate hostname verification passed for `pgbouncer.internal.lorawan.com`.
- Certificate public key and private key public key hashes matched.

## 8.18 Phase 7 ULC-03 PgBouncer SCRAM and configuration workflow

ULC-03 follows the same protected authentication workflow validated on ULC-01 and ULC-02.

Operational commands must be recorded with the deployment procedure because PgBouncer authentication depends on PostgreSQL SCRAM verifier extraction, not plaintext passwords.

SCRAM extraction workflow:

```bash
sudo docker compose \\
  -f /etc/lorawan-cloud/spilo/compose.yml \\
  exec -T spilo \\
  psql \\
    -X \\
    -U postgres \\
    -d postgres \\
    -A \\
    -t \\
    -v ON_ERROR_STOP=1 \\
    -c "
SELECT
  '\"' || rolname || '\" \"' || rolpassword || '\"'
FROM pg_authid
WHERE rolname IN (
'chirpstack',
'fabric_adapter',
'telemetry_reader',
'telemetry_writer'
)
AND rolcanlogin
AND rolpassword LIKE 'SCRAM-SHA-256\\$%'
ORDER BY rolname;
" |
sudo tee /run/pgbouncer-userlist.final >/dev/null
```

Install the generated verifier file:

```bash
sudo install \\
-m 640 \\
-o root \\
-g postgres \\
/run/pgbouncer-userlist.final \\
/etc/pgbouncer/userlist.txt
```

Install and verify the node-specific PgBouncer configuration:

```bash
sudo install \
-m 640 \
-o root \
-g postgres \
/tmp/pgbouncer-ulc03.ini \
/etc/pgbouncer/pgbouncer.ini

sudo grep -E \
'^(listen_addr|listen_port|pool_mode|max_client_conn|default_pool_size|max_db_connections|server_idle_timeout|server_tls_sslmode|server_tls_ca_file|client_tls_sslmode|client_tls_cert_file|client_tls_key_file|auth_type|auth_file)[[:space:]]*=' \
/etc/pgbouncer/pgbouncer.ini
```

Validation requirements:

- Exactly four SCRAM entries must exist.
- Entries must be `chirpstack`, `fabric_adapter`, `telemetry_reader`, and `telemetry_writer`.
- `/etc/pgbouncer/userlist.txt` must remain unreadable by `opsadmin`.
- PostgreSQL service account must be able to read the file.

The same installation boundary is used for ULC-01, ULC-02, and ULC-03 before enabling PgBouncer services.

## 8.19 Phase 7 ULC-03 pre-start validation record

ULC-03 PgBouncer configuration reached the pre-start validation boundary.

Validated:

- PgBouncer configuration installed with node-local listener:
  - `listen_addr = 10.104.0.8`
  - `listen_port = 6432`
- TLS material:
  - CA certificate readable by PostgreSQL service account.
  - Server certificate readable by PostgreSQL service account.
  - Private key readable by PostgreSQL service account.
  - Certificate chain verification passed.
- SCRAM authentication file:
  - `/etc/pgbouncer/userlist.txt` installed.
  - Four SCRAM verifier entries present.
  - File ownership and permissions validated.
- HAProxy PostgreSQL endpoints available:
  - `10.104.0.8:15432`
  - `10.104.0.8:15433`
- Local resolver mapping validated:
  - `postgres-ha.internal -> 10.104.0.8`

Next ULC-03 steps:

1. Start PgBouncer.
2. Confirm listener on `10.104.0.8:6432`.
3. Validate client TLS handshake using the PgBouncer certificate identity.
4. Test application database connections through PgBouncer.
5. Enable PgBouncer service after successful runtime validation.

## 8.20 Phase 7 Complete PgBouncer HA Commissioning Record

### Objective

Deploy PgBouncer on all PostgreSQL HA nodes as the stable client connection layer while keeping Patroni responsible for PostgreSQL leader election and HAProxy responsible for primary routing.

Final architecture:

```text
Application clients
        |
        v
PgBouncer :6432
        |
        v
HAProxy :15432
        |
        v
Patroni PostgreSQL primary
        |
        v
Current leader
```

PgBouncer does not replace Patroni or HAProxy. It provides connection pooling and TLS termination for database clients while HAProxy continues selecting the writable PostgreSQL leader.

---

# Phase 7 Execution Record

## Step 1 - PgBouncer package installation

Performed on:

- ULC-01
- ULC-02
- ULC-03

Validation:

```bash
pgbouncer --version
systemctl is-active pgbouncer
systemctl is-enabled pgbouncer
ss -H -lnt | grep ':6432'
```

Initial safety requirement:

```text
PgBouncer installed
PgBouncer stopped
PgBouncer disabled
No :6432 listener exposed
```

The service remained disabled until TLS, authentication, and configuration validation completed.

---

## Step 2 - TLS deployment

TLS materials were installed separately on each node:

```text
/etc/lorawan-pki/pgbouncer/
├── ca.crt
├── server.crt
└── server.key
```

Permissions:

```text
Directory:
750 root:postgres

Files:
640 root:postgres
```

Validation performed:

```bash
openssl verify \
-CAfile /etc/lorawan-pki/pgbouncer/ca.crt \
-verify_hostname pgbouncer.internal.lorawan.com \
/etc/lorawan-pki/pgbouncer/server.crt
```

Required result:

```text
server.crt: OK
```

Certificate and private key matching was verified by comparing public key hashes.

---

## Step 3 - SCRAM authentication installation

PgBouncer uses PostgreSQL SCRAM verifiers.

Plaintext database passwords are not stored by PgBouncer.

The userlist contains:

```text
chirpstack
fabric_adapter
telemetry_reader
telemetry_writer
```

Generated file:

```text
/etc/pgbouncer/userlist.txt
```

Permissions:

```text
640 root:postgres
```

Validation:

```bash
sudo wc -l /etc/pgbouncer/userlist.txt
```

Expected:

```text
4
```

Required access model:

```text
postgres user     -> read allowed
opsadmin user     -> read denied
```

---

## Step 4 - PgBouncer configuration

Each node uses its own private IP.

Configuration pattern:

```ini
listen_addr = <NODE_PRIVATE_IP>
listen_port = 6432

pool_mode = session

max_client_conn = 50
default_pool_size = 3
max_db_connections = 8

server_tls_sslmode = verify-full
server_tls_ca_file = /etc/lorawan-pki/pgbouncer/ca.crt

client_tls_sslmode = require
client_tls_cert_file = /etc/lorawan-pki/pgbouncer/server.crt
client_tls_key_file = /etc/lorawan-pki/pgbouncer/server.key

auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
```

Databases exposed:

```ini
chirpstack
lorawan_telemetry
```

---

## Step 5 - Runtime TLS validation

Every node passed:

```bash
openssl s_client \
-starttls postgres \
-connect <NODE_IP>:6432 \
-CAfile /etc/lorawan-pki/pgbouncer/ca.crt \
-verify_hostname pgbouncer.internal.lorawan.com
```

Verified:

```text
TLSv1.3
TLS_AES_256_GCM_SHA384
Certificate verification OK
```

---

## Step 6 - Application database validation

Validated users:

```text
chirpstack
fabric_adapter
telemetry_reader
telemetry_writer
```

Validation query:

```sql
SELECT
 current_user,
 inet_server_addr(),
 pg_is_in_recovery();
```

Expected:

```text
pg_is_in_recovery = false
```

Successful routing path:

```text
PgBouncer
   |
   v
HAProxy :15432
   |
   v
Patroni leader PostgreSQL
```

---

# Phase 7 Failover Validation

## Controlled Patroni switchover

Initial state:

```text
ulc-02
10.104.0.4
Leader
```

Switchover command:

```text
Primary: ulc-02
Candidate: ulc-01
Time: now
```

Result:

```text
ulc-01
10.104.0.2
Leader

ulc-02
10.104.0.4
Replica

ulc-03
10.104.0.8
Replica
```

Validation:

```bash
curl -s http://10.104.0.2:8008/
curl -s http://10.104.0.4:8008/
curl -s http://10.104.0.8:8008/
```

Confirmed:

```text
Exactly one primary exists.
Replication lag = 0.
```

---

# PgBouncer Failover Routing Test

After Patroni promotion:

Client connection through PgBouncer returned:

```text
current_user = chirpstack
inet_server_addr = 10.104.0.2
pg_is_in_recovery = false
```

Meaning:

```text
Application
   |
   v
PgBouncer
   |
   v
HAProxy
   |
   v
New Patroni leader
   |
   v
ulc-01 PostgreSQL
```

No application connection string changes were required.

No PgBouncer restart was required.

No PostgreSQL restart was required.

---

# Final Phase 7 State

| Node | IP | PgBouncer | TLS | SCRAM | HA Routing |
|---|---|---|---|---|---|
| ULC-01 | 10.104.0.2 | Active + Enabled | PASS | PASS | PASS |
| ULC-02 | 10.104.0.4 | Active + Enabled | PASS | PASS | PASS |
| ULC-03 | 10.104.0.8 | Active + Enabled | PASS | PASS | PASS |

Final verified capabilities:

- PgBouncer deployed on all PostgreSQL HA nodes.
- TLS encryption enabled between clients and PgBouncer.
- TLS encryption enabled between PgBouncer and PostgreSQL.
- SCRAM authentication enabled.
- HAProxy PostgreSQL routing preserved.
- Patroni leader changes handled successfully.
- Database clients continued operating after failover.

Phase 7 status:

```text
COMPLETE
```

Next: [09-mqtt-and-valkey.md](09-mqtt-and-valkey.md)
