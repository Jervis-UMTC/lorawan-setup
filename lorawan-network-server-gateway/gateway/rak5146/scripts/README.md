# Scripts

No automated gateway installer is supported.

ChirpStack Gateway OS must be installed from the official Raspberry Pi 4B Base factory image. A shell script must not replace the image-selection, checksum, backup, RF, certificate, and acceptance gates.

Use:

- [../02-install-chirpstack-gateway-os.md](../02-install-chirpstack-gateway-os.md)
- [../03-configure-concentratord.md](../03-configure-concentratord.md)
- [../04-configure-mqtt-forwarder-and-security.md](../04-configure-mqtt-forwarder-and-security.md)

`install-rak-gateway.sh` is retained only as a non-mutating retirement notice. It exits before making changes.
