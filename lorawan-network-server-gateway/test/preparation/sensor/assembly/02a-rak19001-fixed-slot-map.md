# Sensor Assembly 2A - Fixed RAK19001 Slot Map for EMU-01

This file freezes the **permanent physical slot assignment** for the RAK19001 used by EMU-01.

Do not choose slots ad hoc during assembly. Use this map unless the actual installed hardware revision or the current RAK WisBlock Pin Mapper reports a conflict. If that happens, stop, record the mapper result, and revise the documented baseline before continuing.

## Final permanent map

```text
RAK19001 / EMU-01

Sensor Slot A  -> RAK1903   OPT3001 ambient light
Sensor Slot B  -> EMPTY     reserved / do not use
Sensor Slot C  -> RAK12019  UV sensor
Sensor Slot D  -> RAK12011  barometer + temperature
Sensor Slot E  -> RAK1906   BME680 environmental sensor
Sensor Slot F  -> RAK12010  VEML7700 ambient light

WisIO Slot 1   -> RAK12023 -> one RAK12035 soil probe
WisIO Slot 2   -> RAK12005 -> RAK12030 rain pad

CPU Slot       -> RAK4631 Core A
LoRa RF        -> correct LoRa antenna
USB-C          -> setup/programming/source-log laptop
```

## ASCII board architecture

This diagram is a logical slot map. Follow the **A-F / WisIO silkscreen on the actual RAK19001** when installing modules.

```text
                 RAK19001 - EMU-01 FIXED SENSOR MAP

          SENSOR SLOTS                         WISIO SLOTS

  ┌───────────────────────────┐        ┌───────────────────────────┐
  │ A  RAK1903 OPT3001       │        │ WisIO 1                  │
  │    ambient light         │        │ RAK12023                 │
  │    INT -> WB_IO1         │        │   │                      │
  │                          │        │   └──> RAK12035 SOIL     │
  │ B  EMPTY                 │        │       I2C1 + WB_IO4      │
  │    reserve WB_IO2        │        │                          │
  │                          │        │ WisIO 2                  │
  │ C  RAK12019 UV           │        │ RAK12005                 │
  │    INT -> WB_IO3         │        │   │                      │
  │                          │        │   └──> RAK12030 RAIN     │
  │ D  RAK12011 BARO         │        │       OUT -> WB_IO6     │
  │    INT -> WB_IO5         │        └───────────────────────────┘
  │                          │
  │ E  RAK1906 BME680        │
  │    I2C only              │
  │                          │
  │ F  RAK12010 VEML7700     │
  │    I2C only              │
  └─────────────┬─────────────┘
                │
                ▼
        ┌───────────────────┐
        │ CPU: RAK4631      │────> LoRa antenna
        └─────────┬─────────┘
                  │
                  └──────────────> USB-C programming / serial log
```

## Why this map is used

The RAK19001 has six Sensor slots A-F. The I2C, SPI, power, and ground lines are shared across the Sensor slots, but the slot-specific GPIO lines are different.

The RAK19001 slot-to-default GPIO mapping used by interrupt-capable WisBlock Sensor modules is:

| Sensor slot | Default slot GPIO | Decision in this project |
|---|---:|---|
| A | `WB_IO1` | RAK1903 |
| B | `WB_IO2` | **EMPTY** |
| C | `WB_IO3` | RAK12019 |
| D | `WB_IO5` | RAK12011 |
| E | `WB_IO4` | RAK1906, which does not require the slot interrupt GPIO |
| F | `WB_IO6` | RAK12010, which does not require the slot interrupt GPIO |

### Reason 1 - Slot B stays empty

`WB_IO2` controls the RAK19001 `3V3_S` switched sensor-power rail. The project therefore does not place an interrupt-dependent sensor in Slot B.

Leaving B empty gives the integrated firmware one simple rule:

```text
WB_IO2 = shared 3V3_S power control
not a sensor interrupt line
```

This also preserves one physical Sensor slot as a troubleshooting/reserve position.

### Reason 2 - The interrupt-capable modules use A, C, and D

The permanent build contains three modules whose WisBlock connectors expose an interrupt/output line:

```text
RAK1903  OPT3001 interrupt
RAK12019 LTR-390UV interrupt
RAK12011 barometer digital output/interrupt
```

They are assigned to:

```text
RAK1903   -> Slot A -> WB_IO1
RAK12019  -> Slot C -> WB_IO3
RAK12011  -> Slot D -> WB_IO5
```

This keeps them away from `WB_IO4` and `WB_IO6`, which are already required by the two IO-slot agriculture modules.

### Reason 3 - Soil uses WB_IO4

RAK12023 uses:

```text
I2C1
WB_IO4
3V3_S
GND
```

Therefore Sensor Slot E is **not** used for an interrupt-dependent module in this build, because a typical slot-E interrupt maps to `WB_IO4`.

RAK1906 is safe in E because the BME680 module uses I2C plus power/ground and does not require the slot GPIO for its normal sensor readings.

### Reason 4 - Rain uses WB_IO6

RAK12005 exposes its rain/water digital output on `WB_IO6`.

Therefore Sensor Slot F is **not** used for an interrupt-dependent module in this build, because a typical slot-F interrupt maps to `WB_IO6`.

RAK12010 is safe in F because its VEML7700 communication is I2C based and the normal measurement path does not require the slot GPIO.

## Environmental placement decisions

Electrical conflict avoidance takes priority over cosmetic symmetry.

### RAK1903 in Slot A

Slot A is selected for the OPT3001 because:

- RAK1903 is valid on A/C/D/E/F according to its datasheet;
- A maps its interrupt to the otherwise free `WB_IO1`;
- WisBlock Sensor modules in Slot A can be oriented outward from the base when the physical build allows it;
- the outward position helps prevent another board/cable from shading the optical sensor.

Install it so the light-sensitive surface remains unobstructed.

### RAK12019 in Slot C

RAK12019 is restricted to Sensor C-F. Slot C is selected because:

- it satisfies the module restriction;
- its interrupt maps to free `WB_IO3`;
- Slot C can be oriented outward when the base/mechanical build permits it;
- the UV optical surface can be kept clear of the core, antenna cable, and enclosure wall.

### RAK12011 in Slot D

RAK12011 works on A and C-F, but not B. Slot D gives it `WB_IO5`, which is not consumed by the soil or rain IO modules.

Keep the pressure sensing area open to ambient air. Water tolerance of the sensor module does **not** make the RAK19001 base waterproof.

### RAK1906 in Slot E

RAK1906 can use A-F and only requires I2C/power/ground for the normal BME680 measurements. Slot E is therefore used to avoid consuming another unique GPIO.

Because the BME680 measures ambient temperature/humidity and can be affected by local board heat:

```text
keep airflow around RAK1906
keep it away from direct MCU/regulator heat where enclosure design allows
perform the documented burn-in/stabilization
never use a just-powered reading as the environmental baseline
```

If later enclosure measurements prove base-board heat materially biases the BME680, solve that mechanically (airflow, enclosure spacing, or a supported extension strategy) and document the change; do not silently move the module to a GPIO-conflicting slot.

### RAK12010 in Slot F

RAK12010 supports A-F and uses I2C for the VEML7700 measurement. Slot F therefore avoids consuming the interrupt GPIOs required by A/C/D.

Keep the optical surface unobstructed and record it separately from the RAK1903 OPT3001 reading.

## WisIO Slot assignment

The two RAK19001 40-pin WisIO connectors expose the same IO, UART, SPI, and I2C signals. For reproducible assembly, this project still freezes their roles:

```text
WisIO Slot 1 -> RAK12023 soil connector
WisIO Slot 2 -> RAK12005 rain module
```

If the actual board/mapper labels the two connectors as `Connector A/B` instead of `WisIO 1/2`, record the physical silkscreen-to-project-name mapping once in `sensor-pin-map.txt`.

Do not swap them after the testbed baseline is frozen, even though the two base-board IO connectors are electrically equivalent.

## Shared 3V3_S rule

RAK12023 and RAK12005 use the switched `3V3_S` sensor-power rail, controlled through `WB_IO2` on the base/core interface.

Treat it as a shared rail:

```text
WB_IO2 HIGH/active as required
      │
      ├── powers switched sensor rail used by soil path
      └── powers switched sensor rail used by rain path
```

Do not write firmware that assumes `WB_IO2` independently powers only one of these modules.

## Pin Mapper values to enter

In the current WisBlock Pin Mapper choose:

```text
WisBase        = RAK19001
WisCore        = RAK4631

Sensor Slot A  = RAK1903
Sensor Slot B  = NA / unused
Sensor Slot C  = RAK12019
Sensor Slot D  = RAK12011
Sensor Slot E  = RAK1906
Sensor Slot F  = RAK12010

WisIO Slot 1   = RAK12023
WisIO Slot 2   = RAK12005
```

Then inspect the mapper for highlighted conflicts.

Expected project allocation:

```text
WB_IO1 -> RAK1903 interrupt
WB_IO2 -> 3V3_S control
WB_IO3 -> RAK12019 interrupt
WB_IO4 -> RAK12023 soil connector
WB_IO5 -> RAK12011 interrupt/output
WB_IO6 -> RAK12005 rain digital output
```

This is why the map uses every available `WB_IO1` through `WB_IO6` exactly once by role and leaves Sensor B physically unused.

## Mapper acceptance record

Create/update:

```text
chapter4-results/_device-baseline/sensors/sensor-pin-map.txt
```

Record:

```text
WisBase=RAK19001
WisCore=RAK4631
Sensor_A=RAK1903
Sensor_B=NA
Sensor_C=RAK12019
Sensor_D=RAK12011
Sensor_E=RAK1906
Sensor_F=RAK12010
WisIO_1=RAK12023
WisIO_2=RAK12005
WB_IO1=RAK1903_INT
WB_IO2=3V3_S_CONTROL
WB_IO3=RAK12019_INT
WB_IO4=RAK12023
WB_IO5=RAK12011_INT
WB_IO6=RAK12005_RAIN_OUT
mapper_conflicts=NONE
```

Save a screenshot/export of the accepted mapper result if practical.

If the mapper reports a real conflict, `mapper_conflicts=NONE` must **not** be written. Stop and resolve the conflict first.

## Do not move sensors after baseline freeze

Once this map passes integrated sensor verification and preflight:

```text
A = RAK1903
B = EMPTY
C = RAK12019
D = RAK12011
E = RAK1906
F = RAK12010
IO1 = RAK12023
IO2 = RAK12005
```

becomes part of the experiment configuration.

Changing a slot can change the GPIO seen by firmware, mechanical exposure, and measurement environment. Any later slot change requires:

1. power off;
2. update Pin Mapper;
3. update firmware pin definitions if applicable;
4. repeat individual/integrated sensor verification;
5. repeat the full sensor preflight;
6. create a new baseline revision before counted testing resumes.

## Official references

- RAK19001 software configuration / Pin Mapper entry point: `https://docs.rakwireless.com/product-categories/wisblock/rak19001/software-configuration/`
- RAK19001 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak19001/datasheet/`
- WisBlock Pin Mapper guide: `https://learn.rakwireless.com/hc/en-us/articles/26743306645143-How-To-Use-the-WisBlock-IO-Pin-Mapping-Tool`
- WisBlock general quick start: `https://docs.rakwireless.com/product-categories/wisblock/quickstart/`
- RAK1903 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak1903/datasheet/`
- RAK12019 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12019/datasheet/`
- RAK12011 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12011/datasheet/`
- RAK1906 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak1906/datasheet/`
- RAK12010 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12010/datasheet/`
- RAK12023 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12023/datasheet/`
- RAK12005 datasheet: `https://docs.rakwireless.com/product-categories/wisblock/rak12005/datasheet/`
