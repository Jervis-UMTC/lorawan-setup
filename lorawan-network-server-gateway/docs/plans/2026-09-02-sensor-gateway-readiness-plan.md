# Sensor + Gateway Readiness Implementation Plan

**Goal:** leave one coherent current-state documentation path and a tracked final EMU-01 firmware candidate for tomorrow's hardware bring-up.

1. Inventory checkpoint/status references and preserve the build execution log as historical evidence.
2. Delete clearly superseded Phase 11 chat checkpoint and repair references to it.
3. Rewrite the current server continuation checkpoint into concise current truth, removing superseded implementation claims.
4. Correct stale gateway build status and sensor soil-status prose without erasing useful failure history.
5. Add `firmware/EMU01_Agriculture_Node/` with payload-v2 helpers, integrated sensor readers, local-secret template, and final sketch.
6. Add static host tests for payload-v2 byte order/length/validity contract and secret hygiene; run them before claiming repository readiness.
7. Add one `TOMORROW-SENSOR-GATEWAY-BRINGUP.md` operator runbook with explicit stop/pass gates.
8. Update documentation map/root/deployment entry points to point to the new runbook/current state and remove stale checkpoint links.
9. Search repository Markdown for known superseded claims (`ACTIVE / NOT YET PASS`, old missing-runtime statements, invalid soil current-state language) and reconcile operator-facing occurrences.
10. Run repository diff/status, static firmware tests, Markdown-link/status sanity searches, and review the final patch before completion.
