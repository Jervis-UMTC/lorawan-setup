# Research Manual Code-Block Audit

Generated UTC: 2026-09-16T08:22:32Z

The final manual currently contains exactly one released PowerShell operator block: PRE. It was executed with EXECUTE against the live environment and passed. All other Chapter 3 test IDs were invoked through run_test.py with the safe validation path to prove their CLI/interface guard works without starting an incomplete counted test.

| Test | Current status | Command/interface result | Counted action executed? |
|---|---|---|---|
| PRE | READY | PASS - exact published block executed live | YES |
| P1 | CAPTURE_READY | PASS - guard/interface path | NO; no released block |
| P2 | HARNESS_REQUIRED | PASS - guard/interface path | NO; no released block |
| R1 | CAPTURE_READY | PASS - guard/interface path | NO; no released block |
| R2 | HARNESS_REQUIRED | PASS - guard/interface path | NO; no released block |
| A1 | CAPTURE_READY | PASS - guard/interface path | NO; no released block |
| A2 | HARNESS_REQUIRED | PASS - guard/interface path | NO; no released block |
| S1 | CAPTURE_READY | PASS - guard/interface path | NO; no released block |
| S2 | METHODOLOGY_REQUIRED | PASS - guard/interface path | NO; methodology incomplete |
| F1 | CAPTURE_READY | PASS - guard/interface path | NO; no released block |
| F2 | CAPTURE_READY | PASS - guard/interface path | NO; no released block |
| I1 | HARNESS_REQUIRED | PASS - guard/interface path | NO; no released block |
| I2 | HARNESS_REQUIRED | PASS - guard/interface path | NO; no released block |
| I3 | HARNESS_REQUIRED | PASS - guard/interface path | NO; no released block |
| T1 | CAPTURE_READY | PASS - guard/interface path | NO; no released block |
| T2 | CAPTURE_READY | PASS - guard/interface path | NO; no released block |

## Exact live PRE result

- TECHNICAL_GATE=PASS
- TOOL_COMPILE=PASS
- MQTT_TOOL_SELFTEST=PASS
- COUNTED_FIRMWARE=PASS
- RECORDER_STATE=CLEAN
- GATEWAY_LTE=PASS
- LIVE_PRE=PASS
- TEST=PRE STATUS=READY CODE_BLOCK=PASS

## Publication rule

A test is not allowed to gain a manual code block merely because its wrapper exits successfully. It must first have a complete, rehearsed, fail-closed harness that performs the Chapter 3 action and proves the required measurements. P1 remains withheld because its previous live publication rehearsal captured zero EMU-01 source transmissions and zero gateway RF packets.
