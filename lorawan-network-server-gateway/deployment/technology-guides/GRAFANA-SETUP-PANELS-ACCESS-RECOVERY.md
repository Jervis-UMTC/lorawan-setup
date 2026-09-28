# Grafana — Commissioned Installation, Research Cockpit and Complete Panel Interpretation

**Audience:** operator, thesis researcher and engineer responsible for the real ULC-03 monitoring service. Extends [Grafana operator guide 11](11-grafana.md). This is a technology-level standalone *Markdown* companion, written so the eventual complete PDF can include the required procedures directly. Historical 4/6/14-panel snapshots are not the same artifact as the current tracked research dashboard JSON. A dashboard without rows cannot prove a sensor is transmitting; sealed research-recorder evidence, not a screenshot, is the counted trial source of truth.

## 1. Grafana's actual role

~~~text
EMU-01 -> gateway -> ChirpStack -> active Node-RED -> Patroni PostgreSQL
                                                |-> Grafana read-only SELECT
Independent gateway journal + verifier -------->|-> gateway_evidence read-only views
Eligible exact finalized outbox + HRC commit --->|-> Fabric status read-only view
~~~

Grafana **does not** receive raw RF, process OTAA, normalize measurements, create evidence verdicts, commit blockchain records or repair an ingestion failure. If ULC-03 visualization is lost, the gateway, ChirpStack, replicated database and independently owned evidence/Fabric services may still operate; prove their individual health rather than describing everything as down. The local recorder cockpit on workstation port 8765 is **a separate application**, not a Grafana panel.

## 2. Commissioned ULC-03 deployment contract

| Item | Dated commissioned source |
|---|---|
| Host | ULC-03 / 10.104.0.8 |
| Version | Grafana 13.2.0 |
| Immutable image | `grafana/grafana@sha256:3fd54ae1214669f8355f065ec9f6445d5279a3d77095ab048ca045685272429b` |
| Image/runtime identity | UID 472, GID 0 at image inspection; verify live |
| Browser and API | host **127.0.0.1:3000** only; never expose 3000 publicly |
| Deployment material | `/etc/lorawan-cloud/grafana/`, protected env/Compose/provisioning |
| Persistent data | `/srv/grafana/data` -> container `/var/lib/grafana` |
| Memory | reviewed 512 MiB container limit; observe runtime pressure, do not confuse this with total host RAM |
| PostgreSQL | `pgbouncer.internal.lorawan.com:6432` mapped inside container to `10.104.0.8` |
| Database and identity | `lorawan_telemetry` / **telemetry_reader** only |
| TLS | strict server hostname/CA verification, approved local CA copy `/run/pgbouncer/ca.crt` |
| Browser access | restricted workstation SSH tunnel then normal Grafana authentication |

**Do not follow the generic single-VM lab's `telemetry-db:5432` or `SSL disabled` for this cloud.** It is a different deployment. Grafana cannot use `telemetry_writer`, `telemetry_admin`, Fabric/OpenBao identities or the ChirpStack core DB. The PostgreSQL datasource must not allow INSERT/UPDATE/DELETE.

## 3. Private workstation access — step by step

On Windows research workstation, the commissioned restricted SSH identity is:

~~~text
%USERPROFILE%\.ssh\id_ed25519_grafana_tunnel_v2
~~~

The authorized ULC-03 key is *restricted* to forwarding `127.0.0.1:3000`. The local script `%LOCALAPPDATA%\LoRaWAN\grafana-tunnel.cmd` uses `ssh -N -T`, local `-L 127.0.0.1:3000:127.0.0.1:3000`, strict host key verification, explicit identity and BatchMode. At logon, `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\lorawan-grafana-tunnel.vbs` launches that script. The key is not the operator's unrestricted SSH administration identity. No new public firewall allowance is needed.

From **Windows PowerShell**:

~~~powershell
curl.exe -fsS http://127.0.0.1:3000/api/health
Get-CimInstance Win32_Process -Filter "Name='ssh.exe'" |
  Where-Object { $_.CommandLine -like '*id_ed25519_grafana_tunnel_v2*' } |
  Select-Object ProcessId, CommandLine
~~~

**PASS:** authenticated-to-server tunnel responds with Grafana `database: ok` and expected version, and a single intended tunnel process runs. Open `http://127.0.0.1:3000` in a private browser window and sign in with the ordinary Grafana account. The tunnel **does not** bypass Grafana login. For the approved research dashboard, use UID `lorawan-research-cockpit`; the path is `/d/lorawan-research-cockpit/lorawan-research-test-cockpit` (query parameters may control time range/refresh).

If 127.0.0.1:3000 is closed, first check ULC-03 Grafana, then SSH host connectivity, restricted authorization/key, tunnel process and startup launcher. If the tunnel script succeeds manually but not after logon, repair **only the launcher**, not the Grafana firewall. If the key needs rotation, create a new **dedicated restricted key**, install matching narrow ULC-03 authorization, update launcher, prove health, then retire the old one.

## 4. First inspection of the real server

On **ULC-03 Ubuntu Bash** (not Windows):

~~~bash
hostname -f
date -u
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
sudo ss -lntp | grep ':3000' || true
curl --connect-timeout 3 --max-time 5 -fsS http://127.0.0.1:3000/api/health
sudo docker inspect grafana --format 'Image={{.Image}} Status={{.State.Status}} Restarts={{.RestartCount}}' 2>/dev/null || true
~~~

**PASS:** one intended Grafana process/container, loopback-only port 3000, `database:ok`, no restart loop. Docker may display an image **digest prefix instead of “grafana”**; do not report absent solely because image text lacks the product name. Discover by actual Compose project, container labels, exposed loopback port and inspected mount if name changed.

The approved cloud project was staged under `/etc/lorawan-cloud/grafana`, **not generic `/opt/grafana`**. If it was migrated, use `docker inspect` mounts/Compose labels to find the effective project before recreating files. To observe bounded logs:

~~~bash
cd /etc/lorawan-cloud/grafana
sudo docker compose ps
sudo docker compose logs --since=15m --tail=150 grafana
~~~

Only a currently running/known project is suitable for this read-only command. Do not use `docker compose up` as an inspection probe or restart Grafana to fix a blank panel.

## 5. Fresh installation or isolated replacement

**Prerequisites:** working PostgreSQL/Patroni and a **read-only** `telemetry_reader` with approved SCRAM credentials, local PgBouncer/HAProxy :6432 route, validated internal CA, exact image digest, healthy memory/disk, and protected rollback copy of Grafana state/dashboard exports. A password hash from PgBouncer's userlist cannot be reversed into the plaintext datasource password; retrieve it from approved protected custody or perform a controlled PostgreSQL/PgBouncer credential rotation, verifying every affected route. Do not put plaintext into Markdown.

At a new, empty intended ULC-03 destination, create protected `/etc/lorawan-cloud/grafana` and persistent `/srv/grafana/data`; use UID/GID discovered from the exact image and the approved service account to set owner before first start. Place public PgBouncer CA only in `/etc/lorawan-pki/grafana-pgbouncer/ca.crt`, hash-compare against approved source, and mount it read-only as `/run/pgbouncer/ca.crt`. **Never loosen the whole PgBouncer PKI directory**, whose private material belongs to a different service.

The reviewed cloud Compose essentials (template — first confirm current deployed file and protected env; do not overwrite a running instance):

~~~yaml
services:
  grafana:
    image: grafana/grafana@sha256:3fd54ae1214669f8355f065ec9f6445d5279a3d77095ab048ca045685272429b
    restart: unless-stopped
    mem_limit: 512m
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - /srv/grafana/data:/var/lib/grafana
      - /etc/lorawan-pki/grafana-pgbouncer/ca.crt:/run/pgbouncer/ca.crt:ro
    extra_hosts:
      - "pgbouncer.internal.lorawan.com:10.104.0.8"
~~~

The complete approved deployment also supplies **protected** admin and reader credentials and the versioned provisioning files through the current reviewed host runtime; the example above deliberately cannot function as a full substitute for secrets and volume ownership. The initial admin password env initializes a **new** Grafana database but does not automatically reset existing accounts when persistent data exists.

After reviewing full deployment definition and copying protected state (fresh build only):

~~~bash
cd /etc/lorawan-cloud/grafana
sudo docker compose config --quiet
sudo docker compose up -d grafana
sudo docker compose ps grafana
curl --connect-timeout 3 --max-time 5 -fsS http://127.0.0.1:3000/api/health
~~~

**PASS:** service starts from approved digest without a restart/OOM loop; private listener only. Avoid a hard 0.25-vCPU cap on a small shared-vCPU host without performance evidence; the commissioned 512-MiB RAM ceiling is already a meaningful resource constraint.

### 5.1 Configure the database read-only route

In Grafana `Connections -> Data sources -> PostgreSQL` set:

~~~text
Host: pgbouncer.internal.lorawan.com:6432
Database: lorawan_telemetry
User: telemetry_reader
TLS / SSL mode: verify-full
CA file or PEM: approved /run/pgbouncer/ca.crt
PostgreSQL version: match the actual primary
~~~

On this deployment, `pgbouncer.internal.lorawan.com` maps locally to `10.104.0.8` inside the Grafana container. The peer certificate must still verify **the logical hostname**. Save & Test, then run a SELECT from `telemetry.uplinks` or `telemetry.measurements`. A green datasource ping establishes authenticated SQL only; a recent real uplink is separate acceptance. If the connection fails, do not disable SSL or grant a writer role. Confirm DNS/CA/SAN, PgBouncer :6432, HAProxy :15432 and Patroni leader at their own layers.

~~~sql
SELECT now() AT TIME ZONE 'UTC' AS db_utc;
SELECT time, dev_eui, metric_name, metric_value, metric_text, metric_bool, unit, quality
FROM telemetry.measurements
ORDER BY time DESC LIMIT 20;
~~~

## 6. Understand exactly what is deployed versus tracked

The **original 2026-08-29 server-only** `lorawan-overview` dashboard had **four** panels; the 2026-09-01 file-provisioned Telemetry Overview had **six** including evidence checkpoints and verification state. A later workstation access record described research-cockpit UID `lorawan-research-cockpit` with **14 panels / 15-second refresh**. The **currently inspected repository JSON** at `test/automation/research-recorder/grafana-research-cockpit.json` defines **21 panels and dashboard default `refresh="10s"`**. These are *different dated artifacts*. The **latest tracked JSON is not automatically proven imported into the running Grafana service**. Before publishing a final panel count, query the live Grafana dashboard UID under authenticated read-only API or inspect its current provisioned JSON and compare the source/hash. Update deployment and workstation documentation only after distinguishing source from live.

Refresh 10 s means Grafana **reissues queries roughly every ten seconds while the dashboard is open**; it is **not** the sensor sampling rate, real-time streaming, MQTT confirmation, nor assurance that RF packets arrive each refresh. EMU-01 normal production cadence is nominal **300 seconds with +/-15-second jitter**; research firmware may use a deliberately frozen faster counted profile, typically 15 seconds. With production cadence, five minutes without a new reading may be expected near a reporting boundary; use the actual active firmware/profile and a documented grace interval before declaring stale.

## 7. Full research-cockpit panel reference (tracked 21-panel JSON)

This table describes the **current tracked source definition**, which must be reconciled with the live deployed UID before release. Numbers/units are derived from source SQL, not cosmetic labels:

| # | Panel | What the panel measures / interpreting its unit |
|---:|---|---|
| 1 | Last sensor packet age | Seconds since latest recorded `telemetry.uplinks.time` for EMU-01. High value = stale arrival/time, not necessarily radio outage. No rows => no data, not age zero. |
| 2 | Packets last 5 min | Count of recorded canonical EMU-01 uplinks in a rolling 5-minute window. This is **database arrival count**, not RF attempts or successful joins. |
| 3 | App -> DB delay (5 min avg) | Mean of `(received_at - time) * 1000`, **milliseconds**, for rows in latest 5 minutes. Includes whatever timestamp semantics the source event uses; it is not pure radio propagation or Fabric commit latency. |
| 4 | Latest RSSI | Latest ChirpStack reception RSSI in **dBm**, often negative. A less negative value means stronger received power, subject to radio/environment differences. |
| 5 | Latest SNR | Latest signal-to-noise ratio in **dB**; may be negative on valid LoRa links. |
| 6 | Evidence issues | Count of evidence rows labeled `evidence_gap` or `integrity_failure` by the verifier view. A zero count is not proof that every new message was verified. |
| 7 | Latest agriculture readings | Table of most recently stored normalized EMU-01 metrics with units/quality/time, not a list of live analog sensor pins. |
| 8 | Temperature history | Time-series degrees C for approved distinct temperature metrics; don't merge soil, barometer and ambient into one mislabeled series. |
| 9 | Humidity & soil moisture | Percentage values on labeled distinct curves. Soil moisture is a device-mapped measurement, not necessarily laboratory-grade volumetric water content. |
| 10 | Pressure history | kPa; SQL converts original **Pa ÷ 1000**, rather than renaming Pa as kPa. |
| 11 | Light history | Lux (lx); VEML7700 and OPT3001 separate series when present. |
| 12 | Gas resistance | kOhm; SQL converts **ohm ÷ 1000**. It is resistance, not an air-quality index or gas concentration. |
| 13 | UV index | Dimensionless **UV index**; the dashboard unit field may be “none” but the title/value meaning must say index. |
| 14 | Battery voltage | Volts from valid positive battery metric; the USB-powered 0 sentinel means **unavailable**, not 0 V/0%. No-valid-reading is appropriate. |
| 15 | Rain / wet history | Binary 1 wet / 0 dry per bool mapping; display legend, not “percent rain”. |
| 16 | RF signal strength | Historical RSSI dBm for accepted uplinks in selected time window. |
| 17 | RF signal quality | Historical SNR dB for accepted uplinks in selected time window. |
| 18 | Application -> database delay | Per-uplink `(received_at-time) * 1000` in ms. Separate this from #3 averaged statistic. |
| 19 | Recent LoRaWAN packets | Table of stored source/time/device/event and link fields; inspect device identity and timestamp to distinguish EMU-01 from other sources. |
| 20 | Fabric delivery summary | Grouped **database outbox state** (committed vs waiting/retrying/needs attention); cannot prove external ledger finality without authoritative Fabric query/digest reconciliation. |
| 21 | Evidence verification summary | Counts grouped by verifier state; only `verified` is verifier-confirmed, while pending/gap/failure must remain distinct. |

To make future per-device monitoring scalable, parameterize *reviewed* queries with an allowed device variable rather than editing all 21 panels' hard-coded DevEUI independently. Current research-cockpit JSON includes EMU-01-specific SQL and a recent-packet identity table; never claim full sensor-fleet coverage without checking actual variables/queries. Read `metric_name`, `unit`, `quality` and `dev_eui` from the DB; the device model mapping controls their meaning. Keep timestamps in UTC in database and explicit Asia/Manila or user-local Grafana display.

## 8. How to observe a fresh real message in the panel

1. Confirm physical device is powered and has an approved firmware/profile. Do not use synthetic data as proof of RF or a counted trial.
2. Record the starting UTC time and DevEUI, then observe a **new** event at ChirpStack and through the one active Node-RED instance.
3. Query SQL independently for new accepted uplinks and normalized measurements:

~~~sql
SELECT dev_eui,time,received_at,f_cnt,rssi_dbm,snr_db
FROM telemetry.uplinks
ORDER BY time DESC LIMIT 20;
SELECT dev_eui,time,metric_name,metric_value,metric_bool,unit,quality
FROM telemetry.measurements
ORDER BY time DESC,metric_name LIMIT 30;
~~~

4. Set Grafana time range to contain the event (e.g. last 6 hours), refresh/reopen the correct dashboard, and select the right device. Check #1/#2/#7/#19 and one history panel for the same timestamp.
5. Independently check evidence #6/#21 and Fabric #20 if those properties matter. A fresh sensor row can coexist with pending/missing gateway evidence; do not erase that difference.

**PASS:** the SQL source matches the displayed device, timestamp, measured values and unit; the displayed freshness age moves with the last observed event. No data => inspect SQL, then ChirpStack/Node-RED and only then RF/route; a dashboard refresh never creates source packets.

## 9. Restoration and common problems

| Problem | First failing boundary | Fix |
|---|---|---|
| browser localhost:3000 inaccessible | ULC-03 Grafana loopback or workstation SSH forward | verify API on ULC-03, dedicated process/launcher/restricted key; don't open public 3000 |
| Grafana up, datasource fails | CA/hostname, PgBouncer/HAProxy, telemetry_reader | restore strictly verified read-only SQL route |
| SQL has fresh rows, panel empty | UID, panel query, time picker, device hard-code, transformation | compare raw SQL with one known row, check panel variables |
| dashboard #6/#21 confusing | gateway_evidence verifier view | retain pending/gap/failure states rather than hiding or relabeling |
| battery shows zero | USB sentinel or invalid normalized field | display “Unavailable (USB-powered)”/no-data |
| delay appears negative | source UTC/clock discrepancy or timestamp semantics | verify clock and event-time behavior; do not clamp invalid experimental data silently |
| high dashboard memory | limit/panel count/query cost | inspect actual `docker stats` and SQL query latency, reduce unnecessary queries first |
| research result differs from chart | recorder versus dashboard aggregation/window | rely on sealed recorder for counted trials; record query/window definitions |

For backup preserve approved Docker/Compose/provisioning config, immutable image digest, persistent Grafana state, read-only datasource identity/CA custody, dashboard JSON/UID, alerts, access/tunnel restricted identity, and off-host manifest. Back up Grafana's SQLite or other actual configured Grafana metadata store **consistently** (quiesce Grafana or approved snapshot mechanism), but do not restart/stop it just to edit Markdown. Restore the old accepted image and metadata volume as a compatible pair after schema changes; do not clear dashboards or PostgreSQL telemetry. The 2026-08-29 commissioning used a 512-MiB limit: monitor utilization rather than promising permanent capacity on the shared 1-vCPU ULC-03.

**Recovery PASS:** private health API, read-only TLS SQL, expected dashboard UID/panel source, visible current data + freshness/unit/no-data semantics and unchanged research/evidence authority. A six-panel 2026-09-01 baseline is not the final 21-panel research dashboard, and vice versa. Retain both versions' provenance in docs.

Sources for maintaining Markdown: [cloud Grafana commissioning](../server/cloud-production/14a-grafana-cloud-deployment.md), [workstation tunnel](../../test/automation/research-recorder/GRAFANA-LOCAL-ACCESS.md), [current tracked cockpit JSON](../../test/automation/research-recorder/grafana-research-cockpit.json), [operator guide 11](11-grafana.md). The finished Word document must contain necessary commands, dashboard explanations, figures and access/recovery steps *within the book*, not require these source links.
