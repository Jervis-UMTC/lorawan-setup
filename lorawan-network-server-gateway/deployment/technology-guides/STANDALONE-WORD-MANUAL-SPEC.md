# Standalone Comprehensive Word Manual — Source and Acceptance Specification

**Publication decision (2026-09-21):** the final deliverable will be **one comprehensive editable Microsoft Word document (.docx)**, assembled later using the user's **OfficeCLI connector/extension**. Do not create a PDF or DOCX during this documentation audit. Markdown remains the source of truth; this document defines the later Word build, not a claim that one exists.

## Required writing style — revised at user request

Each technology chapter must be practical and concise: **What it does → Prerequisites → Numbered setup instructions → Exact host/shell and command or UI action → Expected result → Short troubleshooting/recovery**. Embed a screenshot or hardware image only when it **shows the specific action or component the adjacent numbered step describes**, with a brief source-credited caption; a picture highlighting Raspberry Pi OS cannot illustrate **Use custom**, a different vendor cellular HAT cannot illustrate this project's SIM7600, and a stock EU868 screen cannot illustrate this gateway's AS923. The Chapter 1 diagram must show both telemetry and independent gateway journal/MQTT witness/SQL verification paths, not merely a generic IoT cloud chain. Keep full necessary technical detail, but omit repeated research disclaimers, lengthy editorial explanations, unnecessary background theory, and progress reports from the operator-facing Word text. Complete one chapter, inspect its layout and commands, then continue to the next chapter. Chapter 1 is only a compact system overview and setup order; the Grafana login screenshot is reserved for the Grafana chapter. This supersedes the earlier verbose Word draft.

## Content the Word file must contain

The Word reader must not need this repository or an external Markdown file to install, configure, observe, troubleshoot, measure or restore the project. Copy the necessary exact commands, descriptions, expected outcomes, cautions, configurations, and recovery steps into the book. Documentation links are editorial provenance and may be printed as optional sources, not mandatory instructions.

1. Project objective, architecture, terminology, reader orientation and system ownership.
2. Hardware inventory, actual EMU-01/SEC module assembly, fixed slot/IO map, safe power/wiring, firmware, DFU and physical acceptance.
3. Gateway OS accepted image, RAK5146/Concentratord, AS923 radio, MQTT Forwarder, gateway EUI and exact regional parameters from commissioned configs.
4. SIM7600/QMI LTE route policy, normal WAN operation, local Mosquitto queue, mTLS bridge and failure/recovery behavior.
5. ULC-01/02/03 host inventory, Ubuntu, DigitalOcean VPC/Reserved IPv4, firewall, SSH, filesystem ownership, Docker/Compose and resource management.
6. etcd, PostgreSQL/Patroni/TimescaleDB, HAProxy/PgBouncer and Valkey/Sentinel, distinct membership/leader/failover and restore boundaries.
7. Cloud Mosquitto identity separation, two-node ChirpStack, gateway/EMU provisioning, protected OTAA material custody and application MQTT paths.
8. Node-RED one-writer flow, exact telemetry schema/field mapping, input evidence and transactional outbox.
9. Gateway integrity journal/uploader, two cloud-broker witnesses, ingest/collector/verifier roles, trusted decoder and SeaweedFS raw objects.
10. OpenBao Raft/Transit/AppRole, PKI/TLS service identities, Fabric HRC source-bound exact-payload transaction and reconciliation/fencing.
11. Grafana read-only data source, private workstation tunnel, dashboard panels with explicit units, stale/no-data conditions and source-vs-live version distinction.
12. Deployment sequence, normal operations, monitoring, backups, single-host failure, non-destructive troubleshooting, rollback and disaster recovery.
13. Research test preparation, readiness gates, supervised recorder, **full Chapter III test conditions, exact denominators, units and interpretation**, distinguished from non-counted rehearsals.
14. Appendices: actual version/digest/listener/certificate-location inventory, complete approved commands and expected outputs, region/payload tables, safety decision trees, glossary, Word-source manifest and references.

## Editorial and technical requirements

- Use **Word Heading styles**, an updateable TOC, numbered captions, tables that repeat headers, page numbers and meaningful cross-references within the same document.
- Clearly label command shell and current working directory for **OpenWrt BusyBox**, **Ubuntu Bash** and **Windows PowerShell**. Each runnable command block must name prerequisites, expected PASS/FAIL and safe recovery; a sample with placeholders must be explicitly a template.
- Protect passwords, tokens, OTAA AppKeys, OpenBao recovery shares and private keys. Explain protected *locations* and authorized retrieval/rotation, never disclose raw values.
- Preserve plain AS923 and exact project EUI/DevEUI/payload contract, current auth boundaries, MQTT QoS distinction, one Node-RED writer and one governed enabled Fabric adapter.
- Clearly distinguish historical commissioning, read-only live observations (timestamp/host/probe), synthetic code qualifications, real non-counted trials, released READY test interfaces and completed formal counted trials.
- Do not invent missing research methodology (notably S2), fake positive outcomes, hide gaps/dead-letter status, or substitute Grafana screenshots for sealed recorder results.
- Write all units as human-readable labels: RAM MiB used/total, network Mbps, RF RSSI dBm/SNR dB, pressure Pa/kPa with numerical conversion and battery USB sentinel as unavailable.

## OfficeCLI Word build — deferred

**Only after an explicit future user instruction**, use the OfficeCLI connector/extension to assemble the complete Markdown source and approved research runbooks into one .docx. Preserve editable tables, copyable code and searchable text. Do not use PDF as the requested deliverable, and do not create a DOCX as part of this audit.

After that build, inspect in Word or the OfficeCLI-supported preview for correct pagination, updateable TOC, images/diagrams without clipping, table/code wrapping, internal cross-references, missing source sections, spelling of identity/contract names and checksum manifest. Record both source and .docx hashes with build timestamp. If later publication needs a separate PDF, that requires a separate user request.

## Current pre-publication stop conditions

- Unreconciled live/provisioned version or image differences: label as **dated** and provide the precise fresh evidence when available.
- Unqualified conditional or destructive recovery command presented as an ordinary quick check.
- Missing/invalid link, inconsistent radio/metric field, syntax failure or unresolved secret candidate.
- Missing exact command context, unresolved placeholder or non-ready formal test disguised as runnable.
- Claiming the tracked Grafana 21-panel JSON is deployed without authenticated live UID comparison.

The final read-only documentation audit report and its limitations are in `FINAL-CROSS-TECHNOLOGY-AUDIT-2026-09-21.md`, when available. It does not replace the operational runbooks.
