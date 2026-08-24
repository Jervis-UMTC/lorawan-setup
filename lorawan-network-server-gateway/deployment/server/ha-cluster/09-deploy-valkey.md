# Server 9. Deploy Valkey

## Goal

Run the same cache technology used by the intended cloud architecture instead of keeping a lab-only Redis shortcut.

Valkey is a ChirpStack dependency. It is not the gateway outage buffer and it does not replace PostgreSQL backups.

## Step 1 - Create the configuration

Create `/opt/lorawan-lab/configuration/valkey/valkey.conf`:

```conf
bind 0.0.0.0
protected-mode yes
port 6379
appendonly yes
maxmemory 160mb
maxmemory-policy noeviction
save 900 1
save 300 10
save 60 10000
```

The service is not published to the VM host, so only containers on the application network can reach it. `maxmemory 160mb` leaves room inside the 256 MiB container limit for Valkey process overhead and persistence work. `noeviction` is deliberate: if the lab exceeds this small cache budget, fail visibly instead of silently evicting session data.

For a production cloud deployment, follow the TLS/authentication and managed-service requirements in [cloud/08-mqtt-and-valkey.md](../cloud-production/08-mqtt-and-valkey.md).

## Step 2 - Add Valkey to Compose

```yaml
  valkey:
    image: ${VALKEY_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_VALKEY_CPUS}"
    mem_limit: "${LAB_VALKEY_MEM}"
    command: ["valkey-server", "/etc/valkey/valkey.conf"]
    volumes:
      - ./configuration/valkey/valkey.conf:/etc/valkey/valkey.conf:ro
      - valkey-data:/data
    networks: [application]
```

Confirm the selected image uses the shown binary and config path before starting. Adjust only to the pinned image's documented paths.

## Step 3 - Start Valkey

```bash
cd /opt/lorawan-lab
docker compose config --quiet
docker compose up -d valkey
docker compose ps valkey
docker compose logs --since=5m --tail=100 valkey
```

## Step 4 - Verify

```bash
docker compose exec valkey valkey-cli ping
docker compose exec valkey valkey-cli INFO server | head -30
```

Expected:

```text
PONG
```

Confirm there is no host listener:

```bash
sudo ss -lntp | grep ':6379' || true
```

Expected: no host-published Valkey listener.

## Troubleshooting

If the image uses `redis-cli` for compatibility rather than `valkey-cli`, use the CLI provided by that pinned image. Do not expose port `6379` to work around Docker DNS or network problems.

## Next step

Continue with [10-deploy-chirpstack.md](10-deploy-chirpstack.md).
