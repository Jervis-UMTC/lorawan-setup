# 2. Flashing Raspberry Pi OS Lite and First Boot

## Why Bookworm instead of the newest release

As of this writing, Raspberry Pi OS has moved to a Trixie (Debian 13, kernel 6.12) base by default, with Bookworm (Debian 12, kernel 6.1, supported into late 2026) still available as a selectable option in Raspberry Pi Imager. This guide defaults to **Bookworm** for one practical reason: the RAK5146's driver stack (the SX1302/SX1303 HAL and RAK's install scripts) predates the kernel change that deprecated the old `/sys/class/gpio` interface, and the community-verified fix for that is documented and tested specifically against Bookworm (see [10-troubleshooting.md](10-troubleshooting.md)). Trixie ships the same GPIO tooling version, so the same fix should apply there too, but there's simply more real-world mileage on Bookworm for this exact hardware combination, plus some early reports of Wi-Fi headless-setup quirks on Trixie. If you'd rather run Trixie, you can — just expect to lean on [10-troubleshooting.md](10-troubleshooting.md) a bit more, and prefer Ethernet over Wi-Fi for initial setup either way.

## Step 1: Install Raspberry Pi Imager

Download it from raspberrypi.com/software for your computer (Windows/macOS/Linux), install, and open it.

## Step 2: Choose the OS image

1. Click **Choose Device** → select **Raspberry Pi 4**.
2. Click **Choose OS**. The top-level "Raspberry Pi OS Lite (64-bit)" entry will give you the current default (Trixie at time of writing). To get Bookworm specifically:
   - Go into **Raspberry Pi OS (other)**
   - Select **Raspberry Pi OS Lite (Legacy, 64-bit)** — this is the Bookworm build
3. Confirm it says **64-bit** — this matters later for Docker image compatibility. Do not use the 32-bit (armhf) image.

## Step 3: Configure before writing (headless setup)

Click the gear icon (or press Ctrl+Shift+X) to open **OS Customisation** before writing the image. This avoids needing a monitor/keyboard on the Pi at all.

Set:
- **Hostname** — e.g. `lorawan-gw` (you'll reach it later at `lorawan-gw.local`)
- **Username and password** — current Raspberry Pi OS no longer ships a default `pi` user; you must set credentials here
- **Enable SSH** — choose password auth for simplicity, or paste a public key if you'd rather use key-based auth from the start
- **Wireless LAN** — only if you're not using Ethernet (see note below)
- **Locale settings** — timezone and keyboard layout

> **If you're using Wi-Fi**: current Trixie-based images use NetworkManager, and the old trick of dropping a `wpa_supplicant.conf` file onto the boot partition manually no longer works — you must configure Wi-Fi through Imager's OS Customisation screen as above. This applies whether or not you end up on Trixie or Bookworm; using Imager's built-in Wi-Fi field is the reliable path either way.
>
> **Recommendation**: connect the Pi to your router by Ethernet cable instead, at least for initial setup. It sidesteps Wi-Fi headless quirks entirely, and a gateway running its own network server benefits from a stable, low-latency link anyway.

## Step 4: Write and boot

1. Click **Write**, confirm the card will be erased, and let it write and verify.
2. Move the card to the Pi, connect Ethernet (if using it), then apply power.
3. First boot takes a couple of minutes — the OS resizes the filesystem and applies your customisation on this boot only.

## Step 5: Find the Pi and connect

From another machine on the same network:

```bash
ssh <username>@<hostname>.local
# e.g. ssh admin@lorawan-gw.local
```

If `.local` mDNS resolution doesn't work on your network, check your router's DHCP client list for the hostname you set, and SSH to the IP address directly instead.

## Step 6: Update the system

```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

Reconnect via SSH once it's back up.

---
Next: [03-system-preparation.md](03-system-preparation.md)
