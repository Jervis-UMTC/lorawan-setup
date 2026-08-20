# Telemetry and Visualization Layer

Add this layer only after the gateway is online in ChirpStack and one real uplink has been accepted.

```text
ChirpStack application MQTT event
  -> Node-RED operational normalization
  -> TimescaleDB
       |-> Grafana
       |-> gateway-evidence trusted-decoder comparison when v2 is enabled
       +-> Fabric outbox for selected events
              -> v1 application-only compatibility
              -> v2 seal eligibility only after gateway evidence = verified
```

The ChirpStack PostgreSQL database remains separate. Node-RED writes telemetry, Grafana reads it with a read-only role, the gateway-evidence verifier owns only its verification schema/result, and the Fabric adapter processes only eligible queued attestations. Node-RED cannot declare v2 evidence verified.

These three services belong to the **full deployment** data layer. The dissertation testing profile uses TimescaleDB + Node-RED only and omits Grafana. Full-deployment container limits are defined by its own environment sizing.

> [!IMPORTANT]
> The numbered files in this folder use the one-VM `/opt/lorawan-lab` Compose topology. For the real multi-node cloud deployment, keep the same telemetry schema and role boundaries but use [Cloud Grafana Deployment](../cloud-production/13a-grafana-cloud-deployment.md) and the [Cloud HA + Grafana deployment-day runbook](../cloud-production/18-cloud-ha-grafana-deployment-day-runbook.md) for placement, networking, and execution order.

## Read in this order

1. [01-deploy-timescaledb.md](01-deploy-timescaledb.md)
2. [02-deploy-node-red.md](02-deploy-node-red.md)
3. [03-deploy-grafana.md](03-deploy-grafana.md)
4. For v2, implement and verify [Gateway Integrity](../integrations/gateway-integrity/00-README.md) after the reviewed service artifacts exist.
5. [../fabric-attestation/00-README.md](../fabric-attestation/00-README.md)

## Required boundaries

- Do not give Node-RED access to the ChirpStack database.
- Do not give Grafana a database writer or administrator role.
- Do not publish PostgreSQL, Node-RED, or Grafana broadly on the LAN.
- Do not store Fabric private keys in Node-RED flows or Grafana.
- Do not let a Fabric outage stop telemetry ingestion.
- Do not give Node-RED or the Fabric adapter permission to set gateway evidence `verified`.
- Do not give the gateway-evidence verifier OpenBao sign permission or the Fabric client private key.

## Final checks

- one real uplink creates one telemetry event;
- replaying the same event does not create duplicates;
- Grafana shows event time and freshness, not only the value;
- Node-RED and Grafana require authentication;
- TimescaleDB has a readable off-host backup;
- a selected event can be queued for Fabric without changing the stored telemetry;
- when v2 is enabled, one real event reaches `verified` only after journal/MQTT/application/trusted-decoder checks, and pending/gap/failure states remain visibly distinct.
