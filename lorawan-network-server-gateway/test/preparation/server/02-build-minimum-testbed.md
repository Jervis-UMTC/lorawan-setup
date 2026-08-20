# Server 2. Build the Minimum Dissertation Testbed

This manual is a **step-by-step guide** to building and operating the 7-container dissertation testbed on a single local VM.

All server commands, configuration files, SQL schemas, PKI generation scripts, and validation steps are inline. Physical Raspberry Pi gateway configuration is intentionally handed off to `test/preparation/gateway/04-06` after the server has the gateway EUI, certificate, ACL, and ChirpStack registration. Keeping one gateway procedure prevents the server manual from silently bypassing the required local MQTT buffer.

---

## Service Lifecycle Architecture & Execution Strategy

Understanding the operational workflow of this testbed:

1. **First-Time Provisioning (Initialization Phase)**:
   - On a fresh VM, inner database roles (`chirpstack`, `telemetry_writer`, `fabric_adapter`), telemetry tables, OpenBao KMS Transit keys, and TLS certificates are initialized **once**.
   - Follow Sections 1 through 13 sequentially during initial setup to initialize these assets without containers crash-looping due to missing database tables or unsealed keys.

2. **Standard / Daily Operation (Single-Command Option A Execution)**:
   - Once initial provisioning is completed, all container states, databases, and keys persist in named Docker volumes (`telemetry-data`, `openbao-data`, `valkey-data`, `mosquitto-data`, `node-red-data`).
   - To start, stop, or restart the entire 7-container testbed stack at any point, execute **a single Docker Compose command**:
     ```bash
     cd /opt/lorawan-lab
     docker compose up -d    # Starts all 7 services in proper dependency order
     docker compose stop     # Gracefully stops all 7 services
     ```
   - Docker Compose automatically respects all `depends_on` graph relationships (`telemetry-db`, `valkey`, `mosquitto` $\rightarrow$ `chirpstack`, `node-red`, `fabric-adapter`).

---

## 1. Allocate VM Resources & Prepare OS

### Hardware Profile
Allocate only a portion of your physical host's hardware (e.g., 8 GiB physical host):

```text
Guest OS: Ubuntu Server 24.04 LTS (No desktop GUI)
RAM:  5 GiB (Absolute minimum: 4 GiB)
vCPU: 4 vCPU cores
Disk: 50 GiB SSD-backed minimum
Network: Bridged Adapter (or Host-Only with Port Forwarding for SSH :22 / MQTT :8883)
```

**Accompanying Explanation & Rationale:**
- **Host Memory Protection**: Leaving 3 GiB RAM and 4 CPU threads unallocated ensures the host hypervisor has sufficient headroom. If the VM is over-allocated to 8 GiB, host OS memory pressure will trigger disk swapping, artificially inflating test latency and invalidating dissertation benchmark timings.
- **Minimum VM Ceiling**: A 5 GiB RAM allocation gives TimescaleDB (1 GiB), ChirpStack (512 MB), Node-RED (384 MB), Fabric-Adapter (384 MB), OpenBao (256 MB), Valkey (192 MB), and Mosquitto (192 MB) ample operating room without host swap interference.

---

### OS OS Swap & Memory Tuning Commands

Run on the VM:

```bash
# Add 2 GiB swap safety net
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Tune swappiness for database performance
printf 'vm.swappiness=10\n' | sudo tee /etc/sysctl.d/99-lorawan-test-memory.conf
sudo sysctl --system
```

---

### Install Docker Engine & Docker Compose v2

Run on the VM:

```bash
# Add Docker's official GPG key:
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Allow non-root docker commands for current user:
sudo usermod -aG docker $USER
```

*Note: Log out and log back in over SSH to apply the `docker` group membership.*

Verify installation:

```bash
docker version
docker compose version
```

---

## 2. Required External Hardware Checklist

Ensure the following physical hardware is present outside the server VM:

```text
1 x Raspberry Pi 4B + RAK5146 gateway
1 x correct antenna
2 x RAK4631 WisBlock Core + RAK19001/RAK19007 baseboards from the Agriculture Kit
  - RAK4631 #1 / RAK19001 = EMU-01 legitimate full physical-sensor OTAA node
  - RAK4631 #2 / RAK19007 = SEC-02 second-copy sensor verification, then invalid-device / replay / spoofing security test node
Complete Agriculture Kit direct sensor inventory, with one full sensor set retained on EMU-01
1 x separate test laptop for MQTT and flooding
```

**Accompanying Explanation & Rationale:**
- **Physical Sensor + RF Integrity**: EMU-01 samples the real Agriculture Kit sensors and transmits those measurements through real LoRaWAN RF and the RAK5146. This preserves physical sensing, OTAA, MIC, frame-counter, RF reception, gateway forwarding, and buffering in the measured path. Direct MQTT-only sensor simulation is not used for counted LoRaWAN results.
- **Two fixed RAK4631 roles**: Keeping EMU-01 as the legitimate device and SEC-02 as the security node prevents invalid credentials/raw-frame tooling from contaminating the normal device. SEC-02 must never be provisioned with EMU-01's legitimate AppKey or session keys.
- **Isolated Flooding Workstation**: Dedicated test laptop prevents load generator execution overhead from consuming vCPU cycles on the server VM.

---

## 3. Create Project Directory & Mount Structure

On the VM:

```bash
sudo mkdir -p /opt/lorawan-lab
sudo chown "$USER":"$USER" /opt/lorawan-lab
cd /opt/lorawan-lab
mkdir -p configuration/{mosquitto,valkey,chirpstack,openbao}
mkdir -p secrets/openbao-approle
```

**Accompanying Explanation & Rationale:**
- **Permissions & Mount Isolation**: Placing the testbed in `/opt/lorawan-lab` with standard `$USER` ownership avoids running Compose operations as `root` while providing clean mount targets for read-only config subdirectories (`configuration/`) and sensitive TLS key storage (`secrets/`).

---

## 4. Create the Minimal 7-Container `docker-compose.yml`

Create `/opt/lorawan-lab/docker-compose.yml`:

```bash
cat << 'EOF' > /opt/lorawan-lab/docker-compose.yml
networks:
  application:
  telemetry:
    internal: true
  kms:
    internal: true

volumes:
  telemetry-data:
  mosquitto-data:
  valkey-data:
  node-red-data:
  openbao-data:

services:
  telemetry-db:
    image: timescale/timescaledb:latest-pg15
    container_name: telemetry-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: telemetry_admin
      POSTGRES_PASSWORD: ${LAB_DB_PASSWORD:-telemetry_secret_pass}
      POSTGRES_DB: lorawan_telemetry
    cpus: ${LAB_TIMESCALEDB_CPUS:-1.00}
    mem_limit: ${LAB_TIMESCALEDB_MEM:-1024m}
    volumes:
      - telemetry-data:/var/lib/postgresql/data
    networks:
      - telemetry

  mosquitto:
    image: eclipse-mosquitto:2.0
    container_name: mosquitto
    restart: unless-stopped
    cpus: ${LAB_MOSQUITTO_CPUS:-0.25}
    mem_limit: ${LAB_MOSQUITTO_MEM:-192m}
    ports:
      - "8883:8883"
    volumes:
      - ./configuration/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - ./configuration/mosquitto/passwd:/mosquitto/config/passwd:ro
      - ./configuration/mosquitto/acl:/mosquitto/config/acl:ro
      - ./secrets/certs:/mosquitto/config/certs:ro
      - mosquitto-data:/mosquitto/data
    networks:
      - application

  valkey:
    image: valkey/valkey:7.2-alpine
    container_name: valkey
    restart: unless-stopped
    cpus: ${LAB_VALKEY_CPUS:-0.20}
    mem_limit: ${LAB_VALKEY_MEM:-192m}
    command: valkey-server --save 60 1 --loglevel notice
    volumes:
      - valkey-data:/data
    networks:
      - application

  chirpstack:
    image: chirpstack/chirpstack:4.9.0
    container_name: chirpstack
    restart: unless-stopped
    command: -c /etc/chirpstack
    cpus: ${LAB_CHIRPSTACK_CPUS:-0.60}
    mem_limit: ${LAB_CHIRPSTACK_MEM:-512m}
    depends_on:
      - telemetry-db
      - valkey
      - mosquitto
    ports:
      - "8080:8080"
    volumes:
      - ./configuration/chirpstack:/etc/chirpstack:ro
    networks:
      - application
      - telemetry

  node-red:
    image: nodered/node-red:latest
    container_name: node-red
    restart: unless-stopped
    cpus: ${LAB_NODE_RED_CPUS:-0.50}
    mem_limit: ${LAB_NODE_RED_MEM:-384m}
    environment:
      TZ: Asia/Manila
    depends_on:
      - telemetry-db
      - mosquitto
    ports:
      - "1880:1880"
    volumes:
      - node-red-data:/data
    networks:
      - application
      - telemetry

  openbao:
    image: openbao/openbao:2.0.0
    container_name: openbao
    restart: unless-stopped
    cpus: ${LAB_OPENBAO_CPUS:-0.25}
    mem_limit: ${LAB_OPENBAO_MEM:-256m}
    command: ["server", "-config=/openbao/config/openbao.hcl"]
    volumes:
      - ./configuration/openbao:/openbao/config:ro
      - openbao-data:/openbao/data
    networks:
      - kms

  fabric-adapter:
    image: lorawan/fabric-adapter:latest
    container_name: fabric-adapter
    restart: unless-stopped
    cpus: ${LAB_FABRIC_ADAPTER_CPUS:-0.50}
    mem_limit: ${LAB_FABRIC_ADAPTER_MEM:-384m}
    environment:
      DB_HOST: telemetry-db
      DB_PORT: "5432"
      DB_NAME: lorawan_telemetry
      DB_USER: fabric_adapter
      DB_PASSWORD: ${LAB_DB_PASSWORD:-telemetry_secret_pass}
      OPENBAO_ADDR: http://openbao:8200
      OPENBAO_TRANSIT_KEY: lorawan-evidence
      OPENBAO_ROLE_ID_FILE: /run/openbao-approle/role_id
      OPENBAO_SECRET_ID_FILE: /run/openbao-approle/secret_id
    volumes:
      - ./secrets/openbao-approle:/run/openbao-approle:ro
    depends_on:
      - telemetry-db
      - openbao
    networks:
      - application
      - telemetry
      - kms
EOF
```

**Accompanying Explanation & Rationale:**
- **Single Minimal Stack Topology**: Consolidates network server, telemetry data ingestion, KMS attestation, and Fabric adapter functions into one `docker-compose.yml`.
- **Elimination of Production HA Middleware**: Excludes Patroni, etcd, HAProxy, PgBouncer, and Grafana. This saves ~1.5 GiB RAM while retaining 100% of functional LoRaWAN MAC processing, telemetry persistence, and cryptographic outbox commit mechanics required for research verification.

---

## 5. Create Resource Configuration (`.env`)

Add resource safety limits to `/opt/lorawan-lab/.env`:

```bash
cat << 'EOF' > /opt/lorawan-lab/.env
LAB_DB_PASSWORD=telemetry_secret_pass
LAB_MOSQUITTO_CPUS=0.25
LAB_MOSQUITTO_MEM=192m
LAB_VALKEY_CPUS=0.20
LAB_VALKEY_MEM=192m
LAB_CHIRPSTACK_CPUS=0.60
LAB_CHIRPSTACK_MEM=512m
LAB_TIMESCALEDB_CPUS=1.00
LAB_TIMESCALEDB_MEM=1024m
LAB_NODE_RED_CPUS=0.50
LAB_NODE_RED_MEM=384m
LAB_OPENBAO_CPUS=0.25
LAB_OPENBAO_MEM=256m
LAB_FABRIC_ADAPTER_CPUS=0.50
LAB_FABRIC_ADAPTER_MEM=384m
EOF

chmod 600 /opt/lorawan-lab/.env
```

Verify configured services:

```bash
cd /opt/lorawan-lab
docker compose config --services
```

Expected output:
```text
chirpstack
fabric-adapter
mosquitto
node-red
openbao
telemetry-db
valkey
```

---

## 6. Deploy TimescaleDB & Initialize Telemetry Schema

### Start TimescaleDB Container

```bash
cd /opt/lorawan-lab
docker compose up -d telemetry-db
docker compose ps telemetry-db
```

Wait until PostgreSQL is ready:
```bash
until docker compose exec telemetry-db pg_isready -U telemetry_admin; do
  sleep 2
done
```

---

### Create ChirpStack Database & Role

Execute inside PostgreSQL:

```bash
docker compose exec -T telemetry-db psql -U telemetry_admin -d lorawan_telemetry << 'SQL'
CREATE ROLE chirpstack LOGIN PASSWORD 'chirpstack_pass';
CREATE DATABASE chirpstack OWNER chirpstack;
\c chirpstack
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL
```

---

### Create Generic Telemetry Schema & Hypertables

Run this single SQL block to create roles, schemas, generic `uplinks`, `measurements`, `device_registry`, hypertables, and indexes:

```bash
docker compose exec -T telemetry-db psql -U telemetry_admin -d lorawan_telemetry << 'SQL'
-- 1. Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- 2. Create roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telemetry_writer') THEN
        CREATE ROLE telemetry_writer LOGIN PASSWORD 'writer_secret_pass';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telemetry_reader') THEN
        CREATE ROLE telemetry_reader LOGIN PASSWORD 'reader_secret_pass';
    END IF;
END
$$;

-- 3. Create Telemetry Schema
CREATE SCHEMA IF NOT EXISTS telemetry;

-- 4. Create uplinks table
CREATE TABLE IF NOT EXISTS telemetry.uplinks (
    event_key           TEXT NOT NULL,
    time                TIMESTAMPTZ NOT NULL,
    received_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    domain              TEXT,
    site_id             TEXT,
    zone_id             TEXT,
    asset_id            TEXT,
    application_id      TEXT,
    application_name    TEXT,
    device_id           TEXT,
    device_name         TEXT,
    dev_eui             TEXT NOT NULL,
    device_model        TEXT,
    decoder_version     TEXT,
    gateway_id          TEXT,
    region              TEXT,
    f_port              INTEGER,
    f_cnt               BIGINT,
    confirmed           BOOLEAN,
    rssi_dbm            INTEGER,
    snr_db              DOUBLE PRECISION,
    temperature_c       DOUBLE PRECISION,
    humidity_percent    DOUBLE PRECISION,
    battery_v           DOUBLE PRECISION,
    payload_json        JSONB NOT NULL,
    raw_data            TEXT,
    mqtt_topic          TEXT
);

-- 5. Create measurements table
CREATE TABLE IF NOT EXISTS telemetry.measurements (
    measurement_id      BIGINT GENERATED BY DEFAULT AS IDENTITY,
    time                TIMESTAMPTZ NOT NULL,
    event_key           TEXT NOT NULL,
    domain              TEXT,
    site_id             TEXT,
    zone_id             TEXT,
    asset_id            TEXT,
    device_id           TEXT,
    dev_eui             TEXT NOT NULL,
    metric_name         TEXT NOT NULL,
    metric_value        DOUBLE PRECISION,
    metric_text         TEXT,
    metric_bool         BOOLEAN,
    unit                TEXT NOT NULL,
    quality             TEXT NOT NULL DEFAULT 'measured',
    source_field        TEXT,
    payload_json        JSONB
);

-- 6. Create device registry
CREATE TABLE IF NOT EXISTS telemetry.device_registry (
    dev_eui             TEXT PRIMARY KEY,
    device_id           TEXT,
    device_name         TEXT,
    domain              TEXT,
    site_id             TEXT,
    zone_id             TEXT,
    asset_id            TEXT,
    device_model        TEXT,
    decoder_name        TEXT,
    decoder_version     TEXT,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen          TIMESTAMPTZ,
    last_seen           TIMESTAMPTZ,
    notes               TEXT
);

-- 7. Convert to Hypertables
SELECT create_hypertable('telemetry.uplinks', 'time', if_not_exists => TRUE);
SELECT create_hypertable('telemetry.measurements', 'time', if_not_exists => TRUE);

-- 8. Add Indexes
CREATE UNIQUE INDEX IF NOT EXISTS uplinks_event_key_time_uq ON telemetry.uplinks (event_key, time);
CREATE INDEX IF NOT EXISTS uplinks_device_time_idx ON telemetry.uplinks (dev_eui, time DESC);
CREATE INDEX IF NOT EXISTS measurements_device_metric_time_idx ON telemetry.measurements (dev_eui, metric_name, time DESC);
CREATE UNIQUE INDEX IF NOT EXISTS measurements_event_metric_unit_time_uq ON telemetry.measurements (event_key, metric_name, unit, time);

-- 9. Grant Permissions
GRANT USAGE ON SCHEMA telemetry TO telemetry_writer, telemetry_reader;
GRANT INSERT, SELECT ON telemetry.uplinks, telemetry.measurements TO telemetry_writer;
GRANT SELECT ON ALL TABLES IN SCHEMA telemetry TO telemetry_reader;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA telemetry TO telemetry_writer;
SQL
```

---

## 7. Deploy Mosquitto Broker & Valkey Cache

### Create Mosquitto Configuration & ACL

Create `/opt/lorawan-lab/configuration/mosquitto/mosquitto.conf`:

```conf
persistence true
persistence_location /mosquitto/data/
log_dest stdout
per_listener_settings true

# Listener 1: Internal application (Docker-internal)
listener 1883
protocol mqtt
allow_anonymous false
password_file /mosquitto/config/passwd
acl_file /mosquitto/config/acl

# Listener 2: Physical Gateway mTLS (Host-published 8883)
listener 8883
protocol mqtt
cafile /mosquitto/config/certs/mqtt-ca.crt
certfile /mosquitto/config/certs/server.crt
keyfile /mosquitto/config/certs/server.key
require_certificate true
use_identity_as_username true
allow_anonymous false
acl_file /mosquitto/config/acl
tls_version tlsv1.2
```

Create base Mosquitto ACL `/opt/lorawan-lab/configuration/mosquitto/acl`:

```text
# Internal ChirpStack Service
user chirpstack
topic readwrite as923/gateway/#
topic readwrite application/#

# Internal Node-RED Service
user node_red
topic read application/+/device/+/event/up
```

Create Mosquitto user password file `/opt/lorawan-lab/configuration/mosquitto/passwd`:

```bash
sudo docker run --rm -v /opt/lorawan-lab/configuration/mosquitto:/work eclipse-mosquitto:2.0 mosquitto_passwd -c -b /work/passwd chirpstack chirpstack_pass
sudo docker run --rm -v /opt/lorawan-lab/configuration/mosquitto:/work eclipse-mosquitto:2.0 mosquitto_passwd -b /work/passwd node_red node_red_pass
sudo chmod 600 /opt/lorawan-lab/configuration/mosquitto/passwd
sudo chown 1883:1883 /opt/lorawan-lab/configuration/mosquitto/passwd
```

---

### Generate Server & Gateway mTLS Certificates

Run this script to generate the CA, Server Certificate, and Gateway Client Certificate:

```bash
sudo install -d -m 700 /root/lorawan-lab-pki
mkdir -p /opt/lorawan-lab/secrets/certs

sudo bash -c '
set -e
cd /root/lorawan-lab-pki

# 1. Generate CA
openssl genrsa -out ca.key 4096
openssl req -x509 -new -nodes -key ca.key -sha256 -days 3650 -out ca.crt -subj "/CN=LoRaWAN-Lab-CA"

# 2. Generate Broker Server Certificate (CN=lora-test-server)
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr -subj "/CN=lora-test-server"
cat > server.ext <<EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names
[alt_names]
DNS.1 = lora-test-server
IP.1 = 127.0.0.1
EOF
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out server.crt -days 365 -sha256 -extfile server.ext

# Copy broker certs into place
cp ca.crt server.crt server.key /opt/lorawan-lab/secrets/certs/
cp ca.crt /opt/lorawan-lab/secrets/certs/mqtt-ca.crt
chmod 644 /opt/lorawan-lab/secrets/certs/*.crt
chmod 600 /opt/lorawan-lab/secrets/certs/*.key
chown -R 1883:1883 /opt/lorawan-lab/secrets/certs
'
```

Start Mosquitto and Valkey:

```bash
cd /opt/lorawan-lab
docker compose up -d mosquitto valkey
docker compose ps mosquitto valkey
```

---

## 8. Configure & Deploy ChirpStack

Create `/opt/lorawan-lab/configuration/chirpstack/chirpstack.toml`:

```toml
[logging]
level = "info"

[postgresql]
dsn = "postgresql://chirpstack:chirpstack_pass@telemetry-db:5432/chirpstack?sslmode=disable"
max_open_connections = 10

[redis]
servers = ["redis://valkey:6379"]

[network]
net_id = "000000"
enabled_regions = ["as923"]

[api]
bind = "0.0.0.0:8080"
secret = "chirpstack_jwt_secret_change_me_32chars"

[integration]
enabled = ["mqtt"]

[integration.mqtt]
server = "tcp://mosquitto:1883"
json = true
username = "chirpstack"
password = "chirpstack_pass"
```

Create Region File `/opt/lorawan-lab/configuration/chirpstack/region_as923.toml` using the ChirpStack v4 region structure. Preserve any additional AS923 channel/network fields required by the current project; the important v4 shape is:

**Frozen lab rule:** this testbed uses plain `AS923` end-to-end: ChirpStack enabled region `as923`, region ID `as923`, MQTT topic prefix `as923`, Gateway OS channel plan `AS923`, and RAK4631 firmware constant `LORAMAC_REGION_AS923`. Do not substitute `as923_3` / `LORAMAC_REGION_AS923_3` on only one component.

```toml
[[regions]]
id="as923"
description="AS923"

[regions.network]
rx2_frequency=923200000
rx2_dr=2

[regions.gateway.backend]
enabled="mqtt"

[regions.gateway.backend.mqtt]
topic_prefix="as923"
server="tcp://mosquitto:1883"
username="chirpstack"
password="chirpstack_pass"
```

`chirpstack.toml` must keep:

```toml
[network]
enabled_regions = ["as923"]
```

Do not use the old singular `[region]` / `[region.gateway.backend.mqtt]` form with ChirpStack 4.9.

Before starting ChirpStack, keep the bind-mounted configuration directory deliberately small. **Do not leave backup TOML files in `configuration/chirpstack/`** because ChirpStack loads configuration from that mounted directory and stale files can cause duplicate-key parse failures.

```bash
cd /opt/lorawan-lab
mkdir -p config-backups/chirpstack

# Move any old backups out of the bind-mounted config directory before startup.
find configuration/chirpstack -maxdepth 1 -type f \
  \( -name '*.bak' -o -name '*.old' -o -name '*.before-fix' \) \
  -exec mv -t config-backups/chirpstack {} + 2>/dev/null || true

grep -RnsE '^\[region\]$|^\[\[regions\]\]$' configuration/chirpstack
find configuration/chirpstack -maxdepth 1 -type f -printf '%f\n' | sort
```

For this minimum setup the intended active top-level TOML set is only `chirpstack.toml` and `region_as923.toml`. A crash such as `duplicate key region in document root` means inspect the mounted directory for stale/duplicate TOML before changing unrelated services.

Start ChirpStack:

```bash
docker compose up -d chirpstack
docker compose logs --since=2m --tail=100 chirpstack
```

Verify ChirpStack migrations succeeded and web UI is listening at `http://<VM_IP>:8080`.

---

## 9. Provision Gateway mTLS Identity & ACL

### Order of Operations Workflow
1. **Step A (Server-Side mTLS & ACL)**: Issue the client certificate and ensure exactly one matching Mosquitto ACL block exists first. Mosquitto on port `8883` will reject any incoming gateway mTLS connection until its certificate CN and topic ACL are authorized.
2. **Step B (ChirpStack Web UI Registration)**: Add the gateway in ChirpStack Web UI (`http://<VM_IP>:8080`) using the exact 16-hex Gateway EUI. AS923 is selected by the server region configuration, not a required Add Gateway dropdown.
3. **Step C (Raspberry Pi Gateway Setup)**: Copy certificate files to the Pi, configure the persistent bridge, and start the Pi Mosquitto service.

---

### Step A: Issue Server-Side mTLS Certificates & Mosquitto ACL

To authorize a physical gateway (lab example EUI `0016c001f139a1cb`), issue its client certificate and keep exactly one ACL block for that EUI:

```bash
export GATEWAY_EUI="0016c001f139a1cb"

# 1. Issue Client Certificate & Copy to /opt/lorawan-lab/secrets/certs/
sudo bash -c "
cd /root/lorawan-lab-pki
openssl genrsa -out ${GATEWAY_EUI}.key 2048
openssl req -new -key ${GATEWAY_EUI}.key -out ${GATEWAY_EUI}.csr -subj \"/CN=${GATEWAY_EUI}\"
openssl x509 -req -in ${GATEWAY_EUI}.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out ${GATEWAY_EUI}.crt -days 365 -sha256
cp ${GATEWAY_EUI}.crt ${GATEWAY_EUI}.key /opt/lorawan-lab/secrets/certs/
chmod 644 /opt/lorawan-lab/secrets/certs/*.crt
chmod 600 /opt/lorawan-lab/secrets/certs/*.key
"

# 2. Inspect the ACL before editing. Do not append duplicate gateway blocks.
grep -n -A4 -B1 "^user ${GATEWAY_EUI}$" /opt/lorawan-lab/configuration/mosquitto/acl || true

sudoedit /opt/lorawan-lab/configuration/mosquitto/acl
```

Keep exactly one block for the real EUI and remove stale/wrong-EUI duplicates:

```text
user <GATEWAY_EUI>
topic write as923/gateway/<GATEWAY_EUI>/event/#
topic write as923/gateway/<GATEWAY_EUI>/state/#
topic read as923/gateway/<GATEWAY_EUI>/command/#
```

Then reload Mosquitto:

```bash
cd /opt/lorawan-lab
sudo docker compose restart mosquitto
```

---

### Step B: Register Gateway in ChirpStack Web UI

1. Open your browser and navigate to ChirpStack Web UI: `http://<SERVER_VM_IP>:8080`
2. Log in with admin credentials (default: `admin` / `admin`).
3. Navigate to **Tenants** $\rightarrow$ **ChirpStack** $\rightarrow$ **Gateways**.
4. Click **Add Gateway** and enter the fields exposed by ChirpStack 4.9:
   * **Name**: `Gateway-01`
   * **Gateway ID (EUI64)**: `<GATEWAY_EUI>` — paste the exact 16-hex value reported by Concentratord; it must match the certificate CN and Mosquitto ACL.
   * **Byte Order**: `MSB`
   * **Stats interval (secs)**: `30`
5. Click **Submit**.

The ChirpStack 4.9 Add Gateway form used by this lab does **not** expose a Region dropdown. Region selection for gateway MQTT processing comes from the server configuration (`enabled_regions = ["as923"]` plus the active `[[regions]]` definition), not from inventing a missing UI field.

Interpret the UI precisely:

```text
gateway absent from list       -> not registered
gateway present, Last seen: Never -> registered, but ChirpStack has not successfully processed a gateway event yet
```

ChirpStack does not auto-discover or auto-create a gateway merely because MQTT traffic arrives.

---

## 10. Complete the Physical Raspberry Pi Gateway

Do **not** point `chirpstack-mqtt-forwarder` directly at `ssl://<SERVER_VM_IP>:8883`. That bypasses the local persistent buffer required by this test architecture and contradicts the gateway verification manual.

At this point the server side must already have:

```text
Gateway EUI registered in ChirpStack
Gateway certificate + private key issued for that exact EUI
Broker CA certificate
Exact-EUI Mosquitto ACL
Server MQTT endpoint reachable on TCP 8883
```

Now continue on the Raspberry Pi in this exact order:

```text
test/preparation/gateway/04-configure-local-mqtt-buffer.md
  -> local Mosquitto on 127.0.0.1:1883
  -> separate uplink/state and downlink mTLS bridges to lora-test-server:8883 (or another SAN-matching server name)

test/preparation/gateway/05-configure-mqtt-forwarder.md
  -> MQTT Forwarder publishes Protobuf to 127.0.0.1:1883

test/preparation/gateway/06-verify-gateway-os.md
  -> prove local gateway event, remote broker delivery, and ChirpStack Last seen
```

The gateway does **not** auto-create itself in ChirpStack. Step B must already contain the exact Concentratord EUI. After Gateway 04-05 are complete, generate one real uplink and confirm the registered gateway's **Last seen** timestamp changes. If it does not, stop at the first failing hop in Gateway 06 instead of changing the EUI or adding a second gateway record.

---

## 11. Deploy Node-RED Telemetry Ingestion Pipeline

Start Node-RED:

```bash
docker compose up -d node-red
docker compose ps node-red
```

Node-RED connects inside Docker network to:
- **MQTT**: `tcp://mosquitto:1883` (User: `node_red`, Pass: `node_red_pass`)
- **PostgreSQL**: `telemetry-db:5432` (User: `telemetry_writer`, Pass: `writer_secret_pass`, Database: `lorawan_telemetry`)

Verify telemetry ingestion by checking PostgreSQL uplinks:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key, time, dev_eui, f_cnt FROM telemetry.uplinks ORDER BY time DESC LIMIT 5;"
```

---

## 12. Deploy & Initialize OpenBao KMS

### Write OpenBao Configuration

Create `/opt/lorawan-lab/configuration/openbao/openbao.hcl`:

```hcl
ui = true
api_addr     = "http://openbao:8200"
cluster_addr = "http://openbao:8201"

storage "file" {
  path = "/openbao/data"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}
```

Start OpenBao container:

```bash
docker compose up -d openbao
docker compose ps openbao
```

---

### Initialize & Unseal OpenBao KMS

Run this automated initialization script:

```bash
sudo install -d -m 0700 /root/lorawan-lab-openbao

# Initialize OpenBao
sudo sh -c '
docker compose exec -T -e BAO_ADDR=http://127.0.0.1:8200 openbao \
  bao operator init -key-shares=3 -key-threshold=2 -format=json \
  > /root/lorawan-lab-openbao/init.json
'

# Read Unseal Keys & Root Token
KEY1=$(sudo jq -r '.unseal_keys_b64[0]' /root/lorawan-lab-openbao/init.json)
KEY2=$(sudo jq -r '.unseal_keys_b64[1]' /root/lorawan-lab-openbao/init.json)
ROOT_TOKEN=$(sudo jq -r '.root_token' /root/lorawan-lab-openbao/init.json)

# Unseal OpenBao
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal "$KEY1"
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal "$KEY2"

# Enable Transit Engine & Create Evidence Key
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$ROOT_TOKEN" openbao bao secrets enable transit
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$ROOT_TOKEN" openbao \
  bao write transit/keys/lorawan-evidence type=ecdsa-p256 exportable=false

# Create AppRole for Fabric-Adapter
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$ROOT_TOKEN" openbao bao auth enable approle

docker compose exec -i -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$ROOT_TOKEN" openbao \
  bao policy write fabric-evidence-signer - <<'HCL'
path "transit/sign/lorawan-evidence/sha2-256" { capabilities = ["update"] }
path "transit/verify/lorawan-evidence/sha2-256" { capabilities = ["update"] }
HCL

docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$ROOT_TOKEN" openbao \
  bao write auth/approle/role/fabric-adapter token_policies=fabric-evidence-signer secret_id_ttl=0

# Save AppRole RoleID and SecretID to secrets folder
docker compose exec -T -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$ROOT_TOKEN" openbao \
  bao read -field=role_id auth/approle/role/fabric-adapter/role-id \
  > /opt/lorawan-lab/secrets/openbao-approle/role_id

docker compose exec -T -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$ROOT_TOKEN" openbao \
  bao write -f -field=secret_id auth/approle/role/fabric-adapter/secret-id \
  > /opt/lorawan-lab/secrets/openbao-approle/secret_id

chmod 600 /opt/lorawan-lab/secrets/openbao-approle/*
```

Verify OpenBao status:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status
```

---

## 13. Create Fabric Outbox Table & Deploy Fabric Adapter

### Create `telemetry.fabric_outbox` Table & Immutability Triggers

Run inside PostgreSQL:

```bash
docker compose exec -T telemetry-db psql -U telemetry_admin -d lorawan_telemetry << 'SQL'
-- 1. Create Outbox Table
CREATE TABLE IF NOT EXISTS telemetry.fabric_outbox (
    outbox_id             BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    event_key             TEXT NOT NULL UNIQUE,
    source_event_key      TEXT NOT NULL,
    observed_at           TIMESTAMPTZ NOT NULL,
    event_type            TEXT NOT NULL,
    schema_version        TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'pending',
    attempts              INTEGER NOT NULL DEFAULT 0,
    next_attempt_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    worker_id             TEXT,
    processing_started_at TIMESTAMPTZ,
    lease_expires_at      TIMESTAMPTZ,
    canonical_json        TEXT,
    digest_sha256         TEXT,
    evidence_signature_alg TEXT,
    evidence_signing_key_id TEXT,
    evidence_signature    TEXT,
    evidence_sealed_at    TIMESTAMPTZ,
    fabric_tx_id          TEXT,
    submitted_at          TIMESTAMPTZ,
    committed_at          TIMESTAMPTZ,
    last_error_category   TEXT,
    last_error            TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Immutability Trigger
CREATE OR REPLACE FUNCTION telemetry.enforce_fabric_outbox_immutability()
RETURNS trigger AS $$
BEGIN
  IF NEW.event_key IS DISTINCT FROM OLD.event_key OR NEW.source_event_key IS DISTINCT FROM OLD.source_event_key THEN
    RAISE EXCEPTION 'fabric outbox source identity is immutable';
  END IF;
  IF OLD.canonical_json IS NOT NULL AND NEW.canonical_json IS DISTINCT FROM OLD.canonical_json THEN
    RAISE EXCEPTION 'fabric outbox evidence seal is immutable';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS fabric_outbox_immutability_trg ON telemetry.fabric_outbox;
CREATE TRIGGER fabric_outbox_immutability_trg
BEFORE UPDATE ON telemetry.fabric_outbox
FOR EACH ROW EXECUTE FUNCTION telemetry.enforce_fabric_outbox_immutability();

-- 3. Create fabric_adapter role & grants
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='fabric_adapter') THEN
    CREATE ROLE fabric_adapter LOGIN PASSWORD 'adapter_secret_pass';
  END IF;
END
$$;

GRANT USAGE ON SCHEMA telemetry TO fabric_adapter;
GRANT SELECT, UPDATE ON telemetry.fabric_outbox TO fabric_adapter;
GRANT SELECT ON telemetry.uplinks, telemetry.measurements TO fabric_adapter;
SQL
```

---

### Start Fabric Adapter Service

```bash
docker compose up -d fabric-adapter
docker compose ps fabric-adapter
```

---

## 14. Stack Verification & Single-Command Daily Operations

Now that the initial setup is complete, verifying and operating the full 7-container stack is completely streamlined!

### Daily Operation Command (Option A)

To start, stop, or view status of all 7 containers simultaneously:

```bash
cd /opt/lorawan-lab

# Start all 7 services:
docker compose up -d

# Stop all 7 services:
docker compose stop

# Check status:
docker compose ps
```

---

### Verification Checklist Commands

Run to verify the 7-container stack health and system memory limits:

```bash
cd /opt/lorawan-lab

# 1. Verify 7 services are running
docker compose config --services

# 2. Check container status
docker compose ps

# 3. Check memory & CPU stats
free -h
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'

# 4. Check for any Linux Kernel OOM kills
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true
```

The service list must return exactly these 7 services:

```text
chirpstack
fabric-adapter
mosquitto
node-red
openbao
telemetry-db
valkey
```

### End-to-End Event Processing Flow

When an uplink packet is transmitted by EMU-01, the payload contains real physical Agriculture Kit sensor values plus deterministic packet-accounting markers and traverses the complete physical/application pipeline:

```text
RAK4631 EMU-01 (physical Agriculture Kit sensor payload v2 over real AS923 OTAA LoRaWAN RF)
  -> Gateway Packet Forwarder / Mosquitto Bridge (Port 8883 mTLS)
  -> Server Mosquitto Broker (Internal Port 1883)
  -> ChirpStack Network Server (LoRaWAN Frame Decoded)
  -> Node-RED Data Pipeline
  -> TimescaleDB (telemetry.uplinks & telemetry.measurements)
  -> Fabric Outbox (telemetry.fabric_outbox)
  -> OpenBao KMS (ECDSA-P256 HMAC Evidence Seal)
  -> Fabric Adapter (Ledger Transaction Commit)
```

Verify the latest ingested uplink in TimescaleDB:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key, time, dev_eui, f_cnt, rssi_dbm FROM telemetry.uplinks ORDER BY time DESC LIMIT 5;"
```

Your 7-container dissertation testbed is now fully operational. After the gateway has completed its final preparation, complete [Sensor Preparation](../sensor/00-README.md) and [Test Tools Preparation](../tools/00-README.md). Then start counted testing at [Execution 01 - Common Run Preparation](../../execution/01-common-run-preparation.md).
