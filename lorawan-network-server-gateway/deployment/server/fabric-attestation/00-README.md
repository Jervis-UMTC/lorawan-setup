# External Hyperledger Fabric Integration Lab

This folder tests **our client/integration side only**. Another team creates and operates the Hyperledger Fabric network.

Do not create Fabric organizations, peers, orderers, CAs, channels, or a Fabric test network as part of this LoRaWAN lab.

## Data path

```text
LoRaWAN
  -> gateway delivery + journal evidence paths
  -> remote MQTT / ChirpStack
  -> Node-RED operational normalization
  -> TimescaleDB
       |
       +-> v1 historical application-only evidence
       |
       +-> v2 gateway evidence verifier
              -> journal/checkpoint continuity
              -> remote gateway-MQTT match
              -> ChirpStack lineage
              -> trusted decoder comparison
              -> VERIFIED
  -> durable Fabric outbox
  -> Fabric adapter/client container
       |
       +-> OpenBao Transit KMS
       |    -> non-exportable ecdsa-p256 evidence key
       |    -> sign / verify exact canonical bytes
       |
       +-> <FABRIC_GATEWAY_ENDPOINT>
  -> existing <FABRIC_CHANNEL_NAME>
  -> existing <FABRIC_CHAINCODE_NAME>
  -> commit status / transaction ID back to TimescaleDB
```

The adapter runs with the LoRaWAN application services and the Fabric network is external. In the barebones dissertation VM, the historical lab still uses its existing telemetry database profile. In the **three-Droplet cloud HA POC**, do not deploy a fourth standalone TimescaleDB server: install the same TimescaleDB extension build on all three Patroni/PostgreSQL members, enable it in `lorawan_telemetry`, keep telemetry in Timescale hypertables, and keep the outbox as an ordinary table in that same HA database. See [../cloud-production/20-openbao-and-fabric-adapter.md](../cloud-production/20-openbao-and-fabric-adapter.md).

The gateway-integrity ingestor, MQTT evidence collector, and verifier are documented as **required roles for v2**, but this repository does not yet contain completed reviewed images for them. Do not add invented Compose images. v1 lab testing can continue unchanged; v2 acceptance is blocked until those reviewed implementations and the separate v2 canonicalization test vector exist.

The lab deliberately runs **one** OpenBao container so Test 6/Test 12 can simulate a complete KMS outage. Do not copy that one-node KMS shape into production. The three-Droplet cloud deployment uses **OpenBao-1/2/3 as a three-member Integrated Storage/Raft cluster** and **Fabric adapter-1/2 as two lease-based workers**; see [../cloud-production/20-openbao-and-fabric-adapter.md](../cloud-production/20-openbao-and-fabric-adapter.md). This is the minimum cloud mapping that avoids a single OpenBao node while keeping the external Fabric network outside this repository.

## Read in this order

1. [Collect the external Fabric handoff](01-collect-external-fabric-handoff.md)
2. [Deploy the OpenBao evidence KMS](01-deploy-openbao-kms.md)
3. [Create the durable outbox and deploy the adapter](02-create-outbox-and-adapter.md)
4. [Test submission, KMS/Fabric outages, and reconciliation](03-test-and-reconcile.md)

For the dissertation's controlled post-storage integrity experiment, the adapter or companion verifier must also implement the read-only current-source canonicalization mode defined in [02-create-outbox-and-adapter.md](02-create-outbox-and-adapter.md). The experiment procedure is [Execution 05 - Data Integrity](../../../test/execution/05-data-integrity.md).

Also read:

- the reusable [Gateway Integrity manuals](../integrations/gateway-integrity/00-README.md) for v2 source verification; and
- the reusable [Hyperledger Fabric manuals](../integrations/hyperledger-fabric/00-README.md) for sealing/submission.

## Required values from the Fabric team

Do not invent these:

```text
<FABRIC_GATEWAY_ENDPOINT>
<FABRIC_MSP_ID>
<FABRIC_CHANNEL_NAME>
<FABRIC_CHAINCODE_NAME>
<FABRIC_CA_CERT>
<FABRIC_CLIENT_CERT>
<FABRIC_CLIENT_KEY>
<FABRIC_TLS_SERVER_NAME>
```

Also obtain the exact submit/query function names, contract/schema version, endorsement expectations, duplicate behavior, commit-status semantics, certificate rotation process, rate limits, maintenance windows, and support contact.

## Non-blocking rule

Fabric availability must never be part of the telemetry ingestion transaction.

Node-RED writes accepted telemetry and the selected outbox job to the selected telemetry PostgreSQL database first. In the cloud HA POC, that database is `lorawan_telemetry` on Patroni. For v2, that job is **not seal-eligible** until the independent verifier reports `verified`. The adapter submits later. When Fabric, KMS, or gateway evidence verification is unavailable:

```text
MQTT ingestion       -> continues
ChirpStack           -> continues
Node-RED validation  -> continues
telemetry PostgreSQL -> continues
Fabric outbox        -> accumulates with bounded retry/backoff
OpenBao KMS          -> may be unavailable/sealed without blocking telemetry
Gateway verifier     -> may be pending/gap/failure without stopping telemetry
v2 outbox work        -> remains unsealed until verification is eligible
Fabric adapter        -> retries/reconciles independently; never bypasses evidence or KMS verification
```

## What this lab must prove

- selected telemetry creates one durable outbox record using a stable event key;
- historical v1 behavior remains reproducible and its fixed RFC 8785 vector remains unchanged;
- when v2 is enabled, journal/checkpoint/remote-MQTT/application/trusted-decoder evidence reaches `verified` before the adapter may seal the row;
- v2 `pending`, `evidence_gap`, and `integrity_failure` cannot be silently promoted by Node-RED or the adapter;
- the Fabric adapter uses only the client identity supplied for this integration;
- OpenBao Transit owns a non-exportable `ecdsa-p256` evidence key and the adapter receives only least-privilege sign/verify authorization;
- one sealed outbox row stores the exact RFC 8785 canonical JSON, matching SHA-256, complete OpenBao versioned signature, and derived KMS key-version ID;
- a one-byte change fails OpenBao verification;
- an OpenBao sealed/unavailable condition blocks only evidence sealing/verification and Fabric submission, not MQTT, ChirpStack, Node-RED, or telemetry PostgreSQL ingestion;
- TLS validates `<FABRIC_TLS_SERVER_NAME>` against `<FABRIC_CA_CERT>`;
- transaction submission uses the existing channel and chaincode;
- endorsement/submission errors are classified;
- a transaction ID is not treated as confirmation until commit status is valid;
- timeouts after submission enter `submitted_unknown` and are reconciled before retry;
- duplicate retries do not create conflicting ledger state;
- Fabric outage does not block telemetry ingestion or telemetry PostgreSQL storage;
- the queue drains after Fabric recovery;
- failed/dead-letter items retain enough information for manual reconciliation;
- Grafana exposes queue age, failures, submitted-unknown jobs, commit latency, and gateway-evidence pending/gap/failure state where the v2 implementation is enabled.
