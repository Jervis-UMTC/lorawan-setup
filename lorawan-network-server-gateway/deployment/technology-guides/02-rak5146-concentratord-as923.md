# RAK5146 / ChirpStack Concentratord / AS923 — Operator Manual

## What this technology does

The RAK5146/SX1303 is Gateway-01's LoRa concentrator. ChirpStack Concentratord is the only process allowed to control that radio. It receives LoRa frames from sensors and exposes the supported event interface used independently by MQTT Forwarder and the gateway evidence journal.

## Current radio contract

- Gateway: `Gateway-01`.
- Concentrator: RAK5146/SX1303 over SPI.
- Region: **AS923**.
- MQTT region/topic prefix: `as923`.
- Authoritative Gateway EUI: `0016c001f139a1cb`.
- MQTT Forwarder backend: Concentratord.
- Legacy Semtech UDP Packet Forwarder: disabled.

The current project baseline uses the plain label **AS923**. Some older setup prose contains more specific historical regional wording; do not relabel the active system from documentation alone. Verify exact live frequencies/channels before any radio change.

## Safety rules

1. Only one service may own the concentrator.
2. Never start the legacy UDP packet forwarder beside Concentratord.
3. Never change region/channel plan at only one layer. Sensor firmware, gateway, ChirpStack region, MQTT prefix, RX settings, and tests must remain compatible.
4. Do not raise transmit power to compensate for a receive problem.
5. Do not detach/reseat the RAK5146 while the gateway is powered.

## Step 1 — Confirm Concentratord is alive

Run on Gateway-01:

```sh
ubus call chirpstack-concentratord-sx1302 concentratord_stats
service chirpstack-concentratord-sx1302 status
```

**PASS means:** the service answers without an IPC/UBus error and returns live concentrator statistics.

If the service name differs after an intentional package change, discover it first rather than guessing:

```sh
ps w | grep '[c]hirpstack-concentratord'
uci show chirpstack-concentratord
```

## Step 2 — Confirm hardware identity from the active startup

```sh
logread -e chirpstack-concentratord | tail -n 120
```

Look for the successful SX1302/SX1303 startup and the retrieved Gateway ID.

**PASS means:** the active process reports Gateway EUI `0016c001f139a1cb` and does not repeatedly fail SPI reset/initialization.

**Do not:** select an arbitrary 16-hex value from inactive SX1301 configuration. The running RAK5146 startup is authoritative.

## Step 3 — Confirm effective radio configuration

```sh
uci show chirpstack-concentratord
```

Verify the active configuration indicates:

- enabled service;
- SX1302/SX1303 chipset family;
- RAK5146 model/profile;
- AS923 region/channel plan;
- SPI rather than an unrelated USB concentrator mode.

If the live configuration exposes exact channel frequencies, record those before changing anything. Do not infer them from a generic AS923 table when diagnosing a live mismatch.

## Step 4 — Confirm no competing packet forwarder is active

```sh
uci show chirpstack-udp-forwarder
ps w | grep -E '[u]dp-forwarder|[p]acket_forwarder' || true
```

**PASS means:** there is no enabled remote UDP packet-forwarder path competing with Concentratord/MQTT Forwarder.

## Step 5 — Confirm the local RF-to-MQTT handoff

First confirm local Mosquitto is listening:

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

It must be loopback-only. Then, in one shell, subscribe to the gateway event hierarchy:

```sh
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'as923/gateway/0016c001f139a1cb/event/#' -v
```

Generate one approved real sensor uplink.

**PASS means:** a message arrives on the correct EUI/topic. The payload may appear binary because the gateway path uses Protobuf.

**If no message arrives:** stop here. Do not edit cloud certificates. Check sensor transmission, AS923 compatibility, Concentratord event reception, MQTT Forwarder backend, and local Mosquitto.

## Step 6 — Distinguish common OTAA failures

If JoinRequest is visible but JoinAccept never completes, inspect in this order:

1. sensor and gateway regional/channel compatibility;
2. ChirpStack `region_as923` configuration;
3. DevEUI and JoinEUI registration;
4. AppKey/NwkKey material in the correct protected source;
5. RX1/RX2 parameters and device profile;
6. downlink scheduling/radio transmit evidence.

Do not repeatedly rotate keys or re-register the device until RF/channel agreement has been proven.

## Step 7 — Verify evidence observation after a real uplink

The gateway journal must consume the supported Concentratord event interface independently of MQTT Forwarder. Use the evidence-service manual to confirm one new journal sequence corresponds to the same known test uplink.

A normal application event with no source evidence is **not** a complete v2 evidence result.

## Change procedure

Before changing radio configuration:

1. save an off-gateway Gateway OS backup;
2. record current `uci show chirpstack-concentratord` output without secrets;
3. record the current Gateway EUI and channel/frequency values;
4. change only the intended radio setting;
5. Save & Apply once;
6. wait for SPI initialization to finish;
7. rerun Steps 1–5;
8. if a regional parameter changed intentionally, verify sensor firmware and ChirpStack before generating traffic.

Do not repeatedly click **Save & Apply** while the radio is initializing.

## Troubleshooting order

| Symptom | Likely layer |
|---|---|
| SPI/reset errors, no Gateway EUI | HAT seating, SPI/GPIO profile, power, Concentratord |
| Stable EUI but zero RF events | antenna, sensor TX, frequency/channel/SF/BW mismatch |
| Local RF/MQTT events but no cloud | local broker bridge/LTE/TLS |
| JoinRequest received but no JoinAccept | keys/profile/RX/downlink/region mismatch |
| App data present but evidence missing | evidence journal/interface, not radio delivery |

Continuous GPS/GNSS warnings are not proof that RF is broken. Diagnose GPS separately unless the selected test actually requires GNSS timing.

## Recovery

For a service-only failure, repair configuration/package/service state before considering a reflash. For a suspected hardware failure, power down before reseating or replacing the concentrator. After replacement, do not assume the Gateway EUI is unchanged; retrieve it from the active RAK5146 startup and deliberately update every identity-bound dependency if the EUI changed.

## Completion checklist

- Concentratord stats respond.
- service is not crash-looping.
- active Gateway EUI is `0016c001f139a1cb` unless hardware was intentionally replaced.
- current region is AS923.
- no competing UDP forwarder is active.
- one real uplink reaches the local `as923/gateway/.../event/#` topic.
- the evidence path can observe the source event independently.

## Detailed runbooks

The consolidated [RAK5146/AS923 setup and acceptance procedure](RAK5146-AS923-COMMISSIONING.md) includes physical installation, effective radio configuration, forwarder setup, source identity and recovery.

- [`../gateway/setup/01-hardware-assembly.md`](../gateway/setup/01-hardware-assembly.md)
- [`../gateway/setup/03-configure-concentratord.md`](../gateway/setup/03-configure-concentratord.md)
- [`../gateway/setup/05-configure-mqtt-forwarder.md`](../gateway/setup/05-configure-mqtt-forwarder.md)
- [`../gateway/setup/06-verify-gateway-os.md`](../gateway/setup/06-verify-gateway-os.md)
- [`../gateway/operations/06-rf-planning-and-site-survey.md`](../gateway/operations/06-rf-planning-and-site-survey.md)