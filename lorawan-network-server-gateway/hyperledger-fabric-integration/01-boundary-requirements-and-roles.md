# 1. Boundary, Requirements, and Roles

Start with the business reason for using Fabric. Do not begin by copying every MQTT message onto a blockchain. A permissioned ledger is useful when multiple organizations need a shared, tamper-evident record and no single organization should silently rewrite the history.

## 1.1 Suggested use cases

Choose one concrete use case for the first pilot:

| Use case | On-chain record | Off-chain detail |
|---|---|---|
| Sensor reading attestation | Hash, device reference, event time, source, submitter, status | Full decoded payload, raw data, charts |
| Produce custody transfer | Transfer ID, current owner, timestamp, approval state | Temperature history, documents, photos |
| Quality inspection | Inspection ID, result, inspector organization, evidence hash | Inspection form, images, laboratory files |
| Equipment maintenance | Asset ID, work-order state, approval, completion time | Vibration history, technician notes, manuals |
| Port cargo or reefer condition | Container or asset reference, condition attestation, exception state | Full time series, alarms, location history |

Do not call the first use case simply blockchain telemetry. State exactly which decision, dispute, or audit problem the ledger solves.

## 1.2 What should remain off-chain?

Keep these in TimescaleDB or an object store:

- every periodic sensor sample;
- high-frequency data;
- raw LoRaWAN payloads;
- personally identifiable information;
- images, documents, and large evidence files;
- data that must be deleted under a retention policy;
- operational dashboards and aggregates.

Put only the minimum verifiable record on Fabric:

- an opaque event or asset identifier;
- the observation time and ingestion time;
- the source gateway or system identifier;
- the measurement summary or business state;
- the hash of the canonical off-chain record;
- the off-chain locator or retention reference;
- the submitting organization and schema version.

Hashing proves that a later file matches the committed digest. It does not prove that the sensor was calibrated, that the input was truthful, or that the original file was lawfully collected.

## 1.3 Responsibility matrix

| Responsibility | LoRaWAN/platform team | Fabric/network team | Joint decision |
|---|---:|---:|---:|
| Gateway, ChirpStack, MQTT | Own | Consulted | No |
| TimescaleDB telemetry schema | Own | Consulted | No |
| Fabric organizations and peers | No | Own | No |
| Fabric CA, MSP, TLS | No | Own | No |
| Chaincode business logic | Consulted | Own or assigned developer | Yes |
| Telemetry canonicalization and hashing | Own | Consulted | Yes |
| Channel membership | No | Own | Yes |
| Endorsement policy | No | Own | Yes |
| Which data is public to channel members | Consulted | Consulted | Own jointly |
| Integration adapter deployment | Own or application team | Consulted | Yes |
| Incident response | First-line for MQTT/database | First-line for Fabric | Joint escalation |

The exact ownership must be written into the project handoff. A blockchain team should not be expected to infer the meaning of TempC_SHT31, gateway IDs, device IDs, or ChirpStack event timing.

## 1.4 Requirements to freeze before development

Write down:

1. The business event that creates a ledger record.
2. Whether every reading is recorded or only windows, exceptions, or signed summaries.
3. The organizations that must read, submit, endorse, or approve.
4. The channel or private data collection that will contain the record.
5. The required finality and acceptable delay.
6. The retention policy for TimescaleDB and the off-chain evidence.
7. The canonical JSON serialization and hash algorithm.
8. The idempotency key and retry behavior.
9. The correction process for an erroneous measurement.
10. The owner of the Fabric identity used by the adapter.

## 1.5 A safe first pilot

Use a low-risk, non-safety-critical pilot:

~~~text
For each selected device and time window:
  1. Query the accepted rows from TimescaleDB.
  2. Canonicalize the selected summary.
  3. Calculate a digest.
  4. Submit one attestation transaction to Fabric.
  5. Wait for the commit status.
  6. Store the Fabric transaction ID back in TimescaleDB.
  7. Verify the digest from the original rows.
~~~

This proves the integration without creating a ledger transaction for every radio packet.

Next: [02-fabric-network-handoff.md](02-fabric-network-handoff.md)
