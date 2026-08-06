# 1. Architecture and Decisions

## 1.1 Data path

```text
RAK5146 SPI
  -> Gateway OS Base
  -> Concentratord
  -> MQTT Forwarder, QoS 1
  -> local Mosquitto on loopback
  -> persistent finite outgoing queue
  -> mTLS bridge
  -> remote Mosquitto
  -> ChirpStack
```

## 1.2 Gateway component decision

Gateway OS Base remains the supported image because ChirpStack and application services are external.

Use MQTT Forwarder for Concentratord. Do not install current ChirpStack Gateway Bridge on the gateway: its Concentratord backend was removed, so it does not replace MQTT Forwarder and does not satisfy the buffering requirement.

Use a local open-source Mosquitto broker for buffering. MQTT Forwarder sends QoS 1 messages to the loopback broker; a persistent Mosquitto bridge forwards them remotely.

## 1.3 Buffering semantics

```text
event/# -> outgoing bridge QoS 1, persistent session
state/# -> outgoing bridge QoS 1, persistent session
command/# -> incoming bridge QoS 0, clean session
```

This provides bounded at-least-once uplink delivery. Duplicate messages may occur after reconnect, so application storage must use ChirpStack `deduplicationId` or a stable event key and uniqueness constraints.

Downlinks are intentionally not store-and-forward. Commands tied to LoRaWAN receive windows must not be replayed after connectivity returns.

## 1.4 Storage boundary

The queue must use verified persistent storage and finite message and byte limits. `/tmp` is prohibited. `/var` must not be used unless the exact Gateway OS mount layout proves it is persistent.

Queue sizing must include peak uplink rate, serialized event size, outage duration, protocol overhead, safety factor, free-space reserve, and SD-card endurance.

## 1.5 Authentication boundary

The remote broker terminates TLS and maps the unique gateway certificate identity to exact gateway topics. The loopback broker is unauthenticated only because it listens solely on `127.0.0.1`.

A TLS connection alone is not proof. Verify certificate chain, hostname, expiry, key match, ACL isolation, topic prefix, Gateway ID, and real message flow.

## 1.6 Region source of truth

These values must agree:

```text
country authorization
RAK5146 frequency variant
antenna band, gain, and cable loss
Gateway OS Concentratord channel plan
MQTT region topic prefix
ChirpStack enabled region
end-device firmware and device profile
```

**Stop here. Do not continue until this condition is resolved.** Do not transmit with an unverified RF plan.

## 1.7 Failure tests

Measure independently:

- WAN disconnect and reconnect;
- remote broker restart;
- gateway reboot while messages are buffered;
- queue drain rate and duplicate count;
- queue limit and overflow behavior;
- storage free-space reserve;
- invalid or revoked gateway certificate;
- stale-downlink prevention;
- configuration restore to spare media.
