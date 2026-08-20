# Data 2. Deploy Node-RED and Store Uplinks

Node-RED subscribes to ChirpStack application events, validates and normalizes them, and writes telemetry plus any Fabric outbox job in one database transaction. It is the operational application processor, not the gateway-evidence verifier.

## Step 1: Add a broker identity for Node-RED

On the application-server VM, first check whether the identity already exists:

```bash
cd /opt/lorawan-lab
grep -q '^node_red:' configuration/mosquitto/passwd \
  && echo 'node_red already exists' \
  || docker run --rm -it \
       -v "$PWD/configuration/mosquitto:/work" \
       "$MOSQUITTO_IMAGE" \
       mosquitto_passwd /work/passwd node_red
```

Do not rotate an existing password accidentally. Rotate it only when the Node-RED credential is updated in the same maintenance window.

Confirm the active ChirpStack application event topic. The ACL below matches the documented default:

```bash
grep -RniE 'event_topic|command_topic' configuration 2>/dev/null
```

Add to the Mosquitto ACL:

```text
user node_red
topic read application/+/device/+/event/up
```

The `chirpstack` broker identity must be allowed to publish the corresponding application event topic. Do not give Node-RED `#` access or gateway-command permission.

Restart and inspect the broker:

```bash
docker compose restart mosquitto chirpstack
docker compose logs --since=5m --tail=100 mosquitto chirpstack
```

## Step 2: Add protected Node-RED variables

Add to `.env`:

```dotenv
NODE_RED_CREDENTIAL_SECRET=<REPLACE_WITH_64_HEX_CHAR_SECRET>
LORAWAN_REGION_ID=<CONFIRMED_CHIRPSTACK_REGION_ID>
```

Generate the credential secret with `openssl rand -hex 32` only when creating a new Node-RED credential store. Keep `.env` mode `600`. Do not rotate this value independently after `flows_cred.json` contains encrypted credentials; back up the Node-RED volume and follow a controlled credential re-entry procedure.

## Step 3: Add Node-RED to Compose

```yaml
  node-red:
    image: ${NODE_RED_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_NODE_RED_CPUS}"
    mem_limit: "${LAB_NODE_RED_MEM}"
    ports:
      - "127.0.0.1:1880:1880"
    environment:
      TZ: Asia/Manila
      NODE_RED_CREDENTIAL_SECRET: ${NODE_RED_CREDENTIAL_SECRET}
      LORAWAN_REGION_ID: ${LORAWAN_REGION_ID}
    volumes:
      - node-red-data:/data
    depends_on:
      telemetry-db:
        condition: service_healthy
      mosquitto:
        condition: service_started
    networks: [application, telemetry]
```

Confirm the top-level `node-red-data` volume already declared in [Server 2](../ha-cluster/02-docker-topology-and-network.md). Do not add a second top-level `volumes:` key.

Do not mount the Docker socket, host root filesystem, Fabric private keys, or ChirpStack configuration into Node-RED.

## Step 4: Start and secure the editor

```bash
docker compose config --quiet
docker compose up -d node-red
docker compose ps node-red
sudo ss -lntp | grep ':1880'
```

Follow [`server/integrations/node-red/01-deploy-node-red.md`](../integrations/node-red/01-deploy-node-red.md) to set `credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET` and enable `adminAuth` with a bcrypt password hash. Verify the environment variable is non-empty, `/auth/login` reports credential authentication, and an unauthenticated `/flows` request is rejected.

Use an SSH tunnel from the operator workstation:

```bash
ssh -L 1880:127.0.0.1:1880 <SERVER_USER>@<LAB_SERVER_IP_ADDRESS>
```

## Step 5: Configure MQTT and PostgreSQL

Follow [`server/integrations/node-red/02-configure-mqtt-and-postgresql.md`](../integrations/node-red/02-configure-mqtt-and-postgresql.md), with these lab values:

```text
MQTT host: mosquitto
MQTT port: 1883
MQTT user: node_red
MQTT topic: application/+/device/+/event/up
PostgreSQL host: telemetry-db
Database: lorawan_telemetry
Role: telemetry_writer
```

Inside the Compose network, plain MQTT and PostgreSQL are accepted because the traffic does not leave the isolated container network. Do not publish either port to the host.

## Step 6: Build the telemetry flow

Follow [`server/integrations/node-red/03-build-telemetry-flow.md`](../integrations/node-red/03-build-telemetry-flow.md).

Deploy in this order:

```text
mqtt in -> json -> validated debug
mqtt in -> json -> validation function -> parameterized PostgreSQL insert
PostgreSQL insert -> sanitized success and error paths
```

Do not add Fabric submission or gateway-verification authority to the Node-RED flow. The flow only creates a durable outbox job for selected events; the adapter submits it later. For v2, the independent verifier described under [Gateway Integrity](../integrations/gateway-integrity/00-README.md) must separately compare the accepted raw application bytes with its pinned trusted decoder and the stored normalized values before the outbox row becomes seal-eligible.

## Step 7: Verify one real event

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,dev_eui,device_name,region FROM telemetry.uplinks ORDER BY time DESC LIMIT 10;"
```

Replay the same sanitized event once. Its unique event count must remain one.

This proves Node-RED application storage only. Do not describe the row as gateway-verified until the separate v2 evidence lineage is installed and reports `verified`.
