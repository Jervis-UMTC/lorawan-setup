# End-to-End Integration and Data Lineage — Operator Manual

> **Scope:** This is the companion to the 20 individual [technology manuals](00-README.md). It explains the interfaces *between* them. For exact deployment commands, configuration, and rollback, use the linked component manual. The baseline below is grounded in the [2026-09-17 documentation checkpoint](CURRENT-DOCUMENTATION-BASELINE.md) and [cloud continuation checkpoint](../server/cloud-production/00-current-server-continuation-checkpoint.md); it is **not** a fresh live health report.

## What the system is intended to prove

The project acquires real agricultural sensor observations, transports them over LoRaWAN, stores usable telemetry, and independently preserves/verifies evidence of the gateway-originated data path before eligible evidence is anchored in HRC Hyperledger Fabric. A dashboard picture is not the authoritative measurement or immutable evidence record. Preserve the exact source bytes and the supervised research-recorder output when making research claims.

## System boundaries and owners

| Boundary | Producer → consumer | Contract / evidence | First diagnosis |
|---|---|---|---|
| Measurement | EMU-01 sensor → RAK5146 | RAK4631 firmware payload-v2; accepted profile is OTAA, Class A, **plain AS923**, 46-byte application payload | [Sensor firmware](18-rak4631-wisblock-sensor-firmware.md), [RF/Concentratord](02-rak5146-concentratord-as923.md) |
| RF forwarding | RAK5146/Concentratord → gateway MQTT forwarder | Gateway EUI `0016c001f139a1cb`; MQTT region prefix `as923` | [Gateway OS](01-gateway-os-openwrt.md), [ChirpStack](05-chirpstack.md) |
| Cloud transport | Gateway local persistent Mosquitto → cloud Mosquitto | mTLS bridge over health-gated SIM7600 `wwan0` production-primary WAN; separately configured Wi-Fi fallback is not assumed; management Ethernet must not silently become production uplink | [LTE](03-sim7600-lte-backhaul.md), [Mosquitto](04-mosquitto-mqtt.md), [PKI](17-pki-tls-and-service-identity.md) |
| LoRaWAN server | Cloud MQTT → ChirpStack | Gateway event, device identity, frame counters, OTAA/session and regional parameters | [ChirpStack](05-chirpstack.md), [Valkey/Sentinel](09-valkey-sentinel.md) |
| Application | ChirpStack MQTT integration → Node-RED | Source identity, received payload, decode/validation, measurement mapping | [Node-RED](10-node-red.md) |
| Persistence | Node-RED → PostgreSQL/TimescaleDB | Telemetry writes and atomic Fabric outbox creation; one active Node-RED writer (ULC-03), fenced ULC-02 standby | [Node-RED](10-node-red.md), [Database](07-postgresql-patroni-timescaledb.md) |
| Evidence | Gateway journal + MQTT witness + application events → evidence services | Raw evidence in SeaweedFS; metadata and verifier-owned results in PostgreSQL | [Evidence services](14-gateway-evidence-services.md), [SeaweedFS](13-seaweedfs.md) |
| Claim eligibility | Verifier/finalizer → `telemetry.fabric_outbox` | Immutable `finalized_payload IS NOT NULL`; v2 additionally requires exactly matching verifier-owned `status='verified'` | [Evidence services](14-gateway-evidence-services.md), [Fabric adapter](15-hyperledger-fabric-adapter.md) |
| Blockchain | Sole enabled adapter on ULC-01 → OpenBao/HRC Fabric | Source-bound contract; exact finalized bytes in transient `hrc.exact_payload`; authoritative commit, query, digest-match | [OpenBao](12-openbao.md), [Fabric adapter](15-hyperledger-fabric-adapter.md) |
| Display/research | Database/service metrics → Grafana/recorder | Grafana for observation; sealed recorder artifacts for counted measurements | [Grafana](11-grafana.md), [Research recorder](19-research-recorder-and-test-automation.md) |

## Follow one physical observation

1. On EMU-01, capture the serial `SENSOR_TX` marker, firmware identity/profile, observation time, and original application bytes. Do not substitute a synthetic payload without marking the run synthetic.
2. At Gateway-01, distinguish RF reception from MQTT delivery. Confirm the exact regional and device settings *end to end* before modifying radio parameters.
3. At the gateway's local MQTT buffer and LTE route, verify whether the message has reached the bridge. A healthy RF receiver does not prove cloud connectivity; a connected modem does not prove this MQTT flow used LTE.
4. In cloud MQTT and ChirpStack, match gateway/device IDs and the representative event to the application integration. Use frame counters and timestamps appropriately; avoid assuming one event per radio attempt.
5. In Node-RED and PostgreSQL, verify the application record and any derived measurements. Count persisted rows separately from radio transmissions, MQTT deliveries, and blockchain anchors.
6. In the evidence lane, correlate the gateway journal, MQTT witness, raw object, verifier result, and finalization by canonical source identity and observation time. Preserve raw object identity and immutable bytes.
7. In the Fabric outbox, assess eligibility before examining adapter or blockchain health. A `pending` row with `attempts=0` can be correct when finalization/verification has not completed.
8. For eligible claims, verify that only the ULC-01 adapter is write-enabled until the ULC-02 fencing gate passes. Confirm the HRC commit status, `QuerySourceBoundAnchor` and `VerifySourceBoundDigest` match; do not equate a submitted proposal with final ledger acceptance.
9. For research results, retain the run manifest, original capture, derived measurements, validation output, and seals/checksums under the protected `chapter4-results/` tree using the [research recorder](../../test/automation/research-recorder/README.md) and the current [testing instructions](../../test/00-README.md).

## HRC exact-payload contract

```text
Gateway endpoint: 10.104.0.7:7051
TLS server name:  peer1.hrc.local
MSP:              HrcMSP
Channel:          hrc-channel
Chaincode:        hrc-evidence
Source namespace: lorawan-gateway-evidence

CreateSourceBoundAnchor(SourceRecordID, sourceType, producer, producedAt, schemaVersion)
  transient hrc.exact_payload = exact immutable finalized_payload bytes
QuerySourceBoundAnchor(SourceRecordID)
VerifySourceBoundDigest(SourceRecordID, sha256(finalized_payload))
```

Never reconstruct `finalized_payload` from a JSONB projection; never restore retired transaction names. If submission outcome is uncertain, use the durable prepared transaction and signed commit-status request in `reconciling` rather than blindly creating another transaction. ULC-02 is a fenced standby until build parity, ownership, and the controlled takeover acceptance are proven.

## Failure isolation matrix

| Missing result | First boundary to prove | Do not assume |
|---|---|---|
| No sensor result | Sensor power/firmware/SERIAL, then AS923 RF | Database or Fabric outage |
| Gateway hears sensor, no cloud event | Local MQTT, LTE route, TLS bridge, cloud broker | Bad sensor payload |
| ChirpStack event but no measurement | Integration topic, Node-RED decode/validation, database write | Radio failure |
| Measurement but no verified evidence | Journal/witness correlation, raw object, verifier/finalizer | Fabric transaction failure |
| Pending outbox with zero claims | Exact finalized bytes and v2 verifier match | Fabric writer dead |
| Eligible row not confirmed | Sole writer, DB lease/fencing, OpenBao, Fabric gateway, endorsement, commit, query/digest | A generic network issue |
| Grafana not showing data | SQL datasource/query/time window, then upstream writer | That no sensor data arrived |
| Research test not marked ready | Test-specific GO/NO-GO, firmware profile, synchronized clocks, recorder captures | That whole platform is down |

## Safe service/recovery ordering

For a fresh rebuild, restore network and trust material; etcd; PostgreSQL/Patroni/TimescaleDB and HAProxy/PgBouncer; Valkey/Sentinel and Mosquitto; ChirpStack; OpenBao and evidence/object storage; Node-RED/Grafana; gateway radio, buffered MQTT and LTE; evidence services; and finally Fabric adapter plus real end-to-end verification. Check actual dependencies and roles; this order is not an instruction to restart a working cluster.

For a partial outage, repair the earliest failing layer and verify one representative real operation. Keep buffered gateway data and durable Fabric reconciliation state. Never purge research evidence, delete journal lineage, clear the outbox, enable a second writer, or invoke failover to make a dashboard temporarily green.

## Complete rebuild and cross-layer acceptance companion

Use [end-to-end rebuild order, one-event lineage, failure isolation, data-quality rules and whole-platform acceptance](END-TO-END-REBUILD-LINEAGE-ACCEPTANCE.md). It combines dependency order without replacing the technology-specific recovery chapters.

## Minimum acceptance evidence

- Actual firmware/profile, sensor, Gateway EUI, AS923 settings and original payload identified.
- Sensor RF → local MQTT → cloud MQTT → ChirpStack → application → database traceable for one real observation.
- Verifier-owned matching evidence and raw object available for v2 claims.
- If anchoring is tested, sole adapter writer and authoritative Fabric commit/query/digest result confirmed.
- Timestamps, collection method, units, test mode and checksums in the retained research artifact.
- No immediately relevant critical error; explicitly state any layer that could not be tested.

See [Word document publication and review](WORD-PUBLICATION.md) before releasing this guide or the 20 technology manuals as PDFs.
