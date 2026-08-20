# Cloud Simulation 1. Create the Cloud-Server VM

> This is the separate **full-stack single-VM simulation**, not the current 3 x 2-GiB cloud HA POC. Do not use its 12-GiB VM size to estimate the POC cost or minimum Droplet size.

This procedure creates a VM that behaves like a small remote cloud host while remaining on the local hypervisor.

First read Steps 1 and 2 below to choose the virtual network and profile values. Then complete [Create and prepare the application server VM](../../ha-cluster/01-create-server-vm.md) using the **full-stack starting profile: 12 GiB RAM, 8 vCPU, and 160 GiB SSD-backed disk** on a larger physical host. Return here for Steps 3 through 5 to verify the simulation boundary.

## Step 1: Select the virtual network model

### Recommended: two virtual adapters

Use two VM network adapters when the hypervisor supports them:

```text
Adapter 1: management network
  -> reachable only from the administration workstation

Adapter 2: simulated public/gateway network
  -> reachable from the Raspberry Pi gateway
  -> exposes TCP 8883 for MQTT delivery
  -> may expose TCP 443 for reviewed evidence ingest only after the v2 service exists
```

This makes the security boundary visible without requiring a real cloud provider.

Configure only one default route. Give the second adapter a route only for its attached subnet unless it is deliberately selected as the VM's default path. Multiple competing default gateways can create asymmetric MQTT and SSH traffic that appears as an intermittent firewall or TLS problem.

A single bridged adapter is acceptable for a small lab when UFW restricts every service correctly. Do not mistake a single LAN for a real public/private cloud network.

## Step 2: Apply the cloud-simulation values

Use:

```text
<SERVER_VM_HOSTNAME> = lora-cloud-sim
<SERVER_VM_IP_ADDRESS> = <CLOUD_SIM_VM_IP_ADDRESS>
<SERVER_VM_FQDN> = <CLOUD_SIM_SERVER_FQDN>
<MQTT_BROKER_FQDN> = <CLOUD_SIM_MQTT_FQDN>
<EVIDENCE_INGEST_FQDN> = <CLOUD_SIM_EVIDENCE_FQDN> when v2 is implemented
<MANAGEMENT_SUBNET_CIDR> = <CLOUD_SIM_MANAGEMENT_SUBNET_CIDR>
<GATEWAY_IP_ADDRESS> = <GATEWAY_IP_ADDRESS>
```

Suggested local-only names:

```text
<CLOUD_SIM_SERVER_FQDN> = lora-cloud-sim.test
<CLOUD_SIM_MQTT_FQDN> = mqtt.lora-cloud-sim.test
<CLOUD_SIM_EVIDENCE_FQDN> = evidence.lora-cloud-sim.test when v2 is implemented
<CHIRPSTACK_FQDN> = chirpstack.lora-cloud-sim.test
```

Create matching DNS or hosts entries on the administration workstation and gateway resolver path.

## Step 3: Verify routing from the gateway network

From a host on the same network as the Raspberry Pi:

```bash
getent hosts <CLOUD_SIM_MQTT_FQDN>
ping -c 4 <CLOUD_SIM_VM_IP_ADDRESS>
```

DNS resolution and basic routing must work before Mosquitto is configured. The MQTT TLS port is tested after the broker starts in the MQTT security manual.

From the VM, verify the route back to the gateway:

```bash
ip -brief address
ip route
ping -c 4 <GATEWAY_IP_ADDRESS>
```

## Step 4: Apply the simulated cloud firewall boundary

After the common VM guide installs UFW, verify these rules:

```bash
sudo ufw status numbered
sudo ss -lntup
```

The final gateway-facing boundary is:

```text
Allow TCP 8883 from the gateway address or approved gateway subnet
Allow TCP 443 from the gateway address/subnet only after the reviewed evidence-ingest service is deployed
Deny TCP 1883 from every external interface
Deny UDP 1700
Deny PostgreSQL, PgBouncer, HAProxy, Valkey, ChirpStack, Node-RED, TimescaleDB, and Grafana from the gateway network
Allow SSH only from the management subnet
```

Use SSH tunnels from the administration workstation:

```bash
ssh -L 8080:127.0.0.1:8080 <ADMIN_USER>@<CLOUD_SIM_SERVER_FQDN>
```

Then open `http://127.0.0.1:8080` locally after ChirpStack starts.

## Step 5: Test VM restart and address stability

Reboot the VM:

```bash
sudo reboot
```

After reconnecting, confirm:

```bash
hostnamectl
ip -brief address
ip route
sudo systemctl is-active docker
sudo ufw status verbose
```

Do not continue if the address, route, or firewall differs after reboot.

## Completion check

- the VM uses the intended management and gateway-facing network path;
- the simulated MQTT DNS name resolves to the VM address;
- SSH is reachable only through the management boundary;
- gateway MQTT delivery traffic is limited to TCP `8883`;
- TCP `443` is not exposed until a reviewed evidence-ingest service exists; when deployed, it is limited to the approved gateway source and mTLS identity;
- TCP `1883` and UDP `1700` are not exposed;
- Docker and the VM return automatically after reboot.

## Next step

Continue with [02-deploy-chirpstack.md](02-deploy-chirpstack.md).
