# Rebuild the Security Evidence Services

Use this page when setting the project up again on a Windows amd64 development/build host.

## Efficient new-session start

The cloud evidence services are commissioned. For current work, inspect the Gateway OS/OpenWrt target build environment first. Use the pinned Rust default gate only when a source regression check is useful:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\gateway\scripts\dev-build.ps1
```

The current Rust source implements the writer/uploader runtime and passes 28 tests plus format/Clippy/locked build, but this workstation command does not create or validate the final OpenWrt `concentratord-zmq` binary/package. The target build/package and physical lineage are the current gateway gates.

## One command

Prerequisites:

- PowerShell;
- `curl.exe` (normal modern Windows installation);
- `rustup` from the official Rust installer.

From repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\scripts\verify-build.ps1
```

That command verifies both implementation halves:

```text
cloud/
  checksum-pinned portable Go 1.25.0
  tracked go.mod + go.sum
  gofmt
  go test ./...
  go build ./...
  deterministic Linux/amd64 binary candidates

gateway/
  exact Rust 1.82.0 / rustc commit pin
  tracked Cargo.lock
  cargo fmt --check
  cargo test --locked
  cargo clippy --locked -D warnings
  cargo build --locked
```

All Go toolchains/caches/binaries and Rust dependency/build caches are generated in ignored project-local directories. They are never required Git inputs.

## Interrupted internet

The Go bootstrap downloads to a partial archive and resumes the same file. Cargo preserves successfully downloaded crates and retries locked dependency fetches. After one successful online run, use:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\scripts\verify-build.ps1 -Offline
```

Offline mode fails rather than silently going online if required cached inputs are missing.

To additionally prove that the extracted Go compiler can be recreated from its checksum-verified cached archive:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\scripts\verify-build.ps1 -Offline -ResetGoToolchain
```

## Detailed manuals

- Cloud Go build: `cloud/BUILD.md`
- Gateway Rust build: `gateway/BUILD.md`
- OCI packaging: `cloud/packaging/README.md`

This build layer does not mutate PostgreSQL, MQTT, Node-RED, OpenBao, the physical gateway, DNS, PKI, or live cloud services.
