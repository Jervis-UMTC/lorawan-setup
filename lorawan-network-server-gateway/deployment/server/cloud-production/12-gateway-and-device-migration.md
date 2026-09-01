# 12. Gateway and Device Migration

> **Status: REQUIRED PRE-TEST SETUP / DRAFT.** Public MQTT normal-path activation and the Phase 13A backup safety checkpoint are available. Do not cut over a gateway or device until the remaining Phase 11 Gateway OS normal-path package/configuration is installed and verified on the physical gateway. For the current non-destructive fast path, the verified off-host logical-backup archive/hash is sufficient; isolated restore and destructive DR proof remain deferred to the later Phase 15 boundary. This is a cutover/provisioning phase, not a chaos phase.

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
- validated logical dumps of `chirpstack` and `lorawan_telemetry` plus the current off-host SHA-256-verified Phase 13A transport archive per [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md); isolated restore rehearsal is deferred until the later destructive/failover boundary for this POC fast path; WAL/base-backup/PITR evidence is required only if that later production backup profile has actually been enabled;
- PgBouncer pooling and HAProxy primary routing;
- Valkey replication + Sentinel automatic failover test;
- MQTT TLS and per-gateway ACL test using a staging identity;
- when v2 gateway integrity is in scope, evidence-ingest mTLS identity, checkpoint conflict rules, read-only gateway MQTT collector, journal/segment verifier, and trusted-decoder staging tests;
- one ChirpStack node and then two-node application test;
- public TLS and load-balancer health;
- the minimal command-line observability/evidence checks required by this POC.

Use a reserved staging gateway/device or synthetic application event. Do not connect the authoritative production-like gateway yet.

**Mandatory Phase 13A boundary:** before the cutover/provisioning window, create the protected database/configuration backup set and copy the transport archive off the target Droplets with a matching destination SHA-256. For the current non-destructive fast path, that checkpoint is sufficient; complete the isolated `lorawan_telemetry` restore rehearsal before Phase 15 destructive/failover testing, not during normal-path commissioning.

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

### Pre-cutover gateway MQTT identity clarification - 2026-08-28

Step 6 below installs the **already-issued and already-server-validated** cloud gateway credential on Gateway OS; it must not be the first time the cloud broker authentication boundary is created. To avoid a circular dependency with Phase 10/11, complete the provider-independent gateway mTLS preparation before the final migration window: commission client-certificate authentication on the gateway-facing cloud `:8884` backend, issue the per-gateway `clientAuth` certificate with CN equal to the authoritative EUI, install the exact-EUI ACL, and prove positive/negative authorization through the existing anchor `:8883` path using the internal broker identity.

The final public FQDN and Reserved IPv4 are **not required** for that preparation. They are required before Step 6 repoints the physical gateway to the Internet-facing broker. During Step 6, install the previously proven cloud CA/client bundle and change the bridge endpoint only after public `mqtt.<DOMAIN>:8883` validates with the broker certificate's public SAN.

### Gateway MQTT cloud client certificate issuance PASS - 2026-08-28

The real physical Gateway EUI `0016c001f139a1cb` now has a dedicated cloud MQTT client identity issued on `ulc-03` from the commissioned internal CA. Issuance directory: `/root/lorawan-pg-ca/gateway-0016c001f139a1cb-issuance-20260828T015149Z`; protected transfer bundle is its `transfer/` subdirectory. The certificate subject is `CN = 0016c001f139a1cb`, issuer `CN = LoRaWAN PostgreSQL Internal CA`, serial `D8732205912F3C3AC56E0A01E1E10583`, validity `2026-08-28 01:51:51Z` through `2027-09-29 01:51:51Z`, SHA-256 fingerprint `82:C6:9A:D7:12:5D:8C:45:F3:8F:BA:AB:F9:6E:7E:3B:41:F4:BE:78:95:FE:16:05:FD:58:2E:09:9D:F3:0A:ED`, and certificate SHA-256 `f348cef6e280dff82722ff908cc96e694faf183eec1dffc55a7abc690cb472d8`.

The certificate chains successfully for `sslclient`, is rejected for `sslserver`, and its public key matches the RSA-3072 private key. The issuing CA SHA-256 remains `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`; the existing CA serial-file SHA-256 remained byte-identical at `50df8c462ef9465ab9198284fa1234f0cbfa4f33eb9779ce6d50dd23a618463d` because issuance used an explicit random serial. `GATEWAY_MQTT_CLIENT_CERT_ISSUANCE=PASS`. No Mosquitto, HAProxy, DNS, firewall, or gateway runtime was changed by issuance.

Next boundary: canary-harden `ulc-01` gateway-facing Mosquitto `:8884` only to require client certificates, map certificate CN to MQTT username, and enforce an exact-EUI `as923` gateway ACL. Preserve ChirpStack `:8885` and Node-RED `:8886`. After `ulc-01` passes direct mTLS verification with the new gateway certificate, repeat the same bounded rollout on `ulc-02`.
### ulc-01 gateway mTLS canary PASS - 2026-08-28

`ulc-01:8884` was hardened from server-TLS-only to gateway client-certificate authentication without changing the ChirpStack `:8885` listener. The active gateway listener now has `require_certificate true`, `use_identity_as_username true`, `allow_anonymous false`, and `/etc/mosquitto/gateway.acl`. The exact Gateway EUI `0016c001f139a1cb` is permitted to write only its own `as923/.../event/#` and `state/#` topics and read only its own `command/#` hierarchy. Mosquitto restarted successfully, `:8884` and `:8885` remained listening, the issued gateway certificate completed TLS and MQTT CONNECT/SUBSCRIBE successfully, and a no-client-certificate connection was rejected. Rollback copy: `/etc/mosquitto/gateway-mtls-20260828T015613Z`. Next boundary: apply the same bounded change to `ulc-02` and prove the same certificate/ACL behavior there before transferring the cloud certificate bundle to Gateway OS.
### ulc-02 gateway mTLS rollout PASS - 2026-08-28

`ulc-02:8884` now matches the proven `ulc-01` gateway-authentication boundary: `require_certificate true`, `use_identity_as_username true`, `allow_anonymous false`, and `/etc/mosquitto/gateway.acl`. Gateway EUI `0016c001f139a1cb` is limited to its own AS923 event/state/command hierarchy. Mosquitto restarted successfully; `:8884` and ChirpStack `:8885` remained listening. The issued gateway certificate completed TLS, MQTT CONNECT, and own-command SUBSCRIBE successfully, while a no-client-certificate connection was rejected. Rollback copy: `/etc/mosquitto/gateway-mtls-20260828T015801Z`. Therefore both cloud MQTT broker backends now enforce the intended per-gateway mTLS identity. Next boundary: transfer only the three-file cloud certificate bundle (`ca.crt`, `0016c001f139a1cb.crt`, `0016c001f139a1cb.key`) to Gateway OS; do not change the working local Mosquitto topology yet.
### ulc-02 gateway mTLS state observed - 2026-08-28

Live read-only inspection after the first rollout wrapper showed `ulc-02` is already in the intended gateway mTLS state: `/etc/mosquitto/conf.d/tls.conf` has `listener 8884`, `require_certificate true`, `allow_anonymous false`, `use_identity_as_username true`, and `acl_file /etc/mosquitto/gateway.acl`; `/etc/mosquitto/gateway.acl` exists as `0640 root:mosquitto`; `per_listener_settings true` remains active; and the dedicated ChirpStack listener remains `10.104.0.4:8885` with its own password/ACL files. Therefore do not reapply the mutation. The remaining boundary is a direct positive mTLS/MQTT proof with gateway certificate CN `0016c001f139a1cb` plus a no-client-certificate rejection proof.
### Both cloud gateway MQTT brokers mTLS acceptance PASS - 2026-08-28

Direct verification from `ulc-03` against `ulc-02:8884` using the issued gateway identity `CN = 0016c001f139a1cb` passed TLS, MQTT CONNECT, and subscription to the gateway's own `as923/gateway/0016c001f139a1cb/command/#` hierarchy. A client without a certificate was rejected. Combined with the earlier `ulc-01` canary proof, both gateway-facing Mosquitto backends now enforce per-gateway mTLS and the exact EUI ACL while preserving the dedicated ChirpStack `:8885` listeners. The cloud broker-side gateway authentication boundary is therefore complete. Next: transfer only `ca.crt`, `0016c001f139a1cb.crt`, and `0016c001f139a1cb.key` from the protected `ulc-03` issuance bundle to Gateway OS; do not alter the local loopback broker topology during certificate import.

### Streamlined Phase 12 entry gate - 2026-08-28

The Phase 13A fast backup checkpoint is now PASS: `phase13a-20260827T032756Z.tar.gz` exists off-host on the Windows administration workstation and its SHA-256 matches the `ulc-03` source (`e97d50c31252ede1fe55b734b6686f270e92ebecb69a36d637b04fbf726cda1c`). Do not repeat database dumps or restore rehearsal during normal-path commissioning.

Phase 12 is no longer blocked by the public MQTT endpoint. `smartagri-mqtt.duckdns.org:8883` through Reserved IPv4 `129.212.208.168` has passed public-name verification, real gateway mTLS CONNECT, and authorized SUBSCRIBE. The gateway-side cloud certificate, exact-EUI ACL, local Mosquitto buffer, SIM7600 QMI data session, and public LTE connectivity are also proven. The remaining cutover boundary is physical Gateway OS access: repoint the bridge, preserve strict TLS/mTLS, prove QoS 1 delivery and application flow, then promote LTE according to Phase 11. Reserved-IP automatic failover remains a separate HA test, not a normal-path blocker.

### Production ChirpStack gateway/device provisioning PASS - 2026-09-01

The cloud ChirpStack 4.19 registry was verified empty before provisioning, then populated through the supported authenticated gRPC API rather than by copying rows from the older ChirpStack 4.9 lab database. Current production objects are:

```text
application:     dissertation-sensors
gateway:         Gateway-01
gateway EUI:     0016c001f139a1cb
device profile:  EMU-01 RAK4631 AS923
device:          dissertation-emu-01
device EUI:      ac1f09fffe296d29
JoinEUI:         0000000000000000
region:          AS923 / region id as923
LoRaWAN MAC:     1.0.2
regional params: B
activation:      OTAA
class:           A
ADR algorithm:   default
expected uplink: 15 seconds
```

The EMU-01 LoRaWAN root key was transferred through protected temporary files and verified byte-for-byte against the previously working lab key without recording or printing the key value. The production JavaScript payload codec was likewise verified byte-for-byte against the reviewed payload-v2 decoder. SEC-02 remains intentionally outside the permanent production registry as a security/test fixture. The temporary global ChirpStack provisioning API key was revoked after provisioning and its protected on-host token file was removed. `PRODUCTION_CHIRPSTACK_REGISTRY=PASS` is authoritative; tomorrow's remaining acceptance requires the real flashed gateway and EMU-01 radio uplink, not more server object creation.
