# Gateway-01 administrator access and LTE/MQTT recovery — 2026-09-21

## Gateway administrator credential (protected; not Git)

- Host: `192.168.20.11` on management Ethernet; account: `root`.
- The verified password is saved on the project workstation **outside the Git repository** in a Windows-DPAPI encrypted, current-user credential file:

  `C:\Users\smartagriintern\.lorawan-private\gateway-01-root.dpapi`

- This directory has NTFS permission inheritance disabled, restricted to the workstation user and SYSTEM. The password **ends in a literal period (.)**; omitting it causes authentication failure. SSH password login with the exact supplied credential was verified on the physical gateway on 2026-09-21. The similarly named cloud `opsadmin` account is a separate login; never assume passwords are interchangeable.
- To load the password in a secure PowerShell object while logged in as the same Windows user: `$gatewayRootPassword = Get-Content -LiteralPath (Join-Path $HOME '.lorawan-private\gateway-01-root.dpapi') -Raw | ConvertTo-SecureString`. DPAPI material may not decrypt on a different workstation/Windows profile; transfer through an approved secure secret manager if the machine is rebuilt. For manual login: `ssh root@192.168.20.11` and supply the gateway password when prompted.
- **Never commit the plaintext password or decrypted value to `.md`, a command argument, screenshots, generated PDFs, a transcript, or Git.** The protected credential file is the recorded password; this guide documents exactly where and how to retrieve it.
- The research recorder SSH key `~/.ssh/id_ed25519_research_recorder` intentionally has forced-command read-only access. Do not remove that guard; use separate authenticated root/password access for gateway administration.

## Live bridge failure and recovery (verified)

The commissioned path is EMU-01 -> Gateway-01 AS923 -> local MQTT -> **SIM7600 `wwan0`** -> `smartagri-mqtt.duckdns.org:8883` (Reserved IP `129.212.208.168`) -> ChirpStack/DB/evidence/Fabric. RJ45 `br-lan=192.168.20.11/24` is management only, not an alternate Internet backhaul.

At ~06:03 UTC 2026-09-21 both Mosquitto bridges were disconnected with `Error creating bridge: Try again.` The apparent QMI state was misleading: `network.interface.lte up=true`, `uqmi --get-data-status=connected`, public route `via wwan0`, and the stale PDP address existed, **but direct carrier DNS and 1.1.1.1 public IP probes timed out**, while dnsmasq logged `Maximum number of concurrent DNS queries reached (max: 150)`. Remote broker was reachable from the workstation; gateway Concentratord continued to receive local radio frames. This is a stale LTE IP dataplane with cascading DNS failure, not evidence of wrong Mosquitto credentials or certificate mismatch.

`lte-route-health` service itself was nominally running but had hung descendants `/usr/sbin/lte-route-health daemon` and `uqmi -d /dev/cdc-wdm0 --get-current-settings`; its persisted failure state had not updated since ~05:05 UTC. Only this verified blocked state justified manual targeted recovery; do not reset SIM7600 for a broker-only outage when IP/dataplane passes.

Actual successful stage-1 recovery, through the authorized Gateway-01 root management console:

```sh
/etc/init.d/lte-route-health stop
ifdown lte
sleep 3
ifup lte
# Remove ONLY identified orphaned QMI/controller workers from this stopped service.
# Their historical PIDs were 17548, 17549, 17553; NEVER reuse these PID numbers.
# Inspect ps/parent ownership before terminating any process.
/etc/init.d/lte-route-health start
```

The system initially lacked its public default after `ifup lte` because `lte-route-health` owns the field default route. It returned after the controller started, **without modifying UCI DNS, routes, TLS files, bridge settings, or the production broker**. Revalidation:

- `default via 100.73.133.168 dev wwan0 src 100.73.133.167 metric 10`.
- Public LTE ping returned a real ICMP reply from `1.1.1.1` (~265.7 ms).
- Direct carrier DNS `131.226.72.19` resolved the broker hostname to `129.212.208.168`.
- `netstat -nt` showed **two distinct `ESTABLISHED` TCP sessions** from `100.73.133.167` to `129.212.208.168:8883`; one later read-only recorder snapshot independently confirmed the pair.
- Cloud DB packet-flow readback then showed 76 buffered EMU-01 uplinks in the queried reconnect window, proving resumed transport. At that sample they were still pending evidence and Fabric settlement. Gateway uploader logs recorded prior exit status 6 (DNS) then exit status 52 on its first attempt after transport recovery. Do **not** mark them verified/committed before an independent later query actually confirms it.

The health-controller script lives at `deployment/gateway/image-overlay/files/usr/sbin/lte-route-health`, SHA-256 `39fc435777025484f7543818873d6e106f12fd93e58111a66feace45f6ea995e` as deployed at the incident. The observed hangs warrant a separate bounded-process/wait-child watchdog review; do not claim the controller itself auto-recovered this incident.

## Subsequent sensor, evidence, and F1 recovery

After the bridges returned, EMU-01 was found sampling on COM11 at 15-second intervals but its `SENSOR_TX` sequences 223/224 had `join=1,send_status=-1` and gateway radio frames had stopped at ~05:59:37Z. The frozen research image was checked and restored with the existing controlled DFU canary. `chapter4-results/authentication/lorawan/A1-LORAWAN-emu-reboot-canary-20260921-141713/summary.json` records **PASS**, an observed real join callback, successful uplink and verified 15-second cadence. No formal trial was counted. The gateway subsequently received fresh AS923 frames at 923.2/923.4 MHz and the cloud received new EMU uplinks.

The evidence verifier also resumed: samples progressed from `verified=3818,pending=82,latest_verified_at=05:19Z` before recovery to `verified=3924,pending=18,latest_verified_at=06:26:42Z` afterward, with `evidence_gap=0` and `integrity_failure=0`. A later F1-window packet-flow export showed 31 EMU entries, of which 13 were verified/confirmed, 17 still pending/pending and one verified/pending at that instant. Backlog settles asynchronously; this is a point-in-time count, not a permanent clean-queue guarantee.

The **full real F1** isolated connection flood then passed at 0/10/50 invalid connection attempts per second, 30 seconds per window, and two legitimate EMU-01 cloud deliveries in each window; 0 invalid connections were accepted. See `F1-LIVE-REHEARSAL-20260921.md`. F1's own recorder has Fabric settlement disabled, so it is not independent HRC-ledger proof. The full F2 test remains the next live commissioning target.

## Minimal recurrence check

Use the current restricted gateway `snapshot` first: confirm registered LTE, default via `wwan0`, **two established** broker `:8883` connections. If absent, root check `ip route`, `nslookup` against configured carrier servers, public-IP dataplane, `logread -e mosquitto`, and active `lte-route-health` processes. Separate QMI bearer presence from actual user-plane traffic. Preserve gateway time, mTLS, sensor firmware and evidence journal across targeted LTE restarts. Finally require one new EMU-01 packet in ChirpStack/DB and one confirmed, evidence-verified outbox transaction before declaring complete sensor-to-Fabric recovery.

Current flood-test state: full live non-counted F1 rehearsal has passed; the isolated-only F2 actor also passed, but the full real F2 windows remain uncommissioned. No Chapter 4 trial was counted during this repair or rehearsal.
