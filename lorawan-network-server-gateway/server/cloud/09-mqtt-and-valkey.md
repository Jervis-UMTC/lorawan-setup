# 9. Gateway MQTT Buffer, Remote Broker, and Valkey

## 9.1 Two broker roles

```text
Gateway local Mosquitto
  -> loopback ingress from MQTT Forwarder
  -> finite persistent event/state queue
  -> outgoing mTLS bridge

Remote MQTT broker
  -> gateway certificate validation and ACLs
  -> ChirpStack gateway backend
  -> application integrations
```

The local broker is per gateway and does not need clustering. The remote broker availability design must match the fleet and server requirements.

## 9.2 Local broker requirements

- listener only on `127.0.0.1:1883`;
- persistence enabled on verified non-tmpfs storage;
- finite message and byte queue limits;
- event/state bridge QoS 1 with persistent session;
- command bridge QoS 0 with clean session;
- unique remote client IDs;
- bridge mutual TLS using the unique gateway certificate;
- no plaintext LAN or WAN listener;
- monitored storage, reconnects, queue growth, drops, and drain rate.

## 9.3 Remote listener plan

```text
Public gateway endpoint: mqtt.<DOMAIN>:8883/TCP
Private application endpoint: <PRIVATE_MQTT_ENDPOINT>:8883/TCP or the same broker service
Plaintext 1883: disabled
Administration/API: management network only
```

Use Layer-4 TCP pass-through so the broker receives the client certificate.

## 9.4 Gateway ACL

```text
user <GATEWAY_EUI>
topic write <REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/#
topic write <REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/#
topic read <REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/#
```

Both `gw-up-<GATEWAY_EUI>` and `gw-down-<GATEWAY_EUI>` use this certificate identity. Test denial against another Gateway ID.

## 9.5 ChirpStack ACL

```text
user chirpstack
topic read <REGION_TOPIC_PREFIX>/gateway/+/event/#
topic read <REGION_TOPIC_PREFIX>/gateway/+/state/#
topic write <REGION_TOPIC_PREFIX>/gateway/+/command/#
topic write application/+/device/+/event/#
topic read application/+/device/+/command/#
```

Enumerate approved region prefixes instead of granting `#`.

## 9.6 Buffer delivery semantics

Uplink and state delivery is at-least-once. A connection loss after remote receipt but before acknowledgement can cause retransmission.

Node-RED and TimescaleDB must use the ChirpStack `deduplicationId` or stable event key and uniqueness indexes. One physical LoRaWAN uplink must produce one canonical application row even when MQTT is delivered more than once.

Downlink commands are live-only. The gateway downlink bridge uses QoS 0 and a clean session. Do not enable remote QoS 0 queueing for this path.

## 9.7 Queue sizing and outage behavior

Measure real serialized event size and peak uplink rate. Test:

- WAN outage longer than normal but within the design target;
- gateway reboot during outage;
- remote broker restart;
- queue drain after recovery;
- duplicate count;
- queue limit and drop behavior;
- storage free-space reserve;
- stale-downlink prevention.

If an outage exceeds the finite queue, older or newer messages may be dropped according to observed broker behavior. Alert before this point and define the response: restore the remote path, protect the filesystem reserve, identify the retained frame-counter range, and report confirmed loss without deleting queue evidence.

## 9.8 Remote broker availability

Mosquitto is suitable when its non-clustered limitations are accepted. Two independent Mosquitto nodes behind a load balancer do not share sessions or queues.

When shared durable sessions or cross-node state are required, select and test an open-source clustered broker whose exact community edition provides them.

A TCP health check is insufficient. Add an authenticated synthetic publish/subscribe test and verify a real gateway event.

## 9.9 TLS lifecycle

The remote server certificate SAN must include `mqtt.<DOMAIN>`. Maintain gateway-certificate inventory, expiry alerts, renewal, revocation, emergency replacement, and encrypted recovery. Never mount the CA private key into runtime services.

## 9.10 Valkey

Keep Valkey private, TLS-protected across hosts, authenticated, monitored, and sized with memory headroom. Broker buffering does not replace ChirpStack's Valkey or database recovery requirements.

## 9.11 Final checks

- Local queue survives WAN loss and reboot.
- Queue size is finite and monitored.
- Remote MQTT exposes only TLS 8883.
- Gateway certificates are unique and ACL-isolated.
- Duplicate replay is idempotent downstream.
- Stale commands are not replayed.
- Remote broker edition and failover semantics are tested.
- Valkey remains private and monitored.

Next: [10-chirpstack-cloud-cluster.md](10-chirpstack-cloud-cluster.md)
