# LoRaWAN Field Troubleshooting Catalog

Welcome to the **LoRaWAN Field Troubleshooting Catalog**. This directory contains modular, problem-specific manuals for diagnosing, troubleshooting, and resolving real-world field issues encountered across LoRaWAN networks, edge gateways, ChirpStack network servers, and end-node sensors.

---

## 📚 Troubleshooting Manual Index

Each manual below provides an executive symptom summary, root cause analysis, diagnostic commands (Linux CLI, ChirpStack logs, Wireshark filters, SQL queries), and a step-by-step resolution blueprint.

| Manual File | Core Problem | Key Symptoms | Primary Resolution Strategy |
| :--- | :--- | :--- | :--- |
| **[01-signal-collisions-airspace-congestion.md](./01-signal-collisions-airspace-congestion.md)** | **Signal Collisions & Congestion** | High packet loss during peak hours, radio interference, overlapping channels | Enable ADR, add $\pm 30\text{s}$ jitter, compress payloads to 11-byte hex arrays, enable LBT |
| **[02-frame-counter-discrepancy-fcnt-reset.md](./02-frame-counter-discrepancy-fcnt-reset.md)** | **FCnt Reset & Out-of-Sync Drops** | Packets visible on Gateway/SDR but ChirpStack silently drops them | Session re-alignment, persistent NVM FCnt, clean OTAA re-join, validation relaxation |
| **[03-mic-mismatch-cryptographic-failure.md](./03-mic-mismatch-cryptographic-failure.md)** | **MIC Mismatch & Crypto Errors** | ChirpStack logs "invalid MIC", Join-Request or Data Up rejected | Key auditing (`AppKey`/`NwkSKey`), LoRaWAN version alignment (1.0.3 vs 1.0.4), DevEUI byte-order check |
| **[04-downlink-latency-actuator-timeout.md](./04-downlink-latency-actuator-timeout.md)** | **Downlink Latency on Actuators** | Emergency `CLOSE_VALVE` downlinks sit queued; valve fails to close | Class B ping slots setup, Class C conversion for mains power, threshold alarm uplinks |
| **[05-offline-gateway-backhaul-buffer-overflow.md](./05-offline-gateway-backhaul-buffer-overflow.md)** | **Offline Backhaul & Packet Loss** | Cellular/Wi-Fi drops at remote farm; telemetry lost during storm outage | Direct AP mode (`192.168.23.150`), packet forwarder memory buffering, static Netplan routing |
| **[06-rf-attenuation-canopy-propagation-loss.md](./06-rf-attenuation-canopy-propagation-loss.md)** | **Canopy Foliage Absorption** | Low RSSI ($< -120\text{ dBm}$), negative SNR ($< -10\text{ dB}$), summer foliage drops | Antenna height optimization, high-gain omni selection, ADR Spreading Factor tuning |
| **[07-sensor-battery-drain-high-time-on-air.md](./07-sensor-battery-drain-high-time-on-air.md)** | **Rapid Sensor Battery Depletion** | Node battery dies in 3 months instead of 3–5 years | Fix SF12 lock-in, unconfirmed uplink migration, transmit interval tuning, sleep current audit |
| **[08-regional-frequency-band-mismatch.md](./08-regional-frequency-band-mismatch.md)** | **Regional Channel Mask Mismatch** | Raw RF energy visible on SDR, but ChirpStack ignores telemetry | Align `chirpstack.toml` region channels, match gateway `global_conf.json`, node AT channel mask |

---

## 🛠️ Diagnostics Decision Flowchart

```text
                                [ Field Issue Detected ]
                                           │
                        ┌──────────────────┴──────────────────┐
                        ▼                                     ▼
            [ Signal Invisible on SDR ]            [ Signal Visible on SDR ]
                        │                                     │
         ┌──────────────┴──────────────┐        ┌─────────────┴─────────────┐
         ▼                             ▼        ▼                           ▼
  [Check Antenna & ]          [Check Region & ]  [ChirpStack Drops Packet]  [Downlink Delayed]
  [Hardware Power  ]          [Channel Mask   ]           │                         │
  (See Manual 06)             (See Manual 08)   ┌─────────┴─────────┐       ┌───────┴───────┐
                                                ▼                   ▼       ▼               ▼
                                         [FCnt Out-of-Sync]   [Invalid MIC] [Class A Valve] [Offline AP]
                                         (See Manual 02)      (See Manual 03)(See Manual 04)(See Manual 05)
```
