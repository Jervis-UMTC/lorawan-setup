# 13. Minimal POC Backup and Recovery

> **Status: REQUIRED PRE-TEST CHECKPOINTS / DRAFT.** Use this manual twice before Phase 15: **Phase 13A** creates the pre-cutover safety boundary before authoritative gateway/device onboarding; **Phase 13B** creates the final full-stack snapshot after Node-RED, Grafana, OpenBao, and Fabric are commissioned. Recovery procedures are documented here, but intentional destructive recovery tests belong to Phase 15.

This HA POC is **not** trying to prove a production disaster-recovery platform. It still needs a real rollback boundary before we deliberately kill leaders, members, and hosts.

> **HA-preserving scope boundary:** Phase 13 does not authorize removing or bypassing any commissioned HA component. Patroni/Spilo, etcd, HAProxy, PgBouncer, Valkey/Sentinel, MQTT redundancy, and the two-node ChirpStack design remain part of the active system. For normal functional commissioning, use the already-passed live HA health/routing evidence plus the fresh validated local logical dumps created on 2026-08-27. The more rigorous off-Droplet copy and isolated-restore rehearsal may be deferred until the dedicated destructive/failure-injection boundary unless a new failure signal, migration risk, or operator requirement makes them immediately necessary. Do not confuse "defer rigorous DR proof" with "remove HA".

The rule is simple:

> Do not inject a destructive failure until the fully commissioned state needed to rebuild the POC exists outside the three target Droplets and the required isolated restore checks have passed.

## 13.0 Two mandatory backup checkpoints

### Phase 13A - before gateway/device cutover

Normally complete after Phase 11 and before Phase 12. If the physical gateway is temporarily unavailable, the **cloud-only 13A checkpoint may be executed and closed first** because it does not mutate gateway state: protect the commissioned cloud databases/configuration, copy the backups off the target Droplets, validate catalogs/checksums, and complete an isolated `lorawan_telemetry` restore with Timescale objects intact. When a legacy authoritative source exists, protect that source independently as part of the migration plan. Phase 12 still requires both Phase 11 normal-path commissioning and Phase 13A PASS; finishing 13A early does not waive the gateway prerequisite.

**13A PASS permits Phase 12 cutover/provisioning. It does not permit Phase 15 fault injection.**

### Phase 13B - after every pre-test service is commissioned

Re-run the backup collection after Phase 12A, Phase 14A, and Phase 20. Include Node-RED flow/config, Grafana dashboard/data-source exports, OpenBao recovery/Raft snapshot material, Fabric adapter image/config references, public-ingress scripts/units, and the final database state.

**13B PASS is one prerequisite of Phase 14B.** The backup identifier used by Phase 15 must refer to this fully commissioned snapshot, not an earlier partial build.

## 13.1 What to protect

Before destructive tests keep copies of:

```text
chirpstack logical database dump
lorawan_telemetry logical database dump
etcd cluster snapshot + member/config record
OpenBao recovery/unseal material outside the runtime hosts
OpenBao Raft snapshot before destructive KMS recovery tests
HAProxy/PgBouncer configs
public-ingress failover scripts + systemd units/timer
Reserved IPv4 + ha-01/ha-02 Droplet IDs + anchor IPv4 record
ChirpStack configs/region files
Mosquitto configs/ACLs
Valkey/Sentinel configs
Node-RED flow export
Grafana dashboard export
Fabric handoff metadata
Fabric adapter config/image reference when an implementation exists
```

Do not create paid object storage only because a future production design normally would. For this POC, the administration workstation or another protected system outside `ha-01/02/03` is sufficient as the off-host copy.



### Current Phase 13A preflight result - 2026-08-27

The cloud-only read-only preflight is **PASS**. The initial checker falsely treated missing ulc-03 `:16379` and `:18883` listeners as failures. Those frontends are intentionally application-node-only: Valkey writable-primary HAProxy is commissioned on ulc-01/02, and the ChirpStack workload MQTT HAProxy frontends are commissioned on ulc-01/02. Do not deploy either frontend on ulc-03. Patroni, etcd, all required database routes, both ChirpStack application nodes, PostgreSQL/TimescaleDB state, telemetry hypertables/schema state, backup tools, and local backup capacity passed. Continue with fresh Phase 13A dumps.

The first fresh-dump wrapper then stopped safely before creating either dump because it required `host(inet_server_addr()) = 10.104.0.8` while `psql` was using the local Unix-domain socket inside the Spilo container. On a Unix-socket PostgreSQL session `inet_server_addr()` is `NULL`, so the observed `|t` means only `pg_is_in_recovery() = true`; it is not evidence of a wrong node. For local-container backup work, verify the host identity outside SQL and require only replica state from PostgreSQL, or explicitly connect by TCP if the server address itself is part of the assertion. Reuse the existing timestamped directory only if it contains no dump artifacts; otherwise create a new timestamped directory.

## 13.2 Create one protected backup directory

Run on the host from which backups are being collected:

```bash
umask 077
BACKUP_DIR="$HOME/backups/lorawan-ha-poc-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
printf '%s\n' "$BACKUP_DIR"
```

Store the test/run identifier beside the backup so later evidence shows which failure rehearsal it protected.

Do not put database passwords, private keys, or OpenBao recovery material in the general command transcript.

## 13.3 PostgreSQL logical dumps through the stable HA path

Both logical databases live on the same Patroni cluster:

```text
chirpstack
lorawan_telemetry [TimescaleDB enabled]
```

Use a protected backup/admin role that can read the required database objects. Connect through the local PgBouncer/HAProxy route or an explicitly verified current-primary admin route.

If using PgBouncer, first confirm `<BACKUP_ROLE>` is actually admitted by the configured `auth_file`/`auth_query` and can connect to **both** logical databases. Do not weaken PgBouncer authentication just to make a backup work. If the backup role is intentionally excluded from PgBouncer, use a separately approved TLS-verified current-primary administration path and record that exception.

Example using the stable pool path:

```bash
pg_dump \
  --host=pgbouncer.internal.lorawan.com \
  --port=6432 \
  --username=<BACKUP_ROLE> \
  --dbname=chirpstack \
  --format=custom \
  --file="$BACKUP_DIR/chirpstack.dump"

pg_dump \
  --host=pgbouncer.internal.lorawan.com \
  --port=6432 \
  --username=<BACKUP_ROLE> \
  --dbname=lorawan_telemetry \
  --format=custom \
  --file="$BACKUP_DIR/lorawan_telemetry.dump"
```

Provide authentication through the approved protected mechanism such as `.pgpass`, a short-lived credential source, or an interactive prompt. Do not put the live password in the command line.

Immediately validate both catalogs:

```bash
pg_restore --list "$BACKUP_DIR/chirpstack.dump" >/dev/null
pg_restore --list "$BACKUP_DIR/lorawan_telemetry.dump" >/dev/null
sha256sum "$BACKUP_DIR/chirpstack.dump" "$BACKUP_DIR/lorawan_telemetry.dump" \
  | tee "$BACKUP_DIR/SHA256SUMS"
```

**Stop here** if either `pg_restore --list` fails or either dump is zero bytes.

Why both dumps matter: `lorawan_telemetry` contains the Timescale hypertables and the current application schema. `telemetry.fabric_outbox` is included **only after it has actually been commissioned** by the later Node-RED/Fabric setup. At the current pre-Phase-12A 13A checkpoint, preserve the live source state exactly; do not create an outbox merely to make the backup match the future target architecture.


### Current Phase 13A fresh logical backup result - 2026-08-27

The corrected fresh-backup retry is **PASS** on `ulc-03`. Host identity was verified outside PostgreSQL and the local Spilo member returned `pg_is_in_recovery() = true`. Both `chirpstack` and `lorawan_telemetry` exist. Source metadata recorded PostgreSQL `18.6`, ChirpStack counts `tenant=1, application=0, device_profile=0, device=0, gateway=0`, telemetry counts `uplinks=0, measurements=0, device_registry=0`, TimescaleDB `2.29.2`, hypertables `measurements,uplinks`, and `fabric_outbox_count=0`. Fresh custom-format dumps were created under `/home/opsadmin/backups/phase13a-20260827T032756Z`: `chirpstack.dump` about 99 KiB and `lorawan_telemetry.dump` about 58 KiB. Both archives passed `pg_restore --list`; `SOURCE-METADATA.txt`, both dumps, and `SHA256SUMS` are mode `0600`; `sha256sum -c SHA256SUMS` passed for all three hashed files. The TimescaleDB `continuous_agg` circular-foreign-key warning is expected for this full custom-format dump and does not invalidate the archive; the isolated restore rehearsal remains the authoritative restore proof. The database-backup sub-gate is therefore complete locally, but Phase 13A remains open until this directory is copied off the target Droplets and destination hashes are verified.

## 13.4 Copy PostgreSQL backups off the three Droplets

If the backup was created on `ha-01`, `ha-02`, or `ha-03`, copy the entire protected backup directory to the administration workstation or another approved off-host location before the destructive test.

Then recalculate the checksums at the destination and compare with `SHA256SUMS`.

A dump that exists only on a Droplet scheduled for failure is not a useful rollback copy.

## 13.5 etcd snapshot before destructive coordination tests

For a normal single-member loss, the preferred recovery is to restore/rejoin the missing member using the normal etcd member procedure. A cluster snapshot is still mandatory safety evidence before deliberately changing membership or performing a destructive quorum-recovery test.

Using a compatible `etcdctl` against the currently tested east-west endpoints:

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint health

ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379 \
  snapshot save "$BACKUP_DIR/etcd.snapshot"
```

These commands match the current HTTP-only etcd deployment on `10.104.0.0/20`. If etcd transport TLS is deployed later, update this procedure and use the tested CA/client credentials; do not mix the two transport modes.

Inspect the snapshot using the status command supported by the pinned etcd release (`etcdutl snapshot status` on releases that use `etcdutl`). Record:

```text
etcd member list
cluster ID
member IDs / names / peer URLs
snapshot hash/revision/status
```

The etcd snapshot contains coordination state, not PostgreSQL rows.

## 13.6 OpenBao recovery material and Raft snapshot

Keep Shamir/recovery/unseal material **outside** `ha-01/02/03` and outside the general configuration archive.

Before an OpenBao failure rehearsal record:

```text
member list
active node
sealed/unsealed state
Raft health
Transit mount
lorawan-evidence key metadata
```

Before a test that can damage Raft state, use a privileged backup identity—not the Fabric adapter—to create the approved snapshot, for example with the pinned CLI:

```bash
bao operator raft snapshot save "$BACKUP_DIR/openbao.snap"
```

Then copy that snapshot off the three Droplets and retain the protected recovery material needed to restore/unseal the cluster.

The Fabric adapter must not receive root, recovery, or snapshot privileges.

## 13.7 Configuration snapshot

Capture the non-secret configuration that would be needed to reconstruct the scale model:

```text
HAProxy
PgBouncer
public-ingress scripts and systemd service/timer units
Reserved IPv4, ha-01/ha-02 Droplet IDs, anchor IPv4s, and expected initial/current owner
public-ingress health/takeover/evaluator script hashes
Patroni/Spilo non-secret config and image digest
etcd member/config and pinned version
Mosquitto config + ACL + image digest
Valkey/Sentinel config + image digest
ChirpStack region/config files + image digest
Node-RED flow export + palette versions
Grafana dashboard/data-source export
OpenBao server config + version
Fabric handoff metadata
Fabric adapter non-secret config/image digest when available
```

Keep private keys/passwords in their designated protected recovery location, not in a general tar archive. In particular, do **not** copy the live `DIGITALOCEAN_TOKEN` from `/etc/lorawan-cloud/public-ingress.env` into the ordinary configuration bundle. Record its secret-store reference and required permission scope, then restore the token separately through the approved secret workflow.

## 13.8 Isolated PostgreSQL restore rehearsal

Do this before the first destructive HA test and after any PostgreSQL-major/TimescaleDB change.

Use a temporary target that has:

```text
same compatible PostgreSQL major
same required TimescaleDB extension build available
no production data
no connection from live ChirpStack/Node-RED/Fabric adapters
```

Procedure:

1. create a temporary empty PostgreSQL instance/database outside the live three-node cluster when possible;
2. verify the TimescaleDB extension files are available for the selected PostgreSQL major;
3. create/enable the extension as required by the restore procedure;
4. run `pg_restore --list lorawan_telemetry.dump` again on the restore host;
5. restore with `--exit-on-error`;
6. query `pg_extension` and confirm `timescaledb` is present;
7. query `timescaledb_information.hypertables` and confirm `telemetry.uplinks` and `telemetry.measurements` are hypertables;
8. compare `telemetry.fabric_outbox` with the recorded source state: if the source backup contains it, confirm it restores as an ordinary table; if the source records it as not-yet-commissioned, confirm it remains absent rather than creating it during restore;
9. compare the small POC row counts with the source evidence;
10. verify the `telemetry_reader`/writer ownership/grants needed by the restored schema;
11. capture the sanitized restore result;
12. destroy the temporary restore target after the evidence is retained.

Do not call a backup tested merely because `pg_dump` exited zero. The restore rehearsal is what proves the dump is usable.

## 13.9 Outbox recovery rule

After restoring `lorawan_telemetry`:

```text
1. keep both Fabric adapters stopped
2. start only adapter-1
3. inspect pending / processing / submitted_unknown / confirmed rows
4. release or wait out only leases proven stale
5. reconcile submitted_unknown against external Fabric commit status
6. verify no row is falsely marked confirmed
7. only then start adapter-2
```

Why: a Fabric transaction may have committed even when the client timed out. Blind replay can create duplicate/conflicting work.

If the adapter implementation is not yet available, preserve the outbox and mark this operational step blocked rather than pretending reconciliation has been tested.

## 13.10 What is deliberately deferred

Not required to pass the **structural HA POC**:

```text
WAL-G
continuous WAL archiving
PITR
paid object storage
multi-region backup replication
long production retention schedules
production RPO/RTO certification
```

These are future deployment hardening, not reasons to remove Patroni, TimescaleDB, OpenBao, or the outbox from the POC.

## 13.11 Phase 13A pass condition

Phase 13A passes before Phase 12 when:

- current `chirpstack` and `lorawan_telemetry` logical dumps exist outside the target Droplets;
- dump catalogs parse and checksums match the off-host copies;
- an isolated `lorawan_telemetry` restore succeeds with Timescale hypertables/constraints intact;
- the current etcd snapshot/member/config record exists off-host;
- current non-secret HAProxy/PgBouncer/Mosquitto/Valkey/ChirpStack configuration references are captured;
- when a legacy source exists, its final migration backup procedure and off-host destination are ready.

After **13A PASS**, continue to [12-gateway-and-device-migration.md](12-gateway-and-device-migration.md) only when Phase 11 has also passed. If Phase 11 is still hardware-blocked, keep the 13A evidence as the current rollback checkpoint and resume Phase 11 when the gateway becomes available. Do not start fault injection.

## 13.12 Phase 13B final full-stack snapshot

After Node-RED, Grafana, OpenBao, and the Fabric adapters have passed their normal-path setup, repeat the backup collection and add:

```text
Node-RED flow export + image/palette/config references
Grafana dashboard/data-source export without credentials
OpenBao recovery material protected off-host
OpenBao Raft snapshot + version/member record
Fabric adapter immutable image/source reference + worker IDs/config reference
Fabric external handoff metadata + last normal confirmed tx reference
public-ingress Reserved IPv4/Droplet/anchor worksheet
public-ingress script/systemd hashes and protected token reference
final schema/migration/outbox state
final service image/config hashes needed to recreate the tested baseline
```

Re-check the database dumps and isolated restore against the final schema. Phase 13B must not rely only on the earlier 13A archives because the application/outbox state has changed.

**Phase 13B PASS does not itself authorize fault injection.** Next run the healthy evidence-harness dry run in [14-observability-alerting-and-logging.md](14-observability-alerting-and-logging.md), then the hard gate in [14b-pre-test-commissioning-gate.md](14b-pre-test-commissioning-gate.md).
