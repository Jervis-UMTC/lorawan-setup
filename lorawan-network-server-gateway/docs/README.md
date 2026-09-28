# Documentation History and Archive Index

This directory holds preserved historical/provenance material. It is **not** the primary operator path for the live LoRaWAN system.

For current work, start at [`../00-README.md`](../00-README.md) or [`../DOCUMENTATION-MAP.md`](../DOCUMENTATION-MAP.md), then stay inside either the `test/` or `deployment/` workflow that matches the objective.

## Layout

```text
docs/
|-- README.md
`-- archive/
    |-- 2026-09-02-sensor-gateway-bringup-handoff.md
    |-- 2026-09-02-server-hardening-snapshot.txt
    |-- plans/
    |   |-- 2026-09-02-sensor-gateway-readiness-design.md
    |   `-- 2026-09-02-sensor-gateway-readiness-plan.md
    `-- thesis-source/
        |-- Chapter 3_extracted.txt
        `-- Chapter 4_extracted.txt
```

The old readiness plans and next-day bring-up handoff are retained for provenance only. Their future-tense wording and intermediate status assertions must not override later live acceptance evidence. Raw thesis extracts are likewise retained only as source/provenance material; the working thesis revisions remain at repository root as `Chapter 3_refined.md` and `Chapter 4_refined.md`.

## Preservation rule

- Archive completed plans/handoffs when they still explain an important decision; do not leave them beside current operator entry points.
- Keep current operating truth in the relevant deployment/test runbook or current-state board.
- Keep detailed commissioning chronology in the build/execution log rather than duplicating it in current-state files.
- Never rewrite or delete sealed Chapter 4 research evidence merely to simplify documentation.
- Generated caches/build trees may be disposable; `chapter4-results/` is not.
