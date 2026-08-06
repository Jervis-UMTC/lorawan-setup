# 10. Troubleshooting

Organized by symptom. Cross-references point back to the step where the underlying config lives.

## Concentrator won't start / chip version reads `0x00`

A `0x00` (or otherwise implausible) chip version means the Pi is talking over SPI but the RAK5146 isn't actually responding — the concentrator itself was never detected.

- **Check the HAT is fully seated** on the 40-pin header, straight and pressed all the way down. This is the single most common cause.
- **Confirm the antenna is connected.** Some concentrator firmware/hardware behaves erratically or refuses to initialize properly without a load on the RF path — and running it unterminated risks damaging it besides.
- **Confirm you selected the right model during install** ([04](04-lora-concentrator-setup.md), Step 2) — RAK5146 (SX1303) and the older RAK2287 (SX1302) use different option numbers in the installer, and picking the wrong one will build the wrong HAL.
- **Reseat and retry** — SPI is sensitive to poor mechanical contact in a way that often doesn't show up as an obvious "loose connector" symptom.

## `reset_lgw.sh` errors: `I/O error`, `cannot create /sys/class/gpio/gpioNN/...`

This is the known Bookworm/Trixie kernel incompatibility covered in [04-lora-concentrator-setup.md](04-lora-concentrator-setup.md), Step 5 — the legacy sysfs GPIO interface these scripts were written against no longer exists on current kernels. Apply the libgpiod v2 patch there. If sysfs paths remain in the log afterward, double-check that you patched `/opt/ttn-gateway/packet_forwarder/lora_pkt_fwd/reset_lgw.sh` and `start.sh`, not similarly named files elsewhere.

## `gpioset: invalid line value: 'gpiochip0'`

The script is calling libgpiod v2 with the old v1 positional syntax, such as `gpioset gpiochip0 17=0`. On Bookworm/Trixie, use `gpioset --chip gpiochip0 17=0` instead. Apply Step 5 of [04-lora-concentrator-setup.md](04-lora-concentrator-setup.md), which patches the actual `GPIO_CHIP` / `RESET_GPIO` script variables without hard-coding a new reset pin.

## Service stays `active` but never starts the packet forwarder

`ttn-gateway.service` uses `Restart=always`, so an `active` status can be misleading. There are two checks:

- Healthy: the cgroup contains `./lora_pkt_fwd`, and the log says `Reset sequence completed` followed by normal packet-forwarder startup.
- Not healthy: the cgroup contains only `start.sh` and a long-running `gpioset --chip gpiochip0 ...` process. libgpiod v2 holds a line by default, which blocks the next line of the reset script indefinitely.

Step 5 in [04-lora-concentrator-setup.md](04-lora-concentrator-setup.md) adds `--hold-period 100ms --toggle 0` to each reset pulse so `gpioset` exits. Do not use a bare `gpioset --chip ...` call in these scripts.

## `sx1261_com_open` / `failed to connect to the sx1261 radio (LBT/Spectral Scan)`

The chosen RAK regional template has enabled spectral scan and LBT under `sx1261_conf`, but this RAK5146 SPI installation has no usable SX1261 SPI connection. A typical log sequence is:

```
SX1261 spi_path is not configured in global_conf.json
Spectral Scan with SX1261 is enabled
Listen-Before-Talk with SX1261 is enabled
ERROR: sx1261_com_open: Failed to connect to sx1261 radio
```

For the Philippines AS923-3 configuration in this guide, disable both `spectral_scan.enable` and `lbt.enable` as documented in [04](04-lora-concentrator-setup.md), Step 9. Do not disable LBT on hardware/regions that require and support it; confirm the local regulatory requirement first.

## Gateway never shows up as "seen" in ChirpStack / Gateway Bridge logs show nothing

Work through these roughly in order of how often each turns out to be the culprit:

1. **Region/topic-prefix mismatch.** The prefix in `chirpstack-gateway-bridge`'s three `INTEGRATION__MQTT__*_TOPIC_TEMPLATE` environment variables ([06](06-chirpstack-server-deployment.md)) must exactly match the region `id` string used in `chirpstack.toml`. A leftover `eu868` in one place and `as923_3` in another means the bridge and core server are publishing/subscribing to completely different MQTT topics and will never see each other, with no obvious error anywhere.
2. **Packet forwarder isn't actually running.** `pgrep -af '[l]ora_pkt_fwd'` — if it prints nothing, check `sudo systemctl status ttn-gateway --no-pager -l` and the last 100 service log lines. Do not assume a running `start.sh` wrapper means the concentrator succeeded.
3. **The local override is incomplete.** Check `local_conf.json` ([07](07-connect-gateway-to-chirpstack.md)). It needs `gateway_ID`, `server_address: "127.0.0.1"`, `serv_port_up: 1700`, and `serv_port_down: 1700` under `gateway_conf`. If the startup log still says `eu1.cloud.thethings.network`, the packet forwarder is using the regional template's default rather than local ChirpStack.
4. **Port 1700 conflict or local firewall block.** `sudo ss -ulnp | grep 1700` should show the Gateway Bridge container's process listening. If `ufw` is already enabled at this point in your setup, confirm you haven't accidentally blocked loopback traffic (you shouldn't have, by default, but it's worth ruling out).
5. **Gateway ID typo when registering in the UI.** ChirpStack expects the EUI as lowercase hex with no separators — double-check against exactly what's in `local_conf.json`.

## `docker compose up` fails to pull images, or containers exit immediately with an architecture-related error

```bash
docker info | grep -i architecture
```

Should read `aarch64`. If it doesn't, you're running a 32-bit OS — go back to [02-flash-raspberry-pi-os.md](02-flash-raspberry-pi-os.md) and reflash with the 64-bit image; there's no good workaround for this short of that.

## Docker APT update returns `404 Not Found` for `linux/raspbian trixie`

The Docker Raspbian repository does not publish a `trixie` suite. This is a repository-selection problem, not a broken Pi installation. Do not run `apt-secure` — it is not a command.

Replace the repository URL with Docker's Debian repository:

```bash
sudo sed -i 's#https://download.docker.com/linux/raspbian#https://download.docker.com/linux/debian#' /etc/apt/sources.list.d/docker.list
```

```bash
sudo apt update
```

If the key was created as `/etc/apt/keyrings/docker.gpg`, the existing key can continue to be used. For a clean new installation, follow the Debian-based repository commands in [05-docker-installation.md](05-docker-installation.md), which use `/etc/apt/keyrings/docker.asc` and the Debian repository.

The expected source for a Trixie arm64 Pi is equivalent to:

```text
deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian trixie stable
```

## PostgreSQL / ChirpStack container stuck restarting after first `docker compose up`

Often just needs more time on a Pi 4's SD card I/O — Postgres has to initialize its data directory on the very first start. Give it a couple of minutes and check again:

```bash
docker compose logs postgres
docker compose logs chirpstack
```

If it's genuinely stuck (not just slow), a Pi running low on RAM under the combined load of the packet forwarder plus the full container stack is a common cause on 2 GB boards — see the swap setup in [03-system-preparation.md](03-system-preparation.md), and consider it a sign you're near this board's practical ceiling for this workload.

## Web UI (port 8080) not reachable from your browser

- `docker compose ps` — confirm the `chirpstack` container is actually `running`/`healthy`.
- Confirm you're using the Pi's current IP/hostname — if you set a static IP in [03](03-system-preparation.md) after already having connected once, your bookmark/history might have the old address.
- If you enabled `ufw` in [09](09-autostart-persistence-hardening.md), confirm the `8080/tcp` rule is actually present: `sudo ufw status`.

## Device joins but data looks garbled, or never joins at all

- **Never joins**: almost always a wrong AppKey, wrong DevEUI, or a region/channel-plan mismatch between what the device firmware expects and what you configured in the device profile.
- **Garbled payload**: this is normal at the LoRaWAN layer — ChirpStack decrypts the frame but doesn't know your application's payload format. You need a payload codec (JavaScript function) on the device profile or application to turn raw bytes into meaningful fields, matched to whatever encoding your specific end device uses. Check its datasheet/firmware documentation for the payload format.

## Still stuck

Two of the best places to search for anything specific to this exact hardware combination:
- The [RAKwireless community forum](https://forum.rakwireless.com/) — search for your exact error text; the GPIO fix in this guide came directly from a real thread there.
- The [ChirpStack community forum](https://forum.chirpstack.io/) — more useful for anything on the network-server side once the gateway is successfully delivering packets.
