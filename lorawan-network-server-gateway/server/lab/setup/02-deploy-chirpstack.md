# Server 2. Deploy ChirpStack for Gateway OS MQTT

Run this guide on the application VM.

The gateway's local persistent Mosquitto bridge connects to the remote broker. Do not deploy a server-side ChirpStack Gateway Bridge.

```text
Gateway OS MQTT Forwarder
  -> local persistent Mosquitto
  -> MQTT over mutual TLS
  -> remote Mosquitto
  -> ChirpStack region MQTT backend
```

## Step 1: Select a repeatable deployment source

Choose a reviewed 40-character commit from the ChirpStack Docker repository and resolve the exact image references used by that revision:

```text
ChirpStack Docker repository commit: <REVIEWED_CHIRPSTACK_DOCKER_COMMIT>
ChirpStack image and digest:
Mosquitto image and digest:
PostgreSQL image and digest:
Redis image and digest:
Enabled ChirpStack region IDs:
```

Keep these values with the Compose backup because they identify a compatible rebuild and rollback state. `<REVIEWED_CHIRPSTACK_DOCKER_COMMIT>` comes from the repository revision selected after review; do not use a shortened or moving branch name for a repeatable deployment.

## Step 2: Inspect the selected Compose revision

```bash
cd /opt/chirpstack-docker
git rev-parse HEAD
git status --short
docker compose config --services
docker compose config --images
find configuration -maxdepth 3 -type f -print | sort
```

Identify:

- the ChirpStack service;
- Mosquitto;
- PostgreSQL and Redis;
- active region files;
- certificate mount paths;
- any Gateway Bridge services inherited from the example.

## Step 3: Remove the server-side Gateway Bridge path

Gateway OS already runs MQTT Forwarder. Disable or remove all `chirpstack-gateway-bridge` services from the active Compose configuration.

Validate:

```bash
if docker compose config --services | grep -qi gateway-bridge; then
  echo 'Unexpected Gateway Bridge service remains' >&2
  exit 1
fi
```

No Gateway Bridge container is required for this architecture.

## Step 4: Configure the active ChirpStack region

Open the exact active region configuration and verify its gateway MQTT backend.

The required settings are equivalent to:

```toml
[regions.gateway.backend.mqtt]
server="ssl://mosquitto:8883"
client_id="chirpstack-<APP_NODE_NAME>"
ca_cert="/etc/chirpstack/certs/mqtt-ca.crt"
tls_cert="/etc/chirpstack/certs/chirpstack.crt"
tls_key="/etc/chirpstack/certs/chirpstack.key"
```

The private key format must match the pinned ChirpStack version. Current ChirpStack configuration documentation expects the gateway-backend MQTT TLS key in PKCS#8 form.

Verify the region topic prefix in the same file:

```text
Region ID: <CONFIRMED_REGION_ID>
Topic prefix: <CONFIRMED_REGION_TOPIC_PREFIX>
```

`<CONFIRMED_REGION_ID>` is the ChirpStack region file selected for the legal channel plan. `<CONFIRMED_REGION_TOPIC_PREFIX>` is the topic namespace from that file and must match Gateway OS MQTT Forwarder exactly. A mismatch produces broker traffic that ChirpStack does not consume even when TLS succeeds.

## Step 5: Configure application MQTT integration

When Node-RED or another approved integration consumes application events, configure the ChirpStack MQTT integration to use the same broker with its own client connection and approved certificate identity.

Do not grant gateway certificates access to application topics.

## Step 6: Mount certificates read-only

Mount only the runtime files required by ChirpStack:

```text
mqtt-ca.crt
chirpstack.crt
chirpstack.key
```

Do not mount the MQTT CA private key.

Resolve the container user from the pinned image before setting ownership:

```bash
docker image inspect <PINNED_CHIRPSTACK_IMAGE> \
  --format '{{json .Config.User}}'
```

Make the private key readable only by the effective ChirpStack process identity.

## Step 7: Validate and start

```bash
docker compose config --quiet
docker compose up -d mosquitto redis postgres chirpstack
docker compose ps
docker compose logs --since=5m --tail=300 mosquitto chirpstack
```

Healthy evidence:

- no Gateway Bridge container is running;
- Mosquitto starts its TLS listener;
- ChirpStack validates the broker certificate;
- Mosquitto accepts the `chirpstack` client certificate;
- enabled regions and topic prefixes load without error;
- PostgreSQL and Redis are healthy according to application-level checks.

If ChirpStack cannot connect, check the mounted CA/client files, private-key format and permissions, broker hostname, region file, and topic prefix before changing the gateway. If Compose still renders a Gateway Bridge service, remove it from the active configuration rather than leaving an unused parallel path.

Continue with [03-secure-gateway-mqtt.md](03-secure-gateway-mqtt.md).
