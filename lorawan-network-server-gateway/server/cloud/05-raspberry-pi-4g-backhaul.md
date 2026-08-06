# 5. Gateway OS Uplink Buffer over 4G

## 5.1 Goal

```text
MQTT Forwarder
  -> local Mosquitto persistent queue
  -> ssl://mqtt.<DOMAIN>:8883 over 4G
```

The remote connection uses a unique gateway certificate. MQTT Forwarder does not connect directly to the cloud.

## 5.2 Confirm the gateway and 4G inputs

Before changing the backhaul, confirm the Gateway EUI and legal RF plan are stable, the modem and SIM support the selected carrier/APN, DNS resolves `mqtt.<DOMAIN>`, and the gateway has the cloud CA and unique client certificate for that EUI. Keep the tested Gateway OS image reference, RAK5146 variant, queue path and finite limits, free-space reserve, APN configuration reference, broker endpoint, certificate fingerprint/expiry, and encrypted rollback backup because those values are needed to restore service without changing the radio identity.

Do not copy SIM PINs, APN passwords, or private keys into the manual or test notes.

## 5.3 Install and configure Gateway OS

Follow:

- [Gateway OS installation](../../gateway/setup/02-install-chirpstack-gateway-os.md)
- [Concentratord](../../gateway/setup/03-configure-concentratord.md)
- [Persistent MQTT buffer](../../gateway/setup/04-configure-local-mqtt-buffer.md)
- [MQTT Forwarder](../../gateway/setup/05-configure-mqtt-forwarder.md)

Keep UDP Forwarder disabled.

## 5.4 Configure and verify 4G

Use the modem and carrier procedure supported by the pinned Gateway OS/OpenWrt release. The command names and LuCI fields can differ by release, so verify the installed modem packages and interface name before applying a copied example.

```sh
ip addr
ip route
ping -c 4 <APPROVED_TEST_HOST>
nslookup mqtt.<DOMAIN>
date -u
```

A healthy result shows an address on the intended 4G interface, a default route with the expected metric, working DNS, synchronized time, and reachability to the approved test host. No address points to SIM/APN/modem registration; an address without a route points to interface or metric configuration; DNS failure should be corrected before testing MQTT. Protect APN credentials and SIM PINs. Set route metrics deliberately when Ethernet and 4G coexist.

## 5.5 Configure the cloud bridge

MQTT Forwarder remains:

```text
Server: tcp://127.0.0.1:1883
QoS: 1
Backend: concentratord
```

Local Mosquitto bridge configuration uses:

```text
address mqtt.<DOMAIN>:8883
bridge CA: cloud broker CA
bridge certificate: unique gateway certificate
bridge key: matching private key
event/state: out QoS 1
command: in QoS 0, clean session
```

## 5.6 Network exposure

The gateway initiates outbound TLS. Do not forward internet ports to LuCI, SSH, local MQTT, or radio services. Local 1883 must remain on loopback. Cloud ingress exposes only TCP 8883.

## 5.7 4G outage test

Measure:

- bridge disconnect detection and retry;
- local queue growth;
- SD-card free space;
- gateway stale/offline transition;
- queue persistence across gateway reboot;
- queue drain after 4G recovery;
- duplicate deliveries and unique application records;
- stale-downlink prevention;
- reconnect data usage.

## 5.8 Final acceptance

- Local queue is finite and persistent.
- Real uplinks survive the designed 4G outage and reboot.
- Queue drains after recovery.
- Remote mTLS and ACLs pass.
- Duplicate application records are prevented.
- Stale downlinks are not replayed.
- RF and UDP controls remain unchanged.
