# Server 3. Deploy the Three-Member etcd Quorum

## Goal

Run three etcd members in Docker so Patroni can use a real majority quorum for leader election and cluster state.

This adapts [the production etcd manual](../cloud-production/06-etcd-cluster.md) to one lab VM. Container failure is useful for learning quorum behavior, but it is not a separate physical failure domain.

## Before you start

Run on the **lab server VM**:

```bash
cd /opt/lorawan-lab
. ./.env
printf '%s\n' "$ETCD_IMAGE"
docker image inspect "$ETCD_IMAGE" --format '{{json .RepoDigests}}'
```

Confirm the selected etcd version and its supported flags before continuing.

## Step 1 - Add the etcd services

Merge these services into `compose.yml`:

```yaml
services:
  etcd-1:
    image: ${ETCD_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_ETCD_CPUS}"
    mem_limit: "${LAB_ETCD_MEM}"
    command:
      - etcd
      - --name=etcd-1
      - --data-dir=/etcd-data
      - --listen-client-urls=http://0.0.0.0:2379
      - --advertise-client-urls=http://etcd-1:2379
      - --listen-peer-urls=http://0.0.0.0:2380
      - --initial-advertise-peer-urls=http://etcd-1:2380
      - --initial-cluster=etcd-1=http://etcd-1:2380,etcd-2=http://etcd-2:2380,etcd-3=http://etcd-3:2380
      - --initial-cluster-state=new
      - --initial-cluster-token=lorawan-lab-etcd
    volumes:
      - etcd-1-data:/etcd-data
    networks: [dcs]

  etcd-2:
    image: ${ETCD_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_ETCD_CPUS}"
    mem_limit: "${LAB_ETCD_MEM}"
    command:
      - etcd
      - --name=etcd-2
      - --data-dir=/etcd-data
      - --listen-client-urls=http://0.0.0.0:2379
      - --advertise-client-urls=http://etcd-2:2379
      - --listen-peer-urls=http://0.0.0.0:2380
      - --initial-advertise-peer-urls=http://etcd-2:2380
      - --initial-cluster=etcd-1=http://etcd-1:2380,etcd-2=http://etcd-2:2380,etcd-3=http://etcd-3:2380
      - --initial-cluster-state=new
      - --initial-cluster-token=lorawan-lab-etcd
    volumes:
      - etcd-2-data:/etcd-data
    networks: [dcs]

  etcd-3:
    image: ${ETCD_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_ETCD_CPUS}"
    mem_limit: "${LAB_ETCD_MEM}"
    command:
      - etcd
      - --name=etcd-3
      - --data-dir=/etcd-data
      - --listen-client-urls=http://0.0.0.0:2379
      - --advertise-client-urls=http://etcd-3:2379
      - --listen-peer-urls=http://0.0.0.0:2380
      - --initial-advertise-peer-urls=http://etcd-3:2380
      - --initial-cluster=etcd-1=http://etcd-1:2380,etcd-2=http://etcd-2:2380,etcd-3=http://etcd-3:2380
      - --initial-cluster-state=new
      - --initial-cluster-token=lorawan-lab-etcd
    volumes:
      - etcd-3-data:/etcd-data
    networks: [dcs]
```

The single-host lab uses plaintext only inside the Docker `dcs` network so you can focus on quorum and Patroni behavior. The production cloud manual requires TLS on inter-host etcd traffic. Do not copy this plaintext transport exception into cloud deployment.

## Step 2 - Validate before starting

```bash
docker compose config --quiet
docker compose config --services | grep '^etcd-'
```

Expected:

```text
etcd-1
etcd-2
etcd-3
```

## Step 3 - Start all three members

```bash
docker compose up -d etcd-1 etcd-2 etcd-3
docker compose ps etcd-1 etcd-2 etcd-3
docker compose logs --since=5m --tail=200 etcd-1 etcd-2 etcd-3
```

## Step 4 - Verify quorum

Run `etcdctl` inside one member:

```bash
docker compose exec etcd-1 sh -lc '
  export ETCDCTL_API=3
  export ETCDCTL_ENDPOINTS=http://etcd-1:2379,http://etcd-2:2379,http://etcd-3:2379
  etcdctl endpoint health --cluster
  etcdctl endpoint status --cluster --write-out=table
  etcdctl member list --write-out=table
'
```

Pass only when all three endpoints are healthy, exactly one etcd leader exists, and the member list contains `etcd-1`, `etcd-2`, and `etcd-3`.

## Step 5 - Prove one-member failure tolerance

```bash
docker compose stop etcd-3
docker compose exec etcd-1 sh -lc '
  export ETCDCTL_API=3
  export ETCDCTL_ENDPOINTS=http://etcd-1:2379,http://etcd-2:2379
  etcdctl endpoint health --cluster
'
```

The remaining two members must still form a majority.

Restore the member:

```bash
docker compose start etcd-3
sleep 5
docker compose exec etcd-1 sh -lc '
  export ETCDCTL_API=3
  export ETCDCTL_ENDPOINTS=http://etcd-1:2379,http://etcd-2:2379,http://etcd-3:2379
  etcdctl endpoint health --cluster
'
```

Do not stop a second etcd member during normal testing while one member is already down.

## Verify

Record:

```bash
docker compose exec etcd-1 etcd --version
docker compose exec etcd-1 etcdctl version
docker compose exec etcd-1 sh -lc 'ETCDCTL_API=3 etcdctl --endpoints=http://etcd-1:2379,http://etcd-2:2379,http://etcd-3:2379 endpoint status --write-out=table'
```

## Troubleshooting

If a member reports a cluster-ID mismatch, do not delete volumes blindly. Check whether an old lab cluster already exists. Only remove the etcd lab volumes when you intentionally want a fresh disposable DCS and no Patroni cluster depends on it.

## Next step

Continue with [04-deploy-spilo-patroni-postgresql.md](04-deploy-spilo-patroni-postgresql.md).
