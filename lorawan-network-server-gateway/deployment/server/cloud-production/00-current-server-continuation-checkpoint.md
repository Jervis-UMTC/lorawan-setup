# Current Server / Gateway / Sensor State

**Authoritative current-state summary through 2026-09-17.** This file is intentionally concise. It records the latest verified operating boundary only; commissioning chronology, superseded values, failed attempts, and dated debugging detail belong in [`00-build-execution-log.md`](00-build-execution-log.md) or the relevant component manual.

## Operator entry points

- Research execution and evidence capture: [`../../../test/00-README.md`](../../../test/00-README.md), [`../../../test/automation/research-recorder/README.md`](../../../test/automation/research-recorder/README.md), then the selected manual under `../../../test/execution/`.
- Cloud deployment/operations: this file, then [`00-README.md`](00-README.md) for the component map.
- Detailed historical commissioning evidence: [`00-build-execution-log.md`](00-build-execution-log.md). Do not use old intermediate status statements there as current truth.
- Historical plans, raw thesis extracts, and completed bring-up handoffs are under `../../../docs/archive/` and are not operator authorities.

## Fresh pre-test readiness scan - 2026-09-16

A new non-destructive end-to-end readiness scan was executed on 2026-09-16 before counted research work. The repository readiness gate `test/automation/research-manual/ensure_ready.py` completed with `TECHNICAL_GATE=PASS`, `TOOL_COMPILE=PASS`, `MQTT_TOOL_SELFTEST=PASS`, `COUNTED_FIRMWARE=PASS`, `RECORDER_STATE=CLEAN`, `GATEWAY_LTE=PASS`, and `LIVE_PRE=PASS` at `2026-09-16T07:05:21Z`.

Fresh verified facts from this scan:

- EMU-01 is present on `COM11`; SEC is present on `COM16`.
- The archived 15-second counted EMU-01 profile is reproducible and hash-consistent with the current tracked source. The boot capture recorded `EMU01_SENSOR_INIT=PASS`.
- Gateway-01 LTE is up on `wwan0`; the metric-10 default route and the route to the production MQTT endpoint use LTE; both MQTT TLS bridge sockets are established; the SIM7600 is registered on LTE.
- ULC-01/02/03 and Gateway-01 are reachable through the restricted research-recorder path.
- PostgreSQL still presents exactly one leader in the recorder preflight.
- Gateway-evidence collector/verifier readiness checks are HTTP 200 on their commissioned nodes.
- The latest accepted gateway checkpoint for `0016c001f139a1cb` was visible during the live preflight, and no `evidence_gap` / `integrity_failure` condition caused the gate to fail.
- Cross-host timing passed the recorder's strict readiness limits: cloud spread remained below 250 ms and gateway/cloud skew remained below 1.5 s.

This is the current **technical platform readiness** boundary. It does not replace the formal sensor GO/NO-GO procedure in `test/preparation/sensor/preflight/04-go-no-go-transition.md`. Before a counted full-stack run, preserve fresh evidence for the final sensor build: OTAA JoinRequest/JoinAccept, at least ten consecutive post-join uplinks with zero selected codec errors, source-to-decoder comparison, application/TimescaleDB correlation, and the required Fabric/outbox condition. The current live PRE intentionally does not fabricate those research observations.

The test-command compatibility matrix is also intentionally fail-closed: `PRE` and `P1` are fully `READY`; several later experiments remain `CAPTURE_READY` or `HARNESS_REQUIRED`, and `S2` remains `METHODOLOGY_REQUIRED`. Those labels are experiment-orchestration/methodology gates, not failures of the commissioned LoRaWAN infrastructure.

## Research/Fabric eligibility diagnostic - 2026-09-17

The current adapter implementation and research diagnosis add one important operator rule: a Fabric outbox row can remain `pending` with `attempts=0` even while the ULC-01 writer is healthy. The normal claim query requires immutable `finalized_payload IS NOT NULL`; `telemetry-attestation-v2` additionally requires a matching verifier-owned `gateway_evidence.event_verification.status='verified'` row. Diagnose outbox finalization/eligibility before treating an unclaimed row as a Fabric, OpenBao, or worker outage.

The commissioned HRC Task 37 API remains source-bound: `CreateSourceBoundAnchor(SourceRecordID, sourceType, producer, producedAt, schemaVersion)` with exact immutable `finalized_payload` bytes sent only as transient `hrc.exact_payload`, followed by `QuerySourceBoundAnchor(SourceRecordID)` and `VerifySourceBoundDigest(SourceRecordID, observedDigest)`. Prepared transaction bytes and a signed commit-status request are persisted before orderer submission; uncertain outcomes enter governed reconciliation rather than blind resubmission. A stale HRC peer ledger can make client `CommitStatus` waiting appear hung even when endorsement and orderer submission succeeded, so troubleshoot those layers separately.

**Audit note:** a fresh direct SSH probe from the documentation workspace on 2026-09-17 was denied by public-key authentication. This audit therefore makes no new host-runtime claim from that failed probe; it reconciles current facts from commissioned checkpoints, research preflight evidence, and current implementation/source contracts.

## Current operational state

| Layer | Current verified state |
|---|---|
| etcd | 3-node quorum commissioned |
| PostgreSQL / Patroni / TimescaleDB | HA cluster commissioned; application and evidence database paths proven |
| HAProxy / PgBouncer | Commissioned verify-full database routing and role authentication |
| Mosquitto | Preferred/backup HA normal path commissioned; do not restore round-robin live-session routing |
| Valkey / Sentinel | HA path commissioned |
| ChirpStack | Two-node cloud cluster commissioned on plain `AS923` / MQTT prefix `as923` |
| OpenBao | 3-node KMS normal path and audit commissioned |
| Node-RED | `ulc-03` A active; `ulc-02` B fenced/standby; atomic telemetry + Fabric outbox path proven |
| Grafana | Server deployment and real telemetry/evidence read path commissioned |
| Gateway evidence | Gateway journal/uploader, replicated ingest/collectors/verifiers, trusted decoder, and object-storage path commissioned |
| Gateway-01 | RAK5146, AS923, SIM7600 LTE production-primary backhaul, management Ethernet, MQTT and evidence paths physically proven; **automatic Wi-Fi Internet fallback is not assumed** unless separately configured and live route-tested |
| EMU-01 | OTAA, payload-v2, production scheduler, application telemetry, and evidence lineage physically proven |
| Fabric | **ULC-01 production writes enabled and verified**; ULC-02 remains write-disabled until HA ownership/fencing acceptance |
| Public ingress | ChirpStack/Evidence/MQTT normal path commissioned on Reserved IPv4; provider-side reassignment/failover acceptance remains a separate gate |
| Research recorder | Core supervised capture path operational; fixed aggregate `evidence-status` wrapper extension remains a separately staged compatibility improvement where not yet deployed |

The current system is ready for the research procedures whose own GO/NO-GO gates pass. Do not recommission healthy infrastructure merely because an older dated section, plan, or build log describes a previously pending state.

## Fresh-start gateway evidence lineage baseline - 2026-09-11

A new deliberate evidence/test reset was completed at approximately `2026-09-11T02:44Z` after a live acceptance run exposed that Gateway-01 still retained its commissioned historical journal while the server metadata had previously been cleared. The operator explicitly requested that the Gateway-01 segment lineage be deleted and restarted from a true fresh origin.

Verified reset boundary:

- Gateway-01 evidence writer, uploader, and Mosquitto bridge were stopped before mutation.
- Gateway-01 had `226` closed journal segment files plus `1` open segment, with durable state `next_segment_id=227`, `next_sequence=3224`. All closed/open journal files, `journal-state.json`, and uploader receipt state were removed. Evidence TLS material, UCI configuration, firmware, and identities were preserved.
- The seven active research/runtime PostgreSQL tables were truncated with identities reset: `telemetry.uplinks`, `telemetry.measurements`, `telemetry.fabric_outbox`, `gateway_evidence.mqtt_gateway_events`, `gateway_evidence.event_verification`, `gateway_evidence.segments`, and `gateway_evidence.checkpoints`. The pre-reset counts were `9`, `117`, `9`, `271`, `9`, `4`, and `4` respectively; the transaction completed with all seven at `0`.
- Immutable SeaweedFS/raw object-store history was intentionally preserved. It has no active segment/checkpoint metadata references after this reset and must not be treated as current lineage.
- Gateway services were restarted in writer -> uploader -> Mosquitto order. The new durable journal state is exactly `next_segment_id=1`, `next_sequence=1`, `previous_record_hash=GENESIS`, `previous_segment_hash=GENESIS`, with `0` closed and `0` open segment files immediately after initialization.
- The uploader recreated an empty canonical receipt state: `{"checkpoint_receipts":{},"segment_receipts":{}}`.
- After the MQTT bridge reconnected, fresh gateway stats began arriving normally. At the first post-reset consistency check: `telemetry.uplinks=0`, `telemetry.measurements=0`, `telemetry.fabric_outbox=0`, `gateway_evidence.event_verification=0`, `gateway_evidence.segments=0`, and `gateway_evidence.checkpoints=0`; `gateway_evidence.mqtt_gateway_events=5` represented only new post-reset gateway traffic.
- Because the DITO uplink remained unavailable during this acceptance session, the already-established temporary opaque workstation relays for MQTT TLS and evidence HTTPS/mTLS remained in service. TLS and client-certificate authentication remain end-to-end; these relays are transport-only and are not a permanent architecture change.

**This 2026-09-11 boundary supersedes the prior Gateway journal lineage for new research testing. New evidence must begin from segment `1` / sequence `1` / `GENESIS`. Do not replay the deleted Gateway receipt/journal state into the active runtime.**

## Fresh-start testing baseline - 2026-09-10

A definitive active-runtime reset began at `2026-09-10T06:11:31Z` and was re-verified through `2026-09-10T06:21:33Z`. Both ChirpStack instances, both server Mosquitto brokers, Node-RED, the evidence ingest/collector/verifier workers, and both Fabric adapter instances were quiesced before state was cleared.

The reset deliberately established this empty testing epoch:

- `telemetry.uplinks`, `telemetry.measurements`, `telemetry.fabric_outbox`, `gateway_evidence.mqtt_gateway_events`, `gateway_evidence.event_verification`, `gateway_evidence.segments`, and `gateway_evidence.checkpoints` were truncated with identities reset; final counts remained exactly `0` on all three PostgreSQL members.
- Valkey DB 0 on the ULC-02 primary was reduced from `37` legacy ChirpStack metrics/stream keys to `0`, synchronously, and the empty state was saved and replicated. Those keys were prior metrics/stream runtime history rather than device registration/configuration.
- The server Mosquitto persistence databases on ULC-01 and ULC-02 were backed up and removed while the brokers were stopped. After the complete application stack had restarted, neither broker had recreated `mosquitto.db`, proving there was no persisted server-broker queue/session residue at the final check.
- Node-RED was restarted, clearing transient in-memory state. Its tracked/runtime flow configuration under `/srv/node-red/data` was preserved.
- ChirpStack registration state was intentionally preserved: `tenant=1`, `application=1`, `device=1`, `gateway=1`; `device_queue_item=0` and `multicast_group_queue_item=0` remained empty.
- Immutable SeaweedFS raw evidence objects, OpenBao audit/security history, configuration, identities/certificates, schemas, deployment material, and research/recovery archives were preserved. They are audit/recovery history, have no active telemetry/evidence database references after the reset, and cannot replay themselves into the live pipeline.

Fresh-start recovery copies:

```text
ULC-01 /var/backups/lorawan-clean-reset/freshstart-20260910T061131Z/mosquitto-ulc01.db
ULC-02 /var/backups/lorawan-clean-reset/freshstart-20260910T061131Z/mosquitto-ulc02.db
ULC-02 /var/backups/lorawan-clean-reset/freshstart-20260910T061131Z/valkey-ulc02-preflush.rdb
```

Final health proof after the reset: ULC-01 remained Patroni primary with ULC-02/03 streaming; the primary etcd quorum and the separate SeaweedFS metadata-etcd quorum answered healthy commit probes; both ChirpStack frontends returned HTTP `200`; evidence collectors and verifiers reported `ready`; Node-RED was Docker-healthy and HTTP `200`; Grafana `/api/health` reported database `ok`; OpenBao was initialized/unsealed with ULC-02 active; SeaweedFS master endpoints returned HTTP `200`; ULC-01 reached `10.104.0.7:7051` and logged `fabric_adapter_ready` with its canonical self-test passing; ULC-02 Fabric remained correctly fenced in standby. Every server had zero failed systemd units and zero exited Docker containers. MQTT/TLS reconnect warnings observed only while the brokers were deliberately stopped disappeared after stabilization, with zero post-stabilization application errors.

**This 2026-09-10 boundary is the authoritative empty testing epoch. Any telemetry/evidence rows or ChirpStack runtime metric/stream keys created after it are fresh post-reset data.**

## Prior clean server runtime baseline - 2026-09-09

A deliberate server-side clean reset was completed after the September 9 research/presentation work. Writers were quiesced first, the full `lorawan_telemetry` database was archived from the verified Patroni leader, and only active telemetry/evidence runtime rows were truncated. ChirpStack tenant/application/device/gateway registrations, database schemas, credentials, certificates, deployment files, persistent volumes, tagged rollback images, and `chapter4-results/` research evidence were preserved.

Recovery archive on ULC-01:

```text
/var/backups/lorawan-clean-reset/lorawan_telemetry-preclean-20260909T095657Z.dump
SHA-256 382723d51f126f0a555368a12bc15840664229e2e43004fba4e0c5a27c767580
/var/backups/lorawan-clean-reset/lorawan_telemetry-preclean-20260909T095657Z.manifest.txt
```

The post-clean replicated baseline is exactly zero rows in `telemetry.uplinks`, `telemetry.measurements`, `telemetry.fabric_outbox`, `gateway_evidence.mqtt_gateway_events`, `gateway_evidence.event_verification`, `gateway_evidence.segments`, and `gateway_evidence.checkpoints` on ULC-01/02/03. ULC-01 is the Patroni primary; ULC-02 and ULC-03 are streaming replicas at the same WAL location. Evidence collectors/verifiers are ready, the ULC-01 Fabric adapter is enabled/ready, the ULC-02 adapter is standby, Node-RED is healthy, both ChirpStack frontends return HTTP 200, Grafana health reports its database `ok`, and OpenBao is initialized/unsealed on all three nodes with ULC-02 active at this check. No exited Docker containers or failed systemd units remained. Old application Docker logs, closed `/tmp` deployment/test artifacts, the stale `grafana-pre-pgbouncer-fix-20260909` container, and disposable Docker build cache were removed; active configuration and recovery assets were not pruned.

## Fabric production boundary

ULC-01 passed the HRC Task 37 external qualification and is the only production-enabled Fabric writer at this boundary.

Verified integration anchors:

```text
FABRIC_GATEWAY_ENDPOINT=10.104.0.7:7051
FABRIC_TLS_SERVER_NAME=peer1.hrc.local
FABRIC_MSP_ID=HrcMSP
FABRIC_CHANNEL=hrc-channel
FABRIC_CHAINCODE=hrc-evidence
AuthenticatedSourceSystemID=lorawan-gateway-evidence
ULC-01 FABRIC_ADAPTER_ENABLED=true
ULC-02 FABRIC_ADAPTER_ENABLED=false
```

Qualification row `1960` is confirmed on Fabric transaction `dd11910c1e7c28edd11334a03cce10d80d574692733458c9059d2775be5131b8`; source-bound query and digest verification matched. On 2026-09-09 the ULC-01 production Adapter passed its activation preflight, had zero restarts, and had produced 325 post-activation confirmed writes (326 total including the qualification row). The verified immutable image ID is `sha256:d12e73ae24f7823730b6632fe8209e844c0d6125bd6a9c13e9d75cc330664f74`; service-binary SHA-256 is `a53990277d9032e60a9f0bfb52619a21e8c999a3573477dbfb3efe6ca6fb9591`.

Before the 2026-09-09 clean reset, no eligible verified exact-payload rows were waiting; the historical pending/dead-letter backlog and previously retained verifier-pending rows were runtime history, not replay candidates. That state is no longer present in the active database: it is preserved only in the pre-clean recovery dump and manifest listed above. Do not restore or replay that dump into production except for an explicit recovery/investigation, and do not rerun qualification candidate `1960`.

ULC-02 activation is a distinct HA boundary. Keep it `FABRIC_ADAPTER_ENABLED=false` until the documented ownership/fencing and failover conditions are deliberately accepted. Do not reuse HRC administrator material, the Task-39 writer, Caliper aliases, or temporary qualification credentials.

## Gateway and radio boundary

Gateway-01 is physically accepted on the commissioned AS923 image and configuration. The accepted image remains:

```text
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz
SHA-256 bafe8b97baf9353df2654b1c8b71fa53d2ff764cd264d0ed6c924dd25a5ec67d
Gateway EUI 0016c001f139a1cb
```

The live gateway has proven RAK5146 detection, intended EUI, AS923 radio operation, reboot persistence, protected identity restore, real EMU-01 traffic, evidence lineage, and SIM7600 LTE cloud transport. LTE is the health-gated production primary route, Wi-Fi is automatic fallback, and Ethernet remains management-only. Rebuild or reflash only for an actual regression or intentional image change.

EMU-01 uses the tracked source under `../../../firmware/EMU01_Agriculture_Node/`. The accepted application contract remains payload-v2, 46 bytes, OTAA, Class A, plain AS923, ADR, unconfirmed normal uplinks, and deterministic `SENSOR_TX` serial output. Production scheduling uses local sampling plus approximately five-minute staggered/jittered uplinks; temporary counted-test firmware is a research profile, not the production baseline.

## Evidence and application boundary

The accepted normal path is:

```text
EMU-01 -> LoRaWAN RF -> Gateway-01 -> LTE/mTLS MQTT -> ChirpStack
       -> Node-RED -> TimescaleDB -> Grafana
       -> telemetry.fabric_outbox -> Fabric Adapter -> OpenBao seal/verify -> HRC Fabric

Gateway journal + MQTT witness + application telemetry
       -> replicated evidence ingest/collectors/verifiers -> trusted decoder/object storage
```

Gateway evidence is part of the security proof, not optional logging. Keep the journal/uploader, mTLS ingest boundary, collectors, verifier, trusted decoder, and retained research evidence intact. `chapter4-results/` contains research artifacts and must never be treated as disposable documentation clutter.

## Remaining boundaries

These are not reasons to rebuild already-passing layers:

1. **Fabric HA:** ULC-02 writer activation/failover remains gated by its ownership/fencing acceptance.
2. **Reserved IPv4 HA:** normal public ingress is proven; provider-side reassignment authority and controlled failover acceptance remain separate work.
3. **Research outbox finalization/eligibility:** current v2 research rows must receive immutable `finalized_payload` and satisfy verifier-owned `verified` state before the Fabric worker can claim them; fix this upstream boundary rather than masking it with manual Fabric retries.
4. **Backup/recovery acceptance:** execute only the remaining acceptance items identified by the backup/recovery manual; do not repeat already-recorded normal-path checks without cause.
5. **Research execution:** follow the current `test/` GO/NO-GO gates and table-by-table procedures; preserve sealed run artifacts.
6. **Recorder wrapper version skew:** where the restricted server wrapper does not yet expose aggregate `evidence-status`, the recorder intentionally records `UNAVAILABLE_WRAPPER_UPGRADE_REQUIRED` rather than fabricating counts. This does not invalidate independent readiness checks that already pass.

## Do not repeat without a state-changing reason

- Core HA commissioning already proven.
- Gateway flashing, RAK5146 detection, AS923 commissioning, LTE primary-path proof, and EMU-01 normal RF acceptance.
- Task 37 Fabric qualification row `1960`.
- Broad replay of historical Fabric outbox rows.
- Disruptive failover tests after unrelated documentation or presentation changes.
- Any use of archived plans/handoffs as if they were current runbooks.

## Authoritative component references

- Cloud component map: [`00-README.md`](00-README.md)
- Historical commissioning evidence: [`00-build-execution-log.md`](00-build-execution-log.md)
- Fabric/OpenBao operations: [`20-openbao-and-fabric-adapter.md`](20-openbao-and-fabric-adapter.md)
- Backup/recovery: [`13-backup-restore-and-disaster-recovery.md`](13-backup-restore-and-disaster-recovery.md)
- Troubleshooting: [`17-troubleshooting.md`](17-troubleshooting.md)
- Gateway setup: [`../../gateway/setup/`](../../gateway/setup/)
- Research testing: [`../../../test/00-README.md`](../../../test/00-README.md)
- Research evidence layout: [`../../../chapter4-results/README.md`](../../../chapter4-results/README.md)
- Historical/provenance material: [`../../../docs/README.md`](../../../docs/README.md)
