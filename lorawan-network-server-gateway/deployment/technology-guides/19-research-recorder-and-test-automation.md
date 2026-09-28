# Research Recorder and Test Automation — Operator Manual

## What this technology does

The research recorder is the authoritative evidence-capture system for the dissertation experiments. It captures USB source attempts, Gateway-01 evidence, cloud logs, resource metrics, database exports, evidence status, Fabric outbox state, run timing, hashes and derived summaries.

Grafana and the live cockpit are observation aids. The sealed recorder bundle is the authority for a formal trial.

## Current entry points

~~~text
test/automation/research-recorder/research_recorder.py
test/automation/research-manual/run_test.py
test/automation/research-manual/ensure_ready.py
test/automation/research-recorder/research_cockpit.py
test/automation/research-recorder/summarize-run.py
test/automation/research-recorder/summarize-study.py
~~~

**Fresh read-only 2026-09-21 08:09 UTC inspection:** the restricted forced-command SSH wrapper reported `research-recorder-server-v10` on ULC-01 and `research-recorder-server-v8` on ULC-02 and ULC-03; Gateway-01 reported `research-recorder-gateway-v3`. These are host-specific deployed versions, not one global version. The older repository-source v7/v5 notes are historical; compare the verb and response actually needed by each test before using it. Do not claim all servers are v10 without deployment proof.

## Step 1 — Read the current authority

Before a formal test read:

~~~text
test/ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md
test/automation/research-manual/CURRENT-READINESS.md
test/automation/research-manual/CONTINUATION.md
chapters/lorawan_research_test_manual_final.md
~~~

Chapter requirements define what must be measured. Verified live infrastructure defines how it is executed.

## Step 2 — Install the pinned Python dependency

~~~powershell
python -m pip install --user -r .\lorawan-network-server-gateway\test\automation\research-recorder\requirements.txt
~~~

The pinned dependency is pyserial 3.5.

Do not weaken workstation PowerShell policy to run older prototypes.

## Step 3 — Preserve the restricted SSH boundary

Recorder key:

~~~text
%USERPROFILE%\.ssh\id_ed25519_research_recorder
~~~

The key is forced-command only. It must not provide arbitrary shell access. Never replace it with an embedded password or administrator private key.

## Step 4 — Check recorder state

~~~powershell
$R = '.\lorawan-network-server-gateway\test\automation\research-recorder\research_recorder.py'; python $R status
~~~

**PASS means:** no unexpected formal run is active.

If an interrupted run exists, preserve it and use recover; do not delete its marker.

## Step 5 — Run formal preflight

~~~powershell
python $R preflight --require-emu --require-sec
~~~

This checks serial devices, cloud collectors, database topology, evidence services, clock alignment and required tooling.

A green platform preflight does not make every experiment READY.

## Step 6 — Respect the clock gate

Do not start timing-sensitive counted work while recorder clock validation fails.

If it fails:

1. determine whether workstation/PDC, Gateway-01 or cloud time is wrong;
2. repair the authoritative time source;
3. rerun preflight;
4. begin no counted run until PASS.

Never rewrite timestamps after capture.

## Step 7 — Check formal test readiness

From the repository parent directory, inspect the generated release gate before selecting a test:

~~~powershell
Get-Content '.\lorawan-network-server-gateway\test\automation\research-manual\CURRENT-READINESS.md'
python .\lorawan-network-server-gateway\test\automation\research-manual\run_test.py --help
~~~

`--help` documents the interface; **it does not run or prove the experiment readiness gate**. Read the generated technical gate and per-test status, then follow the released test-specific operator block. Status meanings:

~~~text
READY                 complete runnable action
CAPTURE_READY         capture exists; deliberate fixture incomplete
HARNESS_REQUIRED      reviewed orchestrator/fixture still missing
METHODOLOGY_REQUIRED  Chapter 3 itself is incomplete
~~~

Only READY tests may appear as executable blocks in the final manual.

## Step 8 — Start a formal recorder run

**Do not launch a counted experiment from a generic example in this technology guide.** Choose only a currently released READY test, pass the current technical/device/clock and experiment-specific gates, and execute that test's exact operator block under `test/automation/research-manual/` or the corresponding approved execution manual. At the latest inspected generated gate (`2026-09-21 07:55:23 UTC`), PRE and P1 alone were released; re-read the generated gate before each actual trial; example authentication commands are not a substitute for a released A1 procedure.

Keep the foreground recorder terminal open while its approved run is active. Use a unique run ID and the exact experiment group/condition/expected outcome required by the formal manual.

## Step 9 — Mark deliberate actions

~~~powershell
python $R mark --message 'A1-01 reset issued'
~~~

Use markers for resets, cable changes, fault injection or physical actions whose timing matters.

## Step 10 — Yield one serial port safely

EMU:

~~~powershell
python $R serial-pause --device emu
python $R serial-resume --device emu
~~~

SEC:

~~~powershell
python $R serial-pause --device sec
python $R serial-resume --device sec
~~~

Perform only the approved fixture/firmware action between pause and resume.

## Step 11 — Inspect evidence state while running

~~~powershell
python $R evidence-status
~~~

This is a fixed read-only boundary. Do not manually rewrite verifier or Fabric states to improve a trial.

## Step 12 — Record trial classification after evidence review

~~~powershell
python $R trial --trial-id A1-01 --condition 'correct OTAA credentials' --expected allow --actual allow --status PASS --notes 'JoinRequest received; JoinAccept; application uplink stored'
~~~

Allowed classifications: PASS, FAIL, INVALID and BLOCKED.

The recorder itself finalizes as RECORDED_UNCLASSIFIED; it does not invent the conclusion.

## Step 13 — Stop normally

Use Ctrl+C in the foreground run.

Normal finalization must:

~~~text
stop collectors
export exact-window DB/log evidence
calculate derived metrics
write end metadata
hash completed evidence
seal raw files read-only
remove active marker
~~~

Do not kill Python when clean finalization is possible.

## Step 14 — Recover an interrupted run

~~~powershell
python $R status
python $R recover
~~~

Recovery preserves and finalizes partial evidence. Do not delete _recorder-active.json to get back to CLEAN.

## Step 15 — Understand the evidence tree

~~~text
chapter4-results/<group>/<run-id>/
  raw/
  metadata/
  derived/
~~~

Typical authoritative files include source serial, gateway/resource data, ULC resource data, uplinks.csv, measurements.csv, fabric-outbox.csv, exact-window service logs, run metadata, SHA256SUMS.csv and derived trial summaries.

Never edit raw files.

## Step 16 — Verify the evidence seal

A valid finalized run must have:

~~~text
no missing manifest files
no hash mismatch
no unexplained active marker
no unexplained stop/supervisor failure
all required collectors present
~~~

If a required stream failed, classify the trial from evidence; do not repair raw files afterward.

## Step 17 — Keep PDR and database delivery separate

Formal Chapter 3 PDR:

~~~text
unique legitimate ChirpStack-accepted uplinks / captured scheduled SENSOR_TX attempts x 100
~~~

Database delivery:

~~~text
exact DB payload matches for comparable source attempts / eligible comparable source attempts x 100
~~~

Never use simple DB-row-count/source-count as PDR.

## Step 18 — Preserve exact payload correlation

The recorder reconstructs the 46-byte payload-v2 from each SENSOR_TX line and matches it to telemetry.uplinks.raw_data.

Do not replace exact-byte correlation with timestamp-only, FCnt-only or sequence-only matching.

## Step 19 — Use the cockpit correctly

~~~text
http://127.0.0.1:8765/
~~~

The cockpit shows packet flow, resources, service roles, database counts, evidence readiness and Fabric state.

It is not the formal result authority. Sealed recorder evidence is.

## Step 20 — Use skip-serial only for uncounted smoke

~~~powershell
python $R run --skip-serial --duration-seconds 60 --group smoke --run-id recorder-smoke
~~~

Never use --skip-serial when the formal denominator depends on SENSOR_TX attempts.

## Current restricted remote verbs

~~~text
version
utc-now
clock-probe
evidence-ready
snapshot
db-role
evidence-status
monitor-stream
resource-host
resource-docker
db-export
docker-log
unit-log
kernel-log
~~~

Arbitrary commands must remain rejected.

## Troubleshooting order

| Symptom | First check |
|---|---|
| EMU COM busy | Serial Monitor/orphan serial process |
| SEC missing | current COM / device mode |
| clock gate fails | PDC/workstation/Gateway/cloud time |
| remote command rejected | wrapper version/deployment |
| one collector dies | supervisor and that collector log |
| no DB rows | source -> RF -> ChirpStack -> app |
| DB rows, no Fabric terminal state | evidence eligibility/finalization/adapter |
| impossible >100% PDR | metric/window/deduplication bug |
| hash mismatch | preserve evidence and classify honestly |
| cockpit stale | monitor stream; never edit evidence |

## Security boundary

- recorder SSH is forced-command only;
- no arbitrary SQL from workstation;
- no embedded admin password;
- AppKeys/private keys must not enter evidence;
- raw evidence is sealed read-only;
- failures are preserved rather than cleaned away.

## Completion checklist

- current source-of-truth/readiness read;
- recorder clean before start;
- preflight PASS;
- clock gate PASS;
- required serial sources captured;
- supervisor remains healthy;
- actions marked;
- classification evidence-based;
- run finalizes/recover succeeds;
- manifest hashes verify;
- raw evidence read-only;
- correct metric definitions used;
- non-ready tests remain unpublished.

## Complete research execution and metrics companion

Use [research automation, formal Chapter III matrix, denominators/units, run sealing and recovery](RESEARCH-AUTOMATION-EXPERIMENT-METRICS-RECOVERY.md). It distinguishes code-only tests, non-counted rehearsals, READY operator actions and completed counted trials.

## Detailed references

- [Recorder README](../../test/automation/research-recorder/README.md)
- [Research manual tooling](../../test/automation/research-manual/README.md)
- [Continuation state](../../test/automation/research-manual/CONTINUATION.md)
- [Metrics source of truth](../../test/ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md)
