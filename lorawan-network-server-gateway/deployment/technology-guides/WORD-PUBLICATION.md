# Comprehensive Word Manual — Future OfficeCLI Publication Plan

## Deliverable decision

The user selected **one complete editable Word (.docx) manual**, to be created **later through the OfficeCLI connector/extension**. **Do not generate a PDF or Word document during the present audit.** The repository Markdown is canonical and must remain editable independently of any future Word copy.

The specification is [STANDALONE-WORD-MANUAL-SPEC.md](STANDALONE-WORD-MANUAL-SPEC.md). The source index is [00-README.md](00-README.md); final review is [FINAL-CROSS-TECHNOLOGY-AUDIT-2026-09-21.md](FINAL-CROSS-TECHNOLOGY-AUDIT-2026-09-21.md).

## Incremental OfficeCLI build status — 21 September 2026

The user subsequently authorized **starting** the Word manual, one chapter at a time, with genuine screenshot evidence. Stage 1 now exists at `../../documentation/LoRaWAN-Operator-Manual-WIP.docx`: editable A4 cover, updateable contents, eleven-section Chapter 1 with native tables, a real credential-empty Grafana login screenshot, safe command and data-lineage/failure guidance. See `../../documentation/word-src/CHAPTER-PROGRESS.md` for staged source/QA and Gateway OS next steps. This file is an **unfinished evolving Word document**, not the promised full manual. Continue extending the SAME file on future chapter work, refreshing TOC and validating all changed pages. No PDF was generated for the user.

## Source inclusion

The Word file shall print all necessary content from:
- 21 numbered operator guides 01–21, including the integration guide and its full companion.
- Commissioned installation/recovery companions for every technology (Gateway, radio, LTE, cloud MQTT, ChirpStack, etcd, PostgreSQL/Patroni/TimescaleDB, HAProxy/PgBouncer, Valkey/Sentinel, Node-RED, Grafana, OpenBao, SeaweedFS, gateway evidence, Fabric, PKI, cloud runtime, EMU, SEC and research).
- Actual approved command/script/configuration appendices and the current test Chapter III methodology, test-specific gate/readiness, researcher observation commands and measured-unit definitions.
- Backup/restore, security, disaster recovery, topology and reliable cross-technology troubleshooting.
- Provenance/dated live snapshot, document version, redacted credential locations, software image/config hashes.

**Do not paste unverified historical sample commands as directly executable instructions.** Code-only and non-counted test results must not appear as completed counted trials, and blocked methodology such as S2 must remain explicit.

## Publication-time process (future request only)

1. Refresh dated operational facts and compare with repository runbooks and active versions using targeted read-only checks, without re-running disruptive tests to assemble a book.
2. Run the checked-in static audit helpers, inspect all secrets/placeholder/command findings, and review exact-meaning radio, TLS, metric, identity and Fabric fields.
3. Use the OfficeCLI connector to construct/edit one .docx, apply Word styles/automatic TOC/captions/cross-references, repeat table headers, preserve copyable commands, and include internal rather than mandatory Markdown navigation.
4. Inspect complete rendered Word document with the supported OfficeCLI preview/inspection, not only its first page. Verify all tables, headings, diagrams, code and research tables for clarity and truncation, update field-generated TOC and page numbers.
5. Create a release manifest with source and .docx SHA-256 hashes, generation timestamp and remaining historical/unverified facts, preserving the Markdown source of truth.

No PDF workflow is part of the requested publication.
