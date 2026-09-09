# Task 37 / production Fabric adapter build lock

The original Task 37 source repair was committed as `60fd903f9ab59536a7d311a717e2a89e7ecf058c`. Its first repaired qualification adapter build produced SHA-256 `f28d5469895e3d65547389ba01869dea3ebe898b6d60371f35bafe4ecba389c8` at `25585628` bytes. That qualification-era binary superseded the older pre-Task37 `ac2180e9...` adapter and must not be confused with the later production continuous-writer build below.

## Production continuous-writer build

The production worker includes the Task 37 exact-payload and durable-transaction repair plus the SQL parameter-typing correction required by the generic outbox `finish()` path. The corresponding deployment/recovery changes were preserved in repository commit `bc569a1` and pushed to `main`.

Verified build environment:

- Go `1.25.0`
- builder image `golang:1.25.0-bookworm` (`linux/amd64`)
- `GOENV=off`
- `GOOS=linux`, `GOARCH=amd64`, `CGO_ENABLED=0`
- build flags: `-trimpath -buildvcs=false -mod=readonly`
- targeted tests: `./internal/fabricadapter` and `./cmd/fabric-adapter`
- isolated `cloud-sim` builder; production hosts were not used as compilers

Two independent binary builds were byte-identical:

```text
size=25609711
sha256=a53990277d9032e60a9f0bfb52619a21e8c999a3573477dbfb3efe6ca6fb9591
REPRODUCIBLE_BUILD=PASS
```

The locked binary was packaged twice with Buildx using `--no-cache --provenance=false --sbom=false`, fixed `SOURCE_DATE_EPOCH=1788825600`, numeric runtime user `65532:65532`, and `/service` entrypoint. Both runs produced the same image identity:

```text
image_tag=task37-gateway-fabric-adapter:prod-a53990277d9032e6
image_id=sha256:d12e73ae24f7823730b6632fe8209e844c0d6125bd6a9c13e9d75cc330664f74
binary_label=a53990277d9032e60a9f0bfb52619a21e8c999a3573477dbfb3efe6ca6fb9591
OCI_REPRODUCIBLE=PASS
```

Saved image archive:

```text
size=12238336
sha256=335a8e920b4eba5b7cbf73a0cac4edfeac15d99017a0b832c0b20d887df65f4c
```

## Live placement

- ULC-01 runs the exact production image ID above with `FABRIC_ADAPTER_ENABLED=true` as the governed continuous Fabric writer.
- ULC-02 remains `FABRIC_ADAPTER_ENABLED=false` standby and must not be enabled until lease renewal / ownership fencing and the dual-worker HA acceptance gate pass.
- Do not rerun the one-record Task 37 qualification candidate merely to prove the continuous worker.

The older `f28d5469...` Task 37 qualification binary and `ac2180e9...` pre-Task37 binary remain historical evidence only; production recovery must use the `a5399027...` binary / `d12e73ae...` image identity above.