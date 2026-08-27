# Gateway 2A. Build a SIM7600-Capable ChirpStack Gateway OS Image

Use this manual only when the official ChirpStack Gateway OS Base image does not contain kernel modules required by the Waveshare SIM7600G-H.

The current Phase 11 evidence requires this branch. Gateway OS `4.12.0` on Raspberry Pi 4B runs kernel `6.6.141~ce9a7c4f21afbe9986efeaec95ee2cce-r1`, while the stock OpenWrt `24.10.7` kmods repository for the same nominal kernel release requires `6.6.141~910ca1d362cc3ff4f2a1d9a4e9759bc8-r1`. These ABI hashes are different. Do not force-install the stock modules into the Gateway OS kernel.

The durable repair is to build the Gateway OS image from its own pinned source/configuration with the modem support selected before the kernel and image are compiled. Direct installation on the live gateway would be acceptable only if a `kmod-*` package set built for the **exact same Gateway OS kernel ABI** were available; the stock OpenWrt packages proven in Phase 11 are not. Do not force those packages or manually copy foreign `.ko` files into `/lib/modules`.

The build host does not have to be Docker Desktop specifically. Any supported Linux environment with a working Docker engine is sufficient for the Gateway OS build. On the current workstation, Ubuntu 24.04 under WSL2 may run its own Linux Docker engine, which is simpler than depending on Docker Desktop WSL integration if Desktop is not already usable.

## 2A.1 Result

**Design invariant:** this remains ChirpStack Gateway OS **Base**, not Raspberry Pi OS, Ubuntu, or a generic writable OpenWrt install. Preserve the Gateway OS storage model: an immutable/read-only SquashFS base root filesystem with the normal writable OverlayFS persistence layer on top. The custom build must add only the required modem support and must not convert the image to a conventional fully writable root filesystem, replace the Base profile with Gateway OS Full, or bypass the normal Gateway OS sysupgrade/overlay recovery model.

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

`OFF_GATEWAY_ROLLBACK_COPY=PASS` and `CUSTOM_IMAGE_BUILD_ALLOWED=YES` prove the configuration/private recovery artifacts are preserved. A **spare microSD card is preferred but not mandatory**. If no spare card is available, use a controlled single-card reflash path: before overwriting the current card, preserve the exact official Gateway OS `4.12.0` Raspberry Pi Base image outside the gateway, calculate and record its SHA-256, confirm the workstation can write an SD image, keep the verified configuration/private recovery bundles available, and accept planned gateway downtime during rollback. Do not overwrite the only card until those reflash prerequisites pass. Retain the gateway `/tmp` copies until the custom image has booted and the restore boundary has been verified.

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

### Current build-host state - 2026-08-27

The workstation is already adequate for the build: Windows 10 Pro, `15.6 GiB` RAM, `8` logical CPU threads, `126.8 GiB` free on `C:`, WSL2, and Ubuntu `24.04.4 LTS`. The Linux account `smartagriintern` is initialized with `sudo`, Git `2.43.0` is present, Internet/DNS works, and the Linux filesystem has ample space. Keep the build tree under `/home/smartagriintern/src`, not `/mnt/c`.

GNU `make` and the native Linux Docker toolchain are now installed and proven inside Ubuntu WSL2. GNU Make reports `4.3`; Docker client/server report `29.1.3` with `OSType=linux` and `Architecture=x86_64`; Docker Compose v2 was subsequently installed and reports `2.40.3+ds1-0ubuntu1~24.04.1`. Docker Desktop remains optional and is not used by the active build path.

The build workspace is `/home/smartagriintern/src/chirpstack-gateway-os`. An intermittent WSL DNS regression was isolated to the WSL-generated resolver `192.168.176.1`: direct lookups could pass while `git clone` failed seconds later. A reversible temporary `/etc/resolv.conf` using `1.1.1.1` and `8.8.8.8` passed five repeated lookups plus `git ls-remote`; keep that temporary resolver only while the build may still need source/package downloads.

The repository then cloned successfully and is pinned to Gateway OS tag `v4.12.0`, commit `2112dbdbda48cd77ec1b82499e389abd728e84a1`. Pinned submodules are `chirpstack-openwrt-feed` at `2a959fab57cf5a49b843ceac4b0541169e831703` and OpenWrt at `b40dfac0a31695596f7c1f5f1519302ca8237f6e`.

The initial Compose blocker (`unknown flag: --rm`) is **resolved**, not current. `make init` then completed the expensive feed update/install and stopped only on the final pre-environment `quilt init` with `No series file found`; the later target switch resolved the real patch path and successfully applied the Raspberry Pi target patches. The Raspberry Pi Base environment is therefore already selected. Do not rerun Docker installation, clone, feed installation, or target switching merely to reproduce earlier evidence.

The next attempted non-interactive package edit failed before changing modem package state because `openwrt/scripts/config` is a directory in this pinned tree. The corrected build block uses minimal `.config` updates plus `make defconfig` and an eight-package verification gate. The operator reports that this corrected block has reached the compilation stage and is still compiling. Final image/manifest/hash output has not yet been captured, so the build remains **ACTIVE / NOT YET PASS**. See [Phase 11A - Current Continuation Checkpoint](../../server/cloud-production/11a-phase11-continuation-checkpoint.md) before resuming in a new session.

The earlier H-1/H-2/H-3/H-4A probes are retained as historical evidence in the Phase 11 deployment log, not as separate operator gates. From this point use one streamlined build flow:

```text
Ubuntu WSL2
  -> install/verify make + Linux Docker
  -> clone Gateway OS v4.12.0 under Linux home
  -> select bcm27xx/bcm2709 Base
  -> add only SIM7600 serial/QMI packages
  -> build
  -> verify image/manifest/hash
  -> confirm single-card rollback is reflash-ready
  -> planned reflash
  -> verify RAK5146 + Gateway EUI + AS923 + SIM7600
```

Stop only on a real safety/correctness failure: build dependency unavailable, wrong target/release, required package missing, build/hash verification failure, or rollback prerequisites incomplete. Do not create a new micro-phase merely for a successful read-only command.

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

### Current v4.12.0 initialization compatibility note - 2026-08-27

On the current build host, `make init` completed the expensive/required initialization work successfully: both pinned submodules were checked out, all OpenWrt feeds were updated, and all feeds were installed. It then stopped only on its final command:

```text
docker compose run --rm chirpstack-gateway-os quilt init
No series file found
make: *** [Makefile:17: init] Error 1
```

Do **not** repeat the feed update/install after this exact failure. The upstream Compose environment sets `QUILT_PATCHES=/workdir/conf/patches`, while the upstream `switch-env` target creates the `conf/patches` symlink only after a target environment is selected. With the current Debian `stable-slim` Quilt package, `quilt init` rejects the missing `series` file before that target link exists. Treat this as an initialization-order/tool-version compatibility issue, not a failed OpenWrt feed initialization.

For this exact state, continue directly with `make switch-env ENV=base_raspberrypi_bcm27xx_bcm2709` inside the build container. Its initial `quilt pop -a` is intentionally non-fatal, then it creates the target `.config`, `files`, and `patches` symlinks and applies the target patch series. Pass only if the target patch series exists and `quilt push -a` completes successfully. Do not create an ad-hoc empty `series`, alter the upstream Makefile, or rerun all feed installation merely to make the final `quilt init` return zero.

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

The Raspberry Pi Base environment switch has already passed and applied all three target patches. On this pinned OpenWrt tree, `openwrt/scripts/config` is a **directory containing the Kconfig implementation**, not the command-line helper used by some other projects. Do not call `./scripts/config --enable ...`.

For an interactive build, the upstream-supported method remains:

```bash
cd openwrt
make menuconfig
```

For this reproducible Phase 11 build, use the equivalent non-interactive `.config` update: remove any existing value or `not set` line for only the required package symbols, append `=y`, then let OpenWrt `make defconfig` resolve and validate dependencies. This is the same `.config` input path used by OpenWrt's build system; `defconfig` is the authoritative normalization step.

Required packages:

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

Keep the existing Gateway OS Base selections and existing PPP support. Do not deselect RAK/ChirpStack packages and do not add unrelated modem frameworks merely because they are present in the feeds.

After the eight symbols are changed, run:

```bash
make defconfig
```

Then prove the intended package selection before compiling:

```bash
grep -E '^CONFIG_PACKAGE_(kmod-usb-serial|kmod-usb-serial-wwan|kmod-usb-serial-option|kmod-usb-wdm|kmod-usb-net|kmod-usb-net-qmi-wwan|uqmi|luci-proto-qmi)=' .config
```

All eight packages must resolve to `=y`. If `make defconfig` removes or changes any requested symbol, stop and inspect that symbol's dependencies instead of forcing the build.

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

## 2A.8A Use compile time for independent rollback/readiness work

While the custom image is compiling, prepare only items that do not mutate the active source tree or the gateway SD card:

1. Download the official ChirpStack Gateway OS `4.12.0` Raspberry Pi 4B **Base factory image** from the ChirpStack Raspberry Pi download page and calculate its SHA-256 locally. Keep both the image and hash outside the gateway as the single-card rollback source.
2. Re-verify the existing off-gateway sysupgrade archive and protected Mosquitto/configuration bundle against their already-recorded SHA-256 values. Do not open or print secret-bearing file contents.
3. Confirm the workstation has an SD-card reader/writer and an imaging application ready, but do **not** remove or overwrite the gateway's only card while the build is running.
4. Record the carrier/APN information for the installed SIM, including whether the SIM requires a PIN. Do not send USB-mode-changing AT commands.
5. Keep a post-flash verification sheet ready for: Gateway OS release/kernel, RAK5146, Gateway EUI `0016c001f139a1cb`, AS923, Wi-Fi management, Mosquitto persistence, MQTT Forwarder local endpoint, UDP Forwarder disabled state, SIM7600 USB binding, `/dev/ttyUSB*`, and QMI/PPP evidence.
6. Keep the temporary WSL DNS override in place until all source/package downloads are finished; restore the original WSL resolver only after the build no longer needs network access.

These preparations may run in parallel with compilation because they do not alter `openwrt/.config`, build outputs, the running gateway, or its SD card.

### Current parallel-preparation result - 2026-08-27

The operator completed the non-destructive rollback preparation while the custom image continued compiling:

```text
factory rollback artifact:
C:\Users\smartagriintern\lorawan-recovery\gateway-01\factory-v4.12.0\chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz
size: 27606919 bytes
SHA-256: 395e79fe041c4118e10dd4cf796aa426a565d5e733144485d8d014a8d8dbf0a6

existing sysupgrade backup re-hash: PASS
existing protected configuration/private backup re-hash: PASS

SD imaging software:
C:\Users\smartagriintern\AppData\Local\Programs\balena-etcher\balenaEtcher.exe
SD_WRITER_SOFTWARE=PASS

post-flash checklist:
C:\Users\smartagriintern\lorawan-recovery\gateway-01\factory-v4.12.0\PHASE11-POST-FLASH-CHECKLIST.txt

GATEWAY_SD_CARD_TOUCHED=NO
```

Treat these as completed prerequisites. Do not confuse `SD_WRITER_SOFTWARE=PASS` with proof that the physical SD reader/writer path has been exercised. Before the only production card is overwritten, still confirm the physical reader/writer path and accept the maintenance-window downtime. Carrier/APN/PIN information also remains a later LTE-commissioning input.



### Build-finished status - 2026-08-27

The operator reports that the Phase 11 custom Gateway OS compilation has finished. This does **not** yet close the build branch: the final command result and generated artifacts still require verification. Preserve the existing build tree and inspect it incrementally; do not rerun `make`, `make init`, or the target switch unless evidence shows the build actually failed or an artifact is missing.

Before flashing, capture and verify the existing outputs exactly as described in section 2A.9. In particular, require all eight modem packages in the generated manifest and record SHA-256 for the factory image, manifest, and final `.config`. The production SD card remains untouched.

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

## 2A.10 First boot on spare or controlled single-card media

A spare microSD card remains the preferred first-boot path. When only the single production card exists, do not write it until the reflash-ready rollback gate is closed. Current evidence already covers the Gateway OS `4.12.0` Base factory artifact plus local SHA-256, the verified configuration/private recovery bundles, and installed imaging software. Still require a confirmed physical SD reader/writer path, maintenance-window acceptance, and a successfully verified custom image/manifest before writing the card.

Flash the custom **factory** image using the procedure in [Gateway 2](02-install-chirpstack-gateway-os.md). On the single-card path, this is the planned maintenance-window cutover and rollback means reflashing that same card with the preserved official factory image before restoring the verified backups.

Before restoring the production-like configuration, boot the custom image and verify only the platform/modem layer:

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

Once the custom image proves the modem drivers load correctly on the selected spare-card or controlled single-card path:

1. restore the protected Gateway OS configuration archive;
2. verify Gateway EUI remains `0016c001f139a1cb`;
3. verify Concentratord remains RAK5146 / AS923;
4. keep UDP Forwarder disabled;
5. verify MQTT Forwarder still targets `127.0.0.1:1883`;
6. verify Mosquitto remains loopback-only and persistent;
7. preserve the existing Wi-Fi management path during LTE commissioning;
8. name the future cellular logical interface `lte`, not `wwan`, because `wwan` is already the Wi-Fi management interface in this gateway.

If spare media is available, keep the original working microSD card untouched until the rebuilt gateway passes normal-path verification. On the single-card path, do not begin the first write until the reflash-ready rollback gate above is complete; after writing, retain every off-gateway rollback artifact until normal-path verification passes.

## 2A.12 Pass condition

This image-build branch passes when:

```text
source pinned to Gateway OS v4.12.0
Raspberry Pi Base bcm27xx/bcm2709 environment used
custom image manifest contains required SIM7600 serial drivers
stock OpenWrt foreign-ABI kmods were not installed
custom image boots on the selected spare-card or controlled single-card path
RAK5146 remains detected
SIM7600 1e0e:9001 binds to the intended drivers
/dev/ttyUSB* exists
QMI control/network interface exists if QMI is the proven data path
working gateway configuration can be restored without changing EUI/AS923 identity
rollback remains possible through the preserved official factory image plus verified off-gateway configuration/private backups
```

After this passes, return to [Phase 11](../../server/cloud-production/11-raspberry-pi-4g-backhaul.md) for SIM registration, APN, LTE routing, QoS 1 correction, and cloud MQTT commissioning.
### Post-build verifier correction - 2026-08-27

**Observed verifier-only failure.** The first post-build output check was launched from `/mnt/c/Users/smartagriintern`, so `git describe` / `git rev-parse` failed with `not a git repository` before any build artifact was inspected. This does **not** establish that the Gateway OS build failed. The operator login shell survived and no SD-card write occurred.

A second issue was found in that verifier before retry: it converted package names such as `kmod-usb-serial` to underscores when constructing `CONFIG_PACKAGE_...` symbols. OpenWrt package configuration symbols retain the package-name hyphens (for example `CONFIG_PACKAGE_kmod-usb-serial=y`). The corrected verifier must therefore `cd ~/src/chirpstack-gateway-os` explicitly and test the exact hyphenated symbols.

Do not rebuild. Resume from read-only output verification only. Do not flash until image, manifest, required package membership, and hashes are all proven.

### Custom-image Stage 1 verification PASS - 2026-08-27

The corrected read-only post-build verifier completed successfully. The earlier verifier failure was only a wrong-working-directory/script issue and did not invalidate the build.

Verified source and target:

```text
Gateway OS tag: v4.12.0
Gateway OS commit: 2112dbdbda48cd77ec1b82499e389abd728e84a1
OpenWrt target: bcm27xx/bcm2709
```

All eight required SIM7600 packages are present in both the final OpenWrt `.config` and the generated image manifest:

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

Generated factory image:

```text
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz
size: 27672032 bytes
SHA-256: 1540958a7247e78e0e0d6791e3550f5d608865e940fc7463a5ff68229199bc3f
```

Generated manifest:

```text
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2.manifest
size: 8009 bytes
SHA-256: 49ea8900d5edccd89bafb6868f7918b71eb28c15481b67e390d69b6e7d513561
```

Final OpenWrt configuration SHA-256:

```text
d17b44d29cbfc54ef40734532ee5ce900c9ff110b95c9f5107f54bbb0753cdfa
```

The target directory also contains a generated `sha256sums` file. Stage 1 establishes that the intended factory image exists and that its manifest contains the complete required modem package set. Before any SD-card write, still verify the generated `sha256sums` against the produced artifacts, preserve the custom build evidence outside the WSL build tree, restore the temporary WSL DNS after preservation, confirm the physical SD reader/writer path, and explicitly accept the maintenance-window downtime.

`GATEWAY_SD_CARD_TOUCHED=NO` remains authoritative.
