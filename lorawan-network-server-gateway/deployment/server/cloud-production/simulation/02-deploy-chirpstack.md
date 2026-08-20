# Cloud Simulation 2. Deploy the Complete Shared Docker Stack

The cloud simulation does not use a smaller ChirpStack-only Compose project. It reuses the complete single-VM Docker topology from the lab.

The currently executable simulation remains the **v1-compatible delivery/application stack**. The gateway-integrity v2 manuals reserve 192 MiB and 0.20 CPU for each future ingestor/collector/verifier role, but reviewed images are not yet present. Do not add placeholder containers or claim v2 simulation coverage until those artifacts exist; measure the real services against those initial ceilings when they are built.

## Step 1 - Build the canonical lab stack

Complete these lab manuals on the cloud-simulation VM:

1. [Docker topology and networks](../../ha-cluster/02-docker-topology-and-network.md)
2. [etcd quorum](../../ha-cluster/03-deploy-etcd-quorum.md)
3. [Spilo / Patroni PostgreSQL](../../ha-cluster/04-deploy-spilo-patroni-postgresql.md)
4. [PostgreSQL HA verification](../../ha-cluster/05-verify-postgresql-ha.md)
5. [HAProxy](../../ha-cluster/06-deploy-haproxy.md)
6. [PgBouncer](../../ha-cluster/07-deploy-pgbouncer.md)
7. [Mosquitto](../../ha-cluster/08-deploy-mosquitto.md)
8. [Valkey](../../ha-cluster/09-deploy-valkey.md)
9. [ChirpStack](../../ha-cluster/10-deploy-chirpstack.md)

Use `/opt/lorawan-lab` exactly as the lab does.

## Step 2 - Apply cloud-simulation profile values

```text
<SERVER_VM_HOSTNAME> = lora-cloud-sim
<SERVER_VM_IP_ADDRESS> = <CLOUD_SIM_VM_IP_ADDRESS>
<MQTT_BROKER_FQDN> = <CLOUD_SIM_MQTT_FQDN>
<BROKER_BIND_ADDRESS> = <CLOUD_SIM_VM_IP_ADDRESS>
<CONFIRMED_REGION_ID> = same active region as Gateway OS
<CONFIRMED_REGION_TOPIC_PREFIX> = same topic prefix as Gateway OS
```

Do not rename internal Docker services to imitate cloud hostnames. Docker DNS names remain:

```text
etcd-1 etcd-2 etcd-3
spilo-1 spilo-2 spilo-3
haproxy
pgbouncer
mosquitto
valkey
chirpstack
```

## Step 3 - Verify parity

```bash
cd /opt/lorawan-lab
docker compose config --services
docker compose config --images
docker compose ps
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
docker compose exec spilo-1 patronictl list
docker compose exec etcd-1 sh -lc 'ETCDCTL_API=3 etcdctl --endpoints=http://etcd-1:2379,http://etcd-2:2379,http://etcd-3:2379 endpoint health --cluster'
```

Required result:

- the VM uses the full-stack resource profile selected in Cloud Simulation 1 and has no OOM-killed service;
- three healthy etcd members;
- one Patroni leader and two replicas;
- HAProxy and PgBouncer are in the normal database path;
- Valkey is used instead of a lab-only Redis service;
- no standalone ChirpStack PostgreSQL container exists;
- no server-side Gateway Bridge exists;
- no invented gateway-evidence service image is running merely to make the topology look complete;
- when v2 is later added, its services must be pinned and sized explicitly rather than hidden inside the existing ChirpStack container.

## Next step

Continue with [03-secure-gateway-mqtt.md](03-secure-gateway-mqtt.md).
