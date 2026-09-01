# Cloud Evidence OCI Packaging

This directory packages the already-tested Linux/amd64 Go binaries into minimal runtime images. It does not compile source inside Docker and does not download a base image: runtime images use `FROM scratch`.

## Why this packaging is narrow

The trusted build boundary is intentionally split:

```text
tracked Go source + go.sum
        |
        v
scripts/dev-build.ps1
        |
        +-- pinned Go 1.25.0 archive + SHA-256
        +-- gofmt / go test / go build
        `-- locked Linux/amd64 binary bytes
                |
                v
        packaging/binaries.lock
                |
                v
        tiny Docker context
        Dockerfile + one file named service
                |
                v
        scratch / UID 65532 / no shell / no package manager
```

This prevents a Docker build from silently compiling with a different toolchain or copying source trees, `.env` files, certificates, caches, or other repository content into the image.

## Runtime image contract

Each image contains only `/service` and Docker metadata:

```text
base:        scratch
entrypoint:  /service
user:        65532:65532
binary mode: 0555
port meta:   8080/tcp
stop signal: SIGTERM
shell:       none
package mgr: none
secrets:     none
```

The services use explicit mounted CA/certificate/key paths from their environment and therefore do not depend on a bundled operating-system CA store. Docker still supplies the normal container `/etc/hosts`, `/etc/hostname`, and `/etc/resolv.conf` needed by Go's pure resolver.

The image deliberately has no `HEALTHCHECK` executable. Adding `curl` or a shell solely for health checks would weaken the runtime image. Deployment must probe the service health/readiness endpoint externally and use container process state as the liveness boundary. Ingest exposes `/livez` and `/readyz` over its mTLS listener; collector, verifier, and Fabric adapter expose `/healthz` and `/readyz` on private/loopback health listeners.

## Locked current binaries

`binaries.lock` is an acceptance lock, not an automatically updated output. A source change that changes a binary must first pass the reproducible Go build; review the source/test result, then deliberately update this lock before rebuilding an image.

Current accepted Linux/amd64 bytes:

```text
gateway-evidence-ingest
  18179015 bytes
  a5de435343ee57b8725608e11cf356249a921d208cc041f5c59686f554bc3bf2

gateway-mqtt-evidence-collector
  18552641 bytes
  3d31d2b501fccf1bc5472708f2eb858eafd3efa7c6d0e66309d12937658aa0b5

gateway-evidence-verifier
  17814443 bytes
  69095c14a65e281b2574efcf968b2e77c260d66ed59396afa7bb31a3b922ab3a

gateway-fabric-adapter
  25527785 bytes
  ac2180e96e31a8e66ea8a5a3ef41c51c458865f550b3ef94159f4bbc5c256afd
```

## Static packaging validation

This works even on a host without Docker, provided the host is allowed to execute PowerShell scripts:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\cloud\packaging\build-images.ps1 -Offline -ValidateOnly
```

It reruns the reproducible Go build from the local cache, recomputes/injects the trusted-decoder source-package digest into the verifier, verifies every output against `binaries.lock`, and checks the minimal Dockerfile invariants. It never claims an image digest.

`-ExecutionPolicy Bypass` is process-scoped and **cannot override a domain/enterprise `MachinePolicy=Restricted`**. If Group Policy blocks script execution, use an approved build host or have the workstation policy corrected through the normal administrative channel. Do not inline-copy the build script, weaken enterprise policy, or accept hand-built binaries as a substitute for the pinned build/lock gate. A fresh build host also needs the cached/offline inputs described in `../BUILD.md`, or one successful online bootstrap before `-Offline` can work.

## Build on a Docker Buildx host

After the normal Go bootstrap has populated the cache, the packaging script builds exactly one `linux/amd64` platform image and rejects any loaded image whose inspected OS/architecture differs:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\cloud\packaging\build-images.ps1 -Offline
```

The script creates a temporary context containing only the tracked Dockerfile and one checksum-locked binary, normalizes both mtimes to `SOURCE_DATE_EPOCH=1788048000`, builds with provenance/SBOM attestations disabled for byte-stability testing, verifies the image runs as numeric non-root UID/GID `65532:65532`, verifies the entrypoint, prints the local content-addressed image ID, and removes the temporary context.

To require two builds to produce the same local image ID:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\evidence-services\cloud\packaging\build-images.ps1 -Offline -VerifyTwice
```

Do not record `OCI_IMAGE_REPRODUCIBILITY=PASS` unless that command actually passes on the selected Buildx version. This repository runner currently has no Docker/Podman/Buildah/nerdctl/ORAS, so no OCI image ID or registry digest is claimed here yet.

## Secrets and writable state

Never put DSNs, passwords, MQTT credentials, private keys, certificates, or raw evidence into the image. Supply them at deployment time through protected environment files and read-only mounts.

The root filesystem should be mounted read-only by the deployment definition. The filesystem object-store backend remains development-only. Production uses the S3-compatible backend against the commissioned self-hosted SeaweedFS 4.41 HA endpoint. Storage infrastructure/replication/TLS/create-only semantics and S9 production-helper cross-host acceptance are PASS. The four cloud OCI images are built, published, and pinned by immutable GHCR digests; this packaging directory remains the reproducible rebuild path.
