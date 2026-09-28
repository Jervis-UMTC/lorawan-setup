# F1 partial live commissioning and Gateway-01 cloud-bridge block — 2026-09-21

**State:** Isolated F1 load actor PASS; whole-system F1 rehearsal **BLOCKED BEFORE FLOOD** by actual gateway-to-cloud MQTT bridge outage. Neither synthetic nor partial observations are Chapter 4 counted data.

## Exact findings

- `run_test.py F1`, `RESEARCH_MANUAL_REHEARSAL_SECONDS=30`, `EXECUTE`: nonzero exit during `ensure_ready.py`. Tool/contract/oversight/firmware/recorder gates PASS; gateway LTE gate FAIL because `mqtt_established=false`; LIVE_PRE was SKIPPED. No flooding or counted action started by this command.
- Gateway Ethernet/restricted recorder live. LTE interface `wwan0=100.73.133.167/28` UP and network registered, public broker route `129.212.208.168 via 100.73.133.168 dev wwan0`, default via `wwan0`; signal near RSRP -104 to -105 dBm, SNR -3.2 to 0 dB at investigation time. **No TCP :8883 established session** on the gateway. Concentratord still receives new physical EMU-01 frames on AS923 923.2/923.4 MHz at 15-second intervals; local ChirpStack MQTT forwarder still emits local MQTT topics.
- Live, bounded gateway `logstream` showed both `cloud-uplink` and `cloud-downlink` attempts to `smartagri-mqtt.duckdns.org:8883` and repeated Mosquitto `Error creating bridge: Try again.` The literal error does **not alone establish** whether the fault is DNS, LTE carrier reachability, or another connector-level failure.
- The ULC-01 resolver returns `129.212.208.168` for that DuckDNS name; cloud host had MQTT :8883 listening on relevant private interfaces; workstation TCP to `129.212.208.168:8883` succeeded. A read-only restricted server DB export `2026-09-21T05:25:00Z..05:40:00Z` showed **zero new EMU-01 uplinks** despite fresh gateway radio frames. This is the current loss boundary: local gateway-to-public-broker cloud bridge; do not diagnose the still-running database/Fabric chain as the source of this gap.
- Current project-authorized research-recorder gateway SSH key exposes bounded `snapshot`, `radio-recent`, `logstream`, etc. but not root shell/service/network mutations. No gateway DNS, routes, certificates, Mosquitto bridge configuration, or production broker were changed; a safe external admin gateway path must be established before privileged repair. Do not bypass the live LTE gate just to obtain a research PASS.

## Isolated F1 actor/fixture rehearsal (genuine network traffic, not synthetic)

The checked `run_test.py F1 --synthetic` passed **16/16** code/contract tests. Separately, the existing Python `flood_harness.py` actions started **only** the ephemeral ULC-01 flood listener `127.0.0.1:1885`, verified `FLOOD_PASSWORD_SMOKE=PASS`, and opened the explicitly owned SSH tunnel `127.0.0.1:11885`. One non-counted actual workload per rate:

| Rate, connections/second | Duration | Launched / planned | Isolated listener rejects | Accepted invalid | Local/unobserved errors | Result |
|---|---:|---:|---:|---:|---:|---|
| 0 | 3 s | 0/0 | 0 | 0 | 0 | PASS |
| 10 | 4 s | 40/40 | 40 | 0 | 0 | PASS |
| 50 | 4 s | 200/200 | 200 | 0 | 0 | PASS |

`target_observed` matched 0, 40, 200, respectively. SSH tunnel cleanup PASS; research listener stop and independent status `listener=INACTIVE`. Production Mosquitto and its normal topics were untouched. This proves the **isolated test actor and rejection measurement**, not legitimate-sensor delivery during the actual F1 0/10/50 windows. No end-to-end F1 verdict or research samples may be reported from it.

## Efficient next step

Recover Gateway-01 bridge connectivity first. With authorized gateway admin access, inspect current `smartagri-mqtt.duckdns.org` DNS resolution and nameserver reachability through LTE, bounded TCP :8883 reachability via `wwan0`, the actual two bridge configs/TLS error details, and Mosquitto live state. Correct the identified layer without rerouting through RJ45, disabling certificate validation, weakening mTLS, touching production broker credentials, or blindly resetting LTE. Confirm two established cloud `:8883` sessions from `wwan0` and one new verified EMU-01 uplink and outbox confirmation. Then rerun `run_test.py F1` with the existing non-counted rehearsal environment setting and its normal preflight; preserve the full 0/10/50 per-window valid delivery/rejection proof.
