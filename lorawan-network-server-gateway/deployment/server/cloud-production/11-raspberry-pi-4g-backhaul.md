# 11. Gateway OS Delivery Buffer and Integrity Journal over a USB 4G/LTE Dongle

> **Current status: BUILD/LTE/CLOUD NORMAL-PATH COMMISSIONING SUBSTANTIALLY PASS; FINAL PHYSICAL RF ACCEPTANCE REQUIRED.** The accepted 2026-09-01 Gateway OS image includes AS923, SIM7600/QMI, Mosquitto, and the gateway-evidence writer. Historical build/probe failures below are retained only as troubleshooting evidence. For the next physical session use `../../../TOMORROW-SENSOR-GATEWAY-BRINGUP.md`; do not reconstruct the workflow from old continuation checkpoints or repeat passed server/build work. Provider Reserved-IP failover authority and external Fabric execution remain separate acceptance boundaries. **Do not perform LTE-outage, gateway-reboot, broker-loss, or queue-drain failure experiments here; Phase 15 owns those tests after the full setup gate passes.**

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

**Historical handoff note (superseded):** at this point on 2026-08-27 the corrected build was still compiling. Later sections prove the build, flash, SIM7600/QMI runtime, LTE path, and the newer 2026-09-01 flash-ready AS923+journal release. Do not use this paragraph as current state.

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

### Phase 11 current continuation after custom-image cutover - 2026-08-28

The custom Gateway OS image has now booted successfully with SIM7600 support. Runtime proof shows `1e0e:9001`, `option`, `usb_wwan`, `qmi_wwan`, `cdc_wdm`, `/dev/ttyUSB0..4`, `/dev/cdc-wdm0`, and modem interface `wwan0`. The verified Gateway OS configuration was restored, the Mosquitto packages were reinstalled after the factory flash, the protected `/etc/mosquitto` tree was restored, and the local broker again listens only on `127.0.0.1:1883`. MQTT Forwarder reconnects locally as Gateway EUI `0016c001f139a1cb`. The old `lora-test-server:8883` bridge is retired from the active production path.

Do **not** wait idly for the public domain before continuing. The next provider-independent server step is to finish the cloud gateway MQTT authentication boundary: the current cloud `:8884` listener is server-TLS only (`require_certificate=false`) and no cloud-issued gateway client certificate is recorded. Issue the cloud `clientAuth` identity for EUI `0016c001f139a1cb`, install the exact `as923` EUI ACL, harden `:8884` to client-certificate authentication canary-first on both brokers, and prove it through the existing anchor `:8883` paths using `mqtt.internal.lorawan.com`. Public FQDN/Reserved-IP/DNS activation follows afterward.

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


## 11.9 Verified SIM7600 / DITO QMI commissioning path - 2026-08-28

This section is the **known-good path that actually succeeded on the physical gateway**. Use it for the next gateway or for recovery after a clean Gateway OS restore. It intentionally omits failed probe variants and keeps only the commands and checkpoints that produced authoritative PASS results.

### 11.9.1 Preserve one management path during LTE commissioning

The gateway management Wi-Fi is the OpenWrt logical interface `wwan`, not the SIM7600 data interface:

```text
Wi-Fi logical interface: wwan
Wi-Fi kernel device:      phy0-sta0
Management IPv4:          192.168.8.11/24
Management gateway:       192.168.8.1
SIM7600 logical interface: lte
SIM7600 kernel device:     wwan0
QMI control device:        /dev/cdc-wdm0
```

During this commissioning run, Ethernet and Wi-Fi were both attached to the same `192.168.8.0/24` network. Ethernet obtained `192.168.8.131` while Wi-Fi remained `192.168.8.11`, and the default route temporarily preferred `br-lan`. Unplugging Ethernet removed the same-subnet multi-homing ambiguity. Keep Ethernet unplugged while repeating this procedure unless Ethernet and Wi-Fi are intentionally placed on different subnets or explicit route metrics have been designed.

The restored configuration also contained an unintended DHCP server on the upstream Wi-Fi client interface. Disable that once:

```sh
uci set dhcp.wwan.ignore='1'
uci commit dhcp
/etc/init.d/dnsmasq restart
```

**Why:** `wwan` is a Wi-Fi client on the upstream LAN. It must not hand out leases on `lorawan5`; the upstream router is the DHCP authority.

### 11.9.2 Confirm the rebuilt Gateway OS exposes the proven QMI path

The custom Gateway OS build already proved this runtime topology:

```text
SIM7600 USB ID: 1e0e:9001
serial devices: /dev/ttyUSB0 .. /dev/ttyUSB4
QMI control:    /dev/cdc-wdm0
QMI netdev:     wwan0
loaded path:    option + usb_wwan + qmi_wwan + cdc_wdm
```

The required packages on the successful gateway are:

```sh
opkg list-installed | grep -E '^(uqmi|luci-proto-qmi|kmod-usb-net-qmi-wwan) '
```

Verified installed packages:

```text
kmod-usb-net-qmi-wwan - 6.6.141-r1
luci-proto-qmi - 26.148.37199~3cf713a
uqmi - 2025.07.30~7914da43-r2
```

Do not repeat the package/driver inventory during normal recovery if `/dev/cdc-wdm0` and `wwan0` already exist and the above packages remain installed.

### 11.9.3 Use the proven SIM7600 AT port

A BusyBox-compatible reader-first probe proved both `/dev/ttyUSB2` and `/dev/ttyUSB3` are AT-capable. Use `/dev/ttyUSB2` for the normal status checks.

The successful modem status set was:

```text
AT+CPIN?
AT+CSQ
AT+CEREG?
AT+COPS?
```

Verified responses:

```text
+CPIN: READY
+CSQ: 22,99
+CEREG: 0,1
+COPS: 0,0,"515 66 DITO",7
```

Interpretation:

- `+CPIN: READY` = SIM present and not waiting for a PIN.
- `+CSQ: 22,99` = usable/strong radio signal during commissioning.
- `+CEREG: 0,1` = registered on the home LTE network.
- `+COPS: ... "515 66 DITO",7` = registered to DITO using LTE access technology.

Do not send `AT+CUSBPIDSWITCH`; the current USB composition is already working.

### 11.9.4 Read the PDP contexts before configuring OpenWrt

Use the proven AT port and query the modem instead of guessing its current data contexts:

```text
AT+CGDCONT?
```

Verified result:

```text
+CGDCONT: 1,"IP","","0.0.0.0",0,0,0,0
+CGDCONT: 2,"IPV4V6","ims","0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0",0,0,0,0
+CGDCONT: 3,"IPV4V6","","0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0",0,0,0,1
```

CID 2 is the carrier IMS context and must not be repurposed. The normal data context had no APN configured. The DITO packet-data APN used successfully by this gateway is:

```text
internet.dito.ph
```

No carrier username or password was required.

### 11.9.5 Prove the LTE logical name is free and preserve Wi-Fi `wwan`

Before creating the LTE interface, the successful pre-mutation state was:

```sh
uci -q show network.lte || echo 'LTE_INTERFACE_ABSENT=YES'
uci show network.wwan
ls -l /dev/cdc-wdm0 /sys/class/net/wwan0
```

Expected important state:

```text
LTE_INTERFACE_ABSENT=YES
network.wwan.ipaddr='192.168.8.11'
network.wwan.gateway='192.168.8.1'
/dev/cdc-wdm0 exists
/sys/class/net/wwan0 exists
```

**Why:** OpenWrt logical `wwan` is the management Wi-Fi interface, while Linux kernel `wwan0` is the modem netdev. The cellular logical interface is therefore named `lte` to avoid a namespace collision.

### 11.9.6 Create the QMI LTE interface without changing the default route

The exact configuration that succeeded is:

```sh
uci set network.lte='interface'
uci set network.lte.proto='qmi'
uci set network.lte.device='/dev/cdc-wdm0'
uci set network.lte.apn='internet.dito.ph'
uci set network.lte.auth='none'
uci set network.lte.pdptype='IP'
uci set network.lte.defaultroute='0'
uci set network.lte.peerdns='0'
uci commit network
```

Verify before activation:

```sh
uci show network.lte
```

Known-good stanza:

```text
network.lte=interface
network.lte.proto='qmi'
network.lte.device='/dev/cdc-wdm0'
network.lte.apn='internet.dito.ph'
network.lte.auth='none'
network.lte.pdptype='IP'
network.lte.defaultroute='0'
network.lte.peerdns='0'
```

`defaultroute=0` and `peerdns=0` are deliberate commissioning controls. They allow the LTE packet-data session to come up without replacing the working Wi-Fi management/default path before the real public MQTT endpoint is ready.

### 11.9.7 Bring up QMI and verify the dynamic IPv4 child interface

Activate LTE:

```sh
ifup lte
sleep 10
ubus call network.interface.lte status
ubus list 'network.interface.*' | grep lte
ubus call network.interface.lte_4 status
ip -4 addr show dev wwan0
ip -4 route
```

Verified parent state:

```text
network.interface.lte: up
l3_device: wwan0
proto: qmi
cid_4: 18
pdh_4: present
```

Verified dynamic child state:

```text
network.interface.lte_4: up
proto: dhcp
device: wwan0
IPv4: 100.73.25.125/30
carrier gateway/DHCP server: 100.73.25.126
carrier DNS: 131.226.72.19, 131.226.73.19
```

The carrier default route and peer DNS remain **inactive** at this stage because `network.lte.defaultroute=0` and `network.lte.peerdns=0` were intentionally set.

### 11.9.8 Prove real Internet traffic over LTE without replacing Wi-Fi routing

Use one temporary host route so the test destination is forced through DITO while the gateway's normal default route remains untouched:

```sh
ip route add 1.1.1.1/32 via 100.73.25.126 dev wwan0 src 100.73.25.125
ip route get 1.1.1.1
ping -c 4 -W 3 1.1.1.1
RC=$?
ip route del 1.1.1.1/32 via 100.73.25.126 dev wwan0 2>/dev/null || true
echo "LTE_PUBLIC_PING_EXIT=$RC"
ip route
```

Verified route selection:

```text
1.1.1.1 via 100.73.25.126 dev wwan0 src 100.73.25.125
```

Verified public connectivity:

```text
2 replies from 1.1.1.1 out of 4 probes
LTE_PUBLIC_PING_EXIT=0
```

The observed 50% packet loss is recorded for later link-quality monitoring, but it does not invalidate the commissioning result: public IPv4 traffic was proven end-to-end through the DITO LTE data path and the temporary route was removed afterward.

### 11.9.9 Current verified Phase 11 LTE boundary

The following are now authoritative PASS results:

```text
SIM7600 USB/serial/QMI driver path          PASS
SIM present and PIN-unlocked                PASS
DITO LTE registration                       PASS
DITO APN identified                         PASS
OpenWrt logical lte interface created       PASS
QMI packet-data session established         PASS
LTE child IPv4 lease                        PASS
Carrier gateway and DNS learned             PASS
Public IPv4 traffic over LTE                 PASS
Wi-Fi management path preserved             PASS
Unintended Wi-Fi DHCP service disabled      PASS
```

Current staged topology:

```text
Gateway applications / Mosquitto bridge
              |
              | normal route NOT switched yet
              v
Wi-Fi management: wwan / phy0-sta0 / 192.168.8.11

SIM7600 QMI staging path:
logical lte
   |
/dev/cdc-wdm0
   |
qmi_wwan
   |
wwan0 = 100.73.25.125/30
   |
DITO gateway = 100.73.25.126
   |
Public Internet = proven
```

Do **not** change `network.lte.defaultroute` to `1` yet. The remaining cutover blocker is the production public MQTT path:

```text
mqtt.<REAL-DOMAIN>:8883
        -> Reserved Public IPv4
        -> HAProxy public ingress
        -> Mosquitto HA gateway listener
```

First commission the real public FQDN, Reserved IPv4, firewall `8883/tcp`, DNS, and broker certificate SAN for that hostname. Then validate the gateway bridge against the real endpoint with mTLS. Only after that proof should LTE become the gateway's intended normal/default route.
