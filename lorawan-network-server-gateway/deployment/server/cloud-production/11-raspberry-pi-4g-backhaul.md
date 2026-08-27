# 11. Gateway OS Delivery Buffer and Integrity Journal over a USB 4G/LTE Dongle

> **Status: REQUIRED PRE-TEST SETUP / ACTIVE.** The physical gateway is available again. Preserve the known hardware baseline (Raspberry Pi 4B + RAK5146 + Waveshare SIM7600G-H) and resume from the read-only reuse/modem inventory before changing live gateway state. Phase 13A cloud backup work is paused while Phase 11 is active; Phase 12 still requires both Phase 11 normal-path commissioning and Phase 13A PASS. The Phase 10 provider-owned Reserved-IP/firewall/DNS work remains pending externally. **Do not perform LTE-outage, gateway-reboot, broker-loss, or queue-drain failure experiments here; Phase 15 owns those tests after the full setup gate passes.**

## 11.0 Fast reuse gate - inspect before changing the gateway

Do not reflash Gateway OS or rewrite a working radio configuration merely because Phase 11 is now active. First capture the current gateway state in one read-only pass. Reuse any component that already satisfies the commissioned requirements and continue only from the first missing item.

The reuse gate must identify: Gateway OS release, UTC time, free persistent storage, active RAK5146/SX1303 Concentratord configuration, authoritative Gateway EUI, plain `as923` topic prefix, UDP Forwarder disabled state, MQTT Forwarder endpoint/backend, any existing loopback Mosquitto listener/configuration, and USB/LTE interfaces. A previous working result is useful context but does not replace this current inspection.

**Current LTE hardware baseline:** the gateway uses a **Waveshare SIM7600G-H 4G DONGLE**. Waveshare documents this model for Linux hosts and lists NDIS/RNDIS/PPP dial-up support. Therefore do **not** assume the dongle is QMI or MBIM and do not send a USB-mode-changing AT command during discovery. First identify the composition currently presented to Gateway OS from `lsusb`, kernel logs, `/dev/ttyUSB*`, `/dev/cdc-wdm*`, and any new network interface. Preserve the working USB composition unless the current Gateway OS cannot use it.

**Why:** this shortens the phase while reducing risk. Reflashing or rewriting a functioning gateway would create unnecessary RF identity, networking, and credential changes. Read-only discovery lets the operator skip already-complete setup and mutate only the missing layer.

### 11.0A Fast read-only gateway inventory

Run this directly on the Gateway OS shell. It intentionally avoids full wireless/network secret dumps and never reads a private-key body:

```sh
echo '=== PHASE 11.0A GATEWAY REUSE INVENTORY ==='

echo '--- OS / time / storage ---'
cat /etc/os-release
uname -a
date -u
df -h /

echo '--- core service state ---'
monit status 2>/dev/null || true
ps w | grep -E '[c]hirpstack-concentratord|[c]hirpstack-mqtt-forwarder|[m]osquitto'

echo '--- Concentratord effective config ---'
uci show chirpstack-concentratord 2>/dev/null || true

echo '--- recent Concentratord identity/startup ---'
logread -e chirpstack-concentratord 2>/dev/null | tail -n 120

echo '--- MQTT Forwarder effective config ---'
uci show chirpstack-mqtt-forwarder 2>/dev/null || true

echo '--- UDP Forwarder effective config ---'
uci show chirpstack-udp-forwarder 2>/dev/null || true

echo '--- local Mosquitto process/listener ---'
ps w | grep '[m]osquitto' || true
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp 2>/dev/null | grep ':1883' || true

echo '--- Mosquitto persistence/listener policy ---'
grep -E '^(persistence|persistence_location|persistence_file|autosave_interval|max_queued_messages|max_queued_bytes|listener|protocol|allow_anonymous|include_dir)' /etc/mosquitto/mosquitto.conf 2>/dev/null || true

echo '--- Mosquitto cloud bridge metadata only ---'
grep -E '^(connection |address |remote_clientid|cleansession|bridge_cafile|bridge_certfile|bridge_keyfile|bridge_insecure|topic )' /etc/mosquitto/conf.d/bridge.conf 2>/dev/null || true

echo '--- network / USB / LTE discovery ---'
ip link
ip -4 addr
ip route
lsusb 2>/dev/null || true
dmesg | tail -n 120

echo '=== PHASE 11.0A COMPLETE ==='
```

Record the active 16-hexadecimal Gateway EUI from the successful SX1302/SX1303 Concentratord startup, not an inactive SX1301 placeholder. The current POC region topic prefix must remain exactly `as923`. A correct already-buffered delivery path has MQTT Forwarder targeting `tcp://127.0.0.1:1883` with QoS 1, UDP Forwarder disabled, local Mosquitto bound only to loopback `1883`, persistence enabled with finite queue limits, and cloud bridge metadata referencing the intended MQTT endpoint. If any of those are already correct, do not recreate them.

The inventory may show an LTE device/interface but does not prove carrier registration or cloud reachability; those are verified later after the modem mode is identified. If Mosquitto or the bridge files are absent, record `ABSENT` and continue with the local-buffer section rather than installing packages blindly.

### Phase 11.0A/0B live inventory result - 2026-08-26

**PASS for gateway reuse / PARTIAL for LTE driver binding.** The gateway is running ChirpStack Gateway OS `4.12.0` (`r29197-ab4c7d6af7`) on Raspberry Pi 4B with about `3.8 GiB` free on the persistent overlay. The active Concentratord is `chirpstack-concentratord-sx1302` `4.7.1` using `model='rak_5146'`, region `AS923`, channel plan `as923`, with active Gateway EUI **`0016c001f139a1cb`**. The SX1302 startup shows the expected AS923 923.2-924.6 MHz multi-SF channel set. The inactive SX1301 placeholder EUI must not be used. UDP Forwarder is disabled.

MQTT Forwarder `4.6.0` already uses the correct local-buffer topology: `tcp://127.0.0.1:1883`, topic prefix `as923`, and the active Gateway EUI. However, its current UCI value is **QoS `0`**, while the commissioned persistent-buffer design requires QoS `1`; treat that as a later bounded configuration correction after the LTE driver path is understood. Do not bypass local Mosquitto.

Local Mosquitto is already running and listening only on `127.0.0.1:1883`. Persistence is enabled at `/etc/mosquitto/data/mosquitto.db`, autosave is `60` seconds, the finite queue limits are `100000` messages and `104857600` bytes, and the local listener is loopback-only. The two existing mTLS bridges use the gateway-specific certificate paths and split uplink/state (`out 1`, persistent session) from downlink command traffic (`in 0`, clean session). Their current remote target is `lora-test-server:8883`; treat that as the existing test endpoint, not as proof that the future public `mqtt.<DOMAIN>` path is commissioned.

The Waveshare SIM7600G-H is physically detected by the kernel as SimTech USB **`1e0e:9001`**. It appeared first at `1-1.1`, disconnected, then re-enumerated at `1-1.3`. At the inventory checkpoint there were **no** `/dev/ttyUSB*` nodes, no `/dev/cdc-wdm*` node, and no modem-created network interface. The installed packages include generic USB serial/FTDI and PPP support but do not yet prove a matching SIM7600 serial or USB-network driver is present. Do not infer QMI, MBIM, RNDIS, or PPP from the product ID alone; inspect the live USB interface descriptors and bound-driver state first.

The existing OpenWrt logical interface named `wwan` is **not LTE**: it is the current Wi-Fi station `phy0-sta0`, address `192.168.8.11/24`, with the default route through `192.168.8.1`. Keep this management path intact. When the SIM7600 data interface is commissioned, give it a distinct logical name rather than overwriting the working Wi-Fi `wwan` configuration.

### Phase 11.0C USB descriptor result - 2026-08-26

The live `1e0e:9001` device exposes one configuration with six USB interfaces numbered `0` through `5`. Every interface is vendor-specific (`class ff`) and every interface is currently **UNBOUND**. The kernel has generic `usbserial` plus `ftdi_sio` and `cdc_acm` loaded, but the SIMCom `option` serial driver is not loaded; there are still no `/dev/ttyUSB*`, `/dev/cdc-wdm*`, or modem network devices. This rules out treating the current composition as an already-bound RNDIS/CDC-Ethernet/MBIM interface.

Linux's `option` driver includes the SIMCom/ALINK `1e0e:9001` product family and reserves the higher data/ADB interfaces rather than binding every function as a serial port. For this gateway, commission the **serial option driver first** and verify the resulting ttyUSB layout before choosing the LTE data-plane package. Do not issue `new_id`, `AT+CUSBPIDSWITCH`, or another USB-mode change unless the packaged driver fails to recognize the device after installation and a separate diagnostic proves that a manual binding is required.

The first package mutation is therefore split into two gates: refresh the pinned Gateway OS package indexes and verify the matching `kmod-usb-serial-option` package is available for the running `6.6.141` kernel; only then install that one package and re-check binding. QMI/MBIM/RNDIS packages remain deferred until the post-serial-binding interface state identifies the actual data-plane requirement.

### Phase 11.0D package-index result - 2026-08-26

The gateway preserved its Wi-Fi management baseline (`phy0-sta0` at `192.168.8.11/24`, default route via `192.168.8.1`) and confirmed kernel `6.6.141`. `opkg update` completed successfully against the Gateway OS / OpenWrt `24.10.7` feeds with valid signatures. The normal package indexes expose the user-space `uqmi` and `umbim` tools, but `opkg list` returned **zero** `kmod-usb-serial-option` candidates. No driver was installed and no network or modem USB-mode change occurred.

Do **not** interpret this as unsupported SIM7600 hardware. OpenWrt 24.10 stores kernel-module packages in the target-specific `kmods/<kernel-ABI>/` repository, and a normal release image/feed can omit that kmods source from `distfeeds.conf`; the `kmod-usb-serial-option` module still exists for Linux `6.6.141`. Before editing any feed file, derive the exact installed kernel package/ABI token, current target/subtarget, and existing feed definitions from the live gateway. Add only a kernel-module source whose exact ABI dependency matches the installed kernel; never use `--force-depends`, a foreign target, or a guessed kernel ABI.

### Phase 11.0E exact-kmods result - 2026-08-26

The gateway is ChirpStack Gateway OS `4.12.0` on target `bcm27xx/bcm2709`, architecture `arm_cortex-a7_neon-vfpv4`, running kernel `6.6.141`. Its installed kernel package is **`6.6.141~ce9a7c4f21afbe9986efeaec95ee2cce-r1`**. The only official OpenWrt `24.10.7` bcm2709 kmods directory for `6.6.141` is `6.6.141-1-910ca1d362cc3ff4f2a1d9a4e9759bc8`; its `kmod-usb-serial-option` and `kmod-usb-serial-wwan` packages depend on kernel **`6.6.141~910ca1d362cc3ff4f2a1d9a4e9759bc8-r1`**. These ABI hashes do not match.

Therefore **do not add that OpenWrt kmods directory as an install source and do not force-install its modules**. Same upstream kernel version does not make separately configured OpenWrt kernel modules ABI-compatible. This matches the known ChirpStack Gateway OS limitation that common USB-4G `kmod-*` packages may be unavailable for its custom kernel image.

Before committing to a rebuilt Gateway OS image, perform one final read-only capability probe: inspect the running kernel configuration, existing module files, and the already-loaded generic `usbserial` driver. If the required SIM7600 serial/network functions are not built into this custom kernel and there is no safe existing generic-driver path, the correct durable fix is to build/pin a ChirpStack Gateway OS image from the same source revision with the required USB modem kernel modules included, rather than mixing stock OpenWrt kmods with the custom kernel.

### Phase 11.0F current-kernel capability result - 2026-08-26

The read-only kernel probe confirmed the installed Gateway OS image does **not** already contain a usable SIM7600 modem stack. The running kernel remains `6.6.141~ce9a7c4f21afbe9986efeaec95ee2cce-r1`. No readable kernel config is exposed through `/proc/config.gz` or `/boot/config-6.6.141`, so built-in configuration cannot be inferred from config text; runtime/module evidence is authoritative instead.

The only relevant module file present is `/lib/modules/6.6.141/usbserial.ko`. Installed packages are `kmod-usb-acm`, generic `kmod-usb-serial`, and `kmod-usb-serial-ftdi`. The USB-serial subsystem exposes only `ftdi_sio` and the generic driver. There is no packaged/current-kernel `option.ko`, `usb_wwan.ko`, `qmi_wwan.ko`, `cdc-wdm.ko`, `cdc_ether.ko`, `cdc_ncm.ko`, `cdc_mbim.ko`, or `rndis_host.ko`, and no SIM7600 module alias database entry is available. All six `1e0e:9001` interfaces remain unbound. Wi-Fi management remains `192.168.8.11/24` with default route via `192.168.8.1`.

Although the generic USB-serial driver exposes a writable `new_id` control, do **not** treat `echo 1e0e 9001 > .../generic/new_id` as the permanent deployment fix. That broad VID/PID match can claim multiple vendor-specific functions, including interfaces that the SIMCom-aware `option` driver deliberately excludes, and it does not provide the intended `usb_wwan`/SIMCom driver behavior. A generic bind may be used only as a separately reviewed temporary diagnostic if later required; it is not the Phase 11 commissioned LTE path.

**Current decision:** the as-installed Gateway OS 4.12.0 image cannot commission the SIM7600G-H cleanly with its present kernel modules, and the stock OpenWrt kmods cannot be mixed in because of the proven ABI hash mismatch. Installing drivers directly on the live gateway would be acceptable **only if** an official or locally built package set exists for the exact running Gateway OS kernel ABI. No such matching package set is currently available. Do not use `--force-depends` or copy foreign `.ko` files manually. The supported path is therefore to build or obtain a Gateway OS image/package set containing the required modem drivers compiled together with the Gateway OS kernel, while preserving the existing RAK5146/AS923/gateway-EUI configuration and keeping the current image/config backup available for rollback.

The external build host is needed to **compile an ABI-matched kernel/module set**, not because the SIM7600 must be configured from Windows. The Raspberry Pi gateway remains the runtime target. Building the OpenWrt/Gateway OS kernel on the live gateway is avoided because the gateway has only a small persistent overlay and is already a commissioned radio appliance. The build can use any supported Linux Docker engine; Docker Desktop is optional, not a project requirement.

Upstream ChirpStack Gateway OS supports this directly through its Docker-based source build. The reproducible project procedure is now documented in [Gateway 2A - Build a SIM7600-Capable ChirpStack Gateway OS Image](../../gateway/setup/02a-build-sim7600-capable-gateway-os.md). It pins Gateway OS `v4.12.0`, preserves the existing Base/Raspberry Pi target, builds the SIMCom serial drivers into the same kernel/image, and includes the QMI candidate data path without activating it until runtime proof. A spare card is preferred but not mandatory: with only one SD card, the hard gate becomes a reflash-ready rollback boundary using the exact official factory image plus the already verified off-gateway configuration/private backups. Do not install foreign stock OpenWrt kmods after boot.

### Phase 11.0G rollback-backup result - 2026-08-26

**PASS on the live gateway; off-gateway copy still required before any build/reflash.** The pre-custom-image backup ran without service restarts, network changes, modem changes, or loss of the Wi-Fi management path. The normal Gateway OS configuration archive is `/tmp/gateway-os-backup-20260826-082144.tar.gz`, size about `15.5 KiB`, SHA-256 `572bfa3f45a69c5ed2ca99263988e8acf2e91ddb514f538520f62d5fb12488a1`. It contains the critical Concentratord, MQTT Forwarder, UDP Forwarder, network, and wireless UCI files.

The normal `sysupgrade` archive contains `/etc/mosquitto/mosquitto.conf` but does **not** contain the Mosquitto certificate tree or persistent data tree. Therefore the explicit protected recovery bundle is required: `/tmp/gateway-critical-private-20260826-082144.tar.gz`, size about `6.0 KiB`, SHA-256 `f74fc55480bd4edf11a745118e15eae7afac43fff9daabcd64bb20aed4757db1`. It was created from the complete `/etc/mosquitto` tree plus the critical UCI files and passed archive-integrity verification. Treat this second archive as secret material because it may contain the gateway MQTT private key and Wi-Fi credentials; never commit it to Git or paste its contents into documentation/chat.

The shell reported `hostname: not found`; this is a minimal-image utility omission and did not affect the backup gate. Gateway identity remains independently established by the Gateway OS/UBus/Concentratord evidence. **Do not delete the `/tmp` copies or start the custom-image build until both archives have been copied to protected storage outside the gateway and their SHA-256 values match there.**

The first Windows OpenSSH transfer attempt failed after authentication with `ash: /usr/libexec/sftp-server: not found`. This was a protocol compatibility issue, not a backup-integrity failure: modern OpenSSH `scp` uses SFTP by default, while this minimal Gateway OS image does not provide the SFTP server helper. The retry with `scp -O` forced the legacy SCP protocol and completed successfully.

### Phase 11.0G-2 off-gateway preservation result - 2026-08-26

**PASS.** Both rollback artifacts were copied to protected workstation storage at `C:\Users\smartagriintern\lorawan-recovery\gateway-01\20260826-082144` without changing gateway state. The copied sysupgrade archive is `15908` bytes and its SHA-256 exactly matches `572bfa3f45a69c5ed2ca99263988e8acf2e91ddb514f538520f62d5fb12488a1`. The copied protected critical bundle is `6188` bytes and its SHA-256 exactly matches `f74fc55480bd4edf11a745118e15eae7afac43fff9daabcd64bb20aed4757db1`.

The off-gateway configuration/private rollback boundary is therefore closed: `OFF_GATEWAY_ROLLBACK_COPY=PASS`, `CUSTOM_IMAGE_BUILD_ALLOWED=YES`, `PHASE11_0G2_RESULT=PASS`, and the Windows PowerShell session survived. Because only one SD card is available, do **not** overwrite it yet. Before the first custom-image write, preserve and hash the exact official Gateway OS `4.12.0` Raspberry Pi Base factory image and confirm the workstation has a working SD-card writer. Once that additional gate passes, the same card may be reflashed during a planned maintenance window; rollback then means reflashing the official image and restoring the verified backups, with expected gateway downtime. Retain the gateway `/tmp` copies until the custom image and restore path have been verified.

### Phase 11 build-host consolidation - 2026-08-27

The build-host investigation is complete enough to stop creating micro-gates. The workstation has adequate CPU/RAM/disk, WSL2 is working, Ubuntu `24.04.4 LTS` is initialized, Git is present, and Linux networking/DNS is healthy. Keep the Gateway OS source/build tree under `/home/smartagriintern/src`, not `/mnt/c`.

The Linux build dependencies are installed and verified inside Ubuntu WSL2: GNU Make `4.3`, Docker client/server `29.1.3`, `OSType=linux`, `Architecture=x86_64`, and Docker Compose v2 `2.40.3+ds1-0ubuntu1~24.04.1`. Docker Desktop is **not** a project requirement and is not part of the active path. The build tree is `/home/smartagriintern/src/chirpstack-gateway-os`.

The intermittent WSL DNS regression was bypassed with a reversible temporary resolver override. Five repeated lookups and `git ls-remote` passed, after which ChirpStack Gateway OS cloned successfully and `v4.12.0` was pinned at commit `2112dbdbda48cd77ec1b82499e389abd728e84a1`. Pinned submodules are `chirpstack-openwrt-feed` `2a959fab57cf5a49b843ceac4b0541169e831703` and OpenWrt `b40dfac0a31695596f7c1f5f1519302ca8237f6e`.

The earlier missing-Compose failure is resolved. The later `make init` stop at `quilt init` / `No series file found` occurred only after the complete OpenWrt feed update/install and is understood as an initialization-order/tool-version compatibility issue. Do not rerun the full feed installation or invent an empty patch series. The pinned `base_raspberrypi_bcm27xx_bcm2709` switch subsequently passed, `conf/.config`, `conf/files`, and `conf/patches` point to that environment, and all three target patches (`no-uart-console`, `boot-config`, and `image-with-padded-rootfs`) applied successfully.

The next attempt failed before changing modem package state because `openwrt/scripts/config` is a directory in this pinned tree, not a command-line helper. The corrected procedure edits only the eight required `CONFIG_PACKAGE_*` lines, runs `make defconfig`, requires all eight to resolve to `=y`, and then builds with the already-selected target.

**Current handoff state:** the operator reports that the corrected block has reached the compilation stage and is still compiling. No final image filename, manifest, custom-image SHA-256, or final build PASS has been captured yet. The gateway SD card remains untouched. For exact chat-to-chat continuation, evidence boundaries, do-not-repeat guidance, rollback state, and the post-build sequence, read [Phase 11A - Current Continuation Checkpoint](11a-phase11-continuation-checkpoint.md) before issuing another build command.

**Parallel rollback preparation result:** while compilation continued, the Gateway OS `4.12.0` Base factory artifact was preserved at `C:\Users\smartagriintern\lorawan-recovery\gateway-01\factory-v4.12.0` and hashed as `395e79fe041c4118e10dd4cf796aa426a565d5e733144485d8d014a8d8dbf0a6` (`27606919` bytes). Both previously preserved gateway backup archives passed re-hash, balenaEtcher was found at `C:\Users\smartagriintern\AppData\Local\Programs\balena-etcher\balenaEtcher.exe`, and a post-flash checklist was created in the rollback directory. The gateway SD card was not touched. This proves the retained image/hash, backup, imaging-software, and checklist portions of rollback readiness; it does not yet prove a physical SD reader/writer path or maintenance-window acceptance.

From here, execute Phase 11 only from the first unresolved boundary: let the active build finish, verify the custom image/manifest/hash, finish the remaining physical SD reader/writer and maintenance-window rollback checks, then perform the planned reflash and runtime verification. The rollback factory image/hash, backup re-verification, imaging software, and post-flash checklist are already complete. Historical build-host failures remain evidence, not instructions to repeat passed work.

## 11.1 Goal

Keep two independent outbound paths over the same 4G backhaul:

```text
DELIVERY
MQTT Forwarder
  -> local Mosquitto persistent queue
  -> ssl://mqtt.<DOMAIN>:8883 over 4G

EVIDENCE
Concentratord
  -> integrity journal
  -> local hash-chained segments
  -> https://evidence.<DOMAIN>:443 over 4G
```

MQTT uses a unique gateway certificate. The evidence uploader uses its own per-gateway machine identity when the v2 path is deployed. MQTT Forwarder never connects directly to the cloud and the journal never owns the SPI radio.

## 11.2 Confirm the gateway and 4G inputs

Before changing the backhaul, confirm the Gateway EUI and legal RF plan are stable, the modem and SIM support the selected carrier/APN, and DNS resolves every enabled machine endpoint.

For delivery confirm:

```text
mqtt.<DOMAIN>
MQTT cloud CA
unique MQTT client identity for the Gateway EUI
queue path/finite limits/free-space reserve
```

For v2 evidence also confirm:

```text
evidence.<DOMAIN>
evidence server CA
unique evidence-upload identity mapped to the Gateway EUI
journal implementation/version/hash
journal storage budget and latest local chain/checkpoint state
```

Keep the tested Gateway OS image reference, RAK5146 variant, APN reference, endpoints, certificate fingerprints/expiry, and encrypted rollback backup because those values are needed to restore service without changing radio or evidence identity.

Do not copy SIM PINs, APN passwords, or private keys into the manual or test notes.

## 11.3 Install and configure Gateway OS

Follow:

- [Gateway OS installation](../../gateway/setup/02-install-chirpstack-gateway-os.md)
- [Concentratord](../../gateway/setup/03-configure-concentratord.md)
- [Persistent MQTT buffer](../../gateway/setup/04-configure-local-mqtt-buffer.md)
- [Software-only integrity journal](../../gateway/setup/04a-configure-gateway-integrity-journal.md)
- [MQTT Forwarder](../../gateway/setup/05-configure-mqtt-forwarder.md)

Keep UDP Forwarder disabled.

## 11.4 Connect the USB 4G/LTE dongle without losing management access

Keep Ethernet or the currently working management connection attached while commissioning LTE. Do not make LTE the only route until the modem has passed registration, DNS, MQTT, and reconnect tests.

**Why:** if the APN, modem driver, or route is wrong, keeping the known-good management path prevents a remote lockout while you troubleshoot the gateway.

Before plugging in the dongle, confirm the Raspberry Pi power supply is stable. LTE modems can draw short current bursts, especially during network registration or weak-signal transmit. If the modem repeatedly resets, disappears from USB, or the gateway becomes unstable, investigate power before changing network configuration. A powered USB hub is preferable to guessing at modem settings when power is the actual problem.

The current dongle is the **Waveshare SIM7600G-H 4G DONGLE**. Its documented Linux USB networking options include NDIS/RNDIS/PPP, but the module can expose different USB compositions depending on prior configuration. Treat the **currently enumerated interfaces** as authoritative; do not switch USB PID/mode just because an online example uses a different composition.

After inserting the dongle, inspect what Gateway OS/OpenWrt actually detected:

```sh
logread | tail -n 100
dmesg | tail -n 100
lsusb 2>/dev/null || true
ip link
ip addr
uci show network
ubus call network.interface dump
```

Look for the SIMCom/Waveshare USB device and the network/control interfaces it created. For this exact dongle, prefer an already-working USB Ethernet/RNDIS-style interface when Gateway OS supports it because it keeps the data path simple; PPP is a fallback only when the live composition and installed release require it. Do not install QMI/MBIM packages unless the device actually exposes the corresponding `cdc-wdm`/WWAN mode.

Common modem presentations include:

```text
ECM/RNDIS/HiLink-style modem
  -> looks like a USB Ethernet interface
  -> normally receives an address with DHCP

QMI modem
  -> usually exposes a wwan interface plus a cdc-wdm control device
  -> requires the matching QMI support in the pinned OpenWrt build

MBIM modem
  -> usually exposes a wwan interface plus a cdc-wdm control device
  -> requires the matching MBIM support in the pinned OpenWrt build

Older PPP modem
  -> exposes serial ports
  -> use only when that exact modem and Gateway OS release are known to require PPP
```

Do not install every modem package blindly. Identify the dongle mode first, then use the package/LuCI procedure supported by the pinned Gateway OS release.

## 11.4A Configure the carrier/APN

Record the carrier and APN reference outside Git. Configure only the values required by the SIM plan:

```text
APN
PDP/IP family when required
SIM PIN only when enabled
username/password only when the carrier actually requires them
```

Do not assume public IPv4. Most mobile connections may sit behind carrier NAT/CGNAT, which is acceptable for this design because the gateway creates outbound TLS connections to the cloud.

**No inbound port forwarding to the gateway is required.** Do not expose LuCI, SSH, MQTT 1883, or any radio service through the mobile network.

## 11.4B Verify LTE addressing, routing, DNS, and time

Once the LTE interface reports connected, run:

```sh
ip addr
ip route
ubus call network.interface dump
ping -c 4 <APPROVED_TEST_HOST>
nslookup mqtt.<DOMAIN>
date -u
```

When gateway evidence is deployed, also verify:

```sh
nslookup evidence.<DOMAIN>
```

A healthy result shows:

```text
LTE/wwan interface has an address
default route exists through the intended LTE interface
route metric is intentional when Ethernet/Wi-Fi also exists
DNS resolves the cloud MQTT hostname
UTC time is correct enough for TLS validation
basic outbound reachability works
```

Interpret failures in this order:

```text
No modem/interface
  -> USB detection, driver/protocol support, or power problem

Interface exists but has no address
  -> SIM registration, APN, PIN, carrier, or modem-session problem

Address exists but no default route
  -> interface/network or route-metric configuration problem

IP connectivity works but DNS fails
  -> resolver/DHCP/DNS configuration problem

DNS works but MQTT TLS fails
  -> cloud firewall, port 8883, certificate, hostname, client identity, or ACL problem
```

**Why:** this keeps LTE troubleshooting separate from LoRaWAN and MQTT. Do not change the radio region or ChirpStack device configuration to fix a mobile-network routing problem.

## 11.4C Make LTE the intended cloud path

When Ethernet, Wi-Fi, and LTE coexist, choose route metrics deliberately. During commissioning, keep the management route stable and make sure the cloud-bound route behaves as intended.

Verify again:

```sh
ip route
nslookup mqtt.<DOMAIN>
```

Then watch the local Mosquitto bridge logs while sending a real uplink. The success condition is not just "the Internet works"; the gateway must establish the MQTT mTLS session over the intended mobile path and ChirpStack must update gateway last-seen.

## 11.5 Configure the cloud bridge

MQTT Forwarder remains:

```text
Server: tcp://127.0.0.1:1883
QoS: 1
Backend: concentratord
```

Local Mosquitto bridge configuration uses:

```text
address mqtt.<DOMAIN>:8883
bridge CA: cloud broker CA
bridge certificate: unique gateway certificate
bridge key: matching private key
event/state: out QoS 1
command: in QoS 0, clean session
```

## 11.6 Network exposure

The gateway initiates outbound TLS. Do not forward internet ports to LuCI, SSH, local MQTT, journal storage, or radio services. Local 1883 must remain on loopback.

Cloud gateway-facing ingress is limited to:

```text
TCP 8883 -> MQTT mTLS
TCP 443  -> evidence HTTPS/mTLS, only when the reviewed evidence service exists
```

The evidence API does not expose the journal filesystem and MQTT 8883 does not carry journal segment uploads.

## 11.7 Normal-path commissioning verification

Before leaving setup, prove the gateway works **without intentionally breaking its WAN or rebooting it**:

```text
Gateway EUI stable
RAK5146 / AS923 channel plan correct
Concentratord healthy
UDP Forwarder disabled
MQTT Forwarder -> tcp://127.0.0.1:1883, QoS 1
local Mosquitto listener loopback-only
persistent queue path exists, is writable, finite, and has an OS free-space reserve
LTE modem registered with intended APN
LTE interface/address/default route/DNS/UTC time healthy
mqtt.<DOMAIN>:8883 reachable through the intended LTE path
unique gateway mTLS certificate accepted
broker ACL permits only that gateway's approved topics
ChirpStack gateway last-seen updates
one real OTAA and uplink succeed
one safe Class A downlink succeeds only when the device has a reviewed command contract
```

For the integrity-journal feature, normal setup additionally requires a **reviewed, pinned implementation** and a healthy current chain/checkpoint path. Record implementation version/hash, current sequence, record/segment hash, storage budget, and server checkpoint. If the selected full-feature scope requires this feature but the reviewed implementation/server roles do not exist, carry that as a Phase 14B `BLOCKED` item; do not invent a script to make setup look complete.

## 11.8 Failure tests explicitly deferred to Phase 15

Phase 15 owns LTE disconnect/reconnect, persistent queue growth/drain, gateway reboot with queued messages, stale-downlink prevention, duplicate handling after reconnect, journal offline growth/reconciliation, checkpoint non-advancement while offline, and failure-period data-usage observations.

Phase 11 passes on a verified healthy path plus a correctly configured persistent buffer and, when implemented, a healthy integrity chain. RF and UDP controls remain unchanged.

Next required checkpoint: **Phase 13A** in [13-backup-restore-and-disaster-recovery.md](13-backup-restore-and-disaster-recovery.md), then [12-gateway-and-device-migration.md](12-gateway-and-device-migration.md).
