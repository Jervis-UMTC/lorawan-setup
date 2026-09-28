# Documentation Baseline — Commissioning Through 2026-09-18; Research Readiness Snapshot 2026-09-21

This file freezes the documentation authority and current architecture assumptions to use when creating or revising LoRaWAN infrastructure manuals. It is not a deployment runbook and it does not replace live verification.

## Authority order

When sources disagree, use this order:

1. Fresh verified live state, when access is available and the check is directly relevant.
2. [`../server/cloud-production/00-current-server-continuation-checkpoint.md`](../server/cloud-production/00-current-server-continuation-checkpoint.md) for the latest commissioned system boundary.
3. Current implementation, migrations, contracts, and deployment material under `../../evidence-services/` and the active gateway/firmware source trees.
4. Current component runbooks linked from the technology guides.
5. Dated build logs, archived plans, thesis extracts, and bring-up handoffs only as historical provenance.

A failed live probe is not evidence that a previously commissioned component changed state. During the 2026-09-17 documentation audit, a direct SSH probe from the documentation workspace was denied by public-key authentication, so this audit makes no new host-runtime claim from that failed attempt.

## Fresh limited live observations — 2026-09-21, 08:09–08:11 UTC

The documentation audit used the dedicated **restricted, read-only research-recorder SSH identity**, not an administrative shell, on Gateway-01 and ULC-01/02/03. The sanitized source is `LIVE-READONLY-CHECKPOINT.json` in this directory. All four forced-command `version` and bounded `snapshot` calls succeeded. These observations do **not** prove every application path, radio packet, backup restore, HRC commit or failover.

- ULC-01, ULC-02 and ULC-03 answered their correct host identity and returned database roles **leader**, **replica**, **replica**, respectively. This is a dated elected-primary observation only, not a permanent leader assignment.
- ULC-01 evidence collector-1, ULC-02 verifier-1, ULC-03 collector-2/verifier-2 each returned approved `evidence-ready` PASS. Docker snapshots showed the intended ChirpStack containers on ULC-01/02 and active Node-RED and Grafana containers on ULC-03; **the snapshots alone do not prove** application flow correctness, identical image parity or Fabric standby enable flags.
- Gateway-01 returned a route involving production LTE `wwan0` and **two established cloud MQTT :8883 TCP sockets**. This is connectivity evidence at that instant, not a proof of a new EMU physical uplink or HRC commit.
- Workstation restricted Grafana tunnel `http://127.0.0.1:3000/api/health` returned HTTP 200, `database=ok`, and Grafana **13.2.0**. Its authenticated dashboard UID/installed panel count/refresh were **not** checked: 21 panels/10s remains the tracked JSON definition, while 14 panels/15s is an older access checkpoint.
- Wrapper versions are **not identical across ULCs**: ULC-01 reported `research-recorder-server-v10`, ULC-02/ULC-03 `research-recorder-server-v8`, and Gateway-01 `research-recorder-gateway-v3`; compatibility must be checked per verb/host. Prior v7/v5 statements were source/historical records, not the observed deployed fleet.

The generated formal readiness report most recently inspected was `2026-09-21T07:55:23Z`: Technical gate PASS, LTE PASS, Live PRE PASS, released **PRE and P1 only**. Concurrent separately owned research work can generate a newer report; always read it again before a counted experiment. This documentation audit does not start a counted run or advance a readiness label.

## Earlier same-day research readiness (superseded by the newer generated checkpoint above)

An earlier, superseded generated research gate at `test/automation/research-manual/CURRENT-READINESS.md`, timestamped `2026-09-21T06:19:32Z`, reported **Technical gate PASS**, Gateway LTE invariant PASS, Live PRE PASS, recorder CLEAN, tool compile PASS, MQTT tooling self-test PASS, contract/synchronization tests PASS, oversight audit PASS and counted firmware archive PASS. PRE and P1 are individually READY; other research experiments are not automatically released. An earlier same-day `05:30:45Z` run had LTE FAIL and live PRE SKIPPED; **do not copy that superseded failure as current status**. This is a dated generated report rather than a fresh live infrastructure probe; run the appropriate gate again before starting counted work.

## Stable current architecture facts

- Regional plan is **plain AS923** and the MQTT region prefix is `as923`. Do not substitute AS923-3 unless an intentional end-to-end migration is later commissioned.
- Gateway-01 uses Raspberry Pi / ChirpStack Gateway OS, RAK5146, ChirpStack Concentratord, local persistent Mosquitto, and the software evidence journal/uploader. Gateway EUI is `0016c001f139a1cb`.
- SIM7600 `wwan0` is the health-gated production-primary WAN path. The current tracked field overlay does **not** promise automatic Wi-Fi Internet fallback; configure and prove one separately if required. Ethernet is management-only and must not silently become the production data path.
- Cloud Mosquitto is preferred/backup service HA, not replicated MQTT-session active/active.
- ChirpStack runs as the commissioned two-node application/network-server tier; Valkey/Sentinel provides its HA cache/runtime support.
- PostgreSQL/Patroni/TimescaleDB is the three-member durable data layer, coordinated through etcd. HAProxy and PgBouncer provide stable routing/pooling.
- Node-RED is active/passive: ULC-03 is the active application writer and ULC-02 is fenced standby. Do not run both merely for availability.
- Grafana is read-only observability. Counted research truth comes from the research-recorder/sealed result artifacts, not dashboard screenshots alone.
- Gateway evidence ingest, MQTT collectors, verifier replicas, trusted decoder, PostgreSQL evidence metadata, and SeaweedFS raw evidence storage are commissioned. Real v2 gateway lineage has passed.
- OpenBao is the commissioned three-member KMS/Transit cluster used by the Fabric integration.
- HRC Task 37 is commissioned. Fresh 2026-09-18 read-only checks show ULC-01 `enabled=true` / `status=ready` with worker `fabric-adapter-ulc-01`, while ULC-02 is healthy `enabled=false` / `status=standby`. ULC-02 remains fenced because its live image reference differs from ULC-01 and current image parity/generation-fencing takeover acceptance has not yet been re-proven.

## Current Fabric contract

```text
Gateway endpoint: 10.104.0.7:7051
TLS server name:  peer1.hrc.local
MSP:              HrcMSP
Channel:          hrc-channel
Chaincode:        hrc-evidence
Source namespace: lorawan-gateway-evidence

CreateSourceBoundAnchor(SourceRecordID, sourceType, producer, producedAt, schemaVersion)
  transient hrc.exact_payload = immutable finalized_payload bytes
QuerySourceBoundAnchor(SourceRecordID)
VerifySourceBoundDigest(SourceRecordID, sha256(finalized_payload))
```

The retired `CreateAnchor`, `QueryAnchor`, `QueryAnchorByRecordID`, and `VerifyDigest` APIs must not be restored. Exact `finalized_payload` bytes must never be reconstructed from JSONB, `raw_data`, maps, structs, or projections.

For a new Fabric claim, `finalized_payload IS NOT NULL` is mandatory. A `telemetry-attestation-v2` row additionally requires exactly matching verifier-owned `status='verified'`. Therefore a row can remain `pending` with `attempts=0` while the Fabric writer itself is healthy.

Current post-submit lifecycle is `reconciling` for uncertain recoverable state and `needs_attention` for permanent/conflicting evidence. `submitted_unknown` remains only as migration compatibility and is not emitted by the current worker. Prepared transaction bytes and the signed commit-status request are persisted so recovery can use the same transaction rather than blindly resubmitting.

## Open gates that must stay visible

- ULC-02 Fabric takeover/ownership/fencing acceptance. Fresh 2026-09-18 state is intentionally blocked before takeover because ULC-01 reports `gateway-fabric-adapter:fairness-20260915` while ULC-02 reports `9e08e25fe5dd`; load/verify one accepted current build on both nodes while ULC-02 remains disabled, verify worker identity and migration 003, then run the controlled failover gate.
- DigitalOcean Reserved IPv4 reassignment authority and controlled failover acceptance.
- Upstream research outbox finalization/eligibility for any future rows that lack immutable `finalized_payload` or required verifier state. The fresh 2026-09-18 monitor snapshot showed `2094/2094` Fabric outbox rows confirmed and `2094/2094` evidence verifications verified, so the earlier pending backlog is historical rather than a current blocker.
- Explicitly deferred destructive backup/restore and failure-injection acceptance tests.
- Experiment-specific research GO/NO-GO gates under `test/`; a commissioned infrastructure layer does not automatically make every experiment ready.

## Superseded statements — never copy as current truth

Do not reintroduce these into active manuals:

- `AS923-3` as the commissioned regional plan.
- `GATEWAY_EVIDENCE_RUNTIME=SERVER_PASS_GATEWAY_PENDING`.
- `GATEWAY_EVIDENCE_V2_NORMAL_PATH=NOT_YET_CLAIMED`.
- “Fabric handoff pending” or “adapter image missing” for the current HRC deployment.
- Instructions to run ULC-01 and ULC-02 simultaneously as enabled Fabric writers.
- `submitted_unknown` as the normal current uncertain-submit state.
- The retired HRC Fabric transaction names listed above.
- Historical commissioning status statements from `00-build-execution-log.md` or `docs/archive/**` presented as present-tense operator instructions.

## Standard structure for final technology documentation

For each technology, document: purpose and ownership; current placement; interfaces and ports; dependencies; current configuration/identity; normal operations; recovery; verification/acceptance; troubleshooting by failing layer; security boundaries; and authoritative references. Keep chronological debugging detail in historical logs rather than duplicating it into current manuals.
