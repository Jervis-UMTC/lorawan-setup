# 4. Automation, Alerts, and Downlinks

Use the verified telemetry insert flow as the stable base. Add automation in separate branches so an alert or external API failure cannot block storage. This platform is not an approved emergency shutdown, interlock, collision-avoidance, or other safety-critical control system.

## 4.1 Alert branch

Recommended structure:

~~~text
validated message
  -> database insert
  -> switch: threshold condition
  -> rate limit
  -> notification output
~~~

Do not place a slow HTTP request before the database insert. A remote API timeout should not prevent the telemetry record from being stored.

## 4.2 Example threshold function

For an S31/S31B temperature field, obtain the approved threshold from protected environment configuration rather than hard-coding it in the flow:

~~~javascript
const object = msg.payload.object || {};
const temperature = Number(object.TempC_SHT31);
const threshold = Number(env.get('HIGH_TEMPERATURE_C'));

if (!Number.isFinite(temperature) || !Number.isFinite(threshold)) {
    node.warn('Temperature or approved threshold is unavailable');
    return null;
}

if (temperature > threshold) {
    msg.alert = {
        type: 'high_temperature',
        device: msg.payload.deviceInfo ? msg.payload.deviceInfo.deviceName : 'unknown',
        value: temperature,
        threshold,
        eventKey: msg.telemetrySummary ? msg.telemetrySummary.eventKey : null
    };
    return msg;
}

return null;
~~~

Only after the domain owner approves the value, units, persistence period, stale-data rule, recipient, and response, add the variable to the protected `.env` file:

~~~dotenv
HIGH_TEMPERATURE_C=<APPROVED_THRESHOLD>
~~~

Pass it into the Node-RED service explicitly:

~~~yaml
environment:
  HIGH_TEMPERATURE_C: ${HIGH_TEMPERATURE_C}
~~~

Run `docker compose config --quiet`, restart Node-RED, and verify `docker compose exec node-red printenv HIGH_TEMPERATURE_C` returns the intended value. Do not treat an example threshold as a universal safe value.

## 4.3 Downlink identity and topic

Create a separate MQTT broker configuration node for approved downlinks:

~~~text
Broker: mosquitto
Port: 1883
Username: node_red_downlink
~~~

The broker ACL must restrict this identity to the approved application and device command topics. Do not reuse the read-only `node_red` ingestion identity and do not grant wildcard command access.

ChirpStack's MQTT downlink command topic is:

~~~text
application/<APPLICATION_ID>/device/<DEV_EUI>/command/down
~~~

Example payload:

~~~json
{
  "devEui": "replace_with_real_deveui",
  "confirmed": false,
  "fPort": 2,
  "data": "base64_payload"
}
~~~

The data value is base64-encoded. The fPort and payload must come from the exact Dragino model manual.

## 4.4 Downlink safety gates

Before enabling any automatic downlink, obtain explicit application-owner approval and verify that loss, delay, duplication, or an incorrect command cannot create an unsafe state. Then:

- verify the device is Class A, B, or C;
- verify the device's receive timing;
- verify the exact command port;
- test manually with one device;
- log every command and response;
- rate-limit commands; and
- provide a manual disable switch;
- use a stable command idempotency key where the device protocol supports it;
- define what happens after an unknown delivery result; and
- retain an audit record containing operator or rule, device, payload digest, port, request time, and observed result.

For battery Class A devices, downlinks are normally delivered only after an uplink receive window. A queued command, MQTT publish, or gateway transmission does not prove the device applied the command. Confirm application-level acknowledgement when the device protocol supports it.

## 4.5 Do not put secrets in messages

Do not use Node-RED messages, debug nodes, or dashboard text fields for:

- AppKey;
- NwkKey;
- PostgreSQL passwords;
- MQTT passwords;
- API tokens; or
- webhook signing secrets.

Use protected Node-RED credentials and environment configuration.

## 4.6 Node-RED context and restart behavior

If an alert requires consecutive readings, persist the counter intentionally. An in-memory context resets on a container restart. Use a persistent context store or the telemetry database when the state must survive reboot.

Next: [05-testing-and-troubleshooting.md](05-testing-and-troubleshooting.md)
