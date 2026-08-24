# 13. Minimal POC Backup and Recovery

> **Status: STANDBY / DRAFT.** The final backup set cannot be fixed until the dependent services are actually deployed. Keep the etcd guidance aligned with the validated cluster, but re-check PostgreSQL, OpenBao, application, and configuration backup commands as each technology becomes active.

This HA POC is **not** trying to prove a production disaster-recovery platform. It still needs a real rollback boundary before we deliberately kill leaders, members, and hosts.

The rule is simple:

> Do not inject a destructive failure until the state needed to rebuild the POC exists somewhere outside the three target Droplets and at least the PostgreSQL dump has been read/restore-tested.

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

Why both dumps matter: `lorawan_telemetry` contains the Timescale hypertables **and** `telemetry.fabric_outbox`.

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
8. confirm `telemetry.fabric_outbox` exists as an ordinary table;
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

## 13.11 Destructive-test go/no-go

Proceed only when all are true:

- `chirpstack.dump` and `lorawan_telemetry.dump` exist outside the target Droplets;
- both dump catalogs are readable and checksums match the off-host copies;
- at least one isolated `lorawan_telemetry` restore has succeeded with Timescale hypertables intact;
- an etcd snapshot/member record exists before destructive etcd membership testing;
- OpenBao recovery/unseal material is protected outside the runtime nodes;
- an OpenBao Raft snapshot exists before destructive KMS recovery testing;
- the configuration/image references required to rebuild the POC are recorded;
- the Reserved IPv4, app Droplet IDs, anchor addresses, public-ingress script/unit hashes, and failover-token secret reference are recorded off-host;
- both app-host anchor listeners have passed local health and one manual Reserved-IP move has been proven before automatic public-ingress failure testing;
- the Fabric outbox recovery state machine is understood, even if adapter execution is currently blocked by a missing implementation.

Next: [14-observability-alerting-and-logging.md](14-observability-alerting-and-logging.md).
