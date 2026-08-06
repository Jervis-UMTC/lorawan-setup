# Gateway 5. Configure ChirpStack MQTT Forwarder

MQTT Forwarder reads ChirpStack Protobuf packets from Concentratord and publishes them only to the local Mosquitto broker. The local broker owns the remote TLS certificates, persistent uplink queue, and WAN bridge.

Complete [04-configure-local-mqtt-buffer.md](04-configure-local-mqtt-buffer.md) first.

## Step 1: Open MQTT Forwarder

In Gateway OS:

```text
ChirpStack > MQTT Forwarder
```

Select the slot connected to the commissioned RAK5146.

## Step 2: Configure the Concentratord backend

```text
Enabled: yes
Backend: concentratord
Forward CRC OK: yes
Forward CRC invalid: no, unless a controlled RF test requires it
Forward CRC missing: no, unless the approved hardware path requires it
```

Do not select `semtech_udp`.

## Step 3: Configure the loopback MQTT connection

Set the values supported by the pinned Gateway OS release:

```text
Topic prefix: <CONFIRMED_REGION_TOPIC_PREFIX>
Use JSON: disabled
Server: tcp://127.0.0.1:1883
QoS: 1
Clean session: false
Client ID: gw-fwd-<GATEWAY_EUI>
Username: empty
Password: empty
CA certificate: empty
TLS certificate: empty
TLS key: empty
```

`<CONFIRMED_REGION_TOPIC_PREFIX>` is the effective prefix checked after Concentratord configuration. `<GATEWAY_EUI>` is the stable 16-hexadecimal Gateway EUI shown by Concentratord. `gw-fwd-` plus that EUI is 23 characters, which fits the MQTT Forwarder client-ID limit documented for the current configuration.

QoS 1 requests broker acknowledgement and can be delivered more than once after a reconnect; downstream storage must deduplicate. The local listener is anonymous only because it is bound exclusively to loopback. Do not use this configuration with a LAN- or WAN-facing listener.

Click **Save & Apply**.

If the LuCI page does not expose QoS, clean-session, or client-ID fields, inspect the pinned package's generated configuration and supported UCI schema. Do not invent UCI option names or modify the init script blindly.

## Step 4: Inspect effective configuration

```sh
uci show chirpstack-mqtt-forwarder
monit status
logread -e chirpstack-mqtt-forwarder
logread -e mosquitto
```

Healthy evidence:

- backend is `concentratord`;
- server is `tcp://127.0.0.1:1883`;
- QoS is `1`;
- client ID is fixed and gateway-specific;
- topic prefix matches the active ChirpStack region;
- JSON is disabled;
- no direct WAN broker certificate is configured in MQTT Forwarder;
- the local broker accepts event and state publishes.

If MQTT Forwarder restarts repeatedly, reports connection refusal, or publishes no local events, compare the rendered UCI values with the fields above, confirm Mosquitto is listening on loopback, and inspect Concentratord before changing any remote broker setting.

## Step 5: Verify local-only exposure

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Pass only when the listener is `127.0.0.1:1883`.

## Step 6: Verify UDP Forwarder remains disabled

```sh
uci show chirpstack-udp-forwarder
monit status
```

No remote UDP server may be configured.

Continue with [06-verify-gateway-os.md](06-verify-gateway-os.md).
