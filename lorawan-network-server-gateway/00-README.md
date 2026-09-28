# LoRaWAN Gateway and Server Documentation

Choose one path and stay in that path while working:

```text
test/              -> dissertation preparation, automated capture, and counted Chapter III/IV procedures
deployment/        -> complete deployment, HA, security, operations, and cloud manuals
evidence-services/ -> reproducible gateway/cloud evidence-service source and build/deploy material
firmware/          -> tracked sensor firmware source
chapter4-results/  -> retained research evidence and derived run outputs
docs/              -> planning/history index; not the live operator entry point
presentations/     -> presentation material
```

Choose your objective first:

| Directory | Purpose | Entry Point |
|---|---|---|
| **[test/](test/00-README.md)** | Build the smallest testbed that can execute the dissertation experiments and collect Chapter IV evidence. | [test/00-README.md](test/00-README.md) |
| **[deployment/](deployment/00-README.md)** | Build or operate the complete gateway/server architecture, including HA and production/cloud controls. | [deployment/00-README.md](deployment/00-README.md) |
| **[presentations/](presentations/2026-08-07-weekly-standup.html)** | Presentation and project-update material. | [presentations/2026-08-07-weekly-standup.html](presentations/2026-08-07-weekly-standup.html) |

For complete documentation layout and research alignment, see [DOCUMENTATION-MAP.md](DOCUMENTATION-MAP.md).

**Current research entry point:** use [test/00-README.md](test/00-README.md), then the [automated research recorder](test/automation/research-recorder/README.md) and the experiment-specific [counted execution manual](test/execution/00-README.md). Fabric is no longer an external activation blocker: ULC-01 production writes are enabled and verified; ULC-02 remains deliberately write-disabled until its HA fencing/ownership gate. Follow each current test manual's own GO/NO-GO status.

**Research truth boundary:** Chapter 3/4 PDFs and dissertation drafts are requirements references, not descriptions of current runtime state and not result truth. For a formal trial, the sealed capture under `chapter4-results/` is authoritative. Fresh read-only monitoring is authoritative only for the apparatus state at the time observed, while current deployment/configuration material is the reproducibility reference. Setup, smoke, recovery and preflight traffic must not be counted as formal trial data unless it falls inside an explicitly started recorder run and that run is classified accordingly.

The former next-day bring-up document is preserved only as historical provenance at [docs/archive/2026-09-02-sensor-gateway-bringup-handoff.md](docs/archive/2026-09-02-sensor-gateway-bringup-handoff.md).

---

## Supported Architecture Overview

```text
LoRaWAN Edge (Sensors & Raspberry Pi 4B + RAK5146 Gateway)
  -> ChirpStack Concentratord
      |-> MQTT Forwarder -> local Mosquitto disk buffer -> mTLS -> Server Mosquitto
      `-> gateway integrity journal -> hash-chained segments/checkpoints -> HTTPS/mTLS evidence ingest

Server evidence path
  Server Mosquitto -> read-only evidence collectors -> immutable SeaweedFS raw evidence
  ChirpStack -> Node-RED validation/normalization -> TimescaleDB telemetry + durable Fabric outbox
  journal + MQTT witness + application/telemetry -> evidence verifier + pinned trusted decoder
  verified v2 only -> Fabric Adapter -> OpenBao sign/verify -> Hyperledger Fabric
```

---

## Essential Gateway & Security Rules

- Use official ChirpStack Gateway OS **Base** image for Raspberry Pi 4B.
- Configure RAK5146 through **ChirpStack > Concentratord** (AS923 region plan).
- Keep UDP Forwarder disabled.
- Local Mosquitto broker must be bound strictly to `127.0.0.1:1883`.
- Bridge connection to server uses mutual TLS on `ssl://<BROKER_FQDN>:8883` with client certificate CN equal to `<GATEWAY_EUI>`.
- Treat buffered delivery as at-least-once; downstream integrations must remain idempotent.
- Do not place private keys, OTAA root keys, passwords, or OpenBao recovery shares in Markdown files.


