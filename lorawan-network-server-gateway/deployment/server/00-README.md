# Full Server Deployment

Choose the target before starting.

## Current target - three-Droplet cloud HA POC

Start with:

1. [cloud-production/00-evidence-services-and-gateway-journal-continuation.md](cloud-production/00-evidence-services-and-gateway-journal-continuation.md) for the current execution board; the cloud/public server lane is commissioned and the Gateway OS/OpenWrt lane is delegated to a separate agent, so server work must not duplicate that setup/package task;
2. [cloud-production/00-current-server-continuation-checkpoint.md](cloud-production/00-current-server-continuation-checkpoint.md) for the exact broader live server state and do-not-repeat boundaries;
3. [cloud-production/00-README.md](cloud-production/00-README.md) for the architecture map and phase boundaries;
4. [cloud-production/02-capacity-cost-and-ip-plan.md](cloud-production/02-capacity-cost-and-ip-plan.md) for the non-secret IP/version worksheet;
5. [cloud-production/00-build-execution-log.md](cloud-production/00-build-execution-log.md) only for detailed executed commands, failures, fixes, and historical evidence.

Follow dependency/resume state rather than file numbering.

[cloud-production/19-cloud-ha-grafana-deployment-day-runbook.md](cloud-production/19-cloud-ha-grafana-deployment-day-runbook.md) is the complete target sequence reference, not proof that its later phases are already validated.

This is the current **scale-model-of-future-deployment** track. Do not deploy `ha-cluster/` then `data-layer/` first for this target; doing so would recreate lab-only service placement such as a standalone telemetry database and confuse the cloud topology.

Other targets:

- **Single-host/full-stack lab reference:** use `ha-cluster/`, `data-layer/`, and `fabric-attestation/` as directed by their own READMEs.
- **Technology detail only:** use `integrations/` as a reference. Several integration manuals contain explicit lab-vs-cloud branches; choose the branch before running commands.

---

## Directory Organization

```text
deployment/server/
├── 00-README.md             # This file
├── ha-cluster/              # 3-node etcd, 3-node Spilo/Patroni PostgreSQL HA, HAProxy, PgBouncer, Valkey cache, ChirpStack Cluster (01-14)
├── data-layer/              # TimescaleDB hypertables, Node-RED telemetry flows, Grafana dashboards & alerting (01-03)
├── fabric-attestation/      # Fabric handoff, OpenBao Transit, outbox/adapter, commit/reconciliation (01-03)
├── cloud-production/        # Current 3-Droplet HA POC / future-deployment scale model (00-20) + simulation references
└── integrations/            # Technology reference manuals (timescaledb, node-red, grafana, hyperledger-fabric, gateway-integrity, technology-transfer)
```

---

## Lab/full-stack reference build order

> [!IMPORTANT]
> `ha-cluster/` and `data-layer/` are **not** the host layout for the current multi-node cloud POC. Use `cloud-production/` for the current deployment. The sequence below is only for the separate lab/full-stack reference environment.

Use this order for that lab/reference environment:

1. [ha-cluster/](ha-cluster/00-README.md) — build the database/messaging/ChirpStack foundation and gateway MQTT security.
2. Configure and register the physical gateway through [../gateway/](../gateway/00-README.md); prove one real uplink reaches ChirpStack.
3. [data-layer/](data-layer/00-README.md) — deploy TimescaleDB, Node-RED, then Grafana; prove one real event is stored once.
4. [fabric-attestation/](fabric-attestation/00-README.md) — collect the external Fabric handoff, deploy OpenBao, create the outbox/adapter, and prove one valid commit.
5. Return to HA/recovery/backup procedures only after the end-to-end path works. Do not debug failover and first-time integration at the same time.

Each suite has its own pass conditions. Stop at the first failing layer.

## Component suites

- **[ha-cluster/](ha-cluster/00-README.md)**: Deploy etcd quorum, Spilo/Patroni PostgreSQL HA, HAProxy, PgBouncer, Mosquitto, Valkey, ChirpStack, and gateway MQTT mTLS.
- **[data-layer/](data-layer/00-README.md)**: Deploy TimescaleDB hypertables for IoT telemetry, Node-RED normalization flows, and Grafana monitoring dashboards with read-only database accounts.
- **[fabric-attestation/](fabric-attestation/00-README.md)**: Collect the external Fabric handoff, deploy OpenBao Transit, create the durable outbox/adapter, and test commit/reconciliation behavior. Gateway-evidence v2 contracts live under `integrations/gateway-integrity/`.
- **[cloud-production/](cloud-production/00-README.md)**: Current three-Droplet HA proof of concept / future-deployment scale model. TimescaleDB stays inside Patroni; Node-RED A is active on ulc-03 with B fenced on ulc-02; Grafana is on ulc-03; OpenBao is 3-member and its audit boundary is complete. The cloud evidence lane is now commissioned server-side: three-node PgBouncer evidence SCRAM, SeaweedFS S9, immutable GHCR image digests, Evidence PKI, four read-only collector MQTT identities/ACLs, two ingest replicas, two dual-broker collectors, two verifier/trusted-decoder replicas, disabled Fabric adapter standbys, shared-443 SNI routing, and Grafana evidence panels are PASS. Remaining gates are the Gateway OS target package/physical gateway lineage, Reserved-IP reassignment/failover authority and acceptance, and the external Fabric handoff. The ordinary public ChirpStack/Evidence/MQTT normal path is commissioned.
- **[integrations/](integrations/node-red/00-README.md)**: Consult reusable technology-specific manuals.
