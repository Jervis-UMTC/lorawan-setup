# Research Test Manual Continuation

## P1 preflight — 2026-09-28

Fresh live P1 preflight PASS. `ensure_ready.py` generated `CURRENT-READINESS.json` at 2026-09-28T00:30:11Z with technical/tooling gates PASS, recorder CLEAN, counted EMU firmware archive PASS, Gateway LTE PASS, Live PRE PASS and P1 READY. EMU-01 was observed on COM11 with three joined successful `SENSOR_TX` transmissions at 15.005/15.010-second cadence; Gateway-01 received current SF7 AS923 uplinks at 923.2/923.4 MHz. A 60-second live Gateway logstream observed zero USB disconnects, qmi_wwan -71 errors, LTE-down events, MQTT mTLS failures or bridge errors. LTE session uptime was 1224 seconds on the final gate, with wwan0 cloud route and two MQTT TLS sockets established. Evidence services were ready on all ULC nodes; verification backlog fell from 21 pending to 8 while verified count advanced from 5278 to 5299, showing catch-up rather than a stuck pipeline. Because the previous counted P1 failure was caused by repeated SIM7600 USB/QMI resets, `ensure_ready.py` now requires at least 600 seconds of continuous LTE-session uptime before P1 can be declared ready. No counted P1 run was started during this preflight.

The canonical editable, single-file research results log is `documentation/LoRaWAN_Research_Test_Results.docx`. It starts with P1; append each subsequent actual LoRaWAN-controlled test into that same Word file using the OfficeCLI extension. Do not create separate final-results DOCXs. The LoRaWAN team runs tests through `jervis-hijo`; the HRC Fabric manual is reference methodology and HRC evidence may be joined only when actually observed, without initiating a second Fabric-side test. P1 `P1-1-20260922-105310` retains `RECORDED_WITH_ERRORS` and must not be counted as a clean formal repetition.

## P1 real 30-minute evidence and recorder interruption — 2026-09-22

A genuine `P1-1-20260922-105310` closed 30-minute EMU-01 run measured 120 source attempts, 119 unique accepted ChirpStack uplinks, 119 stored events / 1,547 sensor rows, and 119/119 Fabric-confirmed outbox records. Formal PDR 99.1667%; sensor→DB mean 628.631 ms (sample SD 165.634 ms); 119/1,800 = 0.06611 stored readings/s; clock calibration PASS. The supervised owner and all 11 collectors were already dead when recovered after the measurement window. Recovery sealed 63 files and regenerated the summary; independent reproducibility PASS, but `run-status.txt=RECORDED_WITH_ERRORS` and operator recovery exit=2. **Do not count this as a clean formal P1 repetition.** Preserve the genuine measurements and original failure; full provenance and operating correction: `test/automation/research-manual/P1-LIVE-AUDIT-20260922.md`. P1 must run in a persistent PowerShell session through the measurement, Fabric settlement and finalization; count only clean, validated, sealed repetitions.

## I2 current-v2 post-storage integrity contract gap — 2026-09-21 (latest)

**Current Step:** I2 remains `HARNESS_REQUIRED` **by design**, without changing production SQL, source records, ledger state or the evidence outbox. Two independently verified real confirmed EMU-01 R2 records use `telemetry-attestation-v2`, but I2's existing Go read-only current-source rehasher and Python scorer are frozen to v1 synthetic vectors. Production v2 requires a verified gateway lineage row and the HRC ledger anchor hashes immutable `finalized_payload` exact bytes separately from sealed canonical evidence. Running v1 tamper logic against those live v2 rows would be an incorrect conclusion.

**Completed:** Verified actual production schema/anchor implementation in `evidence-services/cloud/internal/fabricadapter/evidence.go`, `canonical.go`, `worker.go` and `cmd/research-i2-current-source/main.go`; added regression explicitly rejecting real-v2-shaped schema in the v1 I2 scorer. I2 code-only **26/26 PASS**, total allowlisted offline suite **208/208 PASS, 16 suites** at `chapter4-results/code-qualification/offline-code-20260921T083510017298Z/code-only-summary.json`. Corrected I2 operator-status explanation and historical v1 guide; full non-destructive v2 exporter/recompute/original anchor split, independent HRC query and transactional restore requirements: `test/automation/research-manual/I2-LIVE-READINESS-20260921.md`. No formal Chapter 4 trial counted.

**Next Step:** Implement/qualify a read-only production-v2 snapshot exporter and Go recomputation with verified gateway lineage and exact original outbox/anchor refs; test a reserved clone/transactional row and guaranteed restore before authorizing any production post-storage alteration. Do not let the v1 synthetic scorer masquerade as live evidence.

## R2 two-record real Fabric reconciliation commissioned — 2026-09-21 (current)

**Current Step:** Scoped non-counted R2 **PASS**, with exact two source-event records reconciled after Fabric gateway reaccess. Formal ten-record R2 and independent HRC ledger-query confirmation remain unreleased; do not count this as a Chapter 4 trial.

**Completed:** Installed the hash-verified repository Fabric-isolation helper on ULC-01; current adapter `lorawan-gateway-evidence-fabric-adapter-1` at `172.19.0.4` connects to private HRC Fabric Gateway `10.104.0.7:7051`. Its scoped `DOCKER-USER` rule was empty/inactive before and is now **INACTIVE** after restoration; recorder clean. The first rehearsal `R2-rehearsal-20260921-155652` failed **before isolation** at baseline 0/2 due delayed async outbox confirmation; retained as a failed commissioning attempt. The follow-up non-counted real `R2-rehearsal-20260921-160954` passed: 2/2 fresh confirmed baseline, 2/2 newly selected outage records remained unconfirmed during adapter-only Fabric endpoint REJECT, 2/2 of the **same source_event_keys and SHA-256 digests** confirmed exactly once with TxIDs after removal, no false verification, recovery **56.370 s**. An additional independent live ULC-01 DB-leader readback reconfirmed those two keys, digests and TxIDs after the session. Session and sealed recorder: `chapter4-results/resilience/_sessions/R2-rehearsal-20260921-160954.json` and `chapter4-results/resilience/R2-rehearsal-20260921-160954/`; full distinction in `test/automation/research-manual/R2-LIVE-READINESS-20260921.md`. Latest after-code-change offline qualification **207/207 PASS across 16 suites**, `chapter4-results/code-qualification/offline-code-20260921T081154179024Z/code-only-summary.json`.

**Important scope:** The failed outage records show `fabric_prepare_failure`, with **no prepared TxID** at the outage boundary. This qualifies recovery from Prepare unavailability, not runtime same-prepared-transaction retry or an independent HRC `QuerySourceBoundAnchor` world-state proof. Keep R2 `HARNESS_REQUIRED` for its formal ten-record procedure. No extra induced outage is needed just to repeat this rehearsal.

**Next Step:** Commission a different as-yet unqualified intervention or coordinate independent HRC ledger-query evidence with the Fabric side. Preserve LTE primary routing, adapter availability and research recorder clean state.

## S1 live security proof and R2 scoped-isolation deployment gap — 2026-09-21 (current)

**Current Step:** S1 now has **2/2 genuine non-counted RF attack probes received and not accepted**; R2 remains `HARNESS_REQUIRED` because ULC-01's pre-existing restricted `fabric-isolation-status` action points to a missing deployed root helper. No R2 Fabric outage was started.

**Completed:** S1 old exact ciphertext replay `FCnt=212` independently received by RAK5146 uplink ID `1391523988`, immutable journal sequence `4280`; no accepted application, database or Fabric outbox event. S1 fresh-counter wrong-MIC spoof retained DevAddr, `FCnt=307`, gateway uplink ID `3113324003`, journal sequence `4315`, also not accepted; later genuine uplink using the same frame counter was accepted. SEC-01 independently verified parked `NWM=1 BAND=8 NJM=1 CLASS=A NJS=0 DEVEUI=0...`. **No explicit ChirpStack MIC-specific rejection log was observed**—do not invent that narrower claim. All 8 original session files SHA-256-verified; real non-counted summary `chapter4-results/security/S1-rehearsal-20260921/session-summary.json`, explanation `test/automation/research-manual/S1-LIVE-REHEARSAL-20260921.md`. After RUI3 replay-helper code fixes, consolidated offline suite **205/205 PASS (16 suites)**. Formal S1 40-attempt design remains uncommissioned.

**R2 live read-only finding:** `r2_fabric_reconciliation.py` source-order guard PASS, but restricted `fabric-isolation-status` failed `sudo: /usr/local/sbin/lorawan-fabric-endpoint-isolation: command not found`. Exact safe operator `run_test.py R2` correctly returned `HARNESS_REQUIRED`, guard/interface PASS, counted test not started. Missing helper is in the repo at `test/automation/resilience/fabric_endpoint_isolation.sh`; deployment/privilege layout and conditional recovery are documented in `test/automation/research-manual/R2-LIVE-READINESS-20260921.md`. No firewall/network change was applied and no live R2 conclusion may be claimed.

**Next Step:** Reconcile the ULC-01 helper with its source under authorized administration and verify actual adapter container private source IP plus endpoint before one scoped non-counted outage; meanwhile commission the next safe non-disruptive research test, avoiding gratuitous repeats of S1/F1/F2.

## S1 real replay and invalid-MIC spoof rehearsals — 2026-09-21 (latest)

**Current Step:** S1 has two genuine, received, non-counted RF attack proofs: replay **1/1** and invalid-MIC address-level spoof **1/1**. Neither was accepted as a ChirpStack application uplink or created a DB/outbox row. Complete 40-attempt Chapter 3 S1 operator harness is still **CAPTURE_READY**, not formally released.

**Completed:** Physical SEC-01 COM16 RUI3 4.2.4 AS923 and EMU COM11 verified, captured accepted immutable-gateway-journal + packetflow + RAK5146 PHY control `FCnt=212`, SHA-256 `ee93f129...`, 7 FCnt old at fixture creation. Corrected live S1 helper bugs: forced-low DTR/RTS caused mute UART; one serial handle did not survive `AT+NWM=0/1` re-enumeration; `AT+PCRYPT=0` is unsupported. New helper reopens USB per command, never retries ambiguous `AT+PSEND`, fails promptly for unknown commands and verifies SEC's parked RUI3 state after each action. Replayed exact 59 ciphertext bytes: RAK frame ID **1391523988**, journal sequence **4280**, cloud UTC `07:18:13.561Z`; same SHA-256 appears in gateway event only, no application/DB/outbox. Spoofed preserved DevAddr `0199DDF0`, fresh unaccepted `FCnt=307` vs latest 275, last MIC byte XOR01 without recomputation or session keys: RAK ID **3113324003**, gateway sequence **4315**, `07:26:34.807Z`, gateway event only. Later genuine packet with same DevAddr/FCnt307 was accepted, proving attack did not consume the counter. SEC returned verified `NWM=1,BAND=8,NJM=1,CLASS=A,NJS=0,DEVEUI=0000000000000000`; evidence verifier gap/integrity errors 0. **Explicit ChirpStack MIC-error log NOT_OBSERVED** (do not invent that evidence). Cloud/workstation time offset -86.403517s calibrated by live recorder PRE to correlate transmit and radio times. Eight SHA-256-sealed evidence files and status in `chapter4-results/security/S1-rehearsal-20260921/`; explanation `test/automation/research-manual/S1-LIVE-REHEARSAL-20260921.md`. Full allowlisted code regression **205/205 PASS across 16 suites**, `chapter4-results/code-qualification/offline-code-20260921T073413715890Z/code-only-summary.json`. All formal counts remain 0.

**Next Step:** Automate distinct 10 control + 10 physically received replay + 10 fresh control + 10 received spoof attempts with explicit ChirpStack counter/MIC log provenance and per-attempt CSV before formal S1. For another test, prefer an unqualified Fabric-connected test (R2/P2/I2) when HRC-side actor/readback is available; do not replay these already proved two smoke attacks just for a duplicate check.

## F2 combined evidence recovered and runner made interruption-safe — 2026-09-21 (latest)

**Current Step:** F2's already completed live 0/10/50 malformed-message windows are preserved in a single **recovered** non-counted session. No malformed traffic was regenerated. The original outer command **timed out**, not exit 0, so formal operator release remains conservative.

**Completed:** Ran `py -3 test/automation/flooding/flood_session.py F2 20260921-143817`, which independently rescored all three saved real F2 windows, verified all **186** manifest-listed files by SHA-256 and size, and checked ULC-03 original Node-RED flow healthy/branch absent, ULC-01 isolated listener INACTIVE, workstation tunnel absent and recorder clean. Wrote `chapter4-results/dos-flooding/_sessions/F2-20260921-143817.json` with `status=WINDOWS_PASS_OPERATOR_TIMEOUT`, `operator_exit_code=null`, `formal=false`, and `counted_research=false`; no fabricated command PASS. Hardened `flood_harness.py` to atomically checkpoint at start, after **each** completed flood window, on failure/interruption and after teardown; incomplete work never reports PASS. Added 4 offline tests for complete session, partial failure, bad SHA-256, and missing windows; full code-only suite **202/202 PASS across 16 suites** at `chapter4-results/code-qualification/offline-code-20260921T070240188741Z/code-only-summary.json`. For future F2 **rehearsals only**, default recovery is 10 s for 30 s measurements to fit bounded remote execution; formal F2 remains unchanged at 300 s flood / 300 s recovery x3 repetitions. The new one-block path is code-tested but not independently re-run live. Details: `test/automation/research-manual/F2-LIVE-REHEARSAL-20260921.md`.

**Next Step:** Commission another unqualified research intervention (S1 live reception or R2 with Fabric-side readiness), using the existing PRE/LTE sensor flow; avoid repeating F2's already qualified 1,800 malformed-message measurement simply to prove report writing.

## Full F2 malformed-message windows qualified / runner timeout — 2026-09-21 (latest)

**Current Step:** All three genuine 30-second F2 cloud-UTC flood windows are recorded **PASS**; the original one-block MCP invocation timed out at 570 seconds after window finalization and did not emit the combined session/exit 0. Do not claim the operator command fully qualified, and do not repeat all 1,800 malformed messages unnecessarily.

**Completed:** The manual F2 preflight passed `TECHNICAL_GATE`, `GATEWAY_LTE`, `LIVE_PRE`, firmware, clock and recorder clean. Actual 0/10/50 malformed-message/s test windows observed rejected 0/0, 300/300 and 1500/1500, accepted 0, legitimate EMU-01 cloud deliveries **1/2/2**, unauthorized uplink/outbox 0, per-window harness PASS, recorder return code 0. Independently reran real F2 scorer and checked **186** manifest-listed files by SHA-256 and byte length: PASS. After forced runner termination, verified ULC-03 temporary Node-RED branch gone, original flow hash restored, healthy container; actively stopped leftover ULC-01 isolated listener, confirmed INACTIVE; SSH test tunnel and recorder sentinel absent. Evidence `chapter4-results/dos-flooding/F2-rehearsal-r{0,10,50}-n1-20260921-143817/` and `test/automation/research-manual/F2-LIVE-REHEARSAL-20260921.md`. Recorder's independent Fabric settlement is disabled for F1/F2, so no per-window HRC ledger-query claim. No counted research.

**Next Step:** Qualify F2 one-block orchestration completion using a persistent process or shorter non-counted recovery profile if needed; the 30-second window methodology and load actor already passed. Then proceed to other uncommissioned tests or HRC independent ledger evidence, not another routine F1/P1/T1/T2 replay.

## Gateway root access restored, LTE+EMU recovered, real F1 PASS — 2026-09-21 (latest)

**Current Step:** Gateway-01 administrator login is now verified: `ssh root@192.168.20.11`. The earlier 05:55 "admin access blocked" and F1 "gateway cloud bridge blocked" sections below are **historical** and superseded. The exact user-provided password includes a **final period**, which was missing from earlier attempts. It is recorded outside Git in a protected Windows DPAPI credential file `C:\Users\smartagriintern\.lorawan-private\gateway-01-root.dpapi` (NTFS inheritance disabled); retrieval and recovery details: `test/automation/research-manual/GATEWAY-ADMIN-AND-LTE-RECOVERY-20260921.md`. Never commit/decrypt the actual password into repository Markdown or logs.

**Completed:** Identified the true MQTT failure as a **stale SIM7600 LTE IP dataplane/QMI worker**, not broker TLS: QMI reported "connected" but real public IP and direct carrier DNS timed out, dnsmasq saturated, health-controller QMI descendants hung. Through admin SSH, stopped only the LTE route-health controller, performed targeted `ifdown lte`/`ifup lte`, terminated only independently identified orphan QMI/controller PIDs, restarted route-health. Verified real 1.1.1.1 reply, carrier DNS resolution, restored default via `wwan0`, **two established 100.73.133.167 -> 129.212.208.168:8883 bridge sockets**; no Mosquitto/certificate/UCI changes or LAN fallback. EMU-01 was separately sampling but stuck `send_status=-1`; the SHA-256-verified same-image DFU canary restored successful OTAA and uplinks (`chapter4-results/authentication/lorawan/A1-LORAWAN-emu-reboot-canary-20260921-141713/summary.json`: PASS, non-counted). Evidence verifier recovered from 3818 verified/82 pending to 3924 verified/18 pending at a later snapshot, gaps and integrity failures 0.

**Full F1 live, non-counted rehearsal PASS:** Exact manual `run_test.py F1` with 30-second windows passed `TECHNICAL_GATE`, `GATEWAY_LTE`, `LIVE_PRE`, and all 0/10/50 connections/s windows. Rejected **0/0, 300/300 and 1500/1500** invalid connections, accepted 0, **2 legitimate EMU-01 cloud deliveries in each window**, unauthorized uplink/outbox rows 0, cleanup errors 0. Sealed evidence `chapter4-results/dos-flooding/_sessions/F1-20260921-141932.json`, full explanation `test/automation/research-manual/F1-LIVE-REHEARSAL-20260921.md`. F1 recorder's Fabric settlement was disabled; do not claim independent per-window HRC ledger query. Formal Chapter 4 flood counts remain 0.

**Next Step:** Run one bounded **full live F2** malformed-message rehearsal with legitimate EMU transmission through 0/10/50 per-window loads; F2 isolated actor was already proven. Do not re-prove PRE/F1/196+ synthetic suite unless the relevant components change.

## Gateway admin access investigation — 2026-09-21 (~05:55 UTC; latest)

**Current Step:** Cloud MQTT bridge still has zero established sockets; only authorized restricted research-recorder SSH works. Cloud opsadmin password is not Gateway-01 root password. User granted broad SSH operational authority; credentials are still a separate technical requirement.

**Completed:** Rechecked live gateway LTE `wwan0=100.73.133.167/28`, registered and public broker/default routes on LTE, no :8883 sockets. Workstation full SSH inventory, Ubuntu WSL SSH identities, Windows Credential Manager and ULC-01 operator/protected key-name search yielded no alternate Gateway-01 administrator identity. Gateway SSH port is up; LuCI port 443 is up but replies `403 / x-luci-login-required`. The current research-recorder SSH identity remains forced-command diagnostic-only; attempted gateway root password login with existing opsadmin secret failed and was stopped without guessing. Other production infrastructure left unchanged. Full gateway-root DNS/TCP/mosquitto diagnosis and repair remain blocked by unavailable gateway administrator authentication. Detailed findings and recovery checks: `test/automation/research-manual/F2-PARTIAL-REHEARSAL-AND-GATEWAY-RECOVERY-20260921.md`.

**Next Step:** Obtain the actual Gateway-01 administrative root credential or an authorized admin private key/session, then inspect `nslookup smartagri-mqtt.duckdns.org`, `/etc/resolv.conf`, LTE-bound TCP :8883, `logread -e mosquitto`, cert validity and mTLS health. Fix only evidenced root cause, prove two :8883 LTE bridge sockets and a fresh EMU-01 Fabric-confirmed uplink, then run full non-counted F1/F2. Do not weaken authentication or route sensor cloud traffic over management Ethernet.

## Gateway bridge recovery boundary and F2 isolated actor — 2026-09-21 (latest)

**Current Step:** F1/F2 end-to-end live testing stays blocked because Gateway-01 has no established MQTT `:8883` uplink/downlink bridge. `wwan0`, LTE default route and local AS923 EMU-01 frame reception remain up; ULC-01's DNS resolves the public MQTT hostname, Windows can connect to `129.212.208.168:8883`, but no fresh cloud EMU uplink. Gateway Mosquitto repeatedly logs `Error creating bridge: Try again.` Exact failing gateway DNS/LTE TCP/TLS layer is not proven without admin diagnostics. Available restricted gateway SSH key cannot run those; the known cloud opsadmin password failed for Gateway-01 root. No production config, routes or mTLS changed. Do not bypass the gate.

**Completed:** Actual isolated F2 Node-RED + MQTT malformed-message path with existing restricted research fixtures: 0/0 (0/s 3s), 40/40 (10/s 4s), 200/200 (50/s 4s) messages generated/published/received/rejected, invalid accepted 0. The all-in-one subprocess hit a global timeout **after tunnel cleanup**; independent final inspection proved Node-RED research nodes absent, original flow hash restored, healthy container, isolated listener INACTIVE. F2 synthetic test `16/16 PASS`, F1 isolated real conn-flood actor also passed in previous run. Neither is a complete live flood research trial, counted=0. Evidence and admin-only recovery checklist: `test/automation/research-manual/F2-PARTIAL-REHEARSAL-AND-GATEWAY-RECOVERY-20260921.md`.

**Next Step:** Establish authorized Gateway-01 admin SSH access and verify resolver + LTE-bound TCP :8883 + bridge-specific logs/cert before targeted recovery. Confirm new EMU-01 DB uplink and Fabric-confirmed outbox, then run full non-counted F1/F2 via manual command with true 0/10/50 per-window sensor-delivery checks. Do not rerun isolated actors or full 198/198 regression without a pertinent code change.

## F1 partial live flood commissioning / gateway cloud-bridge outage — 2026-09-21 (current)

**Current Step:** End-to-end F1 is blocked by a real gateway-to-cloud MQTT outage; do not use the isolated flood test as Chapter 4 PASS.

**Completed:** The real manual `run_test.py F1` rehearsal failed closed at technical preflight: `GATEWAY_LTE=FAIL` solely because gateway MQTT :8883 bridge has no established session; LTE `wwan0` and default/public broker route remain up and registered, live PRE skipped. Gateway concentratord/forwarder continue receiving/sending local AS923 EMU frames every ~15s, but bounded cloud DB export found no new uplinks. Gateway logs show repeated `cloud-uplink`/`cloud-downlink` bridge creation errors `Try again` to `smartagri-mqtt.duckdns.org:8883`; cloud resolves its intended Reserved IP and public :8883 is reachable from workstation. Root cause within gateway LTE DNS/network/bridge is NOT independently isolated; no privileged gateway change or bypass was made. F1 synthetic code `16/16 PASS`; genuine **isolated flood-only actor** also PASS: 0/0, 40/40 (10/s for 4s), 200/200 (50/s for 4s) broker-observed/rejected, invalid accepted 0, local errors 0, tunnel/listener cleanup PASS. This does not test legitimate sensor delivery during flood windows. `test/automation/research-manual/F1-PARTIAL-REHEARSAL-20260921.md` has the exact fault boundary, evidence and recovery checks. Formal research counted=0.

**Next Step:** Restore Gateway-01's two mTLS MQTT bridges over LTE (not LAN) through an authorized admin channel, then verify fresh ChirpStack DB/Fabric flow and rerun the actual F1 non-counted 0/10/50 windows. Do not run F2/other live tests requiring cloud telemetry while this gate is failing.

## A1 live LoRaWAN + isolated MQTT commissioning — 2026-09-21 (latest)

**Current Step:** A1 LoRaWAN and MQTT real non-counted condition sets have passed. The separate Fabric authentication third and all formally counted nine-condition x10 trials remain unreleased.

**Completed:** Exact `a1_lorawan_harness.py --rehearsal` exit 0: **3/3 real LoRaWAN conditions correct**, gateway JoinRequest journal sequences 3864/3865/3866 bound to correct JoinEUI/DevEUI, wrong AppKey rejected without altering registered ChirpStack session, unregistered DevEUI rejected with registered=0, legitimate EMU OTAA allowed with new session and successful uplink; SEC parked and EMU same SHA-256 firmware restored. Evidence `chapter4-results/authentication/lorawan/A1-LORAWAN-rehearsal-20260921-131919/`. First MQTT rehearsal failed closed due stale six-field live helper vs repo seven-field observer-proof parser; preserved failed report, updated **only isolated ULC-01 helper** after backup and hash check to repo SHA-256 `cb0487fdc21f29b6aa9c002e0c1d1b98dd0ec197777ad8f454f2ffd7b79965db`. Second `a1_mqtt_harness.py --rehearsal` exit 0: **30/30** isolated MQTT decisions: 10 allowed observed, 10 wrong-password rejected/unobserved, 10 prohibited-topic rejected/unobserved, false acceptance/rejection 0, unauthorized delivery 0, isolated listener stopped and independently status INACTIVE. Evidence `chapter4-results/authentication/mqtt/A1-MQTT-rehearsal-20260921-132300/`. Updated A1 manual status wording, not status: still `CAPTURE_READY` until Fabric-side real authentication actor and synchronized methodology commissioned. Full detail `test/automation/research-manual/A1-LIVE-REHEARSAL-20260921.md`. Non-counted; offline baseline **198/198** remains.

**Next Step:** Safely commission one isolated real F1/F2 flood window with legitimate EMU delivery (prefer harness built-in bounded rehearsal), or commission A1 Fabric-side fixture when HRC actor is available. Do not re-run already proved P1/T1/T2 or 30-case MQTT without a pertinent change.

## T2 live history/chronology commissioning — 2026-09-21 (latest)

**Current Step:** The exact T2 manual operator command now has a successful non-counted five-record real-world rehearsal. Formal Chapter 4 trial count remains zero.

**Completed:** `RESEARCH_MANUAL_REHEARSAL_SECONDS=120` and `run_test.py T2` with `EXECUTE` exited 0, `TRACEABILITY_HARNESS=PASS test=T2 formal=False`. Closed 120-second window contained **8/8 confirmed uplinks/outbox rows**, no missing source events, and after-window Fabric settlement completed. Selected independent database-leader readback: **5/5 original event keys retrieved** with frame counters **169–173**, test sequences **170–174**, 13 distinct normalized measurement fields per reading, 5/5 confirmed outbox transaction IDs and SHA-256 digests, chronological-order accuracy **100%**, missing/duplicates **0/0**. Each of the five USB-powered records correctly carries `battery_v=NULL quality=invalid`; no voltage is fabricated. The five-record reconstruction took ~**4.458 s**. Evidence: `chapter4-results/traceability/T2-rehearsal-20260921-130551/` and `chapter4-results/traceability/_sessions/T2-20260921-130551.json`; explanation: `test/automation/research-manual/T2-LIVE-REHEARSAL-20260921.md`. Live PRE, LTE, clock and recorder health passed. No counted trials.

**Next Step:** Traceability T1/T2 capture/retrieval code is live-rehearsed, but formal release still needs independently observed HRC ledger query results (current scorer verifies confirmed DB outbox+TxID) and full formal sampling. Choose the next isolated, non-counted intervention test (A1 LoRaWAN/MQTT, F1/F2 or R2), inspect its exact restricted-action readiness and perform one bounded genuine trial. Avoid repeating P1/T1/T2 without code or infrastructure change.

## T1 live traceability commissioning — 2026-09-21 (latest)

**Current Step:** One full non-counted T1 capture and independent per-record DB retrieval has passed. Do not count any of these as Chapter 4 repetitions.

**Completed:** The existing sealed P1 run initially exposed a real T1 scorer failure: USB-powered EMU-01 stores `battery_v=NULL`, `quality=invalid`, `source_field=battery_v` rather than a fabricated 0 V reading. Corrected the scorer to preserve exactly this known-unavailable field as `value:null` while rejecting unrelated missing measurements; added 2 targeted regressions (11/11 T1/T2 unit tests). Replayed 2/2 genuine P1 records against fresh independent DB leader readbacks and outbox-confirmed Fabric TxIDs: PASS. Then executed **the exact manual T1 operator command** with `RESEARCH_MANUAL_REHEARSAL_SECONDS=55`: exit 0; `TRACEABILITY_HARNESS=PASS formal=False`; closed-window 3/3 source events and outbox transactions confirmed; 2/2 independently re-retrieved selected records, each 13 fields (12 available values and explicitly invalid/unavailable battery), source ID, timestamp, frame counter, digest, and TxID present; no missing/duplicate selected records. SHA-256 sealed run `chapter4-results/traceability/T1-rehearsal-20260921-125602/`; separate scorer JSON `chapter4-results/traceability/_sessions/T1-20260921-125602.json`. No independent HRC ledger query by this scorer (it verifies confirmed database outbox with TxID); do not promote formal T1 to READY on that basis. Latest consolidated code-only suite **198/198 PASS across 16 suites**, `chapter4-results/code-qualification/offline-code-20260921T050059692509Z/code-only-summary.json`. Full scope and field-availability explanation: `test/automation/research-manual/T1-LIVE-REHEARSAL-20260921.md`.

**Next Step:** Commission T2 non-counted five-reading chronology with its own fresh run, then resolve independent HRC ledger query evidence before releasing formal traceability operator blocks. Check live evidence schema v2 versus frozen I2 v1 helper when I2 is commissioned.

## Rapid hardware-connected readiness sweep — 2026-09-21 (current)

**Current Step:** The PRE + bounded P1 operator path and all available synthetic operator commands have passed; formal research runs remain uncounted. No other live experiments were initiated by this sweep.

**Completed:** First P1 launch correctly failed closed because `oversight_status.py` checked the obsolete source substring `query < status < retry`, whereas the strengthened R2 harness checks `query < verify < status < retry` (Query → VerifyDigest → CommitStatus → same-prepared-transaction retry). Corrected only that stale audit token; `OVERSIGHT_AUDIT=PASS`, `TECHNICAL_GATE=PASS`, `LIVE_PRE=PASS`, and `GATEWAY_LTE=PASS`. Executed **the exact P1 manual entry point** with `RESEARCH_MANUAL_REHEARSAL_SECONDS=65` and `EXECUTE`, using a non-counted smoke run. It exited 0 and reported `P1_MEASUREMENT_BOUNDARY=PASS`: **4 source attempts; 4 ChirpStack-accepted; 4 database uplinks; 4/4 Fabric-confirmed with transaction IDs**. The after-window Fabric settlement reached `CONFIRMED` (4/4), collector health checks passed, clock-calibration drift was 0.001193 s (< 0.100 s limit), and the recorder marker was removed. Saved run `chapter4-results/smoke/manual-P1-rehearsal-20260921-124351/` contains `derived/run-summary.json`, `metadata/fabric-settle.json`, source/measurement/outbox CSVs and SHA256SUMS. `RECORDED_UNCLASSIFIED` is the normal non-counted run status, not a formal PASS classification. Executed **13/13** available `run_test.py <ID> --synthetic` commands successfully (A1 A2 P2 R1 R2 S1 F1 F2 I1 I2 I3 T1 T2). PRE, P1 and S2 correctly report `SYNTHETIC=UNAVAILABLE`, not a fake PASS. Prior full code regression is **196/196 PASS**, and only the oversight guard changed in this sweep.

**Next Step:** The hardware and real P1 measurement/observation pipeline are usable. For each other formal test, commission its own attack/outage/Fabric actor and real evidence path before promoting it to READY; avoid equating synthetic code PASS with live experiment PASS. S2 remains `METHODOLOGY_REQUIRED`. No counted Chapter 4 repetitions have been started.

## Live hardware reconnection — 2026-09-21 (current)

**Current Step:** Real full-stack smoke is verified, not a counted Chapter 4 experiment. The prior hardware-disconnected instructions below are historical. See `test/automation/research-manual/REAL-HARDWARE-RECONNECT-20260921.md` for precise evidence and source paths.

**Completed:** Workstation Ethernet `192.168.20.30/24` to Gateway-01 `192.168.20.11`; EMU-01 COM11, SEC-01 COM16. Real recorder `preflight --require-emu --require-sec` exited 0: ULC-01/02/03 and gateway reachable, one database leader/two replicas, cloud evidence services ready, calibrated CLOCK_GATE PASS. Gateway LTE `wwan0=100.73.133.167/28` retained the default/cloud MQTT route; management LAN separate. Corrected RUI3 query-echo bug in A1 LoRaWAN harness and added regression (targeted 16/16 PASS); one controlled unregistered SEC join produced fresh 923.2 MHz SF10 gateway frames and SEC was re-parked. EMU-01 was restored with its SHA-256-verified 15-second research firmware via successful COM12 DFU. Retained serial showed OTAA JOIN PASS and three successful source sends at 15007/15006 ms intervals, valid=0x7F. Initial canary summary remains FAIL because boot-only banner was missed; corrected canary accepts the archived verified DFU plus measured cadence as alternative profile proof, without rewriting the old report. Real DB readbacks: five new EMU uplinks and 65 measurements (13 each); subsequently gateway packetflow showed fifteen EMU records, nine evidence-verified and Fabric-confirmed with transaction IDs, six newer records pending asynchronous settlement at observation time. `evidence_gap=0`, `integrity_failure=0`. Representative Fabric TxID `042c46dbcbf88f79ae85e60c7acfa78423a4573a09e29b37b0575b7eceff69bd`. No synthetic or real rehearsal records were counted as formal research samples.

**Next Step:** Once ready to execute a research operator test, run a bounded non-counted P1 recorder rehearsal and inspect its closed-window source/database/Fabric reconciliation. Do not promote uncommissioned A1/F1/F2/R1/R2/T1/T2/I1/I2/I3 tests to READY based on this one smoke. S2 still needs methodology. The 15-second EMU research firmware remains installed; avoid leaving unnecessary continuous sample traffic when hardware is idle. The complete offline suite was rerun after the live-derived A1 parser fix: **196/196 PASS across 16 suites**, non-counted report `chapter4-results/code-qualification/offline-code-20260921T043222317342Z/code-only-summary.json`.


## Streamlined synthetic operator-command rehearsal — 2026-09-21

**Current Step:** Keep the gateway/sensors disconnected and verify real operator command dispatch with synthetic fixtures, not counted measurements. `run_test.py <ID> --synthetic` now uses `offline_test.py` before any live preflight, while ordinary `run_test.py <ID>` retains its existing guarded/manual execution path.

**Completed:** All **13/13** mapped test IDs (`A1 A2 P2 R1 R2 S1 F1 F2 I1 I2 I3 T1 T2`) passed their exact operator `--synthetic` command. `PRE P1 S2` correctly returned `SYNTHETIC=UNAVAILABLE` (nonzero), not fake PASS. Ordinary `run_test.py I3` still reports `HARNESS_REQUIRED` and does not start counted work. Static Python compile and diff checks passed. See `test/automation/research-manual/SYNTHETIC-COMMAND-REHEARSAL.md`. The preceding full consolidated suite remains **195/195 PASS** across 16 suites; the dispatch mapping adds no new counted trials.

**Next Step:** Once physical hardware returns, run real PRE and one genuine sensor-to-Fabric smoke flow. Then commission unready experiments against their actual production paths one by one; do not mark synthetic samples as live. S2 requires a methodology definition before a valid experiment can exist.


## Latest checkpoint — 2026-09-21 hardware-offline test-code batch

**Current Step:** Stop all tests requiring Gateway-01 or powered sensors. Qualify existing research test code one harness at a time with deterministic, non-counted fixtures. Earlier live infrastructure notes below are historical, not a claim about currently disconnected hardware.

**Completed:** One-command offline qualification now passes **196/196 tests** across research contract, A1 MQTT, A1 LoRaWAN, A2 Fabric endorsement-evidence scoring, I1 experimental application-integrity gate/scorer, I2 read-only production-v1 source recomputation/evidence scorer, I3 source-bound ledger duplicate/overwrite evidence scorer, Fabric synchronization, P2 pair runner, R1 LTE route gate, R2 reconciliation, F1/F2 flooding validation, T1/T2 traceability, S1 replay helper, and mock MQTT wire. The exact machine-readable output is `chapter4-results/code-qualification/offline-code-20260921T043222317342Z/code-only-summary.json`; details and one command to rerun are in `test/automation/OFFLINE-CODE-QUALIFICATION.md`. New guards prevent stale JoinRequests, wrong JoinEUI matches, duplicated outage event keys, arbitrary P2 resume PASS summaries, incomplete 13-metric readings, and chronology-score false positives. No gateway/sensor, production MQTT, or live Fabric mutation was invoked in this batch.

**A1-specific outcome:** `py -3 test/automation/offline_test.py A1` returned `CODE_ONLY_PASS` for 30/30 non-counted checks (contract 6, MQTT 6, LoRaWAN packet/state 15, LoRaWAN mocked workflow 3). The LoRaWAN guards now reject stale or wrong-JoinEUI packets, missing/changed server evidence and valid-join claims without verified new session; mocked cleanup failure forces FAIL. `join_observation_ms` measures the local join-observation interval; it is not a server processing-time measurement. The newly edited helpers have not been live-commissioned.

**P2-specific outcome:** `py -3 test/automation/offline_test.py P2` returned `CODE_ONLY_PASS` for 25/25 checks (research contract 6, Fabric sync 2, P2 pair-runner 17). It now verifies payload digest, frozen rate/interval, formal status, queue/latency/achieved TPS, commit counts and drain timestamps. Go benchmark source uses the frozen session duration instead of `planned/rate`; Go build limitation resolved later in the I2 batch: project-local Go 1.25.0 compiled `./cmd/research-fabric-benchmark` successfully. P2 live benchmarking remains uncommissioned. The user has no gateway/sensor connection; none was required or attempted.

**R1-specific outcome:** `py -3 test/automation/offline_test.py R1` returned `CODE_ONLY_PASS` for 20/20 checks (research contract 6, R1 route/outage parser 14). The parser now binds cloud-route source to the LTE IPv4 and destination to an established MQTT peer; malformed snapshot errors produce retained SHA-256-sealed FAIL evidence. This does NOT exercise gateway outage induction, restoration, LTE route mutation or real connectivity.

**A2-specific outcome:** `py -3 test/automation/offline_test.py A2` passed 24/24 hardware-free checks (research contract 6, A2 evidence scorer 18). The Fabric-team handoff and exact pre/post-query evidence contract are in `test/automation/authentication/A2-OFFLINE-EVIDENCE-CONTRACT.md`. No live endorsement-policy fixture, Fabric transaction or counted A2 sample was created. A2 remains HARNESS_REQUIRED in the operator manual.

**I1-specific outcome:** `py -3 test/automation/offline_test.py I1` passed 24/24 Python-level checks (contract 6 + I1 scorer 18), including 13/13 direct Node.js VM checks against the exact Node-RED Function-node body. File locations, wiring and evidence requirements are in `test/automation/integrity/I1-OFFLINE-QUALIFICATION.md`. The function has not been installed in Node-RED and no actual database/Fabric path was tested; I1 stays HARNESS_REQUIRED for live counted trials.

**I2-specific outcome:** `py -3 test/automation/offline_test.py I2` returned `CODE_ONLY_PASS` 25/25 (contract 6 + I2 scorer 19). Project-local Go 1.25.0 was installed; the new read-only production-reuse I2 Go helper passed 5/5 direct Go tests and the exact Python-to-Go baseline/tamper/restore cross-language check passed 3/3 phases. The previously uncompiled P2 Go command also compiled successfully. `test/automation/integrity/I2-OFFLINE-QUALIFICATION.md` preserves command paths and live limitations. No database row, Fabric anchor or sensor was altered.

**I3-specific outcome:** `py -3 test/automation/offline_test.py I3` returned `CODE_ONLY_PASS` 39/39 (contract 6 + I3 exact-payload ledger evidence scorer 33). The full synthetic ten baseline + ten same-exact-payload retry + ten conflicting-payload structure passed; negative cases preserve security FAIL when original world state changes, and mark absent independent query/incorrect attack INVALID. `test/automation/integrity/I3-OFFLINE-QUALIFICATION.md` documents the Fabric team's pre/post-query, identity/anchor, digest, and record-count handoff. Live I3 remains `HARNESS_REQUIRED`; no ledger transaction was submitted and no synthetic Chapter 4 samples were counted.

**Next Step:** Audit remaining unqualified operator/manual command surfaces one test at a time; keep published manual statuses unchanged until the full real-world action is commissioned. S2 remains `METHODOLOGY_REQUIRED`, not solved with synthetic records.

## Current checkpoint — 2026-09-21, A1 MQTT code qualification

**Current Step:** A1 MQTT is the only test under review in this batch. The September 18 isolated broker rehearsal is retained as historical PASS evidence, but the newly hardened code has NOT yet been live-commissioned; do not promote the entire 90-attempt A1 experiment to READY.

**Completed:** Verified `chapter4-results/authentication/mqtt/A1-MQTT-rehearsal-20260918-154556/a1-mqtt-summary.json` contains 10 allowed, 10 wrong-password and 10 prohibited-topic trials, zero incorrect decisions, fixture smoke PASS and cleanup PASS. On September 21, ULC-01 answered `research-actions-v2|ulc-01` and the isolated authentication listener reported INACTIVE. TCP/22 and later SSH worked after transient handshake timeouts. The administrator SSH key was not usable in noninteractive BatchMode, so the modified server helper and restricted wrapper have not been deployed.

**Code corrections in this batch:** The trial protocol now emits an explicit observer-delivery field; unauthorized topic delivery is derived from actual observer evidence rather than hard-coded false. Wrong-password trials have their own observer; publication response time ends before the negative observation timeout. The harness validates expected decisions by condition, count and unique trial IDs, latency, observer proof and verified listener post-stop status. Partial-start failures trigger teardown. The server helper refuses to erase runtime material when the isolated service remains active. The repository wrapper/sudoers no longer allow retrieving generated A1 credentials over the restricted research key. Six targeted parser/contract unit tests passed, and both edited shell scripts passed the final `sh -n` check under Ubuntu WSL.

**Next Step:** Use authorized administrator SSH signing to deploy the updated `mqtt_test_listener.sh`, `server-actions-ssh.sh` and `lorawan-research-actions.sudoers` to ULC-01; validate sudoers and restart only the isolated A1 fixture if needed. Rehearse the exact revised 30-trial MQTT code, verify 10/10 per condition and observed unauthorized delivery 0, check no isolated service/socket or secrets remain, and compare production Mosquitto pre/post fingerprints. Then update this checkpoint and only the MQTT-subtest qualification status. A1 LoRaWAN and Fabric identity tests remain separate.

## Current verified state — 2026-09-18 infrastructure audit

This section supersedes the older P1/OTAA/Fabric blocker notes below. Historical notes remain context, not current readiness.

### Current Step
A1 authentication commissioning is in progress. The isolated MQTT third is live-qualified; LoRaWAN is next, followed by the external Fabric identity third.

### Completed
- Live readiness at 2026-09-18T03:25:01Z: tooling, counted firmware archive, gateway LTE, clocks, recorder access and full-stack PRE passed.
- ULC-01 is the database leader; ULC-02 and ULC-03 are replicas. All three servers and Gateway-01 were reachable. Collector/verifier readiness endpoints returned HTTP 200; preflight recorded zero evidence_gap and integrity_failure.
- Fresh run: chapter4-results/smoke/manual-P1-rehearsal-20260918-112426. Its exact cloud-UTC measurement window was 03:24:09.233Z–03:25:09.233Z.
- P1 wrapper exited 0: 4 scheduled source attempts, 4 unique ChirpStack accepts (100% PDR in this small rehearsal), 4 calibrated sensor-to-database samples, and 4/4 Fabric confirmations with transaction IDs.
- Observed uplink frequencies: 923.2 and 923.4 MHz. This is observed traffic, not a complete regional-configuration audit.
- Fabric settlement completed in 215.695 seconds within the 420-second allowance, after the measurement window closed. Do not shorten the observation window or count settlement traffic as new source attempts.
- All 62 evidence-manifest entries verified. Summary regeneration twice in a temporary copy reproduced every JSON field except relocated run_dir and byte-identical CSV. Original evidence remained sealed.
- The verifier rejected an intentionally modified CSV in a temporary fixture. Recorder state and ownership lock were clean after completion.
- Fixed ensure_ready.py so --skip-live-pre reports technical_gate=SKIPPED on successful tooling-only checks, rather than implying live PASS. Four targeted cases passed on the host: live success, live failure, tooling-only success and tooling failure.
- Added research-recorder/verify-run-reproducibility.py. Instructions are in this directory's README.md; machine-readable evidence is REPRODUCIBILITY-20260918.json.
- A1 MQTT commissioning passed on ULC-01 using the restricted `research-actions-v2` fixture. Rehearsal `chapter4-results/authentication/mqtt/A1-MQTT-rehearsal-20260918-154556` recorded exactly 30 trials: 10 allowed, 10 wrong-password, and 10 prohibited-topic decisions. All 30 matched expectation, false acceptance count was zero, smoke and cleanup passed, and the temporary listener was confirmed inactive afterward.
- Production Mosquitto isolation was verified with byte-identical pre/post process/config/listener fingerprints (SHA-256 `ad2833f211f9e7db674c54df45b4b42dd25d6212987ddf60897a7357f579a4a3`); port 1884 was absent after teardown. This commissions only the MQTT third of A1, not the whole A1 experiment.

### Next Step
Proceed with formal P1 repetitions or commission the remaining test harnesses individually. Only PRE and P1 are released READY commands. No counted 30-minute P1 repetition was performed by this audit. S2 still requires a specified methodology; other unreleased test IDs retain their current harness/capture restrictions.

### Operational notes
Use a persistent managed process for the interactive P1 command so capture and finalization survive individual MCP request timeouts. The 60-second rehearsal is selected explicitly with RESEARCH_MANUAL_REHEARSAL_SECONDS=60 and is non-counted. Allow the process to finish; a silent interval can include preflight, warm-up, settlement and evidence export.

During this audit, lorawan-setup-scoped MCP calls stalled while commands through the same jervis-hijo host's authorized rel-ai-mcp workspace returned successfully using the absolute LoRaWAN project path. A transport timeout alone did not establish an infrastructure outage. Check existing process state and saved results before retrying an experiment.

The workstation was approximately 91 seconds ahead of cloud UTC. The recorder independently calibrated the source clock at both boundaries; the measured drift was about 1.24 ms. This is calibrated measurement support, not a claim that the workstation clock is synchronized.

Reproducibility here means deterministic processing of these recorded inputs with the recorded Python version and summarizer hash. It does not prove fresh-machine deployment, repeatable RF outcomes, full HA failover, or readiness of every Chapter 3 experiment.

This file is the handoff point for continuing the Chapter 3 research-test manual work in a new chat.

## Current rule

- `chapters/Zacarias_Chapter3.pdf` controls the required experiments, counts, durations, workloads, measurements, formulas, and stated acceptance/security criteria.
- Verified live infrastructure controls how those experiments are executed.
- Stale architecture/topology prose from Chapter 3 is not implementation authority.
- The operator manual must stay simple.
- A test code block is included in the operator manual only when the complete action is currently runnable through the commissioned harness.
- Syntax-only checks, guard-only commands, intentional `BLOCKED` snippets, and missing-fixture placeholders do not qualify as working operator blocks.
- Tests that are still incomplete remain documented with their full Chapter 3 measurement requirements, but no operator code block is published until the harness passes.

## Verified platform state before this manual audit

On 2026-09-16 the live technical readiness gate passed with the counted EMU-01 profile, Gateway-01 LTE production path, ULC cloud stack, database leader check, evidence services, clock gate, and restricted recorder access healthy. EMU-01 was present on COM11 and the security node on COM16. The recorder reported zero `evidence_gap` and zero `integrity_failure` statuses during the fresh preflight.

## Chapter 3 coverage audit completed

The manual covers P1, P2, R1, R2, A1, A2, S1, S2, F1, F2, I1, I2, I3, T1, and T2. Important methodology notes retained:

- P2 requires four Fabric workloads (1 tx/15 s, 1 TPS, 5 TPS, 10 TPS), 5 minutes each, three repetitions. Chapter 3 requires a with-vs-without-Fabric comparison but does not prescribe the no-Fabric comparison count. Any chosen comparison design must be frozen before counted execution.
- S2 application-layer duplicate/replay is listed in Chapter 3 but lacks a standalone count, timing, injection boundary, metric formula, and pass rule. It remains methodology-blocked and must not be invented or substituted with I3.
- Resource measurements follow the current participating machines while preserving the Chapter 3 CPU/memory/bandwidth metrics.

## Operator-block audit in progress

The previous validation logic reported `PASS` even for tests whose status was `HARNESS_REQUIRED`, `CAPTURE_READY`, or `METHODOLOGY_REQUIRED`. That is being corrected. The new publication rule is stricter: only complete `READY` tests may expose a code block in the final manual.

Current formal readiness before this cleanup:

- PRE: READY
- P1: READY
- P2: HARNESS_REQUIRED
- R1: CAPTURE_READY
- R2: HARNESS_REQUIRED
- A1: CAPTURE_READY
- A2: HARNESS_REQUIRED
- S1: CAPTURE_READY
- S2: METHODOLOGY_REQUIRED
- F1: CAPTURE_READY
- F2: CAPTURE_READY
- I1: HARNESS_REQUIRED
- I2: HARNESS_REQUIRED
- I3: HARNESS_REQUIRED
- T1: CAPTURE_READY
- T2: CAPTURE_READY

## Current step

1. Change readiness validation so non-ready experiments are never shown as code-block PASS.
2. Rehearse the released PRE/P1 entry points against the live environment.
3. Replace the long manual with a simple measurement-first format.
4. Keep code blocks only for released READY tests.
5. Regenerate and render-check the PDF.

## Next engineering work after this cleanup

Finish and commission missing one-block harnesses one experiment at a time. When a harness becomes complete, run its non-destructive interface checks plus a safe rehearsal/canary, update readiness to READY, then add exactly one simple operator block to the manual. Do not publish a block first and hope the fixture works later.

## 2026-09-16 operator-block verification update

- The manual was reduced to a simple measurement-first format. Non-ready tests retain their Chapter 3 design and measurements but have no placeholder operator commands.
- `ensure_ready.py` now validates only operator blocks actually released in the manual instead of reporting guard-only non-ready tests as code-block PASS.
- The exact PRE manual command was executed live and passed: technical gate, tooling compile, MQTT self-test, counted firmware archive, recorder state, Gateway-01 LTE invariant, and live full-stack PRE were all PASS.
- The first 15-second P1 rehearsal proved recorder lifecycle/finalization and produced sealed evidence, but it contained zero EMU-01 `SENSOR_TX` attempts. Formal PDR was correctly `WITHHELD_NO_SENSOR_TRANSMISSION_ATTEMPTS`; therefore that rehearsal does not prove P1 measurement readiness.
- An ad-hoc 60-second serial audit temporarily created its own COM11 lock because its launcher left a child `serial_capture.py` process alive after the parent was killed. Both audit processes were terminated. This was an audit-side process-lifecycle artifact, not accepted as a production recorder defect.
- `run_test.py` has now been hardened so a P1 rehearsal/formal run cannot return success merely because capture stopped cleanly: it must have source attempts and `MEASURED_CHIRPSTACK_ACCEPTANCE_BOUNDARY`. A formal 30-minute P1 additionally requires at least 100 source attempts before it can return success.
- A clean 60-second P1 rehearsal is now the publication gate. If it does not produce real EMU-01 source attempts plus measurable ChirpStack PDR, P1 must be removed from the released manual blocks until the sensor path is repaired.

## Final code-block publication result for this audit

- PRE remains released. Its exact manual command was executed live and passed the full technical gate, including Gateway-01 LTE and live PRE.
- P1 is no longer released. A clean 60-second rehearsal (`manual-P1-rehearsal-20260916-160437`) ran through the real recorder/finalization path with healthy supervisor checks, but EMU-01 produced 0 `SENSOR_TX` attempts and Gateway-01 concentratord reported `rx_received: 0` / `rx_received_ok: 0`. The hardened P1 entry point therefore exited nonzero with `P1 measurement boundary invalid: source attempts=0, need >= 1`.
- `run_test.py` now fails P1 when required source/PDR evidence is missing; a formal P1 would also require at least 100 source attempts before returning success.
- Because the user requires every manual code block to be working, the P1 code block was removed from the manual and P1 status changed to `CAPTURE_READY; live sensor transmission boundary not proven`.
- The final manual now contains exactly one operator code block: PRE. All other tests remain fully documented for measurements/design but have no command until their complete harness and required observation boundary pass.

Next technical task if continuing beyond manual cleanup: diagnose the current EMU-01 OTAA/RF state, restore real 15-second `SENSOR_TX` + gateway reception, rerun a clean P1 rehearsal, and only then re-release P1.

## Final manual state after regeneration

- Full live `ensure_ready.py` completed PASS at `2026-09-16T08:09:56Z`: technical gate, tooling compile, MQTT self-test, counted firmware archive, recorder state, Gateway-01 LTE invariant, and live PRE all PASS.
- Published operator blocks: PRE only. `CURRENT-READINESS.md` lists PRE = READY / PASS and no other released block.
- Final Markdown audit: exactly 1 PowerShell code block (2 fence lines), PRE command count = 1, P1 command count = 0, P1 withheld-status marker present.
- Simplified PDF regenerated from the final Markdown. SHA-256: `404281D2641EBE4E86470582653A11F32C1130ECEAA6184AD75B1D4D798D0F3F`; size 258,966 bytes.
- Browser layout inspection of the rendered manual confirmed a readable simple layout, intact status table, PRE command visible, and P1 marked not released.

Resume rule: never add a test command to the manual merely because its interface or guard validates. Add it only after the complete test action and required observation boundary pass a real rehearsal/canary. The next unreleased candidate is P1, but first repair/prove EMU-01 OTAA/15-second RF traffic.

## 2026-09-16 per-test code-block audit
- Exact published PRE block executed live and PASS.
- All 16 test IDs passed their safe wrapper/interface validation path.
- Manual still contains exactly one released PowerShell block: PRE.
- P1 remains withheld because live measurement boundary is not proven.
- Detailed audit: test/automation/research-manual/CODE-BLOCK-AUDIT-20260916.md

## 2026-09-16 commissioning continuation
- A durable commissioning task was opened to make every Chapter 3 test a complete fail-closed one-command action before publication.
- EMU-01 COM11 was initially blocked by orphaned `serial_capture.py` child processes left after stopping a diagnostic parent process. Both child processes were terminated and an exclusive COM11 open then passed. This process-tree cleanup gap must be hardened in the recorder tooling.
- The workstation Arduino/RAK toolchain is installed even though `arduino-cli` is not on PATH. Verified CLI: Arduino CLI 1.5.1; installed RAKwireless nRF52 core 1.3.3; FQBN `rakwireless:nrf52:WisCoreRAK4631Board`.
- The archived counted EMU-01 15-second image was hash-verified against its build record before upload. The image itself was not rebuilt or altered.
- The first Arduino upload attempt failed because the orphan serial process still owned COM11. A later PowerShell wrapper incorrectly treated normal DFU stderr as a terminating PowerShell error and left the node in bootloader mode on COM12. Direct invocation of the RAK/Adafruit DFU executable then completed successfully with exit code 0 and `Device programmed`.
- A bounded 75-second post-flash serial proof on the application port then returned `EMU01_OTAA_JOIN=FAIL`, `SENSOR_TX_COUNT=0`. This proves the counted firmware boots and executes but the LoRaWAN join currently fails. The active P1 blocker is therefore the OTAA/RF/network-server join boundary, not firmware programming, USB enumeration, recorder startup, or LTE backhaul.
- Gateway-01 production backhaul remained healthy during this work: LTE `wwan0` is up and registered, default route metric 10 is active, the cloud route uses `wwan0`, and MQTT mTLS to port 8883 is established.
- Historical verified configuration names EMU-01 DevEUI `ac1f09fffe296d29` and JoinEUI `0000000000000000`; the current protected AppKey must be compared to the live ChirpStack root key without writing either secret into repository documentation or chat output.
- Next P1 action: compare protected EMU-01 DevEUI/JoinEUI/AppKey and AS923 settings against the live ChirpStack device/profile/root-key state and inspect the latest gateway/ChirpStack join evidence. Fix the first mismatched side, then require OTAA PASS + at least two 15-second `SENSOR_TX` records + gateway/ChirpStack reception before rerunning the full P1 recorder rehearsal.

## 2026-09-17 P1 live recovery and Fabric blocker
- EMU-01 is now joined and transmitting the counted profile correctly. Bounded COM11 capture observed consecutive 15-second `SENSOR_TX` records with `join=1` and `send_status=0`.
- Gateway-01 simultaneously receives the matching AS923 RF cadence. After joining, ADR converged toward SF7 while LTE `wwan0` remained the production cloud path and MQTT mTLS stayed established.
- `run_test.py` gained an explicit non-counted P1 commissioning mode: setting `RESEARCH_MANUAL_REHEARSAL_SECONDS` intentionally permits an unreleased P1 rehearsal in the `smoke` group without weakening the normal guard or marking P1 READY.
- Rehearsal `manual-P1-rehearsal-20260917-083631` is invalid for publication because the outer command timeout killed the wrapper before orderly stop. The source window contained four valid attempts but remote evidence continued until recovery, producing a mismatched observation window. Recorder recovery subsequently cleared all children and the active marker. Treat this run as diagnostic only.
- Clean rehearsal `manual-P1-rehearsal-20260917-084445` completed normally with recorder CLEAN. It measured 4 source attempts, 4 ChirpStack accepts, formal PDR 100%, exact payload/FCnt correlation, populated gateway/server resource samples, and complete telemetry measurements. The P1 radio/application/measurement boundary is therefore proven.
- P1 is still NOT released because the Fabric portion of the Chapter 3 contract failed live. All four rehearsal outbox rows remained `pending` with no Fabric TxID/commit/block data after the run. A later read-only query still showed those same rows pending; global evidence status was `pending=15`, `verified=103`, `evidence_gap=0`, `integrity_failure=0`, and `LATEST_VERIFIED_AT=2026-09-17 00:45:45.470188+00`, before the first P1 event.
- Both Fabric-adapter containers report Up, but run-window adapter logs are empty and the queue is not advancing. Container-up state is therefore insufficient; the active blocker is the Fabric adapter worker/claim/credential/lease path.
- Do not promote P1 or publish its manual command until the Fabric queue resumes, the exact P1 events reach a measurable terminal Fabric state, and a new clean P1 rehearsal proves Fabric transaction success in addition to PDR/resources.
- Next action: diagnose adapter worker state, OpenBao/AppRole rotation, lease/claim state, and Fabric Gateway reachability using existing authorized control paths; repair minimally; verify `pending` decreases and `verified` advances; then harden the P1 publication validator to require Fabric completion before rerunning the clean rehearsal.

## 2026-09-17 Fabric outbox eligibility diagnosis
- Live ULC-01 monitoring proves the Fabric adapter is enabled and HTTP-ready, not dead: adapter readiness returned HTTP 200 while the database contained 292 outbox rows (`confirmed=69`, `pending=222`, `processing=1`). Collector readiness was also HTTP 200.
- A 24-hour EMU-01 outbox export found 195 telemetry-attestation-v2 rows. Every one was still `pending`, every one had `attempts=0`, and every `last_error_category` was empty. New rows continued arriving on the expected ~15-second cadence. This proves the adapter is not reaching Fabric and being rejected; these rows are not being claimed at all.
- A matching recent gateway packet-flow export found 199 EMU-01 rows: 185 already had evidence status `verified`, 14 were still `pending` with reason `journal_source_missing`, and all 199 outbox rows were `pending`. Therefore evidence verification lag explains only the newest minority and cannot explain the main Fabric backlog.
- The current adapter claim predicate was inspected in `evidence-services/cloud/internal/fabricadapter/repository.go`. A normal row is claimable only when status is pending/failed and `next_attempt_at <= now()`, `finalized_payload IS NOT NULL`, and (for `telemetry-attestation-v2`) a matching `gateway_evidence.event_verification` row is `verified`. Since 185 recent EMU rows are verified but remain attempts=0, the immediate fault boundary is a remaining eligibility condition, most likely missing `finalized_payload` or scheduling state, not OpenBao/Fabric transaction rejection.
- Do not chase Fabric Gateway or OpenBao errors until the unclaimed-row eligibility failure is proven. Next action: trace the production outbox insert/finalization path, prove which claim prerequisite is absent on live EMU rows, repair that upstream durable write/state transition, drain the backlog, then rerun P1 only after new rows are claimed and committed.

