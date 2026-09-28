# OpenBao — Three-Node KMS Bootstrap, Identity, Operations and Recovery

**Status:** commissioned normal-path architecture. This is a reproducible technology chapter, not authorization to initialize/restore a live KMS or a fresh assertion about current leader or seal state. Read [operator guide 12](12-openbao.md) first. Never copy an OpenBao recovery share, root token, Transit private key, RoleID/SecretID value or audit HMAC material into Git, a terminal transcript or the final Word document.

## 1. Identify the exact service and why it exists

OpenBao 2.6.2 maintains an independent **three-voter integrated Raft** KMS on ULC-01/02/03 (10.104.0.2, .4, .8); each node has private TLS API `:8200` and Raft traffic `:8201`. The sole enabled Fabric adapter on ULC-01 uses its **own local HAProxy** `openbao-kms.internal.lorawan.com:18200` to reach a usable unsealed backend; standby ULC-02 has the same private frontend but does **not** become a production Fabric writer merely because KMS is healthy. ULC-03 does not need `:18200`. Quorum is 2 of 3, but three healthy members should be restored before further maintenance.

OpenBao signs/verifies the **digest** of approved exact payload bytes with a non-exportable `ecdsa-p256` Transit key. The external HRC Fabric ledger stores/verifies the source-bound anchor; the **separate gateway-evidence verifier** decides whether a LoRaWAN event is eligible. These authorities must not be merged.

## 2. Commissioned identity and runtime inventory

| Area | What to preserve |
|---|---|
| OpenBao release | 2.6.2 OCI index `sha256:11fd73a2102cda9c55d5d881a8c3210303146a7ec1e8ac76f526e175c6d24641`; commissioned linux/amd64 manifest `sha256:e29524ba7c3f20d01f562c481e3eccbad6c91df45a2f2531433da4951e408cff`. Inspect current running image ID before replacement. |
| Host config | `/etc/lorawan-cloud/openbao/openbao.hcl`, `/etc/lorawan-cloud/openbao/compose.yml` |
| Host TLS | `/etc/lorawan-pki/openbao/ca.crt`, node-specific server.crt/key; actual cert SAN must cover the client-visible `openbao-kms.internal.lorawan.com` |
| Durable state | `/srv/openbao/data`, separately protected off-node bootstrap/recovery shares and snapshot |
| Stable adapter CA | `/etc/haproxy/openbao-ca.crt` on ULC-01/02, byte-identical to approved OpenBao CA |
| Engine/key | `transit/`, `lorawan-evidence` nonexportable P-256 with plaintext backup disabled |
| Policy | `fabric-evidence-signer`: *only* update on `transit/sign/lorawan-evidence/sha2-256` and `transit/verify/lorawan-evidence/sha2-256` |
| Authentication | `approle/`, role `fabric-adapter`, bind_secret_id true, SecretID TTL 86400 seconds (24 h), protected per-adapter RoleID and short-lived SecretID |
| Audit | reviewed enabled audit device and protected audit path; disabling/re-enabling it can change HMAC/salt continuity |

Use the reviewed exact deployment file for complete HCL, security options, and mounts. Do **not** overwrite an existing live Raft volume with a generic template. The OpenBao private CA key does not belong on every service host just because the public CA certificate does.

## 3. Read-only health: each ULC shell

~~~bash
hostname -f
date -u
sudo docker compose -f /etc/lorawan-cloud/openbao/compose.yml ps
sudo docker inspect openbao --format 'status={{.State.Status}} restarts={{.RestartCount}} image={{.Image}}'
sudo ss -lntp | grep -E ':(8200|8201|18200)\b' || true
~~~

The right `:8200` and `:8201` binds are **node-specific private IPs**, never wildcard/public. `:18200` is present only on ULC-01/02. Find active/standby from live state; old “leader on ULC-01” screenshots are not routing instructions.

Check direct status using the actual local VPC IP from an authorized container; for ULC-01 example:

~~~bash
sudo docker exec -e BAO_ADDR=https://10.104.0.2:8200 \
  -e BAO_CACERT=/openbao/tls/ca.crt \
  openbao bao status -format=json
~~~

Inspect JSON: `initialized=true`, `sealed=false`, `storage_type=raft` and `ha_enabled=true`. A sealed process can exist without serving signing; **do not run `bao operator init` on a sealed node**. If an IP is absent from the server certificate, this CLI example may fail hostname checking; prefer the approved direct API test below which sets the correct TLS name.

~~~bash
curl --connect-timeout 3 --max-time 5 \
 --cacert /etc/lorawan-pki/openbao/ca.crt \
 --resolve 'openbao-kms.internal.lorawan.com:8200:10.104.0.2' \
 -sS -o /dev/null -w 'DIRECT_HTTP=%{http_code}\n' \
 'https://openbao-kms.internal.lorawan.com:8200/v1/sys/health?standbyok=true'
~~~

Repeat per node with its real IP. `HTTP 200` with verified CA/hostname is a usable initialized/unsealed node under `standbyok=true`, not proof of Raft membership. From ULC-01/02 verify their own local `:18200` similarly with `/etc/haproxy/openbao-ca.crt`. On authenticated admin path require **three voters, one leader**, with the correct Raft membership. Do not paste admin tokens into interactive shell history for a health check.

## 4. Distinguish bootstrap from recovery

**Empty cluster/new first installation only:**

1. Confirm **all three** private IPs, Raft/client port reachability, synchronized time, Docker/Compose, free persistent storage, approved immutable OpenBao image and node-specific certificate/key/CA; verify the config's three unique node IDs and addresses.
2. Create protected config/storage/PKI paths following the source deployment bundle with the correct numeric runtime user. A missing directory on one host must not cause an administrator to recreate an entire existing cluster.
3. Configure all three reviewed HCL/Compose definitions. Validate HCL and Compose *off-path* before starting.
4. Start **one** nominated initial OpenBao node; initialize **once**, under a protected operator session. Transfer recovery/unseal material **off node** into the approved secure custody immediately; redact output.
5. Unseal initial member through the approved protected workflow; confirm initialized/unsealed and its Raft role.
6. Start the second member; **join the existing Raft cluster** and unseal it. Check authenticated membership. Repeat for third member. **Never initialize each node separately.**
7. Prove 3 voters, one leader, TLS and private binds. Then *only on an explicitly empty administrative mount/key/role state* enable Transit, create the non-exportable key, exact policy and AppRole sequentially with read-back gates. Do not recreate an already-existing key or role.
8. Enable ULC-01 and ULC-02's node-local KMS HAProxy frontends **one host at a time**, preserving all existing SQL/MQTT/other frontends. Require CA/name verification and normal scoped sign+verify acceptance through `:18200`. A signing test is not Fabric commit verification.

**Existing cluster/recovery:** do **not** run the bootstrap sequence. A sealed member requires authorized unseal material and an established cluster identity, not init. A failed single member requires surviving authoritative membership and compatible local state. A quorum-loss/entire-cluster snapshot restore is a separate *isolated* controlled DR operation with protected shares, snapshot provenance, no competing original authority, and a clear database/Fabric outbox recovery boundary. An ordinary `bao operator raft snapshot restore` on a live three-member cluster is unsafe.

## 5. AppRole lifecycle and common auth failure

Adapter authentication is distinct from server TLS. Inspect the current app's `/readyz`, protected RoleID/SecretID locations, AppRole policy/TTL and current active Raft member before rotation. The commissioned SecretID TTL is **24 h**, so stale credentials may explain a functioning KMS endpoint with a failed signer login.

The 2026-09-08 qualification exposed a real trap: issuing a new SecretID against an OpenBao **standby** could fail storage persistence as read-only. The approved rotation helper discovers the *active* member and confirms the unchanged RoleID, role/policy, key type/nonexportability and TTL before issuing; install the new SecretID only in protected adapter runtime custody and verify scoped login/sign/verify without printing it. Do not grant a broader policy to bypass a bad token. Revoke the superseded SecretID according to the approved overlap and standby/writer requirements.

## 6. Backup, failure isolation and handoff

- **Process up but sealed:** use protected unseal/recovery, not initialization.
- **Direct :8200 healthy but :18200 failed:** diagnose HAProxy TLS backend/health, local listener, and CA copy, not Raft reset.
- **Sign fails after successful login:** inspect Transit key path, exact hash algorithm, key policy and request bytes.
- **Sign works, Fabric unavailable:** adapter/HRC path; telemetry and evidence should continue while eligible outbox waits or reconciles.
- **Audit device cannot write:** treat it as a security/availability fault; do not casually disable/re-enable audit logging to “clean up” evidence.
- **One Raft voter down:** repair one member with 2/3 still agreed; do not use the outage as a routine failover demonstration.

Protected backup inventory must include compatible image/config, service PKI, complete off-node Raft snapshot with verified status/hash, retained recovery/unseal material, audit device/storage recovery, AppRole rotation custody and adapter outbox/identity dependencies. A snapshot **does not** contain all independent PostgreSQL/SeaweedFS/Fabric state. Record the exact timestamp/revision and planned RPO/RTO for any full restore.

**PASS:** 3 intended voters, one leader, all initialized/unsealed, private listener exposure, two working node-local KMS frontends, non-exportable signer key, correct least-privilege AppRole, healthy audit, scoped sign/verify and recoverable protected snapshot. A live external anchor additionally requires the adapter's authoritative Fabric commit/query/verify gate.

Source maintenance: [actual three-node KMS runbook](../server/cloud-production/20a-openbao-three-node-ha-deployment.md), [Fabric qualification](../server/cloud-production/20-openbao-and-fabric-adapter.md). Include operative steps, security boundary and failures inside the comprehensive Word document, not mandatory Markdown links.
