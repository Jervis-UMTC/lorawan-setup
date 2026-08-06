# 2. Core Platform and Domain Profile

The cleanest transfer strategy is to keep infrastructure concerns separate from business meaning. A new domain should be able to use the same gateway, MQTT, Node-RED, TimescaleDB, and Grafana services while supplying a different profile.

## 2.1 Common telemetry envelope

Use a domain-neutral envelope around every normalized observation:

~~~json
{
  "schema_version": "telemetry-envelope-v1",
  "domain": "agriculture",
  "site_id": "farm-01",
  "zone_id": "greenhouse-a",
  "asset_id": "greenhouse-a-sensor-01",
  "device_id": "dragino-s31-01",
  "device_eui": "REPLACE_WITH_DEVEUI",
  "gateway_id": "<GATEWAY_EUI>",
  "observed_at": "<OBSERVED_AT_UTC>",
  "received_at": "<RECEIVED_AT_UTC>",
  "measurements": [
    {
      "name": "temperature",
      "value": 24.7,
      "unit": "Cel",
      "quality": "measured"
    }
  ],
  "source": {
    "network_server": "chirpstack",
    "application_id": "agriculture",
    "f_port": 2,
    "f_cnt": 104
  }
}
~~~

The current TimescaleDB table has convenient agriculture columns such as temperature_c and humidity_percent. Keep those columns for compatibility, but add a domain-neutral representation or a domain-specific child table when the project grows beyond a single sensor family.

## 2.2 Domain profile example

Store profile configuration in version control, without secrets:

~~~yaml
profile_id: agriculture-greenhouse-v1
domain: agriculture
asset_type: greenhouse_sensor
metrics:
  temperature:
    source_field: TempC_SHT31
    unit: Cel
    min_valid: -40
    max_valid: 85
  humidity:
    source_field: Hum_SHT31
    unit: '%'
    min_valid: 0
    max_valid: 100
  battery:
    source_field: BatV
    unit: V
alert_rules:
  temperature_high:
    condition: temperature > 35
    response: notify_farm_operator
~~~

A port profile might look like:

~~~yaml
profile_id: port-reefer-monitor-v1
domain: port_services
asset_type: refrigerated_container
metrics:
  cargo_temperature:
    source_field: cargo_temp
    unit: Cel
  door_state:
    source_field: door_open
    unit: boolean
  battery:
    source_field: battery_v
    unit: V
alert_rules:
  temperature_exception:
    condition: cargo_temperature outside approved_band
    response: create_exception_and_notify
~~~

These examples are specifications, not device-decoder instructions or approved thresholds. Confirm the actual sensor payload, unit, valid range, reporting interval, stale-data rule, and business response with the domain owner before implementation.

## 2.3 Identifier hierarchy

Do not use the radio identifier as the business identity:

~~~text
device_eui
  -> device_id
  -> asset_id
  -> zone_id
  -> site_id
  -> organization_id
~~~

Reasons:

- a device can be replaced while the asset remains;
- an asset can move between zones;
- a sensor can be temporarily mounted for a survey;
- a port container can move through many sites;
- an agriculture field can be replanted while the zone remains;
- a gateway is infrastructure, not the asset being measured.

Keep an effective-from and effective-to period for device-to-asset assignments.

## 2.4 Define the metric dictionary

For every metric, define the fields below. The dictionary is consumed by payload validation, TimescaleDB normalization, Grafana units, alert thresholds, retention, and external adapters:

| Field | Example |
|---|---|
| Canonical name | cargo_temperature |
| Source field | cargo_temp |
| Unit | degrees Celsius |
| Data type | decimal |
| Valid range | domain-approved |
| Sampling interval | 15 minutes |
| Accuracy | vendor specification |
| Calibration interval | domain-approved |
| Quality states | measured, missing, invalid, estimated |
| Retention | operational and legal decision |
| Alert owner | named team |
| External mapping | system field or API |

Units must be stored explicitly. Do not infer Fahrenheit, Celsius, volts, percentage, or millimeters from a dashboard label.

## 2.5 Domain profile versioning

Version profiles independently from the platform:

~~~text
platform release: 1.4.0
agriculture profile: 1.2.0
port profile: 0.1.0-pilot
decoder: dragino-s31-v1
dashboard: port-reefer-v0.3
~~~

When a profile changes:

1. assign a new profile version and state the reason and affected sites;
2. preserve the previous mapping and decoder so historical data remains interpretable;
3. test representative old and new payloads against the new profile;
4. decide whether historical backfill is valid or would rewrite prior meaning;
5. update dashboards, alerts, and adapters that consume changed fields;
6. deploy one pilot device and compare expected versus stored metrics before wider rollout.

Next: [03-agriculture-to-port-case-study.md](03-agriculture-to-port-case-study.md)
