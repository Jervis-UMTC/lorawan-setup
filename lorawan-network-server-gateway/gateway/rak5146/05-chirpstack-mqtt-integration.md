# Connect the Buffered RAK5146 Gateway to ChirpStack

## Data path

```text
Gateway OS MQTT Forwarder
  -> local persistent Mosquitto
  -> mutual-TLS Mosquitto bridge
  -> remote MQTT broker
  -> ChirpStack region gateway MQTT backend
```

Do not deploy a server-side ChirpStack Gateway Bridge. Do not install current Gateway Bridge on the gateway for Concentratord.

## Gateway ACL

```text
user <GATEWAY_EUI>
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/#
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/#
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/#
```

`<GATEWAY_EUI>` is the stable 16-hexadecimal value reported by Concentratord. `<CONFIRMED_REGION_TOPIC_PREFIX>` comes from the active Gateway OS and ChirpStack region configuration. The certificate Common Name equals the Gateway EUI. The bridge client IDs `gw-up-<GATEWAY_EUI>` and `gw-down-<GATEWAY_EUI>` aid diagnostics but do not replace certificate-based authorization.

## ChirpStack ACL

Use a separate `chirpstack` certificate:

```text
user chirpstack
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/event/#
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/state/#
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/command/#
```

## Acceptance

First confirm the remote broker accepts this certificate and denies an attempt to use another gateway's topic. Then verify a real uplink, a safe live Class A downlink, WAN-outage buffering, reboot persistence, queue drain, duplicate idempotency, and stale-downlink prevention.

A connected MQTT client without a fresh ChirpStack gateway update usually means the region prefix, Protobuf format, ChirpStack backend, or topic ACL is still wrong.
