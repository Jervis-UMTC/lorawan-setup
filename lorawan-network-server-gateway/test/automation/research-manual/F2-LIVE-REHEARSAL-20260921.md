# F2 live malformed-message commissioning — 2026-09-21 (non-counted)

**Evidence result: three full real 30-second flood windows PASS. Operator-runner result: TIMEOUT after recording the windows, before producing the combined session file.** Do not describe the exact top-level `run_test.py F2` command as exit-0 PASS. All window-specific `flood-harness-result.json` records are PASS and all three recorder runs completed. The earlier F2 isolated-only rehearsal is not reused as genuine sensor-delivery evidence here.

## Live run and measurements

Invoked the real manual command `RESEARCH_MANUAL_REHEARSAL_SECONDS=30 py -3 test/automation/research-manual/run_test.py F2` with `EXECUTE`; technical, firmware, clock, LTE, recorder and LIVE_PRE gates all passed. The MCP command had a 570-second execution limit and was force-terminated after its three dedicated windows had finalized, before the outer flood harness could emit `_sessions/F2-20260921-143817.json` and its exit status. This **is a command-completion qualification gap**, not a window-measurement failure.

| Malformed-message rate | Actual received/rejected | Incorrectly accepted | Real EMU-01 cloud deliveries in flood window | Mean delivery latency |
|---|---:|---:|---:|---:|
| 0 messages/s | 0/0 | 0 | 1 | 13.325 ms |
| 10 messages/s | 300/300 | 0 | 2 | 20.331 ms |
| 50 messages/s | 1,500/1,500 | 0 | 2 | 31.736 ms |

Source run folders, each with recorder status `RECORDED_UNCLASSIFIED`, its own `metadata/SHA256SUMS.csv`, raw gateway/EMU/DB/Node-RED evidence and `derived/flood-harness-result.json`:

- `chapter4-results/dos-flooding/F2-rehearsal-r0-n1-20260921-143817/`
- `chapter4-results/dos-flooding/F2-rehearsal-r10-n1-20260921-143817/`
- `chapter4-results/dos-flooding/F2-rehearsal-r50-n1-20260921-143817/`

All three results explicitly show `status=PASS`, `errors=[]`, `recorder_returncode=0`, `formal=false`; no fake database uplinks or outbox rows in either the per-window or global guards; 0 unauthorized rows at 0, 10 and 50/s. Exact source-to-cloud delivery remains distinct from independently confirmed Fabric world-state: **Fabric settlement is disabled for flooding recorder runs**, and no HRC ledger query was part of this F2 scorer.

### Independent post-timeout verification and rollback

A separate Python check reran the **actual `flood_harness.validate_run('F2', rate, 30, ... formal=False)`** for all three saved results, checked legitimate delivery and recorder exit, and compared **all 186 manifest-listed source/observation/summary files** by size and SHA-256 to sealed manifests: PASS. The project recording sentinel `chapter4-results/_recorder-active.json` was absent and workstation SSH tunnel port 11885 closed.

The combined operator wrapper timed out before its final cleanup/status reporting. Separate real-time restricted research-action status and cleanup verified ULC-03 Node-RED `branch_installed=false`, `state_present=false`, `research_nodes_present=[]`, original `flow_sha256=5f3d60e7ab2bb5fa8aa424c75da3cdca37bb716a7f66ee53b5f155c6e80fc2de`, container healthy. ULC-01 isolated flood listener was initially still ACTIVE after interruption; explicitly stopped and independently verified `listener=INACTIVE`. A repeated branch-remove returned `research flood state is absent; safe restore unavailable` **because the branch was already removed**. No production MQTT/Node-RED flow changes were left behind.

## Recovered original session and interruption-safe operator path (subsequent repair)

The original missing combined report was **reconstructed without generating new malformed traffic**. From the actual sealed 0/10/50 windows, the new read-only recovery command:

```powershell
py -3 test/automation/flooding/flood_session.py F2 20260921-143817
```

verified all **186** manifest entries again, reran the same F2 load/DB delivery scorer on all three non-counted windows, checked the live ULC-03 Node-RED branch was absent and healthy, ULC-01 isolated listener inactive, workstation flood tunnel absent and research recorder clean. It created `chapter4-results/dos-flooding/_sessions/F2-20260921-143817.json` with **`status=WINDOWS_PASS_OPERATOR_TIMEOUT`**, `recovered_after_operator_timeout=true`, `operator_exit_code=null`, `formal=false`, and `counted_research=false`. This is a transparent *recovered evidence bundle*, NOT an assertion that the original timed-out command completed successfully.

The common `flood_harness.py` now writes an atomic combined-session checkpoint before any fixture mutation, immediately after each completed window, before teardown, and on completion/failure. Cooperative SIGTERM/KeyboardInterrupt attempts cleanup; an externally forced kill cannot guarantee remote fixture cleanup, so the recovered-session command independently requires inactive fixtures. A real second/third-window failure leaves `status=INCOMPLETE` and the preceding successful windows preserved, never a fabricated PASS. Four new in-process regression tests passed, including failure injection, manifest tampering/missing-window refusal and complete-session report. **No additional live F2 attack run was needed to qualify the recovery feature.**

For future **non-counted F2 rehearsals only**, the manual command now defaults to a shorter, separately printed **10-second recovery interval** for a 30-second measurement window to avoid the 570-second remote command limit. You can set `RESEARCH_MANUAL_REHEARSAL_RECOVERY_SECONDS` to an explicit 1..measurement-seconds value when needed. Formal Chapter 3 F2 remains exactly **300-second flood windows, 300-second recovery, three repetitions**; the frozen experimental design was not changed. The revised one-block operator path is code-tested but has **not** been rerun live end to end, so keep that narrow boundary explicit.

Latest full offline code-only suite: **202/202 PASS across 16 suites**, `chapter4-results/code-qualification/offline-code-20260921T070240188741Z/code-only-summary.json`.

## Readiness

The genuine end-to-end F2 **0/10/50 per-window behavior has live proof** and the recovered session is explicitly labeled after the original operator timeout. The new incremental session writing and shorter non-counted recovery have passed offline fault-injection checks; the revised one-block operator command has not yet had an independent new live exit-0 run. Do not needlessly repeat the 1,800 invalid messages or label the original command exit-0. No Chapter 4 formal trial was counted.

Next investigate remaining not-yet-live-qualified tests and coordinate Fabric-side independent ledger proof, rather than rerunning known-good F1/F2 attack actors. Formal five-minute x three-repetition methodology remains protected by the contract; these 30-second non-counted windows are only commissioning.
