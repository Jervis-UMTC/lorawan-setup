# Gateway Security Evidence Services

This directory contains the implementation artifacts for the gateway-integrity v2 security-evidence path documented under `deployment/server/integrations/gateway-integrity/`.

## Current implementation boundary

Implemented as repository source/static-policy artifacts:

- language-independent contracts for `gateway-journal-v1`, `gateway-journal-segment-v1`, `concentratord-uplink-correlation-v1`, `evidence-ingest-api-v1`, `evidence-ingest-receipt-v1`, `mqtt-capture-v1`, and `trusted-decoder-normalized-v1`;
- a dependency-light Go cloud module foundation;
- validated environment configuration with secret-safe summaries;
- structured JSON logging helpers;
- database capability interfaces shared by later repositories/workers;
- an immutable filesystem object-store backend for **development/smoke use only**;
- deterministic `mqtt-capture-v1` capture-key construction and fixed vector;
- independent Agriculture Kit payload-v2 trusted decoder source with fixed raw/normalized SHA-256 vector;
- evidence-ingest HTTP handler/core for checkpoints and closed segments, including stable `evidence-ingest-receipt-v1` acknowledgements derived from persisted server acceptance time;
- direct verified-client-certificate identity binding for one 16-hex Gateway EUI;
- request-body/content-type/unknown-field/trailing-JSON controls;
- checkpoint semantic digest, duplicate/conflict handling, and monotonic-regression rejection contract;
- raw-segment object SHA verification and raw-object-before-metadata persistence ordering;
- memory metadata repository for unit/local smoke tests only;
- production PostgreSQL ingest repository using per-Gateway-EUI advisory transaction locks for atomic checkpoint/segment decisions;
- pgx-backed connection policy pinned to Go 1.25 / pgx v5.10.0 with hostname-verified TLS, SCRAM-only authentication, expected-role membership, and per-session writable-primary checks;
- executable `gateway-evidence-ingest` process wiring with graceful shutdown and direct mTLS listener construction;
- frozen `mqtt-collector-runtime-v1` dual-broker contract and Paho MQTT v5 source pinned at `github.com/eclipse/paho.golang v0.23.0`;
- `gateway-mqtt-evidence-collector` source with two independent persistent sessions to the physical Mosquitto backends, exact opaque payload capture, read-only subscription behavior, raw-object-before-metadata-before-ACK ordering, PostgreSQL duplicate convergence, and `/healthz`/`/readyz`/`/metrics` endpoints; `event/up` additionally receives the pinned `concentratord-uplink-correlation-v1` semantic projection only after raw storage succeeds;
- frozen `verifier-runtime-v1` source boundary with v2 outbox discovery, `SKIP LOCKED` lease claims, lease-owner fencing, deterministic application/trusted-decoder comparison, exact first-reception provenance, raw MQTT object reopen/redecode, deterministic MQTT lookup, exact closed-journal parsing, complete predecessor-object chain verification through the matched segment, accepted-checkpoint digest recomputation, bounded retry, health/object-store readiness, full lineage persistence, and lease-fenced complete-lineage promotion to `verified`;
- trusted-decoder startup self-test plus build-time package-digest gate;
- `gateway-evidence-verifier` executable source using the `gateway_evidence_verifier` PostgreSQL authority boundary;
- separate `gateway-fabric-adapter` source with pinned Fabric Gateway v1.12.0/JCS v1.0.1, frozen v1/v2 startup vectors, immutable OpenBao seal persistence/verification, seven-argument Fabric submit/reconciliation state machine, read-only reconstruction mode, and fail-closed pre-handoff standby runtime;
- a Rust 1.82 gateway crate with exact `gateway-journal-v1` RFC 8785 hashing, canonical JSONL segment framing, monotonic state, torn-tail recovery, segment/checkpoint upload projection, independently reproduced fixed record/segment/object vectors, strict receipt validation/state, and a compiled `gw.Event`/`gw.UplinkFrame` Concentratord adapter pinned to the commissioned schema with an independent semantic correlation vector;
- `migrations/001_gateway_evidence.sql` with the evidence schema, worker-lease state, canonical lowercase Gateway-EUI constraints, database-level checkpoint monotonicity trigger, segment-1 `GENESIS`/later-predecessor constraints, verified-row projection completeness constraints, indexes, views, and least-privilege role grants;
- `migrations/001_gateway_evidence.verify.sql` for post-migration schema/ACL/invariant verification.

Not implemented or commissioned yet:

- selection and live commissioning of a production durable raw-object service. The Go source now includes an S3-compatible immutable backend with HTTPS/explicit-CA validation, conditional create-if-absent semantics, idempotent duplicate comparison, bounded reads, and tests; what remains is choosing/provisioning a real backend whose replication/failure domain demonstrably survives one Droplet loss;
- registry OCI images for the cloud evidence services; four Linux/amd64 executable candidates are compiled/tested and locked, and static scratch packaging validation passes, but image build/push/registry digest pinning is still pending;
- live collector identities/ACLs and four commissioned MQTT sessions;
- live verifier authority exercise; source can author `verified` only through the complete-lineage lease-fenced path, but no live verified row is claimed until production storage/migration/credentials/replicas and one real gateway lineage are commissioned;
- one real commissioned-gateway Concentratord event plus corresponding MQTT `event/up` fixture to validate the frozen synthetic `concentratord-uplink-correlation-v1` contract against physical runtime bytes;
- gateway HTTP transport and durable on-disk receipt-file persistence; request/receipt validation state exists, but **all local evidence-retirement/delete behavior remains intentionally absent**;
- Evidence PKI/shared-443 ingress adapter/configuration;
- live PostgreSQL migration, role credentials, or evidence listeners.

The repository host does not require a global Go installation. `cloud/scripts/dev-build.ps1` bootstraps checksum-pinned Go 1.25.0 into project-local ignored paths, isolates all Go caches, and the current four-service tree passes `gofmt`, `go test ./...`, `go build ./...`, and Linux/amd64 builds. The checksum-pinned offline reset-toolchain recovery mechanism was proven earlier; current four-binary acceptance is the full offline build plus exact-lock packaging validation, not a newly claimed reset replay. The Rust side is pinned by `gateway/rust-toolchain.toml` to Rust 1.82.0 and `gateway/scripts/dev-build.ps1` verifies the exact rustc commit, locked crate graph, formatting, tests, Clippy, and build. `scripts/verify-build.ps1` is the one-command entry point for both halves, including cached offline mode. Registry Docker/OCI image execution remains a separate gate.

## Layout

```text
evidence-services/
  contracts/
    evidence-ingest-api-v1/
    evidence-ingest-receipt-v1/
    gateway-journal-v1/
    gateway-journal-segment-v1/
    mqtt-capture-v1/
    mqtt-collector-runtime-v1/
    trusted-decoder-normalized-v1/
    verifier-runtime-v1/
  gateway/
    Cargo.toml
    Cargo.lock
    src/
    tests/
  cloud/
    go.mod
    internal/
      config/
      database/
      ingest/
      logging/
      mqttcapture/
      mqttcollector/
      objectstore/
      uplinkcorrelation/
      trusteddecoder/
      verifier/
    cmd/
      evidence-ingest/
      evidence-mqtt-collector/
      evidence-verifier/
  migrations/
```

The Go `cmd/` trees contain source wiring; generated binaries stay in ignored `.dev-out/`. The Rust gateway tree contains the journal/segment/state/upload contract core and pinned Concentratord adapter, while physical IPC/runtime packaging remains a later gate. Rebuild instructions start at `BUILD.md`. Server reconstruction is defined in `cloud/deploy/README.md` and uses the same tracked Compose bundle on all three hosts with profile-specific host env files. Do not commit generated toolchains, caches, targets, binaries, live env files, credentials, or private keys.

## Safety boundary

The filesystem object store and in-memory metadata repository are intentionally development/test-only. They prove API semantics such as create-if-absent, exact duplicate idempotency, conflicting duplicate rejection, checkpoint regression rejection, and SHA-256 verification. They do **not** satisfy the live cloud requirements for one-Droplet-loss raw-byte durability or PostgreSQL-backed metadata HA.

`001_gateway_evidence.sql` is an implementation artifact, not evidence that the live Patroni cluster has been mutated. Apply it only through the guarded deployment journey after the production raw-store, compiled runtimes, restore, PKI/ingress, and credential gates are ready.
