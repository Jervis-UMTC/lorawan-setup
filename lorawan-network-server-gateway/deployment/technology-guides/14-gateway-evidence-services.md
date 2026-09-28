# Gateway Evidence Services — Operator Manual

## What this technology does

The gateway-evidence subsystem preserves and verifies an independent source lineage beside the ordinary application path. It answers a different question from ChirpStack and Node-RED:

> Do the retained gateway journal, cloud MQTT witness, application event, raw bytes, trusted decode, and stored telemetry all agree?

It consists of separate least-privilege services. No one cloud evidence service is allowed to own the entire trust chain.

## Current commissioned placement

```text
Gateway-01
  gateway-integrity-journal
  gateway-journal-uploader

ULC-01
  ingest-1
  collector-1
  fabric-adapter-1 ENABLED

ULC-02
  ingest-2
  verifier-1 + trusted decoder
  fabric-adapter-2 DISABLED

ULC-03
  collector-2
  verifier-2 + trusted decoder
```

Cloud evidence processing is replicated:

```text
ingest-1/2      active/active
collector-1/2   active/active; each maintains sessions to BOTH broker backends
verifier-1/2    active/active; PostgreSQL lease-fenced workers
trusted decoder identical immutable package on both verifier replicas
raw objects     SeaweedFS cross-host durable store
metadata/state  PostgreSQL/Patroni
```

The physical gateway itself remains one device; replicated cloud processing does not make the radio gateway physically redundant.

## Trust and authority split

| Component | Authority |
|---|---|
| gateway journal | append local source evidence |
| uploader | upload closed evidence/checkpoints; no history rewrite |
| ingest | authenticate upload and append metadata/raw object |
| MQTT collector | read-only witness of gateway MQTT events |
| verifier | correlate evidence and write verifier-owned result |
| trusted decoder | independent deterministic decode |
| Node-RED | application telemetry writer only |
| Fabric adapter | restricted outbox/OpenBao/Fabric authority only |

A verifier must not possess OpenBao signing authority or a Fabric private identity.

## Current deployment layout

Tracked bundle:

```text
evidence-services/cloud/deploy/
  compose.yml
  compose.collector-mtls.yml
  compose.fabric-adapter-enabled.yml
  preflight.sh
  fabric-adapter-enable-preflight.sh
  release.commissioned.env
```

Protected runtime material:

```text
/etc/lorawan-cloud/gateway-evidence/
/etc/lorawan-pki/gateway-evidence/
```

Every commissioned cloud evidence container runs as numeric `65532:65532`, read-only root filesystem, capabilities dropped, no-new-privileges, and bounded PID/memory/CPU/log settings.

## Step 1 — Check intended service placement

Run on each cloud host:

```bash
sudo docker ps   --filter 'label=com.docker.compose.project=lorawan-gateway-evidence'   --format 'table {{.Names}}\t{{.Label "com.docker.compose.service"}}\t{{.Status}}\t{{.Image}}'
```

Expected logical placement:

- ULC-01: `ingest`, `collector`, `fabric-adapter`;
- ULC-02: `ingest`, `verifier`, `fabric-adapter`;
- ULC-03: `collector`, `verifier`.

**PASS means:** only the intended roles are running and none is restart-looping.

## Step 2 — Check health and readiness endpoints

The evidence containers expose status on container port `8080`. Collector, verifier, and Fabric adapter bind host loopback; ingest binds the selected private host IP.

Use Docker's published-port mapping instead of guessing the host port:

```bash
for svc in ingest collector verifier fabric-adapter; do
  id="$(sudo docker ps -q     --filter 'label=com.docker.compose.project=lorawan-gateway-evidence'     --filter "label=com.docker.compose.service=$svc" | head -n1)"
  [ -n "$id" ] || continue

  echo "=== $svc ==="
  endpoint="$(sudo docker port "$id" 8080/tcp | head -n1)"
  echo "$endpoint"
  host="${endpoint%:*}"
  port="${endpoint##*:}"
  [ "$host" = "0.0.0.0" ] && host=127.0.0.1

  curl --connect-timeout 3 --max-time 8 -fsS "http://${host}:${port}/readyz"
  echo
done
```

**PASS means:**

- ingest is ready when its PostgreSQL/object-store dependencies are usable;
- each collector is ready only when both broker sessions plus PostgreSQL/object storage are usable;
- each verifier is ready only when PostgreSQL, object storage, worker state, and trusted-decoder self-test are good;
- ULC-01 Fabric adapter reports enabled/ready;
- ULC-02 Fabric adapter reports healthy `standby` with `enabled=false`.

A `/healthz` response proves a process is alive; `/readyz` is the stronger dependency check.

## Step 3 — Check recent service logs without dumping secrets

```bash
for svc in ingest collector verifier fabric-adapter; do
  id="$(sudo docker ps -q     --filter 'label=com.docker.compose.project=lorawan-gateway-evidence'    --filter "label=com.docker.compose.service=$svc" | head -n1)"
  [ -n "$id" ] || continue
  echo "=== $svc ==="
  sudo docker logs --since=15m --tail=120 "$id"
done
```

Look for repeated DB/S3/TLS/MQTT errors, lease failures, trusted-decoder self-test failure, conflicting object identity, evidence integrity errors, or adapter reconciliation errors.

Do not enable debug logging if it would expose DSNs, authorization headers, payload secrets, or key material.

## Step 4 — Verify the collector boundary

The commissioned collector contract is:

```text
brokers:       10.104.0.2:8884 and 10.104.0.4:8884
TLS name:      mqtt.internal.lorawan.com
auth:          mTLS
topic:         as923/gateway/+/event/#
permission:    READ only
publish:       denied
```

Each collector replica owns two distinct persistent client IDs, one per broker backend. The brokers do not replicate session state, so routing a collector only through the preferred/backup frontend is not equivalent.

If collector `/readyz` fails while the process lives, troubleshoot broker-1 session, broker-2 session, PostgreSQL, and object storage separately.

## Step 5 — Verify evidence database state

Using an approved read-only PostgreSQL session to `lorawan_telemetry`, inspect outcomes:

```sql
SELECT status, count(*)
FROM gateway_evidence.event_verification
GROUP BY status
ORDER BY status;

SELECT gateway_id, last_sequence, server_received_at
FROM gateway_evidence.checkpoints
ORDER BY server_received_at DESC
LIMIT 10;
```

Interpret states literally. `verified`, `evidence_gap`, `integrity_failure`, and still-pending work have different meanings.

Do not update verifier-owned rows manually to make a downstream test pass.

## Step 6 — Verify one lineage only when a real event is expected

For one known recent event, prove the chain in this order:

```text
application event
-> MQTT witness object
-> gateway journal record
-> closed segment + predecessor chain
-> checkpoint
-> trusted decode
-> stored telemetry comparison
-> verifier-owned terminal result
```

Do not use dashboard appearance as acceptance proof. The verifier must reopen retained objects and recompute the required identities/hashes.

## Step 7 — Understand recovery behavior

A WAN outage or one evidence-service replica loss does not require deleting or reconstructing authority state.

```text
gateway journal          continues locally
local Mosquitto queue     grows if WAN is down
uploader                  resumes from durable receipts
ingest replicas           accept exact retries idempotently
collector duplicates      collapse through deterministic capture identity
verifier leases           expire/reclaim after worker loss
telemetry                 may continue while evidence stays pending
v2 Fabric eligibility     remains blocked until verifier-owned verified state exists
```

Availability-first telemetry must not be misrepresented as verified evidence.

## Safe deployment/change procedure

1. Prove PostgreSQL, object storage, and cloud MQTT dependencies first.
2. Run the tracked host/staged deployment preflight appropriate to the change.
3. Keep image references immutable.
4. Change only the affected replica/profile.
5. Preserve separate workload identities.
6. Validate Compose with `docker compose config --quiet`.
7. Recreate/restart only the affected service.
8. Require `/readyz` after the change.
9. Verify one representative real lineage only when the change affects evidence semantics.
10. Keep Fabric activation as its own governed gate.

Do not bring every evidence replica and both Fabric adapters up blindly as one recovery action.

## Gateway-side evidence rule

Gateway journal state is durable and is not normally reset. A deliberate fresh research epoch must quiesce the writer/uploader first and explicitly establish a new `GENESIS` boundary. Raw SeaweedFS history may remain retained even when active database metadata is intentionally reset.

Never delete current gateway journal/receipt state as an ordinary troubleshooting step.

## Troubleshooting map

| Symptom | First check |
|---|---|
| ingest not ready | PostgreSQL + SeaweedFS `:18443` + TLS/mTLS |
| collector alive but not ready | both fixed broker sessions, then DB/S3 |
| verifier alive but not ready | DB/S3 + trusted-decoder self-test + worker state |
| telemetry exists but verification remains pending | missing evidence/correlation, not Fabric |
| `integrity_failure` | preserve artifacts; investigate exact mismatch before retry |
| `evidence_gap` | missing lineage/checkpoint/MQTT witness; do not fabricate |
| duplicate collector observations | deterministic capture identity + DB uniqueness |
| one replica down | repair that replica; do not remove the HA responsibility |
| Fabric pending with attempts=0 | check finalized payload + verifier eligibility first |

## Completion checklist

- intended two-replica ingest/collector/verifier placement is present;
- all active evidence services return `/readyz`;
- both collector replicas maintain the two fixed broker sessions;
- verifier trusted-decoder self-test passes;
- PostgreSQL evidence metadata is readable;
- SeaweedFS dependency is healthy;
- no immediate `evidence_gap` / `integrity_failure` condition exists for the event under test;
- ULC-01 adapter is the only enabled writer;
- ULC-02 adapter remains standby until its separate HA gate is accepted.

## Complete gateway-to-cloud lineage companion

Use [Gateway evidence independent journal, two MQTT witnesses, trusted decoder, verifier-owned verdicts and protected recovery](GATEWAY-EVIDENCE-LINEAGE-DEPLOY-RECOVERY.md). Sensor telemetry and evidence verification remain separate authorities; never manufacture a missing journal/object or relabel an evidence gap to make a presentation healthy.

## Detailed references

- [`../../evidence-services/README.md`](../../evidence-services/README.md)
- [`../../evidence-services/cloud/deploy/README.md`](../../evidence-services/cloud/deploy/README.md)
- [`../server/integrations/gateway-integrity/04-service-architecture-and-runtime-contract.md`](../server/integrations/gateway-integrity/04-service-architecture-and-runtime-contract.md)
- [`../server/integrations/gateway-integrity/06-replicated-ha-deployment-journey.md`](../server/integrations/gateway-integrity/06-replicated-ha-deployment-journey.md)
