# OpenBao — Operator Manual

## What this technology does

OpenBao is the three-node KMS/secret-management service used by the Fabric evidence path. It stores the non-exportable Transit signing key, authenticates the Fabric adapter through a least-privilege AppRole, and maintains the cryptographic/audit boundary independently from Hyperledger Fabric.

OpenBao is **not** the Fabric ledger and is not the gateway-evidence verifier.

## Current commissioned topology

```text
ULC-01 10.104.0.2 -> OpenBao voter -> TLS API :8200 / Raft :8201
ULC-02 10.104.0.4 -> OpenBao voter -> TLS API :8200 / Raft :8201
ULC-03 10.104.0.8 -> OpenBao voter -> TLS API :8200 / Raft :8201

quorum = 2 of 3

ULC-01 adapter -> local HAProxy :18200 -> usable OpenBao backend
ULC-02 adapter -> local HAProxy :18200 -> usable OpenBao backend
TLS service name = openbao-kms.internal.lorawan.com
```

Current commissioned version: OpenBao 2.6.2 pinned by immutable image in the deployment runbook.

Runtime layout:

```text
/etc/lorawan-cloud/openbao/openbao.hcl
/etc/lorawan-cloud/openbao/compose.yml
/etc/lorawan-pki/openbao/{ca.crt,server.crt,server.key}
/srv/openbao/data
container name: openbao
```

## Security hard stops

Routine health work must **never** casually run:

```text
bao operator init
bao operator unseal with shares pasted into a terminal
bao operator raft snapshot restore
Transit key delete/rotate/export operations
AppRole SecretID generation outside the documented rotation procedure
root-token extraction for ordinary troubleshooting
Raft data deletion/reset
```

Initialization occurs once per cluster. The protected bootstrap/recovery material must never be printed, committed to Git, copied into Markdown, or pasted into chat.

## Step 1 — Check container state on all three nodes

Run on ULC-01, ULC-02, and ULC-03:

```bash
sudo docker compose -f /etc/lorawan-cloud/openbao/compose.yml ps
sudo docker inspect openbao --format 'status={{.State.Status}} restart_count={{.RestartCount}}'
```

**PASS means:** the OpenBao container is running on each intended member without a restart loop.

## Step 2 — Check private listeners

On each node:

```bash
sudo ss -lntp | grep -E ':(8200|8201)\b'
```

Expected: the node's own private `10.104.0.x` address, not a wildcard/public listener.

ULC-01 and ULC-02 should additionally have the HAProxy adapter-facing endpoint:

```bash
sudo ss -lntp | grep ':18200\b'
```

ULC-03 does not need an adapter-facing `:18200` frontend.

## Step 3 — Check direct node initialization/seal/HA state without a token

Use the current node IP:

```bash
NODE_IP="$(hostname -s | awk '{if($0=="ulc-01")print "10.104.0.2"; else if($0=="ulc-02")print "10.104.0.4"; else if($0=="ulc-03")print "10.104.0.8"}')"

test -n "$NODE_IP" || { echo 'UNKNOWN_HOST'; exit 1; }

sudo docker exec \
  -e BAO_ADDR="https://${NODE_IP}:8200" \
  -e BAO_CACERT=/openbao/tls/ca.crt \
  openbao bao status -format=json
```

Interpret the JSON, not only the process exit code.

**Normal commissioned result:**

```text
initialized = true
sealed = false
storage_type = raft
ha_enabled = true
```

A sealed OpenBao server can return a non-zero CLI status even though the process is running. That means the KMS is not usable; it is not permission to reinitialize it.

## Step 4 — Check direct TLS health with a bounded timeout

```bash
NODE_IP="$(hostname -s | awk '{if($0=="ulc-01")print "10.104.0.2"; else if($0=="ulc-02")print "10.104.0.4"; else if($0=="ulc-03")print "10.104.0.8"}')"

curl --connect-timeout 3 --max-time 5 \
  --cacert /etc/lorawan-pki/openbao/ca.crt \
  --resolve "openbao-kms.internal.lorawan.com:8200:${NODE_IP}" \
  -sS -o /tmp/openbao-health.json -w 'HTTP=%{http_code}\n' \
  'https://openbao-kms.internal.lorawan.com:8200/v1/sys/health?standbyok=true'

cat /tmp/openbao-health.json
rm -f /tmp/openbao-health.json
```

**PASS means:** the initialized/unsealed node is classified usable under `standbyok=true`, with TLS hostname verification intact.

Do not use `-k`, `tls-skip-verify`, or an IP-name mismatch workaround.

## Step 5 — Check the stable KMS endpoint from adapter hosts

On ULC-01:

```bash
curl --connect-timeout 3 --max-time 5 \
  --cacert /etc/haproxy/openbao-ca.crt \
  --resolve 'openbao-kms.internal.lorawan.com:18200:10.104.0.2' \
  -sS -o /dev/null -w 'HTTP=%{http_code}\n' \
  'https://openbao-kms.internal.lorawan.com:18200/v1/sys/health?standbyok=true'
```

On ULC-02, use `10.104.0.4` in `--resolve`.

**PASS means:** HTTP 200 through the node-local HAProxy KMS frontend with hostname verification.

If direct OpenBao nodes are healthy but `:18200` fails, troubleshoot HAProxy KMS routing before changing OpenBao.

## Step 6 — Check recent bounded logs

```bash
sudo docker compose -f /etc/lorawan-cloud/openbao/compose.yml \
  logs --since=15m --tail=150 openbao
```

Look for seal, Raft, storage, TLS, audit, or request-forwarding errors. Do not dump secret-bearing request payloads.

## Step 7 — Verify 3-voter Raft membership only with approved administrative authority

Raft membership is an authenticated administrative read. Use the protected operator procedure from the OpenBao runbook; do not extract the root token into ordinary shell history.

Required result:

```text
exactly three intended voters
one current leader
ULC-01, ULC-02, ULC-03 all represented
```

The leader may move. Do not fail it back to match old documentation.

## Step 8 — Verify the Transit/AppRole security contract

The commissioned contract is:

```text
Transit key: lorawan-evidence
key type: ecdsa-p256
exportable: false
plaintext backup: false

policy: fabric-evidence-signer
allowed paths only:
  transit/sign/lorawan-evidence/sha2-256 -> update
  transit/verify/lorawan-evidence/sha2-256 -> update

AppRole: fabric-adapter
bind_secret_id: true
SecretID TTL: 24 h
```

Do not regenerate a SecretID merely because its current value is not visible. Inspect the adapter auth failure and follow the explicit credential-rotation procedure.

Important operational fact: issue/rotate the Fabric adapter SecretID against the **current active OpenBao member** using the reviewed helper. The current production history already proved that issuing against a standby can fail persistence against read-only storage.

## Step 9 — Verify audit boundary before trusting signing evidence

Use the OpenBao runbook's audit inspection commands and confirm the commissioned audit device remains enabled/healthy and its storage path is protected.

Do not disable/re-enable an audit device to clear an error casually; doing so changes salt/HMAC continuity and can destroy incident-response evidence.

## Safe configuration change procedure

1. prove all three members are initialized/unsealed and the stable endpoint works;
2. identify the current Raft leader with the approved admin read path;
3. back up the exact configuration being changed;
4. validate OpenBao HCL with the pinned image before restart;
5. validate Compose model;
6. change one node/candidate at a time;
7. preserve quorum throughout;
8. verify direct node health and stable `:18200` health;
9. verify Raft membership;
10. verify one harmless scoped cryptographic operation only when the changed boundary requires it.

Do not restart all three members for a normal config change.

## Backup/recovery rule

Before destructive KMS testing or recovery, use the dedicated runbook to create/verify a Raft snapshot and confirm protected recovery/unseal material exists off-node.

OpenBao Raft replication is HA, not a substitute for the protected recovery material or a tested recovery path.

Never perform an in-place snapshot restore merely because one node is unhealthy.

## Troubleshooting map

| Symptom | First check |
|---|---|
| container down | Compose/config/storage/TLS/runtime |
| process up, node sealed | seal/recovery procedure; **not init** |
| direct node healthy, `:18200` fails | HAProxy KMS frontend/backend health |
| only adapter auth fails | AppRole RoleID/SecretID TTL/policy/login path |
| login works, sign denied | signer policy/key path/capabilities |
| signing works, Fabric fails | Fabric adapter/Fabric network, not OpenBao |
| inconsistent Raft peer view | authenticated Raft/member/network investigation |

## Completion checklist

- three OpenBao containers running;
- all three initialized and unsealed;
- private `8200/8201` listener exposure only;
- exact three-voter Raft cluster with one leader;
- ULC-01/02 stable `:18200` KMS endpoints return TLS-verified health;
- `lorawan-evidence` key remains non-exportable ECDSA P-256;
- signer policy remains sign/verify-only;
- adapter AppRole remains least privilege;
- audit boundary is healthy;
- protected recovery/snapshot procedure is known before destructive work.

## Complete commissioning, AppRole and recovery companion

Use [OpenBao three-member KMS installation, AppRole/Transit identity, rotation, protected snapshots and recovery](OPENBAO-HA-PKI-APPROLE-RECOVERY.md). Bootstrap instructions are **not** a sealed-node repair, and ULC-02 Fabric adapter ownership remains separate from KMS health.

## Detailed runbooks

- [`../server/cloud-production/20a-openbao-three-node-ha-deployment.md`](../server/cloud-production/20a-openbao-three-node-ha-deployment.md)
- [`../server/cloud-production/20-openbao-and-fabric-adapter.md`](../server/cloud-production/20-openbao-and-fabric-adapter.md)