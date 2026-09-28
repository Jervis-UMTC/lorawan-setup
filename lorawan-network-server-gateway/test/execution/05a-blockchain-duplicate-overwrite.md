# I3. Blockchain Duplicate and Unauthorized-Overwrite Integrity

This is the separate blockchain-layer integrity experiment required by the new Chapter 3. Do not merge it into the 40 I1/I2 application/post-storage attempts.

## Required design

Establish **10 valid baseline anchors** in Fabric. Each anchor must have a unique trace/record ID and its original SHA-256 record hash preserved in the evidence manifest.

Then perform:

```text
10 duplicate attempts:
  same 10 trace IDs
  same original hashes

10 conflicting overwrite attempts:
  same 10 trace IDs
  deliberately different hashes
```

The ten baseline anchors are the reference state used by both attack phases. State clearly in Chapter IV that the chapter does not unambiguously define whether those baseline-anchor creations are counted as attack trials; report them separately as 10 baseline fixtures plus 20 mutation attempts.

## Fixture policy

Use synthetic, deterministic integrity-test records in a dedicated namespace. Never deliberately overwrite a real agricultural record or destroy the only copy of a research anchor. Record the exact canonical input used to calculate each original and conflicting hash.

## Baseline phase

For each of the 10 trace IDs:

1. prove the key is absent or reserved for this fixture;
2. submit the valid baseline anchor;
3. require valid Fabric commit status;
4. query the ledger;
5. save the exact original hash and transaction evidence.

Do not begin mutation attempts until all ten baseline anchors have been independently read back.

## Duplicate phase

For each baseline anchor, submit the same trace ID with the **same hash**. Immediately query the original anchor after each attempt.

Save request, response, transaction/validation result if produced, and post-attempt state. The critical evidence is whether the existing valid state changed, multiplied, or otherwise became inconsistent.

## Conflicting-overwrite phase

For each baseline anchor, submit the same trace ID with a **different deliberate hash**. Immediately query the original anchor after each attempt and compare it byte-for-byte with the baseline evidence.

A client rejection message without ledger-state verification is insufficient.

## Calculations

```text
duplicate-rejection rate
overwrite-rejection rate
original-hash preservation rate
unauthorized state-change count
```

For each trace ID preserve:

```text
baseline hash
attempted hash
pre-attempt queried hash
post-attempt queried hash
request result
transaction ID / validation code when applicable
state changed? yes/no
```

Required secure behavior is that a duplicate/conflicting mutation cannot replace the original valid anchor and the original hash remains preserved for every tested trace ID.

## Validity rules

An attempt is INVALID if the baseline anchor cannot be proven first, the wrong trace ID is submitted, the intended same/different hash condition is not achieved, the ledger cannot be queried afterward, or an unrelated Fabric outage prevents observing the decision.

An unexpected accepted mutation with proven state change is FAIL and must remain in the research data.
