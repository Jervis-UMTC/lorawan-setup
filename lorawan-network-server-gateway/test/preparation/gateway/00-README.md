# Gateway Preparation

Use these manuals to prepare the physical Raspberry Pi 4B + RAK5146 gateway for the dissertation test track.

## Why the setup is split

The server needs the real Gateway EUI before it can create the gateway certificate, broker ACL, and ChirpStack gateway record. Therefore the order is intentionally:

```text
Gateway 01-03
  -> record real Gateway EUI
  -> prepare server and provision that EUI
  -> Gateway 04-06
  -> end-to-end gateway acceptance
```

## Manuals

1. [01-hardware-assembly.md](01-hardware-assembly.md) - assemble Raspberry Pi 4B, RAK5146 SPI HAT, pigtail, and antenna safely.
2. [02-install-chirpstack-gateway-os.md](02-install-chirpstack-gateway-os.md) - install and secure ChirpStack Gateway OS Base and establish management networking/time.
3. [03-configure-concentratord.md](03-configure-concentratord.md) - configure the RAK5146 for the frozen lab **plain AS923** plan, keep the MQTT region topic prefix `as923`, and record the authoritative 16-hex Gateway EUI.
4. **Pause here and complete [../server/](../server/00-README.md).**
5. [04-configure-local-mqtt-buffer.md](04-configure-local-mqtt-buffer.md) - configure bounded persistent local Mosquitto buffering and the server mTLS bridge.
6. [05-configure-mqtt-forwarder.md](05-configure-mqtt-forwarder.md) - publish Concentratord events to `127.0.0.1:1883` at QoS 1.
7. [06-verify-gateway-os.md](06-verify-gateway-os.md) - verify the radio, local MQTT hop, remote bridge, ChirpStack registration, buffering, and recovery behavior.

## Gateway acceptance

The gateway is ready when:

```text
[ ] Gateway OS Base is running with correct UTC time
[ ] RAK5146/SX1303 initializes over SPI
[ ] frozen lab plain AS923 plan is active (not AS923-3)
[ ] MQTT region topic prefix is exactly `as923`
[ ] real Gateway EUI is stable across reboot
[ ] UDP Forwarder is disabled
[ ] MQTT Forwarder publishes to loopback Mosquitto, not directly to the server
[ ] local listener is 127.0.0.1:1883
[ ] gateway mTLS bridge authenticates on server port 8883
[ ] exact-EUI broker ACL works
[ ] ChirpStack gateway Last seen updates for the registered EUI
[ ] real OTAA uplink reaches ChirpStack
[ ] buffered uplinks survive the defined outage/reboot check and drain after reconnect
```
