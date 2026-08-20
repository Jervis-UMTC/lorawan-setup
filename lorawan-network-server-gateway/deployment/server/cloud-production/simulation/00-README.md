# Single-VM Cloud Simulation

> **Separate profile:** this is the older/heavier full-stack single-VM regression simulation. It is **not** the sizing or data-layer source of truth for the current cheap three-Droplet HA POC. The current POC uses 3 x 2-GiB Droplets and stores telemetry/outbox in the shared Patroni PostgreSQL cluster; see [../00-README.md](../00-README.md).

Use this track when you want the complete Docker lab to behave like a remote cloud host before provisioning real cloud infrastructure.

The simulation reuses the same **full** server topology documented under `deployment/server/ha-cluster/`:

```text
Gateway OS Base
  -> Concentratord
       |
       +-> delivery: gateway-local persistent Mosquitto
       |    -> mutual-TLS MQTT to <MQTT_BROKER_FQDN>:8883
       |    -> Mosquitto
       |    -> ChirpStack
       |
       +-> evidence: software integrity journal
            -> local hash-chained segments
            -> cloud checkpoint/segment path only after reviewed v2 services exist
       -> Valkey
       -> PgBouncer
            -> HAProxy
                 -> Spilo / Patroni PostgreSQL leader
                      -> three-member etcd quorum
  -> TimescaleDB / Node-RED / Grafana
  -> external Fabric adapter/client integration path after its reviewed image and handoff exist
```

Everything still runs on one Ubuntu Server VM, but this is the **full-stack simulation**, not the dissertation VM. Use the full-stack starting profile from `ha-cluster/01-create-server-vm.md` (12 GiB RAM / 8 vCPU / 160 GiB disk) on a physical host with additional headroom. Do not run this VM on the dissertation's 8 GiB physical host. Containers simulate service separation and failover; they do not provide physical host or availability-zone redundancy.

The currently executable simulation remains v1-compatible. The v2 gateway-evidence roles are documented contracts until reviewed images, endpoint implementation, trusted decoder, and the separate v2 canonicalization vector exist. Do not invent placeholder containers/ports and call v2 simulated.

## What changes from the normal lab

Keep the Docker service names, Compose networks, image pins, PostgreSQL path, MQTT ACLs, Gateway-EUI identities, region files, and verification commands identical.

Change only the host profile:

- VM hostname;
- management and gateway-facing virtual adapters;
- DNS names representing cloud endpoints;
- UFW source ranges;
- MQTT broker certificate SAN;
- backup destination and labels.

## Simulation profile

```text
VM hostname: lora-cloud-sim
Management name: <CLOUD_SIM_SERVER_FQDN>
MQTT broker name: <CLOUD_SIM_MQTT_FQDN>
ChirpStack name: <CHIRPSTACK_FQDN>
VM address: <CLOUD_SIM_VM_IP_ADDRESS>
Gateway MQTT port: 8883/TCP
Evidence ingest port when reviewed v2 service exists: 443/TCP
ChirpStack local port: 8080/TCP through SSH tunnel
Compose project: /opt/lorawan-lab
```

Use a reserved test domain such as `.test` for local-only simulation. Do not expose the VM directly to the public internet merely to imitate cloud networking.

## Setup order

1. [Create the cloud-simulation VM and network boundary](01-create-cloud-simulation-vm.md)
2. [Deploy the complete Docker lab stack](02-deploy-chirpstack.md)
3. [Apply the shared mutual-TLS MQTT boundary](03-secure-gateway-mqtt.md)
4. [Provision the shared per-gateway identity](04-provision-gateway-mqtt-identity.md)
5. [Configure/verify the gateway journal contract](../../../gateway/setup/04a-configure-gateway-integrity-journal.md) when its reviewed implementation exists.
6. [Verify the physical gateway delivery + evidence paths](../../../gateway/setup/06-verify-gateway-os.md).
7. For v2, implement the reviewed [Gateway Integrity server roles](../../integrations/gateway-integrity/00-README.md) before claiming evidence-path simulation coverage.
8. [Run the lab failure/recovery tests](../../ha-cluster/13-failure-recovery-tests.md)
9. [Run the lab backup/restore checks](../../ha-cluster/14-backup-and-restore.md)

After this passes, use [the production cloud track](../00-README.md) for real independent hosts, provider networking, the self-managed Reserved-IP/HAProxy public-ingress layer, physical PostgreSQL failure domains, and disaster recovery.

## Required result

- the same etcd / Spilo / Patroni / HAProxy / PgBouncer chain used by the normal lab is running;
- the Raspberry Pi reaches the simulated cloud through TCP `8883` for MQTT delivery; when reviewed v2 evidence ingest is deployed, its separate HTTPS/mTLS path uses only the approved TCP `443` endpoint;
- the MQTT certificate validates the simulated cloud DNS name;
- no server-side Gateway Bridge or Semtech UDP listener is added;
- a VM reboot preserves the Docker volumes and configuration;
- a gateway WAN outage still uses the gateway-local delivery queue and local journal independently;
- when v2 is actually implemented, recovery proves journal segment/checkpoint upload and reconciliation instead of merely MQTT queue drain;
- once the reviewed Fabric adapter is present, external Fabric outage behavior remains non-blocking and the durable outbox is the recovery boundary.
