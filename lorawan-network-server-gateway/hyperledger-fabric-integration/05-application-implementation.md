# 5. Application Implementation Handoff

This guide describes what the application developer implements. It is not a command sequence for creating a Fabric network.

## 5.1 Recommended adapter responsibilities

The adapter service should:

1. read pending events from the outbox;
2. validate the contract version;
3. load only the required off-chain data;
4. produce canonical JSON;
5. calculate the digest;
6. connect using the organization identity supplied by the Fabric team;
7. evaluate the contract version before submitting;
8. submit the transaction;
9. wait for commit status;
10. record the transaction ID and result;
11. expose metrics and structured logs;
12. retry transient failures without changing event_key.

## 5.2 Configuration contract

Use environment variables or a secret manager. Do not commit real values:

~~~text
FABRIC_GATEWAY_ENDPOINT=REPLACE_WITH_FABRIC_GATEWAY_ENDPOINT
FABRIC_TLS_ROOT_CERT=REPLACE_WITH_SECURE_CERTIFICATE_PATH
FABRIC_MSP_ID=REPLACE_WITH_MSP_ID
FABRIC_CERT_PATH=REPLACE_WITH_CLIENT_CERTIFICATE_PATH
FABRIC_KEY_PATH=REPLACE_WITH_CLIENT_PRIVATE_KEY_PATH
FABRIC_CHANNEL=REPLACE_WITH_CHANNEL
FABRIC_CHAINCODE=REPLACE_WITH_CHAINCODE
FABRIC_CONTRACT=REPLACE_WITH_CONTRACT_NAME
FABRIC_SUBMIT_FUNCTION=CreateAttestation
FABRIC_QUERY_FUNCTION=ReadAttestation
FABRIC_MAX_ATTEMPTS=REPLACE_WITH_LIMIT
FABRIC_RETRY_DELAY_SECONDS=REPLACE_WITH_DELAY
~~~

The Fabric team must provide the values and the permitted storage method. The LoRaWAN team must not generate a Fabric admin identity or copy a private key from another organization.

## 5.3 High-level Node application flow

For Fabric v2.4 and later, use the Fabric Gateway client API supported by the team's chosen language. The following pseudocode is intentionally incomplete until the network team supplies the connection profile and chaincode contract:

~~~javascript
const pending = await outbox.claimNext();
const attestation = buildCanonicalAttestation(pending);
const digest = sha256(attestation.canonicalJson);

const gateway = await connectUsingFabricIdentity({
    endpoint: process.env.FABRIC_GATEWAY_ENDPOINT,
    tlsRootCert: process.env.FABRIC_TLS_ROOT_CERT,
    certificate: process.env.FABRIC_CERT_PATH,
    privateKey: process.env.FABRIC_KEY_PATH,
    mspId: process.env.FABRIC_MSP_ID
});

const network = gateway.getNetwork(process.env.FABRIC_CHANNEL);
const contract = network.getContract(process.env.FABRIC_CHAINCODE);

const result = await contract.submitTransaction(
    process.env.FABRIC_SUBMIT_FUNCTION,
    attestation.event_key,
    attestation.canonicalJson,
    digest
);

await outbox.markConfirmed({
    eventKey: attestation.event_key,
    transactionId: result.transactionId
});
~~~

The real implementation must distinguish:

- proposal or endorsement failure;
- submission failure;
- commit invalidation;
- commit timeout with unknown final state;
- duplicate event with matching digest;
- duplicate event with conflicting digest;
- authorization failure;
- chaincode validation failure.

## 5.4 Do not use the database as a false confirmation

Writing a Fabric transaction ID before commit status is received is not confirmation. Store explicit states:

~~~text
pending
  -> submitting
  -> submitted_unknown
  -> confirmed
  -> failed
  -> dead_letter
~~~

When the adapter receives a timeout after submission, query the ledger by event_key or transaction ID before retrying. A retry is safe only when the chaincode and event-key rules make it idempotent.

## 5.5 API alternative

If the platform team should not receive Fabric certificates, deploy a Fabric integration API owned by the Fabric or application team:

~~~text
Node-RED or scheduled worker
  -> authenticated HTTPS request with event_key, canonical_json, digest
  -> Fabric integration API
  -> Fabric Gateway
~~~

The API must authenticate the caller, validate the schema, enforce rate limits, avoid accepting arbitrary chaincode function names, and return a clear commit-status model.

## 5.6 Logging

Log:

- event_key;
- contract and schema version;
- adapter version;
- request and commit timestamps;
- Fabric transaction ID;
- result status;
- retry count;
- error category.

Do not log:

- Fabric private keys;
- TLS private material;
- LoRaWAN root keys;
- full raw payloads when they contain sensitive values;
- credentials;
- unrestricted personal information.

References:

- [Running a Fabric application](https://hyperledger-fabric.readthedocs.io/en/latest/write_first_app.html)
- [Fabric Gateway client model](https://hyperledger-fabric.readthedocs.io/en/latest/gateway.html)
- [Fabric event services](https://hyperledger-fabric.readthedocs.io/en/latest/peer_event_services.html)

Next: [06-security-operations-and-testing.md](06-security-operations-and-testing.md)
