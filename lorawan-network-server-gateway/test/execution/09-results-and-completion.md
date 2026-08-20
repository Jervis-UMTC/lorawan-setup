# Execution 9. Results, Calculations, and Completion

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

```text
[ ] 3 normal-operation runs x 30 minutes
[ ] 90 authentication/access-control attempts
[ ] 40 counted replay/spoofing attempts
[ ] 40 data-integrity attempts
[ ] 20 traceability trials covering 60 records
[ ] 18 flooding runs + 18 recovery periods
[ ] 3 resilience runs x 2 hours
[ ] raw logs retained
[ ] database exports retained
[ ] Fabric transaction evidence retained
[ ] resource samples retained
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

## 5. Authentication/access-control summary

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

These results feed Chapter IV Table 12.

## 6. Replay/spoofing summary

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

These results feed Table 13.

## 7. Integrity summary

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

These results feed Table 14.

## 8. Traceability summary

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

These results feed Table 15.

## 9. Flooding summary

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

These results feed Table 16.

## 10. Resilience summary

Across the three runs summarize each period separately:

```text
normal before interruption
Internet interruption
recovery after reconnection
```

Calculate:

```text
stored/expected readings
missing records
duplicate records
local service availability
latency
chronological accuracy
recovery time
Fabric work queued while unreachable
Fabric work committed after recovery
```

Because the current Fabric network is external, do not label queued outbox jobs as successful Fabric commits during Internet loss.

These results feed Table 17, with the actual architecture behavior explained in the discussion.

## 11. Standard deviation

Use the same sample/population convention consistently throughout the dissertation and state it in the methodology. Do not switch conventions between tables.

For repeated experimental observations, preserve the individual values used to calculate the reported mean and standard deviation.

## 12. Final evidence audit

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

## 13. Back up the completed dataset

Create a protected archive and copy it off the lab VM:

```bash
cd "$HOME"
tar -czf chapter4-results.tar.gz chapter4-results
sha256sum chapter4-results.tar.gz > chapter4-results.tar.gz.sha256
```

Store the archive and checksum outside the VM.

Do not include live private keys, device root keys, Fabric client keys, OpenBao recovery shares, passwords, or tokens in the results archive.

## Completion condition

The dissertation testing phase is complete only when all required counts are met, every summary can be traced to raw evidence, and failed/invalid trials are reported rather than silently discarded.
