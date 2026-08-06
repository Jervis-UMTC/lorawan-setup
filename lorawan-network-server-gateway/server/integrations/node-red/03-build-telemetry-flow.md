# 3. Build the MQTT-to-Timescale Telemetry Flow

Build and validate the flow in stages. The completed flow writes one `telemetry.uplinks` row and zero or more `telemetry.measurements` rows in one PostgreSQL statement. If any part of the statement fails, PostgreSQL rolls back the entire statement so the generic event and normalized metrics do not drift apart.

## 3.1 Preconditions

Complete the telemetry schema guide first. Verify that both hypertables and both uniqueness indexes exist:

~~~bash
cd /opt/chirpstack-docker
~~~

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'telemetry' AND indexname IN ('uplinks_event_key_time_uq', 'measurements_event_metric_unit_time_uq') ORDER BY indexname;"
~~~

Confirm the Node-RED container has the exact regional identifier:

~~~bash
docker compose exec node-red printenv LORAWAN_REGION_ID
~~~

The value must match the active ChirpStack region ID and the Gateway OS Concentratord/MQTT Forwarder regional configuration, for example `as923_3`. **Stop here. Do not deploy the flow** if the value is blank, inferred from a display label, or inconsistent with the radio configuration.

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

Place a **function** node before the PostgreSQL node. Use the following code for the documented Dragino LSN50v2-S31/S31B payload fields:

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

const receivedAt = new Date().toISOString();
const fPort = numberOrNull(p.fPort);
const fCnt = numberOrNull(p.fCnt);
const gatewayId = rxInfo.gatewayId ? String(rxInfo.gatewayId).toLowerCase() : null;
const deduplicationId = String(p.deduplicationId || '').trim();
const eventKey = deduplicationId || [
    devEui,
    fCnt === null ? '' : String(fCnt),
    fPort === null ? '' : String(fPort),
    eventTime
].join('|');

const temperature = numberOrNull(decoded.TempC_SHT31);
const humidity = numberOrNull(decoded.Hum_SHT31);
const battery = numberOrNull(decoded.BatV);

const metrics = [
    { metric_name: 'temperature', metric_value: temperature, unit: 'Cel', source_field: 'TempC_SHT31' },
    { metric_name: 'humidity', metric_value: humidity, unit: '%', source_field: 'Hum_SHT31' },
    { metric_name: 'battery', metric_value: battery, unit: 'V', source_field: 'BatV' }
].filter((metric) => metric.metric_value !== null);

msg.query = [
    'WITH inserted_uplink AS (',
    '  INSERT INTO telemetry.uplinks (',
    '    event_key, time, received_at, application_id, application_name, ',
    '    device_id, device_name, dev_eui, gateway_id, region, f_port, f_cnt, ',
    '    confirmed, temperature_c, humidity_percent, battery_v, rssi_dbm, ',
    '    snr_db, payload_json, raw_data, mqtt_topic',
    '  ) VALUES (',
    '    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, ',
    '    $12, $13, $14, $15, $16, $17, $18, $19::jsonb, $20, $21',
    '  ) ON CONFLICT (event_key, time) DO NOTHING',
    '  RETURNING 1',
    '), event_identity AS (',
    '  SELECT $1::text AS event_key, $2::timestamptz AS time',
    ')',
    'INSERT INTO telemetry.measurements (',
    '  time, event_key, device_id, dev_eui, metric_name, metric_value, unit, ',
    '  quality, source_field, payload_json',
    ')',
    'SELECT ',
    '  e.time, e.event_key, $6, $8, m.metric_name, m.metric_value, m.unit, ',
    "  'measured', m.source_field, $19::jsonb",
    'FROM event_identity AS e',
    'CROSS JOIN (SELECT count(*) FROM inserted_uplink) AS uplink_state',
    'CROSS JOIN LATERAL jsonb_to_recordset($22::jsonb) AS m(',
    '  metric_name text, metric_value double precision, unit text, source_field text',
    ')',
    'ON CONFLICT (event_key, metric_name, unit, time) DO NOTHING;'
].join(' ');

msg.params = [
    eventKey,
    eventTime,
    receivedAt,
    deviceInfo.applicationId || null,
    deviceInfo.applicationName || null,
    deviceInfo.deviceId || null,
    deviceInfo.deviceName || null,
    devEui,
    gatewayId,
    regionId,
    fPort,
    fCnt,
    p.confirmed === true,
    temperature,
    humidity,
    battery,
    numberOrNull(rxInfo.rssi),
    numberOrNull(rxInfo.snr),
    JSON.stringify(decoded),
    p.data || null,
    msg.topic || null,
    JSON.stringify(metrics)
];

msg.telemetrySummary = {
    eventKey,
    devEui,
    eventTime,
    metricCount: metrics.length
};

return msg;
~~~

The code rejects malformed identity and event time rather than silently creating misleading records. It uses ChirpStack's `deduplicationId` when available; otherwise it derives a stable key from device identity, frame counter, port, and event time. Do not add a retry counter or current receipt time to the event key.

For another sensor model, define a separate reviewed mapping from decoded source fields to canonical metric names and units. Do not reuse the S31/S31B fields merely because another device reports temperature or humidity.

## 3.4 Configure the PostgreSQL node

Set the PostgreSQL node to use:

~~~text
Query source: msg.query
Parameter source: msg.params
Database configuration: telemetry-db / lorawan_telemetry / telemetry_writer
Output: default result object
~~~

Confirm those property names against the installed, pinned PostgreSQL node version. Connect a catch node to an operational error branch and include `msg.telemetrySummary` in sanitized error logs. Do not log database passwords or the full raw event by default.

## 3.5 Verify one real event and its metrics

After a real device uplink, query both tables using the event key or device EUI observed in the sanitized Node-RED summary:

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT event_key, time, device_name, dev_eui, region, temperature_c, humidity_percent, battery_v FROM telemetry.uplinks ORDER BY time DESC LIMIT 10;"
~~~

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT event_key, time, dev_eui, metric_name, metric_value, unit, quality, source_field FROM telemetry.measurements ORDER BY time DESC, metric_name LIMIT 30;"
~~~

A valid S31/S31B event should create one uplink row and up to three measurement rows, depending on which decoded fields are present. These rows prove the Node-RED-to-database path only; they do not replace evidence of RF reception, OTAA success, decryption, or codec correctness.

## 3.6 Verify duplicate handling

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

Next: [04-automation-and-downlinks.md](04-automation-and-downlinks.md)
