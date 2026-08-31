# Reproducible Gateway Rust Build

This manual owns the build/test setup for the gateway evidence crate. The crate is source/package validation for the journal, segment, upload-state, receipt, and pinned Concentratord correlation contracts; it is **not yet a commissioned Gateway OS executable**.

## Pinned inputs

```text
Rust release:      1.82.0
rustc commit:      f6e511eec7342f59a25f7c0534f1dbea00d01b14
Toolchain file:    rust-toolchain.toml
Dependency lock:   Cargo.lock
Edition:           2021
unsafe Rust:        forbidden
```

`rust-toolchain.toml` pins the exact compiler release and required `rustfmt`/`clippy` components. `scripts/dev-build.ps1` additionally verifies the exact rustc commit before running the build gates.

## Prerequisite

Install `rustup` from the official Rust installer. No particular default Rust compiler is required; the repository selects 1.82.0 explicitly.

## Normal build

From repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\gateway\scripts\dev-build.ps1
```

The script:

1. finds `rustup`;
2. installs Rust 1.82.0 if missing;
3. verifies release `1.82.0` and rustc commit `f6e511eec7342f59a25f7c0534f1dbea00d01b14`;
4. uses tracked `Cargo.lock` with `--locked`;
5. stores crate downloads in ignored project-local `.dev-cargo/`;
6. stores compilation output in ignored project-local `.dev-target/`;
7. runs `cargo fmt --check`;
8. runs all tests;
9. runs Clippy with warnings denied;
10. runs a locked build.

Expected final markers:

```text
RUST_TOOLCHAIN_IDENTITY=PASS
RUST_CARGO_FETCH=PASS
RUST_FMT=PASS
RUST_TEST=PASS
RUST_CLIPPY=PASS
RUST_BUILD=PASS
REPRODUCIBLE_GATEWAY_RUST_BUILD=PASS
```

If the internet connection drops during dependency fetch, rerun the same command. Cargo keeps successfully downloaded crates in `.dev-cargo/`, and the script retries the locked fetch before stopping.

## Offline rebuild

After one successful online run has populated the exact Rust toolchain and project-local Cargo cache:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\gateway\scripts\dev-build.ps1 -Offline
```

Offline mode refuses to install a missing toolchain and passes Cargo `--offline`; it cannot silently access the network.

## What this proves

It proves the tracked Rust source builds/tests against the exact compiler identity and locked crate checksums. It does not prove physical Concentratord IPC access, Gateway OS packaging, service supervision, flash durability, WAN behavior, or real paired gateway/MQTT correlation. Those remain later commissioning gates.
