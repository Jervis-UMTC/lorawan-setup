# Hyperledger Fabric Integration

Use these guides when another team operates the Hyperledger Fabric network and this project supplies a controlled telemetry integration. The documents define the handoff, data contract, adapter behavior, security, and verification work; they do not claim that a Fabric endpoint, identity, channel, chaincode, or adapter already exists.

For the full integration environment, follow [fabric-attestation/00-README.md](../../fabric-attestation/00-README.md). That suite tests the outbox, OpenBao Transit evidence KMS, adapter/client credentials, external Fabric Gateway connection, commit handling, KMS/Fabric outages, and recovery. It does not create or administer a Fabric network.

## Ownership boundary

```text
LoRaWAN application team owns:
  gateway and ChirpStack event source
  MQTT and TimescaleDB
  telemetry normalization and stable event keys
  gateway journal/checkpoint and server verification contract when v2 is used
  outbox and adapter requirements
  OpenBao/KMS evidence-signing policy and recovery, unless a separate security team owns it
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

The repository now has two explicitly versioned evidence meanings.

### Historical application-only path: `telemetry-attestation-v1`

```text
ChirpStack application event
  -> Node-RED validation
  -> TimescaleDB telemetry row and durable outbox item
  -> Fabric adapter
  -> OpenBao seal
  -> Fabric
```

Keep v1 stable for existing evidence and its fixed canonicalization test vector. Do not silently describe old v1 records as gateway-journal verified.

### Gateway-verified path: `telemetry-attestation-v2`

```text
Concentratord journal -----------+
                                 |
remote gateway MQTT collector --+--> gateway evidence verifier
                                 |       |
ChirpStack application event ----+       +-> trusted decoder
                                         +-> compare TimescaleDB
                                         |
                                      VERIFIED
                                         |
                                         v
                              durable Fabric outbox
                                         |
                                   Fabric adapter
                                         |
                           RFC 8785 + SHA-256 + OpenBao
                                         |
                                      Fabric
```

Read [Gateway Integrity](../gateway-integrity/00-README.md) before enabling v2.

Keep high-volume raw telemetry and full gateway journal objects off-chain. Put compact verification references and the canonical evidence digest on Fabric. OpenBao/Fabric preserve the verified evidence from that point forward; they still cannot prove that a physically compromised sensor measured the real world accurately.

## What Fabric adds

Fabric can provide shared evidence of a submitted event or state transition, multi-organization endorsement, custody or inspection history, and a committed transaction identifier. It does not replace the gateway journal/checkpoint verifier, ChirpStack, TimescaleDB, Grafana, safety controls, or the governance needed to make a record legally or operationally meaningful.

## Values that must come from the Fabric team

Do not invent these placeholders:

- `<FABRIC_GATEWAY_ENDPOINT>`: the Fabric Gateway host and port.
- `<FABRIC_MSP_ID>`: the case-sensitive organization identity.
- `<FABRIC_CHANNEL_NAME>`: the existing channel used by this integration.
- `<FABRIC_CHAINCODE_NAME>`: the already deployed chaincode name.
- `<FABRIC_CA_CERT>`: the trusted TLS CA certificate supplied for the Gateway endpoint.
- `<FABRIC_CLIENT_CERT>`: the dedicated application identity certificate.
- `<FABRIC_CLIENT_KEY>`: the matching private key, delivered only through the approved protected channel.
- `<FABRIC_TLS_SERVER_NAME>`: the hostname expected in the Gateway endpoint certificate.
- exact contract, submit, and query function names: the deployed application contract.
- endorsement policy and commit behavior: the organizations and result required before an outbox row is confirmed.

Next: [01-boundary-requirements-and-roles.md](01-boundary-requirements-and-roles.md)
