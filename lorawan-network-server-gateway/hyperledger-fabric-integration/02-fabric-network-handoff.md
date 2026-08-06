# 2. Fabric Network Handoff Package

The Fabric team creates and operates the network. Your job is to give them a precise integration request. Send this document as a checklist, then ask them to return the completed fields and test credentials through an approved secure channel.

## 2.1 Information the Fabric team must provide

Request the following:

| Item | Required value | Why it is needed |
|---|---|---|
| Fabric version | Exact network and peer versions | Client compatibility and support |
| Organization name | For example, AgricultureOrg or PortOperatorOrg | MSP and policy identity |
| MSP ID | Exact case-sensitive MSP identifier | Transaction signing and authorization |
| Channel name | Exact channel | Ledger routing |
| Chaincode name | Exact deployed chaincode name | Contract lookup |
| Chaincode version and sequence | Current definition | Upgrade coordination |
| Required transaction names | For example, CreateAttestation | Application contract |
| Query transaction names | For example, ReadAttestation | Verification |
| Endorsement policy | Organizations required to endorse | Retry and availability planning |
| Fabric Gateway endpoint | Host and port | Client connection |
| Peer endpoint | If the client profile requires it | Gateway and TLS routing |
| TLS CA certificate | Out-of-band trusted certificate | Prevent endpoint impersonation |
| Client identity certificate | Public certificate for the adapter | Authentication |
| Client private key | Securely provisioned, never emailed in plain text | Transaction signing |
| Connection profile | Network connection details | Client configuration |
| Event behavior | Commit and chaincode event format | Downstream processing |
| Rate limits | Transactions per second and burst limits | Back-pressure design |
| Maintenance windows | Expected outages and upgrade process | Operational planning |

Fabric channels define membership and ledger separation, while policies determine who can act. Do not invent channel names, MSP IDs, or endorsement rules in the Node-RED flow.

## 2.2 Information your team must provide

Give the Fabric team:

- gateway ID: 2CCF67FFFE0ABEE3;
- current LoRaWAN region: AS923-3, subject to local regulatory confirmation;
- ChirpStack application and device identifier conventions;
- DevEUI normalization rule;
- decoded Dragino field names;
- MQTT topic pattern: application/+/device/+/event/up;
- TimescaleDB table and view names;
- timestamp policy: UTC;
- duplicate key policy;
- expected event volume and aggregation window;
- example sanitized uplink JSON;
- example canonical attestation JSON;
- desired query and verification operations;
- data classification for each field.

Do not send passwords, private keys, LoRaWAN root keys, or raw personal data in a normal project chat or issue.

## 2.3 Handoff request template

Copy and complete this template for the Fabric team:

~~~text
Integration name: LoRaWAN telemetry attestation
Environment: pilot / staging / production
Submitting organization:
MSP ID:
Channel:
Chaincode:
Chaincode version:
Fabric Gateway endpoint:
TLS server name:
Required transaction:
Required query:
Required event:
Client identity name:
Endorsement policy:
Expected transaction rate:
Maximum accepted delay:
Private data requirement:
Test window:
Support contact:
Certificate rotation contact:
~~~

## 2.4 Acceptance criteria for the handoff

The handoff is complete only when the Fabric team has supplied:

- a reachable staging Gateway endpoint;
- a valid test identity;
- the trusted TLS CA material;
- the channel and chaincode names;
- a transaction that can be evaluated;
- a transaction that can be submitted;
- a documented commit-status result;
- a documented failure response for duplicate events;
- a certificate rotation procedure;
- a support and incident path.

Do not treat a file called connection profile as sufficient by itself. The adapter also needs the correct identity, private key, TLS trust roots, chaincode contract, and authorization policy.

## 2.5 Security boundary

The integration application should connect to a Fabric Gateway that belongs to the same organization as its client identity. Store the private key in a protected secret mechanism or file with restricted permissions. Never store it in Node-RED flow JSON, a dashboard, a Git repository, or a debug message.

References:

- [Fabric Gateway application model](https://hyperledger-fabric.readthedocs.io/en/latest/gateway.html)
- [Certificates and identity management](https://hyperledger-fabric.readthedocs.io/en/latest/certs_management.html)
- [Fabric channels](https://hyperledger-fabric.readthedocs.io/en/latest/channels.html)

Next: [03-integration-architecture.md](03-integration-architecture.md)
