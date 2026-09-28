# Gateway OS production image overlay

This directory is the reproducible, non-secret overlay for the commissioned Gateway OS v4.12.0 factory image. Copy `files/` into the selected Gateway OS environment `conf/files/`, merge `package.config.fragment` into the environment `.config`, run OpenWrt `defconfig`, then build through the pinned Gateway OS Docker build environment.

The overlay intentionally contains only defaults safe to bake into a factory image:

- ChirpStack Concentratord enabled for `sx1302`, model `rak_5146`, region `AS923`, channel plan `as923`, GNSS enabled;
- normal ChirpStack MQTT Forwarder enabled with topic prefix `as923` and local broker `tcp://127.0.0.1:1883`;
- UDP Forwarder disabled;
- `mosquitto-ssl` selected and configured as a loopback-only local broker with persistent storage under `/etc/mosquitto/data`;
- `98_prepare_local_mosquitto` creates the persistent broker directories during `S10boot`, before `S80mosquitto` starts;
- SIM7600/QMI packages and `gateway-evidence` selected by `package.config.fragment`.

Do not place Wi-Fi credentials, SSH host keys, MQTT bridge client keys/certificates, gateway-evidence mTLS keys/certificates, or other private material here. Production bridge/evidence credentials are provisioned separately after flash through the protected secret/recovery process.

The proven profile remains `bcm27xx/bcm2709 DEVICE_rpi-2` even though the hardware is Raspberry Pi 4; changing profile solely to match the board name would discard the known-working baseline.

Current flash-ready factory release (2026-09-01):

- file: `chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz`
- bytes: `28900364`
- SHA-256: `bafe8b97baf9353df2654b1c8b71fa53d2ff764cd264d0ed6c924dd25a5ec67d`
- Windows recovery copy: `C:\Users\smartagriintern\lorawan-recovery\gateway-01\custom-v4.12.0-sim7600-as923-journal-20260901`

The image was accepted only after generated checksum verification, gzip/partition validation, independent SquashFS extraction, manifest inspection, boot-link inspection, AS923-1 channel-file checks, SIM7600 kernel-module checks, local Mosquitto checks, gateway-evidence service-default checks, and a scan confirming no gateway-evidence TLS secrets were embedded.

### Physical clean-overlay correction - 2026-09-02

Physical Gateway-01 commissioning independently re-extracted this exact accepted factory artifact and confirmed that its immutable SquashFS contains no production MQTT bridge configuration/certificates, no Evidence mTLS credentials, and no `gateway-commissioning-relay` host overrides. The reused microSD nevertheless booted with those files because stale writable OverlayFS state survived outside the compact factory-image write. OpenWrt `jffs2reset` was therefore used deliberately to erase only writable overlay state, followed by protected reprovisioning and a reboot acceptance.

That same offline inspection exposed one immutable-release mismatch: the already-accepted 2026-09-01 SquashFS contains MQTT Forwarder `qos '0'`. The tracked overlay in this directory is corrected to `qos '1'` for any future deliberate rebuild, while the currently commissioned Gateway-01 has QoS 1 explicitly persisted in its clean writable overlay. **Do not rebuild the current gateway solely for this corrected default**; its accepted image hash remains authoritative and its live runtime has already passed QoS-1/cloud/reboot verification.

For future reused-card flashes, run `../automation/commission-clean-overlay.sh preflight` before restoring production credentials. A fresh target that already contains bridge/evidence private keys or commissioning relay host overrides must be treated as stale-overlay evidence, not as proof that secrets were baked into this image.

## LTE-primary health-based routing

The overlay installs `/usr/sbin/lte-route-health` and `/etc/init.d/lte-route-health`. The commissioned field topology uses the SIM7600 QMI `wwan0` interface as the normal production Internet uplink; RJ45/`br-lan` at `192.168.20.11` is management-only. No automatic Wi-Fi Internet fallback is part of this commissioned topology unless one is deliberately configured separately. The logical LTE interface keeps `defaultroute=0` and `peerdns=1`, so the route manager—not netifd—owns the production default while DITO's QMI DNS servers remain available. Whenever QMI reports a valid IPv4 address and gateway, the controller first installs or refreshes an LTE default route at metric 10 and then verifies the production MQTT mTLS path to `129.212.208.168:8883`. A failed broker/TLS probe does **not** remove an otherwise valid LTE default route, because doing so would also strand DNS, NTP, and autonomous recovery; the LTE route is removed only when the current QMI session no longer supplies a usable address or gateway. The daemon reevaluates the path every 30 seconds and recovers automatically after boot or PDP-address changes. Dataplane health is evaluated separately from broker health: two consecutive public-IP dataplane failures trigger a bounded `ifdown lte` / `ifup lte` recovery; if the dataplane is still unavailable shortly after that recovery, the daemon may reset only the SIM7600 with the proven `AT+CFUN=1,1` sequence. The modem-reset path waits for USB/QMI disappearance and re-enumeration, has a 15-minute reset cooldown, and never triggers merely because the production broker/TLS probe is down while general LTE IP connectivity is healthy. On 2026-09-16 both stages were exercised live over Ethernet management: stage 1 recovered a stale QMI session, and stage 2 re-enumerated the modem, obtained a fresh DITO PDP address, restored metric-10 LTE, DNS, public IP reachability, and production MQTT mTLS. `97_lte_primary_failover` makes this policy reproducible on a fresh overlay.
