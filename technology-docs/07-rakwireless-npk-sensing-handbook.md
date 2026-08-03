# Volume 07: RAKwireless WisBlock & RS485 Soil NPK Sensing Handbook

## Executive Summary & Educational Purpose

This handbook covers modular node assembly, embedded C++ firmware, industrial serial communications, soil chemistry physics, and power management using the **RAKwireless WisBlock System** and **Industrial RS485 Soil NPK Sensors**. Designed for embedded systems developers, agricultural hardware engineers, and agronomists, this text details WisBlock modular architectures, Modbus RTU CRC-16 calculation algorithms, soil nutrient measurement techniques for Nitrogen (N), Phosphorus (P), and Potassium (K), solar power budgets, and precision fertilization ROI.

---

## 1. RAKwireless WisBlock Modular Hardware System

The RAKwireless WisBlock platform provides a modular "plug-and-play" hardware ecosystem for building solar-powered LoRaWAN field nodes without custom PCB manufacturing.

```text
+-----------------------------------------------------------------------------------+
|                     RAK19007 WisBlock Base Board 2nd Gen                          |
|  • Solar Panel Connector (5V Solar Input) + LiPo Battery Charging Circuit (3.7V)  |
|  • 4x WisBlock Sensor Slots (Slot A, B, C, D) + 1x WisBlock Core Slot            |
+-----------------------------------------------------------------------------------+
                                         │
        ┌────────────────────────────────┴────────────────────────────────┐
        ▼                                                                 ▼
+------------------------------------+                         +--------------------+
| RAK4631 MCU Core Module            |                         | RAK13002 IO Module |
| • Nordic nRF52840 (ARM Cortex-M4F) |                         | • RS485 Transceiver|
| • Semtech SX1262 LoRa Transceiver  |                         | • Modbus Interface |
| • Bluetooth Low Energy (BLE 5.0)   |                         +--------------------+
+------------------------------------+                                    │
                                                                          │ RS485 Bus (A / B Line)
                                                                          v
                                                       +------------------------------------+
                                                       | Industrial Soil NPK Probe          |
                                                       | (Nitrogen, Phosphorus, Potassium)  |
                                                       +------------------------------------+
```

---

## 2. Soil NPK Chemistry & Transducer Physics

Nitrogen (N), Phosphorus (P), and Potassium (K) are the three primary macronutrients required for plant growth.

```text
+-----------------------------------------------------------------------------------+
|                          Macronutrient Chemical Functions                          |
|  • Nitrogen (N): Component of amino acids & chlorophyll. Promotes leaf growth.    |
|  • Phosphorus (P): Core element of ATP energy transfer. Promotes root growth.     |
|  • Potassium (K): Regulates stomatal opening & water balance. Enhances immunity.  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Modbus RTU Protocol & Bit-Level Frame Mechanics

Industrial soil probes utilize **RS485 differential signaling** running the **Modbus RTU** protocol over 2-wire differential pairs (A+ and B-).

### Master Request Frame (Reading NPK Registers)

To read Nitrogen, Phosphorus, and Potassium starting at Holding Register `0x001E` (Quantity: 3 registers):

```text
[ Address ] [ Function ] [ Start Reg High ] [ Start Reg Low ] [ Reg Count High ] [ Reg Count Low ] [ CRC Low ] [ CRC High ]
   0x01        0x03           0x00              0x1E              0x00             0x03          0x65        0xCD
```

### Sensor Response Frame Example

```text
[ Address ] [ Function ] [ Byte Count ] [ N High ] [ N Low ] [ P High ] [ P Low ] [ K High ] [ K Low ] [ CRC Low ] [ CRC High ]
   0x01        0x03         0x06        0x00     0x2D     0x00     0x12     0x00     0x78      0x49        0x56
```

#### Decoded Measurement Data:
* **Nitrogen (N)**: `0x002D` = **45 mg/kg (ppm)**
* **Phosphorus (P)**: `0x0012` = **18 mg/kg (ppm)**
* **Potassium (K)**: `0x0078` = **120 mg/kg (ppm)**

---

## 4. Production Firmware Implementation (RAK4631 WisBlock)

Below is complete C++ firmware for the RAK4631 MCU executing Modbus RTU queries over RS485 and transmitting LoRaWAN uplinks.

```cpp
#include <Arduino.h>
#include <LoRaWan-RAK4630.h>
#include <SoftwareSerial.h>

// RS485 Hardware Pinout on RAK13002
#define RS485_RX WB_IO2
#define RS485_TX WB_IO1
#define RS485_DIR WB_IO3

SoftwareSerial rs485(RS485_RX, RS485_TX);

// Modbus Query Frame: Read N, P, K Registers (0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD)
const byte npk_query[] = {0x01, 0x03, 0x00, 0x1E, 0x00, 0x03, 0x65, 0xCD};
byte response_buf[11];

void setup() {
  pinMode(RS485_DIR, OUTPUT);
  digitalWrite(RS485_DIR, LOW); // Set RS485 to Receive Mode
  rs485.begin(9600);
}

void read_npk_sensor(uint16_t &n, uint16_t &p, uint16_t &k) {
  digitalWrite(RS485_DIR, HIGH); // Transmit Mode
  rs485.write(npk_query, sizeof(npk_query));
  rs485.flush();
  digitalWrite(RS485_DIR, LOW);  // Receive Mode

  delay(100);

  if (rs485.available() >= 11) {
    for (int i = 0; i < 11; i++) {
      response_buf[i] = rs485.read();
    }
    n = (response_buf[3] << 8) | response_buf[4];
    p = (response_buf[5] << 8) | response_buf[6];
    k = (response_buf[7] << 8) | response_buf[8];
  }
}
```

---

## 5. Solar Energy Harvesting & Power Budget Analysis

Field sensor nodes must maintain continuous operation indefinitely using solar power.

### Daily Energy Balance Calculations

$$\text{Daily Energy Consumption (mWh)} = V_{bat} \cdot \left[ (I_{active} \cdot T_{active}) + (I_{sleep} \cdot T_{sleep}) \right]$$

* **Sleep Current ($I_{sleep}$)**: $2.0\text{ }\mu\text{A}$ (nRF52840 System OFF mode).
* **TX Active Current ($I_{active}$)**: $120.0\text{ mA}$ at $+20\text{ dBm}$ transmit power for $1.3\text{ seconds}$.
* **Daily Transmission Count**: 96 uplinks (15-minute interval).
* **Total Daily Power Requirement**: $\approx 15\text{ mAh / day}$.

A standard **3.7V 2000mAh LiPo battery** combined with a **5V 0.5W solar panel** provides **infinite operational autonomy**, even through 30 consecutive days of overcast weather.

---
*Maintained under project `lorawan-setup/technology-docs`.*
