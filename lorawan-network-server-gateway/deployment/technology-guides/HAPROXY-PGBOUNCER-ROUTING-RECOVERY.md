# HAProxy / PgBouncer — Commissioned Routing, Authentication and Recovery

**Scope:** actual three-ULC HA installation, expanding [operator guide 08](08-haproxy-pgbouncer.md). This chapter is not a change request to the live database or MQTT ingress. HAProxy and PgBouncer are *host systemd services*, not extra Patroni members. Each dependency/leader check below must be repeated with fresh live state before a planned change.

## 1. Keep the distinct routing layers separate

~~~text
ULC-01 ChirpStack / ULC-02 ChirpStack / ULC-03 Node-RED+Grafana
  -> pgbouncer.internal.lorawan.com:6432 (maps to THIS host VPC IP)
  -> host PgBouncer session pool (TLS/SCRAM)
  -> postgres-ha.internal:15432 (maps to THIS host HAProxy)
  -> HAProxy picks the current Patroni leader via REST :8008/primary
  -> PostgreSQL private :5432 TLS + role authentication
~~~

*Optional read-only replica/test traffic* uses separate HAProxy `:15433`, never primary writes. HAProxy also carries **different** private TLS-passthrough routes: Gateway public MQTT `:8883 -> cloud broker :8884` on approved ingress candidates, ChirpStack local `:18883 -> broker :8885`, Node-RED `:18884 -> broker :8886` and Fabric OpenBao private `:18200 -> :8200` where commissioned. Changing a single HAProxy frontend risks unrelated production services; validate the *whole* configuration.

## 2. Commissioned versions and local files

| Component | Dated commissioned artifact |
|---|---|
| HAProxy | Ubuntu package `2.8.16-0ubuntu0.24.04.3`, `/etc/haproxy/haproxy.cfg`, systemd `haproxy` |
| PgBouncer | Ubuntu `1.22.0-1build4`, `/etc/pgbouncer/pgbouncer.ini` and protected `/etc/pgbouncer/userlist.txt`, systemd `pgbouncer` |
| Client endpoint | `<THIS_VPC_IP>:6432`, SAN/hostname `pgbouncer.internal.lorawan.com` |
| Backend endpoint | `postgres-ha.internal:15432`, **node-local** HAProxy |
| Database TLS verification | PgBouncer `server_tls_sslmode=verify-full` + `/etc/lorawan-pki/pgbouncer/ca.crt`, PostgreSQL certificate verifies as `postgres-ha.internal` |
| Client auth | TLS with SCRAM-SHA-256, userlist hash parity and per-role privileges |
| Normal pool policy | `pool_mode=session`, small POC budget not an arbitrary performance optimum |

The original Phase 7 runbook describes an initial **four-role** SCRAM baseline; a later evidence expansion documented **ten entries including six evidence users**, consistent across three hosts at that dated checkpoint. The selected/current userlist is authoritative; do not delete “extra” roles because a historical table said four.

## 3. First inspection — no mutations

On **each Ubuntu host**, identify the route and elected database primary:

~~~bash
hostname -f
date -u
sudo systemctl is-active haproxy pgbouncer
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
sudo ss -lntp | grep -E ':(6432|15432|15433|18883|18884|18200)\b' || true
getent ahostsv4 postgres-ha.internal
getent ahostsv4 pgbouncer.internal.lorawan.com
sudo docker exec -e LC_ALL=C spilo patronictl -c /run/postgres.yml list
~~~

**PASS:** services and intended private listeners active; current Patroni leader exactly one; each logical local backend name maps to the current host's `10.104.0.x` and HAProxy's *bound* address. A hostname returning a different/loopback address must be investigated **in PgBouncer's actual resolver cache**, not assumed resolved by one shell's `getent`.

The documented 2026-08-25 two-node ChirpStack commissioning found PgBouncer's c-ares cache for `postgres-ha.internal` contained both `127.0.1.1` and `10.104.0.4` while its frontend was initially bound only on the private IP; a bad-address attempt consumed the 15-second `query_wait_timeout`. The reviewed repair made both currently resolvable addresses route to the same approved TCP frontend while keeping `verify-full` identity and private listener behavior, rather than hiding the problem by increasing pool sizes or changing the PostgreSQL major. Inspect current effective HAProxy and PgBouncer DNS cache before re-applying any historical fix.

## 4. Verify the actual SQL path

Through an *existing least-privilege* connection for `pgbouncer.internal.lorawan.com:6432`, not a printed secret:

~~~sql
SELECT now() AT TIME ZONE 'UTC' AS utc_time,
       inet_server_addr() AS backend,
       pg_is_in_recovery() AS is_replica;
~~~

**PASS:** TLS/auth succeeds and the primary-route query returns `is_replica=false`; a configured read-only replica route should return `true` when separately tested. Do not bypass PgBouncer as a permanent “repair” to make Node-RED work. If direct HAProxy SQL is fine but PgBouncer auth fails, investigate the pooler before changing PostgreSQL role passwords.

Use the approved PgBouncer *admin-console* identity over its local Unix socket or internal endpoint:

~~~sql
SHOW POOLS;
SHOW SERVERS;
SHOW STATS;
SHOW DNS_HOSTS;
~~~

**PASS:** no unexplained waiting clients, connected backend to the intended logical host, expected pool budgets and no stale erroneous DNS target. A host `psql` wrapper without an installed versioned PostgreSQL client may fail **before connecting**: use the already-approved version-compatible Spilo client/container through the authorized local socket, not a needless apt installation or a fake “PgBouncer down” verdict.

## 5. New host installation / one-host replacement

### 5.1 Preserve the dependency order

1. etcd/Patroni current leader and REST private `:8008` are healthy.
2. PostgreSQL certificates, HBA, role password verifiers and server hostname are correct. Do **not** copy raw superuser passwords into a script.
3. Install the **approved exact Ubuntu package versions**, not the latest candidate on every host as an undocumented upgrade.
4. Restore reviewed `/etc/haproxy/haproxy.cfg` and `/etc/pgbouncer/pgbouncer.ini` plus SCRAM userlist from protected backup. Reconcile this host's VPC binds; use the same role credential hash set across all three where commissioned.
5. Restore PgBouncer-specific readable CA/server cert/key bundle without weakening `/etc/lorawan-pki/postgres` permissions. Ensure key mode and unit service user can actually read it.
6. Verify *all* HAProxy frontends, not just SQL; only then admit the replacement host to the production workload/ingress route.

For a fresh isolated host only, the core PgBouncer properties are:

~~~ini
[databases]
chirpstack = host=postgres-ha.internal port=15432 dbname=chirpstack
lorawan_telemetry = host=postgres-ha.internal port=15432 dbname=lorawan_telemetry

[pgbouncer]
listen_addr = <THIS_HOST_PRIVATE_IP>
listen_port = 6432
unix_socket_dir = /run/postgresql
pool_mode = session
max_client_conn = 50
default_pool_size = 3
reserve_pool_size = 1
reserve_pool_timeout = 5
max_db_connections = 8
query_wait_timeout = 15
server_tls_sslmode = verify-full
server_tls_ca_file = /etc/lorawan-pki/pgbouncer/ca.crt
client_tls_sslmode = require
client_tls_cert_file = /etc/lorawan-pki/pgbouncer/server.crt
client_tls_key_file = /etc/lorawan-pki/pgbouncer/server.key
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
~~~

**Template only**: replace the VPC placeholder, restore and verify the complete approved current pool/timeout/logging/admin/TLS settings before writing. A basic `client_tls_sslmode=require` means PgBouncer requires TLS transport, **not client certificate** unless separately configured; database password authentication is SCRAM. Do not call all PgBouncer paths “mTLS”.

The current small-session-pool model may use 3 default + 1 reserve connections and 8 maximum per database per host. It is not proof that arbitrarily many sensor uplinks can be processed concurrently. Measure real pool pressure and application demand before changing budgets; do not switch to transaction pooling without verifying ChirpStack session/prepared-statement compatibility.

### 5.2 Validate and reload only the component changed

After backing up the exact HAProxy file to protected rollback storage:

~~~bash
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sudo systemctl is-active haproxy
sudo ss -lntp | grep -E ':(6432|15432|18883|18884)\b' || true
~~~

Run the reload **only** when the preceding syntax check succeeds and a HAProxy edit actually requires one. If PgBouncer changes, inspect whether the setting is reloadable; e.g. `resolv_conf` in the documented c-ares case reported `changeable=no` and required a planned single-service restart, not `SET`/reload. Back up `pgbouncer.ini` and protected userlist, apply to one host, inspect console pools/DNS and one SQL primary-route operation, then roll onward. Do **not** restart both cloud public-ingress candidates together.

## 6. Rotation, TLS and least privilege

To rotate a role: inventory its SQL privileges and current PgBouncer SCRAM verifier, create approved new verifier/role under a controlled primary transaction, stage compatible hash/ACL across the necessary PgBouncer hosts, validate one client at a time, then revoke the old credential only after active consumers reconnect. Database-only password rotation before updating the pool can strand every app; broadening roles to superuser “temporarily” breaks evidence boundaries. The Node-RED telemetry writer must not be a gateway verifier or Fabric worker. Grafana must not gain writer permission.

For both interfaces, a TLS peer certificate must verify against the *actual service name* used by its client. `postgres-ha.internal` and `pgbouncer.internal.lorawan.com` are separate SAN roles. Access through a raw VPC IP should not silently bypass verification. ChirpStack 4.19.1's *core PostgreSQL DSN* uses `sslmode=require` plus a separate CA field, whereas PgBouncer's upstream server TLS uses `verify-full`; do not mass-replace one with the other.

## 7. Repair the first failing layer

| Symptom | First check |
|---|---|
| no primary Patroni | etcd quorum and database leader; router cannot create a leader |
| `:15432` closed | host HAProxy service/bind/firewall, before database credentials |
| direct `:15432` SQL works but `:6432` fails | PgBouncer userlist, TLS, per-database pool/admin state |
| PgBouncer has bad backend address | `SHOW DNS_HOSTS`, systemd-resolved, bind addresses, hostname TLS contract |
| client reaches replica via write route | HAProxy Patroni `/primary` health selection |
| only one app fails | app's URI/role/pool vs systemic backend health |
| no MQTT while SQL works | different HAProxy frontend and Mosquitto backend, not PgBouncer |
| certificate hostname failure | correct SAN/CA and intended client name, never sslmode disable |

**Recovery PASS:** exactly one Patroni leader, both major app nodes' client SQL through their *own* `:6432` routes returns writable primary, workload identities retain least privilege, other frontends healthy, one real database write succeeds through the application transaction. Controlled HA failover is needed after material failover changes, not on every documentation edit.

## 8. What backup and Word document must contain

Preserve actual HAProxy config/frontends/backend lists, PgBouncer ini and protected SCRAM credential recovery process, TLS chain/service cert identity, normal routing/hostname mappings, software versions, systemd overrides, local/private/public firewall map, current elected backend evidence, reload/rollback commands and a sanitized example SQL result. Publish none of the private key/userlist contents.

Source runbook: [PgBouncer/HAProxy commissioning](../server/cloud-production/07-haproxy-and-pgbouncer.md). This chapter will be included **in full** in the standalone Word document; source-reference links do not substitute for operative instructions.
