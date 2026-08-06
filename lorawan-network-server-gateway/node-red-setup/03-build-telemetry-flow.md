# 3. Build the MQTT-to-Timescale Telemetry Flow

Build the flow in stages. Keep a debug node connected until one real sensor message has been inserted and verified in PostgreSQL.

## 3.1 Flow layout

Use this logical sequence:

~~~text
mqtt in
  -> json
  -> function: validate and normalize
  -> postgresql
  -> debug: insert result
~~~

Add a separate error path from the PostgreSQL node to a warning or notification flow.

## 3.2 Function node validation and normalization

Place a **function** node after the JSON node. Use this code:

~~~javascript
const p = msg.payload || {};
const deviceInfo = p.deviceInfo || {};
const object = p.object || {};
const rxInfo = Array.isArray(p.rxInfo) && p.rxInfo.length > 0 ? p.rxInfo[0] : {};

const topicParts = String(msg.topic || '').split('/');
const topicDevEui = topicParts.length >= 4 ? topicParts[3] : '';
const devEui = String(deviceInfo.devEui || topicDevEui || '').toLowerCase();

if (!devEui) {
    node.warn('Dropping uplink without DevEUI');
    return null;
}

function numberOrNull(value) {
    if (value === undefined || value === null || value === '') {
        return null;
    }
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

const eventTime = p.time || new Date().toISOString();
const receivedAt = new Date().toISOString();
const fPort = numberOrNull(p.fPort);
const fCnt = numberOrNull(p.fCnt);
const gatewayId = rxInfo.gatewayId || null;
const eventKey = [
    devEui,
    fCnt === null ? '' : String(fCnt),
    fPort === null ? '' : String(fPort),
    eventTime,
    gatewayId || ''
].join('|');

msg.query = [
    'INSERT INTO telemetry.uplinks (',
    'event_key, time, received_at, application_id, application_name, ',
    'device_id, device_name, dev_eui, gateway_id, region, f_port, f_cnt, ',
    'confirmed, temperature_c, humidity_percent, battery_v, rssi_dbm, ',
    'snr_db, payload_json, raw_data, mqtt_topic',
    ') VALUES (',
    '$1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, ',
    '$12, $13, $14, $15, $16, $17, $18, $19, $20, $21',
    ') ON CONFLICT (event_key, time) DO NOTHING;'
].join('');

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
    'AS923-3',
    fPort,
    fCnt,
    p.confirmed === true,
    numberOrNull(object.TempC_SHT31),
    numberOrNull(object.Hum_SHT31),
    numberOrNull(object.BatV),
    numberOrNull(rxInfo.rssi),
    numberOrNull(rxInfo.snr),
    JSON.stringify(object),
    p.data || null,
    msg.topic || null
];

return msg;
~~~

This function is written for the local Dragino S31/S31B decoder fields. For another sensor model, change the object field mappings after confirming that model's payload codec.

## 3.3 Add an event-key column if using duplicate protection

The function uses event_key for idempotent retries. Add this column and index to the database schema:

~~~sql
ALTER TABLE telemetry.uplinks
    ADD COLUMN IF NOT EXISTS event_key TEXT;
~~~

~~~sql
UPDATE telemetry.uplinks
SET event_key = concat_ws('|', dev_eui, coalesce(f_cnt::text, ''), coalesce(f_port::text, ''), time::text, coalesce(gateway_id, ''))
WHERE event_key IS NULL;
~~~

~~~sql
ALTER TABLE telemetry.uplinks
    ALTER COLUMN event_key SET NOT NULL;
~~~

~~~sql
CREATE UNIQUE INDEX IF NOT EXISTS uplinks_event_key_time_idx
    ON telemetry.uplinks (event_key, time);
~~~

Run these statements before deploying the Node-RED flow. If the table is empty, the first ALTER TABLE is sufficient before creating the unique index.

## 3.4 Configure the PostgreSQL node

Set the PostgreSQL node to:

~~~text
Query: use msg.query
Parameters: use msg.params
Database configuration: telemetry-db
Output: default
~~~

Connect the function node to the PostgreSQL node and the PostgreSQL output to a debug node.

## 3.5 Verify the first insert

When a real device sends an uplink, query the database:

~~~bash
cd ~/chirpstack-docker
~~~

~~~bash
docker compose exec telemetry-db psql -U telemetry_admin -d lorawan_telemetry -c "SELECT time, device_name, dev_eui, temperature_c, humidity_percent, battery_v, rssi_dbm, snr_db FROM telemetry.uplinks ORDER BY time DESC LIMIT 10;"
~~~

The row proves the Node-RED-to-database path. It does not replace verification of the ChirpStack device event and gateway frame.

## 3.6 Preserve unknown decoded fields

The payload_json column stores the complete decoded object. If a later firmware or model adds fields, those fields remain available even before the relational columns are extended.

Do not expose payload_json directly to untrusted users. It may contain device-specific status or operational metadata.

Next: [04-automation-and-downlinks.md](04-automation-and-downlinks.md)
