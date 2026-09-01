# Reproducible Cloud Go Build

This manual owns the developer/build-host setup for the Go evidence services under this directory. It is deliberately self-contained: a fresh Windows build host does **not** need a global Go installation, administrator changes, a PowerShell profile edit, or `go env -w` state.

This build manual is not itself the deployment procedure, but the cloud services built from it are now commissioned. The live PostgreSQL migration/HBA/CONNECT/six-login boundary, three-node PgBouncer evidence auth, SeaweedFS S0-S9, immutable GHCR image refs, PKI/MQTT identities, replicated services, shared-443 and evidence observability are PASS. The remaining end-to-end gate is the Gateway OS target package/physical lineage, plus separate provider/Fabric external inputs.

## Pinned build inputs

```text
Go version:       1.25.0
Developer host:   Windows amd64
Archive:          go1.25.0.windows-amd64.zip
Official URL:     https://go.dev/dl/go1.25.0.windows-amd64.zip
SHA-256:          89efb4f9b30812eee083cc1770fdd2913c14d301064f6454851428f9707d190b
Go module:        evidence-services/cloud/go.mod
Dependency lock:  evidence-services/cloud/go.sum
Deployment build: linux/amd64, CGO_ENABLED=0, -trimpath, -buildvcs=false
```

The version and archive checksum are hard-coded in `scripts/dev-build.ps1`. A different archive is rejected before extraction.

## Generated local paths

All build-host state stays below the project and is ignored by Git:

```text
evidence-services/cloud/.dev-tools/  # verified Go archive + extracted portable toolchain
evidence-services/cloud/.dev-cache/  # Go module/build/GOPATH caches
evidence-services/cloud/.dev-out/    # generated Linux amd64 binaries
```

The earlier interrupted `.tmp-go-build/` location is legacy temporary state and is not an input to this procedure.

## First setup on a fresh Windows build host

From repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\cloud\scripts\dev-build.ps1
```

`-ExecutionPolicy Bypass` applies only to that PowerShell process. The script does not change the machine or user execution policy.

The first run needs internet access for the pinned Go archive and any Go modules not already cached. It downloads the Go archive to a `.partial` file, verifies SHA-256, and only then promotes/extracts it. If connectivity drops, rerun the **same command**: the partial archive is preserved and `curl.exe` resumes it from the saved byte offset. A partial file that already contains the complete archive is promoted without another network request after its pinned SHA-256 matches. Extraction/output staging paths are disposable and are rebuilt automatically.

Normal builds require tracked `go.sum` and run with `-mod=readonly`. They therefore do not silently rewrite dependency lock state.

Expected terminal gates after a successful normal run include:

```text
GO_TOOLCHAIN_CHECKSUM=PASS
GO_VERSION=PASS
GO_MOD_DOWNLOAD=PASS
GO_MOD_VERIFY=PASS
GOFMT=PASS
GO_TEST=PASS
GO_BUILD=PASS
GO_LINUX_AMD64_BINARIES=PASS
REPRODUCIBLE_GO_BUILD=PASS
```

The script also prints one `ARTIFACT|...|sha256:<digest>` line for each generated Linux binary.

## Initial `go.sum` creation or deliberate dependency update

Use this only when initializing the dependency lock or intentionally changing dependencies:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\cloud\scripts\dev-build.ps1 -UpdateModuleLock
```

This runs `go mod tidy` explicitly. If that operation fails, the script restores the previous `go.mod` and `go.sum` state instead of leaving a half-updated dependency lock. Review the `go.mod`/`go.sum` diff before accepting it. Future ordinary builds return to `-mod=readonly`.

## Offline/cached rebuild

After one successful online run has populated the verified archive and module cache:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\cloud\scripts\dev-build.ps1 -Offline
```

Offline mode sets the Go proxy and checksum database network paths to `off`. It fails if the verified toolchain archive or a required module is absent from the project-local cache; it never silently goes online.

To prove the extracted toolchain itself can be recreated from the verified cached archive without internet access:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\cloud\scripts\dev-build.ps1 -Offline -ResetToolchain
```

`-ResetToolchain` removes only the generated extracted Go directory. It preserves the checksum-verified archive and module cache, then reconstructs the toolchain and reruns the full build gates.

## Verified build evidence — 2026-08-30

The build pipeline has previously proven both normal-build and offline reset-toolchain recovery gates. For the current four-binary source tree, the authoritative acceptance is the full offline build plus the exact-lock packaging validation recorded below. Successful build gates are:

```text
GO_TOOLCHAIN_CHECKSUM=PASS
GO_VERSION=PASS
GO_MOD_DOWNLOAD=PASS
GO_MOD_VERIFY=PASS
GOFMT=PASS
GO_TEST=PASS
GO_BUILD=PASS
GO_LINUX_AMD64_BINARIES=PASS
REPRODUCIBLE_GO_BUILD=PASS
```

The current accepted source includes the S3-compatible immutable object-store backend, verifier-owned complete-lineage `verified` transition, frozen v1/v2 JCS vectors, and the real Fabric adapter. The repository-authoritative offline gate passed module verification, `gofmt`, `go test ./...`, `go build ./...`, and Linux/amd64 cross-build for all four services. The resulting accepted executable bytes are:

```text
gateway-evidence-ingest
  size:   18179015
  sha256: a5de435343ee57b8725608e11cf356249a921d208cc041f5c59686f554bc3bf2

gateway-mqtt-evidence-collector
  size:   18552641
  sha256: 3d31d2b501fccf1bc5472708f2eb858eafd3efa7c6d0e66309d12937658aa0b5

gateway-evidence-verifier
  size:   17814443
  sha256: 69095c14a65e281b2574efcf968b2e77c260d66ed59396afa7bb31a3b922ab3a

gateway-fabric-adapter
  size:   25527785
  sha256: ac2180e96e31a8e66ea8a5a3ef41c51c458865f550b3ef94159f4bbc5c256afd
```

`packaging/binaries.lock` is authoritative for this four-binary set, and `build-images.ps1 -Offline -ValidateOnly` rebuilt the set and matched every locked size/hash while also passing the minimal scratch-Dockerfile checks. The ingest binary also carries the production `objectstore-contract-write` and read-only `objectstore-contract-verify` commissioning commands used to prove the selected SeaweedFS S3 endpoint rather than trusting compatibility claims. The verifier build still computes and injects the trusted-decoder source-package digest. The `-Offline -ResetToolchain` mechanism was proven earlier on the same pinned Go archive/build path; do not convert that older recovery proof into a claim that the current four-binary tree completed another reset replay unless such a run is recorded separately.

## What is and is not reproducible here

This procedure proves that the tracked Go source and locked public dependencies compile/test with the exact pinned Go toolchain, and it generates deterministic-path-independent Linux/amd64 executable candidates using `-trimpath` and disabled VCS stamping.

It does **not** by itself prove:

```text
OCI image reproducibility
Ubuntu runtime health
production raw-store durability
live database migration/grants
PKI or shared-443 ingress
replica failover behavior
real physical-gateway evidence lineage
```

Those remain deployment/commissioning gates in `deployment/server/integrations/gateway-integrity/`.

## Rebuilding on another machine

Required tracked inputs are only:

```text
repository source
scripts/dev-build.ps1
go.mod
go.sum
this manual
```

On a clean Windows amd64 host, run the normal command above. The script derives every path from its own location, verifies the exact Go archive, isolates all Go caches, disables the user's Go environment file with `GOENV=off`, and uses only process-local environment changes. Windows `curl.exe` is the only bootstrap download prerequisite; its resumable mode is used specifically so an interrupted connection does not force a clean restart.

Do not copy `.dev-tools`, `.dev-cache`, or `.dev-out` into Git as a substitute for reproducibility.

## Upgrading Go later

Treat a Go upgrade as a reviewed source/build change:

1. choose the new version from the official Go release page;
2. record the exact matching Windows amd64 archive name and SHA-256;
3. update the three pins at the top of `scripts/dev-build.ps1` together;
4. remove/rebuild only generated toolchain state;
5. run the dependency, format, test, host-build, Linux-build, and offline-reset gates;
6. record the new toolchain and executable SHA-256 values in the implementation evidence.

Never change only the version string while leaving an old checksum or cached extracted tree trusted.
