# Fabric Adapter HA Fencing Commissioning

Status date: 2026-09-09

This note records the generation-fencing repair and the exact deployment boundary for commissioning the second Fabric adapter worker. It is intentionally separate from older Task 37 qualification/build evidence.

## Safety boundary

- Never rerun Task 37 qualification candidate/outbox `1960`.
- ULC-01 remains the sole production writer until both nodes run the generation-aware binary and migration `003_fabric_adapter_ha_fencing.sql` is present.
- ULC-02 must remain `FABRIC_ADAPTER_ENABLED=false` until image parity, distinct worker IDs, database fencing, and the controlled failover gate are verified.
- The exact-payload, durable prepared-transaction, Query, and Verify semantics remain unchanged.

## Fencing contract

Migration `003_fabric_adapter_ha_fencing.sql` adds `telemetry.fabric_outbox.lease_generation BIGINT NOT NULL DEFAULT 0`, a nonnegative check, its column comment, and the minimum `fabric_adapter` UPDATE grant for that column.

Every successful claim atomically increments `lease_generation`. Every worker-owned mutation must match all of:

```text
outbox_id
worker_id
lease_generation
lease_expires_at > now()
```

Lease renewal is also generation-bound. The worker performs an explicit generation-aware renewal before Fabric Prepare, before SubmitPrepared, and before reconciliation resubmission. A stale process therefore cannot regain authority merely because it later uses the same stable worker ID.

The migration is additive. It can remain installed during rollback, but dual-worker operation must not mix a generation-aware worker with an older worker that does not enforce the generation predicate.

## Database-backed proof

A disposable PostgreSQL 16 instance exercised the real lease timing and SQL predicates. Result: `HA_FENCE_DB_PROOF_PASS`.

Sequence:

1. worker `same-worker` claimed one row as generation 1;
2. a real 92-second stall allowed the 90-second lease to expire;
3. the same worker ID reclaimed the row as generation 2;
4. stale generation 1 lease renewal affected 0 rows;
5. stale generation 1 prepared-transaction persistence affected 0 rows;
6. stale generation 1 confirmation affected 0 rows;
7. current generation 2 renewal, prepared persistence, and confirmation each affected 1 row;
8. final row was `confirmed|2|current-tx|2`.

The disposable PostgreSQL container was removed after the proof.

## Source/build acceptance

The HA changes were overlaid onto a detached clean `HEAD` worktree so unrelated dirty workspace files could not contaminate acceptance. Using the pinned Go 1.25.0 toolchain with `GOENV=off`, `GOTOOLCHAIN=local`, offline module/cache settings, `-mod=readonly`, `-trimpath`, and `-buildvcs=false`:

```text
GO_MOD_VERIFY=PASS
TASK_GOFMT=PASS
GO_TEST_ALL=PASS
GO_BUILD_ALL=PASS
REPRODUCIBLE_BINARY=PASS
ISOLATED_RELEASE_GATE=PASS
```

Two Linux/amd64, CGO-disabled builds with the build cache cleared between them were byte-identical:

```text
gateway-fabric-adapter
size:   25585501
sha256: 91873499220db54a27c49980a51c8ea4afe0acf9d0c446681cbb6d365db3db6b
```

## Locked deployment image

The test-preparation deployment image is a scratch image containing only the accepted binary, running as `65532:65532` with entrypoint `/service`. The binary label matches the accepted binary SHA-256.

```text
image tag: task37-gateway-fabric-adapter:ha-91873499220db54a
image id:  sha256:d139b25e60bc3b4baf32ad465b59fd8f42a764516eb984d4318a307e3a2947fc
user:      65532:65532
entrypoint:["/service"]
binary:    91873499220db54a27c49980a51c8ea4afe0acf9d0c446681cbb6d365db3db6b
```

The workstation's available legacy Docker builder injects build-history timestamps, so repeated package builds did not produce identical image IDs. Do **not** claim OCI-image reproducibility for this HA package. Binary reproducibility is proven; runtime parity is enforced by deploying the exact same locked archive to both nodes.

Locked deployment archive:

```text
filename: gateway-fabric-adapter-ha-91873499220db54a.tar
sha256:   0e863742cf6bfd8701ce9c5f370d5ec14f47470a637730ebdd82c8a1f3209007
size:     12231168
```

## Production commissioning order

1. Verify ULC-01 is healthy and enabled, ULC-02 is healthy but disabled, and no current critical Fabric errors exist.
2. Apply migration `003_fabric_adapter_ha_fencing.sql` once through the current PostgreSQL primary path; verify column/default/check/comment/grant.
3. Load the locked archive on ULC-01 and roll only the Fabric adapter to the generation-aware image. Verify image ID, binary label, enablement, restart count, DB access, OpenBao access, and Fabric path.
4. Load the exact same archive on ULC-02 while keeping `FABRIC_ADAPTER_ENABLED=false`; verify exact image ID parity and standby self-test/preflight.
5. Verify ULC-01 and ULC-02 use distinct stable `FABRIC_ADAPTER_WORKER_ID` values.
6. Enable ULC-02 and verify two workers can poll safely without simultaneous ownership of the same live claim.
7. Perform one controlled HA acceptance: stop only the ULC-01 adapter, allow the lease boundary to pass as needed, and prove ULC-02 processes a fresh eligible verified exact-payload row. Never use outbox `1960`.
8. Require authoritative Fabric commit, source-bound Query match, and Verify `MATCH` for the representative takeover row.
9. Restore ULC-01 and verify both workers are healthy, no duplicate/conflicting submission exists, and generation fencing remains authoritative.
10. Leave both workers running only after the preceding gate passes; otherwise leave ULC-02 disabled and retain ULC-01 as sole writer.

## Rollback

- If ULC-01 fails after the image rollout, restore its previous known-good image and keep ULC-02 disabled.
- Migration 003 is additive and may remain installed during rollback.
- Never enable the older ULC-02 worker against a dual-worker topology after migration merely because the column exists; both active workers must enforce generation predicates.
- Preserve durable Fabric transaction fields and reconcile unknown submissions before any new Create.
