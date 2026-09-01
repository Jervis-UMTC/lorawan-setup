# EMU-01 Agriculture Node Firmware

Tracked final-firmware candidate for **EMU-01 / RAK19001 + RAK4631 Core A**. It preserves the frozen 46-byte payload-v2, plain AS923, OTAA, Class A, unconfirmed uplinks, and monotonic 15-second schedule.

Before compile: select `WisBlock Core RAK4631 Board`; install the already-proven libraries (`SX126x-Arduino`, `ClosedCube_OPT3001`, `Light_VEML7700`, `Adafruit LPS2X`, `Adafruit Unified Sensor`, `Adafruit BME680`, `RAK12019_LTR390`, `RAK12035_SoilMoisture`); copy `emu01_credentials.example.h` to ignored `emu01_credentials.h` and fill EMU-01's own values locally. Never commit the AppKey.

Healthy hardware acceptance requires: compile/upload, ten cycles with `valid=0x007F`, OTAA, ten Serial-vs-ChirpStack payload comparisons, then sensor preflight. `battery_mv=0` is the frozen USB-only sentinel until a real battery-mV source is validated.
