# Gateway OS / OpenWrt — Operator Manual

## What this technology does

Gateway-01 is a Raspberry Pi 4B running a customized ChirpStack Gateway OS 4.12.0 / OpenWrt-class image. The OS hosts the RAK5146 radio services, MQTT Forwarder, local Mosquitto buffer, gateway evidence runtime, and SIM7600 LTE networking.

This layer is the operating platform. A booted gateway does **not** by itself prove RF, MQTT, LTE, or application delivery.

## Current commissioned boundary

- Platform: Raspberry Pi 4B.
- Gateway OS family: ChirpStack Gateway OS 4.12.0-derived custom image.
- Accepted radio: RAK5146/SX1303.
- Region: **AS923**.
- Gateway EUI: `0016c001f139a1cb`.
- Production Internet path: SIM7600 QMI interface `wwan0`.
- Ethernet: management-only.
- Wi-Fi: a fallback **only if separately configured and live route-tested**; the current field overlay does not guarantee automatic Wi-Fi Internet failover.
- Reflash only for a real regression, media failure, or intentional image change.

## Important paths

| Purpose | Path |
|---|---|
| OpenWrt/UCI configuration | `/etc/config/` |
| Mosquitto configuration | `/etc/mosquitto/` |
| Gateway image overlay source in Git | `deployment/gateway/image-overlay/` |
| Runtime logs | `logread` / service-specific logs |
| Gateway evidence state | use the paths defined by the evidence runbook; preserve it during ordinary recovery |

Never assume `/tmp` is persistent. Do not store the only copy of a certificate, recovery archive, or research evidence there.

## Step 1 — Confirm you are on Gateway-01

Run on the gateway shell:

```sh
cat /etc/os-release
uname -a
ubus call system board
date -u
```

**PASS means:** the board is the expected Raspberry Pi/Gateway OS environment and UTC is plausible.

**If this fails:** do not troubleshoot ChirpStack or MQTT yet. Check power, SD card boot, console, or management networking.

## Step 2 — Check storage before doing anything else

```sh
df -h
mount
```

**PASS means:** root/overlay storage is writable and has free space. A nearly full filesystem can make otherwise unrelated services fail.

**If free space is dangerously low:** do not blindly delete `/etc`, certificates, journal state, Mosquitto persistence, or evidence files. Use the backup/recovery manual to identify safe cleanup targets.

## Step 3 — Check interfaces and routes

```sh
ip -br addr 2>/dev/null || ip addr
ip route
ubus call network.interface dump
```

**PASS means:** management access is present and the intended production path can be identified. On the commissioned gateway, normal production Internet should converge to `wwan0`; Ethernet must remain management-only.

Do not add a manual default route merely because LTE is still converging immediately after boot. The commissioned `lte-route-health` controller owns production route selection.

## Step 4 — Check failed/restarting services

```sh
monit status 2>/dev/null || true
ps w | grep -E '[c]hirpstack-concentratord|[c]hirpstack-mqtt-forwarder|[m]osquitto|[l]te-route-health'
logread | tail -n 120
```

**PASS means:** expected services are present and there is no obvious crash loop, storage error, kernel fault, or repeated modem reset.

A service showing as running is only a process-level check. Continue to the radio, MQTT, and LTE guides for protocol-level proof.

## Step 5 — Inspect configuration safely

Use UCI to inspect only the intended configuration. **Caution:** `uci show network` and other UCI sections can still reveal APN credentials, passwords, authentication tokens or identity paths. Run them only in an approved private terminal, and redact values before putting output into logs, research captures, Markdown or chat. UCI is not automatically secret-safe:

```sh
uci show network
uci show chirpstack-concentratord
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
```

Expected high-level facts:

- Concentratord uses the SX1302/SX1303 RAK5146 profile.
- region/channel plan is AS923.
- MQTT Forwarder points to `tcp://127.0.0.1:1883`.
- MQTT topic prefix is `as923`.
- legacy UDP forwarding is disabled.

Do not copy an old inactive SX1301 Gateway EUI into current configuration.

## Step 6 — Back up before any OS/configuration mutation

For a small UCI/configuration change, first create a Gateway OS backup using **LuCI -> System -> Backup / Flash Firmware -> Generate archive** and copy it off the gateway.

For image/reflash work, also preserve the protected MQTT/evidence identity material according to [`../gateway/operations/02-backup-and-recovery.md`](../gateway/operations/02-backup-and-recovery.md). A normal sysupgrade archive is not guaranteed to contain every private identity or persistent data file.

**Hard stop:** do not reflash until an off-gateway rollback copy and a known-good image are available.

## Step 7 — Make changes with the smallest possible blast radius

For UCI-managed settings:

1. inspect the current section with `uci show`;
2. change only the required option through LuCI/UCI;
3. save/commit;
4. restart or reload only the affected service;
5. immediately run that service's verification steps.

Do not reboot the entire gateway merely to apply a single service change unless that technology specifically requires reboot-level validation.

## Step 8 — Post-change platform verification

```sh
ubus call system board
date -u
df -h
ip route
monit status 2>/dev/null || true
logread | tail -n 100
```

Then verify the affected functional layer:

- radio change -> [02-rak5146-concentratord-as923.md](02-rak5146-concentratord-as923.md)
- LTE/network change -> [03-sim7600-lte-backhaul.md](03-sim7600-lte-backhaul.md)
- MQTT change -> [04-mosquitto-mqtt.md](04-mosquitto-mqtt.md)

## Troubleshooting order

| Symptom | First layer to inspect |
|---|---|
| Gateway completely unreachable | power, SD boot, management interface |
| Shell works but RAK5146 unavailable | Concentratord/SPI/RF guide |
| RF works but cloud delivery fails | local Mosquitto then LTE |
| LTE works but MQTT bridge fails | TLS identity/ACL/cloud MQTT |
| Cloud MQTT works but no app event | ChirpStack |
| Application works but evidence missing | gateway evidence services |

## Recovery rules

- Preserve identities before reinstalling.
- Preserve current journal/evidence state unless the recovery procedure explicitly calls for a deliberate lineage reset.
- A new SD card/image is not automatically a new Gateway EUI; the active RAK5146 identity remains the radio authority.
- After restore/reflash, verify time, storage, RAK5146 EUI, AS923, local MQTT, LTE routing, cloud MQTT, and evidence path before calling recovery complete.

## Completion checklist

The OS layer is healthy when all are true:

- correct Gateway OS/platform is booted;
- UTC is correct;
- persistent storage has safe free space;
- expected interfaces exist;
- production routing can converge correctly;
- no immediate crash loop or failed core service exists;
- effective UCI configuration still matches the current architecture;
- the next functional-layer checks pass.

## Detailed rebuild/recovery runbooks

Start with the consolidated [Gateway hardware, image and protected recovery procedure](GATEWAY-REBUILD-AND-RECOVERY.md), which brings the key setup/recovery prerequisites into one Markdown document.

- [`../gateway/setup/02-install-chirpstack-gateway-os.md`](../gateway/setup/02-install-chirpstack-gateway-os.md)
- [`../gateway/setup/02a-build-sim7600-capable-gateway-os.md`](../gateway/setup/02a-build-sim7600-capable-gateway-os.md)
- [`../gateway/setup/06-verify-gateway-os.md`](../gateway/setup/06-verify-gateway-os.md)
- [`../gateway/operations/02-backup-and-recovery.md`](../gateway/operations/02-backup-and-recovery.md)
- [`../gateway/operations/05-troubleshooting.md`](../gateway/operations/05-troubleshooting.md)