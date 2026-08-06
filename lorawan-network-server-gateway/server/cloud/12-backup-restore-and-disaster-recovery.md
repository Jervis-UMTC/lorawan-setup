# 12. Backup, Restore, and Disaster Recovery

## 12.1 Principles

- Replication is not a backup.
- A backup is not trusted until its catalog, checksum, encryption, off-host copy, and isolated restore have been verified.
- PostgreSQL data, etcd state, Valkey state, MQTT configuration, ChirpStack configuration, PKI, secrets, and infrastructure state are different recovery assets.
- Never test a restore by overwriting production.
- Recovery documentation must work when the original region or account access path is unavailable.

## 12.2 Define recovery objectives

For each asset, choose the maximum acceptable data loss (**RPO**), maximum acceptable recovery time (**RTO**), the person or team able to perform the restore, and a test frequency that proves the objective before it is needed:

| Asset | RPO | RTO | Recovery responsibility | Restore test frequency |
|---|---:|---:|---|---|
| ChirpStack PostgreSQL | `<RPO>` | `<RTO>` | Database owner | `<FREQUENCY>` |
| etcd/Patroni DCS | `<RPO>` | `<RTO>` | Platform owner | `<FREQUENCY>` |
| ChirpStack configuration | `<RPO>` | `<RTO>` | Application owner | `<FREQUENCY>` |
| MQTT configuration/ACLs | `<RPO>` | `<RTO>` | Messaging owner | `<FREQUENCY>` |
| Gateway configuration/PKI | `<RPO>` | `<RTO>` | Gateway owner | `<FREQUENCY>` |
| Infrastructure state | `<RPO>` | `<RTO>` | Cloud owner | `<FREQUENCY>` |
| Managed Valkey | `<RPO>` | `<RTO>` | Application owner | Provider capability test |

## 12.3 Backup storage design

Use a private object-storage bucket dedicated to backup data.

Required controls:

- scoped access key that can access only the required bucket/prefix;
- encryption in transit and at rest;
- object versioning or retention/immutability where available and approved;
- separate administrative permission for lifecycle deletion;
- access logs and alerts;
- lifecycle rules that preserve complete restore chains;
- off-region or independent-account copy for regional/provider-account disasters;
- tested restoration when the primary account credential is unavailable.

Do not place the only backup credentials inside the same environment being recovered.

## 12.4 PostgreSQL physical backups with WAL-G

Spilo commonly integrates WAL-G. Confirm the exact built image configuration and object endpoint.

Keep the WAL-G version, bucket/prefix, base-backup schedule, maximum WAL archive delay, retention rule, encryption method, most recent successful base backup, most recent archived WAL time, and isolated restore target. Together these values describe whether the current restore chain can meet the RPO; an object count alone does not.

Verify from a database member without printing credentials:

```bash
sudo docker exec spilo env | grep -E '^(WALG_|WALE_|AWS_)' | sed 's/=.*$/=<redacted>/'
sudo docker logs --since=24h spilo | grep -iE 'wal|backup|archive' | tail -100
```

Use the image's documented `wal-g backup-list` and `backup-push` commands. Do not invent paths; inspect the container image and environment.

Healthy evidence:

- recent successful base backup;
- continuous WAL arrival;
- no increasing archive backlog;
- object checksums/metadata;
- restore from base backup plus WAL to a requested point in time.

## 12.5 Logical PostgreSQL backups

Physical backups support cluster recovery; logical dumps provide an independent application-level export.

Create a protected custom-format dump through the active primary/admin path:

```bash
install -d -m 700 ~/backups/chirpstack-logical
umask 077
pg_dump \
  --host=127.0.0.1 \
  --port=5432 \
  --username=<BACKUP_ROLE> \
  --dbname=chirpstack \
  --format=custom \
  --file=~/backups/chirpstack-logical/chirpstack-$(date +%Y%m%d-%H%M%S).dump
```

Use `.pgpass`, a short-lived token, client certificate, or another approved protected mechanism. Do not put a password in the command.

Validate:

```bash
pg_restore --list ~/backups/chirpstack-logical/<DUMP_FILE> | head -50
sha256sum ~/backups/chirpstack-logical/<DUMP_FILE>
stat -c '%a %s %n' ~/backups/chirpstack-logical/<DUMP_FILE>
```

Encrypt and copy off-host.

## 12.6 etcd snapshots

Follow [06-etcd-cluster.md](06-etcd-cluster.md). Take a snapshot from a healthy endpoint, validate with `etcdutl snapshot status`, checksum it, and copy it off-host.

The etcd snapshot contains Patroni coordination state, not PostgreSQL rows. Restoring etcd without matching PostgreSQL reality can create dangerous stale leadership information. Recover normal quorum when possible; use snapshot disaster recovery only with the database/platform owners present.

## 12.7 Configuration archives

Archive only approved files and preserve permissions:

```text
Infrastructure-as-code source and locked provider versions
Protected infrastructure state backup
ChirpStack configuration and region files
HAProxy and PgBouncer configurations
Spilo Compose and non-secret configuration
etcd configuration and member inventory
MQTT broker configuration and ACLs
Monitoring rules and dashboards
Gateway OS Base version, factory image filename, source URL, image SHA-256, package inventory, and license notices
Sanitized Gateway OS UCI configuration export and configuration-archive checksum
Encrypted gateway MQTT identity recovery reference, certificate fingerprint, expiry, broker endpoint, and topic prefix
Gateway management-firewall and 4G connection exports
```

Secrets and private keys should be backed up through the approved secret-management/PKI recovery system, not mixed casually into a general tar archive.

Create a manifest containing path, SHA-256, owner, mode, and software version. Test reconstruction on clean hosts.

## 12.8 Managed Valkey recovery

Review the provider's current backup, point-in-time recovery, replica, maintenance, and export capabilities. State exactly which keys, persistence guarantees, and recovery points survive failover or deletion so the ChirpStack recovery procedure does not assume unavailable state.

Do not assume Valkey can be rebuilt without impact. Document whether ChirpStack can recreate required state and what device/session consequences may occur.

Protect against accidental cluster deletion with provider role separation and deletion safeguards where available.

## 12.9 MQTT recovery

Back up:

- broker configuration;
- TLS trust and server certificate references;
- ACL source;
- account/client inventory without live passwords;
- load-balancer health configuration;
- product license and cluster membership information;
- persistent-session/retained-state backup when the selected broker uses them.

For stateless active/standby Mosquitto, recovery rebuilds the broker configuration but does not recreate lost in-flight session state. This limitation must remain in the recovery plan.

## 12.10 Isolated PostgreSQL restore test

Use new hosts, a separate VPC/subnet, or an isolated local environment with no route from production gateways.

Procedure:

1. select an approved base backup and target time;
2. provision new database storage;
3. deploy the exact compatible Spilo image;
4. restore physical backup and WAL according to the pinned Spilo/WAL-G procedure;
5. start PostgreSQL without allowing production application traffic;
6. verify timeline, recovery target, schema, users, tenant/application/device counts, and checksums/sample queries;
7. deploy one isolated ChirpStack instance with disabled outbound integrations;
8. verify login and read-only application behavior;
9. compare the measured restore duration and any deviations with the stated RTO;
10. destroy only the verified disposable environment after evidence is retained.

Do not reuse production MQTT identities or send downlinks during a restore test.

## 12.11 Logical restore test

Create a new empty database:

```bash
createdb --host=<ISOLATED_PRIMARY> --username=<ADMIN_ROLE> chirpstack_restore_test
pg_restore \
  --host=<ISOLATED_PRIMARY> \
  --username=<ADMIN_ROLE> \
  --dbname=chirpstack_restore_test \
  --exit-on-error \
  <LOGICAL_DUMP_FILE>
```

Verify object counts, ownership, extensions, constraints, and application reads. Drop only the confirmed test database.

## 12.12 Point-in-time recovery

Before using PITR, identify the exact target timestamp and timezone, the last known good transaction or event, selected base backup, required WAL range, and expected loss of writes after the target. Tie the recovery to the incident or change that defines why that point is correct.

Recover into a new cluster first. Compare with the damaged production cluster and reconcile business impact. Do not rewind the only production copy in place without an independent verified backup.

## 12.13 Regional disaster recovery

A complete regional DR procedure must be able to create:

1. replacement VPC and firewall rules;
2. three-member etcd cluster or a carefully recovered DCS;
3. three-member Spilo/Patroni cluster from object backups;
4. Managed Valkey replacement and required state recovery;
5. MQTT endpoint and gateway identities;
6. two ChirpStack nodes;
7. DNS/load-balancer endpoints;
8. monitoring and alerting;
9. controlled gateway endpoint cutover.

Keep provider region-specific names, quotas, certificate issuance, DNS control, and object-storage replication in the plan.

Do not change gateway RF configuration during a cloud-region recovery.

## 12.14 Backup monitoring

Alert on:

- last successful base backup age;
- last archived WAL age;
- WAL archive errors or increasing backlog;
- logical dump age and size anomaly;
- etcd snapshot age;
- object-storage access denial;
- lifecycle deletion of protected restore chains;
- checksum mismatch;
- restore test overdue;
- certificate/secret recovery material expiry.

## 12.15 Final checks

- Physical, logical, etcd, configuration, and infrastructure backups have an identified restore procedure and responsible team.
- Backups are encrypted, checksummed, off-host, and protected from routine operators.
- WAL/base and logical restores succeed in isolation.
- PITR is demonstrated to a selected timestamp.
- Regional DR build order and DNS/gateway cutover are rehearsed.
- Measured RPO/RTO meet or explicitly fail the approved objectives.

Next: [13-observability-alerting-and-logging.md](13-observability-alerting-and-logging.md)
