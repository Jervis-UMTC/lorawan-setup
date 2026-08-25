# 16. Operations, Upgrades, Rotation, Scaling, and Decommissioning

> **Status: STANDBY / DRAFT.** These operating procedures depend on the final deployed versions and service layout. Keep them as design guidance and refine each section only after the corresponding technology has been validated.

## 16.1 Operating rule

Change one failure domain at a time. Preserve quorum, database redundancy, application capacity, gateway backhaul, and rollback evidence throughout the maintenance window.

Do not combine operating-system upgrades, PostgreSQL role changes, certificate rotation, firewall changes, and ChirpStack migrations in one unbounded change.

## 16.2 Routine checks

### Daily or automated

- gateway and device freshness;
- gateway journal service state, latest sequence/segment, unuploaded evidence backlog, evidence-storage headroom, and latest accepted checkpoint age;
- gateway-evidence pending/gap/failure counts and oldest pending age when v2 is deployed;
- failed joins, MIC/frame-counter errors, and downlink failures;
- MQTT connection/authentication/ACL errors;
- both ChirpStack readiness states;
- PgBouncer waiting clients and HAProxy primary count;
- Patroni cluster role/lag and etcd quorum;
- Valkey memory/evictions/failover;
- latest logical-backup age/checksum and disk/free space; if WAL archiving is later enabled, also check archive age/failures;
- certificate expiry and clock offset;
- provider incidents, maintenance, and data-cap alerts.

### Weekly

- review capacity trends and noisy alerts;
- confirm off-host backup copies and checksums;
- inspect failed login/firewall/account audit events;
- verify configuration/image drift;
- review long PostgreSQL transactions, vacuum, bloat, and slow normalized queries;
- confirm etcd snapshot and backend size;
- verify gateway modem reconnect history and carrier usage;
- review evidence checkpoint conflicts, journal/MQTT mismatches, trusted-decoder mismatches, and any unresolved evidence gaps.

### Monthly or approved cadence

- restore a representative backup in isolation;
- test one planned failover path in staging;
- review software/security advisories;
- rotate short-lived credentials/certificates as scheduled;
- reconcile cloud inventory, cost, tags, DNS, and ownership;
- validate runbook contacts and provider console access.

## 16.3 Prepare a bounded maintenance procedure

Before changing a production failure domain, write down only the information needed to execute and reverse the work:

```text
Objective and affected hosts, services, or gateways
Current and target image digests, package versions, or configuration hashes
Backup and isolated-restore reference
Expected interruption or reconnect behavior
Exact actions in execution order
Health checks that prove the target state
A measurable rollback trigger
Exact rollback image, configuration, or restore steps
```

Run the procedure on staging or a restored copy when possible. A useful maintenance procedure lets another qualified engineer identify the target, stop at the same failure signal, and return to the last tested state; it does not need unrelated approval or operator fields.

## 16.4 Certificate rotation

Use overlap where the protocol permits.

### Server certificates

1. issue certificate with correct SANs;
2. validate chain/key match offline;
3. install protected copy beside the old certificate;
4. update one backend/node;
5. reload and test hostname/chain/client connectivity;
6. update remaining nodes;
7. remove old certificate after all clients trust the new chain;
8. retain rollback copy for the approved period.

### Gateway OS MQTT client certificates

Rotate one gateway at a time:

1. issue a new client certificate whose Common Name exactly equals the existing 16-hex Gateway ID;
2. validate issuer, validity period, clientAuth EKU, key match, and fingerprint offline;
3. preserve the current Gateway OS configuration and encrypted identity rollback bundle;
4. install the new certificate and private key under `/etc/mosquitto/certs/` on the gateway;
5. validate and restart local Mosquitto, then prove both bridge client IDs, broker mTLS, exact ACL identity, queue drain, real uplink, and safe downlink;
6. revoke the old identity;
7. verify the old certificate is rejected in staging or through the approved revocation test;
8. update the encrypted identity backup and expiry monitoring.

Never distribute one replacement private key to multiple gateways.

### Gateway evidence-upload certificates

When the v2 evidence path is deployed, rotate its client identity independently from MQTT when separate-purpose PKI is used:

1. confirm the latest accepted checkpoint and upload all closable segments;
2. issue a new client identity mapped to the same Gateway EUI and evidence-upload purpose only;
3. validate server trust, client key match, fingerprint, expiry, and revocation reference;
4. install the new credential without changing journal sequence, record hash, or segment identity;
5. submit one fresh checkpoint/segment and prove it extends the existing server anchor;
6. revoke the old evidence-upload identity after the new one is proven;
7. update encrypted recovery records.

Never rotate evidence identity by resetting the journal.

### etcd certificates

Maintain quorum. Rotate peer/server certificates one member at a time and Patroni client trust with CA overlap. Verify endpoint health before the next member.

### PostgreSQL certificates

Update replicas before primary where possible, maintaining CA overlap and client verification. Validate PgBouncer-to-PostgreSQL `verify-full` after every node.

## 16.5 Secret rotation

Use dual-secret overlap only when the service supports it. Otherwise schedule a bounded restart/reconnect.

Rotate independently:

- PostgreSQL ChirpStack role;
- replication/rewind/admin/backup roles;
- PgBouncer authentication verifier/query role;
- MQTT ChirpStack and gateway identities;
- gateway evidence-ingest service credential and per-gateway upload identities;
- evidence-store credentials and verifier DB/object-store identities;
- Valkey credential;
- ChirpStack token secret;
- object-storage access key only when the later WAL/object-storage backup profile is enabled;
- API and alerting tokens.

Changing the ChirpStack token secret invalidates existing tokens and must be identical on both app nodes. Plan user impact.

For a PostgreSQL application-role password rotation in this POC:

1. identify every consumer of the role and confirm a tested rollback secret/reference;
2. create/set the new PostgreSQL secret in the controlled window;
3. update the protected PgBouncer verifier/auth source on **ha-01 only** and reload PgBouncer;
4. verify new connections through `ha-01` without breaking surviving old connections unexpectedly;
5. repeat on **ha-02**, verify ChirpStack-2/adapter-2 as applicable;
6. repeat on **ha-03**, verify Node-RED/Grafana roles as applicable;
7. prove all three `:6432` pool endpoints accept the new credential;
8. revoke the old secret only after old connections are drained or deliberately recycled;
9. verify the old credential is rejected and capture sanitized evidence.

Do not forget `ha-03`: PgBouncer runs on all three POC hosts.

## 16.6 Operating-system patching for the three co-located POC hosts

Every POC Droplet carries multiple quorum roles. Treat the **host** as the failure domain; do not follow a separate "app-node then DB-node" recipe that accidentally reboots the same machine twice.

Before patching any host:

```text
etcd 3/3
PostgreSQL 1 primary + 2 healthy replicas
Valkey 1 primary + 2 healthy replicas
Sentinel 3/3 and CKQUORUM healthy
OpenBao 3/3 unsealed/healthy
both ChirpStack nodes healthy if patching ha-01/ha-02
both Mosquitto backends healthy if patching ha-01/ha-02
current logical backup/restore evidence valid
```

Patch **one host at a time**:

1. choose a host that is not the PostgreSQL primary where practical; if needed, perform a planned Patroni switchover first;
2. if that host is the current Valkey primary, perform/allow a controlled Sentinel failover before maintenance and verify the new primary;
3. if patching `ha-01` or `ha-02` and it currently owns the Reserved IPv4, perform a **planned manual Reserved-IP move** to the other healthy app host and verify public HTTPS/MQTT before maintenance; disable/stop the target host's public-ingress timer during the maintenance window so it cannot compete;
4. confirm the other two etcd/OpenBao/Sentinel members are healthy immediately before reboot;
5. patch and reboot **only that host**;
6. verify private VPC address, time, firewall, mounts, container/runtime services, and certificates after boot;
7. wait for etcd membership, PostgreSQL replication, Valkey replication/Sentinel state, and OpenBao Raft state to return to full health;
8. verify HAProxy/PgBouncer and the host-specific app services;
9. send a fresh staging-device uplink and verify the expected data path;
10. re-enable the returning app host's public-ingress timer only after its anchor listeners pass local health; leave the Reserved IP on the currently healthy owner unless a separate planned move-back is desired;
11. do not patch the next host until all quorum groups are back at 3/3.

A future deployment that moves etcd/database/application roles onto dedicated machines needs a different maintenance sequence; do not copy that future topology back onto this POC runbook.

## 16.7 etcd upgrades

Read the official upgrade guide for the exact source/target versions. Verify supported upgrade order and downgrade behavior.

- snapshot and validate before upgrade;
- upgrade one member at a time;
- keep quorum;
- verify cluster/member versions and health before continuing;
- do not skip unsupported versions;
- do not mix configuration schema from another release.

**Stop here. Do not proceed** if quorum is degraded, snapshot validation fails, or the version path is unsupported.

## 16.8 Spilo and Patroni updates within the same PostgreSQL major

Build, scan, and pin a new image. Test it against a restored copy and staging failovers.

Rolling sequence:

1. validate backups and rollback digest;
2. update one replica;
3. prove replication, Patroni membership, TLS, TimescaleDB library availability, and read checks; if WAL archiving is enabled, verify it too;
4. update the second replica;
5. switchover to an updated replica;
6. update the former primary;
7. verify all members use the target digest;
8. run switchover/failover acceptance tests.

Do not update all members simultaneously.

## 16.8A TimescaleDB extension updates

TimescaleDB is part of the telemetry feature set and must remain promotion-safe on every Patroni member.

For an extension update within a compatible PostgreSQL major:

1. read the target TimescaleDB compatibility/upgrade notes for the exact PostgreSQL major;
2. take/verify both logical dumps and the isolated telemetry restore;
3. build/pin a Spilo image (or package set) containing the target TimescaleDB library;
4. update a PostgreSQL replica first and verify the library is available **without running `ALTER EXTENSION` yet**;
5. return that replica to healthy streaming state;
6. repeat for the second replica;
7. switchover to an updated replica and update the former primary so **all three promotion candidates contain the target library**;
8. only after all members are runtime-compatible, run the version-specific TimescaleDB extension SQL update from one controlled primary session when upstream requires it;
9. query `pg_extension` and `timescaledb_information.hypertables`;
10. perform a Patroni switchover and repeat those queries through the unchanged PgBouncer endpoint;
11. prove a fresh Node-RED telemetry insert and Grafana read.

**Why:** applying the extension catalog update before every promotion candidate has compatible TimescaleDB binaries can create a promoted primary that cannot load the telemetry extension.

## 16.9 PostgreSQL major upgrades

A major upgrade is a migration project, not a normal container restart.

Choose and test a supported method:

- logical dump/restore;
- `pg_upgrade` under the exact Spilo/Patroni procedure;
- logical replication to a new cluster;
- blue/green restore and cutover.

Required:

- extension and schema compatibility;
- new separate volumes/cluster where practical;
- a full tested logical backup/restore for the POC; add PITR evidence when the future WAL/PITR profile is enabled;
- application/version compatibility;
- measured downtime/data synchronization;
- rollback before irreversible writes on the new major;
- new Patroni/HAProxy/PgBouncer validation.

Never attach an existing data directory to a different PostgreSQL major image and hope it starts.

## 16.10 ChirpStack upgrades

1. read release notes and breaking configuration/schema changes;
2. test against an isolated restored database;
3. pin the new image digest and preserve rollback digest;
4. validate region files, codecs, MQTT/Valkey/PostgreSQL clients, and API changes;
5. create backups;
6. drain ChirpStack-2 on `ha-02`;
7. use only ChirpStack-1 on `ha-01` as migration owner;
8. validate migrations and end-to-end gateway/device flow;
9. update ChirpStack-2 on `ha-02`;
10. test app-node and DB failover.

An irreversible database migration may make image rollback impossible without a database restore. State this before the maintenance window and verify the restore path first.

## 16.10A Gateway OS / journal upgrades

Treat Gateway OS, Concentratord, and journal changes as one source-evidence compatibility boundary.

Before upgrading a gateway:

1. identify current/target Gateway OS, Concentratord, MQTT Forwarder, Mosquitto, and journal versions/hashes;
2. drain MQTT delivery work when possible;
3. close/upload/verify journal segments and record a final accepted checkpoint;
4. preserve the rollback image/configuration/identity bundle and continuity manifest;
5. test the exact target image + journal implementation on spare hardware using the same RAK5146 class;
6. prove the target journal consumes the supported Concentratord event interface and produces the expected `gateway-journal-v1` byte/hash contract, or explicitly introduce a reviewed new journal version;
7. prove reboot continuity, WAN outage, segment upload, journal-to-MQTT reconciliation, and trusted-decoder lineage before fleet rollout;
8. upgrade one gateway at a time.

Do not keep the same journal version identifier if the serialized record meaning or hashing bytes changed.

## 16.11 MQTT upgrades

For a true clustered broker, follow its rolling-upgrade and compatibility documentation.

For active/standby Mosquitto:

1. confirm HAProxy currently prefers Mosquitto-1 and both private `:8884` TLS backends are healthy;
2. update Mosquitto-2 (standby) first;
3. test its server certificate, client-certificate requirement, ACLs, and an authorized/unauthorized MQTT operation directly on private `:8884`;
4. stop/drain Mosquitto-1 so HAProxy selects updated Mosquitto-2 through public `:8883` and internal `:18883`;
5. observe gateway and Node-RED/ChirpStack reconnect behavior;
6. update Mosquitto-1;
7. validate it on private `:8884`;
8. restore Mosquitto-1 as preferred and Mosquitto-2 as backup on every HAProxy host;
9. prove the physical gateway queue is drained and one fresh uplink succeeds.

Preserve certificate and ACL consistency. Define the expected clean-session and in-flight-message loss, then compare the observed reconnect with that boundary.

## 16.12 Self-managed Valkey/Sentinel maintenance

Valkey/Sentinel is **self-managed on ha-01/02/03** in this POC; there is no provider-managed Valkey maintenance window.

Use a rolling procedure:

1. record the current Valkey primary with `ROLE` and confirm all three Sentinels agree;
2. run `SENTINEL CKQUORUM lorawan-valkey` and verify enough voters for failover;
3. confirm both replicas are connected and reasonably caught up;
4. take the normal POC database/config backup evidence and verify memory headroom/no evictions;
5. update one **replica** first using the pinned Valkey image/package;
6. verify TLS, authentication, replica link, announced address, and Sentinel discovery after restart;
7. update the second replica and return to three healthy data nodes;
8. trigger a controlled Sentinel failover away from the old primary or stop the old primary under the approved test procedure;
9. verify both commissioned HAProxy Valkey endpoints (`10.104.0.2:16379` and `10.104.0.4:16379`) route only to the promoted writable primary while clients verify `valkey.internal.lorawan.com`;
10. update the former primary and let Sentinel configure it as a replica;
11. confirm all three Sentinels agree, `CKQUORUM` passes, and ChirpStack processes a fresh uplink;
12. restore full 3-node redundancy before closing the window.

Do not manually edit three nodes into competing primaries. Sentinel owns promotion during normal HA operation.

## 16.12A OpenBao and Fabric-adapter rolling changes

For OpenBao, change one Raft member at a time. Before each member restart, prove 3/3 health and keep recovery/unseal material outside the nodes; after restart, explicitly verify the member is unsealed, rejoined, and the stable `:18200` KMS endpoint still signs/verifies before touching the next voter.

For Fabric adapters, update the standby/idle worker first when possible, verify its unique `worker_id`, DB lease behavior, OpenBao identity, and Fabric handoff configuration, then move work and update the other worker. Never run two workers with the same `worker_id` or a shared live lease.

If the reviewed Fabric adapter image still does not exist, this section remains a documented future procedure and is not executable evidence.

## 16.12B Scaling gateway evidence services

Scale the evidence roles independently:

```text
ingestor       -> upload/checkpoint request throughput and object writes
MQTT collector -> gateway event rate and broker subscription semantics
verifier       -> hash/correlation/trusted-decoder backlog
```

Before adding collector/verifier replicas, prove their concurrency/idempotency model. Two collectors must not create ambiguous duplicate forensic records merely because both consumed the same topic, and two verifiers must not race conflicting state transitions. Use stable object/event identities and database uniqueness/claim rules.

Capacity acceptance is based on the worst supported post-outage backlog, not only steady-state events/second.

## 16.13 Scaling application nodes

Add an app node only when:

- the broker consumption model supports another subscriber;
- the token secret and all configurations can be kept identical;
- PgBouncer/HAProxy connection budgets include it;
- load-balancer/firewall/monitoring covers it;
- it has a unique MQTT client identity;
- migrations remain single-owner.

Adding nodes without shared-subscription or duplicate-handling validation can duplicate event processing.

## 16.14 Scaling PostgreSQL

### Vertical scaling

Resize replicas one at a time, verify, switchover, then resize the old primary. Confirm volume latency and memory settings after resize.

### Read replicas

Add only through Patroni/Spilo supported cloning. Read replicas do not increase write capacity. Ensure retention/WAL slots cannot fill the primary disk when a replica is disconnected.

### Write scaling

PostgreSQL streaming replication remains one writable primary. If write capacity is exhausted, optimize workload/indexes/connection pooling, scale the primary, or redesign data placement. Do not distribute ChirpStack writes across replicas.

## 16.15 etcd scaling

Three members tolerate one failure. Five tolerate two but add write latency and operational cost. Do not add members to solve client load or disk problems.

Change membership one member at a time using `etcdctl member add/remove`, with snapshots and quorum evidence. Never use an even voting-member count as an availability improvement.

## 16.16 Storage expansion

Before resizing a PostgreSQL volume:

- identify exact provider volume and host;
- verify backups and free-space trend;
- review provider resize limitations;
- resize one replica first;
- expand partition/filesystem using the correct tool;
- validate filesystem and PostgreSQL;
- repeat under the database rolling procedure.

A provider volume cannot necessarily be shrunk. Keep the tested restore or replacement-volume path as the rollback method.

## 16.17 Decommissioning a node

### Application node

If the application node owns the Reserved IPv4, move it to the other verified app host first. Disable its public-ingress failover timer, stop services, revoke service credentials and certificates, update the failover candidate inventory, preserve required logs, then destroy only the verified target after the retention and rollback requirements are satisfied. Keep public DNS on the Reserved IP unless the entire public service is being retired.

### PostgreSQL replica

Confirm it is not primary, remove it through the Patroni-supported membership procedure, remove replication slots safely, preserve the incident evidence needed for diagnosis, and detach or destroy only the exact verified volume after backup, retention, and recovery requirements are satisfied.

### etcd member

Confirm quorum and member ID, snapshot, remove with `etcdctl member remove`, verify member list/quorum, then destroy. Deleting the host without member removal leaves stale membership.

### Gateway

Confirm the device or gateway is being decommissioned. When the evidence path is enabled:

1. drain MQTT work when possible;
2. upload/verify all retained closed journal segments;
3. create and record a final accepted checkpoint/receipt;
4. preserve server-side checkpoint/segment/captured-event/verification objects for the required retention period;
5. disable the ChirpStack gateway record;
6. revoke both MQTT and evidence-upload identities/ACLs;
7. preserve the inventory and final logs needed for history;
8. erase local secrets/evidence according to the approved retention/destruction policy;
9. dispose of the SIM and hardware according to handling rules.

Do not delete the authoritative server checkpoint merely because the physical gateway is gone.

## 16.18 Configuration drift

Regularly compare:

- infrastructure state versus provider inventory;
- image digests and package versions;
- configuration hashes across app nodes;
- firewall rules and resource tags;
- certificate identities/expiry;
- Patroni dynamic configuration;
- etcd member list;
- PostgreSQL roles/grants and PgBouncer pools;
- MQTT ACL/client inventory;
- gateway inventory and actual last-seen;
- journal implementation/format versions and configured source interface;
- evidence endpoint/PKI identity mapping and latest checkpoint freshness;
- evidence-ingest/collector/verifier versions/configuration and trusted-decoder inventory.

Do not auto-remediate destructive drift without review.

## 16.19 Maintenance final checks

Close a change only when:

- target versions, digests, and configuration hashes can be identified on every changed node;
- quorum, redundancy, replication, backups, and application capacity are restored;
- real gateway/device flow is fresh;
- when enabled, gateway evidence checkpoint/segment/correlation/trusted-decoder flow is fresh and no unexplained pending/gap/failure state remains;
- planned failure tests pass;
- monitoring/alerts/logging are healthy;
- old credentials/images/configs are retired only after rollback window;
- Git/provider inventory is cleanly reconciled;
- residual risk and unverified runtime items are documented.

Next: [17-troubleshooting.md](17-troubleshooting.md)
