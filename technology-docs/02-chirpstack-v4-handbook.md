# Volume 02: ChirpStack v4 Network Server Architecture & Engineering Handbook

## Executive Summary & Educational Purpose

This handbook covers **ChirpStack v4**, the industry-standard, open-source LoRaWAN Network Server stack. ChirpStack handles gateway management, frame deduplication, device activation (OTAA), payload decoding, frame-counter verification, downlinks, gRPC/REST APIs, and database integrations. Designed for system architects, backend engineers, and IoT operations managers, this text details ChirpStack's microservice architecture, component configurations, payload processing pipelines, gRPC code clients, and production troubleshooting runbooks.

---

## 1. ChirpStack v4 Microservice Topology & Architecture

ChirpStack v4 unifies what was previously split into separate Network Server and Application Server microservices into a single consolidated Rust-based binary, significantly increasing performance and reducing memory footprint.

```text
                               +---------------------------------------+
                               |    Gateway Layer (Semtech Forwarder)   |
                               +---------------------------------------+
                                                   │
                                                   │ Semtech UDP Packets (Port 1700)
                                                   v
                               +---------------------------------------+
                               |      ChirpStack Gateway Bridge        |
                               | (UDP Packet -> MQTT Topic Converter)  |
                               +---------------------------------------+
                                                   │
                                                   │ Protobuf / JSON MQTT Topics (Port 1883)
                                                   v
                               +---------------------------------------+
                               |     Mosquitto MQTT Broker Bus         |
                               +---------------------------------------+
                                                   │
                                                   │ Internal MQTT Message Pipeline
                                                   v
+---------------------------------------------------------------------------------------------------+
|                                     ChirpStack v4 Core Server                                     |
|                                                                                                   |
|  +--------------------------------+   +---------------------------------+   +------------------+  |
|  |  Network Server Module         |   | Application Server Module       |   | Web Dashboard UI |  |
|  |  • Frame Counter Verification  |   | • Payload Decoder (JS Engine)   |   |   & REST/gRPC API|  |
|  |  • Deduplication (Redis 7)     |   | • HTTP Webhooks & PostgreSQL    |   |   (Port 8080)    |  |
|  |  • Downlink Queue Scheduler    |   | • Tenant & Device Management    |   |                  |  |
|  +--------------------------------+   +---------------------------------+   +------------------+  |
|                 │                                      │                                          |
|                 v                                      v                                          |
|  +--------------------------------+   +---------------------------------+                         |
|  | Redis 7 (Session & Nonce Cache)|   | PostgreSQL 14 (Metadata DB)     |                         |
|  +--------------------------------+   +---------------------------------+                         |
+---------------------------------------------------------------------------------------------------+
                                   │
                                   │ Decoded JSON Telemetry Streams
                                   v
+---------------------------------------------------------------------------------------------------+
|                                External Integration Subsystems                                    |
|   • PostgreSQL Integration Database (`chirpstack_integration`)                                   |
|   • Node-RED Event Automation Engine (`mosquitto:1883`)                                            |
|   • Grafana Real-Time Dashboards & Analytics (`grafana:3000`)                                     |
|   • Enterprise External Webhooks (HTTP POST endpoints)                                            |
+---------------------------------------------------------------------------------------------------+
```

---

## 2. End-to-End Packet Lifecycle Execution Sequence

When an end-node transmits an uplink packet in the field, it traverses an 8-step execution lifecycle across ChirpStack's microservices:

```text
[ Sensor Node ] ──(1. LoRa RF)──> [ Gateway ] ──(2. UDP 1700)──> [ Gateway Bridge ]
                                                                       │
                                                               (3. MQTT Publish)
                                                                       │
                                                                       v
[ PostgreSQL Integration DB ] <──(7. Integration)── [ Core Server ] <──[ Mosquitto Broker ]
         │                                              │
         v                                      (4. Redis Deduplication)
 [ Grafana / Node-RED ]                         (5. Decrypt AppSKey)
                                                (6. Execute JS Codec)
```

1. **Physical Reception**: Field sensor broadcasts LoRa RF frame; nearby gateways capture the raw packet.
2. **Edge Conversion**: Semtech UDP Packet Forwarder on gateway wraps raw frame in UDP packet and sends to `chirpstack-gateway-bridge` on Port `1700`.
3. **MQTT Encapsulation**: Gateway Bridge converts UDP payload into a structured Protobuf/JSON payload and publishes to MQTT topic: `au915_0/gateway/{gateway_id}/event/up`.
4. **Deduplication (Redis 7)**: ChirpStack Core Server receives the packet from Mosquitto MQTT broker. If multiple gateways received the same frame, Redis holds a **200ms deduplication window**, keeping the packet with the highest Signal-to-Noise Ratio (SNR).
5. **Session Verification & Decryption**: ChirpStack validates `DevAddr` and `FCnt` (Frame Counter) against Redis. It verifies Message Integrity Code (`MIC`) using `NwkSKey` and decrypts `FRMPayload` using `AppSKey`.
6. **Codec Parsing**: ChirpStack executes the JavaScript payload decoder configured in the device's Device Profile, transforming raw hex bytes into structured JSON fields.
7. **Database Persistence**: Decoded telemetry is written to `event_up` inside the PostgreSQL `chirpstack_integration` database.
8. **Application Forwarding**: Decoded JSON is published to application MQTT topics (`application/{app_id}/device/{dev_eui}/event/up`) and dispatched to external Webhooks.

---

## 3. Annotated Production Configurations

### 3.1 ChirpStack Gateway Bridge Config (`chirpstack-gateway-bridge.toml`)

```toml
[integration.mqtt]
# Target MQTT broker
server = "tcp://mosquitto:1883"
json = false # Use compact Protobuf binary serialization over MQTT

# Topic template for uplink events
event_topic_template = "au915_0/gateway/{{ .GatewayID }}/event/{{ .EventType }}"
command_topic_template = "au915_0/gateway/{{ .GatewayID }}/command/{{ .CommandType }}"

[backend.semtech_udp]
# UDP Socket Listener for Semtech Forwarders
ip = "0.0.0.0"
port = 1700
skip_crc_check = false
```

### 3.2 ChirpStack Core Server Config (`chirpstack.toml`)

```toml
[logging]
level = "info"

[postgresql]
dsn = "postgres://chirpstack:chirpstack_pass@postgres:5432/chirpstack?sslmode=disable"
max_open_connections = 20

[redis]
url = "redis://redis:6379/0"

[network]
enabled_regions = ["au915_0", "us915_0", "eu868"]

[api]
bind = "0.0.0.0:8080"
secret = "VERY_SECURE_JWT_SECRET_KEY_CHANGE_IN_PRODUCTION_2026"

[integration]
enabled = ["postgresql", "mqtt"]

[integration.postgresql]
dsn = "postgres://chirpstack_integration:integration_pass@postgres:5432/chirpstack_integration?sslmode=disable"

[integration.mqtt]
server = "tcp://mosquitto:1883"
json = true # Publish human-readable JSON payloads to Application MQTT topics
```

---

## 4. Multi-Tenant Role-Based Domain Hierarchy

ChirpStack v4 enforces a clean 4-tier domain hierarchy to manage enterprise deployments:

```text
[ Global Admin User ]
   │
   ├── [ Tenant 1: Commercial Farm Operations ]
   │      │
   │      ├── [ Device Profile A: WisBlock NPK Sensor Profile ]
   │      │      • LoRaWAN MAC: 1.0.3, Region: AU915 Sub-band 2
   │      │      • Payload Codec: RAK RS485 JS Parser
   │      │
   │      └── [ Application: Orchard Zone 1 ]
   │             ├── [ Device 1: DevEUI A84041380189B98F ]
   │             └── [ Device 2: DevEUI A84041380189B990 ]
   │
   └── [ Tenant 2: Greenhouse Research Array ]
          └── [ Application: Climate House Alpha ]
```

---

## 5. Python gRPC API Client Code Example

Developers can programmatically manage devices, queue downlinks, and query logs using ChirpStack's gRPC API.

```python
import grpc
from chirpstack_api import api

# Connect to ChirpStack gRPC API on Port 8080
channel = grpc.insecure_channel("localhost:8080")
client = api.DeviceServiceStub(channel)

# Define API Authorization Token (JWT)
api_token = "YOUR_ADMIN_API_JWT_TOKEN_HERE"
metadata = [("authorization", f"Bearer {api_token}")]

# Enqueue a Downlink Command (Set Uplink Interval to 60s)
def queue_downlink(dev_eui, hex_payload):
    req = api.EnqueueDeviceQueueItemRequest()
    req.queue_item.dev_eui = dev_eui
    req.queue_item.confirmed = True
    req.queue_item.f_port = 2
    req.queue_item.data = bytes.fromhex(hex_payload)
    
    resp = client.Enqueue(req, metadata=metadata)
    print(f"Downlink queued successfully! Item ID: {resp.id}")

# Usage: Queue 0100003C (60 sec interval) to Node A84041380189B98F
queue_downlink("a84041380189b98f", "0100003c")
```

---

## 6. Comprehensive Troubleshooting & Diagnostic Runbook

### Symptom 1: Gateway Status Shows "Never Seen" / Offline
* **Root Cause Analysis**: Semtech UDP packets on Port 1700 are blocked by firewall or not reaching `chirpstack-gateway-bridge`.
* **Diagnostic Steps**:
  1. Inspect network sockets on server: `sudo netstat -nulp | grep 1700`.
  2. Check Gateway Bridge logs: `sudo docker compose logs -f gateway-bridge`.
  3. Verify gateway `server_address` points to host IP (`hostname -I`).

### Symptom 2: Frame Counter Rejection (`FCNT_DOWN_REJECTED`)
* **Root Cause Analysis**: Device rebooted and reset its internal FCnt to 0, while ChirpStack expected an incrementing number > previous FCnt.
* **Fix**: In ChirpStack Web UI, navigate to **Device ➔ Configuration**, check **Disable Frame-Counter Validation**, or initiate an OTAA Join to reset session state.

---
*Maintained under project `lorawan-setup/technology-docs`.*
