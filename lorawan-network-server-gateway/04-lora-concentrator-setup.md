# 4. RAK5146 Concentrator & Packet Forwarder Setup

This installs RAK's own driver/installer package, which builds the SX1303 HAL and sets up the classic Semtech-style UDP packet forwarder as a native process. It runs outside Docker deliberately — it needs direct SPI and GPIO access, which containers complicate for no real benefit here.

## Step 1: Get the installer

```bash
cd ~
git clone https://github.com/RAKWireless/rak_common_for_gateway.git
cd rak_common_for_gateway
sudo ./install.sh --chirpstack=not_install
```

The `--chirpstack=not_install` flag matters: by default this installer *also* installs RAKWireless's own bundled ChirpStack — which is the old, EOL **v3** (`chirpstack-network-server` + `chirpstack-application-server`, a completely different architecture from v4), running natively and defaulting to the same port 8080 we're using for the real ChirpStack v4 Docker stack in [06](06-chirpstack-server-deployment.md). Left in, it's both wasted effort and a guaranteed port conflict later. Skip it here.

## Step 2: Select your hardware

The installer presents a numbered menu of supported gateway models. For a Pi 4B + RAK5146 SPI Pi HAT with **no LTE**, choose:

```
11. RAK5146 SPI
```

(Option 12 is the same hardware with an LTE backhaul module added — not what we're using here. Options 7/8 are for the older RAK2287/SX1302 module, not the RAK5146/SX1303.)

Let it finish — it builds the HAL from source, which takes a few minutes on a Pi 4.

> **If you see `Failed to disable unit: Unit file hciuart.service does not exist.` and the install stops there**, this is a real bug in the installer, not a cosmetic warning — `rak/install.sh` runs under `set -e` (abort on any error) and calls `systemctl disable hciuart` unconditionally, with no fallback. `hciuart.service` normally hands the UART from Bluetooth to the GPS, but on images where that service was never installed to begin with (common on current Raspberry Pi OS Lite), the command exits non-zero and takes the whole install down with it — silently enough that it can look like it finished. If this happens, before doing anything else, patch that one line in your already-cloned copy and re-run:
> ```bash
> cd ~/rak_common_for_gateway
> sed -i 's/^systemctl disable hciuart.*/systemctl disable hciuart || true/' rak/install.sh
> sudo ./install.sh --chirpstack=not_install
> ```
> Confirm it actually reached the end this time — it should print a banner ending in `The RAKwireless gateway is successfully installed!` and `which gateway-config` should resolve to `/usr/bin/gateway-config`.

## Step 3: Reboot

```bash
sudo reboot
```

## Step 4: Test the packet-forwarder service before configuring ChirpStack

On current Raspberry Pi OS, there are **two** separate GPIO failure modes in RAK's scripts:

1. The original scripts use removed `/sys/class/gpio` paths.
2. Newer installer revisions detect `gpioset`, but call it using the old libgpiod v1 syntax. Raspberry Pi OS Bookworm/Trixie ship libgpiod v2, which requires `--chip`; it also keeps the GPIO line claimed unless told to exit after the pulse.

The systemd unit uses `Restart=always`, so a status of `active` by itself is not proof that the concentrator is working. Check the actual startup log:

```bash
sudo systemctl status ttn-gateway --no-pager -l
```

```bash
sudo journalctl -u ttn-gateway -n 100 --no-pager
```

Apply Step 5 if you see any of the following:

```
cannot create /sys/class/gpio/gpio17/direction: Directory nonexistent
gpioset: invalid line value: 'gpiochip0'
```

Also apply it if `systemctl status` shows a `gpioset --chip gpiochip0 ...` child for more than a few seconds and never reaches `Reset sequence completed` or starts `./lora_pkt_fwd`.

## Step 5: Patch the RAK reset scripts for libgpiod v2

Install the GPIO tools first:

```bash
sudo apt install -y gpiod
```

The following patch targets the script layout used by current `rak_common_for_gateway` releases: `GPIO_CHIP` and `RESET_GPIO` are already selected by the scripts, so do not replace the board-detection logic or hard-code a different pin. It changes calls such as:

```bash
gpioset ${GPIO_CHIP} ${RESET_GPIO}=0
```

to the libgpiod v2 form:

```bash
gpioset --chip ${GPIO_CHIP} --hold-period 100ms --toggle 0 ${RESET_GPIO}=0
```

`--chip` selects `gpiochip0` explicitly. `--hold-period 100ms --toggle 0` produces a short reset pulse and then exits; without it, libgpiod v2 deliberately holds the line forever and `start.sh` never reaches the packet forwarder.

Stop the restart loop:

```bash
sudo systemctl stop ttn-gateway
```

Back up the scripts without overwriting an existing backup:

```bash
cd /opt/ttn-gateway/packet_forwarder/lora_pkt_fwd
```

```bash
sudo cp -pn start.sh start.sh.before-gpiod-v2
```

```bash
sudo cp -pn reset_lgw.sh reset_lgw.sh.before-gpiod-v2
```

Apply the idempotent patch. It handles both the unpatched `gpioset ${GPIO_CHIP}` form and the partial `gpioset --chip ${GPIO_CHIP}` form:

```bash
sudo sed -E -i \
  -e 's#gpioset([[:space:]]+--chip)?[[:space:]]+\$\{GPIO_CHIP\}[[:space:]]+\$\{RESET_GPIO\}=#gpioset --chip ${GPIO_CHIP} --hold-period 100ms --toggle 0 ${RESET_GPIO}=#g' \
  -e 's#gpioget([[:space:]]+--chip)?[[:space:]]+\$\{GPIO_CHIP\}[[:space:]]+\$\{RESET_GPIO\}#gpioget --chip ${GPIO_CHIP} ${RESET_GPIO}#g' \
  start.sh reset_lgw.sh
```

Verify the result before starting the service:

```bash
sudo grep -nE 'gpioset|gpioget' start.sh reset_lgw.sh
```

Every `gpioset` reset line should contain both `--chip ${GPIO_CHIP}` and `--hold-period 100ms --toggle 0`. If these scripts do not use the `GPIO_CHIP` / `RESET_GPIO` variables shown above, stop here and adapt the same two principles to their actual commands: use `--chip` with libgpiod v2 and make every reset pulse exit.

Validate the shell syntax:

```bash
bash -n start.sh
```

```bash
sh -n reset_lgw.sh
```

Start the service and give it time to initialize:

```bash
sudo systemctl start ttn-gateway
```

```bash
sleep 10
```

```bash
sudo systemctl status ttn-gateway --no-pager -l
```

> On a Pi 4B, the RAK scripts should select GPIO 17 on `gpiochip0`. If they do not, run `gpioinfo` and find the chip labeled `pinctrl-bcm2711` (roughly 58 lines). Pi 5 uses a different GPIO chip arrangement.

## Step 6: Confirm the concentrator is actually running

Check both the service and its log:

```bash
sudo systemctl status ttn-gateway --no-pager -l
```

```bash
sudo journalctl -u ttn-gateway -n 100 --no-pager
```

```bash
pgrep -af '[l]ora_pkt_fwd'
```

A healthy start has all of these:

- `systemctl` remains `active (running)` for at least 10 seconds and its cgroup includes `./lora_pkt_fwd`, not only a `gpioset` process.
- The log shows `Reset sequence completed`, a real SX1303 chip version (typically `0x12 (v1.2)` after the reset patch), and no `ERROR: [main] failed to start the concentrator`.
- `pgrep` prints the running packet-forwarder process.

`0x00` means the concentrator is not detected at all — see [10-troubleshooting.md](10-troubleshooting.md). A non-zero chip version alone is not sufficient: continue reading the log for radio, SX1261, or startup errors.

## Step 7: Get your Gateway EUI

You'll need this in a few steps, when you register the gateway in ChirpStack.

```bash
cat /opt/ttn-gateway/packet_forwarder/lora_pkt_fwd/local_conf.json
```

Look for `gateway_ID` under `gateway_conf` — a 16-character hex string (e.g. `AC1F09FFFE123456`). Write it down.

## Step 8: Set the regional channel plan

The installer ships a library of regional configs at `/opt/ttn-gateway/packet_forwarder/lora_pkt_fwd/global_conf/`, and defaults the active `global_conf.json` to **EU868** regardless of what you actually need — this always needs to be changed explicitly, on every install.

`gateway-config`'s menu options for this can be inconsistently labeled between installer versions, so rather than guessing from a menu string, it's more reliable to check the actual channel frequencies inside each candidate file and pick by frequency, matched against your region's real plan:

```bash
cd /opt/ttn-gateway/packet_forwarder/lora_pkt_fwd/global_conf
grep freq_start global_conf.as_915_921.json
```

For **AS923-3 (Philippines)**, the correct file is `global_conf.as_915_921.json` — its two default channels are 916.6 MHz and 916.8 MHz, which is exactly the AS923-3 plan (AS923-1's 923.2/923.4 MHz, shifted down 6.6 MHz). The naming of the other files in that folder is a similar story — go by frequency, not the label, if you're on a different plan:

| File | Default channels | Actual plan |
|---|---|---|
| `global_conf.as_915_928.json` | 923.2 / 923.4 MHz | AS923-1 (default/unshifted) |
| `global_conf.as_920_923.json` | 921.4 / 921.6 MHz | AS923-2 (Indonesia, Vietnam) |
| `global_conf.as_915_921.json` | 916.6 / 916.8 MHz | **AS923-3 (Philippines, Cuba)** |
| `global_conf.as_917_920.json` | 917.3 / 917.5 MHz | AS923-4 (Israel) |

Apply it. Stop the service first, keep a backup, and copy the whole regional file rather than changing individual frequencies:

```bash
sudo systemctl stop ttn-gateway
```

```bash
cd /opt/ttn-gateway/packet_forwarder/lora_pkt_fwd/global_conf
```

```bash
sudo cp -pn ../global_conf.json ../global_conf.json.before-as923-3
```

```bash
sudo cp global_conf.as_915_921.json ../global_conf.json
```

```bash
sudo grep -nE '"radio_[01]"|"type"|"freq"' ../global_conf.json
```

This needs to match what you enable on the ChirpStack side in [06](06-chirpstack-server-deployment.md) — the two need to agree, or your gateway will receive on the wrong frequencies for what your devices transmit on.

## Step 9: Disable unavailable SX1261 features in the AS923-3 template

The `global_conf.as_915_921.json` template bundled with some RAK installer versions enables **spectral scan** and **Listen-Before-Talk (LBT)** under `sx1261_conf`, even though this RAK5146 SPI setup has no usable SX1261 SPI path. The symptom is:

```
SX1261 spi_path is not configured in global_conf.json
ERROR: sx1261_com_open: Failed to connect to sx1261 radio
ERROR: failed to connect to the sx1261 radio (LBT/Spectral Scan)
```

For the Philippines AS923-3 setup documented here, disable both features before starting the packet forwarder. Do not do this on different hardware that genuinely has an SX1261 or in a deployment where local rules require LBT; confirm your regulatory requirements first.

Back up the selected regional file:

```bash
cd /opt/ttn-gateway/packet_forwarder/lora_pkt_fwd
```

```bash
sudo cp -pn global_conf.json global_conf.json.as923-3-before-sx1261-disable
```

Disable spectral scan:

```bash
sudo sed -E -i '/"spectral_scan"[[:space:]]*:/,/"lbt"[[:space:]]*:/ s/"enable"[[:space:]]*:[[:space:]]*true/"enable": false/' global_conf.json
```

Disable LBT:

```bash
sudo sed -E -i '/"lbt"[[:space:]]*:/,/"radio_0"[[:space:]]*:/ s/"enable"[[:space:]]*:[[:space:]]*true/"enable": false/' global_conf.json
```

Verify both values:

```bash
sudo grep -nEi -A 10 -B 2 'spectral_scan|lbt' global_conf.json
```

Both relevant `"enable"` lines must be `false`. You can now start the packet forwarder:

```bash
sudo systemctl start ttn-gateway
```

```bash
sleep 10
```

```bash
sudo systemctl status ttn-gateway --no-pager -l
```

---
Next: [05-docker-installation.md](05-docker-installation.md)
