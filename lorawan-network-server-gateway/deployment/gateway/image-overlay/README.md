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