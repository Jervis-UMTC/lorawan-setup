# Telemetry and Visualization Layer

Add this layer only after the gateway is online in ChirpStack and one real uplink has been accepted.

```text
ChirpStack application MQTT event
  -> Node-RED
  -> TimescaleDB
  -> Grafana
  -> Fabric outbox for selected events
```

The ChirpStack PostgreSQL database remains separate. Node-RED writes to the telemetry database, Grafana reads it with a read-only role, and the Fabric adapter processes only queued attestations.

## Read in this order

1. [01-deploy-timescaledb.md](01-deploy-timescaledb.md)
2. [02-deploy-node-red.md](02-deploy-node-red.md)
3. [03-deploy-grafana.md](03-deploy-grafana.md)
4. [../fabric/00-README.md](../fabric/00-README.md)

## Required boundaries

- Do not give Node-RED access to the ChirpStack database.
- Do not give Grafana a database writer or administrator role.
- Do not publish PostgreSQL, Node-RED, or Grafana broadly on the LAN.
- Do not store Fabric private keys in Node-RED flows or Grafana.
- Do not let a Fabric outage stop telemetry ingestion.

## Final checks

- one real uplink creates one telemetry event;
- replaying the same event does not create duplicates;
- Grafana shows event time and freshness, not only the value;
- Node-RED and Grafana require authentication;
- TimescaleDB has a readable off-host backup;
- a selected event can be queued for Fabric without changing the stored telemetry.
