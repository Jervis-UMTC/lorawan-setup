# 13. Minimal POC Backup and Recovery

> **Status: 13A FAST-PATH PASS / 13S SERVER-ONLY SNAPSHOT MAY PROCEED / 13B FINAL LATER.** Phase 13A already protects the pre-cutover cloud state. While hardware/provider/Fabric dependencies are unavailable, an interim **13S server-only snapshot/export** may capture the currently commissioned server baseline so backup/export tooling is proven early. **13S is not the final Phase 13B backup set.** Phase 13B must still be recreated after every required pre-test service and real application path are commissioned. Intentional destructive recovery tests belong to Phase 15.

This HA POC is **not** trying to prove a production disaster-recovery platform. It still needs a real rollback boundary before we deliberately kill leaders, members, and hosts.

> **HA-preserving scope boundary:** Phase 13 does not authorize removing or bypassing any commissioned HA component. Patroni/Spilo, etcd, HAProxy, PgBouncer, Valkey/Sentinel, MQTT redundancy, and the two-node ChirpStack design remain part of the active system. For normal functional commissioning, use the already-passed live HA health/routing evidence plus the fresh validated local logical dumps created on 2026-08-27. The more rigorous off-Droplet copy and isolated-restore rehearsal may be deferred until the dedicated destructive/failure-injection boundary unless a new failure signal, migration risk, or operator requirement makes them immediately necessary. Do not confuse "defer rigorous DR proof" with "remove HA".

The rule is simple:

> Do not inject a destructive failure until the fully commissioned state needed to rebuild the POC exists outside the three target Droplets and the required isolated restore checks have passed.

## 13.0 Two mandatory backup checkpoints

### Phase 13A - before gateway/device cutover

Normally complete after Phase 11 and before Phase 12. If the physical gateway is temporarily unavailable, the **cloud-only 13A checkpoint may be executed and closed first** because it does not mutate gateway state: protect the commissioned cloud databases/configuration, copy the backups off the target Droplets, validate catalogs/checksums, and complete an isolated `lorawan_telemetry` restore with Timescale objects intact. When a legacy authoritative source exists, protect that source independently as part of the migration plan. Phase 12 still requires both Phase 11 normal-path commissioning and Phase 13A PASS; finishing 13A early does not waive the gateway prerequisite.

**13A PASS permits Phase 12 cutover/provisioning. It does not permit Phase 15 fault injection.**

### Phase 13S - interim server-only snapshot/export while external dependencies are deferred

13S exists only to remove avoidable server-side work from the final commissioning day. It may run now against the commissioned server components and should capture non-secret reconstruction material for etcd, PostgreSQL/Patroni/TimescaleDB, HAProxy/PgBouncer, Mosquitto, Valkey/Sentinel, ChirpStack, Node-RED, Grafana, OpenBao, and the Fabric outbox database layer. It may also record current image digests, configuration hashes, service/listener state, and a fresh logical database backup if the operator deliberately wants a newer rollback point.

Do **not** fabricate missing artifacts. Record these as deferred/BLOCKED in 13S rather than creating substitutes: provider Reserved IPv4/DNS/firewall evidence, physical gateway state, real EMU-01 rows, Fabric adapter image/config/transactions, and gateway-integrity runtimes. Do not place plaintext passwords, private keys, AppKeys, OpenBao root/recovery material, or bearer tokens in the general 13S archive.

For normal server preparation, a successful 13S checkpoint means the locally verified server-only package is intact and reproducible. Once `PHASE13S_LOCAL_PACKAGE=PASS` has been reached, treat `SERVER_ONLY_SNAPSHOT_EXPORT=PASS` as satisfied for the current non-destructive commissioning scope and stop repeating backup/export work. Off-host copying, isolated restore rehearsal, and stronger disaster-recovery proof are deferred to the dedicated destructive/failure-testing boundary before Phase 15. This still does **not** satisfy final Phase 13B, which must be refreshed after the remaining provider, hardware, Fabric, and final acceptance work is commissioned.

### Phase 13S-1 initial three-host preflight harness stop - 2026-08-29

The first 13S-1 wrapper proved the `ulc-03` control-host/free-space gate and noninteractive SSH + `sudo -n` access to both `ulc-01` and `ulc-02`, then returned cleanly to the `ulc-03` prompt before building or running the host probe. No server/service/database mutation occurred. The stop is a shell-transport harness defect: the wrapper itself was being supplied to `sudo bash` through a heredoc, while the Step 2 `ssh` commands inherited that same stdin. SSH is allowed to consume stdin, so it consumed the remaining wrapper text after the access checks. This is not evidence of a server, SSH, sudo, backup-tool, or service failure.

Do not repeat the already-passed access gates merely to diagnose this. Continue from probe construction. When an SSH command inside a heredoc-driven wrapper does **not** intentionally transport a script or payload over stdin, use `ssh -n` or redirect stdin from `/dev/null`. When stdin transport is intentional, redirect from the exact file being sent (for example `ssh ... 'sudo -n bash -s -- ulc-01' < "$PROBE"`) so SSH cannot consume the parent wrapper.

### Phase 13S-1 resumed inventory partial PASS / listener-filter harness defect - 2026-08-29

The corrected resume reached all three hosts and proved the useful inventory through OpenBao tooling. `ulc-01`, `ulc-02`, and `ulc-03` all reported Ubuntu 24.04.4 LTS, zero failed systemd units, healthy commissioned service/container baselines, `etcdctl 3.4.30`, PostgreSQL 18.6 `pg_dump`/`pg_restore`, and OpenBao CLI 2.6.2. Container restart counts were zero and no OOM state was reported. `ulc-03` additionally showed Grafana and active Node-RED running as expected. Patroni remained exactly one leader on `10.104.0.2` plus two replicas on `.4` and `.8`.

The probe then hit `awk: unexpected newline or end of string` in the multi-line listener filter on every host. Because the outer resume wrapper did not use fail-fast handling for each remote probe, it continued to Patroni and printed a final `PHASE13S_SERVER_INVENTORY_PREFLIGHT=PASS` banner even though the per-host probe had exited before listener output, non-secret configuration metadata, and `HOST_PREFLIGHT_*` markers. Therefore that final banner was not authoritative until the missing tail was rerun. Preserve all successful inventory/tool/resource/Patroni evidence and do not repeat OS/resource/tool discovery.

### Phase 13S-1 three-host inventory preflight COMPLETE / PASS - 2026-08-29

The corrected listener/configuration tail passed on all three servers. Every host retained the required etcd, PostgreSQL, PgBouncer, Patroni, OpenBao, and HAProxy database listeners. `ulc-01` and `ulc-02` also retained the commissioned MQTT, ChirpStack, and OpenBao HAProxy listeners; `ulc-03` retained Node-RED on `127.0.0.1:1880`, Grafana on `127.0.0.1:3000`, and the local Node-RED MQTT frontend on `10.104.0.8:18884`. Non-secret reconstruction configuration metadata and SHA-256 values were captured without displaying contents, while PgBouncer userlists and Node-RED/Grafana protected environment files were represented by metadata only.

Combined with the immediately preceding inventory, all three hosts have zero failed units, available backup tooling (`etcdctl 3.4.30`, PostgreSQL 18.6 `pg_dump`/`pg_restore`, OpenBao CLI 2.6.2), current containers with restart count zero/OOM false, and the expected commissioned service layout. Patroni remains one leader on `10.104.0.2` with replicas on `.4` and `.8`. `HOST_PREFLIGHT_ulc-01=PASS`, `HOST_PREFLIGHT_ulc-02=PASS`, `HOST_PREFLIGHT_ulc-03=PASS`, `PATRONI_BASELINE=PASS`, and `PHASE13S_SERVER_INVENTORY_PREFLIGHT=PASS` are authoritative. No service or database state changed.

Next: create a protected timestamped 13S snapshot set containing fresh custom-format `chirpstack` and `lorawan_telemetry` logical dumps plus a validated etcd v3 snapshot/member record. OpenBao Raft snapshotting is a separate privileged sub-boundary; never use the Fabric adapter identity for operator snapshot privileges.

### Phase 13S-2 PostgreSQL + etcd snapshot COMPLETE / PASS - 2026-08-29

The protected server-only snapshot set at `/home/opsadmin/backups/phase13s-20260829T022146Z` is valid. Fresh custom-format dumps were created from the healthy `ulc-03` Spilo replica: `chirpstack.dump` is `101218` bytes and `lorawan_telemetry.dump` is `72384` bytes; both passed `pg_restore --list`. The repeated `en_US.utf-8` Perl warnings remain non-blocking locale noise, and the TimescaleDB `continuous_agg` circular-foreign-key warning is the same known full custom-dump warning already recorded in Phase 13A.

The first etcd health-count attempt stopped only because `etcdctl endpoint health` emitted the three successful endpoint results on stderr while the wrapper redirected stdout only. No etcd failure occurred and the PostgreSQL dumps were preserved rather than recreated. The corrected resume captured stdout+stderr for each endpoint and proved all three endpoints healthy. `etcdctl` is `3.4.30`; the live etcd servers are `3.5.15`. The authoritative member/status record showed three started non-learner members, `etcd-02` on `10.104.0.4` as current etcd leader, and a common Raft term `2` / index `1387` at capture time.

A v3 snapshot was then created from `10.104.0.8:2379` as `etcd.snapshot`, size `491552` bytes. Snapshot status reported hash `c0b2b3a5`, revision `1326`, `1336` total keys, and about `492 kB`. The snapshot set contains nine mode-`0600 opsadmin:opsadmin` files under a mode-`0700 opsadmin:opsadmin` directory: source metadata, both database dumps, etcd health/status/member evidence, etcd snapshot/status, and `SHA256SUMS`. `sha256sum -c` passed before and after ownership/permission normalization. Patroni still reported exactly one leader on `10.104.0.2` and replicas on `.4`/`.8` after snapshot creation. `PHASE13S_POSTGRES_ETCD_SNAPSHOT=PASS` is authoritative. Do not recreate these exact dumps/snapshot unless the source state changes; continue by adding secret-free reconstruction/application exports in a separate 13S sub-boundary.

### Phase 13S-2 PostgreSQL dumps PASS / etcd health-capture harness stop - 2026-08-29

The protected snapshot directory `/home/opsadmin/backups/phase13s-20260829T022146Z` was created successfully on `ulc-03`. The pre-snapshot gate proved `ulc-03` is still a Patroni replica with replay caught up (`true|true`), `etcdctl` is `3.4.30`, and sufficient backup space exists. `SOURCE-METADATA.txt` was created, a fresh `chirpstack.dump` of 101218 bytes passed `pg_restore --list`, and a fresh `lorawan_telemetry.dump` of 72384 bytes passed `pg_restore --list`. The repeated `en_US.utf-8` locale warning remains non-blocking. The TimescaleDB `continuous_agg` circular-foreign-key warning is the already-known full custom-format dump warning and did not invalidate the telemetry catalog check.

Step 6 then stopped on a **health-output capture defect, not an etcd health failure**. `etcdctl endpoint health` visibly returned successful committed-proposal health for all three endpoints (`10.104.0.2`, `.4`, `.8`), but this etcdctl build emitted those human-readable health lines on stderr. The wrapper redirected only stdout to `etcd-endpoint-health.txt`, leaving that file empty; the subsequent `grep -c 'is healthy'` therefore returned zero and intentionally stopped before snapshot creation. Do not recreate the two valid PostgreSQL dumps. Reuse this exact partial directory, capture each etcd endpoint health with stderr included (or rely on the command exit status), then continue with endpoint/member records, etcd snapshot, SHA-256 manifest, ownership/mode normalization, and the final Patroni regression gate.

### Phase 13S-3 secret-free reconstruction export COMPLETE / PASS - 2026-08-29

The reconstruction bundle under `/home/opsadmin/backups/phase13s-20260829T022146Z/reconstruction` is complete for the currently commissioned server-only state. Three host manifests capture OS/service/container/listener state plus safe configuration hashes and protected-file metadata without copying environment files, private keys, PgBouncer userlists, or credential databases. Node-RED B was re-proved fenced with no `:1880` listener and no `flows_cred.json`, then the exact reviewed shared runtime (`compose.yml`, `settings.js`, `package.json`, `package-lock.json`, `flows.json`) was exported from the stopped standby and matched all authoritative hashes. Grafana `compose.yml`, datasource provisioning, dashboard provisioning, and `lorawan-overview.json` passed literal-secret checks before export; `grafana.env` remained excluded. The reconstruction tree contains 16 mode-`0600 opsadmin:opsadmin` files under mode-`0700` directories and its own SHA-256 manifest passed.

The original Phase 13S-2 PostgreSQL/etcd `SHA256SUMS` was rechecked afterward and remained unchanged. Node-RED A remained `running|0|healthy`, Grafana `running|0|false`, and Node-RED B remained fenced. `PHASE13S_RECONSTRUCTION_EXPORT=PASS` is authoritative. Provider-owned public ingress, physical gateway/EMU-01 acceptance, Fabric adapter/handoff, gateway-integrity runtime, final Phase 13B, Phase 14, and Phase 15 remain explicitly deferred or blocked as recorded in `DEFERRED-AND-SEPARATE.txt`.

The next server-only backup boundary is OpenBao. Cloud production currently has no dedicated snapshot-only backup AppRole. Create and verify a least-privilege `openbao-raft-snapshot-reader` policy and `openbao-backup` AppRole before taking the Raft snapshot. Do not use the `fabric-adapter` role and do not take the snapshot with a long-lived root token. Prefer short-lived one-use SecretIDs that are generated only for the snapshot operation and never stored in the general reconstruction archive.

### Phase 13S-4A OpenBao snapshot-only backup identity COMPLETE / PASS - 2026-08-29

The three-node OpenBao cluster was healthy and unsealed before mutation. The existing `lorawan-evidence` Transit key remained `ecdsa-p256`, non-exportable, plaintext backup disabled, deletion disabled, and version `1`; the `fabric-adapter` AppRole retained only the `fabric-evidence-signer` policy and had zero SecretID accessors.

A new policy `openbao-raft-snapshot-reader` was created with exactly one path: `sys/storage/raft/snapshot`, capabilities `read` and `sudo`. A new `openbao-backup` AppRole was then created with only that policy, token TTL `900` seconds, token max TTL `1800` seconds, SecretID TTL `900` seconds, `secret_id_num_uses=1`, and `bind_secret_id=true`. The RoleID exists but was not printed. No backup SecretID was issued during this step and the Fabric adapter still had zero SecretID accessors afterward. All three OpenBao nodes remained initialized and unsealed after the mutation. `PHASE13S_OPENBAO_BACKUP_IDENTITY=PASS` is authoritative.

Next: issue exactly one ephemeral backup SecretID in memory, authenticate once, prove a second login with the same SecretID fails, verify the resulting token has `read,sudo` only on `sys/storage/raft/snapshot` and `deny` on Transit sign/verify and Raft restore/force paths, save one OpenBao Raft snapshot, transfer it into the protected Phase 13S set, revoke the short-lived token, and confirm no reusable backup SecretID remains. Do not use the root token for the snapshot operation itself.

### Phase 13S-4B first snapshot attempt stopped after SecretID issuance - 2026-08-29

The protected OpenBao snapshot workflow passed the existing 13S integrity check, loaded the protected root token without printing it, reverified the `openbao-backup` role, proved zero backup SecretID accessors before issuance, and confirmed a three-voter Raft configuration with `10.104.0.2` as leader at that checkpoint. The root administrative identity then successfully issued one new one-use backup SecretID. Immediately afterward, the wrapper attempted to count SecretID accessors using a Python parser that assumed the JSON document was an object containing `data.keys`. OpenBao 2.6.2 returned the list result as a JSON list in this invocation, so Python raised `AttributeError: 'list' object has no attribute 'get'` and the remote shell exited before AppRole login or snapshot creation.

Treat this as a harness/schema-shape defect, not an OpenBao or Raft failure. The just-issued SecretID value existed only in the failed shell and is no longer recoverable, but its server-side accessor may remain until its 15-minute TTL expires because it was never consumed. Before issuing another SecretID, list accessors with a parser that accepts both top-level JSON lists and wrapped `data.keys` forms. Require at most one accessor because the role had zero immediately before the failed issuance; if one orphan accessor remains, destroy that exact accessor administratively and re-prove zero. Preserve any partial local `openbao-raft-evidence.txt` transcript separately. Do not rerun Phase 13S-4A, do not recreate the backup role/policy, and do not claim an OpenBao Raft snapshot exists from this failed run.

### Phase 13S-4B OpenBao Raft snapshot COMPLETE / PASS - 2026-08-29

The corrected resume found exactly one orphan `openbao-backup` SecretID accessor from the failed parser run, destroyed that accessor administratively, and re-proved a zero-accessor clean baseline before minting a fresh credential. The fresh SecretID was issued under the commissioned `15m` / one-use backup-role constraints, authenticated successfully exactly once, and a second login with the same SecretID was rejected. The consumed accessor disappeared immediately.

The resulting backup token was verified to have exactly `read` + `sudo` on `sys/storage/raft/snapshot`, while Transit sign, Transit verify, and Raft restore/force capabilities were all denied. Using this restricted token against the current Raft leader `10.104.0.2`, OpenBao created `/tmp/phase13s-openbao.snap`; the protected host copy was `30236` bytes with SHA-256 `9965f9e904b83d62b07ebb9321af1b4a45a7f2b15fbfdf50d0c7238fac249e68`. The token was then explicitly revoked. Final backup SecretID accessors = `0`; Fabric adapter SecretID accessors = `0`; all three OpenBao members remained initialized/unsealed.

The snapshot was transferred into `/home/opsadmin/backups/phase13s-20260829T022146Z/openbao.snap`, and its destination SHA-256 exactly matched the source. The remote staging copy was removed. `openbao-raft-evidence.txt`, the preserved failed-run transcript `openbao-raft-evidence.partial-accessor-parser.txt`, and `OPENBAO-SHA256SUMS` were protected as mode `0600 opsadmin:opsadmin`; the OpenBao manifest verified all three artifacts. The original PostgreSQL/etcd snapshot manifest and the reconstruction manifest still pass unchanged. `PHASE13S_OPENBAO_RAFT_SNAPSHOT=PASS` is authoritative.

### Phase 13S-5 final local server-only package COMPLETE / PASS - 2026-08-29

The complete interim server-only snapshot set under `/home/opsadmin/backups/phase13s-20260829T022146Z` was revalidated before packaging. The existing PostgreSQL/etcd, OpenBao, and reconstruction manifests all passed. Required database dumps, etcd snapshot, OpenBao Raft snapshot, Node-RED reviewed runtime export, Grafana provisioning/dashboard export, and deferred/blocker record were present. A filename-level secret gate found no `.env`, private-key, password/userlist, SecretID, root-token, recovery-share, or unseal-share files in the general archive. All source files remained mode `0600 opsadmin:opsadmin` and directories mode `0700 opsadmin:opsadmin`.

`SERVER-ONLY-STATUS.txt` records the server-only/interim scope and explicitly leaves provider ingress, physical gateway/real EMU-01 acceptance, Fabric runtime/handoff/transaction, gateway-integrity runtime, final Phase 13B, final Phase 14, Phase 14B, and Phase 15 unclaimed. `PHASE13S-FULL-SHA256SUMS` covers 30 payload files and passed. The transport archive `/home/opsadmin/backups/phase13s-20260829T022146Z.tar.gz` was created outside the source directory, is `108819` bytes, passed `gzip -t`, contained all required top-level artifacts, and passed a disposable extraction followed by `sha256sum -c PHASE13S-FULL-SHA256SUMS`. Its transport SHA-256 is `19f2072fdfb4ef41e34442c7cc3949decd62a0cb2cee155bcf734f24121397cc`; the sidecar is `/home/opsadmin/backups/phase13s-20260829T022146Z.tar.gz.sha256`. `PHASE13S_LOCAL_PACKAGE=PASS` is authoritative.

**Streamlined commissioning decision - 2026-08-29:** the locally verified package is sufficient for the current server-first preparation scope. The archive has already passed its full 30-file SHA-256 manifest, gzip structure test, disposable extraction, and extracted-manifest verification, so `SERVER_ONLY_SNAPSHOT_EXPORT=PASS` is accepted now. Do not copy it off-host merely to continue normal-path setup, and do not rebuild or rehash it again unless the protected source state materially changes. The `SERVER-ONLY-STATUS.txt` inside this already-built archive still contains the earlier stricter `NOT_YET_OFFHOST_VERIFIED` wording; preserve that file as historical evidence rather than rebuilding the archive solely to change a label. Off-host copy and isolated restore proof remain deferred to the pre-Phase-15 destructive/recovery boundary. This is still an interim Phase 13S package, **not** final Phase 13B.

### Phase 13B - after every pre-test service is commissioned

Re-run the backup collection after Phase 12A, Phase 14A, and Phase 20. Include Node-RED flow/config, Grafana dashboard/data-source exports, OpenBao recovery/Raft snapshot material, Fabric adapter image/config references, public-ingress scripts/units, and the final database state.

**13B PASS is one prerequisite of Phase 14B.** The backup identifier used by Phase 15 must refer to this fully commissioned snapshot, not an earlier 13S/13A partial build.

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

### Streamlined Phase 13A path for normal-path commissioning - 2026-08-28

For the current POC, use the minimum rollback boundary needed to continue **non-destructive** Phase 12 / normal-path testing quickly. The fresh `chirpstack` and `lorawan_telemetry` dumps have already passed local `pg_restore --list` and SHA-256 verification on `ulc-03`; do not recreate or re-parse them unless the source state changes.

The fast Phase 13A checkpoint is:

```text
existing verified logical dumps on ulc-03
    -> package/copy once to the administration workstation
    -> verify one transport SHA-256
    -> retain the off-host copy
    -> continue normal-path commissioning
```

Do **not** require an isolated database restore, etcd snapshot restore rehearsal, destructive membership exercise, or failure injection merely to continue normal-path commissioning. Those stronger DR proofs become mandatory before Phase 15 destructive/failover testing. This streamlining does not remove Patroni, etcd, HAProxy, PgBouncer, Valkey/Sentinel, MQTT HA, or any other HA component.

For the current backup `/home/opsadmin/backups/phase13a-20260827T032756Z`, one compressed archive plus one SHA-256 sidecar is sufficient for the transport step. The internal dump catalogs and hashes are already proven at source.

## 13.4 Copy PostgreSQL backups off the three Droplets

If the backup was created on `ha-01`, `ha-02`, or `ha-03`, copy the entire protected backup directory to the administration workstation or another approved off-host location before the destructive test.

Then recalculate the checksums at the destination and compare with `SHA256SUMS`.

A dump that exists only on a Droplet scheduled for failure is not a useful rollback copy.

### Phase 13A off-host transport PASS - 2026-08-28

The compressed transport archive `phase13a-20260827T032756Z.tar.gz` was copied from `ulc-03` to the Windows administration workstation using the proven `id_ed25519_home_ops` SSH identity. The source SHA-256 was `e97d50c31252ede1fe55b734b6686f270e92ebecb69a36d637b04fbf726cda1c`; Windows `Get-FileHash -Algorithm SHA256` returned the same value and the operator obtained `PHASE13A_OFFHOST_COPY=PASS`. Treat the streamlined Phase 13A transport checkpoint as PASS. For normal-path commissioning, do not repeat the database dumps, dump-catalog checks, isolated restore rehearsal, or destructive DR tests now; the stronger recovery proof remains deferred to the later destructive/failover test boundary.

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

For the current **non-destructive normal-path commissioning**, Phase 13A passes when:

- the already-validated current `chirpstack` and `lorawan_telemetry` logical dumps exist outside the target Droplets;
- the off-host transport archive/hash matches the source transport hash;
- current non-secret HAProxy/PgBouncer/Mosquitto/Valkey/ChirpStack configuration references remain documented;
- when a legacy authoritative source exists, its final migration backup/off-host destination is ready.

Do not repeat source `pg_restore --list` or dump SHA-256 checks when those exact dump files have already passed and have not changed.

Before **Phase 15 destructive/failover testing**, complete the stronger DR gate that was intentionally deferred for speed: isolated `lorawan_telemetry` restore with Timescale objects intact, required etcd snapshot/member/config evidence, and any other destructive-recovery prerequisite relevant to the planned fault.

After the streamlined **13A PASS**, continue to [12-gateway-and-device-migration.md](12-gateway-and-device-migration.md) only when the Phase 11 normal path is also ready. Do not start fault injection until the stronger pre-Phase-15 DR gate passes.

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

### Phase 13A transport archive created PASS - 2026-08-28

The streamlined off-host transport archive was created successfully on `ulc-03` from the already-validated source directory `/home/opsadmin/backups/phase13a-20260827T032756Z`. The resulting archive is `/home/opsadmin/backups/phase13a-20260827T032756Z.tar.gz`, size about 28 KiB, with SHA-256 `e97d50c31252ede1fe55b734b6686f270e92ebecb69a36d637b04fbf726cda1c`. The sidecar `phase13a-20260827T032756Z.tar.gz.sha256` was created successfully. Treat archive creation as PASS. The only remaining fast-path transport gate is to copy the archive to the administration workstation and confirm the destination SHA-256 matches exactly; do not recreate the database dumps or rerun their source validation.
