# Configure the RAK5146 Gateway MQTT Buffer

Use the complete procedures:

- [Persistent local MQTT buffer](../setup/04-configure-local-mqtt-buffer.md)
- [MQTT Forwarder to loopback](../setup/05-configure-mqtt-forwarder.md)
- [Remote broker PKI](../../server/lab/setup/03-secure-gateway-mqtt.md)
- [Gateway identity](../../server/lab/setup/04-provision-gateway-mqtt-identity.md)

## Required path

```text
RAK5146
  -> Concentratord
  -> MQTT Forwarder
  -> tcp://127.0.0.1:1883, QoS 1
  -> local persistent Mosquitto
  -> ssl://<MQTT_BROKER_FQDN>:8883
```

The gateway certificate is installed in local Mosquitto, not MQTT Forwarder. Port `1883` is used only for the loopback hop, while port `8883` is the remote TLS endpoint. MQTT Forwarder must not bypass the queue.

## Required topics

```text
event/# -> outgoing bridge QoS 1
state/# -> outgoing bridge QoS 1
command/# -> incoming bridge QoS 0 with clean session
```

`event` topics carry received gateway events, `state` topics carry gateway status, and `command` topics carry time-sensitive downlink requests. Cross-gateway topics must be denied by the remote broker. UDP Forwarder remains disabled.

A healthy result shows local QoS 1 publication, remote mutual-TLS authentication, and access only to the Gateway EUI embedded in the topics. If the remote path fails, uplink/state messages should accumulate locally rather than disappear or cause MQTT Forwarder to connect directly to the WAN.
