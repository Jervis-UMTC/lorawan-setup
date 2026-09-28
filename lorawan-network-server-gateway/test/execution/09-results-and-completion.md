# Execution 9. Results, Calculations, and Completion
> **Reference procedure only.** Executable operator commands are published only in `chapters/lorawan_research_test_manual_final.md` after live qualification. The fenced snippets below are preserved as implementation/reference text and must not be copied as current commands.

Use this page after the counted experiments. Do not calculate final percentages from screenshots.

## Before calculating anything

Create a trial/run inventory first. Every attempted ID must be classified as:

```text
PASS
FAIL
INVALID
BLOCKED (only when a required external dependency such as approved Fabric identities was unavailable)
```

Only valid counted attempts belong in metric denominators. Do not silently delete FAIL results. INVALID attempts stay in the audit trail but are rerun with new IDs and excluded from the counted denominator.

## 1. Required completed dataset

This checklist follows the new Zacarias Chapter 3 testing authority. Do not declare the research-test phase complete using the older, shorter inventory.

```text
[ ] P1: 3 normal-operation runs x 30 minutes
[ ] P1: formal PDR uses unique ChirpStack-accepted EMU-01 uplinks / successful SENSOR_TX transmissions; exact source-to-database delivery is retained separately
[ ] P2: 12 Fabric performance workload runs (4 workloads x 3 repetitions, 5 minutes each)
[ ] P2: 12 matched no-Fabric controls completed under the pre-registered paired design (project implementation choice; Chapter 3 does not state this comparison-run count)
[ ] P2: paired with-vs-without-Fabric overhead evidence retained
[ ] R1: 3 external-Internet interruption/recovery runs x 2 hours (30/60/30)
[ ] R2: 10 normal Fabric-consistency controls + 10 Fabric-unavailable pending records + reconciliation of those same 10
[ ] A1: 90 authentication/access-control attempts
[ ] A2: 30 endorsement-policy attempts (10 normal + 10 violation + 10 recovery)
[ ] S1: 40 counted LoRaWAN replay/spoofing attempts
[ ] S2: application-layer duplicate/replay requirement formally resolved (procedure/count/metrics/pass rule approved) OR methodology explicitly amended to remove it; no invented counted result
[ ] I1/I2: 40 application-layer/post-storage integrity attempts
[ ] I3: 10 valid baseline anchors + 10 duplicate attempts + 10 conflicting overwrite attempts
[ ] T1/T2: 20 traceability trials covering 60 records
[ ] F1/F2: 18 flooding runs + 18 five-minute recovery periods
[ ] raw logs retained
[ ] database exports retained
[ ] Fabric transaction/query evidence retained
[ ] resource and network-bandwidth samples retained
[ ] numerator/denominator retained for every reported rate
[ ] test-data provenance frozen per experiment (synthetic/known-value fixture vs real physical reading); no silent substitution or relabeling
[ ] every synthetic/load/security fixture is explicitly labeled so generated records cannot be reported as physical agricultural measurements
[ ] EMU-01 source logs + pinned RAK4631 firmware/payload baseline retained
[ ] SEC-02 raw-RF/security-node baseline retained without legitimate keys
[ ] invalid/rerun trials clearly marked and not double-counted
```

## 2. Build the inclusion manifest before summaries

Create `summaries/inclusion-manifest.csv` with at least:

```text
experiment
run_or_trial_id
status
included_in_metric
reason
raw_evidence_path
```

Review the manifest against the required counts before calculating percentages.

## 3. Keep raw and calculated data separate

Recommended structure:

```text
chapter4-results/
  baseline/
  authentication/
  replay-spoofing/
  integrity/
  traceability/
  flooding/
  resilience/
  summaries/
```

Do not edit raw CSV/log files to make a result cleaner. Create corrected/derived files in `summaries/` and preserve the original evidence.

## 4. Normal-operation calculations

### Packet-delivery rate

```text
PDR (%) = unique received legitimate EMU-01 packets / scheduled EMU-01 transmission attempts x 100
```

### End-to-end latency

For each valid matched reading:

```text
L_i = storage timestamp - trustworthy/correlated EMU-01 transmission timestamp
```

Report mean, standard deviation, minimum, and maximum.

### Fabric transaction success rate

```text
TSR (%) = valid committed transactions / submitted transactions x 100
```

A transaction ID without valid commit status is not committed.

### Throughput

```text
throughput = unique legitimate records successfully stored / observation minutes
```

### Resource utilization

Report mean and maximum CPU/memory for the server testbed. Report gateway Raspberry Pi resource use separately when collected. Do not merge them into one percentage.

## 5. Fabric performance and overhead summary

For each of the four authoritative workloads (`1 tx/15 s`, `1 TPS`, `5 TPS`, `10 TPS`) aggregate the three five-minute repetitions and report:

```text
mean/SD Fabric commit latency
committed transaction throughput (TPS)
transaction success rate
average transaction size (bytes)
average block size (bytes)
mean/max CPU
mean/max memory
```

For paired processing with and without Fabric submission also report:

```text
additional latency = latency_with_fabric - latency_without_fabric
percentage latency increase = additional_latency / latency_without_fabric x 100
CPU overhead = CPU_with_fabric - CPU_without_fabric
memory overhead = memory_with_fabric - memory_without_fabric
```

Retain the individual transaction submission/commit timestamps, valid-commit result, transaction size, block reference/size, and raw resource samples used by each aggregate.

## 6. Authentication/access-control summary

For every condition calculate:

```text
authorized success rate
unauthorized rejection rate
false acceptance count
false rejection count
correct-decision rate
mean/SD response time
unauthorized state-change count
```

Main secure result:

```text
false acceptance = 0
unauthorized state change = 0
```

These results feed the authentication/access-control results table.

## 7. Fabric endorsement-policy summary

Calculate separately for normal, policy-violation, and post-restoration conditions:

```text
endorsement-policy enforcement rate
valid transaction success rate
post-restoration recovery transaction success rate
unauthorized state-change count
```

Required secure result:

```text
policy-violation enforcement rate = 100%
unauthorized state changes = 0
valid transactions resume after required endorsement is restored
```

Keep this distinct from Fabric identity authorization: the identity test asks whether an identity may submit; the endorsement test asks whether a transaction lacking a required endorsement can create valid ledger state.

## 8. Replay/spoofing summary

Calculate separately:

```text
replay rejection rate
spoofing rejection rate
false acceptance count
false rejection count
unauthorized propagation rate
mean/SD decision time when measurable
```

Only SEC-02 attack attempts whose RF reception is proven by RAK5146 belong in the denominator. A security-node TX-success message alone is insufficient.

These results feed the replay/spoofing results table.

## 9. Integrity summary

Calculate separately for application-layer and post-storage tests:

```text
integrity verification rate
tamper detection rate
false positives
false negatives
unauthorized storage
mean/SD verification time
```

Main secure result:

```text
false negatives = 0
unauthorized application-layer altered storage = 0
```

Keep the experimental Node-RED control hash distinct from the production Fabric adapter/OpenBao evidence digest in the discussion.

For the separate blockchain-layer duplicate/overwrite test also calculate:

```text
duplicate-rejection rate
overwrite-rejection rate
original-hash preservation rate
unauthorized state-change count
```

The ten established baseline anchors are the reference state; prove after every duplicate/overwrite attempt that the original hash for the corresponding trace ID remains unchanged.

These results feed the integrity results table.

## 10. Traceability summary

Calculate:

```text
individual retrieval success rate
record completeness rate
database-Fabric linkage rate
chronological-order accuracy
missing-record count
duplicate-record count
mean/SD retrieval time
mean/SD history reconstruction time
```

These results feed the traceability results table.

## 11. Flooding summary

For each of the six traffic conditions aggregate the three runs:

```text
legitimate-message delivery
invalid-traffic rejection
mean/SD legitimate latency
mean/max CPU
mean/max memory
service availability
unauthorized records
mean/SD recovery time
```

Keep MQTT connection flooding and invalid application-message flooding separate.

These results feed the flooding results table.

## 12. External-Internet interruption/recovery summary

For each of the three R1 runs summarize the three periods separately:

```text
30-minute normal period
60-minute external-Internet interruption
30-minute recovery period
```

Calculate/report:

```text
local service availability
data-delivery rate
stored/expected readings
data-loss count
duplicate-record count
database-blockchain consistency rate
mean/SD end-to-end latency
recovery time
chronological accuracy
```

This is the Internet-connectivity experiment defined by Zacarias Chapter 3. Do not replace it with a Fabric-only outage. Use the live commissioned topology to implement the external-Internet interruption safely while preserving the intended independent variable.

## 13. Fabric unavailability / consistency / reconciliation summary

For R2 summarize the ten normal controls, ten Fabric-unavailable records, and reconciliation of those same ten pending records. Report:

```text
pending-record identification rate
recovery success rate
post-recovery hash-consistency rate
false-verification count
orphaned database-record count
missing blockchain-record count
duplicate blockchain-record count
conflicting-hash count
failed-reconciliation count
records remaining pending after recovery
recovery time
mean per-record reconciliation time when measured
```

Required research criteria are 100% pending identification, zero false verifications, 100% valid-pending recovery, 100% post-recovery hash consistency, and zero missing/duplicate valid integrity anchors.

Do not label queued/local outbox state as a valid Fabric commitment; require confirmed ledger evidence for `VERIFIED`.

## 14. Standard deviation

Use the same sample/population convention consistently throughout the dissertation and state it in the methodology. Do not switch conventions between tables.

For repeated experimental observations, preserve the individual values used to calculate the reported mean and standard deviation.

## 15. Final evidence audit

For every table value, first be able to answer:

```text
Which EMU-01 test_sequence values were expected in this window?
Which RAK4631 firmware/payload version produced them?
```

Then also answer:

```text
Which raw file produced this number?
Which trials were included?
Which trials were rerun or invalidated?
Which event/frame/transaction IDs support it?
Was the configuration unchanged within the repetition group?
```

If one of those cannot be answered, reconstruct the result from raw logs before writing the final table.

## 16. Back up the completed dataset

Create a protected archive and copy it off the lab VM:

```text
cd "$HOME"
tar -czf chapter4-results.tar.gz chapter4-results
sha256sum chapter4-results.tar.gz > chapter4-results.tar.gz.sha256
```

Store the archive and checksum outside the VM.

Do not include live private keys, device root keys, Fabric client keys, OpenBao recovery shares, passwords, or tokens in the results archive.

## Completion condition

The dissertation testing phase is complete only when all required counts are met, every summary can be traced to raw evidence, and failed/invalid trials are reported rather than silently discarded.
