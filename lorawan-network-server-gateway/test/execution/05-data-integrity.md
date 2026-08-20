# Execution 5. Data Integrity

This test has **40 counted trials**:

```text
Application-layer control:       10 unchanged
Application-layer alteration:    10 altered before storage
Post-storage control:            10 unchanged stored records
Post-storage tampering:          10 modified stored records
Total:                           40
```

Use only dedicated test records. Take a readable TimescaleDB backup first.

## What this test proves

```text
Part A -> can a controlled application-layer change be detected before the altered reading becomes valid stored telemetry?
Part B -> if a stored source row is changed later, does reconstruction from that changed row disagree with the already sealed Fabric evidence?
```

The temporary Node-RED test hash used in Part A and the production Fabric/OpenBao evidence digest used in Part B are separate mechanisms. Keep them separate in the result discussion.

## Before Part A

1. Complete the Execution 01 short preflight.
2. Create and verify the safety database backup from Execution 01 Section 18.
3. Export/save the current known-good Node-RED test flow before editing it.
4. Record that flow revision/hash in the integrity result folder.
5. Confirm one ordinary EMU-01 event stores normally before enabling the temporary hash gate.
6. Confirm the quarantine path cannot reach TimescaleDB or the Fabric outbox.

## Why a test-only Node-RED hash gate is used

The current production architecture does **not** make Node-RED the evidence signer. The Fabric adapter owns RFC 8785 canonicalization, SHA-256, OpenBao verification, and Fabric submission.

The dissertation application-layer experiment, however, requires an initial hash and a second hash around a controlled Node-RED alteration. Implement that as a **temporary test gate only**. It must not replace the normal Fabric-adapter evidence path.

## Part A - Application-layer alteration

### Step A1 - Expose Node.js crypto to test Function nodes

In the Node-RED test configuration, add the Node.js `crypto` module to `functionGlobalContext` using the supported Node-RED settings mechanism:

```javascript
functionGlobalContext: {
    crypto: require('crypto')
}
```

Restart Node-RED and verify a test Function node can obtain it with:

```javascript
const crypto = global.get('crypto');
if (!crypto) {
    node.error('crypto module unavailable');
    return null;
}
return msg;
```

Do not enable arbitrary external modules or `exec` access just for this test.

### Step A2 - Add the integrity gate before the normal storage function

Create two small test controls so the operator does not edit code between trials:

```text
ARM ALTERATION -> flow.set('integrity_alter_next', true)
DISARM          -> flow.set('integrity_alter_next', false)
```

The alteration flag must automatically return to `false` after one altered message so one click cannot unintentionally alter several readings.

Apply the gate **only** to `<TEST_DEV_EUI>`.

Use two outputs:

```text
output 1 -> normal validated telemetry/storage flow
output 2 -> quarantine/debug/file evidence only
```

For foolproof evidence capture, connect the quarantine output to a test-only debug/file path that records at least `test_id`, `test_sequence`, initial hash, final hash, and UTC observation time. Do not connect this output to SQL or Fabric nodes.

The gate must create the same fixed test record before and after the optional mutation:

```text
test_id
dev_eui
f_cnt
sensor_type
sensor_value
unit
event_time
```

For the RAK4631 physical-sensor payload v2 defined in [Sensor Preparation](../preparation/sensor/01-configure-rak4631-emulators.md), use compatibility field `temperature_c` (mapped from RAK1906 `environment_temperature_c`) and unit `Cel` for all 20 application-layer trials. Keep the EMU-01 firmware, sensor map, payload contract, and ChirpStack decoder frozen throughout this experiment.

Conceptual Function-node logic:

```javascript
const crypto = global.get('crypto');
const p = msg.payload || {};
const d = p.object || {};
const devEui = String((p.deviceInfo || {}).devEui || '').toLowerCase();

if (devEui !== '<TEST_DEV_EUI>') return [msg, null];

const record = {
    test_id: String(p.deduplicationId || `${devEui}|${p.fCnt}|${p.time}`),
    dev_eui: devEui,
    f_cnt: Number(p.fCnt),
    sensor_type: 'temperature',
    sensor_value: Number(d.temperature_c),
    unit: 'Cel',
    event_time: String(p.time)
};

const initialBytes = JSON.stringify(record);
const initialHash = crypto.createHash('sha256').update(initialBytes, 'utf8').digest('hex');

if (flow.get('integrity_alter_next') === true) {
    d.temperature_c = Number(d.temperature_c) + 10;
    flow.set('integrity_alter_next', false);
}

const finalRecord = {
    ...record,
    sensor_value: Number(d.temperature_c)
};
const finalBytes = JSON.stringify(finalRecord);
const finalHash = crypto.createHash('sha256').update(finalBytes, 'utf8').digest('hex');

msg.integrityTest = {
    test_id: record.test_id,
    initial_hash: initialHash,
    final_hash: finalHash,
    match: initialHash === finalHash
};

if (initialHash !== finalHash) return [null, msg];
return [msg, null];
```

This hash is the **experimental control hash**, not the production Fabric evidence seal.

### Step A3 - Dry-run the gate before counted trials

Perform two **uncounted** checks:

1. DISARM -> the next EMU-01 reading must have matching hashes and store normally.
2. ARM ALTERATION -> the next EMU-01 reading must have different hashes, go to quarantine, and create no valid DB/Fabric row.

If either dry run fails, repair the temporary flow before starting counted trials.

### Step A4 - Run 10 unchanged controls

For each control:

1. set `flow.integrity_alter_next = false` through a dedicated test Inject node;
2. send one legitimate physical-sensor reading from EMU-01 and record its deterministic `test_sequence`;
3. record the initial and final test hashes;
4. verify they match;
5. verify the record proceeds to normal TimescaleDB storage;
6. when selected, verify the normal Fabric path can confirm it.

Expected: hash match and valid storage.

### Step A5 - Run 10 controlled alterations

For each trial:

1. arm the test flag `flow.integrity_alter_next = true`;
2. send one legitimate physical-sensor EMU-01 reading and record its deterministic `test_sequence`;
3. allow the gate to change only the chosen sensor value after the initial hash;
4. record initial and final hashes;
5. verify they differ;
6. verify the message exits through the quarantine output;
7. verify no valid `telemetry.uplinks` row or Fabric outbox transaction is created for that test ID.

Expected: hash mismatch, quarantine, no valid storage/Fabric submission.

After all 20 counted Part A trials:

1. export the final test flow as evidence;
2. disable/remove the temporary hash gate and ARM/DISARM controls;
3. restore the normal flow from the saved known-good copy;
4. deploy the restored flow;
5. send one normal EMU-01 reading and confirm storage/Fabric operation is normal again.

---

## Part B - Post-storage database tampering

### Step B1 - Create 10 valid confirmed test records

Generate 10 legitimate EMU-01 physical-sensor readings, each with a recorded deterministic `test_sequence`, that:

```text
exist in telemetry.uplinks
have matching outbox rows
have status = confirmed
have Fabric transaction IDs
```

Save their `event_key`, `time`, `payload_json`, convenience value being tested, `canonical_json`, `digest_sha256`, and `fabric_tx_id`.

Create a protected restore table for only these test rows:

```sql
DROP TABLE IF EXISTS telemetry.integrity_restore;
CREATE TABLE telemetry.integrity_restore AS
SELECT event_key,time,payload_json,temperature_c
FROM telemetry.uplinks
WHERE event_key IN (<TEN_QUOTED_TEST_EVENT_KEYS>);
```

Drop this table after restoration and final verification.

### Step B2 - Run 10 unchanged post-storage controls

For each confirmed event:

1. export its stored `canonical_json` and digest;
2. run [Fabric Test 4](../../deployment/server/fabric-attestation/03-test-and-reconcile.md) against that event;
3. confirm the local digest recomputes;
4. confirm OpenBao exact-byte verification returns `true`;
5. query Fabric and confirm the ledger digest matches.

Expected: unchanged record is verified as valid.

### Step B3 - Prepare a temporary tamper account

In the isolated lab, create a temporary role with only the two columns required by the test:

```sql
CREATE ROLE integrity_tamper_test LOGIN;
\password integrity_tamper_test
GRANT USAGE ON SCHEMA telemetry TO integrity_tamper_test;
GRANT SELECT ON telemetry.uplinks TO integrity_tamper_test;
GRANT UPDATE (payload_json, temperature_c) ON telemetry.uplinks TO integrity_tamper_test;
```

Use this role only for the 10 selected event keys. Revoke and drop it immediately after the test.

### Step B4 - Run 10 post-storage tamper trials

Use one event at a time. Do **not** modify all ten rows at once. The required cycle is:

```text
verify original -> modify one row -> recompute from current row -> compare with original Fabric digest -> record -> restore same row -> verify restoration -> next event
```

This keeps every trial independently recoverable.

For each selected event:

1. capture the original Fabric digest and transaction ID;
2. connect interactively with the temporary role so its password is prompted rather than written into the command:

```bash
docker compose exec telemetry-db \
  psql -W -U integrity_tamper_test -d lorawan_telemetry
```

3. for the documented physical-sensor payload-v2 `temperature_c` compatibility field, modify only that selected event:

```sql
UPDATE telemetry.uplinks
SET temperature_c = temperature_c + 10,
    payload_json = jsonb_set(
        payload_json,
        '{temperature_c}',
        to_jsonb(temperature_c + 10),
        false
    )
WHERE event_key = '<TEST_EVENT_KEY>';

\q
```

Keep `temperature_c` as the single controlled field for all 10 post-storage tamper trials so the experimental condition remains identical between repetitions.

4. verify the outbox's already sealed `canonical_json`, digest, key ID, and signature did **not** change;
5. compare the current mutable source row with the sealed canonical evidence;
6. run the reviewed read-only adapter/canonicalization verifier that rebuilds `telemetry-attestation-v1` from the **current source row without signing or submitting**;
7. calculate its current-source SHA-256;
8. compare that hash with the original Fabric digest;
9. record the mismatch and verification time;
10. restore that event with the administrator account:

```sql
UPDATE telemetry.uplinks AS u
SET payload_json = r.payload_json,
    temperature_c = r.temperature_c
FROM telemetry.integrity_restore AS r
WHERE u.event_key = r.event_key
  AND u.time = r.time
  AND u.event_key = '<TEST_EVENT_KEY>';
```

11. re-query the row and prove it matches the restore copy before moving to the next trial.

Expected: current-source hash differs from the original Fabric digest.

### Required adapter testability

Do **not** begin counted post-storage trials until the reviewed Fabric adapter or companion verification tool can render the v1 canonical evidence from a chosen current source row without creating a new seal or Fabric transaction.

The verifier must use the same v1 schema and RFC 8785 rules as the adapter. It must pass the fixed v1 startup vector documented in the Fabric data-contract manual.

If this read-only verification path does not exist, the exact Chapter III post-storage hash-recomputation test is **blocked**. Do not fake the result by hashing arbitrary database JSON.

### Step B5 - Restore and remove the test role

After all trials:

```sql
REVOKE UPDATE (payload_json, temperature_c) ON telemetry.uplinks FROM integrity_tamper_test;
REVOKE SELECT ON telemetry.uplinks FROM integrity_tamper_test;
REVOKE USAGE ON SCHEMA telemetry FROM integrity_tamper_test;
DROP ROLE integrity_tamper_test;
```

Verify the 10 rows match `telemetry.integrity_restore`, then drop the restore table only after the full database backup remains available.

## Required result fields

```text
test_area
condition
trial
test_id_or_event_key
original_hash
recomputed_hash
hash_match
correct_decision
false_positive
false_negative
unauthorized_storage
verification_time_seconds
fabric_tx_id
evidence_reference
```

## Final restoration check

Before leaving the integrity experiment:

```text
[ ] temporary Node-RED gate removed
[ ] normal Node-RED flow restored and tested
[ ] integrity_tamper_test role revoked/dropped
[ ] all ten source rows restored
[ ] safety dump and checksum retained
[ ] one fresh EMU-01 control completes the normal path
```

Do not start traceability with integrity-test controls still active.

## Pass condition

```text
10/10 unchanged application records accepted
10/10 altered application records detected and blocked/quarantined
10/10 unchanged stored records match their Fabric evidence
10/10 post-storage modified records produce source-vs-Fabric mismatch
zero false negative
zero unauthorized storage for the application-layer altered records
```

Continue to [Execution 06 - Traceability](06-traceability.md).
