# 11. Gateway and Device Migration

This guide covers migration from an older all-in-one or server-hosted ChirpStack deployment to the current cloud architecture. The `source` host is the machine that currently runs ChirpStack and its Compose project; it is not the Gateway OS Base appliance described elsewhere in this repository. Set `<SOURCE_COMPOSE_DIR>` to the directory containing that source host's active Compose file; older deployments often placed it under the administrator's home directory. Confirm it with `docker compose ls`, the running container labels, or the service administrator before using the commands below. to the Cloud

## 11.1 Goal

Move the existing ChirpStack state from the Raspberry Pi to the cloud without running two authoritative network servers for the same gateway and devices. Preserve tenants, applications, profiles, gateways, devices, root keys, sessions, frame counters, and integration settings when technically compatible.

## 11.2 Migration strategy decision

Choose one:

### Full ChirpStack database migration

Use when source and target versions are compatible and preserving sessions/frame counters is important. This minimizes device reprovisioning but requires careful version and schema matching.

### Recreate configuration and rejoin devices

Use when the source database is incompatible, small enough to rebuild, or security policy requires new root keys/sessions. This creates more field work and must account for battery devices and physical access.

Do not partially copy tables by hand. Use supported database migration or explicit reprovisioning.

## 11.3 Source inventory

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

## 11.4 Back up and identify the source state

Create a protected custom-format ChirpStack PostgreSQL dump and configuration archive using the logical-backup controls in [12-backup-restore-and-disaster-recovery.md](12-backup-restore-and-disaster-recovery.md). Back up the physical gateway separately with [Gateway Backup and Recovery](../../gateway/operations/02-backup-and-recovery.md). Validate the dump catalog, calculate its checksum, and copy both backup sets off their source systems.

Keep the source ChirpStack image/version, PostgreSQL major/version, schema or migration state, active region-file hashes, Gateway EUI, Concentratord channel plan, effective MQTT region prefix, and last successful uplink time. These values let the target be compared with the authoritative source without copying live root keys into documentation.

**Stop here. Do not cut over** if the source backup is unreadable, exists only on the source host, or the target restore has not succeeded in staging.

## 11.5 Build and validate the cloud before migration

The cloud environment must pass:

- etcd quorum and snapshot test;
- Patroni cluster, replication, and switchover test;
- WAL/base backup and isolated restore;
- HAProxy and PgBouncer routing;
- Managed Valkey failover test;
- MQTT TLS and per-gateway ACL test using a staging identity;
- one ChirpStack node and then two-node application test;
- public TLS and load-balancer health;
- monitoring and alerts.

Use a reserved staging gateway/device or synthetic application event. Do not connect the production gateway yet.

## 11.6 Version compatibility

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

## 11.7 Maintenance window preparation

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

## 11.8 Final cutover sequence

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

Follow [05-raspberry-pi-4g-backhaul.md](05-raspberry-pi-4g-backhaul.md).

Keep Gateway OS Base, the Concentratord RAK5146 profile, Gateway ID, approved channel plan, and MQTT Forwarder loopback endpoint unchanged.

MQTT Forwarder remains:

```text
server = tcp://127.0.0.1:1883
qos = 1
backend = concentratord
```

Install the cloud CA and unique gateway certificate under `/etc/mosquitto/certs/`, then update the local Mosquitto bridge address and approved topic prefix in `/etc/mosquitto/mosquitto.conf`. Keep UDP Forwarder disabled.

### Step 7: Verify gateway traffic

Observe:

- Gateway OS Concentratord, MQTT Forwarder, and local Mosquitto logs;
- local queue size and drain state;
- cloud load-balancer TCP connection state, when used;
- broker mutual-TLS identity and exact gateway topics;
- ChirpStack gateway MQTT backend logs and last-seen;
- one real uplink and one safe Class A downlink.

### Step 8: Start the second cloud ChirpStack node

Add it to the load balancer only after independent health checks pass.

### Step 9: Validate integrations and downlinks

Confirm webhook/MQTT/database integrations and one safe Class A downlink. A queued downlink is not proof of device receipt.

## 11.9 Session and device behavior

A full database migration can preserve sessions and frame counters when versions and data are compatible. Still verify every critical device class.

A device may need OTAA rejoin when:

- sessions were not migrated;
- root keys or JoinEUI changed;
- frame-counter state is inconsistent;
- MAC/region profile changed;
- security policy requires new sessions.

Do not reset frame counters or regenerate root keys as a troubleshooting shortcut. Confirm the vendor-supported rejoin method and expected battery or access impact before the window.

## 11.10 Prevent dual processing

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

## 11.11 Rollback triggers

Examples:

- cloud database restore or migrations fail;
- gateway cannot authenticate or remain connected;
- gateway last-seen does not update within the target;
- devices produce MIC/frame-counter/session errors;
- downlinks fail for an approved test device;
- cloud application/database failover is unstable;
- integrations lose or duplicate data beyond the accepted limit.

## 11.12 Rollback procedure

1. stop both cloud ChirpStack nodes and prevent cloud MQTT command publication;
2. restore the previous local Mosquitto bridge endpoint, CA, client certificate, private key, and topic prefix;
3. restart local Mosquitto without changing MQTT Forwarder's loopback endpoint;
4. start the source broker and ChirpStack services in the documented dependency order;
5. confirm the source database was not modified after the final dump, or reconcile cloud-only changes before rollback;
6. verify source gateway last-seen, one uplink, and one safe downlink;
7. communicate rollback and preserve cloud logs/data for analysis.

Do not run both sides while deciding. Select one authoritative path.

## 11.13 Source decommissioning

After the agreed observation period and a successful cloud backup/restore drill:

- take one final protected source application backup;
- remove live cloud/database secrets from the source application host;
- remove or disable source ChirpStack, PostgreSQL, Valkey/Redis, MQTT broker, Grafana, and Node-RED containers;
- keep the physical gateway on Gateway OS Base with Concentratord, MQTT Forwarder, local persistent Mosquitto, management networking, and approved monitoring;
- verify the source host and gateway listeners independently;
- update asset inventory and diagrams;
- destroy old backups only after the required retention period, legal holds, rollback window, and tested cloud recovery make them unnecessary.

## 11.14 Final checks

- Cloud and source versions were reconciled before restore.
- Final source dump and configuration archives are validated and off-host.
- Source services are stopped during production cloud processing.
- Gateway uses a unique TLS identity over 4G.
- Counts, sessions, real uplinks, and safe downlinks are validated.
- Rollback was demonstrated in staging and remains possible during the observation window.

Next: [12-backup-restore-and-disaster-recovery.md](12-backup-restore-and-disaster-recovery.md)
