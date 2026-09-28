# Gateway-01 — Reproducible Hardware, Gateway OS, and Protected Recovery

> Scope: Consolidated procedure derived from the project’s actual Gateway OS overlay and commissioned gateway/setup/recovery notes as inspected on 2026-09-21. It is **not** a fresh physical rebuild or permission to overwrite the running gateway. Verify protected inventory and effective runtime before making a change.

## What the reader is rebuilding

Gateway-01 is a Raspberry Pi 4B with a RAK5146-115 SPI concentrator and LoRa antenna. It boots **ChirpStack Gateway OS Base 4.12.0**, an OpenWrt-class image, not Raspberry Pi OS or ChirpStack Gateway OS Full. The custom image adds the ABI-matched SIM7600/QMI driver stack, loopback-only persistent Mosquitto and gateway-evidence packages; the deployed configuration additionally provisions protected MQTT and evidence-upload identities. The actual LoRaWAN channel-plan label is **plain `AS923`**, MQTT prefix `as923`, and the accepted RAK5146 Gateway EUI is `0016c001f139a1cb`.

The selected working build environment is `base_raspberrypi_bcm27xx_bcm2709` / `bcm27xx/bcm2709` (`DEVICE_rpi-2`), even though the physical board is a Raspberry Pi 4B. Do not change target solely because its name looks counterintuitive.

## 1. Identify the physical parts with power disconnected

Required: Raspberry Pi 4B, RAK5146-115 **SPI** module (mPCIe-shaped connector is **not PCIe data**), correct RAK Pi HAT, standoffs and screws, 900–930 MHz compatible LoRa antenna/pigtail, SIM7600G-H dongle with adequate USB/power, stable Raspberry Pi power supply, and microSD card. Never connect/disconnect the HAT or module under power.

1. With power off, insert RAK5146 into the HAT's intended module socket at a shallow angle; screw it down without bending the board.
2. Press its LoRa u.FL pigtail **straight down** onto the LoRa RF connector, not the GNSS connector. Attach the matching LoRa antenna to the external SMA connector before powering on.
3. Align HAT with all 40 Raspberry Pi header pins and mount on standoffs; inspect for a one-pin offset, exposed contacts, pinched cables and loose metal.
4. Connect the SIM7600 only to its commissioned USB/power connection. Do not change modem USB composition with AT commands while rebuilding software.
5. Insert the verified factory-image microSD only after the flash and checksum steps below.

**Stop** on uncertain band, variant, seating, power quality, or antenna connection.

## 2. Prepare four off-gateway recovery sets *before* a reflash

| Set | Preserve and protect |
|---|---|
| Factory image | Exact tested factory `.img.gz`, size and SHA-256, plus a compatible spare image if applicable. |
| Gateway configuration | Encrypted Gateway OS backup, UCI/service settings, original management IP/routing, active channel plan, broker queue configuration. |
| Protected identities and persistent delivery | Encrypted MQTT broker CA/client certificate/private key and evidence-upload CA/client certificate/private key, service-specific permissions, retained Mosquitto data when continuity requires it. Never put key bodies in Markdown or Git. |
| Evidence continuity | Gateway journal implementation/version/hash, last valid sequence/record hash/segment hash, unuploaded closed segment inventory and **latest server-accepted checkpoint/receipt**. |

The **accepted custom production-image checkpoint** is:

```text
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz
28900364 bytes
SHA-256 bafe8b97baf9353df2654b1c8b71fa53d2ff764cd264d0ed6c924dd25a5ec67d
```

A separate historical **unmodified factory rollback** is recorded with a different size/hash (`27606919` bytes / `395e79...`); it is **not** interchangeable with the accepted custom SIM7600-capable image. Resolve the file's true identity from its SHA-256, not just its basename.

On Windows, substitute the actual approved protected-image path:

```powershell
$Image = Read-Host 'Absolute path to approved Gateway OS factory image (.img.gz)'
if (-not (Test-Path -LiteralPath $Image -PathType Leaf)) { throw 'Image not found' }
Get-Item -LiteralPath $Image | Select-Object Name,Length
Get-FileHash -LiteralPath $Image -Algorithm SHA256
```

For the accepted custom release, **both** file length and hash must match exactly. If not, stop; do not flash. Hashes for a future intentional build must come from that build’s recorded manifest, not this older artifact.

## 3. Flash and perform a clean first boot (only when an approved rebuild is necessary)

1. Preferred: use a **spare microSD**. With a single production card, first preserve and verify the four recovery sets, SD-card writer and maintenance/recovery window.
2. In Raspberry Pi Imager select *Use custom* and the approved `.img.gz` image. Confirm the correct physical card, write and verify. Decline Raspberry Pi OS customization.
3. Ignore Windows prompts to format OpenWrt/Linux partitions after flashing.
4. Power off gateway, insert card, connect matched antenna and management Ethernet, then power on and allow initialization/partition expansion to complete.
5. On reused media, the compact image may leave the **old writable OverlayFS** beyond the written image. **Before provisioning credentials**, use the tracked `commission-clean-overlay.sh preflight` to detect stale bridge certificates/configuration/commissioning host overrides. Only for an intentional clean rebuild with verified off-device copies, perform a separately approved `jffs2reset` and reboot. Never use `jffs2reset` as routine troubleshooting.
6. Change the factory-empty root password immediately via approved local administration, record it in protected credential storage outside Git, then restrict SSH management access. Do not place passwords or AppKeys into these Markdown documents.

The **management Ethernet checkpoint** is `192.168.20.11/24` on `br-lan`, with **no production default route via Ethernet**. Verify the actual current interface before reconfiguring management access.

## 4. Verify the actual radio and forwarding layout

On the Gateway-01 OpenWrt/BusyBox shell:

```sh
ubus call system board
date -u
df -h
uci show chirpstack-concentratord
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
logread -e chirpstack-concentratord | tail -n 100
```

**PASS:** active `sx1302` config uses `model=rak_5146`, `region=AS923`, `channel_plan=as923`, Gateway EUI `0016c001f139a1cb` appears in the **active Concentratord startup**, MQTT Forwarder is enabled toward `tcp://127.0.0.1:1883`, prefix `as923`, QoS `1`, and UDP Forwarder is disabled. Ignore inactive SX1301 placeholder settings. Do not paste UCI fields containing secrets into a research log.

**Known image-vs-runtime issue:** the accepted 2026-09-01 factory SquashFS included MQTT Forwarder QoS `0`. The tracked **future-build overlay** is corrected to `1`, and the commissioned Gateway-01 runtime has the correction in writable state. On a new flash, explicitly check QoS `1` after applying the protected configuration. Do not reflash a currently working gateway simply to correct the image default.

Confirm local broker listener before sending real traffic:

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

**PASS:** loopback-only `127.0.0.1:1883`, not `0.0.0.0:1883` or the LAN/WAN address. With a currently approved sensor uplink expected, subscribe briefly to `as923/gateway/0016c001f139a1cb/event/#` using the service-native MQTT procedure. A binary Protobuf body is normal. Absence of sensor hardware is **NOT TESTED**, not proof of a working RF layer.

## 5. Restore identities and continuity safely

Restore only the currently authorized protected MQTT/evidence identity bundles; verify file ownership and permissions without printing private-key bodies. Ensure local Mosquitto persistence is on durable storage, not `/tmp`, and the gateway evidence writer/uploader have their reviewed state/data paths.

**Never restore an older journal sequence behind a newer accepted cloud checkpoint.** Before starting new journal writes on recovered media, compare local last valid record/segment hashes and sequence to the server’s latest accepted anchor. If the backup predates the cloud checkpoint, stop and use the governed recovery/new-epoch procedure; do not truncate server metadata or silently restart at GENESIS.

## 6. Verify normal LTE/mTLS plus one representative real event

The gateway LTE route manager owns the production metric-10 default route. Use the LTE guide's QMI/route/bridge checks, not a manual Ethernet default. For an approved real sensor uplink, verify RF reception, local MQTT, LTE-established cloud bridge, ChirpStack acceptance, normalized PostgreSQL measurements, independent evidence verification, then an **eligible** finalized Fabric outbox record reaching authoritative commit/query/digest. Each stage has its own success criterion: `/readyz`, an `ESTABLISHED` socket or a Grafana chart alone cannot prove all stages.

## 7. Restore acceptance and hard stops

**Restore PASS:** intended OS/image identity, Gateway EUI, active AS923 plan, independent evidence journal, loopback QoS-1 local broker and durable queue, two intended remote mTLS bridges over LTE, verified data path, successful downlink if approved, and exact validated journal continuity. Perform outage/reboot/failover trials only when reacceptance calls for them and no counted experiment is in progress.

**Never as a shortcut:** force-install foreign OpenWrt kernel modules; replace `bcm2709` build profile on guesswork; reset source evidence to hide a mismatch; copy unrestricted keys to Git/PDF; place production data traffic on management Ethernet; delete `mosquitto.db` or retained journal files to make a dashboard green.
