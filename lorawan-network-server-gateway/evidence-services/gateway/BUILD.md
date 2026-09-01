# Reproducible Gateway Rust Build

This manual owns the build/test setup for the gateway evidence crate. The crate now includes separate long-running `gateway-evidence-writer` and `gateway-evidence-uploader` executables, crash-safe persistent journal state, durable canonical receipt files, bounded HTTPS/mTLS upload with retry/backoff, `--sync-once`, validated configuration boundaries, and the pinned Concentratord correlation contract. The source/default-feature runtime is implemented and tested; the remaining commissioning boundary is target-native `concentratord-zmq` compilation plus Gateway OS/OpenWrt package/service installation and physical-gateway acceptance.

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

On the current Windows workstation, the canonical PowerShell script is blocked by a machine-enforced `Restricted` execution policy and the MSVC target cannot link because Visual Studio `link.exe` is absent. Do not weaken machine policy merely to make the script run. The accepted source-validation workaround bootstraps the official Rust installer into ignored project-local `.dev-cargo/`, verifies the installer SHA-256, proves the exact Rust 1.82.0 commit, and runs the same format/test/Clippy/build gates with the project-local `x86_64-pc-windows-gnu` toolchain. This is a workstation source-validation fallback only; it is not Gateway OS target acceptance.

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

## New-chat efficiency rule

The cloud evidence rollout is already commissioned. On a new chat, use the cached/pinned default build only as a quick source-regression gate when relevant, then continue directly with the Gateway OS/OpenWrt target build and `concentratord-zmq` package work. Do not spend time repeating cloud rollout steps that are already PASS.

Current source audit is explicit: the writer runtime consumes the pinned Concentratord ZeroMQ contract when built with `concentratord-zmq`; the uploader runtime is implemented independently and resumes durable closed-segment/checkpoint work from disk. The transport source matches the pinned MQTT Forwarder framing: ZeroMQ `SUB`, empty subscription, bounded poll, one-frame protobuf `gw::Event`, with non-uplink stats/mesh events ignored by the uplink path and multipart input rejected. This transport is isolated behind the explicit feature so the default Rust 1.82 build stays portable. `PersistentJournal` makes retained closed/open segments authoritative, syncs evidence bytes before state advancement, performs same-directory replacement plus directory fsync on Unix/Gateway OS, truncates only a torn final JSONL line, promotes completed files left under `open/`, rejects state-ahead corruption, and fails closed on storage-budget exhaustion. `ReceiptStore` persists exact canonical accepted checkpoint/segment receipts with fsync/rename semantics. `CurlTransport` requires HTTPS, CA validation, client certificate/key, bounded connect/request time, and preserves server-name verification; `Uploader` validates receipt identity, persists it before considering work complete, is restart-idempotent, and uses bounded exponential retry only for transient transport/HTTP classes. Local evidence deletion/retirement remains intentionally absent. The remaining code/package gate is native `concentratord-zmq` compilation in the actual Gateway OS/OpenWrt-capable toolchain and service packaging.

### Fresh restricted-workstation verification - 2026-09-01

The current workstation's `.dev-cargo/bin/rustup.exe` proxies existed but the pinned GNU toolchain was no longer installed. The fallback was recovered entirely inside ignored project-local state by setting `RUSTUP_HOME=.dev-cargo/rustup` and installing only `1.82.0-x86_64-pc-windows-gnu` with `rustfmt` and `clippy`. Exact `rustc -vV` returned release `1.82.0`, commit `f6e511eec7342f59a25f7c0534f1dbea00d01b14`, and LLVM `19.1.1`.

Fresh default-feature verification was rerun after the writer/uploader/receipt implementation and passed:

```text
cargo fmt --all -- --check                         PASS
cargo test --locked                                PASS (28 tests total, 0 failed: 19 unit + 9 contract)
cargo clippy --locked --all-targets -- -D warnings PASS
cargo build --locked                               PASS
gateway-evidence-writer --check-config             PASS (previous configuration probe retained)
gateway-evidence-uploader --check-config           PASS (previous configuration probe retained)
```

The configuration probes used only representative non-secret values and did not print private-key contents or credential material. The current 28-test gate includes restart reconstruction, torn-tail truncation, completed-open promotion, state-ahead rejection, start/append/close budget fail-closed behavior, durable receipt restart, uploader receipt idempotency, curl response parsing, and transient/fatal HTTP status policy. This is a fresh source/build proof, not Gateway OS target acceptance: Windows cannot prove the final OpenWrt binary, real ZeroMQ IPC, POSIX/flash behavior under power loss, or service supervision.

## What this proves

It proves the tracked Rust contracts, writer persistence/runtime logic, durable receipt store, HTTPS/mTLS uploader/retry logic, and separated configuration boundaries build/test cleanly against pinned Rust 1.82, while preserving the optional ZeroMQ transport behind its explicit feature. It does **not** yet prove `concentratord-zmq` compiles in the final Gateway OS/OpenWrt target toolchain, physical Concentratord IPC access, target-filesystem behavior under real power loss, service supervision, flash endurance, WAN recovery on hardware, or real paired gateway/MQTT/journal correlation. Those are the remaining target/physical commissioning gates.


## Gateway OS / OpenWrt target acceptance - 2026-09-01

The earlier target/package gap is closed for the factory-image boundary. The `concentratord-zmq` runtime was cross-built for `armv7-unknown-linux-musleabihf` with the OpenWrt hard-float toolchain and packaged as `gateway-evidence 0.1.0-r2`.

```text
gateway-evidence-writer   sha256=295810c45acc86b016aed1f9c7c066e6e2b300480ba19b81951385c1679b4b7c
gateway-evidence-uploader sha256=422b3c54221bdfe161e2edd3672f6dd721c2a068258d57ac4f58141b1c2995d0
cross-builder              sha256:c94da22b5f94919d7aa6ec10a966e5a5436c7a647dfb939b19e4927d727d4942
factory-image              sha256=bafe8b97baf9353df2654b1c8b71fa53d2ff764cd264d0ed6c924dd25a5ec67d
factory-bytes              28900364
manifest                   sha256=02aca2da02f7dbad8d598c90f778b676d0eda569762e0e5bf0cbd7baaadbb18d
config.buildinfo           sha256=3f23016b9a2cae9f2b82c57d6645355cd597ca835c9ad07f69884d6c1b696eab
```

Independent SquashFS inspection confirmed both evidence binaries, service scripts, users/groups, writer boot enablement, uploader default disablement, journal UCI paths, and no embedded evidence TLS secrets. The same image contains the accepted RAK5146/AS923 profile, SIM7600/QMI support, Mosquitto, and normal MQTT Forwarder. Remaining commissioning is physical: one real Concentratord uplink into the journal and, after mTLS provisioning, one accepted server receipt.
