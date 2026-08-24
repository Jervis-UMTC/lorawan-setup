# 11. Gateway OS Delivery Buffer and Integrity Journal over a USB 4G/LTE Dongle

> **Status: STANDBY / DRAFT.** This gateway/backhaul phase is not part of the current completed cloud-server checkpoint. Re-check the actual Gateway OS build, modem mode, carrier/APN, MQTT endpoint, certificates, queue/journal behavior, and routing when this phase becomes active.

## 11.1 Goal

Keep two independent outbound paths over the same 4G backhaul:

```text
DELIVERY
MQTT Forwarder
  -> local Mosquitto persistent queue
  -> ssl://mqtt.<DOMAIN>:8883 over 4G

EVIDENCE
Concentratord
  -> integrity journal
  -> local hash-chained segments
  -> https://evidence.<DOMAIN>:443 over 4G
```

MQTT uses a unique gateway certificate. The evidence uploader uses its own per-gateway machine identity when the v2 path is deployed. MQTT Forwarder never connects directly to the cloud and the journal never owns the SPI radio.

## 11.2 Confirm the gateway and 4G inputs

Before changing the backhaul, confirm the Gateway EUI and legal RF plan are stable, the modem and SIM support the selected carrier/APN, and DNS resolves every enabled machine endpoint.

For delivery confirm:

```text
mqtt.<DOMAIN>
MQTT cloud CA
unique MQTT client identity for the Gateway EUI
queue path/finite limits/free-space reserve
```

For v2 evidence also confirm:

```text
evidence.<DOMAIN>
evidence server CA
unique evidence-upload identity mapped to the Gateway EUI
journal implementation/version/hash
journal storage budget and latest local chain/checkpoint state
```

Keep the tested Gateway OS image reference, RAK5146 variant, APN reference, endpoints, certificate fingerprints/expiry, and encrypted rollback backup because those values are needed to restore service without changing radio or evidence identity.

Do not copy SIM PINs, APN passwords, or private keys into the manual or test notes.

## 11.3 Install and configure Gateway OS

Follow:

- [Gateway OS installation](../../gateway/setup/02-install-chirpstack-gateway-os.md)
- [Concentratord](../../gateway/setup/03-configure-concentratord.md)
- [Persistent MQTT buffer](../../gateway/setup/04-configure-local-mqtt-buffer.md)
- [Software-only integrity journal](../../gateway/setup/04a-configure-gateway-integrity-journal.md)
- [MQTT Forwarder](../../gateway/setup/05-configure-mqtt-forwarder.md)

Keep UDP Forwarder disabled.

## 11.4 Connect the USB 4G/LTE dongle without losing management access

Keep Ethernet or the currently working management connection attached while commissioning LTE. Do not make LTE the only route until the modem has passed registration, DNS, MQTT, and reconnect tests.

**Why:** if the APN, modem driver, or route is wrong, keeping the known-good management path prevents a remote lockout while you troubleshoot the gateway.

Before plugging in the dongle, confirm the Raspberry Pi power supply is stable. LTE modems can draw short current bursts, especially during network registration or weak-signal transmit. If the modem repeatedly resets, disappears from USB, or the gateway becomes unstable, investigate power before changing network configuration. A powered USB hub is preferable to guessing at modem settings when power is the actual problem.

After inserting the dongle, inspect what Gateway OS/OpenWrt actually detected:

```sh
logread | tail -n 100
dmesg | tail -n 100
lsusb 2>/dev/null || true
ip link
ip addr
uci show network
ubus call network.interface dump
```

Look for the modem USB device and the network/control interfaces it created. Common modem presentations include:

```text
ECM/RNDIS/HiLink-style modem
  -> looks like a USB Ethernet interface
  -> normally receives an address with DHCP

QMI modem
  -> usually exposes a wwan interface plus a cdc-wdm control device
  -> requires the matching QMI support in the pinned OpenWrt build

MBIM modem
  -> usually exposes a wwan interface plus a cdc-wdm control device
  -> requires the matching MBIM support in the pinned OpenWrt build

Older PPP modem
  -> exposes serial ports
  -> use only when that exact modem and Gateway OS release are known to require PPP
```

Do not install every modem package blindly. Identify the dongle mode first, then use the package/LuCI procedure supported by the pinned Gateway OS release.

## 11.4A Configure the carrier/APN

Record the carrier and APN reference outside Git. Configure only the values required by the SIM plan:

```text
APN
PDP/IP family when required
SIM PIN only when enabled
username/password only when the carrier actually requires them
```

Do not assume public IPv4. Most mobile connections may sit behind carrier NAT/CGNAT, which is acceptable for this design because the gateway creates outbound TLS connections to the cloud.

**No inbound port forwarding to the gateway is required.** Do not expose LuCI, SSH, MQTT 1883, or any radio service through the mobile network.

## 11.4B Verify LTE addressing, routing, DNS, and time

Once the LTE interface reports connected, run:

```sh
ip addr
ip route
ubus call network.interface dump
ping -c 4 <APPROVED_TEST_HOST>
nslookup mqtt.<DOMAIN>
date -u
```

When gateway evidence is deployed, also verify:

```sh
nslookup evidence.<DOMAIN>
```

A healthy result shows:

```text
LTE/wwan interface has an address
default route exists through the intended LTE interface
route metric is intentional when Ethernet/Wi-Fi also exists
DNS resolves the cloud MQTT hostname
UTC time is correct enough for TLS validation
basic outbound reachability works
```

Interpret failures in this order:

```text
No modem/interface
  -> USB detection, driver/protocol support, or power problem

Interface exists but has no address
  -> SIM registration, APN, PIN, carrier, or modem-session problem

Address exists but no default route
  -> interface/network or route-metric configuration problem

IP connectivity works but DNS fails
  -> resolver/DHCP/DNS configuration problem

DNS works but MQTT TLS fails
  -> cloud firewall, port 8883, certificate, hostname, client identity, or ACL problem
```

**Why:** this keeps LTE troubleshooting separate from LoRaWAN and MQTT. Do not change the radio region or ChirpStack device configuration to fix a mobile-network routing problem.

## 11.4C Make LTE the intended cloud path

When Ethernet, Wi-Fi, and LTE coexist, choose route metrics deliberately. During commissioning, keep the management route stable and make sure the cloud-bound route behaves as intended.

Verify again:

```sh
ip route
nslookup mqtt.<DOMAIN>
```

Then watch the local Mosquitto bridge logs while sending a real uplink. The success condition is not just "the Internet works"; the gateway must establish the MQTT mTLS session over the intended mobile path and ChirpStack must update gateway last-seen.

## 11.5 Configure the cloud bridge

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

## 11.6 Network exposure

The gateway initiates outbound TLS. Do not forward internet ports to LuCI, SSH, local MQTT, journal storage, or radio services. Local 1883 must remain on loopback.

Cloud gateway-facing ingress is limited to:

```text
TCP 8883 -> MQTT mTLS
TCP 443  -> evidence HTTPS/mTLS, only when the reviewed evidence service exists
```

The evidence API does not expose the journal filesystem and MQTT 8883 does not carry journal segment uploads.

## 11.7 4G outage test

Measure:

- bridge disconnect detection and retry;
- local queue growth;
- SD-card free space;
- gateway stale/offline transition;
- queue persistence across gateway reboot;
- queue drain after 4G recovery;
- duplicate deliveries and unique application records;
- stale-downlink prevention;
- reconnect data usage;
- journal sequence and segment growth during the same outage;
- journal-storage percent and OS reserve;
- latest accepted cloud checkpoint age;
- unuploaded closed-segment count/bytes;
- evidence uploader recovery and data usage;
- server journal-to-remote-MQTT reconciliation after connectivity returns.

## 11.8 Final acceptance

- Local delivery queue and journal evidence budget are separately finite and persistent.
- Real uplinks survive the designed 4G outage and reboot.
- Queue drains and missing journal segments upload/reconcile after recovery.
- The checkpoint boundary does not falsely advance while the gateway is offline.
- Remote MQTT mTLS/ACLs and, when enabled, evidence-upload mTLS/identity mapping pass.
- Duplicate application records are prevented.
- Stale downlinks are not replayed.
- RF and UDP controls remain unchanged.

Next standby phase: [12-gateway-and-device-migration.md](12-gateway-and-device-migration.md).
