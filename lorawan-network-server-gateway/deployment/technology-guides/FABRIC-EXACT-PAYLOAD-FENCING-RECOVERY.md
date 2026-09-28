# Hyperledger Fabric Adapter — Exact-Payload Submission, Qualification and Recovery

**Purpose:** reproduce the real LoRaWAN-to-HRC governed bridge, diagnose any failed stage, preserve exact bytes and avoid a second external ledger side effect during retries/HA. This expands [operator guide 15](15-hyperledger-fabric-adapter.md). The external Fabric team independently owns peers, ordering nodes, chaincode and network. Our ULC servers own the outbox, verifier eligibility, adapter, OpenBao identity and client-side reconciliation.

## 1. The actual production contract

~~~text
accepted ChirpStack application uplink
  -> sole active Node-RED -> one SQL telemetry/outbox transaction
  -> immutable telemetry.fabric_outbox.finalized_payload
  -> v2: gateway_evidence.event_verification.status MUST be verified
  -> ULC-01 adapter generation-bound outbox claim
  -> OpenBao AppRole + nonexportable Transit sign/verify
  -> HRC private Fabric Gateway 10.104.0.7:7051 (TLS peer1.hrc.local)
  -> CreateSourceBoundAnchor with EXACT transient hrc.exact_payload
  -> persist same prepared tx + signed CommitStatus request before submit
  -> submit / commit-status / authoritative Query / Verify digest MATCH
  -> confirmed only on agreement
~~~

The only commissioned enabled production worker is **ULC-01**. ULC-02 is installed, healthy **FABRIC_ADAPTER_ENABLED=false** standby; ULC-03 has no adapter. An application MQTT delay, OpenBao outage or Fabric ordering issue must not delete telemetry or cause an invented “confirmed” record.

## 2. HRC private handoff — precise values

| Item | Commissioned value |
|---|---|
| Fabric Gateway endpoint | `10.104.0.7:7051`, on the **private 10.104/20 route**, not old Kubernetes ClusterIP |
| Peer server TLS name | `peer1.hrc.local`; preserve TLS CA and verify SAN |
| Source namespace | `lorawan-gateway-evidence` |
| Source client MSP | `HrcMSP`; dedicated least-privilege ULC-01 adapter identity, not administrator |
| Channel | `hrc-channel` |
| Chaincode | `hrc-evidence`; 1.1 sequence 2 at 2026-09-08 qualification; recheck current on upgrades |
| Contract namespace | empty/default, not the Caliper alias |
| Create | `CreateSourceBoundAnchor(SourceRecordID, sourceType, producer, producedAt, schemaVersion)` |
| Create transient value | `hrc.exact_payload` = original immutable UTF-8 **finalized_payload bytes** |
| Read | `QuerySourceBoundAnchor(SourceRecordID)` |
| Independent digest match | `VerifySourceBoundDigest(SourceRecordID, observedDigest)` => `MATCH` |

Retired names `CreateAnchor`, `QueryAnchor`, `QueryAnchorByRecordID` and `VerifyDigest` **must not** be resurrected. Never JSON-parse and reserialize `finalized_payload` to construct transient bytes. Jsonb/map iteration, whitespace, key ordering or Unicode escaping can change the digest. The authoritative business/source identity is bound to the original event ID and observed time; a retry cannot invent a new source.

## 3. What is stored where

| Storage / identity | Authority |
|---|---|
| `telemetry.uplinks` and `telemetry.measurements` | Source application record and normalized metrics |
| `telemetry.fabric_outbox` | durable eligible candidate, exact finalized bytes, claim and prepared transaction |
| `gateway_evidence.event_verification` | independent verifier-owned v2 decision |
| OpenBao `lorawan-evidence` Transit | signing/verification only; key non-exportable |
| protected Fabric `client.crt/key` and `tls-ca.crt` | scoped Fabric client signing/server trust |
| HRC channel ledger | external authoritative committed anchor and digest query |

No actor may use a database row alone as proof that its commit exists on HRC. A `pending` row with `attempts=0` can mean unselected/unfinished evidence, **not** “Fabric is down.” Qualification source event/outbox `1960` was already committed and **must never be replayed as a new experiment**.

## 4. Runtime files and safe commissioned deployment

On ULC-01/02, the tracked deployment is `evidence-services/cloud/deploy/` with base `compose.yml`, commissioned immutable `release.env`, node-local `host.env`, protected `fabric-adapter.env` and an explicit `compose.fabric-adapter-enabled.yml` *only for the authorized writer*. Current protected host directories:

~~~text
/etc/lorawan-cloud/gateway-evidence/{release.env,host.env,common.env,fabric-adapter.env}
/etc/lorawan-cloud/fabric-adapter/{role_id,secret_id}
/etc/lorawan-pki/fabric/{tls-ca.crt,client.crt,client.key}
~~~

The base Compose file intentionally runs a no-authority standby `enabled=false` which must **not** contact PostgreSQL, read OpenBao SecretID or connect to Fabric. Do not accidentally add the activation overlay to a two-host Compose command. Protected runtime env files are root:root mode 0600; private client key mounted for numeric runtime group 65532 with approved restrictive mode. Do not copy ULC-01 client private identity onto standby. Confirm distinct host-specific worker IDs and the actual deployed approved image/binary digest before considering dual-worker operation.

### 4.1 Read-only state, separately on ULC-01 and ULC-02

~~~bash
hostname -f
date -u
sudo docker ps --filter 'label=com.docker.compose.project=lorawan-gateway-evidence' \
 --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
id="$(sudo docker ps -q \
 --filter 'label=com.docker.compose.project=lorawan-gateway-evidence' \
 --filter 'label=com.docker.compose.service=fabric-adapter' | head -n1)"
if [ -n "$id" ]; then
  sudo docker inspect "$id" --format 'name={{.Name}} image={{.Image}} restarts={{.RestartCount}}'
  sudo docker port "$id" 8080/tcp
else
  echo 'FABRIC_ADAPTER_CONTAINER=ABSENT'
fi
~~~

Check `/healthz` and `/readyz` using the *actually discovered* host-bound health port; ULC-01 should report `enabled=true`, status ready, self-test pass and dependencies usable. ULC-02 should report `enabled=false`, status standby and local canonical self-test pass **without** opening production authority. If both are enabled, stop external write authority safely, preserve outbox/prepared transactions and treat as a fencing incident, not a reason to delete rows.

The 2026-09-18 checkpoint recorded ULC-01 enabled/ready and ULC-02 standby, `2094` confirmed outbox records / `2094` verified gateway events. It also recorded *different* deployed adapter image references, so **runtime parity was not proven**; this dated snapshot is not an invitation to start takeover. Current production status may have changed; run a fresh gate before declaring it.

### 4.2 Preflight before an intended activation

The tracked script is in `evidence-services/cloud/deploy/`. After resolving and backing up the exact release/host configs, run **on the intended enabled writer only**:

~~~bash
sudo ./fabric-adapter-enable-preflight.sh \
 /etc/lorawan-cloud/gateway-evidence/release.env \
 /etc/lorawan-cloud/gateway-evidence/host.env
~~~

**PASS:** `FABRIC_ADAPTER_ENABLE_PREFLIGHT=PASS` after validation of the exact enabled Compose model, PKI/file modes, TLS database/OpenBao/Fabric, source identity and current function names. This script is a **preflight, not an invitation to start the standby**. On a normal documentation-only day, use health/ready/logs rather than rerunning activation or Fabric submits.

## 5. Inspect outbox/eligibility before network probing

Through a reviewed read-only SQL session to current Patroni primary route:

~~~sql
SELECT status,count(*) AS rows
FROM telemetry.fabric_outbox GROUP BY status ORDER BY status;
SELECT outbox_id,source_event_key,observed_at,schema_version,
       status,attempts,finalized_payload IS NOT NULL AS has_finalized_payload,
       worker_id,lease_generation,lease_expires_at,fabric_tx_id,
       last_error_category,last_error
FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 30;
~~~

For a known v2 `source_event_key` and `observed_at`:

~~~sql
SELECT source_event_key,observed_at,status,verified_at
FROM gateway_evidence.event_verification
WHERE source_event_key = '<APPROVED_SOURCE_EVENT_KEY>'
  AND observed_at = '<APPROVED_OBSERVED_AT>'::timestamptz;
~~~

The literal placeholders are **not runnable**. Match exact source identity *and* observation time rather than “closest” evidence record. A v2 row with missing finalized bytes or no matching `verified` decision must remain unclaimed; do not fabricate evidence, move status or patch a historical row by hand. If the database schema/column names changed, inspect the actual tracked migration before copying a historical SQL query.

## 6. Troubleshoot a failed stage in order

1. **Eligibility:** exact non-null finalized bytes and required independent verification.
2. **Claim/fencing:** worker identity, unexpired lease and incrementing generation. Every worker mutation must match `outbox_id` + `worker_id` + `lease_generation` + `lease_expires_at > now()`.
3. **OpenBao:** TLS KMS route `:18200`, current active-member AppRole issuance, scoped sign/verify and audit. Login failure does not justify broad policy.
4. **Fabric Gateway transport:** private route `10.104.0.7:7051`, CA and TLS name `peer1.hrc.local`; TCP/TLS handshake is **not endorsement**.
5. **Proposal/endorsement:** correct MSP, HRC chaincode/channel/source namespace and transient bytes.
6. **Durable prepare:** prepared transaction and signed commit-status request are stored **before** orderer submission.
7. **Submission:** submission status may become unknown if network response is lost; do not create a fresh proposal just because it timed out.
8. **CommitStatus/peer delivery:** distinguish stale peer ledger or delayed delivery from an orderer rejection.
9. **Query:** source-bound returned record/source/digest/payload length match the requested row.
10. **Verify:** HRC digest function returns **MATCH**; only then mark `confirmed` under the governed worker lease.

Normal lifecycle is `pending / processing / failed / reconciling / confirmed / needs_attention / dead_letter`. Historical `submitted_unknown` is schema compatibility only, **not current worker behavior**. Never clear durable prepared transaction fields to “unstick” reconciling. `dead_letter` and `needs_attention` are conditions to diagnose with preserved evidence, not to hide from Grafana presentation.

## 7. Exact-payload and HA acceptance

External writer ownership is an **independent safety gate** from service HA. The generation-aware SQL lease migration `003_fabric_adapter_ha_fencing.sql` prevents a stale generation from renewing, persisting prepared work or confirming even if the same worker ID comes back after lease expiration. It does **not** automatically authorize any two previously mismatched binaries to generate side effects. The current published 2026-09-18 fencing review explicitly said ULC-02 remained disabled pending same accepted build/image on both, distinct worker ID, migration parity and a fresh controlled takeover operation. Do not turn a documentation request into a disruptive failover test.

For a *future approved* controlled takeover: prove ULC-01 sole authority and healthy normal path; stage identical accepted generation-aware build on disabled ULC-02; confirm protected identity and DB migration; fence/stop only current adapter (not SQL/KMS/Fabric); wait for governed lease release/expiry, enable B under approved procedure, submit a **new** eligible real row only once, require authoritative commit/query/verify, then restore safe designated ownership. Qualification row `1960` is excluded. If these gates are not met, leave ULC-01 enabled and ULC-02 disabled.

## 8. Restore contract

Back up and restore as one coherent authority boundary: PostgreSQL `fabric_outbox` lease/status/prepared transaction bytes, related exact immutable `finalized_payload`, gateway evidence records/Seaweed objects, OpenBao signer key/recovery material, dedicated Fabric client keys/CA, and **external HRC committed ledger state**. Restoring a prior SQL snapshot must not cause a previously submitted record to be sent again as a different transaction. Reconcile with authoritative Query and CommitStatus before resuming. Backup/recovery must not allow Node-RED to access verifier-owned status or adapter signing material.

**PASS:** only governed enabled writer, standby genuinely disabled, eligibility exact, private verified DB/KMS/Fabric routes, canonical self-test, one new intended row reaching authoritative commit, source-bound query and Verify MATCH with an independently reproduced digest. An old confirmed count or TLS handshake alone is weaker evidence.

Sources: [HRC Task 37 handoff](../server/integrations/hyperledger-fabric/02-fabric-network-handoff.md), [production qualification](../server/cloud-production/20-openbao-and-fabric-adapter.md), [writer fencing](../../evidence-services/cloud/packaging/FABRIC-HA-FENCING.md), [evidence service deploy](../../evidence-services/cloud/deploy/README.md). Copy all required procedure detail into the final Word document itself.
