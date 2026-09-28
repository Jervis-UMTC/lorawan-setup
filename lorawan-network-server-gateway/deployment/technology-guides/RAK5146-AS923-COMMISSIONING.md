# RAK5146 / Concentratord / AS923 — Commissioned Setup and Acceptance

> Source boundary: physical RAK5146-115 assembly runbook, effective tracked Gateway OS UCI overlay, ChirpStack forwarding runbooks, and dated September 2026 real-RF observations. **Do not infer live channel settings from a generic AS923 country table.** Apply intentional radio changes to the gateway, ChirpStack region/device profile and legitimate sensor firmware together.

## 1. Identify the actual RF system

| Item | Commissioned value |
|---|---|
| Gateway board | Raspberry Pi 4B + RAK5146-115 SPI on RAK Pi HAT |
| Radio | SX1303; high-frequency 902–928 MHz module, matched 900–930 MHz antenna |
| Gateway EUI | `0016c001f139a1cb` from **active SX1302/SX1303 startup** |
| Effective Gateway OS options | `chipset=sx1302`, `model=rak_5146`, `region=AS923`, `channel_plan=as923`, `gnss=1` |
| MQTT prefix / broker | `as923`, `tcp://127.0.0.1:1883`, QoS 1 |
| Non-authoritative values | The inactive SX1301 configuration, example Gateway EUIs, historical AS923 subgroup prose |
| Alternate packet-forwarder | Disabled; must not contend for concentrator hardware |

The observed commissioned multi-SF channel span in the historical gateway startup ran from **923.2 MHz to 924.6 MHz**, and later real node transmissions were received at 923.2 and 923.4 MHz. That **does not by itself prove** every current channel, downlink bandwidth, RX2 frequency, or sensor RX window. Export/record the effective radio configuration and compare against ChirpStack and the sensor rather than inventing the missing table.

## 2. Physical assembly (all power disconnected)

1. Check module and antenna labels, particularly the SPI variant, not an ordinary PCIe modem.
2. Insert the RAK5146 into the intended HAT module socket; mount without flexing. Connect u.FL-to-SMA to **LoRa RF**, not GNSS, straight down.
3. Align the entire 40-pin HAT with the Raspberry Pi header; fix standoffs; confirm no offset, trapped cable or loose hardware.
4. Attach the matching antenna *before power or any transmit*. Protect RF connectors from mechanical stress.
5. Power on with known-good supply; use the actual installed Gateway OS image/overlay instead of rebuilding the Linux radio driver on the live gateway.

## 3. Configure the one correct radio service

In Gateway OS LuCI, open **ChirpStack → Concentratord**. Under Global enable Concentratord, choose the **SX1302/SX1303** chipset; under that chip family use RAK5146 shield/model, **AS923** regional plan and **SPI** (not USB). Keep the Gateway ID override blank so the active RAK5146 identity is retrieved. GNSS may remain enabled per commissioned configuration; GNSS warnings alone do not show LoRa RF is broken.

The reproducible tracked overlay uses:

```text
config global
    option enabled '1'
    option chipset 'sx1302'
config sx1302
    option model 'rak_5146'
    option region 'AS923'
    option channel_plan 'as923'
    option antenna_gain '2'
    option gnss '1'
```

Antenna gain must match the installed antenna and feed losses, not a convenient default copied from another site. Do not increase transmit power or bypass local regulations to "fix" reception.

Save & Apply **once** and allow SPI initialization. Leave the legacy UDP Forwarder disabled.

## 4. Read-only effective radio and EUI proof

On Gateway-01 (OpenWrt/BusyBox shell):

```sh
uci show chirpstack-concentratord
uci show chirpstack-udp-forwarder
ubus call chirpstack-concentratord-sx1302 concentratord_stats
logread -e chirpstack-concentratord | tail -n 120
ps w | grep -E '[c]hirpstack-concentratord|[u]dp-forwarder'
```

**PASS:** the active SX1302 startup retrieves `0016c001f139a1cb`, SPI initializes without recurring errors, `AS923/as923` is active, stats respond, and no second radio owner is running. Ignore inactive SX1301 example `gateway_id` fields. Save sanitized channels/frequencies from the *effective radio* and the equivalent ChirpStack config; do not publish OTAA secrets.

## 5. Configure the forwarding interface without bypassing the local buffer

LuCI **ChirpStack → MQTT Forwarder**: enabled, Concentratord backend, `tcp://127.0.0.1:1883`, prefix `as923`, QoS 1, Protobuf (JSON off), a stable gateway-specific client ID where supported; normal CRC-OK packets only. Do not put the public broker hostname or gateway mTLS private-key path into MQTT Forwarder. Gateway MQTT bridge holds the cloud-facing TLS credentials and persistence.

The image-overlay source explicitly sets:

```text
config global
    option enabled '1'
config mqtt
    option topic_prefix 'as923'
    option server 'tcp://127.0.0.1:1883'
    option qos '1'
```

**Commissioning caveat:** accepted September 1 immutable factory release baked QoS 0, while the tracked future image overlay and commissioned writable runtime use QoS 1. After reflashing the accepted immutable image, verify/reapply the protected runtime configuration rather than assuming it has the overlay’s later correction.

Prove loopback-only broker state:

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

**PASS:** only `127.0.0.1:1883`, not wildcard or Ethernet interface. If an authorized EMU-01 is present, one real uplink should appear under `as923/gateway/0016c001f139a1cb/event/#` locally, then the cloud bridge, ChirpStack device event, application row and independent gateway evidence journal. Binary Protobuf output is expected.

## 6. Diagnose in the right order

| Symptom | First failing boundary |
|---|---|
| No Gateway EUI or SPI/reset/calibration failure | Power/HAT seat/SPI/profile/module driver |
| EUI stable but no RF packet | Sensor serial attempt, antenna, matching channels/SF/BW |
| RF packet visible but local MQTT absent | MQTT Forwarder backend/topic/QoS/local broker |
| Local event visible but cloud absent | Gateway local persistent bridge, LTE dataplane, DNS, mTLS |
| ChirpStack hears JoinRequest but node cannot join | Protected OTAA identity/key, regional downlink RX1/RX2, scheduled downlink |
| Application event accepted but evidence unverified | Independent journal/witness/segment/object/verifier correlation |

No "two good uplinks = complete hardware acceptance": full EMU-01 preparation requires ten valid sensor cycles, fresh OTAA acceptance, at least ten post-join uplinks and ten matching serial/ChirpStack raw payload comparisons plus downstream verification. Do not run unnecessary RF tests during counted sessions.

## 7. Radio replacement/recovery

1. For a software-only outage, inspect service/config/log/UBus first. Change only the failing radio service, not OS and cloud together.
2. For physical reseating, **power off** first. Reboot with antenna connected, capture EUI from active startup.
3. If a replacement RAK5146 produces a different EUI, treat it as an intentional **identity migration** affecting ChirpStack registration, gateway-specific MQTT mTLS client certificate, broker ACL/topic, evidence source identity and commissioning/research records. Do not force the old EUI into the new radio without a separately reviewed identity migration.
4. Verify the complete region alignment: gateway channel list, ChirpStack `region_as923` effective settings and EMU/SEC operating profiles. Keep the current project’s plain `AS923` label unless a deliberate end-to-end migration is documented.
