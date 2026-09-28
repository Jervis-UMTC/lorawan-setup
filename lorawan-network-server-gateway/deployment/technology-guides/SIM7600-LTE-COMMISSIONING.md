# SIM7600 LTE Production Backhaul — Installation, Health and Recovery

> This is the commissioned field configuration and recovery logic, based on the tracked Gateway OS image overlay and 2026-09-21 real LTE/MQTT repair. A process being "running" or QMI "connected" **does not** prove that packets can actually cross the carrier network. No hardware or service was changed while preparing this draft.

## 1. Know what is installed and which network does what

| Item | Intended state |
|---|---|
| USB modem | Waveshare SIM7600G-H, QMI composition (no USB-mode changes) |
| QMI control | `/dev/cdc-wdm0` |
| Data path | `wwan0` |
| OpenWrt logical interface | `lte` |
| SIM/carrier/APN (commissioned configuration) | DITO / `internet.dito.ph` |
| Default-route owner | `/usr/sbin/lte-route-health` |
| Production default when QMI session valid | Via carrier gateway, device `wwan0`, metric `10` |
| Management Ethernet | `br-lan`, commissioned `192.168.20.11/24`; **not** a production Internet default |
| Wi-Fi | Not guaranteed as automatic Internet fallback in the **current tracked field overlay**. Only call it a fallback after verifying a separately configured live path. |
| Cloud MQTT | `smartagri-mqtt.duckdns.org:8883`; September commissioning Reserved IPv4 `129.212.208.168` — re-read real deployed hostname/route before use |

`network.lte.defaultroute=0` is **intentional**: OpenWrt netifd must not race the route controller for the production default. Carrier DNS remains enabled with `peerdns=1`, and QMI does not create the unreliable `lte_4` DHCP child (`dhcp=0`).

The reproducible UCI-default script from the tracked overlay sets:

```sh
uci set network.wwan.metric='50'
uci set network.lte='interface'
uci set network.lte.proto='qmi'
uci set network.lte.device='/dev/cdc-wdm0'
uci set network.lte.apn='internet.dito.ph'
uci set network.lte.auth='none'
uci set network.lte.pdptype='IP'
uci set network.lte.dhcp='0'
uci set network.lte.defaultroute='0'
uci set network.lte.peerdns='1'
uci commit network
```

**Do not paste this over a working live configuration as a health check.** This represents the reviewed custom-image default and must be reconciled with the attached SIM, APN, actual network and authorization before initial commissioning or restoring a replaced gateway.

## 2. Why the custom image matters

The stock Gateway OS kernel and stock OpenWrt module repositories were found to have **different kernel ABI hashes** despite sharing an upstream kernel version. Consequently, `--force-depends`, borrowing another image's `.ko` files and binding all vendor interfaces with generic USB-serial IDs are unsafe installation workarounds.

The Gateway OS Base v4.12.0 custom image was built with ABI-matched `kmod-usb-serial`, `kmod-usb-serial-wwan`, `kmod-usb-serial-option`, `kmod-usb-wdm`, `kmod-usb-net`, `kmod-usb-net-qmi-wwan`, `uqmi` and `luci-proto-qmi`. It preserves RAK5146 SPI/AS923, gateway evidence and the persistent local broker. A spare SD card and protected recovery assets are preferred; do not rebuild the running gateway just to reproduce old commissioning work.

## 3. Inspect physical driver binding (Gateway OpenWrt shell)

```sh
lsusb 2>/dev/null || true
ls -l /dev/cdc-wdm* /dev/ttyUSB* 2>/dev/null || true
ip link show wwan0 2>/dev/null || true
dmesg | grep -Ei 'simcom|sim7600|qmi|cdc-wdm|wwan|usb' | tail -n 80
```

**PASS:** modem present, `/dev/cdc-wdm0`, modem tty devices and `wwan0`; no repeated USB disappearance/reenumeration. A missing device is power/cable/USB/kernel, **not** automatically APN, TLS or ChirpStack.

## 4. Check bearer, actual Internet and intended cloud path separately

```sh
ubus call network.interface.lte status
ip -4 addr show dev wwan0
ip route show default
ip route get 129.212.208.168
nslookup smartagri-mqtt.duckdns.org
date -u
logread | grep 'lte-route-health' | tail -n 45
ss -tnp 2>/dev/null | grep ':8883' || netstat -tnp 2>/dev/null | grep ':8883' || true
```

**PASS, in order:** the logical `lte` interface reports current carrier addressing; default route via `wwan0` with metric `10`; broker route via `wwan0`; current DNS lookup succeeds; clock is usable for TLS; both intended gateway Mosquitto bridges have established sessions to the deployed cloud broker endpoint. The IP address reported by QMI is dynamic and **must not** be copied from a historical incident into static configuration.

To distinguish a stale bearer from a healthy dataplane, use the route-controller’s own bounded health log and, only when needed, a verified LTE-bound public-IP test (not merely interface status). Successful ping alone does not prove MQTT mTLS; successful TLS alone does not prove a canonical sensor row or verified evidence.

### Real September 21 failure mode

At the observed outage, QMI and `ubus` reported **connected** with an LTE default route, yet public-IP and carrier-DNS probes timed out, the broker bridges were absent, `dnsmasq` hit its maximum concurrent DNS queries, and controller/QMI child processes had become hung. The cause was diagnosed as the **LTE user-plane dataplane**, not incorrect LoRaWAN keys or automatically bad mTLS certificates. Following a targeted operator repair, two established connections returned and buffered EMU uplinks resumed. This is a dated failure/recovery example, not evidence of current failure.

## 5. Understand the route-health controller (do not fight it)

The tracked controller checks at approximately **30-second** intervals. It installs/keeps the LTE default as soon as it has usable QMI IPv4 and gateway information, before application probes, to keep DNS/NTP and recovery possible. It tests the LTE IP dataplane separately from MQTT mTLS.

- Two consecutive IP-dataplane failures after boot grace can trigger bounded logical `ifdown lte`/`ifup lte`.
- If dataplane remains unavailable after an interface restart, a reviewed reset stage may issue `AT+CFUN=1,1` **only to the SIM7600**, with re-enumeration checks and a **15-minute reset cooldown**.
- A broker/TLS-only failure while public LTE IP works **must not** reset the modem merely because the remote service is unavailable.
- A QMI address/gateway disappearing can remove the stale LTE route. A failed MQTT probe alone should not remove an otherwise valid LTE default.
- Do not blindly run `pkill -f uqmi`, rewrite DNS, start a second health controller or add a permanent management-Ethernet Internet route.

## 6. Targeted recovery only after the failing layer is proved

Normal approach: allow the controller to converge; check real public IP/DNS/broker reachability. Check the module’s power/USB first if enumerating repeatedly. If the controller itself is stuck with confirmed hung QMI descendants and does not respond to normal health checks, an authorized maintenance action previously used the following staged OpenWrt procedure:

```sh
/etc/init.d/lte-route-health stop
ifdown lte
sleep 3
ifup lte
# If the service still has actual orphan QMI/controller descendants:
# inspect their current parent/command/state; terminate ONLY confirmed orphans.
# Do not copy or reuse historical PID values.
/etc/init.d/lte-route-health start
```

This command group is **a failure-specific repair, not a routine preflight or a research outage fixture**. It interrupts cellular service and may cause queued MQTT messages to accumulate temporarily. Ensure management access and evidence persistence before intervention. Do not run during a counted experiment. Let the controller re-establish the LTE route; do not compensate by editing it manually.

Afterwards prove in sequence: QMI public IP/dns works; `wwan0` route to broker is active; both bridge sockets are ESTABLISHED; gateway local broker remains loopback/QoS 1; one new **real** sensor observation reaches cloud ChirpStack and PostgreSQL; gateway journal/witness evidence verifies and eligible Fabric outbox anchoring is confirmed by its **authoritative** stage.

## 7. What to preserve during connectivity loss

Local Concentratord/MQTT Forwarder should keep receiving real radio events, local Mosquitto retains bounded QoS-1 uplinks, and the independent gateway journal stores source lineage. Cloud acceptance/evidence verification are delayed while offline. Neither growing buffered data nor `pending`/zero-attempt Fabric outbox automatically proves data corruption. Do not delete broker persistence or reset gateway journal sequence merely to clear a dashboard.

**Operational PASS** requires service/interface health, true LTE user-plane reachability, current DNS and UTC, normal cloud bridge sessions over LTE and representative physical uplink delivery. **Research PASS** separately requires the approved recorder/experiment conditions and sealed original evidence.
