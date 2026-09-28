# P2. Hyperledger Fabric Performance and Overhead

This is the counted Chapter 3 Fabric-performance experiment. It is separate from the P1 sensor baseline and from A2 endorsement-policy security testing.

## Research requirement

Chapter 3 requires four valid-transaction workloads:

```text
1 transaction / 15 seconds
1 transaction / second (1 TPS)
5 transactions / second (5 TPS)
10 transactions / second (10 TPS)
```

Run each workload for **5 minutes** and repeat it **3 times**. That gives **12 with-Fabric workload runs**. Return the Fabric network and client path to stable normal operation before every counted run.

Use valid records only. Each submitted test record must follow the same logical record contract as the commissioned integration: unique record identifier, timestamp, device/source identity, SHA-256 record hash, and required selected metadata. Use the commissioned chaincode and real commit/query path; do not replace the ledger with a mock for counted results.

## Pre-registered project choice for the chapter's underspecified comparison

Chapter 3 requires comparison of processing **with and without Fabric** but does not state the number of no-Fabric comparison runs. To prevent post-hoc selection, this project freezes the comparison as follows before counted P2 testing:

```text
Every with-Fabric workload run has one matched no-Fabric control.
Same target rate.
Same 5-minute duration.
Same repetition number.
Same payload/record-generation logic except Fabric submission is bypassed.
Same resource sampler interval.
12 with-Fabric + 12 no-Fabric control runs = 24 measured runs.
```

This 12-pair design is an implementation pre-registration, not a count supplied by Chapter 3. Preserve that distinction in Chapter IV.

To reduce order bias, alternate pair order by repetition:

```text
repetition 1: no-Fabric -> with-Fabric
repetition 2: with-Fabric -> no-Fabric
repetition 3: no-Fabric -> with-Fabric
```

Require at least 60 seconds of stable normal service/resource observation between runs and do not start the next run while the previous Fabric queue is still draining.

## What must be measured

For every with-Fabric run retain per transaction:

```text
workload rate label
repetition
unique record/trace ID
submission timestamp
commit timestamp
commit/validation result
Fabric transaction ID
transaction size bytes
block reference
block size bytes
```

Calculate:

```text
commit_latency_i = T_commit - T_submission
mean and sample SD commit latency
transaction throughput = valid committed transactions / measured seconds
transaction success rate = valid committed / submitted x 100
average transaction size bytes
average block size bytes
average and maximum CPU
average and maximum memory
```

For each matched with/without-Fabric pair calculate:

```text
additional latency = latency_with_fabric - latency_without_fabric
percentage latency increase = additional latency / latency_without_fabric x 100
CPU overhead = CPU_with_fabric - CPU_without_fabric
memory overhead = memory_with_fabric - memory_without_fabric
```

Keep raw CPU/memory samples, not only the aggregate. If network counters are available, preserve RX/TX bytes and derived Mbps as supporting load evidence.

## Validity rules

A run is INVALID when the requested workload was not actually generated for the full measured window, the Fabric path was not healthy before a with-Fabric run, resource capture is incomplete, submission or commit timestamps cannot be reconstructed, a required block/transaction evidence source is missing, or another experiment/attack/outage overlaps the run.

A failed Fabric transaction during an otherwise valid workload is **research data** and belongs in the success-rate denominator; do not mark the run INVALID merely to remove transaction failures.

Do not include unauthorized/policy-violation/replay traffic in P2. Those belong to security experiments.

## Synthetic/physical-data policy

P2 is a controlled Fabric workload test. Use **synthetic but schema-valid test records** with deterministic IDs and hashes so 1/5/10 TPS can be generated independently of the physical LoRaWAN sensor cadence. The 1-per-15-second condition may use the same record schema/cadence as the legitimate sensor path, but counted P2 transaction-load records remain explicitly labeled as P2 test fixtures unless they came from a real P1 sensor run. Never describe generated load records as physical sensor measurements.

## Required evidence bundle

Each pair must retain a manifest linking the run IDs and include workload-generator output, request/submission records, Fabric commit/validation evidence, ledger query evidence, transaction/block-size evidence, host/container resource samples, start/end UTC, environment/configuration hash, and SHA-256 evidence manifest.

Do not start counted P2 until the load generator can enforce the four rates and the recorder can export commit timestamp, transaction size, and block size reproducibly.
