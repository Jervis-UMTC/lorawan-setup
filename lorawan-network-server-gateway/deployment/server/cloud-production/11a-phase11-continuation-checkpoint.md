# Phase 11A. Current Continuation Checkpoint

> **Purpose:** this file is the authoritative chat-to-chat continuation record for the active Raspberry Pi / SIM7600 work. A new troubleshooting session should read this file first, then [Phase 11](11-raspberry-pi-4g-backhaul.md), [Gateway 2A](../../gateway/setup/02a-build-sim7600-capable-gateway-os.md), and [Gateway Recovery](../../gateway/operations/02-backup-and-recovery.md). Do not infer a later PASS from an earlier command merely because the intended next command is documented.

## Current active state - 2026-08-28

**Phase 11 is ACTIVE, but the SIM7600/QMI LTE commissioning path is now proven through real public IPv4 traffic.** The custom ChirpStack Gateway OS image has already been built, flashed to the production SD card, booted, verified, and restored with the gateway's known configuration/private material. Do not return to the build/flash workflow unless the current image is intentionally replaced or a later runtime failure specifically points back to the image.

Current authoritative gateway state:

```text
Gateway OS custom image with SIM7600 drivers     PASS
RAK5146 / gateway runtime restored                PASS
Gateway EUI 0016c001f139a1cb                     PASS
local Mosquitto 127.0.0.1:1883                   PASS
MQTT Forwarder local path                         PASS
cloud gateway client certificate installed        PASS
Wi-Fi management wwan = 192.168.8.11/24          PASS
unintended DHCP server on wwan disabled            PASS
SIM7600 AT-capable port /dev/ttyUSB2              PASS
SIM PIN state = READY                              PASS
DITO LTE registration                             PASS
DITO APN = internet.dito.ph                       PASS
QMI control /dev/cdc-wdm0                         PASS
kernel modem netdev wwan0                         PASS
logical OpenWrt cellular interface lte             PASS
QMI data session / dynamic lte_4                  PASS
LTE IPv4 100.73.25.125/30                         PASS
carrier gateway 100.73.25.126                     PASS
public IPv4 traffic over DITO LTE                 PASS
```

The complete successful command sequence, expected outputs, and technical reasons are consolidated in [Phase 11 section 11.9 - Verified SIM7600 / DITO QMI commissioning path](11-raspberry-pi-4g-backhaul.md#119-verified-sim7600--dito-qmi-commissioning-path---2026-08-28). Use that section instead of reconstructing the sequence from the troubleshooting history below.

Current network staging rules:

```text
Ethernet: keep unplugged during this staging phase
Wi-Fi logical interface: wwan
Wi-Fi kernel device: phy0-sta0
Wi-Fi management IP: 192.168.8.11/24
SIM7600 logical interface: lte
SIM7600 kernel device: wwan0
QMI control: /dev/cdc-wdm0
network.lte.defaultroute='0'
network.lte.peerdns='0'
```

Ethernet remains unplugged because Ethernet `br-lan` and Wi-Fi `phy0-sta0` were simultaneously attached to the same `192.168.8.0/24` network during commissioning, creating route ambiguity. The restored `dhcp.wwan` server was separately disabled with `dhcp.wwan.ignore=1`; do not re-enable DHCP service on the upstream Wi-Fi client interface.

The last verified LTE data session created dynamic child interface `lte_4` on `wwan0` with IPv4 `100.73.25.125/30`, carrier gateway/DHCP server `100.73.25.126`, and carrier DNS `131.226.72.19` / `131.226.73.19`. A temporary `/32` route forced `1.1.1.1` through DITO; the route lookup selected `wwan0`, the ping returned replies with exit status 0, and the temporary route was removed. The observed 50% packet loss is a later quality-monitoring item, not a commissioning blocker.

**Do not promote LTE to the normal/default route yet.** The next real blocker is the production public MQTT path: real `mqtt.<DOMAIN>:8883`, same-region Reserved Public IPv4, provider firewall allowance for `8883/tcp`, public DNS, and a broker certificate valid for the real MQTT hostname. The gateway bridge still points at the retired lab endpoint and must not be repointed until the production public endpoint exists and is ready for mTLS validation.

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

This closes the local factory-image preservation/hash, backup re-verification, imaging-software, and post-flash-checklist items. The custom-image build, manifest/hash verification, generated `sha256sums` integrity check, off-WSL preservation, and DNS restoration have since passed. The only remaining gates before the first write to the single production card are a proven physical SD reader/writer path and explicit maintenance-window acceptance.

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

The custom build is now compiled, verified, integrity-checked, and preserved off WSL. The WSL resolver is restored and healthy. Keep the live gateway SD card untouched until the physical reader/writer and maintenance-window gates are closed.

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
Is the build done? Compilation plus Stage 1 artifact/manifest verification and Stage 2 generated-sha256sums integrity verification PASS; off-WSL preservation PASS; DNS restoration plus the remaining single-card readiness gates are still pending.
Has the gateway been flashed? No.
Why not install stock kmods? Exact kernel ABI hash mismatch.
What is the Gateway EUI? 0016c001f139a1cb.
What is the region? AS923 / prefix as923.
How is SIM7600 connected? USB only; 1e0e:9001.
What is the future LTE interface name? lte; existing wwan is Wi-Fi.
What is the current MQTT gap? Forwarder QoS 0 must later become QoS 1.
Is QMI proven? No; QMI is a candidate and PPP remains fallback.
Is there a spare SD card? No.
What blocks flashing? Confirm the physical SD reader/writer path and explicitly accept the maintenance window.
What should happen next? Close the physical SD reader/writer gate, then record explicit maintenance-window/cutover acceptance before any SD write.
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

### Custom-image Stage 2 artifact-integrity PASS - 2026-08-28

The read-only artifact-integrity gate completed successfully without rebuilding, changing DNS, or touching the gateway SD card. The previously recorded factory-image, manifest, and final OpenWrt `.config` hashes were reverified exactly.

Generated `sha256sums` verification passed for every listed target artifact:

```text
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz: OK
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-sysupgrade.img.gz: OK
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2.manifest: OK
config.buildinfo: OK
feeds.buildinfo: OK
profiles.json: OK
version.buildinfo: OK
```

Authoritative hashes remain:

```text
factory image SHA-256: 1540958a7247e78e0e0d6791e3550f5d608865e940fc7463a5ff68229199bc3f
manifest SHA-256: 49ea8900d5edccd89bafb6868f7918b71eb28c15481b67e390d69b6e7d513561
final openwrt/.config SHA-256: d17b44d29cbfc54ef40734532ee5ce900c9ff110b95c9f5107f54bbb0753cdfa
sha256sums SHA-256: 73ff93c061d87b9e4231776dcb420382a8e539646b64847b8e10ed4498f67e90
```

Reliable UTC mtimes recorded from filesystem epoch timestamps:

```text
factory image: 2026-08-27T05:53:55Z
manifest: 2026-08-27T05:53:56Z
sha256sums: 2026-08-27T05:54:10Z
integrity verification: 2026-08-28T00:46:41Z
```

The factory image and manifest are both explicitly listed in the generated `sha256sums`. Stage 2 closes the custom-build artifact-integrity gate. Remaining pre-flash work is: preserve the verified custom artifacts and evidence outside WSL, verify the copied hashes, restore the temporary WSL DNS only after preservation, confirm the physical SD reader/writer path, and accept the maintenance-window downtime.

`BUILD_REEXECUTED=NO`, `DNS_CHANGED=NO`, and `GATEWAY_SD_CARD_TOUCHED=NO` remain authoritative for this gate.
### Custom-image Stage 3 off-WSL preservation PASS - 2026-08-28

The verified custom Gateway OS output set was copied from the WSL build tree to Windows recovery storage and revalidated there without rebuilding, changing DNS, or touching the production SD card.

Preserved location:

```text
C:\Users\smartagriintern\lorawan-recovery\gateway-01\custom-v4.12.0-sim7600-20260827
```

The preserved set includes the factory image, sysupgrade image, manifest, `config.buildinfo`, `feeds.buildinfo`, `profiles.json`, generated `sha256sums`, `version.buildinfo`, a copy of the final OpenWrt `.config`, and a non-secret build-identity record.

Windows-side revalidation passed exactly:

```text
factory image SHA-256: 1540958a7247e78e0e0d6791e3550f5d608865e940fc7463a5ff68229199bc3f
manifest SHA-256: 49ea8900d5edccd89bafb6868f7918b71eb28c15481b67e390d69b6e7d513561
final OpenWrt .config SHA-256: d17b44d29cbfc54ef40734532ee5ce900c9ff110b95c9f5107f54bbb0753cdfa
generated sha256sums SHA-256: 73ff93c061d87b9e4231776dcb420382a8e539646b64847b8e10ed4498f67e90
```

Running `sha256sum -c sha256sums` against the Windows-side preserved target directory also returned `OK` for every generated artifact listed by OpenWrt. This closes the off-WSL custom-build preservation gate.

The DNS restoration gate is now complete. Remaining pre-flash gates are only: confirm the physical SD reader/writer path and explicitly accept the maintenance-window downtime before writing the only production card.

`BUILD_REEXECUTED=NO`, `DNS_CHANGED=NO`, and `GATEWAY_SD_CARD_TOUCHED=NO` remain authoritative for this preservation gate.
### Custom-image Stage 4 WSL DNS restoration PASS - 2026-08-28

The temporary public-DNS workaround is no longer active. `/etc/resolv.conf` was already restored to the normal WSL-generated symlink `/mnt/wsl/resolv.conf`, whose current resolver is `192.168.176.1`. Five consecutive `getent ahosts github.com` checks passed, so no DNS rollback was required.

Verified boundary:

```text
WSL_GENERATED_RESOLVER_PRESENT=PASS
WSL_DNS_ALREADY_RESTORED=YES
WSL_RESOLV_LINK_RESTORED=ALREADY_PRESENT
WSL_RESOLV_LINK_VERIFIED=PASS
dns_lookup_1=PASS
dns_lookup_2=PASS
dns_lookup_3=PASS
dns_lookup_4=PASS
dns_lookup_5=PASS
ORIGINAL_WSL_DNS_VALIDATION=PASS
DNS_OVERRIDE_RESTORED=YES
BUILD_REEXECUTED=NO
GATEWAY_SD_CARD_TOUCHED=NO
PHASE11_WSL_DNS_RESTORE=PASS
PHASE11_WSL_DNS_RESTORE_EXIT=0
LOGIN_SHELL_SURVIVED=YES
```

The custom build, artifact integrity, off-WSL preservation, and workstation DNS cleanup gates are now closed. The physical SD reader/removable disk path is now proven. The only remaining prerequisite before shutdown/card removal is explicit maintenance-window/cutover acceptance. Do not flash until that approval is given.

### Phase 11 physical SD reader preflight shell-context failure - 2026-08-28

The first physical SD reader preflight did **not** execute because the Windows PowerShell block was pasted into the Ubuntu/WSL Bash shell. Bash rejected PowerShell syntax (`& {`, `Write-Host`, `Get-CimInstance`, `Get-PnpDevice`) before any Windows disk or PnP inventory was performed. Treat this as a shell-context/verifier failure only, not as an SD-reader hardware failure.

Authoritative safety boundary from the failed attempt:

```text
PHYSICAL_SD_READER_PREFLIGHT=NOT_EXECUTED
DISK_WRITE_EXECUTED=NO
DISK_INITIALIZE_EXECUTED=NO
DISK_FORMAT_EXECUTED=NO
IMAGE_WRITE_EXECUTED=NO
GATEWAY_SD_CARD_REMOVED=NO
PRODUCTION_SD_CARD_TOUCHED=NO
```

Retry by invoking Windows PowerShell explicitly from WSL or by running the block in a native Windows PowerShell prompt. Do not remove the production microSD until the empty-reader hardware baseline has passed.
### Streamlined Phase 11 cutover convention - 2026-08-28

From this checkpoint onward, avoid repeating already-passed build, checksum, preservation, DNS, imaging-software, and rollback checks unless a later failure gives a concrete reason. The remaining workflow is intentionally simple:

1. confirm Windows sees the SD reader / intended removable disk;
2. accept the maintenance-window downtime;
3. flash the verified custom factory image;
4. boot the gateway and verify Gateway OS, LoRa radio, Wi-Fi management, packet forwarding, and SIM7600 driver presence;
5. continue LTE commissioning only if those checks work.

A working result is sufficient evidence. Do not add extra test layers merely to restate already-proven state.

The PowerShell reader-preflight attempt that was blocked by Windows script execution policy is a launcher issue only, not a hardware failure. `PRODUCTION_SD_CARD_TOUCHED=NO` remains authoritative.

### Physical SD reader / removable disk detection PASS - 2026-08-28

Windows detected the connected SD reader/media path clearly enough for cutover:

```text
Disk 1
Model: Mass Storage Device USB Device
InterfaceType: USB
MediaType: Removable Media
Size: 31946987520 bytes
```

Treat this as sufficient physical reader/disk evidence for the streamlined Phase 11 cutover. Do not repeat reader diagnostics unless the device later disappears or imaging software cannot see the card.

The production SD card has not yet been removed or written. The only remaining gate before shutdown/card removal is explicit maintenance-window/cutover acceptance. After approval, proceed directly to controlled shutdown, remove the card, re-identify the removable disk by model/size, flash the verified custom factory image, boot, and verify the gateway works.

`PRODUCTION_SD_CARD_TOUCHED=NO` remains authoritative at this checkpoint.
### Phase 11 maintenance-window / cutover approval - 2026-08-28

The operator explicitly approved proceeding with the Phase 11 single-card cutover. Planned gateway downtime and the documented rollback path are accepted.

Current cutover sequence is intentionally streamlined:

1. gracefully power off the live gateway at `192.168.8.11`;
2. remove the production microSD only after shutdown completes;
3. insert it into the already-proven Windows removable-media path and confirm the same ~31.9 GB device;
4. flash the verified custom Gateway OS factory image;
5. reinstall the card, boot, and verify LoRa, Wi-Fi management, existing MQTT path, and SIM7600 driver presence.

Do not repeat already-passed build, checksum, preservation, DNS, or reader checks unless a later step actually fails.

`MAINTENANCE_WINDOW_ACCEPTED=YES`
`CUTOVER_APPROVED=YES`
`PRODUCTION_SD_CARD_TOUCHED=NO` at this approval boundary.
### Production microSD identified for cutover - 2026-08-28

Windows re-identified the inserted production microSD immediately before flashing:

```text
Disk 1
Model: Mass Storage Device USB Device
Interface: USB
Media: Removable Media
Size: 31946987520 bytes
```

This matches the previously observed removable reader/media path and is sufficient for the streamlined cutover. Proceed with balenaEtcher using the preserved custom factory image under `C:\Users\smartagriintern\lorawan-recovery\gateway-01\custom-v4.12.0-sim7600-20260827\target-output\`. Do not select the same-named official rollback image under `factory-v4.12.0`.
### Production microSD custom-image flash PASS - 2026-08-28

The approved Phase 11 single-card cutover has now written the verified custom ChirpStack Gateway OS factory image to the production microSD using balenaEtcher, and the operator reports the flash completed successfully. The written source was the preserved custom image under `C:\Users\smartagriintern\lorawan-recovery\gateway-01\custom-v4.12.0-sim7600-20260827\target-output\`, not the same-named official rollback image under `factory-v4.12.0`.

Because a factory image replaces the previous card contents, do not assume the prior Wi-Fi management address/configuration is already present on first boot. First boot should use Ethernet DHCP when available or the Gateway OS commissioning AP, allow first-boot filesystem expansion/reboot to finish, and prove the SIM7600 runtime driver path before restoring the verified gateway configuration/private backup.

Current cutover state:

```text
CUSTOM_FACTORY_IMAGE_FLASHED=YES
BALEANAETCHER_FLASH_REPORTED_SUCCESS=YES
PRODUCTION_SD_CARD_WRITTEN=YES
ROLLBACK_IMAGE_PRESERVED=YES
NEXT=BOOT_CUSTOM_IMAGE_AND_PROVE_MODEM_DRIVERS
```
### Custom-image first-boot SIM7600 runtime proof PASS - 2026-08-28

The freshly flashed custom Gateway OS booted successfully and runtime modem binding is proven. This closes the custom kernel/module objective; do not repeat build/package checks unless a later runtime regression appears.

Observed runtime evidence:

```text
SIM7600 USB ID: 1e0e:9001
modules loaded: option, usb_wwan, qmi_wwan, cdc_wdm, usbserial
serial devices: /dev/ttyUSB0 through /dev/ttyUSB4
QMI control: /dev/cdc-wdm0
QMI network device: wwan0
qmi_wwan registered the modem data interface successfully
```

The custom image therefore provides both the SIMCom serial path and a working QMI-capable control/network path. The next step is to restore the verified Gateway OS configuration archive, then restore the protected Mosquitto/private bundle as required, and re-verify only the operational identity/path: RAK5146, Gateway EUI `0016c001f139a1cb`, AS923, Wi-Fi management, local Mosquitto/MQTT Forwarder path, and UDP Forwarder disabled.

### Normal Gateway OS configuration restore PASS - 2026-08-28

The verified `gateway-os-backup-20260826-082144.tar.gz` was restored successfully after the custom-image SIM7600 driver proof. The gateway returned to its working management/configuration state. Treat this restore step as PASS and do not repeat it unless a later service check fails. Next restore the protected Mosquitto/private bundle, then run one compact identity/service verification.

### Mosquitto package reinstall PASS - 2026-08-28

After the custom factory-image flash and normal configuration restore, the protected `/etc/mosquitto` tree was restored from the verified private bundle, but the Mosquitto executable/init script was absent because the original broker packages had lived in the previous writable overlay. `opkg update` completed with signed OpenWrt 24.10.7 feeds, then `opkg install mosquitto-ssl mosquitto-client-ssl` installed Mosquitto 2.0.18-r4 and dependencies successfully.

`opkg` detected that the restored `/etc/mosquitto/mosquitto.conf` differed from the package default and preserved the restored production file, placing the package default at `/etc/mosquitto/mosquitto.conf-opkg`. Treat this as expected/pass behavior. Next boundary: confirm `/etc/config/mosquitto` uses `option use_uci '0'`, then enable/restart Mosquitto and verify loopback-only `127.0.0.1:1883`.

### Mosquitto local recovery PASS / bridge TLS pending - 2026-08-28

After reinstalling `mosquitto-ssl` and `mosquitto-client-ssl`, the restored static broker configuration is active with `mosquitto.owrt.use_uci=0`. Mosquitto is running as `mosquitto -c /etc/mosquitto/mosquitto.conf` and listens only on `127.0.0.1:1883`. The local MQTT Forwarder reconnected as gateway EUI `0016c001f139a1cb`, so the local packet-forwarding-to-buffer path is restored.

The two restored bridges still target the old/test endpoint `lora-test-server:8883` and currently report TLS errors. Treat this as a separate outbound bridge TLS issue, not as a failure of the custom image, modem drivers, local broker, or restored gateway configuration. Do not weaken verification with `bridge_insecure true`; isolate the TLS failure with the documented `openssl s_client` mTLS/hostname test.

### Restored bridge failure reclassified as network reachability - 2026-08-28

The restored Mosquitto bridges still target the lab endpoint `lora-test-server:8883`. The direct `openssl s_client` test failed before TLS negotiation with `BIO_connect: Host is unreachable` / `errno=113`. The documented lab name maps `lora-test-server` to `192.168.8.50`. Therefore the current blocker is IP reachability to the old lab server, not CA validation, certificate hostname validation, client-certificate rejection, or the custom Gateway OS image. Do not regenerate certificates or weaken TLS. Check the restored `/etc/hosts` mapping, gateway route, and reachability of `192.168.8.50` first.

### Cloud MQTT cutover decision - 2026-08-28

The restored `lora-test-server:8883` bridge is now retired from the active Phase 11 path. Do not spend additional time repairing the old lab VM merely to complete the custom-image cutover. The intended production gateway path remains local MQTT Forwarder -> loopback Mosquitto buffer -> public `mqtt.<DOMAIN>:8883`.

Current repository evidence proves the cloud MQTT service only on the private/internal identity `mqtt.internal.lorawan.com`; Phase 10 host-owned HAProxy anchor listeners are ready, but the provider-owned public activation is still incomplete. No real public MQTT FQDN or Reserved IPv4 is recorded, and the broker certificates have not yet been reissued with the real public MQTT SAN. Therefore do not point the gateway at a Droplet raw public IP and do not invent a public hostname.

Next external inputs required for the public gateway bridge are: one real public domain/FQDN, one assigned same-region Reserved IPv4, provider firewall allowance for public MQTT `8883/tcp`, DNS `mqtt.<DOMAIN>` -> Reserved IPv4, and broker certificates valid for both `mqtt.internal.lorawan.com` and the real public `mqtt.<DOMAIN>` name. Once those are available, change only the two Mosquitto bridge `address` lines, preserve mTLS verification, and validate the cloud path before moving LTE to the normal route.

### Markdown consistency review - corrected next boundary - 2026-08-28

A repository-wide review found an important sequencing inconsistency. Phase 8 planning shows gateway-facing Mosquitto `:8884` as mTLS, but later live Phase 12A inventory is authoritative and proves both current `:8884` listeners are server-TLS only: `require_certificate=false`, `allow_anonymous=false`, no `use_identity_as_username`, and no gateway ACL/plugin. The repository also contains no evidence that a cloud MQTT client certificate was ever issued for authoritative Gateway EUI `0016c001f139a1cb`; Phase 8 explicitly deferred gateway certificate provisioning. The restored gateway certificate bundle belongs to the previous lab path and must not be assumed to be the cloud production identity.

Therefore the immediate useful next step is **not** repairing `lora-test-server` and **not** waiting for a public domain. First close the provider-independent cloud gateway mTLS boundary:

- issue a cloud `clientAuth` certificate with CN `0016c001f139a1cb`;
- add the exact-EUI `as923` event/state/command ACL;
- change only the gateway-facing `:8884` authentication policy canary-first, preserving ChirpStack `:8885` and Node-RED `:8886`;
- prove positive mTLS, exact-EUI authorization, cross-EUI denial, and no-certificate rejection through both already-commissioned anchor `:8883` paths using SNI `mqtt.internal.lorawan.com`.

After that host-owned boundary passes, the remaining public activation inputs are still the real public FQDN, broker public SAN, assigned Reserved IPv4, provider firewall rule, and DNS. The physical gateway bridge should be repointed only when that public endpoint validates end-to-end.

### Gateway MQTT cloud client certificate issuance PASS - 2026-08-28

The real physical Gateway EUI `0016c001f139a1cb` now has a dedicated cloud MQTT client identity issued on `ulc-03` from the commissioned internal CA. Issuance directory: `/root/lorawan-pg-ca/gateway-0016c001f139a1cb-issuance-20260828T015149Z`; protected transfer bundle is its `transfer/` subdirectory. The certificate subject is `CN = 0016c001f139a1cb`, issuer `CN = LoRaWAN PostgreSQL Internal CA`, serial `D8732205912F3C3AC56E0A01E1E10583`, validity `2026-08-28 01:51:51Z` through `2027-09-29 01:51:51Z`, SHA-256 fingerprint `82:C6:9A:D7:12:5D:8C:45:F3:8F:BA:AB:F9:6E:7E:3B:41:F4:BE:78:95:FE:16:05:FD:58:2E:09:9D:F3:0A:ED`, and certificate SHA-256 `f348cef6e280dff82722ff908cc96e694faf183eec1dffc55a7abc690cb472d8`.

The certificate chains successfully for `sslclient`, is rejected for `sslserver`, and its public key matches the RSA-3072 private key. The issuing CA SHA-256 remains `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`; the existing CA serial-file SHA-256 remained byte-identical at `50df8c462ef9465ab9198284fa1234f0cbfa4f33eb9779ce6d50dd23a618463d` because issuance used an explicit random serial. `GATEWAY_MQTT_CLIENT_CERT_ISSUANCE=PASS`. No Mosquitto, HAProxy, DNS, firewall, or gateway runtime was changed by issuance.

Next boundary: canary-harden `ulc-01` gateway-facing Mosquitto `:8884` only to require client certificates, map certificate CN to MQTT username, and enforce an exact-EUI `as923` gateway ACL. Preserve ChirpStack `:8885` and Node-RED `:8886`. After `ulc-01` passes direct mTLS verification with the new gateway certificate, repeat the same bounded rollout on `ulc-02`.
### ulc-01 gateway mTLS canary PASS - 2026-08-28

`ulc-01:8884` was hardened from server-TLS-only to gateway client-certificate authentication without changing the ChirpStack `:8885` listener. The active gateway listener now has `require_certificate true`, `use_identity_as_username true`, `allow_anonymous false`, and `/etc/mosquitto/gateway.acl`. The exact Gateway EUI `0016c001f139a1cb` is permitted to write only its own `as923/.../event/#` and `state/#` topics and read only its own `command/#` hierarchy. Mosquitto restarted successfully, `:8884` and `:8885` remained listening, the issued gateway certificate completed TLS and MQTT CONNECT/SUBSCRIBE successfully, and a no-client-certificate connection was rejected. Rollback copy: `/etc/mosquitto/gateway-mtls-20260828T015613Z`. Next boundary: apply the same bounded change to `ulc-02` and prove the same certificate/ACL behavior there before transferring the cloud certificate bundle to Gateway OS.
### ulc-02 gateway mTLS rollout PASS - 2026-08-28

`ulc-02:8884` now matches the proven `ulc-01` gateway-authentication boundary: `require_certificate true`, `use_identity_as_username true`, `allow_anonymous false`, and `/etc/mosquitto/gateway.acl`. Gateway EUI `0016c001f139a1cb` is limited to its own AS923 event/state/command hierarchy. Mosquitto restarted successfully; `:8884` and ChirpStack `:8885` remained listening. The issued gateway certificate completed TLS, MQTT CONNECT, and own-command SUBSCRIBE successfully, while a no-client-certificate connection was rejected. Rollback copy: `/etc/mosquitto/gateway-mtls-20260828T015801Z`. Therefore both cloud MQTT broker backends now enforce the intended per-gateway mTLS identity. Next boundary: transfer only the three-file cloud certificate bundle (`ca.crt`, `0016c001f139a1cb.crt`, `0016c001f139a1cb.key`) to Gateway OS; do not change the working local Mosquitto topology yet.
### ulc-02 gateway mTLS state observed - 2026-08-28

Live read-only inspection after the first rollout wrapper showed `ulc-02` is already in the intended gateway mTLS state: `/etc/mosquitto/conf.d/tls.conf` has `listener 8884`, `require_certificate true`, `allow_anonymous false`, `use_identity_as_username true`, and `acl_file /etc/mosquitto/gateway.acl`; `/etc/mosquitto/gateway.acl` exists as `0640 root:mosquitto`; `per_listener_settings true` remains active; and the dedicated ChirpStack listener remains `10.104.0.4:8885` with its own password/ACL files. Therefore do not reapply the mutation. The remaining boundary is a direct positive mTLS/MQTT proof with gateway certificate CN `0016c001f139a1cb` plus a no-client-certificate rejection proof.
### Both cloud gateway MQTT brokers mTLS acceptance PASS - 2026-08-28

Direct verification from `ulc-03` against `ulc-02:8884` using the issued gateway identity `CN = 0016c001f139a1cb` passed TLS, MQTT CONNECT, and subscription to the gateway's own `as923/gateway/0016c001f139a1cb/command/#` hierarchy. A client without a certificate was rejected. Combined with the earlier `ulc-01` canary proof, both gateway-facing Mosquitto backends now enforce per-gateway mTLS and the exact EUI ACL while preserving the dedicated ChirpStack `:8885` listeners. The cloud broker-side gateway authentication boundary is therefore complete. Next: transfer only `ca.crt`, `0016c001f139a1cb.crt`, and `0016c001f139a1cb.key` from the protected `ulc-03` issuance bundle to Gateway OS; do not alter the local loopback broker topology during certificate import.
### Gateway cloud MQTT bundle staging PASS - 2026-08-28

The cloud gateway transfer bundle for EUI `0016c001f139a1cb` was staged under `/home/opsadmin/gateway-mqtt-cloud-0016c001f139a1cb` on `ulc-03` for protected workstation transfer. The directory contains only `ca.crt`, `0016c001f139a1cb.crt`, `0016c001f139a1cb.key`, and `SHA256SUMS`. Recorded SHA-256 values are CA `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`, client certificate `f348cef6e280dff82722ff908cc96e694faf183eec1dffc55a7abc690cb472d8`, and client key `51726e070cd2b3cdae8e7718650f11673989bd00da80641a6695556ad8b8504d`. The private key is mode `0600`; staging completed with `ULC03_GATEWAY_BUNDLE_STAGING=PASS`. Next boundary is workstation copy, hash verification, then legacy-SCP transfer into `/tmp` on Gateway OS before any certificate installation or Mosquitto restart.
### Gateway cloud-certificate workstation relay access-path stop - 2026-08-28

The first cloud-certificate relay attempt did not modify Gateway OS. Windows could not authenticate as `opsadmin@159.223.50.57` because the workstation does not have the authorized `opsadmin` SSH identity, so the 4.5-KiB archive never reached the workstation. Subsequent Windows-to-gateway copy/install commands therefore operated on a nonexistent local file and the gateway-side script stopped at its initial `test -s`/missing-archive gate. Treat later manually-entered `...=PASS` echo lines as non-authoritative; Windows PowerShell 5.1 continued after native-command failures/exceptions. The authoritative archive remains `/home/opsadmin/gateway-0016c001f139a1cb-cloud-mqtt-certs.tar.gz` on `ulc-03`, SHA-256 `294accecdd6080c736c26e3996daba55d19ce62ce0eab52e6d39eea97d698702`. Use the already-proven workstation `jervis` SSH identity for the cloud-to-workstation hop via a temporary `0600` jervis-owned relay copy, then delete that relay copy after workstation hash verification. Do not weaken SSH policy or create/copy an `opsadmin` private key onto the workstation/server solely for this transfer.

### Gateway cloud MQTT certificate transfer PASS - 2026-08-28

The three-file cloud MQTT identity for Gateway EUI `0016c001f139a1cb` completed end-to-end protected transfer from `ulc-03` to the Windows administration workstation and then to Gateway OS `/tmp`. The working workstation SSH identity was `id_ed25519_home_ops`; the first default-agent attempt was correctly rejected. SHA-256 verification passed at the `ulc-03` source, on Windows, and again on the gateway for `ca.crt` (`6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`), `0016c001f139a1cb.crt` (`f348cef6e280dff82722ff908cc96e694faf183eec1dffc55a7abc690cb472d8`), and `0016c001f139a1cb.key` (`51726e070cd2b3cdae8e7718650f11673989bd00da80641a6695556ad8b8504d`). `CLOUD_MQTT_CERT_TRANSFER=PASS`. No active Gateway OS certificate file, Mosquitto configuration, bridge target, or service was changed by this transfer. Next boundary: install the verified `/tmp` files into a new off-path `/etc/mosquitto/certs` candidate, verify chain/CN/key match, preserve the old lab certificate directory as rollback material, then atomically swap the verified candidate into place without restarting Mosquitto or repointing the bridge yet.

### Gateway cloud MQTT certificate install runtime-check stop - 2026-08-28

Gateway OS successfully verified the transferred cloud CA, gateway certificate, and private key by SHA-256, built the new certificate directory off-path, verified the `sslclient` chain, exact Gateway-EUI CN, and certificate/private-key public-key match, preserved the previous active certificate directory at `/etc/mosquitto/certs.before-cloud-20260828T022221Z`, and activated the cloud files under `/etc/mosquitto/certs`. The block then stopped immediately after listing the installed files, before the listener check and `/tmp` cleanup, because the next `pidof mosquitto` gate returned non-zero (or the utility was unavailable). Treat this as a runtime-verifier stop after successful certificate activation, not as certificate-install failure. Do not roll back the cloud files yet. Next perform one compact Gateway OS check using `ps`, the OpenWrt init script, and `ss`/`netstat`; if Mosquitto is not running, restart it once and require the loopback `127.0.0.1:1883` listener before deleting the retained `/tmp` transfer copies. Do not change the bridge endpoint in the same step.

### Gateway cloud MQTT certificate install PASS - 2026-08-28

The cloud CA and gateway client identity are now installed under `/etc/mosquitto/certs/` on the physical Gateway OS. The active files match the recorded SHA-256 values: `ca.crt` `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`, `0016c001f139a1cb.crt` `f348cef6e280dff82722ff908cc96e694faf183eec1dffc55a7abc690cb472d8`, and `0016c001f139a1cb.key` `51726e070cd2b3cdae8e7718650f11673989bd00da80641a6695556ad8b8504d`. The certificate chained for `sslclient`, its CN matched `0016c001f139a1cb`, and certificate/private-key public keys matched. The previous certificate directory is preserved at `/etc/mosquitto/certs.before-cloud-20260828T022221Z`.

Post-install runtime verification passed without changing the bridge target: Mosquitto remained running with the local listener on `127.0.0.1:1883`, ChirpStack MQTT Forwarder remained running, and the temporary `/tmp` certificate copies were removed. `GATEWAY_CLOUD_MQTT_RUNTIME_CHECK_EXIT=0`. Repeated TLS errors against `lora-test-server:8883` are expected because the bridge still targets the retired lab endpoint while now presenting the cloud client identity; do not treat those errors as a failure of the local persistent-buffer path and do not weaken TLS. The public MQTT FQDN/Reserved-IP/DNS path is still not commissioned, so leave the bridge target unchanged until that endpoint is ready.

Next useful Phase 11 boundary: continue SIM7600/LTE commissioning while preserving the working Wi-Fi management interface `wwan`. Use logical interface name `lte` for the QMI data session on `/dev/cdc-wdm0`; do not overwrite the Wi-Fi `wwan` UCI interface.
### SIM7600 AT probe Wi-Fi transient observed - 2026-08-28

After the first `uqmi --get-pin-status` query hung, the operator interrupted it and ran a read-only serial probe against `/dev/ttyUSB2` and `/dev/ttyUSB3` using only `AT`, `ATI`, `AT+CPIN?`, `AT+CSQ`, and `AT+CEREG?`. Neither serial port produced a captured AT response. During/after that probe the operator observed a transient disconnect from the Wi-Fi network shared with the gateway. The probe contained no UCI, route, wireless, USB-mode, APN, or data-session mutation, so do not infer that Wi-Fi configuration changed. Do not repeat the AT or QMI probe until read-only gateway logs are checked for Wi-Fi disassociation, USB reset/re-enumeration, and Raspberry Pi undervoltage/power evidence. Preserve the Wi-Fi logical interface `wwan` and do not send `AT+CUSBPIDSWITCH`.

### Gateway Wi-Fi DHCP leak confirmed - 2026-08-28

Read-only UCI/runtime inspection proved that management Wi-Fi `wwan` is correctly configured as static `192.168.8.11/24` on `phy0-sta0`, but an unintended `dhcp.wwan` server is also active. The generated dnsmasq configuration contains `dhcp-range=set:wwan,192.168.8.100,192.168.8.249,255.255.255.0,12h`, and live logs show the gateway issuing DHCP ACKs to other clients on `lorawan5`. This can conflict with the real upstream DHCP server and explains the observed client connectivity disturbance. The intended project design uses `wwan` only as a management Wi-Fi client and allows SSH/LuCI by placing it in the LAN firewall zone; it does not require DHCP service on `wwan`. First repair only the DHCP leak (`dhcp.wwan.ignore=1`) and verify the generated `wwan` DHCP range disappears before changing firewall-zone duplication, default-route state, or any LTE/modem configuration.

### Streamlined management-path decision - 2026-08-28

The operator confirmed that the workstation connectivity problem stopped after unplugging the Raspberry Pi Ethernet cable. Live evidence showed Ethernet `br-lan` and Wi-Fi `phy0-sta0` simultaneously on the same `192.168.8.0/24` network (`192.168.8.131` and `192.168.8.11` respectively), with the default route previously preferring `br-lan`. Treat same-subnet Ethernet/Wi-Fi multi-homing as the primary immediate cause of the observed connection instability. For Phase 11 commissioning, keep Ethernet unplugged and use Wi-Fi `wwan` as the management path. Do not spend time tuning route metrics or firewall duplication unless the problem recurs. Separately, the confirmed `dhcp.wwan` server leak remains a real configuration defect and should be disabled once; then resume LTE commissioning directly.

### Management Wi-Fi DHCP leak disabled - 2026-08-28

The gateway management Wi-Fi DHCP leak was corrected by setting `dhcp.wwan.ignore=1`, committing the DHCP configuration, and restarting dnsmasq. The operator reported no command errors. Ethernet remains unplugged during LTE commissioning because simultaneous Ethernet and Wi-Fi on the same `192.168.8.0/24` network previously created route ambiguity. Continue with Wi-Fi `wwan` as the management path and use logical interface `lte` for the SIM7600 data session.

### SIM7600 scripted microcom probe inconclusive - 2026-08-28

The bounded `microcom` probe against `/dev/ttyUSB2` and `/dev/ttyUSB3` returned no captured output on either port. This does not prove the modem lacks an AT port because the repository has no proven ttyUSB-to-function mapping and scripted stdin/stdout capture through `microcom` is not authoritative for this Gateway OS. Do not change USB composition. Next use one bounded reader-first `AT` probe across `/dev/ttyUSB0` through `/dev/ttyUSB4` and stop as soon as a port returns `OK`.

### SIM7600 all-port probe tool limitation - 2026-08-28

The attempted bounded AT probe across `/dev/ttyUSB0..4` was inconclusive because Gateway OS does not provide the `timeout` utility: each background reader exited with status `127` before `cat` could read any serial response. Therefore the empty port outputs are not evidence that the SIM7600 ignored AT commands. Continue with a pure BusyBox/ash background-reader probe that starts `cat`, writes `AT`, sleeps briefly, then kills only that reader process; do not alter modem USB mode or network configuration.

### SIM7600 AT-capable ports proven - 2026-08-28

A corrected BusyBox-only serial read proved that `/dev/ttyUSB2` and `/dev/ttyUSB3` both return live SIM7600 AT responses. The modem reported `+CPIN: READY`, followed by `SMS DONE` / `PB DONE`, unsolicited SMS indications, and repeated `AT` / `OK` responses. Treat the SIM as present and PIN-unlocked. Stop scanning all ttyUSB ports; use one proven AT-capable port (prefer `/dev/ttyUSB2` for the next bounded status query) and do not send USB-mode-changing commands. The large repeated `AT` / `OK` stream is probe noise/stale serial traffic and is not a reason to continue port discovery.

### SIM7600 LTE registration PASS - 2026-08-28

AT status captured from `/dev/ttyUSB2` proved the SIM7600 and SIM are operational: `+CPIN: READY`, `+CSQ: 22,99`, `+CEREG: 0,1`, and `+COPS: 0,0,"515 66 DITO",7`. Treat SIM unlock, LTE registration on the home network, and usable radio signal as PASS. The repeated standalone `ERROR` lines came from the crude concurrent serial capture and do not invalidate the successful command-specific responses.

### SIM7600 PDP-context discovery PASS - 2026-08-28

`AT+CGDCONT?` on `/dev/ttyUSB2` returned three contexts: CID 1 is `IP` with a blank APN, CID 2 is the carrier IMS context (`IPV4V6`, APN `ims`), and CID 3 is `IPV4V6` with a blank APN. Do not modify CID 2. The normal packet-data context therefore does not currently contain the carrier APN. DITO's published modem/data configuration identifies the APN as `internet.dito.ph`; use that value for the new OpenWrt QMI interface rather than guessing. The custom Gateway OS has already proved `/dev/cdc-wdm0` plus network device `wwan0`, so the next bounded mutation is to create logical UCI interface `lte` with protocol `qmi`, device `/dev/cdc-wdm0`, APN `internet.dito.ph`, and no carrier username/password. Preserve management Wi-Fi logical interface `wwan` unchanged and verify the new UCI stanza before bringing LTE up or changing firewall/default-route behavior.

### LTE pre-mutation gate PASS - 2026-08-28

The live gateway has no existing logical `network.lte` interface. Management Wi-Fi remains separate as static logical `wwan` at `192.168.8.11/24` with gateway `192.168.8.1`. QMI runtime devices `/dev/cdc-wdm0` and kernel `wwan0` exist. Required packages `kmod-usb-net-qmi-wwan`, `uqmi`, and `luci-proto-qmi` are installed. Treat this gate as PASS and do not repeat the driver/package inventory unless later LTE activation fails. The next required input is the modem PDP/APN context; do not invent an APN.

### LTE QMI interface configured - 2026-08-28

The live gateway now has logical `network.lte` committed with protocol `qmi`, device `/dev/cdc-wdm0`, APN `internet.dito.ph`, authentication `none`, PDP type `IP`, `defaultroute=0`, and `peerdns=0`. Management Wi-Fi logical `wwan` remains unchanged. Treat this configuration gate as PASS. The next bounded action is `ifup lte`, followed by a single runtime check for interface state and assigned cellular address. Do not repeat driver, SIM, registration, APN, or package gates unless LTE activation fails.

### LTE QMI data session PASS - 2026-08-28

`ifup lte` established the DITO QMI packet-data session successfully. Parent logical interface `lte` is up with QMI session identifiers `cid_4` and `pdh_4`; dynamic child interface `lte_4` is up on kernel device `wwan0` and received IPv4 `100.73.25.125/30` with carrier gateway/DHCP server `100.73.25.126`. Carrier DNS advertised `131.226.72.19` and `131.226.73.19`. The default route and peer DNS are intentionally inactive because commissioning uses `defaultroute=0` and `peerdns=0`, preserving management-path behavior. Treat QMI session establishment and LTE address assignment as PASS. Next perform one controlled public-IP connectivity test with a temporary host route through `100.73.25.126`; remove that route immediately after the test.
### LTE public connectivity PASS - 2026-08-28

A controlled host-route test proved end-to-end public Internet connectivity over the DITO QMI path without changing the gateway default route. A temporary `/32` route for `1.1.1.1` was installed via carrier gateway `100.73.25.126` on `wwan0` with source `100.73.25.125`; `ip route get 1.1.1.1` confirmed that path and `ping -c 4 -W 3 1.1.1.1` returned two replies with exit status 0. The temporary route was then removed. Treat LTE public IP connectivity as PASS. The observed 50% packet loss is noted for later quality monitoring but does not invalidate the connectivity proof. Keep `network.lte.defaultroute=0` and `peerdns=0` for now: the continuation plan requires the real public MQTT endpoint / certificate / DNS path to be activated and validated before LTE becomes the gateway normal/default route.

### Streamlined Phase 13A off-host checkpoint PASS - 2026-08-28

The pre-cutover database archive `phase13a-20260827T032756Z.tar.gz` was copied from `ulc-03` to the Windows administration workstation and verified byte-for-byte by SHA-256. Source and destination both equal `e97d50c31252ede1fe55b734b6686f270e92ebecb69a36d637b04fbf726cda1c`; `PHASE13A_OFFHOST_COPY=PASS`. For the current non-destructive commissioning fast path, treat Phase 13A as complete enough to proceed to the Phase 12 entry gate. Rigorous isolated restore and destructive DR proof remain deferred to the later Phase 15 boundary.
