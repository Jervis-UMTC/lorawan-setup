# ChirpStack v4 Node-RED Integration & Event Automation Guide

This guide provides an **exhaustive, production-grade technical procedure** for integrating **Node-RED** into your **ChirpStack v4 Docker Environment**. 

Node-RED serves as an event-driven visual workflow engine. By connecting Node-RED to ChirpStack's Mosquitto MQTT broker and installing the official `@chirpstack/node-red-contrib-chirpstack` node suite, you can build real-time IoT automation flows, payload transformers, automated email/SMS/Telegram threshold alerts, and downlink command triggers for your LoRaWAN sensor network.

---

## 📌 Architecture & Message Pipeline

```text
+---------------------------------------------------------------------------------------+
|                    ChirpStack v4 LoRaWAN Network Server                               |
|  • Receives LoRaWAN Uplink Frames via Semtech UDP Gateway Bridge                     |
|  • Decodes Hexadecimal Payload using JavaScript Codec                                 |
|  • Publishes JSON Uplink Event to Mosquitto MQTT Broker                               |
+---------------------------------------------------------------------------------------+
                                           |
                                           | MQTT Event Topic: application/+/device/+/event/+
                                           v
+---------------------------------------------------------------------------------------+
|                    Mosquitto MQTT Broker Container (mosquitto:1883)                   |
+---------------------------------------------------------------------------------------+
                                           |
                                           | Internal Docker Network Subscribe (TCP 1883)
                                           v
+---------------------------------------------------------------------------------------+
|                     Node-RED Flow Automation Engine (Port 18880)                       |
|  • MQTT In Node (Subscribes to application/+/device/+/event/up)                        |
|  • ChirpStack Device Event & Downlink Nodes (@chirpstack/node-red-contrib-chirpstack)  |
|  • Function & Switch Nodes (Rule-based Threshold Logic)                               |
|  • Output Integration Nodes (HTTP Webhooks, InfluxDB, SMS/Email Alerting)              |
+---------------------------------------------------------------------------------------+
```

---

## 🧠 DEEP TECHNICAL BACKING EXPLANATIONS & ARCHITECTURAL RATIONALE

### 1. Why Use Node-RED for LoRaWAN Event Automation & Integration?
ChirpStack v4 excels at core Network Server responsibilities (radio MAC layer management, OTAA key security, frame counter validation, and payload decoding). However, executing external business logic (such as sending SMS/Telegram alerts, triggering irrigation valves, or pushing data to third-party APIs) directly inside ChirpStack is not natively supported.
* **Event-Driven Architecture**: Node-RED operates on a light-weight, event-driven Node.js runtime. It listens asynchronously to MQTT events published by ChirpStack without polling databases or incurring CPU latency.
* **Visual Flow Pipeline**: Complex multi-step automation logic (e.g., "If soil moisture < 20% AND temperature > 30°C for 3 consecutive uplinks, send Telegram alert and queue LoRaWAN downlink to open solenoid valve") can be built and deployed graphically in seconds.

### 2. How MQTT Topic Wildcards (`application/+/device/+/event/+`) Function
ChirpStack publishes event messages to Mosquitto using a strictly hierarchical MQTT topic scheme:
```text
application/{APPLICATION_ID}/device/{DEV_EUI}/event/{EVENT_TYPE}
```
* **Single-Level Wildcard (`+`)**: Matches exactly one topic level segment.
  * Topic: `application/+/device/+/event/up` subscribes to **all uplink frames** across **all applications** and **all devices** registered on the network server.
  * Topic: `application/79e520a22-.../device/a84041380189b98f/event/+` subscribes to **all event types** (uplink, join, ack, status) for that specific sensor.
* **Multi-Level Wildcard (`#`)**: Matches any number of trailing sub-topics (e.g., `application/#`).

### 3. What Does `@chirpstack/node-red-contrib-chirpstack` Do Under the Hood?
By default, MQTT messages received from ChirpStack v4 are formatted as JSON or Protobuf byte arrays.
* **`device event` Node**: Automatically parses raw MQTT buffers into typed JavaScript objects (`msg.payload.object`), exposing sensor fields (`msg.payload.object.temperature`), metadata (`rxInfo`, `rssi`, `snr`), and device identifiers (`devEui`, `deviceName`).
* **`device downlink` Node**: Encapsulates downlink payloads into binary Protobuf structures expected by ChirpStack's gRPC/MQTT downlink queue topic (`application/{APP_ID}/device/{DEV_EUI}/command/down`), guaranteeing valid payload formatting and port assignment (`fPort`).

### 4. Persistent Volume Mapping (`node-red-data:/data`)
Node-RED stores all user-created flows, node configurations, global context variables, and installed npm palette packages inside `/data`. Mapping `node-red-data:/data` in `docker-compose.yml` ensures that installed nodes (`@chirpstack/node-red-contrib-chirpstack`) and custom automation flows persist permanently across container restarts.

---

## ⚠️ PREREQUISITES & ENVIRONMENT CHECK

Before starting:
1. Ensure your ChirpStack v4 Docker stack is running.
2. Confirm Mosquitto MQTT container (`mosquitto`) is healthy on port `1883`.
3. Check internet access (or pre-downloaded npm dependencies) for installing Node-RED packages.

---

## 🐳 STEP 1: ADD NODE-RED CONTAINER TO DOCKER COMPOSE MANIFEST

To incorporate Node-RED into your ChirpStack Docker infrastructure:

### 1.1 Open `docker-compose.yml`
```bash
cd ~/chirpstack-docker
sudo nano docker-compose.yml
```

### 1.2 Add `node-red` Service Definition
Insert the `node-red` container block under the `services:` section (ensure strict 2-space YAML formatting):

```yaml
  node-red:
    image: nodered/node-red:latest-22
    container_name: node-red
    restart: unless-stopped
    ports:
      - "1880:1880"
    depends_on:
      - mosquitto
      - chirpstack
    environment:
      - TZ=Asia/Manila
    volumes:
      - node-red-data:/data
```

### 1.3 Declare Persistent Volume
Scroll to the bottom `volumes:` section and declare `node-red-data:`:

```yaml
volumes:
  postgresqldata:
  redisdata:
  node-red-data:
```

Save changes (`Ctrl + O`, `Enter`) and exit (`Ctrl + X`).

---

## 🚀 STEP 2: RESTART STACK & VERIFY CONTAINER EXECUTION

Restart Docker Compose to pull the Node-RED image and start the container:

```bash
# Bring stack down
sudo docker compose down

# Start container stack in background
sudo docker compose up -d

# Verify container execution status
sudo docker ps
```

*Confirm `node-red` is running on port `0.0.0.0:1880->1880/tcp`*:

```text
CONTAINER ID   IMAGE                         COMMAND                  STATUS         PORTS
c9d8e7f6a5b4   nodered/node-red:latest-22    "./entrypoint.sh"        Up 1 minute    0.0.0.0:1880->1880/tcp
```

---

## 📦 STEP 3: INSTALL CHIRPSTACK NODE-RED CONTRIBUTION NODES

To decode and manipulate ChirpStack events natively in Node-RED, install the official package: `@chirpstack/node-red-contrib-chirpstack`.

### Method A: Terminal Execution via Docker CLI (RECOMMENDED)

Run these commands inside your Ubuntu VM terminal:

```bash
# 1. Execute interactive bash prompt inside node-red container
sudo docker exec -it node-red bash

# 2. Install ChirpStack nodes using npm
npm install @chirpstack/node-red-contrib-chirpstack

# 3. Exit container prompt
exit

# 4. Restart Node-RED container to load new palette nodes
sudo docker restart node-red
```

---

### Method B: GUI Installation via Node-RED Palette Manager

1. Open your browser and go to `http://<SERVER_IP>:1880`.
2. Click the **Burger Icon** (top-right hamburger menu `☰`) -> Select **Manage palette**.
3. Select the **Install** tab.
4. Search for: `@chirpstack/node-red-contrib-chirpstack`.
5. Click **Install** -> Confirm prompt.

---

## 🌐 STEP 4: ACCESS NODE-RED UI & VERIFY PALETTE

1. Open a browser and navigate to:
   ```http
   http://<SERVER_IP>:1880
   ```
   *(For offline direct AP mode, use `http://192.168.23.137:1880`)*.

2. Look at the left node palette sidebar under the **ChirpStack** category.
3. *Confirm the following nodes are visible*:
   * **`device event`** (Parses incoming uplink events)
   * **`device downlink`** (Formats and queues downlink messages)

---

## 🔄 STEP 5: BUILD AN UPLINK TELEMETRY & ALERT FLOW

Construct your first automated flow to ingest ChirpStack uplinks over MQTT and extract sensor telemetry.

### 5.1 Add and Configure MQTT In Node
1. From the left palette under **network**, drag an **`mqtt in`** node onto the canvas.
2. Double-click the `mqtt in` node to open the **Edit mqtt in node** dialog:
   * **Server**: Ensure `Add new mqtt-broker...` is selected, then click the **Plus button `+`** (or Edit Pencil `✏️`) right next to the Server dropdown menu.
   * **In the "Add new mqtt-broker config node" popup window**:
     * **Server**: Type `mosquitto`
     * **Port**: Type `1883`
     * Click the red **Add** button in the top-right corner.
   * **Action**: `Subscribe to single topic`
   * **Topic**: `application/+/device/+/event/up` *(Recommended for sensor telemetry)*
     > 💡 **Topic Selection Rationale**:
     > * **`application/+/device/+/event/up`**: Listens **exclusively to uplink telemetry** (temperature, humidity, battery data). Recommended for data processing and alert flows.
     > * **`application/+/device/+/event/+`**: Listens to **ALL event types** (uplinks, OTAA joins, downlinks, status checks). Recommended if building a global device logging or network diagnostic flow.
   * **QoS**: `0`
   * **Output**: Select **a parsed JSON object** (or `auto-detect (parsed JSON object, string or buffer)`)
   * **Name**: `ChirpStack MQTT Uplinks`

3. Click the red **Done** button in the top-right corner.

---

### 5.2 Connect ChirpStack Device Event & Debug Nodes
1. Under **ChirpStack** palette, drag a **`device event`** node onto the canvas.
2. Under **output** palette, drag a **`debug`** node onto the canvas.
3. Wire the nodes together:
   * Connect output of **`mqtt in`** -> input of **`device event`**.
   * Connect output of **`device event`** -> input of **`debug`**.

```text
+----------------------------+     +-------------------------+     +-------------------+
|  mqtt in                   |     |  device event           |     |  debug            |
|  (mosquitto:1883)          |===> |  (ChirpStack Parser)    |===> |  (Debug Sidebar)  |
|  Topic: application/.../up |     |                         |     |  msg.payload      |
+----------------------------+     +-------------------------+     +-------------------+
```

4. Click the red **Deploy** button in the top-right corner.

---

### 5.3 Verify Uplink Debug Output
1. Open the **Debug messages** tab in the right sidebar (bug icon `🪲`).
2. Trigger an uplink transmission from your Dragino sensor (or wait for scheduled interval).
3. Expand the received JSON payload tree:
   ```json
   {
     "deviceInfo": {
       "deviceName": "LSN50v2-Sensor-01",
       "devEui": "a84041380189b98f"
     },
     "object": {
       "BatV": 3.664,
       "Door_status": "OPEN",
       "EXTI_Trigger": "FALSE",
       "Hum_SHT31": 49.2,
       "Node_type": "LSN50-S31",
       "TempC_SHT31": 28.8
     }
   }
   ```

---

## ⚡ STEP 6: AUTOMATED ALERTS & DOWNLINK COMMAND TRIGGERING

### 6.1 Create Temperature Threshold Alert (Function Node)
Drag a **`function`** node onto the canvas and paste the following JavaScript matching the Dragino decoder output:

```javascript
// Extract temperature from decoded ChirpStack object (TempC_SHT31)
var temp = msg.payload.object.TempC_SHT31;
var devName = msg.payload.deviceInfo.deviceName;

if (temp && temp > 35.0) {
    msg.topic = "CRITICAL ALERT: High Temperature";
    msg.payload = "Warning! Sensor " + devName + " reported temperature of " + temp + "°C!";
    return msg; // Forward alert to output node
}
return null; // Suppress normal messages
```

Connect `device event` -> `function` -> `email` / `http request` (or Telegram bot node).

---

## 📋 STEP 7: READY-TO-IMPORT NODE-RED FLOW JSON TEMPLATE

You can instantly import a pre-configured processing pipeline into Node-RED:

1. Copy the JSON snippet below.
2. In Node-RED, click top-right menu `☰` -> **Import** -> Paste JSON into clipboard text box -> Click **Import**.

```json
[
    {
        "id": "cs_mqtt_in",
        "type": "mqtt in",
        "z": "flow_chirpstack",
        "name": "ChirpStack Uplink MQTT",
        "topic": "application/+/device/+/event/up",
        "qos": "0",
        "datatype": "json",
        "broker": "mosquitto_broker",
        "nl": false,
        "rap": true,
        "inputs": 0,
        "x": 170,
        "y": 120,
        "wires": [["cs_device_event"]]
    },
    {
        "id": "cs_device_event",
        "type": "chirpstack-device-event",
        "z": "flow_chirpstack",
        "name": "ChirpStack Event Decoder",
        "x": 430,
        "y": 120,
        "wires": [["debug_output", "temp_alert_fn"]]
    },
    {
        "id": "temp_alert_fn",
        "type": "function",
        "z": "flow_chirpstack",
        "name": "Temperature Threshold Check",
        "func": "var obj = msg.payload.object || {};\nvar temp = obj.TempC_SHT31;\nif (temp && temp > 35.0) {\n    msg.payload = {\n        alert: 'CRITICAL_HIGH_TEMP',\n        sensor: msg.payload.deviceInfo.deviceName,\n        value: temp,\n        battery: obj.BatV,\n        time: new Date().toISOString()\n    };\n    return msg;\n}\nreturn null;",
        "outputs": 1,
        "noerr": 0,
        "initialize": "",
        "finalize": "",
        "libs": [],
        "x": 460,
        "y": 200,
        "wires": [["alert_debug"]]
    },
    {
        "id": "debug_output",
        "type": "debug",
        "z": "flow_chirpstack",
        "name": "Full Telemetry Output",
        "active": true,
        "tosidebar": true,
        "console": false,
        "tostatus": false,
        "complete": "payload",
        "targetType": "msg",
        "x": 710,
        "y": 120,
        "wires": []
    },
    {
        "id": "alert_debug",
        "type": "debug",
        "z": "flow_chirpstack",
        "name": "High Temp Alert",
        "active": true,
        "tosidebar": true,
        "console": false,
        "tostatus": false,
        "complete": "payload",
        "targetType": "msg",
        "x": 710,
        "y": 200,
        "wires": []
    },
    {
        "id": "mosquitto_broker",
        "type": "mqtt-broker",
        "name": "Mosquitto Internal",
        "broker": "mosquitto",
        "port": "1883",
        "clientid": "node-red-chirpstack-client",
        "autoConnect": true,
        "usetls": false,
        "protocolVersion": "4",
        "keepalive": "60",
        "cleansession": true
    }
]
```

---

## ⚡ STEP 7: AUTOMATED DOWNLINK QUEUING & CLASS A MECHANICS

Node-RED can trigger automated downlink commands (such as updating telemetry uplink intervals or resetting threshold limits) by publishing MQTT messages to ChirpStack's downlink command topic.

### 7.1 ChirpStack MQTT Downlink Topic Structure
```text
application/{APPLICATION_ID}/device/{DEV_EUI}/command/down
```

### 7.2 Downlink JSON Payload Format
ChirpStack expects a JSON payload containing base64-encoded raw bytes or hex payload structures:

```json
{
  "devEui": "a84041380189b98f",
  "confirmed": false,
  "fPort": 2,
  "data": "AQAAHA==" 
}
```
*(Note: `AQAAHA==` is base64 for hex `0100001C`, or use hex encoding depending on ChirpStack configuration).*

### 7.3 Dragino LSN50v2-S31 Downlink Command Reference

| Command Function | FPort | Hex Payload | Operational Effect |
| :--- | :---: | :--- | :--- |
| **Set Uplink Interval (TDC)** | `2` | `0100003C` | Sets telemetry interval to 60 seconds (1 minute). |
| **Set Uplink Interval (TDC)** | `2` | `01000E10` | Sets telemetry interval to 3600 seconds (1 hour). |
| **Software Reset** | `2` | `04FF` | Reboots sensor MCU without clearing configuration. |
| **Factory Reset (FDR)** | `2` | `04FE` | Restores default factory settings and re-joins OTAA. |

### 7.4 ⚠️ Class A Downlink Delivery & Hardware Reset Gotcha
> ⚠️ **CRITICAL OPERATIONAL CALLOUT**:
> * **Class A Latency**: Dragino LSN50v2-S31 sensors are Class A devices. Downlink commands queued via Node-RED will **NOT** be transmitted instantly. ChirpStack holds the downlink in queue until the sensor sends its **next scheduled Class A uplink**.
> * **DO NOT PRESS PHYSICAL RESET BUTTON**: Pressing the physical `RESET` button on the sensor forces an OTAA `JoinRequest`, which **flushes (clears) all pending queued downlinks** in ChirpStack! To apply queued settings, let the sensor naturally complete its scheduled uplink cycle.

---

## 🔒 STEP 8: NODE-RED SECURITY & CREDENTIAL MANAGEMENT

In production environments, Node-RED Web UI should be protected with user authentication.

### 8.1 Enable Admin Password Authentication
1. Generate a password hash using Node-RED admin tool:
   ```bash
   sudo docker exec -it node-red node -e "console.log(require('bcryptjs').hashSync('YourSecurePassword', 8))"
   ```
2. Edit Node-RED settings file inside container data volume:
   ```bash
   sudo nano /var/lib/docker/volumes/chirpstack-docker_node-red-data/_data/settings.js
   ```
3. Uncomment `adminAuth` section and paste the generated bcrypt hash:
   ```javascript
   adminAuth: {
       type: "credentials",
       users: [{
           username: "admin",
           password: "$2a$08$YourBcryptPasswordHashHere...",
           permissions: "*"
       }]
   },
   ```
4. Restart Node-RED container:
   ```bash
   sudo docker restart node-red
   ```

---

## 🔍 TROUBLESHOOTING RUNBOOK

| Symptom / Error | Root Cause Analysis | Resolution Command |
| :--- | :--- | :--- |
| **ChirpStack nodes missing in left palette** | Package `@chirpstack/node-red-contrib-chirpstack` not installed or container not restarted. | Run `sudo docker exec -it node-red bash -> npm install @chirpstack/node-red-contrib-chirpstack -> exit -> sudo docker restart node-red`. |
| **`mqtt in` node shows `disconnected` state** | Host `mosquitto:1883` unreachable from Node-RED container. | Ensure `mosquitto` container is running (`sudo docker ps`). Check server address is `mosquitto` (not `localhost`). |
| **No debug messages received on uplink** | Incorrect topic filter or QoS mismatch. | Change topic filter to wildcard `application/+/device/+/event/+` and output type to `a parsed JSON object`. |
| **Queued Downlink Not Executed / Discarded** | Physical reset button clicked after queuing downlink via Node-RED, triggering OTAA re-join which flushes queue. | **Do NOT press hardware RESET button**. Allow the sensor to complete its natural Class A uplink cycle to deliver the downlink. |
| **Flow changes lost after container restart** | Persistent volume `node-red-data` not declared in `docker-compose.yml`. | Ensure `volumes: - node-red-data:/data` is present in `docker-compose.yml`. |

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
*Document maintained under `lorawan-setup/docs/05-node-red-integration-guide.md`.*
