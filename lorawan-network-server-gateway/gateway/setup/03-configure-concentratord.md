# Gateway 3. Configure Concentratord for RAK5146

Concentratord is the Gateway OS service that controls the RAK5146 radio and exposes packets to MQTT Forwarder. It is the only process that may own the concentrator.

## Step 1: Verify the RF inputs

Before enabling the radio, assemble the values that determine legal channels and transmit power:

```text
Country or jurisdiction:
Confirmed LoRaWAN region and sub-band:
RAK5146 frequency variant from the module label:
Antenna band and gain:
Cable loss:
Maximum permitted EIRP:
Applicable LBT, dwell-time, and duty-cycle requirements:
```

Keep the confirmed region and antenna values because the same choices are checked again in the MQTT topic prefix, ChirpStack region, and device profile.

**Stop here. Do not continue until this condition is resolved.** Do not enable RF transmission with an unverified region or antenna system.

## Step 2: Open the Concentratord page

In the Gateway OS web interface, open:

```text
ChirpStack > Concentratord
```

Configure:

```text
Enabled chipset: SX1302 / SX1303
Shield model: RAK5146
Channel-plan: <CONFIRMED_GATEWAY_OS_CHANNEL_PLAN>
```

Select the exact sub-band or channel block required by the approved region. Do not choose a generic AS923, AU915, or US915 entry without confirming the required variant or sub-band.

Click **Save & Apply**.

## Step 3: Confirm the Gateway ID

Wait for Concentratord to initialize and refresh the page. The footer must show a 16-hexadecimal Gateway ID instead of `could not read gateway_id`.

Keep the displayed value as `<GATEWAY_EUI>`. A Gateway EUI is a 64-bit identifier written as exactly 16 hexadecimal characters. It is used later for the MQTT certificate identity, topic ACLs, client IDs, and ChirpStack gateway registration.

Use the value reported by Concentratord on the commissioned RAK5146. Do not silently replace it with a network-interface-derived ID. If the value is missing or changes after reboot, inspect the SPI, reset, power, and concentrator logs before continuing.

## Step 4: Inspect the effective UCI configuration

Over SSH:

```bash
uci show chirpstack-concentratord
monit status
logread -e chirpstack-concentratord
```

Healthy evidence:

- the configured chipset and shield match RAK5146;
- the selected channel plan is the approved plan;
- the Gateway ID is stable;
- no repeated SPI, reset, SX1250, clock, calibration, or restart error appears;
- the service remains supervised and running.

## Step 5: Keep the UDP Forwarder disabled

In the web interface open:

```text
ChirpStack > UDP Forwarder
```

Remove all servers and disable the service for every slot.

Verify over SSH:

```bash
uci show chirpstack-udp-forwarder
monit status
```

There must be no configured remote UDP server. Do not use UDP as a fallback.

## Step 6: Confirm the MQTT topic prefix

Saving the Concentratord configuration normally sets the MQTT Forwarder region prefix. Read and retain the effective value before editing MQTT Forwarder because the server subscribes to this exact topic namespace:

```bash
uci show chirpstack-mqtt-forwarder | grep -i topic
```

The value must match the ChirpStack region topic prefix, for example a reviewed value such as `eu868`, `us915_0`, or `as923_2`. Do not copy an example blindly.

Continue with the server-side certificate procedure before configuring MQTT:

[Provision the gateway MQTT identity on the server](../../server/lab/setup/04-provision-gateway-mqtt-identity.md)
