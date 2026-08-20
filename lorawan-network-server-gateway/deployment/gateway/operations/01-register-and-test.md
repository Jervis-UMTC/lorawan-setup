# Operations 1. Register and Test the Buffered, Journaled Gateway

Register the gateway only after the radio, local buffer, remote MQTT path, and reviewed integrity journal have passed their setup checks. Use the Gateway EUI reported by Concentratord; do not derive a different identifier from a network interface.

## Step 1: Confirm the values ChirpStack will depend on

```sh
cat /etc/os-release
monit status
uci show chirpstack-concentratord
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
opkg list-installed | grep '^mosquitto'
sha256sum /etc/mosquitto/mosquitto.conf /etc/mosquitto/conf.d/bridge.conf
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
journal implementation/version/hash, storage budget, and latest local sequence/segment
latest accepted server checkpoint when evidence upload is enabled
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

Enter the exact `<GATEWAY_EUI>` reported by the successful active Concentratord startup; do not use an inactive SX1301 value or a network-interface-derived identifier. In ChirpStack 4.9 the Add Gateway form used by this project expects the exposed fields such as:

```text
Name: Gateway-01
Gateway ID: <GATEWAY_EUI>
Byte order: MSB
Stats interval: 30
```

Do not require a `Region: as923` field when the 4.9 UI does not expose one. The active region is controlled by the server's `enabled_regions` and `[[regions]]` configuration.

Interpret status correctly:

```text
not in gateway list       -> not registered
present, Last seen: Never -> registered, but no gateway event has been processed successfully yet
```

ChirpStack does not auto-create a gateway from MQTT traffic. If Last seen remains Never, troubleshoot the existing record and data path; do not add a second gateway record.

## Step 5: Register an OTAA device and test a real uplink

A **Device EUI** is the end device's 16-hexadecimal identifier. An **OTAA** device uses its root keys during a join to create new session keys. A **device profile** defines the device's region, LoRaWAN MAC version, class, and capabilities. A **payload codec** converts the decrypted application bytes into named fields.

Create or select a device profile that matches the exact device model, firmware, LoRaWAN region, MAC version, and class. Add the device with the Device EUI from its label or secure provisioning record, then enter root keys only through the protected ChirpStack interface. Select a codec supplied or verified for that exact payload format; do not copy a decoder from a similar model without checking fields and units.

Observe Concentratord, MQTT Forwarder, local Mosquitto, the journal's approved diagnostics, remote Mosquitto, the server gateway-MQTT evidence collector when enabled, and ChirpStack while the device joins and sends a normal application uplink.

Pass when:

- join request and join accept complete;
- frame counter advances;
- local broker accepts the event;
- remote broker receives it under the expected Gateway ID;
- ChirpStack `rxInfo` includes the gateway;
- the payload codec produces plausible fields and units for the test condition;
- application integration receives one canonical event;
- the journal records the real uplink with the next sequence and valid hash link;
- when the server integrity path is enabled, the remote gateway MQTT copy matches the journal record and the accepted application event reaches the expected verification state.

A join rejection usually points to Device EUI, JoinEUI, root-key, region, or device-profile mismatch. A successful join with undecoded or implausible fields points to the payload codec or firmware format rather than the radio path.

## Step 6: Test a safe Class A downlink

Queue one non-hazardous command using the exact device manual.

Pass when the remote broker publishes the command, the clean-session downlink bridge receives it live, MQTT Forwarder forwards it, Concentratord schedules it, and the device shows the expected result.

A queued command is not proof of delivery.

## Step 7: Test a short buffer + journal outage

Disconnect WAN briefly, generate known real uplinks, restore WAN, and verify both recovery paths:

```text
Mosquitto queue -> drains operational gateway events
Journal uploader -> uploads missing closed evidence segments/checkpoints
```

Compare frame counters, `deduplicationId`, journal sequences/hashes, latest pre-outage server checkpoint, remote gateway-event captures, verification state, and database row counts. Duplicate MQTT delivery must not duplicate application records. The server checkpoint must not falsely advance while the gateway is disconnected, and uploaded journal history must extend the last accepted anchor after recovery.

## Final acceptance

- Gateway ID and RF plan are stable.
- Local listener is loopback-only.
- Uplink/state QoS 1 buffering works.
- Remote mutual TLS and cross-gateway ACL denial pass.
- Stale downlinks are not replayed.
- UDP Forwarder remains disabled.
- OTAA, real uplink, and safe downlink pass.
- Journal sequence/hash continuity and the short outage/recovery test pass.
- When gateway-integrity v2 is enabled, at least one real application event is uniquely reconciled from journal -> remote MQTT -> ChirpStack -> trusted decoder before being described as `verified`.
