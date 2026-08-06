# Data 3. Deploy Grafana and Monitor the Pipeline

Grafana reads only the telemetry database. It does not connect to the concentrator, Fabric peer, Fabric private key, or ChirpStack administrator database.

## Step 1: Add private Grafana variables

Add to `/opt/chirpstack-docker/.env`:

```dotenv
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<REPLACE_WITH_LONG_UNIQUE_PASSWORD>
```

Keep `.env` mode `600`.

## Step 2: Add Grafana to Compose

```yaml
  grafana:
    image: <PINNED_GRAFANA_IMAGE>
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      GF_SECURITY_ADMIN_USER: ${GRAFANA_ADMIN_USER}
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      GF_USERS_ALLOW_SIGN_UP: "false"
      GF_AUTH_ANONYMOUS_ENABLED: "false"
    volumes:
      - grafana-data:/var/lib/grafana
    depends_on:
      telemetry-db:
        condition: service_healthy
```

Declare:

```yaml
volumes:
  grafana-data:
```

## Step 3: Start and open through a tunnel

```bash
docker compose config --quiet
docker compose up -d grafana
docker compose ps grafana
sudo ss -lntp | grep ':3000'
```

From the operator workstation:

```bash
ssh -L 3000:127.0.0.1:3000 <SERVER_USER>@<LAB_SERVER_IP_ADDRESS>
```

Open `http://127.0.0.1:3000` and change the first-use administrator password when required.

## Step 4: Add the PostgreSQL data source

Follow [`server/integrations/grafana/01-install-and-connect.md`](../../integrations/grafana/01-install-and-connect.md) with:

```text
Host: telemetry-db:5432
Database: lorawan_telemetry
User: telemetry_reader
TimescaleDB: enabled
SSL: disabled only because the connection stays inside the private Compose network
```

The role must have `SELECT` only. Enter the telemetry-reader password through the Grafana data-source form or approved provisioning mechanism; do not add an unused password variable to Compose.

## Step 5: Build the required dashboards

Use the existing dashboard guide, then add these operational panels:

| Panel | Source |
|---|---|
| Latest sensor values and freshness | `telemetry.latest_measurements` |
| Uplinks per device | `telemetry.uplinks` |
| RSSI and SNR trend | `telemetry.uplinks` |
| Pending and failed Fabric jobs | `telemetry.fabric_outbox` |
| Oldest retry-eligible Fabric job | `telemetry.fabric_outbox` |
| Expired processing leases | `telemetry.fabric_outbox` |
| Submitted-unknown jobs and age | `telemetry.fabric_outbox` |
| Confirmed and failed ledger submissions | `telemetry.fabric_outbox` |
| Fabric commit latency | `committed_at - submitted_at` |
| Dead-letter jobs | `telemetry.fabric_outbox` |

Example queue query:

```sql
SELECT
  status,
  count(*) AS jobs
FROM telemetry.fabric_outbox
GROUP BY status
ORDER BY status;
```

Example oldest retry-eligible query:

```sql
SELECT
  EXTRACT(EPOCH FROM (now() - min(created_at))) AS oldest_retry_eligible_seconds
FROM telemetry.fabric_outbox
WHERE status IN ('pending','failed');
```

Example expired-lease query:

```sql
SELECT count(*) AS expired_processing_leases
FROM telemetry.fabric_outbox
WHERE status = 'processing'
  AND lease_expires_at <= now();
```

Example submitted-unknown query:

```sql
SELECT
  count(*) AS submitted_unknown_jobs,
  EXTRACT(EPOCH FROM (now() - min(updated_at))) AS oldest_unknown_seconds
FROM telemetry.fabric_outbox
WHERE status = 'submitted_unknown';
```

Keep these states separate. A pending or failed item is retry-eligible, an expired processing lease is reclaimable, and a submitted-unknown item requires ledger reconciliation before retry.

The outbox table is added in the Fabric guide. Dashboard queries should show `no data` before that migration instead of silently failing.

## Step 6: Create alerts

At minimum, alert on:

- no recent uplink from an expected active device;
- continuously growing Fabric queue;
- oldest pending Fabric job beyond the approved delay;
- dead-letter count greater than zero;
- telemetry database free space below the approved threshold.

A Fabric alert must not trigger an automatic deletion or replay. Operators inspect the event key, error category, and ledger state first.
