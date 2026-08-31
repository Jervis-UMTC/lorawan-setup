# 14. Minimal POC Observability and Evidence Capture

> **Status: 14S SERVER-ONLY HARNESS PRE-STAGING MAY PROCEED / FINAL PHASE 14 AFTER 13B.** The final healthy-baseline evidence run still occurs only after Phase 13B against the fully commissioned system. While hardware/provider/Fabric dependencies are unavailable, an interim **14S server-only harness** may be run against the already commissioned server components to prove commands, permissions, UTC timestamps, redaction, and evidence-directory structure early. `14S` is preparation evidence, not the final Phase 14 PASS.

The POC needs **repeatable evidence**, not a production monitoring platform.

Do not deploy Prometheus, Alertmanager, Loki, or another monitoring stack merely to prove the three-server architecture. For a few sensors, command-line checks, service logs, a small Grafana telemetry dashboard, and timestamped evidence folders are enough.

The important rule is:

> First prove the evidence harness on a fully healthy baseline. Only after Phase 14B passes should the same capture set be used before, during, and after Phase 15 failures.

### Phase 14S server-only evidence-harness pre-stage

Before the final Phase 13B exists, the server-only portion of the harness may be exercised once with a `SERVER-PRESTAGE-...` run ID. Populate only a `before/` state; do not create a fake failure state. Prove non-secret capture for the components that are actually deployed: host resources, etcd, Patroni/PostgreSQL/TimescaleDB, PgBouncer/HAProxy, Valkey/Sentinel, Mosquitto, ChirpStack, Node-RED A/B state, Grafana, OpenBao, and `telemetry.fabric_outbox`. Record hardware/provider/Fabric-adapter/gateway-integrity fields as `DEFERRED` or `BLOCKED` rather than inventing values.

The 14S pass marker is `SERVER_ONLY_EVIDENCE_HARNESS=PASS`. This means the server-side commands/permissions are ready. It does **not** authorize Phase 15 and does not replace the final healthy-baseline run.

### Phase 14S current execution state - 2026-08-29

The first server-only healthy-state capture created run ID `SERVER-PRESTAGE-20260829T133354Z` under `/home/opsadmin/lorawan-ha-evidence/SERVER-PRESTAGE-20260829T133354Z`. It is read-only: no service restart, configuration mutation, backup, or failure injection is part of this run.

The following gates are authoritative PASS and must not be repeated merely because a later harness step stopped:

```text
THREE_HOST_EVIDENCE=PASS
ETCD_3_MEMBER_HEALTH=PASS
PATRONI_1_LEADER_2_REPLICAS=PASS
POSTGRES_TIMESCALE_OUTBOX=PASS
NODE_RED_SINGLE_ACTIVE=PASS
```

At capture time Patroni reported `10.104.0.2` as the single leader and `10.104.0.4` / `10.104.0.8` as replicas. Node-RED A was `running|0|healthy` with HTTP 200 on `127.0.0.1:1880`; Node-RED B remained fenced/stopped. The recurring PostgreSQL locale warning remained non-blocking.

The first Grafana step printed `GRAFANA_CONTAINER=FAIL`, but this was a discovery-harness false negative rather than a service failure. The harness searched Docker's displayed image text for the word `grafana`; because the immutable image was displayed as digest prefix `3fd54ae12146`, no candidate was found. A direct read-only diagnostic then proved the Compose-labeled container `grafana` was `running`, restart count `0`, `OOMKilled=false`, memory limit `536870912`, listener `127.0.0.1:3000`, and `/api/health` returned database `ok`, Grafana `13.2.0`, commit `f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b`. `GRAFANA_RUNTIME_DISCOVERY=PASS` is authoritative.

The corrected resume preserved Steps 1-6, then passed `GRAFANA_HEALTH=PASS` using the Compose service label / loopback port rather than image-name text, and passed `CHIRPSTACK_TWO_NODE_RUNTIME=PASS` on `ulc-01` and `ulc-02`. These are now authoritative and must not be rerun merely because the next OpenBao probe stopped.

The OpenBao step then failed before collecting any member state because `docker exec openbao bao status -format=json` used the CLI default `https://127.0.0.1:8200`. The commissioned OpenBao listeners are intentionally bound to the host-private addresses `10.104.0.2:8200`, `10.104.0.4:8200`, and `10.104.0.8:8200`; container loopback is not a commissioned listener. The resulting `dial tcp 127.0.0.1:8200: connect: connection refused` is therefore a harness-address defect, not evidence of OpenBao service failure. Resume only from OpenBao onward and set `BAO_ADDR=https://<that-node-private-ip>:8200` plus `BAO_CACERT=/openbao/tls/ca.crt` for every in-container `bao status` call.

The final resume set `BAO_ADDR` explicitly to each commissioned private OpenBao API address and `BAO_CACERT=/openbao/tls/ca.crt`. All three members returned `initialized=true`, `sealed=false`, and `ha_enabled=true`, so `OPENBAO_3_NODE_HEALTH=PASS` is authoritative. The harness then wrote the provider/hardware/Fabric/gateway-integrity items as `DEFERRED` or `BLOCKED`, passed the evidence secret-sanity scan, normalized the evidence tree to mode `0700` directories / `0600` files, and generated a final SHA-256 manifest covering the complete 16-file evidence set. `DEFERRED_BLOCKED_RECORD=PASS`, `EVIDENCE_SECRET_GATE=PASS`, `EVIDENCE_SHA256=PASS`, and `EVIDENCE_FILESYSTEM_PROTECTION=PASS` are authoritative.

`SERVER_ONLY_EVIDENCE_HARNESS=PASS` is therefore complete for run `SERVER-PRESTAGE-20260829T133354Z`. The evidence directory is `/home/opsadmin/lorawan-ha-evidence/SERVER-PRESTAGE-20260829T133354Z`. No service restart, configuration mutation, backup, or failure injection occurred during this 14S run. Do not repeat 14S merely to continue setup or begin a new chat; the final Phase 14 healthy-baseline evidence capture still occurs after final Phase 13B against the fully commissioned system.

### Phase 14 healthy-baseline dry run

After the final Phase 13B snapshot exists, create a normal evidence directory and populate the `before/` state for every deployed component. Do not create a fake `during/` failure state. Verify all commands run non-interactively with the intended least-privilege access, timestamps are UTC, and no secrets are copied into evidence.

The final dry run must include Node-RED, Grafana, OpenBao, both Fabric adapters, the latest normal Fabric commit, the current Reserved-IP owner, and the final Phase 13B backup-set identifier.

## 14.1 What every Phase 15 failure run must answer

For each run be able to answer:

```text
what failed?
when was the fault injected?
which PostgreSQL / Valkey / OpenBao roles changed?
did etcd / Sentinel / OpenBao quorum survive?
which Droplet owned the Reserved IPv4 before/after failure?
did the public-ingress failover agent move it, and how long did that take?
which MQTT broker served after failure?
which ChirpStack instance remained usable?
did a NEW post-fault real uplink succeed?
did Timescale telemetry remain consistent?
did the Fabric outbox remain durable?
was Fabric adapter execution deployed or BLOCKED?
did any 2-GiB host OOM or become swap-bound?
what was the measured recovery time?
was full 3-node redundancy restored before the next run?
```

## 14.2 Create one evidence directory per test

On the administration workstation or another approved evidence host:

```bash
RUN_ID="HA-$(date -u +%Y%m%dT%H%M%SZ)-<TEST>-R1"
EVIDENCE="$HOME/lorawan-ha-evidence/$RUN_ID"
umask 077
mkdir -p "$EVIDENCE"/{before,during,after,logs}
printf '%s\n' "$RUN_ID" | tee "$EVIDENCE/RUN_ID.txt"
date -u --iso-8601=seconds | tee "$EVIDENCE/created-at.txt"
```

Create `notes.md` containing only non-secret facts:

```text
run ID:
failure being tested:
fault method:
staging Gateway EUI:
staging DevEUI:
pre-fault test_sequence/event key:
Reserved IPv4 owner before fault:
Reserved IPv4 owner after recovery:
Reserved-IP reassignment action/time:
fault timestamp UTC:
first successful post-fault event UTC:
RTO:
unexpected behavior:
restore timestamp UTC:
final result: PASS / FAIL / BLOCKED
```

Do not copy passwords, private keys, AppKeys, bearer tokens, complete DSNs, or OpenBao recovery material into the evidence folder.

## 14.3 Host resource snapshot

Run on **ha-01, ha-02, and ha-03** before/during/after the test and save the output under the matching evidence subdirectory:

```bash
hostname
printf '\n=== UTC ===\n'
date -u --iso-8601=seconds
printf '\n=== MEMORY ===\n'
free -h
printf '\n=== CPU / LOAD ===\n'
uptime
command -v vmstat >/dev/null && vmstat 1 5 || true
printf '\n=== DISK ===\n'
df -h /
printf '\n=== SERVICES ===\n'
systemctl --failed --no-pager
printf '\n=== CONTAINERS ===\n'
docker stats --no-stream 2>/dev/null || true
printf '\n=== OOM ===\n'
journalctl -k --since today --no-pager | grep -Ei 'oom|out of memory|killed process' || true
```

Why: with 2-GiB shared-CPU nodes, an OOM **or a functional failover failure caused by sustained CPU contention** is a sizing result. Do not restart the process and erase the evidence before recording it. Use the functional recovery criteria rather than inventing a universal CPU-utilization threshold.

## 14.4 etcd snapshot

From an approved administrative shell, using the currently tested east-west endpoints:

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint health

ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint status --write-out=table

ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  member list --write-out=table
```

These commands match the current HTTP-only etcd deployment on `10.104.0.0/20`. Add CA/client options only after an etcd TLS rollout has been completed and tested.

Record:

```text
healthy member count
leader/member IDs
revision
3/3 before
2/3 during one-host/member loss
3/3 after restore
```

A `2/3` state is acceptable only **during the single-failure test**. Do not begin another fault until it is back to `3/3`.

## 14.5 PostgreSQL / Patroni snapshot

Use the exact pinned Patroni configuration:

```bash
patronictl -c <PATRONI_CONFIG> list <PG_SCOPE> --extended
```

Then verify the normal client route from the host being tested:

```bash
psql \
  'host=pgbouncer.internal.lorawan.com port=6432 dbname=postgres user=<MONITOR_ROLE> sslmode=verify-full' \
  -c 'SELECT now() AT TIME ZONE '\''UTC'\'' AS utc_time, inet_server_addr(), pg_is_in_recovery();'
```

Expected for the routed server:

```text
pg_is_in_recovery = false
```

Record:

```text
primary before/after
replica members
lag where available
promotion/switchover time
server address returned through PgBouncer/HAProxy
```

Both logical databases must remain present:

```text
chirpstack
lorawan_telemetry
```

## 14.6 TimescaleDB snapshot

Against `lorawan_telemetry` through the normal PgBouncer path:

```bash
psql \
  'host=pgbouncer.internal.lorawan.com port=6432 dbname=lorawan_telemetry user=telemetry_reader sslmode=verify-full' \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';"

psql \
  'host=pgbouncer.internal.lorawan.com port=6432 dbname=lorawan_telemetry user=telemetry_reader sslmode=verify-full' \
  -c "SELECT hypertable_schema, hypertable_name FROM timescaledb_information.hypertables ORDER BY 1,2;"
```

Required hypertables:

```text
telemetry.uplinks
telemetry.measurements
```

Also record the latest real measurement without assuming a sensor-specific SQL column:

```sql
SELECT time, dev_eui, metric_name, metric_value, metric_text, metric_bool, unit, quality
FROM telemetry.measurements
ORDER BY time DESC
LIMIT 20;
```

After PostgreSQL promotion, repeat the extension/hypertable queries. A promoted member that cannot load TimescaleDB is not an acceptable HA recovery.

## 14.7 PgBouncer / HAProxy snapshot

On each host that owns PgBouncer:

```sql
SHOW POOLS;
SHOW SERVERS;
SHOW STATS;
```

Use the protected PgBouncer admin/stats DSN and redact credentials from saved output.

Record:

```text
client waiting count
server connection count
server address before/after promotion
unexpected auth failures
reconnect behavior
```

For the PostgreSQL HAProxy route, a read-only SQL query through `:15432` must reach a writable primary. For MQTT/Valkey/OpenBao, use the component-specific checks below rather than assuming an HAProxy process means every backend is healthy.

## 14.8 Valkey / Sentinel snapshot

Check all three data nodes:

```bash
valkey-cli --tls --cacert <VALKEY_CA> \
  -h <VALKEY_PRIVATE_IP> -p 6379 \
  -a '<LOAD_FROM_PROTECTED_SOURCE>' ROLE
```

Check all three Sentinels:

```bash
valkey-cli --tls --cacert <VALKEY_CA> \
  -h <SENTINEL_PRIVATE_IP> -p 26379 \
  -a '<LOAD_SENTINEL_SECRET_PROTECTED>' \
  SENTINEL CKQUORUM lorawan-valkey

valkey-cli --tls --cacert <VALKEY_CA> \
  -h <SENTINEL_PRIVATE_IP> -p 26379 \
  -a '<LOAD_SENTINEL_SECRET_PROTECTED>' \
  SENTINEL GET-MASTER-ADDR-BY-NAME lorawan-valkey
```

Finally query the **application endpoint**:

```bash
valkey-cli --tls --cacert <VALKEY_CA> \
  --sni valkey.internal.lorawan.com \
  -h <LOCAL_HAPROXY_PRIVATE_IP> -p 16379 \
  -a '<LOAD_FROM_PROTECTED_SOURCE>' ROLE
```

Record:

```text
primary before/after
replica count
Sentinel CKQUORUM result
promotion time
HAProxy endpoint role
```

The application endpoint must always report the writable primary/master.

## 14.9 MQTT snapshot

The cloud port ownership must be:

```text
HAProxy public gateway service:       :8883 on ulc-01/ulc-02 anchors
HAProxy ChirpStack workload service:  :18883 on ulc-01/ulc-02 private VPC
HAProxy Node-RED ingest service:      :18884 on ulc-03 private VPC
Mosquitto gateway-facing TLS:         :8884 on ulc-01/ulc-02
Mosquitto Node-RED mTLS:               :8886 on ulc-01/ulc-02
Mosquitto ChirpStack workload TLS:    :8885 on ulc-01/ulc-02
Gateway-local buffer:                 127.0.0.1:1883 on Raspberry Pi only
```

On cloud hosts:

```bash
sudo ss -lntp | grep -E ':(8883|8884|8885|18883|18884)\b' || true
```

Record from HAProxy/Mosquitto logs:

```text
preferred broker health
backup broker health
gateway disconnect/reconnect timestamp
Node-RED/ChirpStack MQTT reconnect if affected
first successful post-switch uplink
```

On the Raspberry Pi also record the local queue/persistence indicators described by the gateway buffer manual before, during, and after a backhaul/broker test.

Do not call successful reconnection proof of broker-session replication. The POC is testing service failover plus the gateway's bounded persistent uplink buffer.

## 14.10 ChirpStack snapshot

Record:

```text
ChirpStack-1 process/HTTP health
ChirpStack-2 process/HTTP health
public https://chirpstack.<DOMAIN> result
gateway last-seen
OTAA result when that test is selected
fresh uplink event ID / sequence
downlink result when that test is selected
```

A running process is not enough. The recovery timer ends only on the first **new post-fault** staging-device uplink accepted through the surviving path, using the definition in [15-failover-chaos-and-acceptance-testing.md](15-failover-chaos-and-acceptance-testing.md).

## 14.10A Node-RED and Grafana snapshot

On `ulc-03`, capture:

```text
Node-RED container state/restart count
Node-RED listener = 127.0.0.1:1880 only
Node-RED private MQTT route :18884 listener/backend health
latest real telemetry event_key/test_sequence stored through Node-RED
Node-RED exported flow hash/reference
Grafana container state/restart count
Grafana listener = 127.0.0.1:3000 only
Grafana datasource identity = telemetry_reader
latest dashboard-visible reading time/age
Grafana dashboard export hash/reference
```

Use a read-only database query to correlate the latest telemetry row with the dashboard. Do not use the Grafana admin credential as evidence that the database path works.

## 14.11 OpenBao snapshot

From an approved OpenBao admin environment:

```bash
bao status
bao operator raft list-peers
```

Through the stable HAProxy endpoint:

```bash
curl --fail --silent --show-error \
  --cacert /etc/lorawan-pki/openbao/ca.crt \
  'https://openbao-kms.internal.<DOMAIN>:18200/v1/sys/health?standbyok=true'
```

Record:

```text
member count
active node
sealed/unsealed state
healthy Raft peer set = 3/3
Transit sign/verify result through stable :18200
current Transit key-version metadata without private key material
Phase 15 will record 2/3 behavior during one-member loss
```

Do not put root tokens, recovery shares, or unseal material in the evidence folder.

## 14.12 Fabric outbox and conditional adapter evidence

The outbox exists even when the adapter implementation is unavailable.

Record status counts with a read-only database role, adapting exact status names to the deployed schema:

```sql
SELECT status, count(*)
FROM telemetry.fabric_outbox
GROUP BY status
ORDER BY status;
```

Also record oldest eligible/pending age using the actual schema timestamp column documented by the outbox migration.

### When the adapter implementation is BLOCKED

Record:

```text
adapter execution: BLOCKED - no reviewed implementation/image
outbox table: available
telemetry/outbox atomic commit: PASS/FAIL
OpenBao HA: PASS/FAIL
external Fabric handoff: COMPLETE/BLOCKED
```

Do not create fake `adapter-1 health` evidence.

### When the reviewed adapter is deployed

Also capture:

```text
adapter-1 process health + worker_id
adapter-2 process health + worker_id
current lease owner
lease expiry/reclaim evidence
Fabric tx ID
commit/reconcile result
```

During an external Fabric outage the expected pattern is:

```text
telemetry still inserts
outbox grows/waits
LoRaWAN stays healthy
outbox later reconciles/drains
```

## 14.12A Gateway-integrity evidence-service capture

Add this section only after the reviewed v2 evidence services are actually deployed. It is distinct from the generic test evidence folder: these files prove the **security lineage services themselves**.

Capture at minimum:

```text
gateway-journal.txt
  journal version/executable hash
  process/restarts
  last sequence/record hash
  open/closed segment IDs
  storage usage/reserve
  unuploaded segment count/bytes
  uploader retry state
  latest accepted checkpoint receipt age

evidence-storage.txt
  backend/path identity without secrets
  free space/capacity
  object count/oldest backlog where meaningful
  no-overwrite/append-only configuration evidence

evidence-ingest.txt
  ingest-1 + ingest-2 process/version/image digest
  per-replica health/restart/OOM/resource state
  listener/SNI/backend identity
  accepted/rejected/conflicting upload counters
  latest accepted checkpoint/segment receipt
  duplicate retry convergence to one identity
  unknown/unauthenticated-client rejection evidence

mqtt-evidence-collector.txt
  collector-1 + collector-2 process/version/image digest
  four persistent broker sessions: each collector -> broker-1 + broker-2
  dedicated client IDs/identity names without secrets
  subscription scope
  collector lag/latest captured gateway event
  deterministic capture_key convergence
  publish/command permission denial result

evidence-verifier.txt
  verifier-1 + verifier-2 process/version/image digest
  identical trusted-decoder digest
  current worker_id/lease state
  oldest pending work
  pending/verified/evidence_gap/integrity_failure counts
  unmatched journal/MQTT/application counts
  checkpoint conflict count
  trusted-decoder mismatch count
  expired-lease reclaim evidence from commissioning/Phase15 as appropriate

trusted-decoder.txt
  decoder_id/version or code hash
  fixed-vector self-test result
  latest raw_app_data_sha256/normalized_digest_sha256 references for the selected event

gateway-evidence-state.txt
  selected source event key/observed_at
  verification_id/status/reason
  journal segment/sequence/hash references
  checkpoint ID
  MQTT gateway_event_id
  verified_at/update age

checkpoint-freshness.txt
  latest accepted checkpoint per gateway
  sequence/segment and server_received_at
  age relative to current UTC
```

Do not copy raw private keys, bearer tokens, unrestricted payload dumps, or OpenBao/Fabric credentials into the Phase 14 folder. Raw segments/events remain in the protected evidence store; Phase 14 records stable IDs, hashes, status, and bounded sanitized excerpts.

Diagnostic rule:

```text
telemetry fresh + MQTT fresh + checkpoint stale
```

means delivery is healthy while the evidence upload/ingest path is degraded. Keep those states separate.

## 14.13 Grafana

Grafana is visual confirmation, not the source of truth for failover timing.

Use the small dashboard for:

```text
latest sensor value
latest timestamp / reading age
RSSI/SNR where stored
small history view
```

Keep a slow refresh interval appropriate to the few-sensor POC. Do not change the 2-GiB resource profile by running aggressive dashboard polling during the sizing test.

## 14.14 Before / during / after capture pattern

For each component, save the same command output three times:

```text
<run-id>/
  before/
    hosts-*.txt
    public-ingress.txt
    etcd.txt
    patroni.txt
    timescale.txt
    pgbouncer-*.txt
    valkey-sentinel.txt
    mqtt.txt
    chirpstack.txt
    openbao.txt
    outbox.txt
    gateway-journal.txt              # when v2 deployed
    evidence-storage.txt             # when v2 deployed
    evidence-ingest.txt              # when v2 deployed
    mqtt-evidence-collector.txt      # when v2 deployed
    evidence-verifier.txt            # when v2 deployed
    trusted-decoder.txt              # when v2 deployed
    gateway-evidence-state.txt       # when v2 deployed
    checkpoint-freshness.txt         # when v2 deployed
  during/
    same files
  after/
    same files
  logs/
    only the bounded/sanitized excerpts needed to explain the transition
  notes.md
```

Screenshots may supplement the folder, but do not replace machine-readable command output.

## 14.15 Pass condition

Observability setup is ready only when a **healthy-state dry run** produces, without undocumented memory:

```text
UTC/run identifier and Phase 13B backup ID
host CPU/memory/swap/OOM evidence
etcd 3/3
Patroni primary/replica/lag state
PgBouncer pool/wait state
Timescale extension/hypertable/latest telemetry state
Valkey/Sentinel primary/quorum state
MQTT backend + HAProxy listener state
ChirpStack-1/2 health + gateway last-seen
Reserved IPv4 current owner + failover timer state
Node-RED state + current flow hash + latest stored event
Grafana state + dashboard hash + latest visible reading age
OpenBao 3/3 + Transit normal-path result
when v2 is selected: journal/uploader + ingest + evidence storage + MQTT collector + verifier + trusted decoder + checkpoint freshness + verification-state evidence
when v2 is selected: one real staging lineage already reached verified before any Fabric v2 seal
Fabric adapter-1/2 + outbox counts + last confirmed tx
```

The harness must also have commands/templates ready to populate the later `during/` and `after/` folders, but **no fault is injected in Phase 14**.

Production monitoring, centralized logs, long retention, alert routing, and SLO dashboards are later hardening, not prerequisites for this small architecture.

Next: [14b-pre-test-commissioning-gate.md](14b-pre-test-commissioning-gate.md). Phase 15 remains blocked until that gate passes.
