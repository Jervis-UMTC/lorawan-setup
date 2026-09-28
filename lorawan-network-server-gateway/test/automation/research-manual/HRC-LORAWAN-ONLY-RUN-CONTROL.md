# LoRaWAN-controlled HRC Fabric research tests

The **LoRaWAN team is the sole research-test operator**. All PRE/P1 and joint P2, R2, A1, A2, I1, I2, I3, T1, and T2 runs must be initiated and supervised from the LoRaWAN project using the **jervis-hijo connector**. The HRC Fabric hosts run Fabric components and the existing HRC verification/export commands when invoked by this controller; no separately timed HRC-team test run, independently invented manifest, or manual copy-and-paste by another team may be counted as a joint experiment.

## Single run sequence

1. LoRaWAN preflight and test-specific readiness must pass. A synthetic/code-only PASS is not permission for a counted test; PRE/P1 readiness does not release P2/R2/A1/A2/I1/I2/I3/T1/T2.
2. The LoRaWAN test harness freezes one unique run ID, test ID, repetition, phase/trial identities, time window, expected records, exact accepted payload bytes, and each exact payload SHA-256. Set source namespace to `lorawan-gateway-evidence`. HRC manifest format: `HRC-FABRIC-TEST-MANIFEST-001`; confirm against the actual HRC parser before execution.
3. Via **jervis-hijo only**, transfer identical unmodified manifest bytes to the existing HRC incoming directory. Keep an independent LoRa-side SHA-256; compare with the actual HRC-side SHA-256. Abort if either differs, if the file changes or a run ID is reused.
4. Via the same jervis-hijo-controlled session, run test-specific HRC preflight, manifest validation and the existing HRC test runner on its authorized host. No ungoverned failover, arbitrary path outage, fabricated unauthorized identity, endorsement-policy weakening, or unsynchronized record injection. All fault, security and load conditions must be prescribed by the approved LoRa test harness.
5. The LoRaWAN controller observes source/gateway/ChirpStack/database/Fabric boundaries and original UTC timestamps; retains authentic experiment screenshots and raw outputs; runs HRC disarm, FINAL export, checksum verification and per-run analysis through jervis-hijo; restores the dedicated path after R2.
6. Join source and HRC evidence on `run_id + trial_id + source_record_id + payload_sha256`. Confirm that `payload_sha256 = SHA-256(exact accepted payload bytes)`, without reserialization. A committed Fabric result requires **authoritative validation code 0, transaction identity and matching exact-payload digest**; submit acknowledgement or TxID alone does not suffice. Preserve `UNKNOWN` and distinguish infrastructure failure from tampering.
7. Only accept counted results when **both** the LoRaWAN recorder and HRC FINAL export are clean, verified and deterministically joined. Any error, missing comparator, failed run or partial evidence remains recorded and non-counted. The interrupted 2026-09-22 P1 run has authentic metrics but status `RECORDED_WITH_ERRORS`; it is not a clean formal repetition.

## Test boundaries

- **P2:** four 300-second loads (1 record/15 s, 1/5/10 TPS), three repetitions; preserve matched no-Fabric controls for overhead; no overhead estimate when absent.
- **R2:** normal 10 / unavailable 10 / reconcile the same 10; touch only the dedicated HRC Gateway path, never peers/orderers/chaincode/K3s. Preserve the original logical identities.
- **A1:** Fabric tests are only the Fabric slice of the full 90 LoRaWAN/MQTT/Fabric attempts; separately provisioned negative identity is required.
- **A2:** the existing endorsement policy stays unchanged; negative trial must be an actual missing-required-endorsement condition.
- **I1/I2/I3:** LoRaWAN owns tamper fixtures and exact byte variants; same-source/record/digest is an idempotent retry, different digest is a conflict, and I2 must compare the production evidence schema against its original immutable anchor.
- **T1/T2:** 10 individual records and 10 disjoint five-record sequences; link original source, database and HRC evidence without substituting records.
- **S2** is not supported by the HRC manifest parser described in the provided HRC manual; it remains a LoRa-side methodology issue.

**HRC manual reference:** `HRC_Fabric_Test_Manual.pdf`, especially pp. 3–11, 14–16, 19–22, 24–25, 28, 31–38, 40–44. Its named “Fabric operator” steps become actions executed remotely **by the LoRaWAN operator through jervis-hijo**; HRC's service-level validation, local security safeguards and protected paths remain intact.

**Access gate:** Do not schedule a counted joint test until jervis-hijo can reach the authorized HRC execution host and prove the required preflight, manifest checksum, clean export and read-only artifact retrieval. A reachability failure is not a test outcome and must not be bypassed by asking the HRC team to start an unsynchronized test.
