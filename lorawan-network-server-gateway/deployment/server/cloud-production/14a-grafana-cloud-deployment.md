# 14A. Tiny Grafana POC on ha-03

> **Status: STANDBY / DRAFT.** Grafana is not yet deployed or live-validated in the current cloud build. Re-check the exact image/version, database path, authentication, dashboards, and resource use when this phase becomes active.

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

Before Grafana:

- Patroni is healthy with one primary and two replicas;
- `lorawan_telemetry` exists;
- Node-RED has stored at least one real **EMU-01 payload-v2** row;
- `telemetry_reader` exists with read-only permissions;
- `ha-03` local PgBouncer/HAProxy database path works.

## 14A.4 Minimal container

Run on `ha-03`. Create a dedicated directory instead of adding Grafana to an unrelated Compose project:

```bash
sudo install -d -m 750 /etc/lorawan-cloud/grafana
sudo install -d -m 700 /srv/grafana/data
cd /etc/lorawan-cloud/grafana
```

Set `GRAFANA_IMAGE` to an exact tested tag or immutable digest and keep the admin password in a mode-600 environment file outside Git.

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
      - /etc/lorawan-pki/pgbouncer/ca.crt:/run/pgbouncer/ca.crt:ro
    extra_hosts:
      - "pgbouncer.internal.lorawan.com:<HA03_PRIVATE_IP>"
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

## 14A.8 Failure behavior

Stop Grafana:

```bash
docker compose stop grafana
```

Send another sensor uplink.

Pass when:

```text
ChirpStack continues
Node-RED continues
PostgreSQL stores the row
existing Fabric outbox remains available; deployed adapters can still process it when the adapter implementation exists
```

Restart Grafana and verify the new row appears.

If all of `ha-03` fails, Grafana and Node-RED pause. That is an accepted POC limitation. The PostgreSQL database and existing outbox must still survive on the other Patroni members.

## 14A.9 Pass condition

- no extra monitoring Droplet exists;
- Grafana stays loopback-only;
- it uses `telemetry_reader`;
- it reads `lorawan_telemetry` through PgBouncer/HAProxy;
- stopping Grafana does not affect the LoRaWAN control plane;
- its memory use does not cause the 2-GiB host to OOM during the POC.

Next standby phase: [15-failover-chaos-and-acceptance-testing.md](15-failover-chaos-and-acceptance-testing.md). Keep [19-cloud-ha-grafana-deployment-day-runbook.md](19-cloud-ha-grafana-deployment-day-runbook.md) as a sequence reference, not as a second source of completed-state evidence.
