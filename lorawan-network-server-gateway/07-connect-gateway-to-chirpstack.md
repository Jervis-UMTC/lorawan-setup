# 7. Connecting the Concentrator to ChirpStack

At this point you have two things running independently on the same Pi: the native packet forwarder (from [04](04-lora-concentrator-setup.md)) and the Dockerized ChirpStack stack (from [06](06-chirpstack-server-deployment.md)). This step wires them together.

## Step 1: Point the packet forwarder at the local Gateway Bridge

The packet forwarder needs to send UDP traffic to the Gateway Bridge container, which is listening on port 1700 on the Pi itself (published straight through to the host by the `1700:1700/udp` line in `docker-compose.yml`).

```bash
sudo nano /opt/ttn-gateway/packet_forwarder/lora_pkt_fwd/local_conf.json
```

After a fresh RAK installer run, this file may contain only the Gateway EUI:

```json
{
    "gateway_conf": {
        "gateway_ID": "2CCF67FFFE0ABEE3"
    }
}
```

That is not enough for the self-hosted ChirpStack setup. Expand the `gateway_conf` section and confirm/set **all four** fields:

```json
{
    "gateway_conf": {
        "gateway_ID": "2CCF67FFFE0ABEE3",
        "server_address": "127.0.0.1",
        "serv_port_up": 1700,
        "serv_port_down": 1700
    }
}
```

Since the concentrator and Gateway Bridge are on the same machine, `"127.0.0.1"` is correct — you don't need the Pi's LAN IP here. Leave `gateway_ID` as whatever was already there (it should match the EUI you noted in [04](04-lora-concentrator-setup.md)).

> [!TIP]
> When editing with `nano`, save changes by pressing `Ctrl + O`, hit `Enter`, and exit with `Ctrl + X`. Make sure valid JSON syntax is maintained (commas after every line inside the `gateway_conf` object except the last one).

Do not assume that a `gateway_ID` alone is enough. The regional `global_conf.json` templates commonly retain `server_address: "eu1.cloud.thethings.network"`; if `local_conf.json` does not explicitly contain `server_address`, `serv_port_up`, and `serv_port_down`, the packet forwarder will use that external address instead of ChirpStack. `local_conf.json` values take priority, so it is safer to put the local override there than to rely on or edit a template default.

## Step 2: Restart the packet forwarder

```bash
sudo systemctl restart ttn-gateway
```

```bash
sleep 5
```

```bash
sudo journalctl -u ttn-gateway -n 100 --no-pager
```

After the log says `found configuration file local_conf.json`, it must report `server hostname or IP address is configured to "127.0.0.1"` and both UDP ports as `1700`. If it still reports `eu1.cloud.thethings.network`, the three local override fields are missing, malformed, or outside `gateway_conf`.

## Step 3: Confirm traffic is arriving at the Gateway Bridge

```bash
cd ~/chirpstack-docker
docker compose logs -f chirpstack-gateway-bridge
```

Within a few seconds to a minute (packet forwarders typically send a stats/keepalive packet every 30 seconds), you should see log lines referencing your gateway's EUI. If you see nothing at all, jump to [10-troubleshooting.md](10-troubleshooting.md) — this is the most common place things stall, and it's almost always the region/topic-prefix mismatch from [06](06-chirpstack-server-deployment.md), a firewall blocking UDP 1700 locally, or the packet forwarder not actually running.

## Step 4: Register the gateway in the ChirpStack web UI

1. Log into `http://<pi-ip>:8080`.
2. If you don't already have a tenant, create one (**Tenants → Add tenant**). A single-user home/lab setup can just use one tenant for everything.
3. Go to **Gateways → Add**.
4. Enter:
   - **Gateway ID**: the EUI you noted in [04](04-lora-concentrator-setup.md), e.g. `ac1f09fffe123456` (lowercase, no colons, as ChirpStack expects it)
   - **Name**: whatever's meaningful to you
   - **Region**: select the AS923-3 (or your actual) region — must match what you configured in `chirpstack.toml`
5. Save.

## Step 5: Confirm it's actually online

Give it a minute, then reload the gateway's detail page. You're looking for:
- A recent **Last seen at** timestamp
- Stats data starting to populate (uplink/downlink counters, even if both are zero so far — zero-but-updating means the link is alive)

If "Last seen" stays blank, the gateway isn't reaching ChirpStack yet — back to Step 3's log check.

---
Next: [08-first-device-and-test-uplink.md](08-first-device-and-test-uplink.md)
