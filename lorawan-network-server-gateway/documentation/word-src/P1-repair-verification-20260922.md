## P1 - Recorder correction check

The 90-second non-counted run manual-P1-rehearsal-20260922-132449 used a persistent managed test process instead of a one-shot command. The whole collection and Fabric settlement finished; the process exited 0.

| Check | Actual result |
|---|---|
| Full run duration | 90 seconds |
| Scheduled sensor attempts | 6 |
| ChirpStack accepted uplinks | 6 / 6 |
| Database-matched latency | 6 samples; mean 608.099 ms |
| Fabric outbox confirmed | 6 / 6 |
| ChirpStack deduplication errors | 0 on ULC-01; 0 on ULC-02 during this run |
| Supervisor | Seven PASS checks; no collector errors |
| Sealed evidence | 62 files verified; two summaries regenerated identically |
| Recorder exit | 0; RECORDED_UNCLASSIFIED |
| Formal P1 repetition | NOT COUNTED - 90-second rehearsal only |

The interrupted 30-minute P1 remains 119/120 (99.17%) and RECORDED_WITH_ERRORS. The persistent-process procedure fixes that capture-session failure. The isolated ChirpStack deduplication failure has not been repaired at server configuration level; six clean later readings do not prove that it cannot recur.
