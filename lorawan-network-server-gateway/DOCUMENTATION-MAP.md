# Documentation Map

Use this page only to choose a path. The normal workflow is either `test/` or `deployment/`; do not mix their setup instructions.

---

## 1. Barebones Dissertation Testing

Start here:

[test/00-README.md](test/00-README.md)

The current testing track is split into **preparation** and **counted execution**. The preparation path builds and freezes the physical gateway, minimum server stack, two RAK4631 sensor roles, and test tools. Counted Chapter IV experiments start only after the dedicated sensor preflight records `SENSOR_PREFLIGHT_STATUS=GO`.

```text
test/
├── 00-README.md
├── preparation/
│   ├── 00-README.md
│   ├── gateway/      # Raspberry Pi 4B + RAK5146; hardware -> AS923 -> secure MQTT transport
│   ├── server/       # Ubuntu Server VM + minimum seven-service test stack
│   ├── sensor/       # EMU-01 legitimate physical sensor + SEC-02 security fixture
│   │   ├── assembly/ # physical Agriculture Kit bring-up and code reference
│   │   └── preflight/# final uncounted sensor -> ChirpStack -> DB/Fabric GO/NO-GO
│   └── tools/        # separate test laptop, generators, captures, resource logging
└── execution/
    ├── 00-README.md
    ├── 01-common-run-preparation.md
    ├── 02-normal-operation.md
    ├── 03-authentication-access-control.md
    ├── 04-replay-spoofing.md
    ├── 05-data-integrity.md
    ├── 06-traceability.md
    ├── 07-dos-flooding.md
    ├── 08-resilience-recovery.md
    └── 09-results-and-completion.md
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
OpenBao 3-node KMS normal path                                        PASS
telemetry.fabric_outbox database layer                                PASS
Node-RED A/B atomic-outbox runtime                                    PASS; A active, B fenced
Grafana server-only synthetic datasource/read path                    PASS; real EMU-01 still deferred
Gateway/security evidence-service source/runtime                      CURRENT IMPLEMENTATION PRIORITY
OpenBao audit device                                                   REQUIRED BEFORE FABRIC SIGNING CREDENTIALS
Phase 11/12 physical gateway/cutover                                  HARDWARE DEFERRED
Phase 12A real EMU-01 storage/replay acceptance                       HARDWARE DEFERRED
Full Fabric adapter + external handoff                                BLOCKED / implementation input
Phase 14B / Phase 15                                                   BLOCKED until required gates close
```

[19-cloud-ha-grafana-deployment-day-runbook.md](deployment/server/cloud-production/19-cloud-ha-grafana-deployment-day-runbook.md) remains the full target-sequence reference; it is not evidence that later technologies are already commissioned.

```text
deployment/
├── gateway/         # full Gateway OS setup, operations, and hardware references
│   ├── setup/       # delivery path + integrity journal when implementation exists
│   ├── operations/  # registration, backup/recovery, outage tests, migration, troubleshooting, RF, security
│   └── references/  # vendor/hardware references
└── server/
    ├── ha-cluster/  # reusable HA deployment manuals
    ├── data-layer/  # TimescaleDB, Node-RED, Grafana
    ├── fabric-attestation/ # Fabric handoff, OpenBao Transit, outbox/adapter, reconciliation
    ├── cloud-production/   # current three-Droplet HA build and live evidence log
    └── integrations/       # reusable technology and gateway-evidence contracts; gateway-integrity/04 is canonical topology, /07 is the implementation + HA placement blueprint
```

---

## 3. Presentations

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
