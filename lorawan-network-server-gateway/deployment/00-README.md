# Full Deployment

Use this path for the complete gateway/server architecture. It is separate from the dissertation's counted barebones test VM.

## Current cloud HA starting point

For the current work, start from the reconciled current-state material, not from original phase numbering or an older continuation board:

1. **[server/cloud-production/00-current-server-continuation-checkpoint.md](server/cloud-production/00-current-server-continuation-checkpoint.md)** â€” authoritative current commissioned state, open boundaries, and do-not-repeat list through 2026-09-17.
2. **[technology-guides/00-README.md](technology-guides/00-README.md)** â€” technology-by-technology current architecture summaries.
3. **[server/cloud-production/00-README.md](server/cloud-production/00-README.md)** â€” current architecture/phase status map.
4. **[server/cloud-production/00-evidence-services-and-gateway-journal-continuation.md](server/cloud-production/00-evidence-services-and-gateway-journal-continuation.md)** â€” preserved implementation-era continuation board; consult only when reconstructing that commissioning history, not as current truth.
5. **[server/cloud-production/00-build-execution-log.md](server/cloud-production/00-build-execution-log.md)** â€” detailed chronological execution evidence; historical states inside it are not current instructions.

Continue by dependency/resume point, not simply by the next file number.

The [full target sequence runbook](server/cloud-production/19-cloud-ha-grafana-deployment-day-runbook.md) remains useful as an architecture/build-order reference, but its post-etcd sections are **standby**, not commands to execute blindly.

Do **not** begin by deploying `server/ha-cluster/` or `server/data-layer/` for this cloud POC. Those directories remain useful lab/reference procedures, but the current cloud design co-locates TimescaleDB inside the Patroni cluster, uses cloud-specific MQTT/HAProxy ports, and has its own OpenBao/Fabric readiness gates.

The physical gateway reaches the cloud through outbound USB 4G/LTE while retaining its local persistent MQTT buffer.

---

## Track Overview

Unlike the barebones testing VM, this deployment path is intended for multi-node or enterprise cloud environments:

```text
deployment/
â”œâ”€â”€ 00-README.md             # This file
â”œâ”€â”€ gateway/                 # Full gateway setup, operations, and references
â”‚   â”œâ”€â”€ 00-README.md
â”‚   â”œâ”€â”€ setup/               # Complete Gateway OS setup + journal v2 (01-06, 04a)
â”‚   â”œâ”€â”€ operations/          # Operations suite (01-07: registration, backup, recovery, migration, troubleshooting, RF planning, security/VPN)
â”‚   â””â”€â”€ references/          # Vendor PDF datasheets & hardware checklists
â””â”€â”€ server/                  # Full HA server and cloud architecture
    â”œâ”€â”€ 00-README.md
    â”œâ”€â”€ ha-cluster/          # 3-node etcd, 3-node Spilo/Patroni PostgreSQL HA, HAProxy, PgBouncer, Valkey cache, ChirpStack Cluster (01-14)
    â”œâ”€â”€ data-layer/          # TimescaleDB hypertables, Node-RED telemetry flows, Grafana dashboards & alerting (01-03)
    â”œâ”€â”€ fabric-attestation/  # Fabric handoff, OpenBao Transit, outbox/adapter, commit/reconciliation (01-03)
    â”œâ”€â”€ cloud-production/    # Current 3-Droplet HA POC / future-deployment scale model (00-20) + simulation references
    â””â”€â”€ integrations/        # Technology reference manuals (timescaledb, node-red, grafana, hyperledger-fabric, gateway-integrity, technology-transfer)
```

---

## Complete Technology Stack

```text
Edge Layer:
  Sensors (WisBlock Agriculture Kit)
    -> RAK5146 Concentrator + Raspberry Pi 4B
    -> ChirpStack Concentratord
         |-> MQTT Forwarder -> local Mosquitto disk buffer -> mTLS bridge
         +-> software integrity journal (SHA-256 evidence chain)

Ingress & Messaging Layer:
  DigitalOcean Reserved IPv4 -> current ha-01/ha-02 HAProxy anchor listener
    :443  -> ChirpStack HTTPS
    :8883 -> Mosquitto preferred/backup private TLS :8884
  Reserved-IP ownership fails over through the DigitalOcean API under an etcd lock
  Per-gateway mTLS certificate + ACL isolation
    -> Valkey (in-memory session state cache)
    -> ChirpStack Network Server Cluster

Database High Availability Layer:
  ChirpStack Network Server
    -> PgBouncer (Session Connection Pooler :6432)
    -> HAProxy (Health-Checked Primary Router :15432)
    -> Spilo / Patroni PostgreSQL HA Cluster :5432 (3-Node Primary/Replica)
         ^-- Driven by etcd Distributed Consensus Quorum (3-Node Raft Cluster)

Telemetry, Analytics & Visualization Layer:
  ChirpStack Application Events
    -> Node-RED Operational Normalization & Validation Flow
    -> `lorawan_telemetry` TimescaleDB hypertables inside the same 3-node Patroni cluster
    -> Grafana Dashboards & Real-Time Alerting (Read-Only DB Account)
    -> Gateway Integrity Verifier (v2 evidence verification)

Security & Blockchain Attestation Layer:
  PostgreSQL/Timescale-enabled `lorawan_telemetry` Durable Fabric Outbox
    -> Hyperledger Fabric Adapter & SDK Client
         |-> ULC-01 enabled production writer
         |-> ULC-02 installed but write-disabled pending HA ownership/fencing acceptance
         |-> OpenBao KMS Transit Engine (Non-exportable ECDSA-P256 local evidence seal)
         +-> HRC private Fabric Gateway / `hrc-evidence` source-bound chaincode
```

---

## Execution Order

1. **Gateway:** follow [gateway/00-README.md](gateway/00-README.md) for Gateway OS, buffering, the optional/implemented evidence journal, and operations.
2. **Server:** follow [server/00-README.md](server/00-README.md) for the HA application stack, telemetry layer, OpenBao/Fabric integration, and cloud deployment.
3. Do not copy the full-deployment resource profile into the dissertation test VM. The two paths have different purposes and sizing.

