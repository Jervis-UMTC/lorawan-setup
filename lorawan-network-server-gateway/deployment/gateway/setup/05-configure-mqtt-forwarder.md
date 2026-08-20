# Gateway 5. Configure ChirpStack MQTT Forwarder

MQTT Forwarder receives packets from Concentratord and publishes ChirpStack gateway messages to the local Mosquitto broker. It is the **delivery path**, not the gateway evidence authority.

The independently reviewed journal from Gateway 4A consumes the supported Concentratord event interface beside MQTT Forwarder. This separation lets the server later compare what the journal recorded with what MQTT actually delivered.

For this setup, MQTT Forwarder must not connect directly to the remote broker. The local broker provides TLS, topic bridging, and persistent uplink buffering.

Complete [04-configure-local-mqtt-buffer.md](04-configure-local-mqtt-buffer.md) and [04a-configure-gateway-integrity-journal.md](04a-configure-gateway-integrity-journal.md) before final acceptance.

## Before you begin

Have these values ready:

```text
Gateway EUI: <GATEWAY_EUI>
Region topic prefix: <REGION_TOPIC_PREFIX>
Local broker address: tcp://127.0.0.1:1883
Forwarder client ID: gw-fwd-<GATEWAY_EUI>
```

Confirm the local broker is running:

```sh
ps w | grep '[m]osquitto'
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Continue only when port `1883` is bound to `127.0.0.1`.

## Step 1: Open the MQTT Forwarder page

1. Sign in to the Gateway OS web interface.
2. Open **ChirpStack > MQTT Forwarder**.
3. Select the forwarder instance connected to the configured RAK5146.

The exact field names can vary between Gateway OS releases. Match the settings by purpose rather than copying an option name from another release.

## Step 2: Enable the Concentratord backend

Set the backend fields to the equivalent of:

```text
Enabled: yes
Backend: concentratord
```

Do not select `semtech_udp`. Concentratord is already controlling the RAK5146 and provides the packet stream used by MQTT Forwarder.

## Step 3: Configure packet filtering

Use these normal forwarding settings:

```text
Forward CRC OK packets: enabled
Forward CRC invalid packets: disabled
Forward packets without CRC: disabled unless required by the confirmed radio path
```

CRC-invalid packets are useful only for controlled RF diagnostics. Forwarding them during normal operation adds unusable traffic and can hide radio problems.

When the installed release provides a filter for non-LoRaWAN payloads, keep the setting consistent with the intended network. A normal LoRaWAN-only gateway can filter proprietary non-LoRaWAN frames.

## Step 4: Configure the local MQTT connection

Set:

```text
Server: tcp://127.0.0.1:1883
Topic prefix: <REGION_TOPIC_PREFIX>
QoS: 1
Clean session: false
Client ID: gw-fwd-<GATEWAY_EUI>
Use JSON: disabled
Username: empty
Password: empty
CA certificate: empty
Client certificate: empty
Private key: empty
```

### Why these values are used

- `127.0.0.1` keeps the first MQTT hop inside the gateway.
- QoS 1 makes the local broker acknowledge gateway event and state messages.
- A fixed client ID prevents every restart from appearing as a different client.
- A non-clean session supports reliable reconnect behavior between MQTT Forwarder and the local broker.
- JSON is disabled because ChirpStack uses the Protobuf gateway message format on this path.
- TLS fields are empty because the loopback connection does not leave the gateway. The local Mosquitto bridge holds the remote TLS files.

Do not enter `<MQTT_BROKER_FQDN>` on this page. Doing so bypasses the persistent local queue and can also create unexplained disagreement with the independently designed journal/reconciliation path.

## Step 5: Review metadata and command topics

When the page exposes event, command, state, or metadata topic templates, keep the standard ChirpStack gateway structure under the exact region prefix:

```text
<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/...
<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/...
<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/...
```

Do not remove the Gateway EUI level or replace it with a hostname. The remote broker ACL and ChirpStack gateway lookup depend on this topic structure.

## Step 6: Save the configuration

1. Recheck the Gateway EUI and region prefix.
2. Select **Save & Apply**.
3. Wait for MQTT Forwarder to restart.
4. Refresh the page and confirm the saved values remain present.

## Step 7: Inspect the effective UCI configuration

Run over SSH:

```sh
uci show chirpstack-mqtt-forwarder
monit status
```

Confirm that the effective configuration shows:

- the Concentratord backend;
- `tcp://127.0.0.1:1883`;
- `<REGION_TOPIC_PREFIX>`;
- QoS 1;
- the fixed `gw-fwd-<GATEWAY_EUI>` client ID;
- JSON disabled;
- no remote CA, certificate, or key path.

If the LuCI page does not expose QoS, clean-session, or client-ID fields, inspect the installed package before changing anything:

```sh
opkg list-installed | grep 'chirpstack-mqtt-forwarder'
ps w | grep '[c]hirpstack-mqtt-forwarder'
uci show chirpstack-mqtt-forwarder
```

Use only options supported by that package and its generated configuration. Do not guess UCI keys or edit the init script.

## Step 8: Verify a local gateway event

Open one SSH session and subscribe to this gateway's event topics:

```sh
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t '<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/#' -v
```

Generate one real uplink from an approved LoRaWAN test device.

The subscription should display a topic for the configured Gateway EUI. The payload is binary Protobuf and may appear unreadable in the terminal; the important check here is that a message arrives on the correct topic.

Press `Ctrl+C` after the test.

No message means the failure is before the remote bridge. Check Concentratord, the region prefix, the Gateway EUI, and the local broker before changing remote certificates.

## Step 9: Verify the local listener remains private

Run:

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

The listener must remain `127.0.0.1:1883`. The empty username and password fields are safe only for this loopback-only listener.

## Step 10: Verify UDP Forwarder remains disabled

Run:

```sh
uci show chirpstack-udp-forwarder
```

Remove any enabled remote UDP server through **ChirpStack > UDP Forwarder**. Do not keep UDP as a second path or fallback.

## Troubleshooting

### MQTT Forwarder reports connection refused

Check Mosquitto first:

```sh
ps w | grep '[m]osquitto'
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Start or repair the local broker. Do not replace `127.0.0.1` with the remote broker address.

### No local event appears after an uplink

Check the path in order:

1. Concentratord has a stable Gateway EUI.
2. The device and gateway use the same region and channel plan.
3. MQTT Forwarder uses the Concentratord backend.
4. The topic prefix matches the active region.
5. The local Mosquitto listener is running.

Use the forwarder service messages only after checking the saved settings:

```sh
logread -e chirpstack-mqtt-forwarder
```

### The topic uses the wrong region prefix

Return to Concentratord, confirm the exact channel plan, then update MQTT Forwarder and the local Mosquitto bridge to the same `<REGION_TOPIC_PREFIX>`. The remote ChirpStack server must enable that same region.

### MQTT Forwarder repeatedly restarts

Compare the UCI values with the installed package's supported fields. Remove unsupported guessed options and reapply the configuration through LuCI.

### Local events work but ChirpStack sees nothing

MQTT Forwarder and Concentratord are working. Continue troubleshooting at the local Mosquitto bridge, remote certificate, remote ACL, broker subscription, and ChirpStack region.

## Completion check

Before continuing:

- MQTT Forwarder uses the Concentratord backend;
- the server is `tcp://127.0.0.1:1883`;
- QoS 1 is enabled;
- the client ID is fixed and gateway-specific;
- the topic prefix matches the radio and ChirpStack region;
- JSON is disabled;
- a real local event appears under the correct Gateway EUI;
- no remote TLS files are configured in MQTT Forwarder;
- UDP Forwarder is disabled;
- the evidence journal remains a separate read-only Concentratord consumer and MQTT Forwarder has no permission to rewrite its files.

## Next step

Continue with [06-verify-gateway-os.md](06-verify-gateway-os.md).
