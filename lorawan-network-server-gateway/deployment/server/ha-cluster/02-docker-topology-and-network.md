# Server 2. Create the Docker Lab Topology and Networks

## Goal

Prepare one Compose project that represents the production service roles on a single Ubuntu Server VM.

## Before you start

Run on the **lab server VM** and confirm Docker is already installed by [01-create-server-vm.md](01-create-server-vm.md):

```bash
docker version
docker compose version
df -h /
free -h
```

Create the project directory:

```bash
sudo install -d -m 0755 -o "$USER" -g "$USER" /opt/lorawan-lab
cd /opt/lorawan-lab
```

## Step 1 - Create the project files

```bash
touch compose.yml
install -m 600 /dev/null .env
mkdir -p configuration/{etcd,spilo,haproxy,pgbouncer,mosquitto,valkey,chirpstack,openbao}
mkdir -p data/{etcd-1,etcd-2,etcd-3,spilo-1,spilo-2,spilo-3}
```

Do not store live private keys in the repository. `/opt/lorawan-lab/.env` and runtime PKI paths stay local to the VM and protected.

## Step 2 - Define the Compose networks

Start `/opt/lorawan-lab/compose.yml` with:

```yaml
name: lorawan-lab

networks:
  dcs:
    internal: true
  database:
    internal: true
  application:
  telemetry:
    internal: true
  kms:
    internal: true
```

Role placement:

```text
dcs network:
  etcd-1, etcd-2, etcd-3
  spilo-1, spilo-2, spilo-3

database network:
  spilo-1, spilo-2, spilo-3
  haproxy

application network:
  haproxy
  pgbouncer
  mosquitto
  valkey
  chirpstack
  node-red

telemetry network:
  telemetry-db
  node-red
  grafana
  fabric-adapter

kms network:
  openbao
  fabric-adapter
```

`kms` is an internal Docker network. OpenBao is never published to the VM host in the baseline lab; only the Fabric adapter can reach its Transit API through the `kms` network. The application network is not marked `internal` because selected containers need normal outbound access during installation, image pulls, DNS resolution, or external Fabric submission. Do not publish an internal service port merely because its Docker network has outbound connectivity.

## Step 3 - Create persistent volumes explicitly

Append:

```yaml
volumes:
  etcd-1-data:
  etcd-2-data:
  etcd-3-data:
  spilo-1-data:
  spilo-2-data:
  spilo-3-data:
  mosquitto-data:
  valkey-data:
  telemetry-data:
  node-red-data:
  grafana-data:
  openbao-data:
```

Each PostgreSQL member needs an independent volume. Never mount the same PostgreSQL data directory into two active Spilo containers.

## Step 4 - Record image pins

Add only reviewed immutable references to `.env`:

```dotenv
ETCD_IMAGE=<PINNED_ETCD_IMAGE_OR_DIGEST>
SPILO_IMAGE=<PINNED_SPILO_IMAGE_OR_DIGEST>
HAPROXY_IMAGE=<PINNED_HAPROXY_IMAGE_OR_DIGEST>
PGBOUNCER_IMAGE=<PINNED_PGBOUNCER_IMAGE_OR_DIGEST>
MOSQUITTO_IMAGE=<PINNED_MOSQUITTO_IMAGE_OR_DIGEST>
VALKEY_IMAGE=<PINNED_VALKEY_IMAGE_OR_DIGEST>
CHIRPSTACK_IMAGE=<PINNED_CHIRPSTACK_IMAGE_OR_DIGEST>
TIMESCALEDB_IMAGE=<PINNED_TIMESCALEDB_IMAGE_OR_DIGEST>
NODE_RED_IMAGE=<PINNED_NODE_RED_IMAGE_OR_DIGEST>
GRAFANA_IMAGE=<PINNED_GRAFANA_IMAGE_OR_DIGEST>
OPENBAO_IMAGE=<PINNED_OPENBAO_IMAGE_OR_DIGEST>
POSTGRES_CLIENT_IMAGE=<PINNED_POSTGRES_CLIENT_IMAGE_OR_DIGEST>
CURL_IMAGE=<PINNED_CURL_IMAGE_OR_DIGEST>
```

## Step 5 - Add the full-stack low-load resource ceilings

Add these limits to `.env`:

```dotenv
LAB_ETCD_CPUS=0.20
LAB_ETCD_MEM=128m
LAB_SPILO_CPUS=0.75
LAB_SPILO_MEM=768m
LAB_HAPROXY_CPUS=0.20
LAB_HAPROXY_MEM=128m
LAB_PGBOUNCER_CPUS=0.20
LAB_PGBOUNCER_MEM=128m
LAB_MOSQUITTO_CPUS=0.35
LAB_MOSQUITTO_MEM=192m
LAB_VALKEY_CPUS=0.35
LAB_VALKEY_MEM=256m
LAB_CHIRPSTACK_CPUS=0.75
LAB_CHIRPSTACK_MEM=512m
LAB_TIMESCALEDB_CPUS=0.75
LAB_TIMESCALEDB_MEM=768m
LAB_NODE_RED_CPUS=0.50
LAB_NODE_RED_MEM=384m
LAB_GRAFANA_CPUS=0.40
LAB_GRAFANA_MEM=384m
LAB_OPENBAO_CPUS=0.35
LAB_OPENBAO_MEM=256m
LAB_FABRIC_ADAPTER_CPUS=0.40
LAB_FABRIC_ADAPTER_MEM=256m
LAB_EVIDENCE_SERVICE_CPUS=0.20
LAB_EVIDENCE_SERVICE_MEM=192m
```

Budget:

| Service | Count | Memory each | Memory total | CPU each | CPU total |
|---|---:|---:|---:|---:|---:|
| etcd | 3 | 128 MiB | 384 MiB | 0.20 | 0.60 |
| Spilo / Patroni / PostgreSQL | 3 | 768 MiB | 2304 MiB | 0.75 | 2.25 |
| HAProxy | 1 | 128 MiB | 128 MiB | 0.20 | 0.20 |
| PgBouncer | 1 | 128 MiB | 128 MiB | 0.20 | 0.20 |
| Mosquitto | 1 | 192 MiB | 192 MiB | 0.35 | 0.35 |
| Valkey | 1 | 256 MiB | 256 MiB | 0.35 | 0.35 |
| ChirpStack | 1 | 512 MiB | 512 MiB | 0.75 | 0.75 |
| TimescaleDB | 1 | 768 MiB | 768 MiB | 0.75 | 0.75 |
| Node-RED | 1 | 384 MiB | 384 MiB | 0.50 | 0.50 |
| Grafana | 1 | 384 MiB | 384 MiB | 0.40 | 0.40 |
| OpenBao | 1 | 256 MiB | 256 MiB | 0.35 | 0.35 |
| Fabric adapter | 1 | 256 MiB | 256 MiB | 0.40 | 0.40 |
| Gateway-evidence server roles, when implemented | 3 | 192 MiB | 576 MiB | 0.20 | 0.60 |

Current executable v1 maximum: **5952 MiB** and **7.10 CPUs**. Full documented v2 budget after the three reviewed evidence services exist: **6528 MiB** and **7.70 CPUs**.

These are hard lab ceilings, not reservations. A quiet container uses less. The goal is to stop one service from consuming the entire VM while leaving memory and CPU for Ubuntu and Docker.

Every service manual below applies its matching values with:

```yaml
cpus: "${LAB_<SERVICE>_CPUS}"
mem_limit: "${LAB_<SERVICE>_MEM}"
```

Do not increase one limit without checking `docker stats` and the VM's actual available RAM/CPU. These are full-stack simulation ceilings, not the dissertation test profile and not production sizing.

### Check the budget while building

After each major layer starts, run:

```bash
free -h
docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}'
```

Before failure or backup tests, also check for OOM kills:

```bash
journalctl -k --since today | grep -Ei 'oom|out of memory|killed process' || true
```

Stop and investigate when a container stays above about 85% of its memory limit, the VM has less than about 1 GiB `available` memory before a test, or the kernel reports an OOM kill. Fix connection counts, workload, or an incorrectly sized service before raising a limit.

Use the same reviewed Spilo, PostgreSQL major, Patroni, HAProxy, PgBouncer, and ChirpStack versions that are being validated for the cloud deployment. See:

- [cloud etcd manual](../cloud-production/06-etcd-cluster.md)
- [cloud Spilo / Patroni manual](../cloud-production/07-spilo-patroni-postgresql-cluster.md)
- [cloud HAProxy / PgBouncer manual](../cloud-production/08-haproxy-and-pgbouncer.md)
- [cloud MQTT / Valkey manual](../cloud-production/09-mqtt-and-valkey.md)

Pull and inspect the selected images:

```bash
set -a
. ./.env
set +a
for image in "$ETCD_IMAGE" "$SPILO_IMAGE" "$HAPROXY_IMAGE" "$PGBOUNCER_IMAGE" "$MOSQUITTO_IMAGE" "$VALKEY_IMAGE" "$CHIRPSTACK_IMAGE" "$OPENBAO_IMAGE"; do
  docker pull "$image"
  docker image inspect "$image" --format '{{json .RepoDigests}}'
done
```

## Verify

```bash
cd /opt/lorawan-lab
docker compose config --quiet
find configuration -maxdepth 2 -type d -print | sort
```

Expected result: Compose parses successfully, all required directories exist, and no service has been started yet.

## Troubleshooting

If `docker compose config` reports an unresolved variable, add the missing non-secret image reference or required value to `.env`. Do not replace an unresolved image with `latest` merely to continue.

## Next step

Continue with [03-deploy-etcd-quorum.md](03-deploy-etcd-quorum.md).
