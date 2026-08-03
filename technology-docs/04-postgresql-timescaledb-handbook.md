# Volume 04: PostgreSQL & TimescaleDB Data Persistence Engineering Handbook

## Executive Summary & Educational Purpose

This handbook covers relational data modeling, binary document storage, time-series partitioning, indexing algorithms, and high-throughput SQL analytics using **PostgreSQL 14** and **TimescaleDB**. Designed for database administrators, data architects, and backend engineers, this text details the internal storage structures of ChirpStack event tables, JSONB operator mathematics, Generalized Inverted Index (GIN) execution, TimescaleDB Hypertable chunking, automated data compression, and analytical query performance tuning for high-density IoT telemetry streams.

---

## 1. Database Roles & Schema Isolation in ChirpStack v4

ChirpStack v4 isolates internal network server operational metadata from application event streams using two distinct PostgreSQL databases:

```text
+-----------------------------------------------------------------------------------+
|                                   PostgreSQL 14                                   |
|                                                                                   |
|  +---------------------------------------+   +---------------------------------+  |
|  | Database 1: `chirpstack`              |   | Database 2:                     |  |
|  | • Relational Metadata Store           |   | `chirpstack_integration`        |  |
|  | • Tenants, Applications, Devices      |   | • Time-Series Telemetry Store   |  |
|  | • Device Profiles, Decoders, OTAA Keys|   | • Raw `event_up` Sensor Streams |  |
|  | • Relational B-Tree Primary Keys      |   | • Partitioned Time-Series Chunks|  |
|  +---------------------------------------+   +---------------------------------+  |
+-----------------------------------------------------------------------------------+
                                                           │
                                                           │ Structured JSONB Stream
                                                           v
                                               +-----------------------+
                                               | Grafana Dashboards    |
                                               | & Node-RED Flow Engine|
                                               +-----------------------+
```

---

## 2. Complete Integration Database DDL Schema

Below is the production DDL schema used to initialize `chirpstack_integration` for telemetry logging:

```sql
-- 1. Create Database & Target Extensions
CREATE DATABASE chirpstack_integration;
\c chirpstack_integration;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 2. Primary Telemetry Table: `event_up`
CREATE TABLE IF NOT EXISTS event_up (
    deduplication_id UUID PRIMARY KEY,
    time WITH TIME ZONE NOT NULL,
    tenant_id UUID NOT NULL,
    tenant_name VARCHAR(100) NOT NULL,
    application_id UUID NOT NULL,
    application_name VARCHAR(100) NOT NULL,
    device_profile_id UUID NOT NULL,
    device_profile_name VARCHAR(100) NOT NULL,
    device_name VARCHAR(100) NOT NULL,
    dev_eui BYTEA NOT NULL, -- 8-byte binary DevEUI for space optimization
    dev_addr BYTEA NOT NULL,
    adr BOOLEAN NOT NULL,
    dr SMALLINT NOT NULL,
    f_cnt INT NOT NULL,
    f_port SMALLINT NOT NULL,
    object JSONB NOT NULL,   -- Decoded sensor telemetry JSON document
    rx_info JSONB NOT NULL,  -- Gateway RSSI/SNR metadata array
    tx_info JSONB NOT NULL   -- Frequency/DataRate metadata
);

-- 3. Downlink Events Table: `event_down`
CREATE TABLE IF NOT EXISTS event_down (
    downlink_id UUID PRIMARY KEY,
    time WITH TIME ZONE NOT NULL,
    tenant_id UUID NOT NULL,
    application_id UUID NOT NULL,
    device_name VARCHAR(100) NOT NULL,
    dev_eui BYTEA NOT NULL,
    f_cnt INT NOT NULL,
    f_port SMALLINT NOT NULL,
    data BYTEA NOT NULL
);

-- 4. B-Tree & GIN Indexing
CREATE INDEX IF NOT EXISTS idx_event_up_time ON event_up (time DESC);
CREATE INDEX IF NOT EXISTS idx_event_up_dev_eui ON event_up (dev_eui);
CREATE INDEX IF NOT EXISTS idx_event_up_app_name ON event_up (application_name);
CREATE INDEX IF NOT EXISTS idx_event_up_object_gin ON event_up USING GIN (object);
```

---

## 3. High-Performance JSONB Binary Extraction & Operator Mathematics

PostgreSQL's **JSONB** column type stores telemetry in a decomposed binary format, allowing fast indexing and direct querying of nested key-value pairs without scanning strings.

### 3.1 Operator Matrix

| Operator | Return Data Type | Operator Description | Example Usage |
| :---: | :---: | :--- | :--- |
| `->` | `jsonb` | Extracts field as JSON element. | `object -> 'temperature'` |
| `->>` | `text` | Extracts field as **text** (required for numeric casting). | `(object ->> 'temperature')::numeric` |
| `#>` | `jsonb` | Extracts nested path element. | `rx_info #> '{0,rssi}'` |
| `#>>` | `text` | Extracts nested path element as text. | `rx_info #>> '{0,rssi}'` |
| `@>` | `boolean` | Tests if left JSONB contains right JSONB document. | `object @> '{"nitrogen": 45}'` |
| `?` | `boolean` | Tests if top-level key exists in JSONB. | `object ? 'soil_moisture'` |

### 3.2 Advanced Analytical Query Cookbook

#### 1. Extract Soil NPK Telemetry Stream with Numeric Casting
```sql
SELECT 
    time AS "time",
    device_name,
    encode(dev_eui, 'hex') AS dev_eui_hex,
    (object ->> 'nitrogen')::numeric AS nitrogen_ppm,
    (object ->> 'phosphorus')::numeric AS phosphorus_ppm,
    (object ->> 'potassium')::numeric AS potassium_ppm,
    (object ->> 'soil_moisture')::numeric AS moisture_pct,
    (object ->> 'temperature')::numeric AS temp_celsius
FROM event_up
WHERE 
    $__timeFilter(time)
    AND application_name = 'Soil-Nutrient-Array'
ORDER BY time DESC;
```

#### 2. Hourly Moving Average and Gap Filling
```sql
SELECT 
    time_bucket_gapfill('1 hour', time) AS hour_bucket,
    device_name,
    locf(AVG((object ->> 'soil_moisture')::numeric)) AS avg_moisture_locf,
    interpolated(AVG((object ->> 'temperature')::numeric)) AS avg_temp
FROM event_up
WHERE time >= NOW() - INTERVAL '7 days'
GROUP BY hour_bucket, device_name
ORDER BY hour_bucket ASC;
```

---

## 4. TimescaleDB Hypertables & Compression Engines

For large agricultural properties deploying thousands of sensor nodes, standard PostgreSQL tables can slow down over time. Converting `event_up` into a **TimescaleDB Hypertable** partitions data into time-based chunks automatically.

```text
[ Hypertable: event_up ]
   │
   ├── [ Chunk 1: 2026-07-01 to 2026-07-07 ] ──> Compressed (Gorilla / XOR)
   ├── [ Chunk 2: 2026-07-08 to 2026-07-14 ] ──> Compressed (Gorilla / XOR)
   ├── [ Chunk 3: 2026-07-15 to 2026-07-21 ] ──> Compressed (Gorilla / XOR)
   └── [ Chunk 4: 2026-07-22 to 2026-07-28 ] ──> Uncompressed Active Ingestion
```

### 4.1 Creating Hypertable & Enabling Compression

```sql
-- 1. Convert event_up into a Hypertable chunked by 7-day intervals
SELECT create_hypertable('event_up', 'time', chunk_time_interval => INTERVAL '7 days');

-- 2. Configure Column Compression (Gorilla for timestamps, XOR for floats)
ALTER TABLE event_up SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'dev_eui',
    timescaledb.compress_orderby = 'time DESC'
);

-- 3. Automatically compress chunks older than 14 days
SELECT add_compression_policy('event_up', INTERVAL '14 days');
```

---

## 5. Automated Data Retention Runbook

To prevent server disk space exhaustion during long-term operational deployments:

```sql
-- Automatically drop chunks older than 180 days
SELECT add_retention_policy('event_up', INTERVAL '180 days');

-- View compression statistics and space savings
SELECT 
    hypertable_name,
    total_bytes / 1024 / 1024 AS uncompressed_mb,
    compressed_total_bytes / 1024 / 1024 AS compressed_mb,
    (1 - (compressed_total_bytes::float / total_bytes::float)) * 100 AS compression_ratio_pct
FROM hypertable_detailed_size('event_up');
```

---
*Maintained under project `lorawan-setup/technology-docs`.*
