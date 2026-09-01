# Current Server / Gateway / Sensor State

**Authoritative as of 2026-09-02.** This is a current-state board, not a chronological checkpoint. Historical commands/failures belong in `00-build-execution-log.md` and component manuals.

## Tomorrow entry point

Use `../../../TOMORROW-SENSOR-GATEWAY-BRINGUP.md` for the physical gateway + EMU-01 session.

## Server/cloud - commissioned

- etcd 3-node quorum.
- Patroni/PostgreSQL/TimescaleDB HA and PgBouncer/HAProxy database path.
- Mosquitto HA normal path and gateway mTLS identity/ACL boundary.
- Valkey/Sentinel.
- ChirpStack two-node cloud cluster and plain `AS923` region path.
- OpenBao 3-node KMS normal path and audit.
- Node-RED A active / B fenced, atomic telemetry + Fabric outbox logic.
- Grafana server staging and synthetic application-path verification.
- SeaweedFS/evidence storage lane, gateway evidence ingest/collectors/verifiers/trusted decoder.
- Fabric adapter immutable images deployed healthy in **disabled/fail-closed standby**. Real ledger execution remains intentionally blocked on external Fabric handoff + credential activation.
- Public ChirpStack/Evidence/MQTT normal path commissioned. Reserved-IP reassignment/failover authority remains a provider-side HA acceptance item.

Do not rebuild or recommission these layers tomorrow merely because real RF acceptance is still pending.

## Gateway - accepted build, physical acceptance next

Use the **2026-09-01 flash-ready AS923 + SIM7600 + journal release** documented at the end of `../../gateway/setup/02a-build-sim7600-capable-gateway-os.md`.

Accepted factory image:

```text
chirpstack-gateway-os-4.12.0-base-bcm27xx-bcm2709-rpi-2-squashfs-factory.img.gz
SHA-256 bafe8b97baf9353df2654b1c8b71fa53d2ff764cd264d0ed6c924dd25a5ec67d
```

It supersedes the earlier modem-only candidate for a new flash. It contains the proven RAK5146/AS923 baseline, SIM7600 serial/QMI support, local Mosquitto, and gateway-evidence writer. No evidence TLS secret is baked into the image.

Tomorrow must still prove on the actual flashed hardware: boot, RAK5146 detection, intended Gateway EUI, AS923 channel plan, SIM7600 runtime as needed, protected identity/config restore, ChirpStack gateway `Last seen`, and real EMU-01 RF traffic.

## Sensor - individual hardware proven, final integrated acceptance next

A-copy/B-copy sensor functional verification is substantially complete. Frozen EMU-01 map:

```text
A=RAK1903 OPT3001
B=EMPTY
C=RAK12019 LTR390 UV
D=RAK12011 LPS33HW
E=RAK1906 BME680
F=RAK12010 VEML7700
WisIO1=RAK12023 + RAK12035 soil
WisIO2=RAK12005 + RAK12030 rain
```

Soil calibration: `dry=560`, `wet=328`.

The final integrated source now lives at `../../../firmware/EMU01_Agriculture_Node/`. It preserves payload-v2: 46 bytes, version 2, big-endian, validity bits 0-6 (`0x007F` healthy), OTAA, Class A, plain AS923, unconfirmed uplinks, 15-second monotonic schedule, and deterministic `SENSOR_TX` Serial output. The real AppKey remains local in ignored `emu01_credentials.h`.

Hardware-dependent sensor gates still open:

1. compile final source against the pinned/proven Arduino/BSP/library set;
2. flash EMU-01 and capture ten healthy `0x007F` Serial cycles;
3. OTAA through the real RAK5146;
4. compare ten consecutive payload-v2 Serial sequences against ChirpStack decoding;
5. prove real lineage through Node-RED -> TimescaleDB -> Grafana and evidence path;
6. run sensor preflight and obtain `SENSOR_PREFLIGHT_STATUS=GO`.

## SEC-02 remaining boundary

SEC-02 legitimate OTAA and repeated ~15-second RAK12011 uplinks are proven. Before security conversion, compare decoded RAK12011 pressure/temperature with Serial for several consecutive frames, then retire/rotate the temporary legitimate credential. Never reuse EMU-01 credentials/session state.

## Separate external gates

These are real project gates but are not reasons to redesign a healthy sensor/gateway path tomorrow:

- DigitalOcean Reserved-IP reassignment/failover authority + controlled failover acceptance.
- External Hyperledger Fabric handoff, credential activation, and real ledger transaction.

## Hard rule

No counted experiment begins until the dedicated sensor preflight reports:

`SENSOR_PREFLIGHT_STATUS=GO`
