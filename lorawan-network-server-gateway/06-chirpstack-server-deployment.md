# 6. Deploying the ChirpStack Server (Docker Compose)

This uses ChirpStack's own official Compose skeleton rather than a hand-written one — it stays current with whatever the ChirpStack project actually ships, which matters since the config file format has changed across releases before.

## Step 1: Clone the official repo

```bash
cd ~
git clone https://github.com/chirpstack/chirpstack-docker.git
cd chirpstack-docker
```

This gives you:

```
chirpstack-docker/
├── docker-compose.yml
└── configuration/
    ├── chirpstack/                 # chirpstack.toml — core LNS + app-server config, region list
    ├── chirpstack-gateway-bridge/  # UDP↔MQTT bridge config
    ├── mosquitto/                  # MQTT broker config
    └── postgresql/initdb/          # DB init scripts
```

The stack (as of writing) runs: `chirpstack` (the core network + application server, port 8080), `chirpstack-gateway-bridge` (UDP port 1700), `chirpstack-rest-api` (port 8090, optional REST wrapper over the gRPC API), `postgres`, `redis`, and `mosquitto`. All of ChirpStack's own images publish `arm64` builds, so nothing here needs architecture-specific substitution.

## Step 2: Set your region

The repo ships pre-configured to support all LoRaWAN regions in the core server, but the one `chirpstack-gateway-bridge` service it defines out of the box is wired to the **EU868** MQTT topic prefix. Since we're targeting AS923-3, that needs to change.

Open `docker-compose.yml` and find the `chirpstack-gateway-bridge` service's environment block — it'll look like:

```yaml
environment:
  - INTEGRATION__MQTT__EVENT_TOPIC_TEMPLATE=eu868/gateway/{{ .GatewayID }}/event/{{ .EventType }}
  - INTEGRATION__MQTT__STATE_TOPIC_TEMPLATE=eu868/gateway/{{ .GatewayID }}/state/{{ .StateType }}
  - INTEGRATION__MQTT__COMMAND_TOPIC_TEMPLATE=eu868/gateway/{{ .GatewayID }}/command/#
```

Change the `eu868` prefix in all three lines to `as923_3` (or whichever region ID matches your actual frequency plan — see below if you're unsure of the exact spelling):

```yaml
environment:
  - INTEGRATION__MQTT__EVENT_TOPIC_TEMPLATE=as923_3/gateway/{{ .GatewayID }}/event/{{ .EventType }}
  - INTEGRATION__MQTT__STATE_TOPIC_TEMPLATE=as923_3/gateway/{{ .GatewayID }}/state/{{ .StateType }}
  - INTEGRATION__MQTT__COMMAND_TOPIC_TEMPLATE=as923_3/gateway/{{ .GatewayID }}/command/#
```

Then open `configuration/chirpstack/chirpstack.toml` and check the `enabled_regions` list, plus the individual `[[region]]` blocks further down the file. Confirm there's a block for AS923-3 and note the exact `id` string it uses (copy it verbatim — don't retype it) — that's the value that must match what you just put in the Gateway Bridge's topic templates above. If AS923-3 isn't in `enabled_regions`, add its id to that list, following the pattern of the entries already there.

> Not sure AS923-3 is right for you? It's the LoRa Alliance-designated plan for the Philippines and a few other countries, but confirm against current guidance from your national regulator if precision matters for your deployment — this is one config change in one file if it turns out to be a different variant.

## Step 3: Start the stack

```bash
docker compose up -d
```

First start will take a minute or two — Postgres has to initialize its data directory, and images need to be pulled.

## Step 4: Verify everything is up

```bash
docker compose ps
```

All services should show as `running` or `healthy`. If something is restarting in a loop:

```bash
docker compose logs -f chirpstack
```

(swap the service name to check others — `chirpstack-gateway-bridge`, `postgres`, `mosquitto`, etc.)

## Step 5: Log in

Open `http://<pi-ip-or-hostname>:8080` from a browser on the same network.

Default credentials: **admin / admin**

**Change this password immediately** — Login → user menu → change password. This is a network server with an open port on your LAN; leaving default credentials in place even briefly is the kind of thing that's easy to forget about later.

---
Next: [07-connect-gateway-to-chirpstack.md](07-connect-gateway-to-chirpstack.md)
