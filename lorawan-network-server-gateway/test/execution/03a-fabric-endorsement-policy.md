# A2. Fabric Endorsement-Policy Enforcement

This is the counted Chapter 3 endorsement-policy experiment. It is separate from A1 Fabric identity/authorization: A1 asks whether an identity is allowed to act; A2 asks whether a transaction that lacks required endorsement can alter valid ledger state.

## Required design

Run exactly three conditions, **10 attempts each**:

```text
A2-NORMAL:       10 valid transactions with the required endorsement policy satisfied
A2-VIOLATION:    10 otherwise valid transactions with a required endorsement deliberately unavailable/missing
A2-RESTORED:     10 valid transactions after the required endorsement path is restored
Total:           30 attempts
```

Use a Fabric-team-approved policy/fixture. Do not weaken production policy, delete identities, corrupt channel configuration, or improvise a topology change merely to manufacture a failure.

## Fixture rules

Use unique synthetic test keys/trace IDs that cannot collide with real sensor anchors. The record itself must be schema-valid and the submitting identity must be authorized. The independent variable for `A2-VIOLATION` is **endorsement-policy satisfaction only**.

Before counted testing archive:

```text
channel/chaincode identity
policy definition or approved policy-test description
which endorsement is required
how the violation is induced
how the endorsement path is restored
client identity used
fixture namespace/prefix
```

If the approved Fabric environment cannot provide a controlled missing-endorsement condition, classify A2 `BLOCKED`, not PASS.

## Trial evidence

For every attempt save:

```text
trial ID and condition
unique ledger key/trace ID
pre-attempt ledger query result
submission/proposal timestamp
endorsement/proposal response
transaction ID if one is produced
commit/validation status if applicable
post-attempt ledger query result
response time
```

For `A2-VIOLATION`, prove after **every attempt** that the intended world-state key was not created or changed. A client-side error message alone is insufficient evidence of policy enforcement.

For `A2-NORMAL` and `A2-RESTORED`, require a valid commit plus a successful read-back of the expected state.

## Calculations

```text
normal valid-transaction success rate
endorsement-policy enforcement rate = correctly rejected violation attempts / valid violation attempts x 100
post-restoration transaction success rate
unauthorized state-change count
mean and sample SD response time by condition
```

Required Chapter 3 security result:

```text
endorsement-policy enforcement = 100%
unauthorized state changes = 0
valid transactions resume after endorsement is restored
```

Do not hide a valid unexpected acceptance. It is FAIL research data and stays in the denominator.

## Validity rules

A violation trial is INVALID if the missing-endorsement condition was not proven, the submitted record was malformed for another reason, the client identity was unauthorized for an unrelated reason, ledger pre/post state was not captured, or the Fabric service failed for an unrelated outage.

A normal/restored trial is INVALID if the required endorsement path was not actually healthy before submission. A valid transaction that is rejected unexpectedly is FAIL, not INVALID.
