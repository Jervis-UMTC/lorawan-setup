# Hyperledger Fabric Adapter — Operator Manual

## What this technology does

The Fabric adapter consumes **eligible** rows from `telemetry.fabric_outbox`, verifies/seals the local evidence boundary through OpenBao, prepares a source-bound HRC Fabric transaction, submits it through the private Fabric Gateway, and reconciles the authoritative commit/query/digest result.

It is asynchronous by design. Fabric or OpenBao downtime must not make ordinary sensor telemetry disappear.

## Current production boundary

```text
ULC-01 -> fabric-adapter-1 -> ENABLED production writer
ULC-02 -> fabric-adapter-2 -> installed / healthy / write-disabled standby
ULC-03 -> no Fabric adapter

Gateway endpoint: 10.104.0.7:7051
TLS server name:  peer1.hrc.local
MSP:              HrcMSP
Channel:          hrc-channel
Chaincode:        hrc-evidence
Source namespace: lorawan-gateway-evidence
```

Do not enable ULC-02 merely because ULC-01 is temporarily unreachable. Its ownership/fencing takeover remains a separate HA acceptance boundary.

### Fresh live checkpoint — 2026-09-18

Read-only restricted monitoring proves ULC-01 is `enabled=true` / `status=ready` and ULC-02 is `enabled=false` / `status=standby`; both canonical self-tests pass. The same snapshot reports `2094` Fabric outbox rows and all `2094` are confirmed, with `2094` verifier results all verified. The old pending backlog is not current.

Do **not** run takeover yet: ULC-01 reports image `gateway-fabric-adapter:fairness-20260915`, while ULC-02 reports `9e08e25fe5dd`. Until exact current image/binary parity, distinct worker identity, live migration-003 fencing, and the controlled takeover row are proven, ULC-02 stays disabled.

## Current HRC contract

```text
CreateSourceBoundAnchor(SourceRecordID, sourceType, producer, producedAt, schemaVersion)
  transient hrc.exact_payload = immutable finalized_payload bytes

QuerySourceBoundAnchor(SourceRecordID)

VerifySourceBoundDigest(SourceRecordID, sha256(finalized_payload))
```

The retired `CreateAnchor`, `QueryAnchor`, `QueryAnchorByRecordID`, and `VerifyDigest` APIs must not be restored.

The exact payload is always `telemetry.fabric_outbox.finalized_payload`. Never reconstruct it from JSONB, `raw_data`, maps, structs, or projections.

## Eligibility rule

A fresh claim requires:

```text
finalized_payload IS NOT NULL
```

For `telemetry-attestation-v2`, it additionally requires the matching verifier-owned:

```text
gateway_evidence.event_verification.status = 'verified'
```

Therefore `pending` with `attempts=0` can be correct while the adapter itself is healthy.

## Current lifecycle rule

```text
pending
processing
failed
reconciling
confirmed
needs_attention
dead_letter
```

`submitted_unknown` remains legacy schema compatibility and is not emitted by the current worker.

An uncertain post-submit result enters `reconciling`. Prepared transaction bytes and the signed commit-status request are persisted before orderer submission so recovery can continue the **same transaction** rather than creating a new one blindly.

## Step 1 — Prove writer ownership first

Run on ULC-01 and ULC-02:

```bash
id="$(sudo docker ps -q   --filter 'label=com.docker.compose.project=lorawan-gateway-evidence'   --filter 'label=com.docker.compose.service=fabric-adapter' | head -n1)"

if [ -z "$id" ]; then
  echo 'FABRIC_ADAPTER_CONTAINER=ABSENT'
else
  sudo docker inspect "$id"     --format 'name={{.Name}} status={{.State.Status}} restarts={{.RestartCount}} image={{.Image}}'
  sudo docker port "$id" 8080/tcp
fi
```

**Expected ownership:**

- ULC-01: enabled production writer;
- ULC-02: healthy standby with writes disabled.

If both are enabled, treat that as an HA-fencing incident. Do not let both continue while investigating.

## Step 2 — Check `/healthz` and `/readyz`

```bash
id="$(sudo docker ps -q   --filter 'label=com.docker.compose.project=lorawan-gateway-evidence'   --filter 'label=com.docker.compose.service=fabric-adapter' | head -n1)"

endpoint="$(sudo docker port "$id" 8080/tcp | head -n1)"
host="${endpoint%:*}"
port="${endpoint##*:}"
[ "$host" = "0.0.0.0" ] && host=127.0.0.1

curl --connect-timeout 3 --max-time 5 -fsS "http://${host}:${port}/healthz"
echo
curl --connect-timeout 3 --max-time 8 -fsS "http://${host}:${port}/readyz"
echo
```

**PASS means:**

- ULC-01 reports alive and enabled, with readiness dependencies/self-tests satisfied;
- ULC-02 reports `standby`, `enabled=false`, and canonical self-test pass.

A healthy standby should not open production DB/OpenBao/Fabric authority merely to prove the process exists.

## Step 3 — Check recent bounded logs

```bash
id="$(sudo docker ps -q   --filter 'label=com.docker.compose.project=lorawan-gateway-evidence'   --filter 'label=com.docker.compose.service=fabric-adapter' | head -n1)"

sudo docker logs --since=15m --tail=180 "$id"
```

Look for repeated DB/OpenBao/TLS/Fabric errors, lease-generation loss, preparation/persistence failure, commit-status timeout, reconciliation failure, source-bound Query mismatch, or Verify mismatch.

Do not print protected adapter env files, RoleID/SecretID contents, client private keys, or unrestricted DSNs.

## Step 4 — Diagnose the outbox before blaming Fabric

Using an approved read-only SQL session:

```sql
SELECT status, count(*) AS rows
FROM telemetry.fabric_outbox
GROUP BY status
ORDER BY status;

SELECT
  outbox_id,
  source_event_key,
  observed_at,
  schema_version,
  status,
  attempts,
  finalized_payload IS NOT NULL AS has_finalized_payload,
  worker_id,
  lease_generation,
  lease_expires_at,
  fabric_tx_id,
  last_error_category,
  last_error
FROM telemetry.fabric_outbox
ORDER BY outbox_id DESC
LIMIT 30;
```

For a v2 row that remains `pending`, verify the exact matching evidence result on both source identity and observation time:

```sql
SELECT source_event_key, observed_at, status, verified_at
FROM gateway_evidence.event_verification
WHERE source_event_key = '<SOURCE_EVENT_KEY>'
  AND observed_at = '<OBSERVED_AT>'::timestamptz;
```

Do not manually manufacture `finalized_payload`, `verified`, `confirmed`, or a replacement outbox row.

## Step 5 — Verify dependency boundaries separately

The adapter depends on:

```text
PostgreSQL/PgBouncer -> pgbouncer.internal.lorawan.com:6432
OpenBao              -> https://openbao-kms.internal.lorawan.com:18200
Fabric Gateway       -> 10.104.0.7:7051 / peer1.hrc.local
```

Use the PostgreSQL/PgBouncer and OpenBao manuals first.

For Fabric transport only, verify server TLS without disabling hostname checks:

```bash
openssl s_client   -connect 10.104.0.7:7051   -servername peer1.hrc.local   -verify_hostname peer1.hrc.local   -verify_return_error   -CAfile /etc/lorawan-pki/fabric/tls-ca.crt   </dev/null 2>/dev/null   | grep -E 'Verify return code|subject=|issuer='
```

A passing TLS handshake does not prove endorsement, orderer submission, peer delivery, or commit status.

## Step 6 — Separate Fabric transaction stages

Troubleshoot in this order:

```text
1. outbox eligibility
2. adapter DB lease/generation ownership
3. OpenBao login/sign/verify
4. Fabric Gateway TLS/session
5. proposal/endorsement
6. prepared transaction persistence
7. orderer submission
8. peer commit delivery / CommitStatus
9. QuerySourceBoundAnchor field match
10. VerifySourceBoundDigest = MATCH
```

A stale HRC peer ledger can make client `CommitStatus` wait even after endorsement and orderer submission succeeded. Do not classify that as a generic “submit hang.”

## Step 7 — Verify the HA fencing contract

The current generation-aware claim contract requires every worker-owned mutation to match:

```text
outbox_id
worker_id
lease_generation
lease_expires_at > now()
```

A successful claim increments `lease_generation`. A stale process cannot regain write authority merely by reusing the same stable worker ID.

ULC-02 must remain disabled until the controlled takeover gate proves that both installed workers use the generation-aware build and only one owns external side effects.

Do not reuse qualification outbox row `1960`.

## Step 8 — Run the activation preflight only when activation is intended

The tracked read-only gate is:

```bash
sudo ./fabric-adapter-enable-preflight.sh   /etc/lorawan-cloud/gateway-evidence/release.env   /etc/lorawan-cloud/gateway-evidence/host.env
```

Required marker:

```text
FABRIC_ADAPTER_ENABLE_PREFLIGHT=PASS
```

It verifies protected file modes, PgBouncer TLS DSN, OpenBao route, Fabric certificate/key pairing, HRC CA/TLS identity, current source-bound function names, and the exact enabled Compose model without starting or mutating anything.

Do not run the enabled Compose overlay on ULC-02 as a routine health check.

## Safe adapter change procedure

1. Prove ULC-01 is the sole enabled writer.
2. Check outbox and reconciliation state first.
3. Back up the exact deployment/configuration being changed.
4. Preserve durable prepared-transaction/reconciliation fields.
5. Validate the new immutable image/build and migration compatibility.
6. Keep ULC-02 disabled unless performing the explicit HA gate.
7. Run the activation preflight on the intended owner.
8. Roll only that adapter.
9. Require `/readyz`.
10. Confirm one new **eligible** representative row only when a functional write test is warranted.
11. Require authoritative commit status, source-bound Query match, and Verify `MATCH`.

Never “recover” an uncertain submission by clearing durable transaction fields and creating a fresh transaction.

## Failure behavior

### Fabric unavailable

```text
LoRaWAN + Node-RED + PostgreSQL telemetry continue
eligible fabric_outbox accumulates/reconciles
adapter retries according to governed state
```

### OpenBao unavailable

```text
telemetry continues
adapter cannot complete sealing/submission
outbox waits/retries
```

### ULC-01 adapter lost

Keep ULC-02 fenced unless the explicit takeover procedure is being executed. Database leases alone do not authorize an unreviewed external side-effect takeover.

## Troubleshooting map

| Symptom | First check |
|---|---|
| `pending attempts=0` | finalized payload + v2 verifier eligibility |
| adapter alive but not ready | DB/OpenBao/Fabric dependency reported by readiness/logs |
| OpenBao login denied | RoleID/SecretID lifecycle/policy; do not broaden policy |
| proposal/endorsement fails | Fabric identity/channel/chaincode/function |
| submit accepted, CommitStatus waits | peer ledger/delivery state vs orderer submission |
| `reconciling` persists | same prepared tx + commit-status/query recovery path |
| `needs_attention` | preserve evidence and investigate conflict/permanent failure |
| duplicate/conflicting anchor | stop external writes and inspect fencing/source identity |
| ULC-02 writing unexpectedly | fencing/enablement incident |

## Completion checklist

- ULC-01 is enabled and ready;
- ULC-02 is healthy but `enabled=false`;
- exact HRC source-bound API names are configured;
- exact immutable `finalized_payload` rule is preserved;
- v2 verifier eligibility is preserved;
- DB/OpenBao/Fabric TLS dependencies are healthy;
- no unexplained reconciliation/permanent conflict is present;
- any representative submission ends in authoritative commit + Query match + Verify `MATCH`;
- qualification row `1960` is never rerun.

## Complete HRC exact-payload submission and recovery companion

Use [Fabric adapter governed source-bound API, durable prepared transactions, generation fencing and external ledger reconciliation](FABRIC-EXACT-PAYLOAD-FENCING-RECOVERY.md). The ULC-02 disabled standby must not become an active external writer without build parity and controlled ownership acceptance.

## Detailed references

- [`../server/integrations/hyperledger-fabric/02-fabric-network-handoff.md`](../server/integrations/hyperledger-fabric/02-fabric-network-handoff.md)
- [`../server/cloud-production/20-openbao-and-fabric-adapter.md`](../server/cloud-production/20-openbao-and-fabric-adapter.md)
- [`../../evidence-services/cloud/deploy/README.md`](../../evidence-services/cloud/deploy/README.md)
- [`../../evidence-services/cloud/packaging/FABRIC-HA-FENCING.md`](../../evidence-services/cloud/packaging/FABRIC-HA-FENCING.md)
