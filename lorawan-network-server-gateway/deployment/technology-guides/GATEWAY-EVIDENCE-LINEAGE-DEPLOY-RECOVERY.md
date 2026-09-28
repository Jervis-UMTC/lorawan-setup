# Gateway Evidence Services — Independent Lineage, Deployment and Recovery

**Purpose:** explain how to prove that the gateway, cloud witness, trusted decoder and stored telemetry represent the **same original event**; to restore the subsystem without manufacturing proof; and to operate the real commissioned three-host Go service deployment. Expands [operator guide 14](14-gateway-evidence-services.md). This is not a new real sensor or security test.

## 1. Why the ordinary LoRaWAN path is not evidence by itself

~~~text
RAK5146 -> Concentratord
              |-> MQTT Forwarder -> gateway Mosquitto
              |      -> LTE -> two cloud Mosquitto brokers -> collectors 1/2
              |      -> ChirpStack -> app event -> one active Node-RED -> SQL telemetry
              |
              +-> independent gateway integrity journal
                     -> append seq/hash chain -> closed segment/checkpoint
                     -> durable uploader -> evidence ingest-1/2
                           -> retained SeaweedFS exact raw object
                                     |                 |
                                     +-- verifier-1/2 -+ cloud MQTT witness
                                            |           + trusted decoder
                                            +-> original SQL telemetry comparison
                                            -> gateway_evidence.event_verification
                                                  -> v2 Fabric claim eligibility
~~~

A healthy ChirpStack/Node-RED row proves **delivery/normalization**, not by itself integrity of the earlier gateway radio observation. The gateway journal reads the supported Concentratord event interface **independently of MQTT Forwarder**. The collector witnesses raw cloud MQTT events from **both** independent brokers. The verifier must reopen exact retained objects, validate ordered record hashes and server-receipted checkpoint chain, compare source identities and the independent pinned decoder's approved fields to normalized telemetry, then write only the verifier-owned outcome. An MQTT collector is not allowed to invent a missing gateway journal event.

## 2. Actual placement and runtime protections

| Host | Cloud evidence role |
|---|---|
| ULC-01 / 10.104.0.2 | ingest-1, collector-1, **only enabled** fabric-adapter-1 |
| ULC-02 / 10.104.0.4 | ingest-2, verifier-1, Fabric adapter standby **enabled=false** |
| ULC-03 / 10.104.0.8 | collector-2, verifier-2; no adapter |
| Gateway-01 | gateway-integrity-journal + gateway-journal-uploader (in addition to Concentratord and local MQTT) |

The **four** independent Go cloud service types (ingest, collector, verifier, Fabric adapter) are tracked under `evidence-services/cloud/deploy/`. The base `compose.yml` intentionally disables **both** Fabric adapters; continuous ULC-01 submission requires the separately governed `compose.fabric-adapter-enabled.yml` overlay and acceptance preflight. `compose.collector-mtls.yml` is required for commissioned cloud MQTT collector PKI. Do not start ULC-02 with the enabled overlay as an ordinary repair.

Each Go evidence container is numeric `65532:65532`, read-only root filesystem, no-new-privileges, capabilities dropped, bounded PID/logging and reviewed 192 MiB / 0.20 CPU resource ceilings. Its image may not include a shell/health CLI. Health/readiness is served on container `:8080`, published via actual Docker map; ingest host port is private VPC while collector, verifier and adapter host ports are loopback-only. The public upload route is `https://smartagri-evidence.duckdns.org:443` through the existing HAProxy SNI ingress; do not open a random ingest container port publicly.

## 3. Protected configuration and exact identities

~~~text
/etc/lorawan-cloud/gateway-evidence/
  release.env (immutable image refs)
  host.env (this host's placement/private bindings)
  common.env (non-secret shared settings)
  ingest.env / collector.env / verifier.env (only where relevant)
  fabric-adapter.env (ULC-01 active, ULC-02 protected inactive)
/etc/lorawan-pki/gateway-evidence/
  postgres-ca.crt, s3-ca.crt, workload-specific upload/MQTT certs and protected keys
/etc/lorawan-cloud/fabric-adapter/role_id, secret_id  (adapter activation only)
/etc/lorawan-pki/fabric/                           (adapter activation only)
~~~

Protected role environment files are normally `0600 root:root`; Go runtime keys need host `root:65532 0440` and correct parent directory execute permissions, while public CAs may be `root:65532 0440` or root-owned world-readable **non-writable** public files. The role-specific preflight decides exact approved mode; do not loosen a key because a generic Docker read test fails.

Commissioned SQL identities map to **separate NOLOGIN authority groups**:

| Login | Group role |
|---|---|
| `evidence_ingest_ulc01` / `evidence_ingest_ulc02` | `gateway_evidence_ingestor` |
| `evidence_collector_ulc01` / `evidence_collector_ulc03` | `gateway_evidence_collector` |
| `evidence_verifier_ulc02` / `evidence_verifier_ulc03` | `gateway_evidence_verifier` |

All use their **local** logical PgBouncer `pgbouncer.internal.lorawan.com:6432` mapped to their own host VPC IP, TLS-verified to the normal current Patroni primary. Never use Fabric's SQL role for verifier work.

Object store: `https://evidence-objects.internal.lorawan.com:18443`, bucket `lorawan-evidence`, prefix `lorawan-gateway-evidence`; the service host maps that FQDN to its own local VPC IP while checking the server certificate. Ingest/collector may conditional-create + read; verifier is **read-only**. No role may delete/overwrite retained raw evidence through the runtime S3 endpoint.

MQTT collectors: `10.104.0.2:8884` and `10.104.0.4:8884` separately, correct server TLS name `mqtt.internal.lorawan.com`, dedicated mTLS client certificates with only `read as923/gateway/+/event/#`; two separate persistent client IDs per replica (four sessions total). A preferred/backup **single** HAProxy session cannot replace two independent broker witnesses. The old password-mode collector example is reference-only and production preflight rejects it.

## 4. Reproduce a new cloud deployment (not an old-state reset)

1. Discover current deployment ownership, image references and protected configuration; take an off-host backup of existing SQL metadata, SeaweedFS objects, gateway checkpoint/receipt state and runtime PKI. **Stop** if this is an existing commissioned cluster and the task is only one unhealthy replica.
2. Prove Patroni writable primary, each host's PgBouncer/HAProxy, both independent cloud MQTT brokers and the separate SeaweedFS object-store quorum/TLS/method gate.
3. On each intended host, copy the tracked release/Compose/host templates to protected `/etc/lorawan-cloud/gateway-evidence/`, fill exact reviewed immutable digests, role DSNs, local/private binds, and per-role PKI/identity **outside Git**. Reuse the commissioned roles rather than inventing new superusers.
4. Stage ingest/collector/verifier identities and ensure runtime `65532` can read only the required certificates/keys. Preserve source-Gateway EUI binding and uploader client identity separately from ordinary gateway MQTT.
5. Run `host-preflight.sh` on each host, then `preflight.sh` with its approved root-owned release/host env under the exact checked-out deployment version. Read-only preflights validate dependencies, actual current host ports, file modes, selected S3 backend and broker mTLS. **Preflight PASS does not mean a service has been started.**
6. Validate the *complete* current Compose model (base plus applicable collector mTLS overlay). Enable only intended ingest/collector/verifier roles on their assigned hosts, one host/role group at a time, without enabling a Fabric writer.
7. Observe each `/readyz`, separately verify two collector broker sessions, verify each ingest accepts a known idempotent gateway-upload retry **only during a controlled commissioning window**, and require verifier trusted-decoder self-test.
8. Only when Fabric handoff and fencing gate are separately qualified may the intended ULC-01 adapter activation overlay be applied after `fabric-adapter-enable-preflight.sh`. ULC-02 remains disabled until its independent takeover acceptance.
9. One real current gateway event may be accepted only when its physical source can be observed and the independent journal/MQTT/SQL identity agrees. Synthetic fixture success is only server-path proof, not physical RF acceptance.

## 5. Read-only status without guessing mapped ports

Run on each ULC Ubuntu host:

~~~bash
hostname -f
date -u
sudo docker ps --filter 'label=com.docker.compose.project=lorawan-gateway-evidence' \
 --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
~~~

Find each service's actual published port by Compose labels rather than guessing:

~~~bash
for svc in ingest collector verifier fabric-adapter; do
  id="$(sudo docker ps -q \
    --filter 'label=com.docker.compose.project=lorawan-gateway-evidence' \
    --filter "label=com.docker.compose.service=$svc" | head -n1)"
  [ -n "$id" ] || continue
  endpoint="$(sudo docker port "$id" 8080/tcp | head -n1)"
  host="${endpoint%:*}"; port="${endpoint##*:}"
  [ "$host" = '0.0.0.0' ] && host=127.0.0.1
  printf '%s %s ' "$svc" "$endpoint"
  curl --connect-timeout 3 --max-time 8 -fsS "http://${host}:${port}/readyz"
  printf '\n'
done
~~~

**PASS:** all intended ingest/collector/verifier instances show dependency readiness; collector explicitly has BOTH backend sessions; trusted-decoder test passes. Fabric ULC-01 shows enabled/ready, ULC-02 shows **healthy standby** but no production authority. A healthy standby should *not* open a production DB/Fabric/OpenBao session simply to report process liveness.

Using approved read-only SQL, inspect one expected event and state distribution:

~~~sql
SELECT status,count(*) FROM gateway_evidence.event_verification
GROUP BY status ORDER BY status;
SELECT gateway_id,last_sequence,server_received_at
FROM gateway_evidence.checkpoints
ORDER BY server_received_at DESC LIMIT 10;
~~~

**Important:** `verified`, `pending`, `evidence_gap` and `integrity_failure` are distinct outcomes. Never relabel evidence gap as verified or erase an adverse row to remove an unwanted dashboard item.

## 6. Explain a complete event and the “dead letter” problem

For a recent known accepted source event, match **the same event identity/time** through:

~~~text
Concentratord source frame
 -> journal sequence + previous_record_hash
 -> RFC 8785 canonical record bytes, SHA-256 record hash
 -> closed segment + predecessor hash
 -> upload receipt and server checkpoint
 -> retained SeaweedFS raw object (GetObject and recomputed digest)
 -> independent BOTH-cloud-broker collector record(s)
 -> ChirpStack accepted raw application data / reception metadata
 -> pinned independent trusted decoder
 -> PostgreSQL normalized telemetry comparison
 -> verifier-owned terminal status
~~~

The adapter's `dead_letter` or `needs_attention` status is **not** a generic “unknown error”: it is the actual state/error category after attempts/reconciliation. Determine whether it is blocked by missing finalized bytes, v2 verification, OpenBao/identity, endorsement, peer commit delivery or a permanent content conflict. A Fabric `pending, attempts=0` row may be **correct** while an ineligible event is waiting. Do not silently delete rows, replace payloads, widen privileges or claim zero failure count by hiding a panel.

WAN loss: gateway journal and local MQTT queue may continue; uploader resumes from durable receipts, ingest exact retries are idempotent, collectors' duplicate observations collapse by deterministic identity, and verifier workers reclaim expired leases. Telemetry may arrive while the evidence verdict is still pending. Do **not** claim “verified” simply because a packet is visible at Node-RED.

## 7. Recovery without breaking research evidence

For one unhealthy replica, preserve bounded recent logs and current config/ID, locate its first failing SQL, cloud broker, SeaweedFS or decoder layer, and repair **only** that layer/replica. Do not stop all cloud evidence roles or delete raw objects as a “reset”.

If Gateway-01 journal/receipt is damaged or a formal research epoch intentionally starts over, the approved procedure first **quiesces writer and uploader** and determines the last externally accepted segment/checkpoint. A new genesis/epoch is an explicit signed/recorded authority boundary, not a casual deletion. An older journal copy must not be restored and replayed as if it followed a newer cloud checkpoint.

Full disaster recovery requires mutually consistent gateway journal/receipts, raw objects, SQL evidence metadata, trusted decoder/runtime hashes, service identities/CA, and external Fabric status. Restore in an isolated controlled environment and reconcile external ledger rather than assuming only one PostgreSQL snapshot restores all trust.

**PASS:** correct two-replica placement, runtime isolation, exact four collector sessions, healthy S3/DB, trusted-decoder parity, one independently verified real lineage when the device is available, no immediate unexplained gap/integrity errors and sole enabled Fabric writer. Recorded historical 2026-09-02 492 verified v2 events is a dated result, not today's live count or substitute for new counted research trial.

Source maintenance: [actual cloud deployment](../../evidence-services/cloud/deploy/README.md), [gateway integrity architecture](../server/integrations/gateway-integrity/04-service-architecture-and-runtime-contract.md), and [fenced adapter](../../evidence-services/cloud/packaging/FABRIC-HA-FENCING.md). The final Word document must reproduce its required procedures and full evidence-state interpretation without requiring Markdown.
