# Hyperledger Fabric Integration

Use these guides when another team operates the Hyperledger Fabric network and this project supplies a controlled telemetry integration. The documents define the handoff, data contract, adapter behavior, security, and verification work; they do not claim that a Fabric endpoint, identity, channel, chaincode, or adapter already exists.

For an end-to-end local simulation with a separate Fabric VM, follow [server/lab/fabric/00-README.md](../../lab/fabric/00-README.md). The official Fabric test network used there is a disposable development tool, not a production network template.

## Ownership boundary

```text
LoRaWAN application team owns:
  gateway and ChirpStack event source
  MQTT and TimescaleDB
  telemetry normalization and stable event keys
  outbox and adapter requirements
  reconciliation with off-chain records

Fabric network team owns:
  organizations and MSPs
  peers, orderers, and certificate authorities
  channels, policies, and chaincode lifecycle
  client identity issuance and TLS material
  Fabric Gateway endpoint
  ledger availability and governance
```

The LoRaWAN team can prepare a precise contract and test package without creating the production Fabric network. Do not submit production telemetry until the Fabric endpoint, identity, contract, data ownership, and incident path are known.

## Read in this order

1. [01-boundary-requirements-and-roles.md](01-boundary-requirements-and-roles.md) — Decide which business evidence belongs on the ledger and which telemetry stays in TimescaleDB.
2. [02-fabric-network-handoff.md](02-fabric-network-handoff.md) — Exchange the exact endpoint, identity, channel, contract, policy, and test requirements.
3. [03-integration-architecture.md](03-integration-architecture.md) — Choose the durable outbox and adapter reliability pattern.
4. [04-data-contract-and-chaincode.md](04-data-contract-and-chaincode.md) — Define canonical evidence and chaincode transaction behavior.
5. [05-application-implementation.md](05-application-implementation.md) — Implement submission, commit checking, retry, and reconciliation.
6. [06-security-operations-and-testing.md](06-security-operations-and-testing.md) — Test, monitor, recover, rotate credentials, and operate the integration.

## Recommended architecture

```text
ChirpStack application event
  -> Node-RED validation
  -> TimescaleDB telemetry row and durable outbox item
  -> Fabric adapter service
  -> Fabric Gateway client API
  -> chaincode on a Fabric channel
  -> committed ledger attestation
```

Keep high-volume raw telemetry in TimescaleDB. Put a compact business attestation or cryptographic digest on Fabric. The ledger reference can later be compared with canonical off-chain evidence; it does not prove that the physical sensor was accurate.

## What Fabric adds

Fabric can provide shared evidence of a submitted event or state transition, multi-organization endorsement, custody or inspection history, and a committed transaction identifier. It does not replace ChirpStack, TimescaleDB, Grafana, safety controls, or the governance needed to make a record legally or operationally meaningful.

## Values that must come from the Fabric team

Do not invent these placeholders:

- `<FABRIC_MSP_ID>`: the case-sensitive organization identity.
- `<FABRIC_GATEWAY_ENDPOINT>` and TLS server name: the peer Gateway address and certificate name.
- channel, chaincode, contract, transaction, and query names: the deployed application contract.
- endorsement policy and commit behavior: the organizations and result required before an outbox row is confirmed.
- client certificate/private-key delivery method: the protected signing identity for the adapter.

Next: [01-boundary-requirements-and-roles.md](01-boundary-requirements-and-roles.md)
