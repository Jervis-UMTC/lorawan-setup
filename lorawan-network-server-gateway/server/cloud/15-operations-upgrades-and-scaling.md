# 15. Operations, Upgrades, Rotation, Scaling, and Decommissioning

## 15.1 Operating rule

Change one failure domain at a time. Preserve quorum, database redundancy, application capacity, gateway backhaul, and rollback evidence throughout the maintenance window.

Do not combine operating-system upgrades, PostgreSQL role changes, certificate rotation, firewall changes, and ChirpStack migrations in one unbounded change.

## 15.2 Routine checks

### Daily or automated

- gateway and device freshness;
- failed joins, MIC/frame-counter errors, and downlink failures;
- MQTT connection/authentication/ACL errors;
- both ChirpStack readiness states;
- PgBouncer waiting clients and HAProxy primary count;
- Patroni cluster role/lag and etcd quorum;
- Valkey memory/evictions/failover;
- WAL archive age, backup job result, disk/free space;
- certificate expiry and clock offset;
- provider incidents, maintenance, and data-cap alerts.

### Weekly

- review capacity trends and noisy alerts;
- confirm off-host backup copies and checksums;
- inspect failed login/firewall/account audit events;
- verify configuration/image drift;
- review long PostgreSQL transactions, vacuum, bloat, and slow normalized queries;
- confirm etcd snapshot and backend size;
- verify gateway modem reconnect history and carrier usage.

### Monthly or approved cadence

- restore a representative backup in isolation;
- test one planned failover path in staging;
- review software/security advisories;
- rotate short-lived credentials/certificates as scheduled;
- reconcile cloud inventory, cost, tags, DNS, and ownership;
- validate runbook contacts and provider console access.

## 15.3 Prepare a bounded maintenance procedure

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

## 15.4 Certificate rotation

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

### etcd certificates

Maintain quorum. Rotate peer/server certificates one member at a time and Patroni client trust with CA overlap. Verify endpoint health before the next member.

### PostgreSQL certificates

Update replicas before primary where possible, maintaining CA overlap and client verification. Validate PgBouncer-to-PostgreSQL `verify-full` after every node.

## 15.5 Secret rotation

Use dual-secret overlap only when the service supports it. Otherwise schedule a bounded restart/reconnect.

Rotate independently:

- PostgreSQL ChirpStack role;
- replication/rewind/admin/backup roles;
- PgBouncer authentication verifier/query role;
- MQTT ChirpStack and gateway identities;
- Valkey credential;
- ChirpStack token secret;
- object-storage access key;
- API and alerting tokens.

Changing the ChirpStack token secret invalidates existing tokens and must be identical on both app nodes. Plan user impact.

For PostgreSQL application password rotation:

1. create or set the new secret in PostgreSQL;
2. update protected PgBouncer auth material;
3. reload PgBouncer on one app node;
4. verify new connections and ChirpStack health;
5. update the second app node;
6. revoke the old secret after all old connections drain;
7. verify old authentication failure.

## 15.6 Operating-system patching

Patch one node at a time.

### Application nodes

1. remove node from load balancer;
2. drain/stop ChirpStack safely;
3. patch and reboot;
4. verify HAProxy, PgBouncer, ChirpStack, MQTT, monitoring, and private listeners;
5. return node to load balancer;
6. repeat for the other node.

### Database nodes

1. confirm etcd quorum, Patroni state, replicas, lag, backups, and candidate eligibility;
2. patch a replica first;
3. verify it rejoins and catches up;
4. patch the other replica;
5. perform a planned switchover away from the old primary;
6. patch the former primary;
7. verify three-member health and backups.

If etcd is co-located, each DB-node reboot also removes an etcd vote. Do not reboot another until the first member is fully healthy.

### Dedicated etcd nodes

Patch one member, restore endpoint health/quorum, then continue.

## 15.7 etcd upgrades

Read the official upgrade guide for the exact source/target versions. Verify supported upgrade order and downgrade behavior.

- snapshot and validate before upgrade;
- upgrade one member at a time;
- keep quorum;
- verify cluster/member versions and health before continuing;
- do not skip unsupported versions;
- do not mix configuration schema from another release.

**Stop here. Do not proceed** if quorum is degraded, snapshot validation fails, or the version path is unsupported.

## 15.8 Spilo and Patroni updates within the same PostgreSQL major

Build, scan, and pin a new image. Test it against a restored copy and staging failovers.

Rolling sequence:

1. validate backups and rollback digest;
2. update one replica;
3. prove replication, Patroni membership, TLS, WAL archive, and read checks;
4. update the second replica;
5. switchover to an updated replica;
6. update the former primary;
7. verify all members use the target digest;
8. run switchover/failover acceptance tests.

Do not update all members simultaneously.

## 15.9 PostgreSQL major upgrades

A major upgrade is a migration project, not a normal container restart.

Choose and test a supported method:

- logical dump/restore;
- `pg_upgrade` under the exact Spilo/Patroni procedure;
- logical replication to a new cluster;
- blue/green restore and cutover.

Required:

- extension and schema compatibility;
- new separate volumes/cluster where practical;
- full backup and PITR evidence;
- application/version compatibility;
- measured downtime/data synchronization;
- rollback before irreversible writes on the new major;
- new Patroni/HAProxy/PgBouncer validation.

Never attach an existing data directory to a different PostgreSQL major image and hope it starts.

## 15.10 ChirpStack upgrades

1. read release notes and breaking configuration/schema changes;
2. test against an isolated restored database;
3. pin the new image digest and preserve rollback digest;
4. validate region files, codecs, MQTT/Valkey/PostgreSQL clients, and API changes;
5. create backups;
6. drain `app-02`;
7. use only `app-01` as migration owner;
8. validate migrations and end-to-end gateway/device flow;
9. update `app-02`;
10. test app-node and DB failover.

An irreversible database migration may make image rollback impossible without a database restore. State this before the maintenance window and verify the restore path first.

## 15.11 MQTT upgrades

For a true clustered broker, follow its rolling-upgrade and compatibility documentation.

For active/standby Mosquitto:

1. update standby;
2. test TLS, ACL, synthetic publish/subscribe, and gateway client compatibility;
3. move load-balancer traffic to updated standby;
4. observe reconnect impact;
5. update former active;
6. restore the intended active/standby priority.

Preserve certificate and ACL consistency. Define the expected clean-session and in-flight-message loss, then compare the observed reconnect with that boundary.

## 15.12 Valkey maintenance

Use the provider maintenance window and current upgrade documentation. Before a version change:

- confirm application compatibility;
- review backup/failover capability;
- verify memory headroom/no evictions;
- test in staging;
- monitor ChirpStack reconnect/readiness during maintenance;
- verify key/connection/latency behavior afterward.

## 15.13 Scaling application nodes

Add an app node only when:

- the broker consumption model supports another subscriber;
- the token secret and all configurations can be kept identical;
- PgBouncer/HAProxy connection budgets include it;
- load-balancer/firewall/monitoring covers it;
- it has a unique MQTT client identity;
- migrations remain single-owner.

Adding nodes without shared-subscription or duplicate-handling validation can duplicate event processing.

## 15.14 Scaling PostgreSQL

### Vertical scaling

Resize replicas one at a time, verify, switchover, then resize the old primary. Confirm volume latency and memory settings after resize.

### Read replicas

Add only through Patroni/Spilo supported cloning. Read replicas do not increase write capacity. Ensure retention/WAL slots cannot fill the primary disk when a replica is disconnected.

### Write scaling

PostgreSQL streaming replication remains one writable primary. If write capacity is exhausted, optimize workload/indexes/connection pooling, scale the primary, or redesign data placement. Do not distribute ChirpStack writes across replicas.

## 15.15 etcd scaling

Three members tolerate one failure. Five tolerate two but add write latency and operational cost. Do not add members to solve client load or disk problems.

Change membership one member at a time using `etcdctl member add/remove`, with snapshots and quorum evidence. Never use an even voting-member count as an availability improvement.

## 15.16 Storage expansion

Before resizing a PostgreSQL volume:

- identify exact provider volume and host;
- verify backups and free-space trend;
- review provider resize limitations;
- resize one replica first;
- expand partition/filesystem using the correct tool;
- validate filesystem and PostgreSQL;
- repeat under the database rolling procedure.

A provider volume cannot necessarily be shrunk. Keep the tested restore or replacement-volume path as the rollback method.

## 15.17 Decommissioning a node

### Application node

Drain the load balancer, stop services, revoke service credentials and certificates, remove DNS, tag, and firewall access, preserve required logs, then destroy only the verified target after the retention and rollback requirements are satisfied.

### PostgreSQL replica

Confirm it is not primary, remove it through the Patroni-supported membership procedure, remove replication slots safely, preserve the incident evidence needed for diagnosis, and detach or destroy only the exact verified volume after backup, retention, and recovery requirements are satisfied.

### etcd member

Confirm quorum and member ID, snapshot, remove with `etcdctl member remove`, verify member list/quorum, then destroy. Deleting the host without member removal leaves stale membership.

### Gateway

Confirm the device or gateway is being decommissioned, disable its ChirpStack record, revoke its MQTT certificate and ACL, preserve the inventory and final logs needed for history, erase secrets, and dispose of the SIM and hardware according to the applicable handling rules.

## 15.18 Configuration drift

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
- gateway inventory and actual last-seen.

Do not auto-remediate destructive drift without review.

## 15.19 Maintenance final checks

Close a change only when:

- target versions, digests, and configuration hashes can be identified on every changed node;
- quorum, redundancy, replication, backups, and application capacity are restored;
- real gateway/device flow is fresh;
- planned failure tests pass;
- monitoring/alerts/logging are healthy;
- old credentials/images/configs are retired only after rollback window;
- Git/provider inventory is cleanly reconciled;
- residual risk and unverified runtime items are documented.

Next: [16-troubleshooting.md](16-troubleshooting.md)
