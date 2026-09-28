# Research Test Oversight Audit

This checklist is an executable-design companion to `ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md`.

Global formal-run invariants:
- declare FORMAL vs REHEARSAL before opening the measurement window;
- unique run/trial IDs and exact planned denominator are frozen before counting;
- warm-up is outside the formal window;
- settlement/recovery is separate from the measured generation window;
- failed/invalid attempts are retained, never deleted;
- clock calibration/drift, effective config, raw evidence, and SHA-256 manifest are retained;
- intentional faults must prove they reached the intended layer;
- Fabric-linked evidence joins exactly by run_id + trial_id + source_record_id + payload_sha256.

High-risk gates:
- P1: 3 x 1800 s; nominal 15 s cadence = 120 planned attempts/run. Do not redefine denominator from observed successes.
- P2: 0.0667/1/5/10 TPS x 300 s x 3; matched control for every Fabric run; pair order is pre-registered as control->Fabric, Fabric->control, control->Fabric for repetitions 1/2/3. Use open-loop scheduling and separate commit drain.
- R1: prove LTE is the active WAN before outage and prove no Ethernet/Wi-Fi fallback during the 60-minute interruption.
- R2: isolate Fabric only; freeze the exact 10 outage IDs; query-before-resubmit/automatic-reconcile evidence is mandatory; recovery uses the same 10.
- A1: exactly nine named conditions x10, with layer-specific expected decisions and no timeout misclassified as authentication rejection.
- A2: endorsement violation must be proven independently of transport/auth failures; post-attempt state query required.
- S1: attack is counted only after gateway RF reception. Missed RF is INVALID, not rejection.
- S2: BLOCKED_BY_METHODOLOGY; do not invent a test.
- F1/F2: record planned, generator-achieved and target-observed rates; isolated fixtures only; 5-minute recovery after each condition.
- I1: trusted original hash and exact alteration injection boundary must exist before mutation.
- I2: pre-tamper DB/hash/Fabric evidence first; modify isolated rows only; ledger remains untouched.
- I3: distinguish Fabric transaction validity from anchor semantics; query original state after every duplicate/conflict attempt.
- T1/T2: reconstruct persisted DB/Fabric evidence; T2 uses 10 non-overlapping five-record sequences. Combined traceability = 20 trials / 60 records.

Formal manual release gate:
method frozen + harness exists + exact command rehearsal passes + required evidence seals + cleanup/restoration proven + documentation command audit passes.
