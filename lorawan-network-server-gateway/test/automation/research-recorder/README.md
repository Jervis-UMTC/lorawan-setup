# Automated Research Recorder

This is the preferred evidence-capture path for counted dissertation tests on the **commissioned** Gateway-01 + LTE + three-node cloud system.

## Evidence authority

**The testing evidence is authoritative for observed results.** The current methodology authority for what must be tested and measured is [`../../ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md`](../../ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md), derived from the new `chapters/Zacarias_Chapter3.pdf`. Use it for research questions, experimental conditions, counts, durations, measurements, analysis rules, and stated acceptance/security criteria. Do not treat architecture, topology, technology placement, host roles, status statements, or expected outcomes in that PDF—or older dissertation drafts—as current infrastructure truth.

Use this order when sources disagree:

1. sealed evidence captured for the specific formal trial under `chapter4-results/` is the authority for that trial and its research classification;
2. fresh read-only live observations are the authority for current operational state at the time they were observed;
3. current deployment/configuration material is the reproducibility reference;
4. chapter PDFs, old DOCX files and historical prose are requirements/provenance context only.

A healthy live service does **not** prove that a research trial passed. The recorder deliberately captures evidence first and leaves classification to the evidence from that trial. The implementation must follow the live commissioned system rather than recreating obsolete architecture described in older drafts.

## What is automated

One recorder run automatically retains:

- EMU-01 USB serial with host UTC timestamps and automatic COM-port re-enumeration recovery;
- optional SEC USB serial capture;
- Gateway-01 live `logread` stream;
- Gateway-01 CPU, memory, load and network counters;
- Gateway-01 LTE/QMI, route and production MQTT-socket snapshots;
- host CPU, memory, load and network counters on `ulc-01`, `ulc-02`, `ulc-03`;
- per-container CPU/memory series on all three cloud nodes;
- exact-window ChirpStack, Node-RED, Mosquitto and kernel logs;
- authoritative `telemetry.uplinks`, `telemetry.measurements`, and `telemetry.fabric_outbox` CSV exports from the current Patroni leader;
- RSSI, SNR, gateway frequency, gateway uplink ID, FCnt and `test_sequence` statistics;
- byte-exact EMU-01 source-to-database **delivery correlation** whose source timestamps can be clock-aligned into the authoritative DB export window; this is not the formal Chapter 3 PDR;
- formal Chapter 3 PDR is reported only when the numerator can be derived as unique legitimate uplinks accepted by ChirpStack over the same eligible source-attempt window;
- application-event-to-database timing (`received_at - time`) plus independently calibrated **sensor-transmission-to-database-storage latency** from matched `SENSOR_TX` source timestamps when recorder-v9 start/end clock calibration passes;
- a read-only aggregate verifier/checkpoint snapshot at run start and run end (`metadata/evidence-status-start.txt` and `metadata/evidence-status-end.txt`);
- SHA-256 for every completed evidence file.

Raw files are made read-only after finalization. Calculated files live under `derived/`; never edit raw evidence to improve a result.

## Live testing monitor

`research_cockpit.py` provides the read-only testing monitor at `http://127.0.0.1:8765/`. It is an observation aid for running experiments, not a second result engine.

The cockpit combines the existing live sensor/resource view with `testing_monitor.py`. Each cloud node uses one locked-down SSH `monitor-stream` session so monitoring does not create a burst of competing SSH probes during a trial. Resource records remain approximately one-second observations; slower service/database/evidence observations are multiplexed through the same session. The server wrapper discovers the live Docker/service set instead of relying on chapter-era service lists.

The monitor shows:

- current CPU utilization as percent of 100%, RAM used/total, and network receive/send rates in Mbps with explicit capacity context where a defensible capacity is known;
- received sensor packets by sender, DevEUI, gateway, AS923 radio frequency, RSSI in dBm, SNR in dB, FCnt/test sequence and decoded sensor values;
- packet-level RF-to-application correlation from Gateway-01 reception through gateway MQTT evidence, ChirpStack/application acceptance, TimescaleDB, evidence verification, Fabric outbox and Fabric transaction fields when present;
- duplicate/replay indicators that distinguish an exact PHYPayload received again under a new gateway uplink ID from ordinary MQTT redelivery, plus FCnt/test-sequence repeats, gaps and regressions;
- discovered containers and selected system services with node, role/state and live detail;
- current Patroni leader/replica observations;
- evidence collector/verifier and Fabric adapter readiness, including the deliberately fenced Fabric standby when observed;
- leader-only database counters for LoRaWAN uplinks, decoded measurements, gateway MQTT evidence, evidence segments, checkpoints, verifications and Fabric outbox rows;
- recent warning/error observations and the formal test inventory from `chapter4-results/`.

Operational observation history is stored locally in `%LOCALAPPDATA%\LoRaWAN\testing-monitor.sqlite3` using SQLite/WAL. Packet observations are stored separately in `%LOCALAPPDATA%\LoRaWAN\packet-monitor.sqlite3`. Service snapshots are persisted at a bounded cadence (currently 60 seconds), packet correlation is refreshed every five seconds, the UI exposes recent history, and observations are retained for seven days. These local histories are useful for diagnosing service and packet behavior; they are **not** substituted for the sealed raw/metadata/derived files of a formal trial.

The packet monitor deliberately uses three different duplicate concepts. An exact `phy_payload_sha256` observed with a **new gateway uplink ID** is a strong RF replay/duplicate candidate. Re-observation of the same gateway uplink ID is transport/capture redelivery and is not counted as another RF packet. Duplicate application identity, FCnt or `test_sequence` is a downstream/session anomaly and is reported separately. This distinction prevents QoS 1 MQTT behavior from being misreported as a LoRaWAN replay.

### Clock and timing gate

Counted runs fail closed unless the source-clock relationship to authoritative cloud UTC is **measured and stable**. `serial_capture.py` timestamps each EMU-01 `SENSOR_TX` line with the workstation clock, while the authoritative run window and database evidence use cloud/server UTC. Recorder v9 therefore does not assume that the workstation wall clock is correct: it independently calibrates the workstation against `ulc-01` immediately before the formal window, repeats the calibration after collectors stop, and invalidates finalization if the start/end mapping drifts by more than **0.100 s**. The calibrated mapping is retained in `metadata/run-meta.json` and is used to derive the Chapter 3 sensor-transmission-to-database-storage latency.

The recorder preflight still takes five midpoint-corrected `utc-now` samples from each of `ulc-01`, `ulc-02`, and `ulc-03`. The three cloud clocks must agree within **0.250 s**, Gateway-01 must remain within **±1.500 s** of the cloud median, and the workstation/cloud offset must be measurable within the bounded calibration range (**±300 s**). Absolute workstation offset is recorded rather than silently treated as zero. A large offset is acceptable only when start/end calibration remains stable; cloud disagreement, gateway disagreement, missing calibration, excessive drift, or negative calibrated sensor-to-database latency invalidates timing evidence.

Historical staging diagnosis found that the domain workstation could inherit a large absolute offset from its PDC even while the cloud and gateway clocks remained mutually coherent. Recorder v9 records that offset explicitly and proves its stability at both run boundaries, so a large but stable workstation wall-clock offset no longer blocks a run or contaminates source timing. The Active Directory time source should still be repaired through the normal PDC hierarchy for operational correctness; do not point a domain member directly at public NTP merely to satisfy research tooling.

Gateway-01 remains independently gated against the cloud median because gateway radio/evidence timestamps are part of the cross-system observation boundary. Its limit remains **±1.500 s**. If gateway/cloud agreement or cloud-node spread exceeds its limit, the recorder still fails closed. The restricted research-recorder key remains read-only and must not be weakened to repair time service configuration.

The cockpit's **Overall staging readiness** panel combines this clock gate with live cloud streams, Gateway management visibility, Patroni role topology, evidence readiness, leader database counters, telemetry-read availability, and the absence of an already-active formal recorder. This panel is an operational preflight aid only; the recorder CLI remains the final start gate and additionally checks required local USB/serial devices.

The server side remains read-only. `DBMETRIC` records are emitted only by the node that is observed as the PostgreSQL leader, avoiding duplicate HA counts. If a gateway management observation becomes unavailable, the cockpit shows **Management observation unavailable** and **Not observed** for unavailable gateway metrics; this means the management path could not be observed and does not prove the gateway or LoRaWAN radio path is offline. Sensor telemetry has separate semantics: a successful database read with zero rows is `idle` / **No fresh packets**; a failed live query is **Telemetry observation unavailable**; a transient read failure with a previous valid snapshot retains that snapshot as `stale`; only a read failure with no usable snapshot is an `error`. The clean fresh-test baseline is therefore expected to show **No fresh packets** until real new AS923 uplinks arrive. Telemetry queries use bounded five-second reads and a 30-second cache horizon, and their SSH subprocesses explicitly use a closed stdin (`DEVNULL`) so a detached/managed cockpit worker cannot block waiting on inherited console input. These rules prevent a slow polling cycle or unavailable management path from being mislabeled as device failure.

Recorder v4 adds a **foreground supervisor**. `run` is now the preferred Chapter 4 entry point: it starts the same serial/remote collectors as `start`, performs a bounded collector/evidence health gate every 15 seconds by default, records those observations in `raw/control-plane-health.csv`, and invokes the normal export/summarize/hash finalizer automatically on duration completion or Ctrl+C. This prevents an unnoticed workstation-session loss from leaving stale active state and silently invalidating later trials. Each supervisor row records the server-authoritative UTC timestamp, the workstation midpoint timestamp around that clock probe, the measured server-minus-workstation offset, and probe round-trip time. This makes workstation clock skew explicit instead of silently mixing clock domains. Experiment timing still uses server-authoritative timestamps and source/database evidence as described below.

Recorder v5 hardens that supervisor for real multi-minute counted work. A dead collector process remains an immediate terminal failure because evidence is actually being lost. Short-lived remote-readiness, USB/re-enumeration, database-role, or clock-probe failures are instead retained as `WARN` observations and must persist for three consecutive health gates before the supervisor aborts; a later clean gate resets the transient-failure count. Per-node SSH/readiness timeouts are converted into explicit health details rather than uncaught exceptions. If the server-authoritative clock probe is temporarily unavailable, the CSV leaves the authoritative timestamp and skew fields blank, records the condition as a warning, and never substitutes workstation time as if it were server time. `status`, `stop`, and `recover` also tolerate a failed final health probe so preservation/finalization can still complete. This policy was added after the 2026-09-04 uncounted counted-profile reload capture showed that a single transient readiness timeout could terminate the foreground supervisor while all child collectors and the actual LoRaWAN path remained healthy.

## Workstation dependency

The recorder is Python-native because this workstation is governed by a domain PowerShell `MachinePolicy=Restricted`. Do not weaken that policy.

Python dependency is pinned in `requirements.txt`:

```text
pyserial==3.5
```

Install/reproduce with:

```powershell
python -m pip install --user -r .\lorawan-network-server-gateway\test\automation\research-recorder\requirements.txt
```

The older `.ps1` prototypes in this directory are not the operator entry point on this workstation.

## Locked-down SSH boundary

The recorder uses a dedicated key outside the repository:

```text
%USERPROFILE%\.ssh\id_ed25519_research_recorder
```

The private key is never stored in the project. Its public key is installed on the three cloud nodes and Gateway-01 with a forced-command wrapper. The key can invoke only the read/capture verbs implemented under `remote/`; an arbitrary command such as `uname -a` is rejected.

Never replace this with an embedded SSH password or copy an administrator private key into the repository.

### Forced-command monitor boundary - current state 2026-09-18

Fresh restricted-key `version` checks on `ulc-01`, `ulc-02`, and `ulc-03` all return `research-recorder-server-v7`, matching the current repository wrapper. Do not reuse the historical v5 wrapper hash as a v7 integrity claim; verify the deployed file hash separately whenever byte-for-byte wrapper attestation is required. Gateway-01 remains on its separately versioned restricted gateway wrapper. The dedicated recorder key remains forced to reviewed verbs; arbitrary shell commands are not permitted.

Server wrapper v7 retains the bounded recorder/readiness verbs, `monitor-stream <seconds>`, and the fixed read-only `db-export packetflow <startUTC> <endUTC> <gatewayEUI>` projection used by the live packet correlator. The monitor stream multiplexes one-second host-resource records with slower service, readiness, database-role, database-counter and bounded recent-error observations. Optional service/error side probes are deliberately non-fatal, so an empty error scan or one failed auxiliary observation cannot terminate the resource stream and silently leave the cockpit stale. The packetflow projection joins already-authoritative gateway MQTT evidence to accepted telemetry, evidence-verification status, Fabric outbox state and Fabric transaction fields. It accepts no arbitrary SQL, table name, column name or filter expression from the caller.

Gateway wrapper v2 retains `snapshot`, `resource` and `logstream` and adds bounded `radio-recent <count>` and `journal-recent <count>` reads. `radio-recent` exposes only recent RAK5146 frame-reception log lines. `journal-recent` exposes retained immutable gateway journal records needed to correlate exact PHYPayload bytes for authorized replay testing. Neither command changes radio, network or journal state.

The `version` verbs and the fixed packetflow/radio reads were verified through the same restricted recorder identity after deployment. Keep the repository wrappers and deployed copies converged; do not bypass or weaken the forced-command boundary to troubleshoot monitoring.

### Read-only evidence-status boundary

The bounded `evidence-status` capability remains part of the current wrapper. It executes fixed SELECT-only queries against the commissioned evidence status views and returns aggregate verification/checkpoint state only. It exposes no payload bytes, evidence hashes, database credentials, arbitrary SQL, or arbitrary shell access.

The older `UNAVAILABLE_WRAPPER_UPGRADE_REQUIRED` compatibility behavior is historical only. Current cloud nodes run wrapper v7, so new formal runs are expected to capture the fixed evidence-status output when the underlying evidence read path is healthy. If a current run receives `command not allowed` or an unavailable-wrapper marker from a cloud node, treat that as a deployment/version regression and investigate it rather than accepting it as the present baseline.

### Journal-read prerequisite

`opsadmin` must be a member of `systemd-journal` on `ulc-01`, `ulc-02`, and `ulc-03`. This is required so the forced-command recorder identity can retain Mosquitto and kernel-journal evidence without using sudo or an unrestricted administrator shell. The membership was applied and verified on all three cloud nodes on 2026-09-03.

### Accepted recorder smoke - 2026-09-03

The first uncounted smoke, `recorder-smoke-20260903`, proved the core start/capture/stop/export/summarize/hash path but exposed the missing journal-read permission above; preserve that run as diagnostic evidence. After correcting journal access, `recorder-smoke-journal-20260903` completed cleanly with all eight live collectors healthy, recorder stop exit `0`, status `RECORDED_UNCLASSIFIED`, no stop-error file, 65 SHA-256 manifest entries independently verified, and 39 raw evidence files sealed read-only. The marker path, TimescaleDB exports, exact-window service logs, kernel logs, statistics, and active-state cleanup were also verified. Static/live recorder validation then passed.

Both smoke runs intentionally used `--skip-serial`. Counted LoRaWAN runs must pass `preflight --require-emu --require-sec` and must not skip EMU-01 source capture when the PDR denominator depends on `SENSOR_TX` attempts.

### Accepted supervised-recorder smoke - 2026-09-04

Recorder v4 was commissioned with two bounded, uncounted foreground `run --skip-serial` smokes against the live Gateway-01 plus three-node cloud. The first run, `collector-supervised-smoke-20260904-0456z`, proved collector supervision and clean automatic finalization but deliberately remains diagnostic evidence because it exposed that its first implementation timestamped supervisor health with workstation UTC while start/end boundaries used server-authoritative UTC. The workstation was materially behind the cloud clock, so those control-plane rows could appear before the run start. The same run also showed that uncounted metadata must not claim the frozen counted EMU profile when serial capture is skipped.

Both provenance defects were corrected before acceptance. `control-plane-health.csv` now records server-authoritative UTC, the bracketing workstation midpoint, measured server-minus-workstation offset, and clock-probe round-trip time. `--skip-serial` metadata now records `serial_capture_enabled=false`, `emu_profile=NOT_CAPTURED_UNCOUNTED`, and leaves counted source/HEX hashes blank rather than implying the counted firmware was observed.

The corrected run `chapter4-results/smoke/collector-supervised-clockfix-20260904` is the accepted v4 supervisor smoke. It exited `0`, finalized as `RECORDED_UNCLASSIFIED`, produced 76 manifest entries with zero missing files and zero SHA-256/size mismatches, left no `_recorder-active.json`, `stop-errors.txt`, or `supervisor-errors.txt`, and recorded three monotonically increasing `PASS` supervisor rows inside the authoritative start/end window. The clock probes measured the server about `104.65-104.90 s` ahead of the workstation with roughly `1.06-1.22 s` round-trip time; this skew is now explicit evidence rather than a hidden timing assumption. A subsequent live `preflight --require-emu --require-sec` also passed with EMU-01 on `COM11`, SEC on `COM16`, `ulc-01` leader, `ulc-02`/`ulc-03` replicas, and all required evidence roles ready.

### Counted-profile post-flash sanity - 2026-09-03

The uncounted readiness run `counted-profile-postflash-sanity-20260903` exercised the frozen 15-second EMU-01 image with real USB source capture and the commissioned Gateway-01/LTE/cloud path. The sealed recorder-v1 bundle contains 189 healthy source attempts (`send_status=0`, sequences 7..195), 192 unique database event keys, 2,496 normalized measurements (exactly 13 per event), and 192 Fabric-outbox rows left `pending` because the external Fabric worker remains intentionally disabled.

A naïve comparison of 192 DB rows against 189 captured source attempts produced an impossible 101.587% value in the sealed v1 derived summary. That number is **not a valid PDR and must not be cited**. Byte-for-byte reconstruction of each 46-byte payload proved 185 exact source/DB matches for sequences 7..191. Those matches establish a stable DB-minus-workstation timestamp offset of about +103.24 seconds. After applying that measured offset to define the source attempts actually covered by the DB export window, all 185 eligible source attempts have exact DB matches: aligned PDR = 100.0%. DB-only rows are the six current-session frames emitted before serial capture plus one prior-session sequence-8 frame admitted by the skewed wall-clock start boundary; source-only sequences 192..195 project beyond the DB export end.

Recorder version 2 therefore no longer calculates PDR as DB-row-count/source-attempt-count. It reconstructs the payload-v2 bytes from every `SENSOR_TX` line, correlates them exactly to `raw_data`, estimates the workstation/cloud clock offset from those exact matches, and limits the denominator to source attempts whose projected DB timestamps fall inside the actual export window. If that aligned observation window cannot be established, PDR is withheld rather than guessed. The sealed v1 bundle is intentionally left unchanged; corrected interpretation is recorded in the preflight analysis outside the sealed run.

The same sanity run exposed a Windows-specific shutdown defect: `taskkill /T /F` could hang while traversing the process tree. Direct `taskkill /PID <pid> /F` was proven against the live recorder-owned processes and a disposable child. Both Python and legacy PowerShell recorder paths now omit `/T`; the Python path also bounds termination to five seconds.

## Result shape

```text
chapter4-results/<group>/<run-id>/
  raw/
    emu-01-source.log
    sec-source.log                  # when requested
    gateway.log
    gateway-resource.csv
    ulc01-host-resource.csv
    ulc01-docker-resource.csv
    ulc02-host-resource.csv
    ulc02-docker-resource.csv
    ulc03-host-resource.csv
    ulc03-docker-resource.csv
    uplinks.csv
    measurements.csv
    fabric-outbox.csv
    *-chirpstack.log
    *-mosquitto.log
    *-node-red.log
    *-kernel.log
    markers.csv
  metadata/
    run-meta.json
    start-utc.txt
    end-utc.txt
    *-snapshot-start.txt
    *-snapshot-end.txt
    database-roles-end.json
    SHA256SUMS.csv
  derived/
    run-summary.json
    run-summary.csv
    trial-results.csv
    run-status.txt
```

`PASS`, `FAIL`, `INVALID`, and `BLOCKED` remain research classifications. The recorder deliberately ends a clean capture as `RECORDED_UNCLASSIFIED`; evidence collection must not invent the experiment outcome.

## Usage

From the repository root:

```powershell
$R = '.\lorawan-network-server-gateway\test\automation\research-recorder\research_recorder.py'

# Remote collectors + Patroni topology; add both flags before LoRaWAN security testing.
python $R preflight --require-emu --require-sec

# Preferred counted-run mode. Keep this terminal open; Ctrl+C finalizes safely.
# Use a second terminal for mark/trial/serial-control commands while this runs.
python $R run `
  --group authentication `
  --run-id auth-lorawan-A1-01 `
  --condition 'registered device with correct OTAA credentials' `
  --expected 'allow; JoinAccept and accepted uplink' `
  --scope lorawan `
  --capture-sec

# Timestamp a physical/software event without stopping capture.
python $R mark --message 'A1-01 reset issued'

# Read the current aggregate verifier/checkpoint state without starting a run.
# This is intentionally strict: on pre-v3 live wrappers it reports that the server-side upgrade is required.
python $R evidence-status

# Optional explicit active-recorder view; the foreground supervisor already gates health every 15 seconds.
python $R status

# When a counted OTAA trial requires reloading the exact frozen EMU image,
# keep the recorder and all remote collectors alive while intentionally yielding COM11.
# The serial log records RECORDER_SERIAL_PAUSED / RECORDER_SERIAL_RESUMED and then
# automatically reacquires the board after DFU re-enumeration.
python $R serial-pause --device emu
# reload the already-frozen counted-test ZIP; do not rebuild here
python $R serial-resume --device emu

# The same mechanism may yield SEC during A2/A3 fixture commands without stopping
# the rest of the counted evidence capture:
# python $R serial-pause --device sec
# ... issue only the documented SEC test-fixture commands ...
# python $R serial-resume --device sec

# Record the trial classification after its evidence is inspected.
python $R trial `
  --trial-id A1-01 `
  --condition 'correct OTAA credentials' `
  --expected allow `
  --actual allow `
  --status PASS `
  --notes 'JoinRequest received; JoinAccept; application uplink stored'

# Normally press Ctrl+C in the foreground `run` terminal when complete.
# It automatically exports DB/log evidence, calculates statistics, hashes files and seals raw evidence read-only.

# Recovery only: if a detached or interrupted run left _recorder-active.json,
# inspect it first, then finalize and preserve it rather than deleting it.
python $R status
python $R recover
```

For a bounded **uncounted** collector smoke test, `run --skip-serial --duration-seconds 60` is appropriate. In that mode `run-meta.json` explicitly marks serial capture disabled and the EMU profile as `NOT_CAPTURED_UNCOUNTED`; it does not claim that the frozen counted-test image was observed. Counted runs normally omit `--duration-seconds` and run until operator Ctrl+C.

Use `--interval 1` for flooding and normally `--interval 5` for baseline/resilience/resource observations. The default supervisor health interval is 15 seconds; do not make it aggressively shorter because each gate also checks the replicated evidence path.

`--skip-serial` exists only for clearly uncounted recorder smoke tests. Do not use it for a counted run whose delivery/PDR denominator depends on EMU-01 `SENSOR_TX` attempts.

## Statistical interpretation

The recorder derives only metrics supported by its actual evidence. Formal Chapter 3 PDR and source-to-database delivery are deliberately separate:

```text
formal Chapter 3 PDR = unique accepted EMU-01 ChirpStack deduplication IDs across both HA ChirpStack logs / captured scheduled SENSOR_TX attempts x 100
database delivery    = exact DB payload matches for eligible source attempts / eligible source attempts x 100
```

For formal PDR, `summarize-run.py` strips ANSI log formatting, unions accepted `deduplication_id`s from `ulc01-chirpstack.log` and `ulc02-chirpstack.log`, associates them with the run's `dev_eui` from `run-meta.json`, and divides that unique accepted count by every captured scheduled `SENSOR_TX` attempt in the same run window. A scheduled source-side send failure remains in the denominator. The percentage is withheld when required logs/device identity/source attempts are missing or when accepted uplinks exceed the source-attempt boundary. This is the Chapter 3 LoRaWAN/ChirpStack metric boundary.

For database delivery, source and database evidence are correlated by reconstructing the exact 46-byte payload-v2 bytes from each `SENSOR_TX` line and matching those bytes to `telemetry.uplinks.raw_data`. Exact matches also provide the measured DB-minus-source clock offset. A source-side attempt remains in the delivery-correlation denominator only when the recorder can prove that attempt lies inside the DB observation window. Boundary attempts outside that comparable window are reported as unmatched correlation evidence, not silently counted as packet loss.

Never copy database delivery into a Chapter IV PDR column merely because both percentages may happen to be equal in a healthy run. An MQTT redelivery is not a second LoRaWAN delivery, and a second LoRaWAN session reusing a sequence/FCnt value is not collapsed merely because the counter repeats.

For replay/spoofing, only attack transmissions whose RAK5146 reception is proven belong in the counted attack denominator. `sec02_replay.py capture --test-sequence <N>` may now bind a replay/spoofing fixture to the exact accepted EMU-01 `test_sequence` designated as that trial's legitimate control; the helper still requires the configured minimum FCnt age and independently correlates the selected packet to Gateway-01 journal, packetflow, and RAK5146 reception evidence before it will create the fixture. This prevents a nearby historical uplink from being silently substituted for the intended control.

`application_event_to_db_ms` is `telemetry.uplinks.received_at - telemetry.uplinks.time`. Do not relabel it sensor-to-database latency unless a separate run proves the source/laptop UTC timestamp is correlated closely enough with the server clock.

The post-run summarizer also reports sample SD, min, max, RSSI, SNR, frequency counts, sequence/FCnt gaps, measurement counts, Fabric outbox states, and per-node host/container resource statistics.

## What remains physical

Evidence capture, exports, statistics, hashing, most attack generators, and server/network fault injection can be automated. Human action remains only where the experimental condition itself is physical, such as reconnecting actually disconnected hardware, deliberately moving nodes/antennas, or changing a real environmental sensor condition.

A physical reset can be timestamped with `mark`. If a test later proves a safe software-reset mechanism for the exact board mode, a test-specific driver can automate that reset as well.
