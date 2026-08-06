# 13. Observability, Alerting, and Logging

## 13.1 Goal

Provide independent evidence from RF reception through cloud persistence and user-visible telemetry. Monitoring must distinguish process availability, dependency health, message flow, database durability, and data freshness.

A green service process does not prove a working LoRaWAN path. A recent database row does not prove correct decoding. A last-known dashboard value does not prove current conditions.

## 13.2 Monitoring architecture

A typical private monitoring path is:

```text
Gateway metrics/logs over outbound TLS
Cloud node exporters on private VPC
Managed-service metrics and provider API
Application synthetic probes
  -> Prometheus-compatible metrics store
  -> Grafana dashboards
  -> Alertmanager/on-call notification
  -> protected centralized logs
```

Monitoring endpoints must not be public. Restrict them to the monitoring subnet or authenticated collector. Pin exporter versions and apply least privilege.

## 13.3 Gateway and 4G signals

Collect or derive:

- Gateway OS Base version, image checksum, OpenWrt/kernel version, uptime, CPU, memory, temperature, storage state, and power warnings;
- Concentratord, MQTT Forwarder, and local Mosquitto process state, restart count, and configuration hash;
- RAK5146 initialization, SPI/reset failures, radio calibration evidence, Gateway ID, and active channel plan;
- local queue database size, persistent-storage free space, configured limits, drops, bridge reconnects, and drain rate;
- remote MQTT connect/disconnect, TLS failures, certificate expiry, ACL denials, and topic prefix;
- evidence that UDP Forwarder, Gateway OS Full local services, and unexpected packet forwarders remain disabled or absent;
- gateway last-seen age and real-frame freshness from ChirpStack;
- modem registration, interface state, signal metrics supported by the modem, APN, route, RTT, packet loss, and reconnect duration;
- SIM/data-cap usage through the carrier API where available;
- certificate expiry and system clock offset.

Do not log the SIM PIN, APN password, MQTT password, private key, or complete device payload by default.

## 13.4 MQTT signals

Collect:

- accepted and rejected connections;
- active connections by client type;
- authentication and ACL denials;
- publish/subscribe rates by approved topic class;
- dropped, queued, expired, duplicate, and retained messages where supported;
- reconnect storms;
- broker memory, file descriptors, CPU, network, and storage;
- load-balancer backend state;
- synthetic publish/subscribe latency;
- TLS version and certificate expiry.

Alert separately on an expected ACL rejection test versus unexpected production authentication failures.

## 13.5 ChirpStack signals

Collect:

- application process/readiness state per node;
- request rate, error rate, and response latency;
- PostgreSQL, Valkey, and MQTT connection failures;
- database migration/schema errors;
- gateway count by freshness state;
- uplink/downlink rates;
- join accepts/rejects and MIC/frame-counter errors;
- integration delivery success/failure/retry;
- queue depth and scheduler warnings where exposed;
- region configuration load failures;
- active image digest and configuration hash.

Create a bounded synthetic API check using a monitoring account with no device-root-key access.

## 13.6 HAProxy signals

Enable the statistics socket or Prometheus endpoint only on a protected local/private listener.

Monitor:

- backend status and health-check result;
- exactly one healthy server in the primary backend;
- replica count and lag-based exclusions;
- connection attempts, failures, retries, and queue time;
- session terminations during failover;
- configuration reload failures;
- certificate expiry when HAProxy terminates TLS.

Critical condition: zero or more than one healthy primary backend. The latter can indicate a broken health check or split-brain evidence and requires immediate write-path review.

## 13.7 PgBouncer signals

From the `pgbouncer` admin database, collect sanitized values from:

```sql
SHOW POOLS;
SHOW STATS;
SHOW DATABASES;
SHOW SERVERS;
SHOW CLIENTS;
```

Monitor:

- active and waiting clients;
- `maxwait` and average query wait;
- active/idle server connections;
- server login failures;
- pool utilization against limits;
- transaction/request rate;
- bytes sent/received;
- repeated reconnects after Patroni changes;
- file descriptors and process memory.

Do not export complete client query strings or credentials.

## 13.8 PostgreSQL and Patroni signals

Use a least-privilege monitoring role and a supported PostgreSQL exporter. Monitor:

- Patroni member role, leader lock, timeline, pending restart, and cluster state;
- primary changes and failover duration;
- streaming replication state and receive/replay lag;
- WAL generation, archive age/errors, and replication slots;
- transaction rate, conflicts, deadlocks, rollbacks, and long transactions;
- connection count by role/database/application;
- query latency and top normalized query classes without sensitive literals;
- table/index size, bloat indicators, vacuum/analyze age, and frozen transaction age;
- checkpoints, buffers, cache behavior, temp files, and I/O latency;
- disk usage/inodes and volume attachment;
- backup age and restore-test age;
- PostgreSQL, Patroni, and certificate versions/expiry.

An exporter must not be superuser unless the exact metric need and risk are approved.

## 13.9 etcd signals

Monitor:

- member count and endpoint health;
- current leader and leader-change rate;
- raft proposal committed/applied difference;
- failed proposals;
- peer RTT;
- WAL and backend fsync latency;
- backend database size and quota;
- compaction/defragmentation status;
- alarms, including no-space;
- snapshot age and checksum validation;
- certificate expiry;
- host disk, CPU, clock, and network.

Alert before disk latency causes election instability. Loss of one member is urgent; loss of quorum is critical.

## 13.10 Managed Valkey signals

Collect provider metrics for:

- availability and failovers;
- memory usage and fragmentation;
- evicted/expired keys;
- connection count and rejections;
- operations and latency;
- CPU/network;
- replication health;
- maintenance events;
- certificate and credential expiry where applicable.

Any eviction must be correlated with ChirpStack behavior. Do not mark the service healthy solely because `PING` succeeds.

## 13.11 Cloud and load-balancer signals

Collect:

- Droplet CPU, bandwidth, disk, power/reboot events, and failed health checks;
- VPC reachability and firewall changes;
- load-balancer active connections, backend health, TLS errors, and response latency;
- block-volume latency, capacity, and attachment state;
- object-storage availability, request failures, backup object growth, and lifecycle deletion;
- Managed Valkey maintenance/failover events;
- cloud account/API authentication and audit events;
- quota and billing/data-transfer anomalies.

Alert on unauthorized tag or firewall changes because resource tags may alter permitted sources.

## 13.12 Data freshness model

Define per gateway and device class:

```text
Expected interval:
Delayed threshold:
Stale threshold:
Offline threshold:
Maintenance suppression:
Owner and escalation:
```

Dashboard state example:

| State | Meaning |
|---|---|
| Current | New data within approved interval and grace period |
| Delayed | Past expected interval but below stale threshold |
| Stale | Last-known value is too old for operational use |
| Never seen | Registered object has no accepted event |
| Maintenance | Approved suppression with owner and end time |
| Unknown | Query, pipeline, or timestamp cannot establish state |

A stale, missing, or failed-query value must never be rendered as a safe current value.

## 13.13 Synthetic end-to-end checks

Use separate test identities and clearly marked data.

### Gateway-path synthetic check

A staging gateway or approved RF test device sends at a known interval. Verify:

1. gateway stats;
2. MQTT event receipt;
3. ChirpStack accepted uplink;
4. expected application integration;
5. database row with stable event key;
6. dashboard freshness update.

Do not transmit outside the approved region/channel plan.

### Cloud-only synthetic check

Without RF, publish only to a dedicated non-production health topic and exercise broker transport. Do not inject fake frames into production ChirpStack application topics.

### Database synthetic check

Through PgBouncer, insert and read a transaction in a dedicated monitoring table/database, then remove only that test record. A database write probe must not modify ChirpStack schema tables.

## 13.14 Alert design

Every actionable alert must contain:

```text
Symptom:
Affected environment/host/service:
First observed and duration:
Current measured value and threshold:
Likely layer:
Immediate safe checks:
Runbook link:
Owner/escalation:
Suppression/maintenance context:
```

Avoid alerts that merely restate "service down" without dependency context.

## 13.15 Initial alert matrix

| Alert | Meaning | First safe action |
|---|---|---|
| Gateway last-seen stale | RF gateway or MQTT path stopped updating | Check power, Concentratord, MQTT Forwarder, local Mosquitto queue, modem, remote broker, certificate identity, and ChirpStack region in order |
| Gateway buffer near limit | WAN or remote broker outage is consuming finite storage | Restore the remote path, preserve free-space reserve, identify oldest/newest queued frames, and apply overflow procedure |
| MQTT synthetic timeout | Broker/LB/auth/topic path failed | Test TLS, backend health, ACL logs, and one protected publish/subscribe |
| No healthy ChirpStack backend | Both app nodes or dependencies failed | Remove only broken nodes; inspect PostgreSQL, Valkey, and MQTT before restart |
| HAProxy primary count not 1 | No writable primary or invalid health evidence | Check Patroni cluster and `/primary`; freeze risky writes if split brain is suspected |
| PgBouncer clients waiting | Pool/server capacity or DB unavailability | Inspect `SHOW POOLS`, HAProxy, PostgreSQL connections, and long transactions |
| Patroni leader changed | Planned or unplanned database role change | Confirm new primary, old primary demotion, replication, and application writes |
| etcd member down | Quorum has lost redundancy | Restore member/connectivity before touching another member |
| etcd quorum lost | Patroni cannot safely coordinate leadership | Stop changes; recover network/members; do not force PostgreSQL manually |
| WAL archive stale | RPO is increasing | Check object access, archive command, disk, and backup credentials |
| Valkey eviction | Memory pressure may remove runtime state | Check memory/key growth and ChirpStack errors; do not change policy blindly |
| Certificate expiring | Future connection outage | Follow staged rotation with overlap and rollback |
| Data stale but services green | Pipeline or device failure hidden by process checks | Trace event timestamps layer by layer |

## 13.16 Logging

Centralize:

- systemd journal and container logs;
- Cloud Firewall/load-balancer/account audit events;
- gateway local Mosquitto queue, persistence, bridge, and drop events;
- remote MQTT authentication/ACL events;
- ChirpStack errors and integration results;
- HAProxy health changes;
- PgBouncer errors and pool events;
- Patroni/PostgreSQL role and recovery events;
- etcd alarms/elections;
- backup/restore jobs.

Use TLS, buffering, backpressure, retention, access control, and redaction. Prevent a log collector outage from filling database disks.

## 13.17 Time and correlation

All systems use UTC internally. Include:

- RFC 3339 timestamp;
- hostname/node/member;
- environment;
- gateway EUI or device identifier only when approved;
- stable event/transaction ID;
- service and version;
- trace/correlation ID where supported.

Never fabricate a single timestamp across events; preserve observed and received times separately.

## 13.18 Final checks

- Every layer has process, dependency, flow, and freshness evidence.
- Alerts have owners, runbooks, and tested notification paths.
- Dashboards distinguish current, delayed, stale, missing, and unknown.
- Backup, certificate, quorum, primary-count, and mobile-data risks alert before exhaustion/outage.
- Synthetic checks cannot affect production devices or downlinks.
- Logs are searchable, time-synchronized, redacted, and capacity-bounded.

Next: [14-failover-chaos-and-acceptance-testing.md](14-failover-chaos-and-acceptance-testing.md)
