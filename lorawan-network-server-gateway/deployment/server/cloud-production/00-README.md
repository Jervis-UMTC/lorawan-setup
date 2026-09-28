# Cloud Production Documentation

> For technology-oriented documentation rather than deployment chronology, see [`../../technology-guides/00-README.md`](../../technology-guides/00-README.md). The guides explain each deployed technology separately and link back here for detailed commissioning and recovery procedures.

This directory is the operator and recovery documentation for the commissioned three-server LoRaWAN cloud deployment. The numbered files are component manuals; they are not a chronological diary.

**Current truth:** read [`00-current-server-continuation-checkpoint.md`](00-current-server-continuation-checkpoint.md) first. Use [`00-build-execution-log.md`](00-build-execution-log.md) only for historical commissioning evidence and troubleshooting provenance.

## Current boundary - through 2026-09-17

| Layer | Status |
|---|---|
| etcd | VALIDATED, 3-node quorum |
| PostgreSQL / Patroni / TimescaleDB | VALIDATED HA cluster |
| HAProxy / PgBouncer | VALIDATED routing/authentication |
| Mosquitto | VALIDATED preferred/backup path |
| Valkey / Sentinel | VALIDATED HA path |
| ChirpStack | VALIDATED two-node cluster, plain AS923 |
| OpenBao | VALIDATED 3-node KMS + audit |
| Node-RED | VALIDATED; A active on ULC-03, B fenced on ULC-02 |
| Grafana | VALIDATED application/evidence read path |
| Gateway evidence services | VALIDATED replicated ingest/collector/verifier/storage path |
| Gateway-01 / EMU-01 | LIVE PASS including RF, LTE backhaul, telemetry and evidence lineage |
| Fabric | **ULC-01 production writer PASS; ULC-02 write-disabled pending HA fencing/ownership acceptance** |
| Public Reserved IPv4 path | Normal path PASS; controlled reassignment/failover acceptance remains separate |
| Research recorder | Operational; follow current `test/` gates for counted work |
| Current Fabric-outbox research eligibility | Diagnose upstream `finalized_payload` + v2 verifier eligibility before Fabric; `pending`/`attempts=0` alone is not an adapter failure |

Do not infer current state from an older dated paragraph in a component manual. If a component manual describes a previous commissioning boundary, the current-state file above wins unless live verification proves otherwise.

## Component manuals

| Manual | Purpose / current role |
|---|---|
| [`01-architecture-decisions-and-scope.md`](01-architecture-decisions-and-scope.md) | Architecture constraints and design decisions |
| [`02-capacity-cost-and-ip-plan.md`](02-capacity-cost-and-ip-plan.md) | Resource/cost/IP baseline |
| [`02a-digitalocean-machine-layout-and-specs.md`](02a-digitalocean-machine-layout-and-specs.md) | Droplet layout/specification baseline |
| [`03-digitalocean-vpc-droplets-and-firewalls.md`](03-digitalocean-vpc-droplets-and-firewalls.md) | DigitalOcean VPC, public ingress, firewall foundation |
| [`04-host-hardening-dns-pki-and-secrets.md`](04-host-hardening-dns-pki-and-secrets.md) | Host hardening, DNS, PKI, secret layout |
| [`04a-host-security-hardening-execution-runbook.md`](04a-host-security-hardening-execution-runbook.md) | Reproducible hardening procedure |
| [`05-etcd-cluster.md`](05-etcd-cluster.md) | etcd cluster deployment/recovery |
| [`06-spilo-patroni-postgresql-cluster.md`](06-spilo-patroni-postgresql-cluster.md) | PostgreSQL/Patroni/TimescaleDB HA |
| [`07-haproxy-and-pgbouncer.md`](07-haproxy-and-pgbouncer.md) | Database routing and pooling |
| [`08-mqtt-and-valkey.md`](08-mqtt-and-valkey.md) | MQTT and Valkey/Sentinel service layer |
| [`09-chirpstack-cloud-cluster.md`](09-chirpstack-cloud-cluster.md) | ChirpStack cloud cluster |
| [`10-self-managed-public-ingress.md`](10-self-managed-public-ingress.md) | Reserved-IP/DNS/TLS ingress and failover design |
| [`11-raspberry-pi-4g-backhaul.md`](11-raspberry-pi-4g-backhaul.md) | Gateway LTE primary/fallback routing |
| [`12-gateway-and-device-migration.md`](12-gateway-and-device-migration.md) | Gateway/device provisioning and migration |
| [`12a-node-red-timescale-telemetry.md`](12a-node-red-timescale-telemetry.md) | Node-RED -> TimescaleDB + Fabric outbox application path |
| [`13-backup-restore-and-disaster-recovery.md`](13-backup-restore-and-disaster-recovery.md) | Backup, restore, recovery acceptance |
| [`14a-grafana-cloud-deployment.md`](14a-grafana-cloud-deployment.md) | Grafana deployment and datasource boundary |
| [`14-observability-alerting-and-logging.md`](14-observability-alerting-and-logging.md) | Observability and logging |
| [`14b-pre-test-commissioning-gate.md`](14b-pre-test-commissioning-gate.md) | Full pre-test gate |
| [`15-failover-chaos-and-acceptance-testing.md`](15-failover-chaos-and-acceptance-testing.md) | Intentional failure/failover acceptance |
| [`16-operations-upgrades-and-scaling.md`](16-operations-upgrades-and-scaling.md) | Operations, maintenance, scaling |
| [`17-troubleshooting.md`](17-troubleshooting.md) | Symptom-driven troubleshooting |
| [`18-runbook-and-handoff-checklists.md`](18-runbook-and-handoff-checklists.md) | Operational handoff checklist |
| [`19-cloud-ha-grafana-deployment-day-runbook.md`](19-cloud-ha-grafana-deployment-day-runbook.md) | **Historical/sequence reference**; not current status authority |
| [`20-openbao-and-fabric-adapter.md`](20-openbao-and-fabric-adapter.md) | Current OpenBao/Fabric adapter operations and HA boundary |
| [`20a-openbao-three-node-ha-deployment.md`](20a-openbao-three-node-ha-deployment.md) | OpenBao three-node deployment/recovery |
| [`00-build-execution-log.md`](00-build-execution-log.md) | Historical detailed commissioning evidence; not current-state authority |

## Commissioned service placement

```text
ULC-01
  etcd-1
  Patroni/PostgreSQL-1
  HAProxy + PgBouncer
  ChirpStack-1
  Mosquitto preferred
  Valkey-1 + Sentinel-1
  OpenBao-1
  evidence ingest / collector placement
  Fabric adapter production writer (enabled)

ULC-02
  etcd-2
  Patroni/PostgreSQL-2
  HAProxy + PgBouncer
  ChirpStack-2
  Mosquitto backup
  Valkey-2 + Sentinel-2
  OpenBao-2
  Node-RED B fenced standby
  evidence ingest / verifier placement
  Fabric adapter standby (write-disabled)

ULC-03
  etcd-3
  Patroni/PostgreSQL-3
  HAProxy + PgBouncer
  Valkey-3 + Sentinel-3
  OpenBao-3
  Node-RED A active
  Grafana
  evidence collector / verifier placement
```

The telemetry database is part of the Patroni PostgreSQL cluster; TimescaleDB is an extension, not a separate database server. `telemetry.fabric_outbox` is an ordinary transactional table and Fabric submission is asynchronous.

## Current application and evidence flow

```text
FIELD
EMU-01 -> AS923 RF -> Raspberry Pi 4B + RAK5146
       -> local MQTT buffer -> mTLS over SIM7600 LTE -> cloud Mosquitto
       -> ChirpStack -> Node-RED -> TimescaleDB -> Grafana
                                  `-> Fabric outbox -> Fabric Adapter -> OpenBao seal/verify -> HRC Fabric

Gateway journal + MQTT witness + application telemetry
       -> Evidence ingest/collectors/verifiers -> trusted decoder -> retained evidence storage
```

The gateway normal path is health-gated LTE primary with Wi-Fi fallback; Ethernet is management-only. MQTT uses a preferred broker plus backup because the two brokers do not replicate live sessions; do not restore round-robin routing.

## Deployment/recovery principles

- Use Ubuntu Server 24.04 LTS x64 (`ubuntu-24-04-x64`) for the commissioned cloud hosts unless an intentional migration is being performed.
- Keep the same pinned TimescaleDB extension version on all Patroni members.
- Preserve private VPC traffic and the narrow Docker-to-host-private firewall allowances documented by the relevant manuals.
- Never put private keys, passwords, OTAA root keys, OpenBao recovery shares, or secret-bearing transient qualification material in Markdown.
- Do not broaden ULC-02 Fabric enablement until its HA fencing/ownership boundary is accepted.
- Do not broadly replay historical Fabric outbox rows that predate exact finalized-payload retention.
- Treat `chapter4-results/` as research evidence, not disposable generated output.
- Match verification to the change: do not repeat disruptive HA/failover tests after documentation-only edits.

## Research execution

Production/cloud documentation describes the deployed infrastructure. Dissertation experiment procedure is authoritative under [`../../../test/`](../../../test/00-README.md). Use the automated research recorder and the selected `test/execution/` manual for measured runs; do not improvise test procedure from this deployment directory.
