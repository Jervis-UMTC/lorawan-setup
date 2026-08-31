# mqtt-collector-runtime-v1

This contract defines how one `gateway-mqtt-evidence-collector` replica witnesses the two commissioned Mosquitto backends.

## Session topology

Each collector process owns exactly two independent MQTT v5 clients:

```text
broker-1 -> tls://10.104.0.2:8884
broker-2 -> tls://10.104.0.4:8884
TLS server identity -> mqtt.internal.lorawan.com
subscription -> as923/gateway/+/event/#
subscription QoS -> 1
clean start -> false
session expiry -> non-zero and operator-configurable
```

The two clients MUST have different client IDs. Collector replica 1 and replica 2 therefore use four client IDs in total. This contract version rejects alternate broker URLs and alternate TLS names: the point of the witness is to observe both commissioned physical backends directly. Do not configure both broker URLs in one AutoPaho client: the brokers do not share MQTT session state.

Each broker session has its own protected authentication configuration. The runtime supports username/password and/or a client certificate so the final broker ACL design can use independently revocable collector identities without reusing ChirpStack, Node-RED, or gateway credentials.

The client never publishes. Broker ACLs remain the authoritative enforcement boundary:

```text
ALLOW READ  as923/gateway/+/event/#
DENY WRITE
DENY command/application-command/admin topics
```

## Durable capture rule

The exact MQTT topic and exact serialized PUBLISH payload bytes are authoritative input. Do not parse and re-serialize the broker event to create the witness identity.

For every observation:

1. require topic shape `as923/gateway/<16-lowercase-hex-EUI>/event/<non-empty-suffix>`;
2. compute frozen `mqtt-capture-v1` `capture_key_sha256` from exact topic + payload bytes;
3. compute `serialized_event_sha256 = SHA256(payload bytes)`;
4. use stable raw object reference `mqtt/<capture_key_sha256>.event`;
5. create the raw object first using create-if-absent semantics;
6. require the raw-object SHA-256 to equal `serialized_event_sha256`;
7. insert the PostgreSQL witness row;
8. when the received PUBLISH has QoS > 0, acknowledge it only after object + metadata persistence succeeds; QoS 0 has no protocol ACK and therefore cannot gain offline-delivery guarantees from a QoS 1 subscription.

A database failure after object creation does not delete the raw object. Retry must converge on the same object identity.

## Duplicate and conflict semantics

The same topic + payload observed by multiple broker/collector sessions intentionally produces the same `capture_key_sha256`.

`broker_received_at` is the receiving collector's UTC receipt timestamp. Different replicas can therefore observe different receipt times for the same capture identity. The first committed row is retained; duplicate receipt time and `collector_version` differences are not conflicts.

For an existing capture key, the exact raw identity fields plus any populated uplink projection must still match. A mismatch under the same capture key is a security conflict and must not be rewritten.

For `event/up` only, `concentratord-uplink-correlation-v1` now freezes the exact MQTT Forwarder payload as `gw.UplinkFrame`. The collector therefore keeps the raw-object-first rule above, then decodes only the pinned fields and stores `phy_payload_sha256`, decimal `uplink_id`, frequency, RSSI, SNR, and `correlation_digest_sha256`. The MQTT topic Gateway EUI must equal the Protobuf `rx_info.gateway_id`; a mismatch fails closed after the raw object is retained. Non-uplink event suffixes remain opaque witnesses with the semantic projection NULL.

This enrichment does not make re-serialized Protobuf authoritative. `capture_key_sha256` and `serialized_event_sha256` continue to bind the exact broker bytes first; the semantic digest exists only for cross-path correlation with the independent gateway journal.

## Library pin

The first source implementation pins:

```text
github.com/eclipse/paho.golang v0.23.0
```

It uses MQTT v5 persistent sessions, QoS 1 subscription, automatic reconnect, and manual acknowledgment so durable evidence persistence precedes PUBACK.
