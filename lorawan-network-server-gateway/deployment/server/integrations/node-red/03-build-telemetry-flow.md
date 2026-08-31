# 3. Build the MQTT-to-Timescale Telemetry Flow

Build and validate the flow in stages. The completed flow writes one `telemetry.uplinks` row and the reviewed normalized `telemetry.measurements` rows in one PostgreSQL statement. When the optional Fabric-outbox CTE from the attestation manual is enabled, that selected outbox row is part of the **same statement and transaction**. If any part of the statement fails, PostgreSQL rolls back the whole statement so telemetry, normalized metrics, and any selected queue work do not drift apart.

### Why Node-RED is before PostgreSQL

The application path is deliberately ordered as:

~~~text
ChirpStack accepted application event
  -> MQTT
  -> Node-RED validation / normalization
  -> PostgreSQL / TimescaleDB
  -> optional Fabric outbox row for selected events
~~~

Node-RED is the ingestion gate, not the database and not the cryptographic trust anchor. It receives an already accepted ChirpStack application event, validates the application identity and timestamp fields required by the telemetry schema, normalizes reviewed sensor fields and units, derives a stable event identity, and builds parameterized SQL. PostgreSQL then enforces durability, uniqueness, transactions, roles, and schema constraints.

This ordering provides practical application-layer protections before a record becomes valid operational telemetry:

- malformed DevEUI values and invalid event timestamps are rejected instead of being silently stored;
- decoded values are converted only through the reviewed mapping and invalid numeric values become null or are rejected according to the mapping policy;
- a stable `event_key` plus database uniqueness constraints prevents legitimate MQTT redelivery from creating duplicate telemetry records;
- parameterized SQL avoids concatenating MQTT data into SQL text and reduces SQL-injection risk;
- the uplink row, normalized measurements, and any selected Fabric outbox entry are committed atomically, so a failed statement does not leave a telemetry record without its required queue entry or vice versa;
- the Node-RED database account remains a limited application writer rather than a database administrator.

These controls improve input hygiene, consistency, and least-privilege operation, but they do **not** prove that a physical sensor measured the real world correctly, make PostgreSQL immutable, or make Node-RED a blockchain signer. Production evidence canonicalization, SHA-256 calculation, OpenBao signing/verification, and Hyperledger Fabric submission belong to the separate Fabric adapter. Node-RED must never receive the Fabric client private key, OpenBao root/unseal material, or permission to create a `verified` gateway-evidence result.

## 3.1 Preconditions

Complete the telemetry schema guide first. Verify that both hypertables and both uniqueness indexes exist.

### Single-host lab

~~~bash
cd /opt/lorawan-lab
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'telemetry' AND indexname IN ('uplinks_event_key_time_uq', 'measurements_event_metric_unit_time_uq') ORDER BY indexname;"
docker compose exec node-red printenv LORAWAN_REGION_ID
~~~

### Three-Droplet cloud HA POC

From `ha-03`, query through the normal database path instead of a nonexistent `telemetry-db` container:

~~~bash
psql 'host=pgbouncer.internal.lorawan.com port=6432 dbname=lorawan_telemetry user=telemetry_reader sslmode=verify-full' \
  -c "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'telemetry' AND indexname IN ('uplinks_event_key_time_uq', 'measurements_event_metric_unit_time_uq') ORDER BY indexname;"

cd /etc/lorawan-cloud/node-red
sudo docker compose --env-file node-red.env exec node-red printenv LORAWAN_REGION_ID
~~~

Also prove `timescaledb_information.hypertables` contains `telemetry.uplinks` and `telemetry.measurements` before deploying a write flow.

Confirm the Node-RED container has the exact regional identifier:

The value must match the active ChirpStack region ID and the Gateway OS Concentratord/MQTT Forwarder regional configuration. In the current cloud POC the commissioned identity is **plain `as923`**, not `as923_2`, `as923_3`, or `as923_4`. **Stop here. Do not deploy the flow** if the value is blank, inferred from a display label, or inconsistent with the radio configuration.

## 3.2 Flow layout

Use one PostgreSQL node so the uplink and normalized metrics are stored atomically:

~~~text
mqtt in
  -> json, only when the MQTT node returns a string
  -> function: validate, normalize, and build parameterized SQL
  -> postgresql: execute msg.query with msg.params
  -> debug: temporary insert result
~~~

Add a catch node and a separate operational error path. A notification failure must not modify or retry the database statement with a different event key.

## 3.3 Configure the function node

Place a **function** node before the PostgreSQL node. The primary project telemetry node is **EMU-01**, whose frozen Agriculture Kit payload v2 is 46 bytes and is already decoded by ChirpStack into the field names below. Do not re-decode the binary payload in Node-RED; normalize the reviewed ChirpStack-decoded object.

~~~javascript
const p = msg.payload || {};
const deviceInfo = p.deviceInfo || {};
const decoded = p.object || {};
const rxInfo = Array.isArray(p.rxInfo) && p.rxInfo.length > 0 ? p.rxInfo[0] : {};

function numberOrNull(value) {
    if (value === undefined || value === null || value === '') {
        return null;
    }
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
}

const topicParts = String(msg.topic || '').split('/');
const topicDevEui = topicParts.length >= 4 ? topicParts[3] : '';
const devEui = String(deviceInfo.devEui || topicDevEui || '').toLowerCase();

if (!/^[0-9a-f]{16}$/.test(devEui)) {
    node.warn('Dropping uplink with missing or invalid DevEUI');
    return null;
}

const eventTime = String(p.time || '');
if (!eventTime || Number.isNaN(Date.parse(eventTime))) {
    node.warn(`Dropping uplink with invalid event time for ${devEui}`);
    return null;
}

const regionId = String(env.get('LORAWAN_REGION_ID') || '').trim();
if (!regionId) {
    node.error('LORAWAN_REGION_ID is not configured');
    return null;
}

const payloadVersion = numberOrNull(decoded.payload_version);
const testSequence = numberOrNull(decoded.test_sequence);
const validity = numberOrNull(decoded.sensor_validity_bitmap);

if (payloadVersion !== 2) {
    node.warn(`Dropping ${devEui} event with unsupported payload_version=${decoded.payload_version}`);
    return null;
}
if (!Number.isInteger(testSequence) || testSequence < 0) {
    node.warn(`Dropping ${devEui} payload-v2 event with invalid test_sequence`);
    return null;
}
if (!Number.isInteger(validity) || validity < 0 || validity > 0xffff) {
    node.warn(`Dropping ${devEui} payload-v2 event with invalid sensor_validity_bitmap`);
    return null;
}

const receivedAt = new Date().toISOString();
const fPort = numberOrNull(p.fPort);
const fCnt = numberOrNull(p.fCnt);
const gatewayId = rxInfo.gatewayId ? String(rxInfo.gatewayId).toLowerCase() : null;
const gatewayUplinkIdRaw = numberOrNull(rxInfo.uplinkId);
const gatewayUplinkId = Number.isInteger(gatewayUplinkIdRaw) && gatewayUplinkIdRaw >= 0 && gatewayUplinkIdRaw <= 0xffffffff ? gatewayUplinkIdRaw : null;
const gatewayFrequencyRaw = numberOrNull((p.txInfo || {}).frequency);
const gatewayFrequencyHz = Number.isInteger(gatewayFrequencyRaw) && gatewayFrequencyRaw > 0 ? gatewayFrequencyRaw : null;
const gatewayContextBase64 = typeof rxInfo.context === 'string' ? rxInfo.context : null;
const deduplicationId = String(p.deduplicationId || '').trim();
const eventKey = deduplicationId || [
    devEui,
    fCnt === null ? '' : String(fCnt),
    fPort === null ? '' : String(fPort),
    eventTime
].join('|');

// Provenance for the reviewed Node-RED field mapping. Increment this mapping
// version whenever source fields, units, validity semantics, or normalization
// behavior changes. Payload byte decoding remains owned by the ChirpStack codec.
const deviceModel = 'RAK WisBlock Agriculture Kit / EMU-01';
const decoderVersion = 'agriculture-kit-payload-v2-node-red-v1';

function bitIsValid(bit) {
    return (validity & (1 << bit)) !== 0;
}

function numericMetric(metricName, sourceField, unit, validityBit) {
    const value = numberOrNull(decoded[sourceField]);
    const measured = bitIsValid(validityBit) && value !== null;
    return {
        metric_name: metricName,
        metric_value: measured ? value : null,
        metric_text: null,
        metric_bool: null,
        unit,
        quality: measured ? 'measured' : 'invalid',
        source_field: sourceField
    };
}

function booleanMetric(metricName, sourceField, unit, validityBit) {
    const present = typeof decoded[sourceField] === 'boolean';
    const measured = bitIsValid(validityBit) && present;
    return {
        metric_name: metricName,
        metric_value: null,
        metric_text: null,
        metric_bool: measured ? decoded[sourceField] : null,
        unit,
        quality: measured ? 'measured' : 'invalid',
        source_field: sourceField
    };
}

const batteryRaw = numberOrNull(decoded.battery_v);
const batteryMeasured = batteryRaw !== null && batteryRaw > 0;

const metrics = [
    numericMetric('soil_moisture_percent', 'soil_moisture_percent', '%', 0),
    numericMetric('soil_temperature_c', 'soil_temperature_c', 'Cel', 0),
    numericMetric('uv_index', 'uv_index', '1', 1),
    numericMetric('barometer_pressure_pa', 'barometer_pressure_pa', 'Pa', 2),
    numericMetric('barometer_temperature_c', 'barometer_temperature_c', 'Cel', 2),
    numericMetric('light_veml7700_lux', 'light_veml7700_lux', 'lx', 3),
    numericMetric('light_opt3001_lux', 'light_opt3001_lux', 'lx', 4),
    numericMetric('environment_temperature_c', 'environment_temperature_c', 'Cel', 5),
    numericMetric('environment_humidity_percent', 'environment_humidity_percent', '%', 5),
    numericMetric('environment_pressure_pa', 'environment_pressure_pa', 'Pa', 5),
    numericMetric('environment_gas_resistance_ohm', 'environment_gas_resistance_ohm', 'ohm', 5),
    booleanMetric('rain_wet', 'rain_wet', 'boolean', 6),
    {
        metric_name: 'battery_v',
        metric_value: batteryMeasured ? batteryRaw : null,
        metric_text: null,
        metric_bool: null,
        unit: 'V',
        quality: batteryMeasured ? 'measured' : 'invalid',
        source_field: 'battery_v'
    }
];

// Compatibility columns remain useful for simple dashboards, but only expose
// environment temperature/humidity when the ENV validity bit says the reading
// is valid. The complete decoded object, including validity and test_sequence,
// is always preserved in payload_json.
const environmentValid = bitIsValid(5);
const temperature = environmentValid ? numberOrNull(decoded.environment_temperature_c) : null;
const humidity = environmentValid ? numberOrNull(decoded.environment_humidity_percent) : null;
const battery = batteryRaw;

msg.query = [
    'WITH inserted_uplink AS (',
    '  INSERT INTO telemetry.uplinks (',
    '    event_key, time, received_at, application_id, application_name, ',
    '    device_id, device_name, device_model, decoder_version, dev_eui, ',
    '    gateway_id, gateway_uplink_id, gateway_frequency_hz, gateway_context_base64, region, f_port, f_cnt, confirmed, temperature_c, ',
    '    humidity_percent, battery_v, rssi_dbm, snr_db, payload_json, ',
    '    raw_data, mqtt_topic',
    '  ) VALUES (',
    '    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $25, $26, $27, $12, ',
    '    $13, $14, $15, $16, $17, $18, $19, $20, $21::jsonb, $22, $23',
    '  ) ON CONFLICT (event_key, time) DO NOTHING',
    '  RETURNING event_key, time',
    '), event_identity AS (',
    '  SELECT $1::text AS event_key, $2::timestamptz AS time',
    ')',
    'INSERT INTO telemetry.measurements (',
    '  time, event_key, device_id, dev_eui, metric_name, metric_value, metric_text, ',
    '  metric_bool, unit, quality, source_field, payload_json',
    ')',
    'SELECT ',
    '  e.time, e.event_key, $6, $10, m.metric_name, m.metric_value, m.metric_text, ',
    '  m.metric_bool, m.unit, m.quality, m.source_field, $21::jsonb',
    'FROM event_identity AS e',
    'CROSS JOIN (SELECT count(*) FROM inserted_uplink) AS uplink_state',
    'CROSS JOIN LATERAL jsonb_to_recordset($24::jsonb) AS m(',
    '  metric_name text, metric_value double precision, metric_text text, ',
    '  metric_bool boolean, unit text, quality text, source_field text',
    ')',
    'WHERE uplink_state.count > 0',
    'ON CONFLICT (event_key, metric_name, unit, time) DO NOTHING;'
].join(' ');

msg.params = [
    eventKey,                              // $1
    eventTime,                             // $2
    receivedAt,                            // $3
    deviceInfo.applicationId || null,      // $4
    deviceInfo.applicationName || null,    // $5
    deviceInfo.deviceId || null,           // $6
    deviceInfo.deviceName || null,         // $7
    deviceModel,                           // $8
    decoderVersion,                        // $9
    devEui,                                // $10
    gatewayId,                             // $11
    regionId,                              // $12
    fPort,                                 // $13
    fCnt,                                  // $14
    p.confirmed === true,                  // $15
    temperature,                           // $16
    humidity,                              // $17
    battery,                               // $18
    numberOrNull(rxInfo.rssi),             // $19
    numberOrNull(rxInfo.snr),              // $20
    JSON.stringify(decoded),               // $21
    p.data || null,                        // $22
    msg.topic || null,                     // $23
    JSON.stringify(metrics),               // $24
    gatewayUplinkId,                       // $25
    gatewayFrequencyHz,                    // $26
    gatewayContextBase64                   // $27
];

msg.telemetrySummary = {
    eventKey,
    devEui,
    eventTime,
    testSequence,
    validity,
    deviceModel,
    decoderVersion,
    metricCount: metrics.length,
    gatewayUplinkId,
    gatewayFrequencyHz,
    gatewayContextPresent: gatewayContextBase64 !== null
};

return msg;
~~~

The code rejects malformed identity/time and rejects a payload that is not the frozen Agriculture Kit payload v2. It uses ChirpStack's `deduplicationId` when available; otherwise it derives a stable key from device identity, frame counter, port, and event time. Do not add a retry counter or current receipt time to the event key.

`payload_json` preserves `test_sequence`, the complete decoded sensor object, and `sensor_validity_bitmap`. Invalid sensor groups are retained in `payload_json`, while their normalized measurement rows use `quality='invalid'` and a null measurement value so an old/sentinel value is not mislabeled as a valid physical measurement.

For gateway-verified `telemetry-attestation-v2`, the same first ChirpStack reception already used for `gateway_id`, RSSI, and SNR also preserves `rxInfo[0].uplinkId` and `rxInfo[0].context`, while `txInfo.frequency` is stored beside them. These nullable provenance fields are not a trust decision; they are deterministic join material for the independent verifier. Existing v1 rows may leave them null. Never reconstruct a missing v2 join by choosing the nearest MQTT timestamp. The battery field has no payload-v2 validity bit; a positive finite voltage is normalized as measured, while the documented USB-only `0` sentinel remains visible in `payload_json`/the compatibility column and is marked invalid in normalized metrics.

`device_model` and `decoder_version` are provenance, not cosmetic labels. `decoderVersion` identifies **this Node-RED normalization mapping**, not the ChirpStack binary codec. Increment it for any material change to source-field names, scaling assumptions, units, or validity behavior.

For historical `telemetry-attestation-v1`, this Node-RED/ChirpStack application provenance remains the existing evidence meaning. For gateway-verified `telemetry-attestation-v2`, the independent gateway-evidence verifier must also run a pinned trusted decoder outside Node-RED against the accepted raw application `data`, record its own decoder ID/version or code hash, and compare the approved normalized fields with this row. Do not reuse the Node-RED `decoderVersion` string as proof that the independent decoder ran.

**SEC-02 is not the permanent multi-sensor telemetry profile.** Its temporary legitimate RAK12011 verification uses a separate 6-byte codec (`barometer_temperature_c`, `barometer_pressure_hpa`) before SEC-02 returns to the security-fixture role. Do not feed that 6-byte payload into this EMU-01 payload-v2 mapping. If the temporary SEC-02 reading needs to be stored, create a separate explicitly versioned mapping and remove/disable it when SEC-02 is converted back to the security fixture.

For any future sensor model, define a separate reviewed mapping from decoded source fields to canonical metric names/units and give it its own model/mapping version. Do not alias different sensor semantics merely because two devices both report temperature or pressure.

## 3.4 Configure the PostgreSQL node

Set the PostgreSQL node to use:

~~~text
Query source: msg.query
Parameter source: msg.params
Database configuration:
  lab   -> telemetry-db:5432 / lorawan_telemetry / telemetry_writer
  cloud -> pgbouncer.internal.lorawan.com:6432 / lorawan_telemetry / telemetry_writer / verified TLS
Output: default result object
~~~

Confirm those property names against the installed, pinned PostgreSQL node version. Connect a catch node to an operational error branch and include `msg.telemetrySummary` in sanitized error logs. Do not log database passwords or the full raw event by default.

## 3.5 Verify one real event and its metrics

After a real device uplink, query both tables using the event key or device EUI observed in the sanitized Node-RED summary.

Use the profile's normal read path:

~~~sql
SELECT event_key, time, device_name, device_model, decoder_version,
       dev_eui, region, f_cnt, temperature_c, humidity_percent, battery_v
FROM telemetry.uplinks
ORDER BY time DESC
LIMIT 10;

SELECT event_key, time, dev_eui, metric_name, metric_value, unit, quality, source_field
FROM telemetry.measurements
ORDER BY time DESC, metric_name
LIMIT 30;
~~~

In the lab run these through `docker compose exec telemetry-db psql ...`. In the cloud POC run them with `psql` through `pgbouncer.internal.lorawan.com:6432` as `telemetry_reader` or another approved read role.

A valid EMU-01 payload-v2 event should create one canonical uplink row plus one normalized row for each reviewed metric mapping. Sensor groups whose validity bit is clear remain represented as `quality='invalid'` rows with null normalized values, while the complete decoded object remains in `payload_json`. These database rows prove the Node-RED-to-database path only; they do not replace evidence of RF reception, gateway-journal continuity, remote gateway-MQTT delivery, OTAA/session processing, or independent decoder correctness.

For v2 evidence, Node-RED must never directly write `gateway_evidence.event_verification.status='verified'`. That state belongs to the independent verifier after it checks the earlier gateway and delivery evidence.

## 3.6 Verify duplicate handling and optional atomic Fabric enqueue

The cloud HA runtime keeps Fabric selection as deployment policy rather than baking a real device identity into the shared flow. `FABRIC_SELECTED_DEV_EUI` is passed through the protected host environment. Until hardware returns, use the reserved fake DevEUI `0000000000000000` only for the documented pre-arrival synthetic fixture. When the approved real staging device is known, change only the protected environment value on both Node-RED candidates; keep the reviewed flow bytes identical.

The same PostgreSQL statement must contain a data-modifying `queued_fabric` CTE that inserts `event_key='uplink:' || <source event key>` into `telemetry.fabric_outbox` with `schema_version='telemetry-attestation-v1'` only when the selected DevEUI matches. In the deployed cloud runtime the selection boolean remains parameter `$25`; the original telemetry parameters remain `$1` through `$24`, and the optional first-reception provenance is appended as `$26` through `$28`. The simpler standalone example above has no outbox CTE, so its provenance parameters begin at `$25`. Because the CTE selects only from `inserted_uplink`, replaying the same event cannot create another outbox job.

Replay the same sanitized Inject-node message once. The row counts for its `event_key` and `time` must not increase:

~~~sql
SELECT count(*)
FROM telemetry.uplinks
WHERE event_key = '<TEST_EVENT_KEY>';

SELECT metric_name, unit, count(*)
FROM telemetry.measurements
WHERE event_key = '<TEST_EVENT_KEY>'
GROUP BY metric_name, unit;
~~~

Each expected count must remain `1`. **Stop here. Do not enable downstream alerts or integrations** if duplicate handling is not proven.

## 3.7 Preserve unknown decoded fields

The `payload_json` column stores the complete decoded object for later analysis. Promote a field into `telemetry.measurements` only after its model, firmware revision, canonical name, type, unit, valid range, and quality behavior are approved.

Do not expose unrestricted `payload_json` to untrusted users. It may contain device status, location-related metadata, or fields that have not passed validation.

Preserve `raw_data` (`p.data`) for the evidence-retention period required by the gateway-integrity policy. The trusted decoder needs those accepted raw application bytes or an independently preserved exact copy; a decoded `payload_json` object alone is not sufficient to prove that Node-RED did not change a value.

Next: [04-automation-and-downlinks.md](04-automation-and-downlinks.md)
