# Synthetic operator-command rehearsal — 2026-09-21

**Result:** 13 of 13 hardware-independent test IDs passed through the **actual** `research-manual/run_test.py --synthetic` dispatch. PRE, P1, S2 returned exit code 2 with `SYNTHETIC=UNAVAILABLE`, rather than fake PASS. All operations were code-only, no samples were counted, and no live gateway, sensor, Node-RED, PostgreSQL, Fabric, or production MQTT action was requested.

From `lorawan-network-server-gateway` repository root, run any mapped test individually:

```powershell
py -3 test/automation/research-manual/run_test.py I3 --synthetic
```

Replace `I3` with one of `A1 A2 P2 R1 R2 S1 F1 F2 I1 I2 I3 T1 T2`. `--synthetic` routes to the allowlisted `offline_test.py` suite **before live tooling/preflight checks**, ignores the live rehearsal environment variable, and runs no live action. Remove `--synthetic` when intending to use the existing operator validation/real commissioning path, which still requires explicit EXECUTE where applicable and obeys the conservative test readiness status.

For all code suites at once:

```powershell
py -3 test/automation/run_offline_qualification.py
```

Last full offline suite before this interface change: `chapter4-results/code-qualification/offline-code-20260921T021548133899Z/code-only-summary.json` recorded **195/195 PASS across 16 allowlisted suites**. This batch also checked both changed Python files compile, targeted diff whitespace, and normal `run_test.py I3` still returns `HARNESS_REQUIRED` with only guard validation. The 13-ID synthetic dispatch passed. The added `offline_test.py` mappings reuse existing tested R2/S1/F1/F2/T1/T2 suites; they do not add new experimental evidence or inflate the consolidated suite count.

**Hardware restored later:** run live PRE first, ensure real EMU-01/SEC-01 events and LTE route are observed, and commission the intentionally blocked experiments individually with the actual Fabric team. A code-only PASS proves the commands/parsers/scorers exercise intended synthetic inputs; it does not prove physical AS923 transmission, radio measurements, provider LTE, actual database quarantine, or HRC world-state mutation/rejection. S2 is **METHODOLOGY_REQUIRED**, not a code defect that synthetic input can solve.
