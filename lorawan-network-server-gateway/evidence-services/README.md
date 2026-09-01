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
- a Rust 1.82 gateway runtime with separate writer/uploader executables, exact `gateway-journal-v1` RFC 8785 hashing, canonical JSONL segments, monotonic crash-safe fsync-backed persistence/recovery, optional pinned ZeroMQ Concentratord subscriber, deterministic correlation, durable canonical receipt storage, HTTPS/mTLS curl transport, bounded retry/backoff, `--sync-once`, and continuous loops. The current default source gate passes 28 tests plus format/Clippy/locked build; target-native OpenWrt compilation and physical installation remain;
- `migrations/001_gateway_evidence.sql` with the evidence schema, worker-lease state, canonical lowercase Gateway-EUI constraints, database-level checkpoint monotonicity trigger, segment-1 `GENESIS`/later-predecessor constraints, verified-row projection completeness constraints, indexes, views, and least-privilege role grants;
- `migrations/001_gateway_evidence.verify.sql` for post-migration schema/ACL/invariant verification.

Current live/pending boundary:

- **cloud evidence runtime is commissioned / PASS**: SeaweedFS 4.41 S0-S9; the `gateway_evidence` PostgreSQL migration/HBA/CONNECT/six SCRAM LOGINs; the ten-role PgBouncer userlist on all three nodes; immutable GHCR image digests; Evidence PKI; four distinct read-only collector mTLS identities/ACLs; ingest-1/2; collector-1/2 each connected to both physical brokers; verifier-1/2 with the pinned trusted decoder; shared anchor `:443` TCP/SNI routing; and Grafana evidence checkpoint/verification panels;
- Fabric adapter-1/2 are deployed from immutable images only in `FABRIC_ADAPTER_ENABLED=false` standby; no SecretID/ledger transaction is claimed;
- the Rust writer/uploader source runtime is implemented and tested. OpenWrt UCI/procd package source exists; the remaining gateway implementation gate is target-native `concentratord-zmq` cross-build/package installation and real IPC/RF acceptance. **Local evidence retirement/delete remains intentionally absent**;
- one real commissioned-gateway journal + corresponding MQTT/application lineage remains hardware-dependent before a live verifier-owned `verified` row is claimed;
- the public ChirpStack/Evidence/MQTT normal path is commissioned on Reserved IPv4 `129.212.208.168`; only Reserved-IP reassignment/failover authority and controlled acceptance remain provider-dependent;
- Fabric ledger execution remains blocked on the external Fabric handoff and deliberate adapter credential activation.

The repository host does not require a global Go installation. `cloud/scripts/dev-build.ps1` bootstraps checksum-pinned Go 1.25.0 into project-local ignored paths, isolates all Go caches, and the current four-service tree passes `gofmt`, `go test ./...`, `go build ./...`, and Linux/amd64 builds. The four accepted cloud images are now published and pinned by immutable GHCR digests in the production release file. The Rust side is pinned by `gateway/rust-toolchain.toml` to Rust 1.82.0; the current default writer/uploader source gate passes 28 tests total, formatting, Clippy, and locked build. The separate native/OpenWrt target build remains required for `concentratord-zmq` and final gateway binaries.

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

The Go `cmd/` trees contain source wiring; generated binaries stay in ignored `.dev-out/`. The Rust gateway tree contains the writer/uploader runtime plus OpenWrt package source; target cross-build and physical package/IPC acceptance remain the later gate. Rebuild instructions start at `BUILD.md`. Server reconstruction is defined in `cloud/deploy/README.md` and uses the same tracked Compose bundle on all three hosts with profile-specific host env files. Do not commit generated toolchains, caches, targets, binaries, live env files, credentials, or private keys.

## Safety boundary

The filesystem object store and in-memory metadata repository are intentionally development/test-only. They prove API semantics such as create-if-absent, exact duplicate idempotency, conflicting duplicate rejection, checkpoint regression rejection, and SHA-256 verification. They do **not** satisfy the live cloud requirements for one-Droplet-loss raw-byte durability or PostgreSQL-backed metadata HA.

`001_gateway_evidence.sql` is the reproducible source of the already-commissioned live schema/ACL boundary. Do not reapply it to the current Patroni cluster; use it for rebuild/recovery or a deliberate forward migration.
