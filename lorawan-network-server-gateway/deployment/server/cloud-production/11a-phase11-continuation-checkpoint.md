# Phase 11A. Current Continuation Checkpoint

> **Purpose:** this file is the authoritative chat-to-chat continuation record for the active Raspberry Pi / SIM7600 work. A new troubleshooting session should read this file first, then [Phase 11](11-raspberry-pi-4g-backhaul.md), [Gateway 2A](../../gateway/setup/02a-build-sim7600-capable-gateway-os.md), and [Gateway Recovery](../../gateway/operations/02-backup-and-recovery.md). Do not infer a later PASS from an earlier command merely because the intended next command is documented.

## Current active state - 2026-08-27

**Phase 11 is ACTIVE. The custom ChirpStack Gateway OS image is currently compiling on the workstation.** The operator reported that the consolidated SIM7600 configuration/build block reached its compilation stage. The final build transcript, generated image filenames, manifest, and image SHA-256 have **not yet been captured**, so `PHASE11_CUSTOM_IMAGE_BUILD=PASS` must not be claimed yet.

The Raspberry Pi gateway is still running from its original SD card. No custom image has been flashed, the only SD card has not been overwritten, and the live LoRaWAN gateway must remain available until the single-card rollback gate is complete.

The build is intended to make one controlled change:

```text
ChirpStack Gateway OS 4.12.0 Base
+ same Raspberry Pi bcm27xx/bcm2709 target
+ existing RAK5146 / ChirpStack gateway stack
+ ABI-matched SIM7600 serial/QMI kernel support
```

It is **not** an OS upgrade, migration to Gateway OS Full, ChirpStack-server install on the Pi, or radio-plan change.

## Do not repeat these already-resolved steps

Do not restart the build process from scratch merely because a previous command failed. The following work is already complete and should be treated as evidence/history unless the source tree is intentionally destroyed:

```text
Ubuntu 24.04 WSL2 installation and first boot
GNU Make installation
Linux Docker Engine installation/start
Docker group access
Docker Compose v2 installation
Gateway OS v4.12.0 clone
source tag/commit pin
OpenWrt/chirpstack-feed submodule checkout
OpenWrt feed update/install
Raspberry Pi Base environment switch
Raspberry Pi target patch application
```

Specifically, do **not**:

```text
reinstall Docker or Docker Desktop
reclone the repository
rerun the expensive feed update/install because of the final quilt-init error
create a fake empty Quilt series
call openwrt/scripts/config as an executable
force-install stock OpenWrt kmods on the live gateway
use opkg --force-depends for modem modules
copy foreign .ko files into /lib/modules
use the generic usbserial new_id mechanism as the commissioned solution
send AT+CUSBPIDSWITCH during normal commissioning
overwrite the only SD card before rollback readiness passes
rename/replace the existing Wi-Fi logical interface wwan with LTE
```

## Physical gateway baseline

```text
Platform: Raspberry Pi 4B
LoRa concentrator: RAK5146 / SX1303 family
Gateway OS: ChirpStack Gateway OS 4.12.0 Base
Gateway OS build observed: r29197-ab4c7d6af7
Kernel: 6.6.141
Concentratord: chirpstack-concentratord-sx1302 4.7.1
MQTT Forwarder: 4.6.0
Region: AS923
Topic prefix: as923
Authoritative Gateway EUI: 0016c001f139a1cb
Inactive SX1301 placeholder EUI: 2ccf67fffe0abee3 - never use this as the gateway identity
```

The RAK5146 radio configuration was already working. Preserve it. The observed AS923 channel plan uses the existing 923.2-924.6 MHz configuration and must not be rewritten merely to add LTE.

Management networking before the custom image:

```text
Wi-Fi station: phy0-sta0
address: 192.168.8.11/24
default gateway: 192.168.8.1
OpenWrt logical interface name: wwan
```

`wwan` is therefore **Wi-Fi management**, not LTE. The future cellular logical interface name is `lte`.

## MQTT / delivery baseline on the gateway

The local store-and-forward topology already exists:

```text
ChirpStack MQTT Forwarder
  -> tcp://127.0.0.1:1883
  -> local Mosquitto persistent broker
  -> remote MQTT bridge
```

Current evidence:

```text
Mosquitto listener: 127.0.0.1:1883 only
persistence: enabled
persistence path: /etc/mosquitto/data/mosquitto.db
autosave: 60 seconds
max queued messages: 100000
max queued bytes: 104857600
UDP Forwarder: disabled
MQTT Forwarder topic prefix: as923
MQTT Forwarder Gateway EUI: 0016c001f139a1cb
MQTT Forwarder current QoS: 0
required commissioned QoS: 1
```

QoS `0 -> 1` is a known later bounded correction. Do not bypass local Mosquitto and do not mix that change into the kernel/image build.

The existing Mosquitto bridge remote is the old/test `lora-test-server:8883`. It is not proof of the final public cloud path. Final public gateway MQTT must eventually use `mqtt.<DOMAIN>:8883`, but Phase 10 provider-owned Reserved-IP/firewall/DNS activation is still pending. Do not substitute a Droplet public IP as the production endpoint.

## SIM7600 hardware evidence and why a custom image is required

The Waveshare SIM7600G-H is connected to the Raspberry Pi **by USB only**, which is the intended connection for this design; no UART wiring is required for the normal path.

The gateway detected the modem as:

```text
SIMTech USB VID:PID: 1e0e:9001
six USB interfaces: 0 through 5
all interfaces vendor-specific at the discovery checkpoint
all six interfaces unbound at the discovery checkpoint
```

There were no `/dev/ttyUSB*`, `/dev/cdc-wdm*`, or modem-created network interfaces on the original image. The existing generic USB serial subsystem is not enough for the commissioned deployment.

The important compatibility result is:

```text
running Gateway OS kernel package:
6.6.141~ce9a7c4f21afbe9986efeaec95ee2cce-r1

stock OpenWrt 24.10.7 bcm2709 modem kmods require:
6.6.141~910ca1d362cc3ff4f2a1d9a4e9759bc8-r1
```

Both use nominal Linux `6.6.141`, but their ABI hashes differ. This is not evidence that Linux 6.6.141 cannot support the SIM7600. The driver source is usable; the available **precompiled stock module binary** is for a different kernel build. Therefore the safe approach is to compile the modem modules together with the pinned Gateway OS kernel/configuration.

Direct live installation would be acceptable only if an exact-ABI `ce9a...` package set were obtained. None has been found in the configured/available feeds.

## Modem support selected for the custom image

The intended built-in package set is:

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

Existing PPP support must remain enabled as fallback. QMI is a **candidate**, not yet the proven runtime data path. After first boot, runtime evidence decides between QMI and PPP; do not assume `/dev/cdc-wdm*` will exist until the rebuilt kernel actually binds the data function.

## Build host and exact source pins

Workstation/build host:

```text
Windows 10 Pro
15.6 GiB RAM
8 logical CPU threads
126.8 GiB free on C: at preflight
WSL2
Ubuntu 24.04.4 LTS
Linux user: smartagriintern
build tree: /home/smartagriintern/src/chirpstack-gateway-os
Git: 2.43.0
GNU Make: 4.3
Docker client/server: 29.1.3
Docker OSType: linux
Docker architecture: x86_64
Docker Compose: 2.40.3+ds1-0ubuntu1~24.04.1
```

Docker Desktop is not required and is not part of the active path.

Pinned source evidence:

```text
Gateway OS tag: v4.12.0
Gateway OS commit: 2112dbdbda48cd77ec1b82499e389abd728e84a1
chirpstack-openwrt-feed commit: 2a959fab57cf5a49b843ceac4b0541169e831703
OpenWrt commit: b40dfac0a31695596f7c1f5f1519302ca8237f6e
OpenWrt release family: 24.10.7
Target environment: base_raspberrypi_bcm27xx_bcm2709
```

The Raspberry Pi environment switch already passed and applied these three real target patches:

```text
no-uart-console.patch
boot-config.patch
image-with-padded-rootfs.patch
```

## Build-host troubleshooting already resolved

### Intermittent WSL DNS

The WSL-generated resolver at `192.168.176.1` resolved `github.com` during `getent` probes but `git clone` failed seconds later with `Could not resolve host: github.com`. A reversible temporary resolver override was applied:

```text
nameserver 1.1.1.1
nameserver 8.8.8.8
options timeout:2 attempts:3
```

Five repeated lookups plus `git ls-remote` passed under that override and the source/feed downloads proceeded. Keep this temporary resolver in place while the active build might still need network downloads. Restore the original WSL-generated `/mnt/wsl/resolv.conf` link after source/package downloads are no longer needed.

### Docker Compose

Ubuntu `docker.io` did not initially include the Compose v2 plugin. `docker-compose-v2` was installed successfully and proved:

```text
Docker=29.1.3
Docker Compose version 2.40.3+ds1-0ubuntu1~24.04.1
```

### `make init` / Quilt

`make init` completed submodule and feed initialization, then its final `quilt init` returned:

```text
No series file found
```

Do not treat that as failed feed initialization. `QUILT_PATCHES` points to `conf/patches`, while the target-specific link is created by `switch-env`. The later Raspberry Pi `switch-env` successfully created the real links and `quilt push -a` applied all three target patches.

### OpenWrt config helper assumption

`openwrt/scripts/config` is a directory in this pinned tree, not the helper executable used in some other projects. The failed `./scripts/config --enable ...` command changed no modem package selection. The corrected procedure edits only the required `CONFIG_PACKAGE_*` lines and then uses `make defconfig` as the authoritative dependency normalization step.

## Active compilation checkpoint

The operator reported that the latest consolidated block is **still in the compilation stage**. The build command in that block is:

```bash
sudo docker compose run --rm chirpstack-gateway-os make -C openwrt -j4
```

The wrapper is designed to reach that command only after selecting the Raspberry Pi target, backing up the pre-modem config, requesting the eight modem packages, running `make defconfig`, and checking that all eight requested `CONFIG_PACKAGE_*` symbols equal `y`.

However, because the terminal output for those checks and the final build result has not yet been pasted into the project evidence, record the current state conservatively:

```text
TARGET_SWITCH = proven PASS
SIM7600 package request/defconfig = operator block reached compilation; final transcript not yet captured
CUSTOM IMAGE BUILD = ACTIVE / NOT YET PASS
CUSTOM IMAGE MANIFEST = NOT YET VERIFIED
CUSTOM IMAGE SHA-256 = NOT YET RECORDED
SD CARD WRITE = NOT STARTED
```

Do not start another build in parallel against the same tree. Let the current build finish or fail, then capture the first authoritative result.

## Single-SD rollback state

There is **no spare microSD card**. This is not an automatic blocker, but the only card must not be overwritten until the reflash-ready rollback gate is complete.

Already preserved off-gateway:

```text
C:\Users\smartagriintern\lorawan-recovery\gateway-01\20260826-082144

gateway-os-backup-20260826-082144.tar.gz
size: 15908 bytes
SHA-256: 572bfa3f45a69c5ed2ca99263988e8acf2e91ddb514f538520f62d5fb12488a1

gateway-critical-private-20260826-082144.tar.gz
size: 6188 bytes
SHA-256: f74fc55480bd4edf11a745118e15eae7afac43fff9daabcd64bb20aed4757db1
```

The critical bundle is secret-bearing. Never print its contents or commit it to Git.

The gateway `/tmp` copies were retained and should remain until the custom image and restore path have been proven.

Rollback preparation evidence captured while the custom image continued compiling:

```text
factory image copy:
C:\Users\smartagriintern\lorawan-recovery\gateway-01\factory-v4.12.0\chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz
size: 27606919 bytes
SHA-256: 395e79fe041c4118e10dd4cf796aa426a565d5e733144485d8d014a8d8dbf0a6

SHA256SUMS.txt: created beside the retained factory image

gateway-os-backup-20260826-082144.tar.gz: PASS on re-hash
gateway-critical-private-20260826-082144.tar.gz: PASS on re-hash

imaging software:
C:\Users\smartagriintern\AppData\Local\Programs\balena-etcher\balenaEtcher.exe
SD_WRITER_SOFTWARE=PASS

post-flash checklist:
C:\Users\smartagriintern\lorawan-recovery\gateway-01\factory-v4.12.0\PHASE11-POST-FLASH-CHECKLIST.txt

GATEWAY_SD_CARD_TOUCHED=NO
```

This closes the local factory-image preservation/hash, backup re-verification, imaging-software, and post-flash-checklist items. It does **not** by itself prove that a physical SD-card reader/writer path has been tested, and it does not record maintenance-window acceptance. Those remain required before the first write to the only production card. The custom-image manifest/hash verification remains pending. The operator now reports compilation has finished, but the final build result, generated artifact inventory, manifest package contents, and hashes have not yet been captured.

ChirpStack's official Raspberry Pi documentation maps Raspberry Pi 4B Base v4.12.0 to this factory artifact:

```text
https://artifacts.chirpstack.io/downloads/chirpstack-gateway-os/4.12.0/raspberrypi/bcm27xx/bcm2709/chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz
```

The `rpi-2` artifact name is expected for the shared bcm2709 image used by Raspberry Pi 2B, 3B/3B+, and 4B in the official download table. The workstation has now preserved a local copy with that exact artifact filename and recorded SHA-256 `395e79fe041c4118e10dd4cf796aa426a565d5e733144485d8d014a8d8dbf0a6`. This proves the identity of the retained local copy for later rollback comparison; it is not a substitute for a vendor-published checksum if one is separately available.

This recovery boundary is not a full block-level clone of the live card. Rollback means: flash the preserved official factory image onto the same card, boot, restore the verified configuration/private bundle, and re-verify the gateway identity/services.

## Productive work while compilation runs

These tasks are safe in parallel because they do not mutate the active OpenWrt source tree or gateway SD card:

```text
DONE - preserve/hash the factory rollback image
DONE - re-hash the two existing off-gateway backup files
DONE - confirm imaging software is installed
DONE - prepare the post-flash verification checklist
PENDING - confirm the physical SD-card reader/writer path is usable
PENDING - record SIM carrier/APN and whether the SIM requires a PIN

UPDATE 2026-08-27 - operator reports the custom Gateway OS compilation has finished. Build success has not yet been accepted because the final build exit/result and generated image/manifest evidence have not yet been captured. Do not flash yet.
```

The compile is now reported finished. Keep the live gateway SD card untouched until the custom image and rollback gate are fully verified. Restore the temporary WSL DNS override only after confirming no further source/package downloads are needed.

## Exact continuation when the current build ends

### If the build fails

Do not rerun `make init`, reclone, or re-switch the Raspberry Pi target. Capture the **first real compiler/package error**, preserve the current tree, and diagnose only that failing target. OpenWrt builds are incremental; do not throw away completed compilation without a concrete reason.

### If the build succeeds

First collect evidence; do not flash immediately:

```text
1. list files under openwrt/bin/targets/bcm27xx/bcm2709/
2. identify the Base factory image and matching manifest
3. calculate SHA-256 of the custom factory image
4. calculate SHA-256 of the manifest
5. calculate SHA-256 of the final custom target .config
6. verify all eight modem packages are present in the generated manifest
7. re-record Gateway OS tag/commit and target
8. record build completion time in UTC
```

The custom-image verification must explicitly contain:

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

If any required package is absent from the final manifest, do not flash.

After all source/package downloads are finished, restore the original WSL resolver rather than leaving the temporary public-DNS override as a permanent workstation change.

The factory-image/hash and imaging-software portions of the rollback gate are now evidenced. After the build succeeds, close the remaining physical SD reader/writer and maintenance-window checks. Only after **both** the custom-image verification and the complete single-card rollback gate pass may the planned SD write begin.

## First boot priorities after the custom image is flashed

Do not configure the carrier/APN first. Prove that the new image preserved the platform and added the intended kernel capability:

```text
Gateway OS release/kernel expected
RAK5146 detected
Concentratord starts
Gateway EUI = 0016c001f139a1cb
AS923 remains selected
SIM7600 1e0e:9001 detected
option / usb_wwan modules load as expected
/dev/ttyUSB* appears
inspect whether /dev/cdc-wdm* appears
inspect whether a modem network interface appears
```

Only runtime evidence decides the data path:

```text
/dev/cdc-wdm* + WWAN/QMI interface -> evaluate QMI
serial ports but no QMI control/network device -> evaluate PPP fallback
```

Do not send `AT+CUSBPIDSWITCH` merely to force the expected topology.

After the modem driver proof, restore/re-verify the gateway configuration and confirm:

```text
RAK5146 / AS923 unchanged
Gateway EUI unchanged
Wi-Fi management still available
logical wwan still belongs to Wi-Fi
MQTT Forwarder still points to tcp://127.0.0.1:1883
local Mosquitto remains loopback-only and persistent
UDP Forwarder remains disabled
```

## Safe SIM/LTE interrogation after serial ports exist

The first AT checks are read-only/safe:

```text
ATI
AT+CPIN?
AT+CSQ
AT+CEREG?
```

Do not place SIM PINs, APN passwords, or private credentials in the repository or normal chat transcript.

After the actual modem mode is proven, configure the cellular path as logical interface `lte`, preserving Wi-Fi `wwan` throughout LTE commissioning. No inbound LTE forwarding is required.

## Phase 11 normal-path completion after LTE works

Phase 11 still needs normal-path commissioning after the kernel/image branch succeeds:

```text
SIM registration
carrier/APN configuration
LTE IP/default-route behavior
preserved Wi-Fi management path during commissioning
MQTT Forwarder QoS correction from 0 to 1
local Mosquitto persistent store-and-forward verification without outage injection
cloud MQTT endpoint/certificate verification when Phase 10 public provider/DNS side is available
```

Intentional LTE outage, gateway reboot, broker-loss, and queue-drain failure experiments belong to **Phase 15**, not Phase 11.

## Cross-phase context

Cloud core state entering this work:

```text
Phase 9 ChirpStack cloud cluster: COMPLETE / PASS
Phase 10 host-owned public ingress work: COMPLETE for host-owned boundary
Phase 10 provider Reserved-IP/firewall/public DNS/public-PKI activation: still externally pending
Current operator has no DigitalOcean panel access; do not send the operator back to that panel
Phase 11: ACTIVE - current task
Phase 13A: pre-cutover backup/restore work was paused for Phase 11 after read-only preflight
Phase 12: blocked until both Phase 11 normal-path commissioning and Phase 13A PASS
Phase 15: blocked until the full pre-test commissioning gate passes
```

Authoritative remaining order:

```text
Phase 11
-> Phase 13A
-> Phase 12
-> Phase 12A Node-RED / TimescaleDB
-> Phase 14A Grafana
-> Phase 20 OpenBao / Fabric
-> Phase 13B
-> Phase 14 healthy evidence
-> Phase 14B hard go/no-go
-> Phase 15 first intentional failure injection
```

## Operator / troubleshooting conventions to preserve

Use a streamlined workflow: batch independent read-only checks, but place real state changes behind verification gates. Do not create a new micro-phase for every successful probe.

For the Raspberry Pi Gateway OS, remember it is OpenWrt/ChirpStack Gateway OS; do not assume Ubuntu/systemd commands are available. For workstation build commands, distinguish Windows PowerShell from Ubuntu WSL explicitly.

When a command fails after earlier stages passed, resume from the first unresolved boundary. Do not automatically repeat expensive or risky passed stages.

## Handoff acceptance

A new chat has enough context to resume when it can answer all of these without guessing:

```text
What is compiling? ChirpStack Gateway OS 4.12.0 Base for bcm27xx/bcm2709 with SIM7600 support.
Is the build done? Compilation and Stage 1 artifact/manifest verification PASS; final pre-flash integrity/preservation and single-card readiness gates are still pending.
Has the gateway been flashed? No.
Why not install stock kmods? Exact kernel ABI hash mismatch.
What is the Gateway EUI? 0016c001f139a1cb.
What is the region? AS923 / prefix as923.
How is SIM7600 connected? USB only; 1e0e:9001.
What is the future LTE interface name? lte; existing wwan is Wi-Fi.
What is the current MQTT gap? Forwarder QoS 0 must later become QoS 1.
Is QMI proven? No; QMI is a candidate and PPP remains fallback.
Is there a spare SD card? No.
What blocks flashing? Generated sha256sums verification, off-WSL preservation of the custom artifacts/evidence, physical SD reader/writer confirmation, and maintenance-window acceptance.
What should happen now that compilation has finished? Capture the build result, identify the generated factory image and manifest, verify all eight required modem packages, and record image/manifest/.config hashes before any SD write.
```

## Build-finished continuation checkpoint - 2026-08-27

The operator reports that the custom ChirpStack Gateway OS compilation has finished. Treat this as **build process finished, verification pending**, not yet as `BUILD=PASS`. No SD-card write has occurred.

Immediate next boundary:

```text
1. capture the final build exit/result without rebuilding
2. list openwrt/bin/targets/bcm27xx/bcm2709/ artifacts
3. identify the custom Base factory image and matching manifest
4. verify all eight required SIM7600 packages are present in the manifest
5. calculate SHA-256 for factory image, manifest, and final openwrt/.config
6. re-record Gateway OS tag/commit and bcm27xx/bcm2709 target
7. record build completion time in UTC
8. only then close the custom-image verification gate
```

Required manifest packages remain:

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

Do not rebuild merely because the verification evidence was not captured during the original command. Inspect the existing build outputs first. Do not flash the only production SD card until this image gate and the remaining physical SD-reader/maintenance-window rollback checks pass.
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
