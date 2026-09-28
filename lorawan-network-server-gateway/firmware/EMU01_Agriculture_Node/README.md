# EMU-01 Agriculture Node Firmware

Tracked final-firmware candidate for **EMU-01 / RAK19001 + RAK4631 Core A**. It preserves the frozen 46-byte payload-v2, plain AS923, OTAA, Class A, unconfirmed uplinks, and production scheduler: 60-second local sampling, DevEUI-staggered nominal 5-minute unconfirmed uplinks with ±15-second jitter, plus randomized/rate-limited rain-transition event uplinks.

Before compile: select `WisBlock Core RAK4631 Board`; install the already-proven libraries (`SX126x-Arduino`, `ClosedCube_OPT3001`, `Light_VEML7700`, `Adafruit LPS2X`, `Adafruit Unified Sensor`, `Adafruit BME680`, `RAK12019_LTR390`, `RAK12035_SoilMoisture`); copy `emu01_credentials.example.h` to ignored `emu01_credentials.h` and fill EMU-01's own values locally. Never commit the AppKey.

Healthy hardware acceptance requires: compile/upload, ten cycles with `valid=0x007F`, OTAA, ten Serial-vs-ChirpStack payload comparisons, then sensor preflight. `battery_mv=0` is the frozen USB-only sentinel until a real battery-mV source is validated.

## Reproducible traffic-profile selector

The sketch defines `EMU01_COUNTED_TEST_PROFILE` with default value `0`. An ordinary build therefore remains the accepted production profile. For Chapter IV counted runs only, compile the same source with `EMU01_COUNTED_TEST_PROFILE=1`; this changes timing only and keeps payload-v2, sensors, AS923, OTAA/Class A, credentials, decoder and application path unchanged.

| Profile | Definition | Local sample | Normal uplink | Jitter |
| --- | --- | ---: | ---: | ---: |
| Production | default / `=0` | 60 s | 300 s | +/-15 s |
| Counted test | `=1` | 15 s | 15 s | 0 s |

The boot log is authoritative. Counted-test evidence must contain `EMU01_TRAFFIC_PROFILE=COUNTED_TEST_15S`, sample/normal interval `15000`, and jitter `0`. Production restoration must contain `EMU01_TRAFFIC_PROFILE=PRODUCTION_5MIN`, sample interval `60000`, normal interval `300000`, and jitter `15000`. Archive the exact build settings and compiled artifact SHA-256 with Chapter IV evidence.
