# Network Server Integration Manual (Local Standalone ChirpStack v4, Remote ChirpStack, TTN, AWS)

This manual provides complete configuration guides to connect the **Raspberry Pi 4 + RAK5146 Gateway** to **Local All-In-One ChirpStack v4 (on same Pi 4)**, **Remote ChirpStack v4**, **The Things Network (TTN v3)**, and **AWS IoT Core for LoRaWAN**.

---

## 1. All-In-One Local ChirpStack v4 Integration (Gateway & Server on Same Raspberry Pi 4)

In an offline or standalone agricultural deployment, running both the **RAK5146 Gateway** and the **ChirpStack v4 Server Stack** locally on the same Raspberry Pi 4 Model B eliminates remote latency, network downtime risk, and external infrastructure costs.

```text
+-----------------------------------------------------------------------------------+
|               ALL-IN-ONE STANDALONE PI 4 SOFTWARE TOPOLOGY                        |
|                                                                                   |
|  [RAK5146 SPI Hardware] <---SPI---> [ChirpStack Concentratord]                    |
|                                              |                                    |
|                                         UDP 1700 (Loopback 127.0.0.1)             |
|                                              v                                    |
|  [Docker Container: ChirpStack Gateway Bridge]                                    |
|                                              |                                    |
|                                         MQTT 1883 (Loopback 127.0.0.1)            |
|                                              v                                    |
|  [Docker Containers: Mosquitto <-> ChirpStack v4 LNS <-> PostgreSQL / Redis]      |
|                                              |                                    |
|                                         HTTP Port 8080                            |
|                                              v                                    |
|  [Web UI Dashboard] -------------> http://<PI_IP_ADDRESS>:8080                    |
+-----------------------------------------------------------------------------------+
```

### 1.1 Local Docker Compose Stack Deployment
Run the following commands on the Raspberry Pi 4 to deploy the local ChirpStack stack:

```bash
# 1. Install prerequisites, Docker Engine & Docker Compose on Pi OS Lite
sudo apt-get update && sudo apt-get install -y curl gpg ca-certificates
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker pi
newgrp docker

# 2. Create project directory
sudo mkdir -p /opt/chirpstack-docker/configuration/chirpstack
sudo mkdir -p /opt/chirpstack-docker/configuration/chirpstack-gateway-bridge
sudo chown -R pi:pi /opt/chirpstack-docker
cd /opt/chirpstack-docker

# 3. Create Gateway Bridge configuration
cat << 'EOF' > configuration/chirpstack-gateway-bridge/chirpstack-gateway-bridge.toml
[general]
log_level="info"

[integration.mqtt]
server="tcp://mosquitto:1883"
event_topic_template="as923/gateway/{{ .GatewayID }}/event/{{ .EventType }}"
command_topic_template="as923/gateway/{{ .GatewayID }}/command/{{ .CommandType }}"

[backend.semtech_udp]
ip_arg="0.0.0.0"
port=1700
EOF

# 4. Create ChirpStack Server configuration
cat << 'EOF' > configuration/chirpstack/chirpstack.toml
[logging]
level="info"

[postgresql]
dsn="postgres://chirpstack:chirpstack@postgres/chirpstack?sslmode=disable"

[redis]
url="redis://redis:6379"

[network]
enabled_regions=["as923"]

[integration]
enabled=["mqtt"]

[integration.mqtt]
server="tcp://mosquitto:1883"
json=true
EOF

# 5. Create docker-compose.yml
cat << 'EOF' > docker-compose.yml
services:
  chirpstack:
    image: chirpstack/chirpstack:4
    command: -c /etc/chirpstack
    restart: unless-stopped
    volumes:
      - ./configuration/chirpstack:/etc/chirpstack
    ports:
      - "8080:8080"
    depends_on:
      - postgres
      - redis
      - mosquitto

  chirpstack-gateway-bridge:
    image: chirpstack/chirpstack-gateway-bridge:4
    restart: unless-stopped
    ports:
      - "1700:1700/udp"
    volumes:
      - ./configuration/chirpstack-gateway-bridge:/etc/chirpstack-gateway-bridge
    depends_on:
      - mosquitto

  mosquitto:
    image: eclipse-mosquitto:2
    restart: unless-stopped
    ports:
      - "1883:1883"
    command: mosquitto -c /mosquitto-no-auth.conf

  postgres:
    image: postgres:14-alpine
    restart: unless-stopped
    environment:
      - POSTGRES_USER=chirpstack
      - POSTGRES_PASSWORD=chirpstack
      - POSTGRES_DB=chirpstack
    volumes:
      - postgresqldata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redisdata:/data

volumes:
  postgresqldata:
  redisdata:
EOF

# 6. Launch Stack
docker compose up -d
```

### 1.2 Accessing the Local Web UI
Open your browser to `http://<PI_IP_ADDRESS>:8080` (Default credentials: `admin` / `admin`).

---

## 2. Remote Private ChirpStack v4 Server Integration

If running ChirpStack on a remote cloud server or central VM:
1. Obtain the Gateway EUI derived from the Pi 4 `eth0` MAC address.
2. In the remote ChirpStack Web UI, navigate to **Gateways -> Add Gateway**.
3. Point your gateway's packet forwarder configuration (`global_conf.json` or `concentratord.toml`) to `<REMOTE_SERVER_IP>` on UDP Port 1700.

---

## 3. The Things Network (TTN / TTS v3) Integration Guide

1. Register Gateway EUI in TTN Console (`eu1.cloud.thethings.network` or `au1.cloud.thethings.network`).
2. Generate a Gateway API key.
3. Configure Basic Station (`/etc/station/tc.uri` and `/etc/station/tc.key`).
