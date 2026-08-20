# 2. Fabric Network Handoff Package

The Fabric team creates and operates the network. Use this procedure to exchange the concrete values the adapter needs and to prove them in staging. Sensitive identity material must use the organization's protected provisioning channel rather than a normal message or issue.

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

- Gateway EUI: `<GATEWAY_EUI>` obtained from the active Concentratord configuration;
- LoRaWAN region: `<CONFIRMED_REGION_ID>` with the site authorization evidence;
- ChirpStack application and device identifier conventions;
- DevEUI normalization rule;
- the frozen EMU-01 payload-v2 decoded field dictionary, including units and `sensor_validity_bitmap` semantics;
- MQTT topic pattern: application/+/device/+/event/up;
- TimescaleDB table and view names;
- timestamp policy: UTC;
- duplicate key policy;
- expected event volume and aggregation window;
- example sanitized uplink JSON;
- example canonical attestation JSON;
- desired query and verification operations;
- data classification for each field.

Do not send passwords, private keys, LoRaWAN root keys, connection profiles containing secrets, or raw personal data in a normal project chat or issue. Exchange certificates and private keys through the approved secure provisioning channel and record only their identifiers, owners, expiry dates, and storage locations in the handoff.

## 2.3 Build the handoff request

Use the template below to collect the environment-specific values. Each field is consumed by the adapter configuration, TLS validation, contract invocation, capacity plan, or support procedure; omit fields that do not apply rather than inventing values:

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

## 2.4 Test the handoff

The handoff is usable only when the Fabric team has supplied and the application team has verified:

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

Do not treat a file called `connection profile` as sufficient by itself. The adapter also needs a verified endpoint, server-name expectation, trusted TLS roots, dedicated client identity, protected private key, exact channel and chaincode contract, authorization policy, commit-status behavior, and revocation process.

## 2.5 Security boundary

The integration application should connect to a Fabric Gateway that belongs to the same organization as its client identity. Store the private key in a protected secret mechanism or file with restricted permissions. Never store it in Node-RED flow JSON, a dashboard, a Git repository, or a debug message.

References:

- [Fabric Gateway application model](https://hyperledger-fabric.readthedocs.io/en/latest/gateway.html)
- [Certificates and identity management](https://hyperledger-fabric.readthedocs.io/en/latest/certs_management.html)
- [Fabric channels](https://hyperledger-fabric.readthedocs.io/en/latest/channels.html)

Next: [03-integration-architecture.md](03-integration-architecture.md)
