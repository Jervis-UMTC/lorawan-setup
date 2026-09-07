# Task 37 Fabric adapter build lock

Current source commit: `60fd903f9ab59536a7d311a717e2a89e7ecf058c`.

The Task 37 source repair changed the Fabric adapter after the original September 1 binary lock was created. The repaired adapter is therefore locked separately from the earlier pre-repair binary.

Verified build environment:

- Go `1.25.0`
- builder image `golang:1.25.0-bookworm` (`linux/amd64`)
- `GOOS=linux`, `GOARCH=amd64`, `CGO_ENABLED=0`
- build flags: `-trimpath -buildvcs=false`
- source exported from the exact commit above, not from the dirty working tree

The adapter was built twice independently on ULC-01 from that frozen source. Both outputs were byte-identical:

- size: `25585628` bytes
- SHA-256: `f28d5469895e3d65547389ba01869dea3ebe898b6d60371f35bafe4ecba389c8`

The deployment image is built once from this locked binary and distributed as the same Docker archive to ULC-01 and ULC-02. Keep `FABRIC_ADAPTER_ENABLED=false` on both hosts until the governed HRC activation gate is satisfied.

Do not use the older adapter lock `ac2180e9...`; it predates the Task 37 source repair.
