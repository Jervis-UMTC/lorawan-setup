# 14. Failover, Fault-Injection, and Acceptance Testing

## 14.1 Goal

Prove the system's response to failures before production and after material changes. Tests must measure impact, recovery, data integrity, and operator visibility rather than only showing that a replacement process started.

Perform destructive or disruptive tests in staging first. Before each test, identify the exact failure being injected, the staging gateway/device/event used for measurement, expected behavior and RTO/RPO, current backup and restore result, monitoring queries, rollback action, and measurable abort condition. Capture the start and recovery times because they are needed to compare the observed outage with the objective.

Use sanitized test data and a reserved staging gateway/device. Never use emergency, life-safety, or critical actuator traffic.

## 14.2 Baseline evidence

Immediately before testing, capture:

- gateway last-seen and one successful uplink/downlink;
- MQTT synthetic result and active connection;
- both ChirpStack node readiness states;
- PgBouncer `SHOW POOLS` and HAProxy backend state;
- `patronictl list` and replication lag;
- etcd endpoint health/status/member list;
- Valkey health, memory, and connection state;
- most recent WAL/base/logical backup and etcd snapshot;
- load-balancer backends;
- system time and active image/package versions.

**Stop here. Do not inject a failure** if the baseline is already degraded or the backup/rollback path is unavailable.

## 14.3 Application-node failure

### Action

Remove or stop `app-01` while `app-02` remains healthy.

### Expected

- application load balancer removes `app-01`;
- UI/API traffic continues through `app-02`;
- the MQTT broker remains available independently of the failed application node;
- the surviving ChirpStack node keeps its gateway MQTT backend connected;
- ChirpStack continues processing events;
- no MQTT trust, region-prefix, database, Valkey, or token-secret mismatch appears;
- fresh uplinks and an approved downlink continue.

### Validate

- HTTP/API success and latency;
- gateway last-seen;
- event count and stable identifiers;
- database writes from surviving node;
- broker subscriptions/clients;
- alert delivery and recovery time.

Repeat in the other direction.

## 14.4 MQTT broker failure

For a managed/clustered broker, use its supported failover test. For active/standby Mosquitto, stop the active backend or remove it from the load balancer.

Expected:

- each gateway's local Mosquitto queue retains new event/state messages within its finite limits;
- gateway bridges reconnect with configured backoff;
- ChirpStack reconnects;
- queued uplinks drain through the surviving broker;
- duplicate delivery remains idempotent downstream;
- no gateway identity/ACL broadening occurs.

Measure disconnect duration, reconnect-storm load, dropped or in-flight messages, and gateway battery/data impact. A broker process that restarts but exceeds the gateway queue or reconnect capacity has not passed the test.

## 14.5 Managed Valkey failover

Use the provider's approved failover mechanism in staging.

Expected:

- endpoint remains stable or application configuration follows the documented provider endpoint;
- both ChirpStack nodes reconnect;
- readiness reflects dependency failure during the event;
- no unapproved eviction or permanent state error occurs;
- gateway processing resumes automatically.

Do not delete/recreate the production cluster to simulate failover.

## 14.6 Planned PostgreSQL switchover

Use Patroni:

```bash
patronictl -c <PATRONI_CONFIG> list <PG_SCOPE> --extended
patronictl -c <PATRONI_CONFIG> switchover <PG_SCOPE>
```

Select the candidate deliberately.

Expected:

- current primary demotes cleanly;
- candidate promotes and owns the leader lock;
- HAProxy `/primary` changes to the new primary;
- PgBouncer replaces old server connections;
- ChirpStack retries transient database errors;
- test event sequence matches the approved RPO.

Validate old primary is in recovery before returning it as a replica.

## 14.7 Unplanned PostgreSQL primary loss

Possible staging actions:

- stop the Spilo container;
- stop the database Droplet;
- isolate only the primary's VPC traffic with a pre-reviewed firewall rule.

Do not corrupt the volume or delete the Patroni key.

Expected:

- Patroni promotes an eligible replica according to lag/synchronous policy;
- old primary cannot continue accepting writes;
- exactly one HAProxy primary backend becomes healthy;
- ChirpStack resumes through PgBouncer;
- alerts identify the role change and failed node;
- the old node rejoins safely or requires documented reinitialization.

### Split-brain checks

On every PostgreSQL member:

```sql
SELECT inet_server_addr(), pg_is_in_recovery(), pg_current_wal_lsn();
```

Use the recovery-safe equivalent on replicas where `pg_current_wal_lsn()` is unavailable/irrelevant. Confirm only one writable primary and one Patroni leader lock.

**Stop here. Do not resume normal writes** if two nodes appear writable or Patroni/etcd evidence conflicts.

## 14.8 PostgreSQL replica loss

Stop one replica.

Expected:

- primary remains available;
- Patroni reports reduced redundancy;
- alert fires;
- backup/WAL archive continues;
- no automatic unsafe promotion of a stale node occurs;
- replica can rejoin or be reinitialized under the approved procedure.

Do not test another database member until redundancy is restored.

## 14.9 etcd single-member loss

Stop one etcd member.

Expected:

- remaining two members preserve quorum;
- Patroni retains leadership and database availability;
- alerts report redundancy loss;
- member returns without cluster-ID or data-dir conflict.

Do not stop a second member.

## 14.10 etcd quorum-loss rehearsal

Perform only in isolated staging with current PostgreSQL and etcd backups.

Expected:

- etcd loses majority and rejects coordination writes;
- Patroni behavior matches the pinned version and configuration;
- no operator starts PostgreSQL manually or deletes DCS state;
- incident runbook identifies network/member recovery before snapshot restore;
- normal quorum recovery is demonstrated;
- snapshot disaster recovery is tested separately on a new cluster.

This test must not be performed casually in production.

## 14.11 4G outage

On the staging gateway, disconnect the mobile connection or use a controlled firewall block without changing RF settings.

Expected:

- Gateway OS, RAK5146, Concentratord, MQTT Forwarder, and local Mosquitto remain healthy;
- local event/state messages accumulate in the finite persistent queue;
- UDP Forwarder does not start as a fallback;
- gateway freshness transitions from current to delayed/stale/offline;
- dashboards do not show last-known telemetry as current;
- a controlled gateway reboot preserves the queue;
- queued uplinks drain after 4G returns;
- duplicate delivery remains idempotent;
- commands created during the outage are not replayed as stale downlinks;
- Gateway ID, RF plan, image, and certificate identity remain unchanged.

Measure queued count, queue-database growth, free space, drain time, duplicates, unique application rows, TLS handshakes, and mobile data used. Compare queue growth and drain rate with the designed outage window; a preserved queue that cannot drain before the next outage is still undersized.

## 14.12 DNS failure and endpoint change

In staging, use a test DNS name or controlled resolver response.

Test:

- temporary resolution failure;
- DNS endpoint change with the planned TTL;
- certificate hostname mismatch rejection;
- recovery after corrected DNS.

Clients must fail closed on certificate mismatch. Do not weaken TLS verification.

## 14.13 Certificate rotation and expiry

Use staging certificates with short, controlled validity.

Test:

1. install new CA/server/client certificates with an overlap period;
2. reload one service/node at a time;
3. prove old and new trust during overlap as designed;
4. revoke/remove old trust;
5. prove expired/revoked identity rejection;
6. verify dashboards and alerts report expiry/rejection.

Do not replace all trust material simultaneously without rollback copies.

## 14.14 Object-storage outage

Block or invalidate only the staging backup path.

Expected:

- PostgreSQL serving path remains available while WAL archive alerts fire;
- archive backlog and local disk consumption are visible;
- operators restore access before disk exhaustion;
- no unreviewed command discards WAL or disables archiving permanently.

Measure the time until the approved RPO is breached.

## 14.15 Load and reconnect storm

Generate approved synthetic load that represents:

- expected and peak uplinks;
- all gateways reconnecting after a broker restart;
- two ChirpStack nodes consuming events;
- dashboard/API reads;
- database writes and maintenance;
- backup/WAL traffic.

Measure:

- broker accepts/rejections and latency;
- ChirpStack processing/error latency;
- PgBouncer waits and server connections;
- PostgreSQL CPU/I/O/WAL/lag;
- etcd latency/elections;
- Valkey memory/latency/evictions;
- load-balancer/backend state;
- end-to-end event freshness.

Stop before resource exhaustion affects unrelated systems.

## 14.16 Data integrity checks

For a known test sequence, compare:

```text
Frames transmitted by test device
Frames received by gateway
MQTT events accepted
ChirpStack uplinks accepted
Application/integration events emitted
Database records stored
Unique event keys
Dashboard points displayed
```

Explain every difference: RF loss, duplicate reception, MQTT retry, deduplication, application rejection, or storage failure. Do not force the numbers to match by deleting evidence.

## 14.17 Acceptance matrix

| Test | Required result |
|---|---|
| App node loss | Service continues through surviving app node |
| MQTT backend loss | Clients reconnect and measured loss stays within accepted semantics |
| Valkey failover | ChirpStack reconnects without unapproved eviction/state failure |
| Planned DB switchover | New primary routed without DSN edits |
| Unplanned DB primary loss | One eligible replica promoted within target and no split brain |
| Replica loss | Writes continue with alert and reduced redundancy |
| One etcd member loss | Quorum and database leadership remain |
| 4G outage | Local queue retains bounded uplinks across outage/reboot, drains after recovery, and does not replay stale downlinks |
| DNS/TLS failure | Clients fail closed and recover after correction |
| Backup path failure | Alerts fire before disk/RPO limit |
| Restore/PITR | Isolated recovery reaches approved point and validates data |
| Peak/reconnect load | Capacity and freshness objectives hold |

## 14.18 Production readiness

The environment is ready for production traffic only when:

- every required failure test reaches its stated result or the unresolved limitation is explicitly excluded from the production design;
- measured RTO and RPO meet the objectives;
- monitoring detects every injected fault soon enough for the required response;
- rollback and isolated restore procedures work;
- firewall, certificate, quorum, and backup configuration return to the intended state after testing;
- gateway RF region and transmit behavior remain unchanged except during a separately controlled RF test;
- deployed Git revision, configuration hashes, image digests, and cloud resource identities can be identified.

Next: [15-operations-upgrades-and-scaling.md](15-operations-upgrades-and-scaling.md)
