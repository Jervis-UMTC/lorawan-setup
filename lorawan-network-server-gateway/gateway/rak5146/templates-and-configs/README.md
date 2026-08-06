# Templates and Configuration References

Do not deploy hand-written Station, Gateway Bridge, packet-forwarder, or regional JSON templates from this folder. The current gateway is configured through the Gateway OS LuCI interface and its generated UCI state.

## Capture the effective configuration

Run on the commissioned Gateway OS device:

```bash
uci show chirpstack-concentratord
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
```

Save a sanitized export with the encrypted gateway backup. Keep the Gateway EUI, confirmed region, topic prefix, local MQTT endpoint, queue path/limits, certificate fingerprint, and the Gateway OS release that generated the configuration. These values are needed to compare a restore or diagnose drift.

Do not export private keys, passwords, or root keys into documentation. A successful export shows Concentratord for RAK5146, MQTT Forwarder using `tcp://127.0.0.1:1883` at QoS 1, and no active UDP Forwarder server.

Regional channels must be selected through the exact Gateway OS Concentratord profile for the installed RAK5146 variant. Do not hand-edit a `global_conf.json` copied from another gateway.

The obsolete Station service, Basic Station Gateway Bridge, Station configuration, and historical `global_conf.*.json` files were removed to prevent accidental deployment.
