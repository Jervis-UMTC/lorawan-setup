# Documentation Map

Use this page only to choose a path. The normal workflow is either `test/` or `deployment/`; do not mix their setup instructions.

---

## 1. Barebones Dissertation Testing

Start here:

[test/00-README.md](test/00-README.md)

Designed for collecting Chapter IV experimental test results (Tables 12–17) on a resource-constrained test host:

```text
test/
├── gateway/         # Barebones physical gateway setup for testing (01-06)
│   ├── 01-hardware-assembly.md
│   ├── 02-install-chirpstack-gateway-os.md
│   ├── 03-configure-concentratord.md
│   ├── 04-configure-local-mqtt-buffer.md
│   ├── 05-configure-mqtt-forwarder.md
│   └── 06-verify-gateway-os.md
└── server/
    └── suite/       # minimum server build + Chapter III/IV test manuals
        ├── 01-build-minimum-testbed.md
        ├── 02-common-test-preparation.md
        ├── 02a-prepare-test-tools.md
        ├── 02b-configure-rak4631-emulators.md  # EMU-01 legitimate sensor + SEC-02 security node
        ├── 03-normal-operation.md        -> Section 3.2.4 / 4.2 (PDR, Latency, TSR, Throughput, CPU/RAM)
        ├── 04-authentication-access-control.md -> Section 3.2.6.1 / 4.3.1 (Table 12: 90 trials)
        ├── 05-replay-spoofing.md         -> Section 3.2.6.2 / 4.3.2 (Table 13: 40 attempts)
        ├── 06-data-integrity.md          -> Section 3.2.6.3 / 4.3.3 (Table 14: 40 attempts)
        ├── 07-traceability.md            -> Section 3.2.6.4 / 4.3.4 (Table 15: 20 trials / 60 rec)
        ├── 08-dos-flooding.md            -> Section 3.2.6.5 / 4.3.5 (Table 16: 18 runs)
        ├── 09-resilience-recovery.md     -> Section 3.2.6.6 / 4.3.6 (Table 17: 3 x 2-hr runs)
        └── 10-results-and-completion.md -> Compile final Chapter IV result tables
```

---

## 2. Full Deployment

Start here:

[deployment/00-README.md](deployment/00-README.md)

Use this path for the complete HA/integration architecture or production/cloud work. For the current real-cloud build, start with [deployment/server/cloud-production/00-README.md](deployment/server/cloud-production/00-README.md), then read [00-build-execution-log.md](deployment/server/cloud-production/00-build-execution-log.md) to see what is actually validated. Continue only with the next active numbered phase. [19-cloud-ha-grafana-deployment-day-runbook.md](deployment/server/cloud-production/19-cloud-ha-grafana-deployment-day-runbook.md) is the full target sequence reference while later technologies remain on standby.

```text
deployment/
├── gateway/         # full Gateway OS setup, operations, and hardware references
│   ├── setup/       # delivery path + integrity journal when implementation exists
│   ├── operations/  # registration, backup/recovery, outage tests, migration, troubleshooting, RF, security
│   └── references/  # vendor/hardware references
└── server/
    ├── ha-cluster/  # etcd, Patroni/PostgreSQL, HAProxy, PgBouncer, Mosquitto, Valkey, ChirpStack
    ├── data-layer/  # TimescaleDB, Node-RED, Grafana
    ├── fabric-attestation/ # Fabric handoff, OpenBao Transit, outbox/adapter, reconciliation
    ├── cloud-production/   # production architecture + full-stack cloud simulation
    └── integrations/       # reusable technology and gateway-evidence contracts
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
Regional channel plan ( Philippines AS923 / AS923-1 )
MQTT server FQDN, CA.crt, and client certificates
4G/LTE dongle model, carrier/APN reference, and tested gateway interface/route
Grafana image/digest, dashboard backup/provisioning reference, and telemetry_reader role reference
Fabric endpoint, MSP ID, channel, chaincode, and function names
OpenBao Transit key version & endpoint
TimescaleDB backup path & SHA-256 checksums
```

> [!CAUTION]
> Never place private keys, OTAA AppKeys, passwords, tokens, or OpenBao recovery shares in Markdown files or public repositories.
