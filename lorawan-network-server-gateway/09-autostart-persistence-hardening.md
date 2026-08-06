# 9. Making It Survive a Reboot (and Keeping It Healthy)

A gateway that only works until the next power cycle isn't very useful. This covers what needs to be true for the whole stack to come back up unattended, plus baseline hardening now that there are open ports on your LAN.

## Step 1: Confirm the packet forwarder starts on boot

`rak_common_for_gateway`'s installer sets this up automatically as part of installation in [04](04-lora-concentrator-setup.md). Confirm after a real reboot rather than assuming:

```bash
sudo reboot
```

Wait for it to come back, reconnect via SSH, then:

```bash
ps aux | grep lora_pkt_fwd
```

If it's not running, check `sudo gateway-config` for a manual start, and look at whatever service/init mechanism the installer used on your system to make it persistent — this varies slightly by OS release, which is one more reason to verify directly rather than assume.

## Step 2: Confirm Docker and the ChirpStack containers start on boot

You already enabled the Docker daemon itself in [05](05-docker-installation.md):

```bash
sudo systemctl is-enabled docker
```

Should return `enabled`. The containers themselves come back up via the `restart: unless-stopped` policy already set in ChirpStack's `docker-compose.yml` — Docker will restart them automatically whenever the daemon starts, as long as they weren't manually stopped before the last shutdown. Verify after the same reboot as Step 1:

```bash
cd ~/chirpstack-docker
docker compose ps
```

## Step 3: Back up what actually matters

The two things worth protecting: the PostgreSQL data (your tenants/applications/devices/keys) and your edited config files.

```bash
# Database dump
docker compose exec postgres pg_dump -U chirpstack chirpstack > ~/chirpstack-backup-$(date +%Y%m%d).sql

# Config files (small, and where you made all your manual edits)
tar -czf ~/chirpstack-config-backup-$(date +%Y%m%d).tar.gz -C ~/chirpstack-docker configuration docker-compose.yml
```

Copy these off the Pi somewhere else periodically — an SD card is not a backup medium you want to rely on for the only copy of anything.

## Step 4: Firewall

```bash
sudo apt install -y ufw
sudo ufw allow ssh
sudo ufw allow 8080/tcp comment 'ChirpStack web UI'
sudo ufw enable
```

Deliberately **not** opening 1700/udp externally — the packet forwarder talks to the Gateway Bridge over `localhost`, so that port never needs to be reachable from outside the Pi itself. If you later add remote gateways reporting to this same ChirpStack instance, you'd open 1700/udp then, and only then.

If you want the web UI reachable only from your own LAN and not from anywhere your router might expose it, double check your router isn't port-forwarding 8080 — `ufw` only controls the Pi's own firewall, not your router.

## Step 5: A few more password/access basics

- Confirm you changed the ChirpStack `admin/admin` default (from [06](06-chirpstack-server-deployment.md)) — worth double-checking here since it's easy to skip in the moment.
- If you're comfortable with it, disable SSH password auth in favor of keys only (`/etc/ssh/sshd_config`, `PasswordAuthentication no`, then `sudo systemctl restart ssh`) — do this only after confirming key-based login already works, or you'll lock yourself out.

## Step 6: Keeping things updated

```bash
# OS packages
sudo apt update && sudo apt full-upgrade -y

# ChirpStack stack
cd ~/chirpstack-docker
docker compose pull
docker compose up -d
```

Read ChirpStack's release notes before pulling a new major/minor version in production — there have been schema and config-format changes across releases historically, and jumping straight to `latest` without reading anything is how you end up debugging a broken login page at an inconvenient time. Pinning to a specific tag (e.g. `chirpstack/chirpstack:4.19` instead of the floating `:4`) once your setup is stable gives you control over exactly when upgrades happen.

---
Next: [10-troubleshooting.md](10-troubleshooting.md)
