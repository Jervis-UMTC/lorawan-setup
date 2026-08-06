# Host-Simulated LoRaWAN, Telemetry, and Fabric Lab

Use this guide when the physical Raspberry Pi 4B + RAK5146 runs Gateway OS Base and the application platform runs on virtual machines. Unless a step names another host, run server-side Compose commands on the application VM from `/opt/chirpstack-docker`. Gateway OS commands run on the Raspberry Pi, Fabric test-network commands run on the Fabric VM, and browser interfaces use the documented SSH tunnels.

```text
LoRaWAN device
  -> RAK5146
  -> Concentratord
  -> MQTT Forwarder, QoS 1
  -> local persistent Mosquitto on the gateway
  -> mutual-TLS bridge
  -> Mosquitto on the application VM
  -> ChirpStack
  -> Node-RED / TimescaleDB / Grafana
  -> durable Fabric outbox and adapter
```

## System roles

Build the application VM before registering devices so the remote MQTT endpoint, ChirpStack region, and gateway certificate are available when Gateway OS is configured.

| System | Role |
|---|---|
| Raspberry Pi 4B | Gateway OS Base, RAK5146, Concentratord, MQTT Forwarder, local persistent Mosquitto buffer |
| Application VM | Remote Mosquitto ingress, ChirpStack, Redis, PostgreSQL, TimescaleDB, Node-RED, Grafana, Fabric adapter |
| Fabric VM | Fabric peers, orderer, CAs, channel, and approved telemetry chaincode |

The current ChirpStack Gateway Bridge is not installed on the gateway because it no longer provides a Concentratord backend. The remote server also does not need Gateway Bridge for this direct MQTT architecture.

## Read in order

1. [Architecture and decisions](01-architecture-and-decisions.md)
2. [Gateway setup](../../gateway/setup/00-README.md)
3. [Application server](setup/01-create-server-vm.md)
4. [Register and test](../../gateway/operations/01-register-and-test.md)
5. [Availability tests](../../gateway/operations/03-availability-tests.md)
6. [Backup and recovery](../../gateway/operations/02-backup-and-recovery.md)
7. [Cloud migration](../../gateway/operations/04-migrate-to-cloud.md)
8. [Troubleshooting](../../gateway/operations/05-troubleshooting.md)

## Verify the completed lab

Test each boundary separately. A healthy container does not prove that the gateway can authenticate, that ChirpStack accepts the region topics, or that telemetry is stored once.

The lab is complete only when:

- the pinned Gateway OS image boots and Concentratord initializes RAK5146;
- local Mosquitto buffers real QoS 1 uplinks across WAN loss and reboot;
- the queue drains after recovery without duplicate application rows;
- the remote broker validates the unique gateway certificate and ACL;
- stale downlink commands are not replayed;
- real OTAA, uplink, and safe Class A downlink pass;
- telemetry storage, dashboards, backup, restore, and Fabric tests pass where implemented.
