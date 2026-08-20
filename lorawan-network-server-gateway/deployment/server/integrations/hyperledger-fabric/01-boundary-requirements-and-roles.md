# 1. Boundary, Requirements, and Roles

Start with the business reason for using Fabric. Do not begin by copying every MQTT message onto a blockchain, installing Fabric components on the gateway, or requesting an administrator identity. A permissioned ledger is useful when multiple organizations need a shared, tamper-evident record and no single organization should silently rewrite the history.

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
| Gateway journal/checkpoint contract and evidence verification | Own | Consulted | Yes when v2 is used |
| Trusted decoder and Node-RED comparison policy | Own | Consulted | Yes when v2 is used |
| Telemetry canonicalization and hashing | Own | Consulted | Yes |
| Channel membership | No | Own | Yes |
| Endorsement policy | No | Own | Yes |
| Which data is public to channel members | Consulted | Consulted | Own jointly |
| Integration adapter deployment | Own or application team | Consulted | Yes |
| Incident response | First-line for MQTT/database | First-line for Fabric | Joint escalation |

The exact ownership must be written into the project handoff. A blockchain team should not be expected to infer the meaning of project fields such as `test_sequence`, `sensor_validity_bitmap`, `barometer_pressure_pa`, gateway IDs, device IDs, or ChirpStack event timing.

## 1.4 Requirements to freeze before development

Approve and version the following before development:

1. The business event that creates a ledger record.
2. Whether every reading is recorded or only windows, exceptions, or signed summaries.
3. The organizations that must read, submit, endorse, or approve.
4. The channel or private data collection that will contain the record.
5. The required finality and acceptable delay.
6. The retention policy for TimescaleDB and the off-chain evidence.
7. The canonical JSON serialization and hash algorithm.
8. The idempotency key and retry behavior.
9. The correction, supersession, rejection, and dispute process for erroneous measurements.
10. Whether the pilot uses historical `telemetry-attestation-v1` or gateway-verified `telemetry-attestation-v2`.
11. For v2, the exact gateway-evidence requirements that produce `verified`, `evidence_gap`, and `integrity_failure`.
12. For v2, the pinned trusted decoder and the policy when it disagrees with Node-RED/TimescaleDB.
13. The owner of the Fabric identity used by the adapter.
14. The exact evidence retained when submission outcome is unknown.

## 1.5 A safe first pilot

Use a low-risk, non-safety-critical pilot:

~~~text
For each selected device and time window using v2:
  1. Wait for the gateway evidence verifier to report VERIFIED.
  2. Query the accepted TimescaleDB row plus the verified gateway-evidence references.
  3. Canonicalize the fixed telemetry-attestation-v2 projection.
  4. Calculate the digest and seal the exact bytes through OpenBao.
  5. Submit one attestation transaction to Fabric.
  6. Wait for valid commit status.
  7. Store the Fabric transaction ID/status in the outbox.
  8. Reconcile the ledger digest against the preserved sealed evidence.
~~~

This proves the integration without creating a ledger transaction for every radio packet. If the pilot intentionally stays on v1, preserve the original v1 meaning and do not claim gateway-journal verification.

Next: [02-fabric-network-handoff.md](02-fabric-network-handoff.md)
