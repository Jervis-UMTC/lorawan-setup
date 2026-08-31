# Replicated Gateway Evidence Services - Streamlined Deployment Journey

> **Status: LIVE COMMISSIONING IN PROGRESS.** Source/build readiness, SeaweedFS infrastructure through the HAProxy boundary, the reviewed `gateway_evidence` migration, and the three-node evidence-aware PostgreSQL HBA are already live PASS. Production object-store helper S9, evidence workload LOGIN/PgBouncer closure, PKI/ingress, and service replicas remain. Preserve completed gates and resume only from the current failed boundary.

## 6.1 Goal

Build the evidence tier so one cloud service instance can disappear without losing an accepted evidence object or creating two authoritative verification results.

Target runtime shape after capacity validation:

```text
                    Reserved IPv4 / shared HTTPS :443
                              |
                    HAProxy ulc-01 OR ulc-02
                              |
                +-------------+-------------+
                |                           |
                v                           v
       evidence-ingest-1            evidence-ingest-2
            ulc-01                       ulc-02
                \                           /
                 +-----------+-------------+
                             |
                       replicated/raw
                       evidence store
                             |
                  PostgreSQL Patroni 3/3
                             |
          +------------------+------------------+
          |                                     |
          v                                     v
 collector-1 ulc-01                       collector-2 ulc-03
   |            |                           |            |
   +-> broker-1 +-> broker-2                +-> broker-1 +-> broker-2
          \                                      /
           +---------------+--------------------+
                           |
                      capture-key
                      deduplication
                           |
              +------------+------------+
              |                         |
              v                         v
       verifier-1 ulc-02          verifier-2 ulc-03
       + trusted decoder          + trusted decoder
              |                         |
              +------ DB leases --------+
                           |
                 one authoritative
                 event_verification
```

The gateway journal/uploader remain single-device services because there is one physical gateway. Their resilience comes from crash-safe local state, independent MQTT delivery buffering, and cloud checkpoints; do not call them an HA pair.

## 6.2 Non-negotiable HA semantics

```text
Ingest
  active/active
  same retry -> one accepted identity
  same identity + different digest -> security conflict

Collector
  active/active
  two replicas
  each replica -> persistent read-only session to broker-1 AND broker-2
  duplicate observations -> one deterministic capture_key_sha256

Verifier
  active/active
  two replicas
  FOR UPDATE SKIP LOCKED + expiring lease
  crash -> lease expires -> other worker reclaims

Trusted decoder
  stateless
  same immutable code/image digest on both verifier replicas

Raw storage
  one-Droplet loss cannot remove the only copy
  create-only/no-overwrite
  exact-byte SHA-256 recovery proof required

Database
  existing 3-node Patroni cluster is the authoritative metadata/state layer
```

## 6.3 Why the setup is split into guarded blocks

One giant script that mutates storage, PostgreSQL, HAProxy, PKI, three services, and Grafana makes failure recovery ambiguous. Instead, use one block per trust boundary. Keep initial commissioning deliberately small: prove each replica starts, then run one representative convergence/function check for the pair. Deep failure testing stays in Guide 3 / Phase 15.

Standard wrapper behavior:

```text
preflight -> install/start replica 1 -> health -> install/start replica 2 -> health -> one functional/convergence smoke -> evidence -> PASS
```

If a block fails after the canary passes, preserve that PASS and resume from the failed replica/check. Do not rerun the whole phase automatically.

### Standard guarded one-block shell pattern

Every future live block should follow the same controlled child-shell shape below. This is a **structural template**, not a command to run now: a delivered live block must replace the marked body with reviewed, concrete commands and remove the template stop gate before the operator executes it.

```bash
sudo bash <<'EOF'
set -euo pipefail

# TEMPLATE SAFETY: a real reviewed block removes this guard.
echo 'TEMPLATE_ONLY=STOP'
exit 64

STEP='<BOUNDARY_NAME>'
RUN_ID="EVIDENCE-SVC-$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="/home/opsadmin/lorawan-ha-evidence/${RUN_ID}/<STEP_DIR>"
install -d -m 700 "$EVIDENCE_DIR"

fail() {
  printf 'STEP=%s\nRESULT=FAIL\nREASON=%s\n' "$STEP" "$*" >&2
  exit 1
}

pass() {
  printf '%s=PASS\n' "$1"
}

# ----------------------------------------------------------
# 1. READ-ONLY PREFLIGHT
#    - previous PASS prerequisites
#    - current service/cluster/resource state
#    - exact target files/listeners free/expected
# ----------------------------------------------------------

# ----------------------------------------------------------
# 2. CANARY MUTATION
#    - minimum rollback copy for this boundary only
#    - validate candidate before reload/start
# ----------------------------------------------------------

# ----------------------------------------------------------
# 3. VERIFY CANARY
#    - health/restart/OOM
#    - permissions/ACLs
#    - functional positive + negative checks
# ----------------------------------------------------------
pass REPLICA_1

# ----------------------------------------------------------
# 4. SECOND REPLICA MUTATION
#    - execute only after REPLICA_1 passed
# ----------------------------------------------------------

# ----------------------------------------------------------
# 5. VERIFY SECOND REPLICA
# ----------------------------------------------------------
pass REPLICA_2

# ----------------------------------------------------------
# 6. HA INVARIANT
#    - duplicate work converges safely
#    - durable state is shared/replicated as designed
#    - no unrelated service regression
# ----------------------------------------------------------
pass HA_INVARIANT

# ----------------------------------------------------------
# 7. SECRET-FREE EVIDENCE
#    - bounded command output/config hashes only
#    - never copy .env/private keys/passwords/tokens/SecretIDs
# ----------------------------------------------------------
find "$EVIDENCE_DIR" -type d -exec chmod 700 {} +
find "$EVIDENCE_DIR" -type f -exec chmod 600 {} +
(
  cd "$EVIDENCE_DIR"
  find . -type f ! -name SHA256SUMS -print0 \
    | sort -z \
    | xargs -0 -r sha256sum > SHA256SUMS
  sha256sum -c SHA256SUMS
)

printf 'STEP=%s\n' "$STEP"
printf 'UTC=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
printf 'REPLICA_1=PASS\n'
printf 'REPLICA_2=PASS\n'
printf 'HA_INVARIANT=PASS\n'
printf 'EVIDENCE_PATH=%s\n' "$EVIDENCE_DIR"
printf '<BOUNDARY_PASS_MARKER>=PASS\n'
EOF
```

Why this pattern is preferred:

- it keeps one logical deployment boundary in one copy/paste operation;
- replica 2 is unreachable if the canary fails because the child shell exits immediately;
- successful early gates can be preserved if a later verification fails;
- evidence generation is part of the block instead of a separate forgotten step;
- the block does not create another full backup cycle;
- the top-level login shell is not left in `set -euo pipefail` mode;
- future wrappers that call SSH must use `ssh -n` for no-input checks or redirect from an explicit payload file so SSH cannot consume the parent heredoc.

For each actual boundary in Sections 6.5-6.12, the project session should produce the concrete reviewed version of this block only when all required image names, paths, identities, ports, and rollback actions are known.

## 6.4 Journey evidence root

For live deployment use one protected run tree on the control host:

```text
/home/opsadmin/lorawan-ha-evidence/EVIDENCE-SVC-<UTC>/
  00-preflight/
  01-storage-db/
  02-pki-ingress/
  03-ingest/
  04-collector/
  05-verifier-decoder/
  06-observability/
  07-normal-path/
  SHA256SUMS
```

Directory mode `0700`; evidence files `0600`. Do not copy `.env`, private keys, database passwords, OpenBao tokens, SecretIDs, recovery material, or Fabric client keys into this tree.

## 6.5 Block 0 - artifact and capacity preflight

**Mutation:** none.

Require before any live evidence service is created:

```text
reviewed source revision for all three server services
immutable image/executable digest for each
runtime UID/GID
health/readiness contract
configuration schema
trusted-decoder immutable digest + fixtures
v2 canonicalization vector
selected replicated evidence-storage technology
reviewed gateway_evidence migration/grants
reviewed shared-443 design
collector TLS/client-ID design for both brokers
rollback commands
```

The one-block preflight must inspect all three hosts for memory, disk, listeners, current containers, restart/OOM state, and the exact ports/mounts the candidate would consume. Do not start anything.

Pass marker:

```text
EVIDENCE_REPLICATED_PREFLIGHT=PASS
```

## 6.6 Block 1 - replicated evidence storage + PostgreSQL migration

**Mutation:** storage namespace/backend plus one reviewed PostgreSQL migration only.

Guarded order inside one block:

```text
1. re-prove Patroni 1 leader / 2 replicas and selected durable storage healthy
2. create the protected evidence namespace/bucket/path with create-if-absent policy
3. write one synthetic non-secret object and verify its exact SHA-256
4. apply the reviewed versioned `gateway_evidence` migration once on the current primary
5. verify tables/constraints/indexes/lease columns/capture-key uniqueness and grants
6. verify both PostgreSQL replicas received the schema
7. delete only the synthetic storage probe if the backend contract permits test cleanup
8. capture hashes/metadata and PASS
```

Do not run a destructive storage failure here; Phase 15 owns actual member-loss testing.

Pass markers:

```text
EVIDENCE_STORAGE_REPLICATION=PASS
EVIDENCE_DB_MIGRATION=PASS
```

## 6.7 Block 2 - evidence PKI + shared HTTPS ingress

**Mutation:** evidence certificates/identities and reviewed HAProxy shared-443 configuration only.

Canary-first order:

```text
1. verify current ChirpStack HTTPS before change
2. verify anchor ownership/listeners
3. issue/stage evidence server certificate and per-gateway clientAuth identity without printing private material
4. validate SAN/EKU/chain/fingerprint/expiry/EUI mapping
5. build HAProxy candidate for ulc-01
6. haproxy -c before reload
7. activate canary
8. prove ChirpStack browser/API HTTPS still works without a client cert
9. prove evidence SNI route rejects no-cert/unknown-client
10. prove valid evidence client reaches only evidence backend
11. only then repeat the reviewed config on ulc-02
12. prove both anchor candidates equivalent
13. capture config hash/cert metadata and PASS
```

The exact SNI/client-cert method remains blocked until the reviewed HAProxy 2.8 configuration exists. Do not globally require a gateway certificate on ordinary ChirpStack HTTPS.

Pass marker:

```text
EVIDENCE_PKI_INGRESS=PASS
```

## 6.8 Block 3 - two active/active ingest replicas

**Mutation:** deploy ingest-1 then ingest-2.

Frozen target placement:

```text
ulc-01 -> evidence-ingest-1
ulc-02 -> evidence-ingest-2
```

One block may do both replicas only with this gate sequence:

```text
1. verify storage + DB + PKI/ingress PASS markers and stage the identical immutable image/config on both hosts
2. install distinct ingest-1 credential; start ingest-1; verify health/runtime UID/listener/resource state
3. install distinct ingest-2 credential; start ingest-2; verify the same health gates
4. send one approved synthetic checkpoint/segment fixture through the normal ingress/backend path
5. repeat the exact fixture once and prove one raw object + one metadata identity remain
6. prove object SHA matches metadata and both replicas remain healthy
7. capture evidence and PASS
```

Pass marker:

```text
EVIDENCE_INGEST_REPLICATED=PASS
```

## 6.9 Block 4 - two active/active MQTT evidence collectors

**Mutation:** dedicated collector identities/ACLs and collector-1/2 runtime.

Frozen target placement:

```text
ulc-01 -> collector-1
ulc-03 -> collector-2
```

Each collector has **two broker sessions**:

```text
collector-N/broker-1 -> 10.104.0.2:8884, TLS identity mqtt.internal.lorawan.com
collector-N/broker-2 -> 10.104.0.4:8884, TLS identity mqtt.internal.lorawan.com
```

Use distinct client IDs for all four sessions and persistent subscriptions. ACL is read-only `as923/gateway/+/event/#`; publish and command topics are denied.

Guarded order:

```text
1. verify both broker backends, TLS identity, and the reviewed read-only ACL configuration
2. stage/start collector-1 and prove its two persistent broker sessions
3. stage/start collector-2 and prove its two persistent broker sessions
4. feed one approved non-RF commissioning fixture through the reviewed safe input path when available
5. prove duplicate observations converge to one `capture_key_sha256` and one logical raw-object identity
6. capture the four client/session health states without secrets
7. PASS
```

Do not interpret the duplicate observation by collector-1/2 as two gateway events.

Pass marker:

```text
EVIDENCE_MQTT_COLLECTOR_REPLICATED=PASS
```

## 6.10 Block 5 - two verifier workers + trusted decoder

**Mutation:** verifier-1/2 runtime only; no OpenBao/Fabric permission.

Frozen target placement:

```text
ulc-02 -> verifier-1 + trusted decoder
ulc-03 -> verifier-2 + trusted decoder
```

Both must report the exact same decoder digest/version before either can process work.

Guarded order:

```text
1. prove one fixed valid decoder vector on both replicas and require identical decoder digest/version
2. start verifier-1 and verify health + least-privilege DB configuration
3. start verifier-2 and verify the same health/configuration gates
4. queue one fixed pending verification fixture
5. prove exactly one worker owns/processes it and the terminal state/reason/digests match the fixture
6. prove no duplicate terminal row/work item appeared and both replicas remain healthy
7. PASS
```

Actual host/process failure timing, lease-expiry/reclaim, SKIP LOCKED distribution under concurrent load, and tamper/reorder/delete/checkpoint-conflict fixtures belong to Guide 3 / Phase 15. They are not required to get the replicated verifier pair installed and working.

Pass markers:

```text
EVIDENCE_VERIFIER_REPLICATED=PASS
TRUSTED_DECODER=PASS
```

## 6.11 Block 6 - read-only evidence observability

**Mutation:** Grafana provisioning/read-only views only.

Add panels/queries for:

```text
replica health ingest-1/2
collector-1/2 broker-session health
verifier-1/2 worker/lease state
latest checkpoint age per gateway
pending verification age
verified/evidence_gap/integrity_failure counts
collector unmatched count
trusted-decoder mismatch count
raw-store replication/member health
v2 outbox rows blocked on verification
```

Telemetry freshness and evidence freshness remain different panels.

Pass marker:

```text
EVIDENCE_OBSERVABILITY=PASS
```

## 6.12 Block 7 - real normal-path lineage

This step waits for the physical gateway and reviewed server runtimes.

One real staging uplink must produce exactly one lineage:

```text
journal record
-> closed segment/checkpoint
-> replicated evidence ingest
-> one logical MQTT capture despite collector replication
-> accepted ChirpStack application event
-> trusted decoder result
-> TimescaleDB row
-> one event_verification row = verified
```

Then and only then may the matching v2 outbox row become eligible for the Fabric Adapter.

Pass marker:

```text
GATEWAY_EVIDENCE_V2_NORMAL_PATH=PASS
```

## 6.13 What gets written to Markdown after every block

After every operator block, record only verified facts:

```text
UTC/date
boundary name
hosts/replicas touched
immutable image/executable hashes
config/migration hash where relevant
non-secret certificate metadata where relevant
resource snapshot
named PASS markers
any harness defect and exact resume point
what was deliberately not repeated
next boundary
```

Update:

```text
deployment/server/integrations/gateway-integrity/<relevant-guide>.md
deployment/server/cloud-production/00-build-execution-log.md
deployment/server/cloud-production/00-current-server-continuation-checkpoint.md
```

If a block partially passes, write the successful gates immediately and resume from the first failed gate. Do not discard valid evidence and do not rerun successful replicas only for ceremony.

## 6.13A Live execution checkpoint — 2026-08-31

This section is the authoritative resume point after the interrupted documentation period. Do not rerun completed boundaries merely to reconstruct evidence.

### Raw evidence infrastructure

```text
SeaweedFS release       4.41 / commit de34a1a87
SeaweedFS image         chrislusf/seaweedfs:4.41@sha256:43b768cd62b00d132439cda881b93fd1adebf1b315e996e794087743821d771d
metadata-etcd image     quay.io/coreos/etcd:v3.5.15@sha256:0934690612905554eb61ddefb9faaaecb47c2f6931dbb453e694358092ee8990
metadata-etcd ports     12379 / 12380
master                  19333 HTTP / 19334 gRPC
volume                  18082 HTTP / 18083 gRPC
filer                    18888 HTTP / 18889 gRPC
raw S3                  127.0.0.1:18333
S3 TLS boundary         node VPC :18443
replication             010 = one additional copy, different rack, same sgp1 DC
```

`SEAWEEDFS_CORE_3_NODE=PASS` and `SEAWEEDFS_REPLICATION_010_EMPIRICAL=PASS` are authoritative. The retained placement fixture is `3,01e3ab96f3`, size `89`, SHA-256 `bf981516163ff1e35d6315213458423860be84f0b7fe74269ac8d780577bb5b`, with copies on two distinct Droplet racks. The `lorawan-evidence` bucket is configured with replication `010` and volume growth count `2`.

Runtime S3 identities are installed for ingest, collector, and verifier. Ingest/collector have read/list/write; verifier has read/list only. The active `s3.json` is identical on all three hosts, SHA-256 `310aa8b74145256bae9e15f759bacfc37d590a5b54c08c348c38ea7e0c6371f8`, protected as `0640 root:1000`. The earlier leaked S3 credentials were retired and must never be reused.

Internal object-store PKI is live. CA SHA-256 is `c1dedc8cc6b58217e955cf763868b429dacdd933bbe7d9ffed147122e9d013fd`; logical endpoint is `evidence-objects.internal.lorawan.com:18443`. HAProxy on ulc-01/02/03 accepts GET/HEAD and only conditional PUT with exactly one `If-None-Match: *`; other methods are `405` and bad/unconditional PUT is `428`. Raw Seaweed S3 remains loopback-only. `HAPROXY_EVIDENCE_S3_3_NODE=PASS` is authoritative. Retained HAProxy fixtures exist on all three nodes and must not be deleted merely to tidy commissioning evidence.

**S9 remains pending.** Full `EVIDENCE_OBJECTSTORE=PASS` is not yet claimed because `gateway-evidence-ingest objectstore-contract-write` plus cross-host `objectstore-contract-verify` must run from the accepted production binary. Discovery proved that accepted binary/image is not present on ulc-01/02/03, and the evidence source/binaries are currently untracked rather than available from `origin/main`. Do not substitute another build or weaken this binary gate.

### `gateway_evidence` database migration

The live migration is COMPLETE / PASS. Repository source hashes remain:

```text
001_gateway_evidence.sql         bf2a1e3188cf67107872c425064d55fb476d7ea58855510b154f7e869795a8b9
001_gateway_evidence.verify.sql  e08112fd48cdb6be058f40487ac7fff4d4b60a9647f2e1750cf1ebbd974ed4ae
```

The reviewed terminal transport copies that were actually executed had hashes `cd03a10f39dc4e780be5f7c7718596816a199dfaf118d7bd9c3f1c5ce4e1a630` and `fc57361eda4fc7fb20e3148eed421e2f653f38dfc25e00e6dee07dba59adc040`; preserve that distinction instead of claiming byte identity with the repository files.

Pre-migration backup on current leader ulc-01 is `/root/backups/evidence-db-pre-migration/20260831T074754Z/lorawan_telemetry.dump`, SHA-256 `f9564ffaf8e65e021fa025cd45e70c9472608bfa7b6e4912cc568cc773aa21de`, size `79962`, with `pg_restore --list` PASS. The Timescale `continuous_agg` circular-FK warning was informational because this was a full custom-format dump, not a data-only dump.

`EVIDENCE_DB_MIGRATION=PASS`, `EVIDENCE_DB_PRIMARY_VERIFY=PASS`, and `EVIDENCE_DB_3_NODE_REPLICATION=PASS` are authoritative. The migration created four `gateway_evidence` base tables, three nullable telemetry provenance columns, six relevant indexes, the monotonic checkpoint trigger, and three passwordless NOLOGIN authority roles:

```text
gateway_evidence_ingestor
gateway_evidence_collector
gateway_evidence_verifier
```

### Evidence PostgreSQL HBA rollout

The HBA extension is COMPLETE / PASS on all three Patroni members. The policy remains exactly 20 rules: no broad rule was added. Instead, the existing three `hostssl lorawan_telemetry ... /32 scram-sha-256` rules now use this user selector:

```text
telemetry_writer,telemetry_reader,fabric_adapter,+gateway_evidence_ingestor,+gateway_evidence_collector,+gateway_evidence_verifier
```

All three live/persistent HBA lists have SHA-256 `a943358a884249aaae74b663a81fa6dde2d7c98deeb31f93def8e5bb4aa729f1`, zero parse errors, and the two final reject rules remain intact. Rollout order was ulc-03 canary/persist -> ulc-02 canary/persist -> ulc-01 leader canary/fresh-auth/persist. No Spilo restart/recreate or Patroni switchover occurred.

Three harness defects were corrected during the rollout and must not be reintroduced:

```text
1. Patroni reload is asynchronous; poll pg_hba_file_rules for convergence instead of sleep 3.
2. OLD_USERS is a prefix of NEW_USERS; compare the parsed HBA user field exactly, not substring containment.
3. pg_stat_replication.client_addr is inet; use host(client_addr), not client_addr::text, for exact address matching.
```

Before leader persistence, brand-new physical-replication `IDENTIFY_SYSTEM` sessions were created from ulc-02 source `10.104.0.4` and ulc-03 source `10.104.0.8` using `standby`, SCRAM, and `sslmode=verify-full`. Both returned system identifier `7676855802088521796`, timeline `3`, LSN `0/68000000`. `FRESH_REPLICATION_AUTH_TO_ULC01=PASS` is authoritative.

### Current workload LOGIN issuance stop

The planned identities are:

```text
evidence_ingest_ulc01     -> gateway_evidence_ingestor
evidence_ingest_ulc02     -> gateway_evidence_ingestor
evidence_collector_ulc01  -> gateway_evidence_collector
evidence_collector_ulc03  -> gateway_evidence_collector
evidence_verifier_ulc02   -> gateway_evidence_verifier
evidence_verifier_ulc03   -> gateway_evidence_verifier
```

The issuance block started from a clean zero-login boundary. `evidence_ingest_ulc01` was created successfully with LOGIN, SCRAM-SHA-256, INHERIT, no superuser/createdb/createrole/replication/bypassrls, and exactly one direct membership in `gateway_evidence_ingestor`. Its pending high-entropy credential is protected under `/root/evidence-db-bootstrap/` and must never be printed or copied into Markdown.

The first direct `sslmode=verify-full` connection reached PostgreSQL and failed with:

```text
FATAL: permission denied for database "lorawan_telemetry"
DETAIL: User does not have CONNECT privilege.
```

Treat this as a **database CONNECT privilege design stop**, not a HBA, TLS, password, SCRAM, or role-membership failure. At this checkpoint only `evidence_ingest_ulc01` exists; the other five workload LOGIN identities have not been created by the failed block. PgBouncer is still unchanged at its existing four-entry `0640 root:postgres` userlist and contains zero evidence identities.

The root cause is now resolved from the authoritative Phase 6 database-credential record: `PUBLIC` CONNECT on `lorawan_telemetry` was deliberately revoked, and CONNECT was granted only to the original `telemetry_writer`, `telemetry_reader`, and `fabric_adapter` runtime roles. The later evidence migration correctly created schema/table authority roles but did not add database-level CONNECT, so the new evidence LOGIN can authenticate but cannot enter the database.

**Exact resume point:** first re-prove the current CONNECT matrix, then grant `CONNECT ON DATABASE lorawan_telemetry` to the three NOLOGIN authority shells `gateway_evidence_ingestor`, `gateway_evidence_collector`, and `gateway_evidence_verifier`. Because the workload LOGIN roles use `INHERIT` and each has exactly one intended authority membership, this keeps database admission group-based instead of adding six per-user grants. Verify that `PUBLIC` remains denied and only the intended authority shells gain CONNECT, then rerun the issuance block in safe-resume mode. Do not recreate `evidence_ingest_ulc01`, rotate its already-generated password, rerun the migration, or redo the HBA rollout merely because this later privilege gate stopped.

## 6.14 Final commissioning rule

```text
replicated process != replicated truth
```

HA is accepted only when durable state makes duplicate execution safe and one-instance loss recoverable:

```text
Ingest replicas          -> idempotent stable identities
Collector replicas       -> deterministic capture key
Verifier replicas        -> durable leases
Trusted decoder replicas -> identical immutable code
Raw evidence store       -> cross-host durable bytes
PostgreSQL               -> Patroni HA
OpenBao                  -> Raft HA
Fabric adapter           -> lease-safe dual workers
```

No component may claim replication merely because `replicas: 2` appears in Compose.