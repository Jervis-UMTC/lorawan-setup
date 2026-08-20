# Fabric 1B. Deploy the OpenBao Evidence KMS

This lab uses **OpenBao Transit** as the application evidence-signing KMS. The Fabric adapter sends canonical evidence bytes to OpenBao and receives a versioned ECDSA signature. The private signing key is generated and retained inside OpenBao; it is never mounted into the adapter container.

This is a single-VM simulation. It proves KMS API, policy, key-version, outage, retry, and recovery behavior, but it does not create host-level isolation because OpenBao and the adapter still share one Docker host. Production must place the KMS on independently protected infrastructure when application-host compromise is in scope.

> [!IMPORTANT]
> The single `openbao` container in this lab is **deliberately not a production availability design**. It lets the failure tests prove that the Fabric path fails closed when the entire KMS is unavailable. A production deployment must replace this single-node dependency with a multi-host OpenBao Integrated Storage (Raft) cluster behind one stable KMS endpoint. The adapter must never fall back to a local evidence private key.

### Lab versus production KMS availability

| Property | Single-VM lab | Production target |
|---|---|---|
| OpenBao voters | 1 | 5 recommended; 3 is the minimum useful HA cluster |
| Failure tolerance | 0 OpenBao node failures | 5 voters tolerate 2 failures; 3 voters tolerate 1 |
| Hosts/failure domains | one Docker host | separate hosts, preferably separate failure domains |
| API path | private Docker `kms` network | private TLS endpoint such as `https://openbao-kms.internal:8200` |
| Seal behavior | Shamir, manually unseal after restart | all standby nodes must remain unsealed, or use a separately protected reviewed auto-unseal design |
| Adapter behavior on one node loss | KMS becomes unavailable in the lab | stable KMS endpoint continues through another unsealed node |
| Adapter behavior on quorum loss | outbox accumulates; no Fabric submission | same fail-closed behavior until quorum returns |

OpenBao Integrated Storage replicates state through Raft. Only an unsealed server can be an HA standby, and a majority of voting members must remain available for Raft writes. Do not count a sealed server as usable redundancy.

## Step 1: Confirm the lab topology and image pin

Run on the lab server VM:

```bash
cd /opt/lorawan-lab
. ./.env
printf 'OpenBao image: %s\n' "$OPENBAO_IMAGE"
docker image inspect "$OPENBAO_IMAGE" --format '{{json .RepoDigests}} {{json .Config.User}}'
docker compose config --quiet
```

Stop if `OPENBAO_IMAGE` is blank, uses `latest`, or is not the reviewed immutable image/tag for this lab.

The topology manual must already contain:

```yaml
networks:
  kms:
    internal: true

volumes:
  openbao-data:
```

Do not publish TCP 8200 or 8201 to the VM host.

## Step 2: Create the OpenBao server configuration

Create the configuration directory and file:

```bash
cd /opt/lorawan-lab
install -d -m 0750 configuration/openbao
cat > configuration/openbao/openbao.hcl <<'HCL'
ui = false

api_addr     = "http://openbao:8200"
cluster_addr = "https://openbao:8201"

storage "raft" {
  path    = "/openbao/data"
  node_id = "openbao-1"
}

listener "tcp" {
  address     = "0.0.0.0:8200"
  tls_disable = true
}
HCL
chmod 0640 configuration/openbao/openbao.hcl
```

The API listener is plaintext **only inside the Docker-internal `kms` network**. Do not copy this exception into production. Production OpenBao must use authenticated TLS and independent host/network controls.

## Step 3: Add OpenBao to Compose

Merge this service into `/opt/lorawan-lab/compose.yml`:

```yaml
  openbao:
    image: ${OPENBAO_IMAGE}
    restart: unless-stopped
    cpus: "${LAB_OPENBAO_CPUS}"
    mem_limit: "${LAB_OPENBAO_MEM}"
    command: ["server", "-config=/openbao/config/openbao.hcl"]
    volumes:
      - ./configuration/openbao:/openbao/config:ro
      - openbao-data:/openbao/data
    networks: [kms]
```

Do not add a `ports:` block. Do not mount the Docker socket. Do not mount Fabric client keys into OpenBao.

Validate and start:

```bash
cd /opt/lorawan-lab
docker compose config --quiet
docker compose up -d openbao
docker compose ps openbao
docker compose logs --since=3m --tail=100 openbao
```

A new server should report that it is not initialized or is sealed. That is expected.

## Step 4: Initialize the single-node lab KMS

Create a protected recovery directory outside the Compose project:

```bash
sudo install -d -m 0700 /root/lorawan-lab-openbao
```

Initialize with three Shamir shares and a threshold of two. Save the JSON directly to a root-only file; do not print it into the terminal transcript:

```bash
sudo sh -c 'umask 077; docker compose -f /opt/lorawan-lab/compose.yml exec -T \
  -e BAO_ADDR=http://127.0.0.1:8200 openbao \
  bao operator init -key-shares=3 -key-threshold=2 -format=json \
  > /root/lorawan-lab-openbao/init.json'

sudo chmod 0600 /root/lorawan-lab-openbao/init.json
sudo test -s /root/lorawan-lab-openbao/init.json
```

`init.json` contains the initial root token and unseal shares. Treat the file as high-impact secret material. Copy the shares/root recovery material to the approved independent protected location, then remove the VM copy after bootstrap if your lab recovery procedure does not require it locally.

## Step 5: Unseal OpenBao

Use two different unseal shares. Run the command with no key argument so the key is entered at the hidden prompt rather than placed in shell history:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal
```

Paste one different share at each prompt.

Verify:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status
```

Pass only when `Initialized` is true and `Sealed` is false.

## Step 6: Bootstrap Transit using the initial root token

Read the root token from the protected initialization record into the current root shell without echoing it:

```bash
sudo -i
cd /opt/lorawan-lab
export OPENBAO_ROOT_TOKEN="$(python3 - <<'PY'
import json
with open('/root/lorawan-lab-openbao/init.json', 'r', encoding='utf-8') as f:
    print(json.load(f)['root_token'])
PY
)"
test -n "$OPENBAO_ROOT_TOKEN"
```

Enable Transit and create the non-exportable P-256 evidence key:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao bao secrets enable transit

docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao \
  bao write transit/keys/lorawan-evidence type=ecdsa-p256 exportable=false allow_plaintext_backup=false
```

If `transit/` already exists, verify it instead of enabling a duplicate mount. Then inspect the key:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao bao secrets list
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao bao read transit/keys/lorawan-evidence
```

Required result: type `ecdsa-p256`, signing supported, `exportable` false, and plaintext backup disabled.

## Step 7: Create the least-privilege adapter policy

```bash
docker compose exec -i -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao policy write fabric-evidence-signer - <<'HCL'
path "transit/sign/lorawan-evidence/sha2-256" {
  capabilities = ["update"]
}

path "transit/verify/lorawan-evidence/sha2-256" {
  capabilities = ["update"]
}
HCL
```

The adapter receives no key-create, key-delete, key-rotate, policy, auth-admin, or raw-storage permission.

## Step 8: Create AppRole machine authentication

Enable AppRole once and create the adapter role:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao bao auth enable approle

docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao \
  bao write auth/approle/role/fabric-adapter \
  token_policies=fabric-evidence-signer \
  token_ttl=15m \
  token_max_ttl=1h \
  secret_id_ttl=0 \
  secret_id_num_uses=0
```

The non-expiring SecretID is a **lab simplification** so a long-running single-VM adapter can reauthenticate without a separate secret-delivery system. Production must use a reviewed workload identity or short-lived/wrapped AppRole credential workflow.

## Step 9: Store only AppRole credentials for the adapter

```bash
install -d -m 0700 /opt/lorawan-lab/secrets/openbao-approle

docker compose exec -T -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao \
  bao read -field=role_id auth/approle/role/fabric-adapter/role-id \
  > /opt/lorawan-lab/secrets/openbao-approle/role_id

docker compose exec -T -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao \
  bao write -f -field=secret_id auth/approle/role/fabric-adapter/secret-id \
  > /opt/lorawan-lab/secrets/openbao-approle/secret_id

chmod 0400 /opt/lorawan-lab/secrets/openbao-approle/role_id
chmod 0400 /opt/lorawan-lab/secrets/openbao-approle/secret_id
```

Do not put RoleID/SecretID values in `.env`, Git, Node-RED, Grafana, or Markdown.

## Step 9A: Create a separate snapshot-only backup identity

The Fabric adapter AppRole must not receive OpenBao backup or restore permission. Create a second policy that can only read a Raft snapshot:

```bash
docker compose exec -i \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao policy write openbao-raft-snapshot-reader - <<'HCL'
path "sys/storage/raft/snapshot" {
  capabilities = ["read", "sudo"]
}
HCL
```

Create the snapshot AppRole:

```bash
docker compose exec \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao write auth/approle/role/openbao-backup \
  token_policies=openbao-raft-snapshot-reader \
  token_ttl=15m \
  token_max_ttl=30m \
  secret_id_ttl=0 \
  secret_id_num_uses=0
```

Store its credentials separately from the adapter identity:

```bash
install -d -m 0700 /opt/lorawan-lab/secrets/openbao-backup

docker compose exec -T \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao read -field=role_id auth/approle/role/openbao-backup/role-id \
  > /opt/lorawan-lab/secrets/openbao-backup/role_id

docker compose exec -T \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao write -f -field=secret_id auth/approle/role/openbao-backup/secret-id \
  > /opt/lorawan-lab/secrets/openbao-backup/secret_id

chmod 0400 /opt/lorawan-lab/secrets/openbao-backup/role_id
chmod 0400 /opt/lorawan-lab/secrets/openbao-backup/secret_id
```

This backup credential can obtain a short-lived token for snapshot **read** only. It cannot restore a snapshot, change policies, rotate Transit keys, or sign evidence. The non-expiring SecretID is again a lab simplification; production backup identity must follow the production KMS authentication policy.

## Step 10: Prove Transit sign and verify before the adapter exists

```bash
umask 077
printf '%s' 'openbao-evidence-kms-self-test' > /tmp/openbao-kms-input.txt
INPUT_B64="$(base64 -w0 /tmp/openbao-kms-input.txt)"

SIGNATURE="$(docker compose exec -T \
  -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao \
  bao write -field=signature transit/sign/lorawan-evidence/sha2-256 \
  input="$INPUT_B64" prehashed=false marshaling_algorithm=asn1 | tr -d '\r\n')"

test -n "$SIGNATURE"
printf 'signature version tag: %s\n' "$(printf '%s' "$SIGNATURE" | cut -d: -f1-2)"

docker compose exec -T -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao \
  bao write transit/verify/lorawan-evidence/sha2-256 \
  input="$INPUT_B64" signature="$SIGNATURE" prehashed=false marshaling_algorithm=asn1
```

Pass only when verification returns `valid true`. Preserve the **complete versioned signature string** in the outbox; do not store only its Base64 tail.

Prove a changed byte fails:

```bash
TAMPERED_B64="$(printf '%s' 'openbao-evidence-kms-self-test!' | base64 -w0)"
docker compose exec -T -e BAO_ADDR=http://127.0.0.1:8200 -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" openbao \
  bao write transit/verify/lorawan-evidence/sha2-256 \
  input="$TAMPERED_B64" signature="$SIGNATURE" prehashed=false marshaling_algorithm=asn1
```

Pass only when verification returns `valid false`.

## Step 10A: Rotate the Transit key and preserve historical verification

The evidence key is versioned. Rotation must create a new version for future signatures while old stored signatures remain verifiable.

Capture the version used by the first signature:

```bash
OLD_VERSION="$(printf '%s' "$SIGNATURE" \
  | sed -n 's/^[^:]*:v\([1-9][0-9]*\):.*/\1/p')"
test -n "$OLD_VERSION"
printf 'old Transit key version: %s\n' "$OLD_VERSION"
```

Rotate only the named Transit key; this is not OpenBao's storage-encryption-key rotation:

```bash
docker compose exec -T \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao write -f transit/keys/lorawan-evidence/rotate
```

Sign the same test bytes again and capture the new version:

```bash
NEW_SIGNATURE="$(docker compose exec -T \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao write -field=signature \
  transit/sign/lorawan-evidence/sha2-256 \
  input="$INPUT_B64" \
  prehashed=false \
  marshaling_algorithm=asn1 | tr -d '\r\n')"

NEW_VERSION="$(printf '%s' "$NEW_SIGNATURE" \
  | sed -n 's/^[^:]*:v\([1-9][0-9]*\):.*/\1/p')"
test -n "$NEW_VERSION"
test "$NEW_VERSION" -gt "$OLD_VERSION"
printf 'new Transit key version: %s\n' "$NEW_VERSION"
```

Verify **both** signatures after rotation:

```bash
OLD_VALID="$(docker compose exec -T \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao write -field=valid \
  transit/verify/lorawan-evidence/sha2-256 \
  input="$INPUT_B64" signature="$SIGNATURE" \
  prehashed=false marshaling_algorithm=asn1 | tr -d '\r\n')"

NEW_VALID="$(docker compose exec -T \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  -e BAO_TOKEN="$OPENBAO_ROOT_TOKEN" \
  openbao bao write -field=valid \
  transit/verify/lorawan-evidence/sha2-256 \
  input="$INPUT_B64" signature="$NEW_SIGNATURE" \
  prehashed=false marshaling_algorithm=asn1 | tr -d '\r\n')"

test "$OLD_VALID" = 'true'
test "$NEW_VALID" = 'true'
```

Do not raise the Transit key's minimum verification version merely because a rotation occurred. Historical evidence remains dependent on its recorded key version for as long as that evidence must be verifiable.

Clean the shell:

```bash
rm -f /tmp/openbao-kms-input.txt
unset INPUT_B64 TAMPERED_B64 SIGNATURE NEW_SIGNATURE \
  OLD_VERSION NEW_VERSION OLD_VALID NEW_VALID OPENBAO_ROOT_TOKEN
exit
```

## Step 11: Record restart behavior

```bash
cd /opt/lorawan-lab
docker compose restart openbao
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status
```

With the Shamir lab seal, restart returns OpenBao to `Sealed: true`. Unseal it with two shares before starting or resuming the Fabric adapter. This deliberately lets the lab exercise KMS-unavailable behavior instead of hiding it behind development mode.

## Production implementation: remove the single-KMS failure point

Do **not** replace the lab Compose service with several OpenBao containers on the same VM and call that production HA. Multiple containers on one host still fail together when the host, storage, kernel, hypervisor, power, or network path fails.

The production pattern is:

```text
Fabric adapter
      |
      | OPENBAO_ADDR=https://openbao-kms.internal:8200
      v
private KMS VIP / load balancer / service address
      |
      +--> openbao-1  voter
      +--> openbao-2  voter
      +--> openbao-3  voter
      +--> openbao-4  voter
      +--> openbao-5  voter

OpenBao nodes:
  API:     TCP 8200 with TLS
  cluster: TCP 8201 between nodes
  storage: local persistent Raft data on every node
```

OpenBao recommends five servers for a production Integrated Storage cluster. Five voting members require three for quorum and tolerate two unavailable voters. If the project accepts a smaller availability target, three voting members require two for quorum and tolerate one unavailable voter. Do not deploy two voting nodes: two voters still require both members for quorum and therefore do not provide useful single-node failure tolerance.

### Production Step A: allocate independent hosts and names

Provision one persistent OpenBao host per voting member. For a five-node target, carry these values through the deployment:

```text
openbao-1.kms.internal
openbao-2.kms.internal
openbao-3.kms.internal
openbao-4.kms.internal
openbao-5.kms.internal
openbao-kms.internal     # stable adapter-facing service name
```

Required network rules:

```text
Fabric adapter -> openbao-kms.internal:8200
approved KMS admin network -> OpenBao API:8200
OpenBao node <-> OpenBao node:8200 during join/administration
OpenBao node <-> OpenBao node:8201 for cluster traffic
Internet -> OpenBao: DENY
```

Place voters across independent failure domains when the platform supports it. Do not put all voters on one Docker host, one physical host, or one storage volume.

### Production Step B: issue TLS certificates before starting OpenBao

Each API listener must use TLS. The certificate presented to clients must validate for the hostname actually used by the client. When a load balancer passes TLS through to the nodes, make sure the node certificates also cover the stable service name when that is the SNI/verification name. Keep the CA and private keys outside source control.

Use paths equivalent to:

```text
/etc/openbao/tls/ca.crt
/etc/openbao/tls/openbao-1-fullchain.pem
/etc/openbao/tls/openbao-1.key
```

Repeat with the correct node certificate/key for every server.

### Production Step C: configure each Raft voter

The following is the **node 1 pattern**. Create the same file on every node, changing `api_addr`, `cluster_addr`, `node_id`, and the node certificate/key paths to that node's own identity. Keep multiple `retry_join` targets so a joining/restarting node is not dependent on one specific peer.

```hcl
ui = false

api_addr     = "https://openbao-1.kms.internal:8200"
cluster_addr = "https://openbao-1.kms.internal:8201"

storage "raft" {
  path    = "/var/lib/openbao"
  node_id = "openbao-1"

  retry_join {
    leader_api_addr       = "https://openbao-2.kms.internal:8200"
    leader_tls_servername = "openbao-2.kms.internal"
    leader_ca_cert_file   = "/etc/openbao/tls/ca.crt"
  }

  retry_join {
    leader_api_addr       = "https://openbao-3.kms.internal:8200"
    leader_tls_servername = "openbao-3.kms.internal"
    leader_ca_cert_file   = "/etc/openbao/tls/ca.crt"
  }

  retry_join {
    leader_api_addr       = "https://openbao-4.kms.internal:8200"
    leader_tls_servername = "openbao-4.kms.internal"
    leader_ca_cert_file   = "/etc/openbao/tls/ca.crt"
  }

  retry_join {
    leader_api_addr       = "https://openbao-5.kms.internal:8200"
    leader_tls_servername = "openbao-5.kms.internal"
    leader_ca_cert_file   = "/etc/openbao/tls/ca.crt"
  }
}

listener "tcp" {
  address         = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_cert_file   = "/etc/openbao/tls/openbao-1-fullchain.pem"
  tls_key_file    = "/etc/openbao/tls/openbao-1.key"
  tls_min_version = "tls12"
}
```

The `cluster_addr` setting is required for Integrated Storage. Raft state is stored locally on every voter and replicated by the cluster; do not point all voters at one shared `raft.db` file or shared writable volume.

### Production Step D: initialize exactly one cluster, then join and unseal the rest

Start all OpenBao services with their node-specific configuration. Initialize **one node only**. Never run `bao operator init` independently on every node, because that creates separate clusters and different root/seal material.

For a Shamir-sealed cluster, the operational sequence is:

```text
1. initialize openbao-1 exactly once;
2. protect the returned root token and unseal shares using the approved recovery process;
3. unseal openbao-1;
4. allow openbao-2..5 to join through retry_join, or join them explicitly with `bao operator raft join`;
5. unseal every joined node with the same cluster unseal shares;
6. prove all expected voters appear in `bao operator raft list-peers`;
7. prove exactly one node is active and the remaining healthy nodes are unsealed standbys.
```

With Shamir, every restarted node must be unsealed independently. A sealed node cannot become an HA standby and cannot take over if the active node fails. If operations require automatic restart recovery, use a separately protected and reviewed auto-unseal mechanism; do not place the auto-unseal dependency in the same failure domain as the OpenBao cluster. Loss of the auto-unseal mechanism can itself prevent the cluster from unsealing.

### Production Step E: put one stable endpoint in front of the cluster

The adapter configuration must contain one service endpoint:

```text
OPENBAO_ADDR=https://openbao-kms.internal:8200
```

Do not configure the adapter with `openbao-1`, then teach application code to guess another node on failure. OpenBao HA and the service/load-balancer layer own node selection and leader changes.

A practical health probe is the OpenBao health endpoint:

```text
GET /v1/sys/health?standbyok=true
```

With normal status-code semantics, initialized/unsealed active nodes are healthy, initialized/unsealed standbys can also be treated as healthy when `standbyok=true`, and sealed nodes remain unhealthy. The load balancer must never route to an uninitialized or sealed node.

### Production Step F: prove quorum before enabling the adapter

From an approved administrative client, set `BAO_ADDR` and `BAO_CACERT`, authenticate with an operator token, and inspect the peer set:

```bash
export BAO_ADDR='https://openbao-kms.internal:8200'
export BAO_CACERT='/path/to/openbao-ca.crt'
bao status
bao operator raft list-peers
```

For a five-voter target, stop if fewer than five expected voters are listed before commissioning. Also inspect HA status through the authenticated `/v1/sys/ha-status` endpoint or equivalent operator tooling. Record which node is active and confirm the others are unsealed standbys.

### Production Step G: perform a real single-node failover test

Before production acceptance:

```text
1. create and verify a harmless Transit test signature through openbao-kms.internal;
2. identify the active OpenBao node;
3. stop only that active node using the approved service procedure;
4. continue calling the stable KMS endpoint;
5. prove another unsealed voter becomes active;
6. sign and verify another harmless test value through the same stable endpoint;
7. run `bao operator raft list-peers` from the surviving cluster;
8. restart the failed node, unseal it when Shamir is used, and wait until it rejoins healthy;
9. repeat the exact-byte Transit verification before declaring recovery complete.
```

The Fabric adapter must not need a configuration change during this test. If changing `OPENBAO_ADDR` is required to recover from one KMS-node loss, the endpoint design is not HA.

### Production Step H: test total KMS/quorum loss without bypassing security

A quorum outage is different from a single-node failure. When quorum is lost or every reachable OpenBao server is sealed/unavailable:

```text
MQTT / ChirpStack / Node-RED / TimescaleDB -> continue
Fabric outbox                              -> keeps durable selected work
Fabric adapter                             -> cannot create/verify a seal
Fabric submission                          -> STOP
local private-key fallback                 -> FORBIDDEN
```

The adapter should classify the KMS failure as transient infrastructure failure, release its processing lease through the normal failed/backoff path, and leave the event durable in the outbox. When KMS quorum returns, the adapter re-authenticates, verifies any already-persisted seal, seals an unsealed event only once, and resumes Fabric submission.

### Production Step I: monitor the KMS as a quorum, not as one URL

Alert on all of these:

- stable KMS endpoint unavailable;
- active node missing;
- expected standby sealed;
- fewer healthy voting peers than the reviewed cluster target;
- Raft quorum at risk or lost;
- peer unexpectedly removed or added;
- repeated leader changes;
- AppRole authentication failures;
- Transit sign/verify failures;
- oldest unsealed Fabric outbox row exceeding its SLA;
- Raft snapshot failure or stale off-host snapshot.

Backups remain required, but a snapshot is disaster recovery, not a substitute for HA. Use Raft HA for ordinary node failure and Raft snapshots for cluster/data-center recovery.

## Lab acceptance

The single-VM lab is ready for the adapter only when all of these are true:

- OpenBao runs from the pinned image on the private `kms` network only;
- Raft storage persists in `openbao-data`;
- initialization and recovery material is protected outside normal Compose configuration;
- Transit is enabled once;
- `lorawan-evidence` is `ecdsa-p256`, non-exportable, and plaintext backup is disabled;
- the `fabric-evidence-signer` policy grants only sign and verify for this one key and SHA-256 path;
- adapter AppRole credentials are stored as root-only files;
- a separate snapshot-only AppRole exists and has no Transit sign/verify or restore permission;
- the KMS self-test returns `valid true` for exact bytes and `valid false` after a byte change;
- rotating `lorawan-evidence` creates a higher Transit key version while both the pre-rotation and post-rotation signatures remain verifiable;
- the operator knows a restart requires unseal in this lab;
- the OpenBao root token and unseal shares are absent from `.env`, Compose, Git, application logs, and PostgreSQL.

Passing this checklist proves the **lab KMS workflow only**. It does not prove KMS high availability.

## Production HA acceptance

Do not call the production KMS highly available until all of these are true:

- the reviewed voter count is deployed on separate persistent hosts/failure domains; the normal target is five voters, or three only when the reduced failure tolerance is explicitly accepted;
- every expected voter appears in `bao operator raft list-peers` and the cluster has quorum;
- exactly one OpenBao node is active and the other healthy voters are unsealed standbys;
- the adapter uses one stable private TLS endpoint such as `https://openbao-kms.internal:8200`, not an individual node address;
- the stable endpoint rejects uninitialized/sealed backends and remains usable when the active voter is stopped;
- stopping one active voter causes another already-unsealed voter to become active without changing adapter configuration;
- Transit sign and verify succeed through the stable endpoint before, during, and after the single-node failover test;
- a restarted Shamir-sealed voter is explicitly unsealed and returns to the healthy peer set before the maintenance window closes;
- loss of KMS quorum causes Fabric work to back off while MQTT, ChirpStack, Node-RED, TimescaleDB, and the durable outbox continue;
- no local evidence-private-key fallback exists;
- Raft peer/quorum health, sealed state, leader changes, Transit failures, and oldest unsealed outbox age are monitored and alerted;
- off-host Raft snapshots and recovery/unseal material are independently protected and their restore procedure has been tested.

Official OpenBao references for this production section:

- https://openbao.org/docs/internals/high-availability/
- https://openbao.org/docs/next/internals/integrated-storage/
- https://openbao.org/docs/next/configuration/storage/raft/
- https://openbao.org/docs/next/concepts/seal/
- https://openbao.org/api-docs/next/system/health/

Next: [02-create-outbox-and-adapter.md](02-create-outbox-and-adapter.md)