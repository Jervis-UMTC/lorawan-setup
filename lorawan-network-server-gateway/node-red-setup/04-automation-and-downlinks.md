# 4. Automation, Alerts, and Downlinks

Use the telemetry insert flow as the stable base. Add automation in separate branches so an alert failure cannot block database storage.

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

For an S31/S31B temperature field:

~~~javascript
const object = msg.payload.object || {};
const temperature = Number(object.TempC_SHT31);

if (!Number.isFinite(temperature)) {
    return null;
}

if (temperature > 35) {
    msg.alert = {
        type: 'high_temperature',
        device: msg.payload.deviceInfo ? msg.payload.deviceInfo.deviceName : 'unknown',
        value: temperature,
        threshold: 35
    };
    return msg;
}

return null;
~~~

Replace the threshold with the actual agricultural or laboratory requirement. Do not treat 35 degrees as a universal safe value.

## 4.3 Downlink topic

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

Before enabling automatic downlinks:

- verify the device is Class A, B, or C;
- verify the device's receive timing;
- verify the exact command port;
- test manually with one device;
- log every command and response;
- rate-limit commands; and
- provide a manual disable switch.

For battery Class A devices, downlinks are normally delivered only after an uplink receive window. Do not declare a downlink failed immediately.

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
