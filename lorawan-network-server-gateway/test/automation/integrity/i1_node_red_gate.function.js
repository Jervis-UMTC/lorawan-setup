// I1 test-only Node-RED Function node. Exactly two outputs:
// output 1: unchanged validated EMU-01 -> existing NORMAL processing
// output 2: altered/invalid EMU-01 -> isolated quarantine/debug/file ONLY
// This experimental JSON.stringify SHA-256 is NOT the Fabric RFC8785 evidence digest.
// Configure functionGlobalContext.crypto=require('crypto') and substitute the reviewed
// device EUI before live deployment; DO NOT install in production until reviewed.
const TEST_DEV_EUI = 'ac1f09fffe296d29';
const testEui = String((msg.payload && msg.payload.deviceInfo && msg.payload.deviceInfo.devEui) || '').toLowerCase();
if (testEui !== TEST_DEV_EUI) {
    // Non-EMU traffic is outside the I1 experiment. Do not consume the arm flag.
    return [msg, null];
}
function quarantine(reason) {
    // Fail closed for I1 target; never send malformed/altered target evidence to SQL/Fabric.
    msg.integrityTest = {test_id: 'I1', status: 'INVALID', reason: String(reason),
                         observed_at_utc: new Date().toISOString()};
    return [null, msg];
}
let armed;
try {
    armed = flow.get('integrity_alter_next') === true;
    // Disarm before any potentially failing operation; one click affects at most one
    // eligible target message even when crypto/input/observation is malformed.
    if (armed) flow.set('integrity_alter_next', false);
} catch (e) {
    node.error('I1 test arm state unavailable');
    return quarantine('arm_state_unavailable');
}
const p = msg.payload || {};
const d = p.object || {};
const temp = d.temperature_c;
const seq = d.test_sequence !== undefined ? d.test_sequence : d.sequence;
const testId = p.deduplicationId;
const fCnt = p.fCnt;
const eventTime = p.time;
if (typeof testId !== 'string' || !testId.trim() || !Number.isInteger(fCnt) || fCnt < 0 ||
    !Number.isInteger(seq) || seq < 0 || typeof temp !== 'number' || !Number.isFinite(temp) ||
    typeof eventTime !== 'string' || !Number.isFinite(Date.parse(eventTime))) {
    node.error('I1 test record missing/invalid identity, counter, sequence, time or temperature');
    return quarantine('invalid_test_record');
}
let crypto;
try {
    crypto = global.get('crypto');
    if (!crypto || typeof crypto.createHash !== 'function') throw new Error('crypto missing');
} catch (e) {
    node.error('I1 crypto unavailable');
    return quarantine('crypto_unavailable');
}
const record = {
    test_id: testId.trim(),
    dev_eui: testEui,
    f_cnt: fCnt,
    sensor_type: 'temperature',
    sensor_value: temp,
    unit: 'Cel',
    event_time: eventTime
};
const beforeJson = JSON.stringify(record);
const beforeHash = crypto.createHash('sha256').update(beforeJson, 'utf8').digest('hex');
// Clone the nested decoded object so this test gate does not silently alter the
// original msg when a later user flow retains its reference.
const afterValue = armed ? temp + 10 : temp;
if (!Number.isFinite(afterValue)) {
    node.error('I1 altered temperature is not finite');
    return quarantine('altered_value_invalid');
}
const afterRecord = {...record, sensor_value: afterValue};
const afterJson = JSON.stringify(afterRecord);
const afterHash = crypto.createHash('sha256').update(afterJson, 'utf8').digest('hex');
const changed = beforeHash !== afterHash;
const routedMsg = {...msg, payload: {...p, object: {...d, temperature_c: afterValue}}};
routedMsg.integrityTest = {
    test_id: testId.trim(),
    test_sequence: seq,
    dev_eui: testEui,
    initial_record_json: beforeJson,
    final_record_json: afterJson,
    initial_hash: beforeHash,
    final_hash: afterHash,
    altered: armed,
    match: !changed,
    status: changed ? 'QUARANTINE' : 'ALLOW',
    observed_at_utc: new Date().toISOString(),
    hash_scope: 'I1_EXPERIMENTAL_JSON_STRINGIFY_NOT_FABRIC'
};
return changed ? [null, routedMsg] : [routedMsg, null];
