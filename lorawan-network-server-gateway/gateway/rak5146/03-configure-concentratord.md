# Configure Concentratord for RAK5146

The complete procedure is maintained here:

[gateway/setup/03-configure-concentratord.md](../setup/03-configure-concentratord.md)

## Web interface path

```text
ChirpStack > Concentratord
```

Set:

```text
Chipset: SX1302 / SX1303
Shield: RAK5146
Channel plan: <CONFIRMED_GATEWAY_OS_CHANNEL_PLAN>
```

Click **Save & Apply** and wait for the radio to initialize. Keep the 16-hexadecimal Gateway EUI shown in the footer; it is used by the certificate, MQTT topics, ACL, client IDs, and ChirpStack registration.

## Verify over SSH

```bash
uci show chirpstack-concentratord
monit status
logread -e chirpstack-concentratord
```

Pass when the RAK5146 initializes, the Gateway EUI remains stable across refresh and reboot, and no repeated SPI, reset, SX1250, clock, calibration, or restart error appears. A missing or changing EUI means the hardware path is not ready for registration.

## Disable UDP Forwarder

```text
ChirpStack > UDP Forwarder
```

Remove all servers and disable every slot. Verify:

```bash
uci show chirpstack-udp-forwarder
```

Do not use UDP as a fallback.
