# RAK5146 ChirpStack Gateway OS Troubleshooting

Use the lowest failing layer first. Gateway commands in this guide run over SSH on ChirpStack Gateway OS; the Docker log command in Section 4 runs on the application server. For persistent-buffer and bridge failures, use the more detailed [buffered gateway troubleshooting runbook](../operations/05-troubleshooting.md).

## 1. Boot and network

This layer is healthy when the gateway has the expected management address, a default route, working broker DNS, correct UTC time, and no boot or filesystem loop in the last logs. A missing address points to link or DHCP; no default route points to network configuration; failed DNS points to the resolver or backhaul; incorrect time causes TLS failures. Correct the first abnormal result and repeat the same commands before changing MQTT certificates.

```bash
ip addr
ip route
nslookup <MQTT_BROKER_FQDN>
date -u
logread | tail -200
```

## 2. Concentratord

```bash
monit status
uci show chirpstack-concentratord
logread -e chirpstack-concentratord
```

```text
no Gateway ID -> wrong profile or radio startup failure -> verify SX1302/SX1303 and RAK5146
SPI/reset error -> HAT, power, seating, or hardware issue -> power down and inspect
calibration loop -> RF variant, clock, profile, or hardware problem -> compare exact labels and logs
wrong region -> regulatory risk -> stop RF transmission and correct the plan
```

## 3. MQTT Forwarder

```bash
uci show chirpstack-mqtt-forwarder
logread -e chirpstack-mqtt-forwarder
```

```text
DNS failure -> fix resolver or route
timestamp/certificate error -> fix NTP before changing trust
unknown CA -> install approved broker CA
certificate rejected -> inspect issuer, expiry, EKU, CN, and key match
not authorized -> compare Gateway ID, region prefix, and exact ACL
```

## 4. Broker and ChirpStack

```bash
docker compose logs --since=10m --tail=400 mosquitto chirpstack
```

A healthy server log shows the broker receiving the regional gateway event topic and ChirpStack updating the registered Gateway EUI's last-seen time. MQTT connection without gateway last-seen means Protobuf, backend `concentratord`, region prefix, broker ACL, or the active ChirpStack region differs. Correct the first mismatch, restart only the affected server service, and verify with a fresh uplink.

## 5. RF and devices

Gateway current but no uplink -> check antenna, RAK5146 variant, channel plan, device region, profile, join keys, and frame counters.

Downlink queued but not transmitted -> check broker command ACL, MQTT Forwarder, Concentratord scheduling, class, receive windows, time, FPort, and legal duty-cycle limits.

## 6. UDP fallback

```bash
uci show chirpstack-udp-forwarder
```

Any configured UDP server is unsupported. Remove it and retest MQTT.

## 7. Recovery

Preserve logs and current configuration. Restore the approved Gateway OS image and configuration on a spare card before overwriting production media.

Pass only when Gateway ID, region, MQTT identity, ACL isolation, real uplink/downlink, reboot, and restore tests succeed.
