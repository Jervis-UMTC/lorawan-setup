# 5. Application Implementation Handoff

Use this guide to implement the adapter application. The Fabric team still creates and operates the Fabric network.

## 5.1 Recommended adapter responsibilities

The adapter service should:

1. claim one eligible outbox row with an expiring processing lease;
2. commit the claim before contacting Fabric;
3. validate the contract version;
4. load only the required off-chain data;
5. produce canonical JSON;
6. calculate the digest;
7. connect using the organization identity supplied by the Fabric team;
8. evaluate the contract version before submitting;
9. submit the transaction;
10. wait for commit status;
11. store the transaction ID, commit status, and completion time in the outbox row;
12. clear the processing lease when leaving `processing`;
13. expose metrics and structured logs;
14. retry transient failures without changing event_key;
15. reconcile `submitted_unknown` before retrying.

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
FABRIC_WORKER_ID=REPLACE_WITH_STABLE_WORKER_IDENTIFIER
FABRIC_PROCESSING_LEASE=REPLACE_WITH_MEASURED_INTERVAL
FABRIC_MAX_ATTEMPTS=REPLACE_WITH_LIMIT
FABRIC_RETRY_DELAY_SECONDS=REPLACE_WITH_DELAY
~~~

The Fabric team must provide the values and the permitted storage method. The LoRaWAN team must not generate a Fabric admin identity or copy a private key from another organization.

## 5.3 High-level Node application flow

For Fabric v2.4 and later, use the Fabric Gateway client API supported by the team's chosen language. The following pseudocode illustrates control flow only. It is not executable and does not define the exact SDK methods, transaction-ID API, commit-status API, TLS options, or error types. Implement against the Fabric team's supported SDK version and approved contract:

~~~javascript
const pending = await outbox.claimNextWithLease({
    workerId: process.env.FABRIC_WORKER_ID,
    lease: process.env.FABRIC_PROCESSING_LEASE
});
if (!pending) return;

// The database claim transaction is committed before this point.
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

const transaction = createTransactionUsingSupportedSdk(contract);
const transactionId = transaction.getTransactionId();
await transaction.submit(
    process.env.FABRIC_SUBMIT_FUNCTION,
    attestation.event_key,
    attestation.canonicalJson,
    digest
);
const commitStatus = await transaction.getCommitStatus();

if (!commitStatus.valid) {
    throw new Error(`Fabric commit invalid: ${commitStatus.code}`);
}

await outbox.markConfirmed({
    eventKey: attestation.event_key,
    transactionId,
    commitStatus
});
~~~

The placeholder transaction helpers above must be replaced with the exact supported SDK API. The real implementation and its tests must distinguish:

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
  -> processing
  -> submitted_unknown
  -> confirmed
  -> failed
  -> dead_letter
~~~

`processing` must include a worker ID, processing start, and lease expiry. Commit the claim before the Fabric call; do not hold a database row lock while waiting for endorsement or commit status. Expired processing leases may be reclaimed. Clear the claim fields whenever the row leaves `processing`.

When the adapter receives a timeout after submission, move the row to `submitted_unknown` and query the ledger by event_key or transaction ID before retrying. The normal pending/failed worker must not claim `submitted_unknown`. A retry is safe only when the chaincode and event-key rules make it idempotent.

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
