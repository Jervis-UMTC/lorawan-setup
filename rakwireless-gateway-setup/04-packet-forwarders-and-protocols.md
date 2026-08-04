# LoRaWAN Packet Forwarder Architecture & Protocol Manual

This document provides an exhaustive technical analysis and line-by-line configuration guide for the three primary LoRaWAN gateway packet forwarder protocols: **Semtech UDP Packet Forwarder**, **Semtech Basic Station (LNS/CUPS)**, and **ChirpStack Concentratord / Gateway Bridge**.

---

## 1. Protocol Comparison Matrix

```text
+-----------------------------------------------------------------------------------+
|                        PACKET FORWARDER PROTOCOL COMPARISON                       |
|                                                                                   |
|  1. Semtech UDP Packet Forwarder (Legacy)                                         |
|     Gateway [UDP Packets / Port 1700 (Unencrypted)] --------> Network Server      |
|                                                                                   |
|  2. Semtech Basic Station (Modern Standard)                                        |
|     Gateway [WebSocket / TLS 1.3 mTLS (wss://)] --------------> Network Server      |
|                                                                                   |
|  3. ChirpStack Concentratord + Gateway Bridge (Optimized Private)                 |
|     Gateway [ZMQ IPC] -> Bridge [Protobuf over MQTT/TLS] ----> Network Server     |
+-----------------------------------------------------------------------------------+
```

| Feature / Criteria | Semtech UDP Packet Forwarder | Semtech Basic Station (LNS/CUPS) | ChirpStack Concentratord & Gateway Bridge |
| :--- | :--- | :--- | :--- |
| **Transport Layer** | Connectionless UDP (Port 1700) | WebSockets (WS/WSS) over TCP | ZMQ IPC + MQTT over TCP |
| **Security & Encryption** | None (Plaintext JSON in UDP payload) | TLS 1.3 / mTLS Client Certificate Auth | TLS 1.3 / MQTT Client Certificate Auth |
| **Network Resilience** | Poor (UDP packets dropped by firewalls) | Excellent (Automatic reconnect, buffering) | Excellent (MQTT QoS 1 / Retain / Offline queue) |
| **Remote Management** | None | Full CUPS (Firmware update & key rotation) | Via MQTT Command Topics |
| **Time Sync** | GPS NMEA text required | LNS Time Sync protocol (no GPS needed) | System Clock / GPS PPS |

---

## 2. Semtech UDP Packet Forwarder Mechanics

The Semtech UDP packet forwarder reads raw IQ data from the SX1302/SX1303 concentrator over SPI, decodes LoRa PHY frames, encapsulates them in a custom binary/JSON UDP packet header, and transmits them to UDP port 1700 of the network server.

### 2.1 Packet Format & Framing
- **PULL_DATA (0x02)**: Sent by gateway every 10s to open NAT ports on routers.
- **PUSH_DATA (0x00)**: Contains received LoRaWAN RF frames in base64 payload inside JSON array `rxpk`.
- **PULL_RESP (0x03)**: Sent by LNS to schedule downlinks via `txpk` JSON array.

### 2.2 Exhaustive Line-by-Line Breakdown of `global_conf.json`

A valid `global_conf.json` file configures the hardware RF front-ends, baseband DSP channels, and network connection parameters.

```json
{
  "SX1302_conf": {
    "spidev_path": "/dev/spidev0.0",
    "com_type": "SPI",
    "com_path": "/dev/spidev0.0",
    "lorawan_public": true,
    "clksrc": 0,
    "full_duplex": false,
    "precision_timestamp": {
      "enable": false
    },
    "radio_0": {
      "enable": true,
      "type": "SX1250",
      "freq": 923200000,
      "rssi_offset": -215.0,
      "rssi_temp_compensation": {
        "coeff_a": 0.0,
        "coeff_b": 0.0,
        "coeff_c": 0.0,
        "coeff_d": 0.0,
        "coeff_e": 0.0
      },
      "tx_enable": true,
      "tx_freq_min": 920000000,
      "tx_freq_max": 928000000
    },
    "radio_1": {
      "enable": true,
      "type": "SX1250",
      "freq": 924000000,
      "rssi_offset": -215.0,
      "rssi_temp_compensation": {
        "coeff_a": 0.0,
        "coeff_b": 0.0,
        "coeff_c": 0.0,
        "coeff_d": 0.0,
        "coeff_e": 0.0
      },
      "tx_enable": false
    },
    "chan_multiSF_0": {
      "enable": true,
      "radio": 0,
      "if": -200000
    },
    "chan_multiSF_1": {
      "enable": true,
      "radio": 0,
      "if": 0
    },
    "chan_multiSF_2": {
      "enable": true,
      "radio": 0,
      "if": 200000
    },
    "chan_multiSF_3": {
      "enable": true,
      "radio": 0,
      "if": 400000
    },
    "chan_multiSF_4": {
      "enable": true,
      "radio": 1,
      "if": -200000
    },
    "chan_multiSF_5": {
      "enable": true,
      "radio": 1,
      "if": 0
    },
    "chan_multiSF_6": {
      "enable": true,
      "radio": 1,
      "if": 200000
    },
    "chan_multiSF_7": {
      "enable": true,
      "radio": 1,
      "if": 400000
    },
    "chan_Lora_std": {
      "enable": true,
      "radio": 0,
      "if": 300000,
      "bandwidth": 500000,
      "spread_factor": 7
    },
    "chan_FSK": {
      "enable": false
    }
  },
  "gateway_conf": {
    "gateway_ID": "AA555A0000000000",
    "server_address": "192.168.1.100",
    "serv_port_up": 1700,
    "serv_port_down": 1700,
    "keepalive_interval": 10,
    "stat_interval": 30,
    "push_timeout_ms": 100,
    "forward_crc_valid": true,
    "forward_crc_error": false,
    "forward_crc_disabled": false
  }
}
```

### 2.3 Parameter Breakdown
- **`spidev_path`**: Defines Linux device node for SPI communication with SX1302.
- **`lorawan_public`**: Must be set to `true` to match the standard LoRaWAN sync word (`0x34`). Setting to `false` configures private LoRa networks (`0x12`).
- **`radio_0.freq` & `radio_1.freq`**: Sets center RF frequencies for the two SX1250 RF transceivers. Individual multi-SF channels specify intermediate frequencies (`if`) relative to these center frequencies: $f_{\text{channel}} = f_{\text{radio}} + f_{\text{if}}$.
- **`stat_interval`**: Frequency in seconds at which the gateway sends health statistics (GPS coordinates, CPU load, RF packets received/transmitted).

---

## 3. Semtech Basic Station (LNS & CUPS Protocols)

Basic Station replaces fragile UDP sockets with secure, long-lived WebSocket connections (`wss://`).

### 3.1 Architecture Overview
- **LNS (LoRaWAN Network Server Protocol)**: Establishes a persistent WebSocket for frame exchange, downlink scheduling, and precise time synchronization.
- **CUPS (Configuration & Update Server Protocol)**: Periodically connects via HTTP/REST to fetch fresh configuration files (`station.conf`), channel plans, and firmware updates.

### 3.2 Basic Station File Hierarchy
- `/etc/station/station.conf`: Main configuration specifying radio driver parameters.
- `/etc/station/tc.uri`: Target LNS URI (e.g., `wss://eu1.cloud.thethings.network:8887`).
- `/etc/station/tc.trust`: Root CA certificate file verifying the server's identity.
- `/etc/station/tc.key` & `/etc/station/tc.crt`: Optional client TLS keypair for mutual authentication (mTLS).

### 3.3 Production `station.conf` Template

```json
{
  "SX1302_conf": {
    "spidev_path": "/dev/spidev0.0",
    "com_type": "SPI",
    "device": "/dev/spidev0.0",
    "radio_0": {
      "enable": true,
      "type": "SX1250",
      "freq": 923200000
    },
    "radio_1": {
      "enable": true,
      "type": "SX1250",
      "freq": 924000000
    }
  },
  "station_conf": {
    "routerid": "B827EBFFFE94C0B2",
    "radio_init": "/usr/local/bin/reset_rak_gateway.sh",
    "log_file": "stderr",
    "log_level": "INFO",
    "log_size": 1000000,
    "log_rotate": 3
  }
}
```

---

## 4. ChirpStack Gateway Bridge Architecture

When deploying private ChirpStack infrastructure, running **ChirpStack Gateway Bridge** directly on the RAK gateway provides maximum reliability.

```text
[RAK Concentrator] <---SPI---> [ChirpStack Concentratord] <---ZMQ---> [Gateway Bridge] <---MQTT/TLS---> [Central ChirpStack Server]
```

### 4.1 Production `chirpstack-gateway-bridge.toml`

```toml
[general]
log_level="info"

[integration.mqtt]
# Central ChirpStack MQTT Broker URL
server="tcp://192.168.1.100:1883"

# MQTT credentials
username=""
password=""

# Topic template prefix
topic_prefix="us915_0"

# QoS level (1 ensures delivery confirmation)
qos=1

# Clean session state
clean_session=false

[backend.concentratord]
# ZMQ sockets exposed by ChirpStack Concentratord
event_url="ipc:///tmp/concentratord_event"
command_url="ipc:///tmp/concentratord_command"

[meta_data]
# Forward gateway CPU and thermal stats to ChirpStack
[meta_data.static]
gateway_model="RAK5146-SPI-RaspberryPi"
```
