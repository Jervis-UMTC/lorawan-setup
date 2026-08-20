# Sensor Assembly 4A - First-Time Arduino IDE Walkthrough for EMU-01

Use this manual if you are new to Arduino IDE. It turns the short software steps in `04-verify-all-sensors.md` into a click-by-click procedure and explains **why** each step exists.

For actual copy/paste code, use [04b-emu01-sec02-code-reference.md](04b-emu01-sec02-code-reference.md) as the authoritative source for both EMU-01 and SEC-02. This walkthrough may repeat code for teaching context, but a chat-only or undocumented sketch must not become the accepted lab baseline.

This is the recommended first-time path after EMU-01 has been physically assembled and has passed the pre-power inspection.

Do **not** start with ChirpStack or LoRaWAN. First prove the local chain one layer at a time:

```text
physical assembly
      ↓
USB device appears
      ↓
Arduino IDE + RAK BSP
      ↓
sketch compiles
      ↓
RAK4631 accepts firmware
      ↓
RAK4631 executes firmware
      ↓
USB Serial works
      ↓
first real sensor works
      ↓
second real sensor works
      ↓
remaining sensors
      ↓
integrated sensor firmware
      ↓
LoRaWAN / ChirpStack
```

Why this order matters:

```text
If seven sensors + LoRaWAN are added immediately and something fails,
we do not know whether the fault is:

Arduino setup?
USB cable?
bootloader?
RAK4631?
sensor library?
I2C?
wrong slot?
bad sensor?
LoRaWAN?

Testing one layer at a time makes the first failing layer obvious.
```

---

# Part 1 - Confirm EMU-01 before USB power

The permanent EMU-01 map must be:

```text
RAK19001 / EMU-01

Sensor A = RAK1903   OPT3001 ambient light
Sensor B = EMPTY / NA
Sensor C = RAK12019  UV
Sensor D = RAK12011  barometer
Sensor E = RAK1906   BME680 environment
Sensor F = RAK12010  VEML7700 ambient light

WisIO 1  = RAK12023 -> RAK12035 soil probe
WisIO 2  = RAK12005 -> RAK12030 rain pad

CPU      = RAK4631
```

Before connecting USB:

```text
[ ] RAK4631 fully seated in CPU slot
[ ] retaining screws installed
[ ] no loose screw or conductive debris
[ ] LoRa antenna attached to the LoRa RF connector
[ ] Sensor B is empty
[ ] all other modules match the fixed map
[ ] soil/rain electronics are dry
[ ] optical sensors are unobstructed
[ ] BME680 has airflow
```

**Why attach the LoRa antenna now?** Later test sketches or examples can enable the radio. Keeping the correct antenna attached avoids accidentally operating the radio without its intended load.

**Stop if:** any module is in the wrong slot, a connector is partly seated, or anything becomes abnormally hot after power is applied.

---

# Part 2 - First USB connection

Use USB-C only for initial bring-up:

```text
Laptop
   │
USB-C DATA cable
   │
   ▼
RAK19001 + RAK4631
```

Do not add battery or solar during this stage.

## Step 2.1 - Connect EMU-01

1. Keep SEC-02 disconnected.
2. Connect a known-good USB-C **data** cable to EMU-01.
3. Wait for Windows to detect the board.
4. Watch for abnormal heat, smell, smoke, unstable LEDs, or repeated USB disconnects.
5. If anything abnormal occurs, unplug immediately.

**Why use a data cable?** Some USB-C cables provide power only. Arduino programming needs both power and USB data.

---

# Part 3 - Install Arduino IDE and the RAK4631 board support

## Step 3.1 - Install Arduino IDE

1. Download Arduino IDE from the official Arduino distribution.
2. On Windows, prefer the normal Arduino installer rather than the Microsoft Store build if third-party BSP installation causes problems.
3. Start Arduino IDE.

**Pass:** Arduino IDE opens normally.

## Step 3.2 - Add the RAKwireless board package URL

In Arduino IDE:

```text
File
  -> Preferences
     -> Additional Boards Manager URLs
```

Add:

```text
https://raw.githubusercontent.com/RAKwireless/RAKwireless-Arduino-BSP-Index/main/package_rakwireless_index.json
```

If another URL is already present, add the RAK URL as another entry rather than deleting the existing one.

**Why?** Arduino IDE does not know how to compile for a RAK4631 by default. This URL tells Boards Manager where to obtain the RAKwireless board definition, compiler settings, core files, and upload tools.

## Step 3.3 - Install the RAKwireless BSP

Open:

```text
Tools
  -> Board
     -> Boards Manager
```

Then:

1. search `RAKwireless` or `RAK`;
2. install the RAKwireless nRF52/WisBlock board package;
3. record the installed version in `arduino-environment.txt`.

The currently observed lab machine used RAKwireless nRF52 BSP `1.3.3`. Record the actual installed version; do not silently update it during a counted experiment group.

**Why?** The BSP supplies the RAK4631-specific Arduino core and DFU/upload tooling.

## Step 3.4 - Select the RAK4631 board

Choose:

```text
Tools
  -> Board
     -> RAKwireless ...
        -> WisBlock Core RAK4631 Board
```

The exact submenu name can vary by BSP version. The selected board name that matters is:

```text
WisBlock Core RAK4631 Board
```

---

# Part 4 - Identify the correct COM port

With EMU-01 connected:

```text
Tools
  -> Port
```

On Windows the board appears as a `COM` port, for example `COM12`.

If you are unsure which port is EMU-01:

```text
disconnect EMU-01
      ↓
look at Tools -> Port
      ↓
reconnect EMU-01
      ↓
look again
      ↓
new COM port = EMU-01
```

Select that port.

**Why?** Arduino IDE needs both the correct board definition and the correct physical serial/DFU port. Selecting the right board but the wrong COM port still prevents upload.

Do not permanently hard-code the COM number in the documentation. The port can change when the RAK4631 enters bootloader mode or after reconnecting USB.

---

# Part 5 - First harmless RAK4631 program

Do this before any sensor code.

## Step 5.1 - Create a new sketch

Open:

```text
File
  -> New Sketch
```

Delete the default contents and paste:

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

### Why this sketch is intentionally simple

It tests only:

```text
compiler
   +
RAK BSP
   +
DFU upload
   +
RAK4631 CPU execution
   +
USB Serial
```

No sensor library and no LoRaWAN code is involved yet.

### Why `Adafruit_TinyUSB.h` is included here

The RAK nRF52 BSP uses TinyUSB for USB functionality. On the observed Windows lab setup with RAKwireless nRF52 BSP `1.3.3`, a sketch using `Serial` without this include produced linker errors such as:

```text
undefined reference to `Adafruit_USBD_CDC::begin(unsigned long)'
undefined reference to `Adafruit_USBD_CDC::operator bool()'
undefined reference to `Serial'
```

Adding:

```cpp
#include <Adafruit_TinyUSB.h>
```

resolved that specific build problem.

Treat this as a **known lab/BSP compatibility fix**, not proof that every future RAK BSP release will require an explicit TinyUSB include.

---

# Part 6 - Understand Verify / Compile

At the upper-left of Arduino IDE:

```text
✓    →
│    │
│    └── Upload
│
└──── Verify / Compile
```

Click the **checkmark / Verify** first.

## What Verify actually does

```text
Arduino source code
      ↓
compiler checks syntax
      ↓
libraries are compiled
      ↓
linker combines sketch + RAK core + libraries
      ↓
final firmware image is created
```

A successful compile ends with output similar to:

```text
Sketch uses 44880 bytes (5%) of program storage space. Maximum is 815104 bytes.
Global variables use 8252 bytes (3%) of dynamic memory, leaving ...
```

The exact numbers change with the sketch.

**Meaning:** the laptop successfully created firmware for the selected RAK4631 target.

It does **not** yet prove that the physical board was programmed or that the code runs.

## If Verify fails with a missing header

Example:

```text
fatal error: Light_VEML7700.h: No such file or directory
```

Meaning:

```text
Arduino reached #include <...>
      ↓
requested library/header is not installed
      ↓
compilation stops before hardware is touched
```

Do not troubleshoot the sensor hardware for a missing-header error. Install the correct library first.

---

# Part 7 - Upload to the physical RAK4631

After Verify passes, click the **right-arrow Upload** button.

A normal RAK4631 DFU upload may show output similar to:

```text
Upgrading target on COMxx with DFU package ...
...
Activating new firmware
Device programmed.
```

## Why `Device programmed.` matters

Compile only proved:

```text
laptop can build firmware
```

`Device programmed.` proves:

```text
laptop
  ↓
Arduino IDE
  ↓
RAK DFU / bootloader
  ↓
firmware written into the physical RAK4631
```

It still does not prove the application is executing correctly. Serial Monitor is the next layer.

## If upload fails

Try in this order:

```text
1. close Serial Monitor
2. double-click RESET on the WisBlock base
3. open Tools -> Port again
4. select the bootloader/new COM port if it changed
5. click Upload again
```

Do not start changing sensor wiring because of a DFU/COM-port problem.

---

# Part 8 - Prove the uploaded firmware is actually executing

Open:

```text
Tools
  -> Serial Monitor
```

Set:

```text
115200 baud
```

Expected output:

```text
==============================
EMU-01 RAK4631 STARTED
USB SERIAL TEST = PASS
==============================
EMU-01 is alive
EMU-01 is alive
EMU-01 is alive
...
```

If the startup banner scrolled past before Serial Monitor opened, seeing repeated:

```text
EMU-01 is alive
```

is enough to prove the loop is running.

## Why this is the first major gate

At this point you have proven:

```text
Arduino IDE installed       PASS
RAK BSP installed           PASS
RAK4631 selected            PASS
USB connection              PASS
firmware compilation        PASS
DFU / bootloader upload     PASS
RAK4631 CPU execution       PASS
USB Serial output           PASS
```

Only now should sensor debugging begin.

---

# Part 9 - First physical sensor: RAK1903 / OPT3001 in Sensor A

Start with RAK1903 because it is a simple I2C sensor and its response is easy to prove physically by changing the light level.

Relevant path:

```text
RAK4631
   │
   │ I2C
   ▼
RAK19001
   │
   └── Sensor A
          │
          └── RAK1903 / OPT3001
```

## Step 9.1 - Install the OPT3001 library

Open Library Manager:

```text
Sketch
  -> Include Library
     -> Manage Libraries...
```

or use the Library Manager icon in the left sidebar.

Search:

```text
ClosedCube OPT3001
```

Install the library that provides:

```cpp
#include <ClosedCube_OPT3001.h>
```

**Why?** The library contains the sensor register/protocol logic. The RAK4631 does not automatically know how to configure an OPT3001 or convert its raw value into lux.

## Step 9.2 - Use the RAK1903 test sketch

Create a new sketch and paste:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include <ClosedCube_OPT3001.h>

#define OPT3001_ADDRESS 0x44

ClosedCube_OPT3001 lightSensor;

void setup()
{
  // RAK19001 switched 3V3_S sensor power.
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("EMU-01 RAK1903 TEST");
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

## Why `WB_IO2` is set HIGH

On the RAK19001, `WB_IO2` controls the switched `3V3_S` sensor power rail used by the project build:

```text
WB_IO2 HIGH
     ↓
3V3_S enabled
     ↓
sensor modules powered
```

This is one reason the permanent project map leaves Sensor B unused.

## Why `Wire.h` is present

`Wire` is Arduino's I2C layer:

```text
RAK4631
   │
   ├── SDA = data
   └── SCL = clock
          │
          ▼
       sensors
```

The OPT3001 is addressed at `0x44` in the RAK example.

## Step 9.3 - Verify, Upload, Serial Monitor

Do the same three-layer check:

```text
Verify ✓
   ↓
firmware builds
   ↓
Upload →
   ↓
Device programmed.
   ↓
Serial Monitor @ 115200
```

Expected output contains changing lux values, for example:

```text
RAK1903 configuration = PASS
RAK1903 light = ... lux
RAK1903 light = ... lux
```

The exact lux value is not the pass criterion.

## Step 9.4 - Physical response test

1. leave RAK1903 exposed to normal room light and observe lux;
2. cover the **RAK1903 in Sensor A** with an opaque object or finger;
3. confirm lux drops;
4. uncover it;
5. confirm lux rises again.

Why this matters:

```text
number appears
     = communication probably works

light changes
   ↓
sensor value changes
     = physical sensor response proven
```

**PASS:** RAK1903 initializes, returns numeric lux values, and responds correctly to changing illumination.

---

# Part 10 - Second physical sensor: RAK12010 / VEML7700 in Sensor F

Test RAK12010 next because it is another easy I2C device and gives a second independent proof that multiple sensor modules can use the shared bus.

Permanent position:

```text
Sensor F = RAK12010 / VEML7700
```

## Step 10.1 - Install the correct VEML7700 library

Open Library Manager and search:

```text
VEML7700
```

Install the **RAKWireless VEML7700** library used by the RAK12010 example. It must provide:

```cpp
#include "Light_VEML7700.h"
```

Do not assume another VEML7700 library is interchangeable. For example, a library using `Adafruit_VEML7700.h` has a different API and will not satisfy a sketch that asks for `Light_VEML7700.h`.

## Exact meaning of this common error

If Verify shows:

```text
fatal error: Light_VEML7700.h: No such file or directory
compilation terminated.
```

then:

```text
RAK4631 hardware        not tested by this compile
RAK12010 hardware       not tested by this compile
I2C bus                 not tested by this compile

problem = required header/library is missing
```

Fix:

```text
Library Manager
      ↓
search VEML7700
      ↓
install RAKWireless-compatible library
      ↓
Verify again
```

Do not remove or reseat the physical RAK12010 merely because of a missing-header compiler error.

## Step 10.2 - Use the RAK12010 test sketch

Create a new sketch:

```cpp
#include <Adafruit_TinyUSB.h>
#include "Light_VEML7700.h"

Light_VEML7700 lightSensor = Light_VEML7700();

void setup()
{
  // Enable RAK19001 switched sensor power.
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("EMU-01 RAK12010 TEST");
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

This uses the same `Light_VEML7700` class, `begin()`, gain setting, integration-time setting, and `readLux()` pattern as the current RAK12010 example.

## Step 10.3 - Verify, Upload, observe

```text
Verify ✓
      ↓
compile passes
      ↓
Upload →
      ↓
Device programmed.
      ↓
Serial Monitor @ 115200
```

Expected:

```text
RAK12010 detected
TEST INITIALIZATION = PASS
RAK12010 light = ... lux
RAK12010 light = ... lux
```

## Step 10.4 - Physical response test

Make sure you manipulate the **RAK12010 in Sensor F**, not the already-tested RAK1903 in Sensor A:

```text
normal room light
      ↓
record lux
      ↓
cover RAK12010
      ↓
lux should decrease
      ↓
uncover RAK12010
      ↓
lux should increase
```

**PASS:** RAK12010 initializes, reports numeric lux, and responds correctly to changing illumination.

## Step 10.5 - Is it okay that RAK12010 is on the bottom side of the RAK19001?

Yes. Keep the project-fixed placement:

```text
Sensor F = RAK12010 / VEML7700
```

RAK documents that RAK12010 can be mounted in Sensor Slots A through F. Therefore, Slot F being physically on the lower side of the RAK19001 is not an electrical problem.

The important issue is **optical exposure**:

```text
Slot F electrically valid
        +
VEML7700 can see intended ambient light
        =
valid placement
```

For bench testing:

```text
[ ] do not lay the RAK12010 face-down against an opaque desk
[ ] use standoffs / feet / spacers so light can reach the lower-side sensor
[ ] keep cables and other PCBs away from the VEML7700 optical surface
[ ] verify cover -> lux decreases and uncover -> lux increases
```

For the final enclosure, provide a suitable opening/window/light path for the RAK12010. A sensor that communicates perfectly over I2C can still produce biased lux measurements if the enclosure physically shades it.

Do **not** move the RAK12010 out of Sensor F just because it is underneath the base. Moving it would change the frozen project slot map and must only be done deliberately with a new Pin Mapper/conflict review.

Keep the two final fields separate:

```text
RAK1903  -> light_opt3001_lux
RAK12010 -> light_veml7700_lux
```

---

# Part 11 - Third physical sensor: RAK12011 barometer in Sensor D

After both light sensors pass, test the RAK12011 next. The RAK12011 uses an ST LPS33HW pressure sensor and reports both barometric pressure and temperature over I2C.

Permanent position:

```text
Sensor D = RAK12011 / LPS33HW
```

RAK allows RAK12011 in Sensor A and C-F. Sensor D is therefore valid and, in our fixed map, gives the module the `WB_IO5` digital-output/interrupt role while avoiding `WB_IO2`, which controls `3V3_S`.

## Step 11.1 - Why test the barometer now?

We already proved two I2C light sensors. The barometer adds a different sensor family while still using the known-good I2C path:

```text
RAK4631 + USB/Serial       already proven
RAK19001 3V3_S             already proven
I2C bus                    already proven
        ↓
new device: RAK12011
        ↓
pressure + temperature
```

If this sensor now fails with `Sensor not found`, troubleshooting can focus on the RAK12011 library/address/Slot-D connection instead of re-questioning the entire Arduino setup.

## Step 11.2 - Install the required library

Open Arduino IDE Library Manager:

```text
Sketch
  -> Include Library
     -> Manage Libraries...
```

Search:

```text
Adafruit LPS2X
```

Install the **Adafruit LPS2X** library used by RAK's current RAK12011 example. If Arduino asks to install dependencies such as **Adafruit Unified Sensor**, install the required dependencies as well.

The test sketch needs:

```cpp
#include <Adafruit_LPS2X.h>
#include <Adafruit_Sensor.h>
```

If Verify reports `No such file or directory` for either header, stop and fix the library installation first. That is a compile-time software problem; the physical RAK12011 has not been tested yet.

## Step 11.3 - Create the RAK12011 test sketch

Create a new sketch and paste:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include <Adafruit_LPS2X.h>
#include <Adafruit_Sensor.h>

Adafruit_LPS22 barometer;

void setup()
{
  // Enable the RAK19001 switched 3V3_S sensor rail.
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("EMU-01 RAK12011 TEST");
  Serial.println("==============================");

  Wire.begin();

  // RAK's current RAK12011 example uses I2C address 0x5D.
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

Why keep `#include <Adafruit_TinyUSB.h>`? The lab RAK4631 BSP already showed that USB `Serial` failed to link without it. We keep the known-good compatibility fix while changing only the sensor layer.

## Step 11.4 - Verify

Click:

```text
✓ Verify
```

Expected successful compile pattern:

```text
Sketch uses ... bytes (...) of program storage space.
Global variables use ... bytes (...) of dynamic memory.
```

Logic:

```text
Verify succeeds
      =
library + sketch + RAK4631 BSP can build together
```

It does **not** yet prove the physical barometer.

## Step 11.5 - Upload

Click:

```text
→ Upload
```

Wait for:

```text
Device programmed.
```

Then open:

```text
Tools -> Serial Monitor
baud = 115200
```

## Step 11.6 - Expected output

A good result should look like:

```text
==============================
EMU-01 RAK12011 TEST
==============================
RAK12011 detected
TEST INITIALIZATION = PASS
RAK12011 temperature = ... C
RAK12011 pressure = ... hPa
RAK12011 temperature = ... C
RAK12011 pressure = ... hPa
```

RAK specifies the RAK12011 pressure range as approximately `260-1260 hPa`. Normal local atmospheric pressure should therefore be a plausible value in that supported range, not `0`, `nan`, or an obvious error/sentinel value.

The temperature is the sensor's local/environment reading. Do not expect it to exactly match the later RAK1906/BME680 temperature because they are separate devices in different physical positions.

## Step 11.7 - What counts as PASS?

```text
RAK12011 detected                 PASS
pressure is numeric/plausible     PASS
temperature is numeric/plausible  PASS
readings repeat without errors    PASS
```

Current EMU-01 lab verification produced:

```text
RAK12011 temperature = 26.49 C
RAK12011 pressure = 1015.66 hPa
```

This is a **functional PASS example**, not a permanent calibration baseline. The useful facts are that the sensor initialized, both fields were numeric, the pressure was physically plausible, and readings were returned without errors.

Unlike the light sensors, you do not need to force a dramatic physical change in atmospheric pressure. The initial goal is reliable detection and plausible pressure/temperature measurements.

Save the final firmware fields separately as:

```text
barometer_pressure_pa
barometer_temperature_c
```

The RAK example reports pressure in `hPa`; the final payload can convert it to pascals with:

```text
Pa = hPa x 100
```

---

# Part 12 - Fourth physical sensor: RAK1906 / BME680 in Sensor E

After the RAK12011 passes, test the RAK1906 environmental sensor.

Permanent position:

```text
Sensor E = RAK1906 / BME680
```

RAK documents that RAK1906 works in Sensor Slots A-F and uses I2C. In our fixed EMU-01 map it stays in Sensor E. The module measures four independent values:

```text
temperature
humidity
pressure
gas resistance
```

## Step 12.1 - Why test RAK1906 now?

We already know the shared I2C path works with three different devices. RAK1906 adds a multi-function environmental sensor and lets us verify the four fields that will later appear separately in the final payload.

```text
known-good RAK4631 + I2C
          ↓
       RAK1906
          ↓
  temperature
  humidity
  pressure
  gas resistance
```

Do not merge these values with the RAK12011 fields. The two modules are separate physical sensors and will not necessarily report identical temperatures or pressures.

## Step 12.2 - Install the required library

Open Arduino IDE Library Manager:

```text
Sketch
  -> Include Library
     -> Manage Libraries...
```

Search:

```text
Adafruit BME680
```

Install **Adafruit BME680**. If Arduino asks to install **Adafruit Unified Sensor** or another required dependency, install the dependency too.

The test sketch needs:

```cpp
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>
```

If Verify reports `No such file or directory`, stop and fix the library installation first. A missing header is still a software-build failure, not proof that the physical RAK1906 is bad.

## Step 12.3 - Create the RAK1906 test sketch

Create a new sketch and paste:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>

Adafruit_BME680 bme;

void setup()
{
  // Enable the RAK19001 switched sensor power rail.
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("EMU-01 RAK1906 TEST");
  Serial.println("==============================");

  Wire.begin();

  // RAK's current RAK1906 example uses BME680 I2C address 0x76.
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

Why keep `Adafruit_TinyUSB.h` and `WB_IO2 = HIGH`? Those are already proven parts of this EMU-01 lab setup: TinyUSB keeps USB Serial linking correctly with the installed RAK BSP, while `WB_IO2` enables the RAK19001 switched `3V3_S` sensor supply.

## Step 12.4 - Verify and Upload

Use the same gates:

```text
Verify ✓
   ↓
Sketch uses ... bytes
Global variables use ... bytes
   ↓
software build PASS
   ↓
Upload →
   ↓
Device programmed.
   ↓
physical RAK4631 programming PASS
```

If Verify fails, fix the first compiler error before touching the hardware. If Verify passes but Upload fails, troubleshoot the COM/DFU layer instead of the BME680.

## Step 12.5 - Open Serial Monitor

Open:

```text
Tools -> Serial Monitor
```

Set:

```text
115200 baud
```

Expected pattern:

```text
==============================
EMU-01 RAK1906 TEST
==============================
RAK1906 detected
TEST INITIALIZATION = PASS
RAK1906 temperature = ... C
RAK1906 humidity = ... %
RAK1906 pressure = ... hPa
RAK1906 gas resistance = ... ohm
```

The exact numbers depend on the room and on sensor warm-up. For an initial functional pass, require numeric values and no repeated `reading FAILED` message.

## Step 12.6 - BME680 burn-in and stabilization rule

This sensor is different from the light sensors and barometer because its gas-sensing element needs time to stabilize.

RAK's current RAK1906 instructions specify:

```text
FIRST USE
read all values every 5 seconds
for at least 20 minutes

LATER POWER-UPS
allow approximately 2-3 minutes
for readings to stabilize
```

Why?

```text
BME680 gas element powers/heats
          ↓
its response changes during warm-up
          ↓
early returned values may be valid communications
but are not yet a stable environmental baseline
```

Therefore separate two judgments:

```text
FUNCTIONAL PASS
sensor detected + four numeric values

STABILIZED BASELINE PASS
required burn-in/stabilization completed
before freezing evidence or comparing runs
```

Do not treat the first gas-resistance number after boot as the final baseline.

## Step 12.7 - What counts as PASS?

```text
RAK1906 detected                  PASS
numeric temperature              PASS
numeric humidity                 PASS
numeric pressure                 PASS
numeric gas resistance           PASS
repeated readings without error  PASS
20-minute first-use burn-in      REQUIRED once
2-3 minute later stabilization   REQUIRED before baseline capture
```

Current EMU-01 lab verification produced two consecutive samples:

```text
RAK1906 temperature = 29.18 C
RAK1906 humidity = 51.21 %
RAK1906 pressure = 1011.12 hPa
RAK1906 gas resistance = 14166 ohm

RAK1906 temperature = 29.17 C
RAK1906 humidity = 51.19 %
RAK1906 pressure = 1011.12 hPa
RAK1906 gas resistance = 14641 ohm
```

Interpretation:

```text
compile                         PASS
DFU upload / "Device programmed." PASS
RAK1906 communication          PASS
four measurement channels      PASS
repeat reading                 PASS
first-use burn-in              COMPLETE (operator-marked)
```

The operator has marked the first-use burn-in gate complete. The gas-resistance value changing between early samples is not by itself a failure; later baseline captures should still allow the normal stabilization period before comparing runs.

Do not require the RAK1906 pressure/temperature to exactly equal the RAK12011 values. They are separate sensor chips in different board positions and have different response/calibration behavior.

Final firmware fields remain separate:

```text
environment_temperature_c
environment_humidity_percent
environment_pressure_pa
environment_gas_resistance_ohm
```

---

# Part 13 - Fifth physical sensor: RAK12019 UV / LTR390 in Sensor C

After the RAK1906 functional test passes, move to the RAK12019 UV sensor.

Permanent position:

```text
Sensor C = RAK12019 / LTR-390UV-01
```

RAK documents RAK12019 for Sensor Slots C-F, so Sensor C is valid for our fixed EMU-01 map. The module communicates over I2C and can operate in either ambient-light mode or ultraviolet mode. For the project payload, test **UV mode** because the final field is intended to be UV index.

## Step 13.1 - Why test UV mode directly?

The RAK12019 can report both ALS and UV information. We already have two dedicated visible-light sensors, so the useful acceptance question is:

```text
Can RAK12019 enter UVS mode?
        ↓
Can it return raw UVS data?
        ↓
Can the selected RAK driver return UVI using getUVI()?
        ↓
yes -> project may legitimately use uv_index
```

This resolves the earlier payload question: RAK's current example exposes `getUVI()` while the device is in `LTR390_MODE_UVS`, so the accepted firmware can use a UV-index field when it uses that driver/API path.

## Step 13.2 - Install the RAK12019 library

Open Arduino IDE Library Manager:

```text
Sketch
  -> Include Library
     -> Manage Libraries...
```

Search for:

```text
RAK12019_LTR390
```

Install the library that provides:

```cpp
#include "UVlight_LTR390.h"
```

Why? The library contains the LTR390 register configuration and the conversion logic used by RAK's example, including `getUVI()`.

If Verify reports:

```text
fatal error: UVlight_LTR390.h: No such file or directory
```

then the failure is still at the compile/library layer. Do not reseat or replace the physical UV sensor yet.

## Step 13.3 - Create the UV-mode test sketch

Create a new sketch and paste:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include "UVlight_LTR390.h"

UVlight_LTR390 uvSensor = UVlight_LTR390();

void setup()
{
  // Enable the RAK19001 switched 3V3_S sensor rail.
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("==============================");
  Serial.println("EMU-01 RAK12019 UV TEST");
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

  // Use UV mode, not ALS mode, for this project test.
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

This deliberately uses the same RAK12019 API names shown in RAK's current example: `init()`, `LTR390_MODE_UVS`, `setGain()`, `setResolution()`, `newDataAvailable()`, `getUVI()`, and `readUVS()`.

We keep `Adafruit_TinyUSB.h` because it is already a known-good USB-Serial compatibility requirement for this lab RAK4631 BSP.

## Step 13.4 - Verify, Upload, and open Serial Monitor

Run the same three gates:

```text
Verify ✓
   ↓
compile succeeds
   ↓
Upload →
   ↓
"Device programmed."
   ↓
Serial Monitor @ 115200
```

Expected startup:

```text
==============================
EMU-01 RAK12019 UV TEST
==============================
RAK12019 detected
UV MODE = PASS
TEST INITIALIZATION = PASS
```

Then expect repeated UV readings such as:

```text
RAK12019 UVI = ...
RAK12019 raw UVS = ...
```

The exact value depends heavily on the light source and actual UV content.

### Current EMU-01 observation: zero UV indoors is INCONCLUSIVE, not FAIL

The current lab run successfully compiled, uploaded, and returned:

```text
Device programmed.
RAK12019 UVI = 0.00
RAK12019 raw UVS = 0
```

Interpret this carefully:

```text
compile/upload path                    PASS
RAK4631 executes the UV sketch         PASS
RAK12019 driver returns numeric values PASS
actual UV response                     NOT PROVEN YET
```

`0.00 / 0` can occur when the sensor is indoors or under a light source with little useful UV content. Do not call the module defective from this result alone, and do not call it a full sensor PASS yet.

## Step 13.5 - Physical UV response test

Do **not** use an ordinary indoor LED lamp as the only UV test source. The purpose is to prove the sensor responds to a meaningful change in UV exposure.

Preferred test:

```text
1. keep the current UV-mode sketch loaded
2. confirm Serial Monitor still prints UVI + raw UVS
3. move EMU-01 to a safe outdoor location with natural daylight
4. keep the RAK12019 optical surface unobstructed
5. wait for several fresh samples
6. record UVI + raw UVS
7. cover only the RAK12019 with an opaque object
8. record several samples
9. uncover it and record several more samples
```

Prefer direct outdoor daylight rather than testing only through a window because glazing can reduce ultraviolet transmission. Keep the electronics dry and do not leave the board where it can overheat. Do not use unsafe UV-C lamps or look directly into hazardous UV sources merely to force a response.

Expected logic:

```text
outdoor / exposed
      ↓
UVS should become non-zero when meaningful UV is present
      ↓
cover sensor
      ↓
UVS/UVI should fall
      ↓
uncover sensor
      ↓
UVS/UVI should rise again
```

### If UVS remains zero outdoors: use ALS mode as a diagnostic

The RAK12019 contains the same LTR390 device for both ambient-light and UV sensing. RAK's official example supports both modes. Temporarily change:

```cpp
uvSensor.setMode(LTR390_MODE_UVS);
```

to:

```cpp
uvSensor.setMode(LTR390_MODE_ALS);
```

Then, in the data-printing section, temporarily replace the UVI/UVS prints with:

```cpp
Serial.print("RAK12019 Lux = ");
Serial.println(uvSensor.getLUX());

Serial.print("RAK12019 raw ALS = ");
Serial.println(uvSensor.readALS());
```

Why this diagnostic helps:

```text
ALS changes when cover/uncover changes light
        ↓
I2C + LTR390 + optical sensor response are alive
        ↓
problem is specifically UV exposure/mode/calculation sensitivity

ALS also stays zero / does not react
        ↓
inspect Sensor C seating, optical obstruction, power, or module fault
```

After this diagnostic, restore `LTR390_MODE_UVS` because the project payload requires UV index rather than a third visible-light field.

## Step 13.6 - What counts as PASS?

```text
RAK12019 detected                 PASS
UV mode confirmed                PASS
getUVI() returns numeric data    PASS
readUVS() returns numeric data   PASS
meaningful UV gives non-zero UVS PASS
cover/uncover changes UV reading PASS
```

The earlier indoor `UVI = 0.00` / `raw UVS = 0` observation remains the captured numeric example. The operator has now marked the RAK12019 physical-response acceptance gate **COMPLETE** for project tracking. No additional outdoor-response values were captured in this walkthrough, so do not invent or backfill measurements that were not recorded.

Final payload field:

```text
uv_index
```

For payload v2 the encoded field remains `uv_index_x100`, so the final integrated firmware multiplies the accepted floating-point UVI by 100 and encodes it as the defined integer field. Do not substitute raw UVS counts into `uv_index_x100`.

---

# Part 14 - Sixth physical sensor: RAK12023 + RAK12035 soil sensor on WisIO 1

The next bench-only test is the soil-moisture assembly:

```text
WisIO 1 = RAK12023 connector module
              │
              └── RAK12035 soil probe
```

RAK12023 is the WisBlock IO connector board. The RAK12035 is the actual capacitive soil probe and reports **soil moisture** plus **soil temperature**. Only one RAK12035 probe is connected to a RAK12023 at a time.

## Step 14.1 - Why calibration comes before the moisture test

Unlike the previous sensors, a raw soil-probe capacitance does not automatically mean a valid moisture percentage.

```text
dry reference
     ↓
store as 0% reference
     ↓
wet reference
     ↓
store as 100% reference
     ↓
future capacitance readings
     ↓
converted to moisture percentage
```

RAK explicitly requires calibration before using the RAK12035 moisture value. The calibration values are saved on the RAK12035 sensor itself.

For this **functional bench verification**, use RAK's basic dry-air / water calibration. Before counted experiments, record the final project calibration method and, if higher measurement accuracy is required, calibrate against the selected dry-soil and water-saturated-soil references rather than treating air/water as a research-grade calibration.

## Step 14.2 - Physical safety check

Before running the calibration:

```text
[ ] RAK12023 is secured in WisIO 1
[ ] RAK12035 cable is firmly connected to RAK12023
[ ] main RAK19001 / RAK4631 electronics remain dry
[ ] probe is clean
[ ] container of clean water is stable and away from the base board
[ ] the probe's white immersion-limit line is visible
```

**Important:** RAK warns that the RAK12035 electronics are not fully waterproof. During the wet calibration, submerge only to the documented white line. Do not immerse the connector/cable electronics or the WisBlock base.

## Step 14.3 - Install the soil library

In Arduino IDE:

```text
Sketch
  -> Include Library
     -> Manage Libraries...
```

Search:

```text
RAK12035_SoilMoisture
```

Install the library that provides:

```cpp
#include "RAK12035_SoilMoisture.h"
```

If Verify reports:

```text
RAK12035_SoilMoisture.h: No such file or directory
```

that is a library-installation problem. The physical soil sensor has not been tested yet.

## Step 14.4 - First run a read-status diagnostic before calibration

Do **not** write calibration values until the raw RAK12035 capacitance read has been proven healthy. The RAK12035 library returns a Boolean success/failure flag from `get_sensor_version()`, `get_sensor_capacitance()`, `get_sensor_moisture()`, `get_sensor_temperature()`, `get_dry_cal()`, and `get_wet_cal()`.

RAK's library explicitly says that when an I2C read returns `false`, the accompanying numeric value must be disregarded. A valid-looking temperature alone therefore does not prove that the capacitance channel is healthy.

Create a new sketch and paste this **read-only diagnostic**. It does not overwrite the stored dry/wet calibration values:

```cpp
#include <Adafruit_TinyUSB.h>
#include <Wire.h>
#include "RAK12035_SoilMoisture.h"

RAK12035 soilSensor;

void setup()
{
  // Enable the RAK19001 switched sensor / IO power rail.
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  Serial.println();
  Serial.println("====================================");
  Serial.println("EMU-01 RAK12035 READ DIAGNOSTIC");
  Serial.println("====================================");

  Wire.begin();

  // begin() resets the RAK12035 and waits for it to respond.
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

Why use this first?

```text
read API returns PASS
        +
raw capacitance is plausible and responsive
        ↓
communication layer proven
        ↓
THEN calibration is allowed
```

The current RAK library documents typical free-air capacitance in the low hundreds at 3.3 V, while published RAK calibration examples vary from probe to probe but are likewise in the hundreds. A raw value near the top of the 16-bit range (for example about `65500`) is therefore not an acceptable calibration reference.

## Step 14.4A - If the diagnostic passes, use RAK's official calibration example

After the read-status diagnostic shows successful capacitance reads with plausible raw values:

```text
Arduino IDE
  -> File
     -> Examples
        -> RAK12035_SoilMoisture
           -> RAK12035_Calibration
```

Use the official RAK calibration example for the actual dry-air and water calibration. Follow its prompts exactly:

```text
dry probe in air
      ↓
100 calibration readings
      ↓
record dry value
      ↓
probe in water only to white line
      ↓
100 calibration readings
      ↓
record wet value
      ↓
values saved on RAK12035
```

The project keeps `Adafruit_TinyUSB.h` in custom lab sketches because the current RAK4631 BSP already proved that this include is needed for reliable USB Serial linking. If the stock RAK example produces the previously observed USB-Serial linker error, add `#include <Adafruit_TinyUSB.h>` at the top and Verify again.

## Step 14.5 - Verify and Upload

Use the same gates:

```text
Verify ✓
    ↓
compile succeeds
    ↓
Upload →
    ↓
Device programmed.
```

If compilation succeeds but Upload fails, troubleshoot the COM/DFU layer exactly as before; do not recalibrate or reseat the soil probe because an upload failure has not reached the sensor yet.

## Step 14.6 - Configure Serial Monitor correctly

Open:

```text
Tools -> Serial Monitor
```

Set:

```text
baud rate = 115200
line ending = Newline
```

The `Newline` setting matters because the calibration sketch waits for you to press **Enter** before each calibration stage.

## Step 14.7 - Perform the dry calibration

When Serial Monitor shows:

```text
STEP 1 - DRY CALIBRATION
Keep the probe clean and completely in dry air.
Press ENTER in Serial Monitor when ready.
```

Do this:

```text
1. keep RAK12035 completely out of water/soil
2. make sure the sensing surface is dry
3. click the Serial Monitor input box
4. press Enter / send a blank line
5. do not touch the probe while 100 readings are collected
```

Expect:

```text
Taking 100 dry readings...
Dry calibration capacitance = <number>
```

The exact number is probe-specific; record it rather than comparing it to somebody else's value.

## Step 14.8 - Perform the wet calibration

The sketch will next say:

```text
STEP 2 - WET CALIBRATION
Submerge ONLY the allowed probe section up to the white line.
Press ENTER when ready.
```

Do this carefully:

```text
1. place clean water in a stable container
2. move the container to the probe, not the powered base board to the water
3. lower ONLY the intended sensing section into the water
4. STOP at the documented white line
5. keep RAK12023, RAK19001, RAK4631, connectors, and cable electronics dry
6. press Enter
7. hold the probe still while 100 readings are collected
```

Expect:

```text
Taking 100 wet readings...
Wet calibration capacitance = <different number>
Calibration values saved to RAK12035
CALIBRATION = COMPLETE
```

Why must the dry and wet values be different? The capacitive sensor is supposed to respond to the dielectric difference between dry air and a wet medium. If the two calibration values are essentially identical, do not accept the calibration.

### Observed EMU-01 invalid calibration example

The first custom calibration attempt produced:

```text
Dry calibration capacitance = 65500
Wet calibration capacitance = 65497
Soil capacitance = 65502
Soil moisture = 0 %
Soil temperature = 31.30 C
```

**Status: INVALID CALIBRATION / SOIL NOT PASSED.**

Reasons:

```text
dry and wet differ by only 3 counts
        +
raw capacitance is near 65535
        +
RAK documents normal capacitance in the hundreds
        ↓
these values must not be used as real calibration references
```

The earlier custom sketch also failed to check the Boolean success/failure result returned by the RAK12035 read APIs. Replace that workflow with the read-status diagnostic in Step 14.4 before recalibrating.

The bad calibration values already written to the RAK12035 are not permanent damage. Once the raw capacitance channel is healthy, rerun the official calibration and the correct dry/wet values will overwrite them.

The follow-up read-status diagnostic returned successful API transactions but still produced abnormal raw data:

```text
capacitance status = PASS | value = 65494
moisture status = PASS | value = 66 %
temperature status = PASS | value = 28.80 C

capacitance status = PASS | value = 65498
moisture status = PASS | value = 100 %
temperature status = PASS | value = 28.80 C
```

Interpretation:

```text
I2C/API transaction status        PASS
raw capacitance plausibility      FAIL
stored dry/wet calibration        INVALID (65500 / 65497)
reported moisture percentage      DO NOT TRUST
soil temperature channel          PLAUSIBLE, but soil assembly not yet accepted
```

The `66% -> 100%` jump is expected from the invalid calibration span: the stored dry and wet references differ by only three counts, so tiny changes in the abnormal raw value can map to very large percentage changes. RAK's published examples use raw/calibration values in the hundreds and require dry/wet calibration references that meaningfully differ.

### Step 14.8A - Isolate the abnormal raw-capacitance fault

Do **not** recalibrate and do **not** move to the rain test until the raw capacitance channel is plausible.

1. Close Serial Monitor.
2. Disconnect USB-C and remove all power from EMU-01.
3. Verify only one RAK12035 probe is connected to the RAK12023.
4. Reseat the RAK12035 cable at the RAK12023 connector; do not force the connector.
5. Verify the RAK12023 itself is fully seated and screwed into `WisIO 1`.
6. Inspect the probe cable and connector for bent contacts, partial insertion, damage, or moisture near the electronics end.
7. Reconnect USB-C.
8. Rerun the read-status diagnostic **without writing any calibration values**.
9. Observe at least 10 consecutive raw capacitance values with the probe clean and dry in air.

The EMU-01 reseat test then produced:

```text
capacitance status = PASS | value = 563
capacitance status = PASS | value = 558
capacitance status = PASS | value = 561
capacitance status = PASS | value = 559
capacitance status = PASS | value = 561

temperature status = PASS | value = 29.30 C
moisture status = PASS | value = 100 %
```

Interpretation:

```text
I2C/API transaction status        PASS
raw capacitance plausibility      PASS
raw dry-air stability             PASS
soil temperature                  PASS / plausible
stored calibration                STILL INVALID (65500 / 65497)
reported moisture = 100%          IGNORE until recalibration
```

The change from `~654xx` to stable `558-563` after reseating strongly indicates that the previous abnormal raw data came from the probe/connector seating path. The second RAK12035 probe is **not needed** for isolation unless the abnormal `654xx` behavior returns.

### Step 14.8B - Recalibrate now that the raw channel is healthy

The old `65500 / 65497` dry/wet values are still stored on the RAK12035, so the current `100%` moisture output is not meaningful. Overwrite them with a new calibration.

Preferred Arduino path:

```text
File
  -> Examples
     -> RAK12035_SoilMoisture
        -> RAK12035_Calibration
```

If this lab BSP again needs the TinyUSB compatibility include, add:

```cpp
#include <Adafruit_TinyUSB.h>
```

at the top before compiling.

Run the calibration in two stages:

```text
DRY
probe clean and completely in air
        ↓
press ENTER
        ↓
collect calibration value
        ↓
expect a plausible value in the hundreds

WET
submerge only the sensing portion
up to the white line
        ↓
keep RAK12023 / connector / electronics dry
        ↓
press ENTER
        ↓
collect second calibration value
        ↓
expect another plausible value in the hundreds
```

Do **not** require wet capacitance to always be numerically higher or lower than dry. RAK's published examples show probe-specific values in both directions. The acceptance requirement is that the two stable calibration points are plausible and meaningfully separated, not that they follow a hard-coded direction.

The current official calibration run has now completed its wet stage and reported:

```text
Calibration in water finished, average capacitance is 328
```

This is a plausible probe-specific wet calibration value and is clearly separated from the healthy dry-air raw readings observed immediately before calibration (`558-563`). However, record the **actual dry calibration value printed earlier in this same calibration run** before declaring the calibration complete. Do not silently substitute the earlier diagnostic raw range for the official saved dry calibration value.

Current calibration status:

```text
raw channel after reseat          PASS (558-563 in dry air)
dry calibration value            PASS = 560
wet calibration value            PASS = 328
calibration separation            PASS = 232 counts
stored dry/wet pair               PASS candidate = 560 / 328
wet-to-dry moisture response      PENDING
```

After the example saves the values, verify the stored calibration and moisture response:

```text
probe remains in wet calibration condition
        -> moisture should move toward the wet end

probe removed, cleaned, and dried
        -> moisture should move toward the dry end
```

If raw capacitance ever returns to `~654xx`, stop calibration again and repeat the power-off/reseat check. Only if reseating no longer restores plausible values should Probe B be swapped onto the same RAK12023 for A/B isolation.

## Step 14.9 - Observe the live measurements

After calibration the same sketch continuously prints:

```text
Soil capacitance = ...
Soil moisture = ... %
Soil temperature = ... C
```

For a simple response check:

```text
probe in/near the wet calibration condition
        ↓
moisture should be toward the wet end
        ↓
remove probe and dry the sensing surface
        ↓
allow readings to settle
        ↓
moisture should move toward the dry end
```

Do not demand an instant perfect `0%` or `100%` on every sample. The functional criterion is that calibration completes, the values are numeric, moisture responds in the correct direction, and temperature is plausible.

## Step 14.10 - What counts as PASS?

```text
RAK12035 responds / firmware version read       PASS
dry calibration value captured                  PASS
wet calibration value captured                  PASS
dry and wet references meaningfully differ      PASS
calibration values saved                         PASS
soil capacitance numeric                         PASS
soil moisture percentage numeric                 PASS
soil temperature numeric/plausible               PASS
wet -> dry condition changes moisture correctly  PASS
```

Final payload fields remain separate:

```text
soil_moisture_percent_x100
soil_temperature_c_x100
```

The Arduino library returns moisture as a percentage and temperature in tenths of a degree Celsius in RAK's current example. The final integrated firmware must explicitly scale these into the payload-v2 integer fields; do not silently change units.

---

# Part 15 - Seventh physical sensor: RAK12005 + RAK12030 rain sensor on WisIO 2

The next bench test is the rain / conductive-water detector:

```text
WisIO 2 = RAK12005 rain detector module
              │
              └── RAK12030 sensing pad
```

RAK documents the RAK12005 as a digital electroconductive-liquid detector. The separate RAK12030 is the part that is intentionally exposed to water. The RAK12005 module, RAK19001 base, RAK4631, connectors, and the rest of EMU-01 must remain dry.

In the current EMU-01 fixed map the RAK12005 output is read on:

```text
WB_IO6
```

RAK's current quick-start example also defines the RAK12005 water input as `WB_IO6`. The detector output goes HIGH when water is detected and LOW when the sensing pad is dry.

## Step 15.1 - Why this test is simpler than the soil test

The rain sensor does not return a continuously calibrated moisture percentage. It is a binary detector:

```text
RAK12030 dry
    ↓
RAK12005 comparator
    ↓
WB_IO6 LOW
    ↓
rain_wet = 0

RAK12030 wet
    ↓
conductivity across copper traces
    ↓
RAK12005 comparator
    ↓
WB_IO6 HIGH
    ↓
rain_wet = 1
```

The small potentiometer on the RAK12005 adjusts the digital detection threshold. Do not turn it unless the dry/wet test demonstrates that threshold adjustment is actually required.

## Step 15.2 - Physical safety check

Before testing:

```text
[ ] RAK12005 is fully seated and secured in WisIO 2
[ ] RAK12030 cable is firmly connected to RAK12005
[ ] RAK12030 sensing pad is clean and initially dry
[ ] RAK12005 electronics remain dry
[ ] RAK19001 / RAK4631 remain dry
[ ] water will be applied only to the exposed copper sensing pad
```

Use only a few drops of clean water for the bench test. There is no need to pour water over the board. After the wet test, wipe and dry the RAK12030 pad before checking the return-to-dry state.

## Step 15.3 - No extra Arduino sensor library is required

RAK's current example reads the comparator output directly with `digitalRead(WB_IO6)`, so this basic test does not need a separate RAK12005 Arduino library.

Keep the TinyUSB include because this lab RAK4631 BSP already proved that USB Serial requires it.

## Step 15.4 - Create the rain detector test sketch

Create a new Arduino sketch and paste:

```cpp
#include <Adafruit_TinyUSB.h>

#define RAIN_PIN WB_IO6

void setup()
{
  // Keep the RAK19001 switched 3V3_S rail enabled for the assembled sensor set.
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);

  Serial.begin(115200);
  delay(2000);

  pinMode(RAIN_PIN, INPUT);

  Serial.println();
  Serial.println("==============================");
  Serial.println("EMU-01 RAK12005 RAIN TEST");
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

Why use `WB_IO6`? RAK's current RAK12005 example explicitly assigns its water-sensor input to `WB_IO6`, and this matches the fixed EMU-01 pin map.

Why keep `WB_IO2 = HIGH`? On the RAK19001, `WB_IO2` controls the switched `3V3_S` supply. Keeping it HIGH preserves the known-good powered state of the assembled sensor set during bench verification.

## Step 15.5 - Verify, Upload, and open Serial Monitor

Run:

```text
Verify ✓
   ↓
compile succeeds
   ↓
Upload →
   ↓
Device programmed.
   ↓
Tools -> Serial Monitor
   ↓
115200 baud
```

There is no external rain-sensor library to troubleshoot here. If Verify fails, focus first on board selection, TinyUSB/BSP, or syntax rather than the RAK12030 pad.

## Step 15.6 - Dry-pad baseline

Start with the RAK12030 completely dry.

Expected output:

```text
RAK12005 digital state = LOW
rain_wet = 0
```

Observe at least five consecutive dry readings. A stable LOW state proves the detector is not falsely asserting rain while the pad is dry.

## Step 15.7 - Wet-pad response

Apply a few drops of clean water directly across the exposed copper traces of the **RAK12030 sensing pad only**.

Do not wet the RAK12005 module or the base board.

RAK's current quick-start states that when water is present, the comparator output switches HIGH. Expected output:

```text
RAK12005 digital state = HIGH
rain_wet = 1
```

Observe at least five consecutive wet readings.

If the pad is clearly wet but the state remains LOW, first verify the RAK12030 cable and RAK12005 seating. Only then consider a small threshold adjustment using the RAK12005 potentiometer. Record any threshold adjustment because it becomes part of the device baseline.

## Step 15.8 - Return-to-dry response

After the wet state is proven:

```text
remove water
   ↓
wipe RAK12030 sensing pad
   ↓
allow copper traces to dry
   ↓
watch Serial Monitor
```

The output should return to:

```text
RAK12005 digital state = LOW
rain_wet = 0
```

This wet-then-dry transition is important because a detector stuck HIGH would be useless for the final experiment even if it can detect the initial water application.

## Step 15.9 - What counts as PASS?

```text
RAK12030 initially dry                  PASS
five stable dry readings = LOW / 0      PASS
water on pad changes state to HIGH / 1  PASS
five stable wet readings                PASS
pad drying returns state to LOW / 0     PASS
RAK12005/base electronics stayed dry    PASS
```

Final payload field:

```text
rain_wet
```

Encode it exactly as:

```text
0 = dry
1 = wet / conductive water detected
```

Do not invent an analog rainfall amount from this module. The RAK12005/RAK12030 path used here is a binary water/rain detector.

---

# Part 16 - What has been proven after the bench sensor sequence

Current status after the completed tests and deferred UV stimulus is:

```text
Arduino IDE / RAK BSP          PASS
USB / COM port                 PASS
DFU bootloader upload          PASS
RAK4631 CPU execution          PASS
USB Serial                     PASS
RAK19001 3V3_S sensor power    PASS
I2C basic operation            PASS
RAK1903 / OPT3001              PASS
RAK12010 / VEML7700            PASS
RAK12011 / LPS33HW             PASS
RAK1906 / BME680               PASS; burn-in gate COMPLETE (operator-marked)
RAK12019 / LTR390 UV           PASS; physical-response gate COMPLETE (operator-marked)
RAK12023 + RAK12035 soil       PASS; dry=560, wet=328, response gate COMPLETE (operator-marked)
RAK12005 + RAK12030 rain       PASS; compile/upload succeeded and operator confirmed responsive dry/wet behavior
```

EMU-01 SENSOR-TYPE COUNT = 7 / 7 COMPLETE.

All seven intended EMU-01 sensing types are now marked complete for project tracking. The seven types are OPT3001 light, LTR390 UV, LPS33HW barometer/temperature, BME680 environment, VEML7700 light, RAK12035 soil moisture/temperature, and RAK12030/RAK12005 rain detection. Where a completion was operator-declared rather than accompanied by new numeric output in this walkthrough, preserve that distinction in the evidence record instead of inventing measurements.

This still does **not** prove the B-copy sensors.

---

# Part 17 - Error classification cheat sheet

Use the first error shown, not random hardware changes.

```text
ERROR / SYMPTOM
      │
      ├─ "No such file or directory" for a .h
      │      -> library/header problem
      │
      ├─ undefined reference to Serial / Adafruit_USBD_CDC
      │      -> TinyUSB / BSP link problem
      │
      ├─ Verify succeeds but Upload fails
      │      -> COM port / DFU / bootloader / USB problem
      │
      ├─ "Device programmed." but Serial Monitor blank
      │      -> check port, baud 115200, reset, sketch execution
      │
      ├─ Serial works but "Sensor not found"
      │      -> sensor power / I2C / slot / connector / device problem
      │
      └─ sensor prints values but physical stimulus does not change them
             -> wrong sensor being manipulated, stale/incorrect read,
                sensor placement, or sensor/driver problem
```

The principle is:

```text
fix the first failing layer
before changing the next layer
```

---

# Part 18 - Evidence to save

Record at minimum:

```text
Arduino IDE version
RAKwireless BSP version
selected board = WisBlock Core RAK4631 Board
Windows COM port used during bring-up
sanity sketch compile result
sanity sketch upload result
RAK1903 library version
RAK1903 light response result
RAK12010 library version
RAK12010 light response result
RAK12010 underside/light-clearance result
RAK12011 / Adafruit LPS2X library version
RAK12011 pressure/temperature result
RAK1906 / Adafruit BME680 library version
RAK1906 four-field result
RAK1906 first-use burn-in completion = COMPLETE (operator-marked; no new timed log captured here)
RAK12019_LTR390 library version
RAK12019 UV-mode/UVI/raw-UVS result
RAK12019 current captured observation = UVI 0.00 / raw UVS 0 indoors
RAK12019 physical-response acceptance gate = COMPLETE (operator-marked; no additional outdoor values captured here)
RAK12019 ALS diagnostic result if later needed
RAK12035_SoilMoisture library version
RAK12035 firmware version
RAK12035 dry calibration capacitance = 560 from the successful official calibration run
RAK12035 wet calibration capacitance = 328 from the successful official calibration run
RAK12035 moisture/temperature response gate = COMPLETE (operator-marked; no additional endpoint values captured here)
soil calibration method used for the final experiment
RAK12005 dry baseline = LOW / rain_wet 0
RAK12005 wet response = HIGH / rain_wet 1
RAK12005 return-to-dry response = LOW / rain_wet 0
RAK12005 threshold/potentiometer adjustment, if any
RAK12005 observed compile/upload = PASS on COM12
RAK12005 operator-confirmed responsive dry/wet behavior = PASS
any workaround required, including TinyUSB include
```

Do not store AppKeys or session keys here.

Suggested file:

```text
chapter4-results/_device-baseline/sensors/arduino-first-bringup.txt
```

---

# Continue

The EMU-01 A-set now has all seven intended sensing types marked complete for project tracking. Three acceptance items that previously remained open—RAK1906 first-use burn-in, RAK12019 physical-response verification, and the RAK12035 wet-to-dry response gate—were explicitly marked complete by the operator; no unrecorded numeric measurements are invented here.

The **RAK12005 + RAK12030 rain sensor on WisIO 2 is functionally PASS**: the sketch compiled, uploaded successfully on COM12, and the operator confirmed that the values respond to the pad's dry/wet condition. Proceed to the B-copy sensor verification on SEC-02.

Before moving any B-copy module, open [02b-rak19007-sec02-fixed-profiles.md](02b-rak19007-sec02-fixed-profiles.md). It freezes the SEC-02 positions as Profile A `A=RAK1903-B, B=RAK12010-B, C=RAK12019-B, D=RAK12011-B, IO=RAK12023+RAK12035-B`, followed—only after complete power removal—by Profile B `A=RAK1906-B, B/C/D=EMPTY, IO=RAK12005+RAK12030-B`. Do not use the EMU-01 RAK19001 A-F map on the RAK19007.

The broader checklist remains in:

[04-verify-all-sensors.md](04-verify-all-sensors.md)

## Official references

- RAK4631 Arduino BSP / nRF52 core: `https://github.com/RAKWireless/RAK-nRF52-Arduino`
- RAK1903 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak1903/quickstart/`
- RAK12010 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak12010/quickstart/`
- RAK12011 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak12011/quickstart/`
- RAK12011 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12011/datasheet/`
- RAK1906 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak1906/quickstart/`
- RAK1906 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak1906/datasheet/`
- RAK12019 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak12019/quickstart/`
- RAK12019 overview: `https://docs.rakwireless.com/product-categories/wisblock/rak12019/overview/`
- RAK12023 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak12023/quickstart/`
- RAK12035 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak12035/quickstart/`
- RAK12005 quick start: `https://docs.rakwireless.com/product-categories/wisblock/rak12005/quickstart/`
- RAK12005 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12005/datasheet/`
- Adafruit TinyUSB: `https://github.com/adafruit/Adafruit_TinyUSB_Arduino`
