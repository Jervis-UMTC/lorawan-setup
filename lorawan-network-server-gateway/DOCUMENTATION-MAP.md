# Documentation Map

## Technology-by-technology architecture guides

For a concise explanation of each technology in the currently commissioned system, start with [`deployment/technology-guides/00-README.md`](deployment/technology-guides/00-README.md). It separates the edge OS/radio, LTE, MQTT, ChirpStack, etcd, PostgreSQL/Patroni/TimescaleDB, HAProxy/PgBouncer, Valkey/Sentinel, Node-RED, Grafana, OpenBao, SeaweedFS, gateway-evidence services, Hyperledger Fabric adapter, cloud/container runtime, and PKI/TLS service identity into individual guides while linking back to the detailed operational runbooks.

For any new documentation work, also read [`deployment/technology-guides/CURRENT-DOCUMENTATION-BASELINE.md`](deployment/technology-guides/CURRENT-DOCUMENTATION-BASELINE.md) first so historical commissioning states are not reintroduced as current instructions.

Use this page only to choose a path. The normal workflow is either `test/` or `deployment/`; do not mix their setup instructions.

---

## 1. Barebones Dissertation Testing

Start here:

[test/00-README.md](test/00-README.md)

The current testing track is split into **preparation** and **counted execution**. The preparation path builds and freezes the physical gateway, minimum server stack, two RAK4631 sensor roles, and test tools. Counted Chapter IV experiments start only after the dedicated sensor preflight records `SENSOR_PREFLIGHT_STATUS=GO`.

```text
test/
â”œâ”€â”€ 00-README.md
â”œâ”€â”€ automation/
â”‚   â””â”€â”€ research-recorder/ # supervised preflight, capture, sealing, recovery, and summaries
â”œâ”€â”€ preparation/
â”‚   â”œâ”€â”€ 00-README.md
â”‚   â”œâ”€â”€ gateway/      # Raspberry Pi 4B + RAK5146; hardware -> AS923 -> secure MQTT transport
â”‚   â”œâ”€â”€ server/       # Ubuntu Server VM + minimum seven-service test stack
â”‚   â”œâ”€â”€ sensor/       # EMU-01 legitimate physical sensor + SEC-02 security fixture
â”‚   â”‚   â”œâ”€â”€ assembly/ # physical Agriculture Kit bring-up and code reference
â”‚   â”‚   â””â”€â”€ preflight/# final uncounted sensor -> ChirpStack -> DB/Fabric GO/NO-GO
â”‚   â””â”€â”€ tools/        # separate test laptop, generators, captures, resource logging
â””â”€â”€ execution/
    â”œâ”€â”€ 00-README.md
    â”œâ”€â”€ 01-common-run-preparation.md
    â”œâ”€â”€ 02-normal-operation.md
    â”œâ”€â”€ 03-authentication-access-control.md
    â”œâ”€â”€ 04-replay-spoofing.md
    â”œâ”€â”€ 05-data-integrity.md
    â”œâ”€â”€ 06-traceability.md
    â”œâ”€â”€ 07-dos-flooding.md
    â”œâ”€â”€ 08-resilience-recovery.md
    â””â”€â”€ 09-results-and-completion.md
```

The frozen dissertation test-lab radio identity is **plain AS923** with MQTT region prefix **`as923`**. Do not change only one radio layer to AS923-3. Any future regional migration must be validated end to end across sensor firmware, RAK5146/Concentratord, MQTT topic prefix, ChirpStack region, and device profiles.

---

## 2. Full Deployment

Start here:

[deployment/00-README.md](deployment/00-README.md)

Use this path for the complete HA/integration architecture or production/cloud work. For the current real-cloud build, start with [deployment/server/cloud-production/00-current-server-continuation-checkpoint.md](deployment/server/cloud-production/00-current-server-continuation-checkpoint.md) first for the exact resume point, then [00-README.md](deployment/server/cloud-production/00-README.md) for the architecture/status map and [00-build-execution-log.md](deployment/server/cloud-production/00-build-execution-log.md) only when detailed historical evidence is needed.

Current cloud continuation boundary:

```text
Core HA: etcd + PostgreSQL/Patroni/TimescaleDB + HAProxy/PgBouncer   VALIDATED
Messaging: Mosquitto + Valkey/Sentinel + two-node ChirpStack         VALIDATED
Phase 13A fast backup/off-host transport                              PASS
OpenBao 3-node KMS + audit                                            PASS
telemetry.fabric_outbox database layer                                PASS
Node-RED A/B atomic-outbox runtime                                    PASS; A active, B fenced
Grafana server-only synthetic datasource/read path                    PASS; real EMU-01 deferred
SeaweedFS evidence storage S0-S9                                      PASS
Evidence migration/HBA/CONNECT/six LOGIN identities                   PASS
PgBouncer evidence SCRAM expansion                                    THREE-NODE PASS
Cloud evidence replicas / Evidence PKI / shared :443                  PASS
Public ChirpStack/Evidence/MQTT normal path                            PASS
Reserved-IP reassignment/failover authority                           EXTERNAL AUTH PENDING
Gateway-01 + RAK5146 + SIM7600 LTE + journal lineage                  PHYSICAL/LIVE PASS
EMU-01 AS923 OTAA + application path through TimescaleDB               LIVE PASS
Automated research recorder + hardware-aware preflight                 PASS
Scoped LoRaWAN Chapter 4 gate                                          LORAWAN_TRACK_STATUS=GO
Fabric / HRC Task 37 qualification                                     PASS
Fabric adapter ULC-01 production writes                               PASS; enabled and verified
Fabric adapter ULC-02                                                  WRITE-DISABLED; HA fencing/ownership gate remains
Research experiment gates                                              FOLLOW CURRENT test/ GO/NO-GO FILES
```

For current research work, start with [test/00-README.md](test/00-README.md), use the [automated research recorder](test/automation/research-recorder/README.md), then follow the selected [counted execution manual](test/execution/00-README.md). Use the concise [current state board](deployment/server/cloud-production/00-current-server-continuation-checkpoint.md) for broader cloud/server context. Real Gateway-01, LTE, EMU-01, and evidence-lineage acceptance are complete. [docs/archive/2026-09-02-sensor-gateway-bringup-handoff.md](docs/archive/2026-09-02-sensor-gateway-bringup-handoff.md) is retained only as the historical 2026-09-02 bring-up handoff, and `00-build-execution-log.md` remains detailed historical evidence.

[19-cloud-ha-grafana-deployment-day-runbook.md](deployment/server/cloud-production/19-cloud-ha-grafana-deployment-day-runbook.md) remains the full target-sequence reference; it is not evidence that later technologies are already commissioned.

```text
deployment/
â”œâ”€â”€ gateway/         # full Gateway OS setup, operations, and hardware references
â”‚   â”œâ”€â”€ setup/       # delivery path + integrity journal when implementation exists
â”‚   â”œâ”€â”€ operations/  # registration, backup/recovery, outage tests, migration, troubleshooting, RF, security
â”‚   â””â”€â”€ references/  # vendor/hardware references
â””â”€â”€ server/
    â”œâ”€â”€ ha-cluster/  # reusable HA deployment manuals
    â”œâ”€â”€ data-layer/  # TimescaleDB, Node-RED, Grafana
    â”œâ”€â”€ fabric-attestation/ # Fabric handoff, OpenBao Transit, outbox/adapter, reconciliation
    â”œâ”€â”€ cloud-production/   # current three-Droplet HA build and live evidence log
    â””â”€â”€ integrations/       # reusable technology and gateway-evidence contracts; gateway-integrity/04 is canonical topology, /07 is the implementation + HA placement blueprint
```

---

## 3. Implementation, Evidence, Firmware, and History

These are supporting roots rather than alternate deployment tracks:

- [evidence-services/README.md](evidence-services/README.md) â€” gateway/cloud evidence-service implementation boundary and current commissioned state.
- [evidence-services/BUILD.md](evidence-services/BUILD.md) â€” reproducible Go/Rust build and cache/toolchain rules.
- [firmware/EMU01_Agriculture_Node/README.md](firmware/EMU01_Agriculture_Node/README.md) â€” tracked EMU-01 firmware source/profile contract.
- [chapter4-results/README.md](chapter4-results/README.md) â€” retained research-evidence layout and immutability rules.
- [docs/README.md](docs/README.md) â€” dated plans and preserved historical artifacts; not current runtime truth.

Repository hygiene rule: generated compiler/toolchain/cache trees under `evidence-services/` and Python `__pycache__/` directories are reproducible and disposable. `chapter4-results/` is the opposite: it contains research evidence and must never be included in generic cleanup. The identical gateway hardware-assembly guide present in both deployment and dissertation preparation paths is intentionally retained as a workflow-local mirror rather than deduplicated at the cost of navigation clarity.

---

## 4. Presentations

Start here:

[presentations/2026-08-07-weekly-standup.html](presentations/2026-08-07-weekly-standup.html)

Contains presentation slide decks and weekly technical updates.

---

## Values to Retain Across Deployment

```text
Gateway EUI (16-hexadecimal ID)
Device EUI & OTAA root keys
Exact validated regional channel plan and MQTT region prefix
MQTT server FQDN, CA.crt, and client certificates
4G/LTE dongle model, carrier/APN reference, and tested gateway interface/route
Grafana image/digest, dashboard backup/provisioning reference, and telemetry_reader role reference
Fabric endpoint, MSP ID, channel, chaincode, and function names
OpenBao Transit key version & endpoint
TimescaleDB backup path & SHA-256 checksums
```

> [!CAUTION]
> Never place private keys, OTAA AppKeys, passwords, tokens, or OpenBao recovery shares in Markdown files or public repositories.


