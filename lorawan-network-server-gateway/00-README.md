# LoRaWAN Gateway and Server Documentation

Choose one path and stay in that path while working:

```text
test/          -> minimum dissertation testbed and Chapter III/IV procedures
deployment/    -> complete deployment, HA, security, operations, and cloud manuals
presentations/ -> presentation material
```

Choose your objective first:

| Directory | Purpose | Entry Point |
|---|---|---|
| **[test/](test/00-README.md)** | Build the smallest testbed that can execute the dissertation experiments and collect Chapter IV evidence. | [test/00-README.md](test/00-README.md) |
| **[deployment/](deployment/00-README.md)** | Build or operate the complete gateway/server architecture, including HA and production/cloud controls. | [deployment/00-README.md](deployment/00-README.md) |
| **[presentations/](presentations/2026-08-07-weekly-standup.html)** | Presentation and project-update material. | [presentations/2026-08-07-weekly-standup.html](presentations/2026-08-07-weekly-standup.html) |

For complete documentation layout and research alignment, see [DOCUMENTATION-MAP.md](DOCUMENTATION-MAP.md).

**Next physical session:** use [TOMORROW-SENSOR-GATEWAY-BRINGUP.md](TOMORROW-SENSOR-GATEWAY-BRINGUP.md) as the single sensor + flashed-gateway execution path. Historical continuation notes are not operator entry points.

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
