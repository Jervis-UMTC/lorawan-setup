# 2. Fabric Network Handoff Package

The Fabric team creates and operates the network. Use this procedure to exchange the concrete values the adapter needs and to prove them in staging. Sensitive identity material must use the organization's protected provisioning channel rather than a normal message or issue.

> **HRC handoff status — 2026-09-08: ULC-01 EXTERNAL QUALIFICATION PASS.** `hrc-evidence` version 1.1 / sequence 2 is live-qualified across all three Fabric peers. The Adapter uses the Task 37 source-bound API: `CreateSourceBoundAnchor(SourceRecordID, sourceType, producer, producedAt, schemaVersion)` with exact payload bytes only in transient key `hrc.exact_payload`, then `QuerySourceBoundAnchor(SourceRecordID)` and `VerifySourceBoundDigest(SourceRecordID, observedDigest)`. The legacy `CreateAnchor`, `QueryAnchor`, `QueryAnchorByRecordID`, and `VerifyDigest` functions are forbidden for Adapter identities. The frozen source identity is `lorawan-gateway-evidence`. ULC-01 (`10.104.0.2`) is commissioned against the restricted TLS-preserving Gateway `10.104.0.7:7051` with TLS name `peer1.hrc.local`, MSP `HrcMSP`, channel `hrc-channel`, chaincode `hrc-evidence`, and dedicated non-admin client identity `lorawan-gateway-evidence-ulc-01`; authoritative activation-preflight SHA-256 remains `d2e7c9a59270d248ea14b4bd035c671e1a9768ddb1ec8bfa527d675c3b3cca97`. The authorized one-record qualification for outbox `1960` / SourceRecordID `fdadcf14-741e-4293-ad38-39ba89369ea7` completed successfully with exact-payload SHA-256 `827e443857118c0f922c2f03e66f950a79092c74d8d8b947d489ace43d157b51`, Fabric transaction ID `dd11910c1e7c28edd11334a03cce10d80d574692733458c9059d2775be5131b8`, and HRC record ID `hrc-record-ad1258ae5ee243c01d1e091c684df1c950589bcbcde820d736a257f8cd052bfb`. The qualification runner only marks the row `confirmed` after authoritative commit success, `QuerySourceBoundAnchor` returns matching source/record/digest/payload-length fields, and `VerifySourceBoundDigest` returns `MATCH`; final outbox state is `confirmed`, `attempts=1`, with prepared transaction and commit-status request retained. The one-shot qualification container is gone. As re-verified on 2026-09-09, the ULC-01 continuous Adapter is active with `FABRIC_ADAPTER_ENABLED=true`; the production activation preflight passes and 325 records have reached `confirmed` after the worker start. ULC-02 (`10.104.0.4`) remains `FABRIC_ADAPTER_ENABLED=false`/deferred; enabling its HA worker is a separate later boundary that requires the lease-renewal/ownership-fencing gate and must not trigger a repeat of candidate `1960`.

## 2.1 Information the Fabric team must provide

Request the following:

| Item | Required value | Why it is needed |
|---|---|---|
| Fabric version | Exact network and peer versions | Client compatibility and support |
| Organization name | For example, AgricultureOrg or PortOperatorOrg | MSP and policy identity |
| MSP ID | `HrcMSP` | Transaction signing and authorization |
| Channel name | `hrc-channel` | Ledger routing |
| Chaincode name | `hrc-evidence` | Contract lookup |
| Chaincode version and sequence | Current definition (still request for change coordination) | Upgrade coordination |
| Contract namespace | empty/default; **not** Caliper alias `hrcEvidence` | Fabric Contract API lookup |
| Required transaction | `CreateSourceBoundAnchor(SourceRecordID, sourceType, producer, producedAt, schemaVersion)` plus transient `hrc.exact_payload` | Task 37 application contract |
| Query transaction | `QuerySourceBoundAnchor(SourceRecordID)` | Verification |
| Digest verification transaction | `VerifySourceBoundDigest(SourceRecordID, observedDigest)` and require `MATCH` | Post-commit verification |
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
- data classification for each field;
- `AuthenticatedSourceSystemID`: `lorawan-gateway-evidence`;
- DigitalOcean VPC: `10.104.0.0/20`;
- ULC-01 private/public source addresses: `10.104.0.2` / `143.198.205.54`;
- ULC-02 private/public source addresses: `10.104.0.4` / `165.22.253.127`.

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
