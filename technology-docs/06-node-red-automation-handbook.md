# Volume 06: Node-RED Event Automation Engine Handbook

## Executive Summary & Educational Purpose

This handbook covers flow-based visual programming, event-driven reactive architecture, MQTT payload parsing, state machine design, and automated physical actuation using **Node-RED**. Designed for automation engineers, systems integrators, and agricultural hardware specialists, this text details how to build an automated **24/7 Digital Farm Watchman** that evaluates live sensor telemetry streams in milliseconds to send instant SMS alerts and trigger physical solenoid irrigation valves.

---

## 1. Node-RED Architecture & Event-Driven Rule Engine

Node-RED is a browser-based visual flow editor containerized on TCP Port `1880`. Built on Node.js, it subscribes directly to the Mosquitto MQTT broker (`mosquitto:1883`), parsing incoming sensor packets asynchronously as events occur.

```text
+-----------------------------------------------------------------------------------+
|                            Mosquitto MQTT Message Broker                          |
|                       Topic: `application/+/device/+/event/up`                    |
+-----------------------------------------------------------------------------------+
                                         │
                                         │ Real-time MQTT Messages (Port 1883)
                                         v
+-----------------------------------------------------------------------------------+
|                           Node-RED Automation Engine                              |
|                                                                                   |
|  +-------------------+   +--------------------+   +----------------------------+  |
|  | MQTT In Node      |-->| JS Function Node   |-->| Switch Node                |  |
|  | (Subscribes stream|   | (Extracts temp &   |   | (Checks thresholds:        |  |
|  |  from ChirpStack) |   |  soil moisture)    |   |  Temp < 2.0°C or           |  |
|  +-------------------+   +--------------------+   |  Moisture < 15%)           |  |
|                                                   +----------------------------+  |
|                                                                 │                 |
|                                         +-----------------------+                 |
|                                         v                       v                 |
|                             +-----------------------+ +-------------------------+ |
|                             | Twilio / SMS Node     | | GPIO / Solenoid Relay   | |
|                             | (Sends Manager Alert) | | (Triggers Water Pump) | |
|                             +-----------------------+ +-------------------------+ |
+-----------------------------------------------------------------------------------+
```

---

## 2. Docker Compose Node-RED Definition (`docker-compose.yml`)

```yaml
  nodered:
    image: nodered/node-red:latest
    container_name: chirpstack-docker-nodered-1
    restart: unless-stopped
    ports:
      - "1880:1880"
    volumes:
      - nodered_data:/data
    environment:
      - TZ=UTC
```

---

## 3. Core Automation Flow Patterns & JavaScript Code Nodes

### Pattern 1: Freeze Protection & Automated Sprinkler Valve Trigger

When canopy temperatures drop below **2.0°C**, frost damage threatens delicate crops. Node-RED catches this event within 50 milliseconds, sending an urgent SMS to farm managers and triggering an automated solenoid irrigation valve to release latent heat.

```text
[ MQTT In: Uplink ] ──> [ Extract Temp ] ──> [ Switch: Temp < 2.0°C ]
                                                      │
                                                      ├──> [ Twilio SMS Alert ]
                                                      └──> [ HTTP Post: Relay ON ]
```

#### JavaScript Function Node: `Evaluate Frost Threshold`

```javascript
// Extract decoded telemetry object from ChirpStack MQTT payload
var telemetry = msg.payload.object;

if (!telemetry || telemetry.temperature === undefined) {
    return null; // Ignore non-temperature uplinks
}

var temp = parseFloat(telemetry.temperature);
var deviceName = msg.payload.deviceInfo.deviceName;

// Use flow context memory to implement a 15-minute alert cooldown timer
var lastAlert = flow.get("last_frost_alert_time") || 0;
var now = Date.now();

if (temp <= 2.0) {
    var alertMsg = null;
    
    // Check if 15 minutes (900,000 ms) have passed since last SMS alert
    if (now - lastAlert > 900000) {
        flow.set("last_frost_alert_time", now);
        alertMsg = {
            payload: "CRITICAL FROST WARNING: Temperature at " + deviceName + 
                     " has dropped to " + temp.toFixed(1) + "°C! Automated sprinklers activated."
        };
    }
    
    // Construct Relay command payload (Always trigger solenoid relay)
    var relayMsg = {
        payload: {
            relay_id: 1,
            state: "ON",
            duration_minutes: 30
        }
    };
    
    return [alertMsg, relayMsg]; // Output to 2 separate nodes
}

return null;
```

---

### Pattern 2: Precision Soil Moisture Drought & Solenoid Actuation

```javascript
// Extract soil moisture from RAKwireless NPK Sensor telemetry
var moisture = parseFloat(msg.payload.object.soil_moisture);

if (moisture < 15.0) { // Below 15% Volumetric Water Content
    msg.payload = {
        command: "ACTUATE_VALVE",
        zone: "Zone_1_North",
        flow_rate_lpm: 50,
        status: "IRRIGATING"
    };
    return msg;
}
```

---

## 4. Hardware Relay Interfacing (Raspberry Pi GPIO Solenoid)

To control a physical 12V / 24V Solenoid Water Valve, Node-RED toggles a Raspberry Pi GPIO pin connected to a 5V Optocoupler Relay Module.

```text
+----------------------+         +-----------------------+         +-------------------+
| Raspberry Pi GPIO 18 |──(5V)──>| Optocoupler Relay     |──(12V)─>| 24V AC Solenoid   |
| (Node-RED Output)    |         | Module (NO / COM)     |         | Water Valve       |
+----------------------+         +-----------------------+         +-------------------+
```

### Node-RED GPIO Node Configuration

* **PIN**: `GPIO 18 - (Pin 12)`
* **Type**: Digital Output
* **Logical Rule**: `1` = Relay Energized (Valve Open), `0` = Relay De-energized (Valve Closed)

---

## 5. Exportable Node-RED Flow JSON Template

To import this automated farm watchman flow into Node-RED:

1. Open Node-RED (`http://<VM-IP>:1880`).
2. Click Menu ➔ **Import**.
3. Paste the JSON template below:

```json
[
  {
    "id": "mqtt_in_chirpstack",
    "type": "mqtt in",
    "z": "flow_farm_watchman",
    "name": "ChirpStack Uplinks",
    "topic": "application/+/device/+/event/up",
    "qos": "2",
    "datatype": "json",
    "broker": "mosquitto_broker",
    "x": 140,
    "y": 120,
    "wires": [["fn_eval_frost"]]
  },
  {
    "id": "fn_eval_frost",
    "type": "function",
    "z": "flow_farm_watchman",
    "name": "Evaluate Frost Threshold",
    "func": "var temp = msg.payload.object ? msg.payload.object.temperature : null;\nif (temp !== null && temp <= 2.0) {\n    msg.payload = 'ALERT: Frost detected! Temp: ' + temp + '°C';\n    return msg;\n}\nreturn null;",
    "outputs": 1,
    "x": 380,
    "y": 120,
    "wires": [["debug_output"]]
  },
  {
    "id": "debug_output",
    "type": "debug",
    "z": "flow_farm_watchman",
    "name": "Console Alert",
    "active": true,
    "x": 610,
    "y": 120,
    "wires": []
  }
]
```

---

## 6. Operational Watchman Best Practices

1. ✅ **Sub-second Latency**: Keep JavaScript functions lightweight; avoid external synchronous HTTP fetches inside critical alert flows.
2. ✅ **Alert Debouncing**: Implement cooldown timers using `flow.get()` context memory to prevent SMS flooding.
3. ✅ **Fail-Safe Valve Shutdown**: Always include a watchdog timer node that automatically closes solenoid valves after 60 minutes in case network connectivity drops mid-irrigation.

---
*Maintained under project `lorawan-setup/technology-docs`.*
