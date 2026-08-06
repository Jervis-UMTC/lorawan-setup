# Hyperledger Fabric Integration

This folder explains how the existing LoRaWAN telemetry platform can integrate with a Hyperledger Fabric network that is created and operated by another team.

The important boundary is:

~~~text
Your team owns:
  LoRaWAN gateway
  ChirpStack
  MQTT
  Node-RED
  TimescaleDB
  telemetry normalization
  integration handoff

Fabric network team owns:
  organizations and MSPs
  peers and ordering service
  Fabric Certificate Authorities
  channels and policies
  chaincode packaging and lifecycle
  client identities and TLS material
  Fabric Gateway endpoint
  ledger operations and governance
~~~

You do not need to create the Fabric network to prepare a good integration. Your responsibility is to provide a stable, documented event contract and to request the connection details and permissions that the Fabric team must supply.

## Recommended order

1. [01-boundary-requirements-and-roles.md](01-boundary-requirements-and-roles.md) — Decide what belongs on the ledger, what remains in TimescaleDB, and who is responsible.
2. [02-fabric-network-handoff.md](02-fabric-network-handoff.md) — Give the Fabric team a complete, testable requirements package.
3. [03-integration-architecture.md](03-integration-architecture.md) — Choose the adapter and reliability pattern.
4. [04-data-contract-and-chaincode.md](04-data-contract-and-chaincode.md) — Define the telemetry attestation contract and transaction functions.
5. [05-application-implementation.md](05-application-implementation.md) — Explain what the integration application team implements.
6. [06-security-operations-and-testing.md](06-security-operations-and-testing.md) — Test, monitor, recover, and operate the integration.

## Recommended architecture

~~~text
Dragino sensor
  -> RAK5146 gateway
  -> ChirpStack
  -> MQTT
  -> Node-RED
  -> TimescaleDB
       |
       | outbox or integration API
       v
Fabric adapter service
  -> Fabric Gateway client API
  -> Fabric peer gateway
  -> chaincode on a Fabric channel
  -> committed ledger event
~~~

Keep high-volume raw telemetry in TimescaleDB. Put a compact, signed, auditable attestation or business state on Fabric. The Fabric record can contain a cryptographic hash and a reference to the off-chain record, allowing another party to verify that the archived telemetry was not changed.

## What this integration is and is not

This integration can provide:

- shared proof that a measurement or state transition was submitted;
- multi-organization approval for business events;
- traceability of custody, inspection, maintenance, or compliance records;
- an auditable link between off-chain telemetry and an on-chain transaction;
- chaincode events that trigger external workflows.

It does not automatically provide:

- a replacement for ChirpStack;
- a replacement for TimescaleDB or Grafana;
- proof that a physical sensor was honest;
- real-time safety control;
- legal validity without the required organizational and regulatory agreements;
- confidentiality from every channel member.

## Reference material

- [Hyperledger Fabric network structure](https://hyperledger-fabric.readthedocs.io/en/latest/network/network.html)
- [Fabric Gateway](https://hyperledger-fabric.readthedocs.io/en/latest/gateway.html)
- [Running a Fabric application](https://hyperledger-fabric.readthedocs.io/en/latest/write_first_app.html)
- [Fabric channels](https://hyperledger-fabric.readthedocs.io/en/latest/channels.html)

Next: [01-boundary-requirements-and-roles.md](01-boundary-requirements-and-roles.md)
