# HAProxy / PgBouncer — Operator Manual

## What these technologies do

HAProxy gives clients stable endpoints while backend roles change. PgBouncer pools PostgreSQL client connections and enforces the commissioned database authentication/TLS boundary.

For database traffic, the current path is:

```text
client
-> PgBouncer :6432
-> HAProxy PostgreSQL-primary route :15432
-> current Patroni leader :5432
```

The same HAProxy installations also serve other approved private/public routes. Do not edit one frontend without validating the whole HAProxy configuration.

## Current database listeners

- PgBouncer client endpoint: `:6432` on each ULC host.
- HAProxy writable-primary route: `:15432`.
- HAProxy replica/test route: `:15433` where documented.
- Backend PostgreSQL members: private `:5432`.

## Step 1 — Prove Patroni first

Before blaming the routers, establish one database leader:

```bash
sudo docker exec -e LC_ALL=C spilo patronictl -c /run/postgres.yml list
```

If Patroni has no safe leader, stop. Fix etcd/Patroni before changing HAProxy/PgBouncer.

## Step 2 — Check service state

```bash
sudo systemctl status haproxy --no-pager -l
sudo systemctl status pgbouncer --no-pager -l
```

A running service is not enough. Continue to listeners and real SQL.

## Step 3 — Validate HAProxy configuration before reload/restart

```bash
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
```

**PASS means:** configuration validates with no fatal error.

Never reload an invalid HAProxy config. Always run this command after editing and before `systemctl reload haproxy`.

## Step 4 — Check database-routing listeners

```bash
sudo ss -lntp | grep -E ':(5432|6432|15432|15433)\b' || true
```

Check that intended listeners are on the expected private/local address, not unexpectedly on `0.0.0.0`/public interfaces.

## Step 5 — Inspect PgBouncer health through its admin interface

Using the protected PgBouncer admin/stats connection already provisioned for this host, run:

```sql
SHOW POOLS;
SHOW SERVERS;
SHOW STATS;
```

Look for:

- excessive waiting clients;
- no available server connections;
- repeated auth failures;
- server target inconsistent with the current primary route.

Do not copy passwords from `/etc/pgbouncer/userlist.txt` into documentation or chat.

## Step 6 — Prove a real SQL connection through the normal path

Using a protected least-privilege DSN for `pgbouncer.internal.lorawan.com:6432`, run:

```sql
SELECT inet_server_addr(), pg_is_in_recovery();
```

**PASS means:** TLS/auth succeeds and a primary-route client returns `pg_is_in_recovery() = false`.

If PgBouncer accepts the client but the SQL backend fails, inspect HAProxy backend/Patroni/TLS. If direct HAProxy works but PgBouncer fails, inspect PgBouncer auth/pool/client TLS.

## Step 7 — Use layer-by-layer isolation

Test in this order:

```text
client -> :6432 listener
client auth/TLS -> PgBouncer
PgBouncer -> :15432
HAProxy -> Patroni primary backend
PostgreSQL TLS/HBA/role
SQL operation
```

Do not change PostgreSQL passwords because HAProxy has no healthy backend, and do not change HAProxy because a client supplied the wrong PgBouncer credential.

## Safe HAProxy change procedure

1. copy `/etc/haproxy/haproxy.cfg` to a protected rollback file;
2. edit only the intended frontend/backend;
3. run `haproxy -c -V -f /etc/haproxy/haproxy.cfg`;
4. if validation fails, do not reload;
5. reload rather than restart when a reload is sufficient;
6. confirm listeners;
7. confirm backend-specific health;
8. run one real client operation.

Command after a successful validation:

```bash
sudo systemctl reload haproxy
sudo systemctl is-active haproxy
```

## Safe PgBouncer change procedure

1. prove Patroni/HAProxy path works first;
2. back up `pgbouncer.ini` and the protected userlist/auth source;
3. change only the intended database/role/pool/TLS item;
4. validate permissions and certificate paths;
5. reload/restart according to the setting changed;
6. run `SHOW POOLS`, `SHOW SERVERS`, and one real SQL query;
7. verify application reconnect behavior.

Do not broaden a database role because one client was configured with the wrong credentials.

## PostgreSQL role-auth synchronization rule

PgBouncer's commissioned SCRAM userlist must match the approved PostgreSQL application/evidence roles. When adding/rotating a role, follow the database/PgBouncer rotation procedure and prove the new role can do only its intended operations.

Do not copy the whole password/userlist file to another environment as a shortcut.

## Troubleshooting map

| Symptom | Likely layer |
|---|---|
| `connection refused` on 6432 | PgBouncer service/listener |
| client TLS hostname error | PgBouncer certificate/SAN/client hostname |
| authentication failed at 6432 | PgBouncer userlist/role/credential |
| PgBouncer has no server | HAProxy route/backend or upstream TLS |
| HAProxy primary route unhealthy | Patroni leader/REST/backend reachability |
| SQL reaches replica on primary route | HAProxy Patroni health selection defect |
| only one app fails | that app's role/DSN/pool, not necessarily cluster |

## Recovery rules

Do not bypass PgBouncer/HAProxy permanently during an incident. Direct-member connections are diagnostic/admin tools; restore the stable client path before declaring recovery complete.

After a PostgreSQL leader change, applications should reconnect without DSN edits. If manual endpoint edits are required, the HA routing layer is not working as intended.

## Completion checklist

- Patroni has one leader;
- HAProxy config validates;
- HAProxy and PgBouncer active;
- expected listeners present/private;
- PgBouncer pools/servers sane;
- a real SQL query through `:6432` reaches a writable primary;
- app roles authenticate with least privilege;
- no application is pinned to a current member IP.

## Complete routing and credential-recovery companion

Use [HAProxy/PgBouncer commissioned routing, TLS/SCRAM, DNS and rollback](HAPROXY-PGBOUNCER-ROUTING-RECOVERY.md). The documented PgBouncer cache/loopback incident and the differences between ChirpStack core DSN and PgBouncer upstream verify-full TLS are essential for a safe repair.

## Detailed runbook

- [`../server/cloud-production/07-haproxy-and-pgbouncer.md`](../server/cloud-production/07-haproxy-and-pgbouncer.md)