# Operations 1. Register and Test the Buffered Gateway

Register the gateway only after the radio, local buffer, and remote MQTT path have passed their setup checks. Use the Gateway EUI reported by Concentratord; do not derive a different identifier from a network interface.

## Step 1: Confirm the values ChirpStack will depend on

```sh
cat /etc/os-release
monit status
uci show chirpstack-concentratord
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
opkg list-installed | grep '^mosquitto'
sha256sum /etc/mosquitto/mosquitto.conf
```

Use the output to confirm:

```text
Gateway EUI from Concentratord
RAK5146 variant and confirmed channel plan
MQTT region topic prefix
MQTT Forwarder loopback server, QoS, and client ID
local Mosquitto queue path, finite limits, and free-space reserve
remote broker FQDN
bridge certificate fingerprint and expiry
Gateway OS and Mosquitto versions tied to the tested rollback state
```

The Gateway EUI, region prefix, and certificate identity must be identical across the gateway and server. Stop if any of them conflict; registering a duplicate or reformatted EUI will not fix the underlying mismatch.

## Step 2: Confirm gateway MQTT layers

On Gateway OS:

```sh
logread -e chirpstack-mqtt-forwarder
logread -e mosquitto
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Pass when MQTT Forwarder publishes to `tcp://127.0.0.1:1883` at QoS 1, local Mosquitto listens only on loopback, and both remote bridges authenticate.

## Step 3: Confirm server health

```sh
cd /opt/chirpstack-docker
docker compose ps mosquitto chirpstack
docker compose logs --since=10m --tail=300 mosquitto chirpstack
sudo ss -lntp | grep ':8883'
```

Pass when the remote broker accepts both bridge client IDs under certificate identity `<GATEWAY_EUI>`, ChirpStack is connected to the region MQTT backend, and no Gateway Bridge container is required.

## Step 4: Register the gateway

Gateway registration tells ChirpStack which 16-hexadecimal Gateway EUI is allowed to represent this physical concentrator. In the ChirpStack web interface, open:

```text
Tenant > Gateways > Add gateway
```

Enter the exact `<GATEWAY_EUI>` shown by Concentratord, a descriptive name that identifies the physical gateway, and site coordinates only when they are known and suitable for the deployment. `<GATEWAY_EUI>` comes from Gateway OS Step 3; do not create a reformatted or network-interface-derived duplicate.

A healthy result shows the new gateway and updates its last-seen or statistics after MQTT traffic arrives. If it remains inactive, compare the EUI, region topic prefix, broker ACL, and ChirpStack MQTT backend before adding another gateway record.

## Step 5: Register an OTAA device and test a real uplink

A **Device EUI** is the end device's 16-hexadecimal identifier. An **OTAA** device uses its root keys during a join to create new session keys. A **device profile** defines the device's region, LoRaWAN MAC version, class, and capabilities. A **payload codec** converts the decrypted application bytes into named fields.

Create or select a device profile that matches the exact device model, firmware, LoRaWAN region, MAC version, and class. Add the device with the Device EUI from its label or secure provisioning record, then enter root keys only through the protected ChirpStack interface. Select a codec supplied or verified for that exact payload format; do not copy a decoder from a similar model without checking fields and units.

Observe Concentratord, MQTT Forwarder, local Mosquitto, remote Mosquitto, and ChirpStack logs while the device joins and sends a normal application uplink.

Pass when:

- join request and join accept complete;
- frame counter advances;
- local broker accepts the event;
- remote broker receives it under the expected Gateway ID;
- ChirpStack `rxInfo` includes the gateway;
- the payload codec produces plausible fields and units for the test condition;
- application integration receives one canonical event.

A join rejection usually points to Device EUI, JoinEUI, root-key, region, or device-profile mismatch. A successful join with undecoded or implausible fields points to the payload codec or firmware format rather than the radio path.

## Step 6: Test a safe Class A downlink

Queue one non-hazardous command using the exact device manual.

Pass when the remote broker publishes the command, the clean-session downlink bridge receives it live, MQTT Forwarder forwards it, Concentratord schedules it, and the device shows the expected result.

A queued command is not proof of delivery.

## Step 7: Test a short buffer outage

Disconnect WAN briefly, generate known real uplinks, restore WAN, and verify the local queue drains. Compare frame counters, `deduplicationId`, and database row counts. Duplicate MQTT delivery must not duplicate application records.

## Final acceptance

- Gateway ID and RF plan are stable.
- Local listener is loopback-only.
- Uplink/state QoS 1 buffering works.
- Remote mutual TLS and cross-gateway ACL denial pass.
- Stale downlinks are not replayed.
- UDP Forwarder remains disabled.
- OTAA, real uplink, and safe downlink pass.
