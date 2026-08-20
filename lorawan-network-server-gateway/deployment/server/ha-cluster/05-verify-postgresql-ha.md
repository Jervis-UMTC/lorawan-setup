# Server 5. Verify PostgreSQL Replication and Failover

## Goal

Prove that Patroni can promote a replica and that the old primary does not remain writable.

Do this before HAProxy, PgBouncer, or ChirpStack are allowed to depend on the cluster.

## Step 1 - Capture the healthy baseline

Run on the **lab server VM**:

```bash
cd /opt/lorawan-lab
. ./.env
docker compose exec spilo-1 patronictl list
```

Record the current leader name.

Check all three Patroni REST roles using an ephemeral curl container:

```bash
for node in spilo-1 spilo-2 spilo-3; do
  printf '%-8s ' "$node"
  docker run --rm --network lorawan-lab_database "$CURL_IMAGE" \
    -s -o /dev/null -w '%{http_code}\n' "http://$node:8008/primary"
done
```

Exactly one node should return HTTP `200` from `/primary`.

## Step 2 - Write a test row through the current primary

Connect to the leader and create a disposable validation table in the `chirpstack` database:

```sql
CREATE TABLE IF NOT EXISTS public.lab_ha_probe (
  probe_id BIGSERIAL PRIMARY KEY,
  written_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  note TEXT NOT NULL
);
INSERT INTO public.lab_ha_probe(note) VALUES ('before failover');
SELECT * FROM public.lab_ha_probe ORDER BY probe_id;
```

## Step 3 - Stop the current leader container

Replace `<CURRENT_LEADER>` with the actual leader reported by Patroni:

```bash
docker compose stop <CURRENT_LEADER>
```

Watch the remaining cluster:

```bash
docker compose exec spilo-2 patronictl list
```

Pass condition: an eligible replica becomes the new leader and the surviving other member remains a replica.

## Step 4 - Prove the promoted member is writable

Connect to the new leader and run:

```sql
SELECT pg_is_in_recovery();
INSERT INTO public.lab_ha_probe(note) VALUES ('after failover');
SELECT * FROM public.lab_ha_probe ORDER BY probe_id;
```

Expected:

```text
pg_is_in_recovery = false
both the before-failover and after-failover rows are visible
```

## Step 5 - Restart the old leader

```bash
docker compose start <OLD_LEADER>
sleep 10
docker compose exec spilo-2 patronictl list
```

The old leader must return as a replica. It must not start accepting independent writes.

## Step 6 - Verify etcd still has quorum

```bash
docker compose exec etcd-1 sh -lc 'ETCDCTL_API=3 etcdctl --endpoints=http://etcd-1:2379,http://etcd-2:2379,http://etcd-3:2379 endpoint health --cluster'
```

## Verify

The PostgreSQL HA layer passes only when:

- one and only one Patroni leader exists;
- two replicas are healthy after the old leader rejoins;
- the validation row written before failover is present afterward;
- a new write succeeds on the promoted leader;
- the old leader returns in recovery mode;
- etcd still reports quorum.

## Troubleshooting

If two PostgreSQL members appear writable, stop application testing immediately. Preserve logs and inspect Patroni / etcd state. Do not manually start PostgreSQL outside Patroni or delete DCS keys to force a leader.

## Next step

Continue with [06-deploy-haproxy.md](06-deploy-haproxy.md).
