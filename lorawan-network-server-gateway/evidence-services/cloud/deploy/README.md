# Reproducible Cloud Evidence Deployment Bundle

This directory is the tracked server-side deployment candidate for the four Go evidence/attestation services: ingest, MQTT collector, verifier, and Fabric adapter. It deliberately stops **before** live activation. Rebuilding a server should require the repository plus protected credentials/PKI and the selected durable S3-compatible service; it should not require reconstructing Compose commands from chat history.

The Fabric adapter has two deliberately separate deployment states. The base `compose.yml` runs adapter-1/2 with `FABRIC_ADAPTER_ENABLED=false`, so they expose only local health/readiness and do not open PostgreSQL, read an OpenBao SecretID, or contact Fabric. Actual ledger submission requires the explicit `compose.fabric-adapter-enabled.yml` overlay and must pass `fabric-adapter-enable-preflight.sh` first.

## Frozen HA placement

```text
ulc-01 / 10.104.0.2
  ingest-1
  collector-1
  fabric-adapter-1 standby -> enabled only after Fabric handoff

ulc-02 / 10.104.0.4
  ingest-2
  verifier-1
  fabric-adapter-2 standby -> enabled only after Fabric handoff

ulc-03 / 10.104.0.8
  collector-2
  verifier-2
  no Fabric adapter worker
```

Every runtime starts with the documented ceiling `192 MiB / 0.20 CPU`. That is a measurement guardrail, not permission to remove HA if the 2-GiB hosts are too small.

## Files

```text
compose.yml                    base four-service definition; adapter is hard-frozen disabled
compose.collector-mtls.yml     collector client-certificate mounts
compose.fabric-adapter-enabled.yml
                               explicit activation overlay; never use for standby staging
release.env.example            immutable OCI digest references for all four binaries
hosts/*.env.example            exact node placement + host ports + enabled-adapter mount paths
env/common.env.example         non-secret common DB/S3 settings
env/ingest.env.example         protected ingest DB/S3 credentials + TLS paths
env/collector-password.env.example
                               legacy/reference input only; production preflight rejects password mode
env/collector-mtls.env.example protected collector DB/S3 + client-certificate paths
env/verifier.env.example       protected verifier DB/S3 settings
env/fabric-adapter.env.example protected DB/Fabric topology settings used only after handoff
host-preflight.sh              early read-only live host/capacity/service/port gate
preflight.sh                   final base/standby staged-config gate
fabric-adapter-enable-preflight.sh
                               separate no-mutation gate before enabling ledger submission
```

The Compose definition runs every container as numeric `65532:65532`, read-only root filesystem, all Linux capabilities dropped, `no-new-privileges`, PID limit 128, bounded Docker logs, and no in-image shell/health utility. Collector/verifier/Fabric-adapter health listeners bind host loopback only. Ingest binds only the selected private host IP/backend port; public `evidence.<DOMAIN>:443` remains an independent HAProxy/SNI design gate.

## Inputs that intentionally remain external

A real base deployment must supply:

1. four OCI image **digest** references built from `../packaging/`;
2. the selected SeaweedFS 4.41 raw-evidence cluster from `seaweedfs/`, commissioned with `010` cross-rack placement and the local internal-TLS create-only S3 frontend;
3. per-role PostgreSQL login credentials, each a member only of its corresponding NOLOGIN group role;
4. per-role S3 credentials with minimum object permissions;
5. Evidence server/client PKI and the commissioned PostgreSQL/MQTT/S3 CA files;
6. dedicated read-only MQTT collector broker identities;
7. free private/loopback host ports confirmed on the live server.

Enabling either Fabric adapter additionally requires the real external Fabric Gateway endpoint/TLS identity, MSP ID, Fabric client certificate/private key, channel/chaincode/contract functions, and a deliberately issued OpenBao AppRole SecretID. None of those values is invented by this repository.

The repository does not guess image digests, secrets, or unused evidence-service host ports. The raw-store endpoint itself is now frozen to `https://evidence-objects.internal.lorawan.com:18443`; each evidence container resolves that name to its local host VPC IP, while SeaweedFS's raw S3 listener remains loopback-only.

## Fixed host layout

Use these directories on every server:

```text
/etc/lorawan-cloud/gateway-evidence/
  release.env
  host.env
  common.env
  ingest.env          # only on ingest hosts
  collector.env       # only on collector hosts
  verifier.env        # only on verifier hosts
  fabric-adapter.env  # ulc-01/02 only, and only after external Fabric handoff

/etc/lorawan-pki/gateway-evidence/
  postgres-ca.crt
  s3-ca.crt
  ingest-server.crt / ingest-server.key / gateway-client-ca.crt  # ingest hosts
  mqtt-ca.crt                                                # collector hosts
  collector-broker*.crt/key                                  # mTLS collector mode only

# ulc-01/02 only, created only at Fabric activation time:
/etc/lorawan-cloud/fabric-adapter/
  role_id
  secret_id

/etc/lorawan-pki/fabric/
  tls-ca.crt
  client.crt
  client.key
```

Protected role env files must be `root:root 0600`. Runtime private keys are bind-mounted into a numeric non-root container; install them as `root:<gid 65532> 0440`. Public certificates/CA files must also be readable by runtime `65532:65532`: use either `root:65532 0440` or a root-owned non-writable world-readable public file such as `0444`. The preflight checks actual mode/GID readability so a `0600 root:root` CA cannot pass and then break container startup.

If GID 65532 is unused on the server, a deployment operator may create a named host group for clarity before installing keys:

```sh
sudo groupadd --system --gid 65532 evidence-runtime
```

Do not change an existing GID 65532 owner blindly. If that numeric GID is already allocated, stop and review the container/runtime ownership design instead of weakening key permissions.

## Prepare configuration

Copy examples, then replace placeholders **outside Git**:

```sh
sudo install -d -m 0750 -o root -g root /etc/lorawan-cloud/gateway-evidence
sudo install -d -m 0750 -o root -g root /etc/lorawan-pki/gateway-evidence

# Example only: choose the matching host file.
sudo install -m 0644 -o root -g root release.env /etc/lorawan-cloud/gateway-evidence/release.env
sudo install -m 0644 -o root -g root host.env /etc/lorawan-cloud/gateway-evidence/host.env
sudo install -m 0644 -o root -g root common.env /etc/lorawan-cloud/gateway-evidence/common.env
sudo install -m 0600 -o root -g root ingest.env /etc/lorawan-cloud/gateway-evidence/ingest.env
```

Do not copy literal example placeholders into production.

### Database credentials

`001_gateway_evidence.sql` creates three NOLOGIN group roles:

```text
gateway_evidence_ingestor
gateway_evidence_collector
gateway_evidence_verifier
```

Create separate LOGIN identities at deployment time and grant each only its matching group role. The examples intentionally use `<INGEST_LOGIN>`, `<COLLECTOR_LOGIN>`, and `<VERIFIER_LOGIN>` because canonical login names/passwords are not frozen until credential issuance.

Every DSN uses the commissioned logical endpoint `pgbouncer.internal.lorawan.com:6432`, database `lorawan_telemetry`, hostname-verified TLS, and the mounted PostgreSQL CA. Because this internal name is not assumed to exist in public DNS, Compose maps it inside every container to the **local node private IP** (`10.104.0.2`, `.4`, or `.8`), preserving the local PgBouncer -> local HAProxy -> Patroni-primary path. The Go pool also enforces SCRAM-SHA-256 and verifies role membership/writable-primary routing on every new physical DB session.

After creating each evidence LOGIN role, regenerate the protected PgBouncer SCRAM verifier candidate from authoritative PostgreSQL state and refresh `/etc/pgbouncer/userlist.txt` **one node at a time** (`ulc-01`, then `ulc-02`, then `ulc-03`), preserving existing role verifiers. Reload PgBouncer in place and prove the new credential through that node's `:6432` endpoint before advancing. Creating the PostgreSQL role without this refresh will leave PgBouncer authentication stale.

### S3 credentials

The object-store backend is implemented, but the service is not selected/provisioned yet. The minimum permission split should be:

```text
ingest:    HeadBucket + GetObject + PutObject on evidence prefix
collector: HeadBucket + GetObject + PutObject on evidence prefix
verifier:  HeadBucket + GetObject only on evidence prefix
```

The application uses conditional create-if-absent writes. Do not grant object delete/overwrite administration to these runtime credentials.

### Collector broker authentication

Production collector authentication is frozen to **mTLS** because the current commissioned `ulc-01:8884` and `ulc-02:8884` gateway-facing broker listeners require client certificates and map certificate identity to the MQTT username. Do not reopen password mode merely for convenience.

```text
collector-mtls.env.example -> /etc/lorawan-cloud/gateway-evidence/collector.env
EVIDENCE_COLLECTOR_AUTH_MODE=mtls
```

Issue dedicated collector clientAuth identities whose Mosquitto usernames receive only `read as923/gateway/+/event/#`; grant no publish or command permission. `compose.collector-mtls.yml` is supplied automatically by `preflight.sh` and must also be supplied to the later activation command. The password example remains reference material only and is rejected by production preflight.

Each collector replica has **two distinct client IDs**, one per fixed backend (`10.104.0.2:8884` and `10.104.0.4:8884`). Across two collectors that produces four independent persistent read-only sessions.

## Fast live-host preflight

Before creating evidence credentials, applying the migration, or choosing final ports, run the same observation-only check from an **already-authorized SSH session** on each server:

```sh
sudo bash host-preflight.sh
```

Run it on `ulc-01`, then `ulc-02`, then `ulc-03`. It verifies current private-IP identity, memory/disk headroom, UID/GID `65532` collision risk, Docker/Compose/Buildx availability, container RSS, HAProxy/PgBouncer state, Patroni/etcd visibility, current `:8884` mTLS policy where Mosquitto lives, the existing anchor `:443`, and dynamically suggests currently free ingest/health ports. Suggested ports are observations only; they are not reserved and should be copied into protected host configuration immediately before the final staged-config preflight.

The script deliberately does not require the repository runner to possess server private keys. Never copy a workstation SSH private key into this repository or onto a Droplet merely to automate this check.

## Mandatory final staged-config preflight

After files are installed, but **before pulling or starting anything**:

```sh
sudo ./preflight.sh \
  /etc/lorawan-cloud/gateway-evidence/release.env \
  /etc/lorawan-cloud/gateway-evidence/host.env
```

It verifies:

- exact frozen node/profile placement, including adapter-1 on ulc-01 and adapter-2 on ulc-02 only;
- correct private IP on the host;
- all four image references are immutable `@sha256` references;
- the base Fabric adapter profile remains standby-only and accepts no DB/OpenBao/Fabric credential mounts;
- selected host ports are numeric and currently free;
- protected env/key ownership and permissions;
- required CA/certificate files are actually readable by runtime `65532:65532` and private keys are `root:65532 0440`;
- `pgbouncer.internal.lorawan.com` is mapped inside containers to the local node private IP;
- production backend is `s3`, never the dev filesystem;
- collector auth-mode-specific inputs;
- PostgreSQL DSNs use the logical PgBouncer endpoint + `verify-full`;
- `docker compose config --quiet` succeeds.

Expected final marker:

```text
EVIDENCE_DEPLOYMENT_PREFLIGHT=PASS
```

The script does not pull images, start containers, issue credentials, alter permissions, or mutate the database.

## Base/standby activation command

Do **not** run this until image digests, object storage, DB migration/login roles + three-node PgBouncer verifier refresh, Evidence PKI, shared-443 design, and live host resource preflight are approved. Production collectors use mTLS, so collector hosts include the collector override:

```sh
sudo docker compose \
  --env-file /etc/lorawan-cloud/gateway-evidence/release.env \
  --env-file /etc/lorawan-cloud/gateway-evidence/host.env \
  -f compose.yml \
  -f compose.collector-mtls.yml \
  up -d
```

On `ulc-02` there is no collector profile, so use only `compose.yml`. The Fabric adapter profile is present on ulc-01/02 but remains disabled by the base Compose definition. Start and verify one logical boundary at a time; do not bring all six evidence replicas plus two adapter standbys up blindly.

## Fabric adapter activation is a separate gate

Do not issue/install an OpenBao SecretID merely because the standby container is healthy. After the external Fabric handoff is complete, install the protected adapter env/identity files, then run:

```sh
sudo ./fabric-adapter-enable-preflight.sh \
  /etc/lorawan-cloud/gateway-evidence/release.env \
  /etc/lorawan-cloud/gateway-evidence/host.env
```

This preflight verifies the exact adapter host/worker identity, protected file modes, `fabric_adapter` PgBouncer TLS DSN, fixed OpenBao service path, Fabric certificate/private-key match, stable OpenBao TLS/health, external Fabric Gateway server TLS, and the combined Compose configuration. It performs no pull/start/credential issuance or state mutation.

Only after that marker is `FABRIC_ADAPTER_ENABLE_PREFLIGHT=PASS` may the explicit overlay be used for the one adapter being activated:

```sh
sudo docker compose \
  --env-file /etc/lorawan-cloud/gateway-evidence/release.env \
  --env-file /etc/lorawan-cloud/gateway-evidence/host.env \
  -f compose.yml \
  -f compose.fabric-adapter-enabled.yml \
  up -d fabric-adapter
```

On ulc-01 include `-f compose.collector-mtls.yml` as well when managing the whole host stack. If the external Fabric Gateway requires a separate **transport mTLS** client certificate rather than server-auth TLS plus the Fabric application identity currently implemented, stop at the preflight failure and extend/rebuild the adapter; never disable TLS verification to force the connection.

## What is still not claimed

The four Linux/amd64 binaries and exact checksum lock are reproducible and the packaging validator accepts all four. This bundle still does **not** claim registry OCI `image@sha256` digests, durable S3 commissioning, live `gateway_evidence` migration/login credentials, Evidence PKI, shared public `:443`, Linux Compose/preflight execution for the newest adapter files, or live service commissioning. It exists so those remaining deployment inputs can be filled into one repeatable, reviewable server layout rather than rebuilt manually later.
