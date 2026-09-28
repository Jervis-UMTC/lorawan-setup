# Chapter 1 — System Overview and Setup Order

## 1.1 What the system does

EMU-01 measures agricultural conditions and sends a 46-byte payload over AS923 LoRaWAN. Gateway-01 receives the radio signal and forwards it over the SIM7600 LTE connection. ChirpStack handles LoRaWAN messages, Node-RED saves measurements in PostgreSQL, and Grafana displays them. Gateway-01 uses **ChirpStack Gateway OS Base**; the ChirpStack network server runs on the cloud servers, not on the gateway. Separate evidence services preserve and verify original gateway events before eligible records are anchored in Hyperledger Fabric.

**Data path:** EMU-01 → RAK5146 / Gateway-01 → MQTT / LTE → cloud MQTT → ChirpStack → Node-RED → PostgreSQL → Grafana.

**Evidence path:** gateway journal → cloud evidence services / SeaweedFS → verifier → Fabric adapter / OpenBao → HRC Fabric.

<!-- ARCHITECTURE_DIAGRAM: Figure 1.1; draw the commissioned EMU-01→Gateway-01→local MQTT/LTE→both cloud brokers→ChirpStack→sole Node-RED SQL writer; journal/mTLS ingest/SeaweedFS and BOTH cloud broker witnesses feed verifier; only verified eligible events go via OpenBao/Fabric. -->

## 1.2 What each technology does

| Technology | Purpose |
|---|---|
| RAK4631 / EMU-01 | Reads agricultural sensors, builds the approved payload and sends a LoRaWAN uplink. |
| ChirpStack Gateway OS Base / OpenWrt | Runs the Raspberry Pi gateway, networking and forwarding services; the Network Server is hosted on ULC servers. |
| RAK5146 / Concentratord | Receives AS923 radio packets and passes them to the packet forwarder. |
| SIM7600 LTE | Provides Gateway-01's field Internet connection through `wwan0`. |
| Mosquitto MQTT | Moves gateway and application events; gateway local broker buffers permitted messages. |
| ChirpStack | Processes LoRaWAN joins, device identities, security, sessions and uplinks. |
| etcd / Patroni / PostgreSQL / TimescaleDB | Coordinates database failover and durably stores measurements and evidence. |
| HAProxy / PgBouncer | Routes clients to the writable PostgreSQL node and pools connections. |
| Valkey / Sentinel | Provides resilient ChirpStack runtime state and cache. |
| Node-RED | Validates/normalizes sensor readings and writes telemetry and Fabric-outbox data. |
| Grafana | Displays read-only measurement histories and system status. |
| SeaweedFS | Retains original raw gateway evidence objects. |
| Gateway evidence services | Collect, match and verify gateway journal, MQTT witness and sensor records. |
| OpenBao / PKI | Protects service identities and provides evidence digest signing. |
| Hyperledger Fabric adapter | Sends eligible exact source payloads to the external HRC ledger and checks finality. |
| Research recorder | Captures, measures and seals formal research test results. |

## 1.3 Equipment and machines

| Device / server | Main task |
|---|---|
| EMU-01 | RAK4631 WisBlock agricultural sensor. |
| Gateway-01 | Raspberry Pi, RAK5146, SIM7600, local MQTT, journal and uploader. |
| ULC-01 | Cloud services and normally the only enabled Fabric adapter. |
| ULC-02 | Cloud HA services and disabled Fabric adapter standby. |
| ULC-03 | Cloud HA services, active Node-RED and Grafana. |
| SEC | RUI3 security-test fixture; use only for its prescribed tests. |
| HRC environment | Separate Hyperledger Fabric peers, orderers and chaincode. |

ULC-01/02/03 database roles can change during failover; check the current writable primary before any database operation.

## 1.4 Before starting setup

1. Connect the research workstation to the intended management network. Keep the gateway powered off while fitting its concentrator and antennas.
2. Prepare Gateway-01, its power supply, Ethernet cable for management, RAK5146 antenna and SIM7600 SIM/antenna.
3. Identify the EMU-01 boards and sensors from the assembly chapter. Do not apply power until the wiring and antenna are checked.
4. Obtain authorized SSH access to ULC-01/02/03 and the gateway, plus approved service certificates and credentials. Do not copy private keys or passwords into this manual.
5. Confirm the required project identities below before provisioning a new device. Do not regenerate an already-registered OTAA identity.

## 1.5 Required project settings

| Setting | Value |
|---|---|
| LoRaWAN region | Plain AS923 |
| Gateway EUI | `0016c001f139a1cb` |
| EMU-01 DevEUI | `ac1f09fffe296d29` |
| EMU-01 JoinEUI | `0000000000000000` |
| Sensor payload | v2 / 46 bytes |
| Activation and device class | OTAA / Class A |
| Gateway production Internet | SIM7600 / `wwan0` |
| HRC Fabric endpoint | `10.104.0.7:7051` |
| HRC TLS server name | `peer1.hrc.local` |

Use the exact frequencies, channel list, data rates and RX parameters from the current gateway, ChirpStack and sensor configurations; do not assume every AS923 installation uses identical defaults.

## 1.6 Setup order

**For a new build, follow the chapters in this order. For an existing running system, inspect before rebuilding anything.**

1. Prepare the Raspberry Pi and install the approved Gateway OS image.
2. Fit and configure RAK5146 / Concentratord for the project's AS923 settings.
3. Configure SIM7600 LTE, local MQTT and the cloud bridge.
4. Prepare ULC-01/02/03: operating system, private networking, Docker and certificates.
5. Set up etcd, PostgreSQL / Patroni / TimescaleDB, HAProxy / PgBouncer and Valkey / Sentinel.
6. Configure cloud MQTT and two ChirpStack instances.
7. Configure SeaweedFS and OpenBao with their own separate storage/consensus state.
8. Deploy one active Node-RED writer, PostgreSQL telemetry mapping and Grafana read-only panels.
9. Deploy gateway journal/uploader and cloud ingest, collectors and verifier.
10. Configure and qualify the sole active Fabric adapter.
11. Assemble, flash, provision and test EMU-01.
12. Set up the research recorder; run approved tests only after the current readiness gate passes.

