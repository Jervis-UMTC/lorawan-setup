# Hyperledger Fabric Simulation Layer

This folder adds a real Fabric test network to the host-simulated cloud lab.

```text
TimescaleDB
  -> durable Fabric outbox
  -> dedicated Fabric adapter
  -> Fabric Gateway on the Fabric VM
  -> telemetry-attestation chaincode
  -> commit status and transaction ID back to TimescaleDB
  -> Grafana queue and reconciliation panels
```

Use a second Ubuntu VM for Fabric. Do not run peers, orderers, certificate authorities, or Fabric private keys on the Raspberry Pi gateway.

## Read in this order

1. [01-deploy-fabric-test-network.md](01-deploy-fabric-test-network.md)
2. [02-create-outbox-and-adapter.md](02-create-outbox-and-adapter.md)
3. [03-test-and-reconcile.md](03-test-and-reconcile.md)

## Important boundary

The official Fabric test network is for development and integration testing. It is not a production network design. A future production connection must use the endpoint, MSP, identity, endorsement policy, certificate lifecycle, and chaincode contract supplied by the Fabric organization.

## What the simulation must prove

- telemetry continues while Fabric is unavailable;
- selected events enter a durable outbox exactly once;
- the adapter uses a dedicated non-admin Fabric identity;
- the adapter waits for valid commit status;
- duplicate retries do not create conflicting ledger state;
- the committed digest matches canonical off-chain evidence;
- Grafana shows queue age, failures, dead letters, and commit latency;
- test-network credentials are never reused for production.
