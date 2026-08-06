# Gateway Documentation

This folder covers the physical LoRaWAN gateway and the services that run on it. The gateway receives LoRa radio frames and forwards them; ChirpStack device management and application processing remain on the server.

## Current data path

```text
RAK5146
  -> ChirpStack Concentratord
  -> ChirpStack MQTT Forwarder
  -> local persistent Mosquitto
  -> mutual-TLS bridge
  -> remote MQTT broker and ChirpStack
```

Concentratord owns the RAK5146. MQTT Forwarder converts its packet stream into ChirpStack gateway MQTT topics. Local Mosquitto then provides a bounded persistent queue for uplink and gateway-state messages when the remote broker is unavailable.

## Folders

| Folder | Purpose |
|---|---|
| [setup/](setup/00-README.md) | Complete Gateway OS installation, local uplink buffer, MQTT Forwarder, and verification |
| [operations/](operations/01-register-and-test.md) | Registration, backup, availability tests, migration, and troubleshooting |
| [rak5146/](rak5146/README.md) | Reusable RAK5146 hardware, RF, security, and diagnostics |
| [references/](references/README.md) | Hardware checklist and vendor PDF references |
| [archive/](archive/01-hardware-assembly.md) | Retired manuals kept only as non-deployable pointers |

## Buffering requirement

The gateway must retain uplink and gateway-state MQTT messages during a bounded WAN or remote-broker outage. The queue must:

- persist across broker and gateway reboot;
- use QoS 1 for uplink and state traffic;
- have finite message and byte limits;
- reside on verified persistent storage, not `/tmp` or an unverified `/var` path;
- expose no network listener beyond loopback;
- drain after connectivity returns;
- tolerate duplicate delivery through downstream idempotency;
- avoid delayed replay of stale downlink commands.

A healthy result is a queue that grows only during a tested outage, survives reboot, and drains after the remote path returns. Continuous growth during normal connectivity means the TLS, DNS, route, broker, certificate, or ACL path is still failing.

Proceed to [setup/00-README.md](setup/00-README.md).
