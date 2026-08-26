# 12. Gateway and Device Migration

> **Status: REQUIRED PRE-TEST SETUP / DRAFT.** Do not cut over a gateway or device until Phase 10 and Phase 11 normal paths are commissioned and the **Phase 13A backup/isolated-restore safety checkpoint** has passed. This is a cutover/provisioning phase, not a chaos phase.

This guide supports two real deployment cases: migration from an older authoritative server-hosted ChirpStack installation, or fresh provisioning directly into the new cloud when there is no authoritative legacy database to import. Do not pretend a fresh deployment is a database migration. When a legacy source exists, the `source` host is the machine that currently runs ChirpStack and its Compose project; it is not the Raspberry Pi Gateway OS appliance.

## 12.1 Goal

Move the existing ChirpStack state from the **source application/server host** to the cloud without running two authoritative network servers for the same gateway and devices. The Raspberry Pi remains the physical gateway. Preserve tenants, applications, profiles, gateways, devices, root-key state, sessions, frame counters, and integration settings when technically compatible.

## 12.2 Migration strategy decision

Choose one:

### Full ChirpStack database migration

Use when source and target versions are compatible and preserving sessions/frame counters is important. This minimizes device reprovisioning but requires careful version and schema matching.

### Recreate configuration and rejoin devices

Use when the source database is incompatible, small enough to rebuild, or security policy requires new root keys/sessions. This creates more field work and must account for battery devices and physical access.

### Fresh cloud provisioning

Use when the new cloud is the first authoritative ChirpStack environment. Create the tenant, application, device profile, gateway, and device using the commissioned ChirpStack UI/API; generate/store root keys through the approved secret workflow; register the real Gateway EUI; then perform a normal OTAA join. There is no source database dump/restore in this branch, but Phase 13A still protects the already-commissioned cloud state before onboarding.

Do not partially copy tables by hand. Use supported database migration, explicit reprovisioning, or the fresh-provisioning branch.

## 12.3 Source inventory

On the legacy source application host, capture the running services without exposing secrets:

```bash
cd <SOURCE_COMPOSE_DIR>
docker compose ps
docker compose config --services
docker compose images
git rev-parse HEAD 2>/dev/null || true
sudo ss -lntup
```

Export or capture the source counts and identifiers for users, tenants, applications, device profiles, gateways, devices, multicast groups, API-key references, integrations, regions, codecs, and external alerts or dashboards. These values are compared with the restored target before gateway traffic is allowed.

Keep only key references and protected storage locations, not AppKey/NwkKey values or live API tokens.

## 12.4 Back up and identify the source state

Create a protected custom-format ChirpStack PostgreSQL dump and configuration archive using the logical-backup controls in [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md). Back up the physical gateway separately with [Gateway Backup and Recovery](../../gateway/operations/02-backup-and-recovery.md). Validate the dump catalog, calculate its checksum, and copy both backup sets off their source systems.

Keep the source ChirpStack image/version, PostgreSQL major/version, schema or migration state, active region-file hashes, Gateway EUI, Concentratord channel plan, effective MQTT region prefix, and last successful uplink time. When gateway integrity is enabled, also retain the journal implementation/format versions, latest local sequence/segment hash, latest accepted server checkpoint/receipt, evidence endpoint identity, and any unuploaded closed-segment inventory. These values let the target be compared with the authoritative source without copying live root keys into documentation.

**Stop here. Do not cut over** if the source backup is unreadable, exists only on the source host, or the target restore has not succeeded in staging.

## 12.5 Build and validate the cloud before migration

The cloud environment must pass:

- etcd quorum and snapshot test;
- Patroni cluster, replication, and switchover test;
- validated logical dumps of `chirpstack` and `lorawan_telemetry` plus an isolated restore rehearsal per [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md); WAL/base-backup/PITR evidence is required only if that later production backup profile has actually been enabled;
- PgBouncer pooling and HAProxy primary routing;
- Valkey replication + Sentinel automatic failover test;
- MQTT TLS and per-gateway ACL test using a staging identity;
- when v2 gateway integrity is in scope, evidence-ingest mTLS identity, checkpoint conflict rules, read-only gateway MQTT collector, journal/segment verifier, and trusted-decoder staging tests;
- one ChirpStack node and then two-node application test;
- public TLS and load-balancer health;
- the minimal command-line observability/evidence checks required by this POC.

Use a reserved staging gateway/device or synthetic application event. Do not connect the authoritative production-like gateway yet.

**Mandatory Phase 13A boundary:** before the cutover/provisioning window, create the protected database/configuration backup set, copy it off the target Droplets, and complete the isolated `lorawan_telemetry` restore rehearsal in [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md).

**Stop here. Do not migrate or provision authoritative device state** while any dependency above is being commissioned for the first time. First-time HA debugging and live cutover must not happen in the same window.

## 12.6 Version compatibility

The safest full migration sequence uses the same ChirpStack application version in source and target for the initial restore. Upgrade only after the cloud copy is stable.

Verify:

- PostgreSQL dump compatibility;
- enabled extensions;
- ChirpStack schema migrations;
- region-file changes;
- codec runtime compatibility;
- MQTT topic prefix;
- Valkey configuration;
- external integration endpoints and credentials.

Do not restore a newer database into an older application image.

## 12.7 Maintenance window preparation

Define:

```text
Start time:
Change owner:
Database owner:
Gateway owner:
Rollback authority:
Expected downtime:
Maximum allowed downtime:
Communication recipients:
Rollback decision deadline:
```

Lower public DNS TTL ahead of the window only when DNS records will change. Confirm local access to the gateway and provider console access to cloud nodes.

## 12.8 Final cutover sequence

### Step 1: Freeze source changes

Prevent administrators from adding/changing devices and integrations. Notify operators that telemetry may be interrupted.

### Step 2: Stop source ChirpStack application processing

Stop source ChirpStack application processing and only the server-side gateway ingress components required by the approved cutover. Leave the gateway's selected radio runtime available for endpoint reconfiguration. Do not start a different gateway transport during the migration.

```bash
cd <SOURCE_COMPOSE_DIR>
docker compose config --services
```

Resolve exact service names and stop only the ChirpStack application and broker components required by the approved plan. This architecture has no server-side Gateway Bridge. Do not stop PostgreSQL before the final dump.

### Step 3: Create the final database dump

```bash
umask 077
docker compose exec -T <SOURCE_POSTGRES_SERVICE> \
  pg_dump -U chirpstack -d chirpstack --format=custom \
  > ~/backups/chirpstack/chirpstack-final-$(date +%Y%m%d-%H%M%S).dump
```

Validate with `pg_restore --list`, checksum, and off-host copy.

### Step 4: Restore into the cloud

Restore only into the verified target database and through the approved primary/admin path. Use `--exit-on-error`. Do not restore over a target containing unreviewed production data.

After restore, compare object and business counts with the source inventory.

### Step 5: Start one cloud ChirpStack node

Review migration logs. Verify users, tenants, applications, profiles, gateways, devices, integrations, and regions before allowing gateway traffic.

### Step 6: Reconfigure Gateway OS MQTT

Follow [11-raspberry-pi-4g-backhaul.md](11-raspberry-pi-4g-backhaul.md).

Keep Gateway OS Base, the Concentratord RAK5146 profile, Gateway ID, approved channel plan, and MQTT Forwarder loopback endpoint unchanged.

MQTT Forwarder remains:

```text
server = tcp://127.0.0.1:1883
qos = 1
backend = concentratord
```

Install the cloud CA and unique gateway certificate under `/etc/mosquitto/certs/`, then update the local Mosquitto bridge address and approved topic prefix in `/etc/mosquitto/mosquitto.conf`. Keep UDP Forwarder disabled.

### Step 6A: Cut over the gateway evidence endpoint without resetting journal history

Run this step only when the gateway-integrity path is deployed.

Before changing the endpoint:

1. create/confirm the latest accepted source-side checkpoint;
2. upload and verify all closed segments when connectivity permits;
3. record the exact checkpoint receipt, sequence, record hash, and segment hash;
4. install the target evidence CA/client identity through the protected gateway procedure;
5. change only the journal uploader endpoint/identity; do **not** reset sequence, segment ID, or previous hash;
6. make the target verifier import/recognize the approved last anchor under the reviewed migration procedure, or explicitly start a new evidence epoch if governance requires one;
7. send a fresh checkpoint/segment and prove it extends the accepted migration anchor.

Do not run two authoritative checkpoint stores that can independently accept conflicting histories for the same gateway without an explicit replication/migration design.

### Step 7: Verify gateway traffic

Observe:

- Gateway OS Concentratord, MQTT Forwarder, local Mosquitto, journal, and uploader health;
- local queue size/drain state plus journal sequence, unuploaded segment backlog, and evidence storage reserve;
- cloud load-balancer TCP connection state, when used;
- broker mutual-TLS identity and exact gateway topics;
- ChirpStack gateway MQTT backend logs and last-seen;
- one real uplink and one safe Class A downlink;
- when enabled, a fresh target-side checkpoint and unique journal -> remote MQTT -> ChirpStack -> trusted-decoder verification result.

### Step 8: Verify the already-commissioned two-node ChirpStack/public path

Phase 9 already commissions both ChirpStack instances and Phase 10 commissions both anchor listeners plus manual Reserved-IP mobility. During cutover, re-check both nodes are healthy and verify the current Reserved-IP owner serves the public endpoints. **Do not repeat host-loss or automatic takeover testing here.**

### Step 9: Validate integrations and downlinks

Confirm webhook/MQTT/database integrations and one safe Class A downlink. A queued downlink is not proof of device receipt.

## 12.9 Session and device behavior

A full database migration can preserve sessions and frame counters when versions and data are compatible. Still verify every critical device class.

A device may need OTAA rejoin when:

- sessions were not migrated;
- root keys or JoinEUI changed;
- frame-counter state is inconsistent;
- MAC/region profile changed;
- security policy requires new sessions.

Do not reset frame counters or regenerate root keys as a troubleshooting shortcut. Confirm the vendor-supported rejoin method and expected battery or access impact before the window.

## 12.10 Prevent dual processing

At no point should the same production gateway publish to two authoritative broker/network-server paths unless a controlled duplicate-handling experiment is explicitly approved.

Before declaring cloud authoritative:

1. verify MQTT Forwarder still points only to the local loopback broker and the local Mosquitto bridge points only to the cloud broker;
2. verify the source application host no longer processes gateway topics;
3. inspect the source Compose services and listeners:

```bash
cd <SOURCE_COMPOSE_DIR>
docker compose ps
sudo ss -lntup
```

Keep source application containers stopped, not deleted, during the rollback window.

## 12.11 Rollback triggers

Examples:

- cloud database restore or migrations fail;
- gateway cannot authenticate or remain connected;
- gateway last-seen does not update within the target;
- devices produce MIC/frame-counter/session errors;
- downlinks fail for an approved test device;
- cloud application/database failover is unstable;
- integrations lose or duplicate data beyond the accepted limit.

## 12.12 Rollback procedure

1. stop both cloud ChirpStack nodes and prevent cloud MQTT command publication;
2. when gateway integrity is enabled, stop accepting new target-side gateway evidence before switching the uploader back, preserve every target checkpoint/segment, and record the last accepted target anchor;
3. restore the previous local Mosquitto bridge endpoint, CA, client certificate, private key, and topic prefix;
4. restore the previous evidence-upload endpoint/identity **without resetting the local journal chain**, using the approved rollback anchor/epoch procedure;
5. restart local Mosquitto without changing MQTT Forwarder's loopback endpoint;
6. start the source broker and ChirpStack services in the documented dependency order;
7. confirm the source database was not modified after the final dump, or reconcile cloud-only changes before rollback;
8. verify source gateway last-seen, one uplink, one safe downlink, and—when enabled—evidence-checkpoint continuity under the rollback procedure;
9. communicate rollback and preserve cloud logs/data/evidence objects for analysis.

Do not run both sides while deciding. Select one authoritative path.

## 12.13 Source decommissioning

After the agreed observation period and a successful cloud backup/restore drill:

- take one final protected source application backup;
- remove live cloud/database secrets from the source application host;
- remove or disable source ChirpStack, PostgreSQL, Valkey/Redis, MQTT broker, Grafana, and Node-RED containers;
- keep the physical gateway on Gateway OS Base with Concentratord, MQTT Forwarder, local persistent Mosquitto, the reviewed integrity journal/uploader, management networking, and approved monitoring;
- verify the source host and gateway listeners independently;
- update asset inventory and diagrams;
- destroy old backups only after the required retention period, legal holds, rollback window, and tested cloud recovery make them unnecessary.

## 12.14 Final checks

- Cloud and source versions were reconciled before restore.
- Final source dump and configuration archives are validated and off-host.
- Source services are stopped during production cloud processing.
- Gateway uses a unique TLS identity over 4G.
- Counts, sessions, real uplinks, and safe downlinks are validated.
- When gateway integrity is enabled, the migration preserves an explicit checkpoint boundary/epoch and one fresh target-side lineage verifies before v2 evidence resumes.
- The rollback procedure and protected source/cloud recovery points remain available during the observation window; failure-injection recovery testing is deferred to Phase 15.

Next required setup phase: [12a-node-red-timescale-telemetry.md](12a-node-red-timescale-telemetry.md).
