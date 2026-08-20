# Sensor 1 - Program the RAK4631, Configure LoRaWAN, and Prove the Complete Sensor Path

> The filename is retained so existing links do not break. EMU-01 is a real physical Agriculture Kit sensor node. SEC-02 is the separate sensor-verification/security node.

Use this manual **after** all hardware and individual-sensor checks in [assembly/04-verify-all-sensors.md](assembly/04-verify-all-sensors.md) pass.

---

# Architecture

## Final EMU-01 path

```text
 ┌──────────────────── PHYSICAL SENSORS ────────────────────┐
 │ soil  UV  barometer  VEML light  OPT light  BME680  rain │
 └──────────────────────────┬────────────────────────────────┘
                            │ sensor APIs
                            ▼
                   ┌─────────────────┐
                   │ RAK4631 EMU-01  │
                   │ Arduino sketch  │
                   └────────┬────────┘
                            │
            ┌───────────────┼────────────────┐
            │               │                │
            ▼               ▼                ▼
       USB serial      payload v2        LoRaWAN RF
       source log       46 bytes              │
                                               ▼
                                         RAK5146
                                               │
                                               ▼
                                          ChirpStack
                                               │
                          ┌────────────────────┼───────────────┐
                          ▼                    ▼               ▼
                       decoder              Node-RED      gateway logs
                          │
                          ▼
                      TimescaleDB
                          │
                          ▼
                    Fabric evidence
```

## Firmware lifecycle of the two cores

```text
CORE A / EMU-01
Arduino RAK4631
      │
      ├─ individual sensor tests
      ├─ integrated sensor bring-up
      └─ FINAL full-sensor LoRaWAN firmware

CORE B / SEC-02
Arduino RAK4631 on RAK19007
      │
      ├─ Profile A: A=RAK1903-B, B=RAK12010-B,
      │             C=RAK12019-B, D=RAK12011-B,
      │             IO=RAK12023+RAK12035-B
      ├─ POWER COMPLETELY OFF
      ├─ Profile B: A=RAK1906-B, B/C/D=EMPTY,
      │             IO=RAK12005+RAK12030-B
      ├─ save B-copy evidence
      ├─ remove temporary Sensor/IO modules
      │
      └─ only AFTER sensor evidence is complete
                │
                ▼
       stripped security baseline
       RAK19007 + Core B + LoRa antenna
       Sensor A-D = EMPTY; IO = EMPTY
                │
                ▼
       security-node firmware path
       RUI3 conversion if using AT/P2P fixtures
```

Do not convert SEC-02 to RUI3 before its B-copy sensor verification is complete unless you intentionally plan to convert it back to the Arduino firmware family for those tests.

---

# Part A - Final EMU-01 firmware

## Step 1 - Confirm the prerequisites

Do not continue unless:

```text
[ ] EMU-01 = RAK19001 + Core A
[ ] all seven A-set sensor types installed
[ ] fixed RAK19001 map is A=RAK1903, B=EMPTY, C=RAK12019, D=RAK12011, E=RAK1906, F=RAK12010, WisIO1=RAK12023, WisIO2=RAK12005
[ ] Pin Mapper result for that exact map is saved with no unresolved conflict
[ ] LoRa antenna attached
[ ] Arduino IDE installed
[ ] RAKwireless Arduino BSP installed
[ ] basic upload to Core A already proven
[ ] every A-copy sensor worked individually
[ ] ten-cycle integrated sensor bring-up already worked
[ ] every B-copy sensor has been or will be verified before SEC-02 security conversion
```

If a sensor cannot initialize in the integrated bring-up sketch, fix that before adding LoRaWAN logic.

---

## Step 2 - Record and freeze the development environment

Create/update:

```text
chapter4-results/_device-baseline/EMU-01-firmware.txt
```

Record:

```text
Arduino IDE version
RAKwireless Arduino BSP version
selected board = WisBlock Core RAK4631 Board
sensor library versions
LoRaWAN/SX126x library version used by the selected RAK example
final source revision/hash
build date
```

Do not update libraries during a counted experiment group.

---

## Step 3 - Open the final firmware project

Use one dedicated Arduino sketch/project for EMU-01.

Recommended logical layout:

```text
EMU01_Agriculture_Node/
│
├── EMU01_Agriculture_Node.ino
├── sensor_readers.h        # optional helper file
├── payload_v2.h            # optional helper file
└── secrets.h               # LOCAL ONLY - never commit
```

`secrets.h` is only an example local organization. If another secure local provisioning mechanism is used, document it. The important rule is that the legitimate AppKey must not enter Git or result/evidence folders.

---

## Step 4 - Select the board and USB port

In Arduino IDE:

1. select `WisBlock Core RAK4631 Board`;
2. connect only EMU-01 by USB-C data cable;
3. open `Tools -> Port`;
4. select the port that appears for Core A;
5. confirm the physical board label says `EMU-01` before uploading.

**Stop if:** you are not certain which physical core the selected port belongs to.

---

## Step 5 - Start from the known-good integrated sensor sketch

Do not begin by writing LoRaWAN code into an untested blank sketch.

Use the integrated bring-up sketch accepted in the previous manual as the base:

```text
setup()
  ├─ serial initialization
  ├─ soil init
  ├─ UV init
  ├─ barometer init
  ├─ VEML7700 init
  ├─ OPT3001 init
  ├─ BME680 init
  └─ rain init
```

Compile once before adding the LoRaWAN portion.

**Expected result:** the exact full-sensor sketch that already produced ten good sample cycles still builds.

---

## Step 6 - Add the LoRaWAN code using a RAK4631 example as the reference

Use the LoRaWAN example/library supplied or referenced by the pinned RAK4631 BSP instead of writing the radio stack from scratch.

Before compiling `LoRaWAN_OTAA_ABP`, install the LoRaWAN dependency that provides `LoRaWan-RAK4630.h`:

```text
Arduino IDE
  -> Sketch
     -> Include Library
        -> Manage Libraries...
```

Search for:

```text
SX126x-Arduino
```

Install the `SX126x-Arduino` library, then close and reopen the sketch if Arduino IDE does not immediately refresh its include index. The RAK4631-specific header is supplied by this library. If compilation reports:

```text
fatal error: LoRaWan-RAK4630.h: No such file or directory
```

the LoRaWAN library is missing or Arduino IDE is not seeing the installed copy; this is not a ChirpStack, OTAA-key, sensor, or radio-region failure.

The final application must provide:

```text
OTAA
Class A
approved project AS923 configuration
DevEUI
JoinEUI/AppEUI
AppKey
15-second application sampling schedule
unconfirmed/confirmed uplink choice frozen before testing
```

Use the LoRaWAN version actually implemented by the pinned build. Do not claim a different MAC version in ChirpStack or the dissertation.

---

## Step 7 - Keep credentials out of the repository

Prepare locally:

```text
LEGIT_DEV_EUI
LEGIT_JOIN_EUI
LEGIT_APP_KEY
```

Rules:

```text
DevEUI/JoinEUI may be recorded as identifiers
AppKey must not appear in Git
AppKey must not appear in screenshots/results
EMU-01 AppKey must never be copied to SEC-02
EMU-01 session keys must never be copied to SEC-02
SEC-02 may temporarily have its OWN legitimate OTAA AppKey for its separate legitimate-node test
```

The temporary SEC-02 legitimate-node test must use a different DevEUI and different AppKey from EMU-01. After that test is recorded, its temporary legitimate credentials are retired before SEC-02 is converted into the security fixture.

If the AppKey is compiled into the sketch, keep its source definition in an ignored/local secrets file and archive only a **redacted** build record.

---

# Part B - Payload v2

## Step 8 - Freeze the binary layout

Final application payload:

```text
Byte(s)  Field                                  Encoding
0        payload_version                        uint8, fixed 2
1-4      test_sequence                          uint32, big-endian
5-8      sensor_uptime_ms                       uint32, big-endian
9-10     soil_moisture_percent_x100             uint16, big-endian
11-12    soil_temperature_c_x100                int16, big-endian
13-14    uv_index_x100                          uint16, big-endian
15-18    barometer_pressure_pa                  uint32, big-endian
19-20    barometer_temperature_c_x100           int16, big-endian
21-24    light_veml7700_lux_x100                uint32, big-endian
25-28    light_opt3001_lux_x100                 uint32, big-endian
29-30    environment_temperature_c_x100         int16, big-endian
31-32    environment_humidity_percent_x100      uint16, big-endian
33-36    environment_pressure_pa                uint32, big-endian
37-40    environment_gas_resistance_ohm         uint32, big-endian
41       rain_wet                               uint8, 0=dry, 1=wet
42-43    battery_mv                             uint16, big-endian
44-45    sensor_validity_bitmap                 uint16, big-endian
```

Total = **46 bytes**.

Do not silently change field order or size. Any incompatible layout change requires a new payload version and matching decoder.

### UV field check

Before freezing payload v2, prove that the selected RAK12019 driver exposes the quantity you are calling `uv_index`. If it exposes only a different/raw UV quantity, use the correct documented field name and update both firmware and decoder before counted testing rather than mislabeling the value.

### Battery field under USB-only testing

Do not fabricate a battery voltage when no battery measurement exists. If the final firmware cannot obtain a meaningful battery value during USB-only operation, use one documented sentinel consistently (for example `0`) and state that rule in the payload baseline.

---

## Step 9 - Implement the validity bitmap

```text
bit 0 = soil valid
bit 1 = UV valid
bit 2 = barometer valid
bit 3 = VEML7700 valid
bit 4 = OPT3001 valid
bit 5 = RAK1906 environment valid
bit 6 = rain valid
bits 7-15 = 0
```

Healthy full cycle:

```text
0b0000000001111111 = 0x007F
```

If a read fails:

```text
read fails
   │
   ├─ clear that sensor validity bit
   ├─ do NOT silently mark a stale previous sample as valid
   └─ still keep this cycle's test_sequence
```

This prevents a sensor failure from being mistaken for an RF packet loss.

---

## Step 10 - Implement one deterministic sample cycle

Use this exact logical order:

```text
15-second boundary
      │
      ▼
increment test_sequence
      │
      ├─ capture monotonic uptime
      ├─ clear validity bitmap
      │
      ├─ read SOIL -> set bit 0 on success
      ├─ read UV   -> set bit 1 on success
      ├─ read BARO -> set bit 2 on success
      ├─ read VEML -> set bit 3 on success
      ├─ read OPT  -> set bit 4 on success
      ├─ read ENV  -> set bit 5 on success
      ├─ read RAIN -> set bit 6 on success
      │
      ├─ pack 46-byte payload
      ├─ print one serial source line
      └─ request one LoRaWAN uplink
```

Do not increment `test_sequence` once per sensor. Increment it once per scheduled telemetry cycle.

---

## Step 11 - Use a monotonic 15-second scheduler

Target:

```text
T0
T0 + 15 s
T0 + 30 s
T0 + 45 s
...
```

Do not implement the long-run timing as simply:

```text
read sensors
send
wait 15 seconds
```

because sensor work plus the wait can make the actual interval drift beyond 15 seconds.

Use a monotonic next-deadline design. The entire sensor/read/pack/send-start path must complete before the next scheduled deadline.

---

## Step 12 - Print one source line per cycle

Use a stable machine-readable format. Example:

```text
SENSOR_TX,seq=125,uptime_ms=1875000,soil_pct=41.23,soil_temp_c=27.10,uv_index=0.18,baro_pa=100812,baro_temp_c=27.22,light_veml_lux=382.10,light_opt_lux=401.25,env_temp_c=27.44,env_humidity_pct=68.31,env_pressure_pa=100790,env_gas_ohm=92314,rain_wet=0,battery_mv=0,valid=0x007F,join=1,send_started=1,send_status=0
```

Use the actual measured values. The example numbers are formatting examples only.

The serial source log is authoritative for:

```text
test_sequence
physical values sampled for that sequence
validity bitmap
scheduled transmission attempt
reset/rejoin evidence
```

---

# Part C - Build and flash EMU-01

## Step 13 - Compile before upload

In Arduino IDE:

1. selected board = RAK4631;
2. selected port = EMU-01;
3. verify required libraries are installed;
4. compile/verify the sketch;
5. resolve all build errors;
6. save the exact accepted source revision/hash.

Do not update random libraries just to make one compiler error disappear without recording the change.

---

## Step 14 - Upload the final firmware

1. Confirm the LoRa antenna is connected.
2. Confirm EMU-01 is physically connected by USB.
3. Confirm you selected EMU-01's port.
4. Click `Upload`.
5. Wait for successful completion.
6. If the port cannot enter bootloader mode, close Serial Monitor, double-click reset, re-select the bootloader/new port if needed, and retry.
7. Reboot/reset EMU-01 after the successful upload.

**Pass:** the final sketch starts and prints its startup/sensor status to serial.

---

## Step 15 - Verify local sensor behavior before joining LoRaWAN

Watch serial output and require:

```text
all expected sensor initializations reported
RAK1906 stabilization requirement satisfied
soil calibration loaded/applied
both light values present separately
rain state readable
validity = 0x007F during healthy cycles
sequence increases once per 15-second cycle
```

Capture at least ten final-firmware cycles over USB serial before troubleshooting the network.

If the validity bitmap is not `0x007F`, fix the sensor first.

---

# Part D - ChirpStack registration and OTAA

## Current lab handoff - 2026-08-19

```text
SEC-02 Profile A functional verification       = PASS (operator-confirmed)
SEC-02 Profile B functional verification       = PASS (operator-confirmed)
all seven B-copy sensor types                  = FUNCTIONALLY VERIFIED
SEC-02 temporary legitimate DevEUI             = AC1F09FFFE296AEB
SEC-02 legitimate OTAA / ChirpStack connection = PASS (operator-confirmed)
SEC-02 repeated 15-second application uplinks  = PASS (operator-confirmed)
SEC-02 RAK12011 radio telemetry path            = PASS to ChirpStack LoRaWAN-frame level
SEC-02 root AppKey                             = configured locally; NOT recorded here
normal final legitimate ChirpStack node        = EMU-01
next SEC-02 action                             = compare decoded RAK12011 values with Serial for several consecutive frames, then retire temporary legitimate mode
```

SEC-02 is now proven to complete OTAA and continue sending repeated real RAK12011 application uplinks through the RAK5146 gateway into ChirpStack. The accepted implementation sends the first sensor frame shortly after join and then continues on the 15-second application schedule from the normal Arduino `loop()` context. Keep SEC-02 on the Arduino firmware family only until the decoded temperature/pressure comparison is complete. **Never reuse EMU-01's AppKey or session keys.** After the legitimate-node check fully passes, retire the temporary SEC-02 key/device activation before converting it to the security fixture.

## Step 15A - Prove a minimal OTAA join before merging the full sensor payload

Do this once before the final 46-byte sensor firmware. It separates LoRaWAN/ChirpStack faults from sensor-integration faults.

On EMU-01:

```text
LoRa antenna attached
      ↓
Arduino IDE
      ↓
File -> Examples -> LoRaWAN_OTAA_ABP
      ↓
configure AS923 + OTAA + Class A + credentials
      ↓
upload the stock Hello! payload
      ↓
prove JoinRequest -> JoinAccept -> first uplink in ChirpStack
      ↓
only then merge the seven-sensor payload v2 code
```

For the RAK `LoRaWAN_OTAA_ABP` example used by the standard RAK4631 Arduino BSP, configure the application values as follows:

```cpp
LoRaMacRegion_t g_CurrentRegion = LORAMAC_REGION_AS923;
bool doOTAA = true;
lmh_confirm g_CurrentConfirm = LMH_UNCONFIRMED_MSG;
DeviceClass_t g_CurrentClass = CLASS_A;
#define LORAWAN_APP_INTERVAL 15000
```

Use unconfirmed uplinks for the normal 15-second telemetry baseline unless the experiment explicitly freezes a different choice. Do not use the default EU868 region.

**Frozen lab region rule:** the already-configured gateway and ChirpStack server use plain `AS923` / region ID and MQTT prefix `as923`. EMU-01 must therefore use exactly `LORAMAC_REGION_AS923`. Do **not** use `LORAMAC_REGION_AS923_3` for this lab unless the gateway and server are deliberately migrated at the same time.

The RAK example uses these OTAA arrays:

```cpp
uint8_t nodeDeviceEUI[8] = { /* EMU-01 DevEUI, MSB order */ };
uint8_t nodeAppEUI[8]    = { /* EMU-01 JoinEUI/AppEUI, MSB order */ };
uint8_t nodeAppKey[16]   = { /* legitimate AppKey, LOCAL SECRET */ };
```

Do not paste real keys into this Markdown file. Keep the AppKey in a local ignored `secrets.h` or another approved local provisioning path.

### ChirpStack 4.x click path for the minimal join

Before creating the device, verify the registered RAK5146 gateway shows a recent `Last seen`. A device cannot join through a gateway path that is not already healthy.

Create the device profile:

```text
Tenant
  -> Device Profiles
     -> Add device profile
```

Use:

```text
Name: EMU-01 RAK4631 AS923
Region: AS923
Region configuration (if shown): as923 / plain AS923
Activation: OTAA
Device class: Class A
```

For the RAK Arduino example based on `SX126x-Arduino`, the library documents LoRaWAN MAC `1.0.2` and Regional Parameters `1.0.2 Rev B`. Use those values when the ChirpStack form exposes them. If the pinned firmware/library is changed later, re-check and match the profile to the actual implementation rather than keeping these values by habit.

For the first join test, leave the payload codec disabled or use a raw/no-op codec. The stock RAK example sends `Hello!`; the Agriculture Kit 46-byte decoder is installed only after the join path is proven.

Create the application if it does not already exist:

```text
Tenant
  -> Applications
     -> Add application

Name: dissertation-sensors
```

Then create EMU-01:

```text
Applications
  -> dissertation-sensors
     -> Devices
        -> Add device
```

Use:

```text
Name: dissertation-emu-01
DevEUI: <LEGIT_DEV_EUI>
Device profile: EMU-01 RAK4631 AS923
```

In ChirpStack v4, the normal local-join-server flow does not necessarily expose a separate JoinEUI field on the device form. The JoinEUI/AppEUI still exists in the OTAA JoinRequest and must match the value frozen in the EMU-01 firmware. After the device record is created, enter the legitimate root AppKey only on the protected OTAA keys page. Do not place it in screenshots or evidence files.

### Minimal OTAA PASS gate

Open both of these ChirpStack views before resetting EMU-01:

```text
EMU-01 -> LoRaWAN frames
EMU-01 -> Device data
```

Reset/power-cycle EMU-01. Require this order:

```text
JoinRequest
   ↓
JoinAccept
   ↓
Join / activation event
   ↓
UnconfirmedDataUp or ConfirmedDataUp
   ↓
raw Hello! application payload appears
```

If the gateway sees `JoinRequest` but the EMU-01 device page does not, check the DevEUI. If ChirpStack sees the JoinRequest but rejects it, check AppKey, JoinEUI routing, device profile MAC/Regional Parameters, and AS923 configuration. If the minimal Hello payload works, freeze the LoRaWAN identity/profile and continue with the full sensor payload; do not change the radio settings while integrating sensors.

## Step 15B - Temporarily test SEC-02 as its own legitimate sensor node

Use this stage when SEC-02 must first prove that its radio, OTAA implementation, gateway path, ChirpStack registration, and a real sensor payload all work under valid credentials.

Do this **before RUI3/security conversion**. Keep SEC-02 on the already-proven Arduino RAK4631 firmware family.

### Identity separation

Use:

```text
device name = dissertation-sec-02-legit
DevEUI       = unique SEC-02/Core-B DevEUI; MUST differ from EMU-01
JoinEUI      = the lab JoinEUI used by this local OTAA flow; all-zero is acceptable only if that is the frozen lab convention
AppKey       = NEW 16-byte SEC-02-only secret
profile      = dedicated `SEC-02 RAK4631 AS923 LEGIT TEST` profile
class        = A
activation   = OTAA
```

Give SEC-02 its **own device profile** with the same LoRaWAN/region settings as the known-good Arduino RAK4631 profile. This keeps the temporary SEC-02 6-byte test codec isolated from EMU-01's 46-byte payload-v2 codec.

Use:

```text
Tenant
  -> Device Profiles
     -> Add device profile

Name: SEC-02 RAK4631 AS923 LEGIT TEST
Region: AS923
Region configuration: as923 / plain AS923
MAC version: 1.0.2
Regional Parameters: 1.0.2 Rev B
Device class: A
Codec: temporary SEC-02 6-byte barometer decoder
```

Then create a second device under the test application:

```text
Applications
  -> dissertation-sensors
     -> Devices
        -> Add device

Name: dissertation-sec-02-legit
DevEUI: AC1F09FFFE296AEB
Device profile: SEC-02 RAK4631 AS923 LEGIT TEST
```

Do not create SEC-02 by cloning EMU-01 credentials. Current temporary legitimate-node DevEUI: `AC1F09FFFE296AEB`.

After the device record is saved, open SEC-02's `Keys (OTAA)` tab and use ChirpStack's key-generation control to generate a new 128-bit AppKey for SEC-02. Save the generated key in ChirpStack, then copy that exact value only into SEC-02's local firmware secret/provisioning file. Do not paste the key into this repository, screenshots, evidence files, or chat. For LoRaWAN 1.0.x, this is the device's OTAA application root key even if an API/internal field is named `nwkKey`.

If a generated SEC-02 AppKey is accidentally disclosed in chat, screenshots, notes, Git, or evidence, treat that key as retired immediately: use ChirpStack to generate/replace it again before the first OTAA join and never record the exposed value in project documentation.

### Fast radio-first check

First run the documented `LoRaWAN_OTAA_ABP` minimal uplink with SEC-02's credentials:

```text
LORAMAC_REGION_AS923
OTAA = true
Class A
unconfirmed uplink
15-second interval
SEC-02 DevEUI
SEC-02 AppKey
```

Require:

```text
JoinRequest seen by RAK5146
        -> JoinAccept generated by ChirpStack
        -> SEC-02 prints joined
        -> at least one application uplink accepted
```

This isolates OTAA/radio configuration before adding a sensor read.

### Real-sensor check

After the minimal join works, use the compile-ready **SEC-02 legitimate RAK12011 OTAA sensor sketch** in [assembly/04b-emu01-sec02-code-reference.md](assembly/04b-emu01-sec02-code-reference.md). Keep the verified RAK12011-B installed in Sensor D for this check.

**Accepted scheduler rule:** keep RAK12011 I2C reads, Serial printing, payload packing, and `lmh_send()` in the normal Arduino `loop()` execution path. Use a monotonic `millis()` deadline to trigger the first post-join uplink and each later 15-second attempt. Do not move the sensor read and `lmh_send()` into a `TimerEvent_t` callback. During bench troubleshooting, that callback-based design completed OTAA but stalled before normal application uplinks; the loop-based scheduler produced repeated `UnconfirmedDataUp` frames at the intended cadence.

The sketch sends a six-byte payload containing:

```text
bytes 0-1 = RAK12011 temperature C x100, signed int16 big-endian
bytes 2-5 = RAK12011 pressure hPa x100, uint32 big-endian
```

Install the temporary decoder from that same code-reference section or inspect the raw bytes. Require multiple consecutive valid uplinks whose decoded temperature/pressure agree with SEC-02 Serial output within the fixed integer scaling.

Record only non-secret evidence:

```text
SEC-02 legitimate OTAA = PASS/FAIL
SEC-02 DevEUI
join UTC window
JoinRequest observed = yes/no
JoinAccept observed = yes/no
number of consecutive real-sensor uplinks
sample serial temperature/pressure
sample decoded temperature/pressure
```

Do not save the AppKey.

### Exit from temporary legitimate mode

After PASS:

1. stop SEC-02 transmissions;
2. record the legitimate-node result;
3. remove/disable the temporary `dissertation-sec-02-legit` device record when it is no longer needed, or at minimum rotate/retire its AppKey before security testing;
4. do not reuse its legitimate session state for attack fixtures;
5. power SEC-02 off before changing Sensor/IO hardware;
6. continue to Part H only when ready to strip the sensors and convert SEC-02 into the isolated security fixture.

---

## Step 16 - Register EMU-01 in ChirpStack

Create one normal OTAA device using:

```text
device name: dissertation-emu-01
DevEUI: <LEGIT_DEV_EUI>
JoinEUI/AppEUI: <LEGIT_JOIN_EUI>
activation: OTAA
class: A
region: plain AS923 (firmware `LORAMAC_REGION_AS923`; ChirpStack region `as923`)
LoRaWAN MAC version: match final firmware
target interval: 15 seconds
```

Enter the legitimate AppKey only in the approved ChirpStack credential field and the secure firmware/provisioning path.

---

## Step 17 - Perform the first OTAA join

Observe simultaneously:

```text
EMU-01 serial monitor
RAK5146/gateway evidence
ChirpStack device events
```

Expected sequence:

```text
EMU-01 starts
    │
    ▼
JoinRequest transmitted
    │
    ▼
RAK5146 receives
    │
    ▼
ChirpStack validates OTAA
    │
    ▼
JoinAccept
    │
    ▼
EMU-01 joined
```

**Stop if:** sensor reads work but OTAA fails. Troubleshoot antenna, AS923 configuration, EUI/key values, device profile, and gateway reception rather than changing sensor libraries.

---

# Part E - ChirpStack decoder

## Step 18 - Install the payload-v2 codec

Use a dedicated codec that rejects incorrect versions/lengths:

```javascript
function decodeUplink(input) {
  const b = input.bytes;
  if (!b || b.length !== 46) {
    return { errors: ["expected 46-byte Agriculture Kit payload v2"] };
  }
  if (b[0] !== 2) {
    return { errors: ["unsupported Agriculture Kit payload version"] };
  }

  const u16 = (i) => (b[i] << 8) | b[i + 1];
  const s16 = (i) => {
    const v = u16(i);
    return v & 0x8000 ? v - 0x10000 : v;
  };
  const u32 = (i) =>
    ((b[i] * 0x1000000) +
     (b[i + 1] << 16) +
     (b[i + 2] << 8) +
     b[i + 3]) >>> 0;

  const environmentTemperature = s16(29) / 100.0;
  const environmentHumidity = u16(31) / 100.0;

  return {
    data: {
      payload_version: b[0],
      test_sequence: u32(1),
      sensor_uptime_ms: u32(5),
      soil_moisture_percent: u16(9) / 100.0,
      soil_temperature_c: s16(11) / 100.0,
      uv_index: u16(13) / 100.0,
      barometer_pressure_pa: u32(15),
      barometer_temperature_c: s16(19) / 100.0,
      light_veml7700_lux: u32(21) / 100.0,
      light_opt3001_lux: u32(25) / 100.0,
      environment_temperature_c: environmentTemperature,
      environment_humidity_percent: environmentHumidity,
      environment_pressure_pa: u32(33),
      environment_gas_resistance_ohm: u32(37),
      rain_wet: b[41] === 1,
      battery_v: u16(42) / 1000.0,
      sensor_validity_bitmap: u16(44),

      // Existing convenience fields used by the test data path.
      temperature_c: environmentTemperature,
      humidity_percent: environmentHumidity
    }
  };
}
```

If Step 8 changed the UV field semantics/name, change the codec consistently before freezing the payload contract.

---

## Step 19 - Compare serial source to decoded output

For at least ten consecutive sequences:

```text
EMU-01 source line
       │
       ├─ test_sequence
       ├─ every physical sensor field
       └─ validity bitmap
       │
       ▼
ChirpStack decoded object
```

Pass only when the same sequence has the expected values after the defined integer scaling/rounding.

---

# Part F - Node-RED and TimescaleDB

## Step 20 - Keep all physical fields

Store the complete decoded object in `payload_json` and normalize at least:

```text
soil_moisture_percent          %
soil_temperature_c             Cel
uv_index                       1 (only if truly UV index)
barometer_pressure_pa          Pa
barometer_temperature_c        Cel
light_veml7700_lux             lx
light_opt3001_lux              lx
environment_temperature_c      Cel
environment_humidity_percent   %
environment_pressure_pa        Pa
environment_gas_resistance_ohm ohm
rain_wet                       boolean/state
battery_v                      V
```

Compatibility fields:

```text
telemetry.uplinks.temperature_c = environment_temperature_c
telemetry.uplinks.humidity_percent = environment_humidity_percent
telemetry.uplinks.battery_v = battery_v
```

Use quality `measured` for valid physical measurements. Do not label the sensor data `synthetic`.

---

## Step 21 - Prove one complete end-to-end record

Pick one `test_sequence` and prove:

```text
EMU-01 serial source
      │ same seq/value
      ▼
ChirpStack decoder
      │ same seq/value
      ▼
Node-RED
      │ same seq/value
      ▼
TimescaleDB payload_json
      │
      ▼
selected Fabric evidence
```

At minimum verify:

```text
test_sequence
sensor_validity_bitmap
soil value
UV value
barometer value
both light values
RAK1906 values
rain state
```

If any field differs beyond the documented integer scaling/rounding, stop and fix the codec/mapping before counted testing.

---

# Part G - Freeze EMU-01

## Step 22 - Create the final baseline

Save:

```text
chapter4-results/_device-baseline/
  EMU-01-hardware.txt
  EMU-01-firmware.txt
  EMU-01-sensor-map.txt
  EMU-01-payload-contract-v2.txt
  EMU-01-sensor-library-versions.txt
  chirpstack-physical-sensor-codec.js
  firmware-source-or-build-hash.txt
  as923-radio-baseline.txt
```

Do not save keys.

After the baseline is frozen, do not modify the sensor map, payload structure, firmware, BSP, or sensor libraries inside the same counted repetition group.

---

# Part H - SEC-02 after sensor verification

## Step 23 - Confirm every B-copy sensor was already tested

Before changing SEC-02 firmware family, require evidence for:

```text
SOIL-B
UV-B
BARO-B
LIGHT-VEML-B
LIGHT-OPT-B
ENV-B
RAIN-B
```

This is the hard boundary between `sensor verification` and `security node`.

The accepted physical profiles are frozen in [assembly/02b-rak19007-sec02-fixed-profiles.md](assembly/02b-rak19007-sec02-fixed-profiles.md). Before changing firmware family, also require:

```text
[ ] Profile A readings and pin-map evidence saved
[ ] Profile B readings and pin-map evidence saved
[ ] USB/battery/solar disconnected before the final rebuild
[ ] Sensor A = EMPTY
[ ] Sensor B = EMPTY
[ ] Sensor C = EMPTY
[ ] Sensor D = EMPTY
[ ] IO slot = EMPTY
[ ] RAK4631 Core B remains installed
[ ] LoRa antenna remains attached
```

Do not leave a temporary Agriculture Kit sensor on SEC-02 merely because it was used during verification. The normal security baseline is intentionally stripped to reduce unrelated hardware variables.

---

## Step 24 - Decide the security firmware path

The current test manuals use RUI3/AT-command fixtures for invalid OTAA and raw LoRa P2P security transmissions.

If Core B is still a standard Arduino-BSP RAK4631, convert it to RAK4631-R/RUI3 **only after B-copy verification** using RAKwireless' current official RAK4631-R DFU/conversion procedure.

Do not copy old bootloader/DFU package names blindly from a screenshot or old note. Use the currently published RAK conversion guide and record the exact package/version used.

After conversion, verify:

```text
AT+VER=?
AT+BUILDTIME=?
AT+REPOINFO=?
AT+HWMODEL=?
AT+HWID=?
```

Save sanitized output as:

```text
SEC-02-rui3.txt
```

---

## Step 25 - Configure the wrong-AppKey fixture

Rules:

```text
EMU-01 = powered off for this identity-overlap fixture
SEC-02 may use LEGIT_DEV_EUI + LEGIT_JOIN_EUI
SEC-02 MUST use WRONG_APP_KEY
SEC-02 MUST NOT receive LEGIT_APP_KEY
```

Representative RUI3 sequence:

```text
AT+NWM=1
AT+NJM=1
AT+BAND=<APPROVED AS923 BAND VALUE>
AT+DEVEUI=<LEGIT_DEV_EUI>
AT+APPEUI=<LEGIT_JOIN_EUI>
AT+APPKEY=<WRONG_APP_KEY>
AT+JOIN=1:0:10:1
AT+NJS=?
```

Do not save the key value in the evidence transcript.

---

## Step 26 - Configure the unregistered-device fixture

Use:

```text
DevEUI = <UNREGISTERED_DEV_EUI>
JoinEUI = dedicated test JoinEUI
AppKey = dedicated test fixture key
```

Confirm the test DevEUI does **not** exist in ChirpStack before counting an unregistered-device attempt.

---

## Step 27 - Prepare raw LoRa P2P mode

Representative RUI3 controls:

```text
AT+NWM=0
AT+P2P=<freq>:<sf>:<bw>:<cr>:<preamble>:<power>
AT+SYNCWORD=<captured/required LoRaWAN-compatible value>
AT+IQINVER=<uplink-compatible value>
AT+PCRYPT=0
AT+PRECV=0
AT+PSEND=<RAW_PHYPAYLOAD_HEX>
```

Do not guess RF settings. Copy frequency/data-rate-related parameters from the actual legitimate captured packet/gateway evidence used by the authorized test.

---

## Step 28 - Prove SEC-02 RF reception before counted replay/spoof tests

```text
SEC-02 raw transmit
      │
      ▼
RAK5146 receives RF
      │
      ▼
gateway evidence saved
```

If RAK5146 does not receive the rehearsal frame, replay/spoofing tests are blocked even if EMU-01 LoRaWAN works normally.

---

# Final setup acceptance before sensor preflight

Do not enter counted execution from this manual. First satisfy this setup gate, then run the dedicated sensor preflight:

```text
[ ] both RAK4631 cores have permanent identities/labels
[ ] all A/B direct sensors were physically verified
[ ] EMU-01 keeps complete A-set installed
[ ] final Arduino firmware uploaded to EMU-01
[ ] validity bitmap = 0x007F during healthy pre-run cycles
[ ] payload v2 frozen at 46 bytes
[ ] 15-second monotonic schedule proven
[ ] source log matches ChirpStack decoder for ten sequences
[ ] EMU-01 OTAA join succeeds
[ ] one physical-sensor record reaches TimescaleDB
[ ] one selected record completes the Fabric evidence path
[ ] firmware/BSP/library versions are recorded
[ ] no legitimate keys are present in Git/evidence/SEC-02
[ ] SEC-02 B-copy verification completed before security conversion
[ ] SEC-02 wrong-AppKey fixture works
[ ] SEC-02 unregistered-device fixture works
[ ] SEC-02 raw LoRa frame is received by RAK5146
```

When this setup gate passes, continue to [preflight/00-README.md](preflight/00-README.md). The preflight re-tests the **frozen final configuration as one system** and must produce `SENSOR_PREFLIGHT_STATUS=GO` before Execution 01 begins.

## Official references

- RAK4631 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak4631/quickstart/`
- RAK4631 overview: `https://docs.rakwireless.com/product-categories/wisblock/rak4631/overview/`
- WisBlock quick start: `https://docs.rakwireless.com/product-categories/wisblock/quickstart/`
- RAK4631-R conversion / DFU: `https://docs.rakwireless.com/product-categories/wisblock/rak4631-r/dfu/`
- RUI3 AT commands: `https://docs.rakwireless.com/product-categories/software-apis-and-libraries/rui3/at-command-manual/`
- Agriculture Kit: `https://docs.rakwireless.com/product-categories/wisblock/kit7-agriculture/overview/`
