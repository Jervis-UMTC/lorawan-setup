# 5. Application Implementation Handoff

Use this guide to implement the adapter application. The Fabric team still creates and operates the Fabric network.

## 5.1 Recommended adapter responsibilities

The adapter service should:

1. claim one eligible outbox row with an expiring processing lease;
2. commit the claim before any Fabric network call;
3. validate `schema_version` and reject unsupported versions;
4. when `schema_version` is `telemetry-attestation-v2`, require exactly one matching gateway-evidence verification row with `status='verified'` **before creating any seal**; `pending` is deferred, `evidence_gap` follows the reviewed gap policy, and `integrity_failure` is a permanent security conflict;
5. when the row is unsealed, load only the fixed schema-specific source projection: historical application fields for v1, or application fields plus verifier-owned gateway-evidence references for v2;
6. construct the exact canonical evidence object defined in `04-data-contract-and-chaincode.md`;
7. canonicalize it with the pinned RFC 8785 JCS implementation and encode the returned canonical JSON as UTF-8 bytes;
8. calculate SHA-256 over those exact bytes;
9. authenticate to OpenBao with the adapter's machine identity and request Transit signing of the exact canonical bytes using the non-exportable `ecdsa-p256` key `lorawan-evidence` and `sha2-256`;
10. parse the Transit key version from the complete versioned signature, derive `openbao:transit:lorawan-evidence:v<version>`, and persist `canonical_json`, `digest_sha256`, signature algorithm, KMS key ID, complete OpenBao signature, and `evidence_sealed_at` as one complete seal **before** contacting Fabric;
11. when a row is already sealed, recompute its digest and verify the stored signature through OpenBao Transit instead of rebuilding it from current telemetry;
12. connect to Fabric using the organization client identity supplied by the Fabric team; the Fabric client private key remains a separate identity from the OpenBao Transit evidence key;
13. evaluate the contract version before submitting;
14. submit the stable event key, digest, and approved envelope fields;
15. wait for valid commit status;
16. store the Fabric transaction ID and completion time only according to the actual commit result;
17. clear the processing lease whenever the row leaves `processing`;
18. retry only transient failures with bounded exponential backoff and jitter without changing `event_key` or the evidence seal;
19. reconcile `submitted_unknown` before retrying;
20. fail closed on an invalid local digest, signature, algorithm, signing-key ID, gateway-evidence conflict, or conflicting duplicate digest;
21. expose metrics and structured logs without logging private keys or unrestricted raw payloads.

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
FABRIC_RETRY_BASE_DELAY_SECONDS=REPLACE_WITH_BASE_DELAY
FABRIC_RETRY_MAX_DELAY_SECONDS=REPLACE_WITH_MAX_DELAY
FABRIC_RETRY_JITTER_SECONDS=REPLACE_WITH_JITTER_BOUND
EVIDENCE_SIGNATURE_ALG=OPENBAO-TRANSIT-ECDSA-P256-SHA2-256
GATEWAY_EVIDENCE_REQUIRED_SCHEMA=telemetry-attestation-v2
GATEWAY_EVIDENCE_GAP_POLICY=REPLACE_WITH_DELAY_REJECT_OR_EXPLICIT_INCOMPLETE_POLICY
OPENBAO_ADDR=REPLACE_WITH_OPENBAO_HTTPS_ENDPOINT
OPENBAO_TRANSIT_MOUNT=transit
OPENBAO_TRANSIT_KEY=lorawan-evidence
OPENBAO_APPROLE_ROLE_ID_FILE=/run/openbao-approle/role_id
OPENBAO_APPROLE_SECRET_ID_FILE=/run/openbao-approle/secret_id
~~~

`OPENBAO_ADDR` must be the **stable private KMS service address** in production, for example `https://openbao-kms.internal:8200`. Do not point production adapter configuration at one Raft member such as `openbao-1` and do not implement application-side leader election. OpenBao HA plus the private load balancer/service endpoint own active-node changes.

If one OpenBao voter fails but quorum and an unsealed standby remain, the same `OPENBAO_ADDR` should continue working without changing adapter configuration. If the stable endpoint or KMS quorum is unavailable, classify it as a transient infrastructure failure, clear/release the processing claim through the normal failure path, persist backoff in `next_attempt_at`, and leave the outbox row durable. Never switch to a local evidence-signing key.

The Fabric team must provide the Fabric values and permitted Fabric-identity storage method. The application/security team operates the evidence KMS. Keep the identities deliberately separate:

```text
Fabric client private key
  held by: Fabric adapter runtime
  purpose: authenticate this client to Hyperledger Fabric

OpenBao Transit key: lorawan-evidence
  held by: OpenBao only; private key is non-exportable
  purpose: seal canonical off-chain evidence before Fabric submission

OpenBao AppRole credentials
  held by: Fabric adapter runtime
  purpose: obtain short-lived OpenBao tokens limited to Transit sign/verify
```

Do not reuse the Fabric client key for evidence sealing. Do not mount an evidence private key into the adapter.

The gateway-evidence verifier has its own database/evidence-store identity. It must not receive the Fabric client key, OpenBao AppRole sign permission, or permission to mutate telemetry measurements. The adapter may read the verified result required for v2, but it must not be allowed to mark that result `verified`. Do not put the Fabric key, OpenBao root token, unseal material, AppRole SecretID, or short-lived OpenBao client token in Node-RED, PostgreSQL, source control, ordinary `.env` values, logs, dashboards, or the ledger. In production, place OpenBao/KMS on infrastructure independently protected from the application/database host and use TLS plus a reviewed machine-authentication mechanism.

## 5.3 Seal first, then submit

For Fabric v2.4 and later, use the Fabric Gateway client API supported by the team's chosen language. The security-sensitive ordering is mandatory even when exact SDK method names differ:

```text
claim eligible row and COMMIT lease
        |
        v
schema v2? -- yes --> require verifier status = verified
        |                         |
        no                        +-- pending/gap/failure --> defer/policy/security stop
        |
        v
row already sealed? ---- yes ----> verify stored digest + signature
        |
        no
        v
load fixed source projection
        |
        v
RFC 8785 canonicalize
        |
        v
exact UTF-8 canonical bytes
        |----------------------|
        v                      v
     SHA-256             ECDSA P-256/SHA-256
        |                      |
        +----------+-----------+
                   v
        persist complete seal
                   |
                   v
        verify the persisted seal
                   |
                   v
           first Fabric call
```

The following Node-style pseudocode defines the required byte-level behavior. `canonicalizeRfc8785` must be a **pinned and tested RFC 8785 implementation**; do not replace it with ordinary `JSON.stringify()`:

~~~javascript
import { createHash } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const OPENBAO_ADDR = process.env.OPENBAO_ADDR.replace(/\/$/, '');
const TRANSIT_MOUNT = process.env.OPENBAO_TRANSIT_MOUNT;
const TRANSIT_KEY = process.env.OPENBAO_TRANSIT_KEY;
let baoToken = null;

async function readSecret(path) {
    const value = (await readFile(path, 'utf8')).trim();
    if (!value) throw new Error(`empty secret file: ${path}`);
    return value;
}

async function loginOpenBao() {
    const roleId = await readSecret(process.env.OPENBAO_APPROLE_ROLE_ID_FILE);
    const secretId = await readSecret(process.env.OPENBAO_APPROLE_SECRET_ID_FILE);
    let response;
    try {
        response = await fetch(`${OPENBAO_ADDR}/v1/auth/approle/login`, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ role_id: roleId, secret_id: secretId })
        });
    } catch (error) {
        throw new TransientKmsError(`OpenBao AppRole connection failed: ${error.message}`);
    }

    if (response.status >= 500) {
        throw new TransientKmsError(`OpenBao AppRole service HTTP ${response.status}`);
    }
    if (!response.ok) {
        throw new PermanentSecurityError(`OpenBao AppRole rejected credentials/request: HTTP ${response.status}`);
    }

    const body = await response.json();
    if (!body?.auth?.client_token) {
        throw new PermanentSecurityError('OpenBao login response contained no client token');
    }
    baoToken = body.auth.client_token;
}

async function transitPost(operation, canonicalBytes, signature = null) {
    if (!baoToken) await loginOpenBao();
    const path = `${TRANSIT_MOUNT}/${operation}/${TRANSIT_KEY}/sha2-256`;
    const payload = {
        input: canonicalBytes.toString('base64'),
        prehashed: false,
        marshaling_algorithm: 'asn1'
    };
    if (signature !== null) payload.signature = signature;

    async function send() {
        try {
            return await fetch(`${OPENBAO_ADDR}/v1/${path}`, {
                method: 'POST',
                headers: {
                    'content-type': 'application/json',
                    'X-Vault-Token': baoToken
                },
                body: JSON.stringify(payload)
            });
        } catch (error) {
            throw new TransientKmsError(`OpenBao Transit connection failed: ${error.message}`);
        }
    }

    let response = await send();

    // The token is intentionally short-lived. Re-authenticate once on 403 in
    // case the cached token expired; a second 403 is not a transient outage.
    if (response.status === 403) {
        baoToken = null;
        await loginOpenBao();
        response = await send();
    }

    if (response.status >= 500) {
        throw new TransientKmsError(`OpenBao Transit service HTTP ${response.status}`);
    }
    if (response.status === 403) {
        throw new PermanentSecurityError('OpenBao Transit permission denied after re-authentication');
    }
    if (!response.ok) {
        throw new PermanentSecurityError(`OpenBao Transit rejected request: HTTP ${response.status}`);
    }
    return response.json();
}

function keyIdFromVersionedSignature(signature) {
    // OpenBao signatures are versioned. Do not depend on the compatibility
    // prefix text; extract only the positive v<number> component.
    const match = String(signature).match(/^[^:]+:v([1-9][0-9]*):/);
    if (!match) throw new PermanentSecurityError('malformed OpenBao versioned signature');
    return `openbao:${TRANSIT_MOUNT}:${TRANSIT_KEY}:v${match[1]}`;
}

const pending = await outbox.claimNextWithLease({
    workerId: process.env.FABRIC_WORKER_ID,
    lease: process.env.FABRIC_PROCESSING_LEASE
});
if (!pending) return;

// The database claim transaction is committed before this point.
// The claim query itself must exclude unverified v2 rows. Re-check before the
// first seal to defend against implementation mistakes or stale worker state.
if (pending.schema_version === 'telemetry-attestation-v2') {
    const verification = await gatewayEvidence.loadForSource({
        sourceEventKey: pending.source_event_key,
        observedAt: pending.observed_at
    });
    if (!verification || verification.status !== 'verified') {
        throw classifyGatewayEvidenceState(verification?.status ?? 'pending');
    }
}

let sealed = await outbox.getSeal(pending.outbox_id);

if (!sealed.canonical_json) {
    const evidence = await evidenceStore.loadFixedProjection({
        fabricEventKey: pending.event_key,
        sourceEventKey: pending.source_event_key,
        observedAt: pending.observed_at,
        schemaVersion: pending.schema_version,
        // For v2 this loader must join verifier-owned gateway evidence and
        // return the fixed gateway_evidence object. For v1 it must not invent
        // those fields or change the historical v1 projection.
        requireGatewayVerified: pending.schema_version === 'telemetry-attestation-v2'
    });

    const canonicalJson = canonicalizeRfc8785(evidence);
    const canonicalBytes = Buffer.from(canonicalJson, 'utf8');
    const digest = createHash('sha256').update(canonicalBytes).digest('hex');

    const signResponse = await transitPost('sign', canonicalBytes);
    const signature = signResponse?.data?.signature;
    if (!signature) throw new TransientKmsError('OpenBao sign returned no signature');
    const signingKeyId = keyIdFromVersionedSignature(signature);

    await outbox.persistCompleteSeal({
        outboxId: pending.outbox_id,
        canonicalJson,
        digestSha256: digest,
        signatureAlg: 'OPENBAO-TRANSIT-ECDSA-P256-SHA2-256',
        signingKeyId,
        signature
    });

    // Re-read what was actually committed to PostgreSQL. Do not continue with
    // only the in-memory object when the persisted evidence is the audit source.
    sealed = await outbox.getSeal(pending.outbox_id);
}

if (sealed.evidence_signature_alg !== 'OPENBAO-TRANSIT-ECDSA-P256-SHA2-256') {
    throw new PermanentSecurityError('unsupported evidence signature algorithm');
}
if (keyIdFromVersionedSignature(sealed.evidence_signature) !== sealed.evidence_signing_key_id) {
    throw new PermanentSecurityError('OpenBao signature version and stored key ID disagree');
}

const canonicalBytes = Buffer.from(sealed.canonical_json, 'utf8');
const recomputedDigest = createHash('sha256').update(canonicalBytes).digest('hex');
if (recomputedDigest !== sealed.digest_sha256) {
    throw new PermanentSecurityError('canonical evidence digest mismatch');
}

const verifyResponse = await transitPost('verify', canonicalBytes, sealed.evidence_signature);
if (verifyResponse?.data?.valid !== true) {
    throw new PermanentSecurityError('OpenBao rejected canonical evidence signature');
}

// No Fabric network operation may occur before the local digest and KMS
// verification above pass.
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
    pending.schema_version,
    pending.event_key,
    pending.event_type,
    sealed.digest_sha256,
    sealed.evidence_signature_alg,
    sealed.evidence_signing_key_id,
    sealed.evidence_signature
);

const commitStatus = await transaction.getCommitStatus();
if (!commitStatus.valid) {
    throw new Error(`Fabric commit invalid: ${commitStatus.code}`);
}

await outbox.markConfirmed({
    eventKey: pending.event_key,
    transactionId,
    commitStatus
});
~~~

The Fabric submission above follows the seven-field dissertation transaction contract: `schema_version`, `event_key`, `event_type`, `digest`, `seal_algorithm`, `seal_key_id`, and `seal_signature`. Do not add raw payload, decoded sensor values, DevEUI, gateway radio observations, or the complete canonical evidence merely because the adapter can read them from TimescaleDB. Chaincode should derive caller identity and transaction time from Fabric and should treat `SHA-256` and `timescaledb` as contract-defined metadata when those values are stored on-chain.

The adapter sends `input = Base64(canonical UTF-8 bytes)` with `prehashed=false`, so OpenBao performs SHA-256 as part of the ECDSA signing operation. The independently stored `digest_sha256` is still computed locally from the same bytes for the Fabric attestation. Do not send the hexadecimal digest string as Transit input; doing so would sign different bytes. Preserve the complete OpenBao versioned signature exactly as returned.

At adapter startup, run the canonicalization test vector for **every schema version the adapter is configured to process**. The approved v1 object must keep producing the existing exact canonical string and SHA-256 digest. A v2-capable adapter must also carry the separately reviewed v2 fixed input/canonical-string/digest vector defined by the implementation handoff. Refuse startup if any enabled version lacks a reviewed vector or if the canonicalization library/version fails it. Do not enable v2 merely because the database contains v2 rows.

OpenBao Transit keeps key versions under the same logical key. A seal records the version in both the complete OpenBao signature and `evidence_signing_key_id`, so rotation must create a **new key version for future seals without rewriting historical rows**. Keep historical versions verifiable for the full evidence-retention period. Before increasing any OpenBao minimum verification version or destroying old key material, prove that no retained outbox/ledger evidence depends on that version.

The placeholder Fabric transaction helpers above must be replaced with the exact supported SDK API and chaincode argument contract. The real implementation and its tests must distinguish:

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

When the adapter receives a timeout after submission, move the row to `submitted_unknown` and query the ledger by `event_key` or transaction ID before retrying. The normal pending/failed worker must not claim `submitted_unknown`. A retry is safe only when the chaincode and event-key rules make it idempotent.

Before **every** retry or reconciliation call, verify the already-persisted local evidence seal. A retry must use the same `canonical_json`, `digest_sha256`, signing-key ID, and signature that existed before the previous Fabric attempt. Do not rebuild the evidence from a telemetry row that could have changed during the outage. If the local seal no longer verifies, do not contact Fabric; preserve the row and move it to a permanent security-conflict/dead-letter path for investigation.

For failures known to occur before a transaction could have been accepted, schedule retries with bounded exponential backoff plus jitter, for example `min(max_delay, base_delay * 2^attempt) + jitter`. Persist `next_attempt_at`; do not sleep while holding a database transaction. Treat OpenBao connection errors, sealed/unavailable `5xx` responses, and comparable infrastructure failures as transient. Treat persistent AppRole rejection, a second Transit `403` after re-authentication, other invalid `4xx` requests, schema validation failures, malformed/mismatched key-version IDs, invalid local seals, and duplicate-key conflicts with a different digest as permanent until an operator resolves them.

## 5.5 API alternative

If the platform team should not receive Fabric certificates, deploy a Fabric integration API owned by the Fabric or application team:

~~~text
Node-RED or scheduled worker
  -> authenticated HTTPS request with event_key + sealed digest/signature metadata
  -> Fabric integration API
  -> Fabric Gateway
~~~

The API must authenticate the caller, validate the schema, enforce rate limits, avoid accepting arbitrary chaincode function names, and return a clear commit-status model.

## 5.6 Logging

Log:

- event_key;
- contract and schema version;
- adapter version;
- evidence schema version;
- for v2, gateway verification ID and verifier status/reason without logging raw journal payloads;
- evidence signing-key ID and signature algorithm;
- local-seal verification result;
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
