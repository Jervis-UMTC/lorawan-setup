# Final Cross-Technology Documentation, Secret and Command Audit — 2026-09-21

## Decision and scope

**Requested future deliverable: one comprehensive editable Word (.docx), later through OfficeCLI. Neither a PDF nor a Word document was generated during this audit.** Markdown and the commissioned implementation remain the source of truth. The legacy PDF publication/specification files now explicitly redirect to `WORD-PUBLICATION.md` and `STANDALONE-WORD-MANUAL-SPEC.md`; current operator guides use Word-document wording for the planned compilation.

This audit covers the 21 numbered guides, every companion Markdown in `deployment/technology-guides`, relevant current implementation/runbook/readiness sources, a privacy-preserving scan of non-archived project Markdown, command-block static/syntax checks, and **bounded read-only live verification** using the dedicated restricted SSH key. It does **not** commission a fresh cluster, restore from backup, change TLS identities, alter application deployment, generate traffic, or count research tests. Another agent owns active R2 research work; its evidence and experimental controls were not touched.

## 1. Live facts refreshed, not inferred

Read-only restricted SSH `version`, `snapshot`, `db-role` and `evidence-ready` ran at **2026-09-21 08:09–08:11 UTC** (16:09–16:11 Asia/Manila). Sanitized machine-readable observations are in `LIVE-READONLY-CHECKPOINT.json`.

| Layer | Verified at that instant | What the probe does not prove |
|---|---|---|
| Gateway-01 | Restricted SSH gateway wrapper v3; `wwan0` route present; **two established cloud MQTT :8883 sockets** | Fresh sensor OTAA/application delivery, byte-exact journal verification, cellular uptime across an outage |
| ULC-01 | Correct host; PostgreSQL reported **leader**; ChirpStack/etcd/Spilo/OpenBao/Seaweed/evidence containers visible; collector-1 READY; recorder wrapper **v10** | Permanent primary role, all three etcd/OpenBao voters/quorums, actual external HRC commit |
| ULC-02 | Correct host; PostgreSQL **replica**; ChirpStack and evidence verifier present; verifier-1 READY; recorder wrapper **v8** | Fabric enabled/disabled flag or image parity just from Docker presence, formal failover |
| ULC-03 | Correct host; PostgreSQL **replica**; Node-RED and Grafana containers visible; collector-2 and verifier-2 READY; recorder wrapper **v8** | One normalized real event, end-to-end SQL idempotency, counted run result |
| Workstation Grafana | Restricted tunnel `127.0.0.1:3000/api/health` HTTP **200**, `database=ok`, Grafana **13.2.0** | Authenticated dashboard UID, installed **panel count and refresh**; repository source 21 panels/10s, historical access note 14 panels/15s |

The source-level `research-recorder-server-v7` prose was stale as a statement about all deployed hosts. Guides 19 and the research companion now explicitly state **ULC-01 v10, ULC-02/03 v8, gateway v3** as dated observations, and require **per-host/per-verb** compatibility rather than pretending the fleet is uniform.

The latest generated research gate *inspected during this audit* was **2026-09-21 07:55:23 UTC**: overall technical gate PASS, gateway LTE PASS, Live PRE PASS, **PRE and P1 READY only**. The generated report may be updated by a separate research work session. Nothing in this audit promotes another experiment or calls a synthetic/non-counted rehearsal a counted Chapter IV run. Fabric adapter's previous ULC-01-enabled / ULC-02-disabled, build-parity-blocked state remains a **dated** commissioning/review claim until independently checked at actual Word-publication time. Likewise a successful dashboard health API is not a verified deployed 21-panel cockpit.

## 2. Cross-component consistency and corrections

The current Markdown authority now keeps the following cross-layer invariants: plain AS923 and `as923` prefix, actual gateway/device identities, intended SIM7600 `wwan0` production WAN with *no assumed automatic Wi-Fi fallback*, separate MQTT gateway/ChirpStack/Node-RED authentication and QoS, exactly one active Node-RED writer, etcd versus separate Seaweed metadata-etcd, current Patroni leader routing, verifier-owned v2 eligibility, immutable `finalized_payload` bytes, nonexportable OpenBao signing and only one governed Fabric adapter writer.

Specific corrections made or verified:
- Fixed the stale Wi-Fi fallback claim in the historical cloud continuation checkpoint, rather than relying only on the later technology baseline.
- Replaced old uniform recorder v7 status and an older 06:19 UTC readiness reference with the new **host-specific** wrappers and 07:55 UTC generated readiness checkpoint.
- Added the bounded 08:09–08:11 UTC live snapshot to `CURRENT-DOCUMENTATION-BASELINE.md`, separating proven role/service availability from unverified quorum, radio, signed evidence or Fabric finality.
- Retired old PDF instructions and linked a self-contained **Word/OfficeCLI** publication contract across the editable technology guides.
- Preserved the observed Grafana 13.2.0 **service** fact while leaving dashboard 14/21 panel-version resolution explicitly unverified until an authenticated readback.
- Preserved the ChirpStack 4.19.1 core PostgreSQL DSN `sslmode=require` + separate CA exception without weakening PgBouncer/Grafana's different `verify-full` settings.
- Did not recast pending/uncertain Fabric outbox, QoS-0 Node-RED failover, synthetic tests or adverse verifier states into a false success claim.

## 3. Credential leakage found and redacted

The final broader non-archived Markdown scan inspected **767** files after the corrections and this audit report was added. It initially found a historical credential-like literal in three lines of the build execution log and one status line of the Spilo/Patroni runbook, plus an inline database URL credential in the **old single-host testbed** manual. These **five actual plaintext occurrences were replaced with redaction or a protected-placeholder marker**; the relevant files remain otherwise intact. Two other URI matches were *already placeholders* and were not treated as leaked secret values. `SECRET-REDACTION-RECORD.json` records counts/paths **without copying credential values**.

The last check, `FINAL-REPOSITORY-MARKDOWN-SECRET-SCAN.json`, reports **zero potential unredacted matches** across its explicit non-archived Markdown scope; the 21 numbered technology guides and their companions also returned zero candidates. This is a pattern-based Markdown audit, **not a guarantee** about historical Git commits, raw research logs, hidden files, protected runtime env, other file formats or previously distributed copies. The credential-like text may still exist in **Git history** or earlier distributed material: coordinate rotation of any still-active affected credential and protected-backup update as a **separate operational change**; do not rewrite Git history, rotate secrets or restart a running research system as an undocumented side effect of a documentation audit.

No private credential values are reproduced in the present reports.

## 4. Commands, template safety and limitations

The final static rescan at **2026-09-21 08:29 UTC** covered **21 numbered guides / 51 Markdown files / 263 relative link targets**: zero missing local targets, zero unbalanced fences and zero secret-value candidates. Its four remaining dated-current-language heuristics point to passages explicitly marked with their observation dates or historical-source status, not to an assertion of continuous present health.

The technology Markdown static scanner observed **344 fenced blocks**, of which **208** are Bash/sh/PowerShell/SQL operator-oriented blocks, plus **21 lines using uppercase placeholder markers**. The final rescan found **zero** broken local link targets, zero unclosed fences, zero direct secret candidates, and zero unqualified dangerous-command patterns under its heuristics; four dated-language flags identify explicitly dated checkpoint/history statements, not current service failures.

The independent PowerShell AST parser, run through an approved non-script file-processing command without altering execution policy, parsed **34 of 34 PowerShell blocks** and found zero syntax errors. Markdown PowerShell *blocks were not executed*. Windows has no usable Linux Bash parser: its `C:\Windows\system32\bash.exe` candidate failed even a trivial `bash -n` smoke check. Thus **150 Bash/sh blocks were not Bash-syntax-certified** here. The automatic audit records `tool_unavailable=true`, not 150 false syntax failures. No `sudo`, SQL mutation, package install, failover, network reset or credential-rotation example was run on production to make a syntax result look like real acceptance.

**Word publication gate still applicable:** resolve each of the 21 placeholder lines into the actual approved non-secret host/path/value or visibly retain the label TEMPLATE; on a proper Linux/Bash-capable *isolated* toolchain do `bash -n` on approved shell blocks and inspect any conditional destructive operations. Reconcile those commands against actual effective host versions/permissions before describing them as copy/paste-ready. Runtime validation of every recovery/destructive command would be inappropriate against a healthy production system.

## 5. Residual verification needed only when appropriate

- **Authenticated Grafana UID/JSON readback:** distinguish the running dashboard panel count/refresh from the 21-panel tracked research JSON and old 14-panel access checkpoint. Health API alone cannot settle this.
- **Current Fabric standby parity and elected KMS/DB/storage quorum:** read exact version/digest, lease/fence/active roles from the affected live service before documenting a newly accepted takeover. This audit did not initiate the concurrently owned R2 experiment or any intentional failover.
- **PostgreSQL image/Timescale version divergence:** original image-package inspection versus later 18.6/2.29.2 checkpoint requires a fresh authorized runtime/config readback before a Word rebuild appendix claims current exact binaries.
- **Research methodology:** only currently READY tests get runnable formal Word operator blocks; S2 remains methodology-blocked until the research authority defines its counts/procedure/acceptance. Completed non-counted S1/F1/F2 and R2 rehearsals are not substituted for formal counts.
- **Destructive restore/cross-region DR and DigitalOcean Reserved IPv4 reassignment:** preserve the existing explicit open gates; do not run them merely to release documentation.
- **Git history exposure:** consider coordinated rotation for any credential shown in old tracked text, without assuming a working-tree redaction erases past copies.


## Final reconciliation addendum — 2026-09-21, 08:35 UTC

One further cross-document consistency correction changed the technology index's misleading `OpenBao seal/verify` phrase to **OpenBao Transit digest sign/verify**; routine signing is not a seal/unseal operation. Its full-rebuild dependency overview now places the independently initialized SeaweedFS raw-object storage and OpenBao KMS before application/evidence/adapter admission, consistent with the full end-to-end companion. A stale 06:19 UTC readiness passage was explicitly marked **earlier and superseded** by the separately dated 07:55 UTC generated gate.

The final targeted `git diff --check` across this task's technology guides and three credential-redacted source runbooks returned **exit 0**; Python audit-helper source compilation succeeded. Reusable static, secret and parse-only report files remain under this directory, and no current counted research assets or live service configuration was changed as part of the documentation task. The two tested general-purpose administrative SSH key attempts were **not authorized/failed**; production Bash syntax verification was *not* bypassed through the restricted research SSH identity. Keep the **150 Bash/sh blocks not yet syntax-certified** as an explicit future Word-publication gate, rather than calling them PASS.

Current output decision remains **Markdown only now, single self-contained Word document via OfficeCLI later when explicitly requested; no PDF**.

## 6. Final documentation artifacts and next publication stage

The editable guides and source companions are in `deployment/technology-guides/`. Key audit evidence: `FINAL-STATIC-AUDIT.json`, `FINAL-COMMAND-SYNTAX-AUDIT.json`, `FINAL-POWERSHELL-AST-AUDIT.json`, `FINAL-REPOSITORY-MARKDOWN-SECRET-SCAN.json`, `LIVE-READONLY-CHECKPOINT.json` and `SECRET-REDACTION-RECORD.json`.

The future Word source contract is [WORD-PUBLICATION.md](WORD-PUBLICATION.md) and [STANDALONE-WORD-MANUAL-SPEC.md](STANDALONE-WORD-MANUAL-SPEC.md). **No .pdf or .docx has been created. OfficeCLI will be used later when the user asks to assemble the Word document.**
