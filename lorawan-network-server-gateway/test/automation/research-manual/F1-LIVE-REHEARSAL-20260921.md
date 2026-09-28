# F1 live connection-flood commissioning — 2026-09-21 (non-counted)

**Outcome:** Real, complete operator command `RESEARCH_MANUAL_REHEARSAL_SECONDS=30 py -3 test/automation/research-manual/run_test.py F1` with `EXECUTE` exited 0. `TECHNICAL_GATE=PASS`, `GATEWAY_LTE=PASS`, `LIVE_PRE=PASS`, `FLOOD_HARNESS=PASS test=F1 formal=False runs=3`. This supersedes only the earlier F1 full-live block in `F1-PARTIAL-REHEARSAL-20260921.md`; earlier test history remains preserved.

## Genuine flood windows and valid EMU-01 delivery

Session JSON: `chapter4-results/dos-flooding/_sessions/F1-20260921-141932.json`. Each 30-second test window has its own sealed recorder directory `chapter4-results/dos-flooding/F1-rehearsal-r{0,10,50}-n1-20260921-141932/` with SHA256SUMS manifest, separate source log/DB uplink, gateway MQTT, outbox and flood-observation raw files.

| Invalid connection rate | Planned/attempted | Rejected/observed | Incorrectly accepted | Legitimate EMU-01 deliveries within window | Mean latency |
|---|---:|---:|---:|---:|---:|
| 0/s | 0/0 | 0 | 0 | 2 | 59.293 ms |
| 10/s | 300/300 | 300 | 0 | 2 | 45.616 ms |
| 50/s | 1500/1500 | 1500 | 0 | 2 | 36.759 ms |

Every recorder returned code 0, rate achievement 0/10/50 s^-1, local generator errors 0, DB guard found 0 fake uplinks/outbox records and each window found 0 unauthorized uplinks/outbox. The isolated listener was independently stopped and reported `INACTIVE`; session `cleanup_errors=[]`. The real gateway remained LTE-primary and transmitted legitimate EMU-01 data through the same real infrastructure.

**Evidence boundary:** Each F1 recorder `metadata/fabric-settle.json` explicitly records `enabled=false`, status `DISABLED`. The F1 decision tests valid cloud database delivery and invalid-connection isolation; it does not itself independently prove per-window Fabric ledger state. Separate post-run gateway packet-flow readback found new EMU rows progressing through evidence verification and some confirmed Fabric outbox transactions; do not confuse those with a per-window HRC ledger query. Every run is `formal=false`; no Chapter 4 trial was counted.

## How the prior environmental block was cleared

Read `GATEWAY-ADMIN-AND-LTE-RECOVERY-20260921.md` for the separate recovered stale SIM7600 LTE userplane, offline carrier DNS, blocked health-controller worker, authorized root access and protected Windows-DPAPI credential location. Two established mTLS broker sockets were verified from `wwan0`; EMU-01 was separately restored with a SHA256-verified same-image DFU after observed `send_status=-1`. The evidence verifier's count progressed from 3818 through 3924 with 0 gaps and 0 integrity failures on subsequent samples. These repairs were non-counted commissioning actions.

**Next:** Complete one similarly bounded, genuine F2 malformed-message full-window rehearsal; retain the earlier F2 isolated-only observations separately. If LTE or EMU telemetry drops again, fail preflight rather than invent a flood PASS. Do not re-run this F1 solely to repeat already established evidence.
