# Install ChirpStack Gateway OS Base

This reference explains the image choice. Follow the complete executable procedure in [gateway/setup/02-install-chirpstack-gateway-os.md](../setup/02-install-chirpstack-gateway-os.md).

Use only the official Raspberry Pi 4B **Base** factory image. Base provides the gateway radio and forwarding services; **Full** also installs local ChirpStack server components and conflicts with this repository's external-server design.

## Values needed before flashing

| Value | Source | Why it matters |
|---|---|---|
| Raspberry Pi model | Board label | Selects the correct factory-image target |
| RAK5146 SPI variant | Module label | Confirms the later Concentratord profile and RF band |
| Gateway OS release and filename | Official ChirpStack download | Identifies the tested build and rollback image |
| Calculated SHA-256 | Download workstation | Detects accidental changes to the retained image |
| Existing backup location | Encrypted off-gateway storage | Prevents overwriting the only recoverable gateway |

After flashing, set a strong root password, configure the management network, verify DNS and time, disable the setup access point when commissioning is complete, and restrict LuCI and SSH to the management path.

Success means the expected Gateway OS release boots, the management address is reachable, time is synchronized, and the gateway services are supervised without restart loops. Do not continue with an unverified mirror, unknown backup, Raspberry Pi OS, or vendor image used as a fallback.
