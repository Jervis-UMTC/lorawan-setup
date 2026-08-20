# Gateway 2. Install ChirpStack Gateway OS Base

This procedure installs ChirpStack Gateway OS **Base** on the Raspberry Pi 4B, opens the management interface, sets the initial password, and verifies that the correct image is running.

Gateway OS Base contains the lightweight gateway runtime needed for Concentratord and MQTT Forwarder with an external server. The image may also contain UDP Forwarder, but this repository keeps it disabled. The software integrity journal is an additional reviewed service added later in [Gateway 4A](04a-configure-gateway-integrity-journal.md); do not assume the base image already provides that custom evidence function. Gateway OS Full adds a local ChirpStack server and is not used in this repository.

---

## Step 1: Download the correct image

### What this step does

Obtains the official ChirpStack Gateway OS Base firmware image (`.img.gz` or `.wic.gz`) matching the Raspberry Pi 4B hardware architecture and system deployment model from the official release page.

### Why we do it

* **Base vs. Full Variant:** Gateway OS Base provides the lightweight radio/forwarding foundation (`concentratord`, `mqtt-forwarder`) required when linking to an external Network Server. This repository later adds local Mosquitto buffering and a small reviewed integrity-journal service while still keeping all heavy ChirpStack/application/database/KMS/Fabric roles off the gateway. The Full variant runs a local ChirpStack server stack and is unnecessary for this dedicated gateway node.
* **Hardware Architecture Compatibility:** Raspberry Pi models use different processor architectures (ARMv7 vs. ARMv8/Cortex-A72) and device tree blobs (DTBs). Flashing an image built for a different model will result in a non-bootable system or kernel panic.
* **Factory vs. Sysupgrade Image:** Factory images include raw partition tables, boot sectors, and bootloaders for initial microSD card flashing. Sysupgrade images only replace existing system partitions on an already running OpenWrt instance and cannot boot a blank card.

### Procedure

On the administration workstation, open the official ChirpStack Gateway OS Raspberry Pi download page.

Select:

```text
Target: Raspberry Pi 4B
Image type: Base
Artifact: SD card factory image
```

The downloaded file normally ends in `.wic.gz` or `.img.gz`.

Keep the exact release and filename available while installing:

```text
Gateway OS release: <GATEWAY_OS_VERSION>
Downloaded image: <GATEWAY_OS_IMAGE>
```

> [!CAUTION]
> Do not use the Raspberry Pi 3, Raspberry Pi 5, Full, or sysupgrade image for a new Raspberry Pi 4B installation.

---

## Step 2: Verify the downloaded file

### What this step does

Calculates the SHA256 cryptographic hash of the downloaded image file on your workstation and compares it against the official checksum published by ChirpStack.

### Why we do it

* **Detect Download Corruption:** Guarantees bit-for-bit file integrity before writing to physical storage. Flashing a corrupted download leads to cryptic write errors, unbootable SD cards, silent file corruption, or unexpected runtime crashes.
* **Security Verification:** Confirms that the file has not been altered or corrupted during transit over the internet.

### Procedure

Run the checksum verification command corresponding to your operating system:

#### Linux

```bash
sha256sum <GATEWAY_OS_IMAGE>
```

#### macOS

```bash
shasum -a 256 <GATEWAY_OS_IMAGE>
```

#### Windows PowerShell

```powershell
Get-FileHash -Algorithm SHA256 .\<GATEWAY_OS_IMAGE>
```

Compare the output hash with the official release checksum. If the values differ, delete the file and download it again.

---

## Step 3: Flash the microSD card

### What this step does

Writes raw sector blocks (bootloader, system partition tables, read-only SquashFS root filesystem, and OverlayFS user partition) directly to the physical sectors of the microSD card.

### Why we do it

* **Raw Sector Disk Writing:** Creates the initial bootable storage layout required by the Raspberry Pi 4B hardware bootloader.
* **Decline RPi OS Customization:** Gateway OS is built on OpenWrt and uses OpenWrt system initialization routines rather than standard Raspberry Pi OS / `systemd` customization scripts. Applying RPi OS customization scripts injects incompatible configuration files that corrupt startup routines.
* **Ignore Windows Format Prompts:** Gateway OS uses native Linux filesystems (`ext4` and `squashfs`). Windows cannot natively read these partitions and falsely reports them as unformatted or corrupted. Accepting a format prompt will permanently erase the freshly flashed Linux installation.

### Procedure

You can use either **Raspberry Pi Imager** or **Balena Etcher**:

#### Raspberry Pi Imager

1. Insert the microSD card into the workstation.
2. Open **Raspberry Pi Imager**.
3. Select **Choose OS** > **Use custom**.
4. Choose `<GATEWAY_OS_IMAGE>`.
5. Select the correct microSD card under **Storage**.
6. Start the write.
7. Decline Raspberry Pi OS customization when prompted.
8. Wait for both writing and verification to finish.
9. Eject the card safely.

#### Balena Etcher

1. Select **Flash from file** and choose `<GATEWAY_OS_IMAGE>`.
2. Select the target microSD card.
3. Start the flash and wait for validation to finish.
4. Eject the card safely.

#### Windows fix when Balena Etcher displays an error

If Balena Etcher displays `(0, h.requestMetadata) is not a function`, uninstall Etcher, install **Balena Etcher 1.18.11**, run as Administrator, and flash the `.img.gz` file directly.

> [!WARNING]
> After flashing, Windows will prompt to format unrecognized partitions. Select **Cancel** for every format prompt.

---

## Step 4: Perform the first boot

### What this step does

Connects all required physical hardware (LoRa antenna, microSD card, network cable) and applies power, allowing Gateway OS to complete its initial partition expansion, SSH key generation, and network initialization.

### Why we do it

* **Electrical Safety (Disconnect Power First):** Inserting microSD cards or connecting GPIO hat boards while 5V/3.3V power rails are live can cause voltage spikes, short circuits, or electrostatic discharge (ESD) damage.
* **Hardware Protection (Attach LoRa Antenna):** LoRa concentrator boards (e.g. SX1302/SX1303) transmit RF calibration pulses during startup. Operating without an antenna causes 100% of transmitted RF energy to reflect back into the Power Amplifier (high VSWR), generating extreme heat that can permanently burn out the RF chip in seconds.
* **Network Auto-Provisioning:** Connecting Ethernet allows Gateway OS to obtain an IP address via DHCP and synchronize its system clock via NTP immediately upon booting.
* **Filesystem Expansion & First-Boot Setup:** On first boot, Gateway OS expands its read-write OverlayFS partition to fill the microSD card and generates system UUIDs and SSH host keys. OpenWrt often performs an automated reboot during this sequence to remount the resized filesystem cleanly. Removing power during this setup will corrupt the filesystem.

### Procedure

1. Disconnect Raspberry Pi power cord.
2. Insert the flashed microSD card firmly into the card slot.
3. Confirm that the LoRa antenna is securely attached to the concentrator board.
4. Connect an Ethernet cable to a local network with DHCP service available.
5. Apply power.
6. Leave the gateway running for at least 3–5 minutes.

> [!IMPORTANT]
> The gateway may reboot automatically during its first startup. Do not remove power while the first boot is still completing.

---

## Step 5: Find the gateway address

### What this step does

Locates the IP address assigned to the gateway on your local network (via your router's DHCP lease table) or connects to the gateway's fallback Wi-Fi commissioning Access Point (`ChirpStackAP-XXXXXX`).

### Why we do it

* **Remote Access Discovery:** Gateway OS operates headless (without a monitor or keyboard). Finding the assigned IP address is mandatory to open the web management interface (LuCI) or establish an SSH terminal connection from an administration computer.

### Procedure

#### Option A: Ethernet (Recommended)

1. Open your router or DHCP server administration page.
2. Check the active DHCP client list for a device named `OpenWrt`, `ChirpStack`, or `RaspberryPi`.
3. Note the IP address as `<GATEWAY_IP>`.

#### Option B: Wi-Fi Commissioning Access Point

If Ethernet is not available, connect your computer to the fallback wireless network:

```text
SSID: ChirpStackAP-XXXXXX
Password: ChirpStackAP
Gateway address: 192.168.0.1
```

---

## Step 6: Open LuCI and complete the first login

### What this step does

Accesses OpenWrt's LuCI web administration interface via web browser (`http://<GATEWAY_IP>/`) and logs in for the first time using the default `root` account with an empty password.

### Why we do it

* **Initial Administrative Access:** Opens the management GUI required to perform security hardening, set passwords, configure network interfaces, and check service status.
* **Credential Separation:** Ensures administrators do not confuse the Wi-Fi commissioning password (`ChirpStackAP`) with the system `root` account password.

### Procedure

1. Open a browser and navigate to `http://<GATEWAY_IP>/` (or `http://192.168.0.1/` if connected via Wi-Fi AP).
2. Accept the browser self-signed HTTPS certificate warning after confirming the IP address matches your gateway.
3. On the login screen, enter:

| Field | First-login value |
|---|---|
| Username | `root` |
| Password | *Leave completely empty (do not type anything)* |

4. Select **Login**.

> [!NOTE]
> Do not type `not set` or `ChirpStackAP` in the password field. Clear any browser autofill values before clicking Login.

---

## Step 7: Set and verify the root password immediately

### What this step does

Configures a new, secure administrative password for the `root` user via LuCI (**System > Administration**), applies the setting, logs out, and verifies login using the new credentials.

### Why we do it

* **Security Hardening:** Gateway OS ships with an unauthenticated/empty root password by default. Setting a strong root password immediately secures both the LuCI web interface and SSH command line against unauthorized network access.
* **Shared Identity:** On Gateway OS, the `root` password protects both the web interface and SSH terminal.
* **Verification:** Logging out and logging back in proves that the password was saved correctly before modifying network settings that could affect connectivity.

### Procedure

1. In LuCI, navigate to **System > Administration**.
2. Under **Router Password**, enter your new strong password in both fields.
3. Select **Save & Apply**.
4. Log out of LuCI using the top-right logout button.
5. Log back in using:
   * **Username:** `root`
   * **Password:** `<YOUR_NEW_ROOT_PASSWORD>`
6. Confirm that login succeeds and the status dashboard opens.

---

## Step 8: Configure the management network

### What this step does

Sets the system hostname, time zone, NTP synchronization servers, network interfaces (Ethernet / Wi-Fi backhaul), and disables the fallback commissioning Wi-Fi Access Point (`ChirpStackAP`).

### Why we do it

* **Time Synchronization (NTP):** Accurate UTC system time is mandatory for validating SSL/TLS certificates when connecting to MQTT brokers / Network Servers and for creating accurate LoRaWAN packet timestamps (`time` field).
* **Network Stability:** Setting static IP addresses or DHCP reservations ensures predictable, long-term remote connectivity for gateway management and data backhaul.
* **Remove Open Access Points:** Disabling `ChirpStackAP` removes an unencrypted, public wireless entry point into your gateway once commissioning is finished.

### Procedure

#### 1. Set Hostname and Time Synchronization (NTP)

1. Open **System > System**.
2. Enter a unique **Hostname** (e.g. `lora-gw-01`).
3. Select your local **Timezone**.
4. Under **Time Synchronization**:
   * Ensure **Enable NTP client** is **checked**.
   * Ensure **Use DHCP advertised servers** is **checked**.
   * Verify NTP candidates (`0.openwrt.pool.ntp.org`, etc.) or add your corporate NTP server.
5. Select **Save & Apply**.

#### 2. Configure Backhaul Interface

1. Open **Network > Interfaces**.
2. Edit the management interface (`lan` or `wan`).
3. Keep **DHCP client** (with a router reservation) or set a static IP if required by your network team.
4. Select **Save & Apply**.

#### 2a. Automated Gateway OS IP Helper (`set-ip.sh`)

To easily switch between **DHCP** and a **Static IP** on Gateway OS (OpenWrt) for either **Ethernet** or **Wi-Fi** backhaul without manually editing UCI configuration tables, install the automated `set-ip.sh` helper script.

##### Installation Command:

Paste this script creation block into your Gateway OS SSH terminal:

```bash
cat << 'EOF' > /usr/bin/set-ip.sh
#!/bin/sh
set -e

TARGET="${1:-}"

# Backward compatibility: if 1st arg is static or dhcp, default target to eth
if [ "$TARGET" = "dhcp" ] || [ "$TARGET" = "static" ]; then
    MODE="$TARGET"
    TARGET="eth"
    shift 1
else
    MODE="${2:-}"
    shift 2 2>/dev/null || true
fi

# Map target to UCI section
case "$TARGET" in
    eth|eth0|ethernet)
        UCI_NET="network.eth0"
        if ! uci get network.eth0 >/dev/null 2>&1; then
            if uci get network.wan >/dev/null 2>&1; then UCI_NET="network.wan"; else UCI_NET="network.lan"; fi
        fi
        ;;
    wifi|wlan|wlan0|wwan)
        UCI_NET="network.wwan"
        if ! uci get network.wwan >/dev/null 2>&1; then
            uci set network.wwan=interface
        fi
        # Ensure radio is enabled on boot
        uci set wireless.radio0.disabled='0' 2>/dev/null || true
        # Permit SSH & LuCI over Wi-Fi by assigning wwan to lan firewall zone
        uci add_list firewall.@zone[0].network='wwan' 2>/dev/null || true
        uci commit wireless
        uci commit firewall
        ;;
    wifi-join|wifi-connect)
        SSID="${1:-}"
        PASS="${2:-}"
        if [ -z "$SSID" ]; then
            echo "Usage: set-ip.sh wifi-join <SSID> [PASSWORD]"
            exit 1
        fi
        echo "[+] Joining Wi-Fi network '$SSID'..."
        # Ensure radio is enabled on boot
        uci set wireless.radio0.disabled='0' 2>/dev/null || true
        uci set wireless.wifinet0=wifi-iface 2>/dev/null || true
        uci set wireless.wifinet0.device='radio0'
        uci set wireless.wifinet0.mode='sta'
        uci set wireless.wifinet0.network='wwan'
        uci set wireless.wifinet0.ssid="$SSID"
        if [ -n "$PASS" ]; then
            uci set wireless.wifinet0.encryption='psk2'
            uci set wireless.wifinet0.key="$PASS"
        else
            uci set wireless.wifinet0.encryption='none'
        fi
        # Permit SSH & LuCI over Wi-Fi by assigning wwan to lan firewall zone
        uci add_list firewall.@zone[0].network='wwan' 2>/dev/null || true
        uci commit wireless
        uci commit firewall
        /etc/init.d/firewall restart 2>/dev/null || true
        wifi reload 2>/dev/null || /etc/init.d/network restart
        echo "[+] Joined Wi-Fi network '$SSID' and enabled SSH access over Wi-Fi (auto-starts on boot)."
        exit 0
        ;;
    *)
        echo "Usage:"
        echo "  Ethernet DHCP:        set-ip.sh eth dhcp"
        echo "  Ethernet Static:      set-ip.sh eth static <IP> <NETMASK> <GATEWAY> [DNS1] [DNS2]"
        echo "  Wi-Fi DHCP:           set-ip.sh wifi dhcp"
        echo "  Wi-Fi Static:         set-ip.sh wifi static <IP> <NETMASK> <GATEWAY> [DNS1] [DNS2]"
        echo "  Connect Wi-Fi SSID:   set-ip.sh wifi-join <SSID> [PASSWORD]"
        exit 1
        ;;
esac

if [ "$MODE" = "dhcp" ]; then
    echo "[+] Configuring Gateway OS $TARGET interface ($UCI_NET) for DHCP..."
    uci set ${UCI_NET}.proto='dhcp'
    uci del ${UCI_NET}.ipaddr 2>/dev/null || true
    uci del ${UCI_NET}.netmask 2>/dev/null || true
    uci del ${UCI_NET}.gateway 2>/dev/null || true
    uci del ${UCI_NET}.dns 2>/dev/null || true
    uci commit network
    /etc/init.d/network restart
    echo "[+] Applied DHCP configuration to $TARGET ($UCI_NET)."

elif [ "$MODE" = "static" ]; then
    IP="${1:-}"
    NETMASK="${2:-255.255.255.0}"
    GATEWAY="${3:-}"
    DNS1="${4:-8.8.8.8}"
    DNS2="${5:-1.1.1.1}"

    if [ -z "$IP" ] || [ -z "$GATEWAY" ]; then
        echo "Usage: set-ip.sh $TARGET static <IP> <NETMASK> <GATEWAY> [DNS1] [DNS2]"
        echo "Example: set-ip.sh $TARGET static 192.168.1.151 255.255.255.0 192.168.1.1"
        exit 1
    fi

    echo "[+] Configuring Gateway OS $TARGET interface ($UCI_NET) with Static IP: $IP (Gateway: $GATEWAY)..."
    uci set ${UCI_NET}.proto='static'
    uci set ${UCI_NET}.ipaddr="$IP"
    uci set ${UCI_NET}.netmask="$NETMASK"
    uci set ${UCI_NET}.gateway="$GATEWAY"
    uci set ${UCI_NET}.dns="$DNS1 $DNS2"
    uci commit network
    /etc/init.d/network restart
    echo "[+] Applied Static IP configuration to $TARGET ($UCI_NET)."

else
    echo "Usage:"
    echo "  Ethernet DHCP:        set-ip.sh eth dhcp"
    echo "  Ethernet Static:      set-ip.sh eth static <IP> <NETMASK> <GATEWAY> [DNS1] [DNS2]"
    echo "  Wi-Fi DHCP:           set-ip.sh wifi dhcp"
    echo "  Wi-Fi Static:         set-ip.sh wifi static <IP> <NETMASK> <GATEWAY> [DNS1] [DNS2]"
    echo "  Connect Wi-Fi SSID:   set-ip.sh wifi-join <SSID> [PASSWORD]"
    exit 1
fi
EOF

chmod +x /usr/bin/set-ip.sh
```

##### Usage Examples:

- **Ethernet Options**:
  ```bash
  set-ip.sh eth static 192.168.1.151 255.255.255.0 192.168.1.1   # Static Ethernet IP
  set-ip.sh eth dhcp                                             # DHCP Ethernet
  ```

- **Wi-Fi Options**:
  ```bash
  set-ip.sh wifi-join "MyHomeSSID" "MyWifiPassword123"           # Connect to Wi-Fi SSID
  set-ip.sh wifi static 192.168.1.152 255.255.255.0 192.168.1.1  # Static Wi-Fi IP
  set-ip.sh wifi dhcp                                            # DHCP Wi-Fi IP
  ```

#### 2b. Configure Wi-Fi Client Mode (If not using Ethernet)

If you plan to run the gateway using Wi-Fi backhaul (connecting wirelessly to a local router instead of Ethernet):

1. Keep `ChirpStackAP` enabled while connected to `192.168.0.1`.
2. Open **Network > Wireless**.
3. Select **Scan** on the wireless radio interface (`radio0` or `radio1`).
4. Find your local Wi-Fi router network SSID and select **Join Network**.
5. Enter your Wi-Fi network password (WPA passphrase) and select **Submit** > **Save & Apply**.
6. Connect your administration computer to that same local Wi-Fi router network.
7. Check your router's DHCP client list to find the gateway's new IP address.
8. Verify you can access LuCI over the new network connection (`http://<NEW_GATEWAY_IP>/`).
9. **Only after verifying access over the new IP address**, proceed to disable `ChirpStackAP`.

#### 3. Disable Commissioning Access Point

> [!WARNING]
> **DO NOT disable the `ChirpStackAP` Access Point if you are currently connected through it AND do not have Ethernet plugged in!**
> Disabling the AP without Ethernet or an active Wi-Fi Client connection to a local router will immediately shut off wireless radio management, **locking you out of the gateway**.
> Only disable `ChirpStackAP` after you have configured Wi-Fi Client mode or connected via Ethernet, and verified you can access LuCI over the new network connection.

1. Open **Network > Wireless**.
2. Locate `ChirpStackAP`.
3. Select **Disable**.
4. Select **Save & Apply**.

---

## Step 9: Verify SSH access

### What this step does

Tests secure remote terminal access from your administration workstation to the gateway via SSH (`ssh root@<GATEWAY_IP>`) using the root password created in Step 7.

### Why we do it

* **Command-Line Administration & Troubleshooting:** Confirms direct terminal access for inspecting low-level system logs, editing configuration files, monitoring system daemons, and running maintenance scripts.

### Procedure

1. On your workstation terminal, run:

```bash
ssh root@<GATEWAY_IP>
```

2. Accept the SSH host key fingerprint prompt.
3. Enter the `root` password set in Step 7.
4. Confirm that the OpenWrt command prompt appears (`root@lora-gw-01:~#`).
5. (Optional) Install your SSH public key for key-based authentication:

```bash
ssh-copy-id root@<GATEWAY_IP>
```

---

## Step 10: Verify the running image

### What this step does

Executes diagnostic commands over SSH (`cat /etc/os-release`, `uname -a`, `date -u`, `ip addr`, `monit status`) to verify system OS details, time sync, network routing, and daemon status.

### Why we do it

* **Operational Health Check:** Validates that the system is running the expected Gateway OS Base image, network routing and NTP synchronization are functioning properly, and critical gateway daemons (`concentratord`, `monit`) are healthy without crash loops.

### Procedure

Run these commands in your SSH terminal:

```sh
cat /etc/os-release
uname -a
date -u
ip addr
ip route
ps w | grep chirpstack
```

Verify that:
- `/etc/os-release` shows `ChirpStack Gateway OS Base`.
- `date -u` shows the current UTC date and time (confirming NTP sync).
- System process list (`ps w`) shows active gateway services.

---

## Step 11: Create the first configuration backup

### What this step does

Generates and downloads a compressed system backup archive (`.tar.gz`) from LuCI (**System > Backup / Flash Firmware**) to your administration workstation.

### Why we do it

* **Disaster Recovery:** Saves a clean baseline snapshot of system configurations, network settings, and credentials off-device. In the event of SD card failure or data corruption, the gateway can be restored quickly without repeating the entire manual setup procedure.

### Procedure

1. In LuCI, open **System > Backup / Flash Firmware**.
2. Under **Backup**, select **Generate archive**.
3. Save the downloaded `.tar.gz` file in a secure backup folder on your workstation.

---

## Troubleshooting

### The gateway does not appear in the DHCP list
- Confirm Ethernet link LEDs are lit on the Raspberry Pi port.
- Wait at least 3-5 minutes for first-boot partition expansion to finish.
- Connect to `ChirpStackAP-XXXXXX` Wi-Fi if available.

### The browser cannot open LuCI
- Ensure your workstation is on the same network subnet as the gateway.
- Clear browser cache or use an Incognito window.
- Verify SSH access to test if the OS is alive.

### System time is incorrect
- Confirm that the default gateway and DNS servers are configured under **Network > Interfaces**.
- Verify that your firewall allows outbound NTP traffic (UDP port 123).

---

## Next Step

Continue with [03-configure-concentratord.md](03-configure-concentratord.md).
