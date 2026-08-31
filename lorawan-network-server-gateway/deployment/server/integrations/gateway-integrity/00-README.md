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
3. [03-testing-monitoring-and-limitations.md](03-testing-monitoring-and-limitations.md) — **Extended validation / Phase 15 reference** for outage, reboot, tamper, gap, and other fault cases. These tests are not all prerequisites for the first working evidence-service deployment.
4. [04-service-architecture-and-runtime-contract.md](04-service-architecture-and-runtime-contract.md) — Canonical long-running service topology, ownership boundaries, exact end-to-end lifecycle, startup order, failure behavior, monitoring, and implementation sequence.
5. [05-preimplementation-readiness-and-deployment-gate.md](05-preimplementation-readiness-and-deployment-gate.md) — Freeze replicated placement, shared-443/mTLS ingress, PKI, cross-host evidence storage, database/grants/worker leases, dual-broker collector identity, trusted decoder, v2 vector, observability, and the minimum proof required before the missing runtimes are activated.
6. [06-replicated-ha-deployment-journey.md](06-replicated-ha-deployment-journey.md) — **Minimum commissioning journey:** one guarded block per boundary, two-replica health, one representative functional path, evidence paths, PASS markers, and resume rules. Deep fault testing stays in Guide 3 / Phase 15.
7. [07-implementation-blueprint-and-ha-placement.md](07-implementation-blueprint-and-ha-placement.md) — Concrete software blueprint: Rust gateway journal/uploader, Go cloud services, raw-storage durability decision, exact HA host placement, verifier work discovery, service health contracts, source-tree shape, and implementation order.

When another manual or diagram is unclear about **which service watches which boundary**, use Guide 4 as the canonical topology. Use Guide 5 when the question is **what must be ready before those services can be safely installed**, Guide 6 for the guarded deployment journey, and Guide 7 when the question is **what code we are actually building and where its HA replicas will live**. The journal, uploader, evidence ingest, MQTT collector, verifier, trusted decoder, and Fabric Adapter are separate responsibilities; do not collapse them into one privileged watcher.

Current implementation order is **server/security-evidence first** while physical gateway access is unavailable:

1. build the Go cloud evidence services, trusted decoder, versioned migration, and storage interface from Guides 5-7;
2. build the Rust gateway journal/uploader against saved/pinned Concentratord event fixtures in parallel, but defer physical installation to hardware access;
3. minimally commission the cloud replicas using Guide 6;
4. later resume [Gateway 4A](../../../gateway/setup/04a-configure-gateway-integrity-journal.md) and [Gateway 6](../../../gateway/setup/06-verify-gateway-os.md) for the real gateway lineage;
5. close OpenBao audit before releasing any Fabric signing credential, not before the evidence verifier stack.

## Initial implementation resource budget

These roles are **not part of the 5 GiB dissertation VM**. When reviewed implementations exist and are added to a larger full-stack environment, an initial low-rate test ceiling is:

```yaml
cpus: "${LAB_EVIDENCE_SERVICE_CPUS}"      # 0.20 CPU per role
mem_limit: "${LAB_EVIDENCE_SERVICE_MEM}" # 192 MiB per role
```

One instance of each of the three server roles would add up to **576 MiB RAM and 0.60 CPU**, but the replicated cloud target uses **two instances of each role**. At the same initial ceiling that is **1152 MiB RAM and 1.20 CPU across the three-host cluster**, balanced at roughly **384 MiB / 0.40 CPU of evidence-service budget per host** by the current placement candidate. These are only starting ceilings; measure the reviewed implementations before freezing placement or production sizing.

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
