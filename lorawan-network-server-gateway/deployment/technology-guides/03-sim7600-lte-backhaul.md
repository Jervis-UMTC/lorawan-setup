# SIM7600 LTE Backhaul — Operator Manual

## What this technology does

The Waveshare SIM7600G-H modem is Gateway-01's commissioned **production-primary Internet path**. The gateway uses the QMI data path with control device `/dev/cdc-wdm0` and network interface `wwan0`.

The design intentionally keeps management Ethernet separate from production traffic so field tests measure the real cellular path.

## Current routing contract

- LTE interface: `wwan0`.
- QMI control device: `/dev/cdc-wdm0`.
- LTE is health-gated production primary.
- Wi-Fi must **not** be assumed to be automatic Internet fallback; the current tracked field overlay says no automatic Wi-Fi fallback unless it is configured separately. Management Ethernet must not become a production Internet route.
- Ethernet is management-only.
- `/usr/sbin/lte-route-health` owns the production default-route policy.
- Normal LTE default route metric: `10`.
- Production MQTT traffic must resolve through LTE in normal commissioned state.

Do not manually force a permanent route through management Ethernet to make a cloud test pass.

## Step 1 — Confirm the modem exists

Run on Gateway-01:

```sh
lsusb 2>/dev/null || true
ls -l /dev/cdc-wdm* /dev/ttyUSB* 2>/dev/null || true
ip link show wwan0 2>/dev/null || true
dmesg | grep -Ei 'simcom|sim7600|qmi|cdc-wdm|wwan|usb' | tail -n 80
```

**PASS means:** the SIMCom/Waveshare USB device is present, `/dev/cdc-wdm0` exists, and `wwan0` exists.

**If the modem repeatedly disconnects/re-enumerates:** check power and USB stability before changing APN or routes.

## Step 2 — Check the logical LTE interface

```sh
ubus call network.interface.lte status
```

**PASS means:** the interface reports up with a current address/gateway appropriate to the carrier session.

Do not reuse an old observed carrier IP as a static configuration value. Cellular PDP addresses can change after reconnect/reboot.

## Step 3 — Check the route controller

```sh
ubus call service list '{"name":"lte-route-health"}'
logread | grep 'lte-route-health' | tail -n 40
```

**PASS means:** the controller is running and not stuck in a rapid restart/reset loop.

The commissioned controller has a boot grace and staged recovery. Immediately after boot, allow it to converge rather than injecting manual routes.

## Step 4 — Verify route selection

```sh
ip route show default
nslookup smartagri-mqtt.duckdns.org
ip route get 129.212.208.168
```

**PASS means:** during normal commissioned LTE operation the production destination resolves over `wwan0`, and the preferred production default is the health-managed LTE route (normally metric `10`).

If public endpoint addressing changes intentionally, verify the currently configured production MQTT hostname/IP from the gateway bridge configuration instead of assuming the historical address above.

## Step 5 — Verify name resolution and UTC

```sh
nslookup smartagri-mqtt.duckdns.org
date -u
```

A bad clock can make valid TLS certificates look expired/not-yet-valid. Fix the network/time path before replacing certificates.

## Step 6 — Verify production TCP/TLS reachability

Do not print the private key. Inspect the bridge metadata first:

```sh
grep -E '^(connection |address |bridge_cafile|bridge_certfile|bridge_keyfile|bridge_insecure|topic )' /etc/mosquitto/conf.d/bridge.conf
```

Then verify the actual bridge is established using service logs/socket state rather than creating a second competing MQTT session:

```sh
logread | grep -Ei 'mosquitto|bridge|connected|connack|tls|certificate' | tail -n 80
ss -tnp 2>/dev/null | grep ':8883' || netstat -tnp 2>/dev/null | grep ':8883' || true
```

**PASS means:** the gateway's configured cloud bridge has an established TLS/MQTT path and the route to that destination is via the intended production interface.

## Step 7 — Prove real traffic, not only connectivity

Generate one approved sensor uplink and verify in order:

1. local gateway MQTT event appears;
2. cloud broker sees the gateway event;
3. ChirpStack accepts the uplink;
4. application telemetry appears.

If local event passes but cloud delivery fails, the fault is in LTE/routing/DNS/TLS/MQTT—not RF.

## Step 8 — What to do during intermittent mobile service

Normal behavior is:

```text
RF continues
-> local MQTT accepts/buffers QoS-1 uplinks
-> LTE controller keeps/re-establishes a usable data path
-> cloud bridge reconnects
-> queued uplinks drain
```

Do not purge `mosquitto.db`, reset the gateway lineage, or route production traffic over management Ethernet simply because the carrier is temporarily weak.

For research resilience tests, use the dedicated test procedure. Do not improvise an outage by repeatedly unplugging the modem during ordinary troubleshooting.

## Change procedure for APN/modem/network settings

1. keep management Ethernet connected;
2. back up Gateway OS configuration;
3. record current `ubus call network.interface.lte status`, `ip route`, and controller log state;
4. change only the required carrier/APN/network item;
5. verify modem registration and QMI addressing;
6. allow `lte-route-health` to converge;
7. verify DNS and UTC;
8. verify route to production MQTT;
9. verify TLS/MQTT bridge;
10. verify one real uplink end to end.

Do not send USB-mode-changing AT commands to the commissioned SIM7600 unless a separately reviewed hardware replacement/recovery procedure requires it.

## Troubleshooting order

| Symptom | Inspect first |
|---|---|
| No USB device | power, cable/port, modem hardware |
| USB present, no `/dev/cdc-wdm0`/`wwan0` | Gateway OS modem driver/image |
| `wwan0` exists, no data session | SIM, carrier registration, APN/PDP |
| Data session works, route wrong | `lte-route-health`, route metrics/policy |
| Route works, DNS/time broken | resolver/NTP/general Internet |
| TCP works, TLS fails | UTC, CA/SAN/client cert, server identity |
| TLS/MQTT works, app missing | ChirpStack/application path |

## Recovery

If the dataplane remains unavailable, use the commissioned staged recovery path rather than manually flapping everything at once. The controller can perform a bounded logical-interface restart and, only after cooldown when required, a SIM7600 functional reset. If the modem is physically unstable, solve power/USB first.

Rebuilding the Gateway OS is a last resort for a driver/image regression and must preserve the known-good rollback image/config/identity boundary.

## Completion checklist

- SIM7600 detected.
- `/dev/cdc-wdm0` and `wwan0` present.
- LTE logical interface has a live session.
- `lte-route-health` is active.
- production route uses LTE during normal operation.
- DNS and UTC are healthy.
- MQTT bridge is connected over TLS.
- a real uplink reaches ChirpStack/application through the cellular path.

## Detailed runbooks

The consolidated [SIM7600 LTE commissioning and staged recovery procedure](SIM7600-LTE-COMMISSIONING.md) contains the current QMI/route-owner settings and the verified September 21 stale-dataplane failure mode.

- [`../server/cloud-production/11-raspberry-pi-4g-backhaul.md`](../server/cloud-production/11-raspberry-pi-4g-backhaul.md)
- [`../gateway/setup/02a-build-sim7600-capable-gateway-os.md`](../gateway/setup/02a-build-sim7600-capable-gateway-os.md)
- [`../gateway/setup/06-verify-gateway-os.md`](../gateway/setup/06-verify-gateway-os.md)
- [`../gateway/operations/03-availability-tests.md`](../gateway/operations/03-availability-tests.md)