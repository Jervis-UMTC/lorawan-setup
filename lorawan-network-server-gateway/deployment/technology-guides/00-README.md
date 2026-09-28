# Technology Guides — Current LoRaWAN Deployment

These files are the **technology-by-technology operator manuals** for the commissioned LoRaWAN infrastructure. They are written so that an operator can start with no assumed knowledge of the stack, identify the correct host, run safe checks in order, understand the expected result, and know where to continue when a check fails.

## Read this first

New to the system? Start with the [first-day operator walkthrough](OPERATOR-FIRST-DAY.md). The [final cross-technology/secret/command audit](FINAL-CROSS-TECHNOLOGY-AUDIT-2026-09-21.md) records the latest read-only live checks, redactions, remaining gates and Word-only publication decision; the [earlier progressive oversight audit](GUIDE-OVERSIGHT-AUDIT-2026-09-21.md) preserves the documentation-consolidation history. The [standalone Word manual specification](STANDALONE-WORD-MANUAL-SPEC.md) defines the future comprehensive editable Word (.docx) document, to be assembled later using the OfficeCLI connector. No Word or PDF artifact is generated in the present audit.

The documentation authority order is:

1. verified live runtime state;
2. [`../server/cloud-production/00-current-server-continuation-checkpoint.md`](../server/cloud-production/00-current-server-continuation-checkpoint.md);
3. current code, migrations, tests, service units, Compose files, and configuration in this repository;
4. these technology guides and their linked component runbooks;
5. build logs and archives only as historical evidence.

Before changing these manuals, read [`CURRENT-DOCUMENTATION-BASELINE.md`](CURRENT-DOCUMENTATION-BASELINE.md). It freezes the current AS923 wording, Fabric Task 37 contract, evidence eligibility rules, writer boundary, and other facts that must not regress into obsolete documentation.

For the later **single self-contained comprehensive Word document (.docx)**, see [WORD-PUBLICATION.md](WORD-PUBLICATION.md). Markdown remains the editable source of truth; the OfficeCLI connector will be used only when the user separately requests the document.

## How to use every guide

Follow the guide from top to bottom. Do not skip directly to a restart or configuration edit.

1. Read **What this technology does** so you know what layer you are testing.
2. Read **Where it runs** and make sure your shell is on the correct machine.
3. Run **Safe health check** before changing anything.
4. Compare the output with **PASS means**. A process being `running` is not enough when the guide also requires a real protocol or data-path check.
5. If a check fails, use **Troubleshooting order** from the first failing layer outward. Do not change healthy downstream components to compensate for an upstream failure.
6. Before any mutation, take the backup or rollback step named in the guide.
7. Make one related change at a time, validate syntax/configuration when the technology supports it, then reload/restart only the affected service.
8. Run **Post-change verification**. Stop if it fails and either repair the change or use the documented rollback.
9. Use the linked deployment/recovery runbook for full rebuilds, migrations, destructive recovery, or intentionally disruptive HA tests.

## Command conventions

- `Gateway-01` commands use the OpenWrt/BusyBox shell and normally run as `root`.
- `ULC-01`, `ULC-02`, and `ULC-03` commands use Ubuntu and normally run as `opsadmin`; use `sudo` only where shown or required.
- Never paste a placeholder such as `<PASSWORD>`, `<TOKEN>`, `<PRIVATE_KEY>`, `<DOMAIN>`, or `<HOST>` literally into a production command. Resolve it from the current protected configuration first.
- Never print private-key bodies, passwords, OpenBao recovery material, Fabric enrollment secrets, OTAA root keys, or unrestricted DSNs into terminals that are being recorded.
- Read-only checks come before state-changing commands.
- Do not run a failover, reboot, package upgrade, database restore, queue purge, or destructive reset merely to prove a documentation edit.

## Commissioned gateway rebuild companions

- [Gateway OS, hardware and protected restore](GATEWAY-REBUILD-AND-RECOVERY.md)
- [RAK5146, plain AS923 and radio/MQTT handoff](RAK5146-AS923-COMMISSIONING.md)
- [SIM7600/QMI, LTE route policy and staged recovery](SIM7600-LTE-COMMISSIONING.md)

These consolidate prerequisites and recovery previously scattered across gateway/setup and gateway/operations. Continue to treat dated observed service health as a checkpoint rather than today's live proof.

## Commissioned MQTT and network-server companions

- [Mosquitto on the gateway and cloud; security, routing, HA and restore](MQTT-INSTALLATION-SECURITY-RECOVERY.md)
- [ChirpStack two-node deployment, OTAA provisioning, AS923 and recovery](CHIRPSTACK-DEPLOYMENT-PROVISIONING-RECOVERY.md)

These companion chapters expand operator guides 04–05 and are part of the required content for the self-contained final Word document.

## Commissioned HA and database companions

- [etcd three-member private Raft cluster and recovery](ETCD-BOOTSTRAP-QUORUM-RECOVERY.md)
- [PostgreSQL/Patroni/TimescaleDB installation and recoverability](POSTGRESQL-PATRONI-TIMESCALEDB-DEPLOYMENT-RECOVERY.md)
- [HAProxy/PgBouncer routing, TLS/SCRAM and failure isolation](HAPROXY-PGBOUNCER-ROUTING-RECOVERY.md)
- [Valkey/Sentinel quorum, TLS replication and recovery](VALKEY-SENTINEL-HA-RECOVERY.md)

These are required source chapters for the eventual comprehensive self-contained Word document, not optional external book prerequisites.

## Commissioned application and observation companions

- [Node-RED payload normalization, safe SQL, sole-writer A/B and recovery](NODE-RED-INGESTION-HA-RECOVERY.md)
- [Grafana installation, restricted workstation path, SQL-only panels, units and recovery](GRAFANA-SETUP-PANELS-ACCESS-RECOVERY.md)

Both are required sources for the final standalone Word document and expand numbered operator guides 10–11.

## Commissioned security, evidence and Fabric companions

- [OpenBao integrated-Raft KMS, Transit/AppRole lifecycle and recovery](OPENBAO-HA-PKI-APPROLE-RECOVERY.md)
- [SeaweedFS raw-object HA, create-only S3 frontend and retained-object recovery](SEAWEEDFS-EVIDENCE-STORE-RECOVERY.md)
- [Gateway evidence independent lineage, collector/verifier ownership and recovery](GATEWAY-EVIDENCE-LINEAGE-DEPLOY-RECOVERY.md)
- [HRC Fabric exact-payload transaction, durable reconciliation and writer fencing](FABRIC-EXACT-PAYLOAD-FENCING-RECOVERY.md)
- [PKI trust and service identity inventory, rotation and restore](PKI-TRUST-IDENTITY-ROTATION-RECOVERY.md)

The final Word document must reproduce all needed instructions from these documents within the book; none is a mandatory external link for the Word document reader.

## Remaining platform, sensor, research and integration companions

- [ULC cloud runtime/bootstrap and host-loss recovery](ULC-CLOUD-RUNTIME-OPERATIONS-RECOVERY.md)
- [EMU-01 hardware assembly, firmware and full acceptance](EMU01-WISBLOCK-ASSEMBLY-FIRMWARE-ACCEPTANCE.md)
- [Research automation, formal matrix, metrics and sealed-run recovery](RESEARCH-AUTOMATION-EXPERIMENT-METRICS-RECOVERY.md)
- [SEC RUI3 authorized security fixture and restore](SEC-RUI3-HARDWARE-SECURITY-RESTORE.md)
- [End-to-end rebuild, data lineage, degradation and final acceptance](END-TO-END-REBUILD-LINEAGE-ACCEPTANCE.md)

These complete the remaining numbered technology areas and are required source material for the comprehensive standalone Word document.

## Current technology map

| # | Technology | Current role | Manual |
|---|---|---|---|
| 01 | Raspberry Pi / ChirpStack Gateway OS / OpenWrt | Edge gateway operating platform | [01-gateway-os-openwrt.md](01-gateway-os-openwrt.md) |
| 02 | RAK5146 + ChirpStack Concentratord | AS923 LoRa RF concentrator and packet interface | [02-rak5146-concentratord-as923.md](02-rak5146-concentratord-as923.md) |
| 03 | SIM7600 LTE | Production-primary Gateway-01 backhaul | [03-sim7600-lte-backhaul.md](03-sim7600-lte-backhaul.md) |
| 04 | Mosquitto MQTT | Edge buffering plus cloud gateway/application messaging | [04-mosquitto-mqtt.md](04-mosquitto-mqtt.md) |
| 05 | ChirpStack | LoRaWAN network/application server | [05-chirpstack.md](05-chirpstack.md) |
| 06 | etcd | Distributed consensus/DCS for HA coordination | [06-etcd.md](06-etcd.md) |
| 07 | PostgreSQL + Patroni + TimescaleDB | Durable HA application/evidence database | [07-postgresql-patroni-timescaledb.md](07-postgresql-patroni-timescaledb.md) |
| 08 | HAProxy + PgBouncer | Service routing and PostgreSQL pooling | [08-haproxy-pgbouncer.md](08-haproxy-pgbouncer.md) |
| 09 | Valkey + Sentinel | ChirpStack runtime state/cache HA | [09-valkey-sentinel.md](09-valkey-sentinel.md) |
| 10 | Node-RED | MQTT application processing, telemetry writer, outbox creator | [10-node-red.md](10-node-red.md) |
| 11 | Grafana | Read-only operational/research visualization | [11-grafana.md](11-grafana.md) |
| 12 | OpenBao | HA KMS/transit signing and protected secret operations | [12-openbao.md](12-openbao.md) |
| 13 | SeaweedFS | Raw/immutable evidence object storage | [13-seaweedfs.md](13-seaweedfs.md) |
| 14 | Gateway evidence services | Journal ingest, MQTT witness, verification, trusted decoding | [14-gateway-evidence-services.md](14-gateway-evidence-services.md) |
| 15 | Hyperledger Fabric adapter | Source-bound HRC blockchain anchoring | [15-hyperledger-fabric-adapter.md](15-hyperledger-fabric-adapter.md) |
| 16 | Ubuntu + Docker Compose + DigitalOcean/VPC | Host/runtime/cloud substrate | [16-runtime-and-cloud-platform.md](16-runtime-and-cloud-platform.md) |
| 17 | PKI / TLS / service identity | Transport authentication and workload identity | [17-pki-tls-and-service-identity.md](17-pki-tls-and-service-identity.md) |
| 18 | RAK4631 / WisBlock Arduino sensor firmware | EMU-01 agriculture-node firmware, payload-v2, OTAA and counted/production profiles | [18-rak4631-wisblock-sensor-firmware.md](18-rak4631-wisblock-sensor-firmware.md) |
| 19 | Python research recorder / test automation | Formal evidence capture, test gating, sealing and measurement automation | [19-research-recorder-and-test-automation.md](19-research-recorder-and-test-automation.md) |
| 20 | RUI3 security node | SEC RAK4631 authorized security-fixture firmware and safe parked state | [20-rui3-security-node.md](20-rui3-security-node.md) |
| 21 | End-to-end integration and data lineage | Cross-system contract, traceability, failure isolation, and research evidence chain | [21-end-to-end-integration-and-data-lineage.md](21-end-to-end-integration-and-data-lineage.md) |

Prometheus, Alertmanager, and Loki are **not** required parts of the commissioned small POC monitoring stack. The current observability model uses service-native health checks/logs, SQL evidence, the research recorder, and Grafana. Do not add a new monitoring platform merely because it appears in an old plan or generic architecture example.

## Current end-to-end flow

```text
EMU-01
  -> AS923 LoRa RF
  -> RAK5146 + Concentratord on Gateway-01
  -> MQTT Forwarder
  -> local Mosquitto persistent buffer
  -> SIM7600 LTE + mTLS
  -> cloud Mosquitto preferred/backup service
  -> ChirpStack
  -> Node-RED
  -> PostgreSQL/TimescaleDB telemetry + durable fabric_outbox
       |-> Grafana (read-only SQL observation)
       `-> eligible finalized outbox record
              -> Fabric Adapter on ULC-01
              -> OpenBao Transit digest sign/verify
              -> HRC Hyperledger Fabric

Independent evidence lane:
Gateway journal + MQTT witness + application telemetry
  -> evidence ingest/collectors/verifiers
  -> trusted decoder
  -> PostgreSQL metadata + SeaweedFS raw objects
```

## Fast fault-location rule

When an end-to-end result is missing, start at the earliest layer that should have produced evidence and move forward only after it passes:

```text
sensor serial -> RF/Concentratord -> local MQTT -> LTE/cloud MQTT
-> ChirpStack event -> Node-RED -> PostgreSQL
    |-> Grafana read-only view
    `-> independent evidence eligibility/finalized_payload -> Fabric adapter -> HRC ledger
```

This prevents a common mistake: restarting Fabric because an outbox row was never eligible, or changing ChirpStack because the gateway never received RF.

## Full rebuild order

For a new environment or disaster recovery, use the detailed runbooks linked by each guide. The normal dependency order is:

```text
host/network/PKI
-> etcd
-> PostgreSQL/Patroni/TimescaleDB
-> HAProxy/PgBouncer
-> Valkey/Sentinel + Mosquitto
-> SeaweedFS raw-object storage + OpenBao KMS
-> ChirpStack
-> Node-RED + Grafana
-> gateway OS/radio/local MQTT/LTE
-> evidence services
-> Fabric adapter
-> end-to-end verification
```

Do not interpret this rebuild order as permission to recommission healthy production layers.