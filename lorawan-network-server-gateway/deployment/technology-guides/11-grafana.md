# Grafana — Operator Manual

## What this technology does

Grafana is the read-only visualization layer for telemetry, infrastructure state, and gateway-evidence status. It helps an operator see what the system is doing; it is **not** the authoritative source of research measurements or verification decisions.

## Current commissioned boundary

- Grafana runs on ULC-03.
- Current commissioned cloud build uses Grafana 13.2.0.
- PostgreSQL datasource uses the read-only `telemetry_reader` role.
- Telemetry and gateway-evidence panels are provisioned.
- Counted Chapter IV results come from sealed recorder/run evidence, not screenshots or dashboard refreshes.

## How to open the dashboard from the research workstation

Grafana remains private on ULC-03. The approved Windows workstation runs a dedicated restricted SSH tunnel to ULC-03 loopback port 3000; this is separate from Grafana's normal login. At Windows logon, `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\lorawan-grafana-tunnel.vbs` starts `%LOCALAPPDATA%\LoRaWAN\grafana-tunnel.cmd`, which uses the separately protected `id_ed25519_grafana_tunnel_v2` key. No public port 3000, anonymous login or unrestricted admin key is required.

From the **Windows workstation**, confirm the established tunnel before browsing:

~~~powershell
curl.exe -fsS http://127.0.0.1:3000/api/health
~~~

**PASS:** response includes `database: ok`; open `http://127.0.0.1:3000/d/lorawan-research-cockpit/lorawan-research-test-cockpit?orgId=1&from=now-6h&to=now` in the workstation browser and authenticate using the normal Grafana account. The separate local recorder cockpit is `http://127.0.0.1:8765/`. The older commissioned workstation-access record describes 14 panels / 15-second refresh for this UID; the **latest inspected tracked JSON** in `test/automation/research-recorder/grafana-research-cockpit.json` defines 21 panels / 10-second default refresh. These are dated/source-specific facts, **not proof that the newest JSON has been imported into the running Grafana**. Check the currently deployed UID/panel count/refresh before publishing a live dashboard claim. Data freshness depends on real source events and SQL writes, never refresh interval alone.

If `127.0.0.1:3000` fails, establish whether Grafana on ULC-03 is healthy, whether the restricted tunnel is running and whether the workstation key/startup launcher is present before editing Grafana or opening public firewall rules. The precise tunnel repair/rotation procedure is in `test/automation/research-recorder/GRAFANA-LOCAL-ACCESS.md` for Markdown operators and must be integrated into the comprehensive Word document rather than left as an external prerequisite.

## Step 1 — Check the Grafana runtime

On ULC-03:

```bash
if [ -d /etc/lorawan-cloud/grafana ]; then
  cd /etc/lorawan-cloud/grafana
  sudo docker compose ps
else
  echo 'GRAFANA_PATH_NOT_FOUND=/etc/lorawan-cloud/grafana; inspect current container mounts/Compose labels before recreating'
fi
```

**PASS means:** the Grafana service/container is running without a restart loop.

If the path has deliberately changed, find the current Compose deployment from the cloud runbook/repository before creating a second Grafana instance.

## Step 2 — Check the local HTTP health endpoint

```bash
curl --connect-timeout 3 --max-time 5 -fsS http://127.0.0.1:3000/api/health
```

If the current cloud deployment binds a different approved private/loopback address, use that documented endpoint.

**PASS means:** Grafana returns healthy database/version information.

Do not expose port 3000 publicly just to make this check easy. Use the documented SSH/private access path.

## Step 3 — Check recent logs

```bash
cd /etc/lorawan-cloud/grafana
sudo docker compose logs --since=15m --tail=150 grafana
```

Look for datasource TLS/auth failures, provisioning errors, plugin crashes, database locks, or restart loops.

## Step 4 — Verify the PostgreSQL datasource independently

Before editing a dashboard because it is blank, use a protected read-only database connection and run:

```sql
SELECT now() AT TIME ZONE 'UTC' AS db_utc;

SELECT time, dev_eui, metric_name, metric_value, metric_text, metric_bool, unit, quality
FROM telemetry.measurements
ORDER BY time DESC
LIMIT 20;
```

**PASS means:** the database has current rows and the read-only path works.

If SQL is healthy but Grafana is blank, the problem is now Grafana/query/time-range/provisioning—not ingestion.

## Step 5 — Verify Grafana really uses read-only credentials

The datasource must use `telemetry_reader` or the current reviewed equivalent. It must not use:

- PostgreSQL administrator/superuser;
- `telemetry_writer`;
- gateway-evidence verifier writer;
- Fabric adapter database identity;
- OpenBao token/AppRole;
- Fabric client identity.

A dashboard must never need write authority.

## Step 6 — Verify time range and freshness before declaring data missing

For every operational dashboard, check:

1. browser/Grafana time zone;
2. selected dashboard time range;
3. latest database event timestamp;
4. panel query interval;
5. datasource query result;
6. panel transformation/field mapping.

A stale panel is different from a failed ingestion path. Display freshness explicitly rather than making the operator infer it from a graph shape.

## Step 7 — Verify telemetry panels

A useful sensor panel should make the following obvious when those values exist:

- device/source identity;
- measurement name;
- value and human-readable unit;
- timestamp/age;
- RSSI/SNR/link quality where appropriate;
- battery status;
- no-data/stale state.

Avoid labels such as `unitless`, unexplained percentages, or raw machine field names when a human-readable unit/meaning is available. **EMU-01 USB-only battery rule:** payload `battery_mv=0` is an unavailable-value sentinel, not a physical 0 V or 0% measurement. Current normalized telemetry represents this as `battery_v=NULL` with `quality=invalid`; show “Unavailable (USB-powered)” or a no-data status rather than a fabricated zero or an empty healthy-looking gauge. CPU, RAM, storage and throughput panels must show meaningful units and, when appropriate, numerator and total capacity.

## Step 8 — Verify evidence panels separately from telemetry freshness

Evidence dashboards may display states such as:

```text
pending
verified
evidence_gap
integrity_failure
```

They must not reinterpret a non-verified status as verified.

Keep separate views for:

- telemetry freshness;
- gateway checkpoint/evidence freshness;
- pending verification age;
- verification outcome counts;
- Fabric outbox/reconciliation state.

A fresh sensor row with stale evidence is a real degraded evidence condition, not a completely healthy event.

## Step 9 — Fabric/outbox display rule

When displaying `telemetry.fabric_outbox`, distinguish at minimum:

```text
pending
processing
failed
reconciling
confirmed
needs_attention
dead_letter
```

`submitted_unknown` may exist only as legacy migration compatibility. Do not present it as the current normal uncertain-submit state.

A `pending` row with `attempts=0` does not automatically mean Fabric is down. The dashboard/query should expose enough context to distinguish missing `finalized_payload` or unverified v2 evidence from an adapter-processing failure.

## Safe dashboard/provisioning change procedure

1. verify current Grafana health;
2. verify the datasource directly with SQL;
3. back up/export current dashboard/provisioning state;
4. change one dashboard/query/provisioning item;
5. reload/restart Grafana only if the changed mechanism requires it;
6. verify the panel against a known SQL result;
7. verify time range, unit, freshness, no-data behavior;
8. verify datasource remains read-only;
9. verify counted research results are still sourced from the recorder, not Grafana.

Do not modify Node-RED ingestion or database rows to make a chart look nicer.

## Troubleshooting map

| Symptom | First check |
|---|---|
| Grafana URL unavailable | container/listener/local access path |
| datasource test fails | PgBouncer/DB/TLS/read-only credential |
| SQL has rows, panel blank | dashboard time/query/variable/transformation |
| panel values stale | latest DB timestamp vs dashboard range/refresh |
| wrong unit/label | panel field config/query alias, not sensor ingestion |
| evidence status confusing | verifier tables/query semantics |
| dashboard differs from counted result | recorder/run evidence is authoritative |

## Backup/recovery

Preserve the deployed Compose/config/provisioning/dashboard state and Grafana persistent data according to the cloud backup runbook. Restoring Grafana must not require changing the telemetry database or granting write privileges.

After restore, verify:

1. local `/api/health`;
2. datasource connection;
3. one known telemetry query;
4. one evidence-status query;
5. dashboard units/freshness.

## Completion checklist

- Grafana on ULC-03 is running;
- local health endpoint passes;
- datasource uses a read-only role;
- direct SQL returns expected telemetry;
- dashboards show identity, units, timestamp/freshness, and no-data state clearly;
- evidence status is displayed without changing it;
- Fabric queue states are not oversimplified;
- research results remain sourced from sealed recorder evidence.

## Complete setup, access and panel interpretation companion

Use [Grafana private installation, restricted workstation access, read-only SQL and each research-cockpit panel's units/meaning](GRAFANA-SETUP-PANELS-ACCESS-RECOVERY.md). Older commissioned 4/6/14-panel dashboards must not be conflated with the latest 21-panel JSON stored in the repository; compare its version to live UID before claiming it is deployed.

## Detailed guides

- [`../server/integrations/grafana/00-README.md`](../server/integrations/grafana/00-README.md)
- [`../server/cloud-production/14a-grafana-cloud-deployment.md`](../server/cloud-production/14a-grafana-cloud-deployment.md)
- [`../server/cloud-production/14-observability-alerting-and-logging.md`](../server/cloud-production/14-observability-alerting-and-logging.md)