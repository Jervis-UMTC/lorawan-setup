# Server 8. Deploy Mosquitto

## Goal

Deploy the remote MQTT broker used by the physical gateways and ChirpStack.

At this stage start Mosquitto with a temporary loopback-only or Compose-internal listener for service validation. The gateway-facing TCP `8883` mutual-TLS listener is configured in [11-secure-gateway-mqtt.md](11-secure-gateway-mqtt.md).

## Step 1 - Create broker directories

Run on the **lab server VM**:

```bash
cd /opt/lorawan-lab
mkdir -p configuration/mosquitto/{certs,conf.d}
chmod 750 configuration/mosquitto configuration/mosquitto/certs
```

## Step 2 - Create the initial broker configuration

Create `configuration/mosquitto/mosquitto.conf`:

```conf
persistence true
persistence_location /mosquitto/data/
log_dest stdout

listener 1883
protocol mqtt
allow_anonymous false
password_file /mosquitto/config/passwd
acl_file /mosquitto/config/acl
```

Create the password and ACL files:

```bash
touch configuration/mosquitto/passwd configuration/mosquitto/acl
chmod 640 configuration/mosquitto/passwd configuration/mosquitto/acl
```

The broker's internal `1883` listener is reachable only through the Docker application network because no host port is published.

## Step 3 - Add Mosquitto to Compose

```yaml
  mosquitto:
    image: ${MOSQUITTO_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_MOSQUITTO_CPUS}"
    mem_limit: "${LAB_MOSQUITTO_MEM}"
    volumes:
      - ./configuration/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - ./configuration/mosquitto/passwd:/mosquitto/config/passwd:ro
      - ./configuration/mosquitto/acl:/mosquitto/config/acl:ro
      - ./configuration/mosquitto/certs:/mosquitto/config/certs:ro
      - mosquitto-data:/mosquitto/data
    networks: [application]
```

Do not publish port `1883`.

## Step 4 - Start and inspect

```bash
docker compose config --quiet
docker compose up -d mosquitto
docker compose ps mosquitto
docker compose logs --since=5m --tail=100 mosquitto
```

## Verify

```bash
docker compose exec mosquitto sh -c 'test -d /mosquitto/data && test -r /mosquitto/config/mosquitto.conf'
```

Do not connect the physical gateway yet. Complete ChirpStack and then replace the gateway-facing listener with mTLS in manual 11.

## Next step

Continue with [09-deploy-valkey.md](09-deploy-valkey.md).
