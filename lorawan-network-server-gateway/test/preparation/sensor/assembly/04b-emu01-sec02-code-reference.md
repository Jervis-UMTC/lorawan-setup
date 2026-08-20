# Sensor Assembly 4B - EMU-01 and SEC-02 Arduino Code Reference

This file is the **copy/paste code reference** for the Arduino sketches used while bringing up and verifying EMU-01 and SEC-02.

## Repository rule: no chat-only test code

Any Arduino sketch used to accept EMU-01 or SEC-02 must exist in this repository before its result is treated as part of the test baseline.

If a sketch is changed during troubleshooting:

1. make the change here or in the specifically linked firmware manual;
2. compile/upload that documented version;
3. record the result;
4. do not rely on a chat transcript as the only copy of working code.

This file covers **bench/core/sensor verification code**. Final EMU-01 LoRaWAN provisioning, payload-v2 rules, decoder code, and SEC-02 security/RUI3 commands remain in [../01-configure-rak4631-emulators.md](../01-configure-rak4631-emulators.md).

Do not put AppKeys or LoRaWAN session keys in this file.

---

# 1. Arduino target used for both nodes

Even when the radio module itself is visibly marked `RAK4630`, select the complete WisBlock Core target:

```text
Tools
  -> Board
     -> RAKwireless nRF Boards
        -> WisBlock Core RAK4631 Board
```

Use Serial Monitor at:

```text
115200 baud
```

The current lab BSP uses `Adafruit_TinyUSB.h` in these custom sketches because it fixed the observed USB-Serial linker failure on the installed RAKwireless nRF52 BSP.

---

# 2. Which sketch can run on which physical node

```text
EMU-01 / RAK19001
  RAK1903   -> yes
  RAK12010  -> yes
  RAK12011  -> yes
  RAK1906   -> yes
  RAK12019  -> yes
  RAK12035  -> yes, through RAK12023
  RAK12005  -> yes, with RAK12030

SEC-02 / RAK19007 Profile A
  RAK1903   -> Sensor A
  RAK12010  -> Sensor B
  RAK12019  -> Sensor C
  RAK12011  -> Sensor D
  RAK12035  -> IO through RAK12023

SEC-02 / RAK19007 Profile B
  RAK1906   -> Sensor A
  RAK12005  -> IO with RAK12030
```

Do not run a sensor acceptance sketch against a SEC-02 profile in which that sensor is not physically installed.

For the shared sensor sketches below, set exactly one node label before compiling:

```cpp
#define NODE_NAME "EMU-01"
```

or:

```cpp
#define NODE_NAME "SEC-02"
```

Changing `NODE_NAME` changes only the Serial label. It does not change sensor wiring or GPIO ownership.

---

# 3. Core/USB sanity sketch - EMU-01

```cpp
#include <Adafruit_TinyUSB.h>

void setup()
{
  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("EMU-01 RAK4631 STARTED");
  Serial.println("USB SERIAL TEST = PASS");
  Serial.println("==============================");
}

void loop()
{
  Serial.println("EMU-01 is alive");
  delay(1000);
}
```

Expected repeating line:

```text
EMU-01 is alive
```

---

# 4. Core/USB sanity sketch - SEC-02

```cpp
#include <Adafruit_TinyUSB.h>

void setup()
{
  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("SEC-02 RAK4631 STARTED");
  Serial.println("USB SERIAL TEST = PASS");
  Serial.println("==============================");
}

void loop()
{
  Serial.println("SEC-02 is alive");
  delay(1000);
}
```

Expected repeating line:

```text
SEC-02 is alive
```

This sanity sketch intentionally contains no sensor or LoRaWAN code. A PASS isolates the basic path:

```text
Arduino build -> bootloader/DFU -> Core -> USB Serial
```

---

# 5. RAK1903 / OPT3001 light test

Use on:

```text
EMU-01 -> Sensor A
SEC-02 -> Profile A, Sensor A
```

Required library/header:

```text
ClosedCube_OPT3001.h
```

Sketch:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include <ClosedCube_OPT3001.h>

#define NODE_NAME "EMU-01"  // Change to "SEC-02" when testing SEC-02.
#define OPT3001_ADDRESS 0x44

ClosedCube_OPT3001 lightSensor;

void setup()
{
  // WB_IO2 enables the switched 3V3_S sensor rail used by this lab setup.
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.print(NODE_NAME);
  Serial.println(" RAK1903 TEST");
  Serial.println("==============================");

  Wire.begin();
  lightSensor.begin(OPT3001_ADDRESS);

  Serial.print("Manufacturer ID: 0x");
  Serial.println(lightSensor.readManufacturerID(), HEX);

  Serial.print("Device ID: 0x");
  Serial.println(lightSensor.readDeviceID(), HEX);

  OPT3001_Config config;
  config.RangeNumber = B1100;
  config.ConvertionTime = B0;
  config.Latch = B1;
  config.ModeOfConversionOperation = B11;

  OPT3001_ErrorCode error = lightSensor.writeConfig(config);

  if (error == NO_ERROR)
  {
    Serial.println("RAK1903 configuration = PASS");
  }
  else
  {
    Serial.print("RAK1903 configuration ERROR = ");
    Serial.println(error);
  }
}

void loop()
{
  OPT3001 result = lightSensor.readResult();

  if (result.error == NO_ERROR)
  {
    Serial.print("RAK1903 light = ");
    Serial.print(result.lux);
    Serial.println(" lux");
  }
  else
  {
    Serial.print("RAK1903 read ERROR = ");
    Serial.println(result.error);
  }

  delay(1000);
}
```

PASS requires valid repeated lux values plus an obvious cover/uncover response.

---

# 6. RAK12010 / VEML7700 light test

Use on:

```text
EMU-01 -> Sensor F
SEC-02 -> Profile A, Sensor B
```

Required library/header:

```text
Light_VEML7700.h
```

Sketch:

```cpp
#include <Adafruit_TinyUSB.h>
#include "Light_VEML7700.h"

#define NODE_NAME "EMU-01"  // Change to "SEC-02" when testing SEC-02.

Light_VEML7700 lightSensor = Light_VEML7700();

void setup()
{
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.print(NODE_NAME);
  Serial.println(" RAK12010 TEST");
  Serial.println("==============================");

  if (!lightSensor.begin())
  {
    Serial.println("RAK12010 NOT FOUND");
    Serial.println("TEST = FAIL");

    while (1)
    {
      delay(1000);
    }
  }

  lightSensor.setGain(VEML7700_GAIN_1);
  lightSensor.setIntegrationTime(VEML7700_IT_800MS);

  Serial.println("RAK12010 detected");
  Serial.println("TEST INITIALIZATION = PASS");
}

void loop()
{
  Serial.print("RAK12010 light = ");
  Serial.print(lightSensor.readLux());
  Serial.println(" lux");
  delay(1000);
}
```

PASS requires initialization plus repeated lux values and a clear cover/uncover response.

---

# 7. RAK12011 / LPS33HW barometer test

Use on:

```text
EMU-01 -> Sensor D
SEC-02 -> Profile A, Sensor D
```

Required headers:

```text
Adafruit_LPS2X.h
Adafruit_Sensor.h
```

Sketch:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include <Adafruit_LPS2X.h>
#include <Adafruit_Sensor.h>

#define NODE_NAME "EMU-01"  // Change to "SEC-02" when testing SEC-02.

Adafruit_LPS22 barometer;

void setup()
{
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.print(NODE_NAME);
  Serial.println(" RAK12011 TEST");
  Serial.println("==============================");

  Wire.begin();

  if (!barometer.begin_I2C(0x5D))
  {
    Serial.println("RAK12011 NOT FOUND");
    Serial.println("TEST = FAIL");

    while (1)
    {
      delay(1000);
    }
  }

  barometer.setDataRate(LPS22_RATE_10_HZ);

  Serial.println("RAK12011 detected");
  Serial.println("TEST INITIALIZATION = PASS");
}

void loop()
{
  sensors_event_t temperature;
  sensors_event_t pressure;

  barometer.getEvent(&pressure, &temperature);

  Serial.print("RAK12011 temperature = ");
  Serial.print(temperature.temperature);
  Serial.println(" C");

  Serial.print("RAK12011 pressure = ");
  Serial.print(pressure.pressure);
  Serial.println(" hPa");

  Serial.println();
  delay(1000);
}
```

PASS requires sensor detection and repeated plausible numeric pressure/temperature values.

---

# 8. RAK1906 / BME680 environment test

Use on:

```text
EMU-01 -> Sensor E
SEC-02 -> Profile B, Sensor A
```

Required headers:

```text
Adafruit_Sensor.h
Adafruit_BME680.h
```

Sketch:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>

#define NODE_NAME "EMU-01"  // Change to "SEC-02" when testing SEC-02.

Adafruit_BME680 bme;

void setup()
{
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.print(NODE_NAME);
  Serial.println(" RAK1906 TEST");
  Serial.println("==============================");

  Wire.begin();

  if (!bme.begin(0x76))
  {
    Serial.println("RAK1906 NOT FOUND");
    Serial.println("TEST = FAIL");

    while (1)
    {
      delay(1000);
    }
  }

  bme.setTemperatureOversampling(BME680_OS_8X);
  bme.setHumidityOversampling(BME680_OS_2X);
  bme.setPressureOversampling(BME680_OS_4X);
  bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
  bme.setGasHeater(320, 150);

  Serial.println("RAK1906 detected");
  Serial.println("TEST INITIALIZATION = PASS");
}

void loop()
{
  if (!bme.performReading())
  {
    Serial.println("RAK1906 reading FAILED");
    delay(5000);
    return;
  }

  Serial.print("RAK1906 temperature = ");
  Serial.print(bme.temperature);
  Serial.println(" C");

  Serial.print("RAK1906 humidity = ");
  Serial.print(bme.humidity);
  Serial.println(" %");

  Serial.print("RAK1906 pressure = ");
  Serial.print(bme.pressure / 100.0);
  Serial.println(" hPa");

  Serial.print("RAK1906 gas resistance = ");
  Serial.print(bme.gas_resistance);
  Serial.println(" ohm");

  Serial.println();
  delay(5000);
}
```

For the first use of each BME680 copy, follow the burn-in/stabilization rule in the verification manual before treating gas-resistance values as baseline evidence.

---

# 9. RAK12019 / LTR390 UV test

Use on:

```text
EMU-01 -> Sensor C
SEC-02 -> Profile A, Sensor C
```

Required header:

```text
UVlight_LTR390.h
```

Sketch:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include "UVlight_LTR390.h"

#define NODE_NAME "EMU-01"  // Change to "SEC-02" when testing SEC-02.

UVlight_LTR390 uvSensor = UVlight_LTR390();

void setup()
{
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.print(NODE_NAME);
  Serial.println(" RAK12019 UV TEST");
  Serial.println("==============================");

  Wire.begin();

  if (!uvSensor.init())
  {
    Serial.println("RAK12019 NOT FOUND");
    Serial.println("TEST = FAIL");

    while (1)
    {
      delay(1000);
    }
  }

  Serial.println("RAK12019 detected");

  uvSensor.setMode(LTR390_MODE_UVS);

  if (uvSensor.getMode() == LTR390_MODE_UVS)
  {
    Serial.println("UV MODE = PASS");
  }
  else
  {
    Serial.println("UV MODE = FAIL");
  }

  uvSensor.setGain(LTR390_GAIN_3);
  uvSensor.setResolution(LTR390_RESOLUTION_16BIT);

  Serial.println("TEST INITIALIZATION = PASS");
}

void loop()
{
  if (uvSensor.newDataAvailable())
  {
    float uvi = uvSensor.getUVI();
    uint32_t rawUvs = uvSensor.readUVS();

    Serial.print("RAK12019 UVI = ");
    Serial.println(uvi);

    Serial.print("RAK12019 raw UVS = ");
    Serial.println(rawUvs);

    Serial.println();
  }

  delay(500);
}
```

The project payload uses `getUVI()` for the UV-index field. Do not substitute raw `readUVS()` for the field named `uv_index`.

---

# 10. RAK12023 + RAK12035 soil read-status diagnostic

Use on:

```text
EMU-01 -> RAK12023 + SOIL-A
SEC-02 -> Profile A IO + SOIL-B
```

Connect exactly one RAK12035 probe.

Required header:

```text
RAK12035_SoilMoisture.h
```

This sketch is deliberately **read-only**. It does not overwrite dry/wet calibration values.

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include "RAK12035_SoilMoisture.h"

#define NODE_NAME "EMU-01"  // Change to "SEC-02" when testing SEC-02.

RAK12035 soilSensor;

void setup()
{
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("====================================");
  Serial.print(NODE_NAME);
  Serial.println(" RAK12035 READ DIAGNOSTIC");
  Serial.println("====================================");

  Wire.begin();
  soilSensor.begin(true);

  Serial.print("RAK12035 library I2C address = 0x");
  Serial.println(soilSensor.get_sensor_addr(), HEX);

  uint8_t version = 0;
  bool versionOK = soilSensor.get_sensor_version(&version);

  Serial.print("firmware read status = ");
  Serial.println(versionOK ? "PASS" : "FAIL");

  if (versionOK)
  {
    Serial.print("RAK12035 firmware version = 0x");
    Serial.println(version, HEX);
  }

  uint16_t storedDry = 0;
  uint16_t storedWet = 0;

  bool dryOK = soilSensor.get_dry_cal(&storedDry);
  bool wetOK = soilSensor.get_wet_cal(&storedWet);

  Serial.print("stored dry read status = ");
  Serial.println(dryOK ? "PASS" : "FAIL");
  if (dryOK)
  {
    Serial.print("stored dry calibration = ");
    Serial.println(storedDry);
  }

  Serial.print("stored wet read status = ");
  Serial.println(wetOK ? "PASS" : "FAIL");
  if (wetOK)
  {
    Serial.print("stored wet calibration = ");
    Serial.println(storedWet);
  }

  Serial.println();
}

void loop()
{
  uint16_t capacitance = 0;
  uint16_t temperature = 0;
  uint8_t moisture = 0;

  bool capOK = soilSensor.get_sensor_capacitance(&capacitance);
  bool moistureOK = soilSensor.get_sensor_moisture(&moisture);
  bool temperatureOK = soilSensor.get_sensor_temperature(&temperature);

  Serial.print("capacitance status = ");
  Serial.print(capOK ? "PASS" : "FAIL");
  if (capOK)
  {
    Serial.print(" | value = ");
    Serial.print(capacitance);
  }
  Serial.println();

  Serial.print("moisture status = ");
  Serial.print(moistureOK ? "PASS" : "FAIL");
  if (moistureOK)
  {
    Serial.print(" | value = ");
    Serial.print(moisture);
    Serial.print(" %");
  }
  Serial.println();

  Serial.print("temperature status = ");
  Serial.print(temperatureOK ? "PASS" : "FAIL");
  if (temperatureOK)
  {
    Serial.print(" | value = ");
    Serial.print(temperature / 10.0);
    Serial.print(" C");
  }
  Serial.println();

  Serial.println("------------------------------------");
  delay(1000);
}
```

Only after raw capacitance is healthy should calibration be written.

For calibration, the project currently uses the installed RAK library example:

```text
Arduino IDE
  -> File
     -> Examples
        -> RAK12035_SoilMoisture
           -> RAK12035_Calibration
```

The repository does not currently contain the vendor example source itself, so this manual does not invent or silently fork that code. If the official calibration example is copied/customized for this project later, the exact accepted source must be added to this file before it becomes the project baseline.

---

# 11. RAK12005 + RAK12030 rain test

Use on:

```text
EMU-01 -> RAK12005 + RAIN-A
SEC-02 -> Profile B IO + RAIN-B
```

Sketch:

```cpp
#include <Adafruit_TinyUSB.h>

#define NODE_NAME "EMU-01"  // Change to "SEC-02" when testing SEC-02.
#define RAIN_PIN WB_IO6

void setup()
{
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  pinMode(RAIN_PIN, INPUT);

  Serial.println();
  Serial.println("==============================");
  Serial.print(NODE_NAME);
  Serial.println(" RAK12005 RAIN TEST");
  Serial.println("==============================");
  Serial.println("DRY pad should report rain_wet = 0");
  Serial.println("WET pad should report rain_wet = 1");
  Serial.println();
}

void loop()
{
  int rainState = digitalRead(RAIN_PIN);

  Serial.print("RAK12005 digital state = ");
  Serial.println(rainState == HIGH ? "HIGH" : "LOW");

  Serial.print("rain_wet = ");
  Serial.println(rainState == HIGH ? 1 : 0);

  Serial.println();
  delay(1000);
}
```

Wet only the RAK12030 sensing pad. Keep the RAK12005, base, core, and connectors dry.

PASS sequence:

```text
dry -> rain_wet 0
wet -> rain_wet 1
dry again -> rain_wet 0
```

---

# 12. EMU-01 final LoRaWAN constants that must stay documented

The final EMU-01 LoRaWAN firmware workflow, payload contract, OTAA provisioning, and decoder are developed/frozen in [../01-configure-rak4631-emulators.md](../01-configure-rak4631-emulators.md). These application constants are mandatory for the current lab baseline:

```cpp
LoRaMacRegion_t g_CurrentRegion = LORAMAC_REGION_AS923;
bool doOTAA = true;
lmh_confirm g_CurrentConfirm = LMH_UNCONFIRMED_MSG;
DeviceClass_t g_CurrentClass = CLASS_A;
#define LORAWAN_APP_INTERVAL 15000
```

OTAA values must use local secret/provisioning storage, not real keys copied into Markdown:

```cpp
uint8_t nodeDeviceEUI[8] = { /* EMU-01 DevEUI, MSB order */ };
uint8_t nodeAppEUI[8]    = { /* EMU-01 JoinEUI/AppEUI, MSB order */ };
uint8_t nodeAppKey[16]   = { /* legitimate AppKey, LOCAL SECRET */ };
```

The current lab region is plain `AS923`; do not change only the sensor node to `AS923_3`.

---

# 12A. SEC-02 temporary legitimate OTAA sensor test - RAK12011-B

Use this **before security/RUI3 conversion** when SEC-02 must first prove that it can operate as a normal legitimate LoRaWAN sensor.

**Accepted bench result - 2026-08-19:** this loop-scheduled implementation completed OTAA and produced repeated `UnconfirmedDataUp` frames in ChirpStack at approximately 15-second intervals. This is the authoritative SEC-02 legitimate-sensor scheduler. An earlier `TimerEvent_t` version that performed the RAK12011 read and `lmh_send()` inside the timer callback joined successfully but did not continue normal application uplinks; do not restore that callback-based send path.

Physical requirement:

```text
SEC-02 / RAK19007
Core B = installed
RAK12011-B = Sensor D
LoRa antenna = attached
USB-C = programming / Serial
```

Use a **unique SEC-02 DevEUI and unique SEC-02 AppKey**. Never place EMU-01's AppKey or session keys in this sketch.

For the easiest bench workflow, use **one `.ino` file only**. Do not create `secrets.h` for this temporary test. Paste SEC-02's 32-character ChirpStack AppKey into the local `SEC02_APPKEY_HEX` line before upload. Keep the real key out of Git and retained evidence.

Compile-ready `.ino`:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_LPS2X.h>
#include <Adafruit_Sensor.h>
#include <LoRaWan-RAK4630.h>

#define APP_INTERVAL_MS 15000
#define APP_PORT 2
#define PAYLOAD_SIZE 6

// SEC-02 DevEUI = AC1F09FFFE296AEB
uint8_t nodeDeviceEUI[8] = {
  0xAC, 0x1F, 0x09, 0xFF,
  0xFE, 0x29, 0x6A, 0xEB
};

// Frozen lab JoinEUI = all zeroes.
uint8_t nodeAppEUI[8] = {
  0x00, 0x00, 0x00, 0x00,
  0x00, 0x00, 0x00, 0x00
};

// Paste the 32-character AppKey generated for SEC-02 in ChirpStack.
// Example format only: "00112233445566778899AABBCCDDEEFF"
const char SEC02_APPKEY_HEX[] = "PASTE_SEC02_APPKEY_HERE";
uint8_t nodeAppKey[16];

Adafruit_LPS22 barometer;

// Keep sensor I2C reads, Serial output, and lmh_send() in loop() rather than
// inside a timer callback. This avoids blocking or re-entrancy problems in
// callback context on the RAK4631 LoRaWAN stack.
static volatile bool networkJoined = false;
static uint32_t nextTxAt = 0;

static uint8_t txBuffer[PAYLOAD_SIZE];
static lmh_app_data_t txData = {txBuffer, 0, 0, 0, 0};

static uint8_t hexNibble(char c)
{
  if (c >= '0' && c <= '9') return (uint8_t)(c - '0');
  if (c >= 'a' && c <= 'f') return (uint8_t)(c - 'a' + 10);
  if (c >= 'A' && c <= 'F') return (uint8_t)(c - 'A' + 10);
  return 0xFF;
}

static bool parseAppKey()
{
  if (strlen(SEC02_APPKEY_HEX) != 32) return false;

  for (uint8_t i = 0; i < 16; i++)
  {
    uint8_t hi = hexNibble(SEC02_APPKEY_HEX[i * 2]);
    uint8_t lo = hexNibble(SEC02_APPKEY_HEX[i * 2 + 1]);

    if (hi == 0xFF || lo == 0xFF) return false;
    nodeAppKey[i] = (uint8_t)((hi << 4) | lo);
  }

  return true;
}

static lmh_param_t loraParams = {
  LORAWAN_ADR_ON,
  DR_0,
  LORAWAN_PUBLIC_NETWORK,
  3,
  TX_POWER_5,
  LORAWAN_DUTYCYCLE_OFF
};

static void sendSensorFrame();

static void rxHandler(lmh_app_data_t *data)
{
  Serial.print("downlink port = ");
  Serial.println(data->port);
}

static void joinedHandler()
{
  Serial.println("==============================");
  Serial.println("SEC-02 OTAA JOIN = PASS");
  Serial.println("==============================");

  // The stack was initialized as CLASS_A in lmh_init(), so do not issue a
  // redundant class request here. Schedule the first real sensor uplink for
  // loop() two seconds after a successful join.
  nextTxAt = millis() + 2000UL;
  networkJoined = true;
  Serial.println("SEC-02 application TX scheduler armed");
}

static void joinFailedHandler()
{
  Serial.println("SEC-02 OTAA JOIN = FAIL");
}

static void classHandler(DeviceClass_t newClass)
{
  Serial.print("LoRaWAN class = ");
  Serial.println("ABC"[newClass]);
}

static lmh_callback_t loraCallbacks = {
  BoardGetBatteryLevel,
  BoardGetUniqueId,
  BoardGetRandomSeed,
  rxHandler,
  joinedHandler,
  classHandler,
  joinFailedHandler
};

void setup()
{
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Wire.begin();

  if (!barometer.begin_I2C(0x5D))
  {
    Serial.println("RAK12011 NOT FOUND - STOP");
    while (1)
    {
      delay(1000);
    }
  }

  barometer.setDataRate(LPS22_RATE_10_HZ);
  Serial.println("RAK12011 detected");

  if (!parseAppKey())
  {
    Serial.println("APPKEY FORMAT ERROR - paste exactly 32 hex characters");
    while (1)
    {
      delay(1000);
    }
  }

  Serial.println("SEC-02 AppKey format = PASS");

  lora_rak4630_init();

  lmh_setDevEui(nodeDeviceEUI);
  lmh_setAppEui(nodeAppEUI);
  lmh_setAppKey(nodeAppKey);

  uint32_t status = lmh_init(
    &loraCallbacks,
    loraParams,
    true,
    CLASS_A,
    LORAMAC_REGION_AS923
  );

  if (status != 0)
  {
    Serial.print("lmh_init failed = ");
    Serial.println(status);
    while (1)
    {
      delay(1000);
    }
  }

  Serial.println("SEC-02 starting legitimate OTAA join...");
  lmh_join();
}

void loop()
{
  if (networkJoined && lmh_join_status_get() == LMH_SET)
  {
    uint32_t now = millis();

    if ((int32_t)(now - nextTxAt) >= 0)
    {
      // Schedule the next attempt before doing sensor/radio work so a slow
      // read or transmit cannot cause an immediate duplicate send.
      nextTxAt = now + APP_INTERVAL_MS;
      sendSensorFrame();
    }
  }

  delay(10);
}

static void sendSensorFrame()
{
  if (lmh_join_status_get() != LMH_SET)
  {
    Serial.println("not joined - sensor frame skipped");
    return;
  }

  sensors_event_t temperature;
  sensors_event_t pressure;
  barometer.getEvent(&pressure, &temperature);

  int16_t tempX100 = (int16_t)round(temperature.temperature * 100.0f);
  uint32_t pressureX100 = (uint32_t)round(pressure.pressure * 100.0f);

  txBuffer[0] = (uint8_t)((tempX100 >> 8) & 0xFF);
  txBuffer[1] = (uint8_t)(tempX100 & 0xFF);
  txBuffer[2] = (uint8_t)((pressureX100 >> 24) & 0xFF);
  txBuffer[3] = (uint8_t)((pressureX100 >> 16) & 0xFF);
  txBuffer[4] = (uint8_t)((pressureX100 >> 8) & 0xFF);
  txBuffer[5] = (uint8_t)(pressureX100 & 0xFF);

  txData.port = APP_PORT;
  txData.buffsize = PAYLOAD_SIZE;

  Serial.print("temperature_c = ");
  Serial.println(temperature.temperature);
  Serial.print("pressure_hpa = ");
  Serial.println(pressure.pressure);

  lmh_error_status result = lmh_send(&txData, LMH_UNCONFIRMED_MSG);

  if (result == LMH_SUCCESS)
  {
    Serial.println("sensor uplink queued = PASS");
  }
  else
  {
    Serial.print("sensor uplink queued = FAIL code ");
    Serial.println(result);
  }
}

```

Temporary ChirpStack decoder for this SEC-02 test:

```javascript
function decodeUplink(input) {
  const b = input.bytes;

  if (!b || b.length !== 6) {
    return { errors: ["expected 6-byte SEC-02 barometer test payload"] };
  }

  let t = (b[0] << 8) | b[1];
  if (t & 0x8000) t -= 0x10000;

  const p = (
    (b[2] * 0x1000000) +
    (b[3] << 16) +
    (b[4] << 8) +
    b[5]
  ) >>> 0;

  return {
    data: {
      node: "SEC-02",
      barometer_temperature_c: t / 100.0,
      barometer_pressure_hpa: p / 100.0
    }
  };
}
```

PASS requires:

```text
RAK12011 detected
        +
SEC-02 OTAA JOIN = PASS
        +
SEC-02 application TX scheduler armed
        +
ChirpStack shows JoinRequest and JoinAccept
        +
multiple 6-byte UnconfirmedDataUp frames accepted
        +
frame cadence is approximately 15 seconds after the first post-join send
        +
decoded temperature/pressure track Serial output
```

Current bench status:

```text
OTAA JoinRequest / JoinAccept                  = PASS
loop-based first post-join sensor transmission = PASS
repeated ~15-second UnconfirmedDataUp frames   = PASS
remaining legitimate-node gate                = decoded RAK12011 values match Serial for several consecutive frames
```

After this legitimate test, do not carry its AppKey/session state into the security fixtures. Retire/rotate the SEC-02 legitimate credential and then follow the security conversion path below.

---

# 13. SEC-02 code/firmware boundary

SEC-02 stays on the Arduino-compatible firmware family while Profile A and Profile B B-copy sensors are being verified.

Only after all B-copy evidence passes does SEC-02 move to the security-node firmware path. The exact RUI3/AT commands for wrong-AppKey and raw-LoRa/P2P fixtures are documented in [../01-configure-rak4631-emulators.md](../01-configure-rak4631-emulators.md).

Never put EMU-01's legitimate AppKey or legitimate session keys into SEC-02.

---

# 14. Fast operator sequence

For either node:

```text
confirm physical profile
        -> confirm Pin Mapper PASS
        -> select RAK4631 board + correct COM port
        -> run core sanity sketch
        -> run only the sketch for the installed sensor
        -> capture Serial evidence
        -> mark PASS/FAIL
```

For SEC-02 specifically:

```text
Profile A:
  sanity -> RAK1903 -> RAK12010 -> RAK12011 -> RAK12019 -> RAK12035

POWER OFF / rebuild / Pin Mapper again

Profile B:
  sanity -> RAK1906 -> RAK12005
```

If working code changes, update this MD first so the repository remains the source of truth.
