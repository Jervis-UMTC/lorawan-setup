# RAK5146 Gateway OS Reference

```text
Raspberry Pi 4B + RAK5146
  -> Gateway OS Base
  -> Concentratord
  -> MQTT Forwarder, QoS 1 to loopback
  -> local persistent Mosquitto
  -> mTLS bridge
  -> remote broker and ChirpStack
```

Current ChirpStack Gateway Bridge is not used for the RAK5146 Concentratord path because that backend was removed.

## Guides

| Guide | Purpose |
|---|---|
| [01-hardware-architecture-and-assembly.md](01-hardware-architecture-and-assembly.md) | Hardware, power, antenna, and assembly |
| [02-install-chirpstack-gateway-os.md](02-install-chirpstack-gateway-os.md) | Gateway OS Base installation |
| [03-configure-concentratord.md](03-configure-concentratord.md) | RAK5146, Gateway ID, region, and UDP disablement |
| [04-configure-mqtt-forwarder-and-security.md](04-configure-mqtt-forwarder-and-security.md) | Local buffer and MQTT Forwarder summary |
| [05-chirpstack-mqtt-integration.md](05-chirpstack-mqtt-integration.md) | Remote broker ACL and ChirpStack backend |
| [06-rf-planning-antennas-and-site-survey.md](06-rf-planning-antennas-and-site-survey.md) | RF planning and site acceptance |
| [07-security-hardening-and-vpn.md](07-security-hardening-and-vpn.md) | Gateway management and identity lifecycle |
| [08-troubleshooting-and-diagnostics.md](08-troubleshooting-and-diagnostics.md) | Layered diagnostics |

Use the complete current procedure in [../setup/00-README.md](../setup/00-README.md).

Do not transmit until country, region, RAK5146 frequency variant, antenna band/gain, channel plan, and legal TX behavior are verified.
