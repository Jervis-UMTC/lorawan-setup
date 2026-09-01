# Gateway evidence OpenWrt package

This directory is the reproducible firmware wrapper for the gateway evidence writer and uploader used by the ChirpStack Gateway OS `v4.12.0` Raspberry Pi Base image.

The runtime binaries are cross-built from the sibling Rust crate with Rust `1.82.0`, target `armv7-unknown-linux-musleabihf`, and the exact OpenWrt `bcm27xx/bcm2709` toolchain (`arm-openwrt-linux-muslgnueabi`, Cortex-A7, NEON/VFPv4, hard-float, musl). Stage the two verified release binaries at `gateway-evidence/files/usr/bin/` before invoking the OpenWrt package build.

The firmware enables only the local writer by default. The uploader is deliberately disabled because the real evidence-ingest HTTPS origin and the gateway-specific mTLS CA/client certificate/private key are deployment credentials and must not be embedded in the image. Provision those files under `/etc/gateway-evidence/tls`, keep the private key mode `0600`, set the uploader UCI values, then enable the uploader.

Persistent journal state lives under `/etc/gateway-evidence/journal`, which is OverlayFS-backed on this Gateway OS target. `/var` is not used as the durable journal root. Journal directories are setgid `2750` and files are `0640`; the uploader shares the evidence group for read access while its TLS directory is `0700` and owned by the uploader identity.
