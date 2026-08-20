# Server 10. Deploy ChirpStack Against PgBouncer and Valkey

## Goal

Run ChirpStack only after its database and cache dependencies are already healthy.

The required path is:

```text
ChirpStack
  -> pgbouncer:6432
  -> haproxy:5432
  -> current Spilo / Patroni PostgreSQL primary

ChirpStack
  -> valkey:6379

ChirpStack gateway backend
  -> mosquitto:1883 inside Docker
```

Do **not** add a standalone `postgres`, `redis`, or server-side Gateway Bridge container.

## Before you start

Run on the **lab server VM**:

```bash
cd /opt/lorawan-lab
. ./.env
docker compose ps etcd-1 etcd-2 etcd-3 spilo-1 spilo-2 spilo-3 haproxy pgbouncer mosquitto valkey
```

Verify the full SQL path:

```bash
docker run --rm --network lorawan-lab_application "$POSTGRES_CLIENT_IMAGE" \
  psql 'host=pgbouncer port=6432 dbname=chirpstack user=chirpstack sslmode=disable' \
  -c 'SELECT current_database(), inet_server_addr(), pg_is_in_recovery();'
```

Use protected password handling. `pg_is_in_recovery()` must be `false`.

Verify Valkey:

```bash
docker compose exec valkey valkey-cli ping
```

Expected: `PONG`.

## Step 1 - Obtain the pinned ChirpStack configuration template

Use the exact reviewed image rather than copying an old configuration blindly:

```bash
. ./.env
docker run --rm "$CHIRPSTACK_IMAGE" --version
docker run --rm "$CHIRPSTACK_IMAGE" configfile > /tmp/chirpstack.toml.example || true
```

If the pinned image uses a different configuration-template command, inspect its help and use that command.

Copy the reviewed template to:

```text
/opt/lorawan-lab/configuration/chirpstack/chirpstack.toml
```

Create the region directory:

```bash
mkdir -p /opt/lorawan-lab/configuration/chirpstack/regions
```

## Step 2 - Configure PostgreSQL through PgBouncer

In the pinned ChirpStack configuration, set the PostgreSQL DSN equivalent to:

```text
postgresql://chirpstack:<CHIRPSTACK_DB_PASSWORD>@pgbouncer:6432/chirpstack?sslmode=disable
```

The local Docker hops are internal lab traffic. Production follows the TLS controls in the cloud manuals.

Confirm no configuration contains `spilo-1`, `spilo-2`, `spilo-3`, or `haproxy` as ChirpStack's direct database host. ChirpStack must know only `pgbouncer:6432`.

## Step 3 - Configure Valkey

Use the exact keys supported by the pinned ChirpStack release. The effective endpoint must be:

```text
valkey:6379
```

Do not configure a separate Redis container for the lab.

## Step 4 - Configure the gateway MQTT backend

The gateway-facing broker is Mosquitto. Inside Docker, ChirpStack connects to the internal broker listener:

For ChirpStack v4 / 4.9, the active region file must use the v4 `[[regions]]` structure and explicitly enable the MQTT gateway backend. Keep all additional region/channel fields from the pinned template; the required shape includes:

```toml
[[regions]]
id="<CONFIRMED_REGION_ID>"

[regions.gateway.backend]
enabled="mqtt"

[regions.gateway.backend.mqtt]
topic_prefix="<CONFIRMED_REGION_TOPIC_PREFIX>"
server="tcp://mosquitto:1883"
client_id="chirpstack-lab"
```

The main ChirpStack config must enable the same region ID. Do not use the old singular `[region]` layout.

Use the same approved region topic prefix as Gateway OS:

```text
Region ID: <CONFIRMED_REGION_ID>
Topic prefix: <CONFIRMED_REGION_TOPIC_PREFIX>
```

Do not install a server-side ChirpStack Gateway Bridge. Gateway OS already uses Concentratord + MQTT Forwarder for delivery and sends the gateway topics through Mosquitto. The independent gateway integrity journal reads beside MQTT Forwarder and does not require Gateway Bridge.

## Step 5 - Create the ChirpStack broker identity

Create a broker password without printing it into documentation:

```bash
cd /opt/lorawan-lab
docker run --rm -it \
  -v "$PWD/configuration/mosquitto:/work" \
  "$MOSQUITTO_IMAGE" \
  mosquitto_passwd /work/passwd chirpstack
```

Add to `configuration/mosquitto/acl`:

```text
user chirpstack
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/event/#
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/state/#
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/command/#
topic write application/+/device/+/event/#
topic read application/+/device/+/command/#
```

Configure ChirpStack's internal broker username/password using the protected secret mechanism supported by the pinned version.

### Step 5A - Reserve a read-only gateway-event identity for the future evidence collector

Run this only when the reviewed gateway MQTT evidence collector implementation is ready to deploy. Do not create unused production credentials merely for documentation completeness.

Its broker ACL is:

```text
user gateway_evidence_collector
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/event/#
```

It receives **no write rule** for gateway event/state/command topics and no application-command permission. The collector observes what the remote broker actually received before ChirpStack application processing; it does not replace ChirpStack.

## Step 6 - Add ChirpStack to Compose

Example service shape:

```yaml
  chirpstack:
    image: ${CHIRPSTACK_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_CHIRPSTACK_CPUS}"
    mem_limit: "${LAB_CHIRPSTACK_MEM}"
    volumes:
      - ./configuration/chirpstack:/etc/chirpstack:ro
    ports:
      - "127.0.0.1:8080:8080"
    networks: [application]
    depends_on:
      - pgbouncer
      - mosquitto
      - valkey
```

Do not add `postgres`, `redis`, or `chirpstack-gateway-bridge` services.

## Step 7 - Validate the rendered project

```bash
docker compose config --quiet
docker compose config --services
```

Required services at this point include:

```text
etcd-1
etcd-2
etcd-3
spilo-1
spilo-2
spilo-3
haproxy
pgbouncer
mosquitto
valkey
chirpstack
```

Fail this step if a standalone `postgres`, `redis`, or Gateway Bridge service appears.

## Step 8 - Start ChirpStack

Before startup, inspect the bind-mounted ChirpStack config directory. Keep backup `.toml` files outside it so stale region files cannot be loaded accidentally:

```bash
cd /opt/lorawan-lab
mkdir -p config-backups/chirpstack
grep -RnsE '^\[region\]$|^\[\[regions\]\]$' configuration/chirpstack
find configuration/chirpstack -maxdepth 1 -type f -printf '%f\n' | sort
```

A `duplicate key region in document root` error is a configuration-directory problem until proven otherwise. Move `.bak`, `.old`, `.before-fix`, and obsolete region TOMLs outside `configuration/chirpstack/` before retrying.

```bash
docker compose restart mosquitto
docker compose up -d chirpstack
docker compose ps chirpstack
docker compose logs --since=10m --tail=300 chirpstack
```

Expected log evidence:

- PostgreSQL connection succeeds through PgBouncer;
- database migrations complete or report the expected current schema;
- Valkey connection succeeds;
- the approved region configuration loads;
- MQTT connection succeeds;
- no Gateway Bridge dependency appears.

## Step 9 - Open the UI through SSH

From the administration workstation:

```bash
ssh -L 8080:127.0.0.1:8080 <ADMIN_USER>@<SERVER_VM_IP_ADDRESS>
```

Open:

```text
http://127.0.0.1:8080
```

Change default credentials immediately if the pinned release starts with any.

## Verify

Run:

```bash
docker compose logs --since=5m --tail=200 chirpstack pgbouncer haproxy valkey mosquitto
docker compose exec spilo-1 patronictl list
```

Then stop the current Patroni leader and confirm ChirpStack recovers without changing its database configuration.

## Troubleshooting

### ChirpStack tries to connect to `postgres:5432`

The old example-stack configuration is still active. Replace it with `pgbouncer:6432` and verify no standalone PostgreSQL service exists.

### ChirpStack tries to connect to `redis:6379`

The old lab shortcut is still active. Configure the pinned release for `valkey:6379`.

### MQTT connects but no gateway events are consumed

Compare `<CONFIRMED_REGION_TOPIC_PREFIX>` in the ChirpStack region file and Gateway OS MQTT Forwarder.

## Next step

Continue with [11-secure-gateway-mqtt.md](11-secure-gateway-mqtt.md).
