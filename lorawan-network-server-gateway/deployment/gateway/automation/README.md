# Gateway clean-overlay commissioning automation

Use `commission-clean-overlay.sh` after flashing the accepted Gateway OS factory image when Gateway-01 must be commissioned from a known-clean writable overlay. The script contains no Wi-Fi password, private key, client certificate, or other production secret.

The physical 2026-09-02 commissioning exposed an important OpenWrt storage behavior on reused media: rewriting the compact factory image did not guarantee that the expanded writable OverlayFS area was clean. Gateway-01 initially booted with old bridge certificates, old Mosquitto bridge configuration, and commissioning-only `/etc/hosts` entries even though independent SquashFS extraction proved those files were not present in the accepted image. `jffs2reset` removed that stale writable state; the gateway was then reprovisioned from the immutable factory image plus authoritative external identities and passed a reboot.

## Safe workflow

1. Boot the freshly flashed gateway through local Ethernet or the normal commissioning AP.
2. Run `commission-clean-overlay.sh preflight` **before copying production credentials**. A fresh provisioning target must not already contain the MQTT bridge private key, Evidence private key, bridge configuration, or `gateway-commissioning-relay` host entries.
3. If preflight reports stale writable state and the gateway is intentionally being rebuilt from scratch, preserve any required recovery material off-device, then run OpenWrt `jffs2reset` manually and reboot. The script never erases the overlay automatically.
4. Remove the factory-empty root password condition with `passwd` and install an authorized admin SSH key through the protected operator process.
5. Stage the protected identities outside Git under the gateway at the default `/tmp/gateway-provision/` layout:

```text
/tmp/gateway-provision/
├── mqtt/
│   ├── ca.crt
│   ├── client.crt
│   └── client.key
└── evidence/
    ├── ca.crt
    ├── client.crt
    └── client.key
```

6. Supply Wi-Fi only through environment variables and apply:

```sh
WIFI_SSID='<ssid>' \
WIFI_PSK='<protected-psk>' \
sh ./commission-clean-overlay.sh apply
```

Do not save the PSK in this repository or shell history. Use an operator method that prevents credential logging when available.

7. Reboot once, then run:

```sh
sh ./commission-clean-overlay.sh verify
```

The verification requires RAK5146 + `AS923/as923`, Gateway EUI `0016c001f139a1cb`, permanent Ethernet management at `192.168.20.11/24`, Wi-Fi as the default route, MQTT Forwarder QoS 1 to `tcp://127.0.0.1:1883`, strict public MQTT mTLS, two established MQTT bridge sockets, Evidence mTLS readiness, and running writer/uploader services.

The script deliberately does **not** claim a gateway Evidence segment receipt until a real LoRaWAN uplink reaches Concentratord after commissioning. That first-sensor boundary was historically executed through `../../../TOMORROW-SENSOR-GATEWAY-BRINGUP.md`; current research acceptance and repeated evidence capture use `../../../test/preparation/sensor/preflight/00-README.md` and `../../../test/automation/research-recorder/README.md`.
