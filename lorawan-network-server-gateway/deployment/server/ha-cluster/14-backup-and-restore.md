# Server 14. Backup and Restore Checks

## Goal

Create and actually restore the recovery assets needed for the single-VM lab.

Replication is not a backup. A file is not trusted until it has been inspected, checksummed, copied off the VM, and restored in isolation.

## Before you start

Run on the **lab server VM**:

```bash
cd /opt/lorawan-lab
. ./.env
docker compose ps
docker compose exec spilo-1 patronictl list
```

Create a protected backup workspace:

```bash
install -d -m 700 ~/backups/lorawan-lab/{etcd,chirpstack-db,telemetry,openbao,config}
```

### Full-stack lab rule: run restore tests one at a time

Before each disposable restore container, check:

```bash
free -h
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}'
```

Do not run the ChirpStack PostgreSQL restore, TimescaleDB restore, and OpenBao restore environments at the same time. Each restore test temporarily adds another database/KMS process outside the normal 6.4 GiB container budget. Finish and destroy one disposable restore environment before starting the next.

If the VM has less than about 1 GiB `available` memory, stop and identify memory pressure before starting a restore. Do not stop a required production-path technology merely to make a restore command fit.

## Step 1 - Back up etcd

Take a snapshot from a healthy member:

```bash
docker compose exec -T etcd-1 sh -lc '
  export ETCDCTL_API=3
  etcdctl --endpoints=http://127.0.0.1:2379 snapshot save /tmp/etcd-snapshot.db
'

ETCD1_ID=$(docker compose ps -q etcd-1)
test -n "$ETCD1_ID"
docker cp "$ETCD1_ID:/tmp/etcd-snapshot.db" \
  ~/backups/lorawan-lab/etcd/etcd-snapshot.db
unset ETCD1_ID
```

Validate the snapshot using the `etcdutl` version matching the selected etcd image:

```bash
sha256sum ~/backups/lorawan-lab/etcd/etcd-snapshot.db
```

Run `etcdutl snapshot status` from the pinned etcd tool image and record the result.

Do not restore this snapshot over the live DCS merely to test it. Restore into a disposable isolated etcd test container/network.

## Step 2 - Create a logical ChirpStack PostgreSQL backup

Dump through the current primary route:

```bash
umask 077
docker run --rm \
  --network lorawan-lab_application \
  -v "$HOME/backups/lorawan-lab/chirpstack-db:/backup" \
  "$POSTGRES_CLIENT_IMAGE" \
  pg_dump \
    --host=haproxy \
    --port=5432 \
    --username=<BACKUP_ROLE> \
    --dbname=chirpstack \
    --format=custom \
    --file=/backup/chirpstack.dump
```

Use protected password handling. Do not put the password on the command line.

Validate:

```bash
docker run --rm \
  -v "$HOME/backups/lorawan-lab/chirpstack-db:/backup:ro" \
  "$POSTGRES_CLIENT_IMAGE" \
  pg_restore --list /backup/chirpstack.dump | head -40

sha256sum ~/backups/lorawan-lab/chirpstack-db/chirpstack.dump
```

For production physical backup/WAL recovery, follow [the cloud backup manual](../cloud-production/13-backup-restore-and-disaster-recovery.md).

## Step 3 - Restore the ChirpStack logical dump in isolation

Start a disposable PostgreSQL container on a separate Docker network:

```bash
docker network create lorawan-restore-test 2>/dev/null || true
docker run -d --rm \
  --name chirpstack-restore-db \
  --network lorawan-restore-test \
  -e POSTGRES_PASSWORD='<TEMPORARY_RESTORE_PASSWORD>' \
  -e POSTGRES_DB=chirpstack_restore \
  "$POSTGRES_CLIENT_IMAGE"
```

Wait for readiness:

```bash
until docker exec chirpstack-restore-db pg_isready -U postgres; do sleep 2; done
```

Restore:

```bash
docker cp ~/backups/lorawan-lab/chirpstack-db/chirpstack.dump \
  chirpstack-restore-db:/tmp/chirpstack.dump

docker exec chirpstack-restore-db \
  pg_restore \
    --username=postgres \
    --dbname=chirpstack_restore \
    --exit-on-error \
    /tmp/chirpstack.dump
```

Inspect representative tables/counts using `psql`. Do not connect the restore database to the live gateway or MQTT broker.

Destroy the disposable restore environment after recording evidence:

```bash
docker stop chirpstack-restore-db
docker network rm lorawan-restore-test
```

## Step 4 - Back up TimescaleDB

Use the existing telemetry backup manual:

[TimescaleDB backup, security, and maintenance](../integrations/timescaledb/04-backup-security-and-maintenance.md)

Store a protected copy under:

```text
~/backups/lorawan-lab/telemetry/
```

Required evidence:

- dump catalog is readable;
- checksum is recorded;
- off-VM copy exists;
- isolated restore succeeds;
- telemetry schema version is present after restore;
- Fabric outbox rows and statuses are preserved.

## Step 5 - Back up and restore-test OpenBao KMS

The `openbao-data` Docker volume contains encrypted KMS state, including the Transit key versions required to verify historical evidence signatures. Copying the volume directory while OpenBao is live is not the supported backup method. Take a Raft snapshot through OpenBao instead.

First prove OpenBao is unsealed:

```bash
docker compose exec \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  openbao bao status
```

Use the dedicated snapshot-only AppRole created by the OpenBao lab manual. The credentials are passed on standard input and the short-lived OpenBao token exists only inside the container process:

```bash
{
  sudo cat /opt/lorawan-lab/secrets/openbao-backup/role_id
  sudo cat /opt/lorawan-lab/secrets/openbao-backup/secret_id
} | docker compose exec -T \
      -e BAO_ADDR=http://127.0.0.1:8200 \
      openbao sh -lc '
        IFS= read -r ROLE_ID
        IFS= read -r SECRET_ID
        export BAO_TOKEN="$(bao write -field=token auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"
        bao operator raft snapshot save /tmp/openbao.snap
        unset BAO_TOKEN ROLE_ID SECRET_ID
      '
```

Copy the snapshot out and checksum it:

```bash
OPENBAO_ID="$(docker compose ps -q openbao)"
test -n "$OPENBAO_ID"
docker cp "$OPENBAO_ID:/tmp/openbao.snap" \
  ~/backups/lorawan-lab/openbao/openbao.snap
docker compose exec openbao rm -f /tmp/openbao.snap
unset OPENBAO_ID

test -s ~/backups/lorawan-lab/openbao/openbao.snap
sha256sum ~/backups/lorawan-lab/openbao/openbao.snap \
  | tee ~/backups/lorawan-lab/openbao/openbao.snap.sha256
```

A checksum alone is not a restore test. Restore the snapshot into a disposable OpenBao instance that has no connection to the live `kms`, `application`, or `telemetry` networks.

Create the isolated restore workspace:

```bash
sudo rm -rf /opt/openbao-restore-test
sudo install -d -m 0700 /opt/openbao-restore-test/{config,data}
sudo cp ~/backups/lorawan-lab/openbao/openbao.snap \
  /opt/openbao-restore-test/openbao.snap
sudo chmod 0600 /opt/openbao-restore-test/openbao.snap

sudo tee /opt/openbao-restore-test/config/openbao.hcl >/dev/null <<'HCL'
ui = false
api_addr = "http://127.0.0.1:18200"
cluster_addr = "https://openbao-restore:8201"
storage "raft" {
  path = "/openbao/data"
  node_id = "openbao-restore"
}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_disable = true
}
HCL
sudo chmod 0600 /opt/openbao-restore-test/config/openbao.hcl

docker network create --internal openbao-restore-test 2>/dev/null || true
```

Start a disposable server. TCP 18200 is bound to loopback only so the host can perform the force-restore API call; it is not exposed on the LAN:

```bash
docker run -d --rm \
  --name openbao-restore \
  --network openbao-restore-test \
  -p 127.0.0.1:18200:8200 \
  -v /opt/openbao-restore-test/config:/openbao/config:ro \
  -v /opt/openbao-restore-test/data:/openbao/data \
  -v /opt/openbao-restore-test/openbao.snap:/restore/openbao.snap:ro \
  -v /opt/lorawan-lab/secrets/openbao-approle:/run/openbao-approle:ro \
  "$OPENBAO_IMAGE" \
  server -config=/openbao/config/openbao.hcl
```

Initialize the disposable instance only to obtain a temporary authorization token for the **force restore**. These temporary credentials belong only to this isolated restore container:

```bash
umask 077
docker exec -e BAO_ADDR=http://127.0.0.1:8200 openbao-restore \
  bao operator init -key-shares=1 -key-threshold=1 -format=json \
  > /tmp/openbao-restore-init.json

TEMP_UNSEAL_KEY="$(python3 - <<'PY'
import json
with open('/tmp/openbao-restore-init.json', 'r', encoding='utf-8') as f:
    print(json.load(f)['unseal_keys_b64'][0])
PY
)"
TEMP_ROOT_TOKEN="$(python3 - <<'PY'
import json
with open('/tmp/openbao-restore-init.json', 'r', encoding='utf-8') as f:
    print(json.load(f)['root_token'])
PY
)"

test -n "$TEMP_UNSEAL_KEY"
test -n "$TEMP_ROOT_TOKEN"
printf '%s\n' "$TEMP_UNSEAL_KEY" | docker exec -i \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  openbao-restore bao operator unseal
unset TEMP_UNSEAL_KEY
```

Force-restore the snapshot over the disposable cluster. `snapshot-force` is used only because the disposable cluster was initialized with different temporary Shamir keys:

```bash
curl --fail --silent --show-error \
  --header "X-Vault-Token: $TEMP_ROOT_TOKEN" \
  --request POST \
  --data-binary @/opt/openbao-restore-test/openbao.snap \
  http://127.0.0.1:18200/v1/sys/storage/raft/snapshot-force
unset TEMP_ROOT_TOKEN
rm -f /tmp/openbao-restore-init.json
```

Restart the disposable instance so it loads the restored seal state:

```bash
docker restart openbao-restore
docker exec -e BAO_ADDR=http://127.0.0.1:8200 openbao-restore bao status || true
```

It should now be sealed. Unseal it using **two original lab OpenBao Shamir shares from the protected recovery store**, entered at the interactive hidden prompts:

```bash
docker exec -it -e BAO_ADDR=http://127.0.0.1:8200 openbao-restore bao operator unseal
docker exec -it -e BAO_ADDR=http://127.0.0.1:8200 openbao-restore bao operator unseal
```

Do not put the original shares in a command argument, file under `/opt/openbao-restore-test`, or shell variable.

Finally prove that the restored snapshot still contains the original AppRole and Transit signing history. Use the original adapter AppRole files mounted read-only into the disposable container:

```bash
docker exec openbao-restore sh -lc '
  export BAO_ADDR=http://127.0.0.1:8200
  ROLE_ID="$(cat /run/openbao-approle/role_id)"
  SECRET_ID="$(cat /run/openbao-approle/secret_id)"
  export BAO_TOKEN="$(bao write -field=token auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"
  bao read transit/keys/lorawan-evidence
  INPUT="$(printf %s openbao-restore-self-test | base64 | tr -d "\n")"
  SIG="$(bao write -field=signature transit/sign/lorawan-evidence/sha2-256 input="$INPUT" prehashed=false marshaling_algorithm=asn1)"
  VALID="$(bao write -field=valid transit/verify/lorawan-evidence/sha2-256 input="$INPUT" signature="$SIG" prehashed=false marshaling_algorithm=asn1)"
  test "$VALID" = true
  unset BAO_TOKEN ROLE_ID SECRET_ID INPUT SIG VALID
'
```

Pass only when the AppRole login succeeds, `transit/keys/lorawan-evidence` exists with its historical versions, and the restored key signs/verifies correctly. For a complete evidence recovery test, also restore the matching TimescaleDB dump in isolation and verify at least one pre-backup stored `evidence_signature` through the restored OpenBao instance.

Destroy the disposable environment:

```bash
docker stop openbao-restore
docker network rm openbao-restore-test
sudo rm -rf /opt/openbao-restore-test
```

The OpenBao Raft snapshot and the Shamir recovery shares are separate recovery assets. The snapshot alone cannot be treated as sufficient recovery material.

## Step 6 - Back up Compose configuration

Do not archive the live Docker socket or raw volumes.

Create a protected configuration archive:

```bash
cd /opt/lorawan-lab
umask 077
tar -czf ~/backups/lorawan-lab/config/lorawan-lab-config.tgz \
  compose.yml \
  configuration
sha256sum ~/backups/lorawan-lab/config/lorawan-lab-config.tgz
```

Review the archive before copying it off-host:

```bash
tar -tzf ~/backups/lorawan-lab/config/lorawan-lab-config.tgz | sort
```

If `configuration/` contains runtime private keys, treat this archive as secret material and encrypt it before off-host storage. Prefer backing up PKI/private keys through the dedicated protected recovery mechanism instead of a general config tarball.

## Step 7 - Back up MQTT PKI separately

Required recovery items:

```text
MQTT CA certificate
protected MQTT CA private-key recovery copy
broker certificate and private key
ChirpStack MQTT client certificate/key when used
Gateway certificate inventory
Gateway certificate fingerprints/serials/expiry
per-gateway ACL source
```

Do not place the CA private key in the Compose runtime mounts.

## Step 8 - Back up Node-RED and Grafana state

Follow the existing integration backup procedures for their named volumes and exported configuration.

At minimum retain:

- Node-RED flows and credential-encryption secret recovery reference;
- Grafana dashboard exports/provisioning and data-source configuration without plaintext secrets.

## Step 9 - Copy backups off the lab VM

The lab VM must not be the only copy.

Copy encrypted/checksummed backups to an independent host or approved backup storage.

Record:

```text
backup timestamp
file name
SHA-256
software/image version
off-host location
restore-test date
restore result
```

## Final acceptance

Backup/restore passes only when:

- etcd snapshot can be inspected and restored in isolation;
- ChirpStack database dump restores to a disposable PostgreSQL instance;
- TimescaleDB dump restores with telemetry and Fabric outbox state;
- OpenBao Raft snapshot is checksummed, restored in isolation, unsealed with protected original recovery shares, and retains the `lorawan-evidence` Transit key history needed to verify stored seals;
- OpenBao backup AppRole cannot sign evidence or restore snapshots;
- configuration archive is readable;
- PKI recovery material exists outside runtime mounts;
- Node-RED/Grafana state can be reconstructed;
- copies exist outside the VM;
- no restore test overwrites the live lab.
