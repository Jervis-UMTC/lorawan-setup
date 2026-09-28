# R2. Fabric Unavailability, Database-Blockchain Consistency, and Reconciliation

This is a separate Chapter 3 resilience experiment from R1 Internet interruption. The independent variable is Fabric availability while the upstream record-processing/database path remains operational.

## Required design

Use controlled test records in a dedicated namespace:

```text
Stage A: 10 normal control records while Fabric is available
Stage B: 10 additional records while Fabric is deliberately unavailable
Stage C: restore Fabric and reconcile those SAME 10 pending records
```

Do not generate a replacement set for Stage C. The research claim depends on recovery of the same records that were created during unavailability.

## State model

Use explicit states in evidence:

```text
PENDING  = complete database record exists but valid Fabric confirmation is not yet available
VERIFIED = corresponding Fabric record is confirmed and hash/query evidence matches
FAILED   = reconciliation was attempted but did not reach valid verified state
```

A transaction ID without valid commit/query evidence is not `VERIFIED`.

## Stage A — normal controls

For each of ten records save the database row/hash, Fabric submission and valid commit evidence, transaction ID, and ledger query result. Require database↔Fabric hash agreement before proceeding.

## Stage B — Fabric unavailable

Apply only the pre-rehearsed Fabric-unavailability condition. Keep the database/application path healthy. Create exactly ten new valid records and prove that each complete database record remains present while its Fabric status is `PENDING` rather than falsely `VERIFIED`.

Save proof of the Fabric-unavailable condition and the ten pending trace IDs/hashes.

## Stage C — reconciliation

After restoring Fabric:

1. take the exact list of ten Stage-B pending trace IDs;
2. **query Fabric for each trace ID before any resubmission/reconciliation action**;
3. if the expected anchor already exists and matches, record that fact and do not create a duplicate;
4. otherwise allow the commissioned reconciliation path to submit/reconcile that same pending record;
5. require valid commit plus post-recovery ledger query/hash match;
6. continue until every recoverable Stage-B record is VERIFIED or explicitly FAILED.

This query-before-resubmission rule is mandatory evidence against duplicate blockchain entries.

## Metrics

Calculate:

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
records remaining PENDING after recovery
recovery time
mean per-record reconciliation time when measured
```

Required Chapter 3 criteria:

```text
100% pending-record identification
0 false verifications
100% recovery of valid pending records
100% post-recovery hash consistency
0 missing/duplicate valid integrity anchors
```

## Validity rules

R2 is INVALID if upstream database ingestion fails during Stage B, Fabric unavailability is not proven, the ten Stage-B trace IDs cannot be frozen before recovery, Stage C substitutes different records, query-before-resubmission evidence is missing, or an unrelated outage prevents classification.

A valid pending record that fails to reconcile is FAIL research data, not INVALID.
