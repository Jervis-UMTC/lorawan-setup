# 16. Cloud Troubleshooting

Start at the lowest layer that does not show a healthy result. Do not restart every node or rotate credentials until the failing boundary is identified.

```text
RAK5146
  -> Concentratord
  -> MQTT Forwarder
  -> gateway-local Mosquitto listener and persistence
  -> DNS / 4G / mutual-TLS bridge
  -> remote MQTT endpoint or Layer-4 load balancer
  -> ChirpStack MQTT region backend
  -> PostgreSQL and Valkey
  -> application integrations
```

Gateway commands in Sections 16.1–16.3 run over SSH on the Raspberry Pi. Cloud commands run on the host that owns the named service. Use one reserved gateway and device event to compare timestamps across layers.

## 16.1 Radio or Gateway ID failure

**Failing layer:** RAK5146 hardware access or Concentratord configuration.

Run on the gateway:

```sh
monit status
uci show chirpstack-concentratord
logread -e chirpstack-concentratord
```

Healthy output shows one running Concentratord instance, the RAK5146/SX1302-or-SX1303 profile, the confirmed legal channel plan, and a stable 16-hexadecimal Gateway ID. SPI, reset, calibration, repeated restart, missing-ID, or changing-ID messages point to profile, HAT seating, power, frequency variant, or hardware trouble.

Correct only the first observed mismatch. Power down before reseating hardware, and stop RF transmission when the region is wrong. Verify by rebooting and confirming the same Gateway ID and channel plan without error loops.

## 16.2 MQTT Forwarder cannot publish locally

**Failing layer:** MQTT Forwarder to the gateway-local Mosquitto listener.

Run on the gateway:

```sh
uci show chirpstack-mqtt-forwarder
logread -e chirpstack-mqtt-forwarder
logread -e mosquitto
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Healthy configuration uses `tcp://127.0.0.1:1883`, QoS 1, Protobuf, backend `concentratord`, and a listener bound only to loopback. Connection refusal means Mosquitto is stopped or invalid; a WAN address means the buffer is bypassed; a non-loopback listener means the broker is exposed.

Validate the broker configuration, correct the differing address, QoS, backend, or listener, and restart only the affected process. Verify with one real gateway event at the local broker.

## 16.3 The local queue grows and does not drain

**Failing layer:** gateway backhaul, DNS, time, TLS, broker ACL, remote MQTT availability, or queue capacity.

Run on the gateway:

```sh
logread -e mosquitto
nslookup mqtt.<DOMAIN>
ip route
date -u
df -h /etc/mosquitto/data
ls -l /etc/mosquitto/data/mosquitto.db
```

| Symptom | Meaning | Smallest safe action |
|---|---|---|
| DNS failure | Resolver, APN, or 4G route problem | Restore DNS or route and keep the queue running |
| Hostname or CA error | Wrong trust file or certificate SAN | Install the intended CA or endpoint; never disable verification |
| Client rejected | Certificate, expiry, EKU, CN, or key mismatch | Compare the certificate identity and private-key match |
| ACL denial | Gateway identity or regional topic mismatch | Compare Gateway EUI, certificate CN, and exact topics |
| Queue grows with a connected bridge | Remote drain rate is below incoming rate | Check broker health and measured publish rate |
| Queue reaches its finite limit | Outage exceeded the buffer design | Restore the remote path, protect free space, and identify the affected interval |
| Database missing after reboot | Volatile path or persistence failure | Stop claiming durable buffering and repair the storage path |

Healthy recovery reconnects both bridge clients, preserves the queue database, drains old events, and continues accepting new uplinks. Verify at the remote broker and then at ChirpStack; do not delete the queue to make disk usage fall.

## 16.4 The remote broker receives events but ChirpStack does not

**Failing layer:** remote MQTT authorization or the ChirpStack regional MQTT backend.

On the MQTT host, confirm the gateway event topic and certificate identity. On each ChirpStack application node, inspect the service logs and active region configuration. The regional topic prefix, Protobuf backend, broker endpoint, client certificate, and trust root must agree.

Healthy behavior updates the registered Gateway EUI's last-seen time after a fresh event. If the broker has the message and ChirpStack does not, correct only the differing regional backend, topic prefix, ACL, or credential and restart the affected ChirpStack node. This architecture does not require ChirpStack Gateway Bridge.

## 16.5 Duplicate application or telemetry rows

**Failing layer:** application idempotency after valid at-least-once MQTT delivery.

Verify the Node-RED stable event key, ChirpStack `deduplicationId` use, and the TimescaleDB uniqueness indexes. Replay one sanitized event. A healthy result leaves one uplink and one row per metric. More rows mean the event key or database constraint is wrong. Fix that layer; do not lower gateway QoS.

## 16.6 A stale downlink appears after reconnect

**Failing layer:** downlink session cleanup or an automation publisher.

Confirm the gateway's `cloud-downlink` bridge uses `cleansession true` and command topic `in 0`. Check the remote broker for retained command messages and duplicate client sessions. Healthy behavior does not replay a Class A command after its receive window.

Disable automatic downlinks until the retaining session or publisher is removed, then verify with one harmless, observable command.

## 16.7 MQTT load-balancer failover does not preserve service

**Failing layer:** Layer-4 routing, backend health, timeout behavior, or broker session design.

Confirm the load balancer uses TCP pass-through, the TLS certificate is presented by the broker path, health checks remove the failed backend, and idle timeouts are longer than the expected MQTT keepalive behavior. A healthy test reconnects the gateway and resumes queue drain without changing its certificate or topics.

A load balancer does not synchronize independent Mosquitto sessions, retained messages, or queues. If failover lands on a broker without the required session state, fix the broker architecture or failover design rather than adding retries at the gateway.

## 16.8 UDP Forwarder traffic appears

**Failing layer:** an unsupported gateway backend is enabled.

Run on the gateway:

```sh
uci show chirpstack-udp-forwarder
monit status
```

Healthy output has no UDP server and the service disabled. Remove the unintended entries, disable only the UDP Forwarder, and verify the MQTT path with a real uplink.

## 16.9 ChirpStack reports database or state errors

**Failing layer:** ChirpStack, PgBouncer/HAProxy, PostgreSQL/Patroni, or Valkey.

Check the application-node logs first, then the connection pool and active PostgreSQL primary, replication state, storage, connection limits, and Valkey endpoint. Healthy results show one writable primary, reachable pool endpoints, bounded connection use, healthy replicas, and the shared Valkey endpoint available to both application nodes.

An authentication error calls for checking the exact service role and secret reference. Connection exhaustion calls for checking pool and database limits. Read-only or no-primary errors call for Patroni and HAProxy diagnosis. Restarting all application and database nodes together destroys the evidence and can worsen failover; correct the first failing dependency and verify one API request plus one fresh uplink.

## 16.10 An upgrade causes a regression

Preserve the Gateway OS image, local broker data and configuration, certificates, cloud image digests, database versions, active schema state, and logs from the failed attempt.

Restore the previously tested component without deleting data volumes. Verify the rollback in layers: gateway radio, local publish, WAN queue, mutual TLS, remote broker, ChirpStack gateway activity, OTAA/uplink, database state, and integrations. A process that merely starts is not a successful rollback.
