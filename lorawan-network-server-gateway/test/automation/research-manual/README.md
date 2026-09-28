# Research Manual Support Tooling

The authoritative operator-facing test manual is:

```text
chapters/lorawan_research_test_manual_final.pdf
chapters/lorawan_research_test_manual_final.md
```

The manual is aligned to `test/ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md`. It keeps the Chapter 3 experiment counts, durations, formulas, evidence boundaries, validity rules, and measurements, but deliberately omits stale implementation prose.

`CONTINUATION.md` is the current handoff for future chats. Read it before changing the manual or test harness.

To exercise the **same operator dispatch without live hardware or production effects**, use `py -3 test/automation/research-manual/run_test.py I3 --synthetic` from the repository root, replacing I3 with A1, A2, P2, R1, R2, S1, F1, F2, I1, I2, I3, T1 or T2. This runs existing allowlisted synthetic tests, never starts a counted run, and does not promote live readiness. PRE/P1 do not have complete offline equivalents; S2 is methodology-blocked. See `SYNTHETIC-COMMAND-REHEARSAL.md` for the checked 13-ID command table and limitations.

`run_test.py` is the fail-closed operator/readiness entry point. A code block may appear in the final manual only when the corresponding test is `READY` and the complete action is runnable. Non-ready tests remain documented without a code block until their harness is commissioned.

Status meanings remain:

- `READY` - the existing harness can perform the complete formal action when preflight passes.
- `CAPTURE_READY` - evidence capture exists, but the deliberate condition/fixture action still has to be performed and proven at the tested layer.
- `HARNESS_REQUIRED` - Chapter 3 is specified but a reviewed fixture/orchestrator is still required; counted execution must fail closed.
- `METHODOLOGY_REQUIRED` - Chapter 3 itself is incomplete for that experiment; counted execution must remain blocked until formally amended.

A green infrastructure preflight is separate from formal experiment readiness. `PRE` proves the commissioned platform, clocks, sensor/gateway path, evidence services, and access paths are healthy. It does not relabel incomplete experiment harnesses as ready.

`CODE-BLOCK-VALIDATION.md` records only released operator-block validation. `CURRENT-READINESS.md` is a point-in-time implementation snapshot, not a substitute for the manual or Chapter 3 source-of-truth.

## Verify a sealed run without changing its evidence

From the project root:

```powershell
python .\test\automation\research-recorder\verify-run-reproducibility.py .\chapter4-results\smoke\RUN_ID
```

Replace RUN_ID with a completed run directory. The checker validates every manifest entry and requires all raw files to be sealed. It regenerates summaries twice in a temporary copy. JSON measurements must match the sealed summary exactly (only the relocated run_dir is excluded); CSV output must be byte-identical. A mismatch exits nonzero. Original evidence is never rewritten.

This proves reproducible processing of the recorded inputs with the reported Python version and summarizer SHA-256. It does not establish statistical repeatability of radio measurements or validate an uncommissioned experiment.

Readiness reporting distinguishes tooling from live checks. With --skip-live-pre, a successful local check reports tooling_gate=PASS and technical_gate=SKIPPED. Only successful live checks can report technical_gate=PASS. Code-block validation checks the interface; it is not evidence that the experiment itself ran.
