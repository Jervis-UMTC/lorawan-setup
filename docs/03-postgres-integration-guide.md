# ChirpStack v4 PostgreSQL Integration & Event Persistence Guide

This technical guide provides an **exhaustive, production-grade procedure** for configuring, deploying, and maintaining the **PostgreSQL Event Integration** in **ChirpStack v4** running within a Dockerized environment.

By default, ChirpStack utilizes an internal PostgreSQL database to store network server state, tenant metadata, application profiles, device keys, and session data. Enabling the **PostgreSQL Integration** configures ChirpStack to automatically stream decoded uplink telemetry, OTAA join events, acknowledgments, device status updates, and location data into a dedicated integration database schema. This enables historical analytics, reporting, and direct integration with BI tools (such as Grafana, Metabase, or PowerBI).

---

## 📌 Architecture & Data Flow

```text
+-----------------------------------------------------------------------------------+
|                        LoRaWAN End-Nodes & Gateways                               |
+-----------------------------------------------------------------------------------+
                                         |
                                         | Semtech UDP / MQTT Uplink
                                         v
+-----------------------------------------------------------------------------------+
|                       ChirpStack v4 Core Network Server                           |
|  • Decodes Hex Payload using Device Profile JavaScript Codec                       |
|  • Processes MAC Commands & Frame Counters                                       |
+-----------------------------------------------------------------------------------+
                                         |
                                         | Integration Event Dispatcher
                                         v
+-----------------------------------------------------------------------------------+
|                   PostgreSQL Database Container (Port 5432)                       |
|                                                                                   |
|  +-----------------------------------+     +-----------------------------------+  |
|  | Database: chirpstack              |     | Database: chirpstack_integration  |  |
|  | Owner: chirpstack                 |     | Owner: chirpstack_integration     |  |
|  | Role: Network State & Metadata    |     | Role: Long-Term Event Storage     |  |
|  +-----------------------------------+     +-----------------------------------+  |
|                                                     |                             |
|                                                     | Decoded JSON Event Tables   |
|                                                     v                             |
|                                            • event_up                             |
|                                            • event_join                           |
|                                            • event_ack                            |
|                                            • event_status                         |
|                                            • event_location                       |
+-----------------------------------------------------------------------------------+
```

---

## 🧠 DEEP TECHNICAL BACKING EXPLANATIONS & ARCHITECTURAL RATIONALE

### 1. Why Separate the `chirpstack_integration` Database from the `chirpstack` Core Database?
In ChirpStack v4, the network server relies on PostgreSQL for two fundamentally different workloads:
* **Core Network State (`chirpstack` database)**: Stores low-latency relational state including Tenants, Users, Applications, Device Profiles, Device Keys (`AppKey`, `NwkSKey`, `AppSKey`), and active Frame Counters (`FCntUp`, `FCntDown`). This database executes frequent, short-lived transactional reads and updates (`SELECT`, `UPDATE`).
* **Telemetry Event Stream (`chirpstack_integration` database)**: Stores high-volume, append-only sensor telemetry streams (`INSERT`). A single LoRaWAN network with 100 sensors transmitting every minute writes over 144,000 row records daily.

**Architectural Risk of Unified Storage**: Storing telemetry events inside the core `chirpstack` database leads to heavy Write-Ahead Log (WAL) expansion, table bloat, index fragmentation, and database lock contention. If an external BI tool (like Grafana or PowerBI) executes a heavy analytical query scanning historical data, it could lock core tables and freeze network server MAC processing, causing dropped LoRaWAN frames and failed OTAA join activations. Creating a dedicated `chirpstack_integration` database isolates analytical loads from core network server state.

### 2. Why Does ChirpStack Store Payloads in PostgreSQL `JSONB` Columns?
LoRaWAN end-nodes (such as environmental sensors, water meters, and asset trackers) transmit diverse data structures. The `event_up` table uses a `JSONB` column named `object` to store the decoded output of JavaScript codecs:
* **Binary Storage Efficiency**: PostgreSQL `JSONB` parses JSON text into a decomposed binary format at insert time, eliminating redundant whitespace and duplicate key parsing overhead.
* **Schema Agnosticism**: Heterogeneous sensors with varying payload formats (e.g. Temperature/Humidity vs GPS coordinates) can be stored in the same `event_up` table without requiring database schema DDL migrations (`ALTER TABLE`) whenever a new sensor model is onboarded.
* **GIN Indexing**: `JSONB` supports Generalized Inverted Index (GIN) indexing, enabling sub-millisecond query performance when filtering by arbitrary nested keys (`object @> '{"Alarm": "TRUE"}'`).

### 3. Connection Pooling & Resource Tuning Rationale
In `chirpstack.toml`, the PostgreSQL integration block exposes connection pool parameters:
```toml
max_open_connections = 10
min_idle_connections = 0
```
* **`max_open_connections = 10`**: Prevents ChirpStack worker threads from exhausting PostgreSQL's `max_connections` limit. In Dockerized environments, each open connection consumes ~2MB to 10MB of RAM inside the Postgres container. Restricting maximum open connections caps RAM usage while guaranteeing thread safety.
* **`min_idle_connections = 0`**: Ensures that idle connections are aggressively closed when telemetry traffic subsides, freeing memory on the host VM.

---

## ⚠️ PREREQUISITES & ENVIRONMENT CHECK

Before executing these steps, ensure:
1. ChirpStack v4 Docker stack is installed and running (`chirpstack-docker`).
2. You are connected to your main management network (or VM terminal) with administrative (`sudo`) access.
3. PostgreSQL container `chirpstack-docker-postgres-1` (or `postgres`) is active.

Verify container status:
```bash
sudo docker ps | grep postgres
```

---

## 🔑 STEP 1: PROVISION INTEGRATION DATABASE & ROLE IN DOCKER

To isolate telemetry event data from ChirpStack’s operational metadata, you must create a dedicated PostgreSQL role and database.

### 1.1 Access PostgreSQL CLI inside the Container
Run the following command to enter the `psql` interactive prompt as the default `chirpstack` superuser:

```bash
sudo docker exec -it chirpstack-docker-postgres-1 psql -U chirpstack -d chirpstack
```
*(If your container is named `postgres`, replace `chirpstack-docker-postgres-1` with `postgres`)*.

### 1.2 Create Dedicated Integration Role & Database
At the `chirpstack=#` prompt, execute the following SQL commands:

```sql
-- 1. Create a dedicated authentication role with a secure password
CREATE ROLE chirpstack_integration WITH LOGIN PASSWORD 'chirpstack_integration';

-- 2. Create the integration database owned by the new role
CREATE DATABASE chirpstack_integration WITH OWNER chirpstack_integration;

-- 3. Grant full privileges on the new database and public schema
GRANT ALL PRIVILEGES ON DATABASE chirpstack_integration TO chirpstack_integration;
\c chirpstack_integration
GRANT ALL ON SCHEMA public TO chirpstack_integration;

-- 4. Exit psql prompt
\q
```

> 💡 **Security Recommendation**: In production environments, replace `'chirpstack_integration'` with a strong, randomly generated password and store it in your environment secret manager.

---

## ⚙️ STEP 2: CONFIGURE CHIRPSTACK TOML CONFIGURATION FILE

Next, update ChirpStack's main configuration file (`chirpstack.toml`) to enable the PostgreSQL integration and supply the Data Source Name (DSN).

### 2.1 Navigate to Configuration Directory
```bash
cd ~/chirpstack-docker
cd configuration/chirpstack
ls -la
```

### 2.2 Edit `chirpstack.toml`
Open `chirpstack.toml` using `nano` or your preferred text editor:
```bash
sudo nano chirpstack.toml
```

### 2.3 Enable PostgreSQL Integration
Locate the `[integration]` block and add `"postgresql"` to the `enabled` list:

```toml
[integration]
enabled=["mqtt", "postgresql"]
```

### 2.4 Configure `[integration.postgresql]` Data Source Name (DSN)
Scroll to or append the `[integration.postgresql]` section and configure the DSN connection string:

```toml
[integration.postgresql]
# DSN connection string format:
# postgres://<USERNAME>:<PASSWORD>@<HOST>:<PORT>/<DATABASE>?sslmode=disable

dsn="postgres://chirpstack_integration:chirpstack_integration@postgres:5432/chirpstack_integration?sslmode=disable"

# Optional Connection Pool Tuning Settings
max_open_connections=10
min_idle_connections=0
```

> 🔑 **DSN Parameter Breakdown**:
> * **`chirpstack_integration` (1st)**: Username created in Step 1.
> * **`chirpstack_integration` (2nd)**: Password created in Step 1.
> * **`postgres:5432`**: Container hostname and port for PostgreSQL inside the Docker network (`postgres` or `postgres:5432`). *Note: Do not use `$POSTGRESQL_HOST` in `chirpstack.toml` as TOML files do not expand shell environment variables.*
> * **`chirpstack_integration` (3rd)**: Target database name created in Step 1.
> * **`sslmode=disable`**: Disables TLS encryption for internal container-to-container network traffic.

Save changes (`Ctrl + O`, `Enter`) and exit (`Ctrl + X`).

---

## 🔄 STEP 3: RESTART DOCKER CONTAINER STACK

For ChirpStack to load the updated `chirpstack.toml` and initialize the PostgreSQL migration schema, restart the Docker Compose stack:

```bash
cd ~/chirpstack-docker
sudo docker compose down
sudo docker compose up -d
```

Check the ChirpStack service logs to confirm successful database connection and schema migration execution:

```bash
sudo docker compose logs -f chirpstack
```
*Look for*: `Initializing PostgreSQL integration` and `Applying schema migrations` (under the `chirpstack::integration::postgresql` log module).

---

## 🔬 STEP 4: VERIFY DATABASE SCHEMA & TABLES

Once restarted, ChirpStack automatically creates the necessary tables in the `chirpstack_integration` database.

### 4.1 Log into Integration Database CLI
```bash
sudo docker exec -it chirpstack-docker-postgres-1 psql -U chirpstack_integration -d chirpstack_integration
```

### 4.2 List Databases
```sql
\l
```
*Confirm that `chirpstack_integration` is listed with owner `chirpstack_integration`.*

### 4.3 Connect to `chirpstack_integration` Database
```sql
\c chirpstack_integration
```

### 4.4 List Relational Data Tables
```sql
\dt
```

*Expected Schema Output*:
```text
               List of relations
 Schema |          Name          | Type  |         Owner         
--------+------------------------+-------+-----------------------
 public | _diesel_schema_migrations | table | chirpstack_integration
 public | event_ack              | table | chirpstack_integration
 public | event_integration      | table | chirpstack_integration
 public | event_join             | table | chirpstack_integration
 public | event_location         | table | chirpstack_integration
 public | event_log              | table | chirpstack_integration
 public | event_status           | table | chirpstack_integration
 public | event_tx_ack           | table | chirpstack_integration
 public | event_up               | table | chirpstack_integration
(9 rows)
```

---

## 📊 STEP 5: ADVANCED SQL QUERIES & DATA ANALYTICS

ChirpStack stores decoded telemetry objects in JSONB format inside the `object` column of the `event_up` table. You can execute high-performance SQL queries directly against this JSON data.

### 5.1 Query Decoded Dragino Sensor Telemetry (`TempC_SHT31`, `Hum_SHT31`, `BatV`)
```sql
SELECT 
    deduplication_id,
    time AS timestamp,
    dev_eui,
    device_name,
    (object->>'TempC_SHT31')::numeric AS temperature_c,
    (object->>'Hum_SHT31')::numeric AS humidity_percent,
    (object->>'BatV')::numeric AS battery_v,
    object->>'Door_status' AS door_status,
    object->>'EXTI_Trigger' AS exti_trigger
FROM event_up
ORDER BY time DESC
LIMIT 10;
```

### 5.2 Query Gateway RF Signal Parameters (RSSI & SNR)
```sql
SELECT 
    time,
    dev_eui,
    device_name,
    f_cnt,
    f_port,
    rx_info->0->>'rssi' AS rssi_dbm,
    rx_info->0->>'snr' AS snr_db
FROM event_up
ORDER BY time DESC
LIMIT 10;
```

### 5.3 Create an Optimized SQL View for Dragino Telemetry
To simplify querying from third-party tools like Grafana, create a database view mapping the Dragino JS decoder fields:

```sql
CREATE OR REPLACE VIEW v_sensor_telemetry AS
SELECT 
    time AS timestamp,
    dev_eui,
    device_name,
    (object->>'TempC_SHT31')::numeric AS temperature,
    (object->>'Hum_SHT31')::numeric AS humidity,
    (object->>'BatV')::numeric AS battery_voltage,
    object->>'Door_status' AS door_status,
    object->>'EXTI_Trigger' AS exti_trigger,
    (rx_info->0->>'rssi')::numeric AS rssi,
    (rx_info->0->>'snr')::numeric AS snr
FROM event_up;
```

Now you can query clean telemetry data using standard SQL:
```sql
SELECT * FROM v_sensor_telemetry WHERE temperature > 30.0;
```

---

## ⚡ STEP 6: PRODUCTION MAINTENANCE & SUGGESTIONS

### 1. Database Indexing for High Data Rates
If you deploy hundreds of sensors transmitting frequently, create indexes on time and device columns:
```sql
CREATE INDEX idx_event_up_time ON event_up (time DESC);
CREATE INDEX idx_event_up_dev_eui ON event_up (dev_eui);
```

### 2. Automated Retention & Data Purging
High-density LoRaWAN networks generate millions of row records over time. Set up a periodic SQL cleanup procedure (or `pg_cron` job) to retain raw events for 90 days:
```sql
DELETE FROM event_up WHERE time < NOW() - INTERVAL '90 days';
```

---

## 💾 STEP 7: AUTOMATED DATABASE BACKUP & DISASTER RECOVERY

To protect telemetry data against host failure or volume corruption, configure automated backups using `pg_dump`.

### 7.1 Backup Command (`pg_dump`)
Execute a compressed SQL dump of the `chirpstack_integration` database directly from the Docker container:

```bash
# Create local backup directory
mkdir -p ~/backups/postgres

# Run pg_dump and compress backup file
sudo docker exec -t chirpstack-docker-postgres-1 pg_dump -U chirpstack_integration -d chirpstack_integration -F c -b -v -f /tmp/chirpstack_integration_$(date +%Y%m%d_%H%M%S).dump

# Copy dump file from container to host system
sudo docker cp chirpstack-docker-postgres-1:/tmp/chirpstack_integration_*.dump ~/backups/postgres/
```

### 7.2 Automated Cron Job Setup (Daily at 2:00 AM)
Open host crontab editor:
```bash
crontab -e
```
Add the following scheduled task line:
```bash
0 2 * * * docker exec -t chirpstack-docker-postgres-1 pg_dump -U chirpstack_integration chirpstack_integration | gzip > ~/backups/postgres/chirpstack_int_$(date +\%F).sql.gz
```

### 7.3 Disaster Recovery Restoration Procedure
To restore an integration database backup onto a fresh installation:

```bash
# 1. Drop existing integration database if corrupt (CAUTION)
sudo docker exec -it chirpstack-docker-postgres-1 psql -U chirpstack -c "DROP DATABASE IF EXISTS chirpstack_integration;"

# 2. Re-create database owned by chirpstack_integration
sudo docker exec -it chirpstack-docker-postgres-1 psql -U chirpstack -c "CREATE DATABASE chirpstack_integration WITH OWNER chirpstack_integration;"

# 3. Restore backup dump file into database
gunzip -c ~/backups/postgres/chirpstack_int_2026-07-30.sql.gz | sudo docker exec -i chirpstack-docker-postgres-1 psql -U chirpstack_integration -d chirpstack_integration
```

---

## 🔗 Sequential Technical Documentation Index

| Sequence | Document | Focus Area | Description |
| :---: | :--- | :--- | :--- |
| **Home** | **[Master Overview (README)](./README.md)** | **Architecture Hub** | Master documentation hub, system bill of materials, network topology, and cheat sheet. |
| **01** | **[01: Master Deployment Guide](./01-master-deployment-guide.md)** | **Foundation & Stack Setup** | 10-part manual covering hypervisor setup, Ubuntu VM provisioning, online Docker installation, and ChirpStack stack launch. |
| **02** | **[02: Offline Direct AP Setup Guide](./02-offline-direct-ap-setup-guide.md)** | **Offline Direct AP Mode** | Complete guide for operating when connected directly to `Gateway_F94C0B` Wi-Fi AP with bridged Wi-Fi NIC and static IP. |
| **03** | **[03: PostgreSQL Integration Guide](./03-postgres-integration-guide.md)** | **Database Event Persistence** | Guide for creating `chirpstack_integration` DB, configuring DSN in `chirpstack.toml`, and running telemetry SQL queries. |
| **04** | **[04: Grafana Integration Guide](./04-grafana-integration-guide.md)** | **Visualization & Dashboards** | Guide for containerizing Grafana (`:3000`), connecting PostgreSQL Data Source (`postgres:5432`), and building dashboards. |
| **05** | **[05: Node-RED Integration Guide](./05-node-red-integration-guide.md)** | **Flow Automation & Alerts** | Guide for containerizing Node-RED (`:1880`), installing ChirpStack nodes, and building threshold alert flows. |
| **Ref** | **[Dragino JS Decoder](./codecs/dragino-lsn50v2-s31-decoder.js)** | **Payload Codec** | Production JavaScript parser for decoding temperature, humidity, and battery voltage bytes. |

---
*Document maintained under `lorawan-setup/docs/03-postgres-integration-guide.md`.*
