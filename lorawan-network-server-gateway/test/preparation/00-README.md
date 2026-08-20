# Test Preparation

Complete this directory before running any counted experiment. The goal is to make the gateway, server, physical Agriculture Kit sensor nodes, and test tools independently test-ready, then prove the complete end-to-end path once before the testbed is frozen.

## Preparation folders

| Folder | Purpose | Ready when |
|---|---|---|
| [gateway/](gateway/00-README.md) | Raspberry Pi 4B + RAK5146 and secure transport | real EUI stable, AS923 correct, buffer/bridge works, ChirpStack sees gateway |
| [server/](server/00-README.md) | Ubuntu VM + minimum seven-service stack | required services healthy, telemetry/storage/Fabric path available |
| [sensor/](sensor/00-README.md) | EMU-01 and SEC-02 | every direct Agriculture Kit sensor copy verified, EMU-01 full-sensor payload v2 works at 15 seconds, SEC-02 invalid/raw-RF functions proven |
| [tools/](tools/00-README.md) | test laptop, generators, resource capture | pilot rates and resource CSVs work |

## Phase 1 - Obtain the gateway identity

Complete in order:

```text
gateway/01-hardware-assembly.md
gateway/02-install-chirpstack-gateway-os.md
gateway/03-configure-concentratord.md
```

Stop and record:

```text
<GATEWAY_IP>
<GATEWAY_EUI>
<REGION_TOPIC_PREFIX> = as923
```

Do not continue with a guessed EUI. Use the 16-hex value reported by the successful active SX1302/SX1303 Concentratord startup.

## Phase 2 - Build the server around that identity

Complete:

```text
server/01-create-server-vm.md
server/02-build-minimum-testbed.md
```

The server preparation must create the broker CA/server certificate, exact-EUI gateway certificate, exact-EUI ACL, ChirpStack gateway record, telemetry database, Node-RED ingestion path, OpenBao path, and Fabric outbox/adapter path.

## Phase 3 - Finish gateway transport

Return to:

```text
gateway/04-configure-local-mqtt-buffer.md
gateway/05-configure-mqtt-forwarder.md
gateway/06-verify-gateway-os.md
```

Do not bypass the gateway's local Mosquitto buffer by pointing MQTT Forwarder directly at the server.

## Phase 4 - Assemble and prepare the physical sensor nodes

Complete in order:

```text
sensor/assembly/00-README.md
sensor/assembly/01-assemble-minimum-test-nodes.md
sensor/assembly/02-assemble-agriculture-sensors.md
sensor/assembly/03-pre-power-check-and-troubleshooting.md
sensor/assembly/04-verify-all-sensors.md
sensor/01-configure-rak4631-emulators.md
```

All direct sensor assemblies are mandatory. One complete A-set stays installed on EMU-01. Every B-copy must be physically installed and read successfully on SEC-02 during preparation before SEC-02 returns to its security-test role. `sensor/assembly/04-verify-all-sensors.md` also installs the Arduino/RAK4631 programming environment, proves USB uploads on both cores, and performs the individual/integrated sensor bring-up before the final LoRaWAN firmware is flashed.

Required roles:

```text
EMU-01 -> legitimate full physical-sensor OTAA node, payload v2 every 15 seconds
SEC-02 -> second-copy sensor verification, then invalid-credential/raw-RF security node with no legitimate root/session keys
```

## Phase 5 - Prepare the test tools

Complete:

```text
tools/01-prepare-test-tools.md
```

The separate Linux test laptop is used for source serial capture and MQTT/flood traffic so generator overhead does not consume measured server resources.

## Phase 6 - Create the preparation evidence folder

On the server VM:

```bash
mkdir -p "$HOME/chapter4-results/_preparation"
```

Create:

```text
chapter4-results/_preparation/testbed-baseline.txt
```

Record only non-secret values:

```text
preparation date UTC
server VM IP
server VM RAM/vCPU/disk
Gateway IP
Gateway EUI
AS923 sub-band/channel plan
Gateway OS version
RAK5146 model
EMU-01 DevEUI
EMU-01 hardware + firmware/build
SEC-02 hardware + firmware/build
payload contract version
Node-RED test flow revision/hash
TimescaleDB schema revision
Fabric contract/version
Fabric adapter version/image
```

Do not place AppKeys, session keys, private keys, passwords, tokens, OpenBao recovery shares, or Fabric signing secrets in this file.

## Phase 7 - Run the dedicated sensor preflight

After the gateway, server, sensor setup, and test tools are ready, run:

```text
sensor/preflight/00-README.md
sensor/preflight/01-hardware-firmware-preflight.md
sensor/preflight/02-lorawan-chirpstack-preflight.md
sensor/preflight/03-application-data-path-preflight.md
sensor/preflight/04-go-no-go-transition.md
```

This is the final **uncounted** acceptance bridge. It proves the frozen EMU-01 configuration through the physical RAK5146, OTAA/ChirpStack, decoder, Node-RED, TimescaleDB, and required Fabric evidence path. It also checks SEC-02/evidence-tool readiness.

Do not enter counted execution unless the status file contains:

```text
SENSOR_PREFLIGHT_STATUS=GO
```

Preflight evidence lives under:

```text
chapter4-results/_preflight/sensor/
```

Do not mix those packets with counted run windows.

## Phase 8 - Final preparation gate

Do not enter `../execution/` until all are true:

```text
[ ] Gateway uses approved AS923 plan and stable real Gateway EUI
[ ] Gateway local Mosquitto and mTLS bridge are accepted
[ ] Server VM is 5 GiB / 4 vCPU and all seven required services are healthy
[ ] Every direct Agriculture Kit sensor copy has been physically used and verified
[ ] EMU-01 retains one complete sensor set with all seven sensor types valid
[ ] EMU-01 OTAA joins and sends physical-sensor payload v2 every 15 seconds
[ ] EMU-01 test_sequence increments once per scheduled reading
[ ] One real EMU-01 reading reaches TimescaleDB
[ ] One selected event has valid Fabric commit evidence
[ ] SEC-02 has no legitimate AppKey/session keys
[ ] SEC-02 raw RF is proven received by RAK5146
[ ] Test-laptop tools pass pilot checks
[ ] Server and gateway resource logging work
[ ] Clocks support the selected latency definition
[ ] No required service is crash-looping or OOM-killed
[ ] testbed-baseline.txt is complete and contains no secrets
[ ] sensor preflight hardware/firmware check passed
[ ] sensor preflight OTAA/RAK5146/ChirpStack check passed
[ ] sensor preflight application/DB/Fabric check passed
[ ] chapter4-results/_preflight/sensor/04-go-no-go/preflight-status.txt records SENSOR_PREFLIGHT_STATUS=GO
```

When every item passes, continue to [../execution/01-common-run-preparation.md](../execution/01-common-run-preparation.md). Execution 01 starts fresh counted-run evidence; preflight traffic remains uncounted.
