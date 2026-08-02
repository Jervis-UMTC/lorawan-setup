# ChirpStack v4 Grafana Integration & Real-Time Visualization Guide

This guide provides an **exhaustive, step-by-step technical procedure** for integrating **Grafana** into your **ChirpStack v4 Docker Stack**. By connecting Grafana directly to the ChirpStack PostgreSQL integration database, you can build real-time monitoring dashboards, dynamic gauges, historical trend graphs, and automated alerting for your LoRaWAN sensor fleet (e.g. Dragino LSN50v2 environmental nodes).

---

## 📌 Architecture & Integration Overview

```text
+---------------------------------------------------------------------------------------+
|                    ChirpStack v4 LoRaWAN Network Server                               |
|  • Decodes End-Node Payloads (Temperature, Humidity, Battery)                         |
|  • Persists Decoded JSON Telemetry into PostgreSQL Database                           |
+---------------------------------------------------------------------------------------+
                                           |
                                           | Database Records (event_up Table)
                                           v
+---------------------------------------------------------------------------------------+
|                   PostgreSQL Database Container (postgres:5432)                       |
|                   Database: chirpstack_integration                                   |
+---------------------------------------------------------------------------------------+
                                           |
                                           | SQL Query Data Source (Port 5432)
                                           v
+---------------------------------------------------------------------------------------+
|                    Grafana Visualization Engine (Port 3000)                           |
|  • Dashboard Panels: Gauges, Time-Series Graphs, Stat Displays                        |
|  • Real-Time Auto-Refresh & Threshold Alerting                                         |
+---------------------------------------------------------------------------------------+
                                           |
                                           | Web Dashboard Access (http://<SERVER_IP>:3000)
                                           v
+---------------------------------------------------------------------------------------+
|                        Operator & Web Browser Clients                                 |
+---------------------------------------------------------------------------------------+
```

---

## 🧠 DEEP TECHNICAL BACKING EXPLANATIONS & ARCHITECTURAL RATIONALE

### 1. Why Containerize Grafana within the Same Docker Compose Stack?
Integrating Grafana directly into the `docker-compose.yml` manifest alongside ChirpStack provides major architectural advantages:
* **Internal Container Network (`postgres:5432`)**: Containers in the same Docker Compose stack communicate across an isolated software bridge network (`172.18.0.x`). Grafana reaches PostgreSQL directly at host alias `postgres` on port `5432` without exposing PostgreSQL to external public networks or requiring complex firewall NAT rules.
* **Unified Microservice Lifecycle**: Managing Grafana with `docker compose up -d` guarantees that visualization services automatically spin up, restart upon unexpected host reboots (`restart: unless-stopped`), and share the same container logging driver.

### 2. Why Are Named Volume Bindings (`grafana-storage:/var/lib/grafana`) Mandatory?
Grafana stores dashboard layouts, user accounts, alert channel configurations, and panel queries inside an internal SQLite database located at `/var/lib/grafana`.
* **Ephemeral Container Risk**: Without persistent volume mounts, any container restart or image update (`docker compose pull`) completely destroys the container's writable layer, erasing all custom dashboards and configurations.
* **Persistent Named Volumes**: Mapping `grafana-storage:/var/lib/grafana` ensures that all dashboard edits, alert rules, and credentials persist safely on host storage across container updates.

### 3. Why Is the `$__timeFilter(time)` Macro Essential in SQL Queries?
When querying millions of telemetry records from PostgreSQL `event_up` table, running unconstrained `SELECT * FROM event_up` will cause massive database full-table scans, memory exhaustion, and slow dashboard render times.
* **Grafana `$__timeFilter` Macro**: Dynamically translates the user's selected time picker window (e.g. "Last 6 hours" or "Last 30 days") into an optimized SQL clause: `WHERE time >= '2026-07-30T02:00:00Z' AND time <= '2026-07-30T08:00:00Z'`.
* **B-Tree Index Scan Optimization**: This forces PostgreSQL to perform targeted index scans on the `time` column index, executing queries in milliseconds regardless of total table size.

---

## 🐳 STEP 1: ADD GRAFANA CONTAINER TO DOCKER COMPOSE MANIFEST

To run Grafana seamlessly within the ChirpStack microservice stack, add the `grafana` container service to `docker-compose.yml`.

### 1.1 Open `docker-compose.yml`
Navigate to your `chirpstack-docker` directory and open the manifest:
```bash
cd ~/chirpstack-docker
sudo nano docker-compose.yml
```

### 1.2 Insert `grafana` Service Block
Under the `services:` block, paste the following service definition (ensure 2-space YAML alignment):

```yaml
  grafana:
    image: grafana/grafana-oss:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=admin12345
    volumes:
      - grafana-storage:/var/lib/grafana
    depends_on:
      - postgres
```

### 1.3 Declare Persistent Storage Volume
Scroll down to the bottom of `docker-compose.yml` under the `volumes:` section and declare `grafana-storage:`:

```yaml
volumes:
  postgresqldata:
  redisdata:
  grafana-storage:
```

> ⚠️ **YAML Indentation Warning**: YAML files require strict 2-space indentation. Do not mix tabs and spaces, or `docker compose` will throw a syntax error.

Save changes (`Ctrl + O`, `Enter`) and exit (`Ctrl + X`).

---

## 🚀 STEP 2: RESTART STACK & VERIFY GRAFANA CONTAINER STATUS

Restart the Docker Compose stack to download the Grafana image and launch the container:

```bash
# Bring stack down
sudo docker compose down

# Launch updated stack in detached background mode
sudo docker compose up -d

# Check running containers
sudo docker ps
```

*Confirm that `grafana` is running and healthy on port `0.0.0.0:3000->3000/tcp`*:

```text
CONTAINER ID   IMAGE                      COMMAND                  STATUS         PORTS
a1b2c3d4e5f6   grafana/grafana-oss:latest "/run.sh"                Up 2 minutes   0.0.0.0:3000->3000/tcp
```

---

## 🔑 STEP 3: ACCESS GRAFANA WEB UI & LOG IN

1. Open a web browser on your host machine (connected to the same network as the VM).
2. Navigate to the Grafana URL:
   ```http
   http://<SERVER_IP>:3000
   ```
   *(For offline direct AP mode, use `http://192.168.23.137:3000`)*.

3. Log in with initial credentials configured in `docker-compose.yml`:
   * **Username**: `admin`
   * **Password**: `admin12345`

---

## 📊 STEP 4: CONFIGURE POSTGRESQL DATA SOURCE IN GRAFANA

1. In the left navigation pane of Grafana, click **Connections** -> **Data sources**.
2. Click **+ Add new data source**.
3. Search for **PostgreSQL** and select it.
4. Configure the PostgreSQL Data Source connection settings:

```text
+-----------------------------------------------------------------------+
|                    Grafana PostgreSQL Data Source                     |
+-----------------------------------------------------------------------+
| Host URL          : postgres:5432                                     |
| Database name     : chirpstack_integration                            |
| Username          : chirpstack_integration (or chirpstack)           |
| Password          : chirpstack_integration (or custom password)       |
| TLS/SSL Mode      : disable                                           |
| Version           : 14 (or match your Postgres version)              |
+-----------------------------------------------------------------------+
```

> 💡 **Container Networking Tip**: When running inside Docker Compose, use `postgres:5432` as the **Host URL** so Grafana communicates with PostgreSQL over the internal Docker network. If connecting from outside Docker, use `<SERVER_IP>:5432`.

5. Scroll down to the bottom and click **Save & test**.
6. *Verify success message*: `Database Connection OK`.

---

## 📈 STEP 5: BUILD A TELEMETRY DASHBOARD & SQL PANELS

Now create visual dashboard panels (Gauges, Stat Cards, and Time-Series charts) using SQL queries against the ChirpStack integration database.

### 5.1 Create a New Dashboard
1. Click **Dashboards** in the left menu -> Click **New** -> **New dashboard**.
2. Click **+ Add panel** (or **Configure visualization**).

---

### 5.2 Configure Gauge Panels for Current Sensor Telemetry

#### 1. Panel Configuration:
* **Visualization**: Select **Gauge** (from the right-hand panel menu).
* **Title**: `Live Environmental Telemetry`

#### 2. Query Setup:
At the bottom of the editor, switch to **Code** query mode, select your PostgreSQL Data Source, and paste the following SQL query matching the Dragino LSN50v2 decoder output:

```sql
SELECT
  time AS "time",
  (object->>'TempC_SHT31')::numeric AS temperature,
  (object->>'Hum_SHT31')::numeric AS humidity,
  (object->>'BatV')::numeric AS battery
FROM event_up
ORDER BY time DESC
LIMIT 1;
```

> 💡 **WHY DOES THIS SHOW ONLY 1 VALUE WHEN YOU HAVE 2+ SENSORS?**
> * The `LIMIT 1` clause forces PostgreSQL to return **only the single most recent row** across the entire table. Whichever sensor sent an uplink last (e.g., Sensor-01 at 13:50) is shown, while Sensor-02 is hidden.
> * To display telemetry for **multiple sensors**, see [Section 5.4: Multi-Sensor Query Patterns & Dashboard Variables](#54-multi-sensor-query-patterns--dashboard-variables).


#### 3. Customize Unit, Min/Max & Thresholds (Handling Multi-Field Panels):

> ⚠️ **CRITICAL GRAFANA GOTCHA**: When a single panel SQL query returns multiple fields (e.g. `temperature`, `humidity`, and `battery`), changing **Standard Options** in the main panel settings will apply that unit (e.g. `°C`) to **ALL fields** globally!
> 
> To format each metric independently with its own Unit, Min/Max, and Threshold colors, use **Field Overrides** (Option A) or split into **Separate Panels** (Option B).

##### Option A: Use Field Overrides (Single Multi-Gauge Panel)

In the right-hand panel settings menu, switch to the **Overrides** tab (or scroll down to the bottom and click **+ Add field override**):

1. **Temperature Override (`temperature`)**:
   * Click **+ Add field override** -> Select **Fields with name** -> Choose `temperature`.
   * Click **+ Add override property** -> Select **Standard options > Unit** -> Set to `Celsius (°C)`.
   * Click **+ Add override property** -> Select **Standard options > Min** -> Set to `-10`.
   * Click **+ Add override property** -> Select **Standard options > Max** -> Set to `60`.
   * Click **+ Add override property** -> Select **Thresholds** -> Set Green for normal range (`20°C` - `30°C`) and Red for warning (`> 35°C`).

2. **Humidity Override (`humidity`)**:
   * Click **+ Add field override** -> Select **Fields with name** -> Choose `humidity`.
   * Click **+ Add override property** -> Select **Standard options > Unit** -> Set to `Percent (0-100%)`.
   * Click **+ Add override property** -> Select **Standard options > Min** -> Set to `0`.
   * Click **+ Add override property** -> Select **Standard options > Max** -> Set to `100`.

3. **Battery Voltage Override (`battery`)**:
   * Click **+ Add field override** -> Select **Fields with name** -> Choose `battery`.
   * Click **+ Add override property** -> Select **Standard options > Unit** -> Set to `Volts (V)`.
   * Click **+ Add override property** -> Select **Standard options > Min** -> Set to `2.0`.
   * Click **+ Add override property** -> Select **Standard options > Max** -> Set to `4.0`.
   * Click **+ Add override property** -> Select **Thresholds** -> Set Base / Red threshold `< 3.0V` (Low Battery Warning) and Green threshold `3.6V`.

##### Option B: Separate Gauge Panels per Metric (Recommended Dashboard Layout)

Create 3 dedicated gauge panels so each panel's **Standard Options** apply exclusively to its own metric:

* **Panel 1: Temperature Gauge**:
  ```sql
  SELECT (object->>'TempC_SHT31')::numeric AS temperature FROM event_up ORDER BY time DESC LIMIT 1;
  ```
  * *Standard Options*: Unit = `Celsius (°C)`, Min = `-10`, Max = `60`.

* **Panel 2: Humidity Gauge**:
  ```sql
  SELECT (object->>'Hum_SHT31')::numeric AS humidity FROM event_up ORDER BY time DESC LIMIT 1;
  ```
  * *Standard Options*: Unit = `Percent (0-100%)`, Min = `0`, Max = `100`.

* **Panel 3: Battery Voltage Gauge**:
  ```sql
  SELECT (object->>'BatV')::numeric AS battery FROM event_up ORDER BY time DESC LIMIT 1;
  ```
  * *Standard Options*: Unit = `Volts (V)`, Min = `2.0`, Max = `4.0`, Red Threshold `< 3.0V`, Green `3.6V`.


---

### 5.3 Configure Time-Series Graph Panels for Historical Trends

To create clean time-series trend graphs for **each sensor reading** (Temperature, Humidity, Battery), use the dedicated SQL queries below:

#### Option A: Dedicated Time-Series Graphs for a Specific Sensor (e.g. `Sensor-01`)

##### 1. Temperature Over Time (`Sensor-01`)
* **Visualization**: `Time series` | **Title**: `Sensor 01 - Temperature History`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    (object->>'TempC_SHT31')::numeric AS "Temperature (°C)"
  FROM event_up
  WHERE $__timeFilter(time)
    AND device_name = 'Sensor-01'
  ORDER BY time ASC;
  ```
* **Standard Options**: Unit = `Celsius (°C)`.

##### 2. Humidity Over Time (`Sensor-01`)
* **Visualization**: `Time series` | **Title**: `Sensor 01 - Humidity History`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    (object->>'Hum_SHT31')::numeric AS "Humidity (%)"
  FROM event_up
  WHERE $__timeFilter(time)
    AND device_name = 'Sensor-01'
  ORDER BY time ASC;
  ```
* **Standard Options**: Unit = `Percent (0-100%)`.

##### 3. Battery Voltage Over Time (`Sensor-01`)
* **Visualization**: `Time series` | **Title**: `Sensor 01 - Battery Voltage History`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    (object->>'BatV')::numeric AS "Battery (V)"
  FROM event_up
  WHERE $__timeFilter(time)
    AND device_name = 'Sensor-01'
  ORDER BY time ASC;
  ```
* **Standard Options**: Unit = `Volts (V)`.

---

#### Option B: Fleet-Wide Comparison Graphs (All Sensors on 1 Chart per Metric)

##### 1. Temperature Comparison (All Sensors)
* **Title**: `Fleet Temperature Trends` | **Visualization**: `Time series`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    device_name AS metric,
    (object->>'TempC_SHT31')::numeric AS "Temperature (°C)"
  FROM event_up
  WHERE $__timeFilter(time)
  ORDER BY time ASC;
  ```

##### 2. Humidity Comparison (All Sensors)
* **Title**: `Fleet Humidity Trends` | **Visualization**: `Time series`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    device_name AS metric,
    (object->>'Hum_SHT31')::numeric AS "Humidity (%)"
  FROM event_up
  WHERE $__timeFilter(time)
  ORDER BY time ASC;
  ```

##### 3. Battery Voltage Comparison (All Sensors)
* **Title**: `Fleet Battery Voltage Trends` | **Visualization**: `Time series`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    device_name AS metric,
    (object->>'BatV')::numeric AS "Battery (V)"
  FROM event_up
  WHERE $__timeFilter(time)
  ORDER BY time ASC;
  ```


#### 3. Save & Apply Dashboard
Click **Save** in the top right -> Name dashboard `Smart Agriculture Telemetry` -> Click **Save**.

---

### 5.4 Multi-Sensor Query Patterns & Dashboard Variables

When operating a fleet of 2 or more sensors (e.g. `Sensor-01`, `Sensor-02`), use the following SQL query strategies to display all sensors simultaneously or switch between them dynamically:

#### Pattern 1: Display Latest Telemetry for ALL Sensors (`DISTINCT ON (dev_eui)`)
To automatically display a gauge card or table row for **every registered sensor** simultaneously:

```sql
SELECT DISTINCT ON (dev_eui)
  device_name,
  (object->>'TempC_SHT31')::numeric AS temperature,
  (object->>'Hum_SHT31')::numeric AS humidity,
  (object->>'BatV')::numeric AS battery
FROM event_up
ORDER BY dev_eui, time DESC;
```
* **Result**: Grafana generates a dedicated gauge (or table row) for **Sensor-01** AND **Sensor-02** automatically.

#### Pattern 2: Dedicated Panels per Sensor & Value Type (`WHERE device_name = '...'`)

To create individual, clean panels for each value type (Temperature, Humidity, Battery) for specific sensors:

##### 1. Temperature Panel (Sensor-01)
* **Title**: `Sensor 01 - Temperature` | **Visualization**: `Gauge`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    (object->>'TempC_SHT31')::numeric AS temperature
  FROM event_up
  WHERE device_name = 'Sensor-01'
  ORDER BY time DESC
  LIMIT 1;
  ```
* **Standard Options**: Unit = `Celsius (°C)`, Min = `-10`, Max = `60`.
* **Thresholds**: Green (`20` - `30`), Red (`> 35`).

##### 2. Humidity Panel (Sensor-01)
* **Title**: `Sensor 01 - Humidity` | **Visualization**: `Gauge`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    (object->>'Hum_SHT31')::numeric AS humidity
  FROM event_up
  WHERE device_name = 'Sensor-01'
  ORDER BY time DESC
  LIMIT 1;
  ```
* **Standard Options**: Unit = `Percent (0-100%)`, Min = `0`, Max = `100`.

##### 3. Battery Voltage Panel (Sensor-01)
* **Title**: `Sensor 01 - Battery` | **Visualization**: `Gauge`
* **SQL Query**:
  ```sql
  SELECT
    time AS "time",
    (object->>'BatV')::numeric AS battery
  FROM event_up
  WHERE device_name = 'Sensor-01'
  ORDER BY time DESC
  LIMIT 1;
  ```
* **Standard Options**: Unit = `Volts (V)`, Min = `2.0`, Max = `4.0`.
* **Thresholds**: Base/Red (`< 3.0`), Green (`3.6`).

> 💡 **Quick Setup Tip**: Create the 3 panels for `Sensor-01` first. Then click the top right menu of each panel -> **More...** -> **Duplicate**, and edit `WHERE device_name = 'Sensor-01'` to `WHERE device_name = 'Sensor-02'` (or `Sensor-03`) for the rest of your sensor fleet.


#### Pattern 3: Dynamic Sensor Dropdown Selector (Dashboard Variable `$device`)
Allow operators to select sensors interactively from a top dropdown menu:

1. In Grafana dashboard, click **Dashboard Settings** (gear icon) -> **Variables** -> **+ Add variable**.
2. **Name**: `device`
3. **Type**: `Query`
4. **Data source**: `PostgreSQL`
5. **Query**:
   ```sql
   SELECT DISTINCT device_name FROM event_up ORDER BY device_name;
   ```
6. Click **Apply**. A dropdown menu `[ Sensor-01 | Sensor-02 ]` will appear at the top of the dashboard.
7. Update your panel SQL query to use the `$device` variable:
   ```sql
   SELECT
     time AS "time",
     (object->>'TempC_SHT31')::numeric AS temperature,
     (object->>'Hum_SHT31')::numeric AS humidity,
     (object->>'BatV')::numeric AS battery
   FROM event_up
   WHERE device_name = '$device'
   ORDER BY time DESC
   LIMIT 1;
   ```

---

## 💾 STEP 6: DASHBOARD JSON EXPORT & ALERT NOTIFICATION CHANNELS

### 6.1 Export Dashboard JSON Model for Portability
1. Open your created dashboard -> Click **Share** (top toolbar icon).
2. Select the **Export** tab.
3. Click **Save to file** or **View JSON**.
4. Store the generated `.json` file in your repository under `docs/dashboards/` for automated infrastructure-as-code deployments.

---

### 6.2 Configure Grafana Threshold Alerting & Webhook Notifications
Grafana allows sending push alerts (Webhook, Slack, Telegram, Email) when sensor telemetry breaches safety bounds.

1. Navigate to **Alerting** in the left menu -> **Contact points** -> Click **Add contact point**.
2. **Name**: `LoRaWAN-Critical-Alerts`
3. **Integration**: Select **Webhook** (or **Telegram** / **Slack**).
4. **URL**: Enter your webhook endpoint URL (or Node-RED HTTP input URL `http://node-red:1880/alert`).
5. Click **Test** -> Click **Save contact point**.
6. Create Alert Rule:
   * Navigate to **Alerting** -> **Alert rules** -> **New alert rule**.
   * Set condition: `WHEN temperature > 35 FOR 5m THEN ALERT`.
   * Assign contact point: `LoRaWAN-Critical-Alerts`.

---

## 🔍 COMPREHENSIVE TROUBLESHOOTING & SUGGESTIONS

| Issue / Error | Cause | Resolution |
| :--- | :--- | :--- |
| **`db query error: dial tcp: lookup postgres: no such host`** | Host URL misconfigured in Grafana connection settings. | Use `postgres:5432` if Grafana and Postgres share the Docker network, or `<VM_IP>:5432`. |
| **Standard Options unit applies to all gauges (`°C` showing on humidity/battery)** | Single SQL query returning multiple fields in one panel shares panel-level Standard Options. | Use **Field Overrides** in the panel sidebar (`Fields with name -> temperature/humidity/battery`) to set units individually, or split into 3 separate Gauge panels. |
| **`pq: password authentication failed for user`** | Mismatched Postgres role credentials. | Verify username/password using `sudo docker exec -it chirpstack-docker-postgres-1 psql -U chirpstack_integration -d chirpstack_integration`. |
| **No data displayed on Grafana panels** | Time range picker set outside packet transmission window. | Adjust top-right time picker to `Last 6 hours` or `Last 24 hours`. Ensure devices are actively transmitting. |
| **`docker compose up` YAML syntax error** | Tab characters used in `docker-compose.yml`. | Replace tabs with 2 spaces in `docker-compose.yml`. |

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
| **06** | **[06: LoRaWAN RF and Security Toolkit Brief](./06-lorawan-rf-security-toolkit-brief.md)** | **Tool Selection & Architecture** | Decision brief for RF/PHY decoding, protocol crafting, packet inspection, network-server behavior, and replay/spoof detection. |
| **07** | **[07: LoRaWAN RF and Protocol Testing Setup Guide](./07-lorawan-rf-and-protocol-testing-setup-guide.md)** | **RF-to-Protocol Test Bench** | Setup and verification path for the SDR, PHY decoder, protocol parser, Wireshark, LAF, and ChirpStack integration. |
| **08** | **[08: LoRaWAN Security Testing Runbook](./08-lorawan-security-testing-runbook.md)** | **Authorized Test Operations** | Pre-flight checks, evidence handling, test cases, stop conditions, triage, and reporting. |
| **09** | **[09: RAK5146 + WisBlock Gateway Commissioning Manual](./09-rak5146-wisblock-gateway-commissioning-manual.md)** | **Incoming Hardware Commissioning** | RAK5146 SPI/AS923 gateway assembly, packet-forwarder setup, WisBlock node programming, OTAA onboarding, and acceptance gates. |
| **Ref** | **[Dragino JS Decoder](./codecs/dragino-lsn50v2-s31-decoder.js)** | **Payload Codec** | Production JavaScript parser for decoding temperature, humidity, and battery voltage bytes. |

---
*Document maintained under `lorawan-setup/docs/04-grafana-integration-guide.md`.*
