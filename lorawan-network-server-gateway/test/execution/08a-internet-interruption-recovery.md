# R1. External-Internet Interruption and Recovery

This is the Chapter 3 Internet-connectivity resilience experiment. It is **not** the same as R2 Fabric-only unavailability.

The chapter's old architecture assumes more services are local than the commissioned system actually uses. Preserve the experimental independent variable and metrics, but implement the interruption against the verified current topology and report actual behavior truthfully.

## Required design

Run **3 repetitions**, each exactly:

```text
30 minutes normal operation
60 minutes external-Internet interruption
30 minutes recovery after connectivity restoration
Total = 120 minutes per run
```

Keep the counted EMU01 15-second source cadence unchanged for the entire run. Do not stop source/resource capture between phases.

## Commissioned-system interpretation

The research question is whether essential monitoring data remain available/preserved during a deliberate external-Internet interruption and whether the system returns to a consistent state afterward. The exact network rule used must be rehearsed and frozen before Run 1.

Because current Fabric is an external dependency, a Fabric outbox row that is merely `PENDING` during an outage is **not** a committed blockchain record. Report this difference from the stale chapter architecture instead of pretending local Fabric verification occurred.

Do not substitute R2's Fabric-endpoint-only block for R1. R1 must create the selected external-Internet loss boundary while preserving power and avoiding unrelated component failures.

## Before each run

Prove and archive normal state: EMU01 counted profile, Gateway/LTE path, cloud ingress, ChirpStack, database, evidence services, Fabric path, clock gate, resource recorder, and current route/connectivity state. Capture the exact interruption rule/script hash.

A full-stack GO is required before R1. If the sensor/gateway is intentionally offline, R1 is BLOCKED and must not be simulated from server-only data.

## Phase evidence

For each phase retain source sequences, LoRaWAN frame counters, gateway/ChirpStack evidence, database rows, Fabric/outbox state, service availability, CPU/memory/network counters, UTC phase markers, and recovery transitions.

Calculate per phase/run:

```text
local service availability
data-delivery rate / stored vs expected readings
missing-record count
duplicate-record count
chronological-order accuracy
database-blockchain consistency rate
end-to-end latency
recovery time
```

Report frequencies/percentages for availability, delivery, missing/duplicate/order/consistency and mean + sample SD for latency and recovery time where Chapter 3 requires repeated numeric observations.

## Recovery boundary

Record the exact connectivity-restoration UTC. Recovery time ends only when the defined external connectivity/service state has returned to the pre-outage normal condition. Separately record when queued Fabric work finishes reconciliation; do not conflate Internet reachability recovery with R2-style per-record Fabric reconciliation.

## Validity rules

A run is INVALID if the intended external-Internet condition was not proven for the full 60 minutes, EMU01/source evidence is lost, the interruption also removes power or creates an unrelated hardware failure, phase timestamps cannot be reconstructed, or the implementation changes between repetitions.

Ordinary packet loss or a valid service degradation caused by the intended outage is research data, not grounds to discard the run.
