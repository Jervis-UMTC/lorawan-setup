# Gateway Integrity and Evidence Verification

These guides define the server-side half of the software-only gateway integrity design.

The physical gateway keeps two paths:

```text
DELIVERY
Concentratord -> MQTT Forwarder -> local Mosquitto -> remote MQTT

EVIDENCE
Concentratord -> hash-chained journal -> cloud checkpoints/segments
```

The server compares the independent paths before treating outage telemetry as gateway-verified evidence.

## Why this exists

`mosquitto.db` is a durable **delivery queue**, not an immutable ledger. It can keep uplinks through a bounded WAN outage, but by itself it does not prove that local gateway history was never rewritten.

The evidence path adds:

- gateway-local ordered observations;
- deterministic record and segment hashes;
- off-device checkpoints that anchor already-observed history;
- a read-only server collector for raw gateway MQTT events before application processing;
- post-outage reconciliation;
- a trusted decoder check outside Node-RED;
- explicit `pending`, `verified`, `evidence_gap`, and `integrity_failure` states;
- compact provenance that can later be sealed by OpenBao and attested through Fabric.

It does **not** make a software-only Raspberry Pi perfectly resistant to full root compromise during a fully disconnected interval. Keep that residual risk visible.

## Architecture

```text
                         PHYSICAL GATEWAY

LoRaWAN sensor
      |
      v
   RAK5146
      |
      v
Concentratord
   /       \
  /         \
 v           v
MQTT       integrity journal
Forwarder      |
  |            +-> sequence + PHYPayload/source evidence
  v            +-> record hash chain
Mosquitto      +-> segment chain
  |            +-> checkpoint/uploader
  |                     |
  +----------+----------+
             |
             v
                       SERVER / CLOUD

             +------------------------------+
             |                              |
             v                              v
      remote MQTT broker             evidence ingest API
             |                              |
      +------+-------+                      v
      |              |                checkpoint store
      v              v                      |
 ChirpStack     gateway-MQTT                 v
                evidence collector      segment store
      |              |                      |
      |              +----------+-----------+
      |                         |
      v                         v
application MQTT        gateway evidence verifier
      |                         |
      +-------------+-----------+
                    |
                    v
          trusted decoder / lineage
                    |
          +---------+----------+
          |                    |
          v                    v
       VERIFIED          GAP / FAILURE
          |
          v
 TimescaleDB + Fabric evidence gate
```

## Trust layers

```text
L1 RADIO
  RAK5146/Concentratord observed a frame.

L2 GATEWAY EVIDENCE
  Journal records what the evidence path observed.

L3 DELIVERY
  Independent server collector records what remote MQTT delivered.

L4 NETWORK
  ChirpStack processes the LoRaWAN frame/session.

L5 APPLICATION
  Trusted decoding is compared with Node-RED/TimescaleDB.

L6 EVIDENCE SEAL
  OpenBao signs verified canonical evidence.

L7 LEDGER
  Fabric preserves the final attestation.
```

A later layer cannot make an earlier false input true. Fabric can permanently preserve a bad value if the system seals it before source verification.

## Read in order

1. [01-evidence-contract-and-checkpoints.md](01-evidence-contract-and-checkpoints.md) — What the gateway records, what the server anchors, and the verification-state model.
2. [02-server-verifier-and-reconciliation.md](02-server-verifier-and-reconciliation.md) — Server components, database model, correlation, trusted decoding, and the Fabric evidence gate.
3. [03-testing-monitoring-and-limitations.md](03-testing-monitoring-and-limitations.md) — Outage, tamper, gap, monitoring, and residual-risk tests.
4. [04-service-architecture-and-runtime-contract.md](04-service-architecture-and-runtime-contract.md) — Canonical long-running service topology, ownership boundaries, exact end-to-end lifecycle, startup order, failure behavior, monitoring, and implementation sequence.

When another manual or diagram is unclear about **which service watches which boundary**, use Guide 4 as the canonical topology. The journal, uploader, evidence ingest, MQTT collector, verifier, trusted decoder, and Fabric Adapter are separate responsibilities; do not collapse them into one privileged watcher.

First complete the gateway-side manuals:

- [Gateway 4A. Configure the integrity journal](../../../gateway/setup/04a-configure-gateway-integrity-journal.md)
- [Gateway 6. Verify the complete gateway](../../../gateway/setup/06-verify-gateway-os.md)

## Initial implementation resource budget

These roles are **not part of the 5 GiB dissertation VM**. When reviewed implementations exist and are added to a larger full-stack environment, an initial low-rate test ceiling is:

```yaml
cpus: "${LAB_EVIDENCE_SERVICE_CPUS}"      # 0.20 CPU per role
mem_limit: "${LAB_EVIDENCE_SERVICE_MEM}" # 192 MiB per role
```

Three roles would therefore add up to **576 MiB RAM and 0.60 CPU**. Keep the roles separate because they have different trust responsibilities. Measure the actual implementations before deciding production sizing.

## Implementation-status rule

The repository currently documents the **contracts and acceptance behavior**. Do not claim that a `gateway-integrity-journal`, `gateway-evidence-ingestor`, `gateway-mqtt-evidence-collector`, or `gateway-evidence-verifier` image already exists unless a reviewed artifact is actually present and pinned.

A missing implementation is a deployment blocker. It is not permission to replace the design with an unreviewed production script.

## Core rule

```text
Mosquitto protects availability.
Journal protects historical consistency.
Cloud checkpoint limits rollback.
Verifier compares independent paths.
OpenBao seals verified evidence.
Fabric preserves the final attestation.
```
