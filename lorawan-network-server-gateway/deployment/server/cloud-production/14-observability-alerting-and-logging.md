# 14. Minimal POC Observability and Evidence Capture

> **Status: REQUIRED PRE-TEST SETUP / DRAFT.** After Phase 13B, run this evidence harness once against the **fully healthy system without injecting any fault**. The purpose is to prove every command, permission, evidence path, and timestamp field works before Phase 15.

The POC needs **repeatable evidence**, not a production monitoring platform.

Do not deploy Prometheus, Alertmanager, Loki, or another monitoring stack merely to prove the three-server architecture. For a few sensors, command-line checks, service logs, a small Grafana telemetry dashboard, and timestamped evidence folders are enough.

The important rule is:

> First prove the evidence harness on a fully healthy baseline. Only after Phase 14B passes should the same capture set be used before, during, and after Phase 15 failures.

### Phase 14 healthy-baseline dry run

Create a normal evidence directory and populate the `before/` state for every deployed component. Do not create a fake `during/` failure state. Verify all commands run non-interactively with the intended least-privilege access, timestamps are UTC, and no secrets are copied into evidence.

The dry run must include Node-RED, Grafana, OpenBao, both Fabric adapters, the latest normal Fabric commit, the current Reserved-IP owner, and the final Phase 13B backup-set identifier.

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
Mosquitto gateway/Node-RED mTLS:      :8884 on ulc-01/ulc-02
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
Fabric adapter-1/2 + outbox counts + last confirmed tx
```

The harness must also have commands/templates ready to populate the later `during/` and `after/` folders, but **no fault is injected in Phase 14**.

Production monitoring, centralized logs, long retention, alert routing, and SLO dashboards are later hardening, not prerequisites for this small architecture.

Next: [14b-pre-test-commissioning-gate.md](14b-pre-test-commissioning-gate.md). Phase 15 remains blocked until that gate passes.
