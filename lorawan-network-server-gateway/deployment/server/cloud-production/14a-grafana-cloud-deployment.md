# 14A. Tiny Grafana POC on ulc-03

> **Status: SERVER-ONLY STAGING + EVIDENCE OBSERVABILITY COMPLETE / PASS; REAL-DATA ACCEPTANCE HARDWARE DEFERRED.** Grafana `13.2.0` is running on `ulc-03` from immutable digest `sha256:3fd54ae1214669f8355f065ec9f6445d5279a3d77095ab048ca045685272429b`, loopback-only on `127.0.0.1:3000`, with strict-TLS `telemetry_reader` datasource health and read-only ACL proof PASS. The provisioned `LoRaWAN Telemetry Overview` now has six panels: the original four telemetry panels plus `Evidence checkpoints` and `Evidence verification state`, both using approved read-only `gateway_evidence` views. The six-panel file was loaded by Grafana provisioning without a restart. `GRAFANA_SERVER_STAGING=PASS` remains authoritative; full Phase 14A still requires a real EMU-01 payload-v2 row and freshness/latest-reading correlation. Grafana is not part of the LoRaWAN control path.

Grafana is only a **small visualization aid** for the HA POC. It is not part of the LoRaWAN control path and it gets no dedicated Droplet.

## 14A.1 Data path

```text
Gateway / device
      |
      v
ChirpStack
      |
      v
Node-RED
      |
      v
lorawan_telemetry database
      |
      v
Grafana
```

The database is the same three-member Patroni PostgreSQL cluster used by ChirpStack. `lorawan_telemetry` has TimescaleDB enabled and stores the telemetry hypertables; there is no separate TimescaleDB server in this POC.

## 14A.2 Resource target

Keep the workload small, but do not impose a hard limit below Grafana's published installation minimum:

```text
Host CPU:      1 shared vCPU; do not add a 0.25-CPU hard cap
Memory limit:  512 MiB
Refresh:       60 seconds
Users:         about 1 operator during the POC
Dashboards:    only the few panels needed for the test
```

Grafana documents 512 MB memory and 1 CPU core as its minimum recommended installation resources. The POC host has only one **shared** vCPU and also runs other services, so this remains an experimental placement rather than a production Grafana sizing claim. Removing the 0.25-CPU cap lets Grafana burst when a dashboard loads instead of creating an artificial CPU bottleneck.

If Grafana reaches the 512-MiB ceiling or materially harms the `ha-03` failure test, record the measurement and resize based on evidence. Do not remove other required architecture features merely to preserve dashboards.

## 14A.3 Preconditions

For **server-only staging now**, require:

- Patroni is healthy with one primary and two replicas;
- `lorawan_telemetry` exists with the commissioned telemetry schema/hypertables;
- `telemetry_reader` exists with read-only permissions and authenticates through the local PgBouncer/HAProxy path;
- `ulc-03` has enough free memory/disk for the 512-MiB Grafana ceiling;
- TCP/3000 is free before first start;
- an exact Grafana image version/digest and its runtime UID/GID are inspected before creating persistent-data ownership;
- the PgBouncer public CA is copied to a Grafana-readable **CA-only** path without loosening `/etc/lorawan-pki/pgbouncer`.

The following is a **final Phase 14A acceptance prerequisite**, not a blocker for server staging:

- Node-RED has stored at least one real **EMU-01 payload-v2** row and duplicate safety has been proven for that event.

An empty query result before hardware returns is expected. The staging gate proves the secure Grafana-to-database path; the later real-reading gate proves telemetry freshness and dashboard semantics.

### Recorded server-only preflight + image pin PASS — 2026-08-29

The `ulc-03` preflight completed without starting Grafana:

```text
TCP/3000 = FREE
host memory = 1.9 GiB total / about 1.2 GiB available
swap = 0
root disk = about 34 GiB available
Node-RED A = healthy, restart_count=0
Grafana running = NO
```

Observed colocated container memory at this checkpoint was approximately `64.6 MiB` for Node-RED A, `31.13 MiB` for OpenBao, `164.6 MiB` for Spilo, and `19.06 MiB` for etcd. This is a preflight snapshot, not a permanent resource guarantee.

The commissioned PgBouncer CA source remained protected as `/etc/lorawan-pki/pgbouncer/ca.crt` (`root:postgres`, mode `0640`) and SHA-256 matched:

```text
6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb
```

Grafana image pin:

```text
release: 13.2.0
immutable image:
  grafana/grafana@sha256:3fd54ae1214669f8355f065ec9f6445d5279a3d77095ab048ca045685272429b
commit:
  f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b
runtime UID: 472
runtime GID: 0
runtime groups: 0
/var/lib/grafana in image: 472:0 mode 777
```

`GRAFANA_SERVER_PREFLIGHT=PASS` and `GRAFANA_SERVER_PREFLIGHT_EXIT=0` are authoritative. The image pull/inspection did not create a Grafana container or listener.

### `telemetry_reader` credential boundary

Repository review found no approved plaintext `telemetry_reader` credential location. PgBouncer contains a valid SCRAM-SHA-256 verifier, but the verifier is intentionally non-reversible and must not be scraped or treated as a password.

Before creating the Grafana data source, either retrieve the existing plaintext from an approved external secret store/custodian or deliberately rotate `telemetry_reader` through PostgreSQL plus all three PgBouncer userlists, verifying each endpoint before staging the replacement password only in Grafana's protected host secret file. Do not grant Grafana `telemetry_writer`, weaken SCRAM/TLS, or place the plaintext in this repository.

Immediate next boundary: resolve that credential custody/rotation decision, then create the Grafana filesystem/public-CA/protected-env/Compose layer from the exact image pin above and keep the first listener loopback-only.

### `telemetry_reader` controlled-rotation preflight PASS — 2026-08-29

The read-only Phase 14A credential preflight on `ulc-03` passed without changing PostgreSQL, PgBouncer, Grafana, or any HA service. Patroni role discovery returned exactly one writable leader: `ulc-01 / 10.104.0.2` with `/leader = 200`, while `ulc-02 / 10.104.0.4` and `ulc-03 / 10.104.0.8` returned `/replica = 200`. Local `ulc-03` PgBouncer remained active/enabled on `10.104.0.8:6432`. PostgreSQL reported `telemetry_reader|true|scram`, proving the role is LOGIN-enabled with a SCRAM-SHA-256 verifier. The protected PgBouncer auth file remained `0640 root:postgres`, contained exactly four entries, and exactly one entry was `telemetry_reader`. Grafana remained absent and TCP/3000 remained free.

The first userlist line-count command used `sudo wc -l < /etc/pgbouncer/userlist.txt`; the invoking non-root shell attempted the redirection before `sudo` and correctly received `Permission denied`. This was a command-harness issue only, not a PgBouncer permission defect. The corrected privileged count returned exactly `4`.

`GRAFANA_TELEMETRY_READER_ROTATION_PREFLIGHT=PASS`. The next bounded mutation is only to generate a new high-entropy `telemetry_reader` password into a root-only pending file on `ulc-03`. Do not alter the PostgreSQL role until that pending file's ownership, mode, length, and format have been verified without printing the secret.

### `telemetry_reader` replacement-secret preparation PASS — 2026-08-29

The replacement reader credential was generated only on `ulc-03` and stored at `/root/grafana-bootstrap/telemetry-reader-password.pending`. The file is `0600 root:root`, exactly 65 bytes, and validated as 64 lowercase hexadecimal characters plus one trailing newline without printing the credential. `GRAFANA_TELEMETRY_READER_SECRET_PREP=PASS`. PostgreSQL and all PgBouncer nodes were still unchanged at this checkpoint.

To reduce operator time without weakening the gate structure, subsequent rotation commands may be grouped into a single child-shell block only when the block verifies each boundary before advancing: rediscover leader -> prove superuser TLS path -> rotate only `telemetry_reader` -> prove direct new-password TLS login -> wait for verifier replication -> regenerate and validate one PgBouncer userlist -> reload in place -> prove new-password authentication through that PgBouncer endpoint. The script must abort at the first failed checkpoint and must never print the plaintext password or SCRAM verifier.

### `telemetry_reader` PostgreSQL rotation + ulc-03 PgBouncer refresh partial PASS — 2026-08-29

The streamlined gated block completed the credential mutation through the `ulc-03` PgBouncer refresh. Patroni was rediscovered immediately before mutation with exactly one leader, `ulc-01 / 10.104.0.2`; the existing Spilo superuser verify-full path to that leader returned `postgres|10.104.0.2|f`. `ALTER ROLE telemetry_reader PASSWORD ...` succeeded without printing the password. A fresh direct verify-full login with the protected replacement credential returned `telemetry_reader|lorawan_telemetry|f`, proving the new PostgreSQL credential itself is valid. The new SCRAM verifier replicated to `ulc-03` immediately, the regenerated four-role PgBouncer candidate passed role/count/SCRAM checks, and the previous auth file was preserved at `/etc/pgbouncer/userlist.txt.before-telemetry-reader-20260829T010150Z`. The installed userlist remained `0640 root:postgres`; PgBouncer reloaded in place with PID `789143` unchanged. These checkpoints are authoritative PASS and must not be repeated merely because the following client probe failed.

The first disposable-client probe stopped **before PgBouncer/SCRAM authentication** because `psql` could not read `/run/pgbouncer/ca.crt` inside that disposable container. The retry changed only the client harness: the exact current Spilo image was run as numeric `0:0`, the mounted CA was proven readable and byte-identical to commissioned SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`, and a verify-full login through physical endpoint `10.104.0.8:6432` using logical host `pgbouncer.internal.lorawan.com` returned `telemetry_reader|lorawan_telemetry|f`. `CONTAINER_CA_READABLE=PASS` and `ULC03_ROTATED_CREDENTIAL_END_TO_END=PASS` are authoritative. No database or service state changed during the retry. Do not repeat the PostgreSQL rotation or the `ulc-03` userlist reload.

### `telemetry_reader` three-node rotation COMPLETE / PASS — 2026-08-29

The remaining two PgBouncer verifier refreshes completed sequentially and safely. `ulc-02` regenerated the authoritative four-role SCRAM userlist from its replicated PostgreSQL state, proved all non-reader verifiers unchanged, preserved `/etc/pgbouncer/userlist.txt.before-telemetry-reader-20260829T010816Z`, installed the new `0640 root:postgres` file, and reloaded PgBouncer in place with PID `787012` unchanged. A verify-full login from `ulc-03` through physical endpoint `10.104.0.4:6432` returned `telemetry_reader|lorawan_telemetry|f`.

Only after `ulc-02` passed, `ulc-01` repeated the same bounded refresh, preserving `/etc/pgbouncer/userlist.txt.before-telemetry-reader-20260829T010820Z` and keeping PgBouncer PID `1105819` unchanged. Verify-full authentication through `10.104.0.2:6432` returned the same expected role/database/writable-primary result. A final all-three gate then authenticated the rotated `telemetry_reader` credential successfully through `10.104.0.2:6432`, `10.104.0.4:6432`, and `10.104.0.8:6432`, while Patroni still showed exactly one leader on `10.104.0.2` and replicas on `.4` and `.8`.

`THREE_NODE_PGBOUNCER_READER_AUTH=PASS`, `FINAL_PATRONI_SINGLE_LEADER=PASS`, and `GRAFANA_TELEMETRY_READER_SECRET_PROMOTION=PASS` are authoritative. The protected password was promoted only after the three-endpoint gate to `/root/grafana-bootstrap/telemetry-reader-password`, remaining `0600 root:root` and 65 bytes. Do not repeat this rotation unless a future authentication failure or deliberate credential-rotation policy requires it.

### Grafana filesystem + trust + protected-config staging PASS — 2026-08-29

The no-start staging block on `ulc-03` completed successfully. `/etc/lorawan-cloud/grafana` is `0750 root:root`; `/srv/grafana/data` is `0700` with numeric owner `472:0`, matching the pinned Grafana runtime; `/etc/lorawan-pki/grafana-pgbouncer` is `0750 root:root`; and its public `ca.crt` is `0640 root:root` with the commissioned SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`. The protected `/etc/lorawan-cloud/grafana/grafana.env` is `0600 root:root`, contains the immutable image pin, a generated Grafana admin credential, and the rotated `telemetry_reader` credential without printing either secret. `/etc/lorawan-cloud/grafana/compose.yml` is `0640 root:root`, validates successfully, binds only `127.0.0.1:3000:3000`, mounts the dedicated CA copy at `/run/pgbouncer/ca.crt`, and maps `pgbouncer.internal.lorawan.com` to `10.104.0.8`.

A disposable container using the exact pinned Grafana image and numeric `472:0` proved the data directory writable and the CA readable and byte-identical. Final safety checks still found no Grafana container and TCP/3000 free. `GRAFANA_HOST_DIRECTORIES=PASS`, `GRAFANA_PGBOUNCER_CA_COPY=PASS`, `GRAFANA_PROTECTED_ENV=PASS`, `GRAFANA_COMPOSE_VALIDATION=PASS`, `GRAFANA_RUNTIME_FILESYSTEM_ACCESS=PASS`, and `GRAFANA_RUNTIME_CA_ACCESS=PASS` are authoritative.

**Grafana 13.2 plugin immutability note:** current Grafana documentation still treats PostgreSQL as bundled/no-install in standard deployments, while the 13.2 source's preinstall registry includes `grafana-postgresql-datasource` and Grafana's generic preinstalled-plugin auto-update setting defaults on. For this immutable POC, set `GF_PLUGINS_PREINSTALL_AUTO_UPDATE=false` before first start so a preinstalled plugin cannot drift independently of the pinned server image. Record the observed PostgreSQL plugin identity/version after startup. Provisioning continues to use the supported `type: postgres` alias.

The next boundary is datasource/dashboard provisioning plus the first controlled Grafana start and runtime verification.

## 14A.4 Minimal container

Run on `ulc-03`. Create a dedicated directory instead of adding Grafana to an unrelated Compose project. Do not choose ownership for `/srv/grafana/data` until the pinned image's numeric runtime UID/GID has been inspected:

```bash
sudo install -d -m 750 /etc/lorawan-cloud/grafana
# create /srv/grafana/data after the image UID/GID gate
cd /etc/lorawan-cloud/grafana
```

Pin `GRAFANA_IMAGE` to an exact tested immutable digest and keep the admin password plus the `telemetry_reader` password in a mode-600 environment file outside Git. Do not place either password in Compose or Markdown. Create `/etc/lorawan-pki/grafana-pgbouncer/ca.crt` as a public CA-only copy of the commissioned PgBouncer CA; the source `/etc/lorawan-pki/pgbouncer` remains protected for the PgBouncer service and must not be made traversable by Grafana.

```yaml
services:
  grafana:
    image: ${GRAFANA_IMAGE}
    restart: unless-stopped
    mem_limit: 512m
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER}
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - /srv/grafana/data:/var/lib/grafana
      - /etc/lorawan-pki/grafana-pgbouncer/ca.crt:/run/pgbouncer/ca.crt:ro
    extra_hosts:
      - "pgbouncer.internal.lorawan.com:10.104.0.8"
```

Do not add a Prometheus stack just to satisfy this POC. Command-line HA checks plus a telemetry dashboard are enough unless infrastructure metrics are part of a specific test.

## 14A.5 Start and open it

```bash
docker compose config --quiet
docker compose up -d grafana
docker compose ps grafana
docker compose logs --since=5m --tail=100 grafana
sudo ss -lntp | grep ':3000'
```

Expected listener:

```text
127.0.0.1:3000
```

From the admin workstation:

```bash
ssh -L 3000:127.0.0.1:3000 <USER>@<HA03_MANAGEMENT_IP>
```

Open `http://127.0.0.1:3000` locally.

## 14A.6 PostgreSQL data source

Use the local HA database path on `ha-03`:

```text
Host: pgbouncer.internal.lorawan.com:6432
Database: lorawan_telemetry
User: telemetry_reader
TLS/SSL: enabled
SSL mode: verify-full (or the equivalent strict hostname+CA mode exposed by the pinned Grafana version)
Root CA: /run/pgbouncer/ca.crt
```

The `extra_hosts` mapping sends this logical name to `ha-03`'s local PgBouncer. Verify the data source with **Save & Test** before building a dashboard. If verification fails, fix the CA/name; do not disable certificate verification as the permanent solution.

Grafana must not use `telemetry_admin`, `telemetry_writer`, `fabric_adapter`, or the ChirpStack database role.

Why: Grafana only reads a few rows for demonstration.

## 14A.7 First dashboard

Keep it tiny:

```text
latest uplink time
reading age
sensor temperature
sensor pressure
RSSI
SNR
last 20 uplinks
```

Only show fields that the device actually sends.

Use the actual generic telemetry schema. For the latest normalized measurements:

```sql
SELECT
    time,
    dev_eui,
    metric_name,
    metric_value,
    metric_text,
    metric_bool,
    unit,
    quality
FROM telemetry.measurements
ORDER BY time DESC
LIMIT 20;
```

For the primary EMU-01 dashboard, select values by approved `metric_name`, for example `barometer_pressure_pa`, `barometer_temperature_c`, `environment_temperature_c`, `environment_humidity_percent`, the two distinct light metrics, soil, UV, rain, and battery. Do not assume a dedicated SQL column exists for every sensor. SEC-02's temporary RAK12011 verification payload is not the permanent dashboard baseline.

## 14A.8 Healthy-state commissioning verification

Do **not** stop Grafana during setup. Instead verify the normal read-only path:

```text
Grafana container = running
listener = 127.0.0.1:3000 only
data source connects as telemetry_reader through ulc-03 PgBouncer/HAProxy
one real Node-RED-stored sensor row is visible
latest-reading age is visible
at least one short historical trend panel is visible
no write-capable database credential is configured
healthy-state memory use is recorded
```

The intended failure behavior remains: if `ulc-03` or Grafana is unavailable, visualization may pause while the LoRaWAN core and persisted PostgreSQL telemetry survive. **Phase 15 tests that claim; Phase 14A does not inject it.**

### Server-only staging PASS boundary

While the gateway is unavailable, Grafana server staging is complete when all of these pass without requiring a telemetry row:

```text
exact immutable Grafana image/digest recorded
container runtime UID/GID recorded
persistent data ownership matches that runtime identity
admin credential stored only in protected host configuration
127.0.0.1:3000 is the only Grafana listener
Grafana starts healthy without a restart loop
pgbouncer.internal.lorawan.com resolves to 10.104.0.8 inside Grafana
/run/pgbouncer/ca.crt is readable and byte-identical to the commissioned PgBouncer CA
PostgreSQL data source authenticates as telemetry_reader with strict TLS verification
read-only schema/catalog query succeeds even when telemetry tables contain zero rows
dashboard/provisioning definition is saved for later real-data validation
```

Record this as `GRAFANA_SERVER_STAGING=PASS`, **not** `PHASE14A=PASS`.

### Server-only Grafana activation COMPLETE / PASS — 2026-08-29

The first controlled Grafana start on `ulc-03` completed the full server-only staging boundary. Grafana started from the pinned 13.2.0 image and reached `/api/health` after 23 seconds with version `13.2.0`, commit `f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b`, runtime state `running|0|false`, and the expected 512 MiB container memory limit. TCP/3000 is exposed only as `127.0.0.1:3000`; no public Grafana listener was created. The runtime also confirmed `GF_PLUGINS_PREINSTALL_AUTO_UPDATE=false`.

Inside Grafana, `pgbouncer.internal.lorawan.com` resolves to `10.104.0.8` and `/run/pgbouncer/ca.crt` remains byte-identical to commissioned SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`. The provisioned PostgreSQL data source resolved at runtime to `grafana-postgresql-datasource`, authenticated as `telemetry_reader`, targeted `lorawan_telemetry` through `pgbouncer.internal.lorawan.com:6432`, and returned datasource health `OK` with `sslmode=verify-full`. Grafana's own data-source query proved `telemetry_reader` has schema usage plus SELECT on `telemetry.uplinks` and `telemetry.measurements`, while INSERT remains denied on both. The empty-table baseline was valid: `uplink_rows=0` and `measurement_rows=0`.

The observed PostgreSQL plugin identity/version is `grafana-postgresql-datasource 13.0.1`. The file-provisioned `LoRaWAN Telemetry Overview` dashboard loaded successfully with four panels: latest uplink/RF quality, reading age, latest selected measurements, and last 20 uplinks. Node-RED A remained `running|0|healthy`; Patroni remained exactly one leader on `10.104.0.2` plus replicas on `.4` and `.8`. Healthy-state container snapshot at this checkpoint was Grafana about `286.8 MiB / 512 MiB` and Node-RED about `75.77 MiB / 1.922 GiB`.

`GRAFANA_SERVER_STAGING=PASS` is now authoritative. Do **not** mark full `PHASE14A=PASS` yet because no real EMU-01 row exists at this server-only checkpoint.

### Synthetic application read-path checkpoint - COMPLETE / PASS with fresh fixture; cleanup pending

Node-RED server commissioning created one intentionally synthetic all-zero-DevEUI payload-v2 fixture and independently proved its telemetry/outbox replay semantics. The first Grafana-own-datasource attempt on 2026-08-30 confirmed Grafana `13.2.0`, commit `f681b1359f6a0b8ecb9f2c49a88ac72b75bde73b`, loopback-only runtime, provisioned datasource UID `lorawan-telemetry` using `telemetry_reader` against `pgbouncer.internal.lorawan.com:6432` with `sslmode=verify-full`, and dashboard UID `lorawan-overview` with the four expected panels. The captured API verifier then stopped after parsing zero base rows.

Later forensics proved that the fixture was not lost through Grafana, Patroni, replication, or Timescale retention: all three members are consistent on timeline `3` with zero lag, Patroni history predates the event, and telemetry has zero Timescale jobs. PostgreSQL statistics show the exact corresponding delete counts (`uplinks=1`, `measurements=13`, `fabric_outbox=1`); ordinary application identities lack DELETE. `ulc-03` shell history contains the targeted cleanup SQL, while the primary `ulc-01` sudo journal records the matching privileged `psql -XAtq` cleanup invocation at `2026-08-29 15:35:09 UTC`. `SYNTHETIC_ROWSET_CLEANUP_ATTRIBUTED=PASS`. The evidence does not establish why that cleanup invocation occurred despite the captured API failure, so do not claim a specific shell-control-flow mechanism.

A fresh fixture `grafana-synthetic-GRAFANA-SYNTH-20260830T000012Z` completed that remaining server-only Grafana data proof. It was inserted from a clean reserved-identity baseline through the exact deployed Node-RED Function and immediately appeared as exactly `1` uplink, `13` measurements, and `1` pending outbox row. Grafana stayed healthy at the existing 512-MiB ceiling. The actual provisioned dashboard targets returned `P1=1`, `P2=1`, `P3=6`, `P4=1` rows, and a code-mode datasource query executed as `telemetry_reader` returned the exact event, all thirteen measurements, the pending outbox row, matching `test_sequence=1788048012`, reading age `5` seconds, and correct latest-view counts. Final database counts remained `1|13|1`; no cleanup ran in the proof block. Evidence is under `/home/opsadmin/lorawan-ha-evidence/GRAFANA-SYNTH-20260830T000012Z`. `GRAFANA_SYNTHETIC_FIXTURE_AND_READ_PATH=PASS` is authoritative for the server-only Grafana read path.

A separate cleanup-only block then re-proved the exact `1|13|1` fixture and its safe pending/unclaimed/unsealed outbox state, discovered exactly one Patroni primary (`10.104.0.2`), and removed only that event in one guarded transaction. The local replica immediately reached `0|0|0`; the reserved synthetic identity returned to `0|0|0`; all three PostgreSQL members independently returned `0|0|0`. Grafana stayed `running|0|false|536870912`, Node-RED A stayed `running|0|healthy`, B remained fenced, and the prior Grafana evidence manifest remained valid while a separate cleanup manifest was added. `GRAFANA_SYNTHETIC_CLEANUP_COMPLETE=PASS` is authoritative. This synthetic result still cannot satisfy the real-sensor freshness requirement below.

### Hardware-dependent final acceptance

After a real EMU-01 payload-v2 event has passed Node-RED/TimescaleDB commissioning, verify the expected dashboard panels show that event, the displayed `test_sequence`/timestamp correspond to the database row, and the freshness/latest-reading-age panel behaves correctly. Only then close the full Phase 14A pass condition.

## 14A.9 Pass condition

- no extra monitoring Droplet exists;
- Grafana stays loopback-only on `ulc-03`;
- it uses only `telemetry_reader`;
- its TLS-verified data source reads `lorawan_telemetry` through PgBouncer/HAProxy;
- real Node-RED-stored sensor values and a short history render correctly;
- the dashboard exposes freshness/latest-reading age needed by the later acceptance tests;
- healthy-state resource use is recorded without OOM evidence.

Next required pre-test setup: [20-openbao-and-fabric-adapter.md](20-openbao-and-fabric-adapter.md), despite its higher file number. Do not begin Phase 15 yet.
