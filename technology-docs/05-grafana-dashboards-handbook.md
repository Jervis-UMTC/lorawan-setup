# Volume 05: Grafana Real-Time Visualization & Scoreboard Handbook

## Executive Summary & Educational Purpose

This handbook covers dashboard engineering, telemetry visualization, SQL query optimization, color-coded thresholding, agronomical disease indexing, and alerting rule architecture using **Grafana**. Designed for agronomists, farm operations managers, and IoT analysts, this text details how to build real-time farm scoreboards that transform raw database streams into clear visual indicators for crop health, microclimate trends, soil nutrient levels, and hazard risks.

---

## 1. Grafana Architecture & Role in IoT Operations

Grafana operates as an open-source visual analytics engine containerized on TCP Port `3000`. It connects directly to the PostgreSQL integration database, executing parametrized SQL queries to render live panels without modifying raw database logs.

```text
+------------------------------------+
|        PostgreSQL Database         |
|  (`chirpstack_integration` store)  |
+------------------------------------+
                  │
                  │ SQL Queries (TCP Port 5432)
                  v
+-----------------------------------------------------------------------------------+
|                           Grafana Analytics Platform                              |
|                                                                                   |
|  +---------------------------+  +---------------------------+  +---------------+  |
|  | Panel 1: Gauge Indicator  |  | Panel 2: Time-Series Graph|  | Panel 3: Alert|  |
|  | • Live Soil Moisture (%)  |  | • Canopy Temp vs Humidity |  | • Frost Threshold|
|  +---------------------------+  +---------------------------+  +---------------+  |
+-----------------------------------------------------------------------------------+
                  │
                  │ HTTP Browser (TCP Port 3000)
                  v
+-----------------------------------------------------------------------------------+
|               Executive Farm Operations Dashboard (PC / Tablet)                   |
+-----------------------------------------------------------------------------------+
```

---

## 2. Automated Data Source Provisioning (`postgres.yaml`)

```yaml
apiVersion: 1

datasources:
  - name: PostgreSQL-ChirpStack
    type: postgres
    access: proxy
    url: postgres:5432
    user: chirpstack_integration
    secureJsonData:
      password: "integration_pass"
    jsonData:
      database: chirpstack_integration
      sslmode: disable
      maxOpen: 10
      maxIdle: 5
      connMaxLifetime: 14400
      postgresVersion: 1400
      timescaledb: false
```

---

## 3. Executive Dashboard Panel Design Specifications

An effective agricultural scoreboard is structured into three visual zones:

```text
+-----------------------------------------------------------------------------------+
| ZONE 1: TOP KPI STAT CARDS (Instant Status At A Glance)                          |
| [ Average Soil Temp: 24.2 °C ] [ Avg Soil Moisture: 34.5% ] [ NPK Ratio: 45:18:120 ]|
+-----------------------------------------------------------------------------------+
| ZONE 2: CORE TIME-SERIES TRENDS (Seasonal & Microclimate Tracking)               |
| [ Chart: 7-Day Canopy Temp & Relative Humidity Overlay ]                         |
| [ Chart: 30-Day Root-Zone Soil Moisture & EC Profile ]                            |
+-----------------------------------------------------------------------------------+
| ZONE 3: HAZARD GAUGE & ALERT BOARD (Immediate Operational Triggers)              |
| [ Gauge: Frost Vulnerability ] [ Gauge: Fungal Blight Risk ] [ Alert History Log ]|
+-----------------------------------------------------------------------------------+
```

---

## 4. Production SQL Panel Query Templates

### Panel 1: Live Root-Zone Soil Moisture Gauge

* **Panel Type**: Gauge
* **Unit**: Percentage (`0–100%`)
* **Color Thresholds**:
  * `0% – 15%`: **Red** (Severe Drought Hazard)
  * `15% – 25%`: **Yellow** (Irrigation Required)
  * `25% – 45%`: **Green** (Optimal Field Moisture)
  * `> 45%`: **Blue** (Waterlogged Soil)

```sql
SELECT 
    (object ->> 'soil_moisture')::numeric AS value
FROM event_up
WHERE 
    $__timeFilter(time)
    AND device_name = 'Field-Zone-1-NPK'
ORDER BY time DESC
LIMIT 1;
```

---

### Panel 2: Microclimate Canopy Temp vs. Relative Humidity Dual-Axis Graph

* **Panel Type**: Time Series
* **Left Y-Axis**: Temperature (°C)
* **Right Y-Axis**: Relative Humidity (%)

```sql
SELECT 
    time AS "time",
    (object ->> 'temperature')::numeric AS "Canopy Temperature (°C)",
    (object ->> 'humidity')::numeric AS "Canopy Relative Humidity (%)"
FROM event_up
WHERE 
    $__timeFilter(time)
    AND application_name = 'Microclimate-Array'
ORDER BY time ASC;
```

---

### Panel 3: Soil NPK Nutrient Ratio Breakdown Chart

* **Panel Type**: Bar Chart / Stat Group

```sql
SELECT 
    (object ->> 'nitrogen')::numeric AS "Nitrogen (N) ppm",
    (object ->> 'phosphorus')::numeric AS "Phosphorus (P) ppm",
    (object ->> 'potassium')::numeric AS "Potassium (K) ppm"
FROM event_up
WHERE 
    $__timeFilter(time)
    AND device_name = 'Field-Zone-1-NPK'
ORDER BY time DESC
LIMIT 1;
```

---

## 5. Agronomical Disease Indexing & Heatmap Models

Fungal pathogens (such as *Phytophthora* or Powdery Mildew) proliferate when canopy relative humidity remains above **85%** while temperature is between **18°C and 26°C** for more than 6 consecutive hours.

### Disease Risk Heatmap SQL Query

```sql
SELECT 
    time_bucket('1 hour', time) AS "time",
    CASE 
        WHEN AVG((object ->> 'humidity')::numeric) >= 85 
             AND AVG((object ->> 'temperature')::numeric) BETWEEN 18 AND 26 
        THEN 3 -- HIGH RISK (Red)
        WHEN AVG((object ->> 'humidity')::numeric) >= 75 
        THEN 2 -- MEDIUM RISK (Yellow)
        ELSE 1 -- LOW RISK (Green)
    END AS "Blight Risk Level"
FROM event_up
WHERE $__timeFilter(time)
GROUP BY 1
ORDER BY 1 ASC;
```

---

## 6. Grafana Alert Rule & Webhook Setup

Grafana evaluates panel thresholds continuously and dispatches notification alerts when conditions breach safety envelopes.

```text
[ Frost Warning Triggered ]
Alert Name: Sub-Freezing Canopy Temperature Hazard
Device: Zone-3-Frost-Sensor
Current Temp: 1.4 °C (Threshold: < 2.0 °C)
Action Taken: Alert sent to Node-RED for automated solenoid heating activation.
```

---

## 7. Scoreboard UX Best Practices

1. **Dashboard Refresh Rate**: Set auto-refresh to **30 seconds** or **1 minute** for field operations (matches sensor transmission interval).
2. **Kiosk Mode**: Append `?kiosk` to dashboard URL for full-screen wall displays in farm management headquarters.
3. **JSON Export**: Save dashboard definitions to JSON templates under source control to restore configurations instantly after system reboots.

---
*Maintained under project `lorawan-setup/technology-docs`.*
