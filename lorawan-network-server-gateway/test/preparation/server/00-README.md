# Server Preparation

This folder builds the minimum server required for the dissertation experiments. It is not the full production deployment.

## Test-server profile

```text
Guest OS: Ubuntu Server 24.04 LTS, no GUI
RAM:      5 GiB
vCPU:     4
Disk:     50 GiB SSD-backed minimum
Host:     8 GiB RAM / 8 CPU threads
```

Do not assign all host resources to the VM. Host swapping or starvation can distort latency and throughput measurements.

## Required services only

```text
Mosquitto
Valkey
ChirpStack
PostgreSQL / TimescaleDB
Node-RED
OpenBao
Fabric adapter
```

Do not add Grafana, etcd, Patroni/Spilo, HAProxy, PgBouncer, Prometheus, or production HA helpers to the measured dissertation VM.

## Manuals

1. [01-create-server-vm.md](01-create-server-vm.md) - create Ubuntu Server VM, configure network/time/swap, install Docker Engine and Compose v2.
2. [02-build-minimum-testbed.md](02-build-minimum-testbed.md) - deploy and configure the seven-service LoRaWAN test stack, provision the real gateway EUI, configure telemetry storage, OpenBao, and the Fabric outbox/adapter, then verify the stack.

## Required gateway input

Before the gateway-identity section of manual 02, obtain the following from `../gateway/03-configure-concentratord.md`:

```text
<GATEWAY_EUI>
<GATEWAY_IP>
<REGION_TOPIC_PREFIX> = as923
```

Use the exact EUI reported by the active SX1302/SX1303 Concentratord startup. Do not use an inactive/stale gateway ID.

## Server acceptance

The server is ready for the final gateway and sensor preparation when:

```text
[ ] exactly the seven required services are configured
[ ] required containers are healthy and not crash-looping
[ ] ChirpStack loads the frozen plain AS923 v4 region configuration without TOML errors
[ ] `[network] enabled_regions` contains the intended `as923` region
[ ] active ChirpStack region ID and MQTT topic prefix are `as923`
[ ] server Mosquitto internal application listener works
[ ] gateway mTLS listener 8883 uses the lab CA/server certificate
[ ] exact real Gateway EUI is registered in ChirpStack
[ ] exact-EUI gateway certificate and ACL exist
[ ] TimescaleDB telemetry schema exists
[ ] Node-RED test telemetry path is configured
[ ] OpenBao Transit sign/verify path is available
[ ] Fabric outbox and reviewed Fabric adapter are available
[ ] no OOM kill is present before testing
```

After server provisioning, return to [../gateway/04-configure-local-mqtt-buffer.md](../gateway/04-configure-local-mqtt-buffer.md).
