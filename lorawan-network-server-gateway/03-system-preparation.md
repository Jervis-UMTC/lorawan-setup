# 3. System Preparation

With SSH access working, prepare the OS before touching the concentrator driver or Docker.

## Step 1: Enable SPI, I2C, and the serial hardware (for GPS)

The RAK5146 talks to the Pi over SPI, uses I2C for some onboard functions, and — if your kit has the onboard GPS — needs the UART freed up for NMEA data rather than a login console.

```bash
sudo raspi-config
```

Navigate to **Interface Options** and:
1. **SPI** → Enable
2. **I2C** → Enable
3. **Serial Port** → When asked *"Would you like a login shell accessible over serial?"* select **No**. When asked *"Would you like the serial port hardware to be enabled?"* select **Yes**.

This combination is important and easy to get backwards: you want the UART's hardware enabled (so the GPS can use it) but *not* claimed by a login console (which would otherwise fight the GPS for the same serial port).

Exit raspi-config and reboot:

```bash
sudo reboot
```

## Step 2: Set a static IP (recommended)

A gateway that's also its own network server should have a predictable address — you'll be pointing your browser at it, and you don't want it changing after a router reboot. Current Raspberry Pi OS uses NetworkManager by default:

```bash
nmcli connection show
```

Find your active connection name (commonly `Wired connection 1` for Ethernet), then set a static IPv4 address — adjust the address/gateway to match your actual LAN:

```bash
sudo nmcli connection modify "Wired connection 1" \
  ipv4.addresses 192.168.1.50/24 \
  ipv4.gateway 192.168.1.1 \
  ipv4.dns "192.168.1.1 1.1.1.1" \
  ipv4.method manual

sudo nmcli connection up "Wired connection 1"
```

Alternatively, just reserve the Pi's current DHCP lease as a static assignment in your router's admin page — often simpler, and keeps IP management in one place.

## Step 3: Give yourself some swap headroom

Compiling the concentrator HAL and running several Docker containers (Postgres, Redis, ChirpStack, Mosquitto, Gateway Bridge) at once can get tight on a 2 GB Pi, and even 4 GB boards benefit from a bit of headroom during the initial build steps.

```bash
sudo dphys-swapfile swapoff
sudo sed -i 's/^CONF_SWAPSIZE=.*/CONF_SWAPSIZE=1024/' /etc/dphys-swapfile
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

This sets 1 GB of swap. It's a safety net, not a performance feature — don't expect to run this stack well long-term on a Pi that's genuinely out of RAM, but it will get you through setup and absorb occasional spikes.

## Step 4: Install base packages

```bash
sudo apt install -y git build-essential i2c-tools python3 curl
```

## Step 5: Basic housekeeping now, before it's harder to remember later

- If you didn't set a strong password/SSH key during imaging, do it now (`passwd`).
- Confirm you can `sudo` without issues and that SSH access is solid — you'll be doing everything else remotely from here.

Full hardening (firewall, disabling password auth, etc.) is covered later in [09-autostart-persistence-hardening.md](09-autostart-persistence-hardening.md), once the services that need specific ports open actually exist.

---
Next: [04-lora-concentrator-setup.md](04-lora-concentrator-setup.md)
