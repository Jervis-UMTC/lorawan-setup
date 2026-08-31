# trusted-decoder-normalized-v1

This contract defines the deterministic output of the independent EMU-01 Agriculture Kit payload-v2 trusted decoder. It is deliberately separate from the ChirpStack JavaScript codec and Node-RED normalization implementation.

## Input

Exactly 46 raw application bytes using the frozen EMU-01 payload-v2 layout in `test/preparation/sensor/01-configure-rak4631-emulators.md`.

Decoder identity:

```text
decoder_id:      emu01-agriculture-kit-payload-v2
decoder_version: trusted-decoder-go-v1
output_schema:   trusted-decoder-normalized-v1
```

The decoder rejects any payload whose length is not 46 or whose first byte is not payload version `2`.

## Validity semantics

The normalized metrics mirror the reviewed Node-RED measurement mapping, but are produced independently from raw bytes:

```text
bit 0 -> soil_moisture_percent + soil_temperature_c
bit 1 -> uv_index
bit 2 -> barometer_pressure_pa + barometer_temperature_c
bit 3 -> light_veml7700_lux
bit 4 -> light_opt3001_lux
bit 5 -> environment_temperature_c + environment_humidity_percent
         + environment_pressure_pa + environment_gas_resistance_ohm
bit 6 -> rain_wet
battery_v -> no validity bit; value > 0 is measured, 0 is invalid sentinel
```

An invalid metric remains present in the normalized object with `quality="invalid"` and null value. This prevents stale/raw values from becoming silently accepted measurements.

## Normalized digest bytes

`normalized_digest_sha256` is SHA-256 over one UTF-8 JSON object with:

- no whitespace or trailing newline;
- top-level key order exactly: `metrics`, `payload_version`, `schema_version`, `sensor_uptime_ms`, `sensor_validity_bitmap`, `test_sequence`;
- metrics sorted lexicographically by `metric_name`;
- metric key order exactly: `metric_name`, `quality`, `source_field`, `unit`, `value_bool`, `value_number`;
- absent numeric/boolean values represented as JSON `null`;
- finite numeric values rendered in ordinary shortest decimal form with no exponent when the payload-v2 range does not require one.

This is a small versioned deterministic contract for trusted-decoder comparison. It is **not** the separate RFC 8785 `telemetry-attestation-v2` Fabric canonicalization contract.

## Fixed valid vector

```text
raw_hex:
0200000001000003e81595fb2e014100018bcd09980000303900001a850aae17eb000189c00001e240010e74007f

raw_app_data_sha256:
06800936504bb1fa954546c3a6bbde7d3a5f2539590d1f32119b19ae162d7460

normalized_digest_sha256:
594e6f77e8f8f6058a16250e6b30ba96a6766f5813c323c22d93ed6fec7d6118
```

Decoded control values include:

```text
test_sequence=1
sensor_uptime_ms=1000
sensor_validity_bitmap=127
soil_moisture_percent=55.25
soil_temperature_c=-12.34
uv_index=3.21
barometer_pressure_pa=101325
barometer_temperature_c=24.56
light_veml7700_lux=123.45
light_opt3001_lux=67.89
environment_temperature_c=27.34
environment_humidity_percent=61.23
environment_pressure_pa=100800
environment_gas_resistance_ohm=123456
rain_wet=true
battery_v=3.7
```

The two expected SHA-256 values were independently calculated from the frozen raw bytes and normalized byte contract before being pinned in the Go regression test.
