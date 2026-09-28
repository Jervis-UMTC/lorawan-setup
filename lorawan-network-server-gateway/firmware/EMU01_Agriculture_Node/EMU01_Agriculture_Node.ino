#include <Adafruit_TinyUSB.h>
#include <Arduino.h>
#include <Wire.h>
#include <ClosedCube_OPT3001.h>
#include "Light_VEML7700.h"
#include <Adafruit_LPS2X.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME680.h>
#include "UVlight_LTR390.h"
#include "RAK12035_SoilMoisture.h"
#include <LoRaWan-RAK4630.h>
#include "payload_v2.h"
#include "emu01_credentials.h"

// Traffic profiles. Production is the default and remains the accepted field
// behavior. Define EMU01_COUNTED_TEST_PROFILE=1 at compile time only for the
// dissertation counted-test artifact. That profile changes timing only; radio,
// identity, payload-v2, sensors, and application behavior remain unchanged.
#ifndef EMU01_COUNTED_TEST_PROFILE
#define EMU01_COUNTED_TEST_PROFILE 0
#endif

#if EMU01_COUNTED_TEST_PROFILE
#define SAMPLE_INTERVAL_MS 15000UL
#define NORMAL_TX_INTERVAL_MS 15000UL
#define TX_JITTER_MS 0UL
#define INITIAL_TX_MIN_DELAY_MS 2000UL
#define EVENT_BACKOFF_MAX_MS 5000UL
#define EVENT_MIN_TX_INTERVAL_MS 15000UL
#else
// Production traffic policy for large deployments: sample locally every minute,
// routine uplinks every five minutes, stable DevEUI-derived initial staggering,
// and +/-15 s interval jitter to avoid fleet synchronization.
#define SAMPLE_INTERVAL_MS 60000UL
#define NORMAL_TX_INTERVAL_MS 300000UL
#define TX_JITTER_MS 15000UL
#define INITIAL_TX_MIN_DELAY_MS 2000UL
#define EVENT_BACKOFF_MAX_MS 5000UL
#define EVENT_MIN_TX_INTERVAL_MS 60000UL
#endif

#define RAIN_POLL_INTERVAL_MS 1000UL

#define APP_PORT 2
#define RAIN_PIN WB_IO6

ClosedCube_OPT3001 opt3001;
Light_VEML7700 veml7700 = Light_VEML7700();
Adafruit_LPS22 barometer;
Adafruit_BME680 bme;
UVlight_LTR390 uv = UVlight_LTR390();
RAK12035 soil;

static volatile bool networkJoined = false;
static uint32_t sequenceNo = 0;
static uint32_t nextSampleAt = 0;
static uint32_t nextNormalTxAt = 0;
static uint32_t nextRainPollAt = 0;
static uint32_t eventTxAt = 0;
static uint32_t lastEventTxAt = 0;
static bool eventPending = false;
static bool haveSample = false;
static bool haveRainState = false;
static uint8_t lastRainState = 0;
static Emu01Sample latestSample;
static uint8_t txBuffer[EMU01_PAYLOAD_SIZE];
static lmh_app_data_t txData = {txBuffer, 0, 0, 0, 0};

// AS923 in the pinned SX126x-Arduino stack defaults to 400 ms uplink dwell time.
// The frozen 46-byte payload is not valid at DR0-DR2; DR3 is the lowest compatible rate.
static lmh_param_t loraParams = {
    LORAWAN_ADR_ON,
    DR_3,
    LORAWAN_PUBLIC_NETWORK,
    3,
    TX_POWER_5,
    LORAWAN_DUTYCYCLE_OFF,
};

static bool timeReached(uint32_t now, uint32_t deadline) {
  return (int32_t)(now - deadline) >= 0;
}

static uint32_t hashDevEui() {
  // FNV-1a over the provisioned DevEUI gives a stable per-device phase without
  // storing another fleet-wide scheduling identifier.
  uint32_t h = 2166136261UL;
  for (size_t i = 0; i < 8; ++i) {
    h ^= nodeDeviceEUI[i];
    h *= 16777619UL;
  }
  return h;
}

static uint32_t randomRangeInclusive(uint32_t maximum) {
  if (maximum == 0) return 0;
  return (uint32_t)random(0, (long)maximum + 1L);
}

static uint32_t nextNormalInterval() {
  const int32_t jitter = (int32_t)random(0, (long)(TX_JITTER_MS * 2UL + 1UL)) -
                         (int32_t)TX_JITTER_MS;
  return (uint32_t)((int32_t)NORMAL_TX_INTERVAL_MS + jitter);
}

static void rxHandler(lmh_app_data_t *d) {
  Serial.print("DOWNLINK,port=");
  Serial.println(d->port);
}

static void joinedHandler() {
  networkJoined = true;
  const uint32_t now = millis();
  const uint32_t usableWindow = NORMAL_TX_INTERVAL_MS - INITIAL_TX_MIN_DELAY_MS;
  const uint32_t initialOffset = INITIAL_TX_MIN_DELAY_MS + (hashDevEui() % usableWindow);
  nextNormalTxAt = now + initialOffset;
  Serial.print("EMU01_OTAA_JOIN=PASS,initial_tx_offset_ms=");
  Serial.println(initialOffset);
}

static void joinFailedHandler() {
  Serial.println("EMU01_OTAA_JOIN=FAIL");
}

static void classHandler(DeviceClass_t c) {
  Serial.print("LORAWAN_CLASS=");
  Serial.println("ABC"[c]);
}

static lmh_callback_t loraCallbacks = {
    BoardGetBatteryLevel,
    BoardGetUniqueId,
    BoardGetRandomSeed,
    rxHandler,
    joinedHandler,
    classHandler,
    joinFailedHandler,
};

static uint16_t u16(float v) {
  if (v <= 0) return 0;
  if (v >= 65535) return 65535;
  return (uint16_t)lroundf(v);
}

static uint32_t u32(double v) {
  if (v <= 0) return 0;
  if (v >= 4294967295.0) return 0xFFFFFFFFUL;
  return (uint32_t)llround(v);
}

static int16_t i16(float v) {
  if (v <= -32768) return -32768;
  if (v >= 32767) return 32767;
  return (int16_t)lroundf(v);
}

static bool initSensors() {
  pinMode(WB_IO2, OUTPUT);
  digitalWrite(WB_IO2, HIGH);
  delay(500);
  Wire.begin();

  bool ok = true;
  opt3001.begin(0x44);
  OPT3001_Config c;
  c.RangeNumber = B1100;
  c.ConvertionTime = B0;
  c.Latch = B1;
  c.ModeOfConversionOperation = B11;
  ok &= (opt3001.writeConfig(c) == NO_ERROR);

  bool v = veml7700.begin();
  ok &= v;
  if (v) {
    veml7700.setGain(VEML7700_GAIN_1);
    veml7700.setIntegrationTime(VEML7700_IT_800MS);
  }

  bool p = barometer.begin_I2C(0x5D);
  ok &= p;
  if (p) barometer.setDataRate(LPS22_RATE_10_HZ);

  bool e = bme.begin(0x76);
  ok &= e;
  if (e) {
    bme.setTemperatureOversampling(BME680_OS_8X);
    bme.setHumidityOversampling(BME680_OS_2X);
    bme.setPressureOversampling(BME680_OS_4X);
    bme.setIIRFilterSize(BME680_FILTER_SIZE_3);
    bme.setGasHeater(320, 150);
  }

  bool x = uv.init();
  ok &= x;
  if (x) {
    uv.setMode(LTR390_MODE_UVS);
    uv.setGain(LTR390_GAIN_3);
    uv.setResolution(LTR390_RESOLUTION_16BIT);
  }

  soil.begin(true);
  pinMode(RAIN_PIN, INPUT);
  return ok;
}

static Emu01Sample sampleSensors() {
  Emu01Sample s;
  s.uptime_ms = millis();

  uint8_t m = 0;
  uint16_t st = 0;
  if (soil.get_sensor_moisture(&m) && soil.get_sensor_temperature(&st)) {
    s.soil_moisture_x100 = (uint16_t)m * 100u;
    s.soil_temperature_x100 = i16((st / 10.0f) * 100.0f);
    s.validity |= VALID_SOIL;
  }

  if (uv.newDataAvailable()) {
    s.uv_index_x100 = u16(uv.getUVI() * 100.0f);
    s.validity |= VALID_UV;
  }

  sensors_event_t t, p;
  barometer.getEvent(&p, &t);
  if (isfinite(p.pressure) && isfinite(t.temperature) && p.pressure > 0) {
    s.barometer_pressure_pa = u32(p.pressure * 100.0);
    s.barometer_temperature_x100 = i16(t.temperature * 100.0f);
    s.validity |= VALID_BAROMETER;
  }

  float vl = veml7700.readLux();
  if (isfinite(vl) && vl >= 0) {
    s.light_veml_lux_x100 = u32(vl * 100.0);
    s.validity |= VALID_VEML7700;
  }

  OPT3001 o = opt3001.readResult();
  if (o.error == NO_ERROR && isfinite(o.lux) && o.lux >= 0) {
    s.light_opt_lux_x100 = u32(o.lux * 100.0);
    s.validity |= VALID_OPT3001;
  }

  if (bme.performReading()) {
    s.environment_temperature_x100 = i16(bme.temperature * 100.0f);
    s.environment_humidity_x100 = u16(bme.humidity * 100.0f);
    s.environment_pressure_pa = u32(bme.pressure);
    s.environment_gas_ohm = u32(bme.gas_resistance);
    s.validity |= VALID_ENVIRONMENT;
  }

  s.rain_wet = digitalRead(RAIN_PIN) == HIGH ? 1 : 0;
  s.validity |= VALID_RAIN;
  return s;
}

static void refreshSample() {
  latestSample = sampleSensors();
  haveSample = true;
  if (!haveRainState) {
    lastRainState = latestSample.rain_wet;
    haveRainState = true;
  }
}

static void printCycle(const Emu01Sample &s, int status, const char *reason) {
  Serial.print("SENSOR_TX,seq=");
  Serial.print(s.sequence);
  Serial.print(",reason=");
  Serial.print(reason);
  Serial.print(",uptime_ms=");
  Serial.print(s.uptime_ms);
  Serial.print(",soil_pct=");
  Serial.print(s.soil_moisture_x100 / 100.0f, 2);
  Serial.print(",soil_temp_c=");
  Serial.print(s.soil_temperature_x100 / 100.0f, 2);
  Serial.print(",uv_index=");
  Serial.print(s.uv_index_x100 / 100.0f, 2);
  Serial.print(",baro_pa=");
  Serial.print(s.barometer_pressure_pa);
  Serial.print(",baro_temp_c=");
  Serial.print(s.barometer_temperature_x100 / 100.0f, 2);
  Serial.print(",light_veml_lux=");
  Serial.print(s.light_veml_lux_x100 / 100.0f, 2);
  Serial.print(",light_opt_lux=");
  Serial.print(s.light_opt_lux_x100 / 100.0f, 2);
  Serial.print(",env_temp_c=");
  Serial.print(s.environment_temperature_x100 / 100.0f, 2);
  Serial.print(",env_humidity_pct=");
  Serial.print(s.environment_humidity_x100 / 100.0f, 2);
  Serial.print(",env_pressure_pa=");
  Serial.print(s.environment_pressure_pa);
  Serial.print(",env_gas_ohm=");
  Serial.print(s.environment_gas_ohm);
  Serial.print(",rain_wet=");
  Serial.print(s.rain_wet);
  Serial.print(",battery_mv=");
  Serial.print(s.battery_mv);
  Serial.print(",valid=0x");
  Serial.print(s.validity, HEX);
  Serial.print(",join=");
  Serial.print(networkJoined ? 1 : 0);
  Serial.print(",send_status=");
  Serial.println(status);
}

static void sendLatest(const char *reason) {
  if (!haveSample) refreshSample();

  Emu01Sample outgoing = latestSample;
  outgoing.sequence = ++sequenceNo;
  outgoing.uptime_ms = millis();
  packPayloadV2(outgoing, txBuffer);
  txData.port = APP_PORT;
  txData.buffsize = EMU01_PAYLOAD_SIZE;

  int status = -1;
  if (lmh_join_status_get() == LMH_SET) {
    status = (int)lmh_send(&txData, LMH_UNCONFIRMED_MSG);
  }
  printCycle(outgoing, status, reason);
}

static void scheduleRainEvent(uint32_t now, uint8_t newState) {
  lastRainState = newState;
  if (!networkJoined || lmh_join_status_get() != LMH_SET) return;

  if (lastEventTxAt != 0 && !timeReached(now, lastEventTxAt + EVENT_MIN_TX_INTERVAL_MS)) {
    return;
  }

  eventTxAt = now + randomRangeInclusive(EVENT_BACKOFF_MAX_MS);
  eventPending = true;
  Serial.print("RAIN_EVENT_SCHEDULED,state=");
  Serial.print(newState);
  Serial.print(",backoff_ms=");
  Serial.println(eventTxAt - now);
}

static void pollRain(uint32_t now) {
  if (!timeReached(now, nextRainPollAt)) return;
  nextRainPollAt = now + RAIN_POLL_INTERVAL_MS;

  const uint8_t state = digitalRead(RAIN_PIN) == HIGH ? 1 : 0;
  if (!haveRainState) {
    lastRainState = state;
    haveRainState = true;
    return;
  }
  if (state != lastRainState) {
    if (haveSample) {
      latestSample.rain_wet = state;
      latestSample.validity |= VALID_RAIN;
    }
    scheduleRainEvent(now, state);
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("EMU01_BOOT");
#if EMU01_COUNTED_TEST_PROFILE
  Serial.println("EMU01_TRAFFIC_PROFILE=COUNTED_TEST_15S");
#else
  Serial.println("EMU01_TRAFFIC_PROFILE=PRODUCTION_5MIN");
#endif
  Serial.print("EMU01_SAMPLE_INTERVAL_MS=");
  Serial.println(SAMPLE_INTERVAL_MS);
  Serial.print("EMU01_NORMAL_TX_INTERVAL_MS=");
  Serial.println(NORMAL_TX_INTERVAL_MS);
  Serial.print("EMU01_TX_JITTER_MS=");
  Serial.println(TX_JITTER_MS);
  Serial.println(initSensors() ? "EMU01_SENSOR_INIT=PASS" : "EMU01_SENSOR_INIT=PARTIAL_FAIL");

  randomSeed(BoardGetRandomSeed() ^ hashDevEui());
  refreshSample();

  const uint32_t now = millis();
  nextSampleAt = now + SAMPLE_INTERVAL_MS;
  nextRainPollAt = now + RAIN_POLL_INTERVAL_MS;

  lora_rak4630_init();
  lmh_setDevEui(nodeDeviceEUI);
  lmh_setAppEui(nodeAppEUI);
  lmh_setAppKey(nodeAppKey);
  uint32_t st = lmh_init(&loraCallbacks, loraParams, true, CLASS_A, LORAMAC_REGION_AS923);
  if (st != 0) {
    Serial.print("LMH_INIT_FAIL=");
    Serial.println(st);
    while (1) delay(1000);
  }
  lmh_join();
}

void loop() {
  const uint32_t now = millis();

  pollRain(now);

  if (timeReached(now, nextSampleAt)) {
    refreshSample();
    do {
      nextSampleAt += SAMPLE_INTERVAL_MS;
    } while (timeReached(now, nextSampleAt));
  }

  if (networkJoined && lmh_join_status_get() == LMH_SET) {
    // Normal telemetry wins when a scheduled event is effectively simultaneous,
    // avoiding two back-to-back uplinks containing the same sample.
    if (timeReached(now, nextNormalTxAt)) {
      refreshSample();
      sendLatest("normal");
      nextNormalTxAt = now + nextNormalInterval();
      eventPending = false;
    } else if (eventPending && timeReached(now, eventTxAt)) {
      refreshSample();
      sendLatest("event");
      lastEventTxAt = now;
      eventPending = false;
    }
  }

  delay(10);
}
