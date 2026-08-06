# 1. Architecture Decisions and Scope

## 1.1 Gateway architecture

```text
Raspberry Pi 4B + RAK5146
  -> Gateway OS Base
  -> Concentratord
  -> MQTT Forwarder, QoS 1
  -> local Mosquitto on 127.0.0.1:1883
  -> finite persistent event/state queue
  -> mutual-TLS Mosquitto bridge
  -> mqtt.<DOMAIN>:8883
  -> remote MQTT broker
  -> ChirpStack
```

Do not deploy Gateway OS Full, Raspberry Pi OS, LoRa Basics Station, Semtech UDP, a second packet forwarder, or a local ChirpStack Network Server.

## 1.2 Why Gateway Bridge is excluded

Current ChirpStack Gateway Bridge releases removed the Concentratord backend. MQTT Forwarder is the supported process that reads Concentratord on Gateway OS.

Gateway Bridge is not a durable uplink queue. The selected open-source buffering layer is local Mosquitto with persistence and an outgoing QoS 1 bridge.

A server-side Gateway Bridge is also unnecessary because ChirpStack consumes the gateway MQTT topics directly.

## 1.3 Buffer guarantees and limits

The architecture provides bounded at-least-once delivery for gateway event and state topics. It does not promise unlimited retention or exactly-once delivery.

Required controls:

- finite `max_queued_messages` and `max_queued_bytes`;
- verified persistent storage path;
- storage free-space alert and reserve;
- queue-depth or database-size monitoring;
- measured drain rate;
- application deduplication;
- overflow procedure;
- clean-session QoS 0 downlink bridge to avoid stale command replay.

## 1.4 Cloud ingress

Expose only:

```text
mqtt.<DOMAIN>:8883/TCP
```

Use Layer-4 pass-through when a load balancer fronts the broker. Mutual TLS remains mandatory even with source-IP restrictions because 4G addresses may change.

## 1.5 Identity and topics

The gateway certificate Common Name equals its 16-hexadecimal Gateway ID.

```text
write <REGION>/gateway/<GATEWAY_EUI>/event/#
write <REGION>/gateway/<GATEWAY_EUI>/state/#
read  <REGION>/gateway/<GATEWAY_EUI>/command/#
```

The two bridge client IDs are `gw-up-<GATEWAY_EUI>` and `gw-down-<GATEWAY_EUI>`. Client IDs aid diagnostics; broker authorization uses the certificate identity and ACL.

## 1.6 RF source of truth

Country authorization, RAK5146 frequency variant, antenna system, Concentratord channel plan, MQTT region prefix, ChirpStack region, and device profile must agree.

**Stop here. Do not continue until this condition is resolved.** Do not transmit with an unknown region or antenna configuration.

## 1.7 Failure domains

Test separately:

- gateway power and SD-card failure;
- RAK5146 or antenna failure;
- local broker failure;
- local queue full or storage pressure;
- 4G and DNS failure;
- remote certificate or ACL rejection;
- remote broker/load-balancer failure;
- ChirpStack, PostgreSQL, Valkey, and integration failure.

A connected bridge does not prove RF health. A queued local message does not prove remote processing.

## 1.8 Upgrade policy

Pin Gateway OS and all packages. Before upgrade, drain the queue when possible, back up the Gateway OS configuration and broker data securely, preserve the old factory image, and test the exact upgrade on spare hardware.
