# Gateway 2A. Build a SIM7600-Capable ChirpStack Gateway OS Image

Use this manual only when the official ChirpStack Gateway OS Base image does not contain kernel modules required by the Waveshare SIM7600G-H.

The current Phase 11 evidence requires this branch. Gateway OS `4.12.0` on Raspberry Pi 4B runs kernel `6.6.141~ce9a7c4f21afbe9986efeaec95ee2cce-r1`, while the stock OpenWrt `24.10.7` kmods repository for the same nominal kernel release requires `6.6.141~910ca1d362cc3ff4f2a1d9a4e9759bc8-r1`. These ABI hashes are different. Do not force-install the stock modules into the Gateway OS kernel.

The durable repair is to build the Gateway OS image from its own pinned source/configuration with the modem support selected before the kernel and image are compiled.

## 2A.1 Result

Build a Raspberry Pi 4B Gateway OS **Base** image that preserves the normal ChirpStack gateway stack and additionally contains:

```text
SIM7600 serial/control path
  kmod-usb-serial
  kmod-usb-serial-wwan
  kmod-usb-serial-option

current SIM7600 data-path candidate
  kmod-usb-wdm
  kmod-usb-net
  kmod-usb-net-qmi-wwan
  uqmi
  luci-proto-qmi

PPP fallback
  keep the existing PPP support selected
```

The QMI packages are included because the current `1e0e:9001` composition exposes a higher vendor-specific data function while the SIMCom-aware `option` driver is intended for the serial functions. Do not configure QMI as the active WAN until the rebuilt gateway proves `/dev/cdc-wdm*` plus the associated WWAN interface actually exist.

Do not add Gateway OS Full, a local ChirpStack server, a second packet forwarder, or unrelated packages.

## 2A.2 Preserve the current working gateway first

Before building or flashing anything, follow [Operations 2. Gateway Backup and Recovery](../operations/02-backup-and-recovery.md).

At minimum preserve outside the gateway:

```text
official current Gateway OS 4.12.0 factory-image reference + SHA-256
Gateway OS sysupgrade configuration archive + SHA-256
current Gateway EUI = 0016c001f139a1cb
current radio plan = AS923 / topic prefix as923
current network management configuration
current Mosquitto configuration + encrypted certificate/private-key recovery bundle
current ChirpStack Concentratord/MQTT Forwarder/UDP Forwarder UCI files
```

Phase 11.0G created the current rollback artifacts on the gateway:

```text
/tmp/gateway-os-backup-20260826-082144.tar.gz
SHA-256 572bfa3f45a69c5ed2ca99263988e8acf2e91ddb514f538520f62d5fb12488a1

/tmp/gateway-critical-private-20260826-082144.tar.gz
SHA-256 f74fc55480bd4edf11a745118e15eae7afac43fff9daabcd64bb20aed4757db1
```

The normal sysupgrade archive does not cover the Mosquitto certificate/data trees, so preserve **both** artifacts. The second archive is secret-bearing recovery material. Before starting the build, copy both files off the gateway over a protected channel and verify the same SHA-256 values on the receiving machine. Do not commit either archive to this repository.

For this exact Gateway OS image, Windows OpenSSH `scp` may fail with `ash: /usr/libexec/sftp-server: not found` because recent OpenSSH clients use SFTP by default and the minimal image does not ship the SFTP server helper. Use legacy SCP mode instead:

```powershell
scp -O root@192.168.8.11:/tmp/gateway-os-backup-20260826-082144.tar.gz root@192.168.8.11:/tmp/gateway-critical-private-20260826-082144.tar.gz <PROTECTED_DESTINATION>\
```

`-O` changes only the transfer protocol; it does not mutate gateway configuration.

The Phase 11.0G-2 retry passed. The protected workstation copy is:

```text
C:\Users\smartagriintern\lorawan-recovery\gateway-01\20260826-082144
```

Verified destination artifacts:

```text
gateway-os-backup-20260826-082144.tar.gz
size 15908 bytes
SHA-256 572bfa3f45a69c5ed2ca99263988e8acf2e91ddb514f538520f62d5fb12488a1

gateway-critical-private-20260826-082144.tar.gz
size 6188 bytes
SHA-256 f74fc55480bd4edf11a745118e15eae7afac43fff9daabcd64bb20aed4757db1
```

`OFF_GATEWAY_ROLLBACK_COPY=PASS` and `CUSTOM_IMAGE_BUILD_ALLOWED=YES`. The first custom-image test must use a **spare microSD card**. Keep the current working card untouched so rollback is physical and immediate. Retain the gateway `/tmp` copies until the spare-card build and restore boundary have been proven.

## 2A.3 Build host requirements

Build on a separate administration/build machine, not on the Raspberry Pi gateway and not on a 2-GiB cloud node used by the POC.

Required:

```text
Git
Docker
stable Internet access
substantial free disk space for an OpenWrt source/build tree
```

The upstream Gateway OS build is Docker-based. Building may take a long time and consume many gigabytes; that is normal.

### Phase 11.0H build-host preflight result - 2026-08-26

The Windows workstation is suitable for the build workload: Windows 10 Pro, `15.6 GiB` RAM, `8` logical CPU threads, and `126.8 GiB` free on `C:`. Windows Git `2.55.0.windows.3` is installed and the protected rollback files remain present. The host-resource and recovery gates therefore pass.

WSL2 is installed, but the only registered distribution is Docker Desktop's internal `docker-desktop` distribution. That is not the normal Linux development workspace for the Gateway OS source tree. Install a normal Linux WSL2 distribution before cloning/building. Docker Desktop's Windows client is present (`29.6.2`) but its Linux engine is currently stopped/unreachable, so start and verify that engine separately before the build.

Treat these as two distinct remediation gates: first establish a normal Linux WSL2 user distribution; then prove Docker Desktop's Linux engine is running and accessible from that distribution. Do not clone Gateway OS source or install build packages until both gates pass.

### Phase 11.0H-1 WSL distro availability result - 2026-08-26

**PASS for distro availability / installation still pending.** `wsl.exe --list --online` explicitly lists `Ubuntu-24.04` as **Ubuntu 24.04 LTS**. The later PowerShell marker `UBUNTU_2404_AVAILABLE=NO` is a false negative from the capture/matching path and does not override the direct WSL listing. Use the exact advertised distro identifier `Ubuntu-24.04`; do not substitute the floating `Ubuntu` alias or a newer release merely because it is available.

The next mutation is intentionally limited to installing `Ubuntu-24.04` as a WSL distribution, preferably with `--no-launch` so installation and first-user initialization remain separate verification gates. WSL's current default version is already `2`, so do not change the global WSL default as part of this step. Docker Desktop remains untouched until the Ubuntu distro itself is registered and reports `VERSION 2`.

## 2A.4 Pin the Gateway OS source

Clone the official repository on the build host:

```bash
git clone https://github.com/chirpstack/chirpstack-gateway-os.git
cd chirpstack-gateway-os
git fetch --tags --force
git checkout --detach v4.12.0
git status --short
git describe --tags --exact-match
git rev-parse HEAD
```

Record the full commit returned by `git rev-parse HEAD` with the build evidence. Do not build from `master` merely because it is newer. The running gateway is on Gateway OS `4.12.0`, so reproduce that release first and change only the required modem package selection.

## 2A.5 Initialize the pinned OpenWrt tree

From the Gateway OS repository root:

```bash
make init
```

This initializes the exact OpenWrt source and feeds used by the pinned Gateway OS source tree.

Then enter the Docker build environment:

```bash
make devshell
```

Run the remaining build commands **inside that development shell** unless the upstream build environment explicitly returns you to the host shell.

## 2A.6 Select the Raspberry Pi 4B Base environment

Inside the development shell:

```bash
make switch-env ENV=base_raspberrypi_bcm27xx_bcm2709
```

Verify the selected environment before editing package selection:

```bash
grep -E '^CONFIG_TARGET_bcm27xx|^CONFIG_TARGET_bcm27xx_bcm2709' openwrt/.config 2>/dev/null || \
grep -E '^CONFIG_TARGET_bcm27xx|^CONFIG_TARGET_bcm27xx_bcm2709' .config
```

Stop if this is not the Raspberry Pi `bcm27xx/bcm2709` Base environment.

## 2A.7 Add only the required modem packages

Change into the OpenWrt tree if the development shell is not already there, then run:

```bash
make menuconfig
```

Use menuconfig search (`/`) for each package name. Select these packages as **built into the image** rather than relying on a later foreign kmods feed:

```text
kmod-usb-serial
kmod-usb-serial-wwan
kmod-usb-serial-option
kmod-usb-wdm
kmod-usb-net
kmod-usb-net-qmi-wwan
uqmi
luci-proto-qmi
```

Keep the existing Gateway OS Base selections and existing PPP support. Do not deselect RAK/ChirpStack packages merely to reduce image size.

Save the configuration, then normalize dependencies:

```bash
make defconfig
```

Prove the intended package selection before compiling:

```bash
grep -E '^CONFIG_PACKAGE_(kmod-usb-serial|kmod-usb-serial-wwan|kmod-usb-serial-option|kmod-usb-wdm|kmod-usb-net|kmod-usb-net-qmi-wwan|uqmi|luci-proto-qmi)=' .config
```

Required packages must resolve to `=y` or to the build-system state that the pinned Gateway OS image generator includes in the final image. If a package is missing after `make defconfig`, stop and inspect its dependencies instead of forcing the build.

## 2A.8 Build the image

From the environment expected by the upstream repository:

```bash
make
```

Do not interrupt the first build simply because it is slow.

After success, inspect the Raspberry Pi target output. The OpenWrt target artifacts normally live under:

```text
openwrt/bin/targets/bcm27xx/bcm2709/
```

Locate the Base factory image and its manifest rather than guessing a filename:

```bash
find openwrt/bin/targets/bcm27xx/bcm2709 \
  -maxdepth 1 -type f \
  \( -name '*.img.gz' -o -name '*.wic.gz' -o -name '*.manifest' -o -name 'sha256sums' \) \
  -print
```

## 2A.9 Verify the custom image before flashing

Record SHA-256 for the exact factory image:

```bash
sha256sum <CUSTOM_GATEWAY_OS_FACTORY_IMAGE>
```

Inspect the generated manifest and require the modem packages:

```bash
grep -E '^(kmod-usb-serial|kmod-usb-serial-wwan|kmod-usb-serial-option|kmod-usb-wdm|kmod-usb-net|kmod-usb-net-qmi-wwan|uqmi|luci-proto-qmi) ' \
  <CUSTOM_IMAGE_MANIFEST>
```

Also preserve:

```text
Gateway OS tag + full source commit
OpenWrt target = bcm27xx/bcm2709
custom .config hash
factory-image filename + SHA-256
manifest filename + SHA-256
build date/time in UTC
```

Do not flash an image whose manifest does not contain the intended modem support.

## 2A.10 First boot on spare media

Flash the custom **factory** image to a spare microSD card using the procedure in [Gateway 2](02-install-chirpstack-gateway-os.md).

Before restoring the production-like configuration, boot the spare card and verify only the platform/modem layer:

```sh
cat /etc/os-release
uname -r
opkg status kernel
opkg list-installed | grep -E '^kmod-usb-(serial-option|serial-wwan|net-qmi-wwan|wdm|net)'
lsmod | grep -E 'option|usb_wwan|qmi_wwan|cdc_wdm|usbserial'
ls -l /dev/ttyUSB* /dev/cdc-wdm* 2>/dev/null
ip -br link 2>/dev/null || ip link
logread | grep -Ei '1e0e|9001|option|ttyUSB|qmi|cdc-wdm|wwan' | tail -n 150
```

Expected direction for the current SIM7600G-H composition:

```text
1e0e:9001 detected
serial interfaces bind to option
/dev/ttyUSB* appears
higher data function binds only to the selected data driver when supported
/dev/cdc-wdm* and a WWAN network interface appear if QMI is active
```

Do not change the modem USB PID with `AT+CUSBPIDSWITCH` merely to make the expected output appear.

## 2A.11 Restore the gateway configuration only after driver proof

Once the spare-card image proves the modem drivers load correctly:

1. restore the protected Gateway OS configuration archive;
2. verify Gateway EUI remains `0016c001f139a1cb`;
3. verify Concentratord remains RAK5146 / AS923;
4. keep UDP Forwarder disabled;
5. verify MQTT Forwarder still targets `127.0.0.1:1883`;
6. verify Mosquitto remains loopback-only and persistent;
7. preserve the existing Wi-Fi management path during LTE commissioning;
8. name the future cellular logical interface `lte`, not `wwan`, because `wwan` is already the Wi-Fi management interface in this gateway.

Do not overwrite the original working microSD card until the rebuilt spare-card gateway passes the normal-path verification in Phase 11.

## 2A.12 Pass condition

This image-build branch passes when:

```text
source pinned to Gateway OS v4.12.0
Raspberry Pi Base bcm27xx/bcm2709 environment used
custom image manifest contains required SIM7600 serial drivers
stock OpenWrt foreign-ABI kmods were not installed
custom image boots on spare media
RAK5146 remains detected
SIM7600 1e0e:9001 binds to the intended drivers
/dev/ttyUSB* exists
QMI control/network interface exists if QMI is the proven data path
working gateway configuration can be restored without changing EUI/AS923 identity
original working SD card remains available for rollback
```

After this passes, return to [Phase 11](../../server/cloud-production/11-raspberry-pi-4g-backhaul.md) for SIM registration, APN, LTE routing, QoS 1 correction, and cloud MQTT commissioning.
