# 9. Two-Node ChirpStack HA on the Minimum Three-Droplet Cluster

> **Status: ACTIVE - PRE-DEPLOYMENT PREFLIGHT / DEPENDENCY CLOSURE.** ChirpStack itself has not yet been installed or started in this cloud build. The database client path, MQTT broker/TLS foundation, and Valkey/Sentinel HA layer are already commissioned. Begin this phase with the read-only gate in section 9.3; do not start ChirpStack until the exact image/config schema is pinned and the remaining MQTT workload-authentication/ACL plus second application-node routing boundary is closed.

## 9.1 Goal and current architecture

The minimum HA profile runs two interchangeable ChirpStack v4 instances:

```text
ulc-01 / 10.104.0.2 -> ChirpStack-1
ulc-02 / 10.104.0.4 -> ChirpStack-2
```

Both instances must use the same application database, Valkey state, region configuration, token/JWT secrets, and integration policy. They connect through local HA components rather than directly to elected database or Valkey nodes.

Current commissioned dependency paths:

```text
PostgreSQL
ChirpStack-1 -> pgbouncer.internal.lorawan.com:6432 -> PgBouncer ulc-01
ChirpStack-2 -> pgbouncer.internal.lorawan.com:6432 -> PgBouncer ulc-02
PgBouncer -> local HAProxy :15432 -> current Patroni primary

Valkey
ChirpStack-1 -> valkey.internal.lorawan.com:16379 -> HAProxy ulc-01
ChirpStack-2 -> valkey.internal.lorawan.com:16379 -> HAProxy ulc-02
HAProxy -> current Sentinel-elected Valkey primary

MQTT foundation already proven
client TLS name -> mqtt.internal.lorawan.com
HAProxy frontend -> 10.104.0.2:8883
Mosquitto backends -> 10.104.0.2:8884 and 10.104.0.4:8884
```

The latest controlled Valkey failover elected **ulc-02 (`10.104.0.4`) as primary**. ulc-01 and ulc-03 are replicas. Keep that Sentinel-elected topology; do not manually fail back before ChirpStack commissioning.

## 9.2 Preconditions and stop conditions

Already proven and reusable:

- three-node PostgreSQL/Patroni HA and the `chirpstack` database;
- validated logical database backup boundary;
- local PgBouncer `:6432` on ulc-01 and ulc-02 with client TLS and SCRAM;
- local HAProxy PostgreSQL primary routing;
- Valkey TLS-only service on three nodes;
- three TLS Sentinels, quorum `2`;
- local writable-primary Valkey HAProxy `:16379` on ulc-01 and ulc-02;
- automatic Valkey promotion, data survival, HAProxy convergence, and old-primary replica rejoin;
- Mosquitto TLS backends on ulc-01/02 and broker-backend failover behind ulc-01 HAProxy `:8883`.

Still required before the **first ChirpStack start**:

1. pin the exact ChirpStack image version and immutable digest;
2. extract/inspect the configuration schema and enabled region-file model from that exact image;
3. verify how that image validates the internal PgBouncer and Valkey CAs;
4. inspect the live Mosquitto authentication/ACL configuration rather than assuming the original design file was deployed;
5. create a least-privilege ChirpStack MQTT workload identity using authentication fields actually supported by the pinned ChirpStack image and live Mosquitto configuration;
6. prove the ChirpStack identity can use only the required gateway-backend/application MQTT topics;
7. close the two-application-node MQTT routing gap. The completed Phase 8B implementation has only the validated `10.104.0.2:8883` HAProxy frontend. ChirpStack-2 must not be declared HA while both instances depend on a single HAProxy process;
8. confirm the legal LoRaWAN region and exact active region file;
9. assign migration owner and rollback point.

Public DNS, Reserved IPv4 failover, and HTTPS `:443` are **not prerequisites for the first private ChirpStack canary**. Those belong to Phase 10 after the two private ChirpStack instances are healthy.

**Stop here:** do not create application secrets, run migrations, or start a ChirpStack container if any item above is unresolved.

## 9.3 First executable step - read-only activation preflight

Run this before installing or changing ChirpStack. The purpose is to capture the actual dependency state and discover whether any old ChirpStack files, containers, ports, or images already exist.

From `ulc-03`, inspect ulc-01 and ulc-02 using the existing deployment SSH path. The preflight must record, without printing secrets:

```text
host name and IP
OS release
Docker Engine + Compose versions
CPU / RAM / disk availability
existing ChirpStack containers/images/directories
port 8080 availability
PgBouncer service + :6432 listener
PostgreSQL login path readiness
HAProxy :16379 listener
Valkey TLS/master routing through :16379
Mosquitto service state / :8884 on both broker nodes
HAProxy MQTT :8883 state on ulc-01
live Mosquitto config directives relevant to authentication/ACL/TLS
existing MQTT credential/ACL files by metadata only
active region/topic-prefix evidence already present in repository/host config
```

For the live Mosquitto configuration, capture only directive names and non-secret paths/settings. Do **not** print password-file contents, private keys, or future ChirpStack credentials.

Pass this gate only when the database and Valkey client paths are still healthy, `8080` is free on both application nodes, and the MQTT authentication/routing gap is precisely known. The output from this gate becomes the basis for the next mutation step; do not guess from the original Phase 8 target design.

### 9.3.1 Observed preflight checkpoint - 2026-08-25

The first Phase 9.3 read-only preflight completed far enough to identify the remaining activation blockers without installing or starting ChirpStack.

Validated on both application nodes:

```text
OS: Ubuntu 24.04.4 LTS
CPU: 1 vCPU
RAM: ~1.9 GiB
root disk: ~48 GiB, ~17% used
Docker Engine: 29.7.2
Docker Compose: v5.5.0
existing ChirpStack containers: none
existing ChirpStack images: none
existing /etc/lorawan-cloud/chirpstack: absent
existing /opt/chirpstack: absent
existing /etc/chirpstack: absent
PgBouncer: active + enabled
PgBouncer listener: local VPC :6432
HAProxy PostgreSQL listeners: local VPC :15432/:15433
HAProxy Valkey writable-primary listener: local VPC :16379
Mosquitto: active + enabled
Mosquitto TLS backend: :8884
```

MQTT routing remains asymmetric exactly as expected from Phase 8B:

```text
ulc-01 10.104.0.2:8883 = present
ulc-02 10.104.0.4:8883 = not yet evidenced/present in the pasted checkpoint
Mosquitto backend :8884 = present on both nodes
```

The live Mosquitto directive inventory showed TLS server configuration on both nodes with `cafile`, `certfile`, private `keyfile`, `require_certificate false`, and `tls_version tlsv1.3`. No active `password_file`, `acl_file`, authentication plugin, or `allow_anonymous` line appeared in the sanitized directive output. Do not infer the effective anonymous-access policy from absence of a line; prove it explicitly before creating the ChirpStack workload identity.

The preflight also exposed a hard blocker on both application nodes:

```text
ulc-01 :8080 = IN USE, wildcard bind
ulc-02 :8080 = IN USE, wildcard bind
```

Because ChirpStack is absent, the process currently owning `:8080` is another service and must be identified before choosing the ChirpStack private HTTP port. Do not stop or reconfigure that service yet.

Phase 9.3 is therefore **PARTIAL / BLOCKED FOR DIAGNOSTIC FOLLOW-UP**, not failed.

### 9.3.2 Phase 9.3A blocker diagnostic - 2026-08-25

The follow-up read-only diagnostic narrowed the remaining blockers further.

Port `8080` on both application nodes is definitely **not** published by Docker. The only running containers are the existing Spilo and etcd containers. An HTTP request to `127.0.0.1:8080/` returned `HTTP/1.1 200 OK` with `Content-Type: application/json` on both ulc-01 and ulc-02, so a real host process is serving JSON there. The unprivileged `ss -p` output did not reveal its PID/process identity. Do not stop it; the next check must use privileged socket/process inspection.

MQTT routing is now precise:

```text
ulc-01 HAProxy MQTT frontend: 10.104.0.2:8883 = PRESENT
ulc-01 HAProxy backend pool: 10.104.0.2:8884 + 10.104.0.4:8884
ulc-02 HAProxy MQTT frontend: 10.104.0.4:8883 = ABSENT
ulc-02 HAProxy MQTT config references = none
Mosquitto TLS backend :8884 = PRESENT on both nodes
```

Therefore ChirpStack-2 cannot yet have an independently local MQTT HAProxy route. This is a real Phase 9 dependency, not merely missing evidence.

Mosquitto authentication remains unresolved. The active inventory still shows `require_certificate false`, and only example ACL/password files were present by metadata. No active `password_file`, `acl_file`, authentication plugin, or explicit `allow_anonymous` directive was observed. Because the earlier recursive grep also included historical/backup files, the next check must inspect only the files actually loaded through `/etc/mosquitto/mosquitto.conf` plus active `conf.d/*.conf` files, then perform a harmless unauthenticated TLS connection test against `:8884` to establish effective behavior.

The database/Valkey dependency listeners remained present on both nodes during this diagnostic: PgBouncer `:6432`, PostgreSQL-primary HAProxy `:15432`, and Valkey writable-primary HAProxy `:16379`.

Phase 9.3 remains **PARTIAL / BLOCKED FOR DIAGNOSTIC FOLLOW-UP**. The next read-only continuation is:

1. identify the privileged PID/process/systemd owner of `:8080` on ulc-01 and ulc-02;
2. inspect only the active Mosquitto configuration files and prove the effective unauthenticated TLS behavior on `:8884` without publishing application data;
3. verify the existing `chirpstack` database login path and Valkey `role:master` routing from each application-host context;
4. after those gates pass, decide whether ChirpStack keeps `:8080` or uses a different private HTTP port, and commission the missing ulc-02 MQTT HAProxy route plus ChirpStack-specific MQTT identity/ACL;
5. only then continue to section 9.4 image pinning/start preparation.

No ChirpStack image pull, configuration directory, secret generation, migration, service restart, or topology change is authorized at this checkpoint.

### 9.3.3 Phase 9.3B probe harness correction - 2026-08-25

The first Phase 9.3B continuation did **not** produce evidence of an SSH, MQTT, or TLS service failure. Both observed failures happened before the intended checks could reach the target service.

The `:8080` owner command was launched from the unprivileged `opsadmin` shell on ulc-03 while pointing SSH at `/root/.ssh/cloud-deployment-phase8`. That private key is root-readable only, so OpenSSH reported `Identity file ... not accessible: Permission denied` and then `Permission denied (publickey)` for ulc-01 and ulc-02. This is a local key-permission/harness error on ulc-03, not evidence that either application node rejected the already-proven deployment identity. The corrected owner probe must run from the existing root shell (`sudo bash`) that can read the Phase 8 deployment key.

The unauthenticated MQTT probe also stopped before connecting to Mosquitto. `mosquitto_sub` reported `Problem setting TLS options: File not found` because it ran as unprivileged `opsadmin` while referencing `/etc/lorawan-pki/mqtt/ca.crt`; that commissioned PKI path is not guaranteed to be readable/traversable by the operator account. Since no MQTT `CONNECT`/`CONNACK` exchange was reached, the result says nothing about anonymous authorization. The corrected probe must either run the client under remote sudo or first use a root-readable CA path, while still omitting username/password/client certificate and publishing no application data.

The active Mosquitto configuration evidence itself remains valid and identical on both nodes:

```text
/etc/mosquitto/mosquitto.conf -> include_dir /etc/mosquitto/conf.d
active conf.d/tls.conf -> listener 8884
cafile /etc/lorawan-pki/mqtt/ca.crt
certfile /etc/lorawan-pki/mqtt/server.crt
private keyfile configured
tls_version tlsv1.3
require_certificate false
no active password_file/acl_file/plugin/allow_anonymous directive observed
```

All PgBouncer `:6432`, PostgreSQL HAProxy `:15432`, Valkey HAProxy `:16379`, and Mosquitto `:8884` listeners remained present during the failed probe. Phase 9.3 therefore remains **PARTIAL / BLOCKED FOR CORRECTED READ-ONLY PROOF**, with no infrastructure regression established.

### 9.3.4 Phase 9.3C corrected proof - 2026-08-25

The corrected privileged owner check finally identified the `:8080` listener on both application nodes. On ulc-01 the listener belongs to `postgres` PID `40033`; on ulc-02 it belongs to `postgres` PID `215126`. The HTTP response is JSON and exposes keys including `postgresql`, `databases`, `processes`, `system_stats`, `disk_stats`, and `hostname`. This is consistent with the existing Spilo/Patroni PostgreSQL service stack rather than ChirpStack. Therefore port `8080` is **reserved by the commissioned database HA stack and must not be reused or stopped for ChirpStack**. Phase 9 will assign ChirpStack a different private host port after the pinned image confirms its container listen behavior.

The corrected MQTT client did reach TLS negotiation, but still did not reach MQTT authorization. It connected to `127.0.0.1:8884`, while the commissioned broker certificate identity is `mqtt.internal.lorawan.com`; hostname verification therefore failed before an MQTT `CONNACK` could be observed. Both nodes returned `mosquitto_sub_exit=14` with `host name verification failed`. This is expected certificate verification behavior and is not an MQTT-authentication failure.

The final read-only MQTT authorization proof must therefore preserve hostname verification while forcing the service name to the local broker IP, for example by temporarily supplying a process-local resolver mapping or connecting to `mqtt.internal.lorawan.com` after a safe local hosts override in a disposable client context. Do not disable hostname verification. The goal is to observe whether an unauthenticated client receives an accepted `CONNACK` or an authorization rejection.

At this checkpoint:

```text
port 8080 owner: known and reserved by PostgreSQL/Spilo stack on both nodes
ulc-01 MQTT HAProxy :8883: present
ulc-02 MQTT HAProxy :8883: absent
Mosquitto TLS backend :8884: healthy on both nodes
Mosquitto effective anonymous authorization: still unresolved
```

Phase 9.3 remains **PARTIAL**, but only the effective MQTT authorization proof and explicit database/Valkey application-path checks remain before dependency closure. Do not pull or start ChirpStack yet.

### 9.3.5 Phase 9.3D TLS proof - 2026-08-25

Phase 9.3D proved the broker TLS identity cleanly on both Mosquitto backends. Direct TLS connections to `10.104.0.2:8884` and `10.104.0.4:8884` using SNI/hostname `mqtt.internal.lorawan.com` negotiated TLS 1.3 with `TLS_AES_256_GCM_SHA384`, validated the internal CA, and returned `Verify return code: 0 (ok)`. The certificate subject is `CN = mqtt.internal.lorawan.com` and its SAN set includes the commissioned service identity.

The `mosquitto_sub` runs returned only `exit=124` from the outer timeout and did not print a broker CONNACK or authorization error. That result is not sufficient to classify anonymous MQTT as allowed or denied: it proves neither authentication success nor rejection. The separate `getent hosts mqtt.internal.lorawan.com` check on ulc-03 returned no mapping, so the next proof must not depend on host DNS or edit `/etc/hosts`.

The remaining authorization proof will therefore use a direct TLS socket to each broker IP while setting the TLS `server_hostname` to `mqtt.internal.lorawan.com`, then send one minimal MQTT 3.1.1 CONNECT packet with no username, password, or client certificate and inspect only the returned CONNACK code. This is read-only from the application's perspective: it creates no subscription, publishes no data, changes no broker state/configuration, and requires no DNS mutation.

Current Phase 9.3 state:

```text
:8080 owner on ulc-01/02 = existing Spilo/PostgreSQL host process; preserve it
Mosquitto TLS identity/CA/hostname verification = PASS on both brokers
ulc-01 local HAProxy MQTT :8883 = present
ulc-02 local HAProxy MQTT :8883 = absent
Mosquitto anonymous authorization = still unclassified; final CONNACK proof required
```

Do not start or pull ChirpStack until the CONNACK proof plus the remaining database/Valkey client-path check are recorded.

### 9.3.6 Phase 9.3E direct MQTT CONNACK proof - 2026-08-25

The final direct MQTT authorization proof passed on both brokers. A minimal MQTT 3.1.1 CONNECT packet with no username, password, or client certificate was sent over a TLS socket that connected directly to each broker IP while still verifying the server as `mqtt.internal.lorawan.com`.

Observed on both ulc-01 and ulc-02:

```text
TLS version: TLSv1.3
cipher: TLS_AES_256_GCM_SHA384
verified hostname: mqtt.internal.lorawan.com
raw CONNACK: 20 02 00 05
CONNACK return code: 5
meaning: Not Authorized
result: ANONYMOUS_MQTT_DENIED
```

This conclusively proves that the commissioned Mosquitto listeners reject anonymous MQTT clients while preserving successful TLS certificate and hostname verification. The result is stronger than the earlier configuration-only inventory because it proves the effective broker behavior on both live nodes.

The remaining Phase 9.3 closure items are now limited to the application dependency paths:

1. prove the existing `chirpstack` PostgreSQL role can connect through each local PgBouncer `:6432` endpoint using verify-full TLS without printing its password;
2. prove each local Valkey HAProxy `:16379` endpoint routes to the current writable master using the existing protected Valkey credential;
3. keep `:8080` reserved for the existing Spilo/PostgreSQL process and choose a different private host port for ChirpStack;
4. retain the known MQTT routing gap: ulc-01 has local HAProxy `:8883`, ulc-02 does not. That route must be commissioned before the two-node ChirpStack deployment is called HA.

Phase 9.3 is **MQTT/TLS/AUTH COMPLETE; DATABASE/VALKEY APPLICATION-PATH CHECKS STILL REQUIRED**. Do not pull or start ChirpStack until those two read-only checks pass.

### 9.3.7 Phase 9.3F credential-discovery checkpoint - 2026-08-25

The Phase 9.3F application-path proof confirmed that the required local listeners remain present on both application nodes, but it did **not** reach either authenticated client path because the credential-discovery guesses did not match the actual protected secret locations.

Observed on both ulc-01 and ulc-02:

```text
PgBouncer :6432 = present
Valkey HAProxy :16379 = present
pgbouncer.internal.lorawan.com = no host mapping returned in the operator shell
DB_SECRET_STATUS = NOT_FOUND
VALKEY_SECRET_STATUS = NOT_FOUND
```

This is a credential-location/discovery issue, not evidence of PostgreSQL, PgBouncer, Valkey, HAProxy, or authentication failure. No login attempt was made because no secret value was loaded. Do not create replacement credentials merely because the filename guesses missed the commissioned files.

Before retrying the application-path proof, inventory only secret **filenames, directories, ownership, permissions, sizes, and modification times** on ulc-01, ulc-02, and ulc-03. Do not print file contents. Prefer existing commissioned credentials over generating new ones.

Phase 9.3 remains **PARTIAL ONLY FOR APPLICATION-PATH PROOF**. MQTT TLS and anonymous-denial checks are complete. The remaining gate is to locate the existing ChirpStack database and Valkey application credentials safely, then prove:

```text
chirpstack -> local PgBouncer :6432 -> current writable PostgreSQL primary
application Valkey credential -> local HAProxy :16379 -> current writable Valkey master
```

Only after those two paths pass should section 9.4 begin.

### 9.3.8 Phase 9.3G partial secret-inventory checkpoint - 2026-08-25

The first Phase 9.3G secret-location inventory returned valid metadata for ulc-01, then stopped before the PgBouncer reference check, ulc-02, and ulc-03. This was a shell-harness issue, not a host/service failure: the `find` command was supplied candidate starting directories that do not all exist, and under `set -e` a non-zero `find` status terminated the remote block even though stderr was redirected.

Valid ulc-01 evidence captured before that stop includes:

```text
/etc/lorawan-cloud exists
/etc/pgbouncer exists
/etc/haproxy/secrets exists
/etc/valkey exists
/etc/pgbouncer/userlist.txt = live protected PgBouncer auth file candidate
/etc/haproxy/secrets/valkey-health.env = dedicated HAProxy health credential only; not an application Valkey credential
/etc/valkey/valkey.conf = active Valkey configuration
```

Do not reuse `valkey-health.env` for ChirpStack: Phase 8 deliberately created that identity as least-privilege HAProxy health-check access. Likewise, do not assume the PgBouncer SCRAM verifier stored in `userlist.txt` is the original plaintext ChirpStack password required by an application client.

The corrected inventory must first build a list containing only directories that actually exist, then run `find` over that list. It must continue through ulc-01, ulc-02, and ulc-03 and still print metadata only, never file contents.

Phase 9.3 remains **PARTIAL ONLY FOR APPLICATION-PATH PROOF**. No new credentials are authorized yet.

### 9.3.9 Phase 9.3H corrected secret inventory - 2026-08-25

The corrected secret-safe inventory completed across ulc-01, ulc-02, and ulc-03 without printing credential values.

PgBouncer evidence is consistent on ulc-01 and ulc-02:

```text
auth_type = scram-sha-256
auth_file = /etc/pgbouncer/userlist.txt
user=chirpstack
user=fabric_adapter
user=telemetry_reader
user=telemetry_writer
```

The protected PgBouncer file therefore proves that the commissioned `chirpstack` SCRAM verifier is present, but it is not a plaintext application password and must not be treated as one. Phase 6 records confirm that runtime-role authentication was intentionally performed with the operator entering the ChirpStack password at a hidden `/dev/tty` prompt; the repository does not record a plaintext server-side copy of that password.

Valkey evidence is also now precise. ulc-03 retains the root-only commissioned application credential at:

```text
/root/lorawan-secrets/valkey-auth.txt
```

Separate root-only files exist for Sentinel authentication and the HAProxy health identity. Keep those identities separate. In particular, do not use `/root/lorawan-secrets/valkey-haproxy-health.txt` or `/etc/haproxy/secrets/valkey-health.env` as the ChirpStack application credential.

The final Phase 9.3 application-path proof must therefore use two different secret-handling methods:

1. prompt the operator for the already-commissioned ChirpStack PostgreSQL password via `/dev/tty` without echoing it, then test the local PgBouncer path on ulc-01 and ulc-02;
2. read `/root/lorawan-secrets/valkey-auth.txt` only inside the root shell on ulc-03 and pass it transiently to the Valkey client without printing it, then test each local HAProxy `:16379` endpoint.

No replacement PostgreSQL password or Valkey credential is needed at this checkpoint.

### 9.3.10 Phase 9.3I PostgreSQL application-path proof - 2026-08-25

The final PostgreSQL application-path proof passed through both commissioned PgBouncer endpoints using the existing `chirpstack` SCRAM credential. The host-side `psql` wrapper on ulc-01/02 was not usable because no versioned PostgreSQL client package is installed there, so the successful proof used the existing `psql` client inside the ulc-03 Spilo container while targeting each application node's private PgBouncer endpoint directly.

Observed results:

```text
10.104.0.2:6432 -> chirpstack|chirpstack|false|10.104.0.2
10.104.0.4:6432 -> chirpstack|chirpstack|false|10.104.0.2
```

This proves both local PgBouncer endpoints authenticated the intended application identity, selected the `chirpstack` database, and converged on the same writable Patroni primary. `pg_is_in_recovery() = false` on the returned server confirms the downstream HAProxy primary route is not sending the application to a replica. The locale warnings emitted by the Spilo client environment are a separate non-blocking hygiene issue.

PostgreSQL application path is therefore **PASS**:

```text
ulc-01 PgBouncer :6432 -> local HAProxy :15432 -> Patroni primary 10.104.0.2
ulc-02 PgBouncer :6432 -> local HAProxy :15432 -> Patroni primary 10.104.0.2
```

### 9.3.11 Phase 9.3J Valkey application-path proof - 2026-08-25

The final Valkey application-path proof passed through both commissioned writable-primary HAProxy endpoints using the existing root-only application credential from `/root/lorawan-secrets/valkey-auth.txt` on ulc-03. The credential was read only inside the privileged shell and was not printed.

Observed results:

```text
10.104.0.2:16379 -> routed_role=master -> PASS
10.104.0.4:16379 -> routed_role=master -> PASS
```

This proves both application-node HAProxy endpoints independently select the current Sentinel-elected writable Valkey primary and do not route ChirpStack-class traffic to a replica.

Phase 9.3 is therefore **COMPLETE / PASS**. The pre-deployment boundary now proves:

```text
ChirpStack not yet installed or started
PostgreSQL path through both PgBouncer endpoints -> writable Patroni primary: PASS
Valkey path through both :16379 endpoints -> writable master: PASS
Mosquitto TLS 1.3 / CA / hostname verification on both brokers: PASS
anonymous MQTT -> denied on both brokers with CONNACK 0x05: PASS
port 8080 -> occupied by existing Spilo/PostgreSQL service and reserved
ulc-01 MQTT HAProxy :8883 -> present
ulc-02 MQTT HAProxy :8883 -> still absent and remains a Phase 9 dependency before two-node HA can be claimed
```

Proceed to Phase 9.4 image pinning and schema inspection. Do not start ChirpStack yet.

## 9.4 Pin and inspect the exact ChirpStack image

After the preflight, choose the exact supported ChirpStack v4 image and record both tag and immutable digest. Do not use `latest`.

Before creating configuration, inspect commands supported by that exact image:

```bash
docker image inspect <PINNED_CHIRPSTACK_IMAGE>
docker run --rm <PINNED_CHIRPSTACK_IMAGE> --version
docker run --rm <PINNED_CHIRPSTACK_IMAGE> --help
```

If the image supports exporting a configuration template, generate it from the image and save a sanitized copy for review. Do not assume the historical `configfile` subcommand exists until `--help` confirms it.

Record:

```text
image reference:
immutable digest:
reported ChirpStack version:
configuration-template command:
database migration behavior:
Redis/Valkey URL/TLS fields:
MQTT authentication/TLS fields:
region directory / include behavior:
runtime UID/GID if non-root:
```

The exact image is authoritative for configuration field names. Do not copy old TOML keys merely because they appear in this manual.

### 9.4.1 Image pinning checkpoint - 2026-08-25

The first Phase 9.4 inspection pinned the ChirpStack release successfully without starting any persistent ChirpStack container.

Observed image identity:

```text
release tag: chirpstack/chirpstack:4.19.1
reported version: chirpstack 4.19.1
platform: linux/amd64
runtime user: nobody:nogroup
entrypoint: /usr/bin/chirpstack
immutable image ID: sha256:9e0105f1dd733d3d3caa77aa7cfdbf817417fab8a093dd89639a2cd899ab9efe
repo digest: chirpstack/chirpstack@sha256:9e0105f1dd733d3d3caa77aa7cfdbf817417fab8a093dd89639a2cd899ab9efe
running ChirpStack containers after inspection: none
```

Deployment must use the immutable digest above rather than the mutable tag alone.

The image CLI proves that `configfile` exists, but the first invocation returned exit code `2` because ChirpStack requires the global `--config <DIR>` argument even for this subcommand. This is a command-invocation issue, not an image or configuration failure. The corrected inspection must provide a disposable empty configuration directory, for example `--config /tmp/chirpstack-config`, then run `configfile`. The generated template must be inspected before creating production files.

Phase 9.4 is therefore **PARTIAL / IMAGE PIN PASS; CONFIGURATION SCHEMA INSPECTION NEXT**. Do not start ChirpStack yet.

### 9.4.2 Configuration schema checkpoint - 2026-08-25

The corrected `configfile` invocation against the exact pinned 4.19.1 digest succeeded using a disposable configuration directory. The generated template was 32,124 bytes / 1,052 lines, and no persistent ChirpStack container or database migration was started.

Authoritative 4.19.1 schema findings:

```text
PostgreSQL: [postgresql]
  dsn="postgresql://...?...sslmode=..."
  ca_cert=""
  max_open_connections=10
  connection_recycling_method="verified"

Valkey / Redis compatibility: [redis]
  servers=["redis://..."]
  TLS uses rediss://
  username/password may be embedded in the URL
  cluster=false for the commissioned non-Redis-Cluster HAProxy endpoint
  no Redis-specific ca_cert field in ChirpStack 4.19.1

ChirpStack MQTT integration: [integration.mqtt]
  server="tcp://127.0.0.1:1883/"
  username=""
  password=""
  client_id=""
  share_name="chirpstack"
  ca_cert=""
  tls_cert=""
  tls_key=""
  TLS transport uses the image's documented ssl:// scheme

API listener: [api]
  bind="0.0.0.0:8080"

Regions: [network]
  enabled_regions=[...]
  each enabled name must match a region configuration [[regions]] name
```

The image filesystem contained no packaged `/etc/chirpstack` files or AS923/regions files during the inspection. Therefore the deployment must provide the configuration directory and approved region configuration explicitly; do not assume usable region files are embedded in this image.

The internal ChirpStack API listener is confirmed as container `0.0.0.0:8080`. This does **not** change the host-port collision finding: host `:8080` is already owned by Spilo/PostgreSQL on ulc-01 and ulc-02. The eventual container publication must therefore use a different private host port while keeping container port `8080`.

Phase 9.4 is now **COMPLETE / PASS** for image identity and schema discovery. Before creating production configuration, the next checkpoint must establish the approved AS923 region source/content, choose and prove a free private host port on both application nodes, and resolve the remaining ulc-02 MQTT HAProxy-route asymmetry. Do not start ChirpStack yet.

## 9.5 Shared configuration directory

### 9.5.1 Deployment-slot preflight - 2026-08-25

The read-only Phase 9.5A deployment-slot preflight established the following live state before any ChirpStack directory, image, container, firewall rule, or service was created on the application nodes:

```text
ulc-01 10.104.0.2:18080 -> FREE
ulc-02 10.104.0.4:18080 -> FREE
ulc-01 host :8080 -> existing Spilo/PostgreSQL service
ulc-02 host :8080 -> existing Spilo/PostgreSQL service
ulc-01 MQTT HAProxy 10.104.0.2:8883 -> PRESENT
ulc-02 MQTT HAProxy 10.104.0.4:8883 -> ABSENT
/etc/lorawan-cloud/chirpstack -> absent on ulc-01 and ulc-02
persistent ChirpStack containers -> none
pinned ChirpStack image on ulc-01/02 -> absent
existing local AS923 / region TOML source on ulc-03 -> none found
```

Port `18080` is therefore the approved candidate private host publication port for ChirpStack, mapping to container `8080`, subject to a final pre-start listener check. Do not bind host `8080`.

The first controlled mutation after this checkpoint is **not** ChirpStack installation. Restore MQTT routing symmetry first by adding the same TLS-passthrough HAProxy frontend/backend design already validated on ulc-01 to ulc-02, changing only the frontend bind address to `10.104.0.4:8883`. Validate the HAProxy configuration before any reload, then verify the listener and both Mosquitto `:8884` backends after reload.

The region source is a separate checkpoint. No AS923 file was found locally, so do not invent or hand-author a region definition from memory. Obtain and review an authoritative ChirpStack 4.19.1-compatible AS923 region file before creating production configuration.

### 9.5.2 ulc-02 MQTT HAProxy syntax checkpoint - 2026-08-25

The missing ulc-02 MQTT HAProxy frontend/backend was added as a controlled Phase 9 change, with a timestamped backup created first:

```text
/etc/haproxy/haproxy.cfg.phase9-before-mqtt-20260825-060048
```

The new block is intentionally equivalent to the validated ulc-01 design except for the local frontend bind address:

```haproxy
frontend mqtt_tls
    bind 10.104.0.4:8883
    mode tcp
    option tcplog
    default_backend mqtt_brokers

backend mqtt_brokers
    mode tcp
    balance roundrobin
    option tcp-check

    server mqtt-ulc01 10.104.0.2:8884 check
    server mqtt-ulc02 10.104.0.4:8884 check
```

`haproxy -c -V -f /etc/haproxy/haproxy.cfg` returned `Configuration file is valid`. HAProxy was deliberately **not reloaded** in that step.

### 9.5.3 ulc-02 MQTT HAProxy activation checkpoint - 2026-08-25

The controlled reload on ulc-02 passed completely. Runtime evidence:

```text
haproxy service -> active / enabled
10.104.0.4:8883 -> LISTEN owned by haproxy
10.104.0.2:8884 -> TCP reachable
10.104.0.4:8884 -> TCP reachable
TLS verification through 10.104.0.4:8883 -> OK
verified peername -> mqtt.internal.lorawan.com
TLS version -> TLSv1.3
unauthenticated MQTT CONNECT -> CONNACK 0x05 Not Authorized
existing :6432 / :15432 / :16379 listeners -> still present
```

This closes the Phase 9 MQTT routing asymmetry. Both application nodes now expose equivalent local TLS-passthrough MQTT frontends on their own private `:8883` addresses while retaining both Mosquitto `:8884` backends. End-to-end TLS terminates only at Mosquitto and anonymous MQTT remains denied through the new ulc-02 route.

The remaining preconfiguration blocker is the authoritative plain-AS923 region file. The frozen deployment identity remains `as923` / plain `AS923`; do not silently substitute `as923_2`, `as923_3`, or `as923_4`. Obtain the region file from an authoritative ChirpStack source compatible with the pinned 4.19.1 release, review its `id`, `common_name`, `topic_prefix`, channels, RX2 parameters, and MQTT backend fields, then preserve its source and checksum before creating production configuration.

### 9.5.4 authoritative AS923 source checkpoint - 2026-08-25

The first Phase 9.5C source inspection successfully fetched the ChirpStack 4.19.1 source and located the plain-AS923 region file before the inspection harness stopped at its first identity grep.

Verified evidence:

```text
source commit: 1ad3e1177c39cc1c566b879898ccf2b96d231260
exact tag reported by repository: api/go/v4.19.1
region path: chirpstack/configuration/region_as923.toml
region SHA-256: ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654
```

The detached-HEAD message is expected for a shallow exact-tag checkout and is not an error. The script then stopped at STEP 5 because its grep required `id`, `description`, and `common_name` to begin at column 1. The region TOML uses nested/indented fields, so grep returned no match and `set -e` terminated the harness. This does not invalidate the fetched source revision, path, or hash.

Phase 9.5C is therefore **PARTIAL / SOURCE AND HASH PASS; REGION CONTENT INSPECTION NEXT**. Re-run content inspection with whitespace-tolerant matching and non-fatal grep behavior. Do not create the production region file yet.

### 9.5.5 authoritative AS923 content checkpoint - 2026-08-25

The corrected content inspection passed and confirms that the exact ChirpStack 4.19.1 source file matches the deployment's frozen plain-AS923 identity.

Verified identity and radio parameters:

```text
source commit: 1ad3e1177c39cc1c566b879898ccf2b96d231260
repository tag reported: api/go/v4.19.1
region path: chirpstack/configuration/region_as923.toml
region SHA-256: ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654
id: as923
description: AS923
common_name: AS923
MQTT topic_prefix: as923
MQTT share_name: chirpstack
uplink channels: 923200000 Hz and 923400000 Hz, 125 kHz, SF7-SF12
rx1_delay: 1
rx1_dr_offset: 0
rx2_dr: 2
rx2_frequency: 923200000 Hz
min_dr: 0
max_dr: 5
```

The authoritative file's default MQTT server is `tcp://localhost:1883`; this value is only an upstream template default and must be replaced in the production copy with the commissioned local HAProxy TLS route on each application node. Do not change the region identity, channel plan, or RX parameters unless a separately validated regional requirement is introduced.

The plain-AS923 provenance blocker is now **CLOSED / PASS**. Production state remains unchanged: no region file has yet been installed under `/etc/lorawan-cloud/chirpstack` and no ChirpStack container has been started.

The next controlled step may now create the shared configuration directory skeleton on ulc-01 and ulc-02 and install a byte-identical copy of this vetted region file, while still leaving the main ChirpStack config, secrets, image pull, and service start for later checkpoints.

### 9.5.6 vetted AS923 install checkpoint - 2026-08-25

The corrected transfer procedure installed the vetted region file on both application nodes using an unprivileged temporary `scp` path followed by a separate privileged install. Per-node evidence is complete and valid:

```text
ulc-01 installed SHA-256: ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654
ulc-02 installed SHA-256: ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654
installed path: /etc/lorawan-cloud/chirpstack/regions/region_as923.toml
ownership/mode: root:root 0644
id: as923
common_name: AS923
topic_prefix: as923
chirpstack.toml: absent
chirpstack.env: absent
ChirpStack container: absent
```

The pasted execution output ended after the ulc-02 per-node checks and did not include the script's final cross-node summary block or `PHASE 9.5D-R PASS` line. Because the individually reported hashes are already identical and equal to the vetted source hash, the installation itself is **PER-NODE PASS**; however, run one final compact cross-node verification before advancing so the manual also has a clean completed harness result.

### 9.5.7 final cross-node AS923 hash verification - 2026-08-25

The compact cross-node verification completed successfully and confirmed that both application nodes retain the exact vetted region file hash:

```text
10.104.0.2 = ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654
10.104.0.4 = ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654
```

This closes the AS923 file-install boundary completely. The region file is byte-identical across both nodes and matches the authoritative ChirpStack 4.19.1 source hash already recorded above. No main ChirpStack configuration, secret file, image, or container was introduced by this verification.

The next checkpoint is main configuration construction, but the MQTT workload-authentication boundary must be isolated first. The production gateway path is certificate-oriented, while ChirpStack requires a distinct service identity. Do not place a ChirpStack password/ACL policy directly onto the existing gateway-facing broker listener. First commission a dedicated ChirpStack MQTT backend listener on both brokers and a redundant local HAProxy route, then build `chirpstack.toml` from the verified 4.19.1 schema. Keep shared non-secret TOML byte-identical across both nodes where possible; use node-local values only where they genuinely differ.

### 9.5.8 dedicated ChirpStack MQTT path preflight - 2026-08-25

The read-only preflight confirmed that the proposed dedicated workload ports and files are currently unused on both application nodes:

```text
ulc-01 Mosquitto 8885 -> FREE
ulc-02 Mosquitto 8885 -> FREE
ulc-01 HAProxy 18883 -> FREE
ulc-02 HAProxy 18883 -> FREE
/etc/mosquitto/chirpstack.passwd -> absent on both nodes
/etc/mosquitto/chirpstack.acl -> absent on both nodes
/etc/mosquitto/conf.d/chirpstack.conf -> absent on both nodes
Mosquitto version -> 2.0.18 on both nodes
existing 8883 / 8884 listeners -> unchanged
existing 6432 / 15432 / 16379 listeners -> unchanged
```

This reserves `:8885` as the dedicated TLS Mosquitto backend listener for ChirpStack workload authentication and `:18883` as the candidate local HAProxy frontend on each application node. The existing gateway-facing MQTT path remains separate on HAProxy `:8883` -> Mosquitto `:8884`.

The next mutation must be limited to Mosquitto. Create one shared ChirpStack service credential, a least-privilege ACL allowing the required `as923/gateway/#` and `application/#` operations, and a TLS listener on `:8885`; validate configuration before reload/restart. Do not modify HAProxy or create `chirpstack.toml` in the same step.

### 9.5.9 ChirpStack MQTT auth/ACL configuration checkpoint - 2026-08-25

The Phase 9.5F1 run created the shared root-only ChirpStack MQTT secret on ulc-03 and successfully installed the following on ulc-01 before the pasted output stopped:

```text
/etc/mosquitto/chirpstack.passwd -> root:mosquitto 0640, hashed password file
/etc/mosquitto/chirpstack.acl -> root:mosquitto 0640
/etc/mosquitto/conf.d/00-auth-scope.conf -> per_listener_settings true
/etc/mosquitto/conf.d/chirpstack.conf -> dedicated TLS listener 10.104.0.2:8885
existing /etc/mosquitto/conf.d/tls.conf -> explicit allow_anonymous false added for :8884
backup stamp -> 20260825-064756
```

The configured ChirpStack ACL is directional: read gateway event/state topics, write gateway command topics, write application event topics, and read application command topics. The dedicated listener uses the commissioned MQTT CA/server certificate/key, TLS 1.3, `allow_anonymous false`, the ChirpStack password file, and the ChirpStack ACL file.

The disposable validation process on ulc-01 returned exit code `124`, which is the expected timeout code when the test broker remains running until intentionally terminated. However, the pasted evidence ended immediately after the config-file load lines and did not include the required socket-open assertions, `MOSQUITTO_CONFIG_VALIDATION=PASS`, live `:8885` absence check, ulc-02 configuration evidence, or the final Phase 9.5F1 completion line.

The compact completion check then proved the split state precisely. On ulc-01, all four ChirpStack MQTT files exist with the expected metadata, `per_listener_settings true` and explicit `allow_anonymous false` are present, disposable Mosquitto listeners `127.0.0.1:28884` and `127.0.0.1:28885` opened successfully, `DISPOSABLE_VALIDATION=PASS`, the live Mosquitto service remained active, and live `:8885` remained inactive. On ulc-02, none of the four ChirpStack MQTT files exists and disposable validation was correctly skipped; its existing `:8883`/`:8884` service state remains unchanged.

Therefore Phase 9.5F1 is **PARTIAL / ULC-01 COMPLETE PASS; ULC-02 NOT YET CONFIGURED**. Do not restart Mosquitto yet. The next mutation must target ulc-02 only, reuse the already-created root-only ChirpStack MQTT secret from ulc-03, install the same hashed password/ACL/auth-scope policy with node-local bind `10.104.0.4:8885`, and repeat the disposable `28884/28885` validation before any live broker restart.

### 9.5.10 ulc-02 ChirpStack MQTT configuration checkpoint - 2026-08-25

The ulc-02-only completion step passed. It reused the existing root-only ChirpStack MQTT secret from ulc-03, installed a hashed `chirpstack` password file plus the same directional ACL policy, enabled per-listener authentication scope, made `allow_anonymous false` explicit on the existing `:8884` listener, and created the node-local dedicated ChirpStack listener at `10.104.0.4:8885`.

Verified evidence:

```text
ulc-02 backup stamp: 20260825-065231
/etc/mosquitto/conf.d/00-auth-scope.conf -> root:root 0644
/etc/mosquitto/conf.d/chirpstack.conf -> root:root 0644
/etc/mosquitto/chirpstack.passwd -> root:mosquitto 0640
/etc/mosquitto/chirpstack.acl -> root:mosquitto 0640
live :8885 before restart -> inactive
disposable 127.0.0.1:28884 -> PASS
disposable 127.0.0.1:28885 -> PASS
DISPOSABLE_VALIDATION -> PASS
live Mosquitto service -> active
live :8885 after validation -> inactive
```

Both broker nodes are now configuration-ready for the dedicated ChirpStack MQTT listener, but neither live broker has yet loaded `:8885`. Phase 9.5F configuration-file preparation is therefore **COMPLETE / PASS**. Activate one live broker at a time, beginning with ulc-01. After each restart, verify that the existing gateway-facing `:8884` listener still serves verified TLS and rejects unauthenticated MQTT, while the new `:8885` listener verifies TLS, accepts the commissioned ChirpStack username/password on allowed topics, and rejects both anonymous access and an intentionally denied topic. Do not restart both brokers together.

### 9.5.11 ulc-01 Mosquitto canary activation checkpoint - 2026-08-25

The first live canary activation on ulc-01 partially passed before the pasted output stopped. The Mosquitto service restarted cleanly, remained enabled/active, and loaded both the existing gateway-facing listener and the new ChirpStack workload listener:

```text
service state -> active / enabled
0.0.0.0:8884 -> LISTEN
[::]:8884 -> LISTEN
10.104.0.2:8885 -> LISTEN
recent Mosquitto errors -> none
legacy :8884 TLS Verification -> OK
legacy :8884 verified peername -> mqtt.internal.lorawan.com
legacy :8884 verify return code -> 0 (ok)
```

This proves that the new `:8885` listener did not prevent the existing `:8884` TLS endpoint from returning after restart. However, the pasted evidence stopped before the dedicated `:8885` username/password authentication test, allowed-topic ACL test, anonymous-denial test, forbidden-topic ACL test, and the final proof that ulc-02 remained untouched.

Phase 9.5G1 is therefore **PARTIAL / ULC-01 LIVE LISTENER + LEGACY TLS PASS; WORKLOAD AUTH/ACL PROOF STILL REQUIRED**. Do not restart ulc-01 again. Continue with a read-only/runtime-only policy test against the already-live `10.104.0.2:8885`, then confirm ulc-02 remains active on `:8884` with its `:8885` listener still inactive before advancing.

The continuation test then proved TLS 1.3, successful `chirpstack` username/password authentication (`CONNACK 0x00`), successful subscription to the allowed gateway-event hierarchy, and anonymous denial (`CONNACK 0x05`). The intentionally forbidden subscription returned a successful SUBACK instead of `0x80`:

```text
authenticated_connack = 20020000
MQTT_AUTHENTICATION = PASS
allowed_suback = 9003000100
ACL_ALLOWED_SUBSCRIBE = PASS
anonymous_connack = 20020005
ANONYMOUS_DENIAL = PASS
denied_suback = 9003000200
```

Do **not** interpret that SUBACK alone as proof that the ACL allowed forbidden message delivery. With Mosquitto, subscription acknowledgement and ACL-enforced message delivery must not be conflated in this test. The prior assertion that a forbidden subscription must return SUBACK failure `0x80` was too strict and produced a test-harness false negative. Keep the ACL unchanged until runtime delivery behavior is tested.

The runtime delivery proof then completed successfully without changing the ACL or restarting Mosquitto again. The live ulc-01 `:8885` listener accepted the commissioned `chirpstack` credential over verified TLS 1.3, allowed the configured gateway-event subscription, allowed application-event publication, denied application-event read by proving that no message was delivered to the subscribed ChirpStack client, and allowed gateway-command publication. The previously successful SUBACK on the write-only application-event topic therefore represented subscription acknowledgement only; it did not bypass delivery authorization.

Verified evidence:

```text
tls_version = TLSv1.3
MQTT_AUTHENTICATION = PASS
allowed_gateway_suback = 9003000100
ACL_ALLOWED_GATEWAY_READ = PASS
write_only_topic_suback = 9003000200
allowed_event_publish_puback = 40020003
ACL_ALLOWED_APPLICATION_WRITE = PASS
ACL_DENIED_APPLICATION_READ = PASS
gateway_command_puback = 40020004
ACL_ALLOWED_GATEWAY_COMMAND_WRITE = PASS
ULC01_CHIRPSTACK_MQTT_ACL = PASS
ulc-02 Mosquitto = active
ulc-02 live :8885 = NOT_ACTIVE
```

This closes the ulc-01 live canary as **COMPLETE / PASS**. Do not modify its ACL based on SUBACK behavior. The next live mutation is ulc-02 only: restart Mosquitto there, prove the existing gateway-facing `:8884` listener still verifies correctly, and repeat the same `:8885` authentication, anonymous-denial, allowed-operation, and delivery-enforcement checks before commissioning the redundant HAProxy `:18883` frontend.

### 9.5.12 ulc-02 Mosquitto live activation checkpoint - 2026-08-25

The ulc-02 live activation has partially passed. Before the restart, the ulc-01 canary remained healthy with both `:8884` and `10.104.0.2:8885` listening. Mosquitto was then restarted on ulc-02 only and returned active/enabled without recent error/fatal/failed log entries.

Verified ulc-02 evidence:

```text
service state -> active / enabled
0.0.0.0:8884 -> LISTEN
[::]:8884 -> LISTEN
10.104.0.4:8885 -> LISTEN
recent Mosquitto errors -> none
legacy :8884 TLS Verification -> OK
legacy :8884 verified peername -> mqtt.internal.lorawan.com
legacy :8884 verify return code -> 0 (ok)
ulc-01 canary listeners -> PASS throughout
```

This proves the second broker loaded the dedicated ChirpStack listener without regressing the existing gateway-facing TLS listener. However, the pasted output stopped before the ulc-02 `:8885` username/password authentication, anonymous-denial, allowed gateway read, application write/read-denial delivery test, allowed gateway command write, and final two-broker `:8885` status summary.

Phase 9.5G2 is now **COMPLETE / PASS**. The continuation proof on ulc-02 verified TLS 1.3 and hostname validation on `10.104.0.4:8885`, accepted the commissioned `chirpstack` credential, rejected anonymous MQTT with CONNACK `0x05`, allowed gateway-event reads, allowed application-event writes, blocked application-event read delivery, and allowed gateway-command writes. Final runtime state also confirmed both ulc-01 and ulc-02 Mosquitto services active with their node-local `:8885` listeners live.

Verified continuation evidence:

```text
ULC02 MQTT_AUTHENTICATION = PASS
ULC02 ANONYMOUS_DENIAL = PASS
ULC02 ACL_ALLOWED_GATEWAY_READ = PASS
ULC02 ACL_ALLOWED_APPLICATION_WRITE = PASS
ULC02 ACL_DENIED_APPLICATION_READ = PASS
ULC02 ACL_ALLOWED_GATEWAY_COMMAND_WRITE = PASS
ULC02_CHIRPSTACK_MQTT_ACL = PASS
ulc-01 Mosquitto = active, :8885 ACTIVE
ulc-02 Mosquitto = active, :8885 ACTIVE
```

Both dedicated ChirpStack Mosquitto backends are therefore commissioned. The next step is HAProxy workload routing: add a local TCP frontend on `10.104.0.2:18883` and `10.104.0.4:18883`, each balancing across `10.104.0.2:8885` and `10.104.0.4:8885`. Validate syntax first and do not reload HAProxy until both node-local configurations pass `haproxy -c`.

### 9.5.13 ChirpStack MQTT HAProxy configuration checkpoint - 2026-08-25

Phase 9.5H1 completed successfully on both application nodes. The dedicated ChirpStack MQTT HAProxy frontend/backend definitions were added to each node's existing `/etc/haproxy/haproxy.cfg` after confirming that local port `18883` was free and that both commissioned Mosquitto `:8885` backends were TCP-reachable.

Verified configuration:

```text
ulc-01 frontend chirpstack_mqtt_tls -> bind 10.104.0.2:18883
ulc-02 frontend chirpstack_mqtt_tls -> bind 10.104.0.4:18883
backend chirpstack_mqtt_brokers -> roundrobin TCP
backend server chirpstack-mqtt-ulc01 -> 10.104.0.2:8885 check
backend server chirpstack-mqtt-ulc02 -> 10.104.0.4:8885 check
ulc-01 haproxy -c -> PASS
ulc-02 haproxy -c -> PASS
ulc-01 live :18883 before reload -> inactive
ulc-02 live :18883 before reload -> inactive
```

Rollback backups created immediately before this mutation:

```text
ulc-01 /etc/haproxy/haproxy.cfg.phase9-before-chirpstack-mqtt-20260825-071511
ulc-02 /etc/haproxy/haproxy.cfg.phase9-before-chirpstack-mqtt-20260825-071512
```

Existing PgBouncer/PostgreSQL, Valkey, and gateway-facing MQTT HAProxy listeners remained present during validation. HAProxy was not reloaded in Phase 9.5H1, so the new frontend remained configuration-only at this checkpoint.

Phase 9.5H1 is **COMPLETE / PASS**. Activate HAProxy one node at a time. After each reload, prove the node-local `:18883` listener is active and that TLS still terminates at Mosquitto with verified peername `mqtt.internal.lorawan.com`; then prove the commissioned ChirpStack username/password authenticates through the frontend. Do not build `chirpstack.toml` until both redundant `:18883` paths pass.

### 9.5.14 ChirpStack MQTT HAProxy activation checkpoint - 2026-08-25

The first Phase 9.5H2 activation completed successfully on ulc-01. HAProxy configuration validation passed, HAProxy reloaded cleanly, and `10.104.0.2:18883` became active while the existing PgBouncer/PostgreSQL, Valkey, and gateway-facing MQTT HAProxy listeners remained present.

Verified ulc-01 end-to-end evidence:

```text
haproxy_state = active
10.104.0.2:18883 = ACTIVE
TLS Verification = OK
verified peername = mqtt.internal.lorawan.com
TLS version = TLSv1.3
authenticated CONNACK = 20020000
HAPROXY_MQTT_AUTHENTICATION = PASS
anonymous CONNACK = 20020005
HAPROXY_ANONYMOUS_DENIAL = PASS
10.104.0.2:8885 backend TCP = PASS
10.104.0.4:8885 backend TCP = PASS
```

The harness then stopped on a shell-only status-print bug: `NAME_CHIRPSTACK_MQTT_HAPROXY` was referenced under `set -u` but was never defined. This failure happened **after** all ulc-01 runtime checks had passed and **before** the script reached the ulc-02 HAProxy reload. Therefore no rollback is required on ulc-01, and ulc-01 must not be reloaded again merely to rerun already-passed checks.

Phase 9.5H2 is currently **PARTIAL / ULC-01 COMPLETE PASS; ULC-02 LISTENER ACTIVATED, END-TO-END PROOF STILL REQUIRED**. The Phase 9.5H2-R continuation first reconfirmed ulc-01 HAProxy active with `10.104.0.2:18883` still listening and completed the final ulc-02 pre-reload syntax check with `Configuration file is valid`. A subsequent minimal no-heredoc recovery step then reloaded ulc-02 HAProxy successfully (`RELOAD_PASS`) and verified the service remained active/enabled with `10.104.0.4:18883` listening under HAProxy PID 507117.

Do not reload either HAProxy again merely to repeat already-passed checks. The remaining Phase 9.5H2 proof was completed read-only through the already-active ulc-02 frontend. TLS verification through `10.104.0.4:18883` returned `Verification: OK`, verified peername `mqtt.internal.lorawan.com`, and verify return code `0 (ok)`. An authenticated `chirpstack` MQTT subscription through the same HAProxy path reached the broker successfully and timed out only because the test topic had no message, which is the expected idle-subscription outcome for this probe. The final two-node state check showed both HAProxy services active with their node-local `:18883` listeners present.

Verified final Phase 9.5H evidence:

```text
ulc-01 10.104.0.2:18883 -> ACTIVE
ulc-02 10.104.0.4:18883 -> ACTIVE
ulc-01 HAProxy -> active
ulc-02 HAProxy -> active
ulc-02 TLS Verification -> OK
ulc-02 verified peername -> mqtt.internal.lorawan.com
ulc-02 MQTT authenticated subscription path -> PASS
```

Phase 9.5H is therefore **COMPLETE / PASS**. The redundant ChirpStack MQTT workload path is commissioned on both application nodes. The next phase may construct the production ChirpStack configuration and protected secret layout using local PgBouncer `:6432`, local Valkey HAProxy `:16379`, local ChirpStack MQTT HAProxy `:18883`, approved AS923, and host publication port `18080` -> container `8080`.

After the image schema is known and the routing/region prerequisites above are closed, create the same root-owned layout on ulc-01 and ulc-02:

```bash
sudo install -d -m 750 /etc/lorawan-cloud/chirpstack
sudo install -d -m 750 /etc/lorawan-cloud/chirpstack/regions
sudo install -m 600 /dev/null /etc/lorawan-cloud/chirpstack/chirpstack.env
```

Keep secrets out of Git. Give the container runtime user only the read permission required for mounted configuration and CA files. The active TOML and region files on both nodes must be byte-identical unless a field is explicitly node-specific, such as an MQTT client ID.

Before each start/restart, record hashes:

```bash
sudo find /etc/lorawan-cloud/chirpstack -type f -exec sha256sum {} +
```

Never print the environment file to collect evidence.

## 9.6 PostgreSQL connection

Each ChirpStack instance uses its **local PgBouncer**:

```text
ulc-01 container
  pgbouncer.internal.lorawan.com -> 10.104.0.2
  -> 10.104.0.2:6432

ulc-02 container
  pgbouncer.internal.lorawan.com -> 10.104.0.4
  -> 10.104.0.4:6432
```

The downstream path is:

```text
PgBouncer :6432
  -> postgres-ha.internal:15432
  -> local HAProxy
  -> current Patroni primary :5432
```

The DSN must retain hostname verification for `pgbouncer.internal.lorawan.com` and use the commissioned `chirpstack` SCRAM credential from protected secret storage. Mount the commissioned PgBouncer CA and use the exact PostgreSQL CA/config field supported by the pinned ChirpStack image.

Illustrative intent only:

```text
postgresql://chirpstack:<SECRET_REFERENCE>@pgbouncer.internal.lorawan.com:6432/chirpstack?sslmode=verify-full
```

Do not start ChirpStack until a TLS login to the same local PgBouncer endpoint succeeds from an equivalent container/network context.

## 9.7 Valkey connection - use the commissioned identity

The commissioned Valkey certificate identity is exactly:

```text
valkey.internal.lorawan.com
```

It is **not** `valkey-ha.internal.<DOMAIN>`.

Map the shared name to the local HAProxy address for each application container:

```text
ChirpStack-1: valkey.internal.lorawan.com -> 10.104.0.2
ChirpStack-2: valkey.internal.lorawan.com -> 10.104.0.4
```

Both then connect to:

```text
rediss://...@valkey.internal.lorawan.com:16379
```

HAProxy passes application TLS through to the currently writable Valkey node. The selected backend presents a certificate valid for `valkey.internal.lorawan.com`, so hostname verification remains stable across Sentinel promotion.

The pinned ChirpStack image must trust the commissioned internal Valkey CA. If its Redis/Valkey configuration supports an explicit CA field, use that. If it relies on the operating-system trust store, mount/import the CA by the method supported by that exact image and prove verification from inside a disposable container first.

**Never disable certificate verification to make this work.**

Before first ChirpStack start, prove from each application host/container context that its local `:16379` endpoint returns a writable `role:master` and that both endpoints survive the current dynamic topology without any hard-coded Valkey primary IP.

## 9.8 MQTT dependency closure before ChirpStack start

The completed gateway-facing MQTT infrastructure currently proves:

```text
certificate name: mqtt.internal.lorawan.com
HAProxy TLS passthrough: 10.104.0.2:8883 and 10.104.0.4:8883
Mosquitto backends: 10.104.0.2:8884 and 10.104.0.4:8884
broker failure detection/recovery: PASS
anonymous MQTT through either HAProxy route: denied
```

The routing asymmetry is closed. The remaining MQTT dependency is the **ChirpStack workload-authentication boundary**. Keep it separate from the gateway-facing broker listener: use dedicated Mosquitto `:8885` listeners with ChirpStack service authentication/ACLs, then expose those through redundant local HAProxy `:18883` frontends.

Before starting ChirpStack:

1. inspect `/etc/mosquitto/mosquitto.conf` and included files on ulc-01 and ulc-02;
2. record the effective `allow_anonymous`, `require_certificate`, password-file/plugin, ACL-file, listener, CA/certificate/key, and TLS-version directives without printing secrets;
3. inspect the pinned ChirpStack MQTT fields;
4. select one supported workload-authentication method and create a distinct ChirpStack identity;
5. grant only the gateway-backend and application-integration topics required by the exact active region/integration configuration;
6. prove an allowed publish/subscribe operation and a denied operation;
7. make the same reviewed policy available on both Mosquitto backends;
8. commission a second application-node MQTT route or another equally redundant private route before calling the two-node ChirpStack deployment HA.

Because the live broker certificate verifies as `mqtt.internal.lorawan.com`, any TLS-passthrough client route must use that hostname/SNI unless new certificates are deliberately issued. Do not configure `mqtt-ha.internal.<DOMAIN>` from the old target design; that name has not been proven in the commissioned certificate.

The exact ChirpStack MQTT TOML is intentionally **not** hard-coded here until the image preflight proves whether this version expects username/password, client certificate/key, or other fields.

## 9.9 Region configuration

Use the exact active region-file model from the pinned ChirpStack image. The current repository test/gateway baseline is intentionally frozen on **plain AS923 with MQTT region prefix `as923`**, not AS923-3. Phase 9 must preserve that existing end-to-end identity unless a deliberate, separately validated migration changes the gateway, sensors, MQTT topic prefix, ChirpStack region, and device profiles together. Copy the exact region ID and frequency plan from the pinned image and the already-approved gateway evidence; do not infer a sub-band from a display label.

Check:

```text
end-device region/frequency variant
RAK5146 hardware region
Gateway OS Concentratord channel plan
Gateway MQTT Forwarder topic prefix
ChirpStack gateway-backend MQTT topic prefix
ChirpStack enabled region ID
region frequencies and data rates
device-profile region / MAC settings
antenna band and gain
local regulatory authorization
```

**Stop if any layer differs.** Do not compensate for a region mismatch in software without correcting the underlying plan.

## 9.10 Shared token and application secrets

Both ChirpStack nodes must use the same ChirpStack token/JWT secret and any shared application-encryption secret required by the pinned version. Generate/store them only after the configuration schema is known.

Do not rotate a shared token secret on one node independently. Do not write live values into the Compose file, TOML committed to Git, command history, or deployment logs.

### 9.10.1 Protected secret inventory checkpoint - 2026-08-25

The ulc-03 control node now holds the complete protected ChirpStack secret set under `/root/lorawan-secrets`. Only file metadata was captured; no secret value was printed.

```text
-rw------- root:root 34 /root/lorawan-secrets/chirpstack-db-auth.txt
-rw------- root:root 65 /root/lorawan-secrets/valkey-auth.txt
-rw------- root:root 65 /root/lorawan-secrets/chirpstack-mqtt-auth.txt
-rw------- root:root 45 /root/lorawan-secrets/chirpstack-api-secret.txt
```

Purpose:

```text
chirpstack-db-auth.txt    -> existing ChirpStack PostgreSQL SCRAM password
valkey-auth.txt           -> commissioned Valkey application password
chirpstack-mqtt-auth.txt  -> dedicated ChirpStack Mosquitto workload password
chirpstack-api-secret.txt -> shared ChirpStack API/token secret for both HA instances
```

This checkpoint is **COMPLETE / PASS**. Keep these source values only in protected control-node storage while constructing node-local runtime configuration. Do not copy the raw files into Git, deployment logs, or shell command arguments. The next configuration step must generate the ulc-01 canary configuration first and keep ulc-02 ChirpStack stopped until the canary and database-migration boundary are proven.

### 9.10.2 ChirpStack 4.19.1 environment-substitution checkpoint - 2026-08-25

Source inspection at commit `1ad3e1177c39cc1c566b879898ccf2b96d231260` proves that `chirpstack/src/config.rs` performs environment-variable substitution on the concatenated contents of every `.toml` file in the configuration directory before TOML parsing. The implementation is explicit:

```rust
for (k, v) in env::vars() {
    content = content.replace(&format!("${}", k), &v);
}
```

Therefore the supported placeholder form is literal `$VARNAME`. There is no evidence of an automatic `CHIRPSTACK__SECTION__FIELD` override convention, and this deployment must not invent one.

The same pinned source confirms the relevant secret-bearing main-config fields: `postgresql.dsn`, `redis.servers`, `integration.mqtt.password`, and `api.secret`. Because substitution occurs before TOML parsing, environment values inserted inside quoted TOML strings must already be safe for that syntactic context; PostgreSQL and Valkey credentials embedded in URLs must also be URL-encoded correctly rather than copied blindly.

The AS923 region TOML is part of the same concatenated configuration and contains its own gateway-backend MQTT `server`, `username`, `password`, and `ca_cert` settings. The authoritative radio/channel values remain frozen to the vetted AS923 source, but the runtime copy must deliberately replace only those MQTT connection defaults with the commissioned local HAProxy workload path and `$VARNAME` secret placeholder. Record a new runtime-file hash after this controlled patch; do not continue calling the modified runtime copy byte-identical to the pristine upstream region source.

Phase 9.6A2 is **COMPLETE / PASS** for environment-substitution semantics.

### 9.10.3 Exact canary field inspection and Valkey trust gate - 2026-08-25

The Phase 9.6B source inspection confirmed the exact ChirpStack 4.19.1 fields required for the ulc-01 canary. `[postgresql]` provides `dsn`, `max_open_connections`, `ca_cert`, and `connection_recycling_method`; `[api]` provides `bind` and `secret`; `[network]` provides `enabled_regions`; `[integration.mqtt]` provides the MQTT server, username, password, client ID, shared-subscription name, CA path, and TLS client-certificate fields. The AS923 region file separately provides the gateway-backend MQTT `topic_prefix`, `share_name`, `server`, `username`, `password`, `client_id`, and `ca_cert` fields.

The production canary must use `connection_recycling_method = "fast"` because PgBouncer is already the external connection pooler. The AS923 radio/channel and network parameters remain unchanged; only its gateway-backend MQTT connection fields may be patched for the commissioned `mqtt.internal.lorawan.com:18883` workload path.

The same inspection exposed one remaining stop condition: the ChirpStack 4.19.1 `[redis]` schema contains `servers`, `cluster`, `key_prefix`, and pool settings but no `ca_cert` field. Do not invent one and do not disable TLS verification. Before writing the ulc-01 production TOML, prove how the exact pinned image and Redis client obtain the trust anchor for `rediss://valkey.internal.lorawan.com:16379` (for example, through the image's system CA bundle or another mechanism supported by the exact runtime). Only after that trust path is proven should the canary files be generated.

Phase 9.6B is **COMPLETE / PASS** for field discovery. ChirpStack remains stopped.

### 9.10.4 Phase 9.6C Valkey TLS trust preflight - PASS - 2026-08-25

The exact pinned ChirpStack `4.19.1` image (`sha256:9e0105f1dd733d3d3caa77aa7cfdbf817417fab8a093dd89639a2cd899ab9efe`) is Alpine Linux 3.24 and runs as `nobody:nogroup`. It contains the standard system CA bundle at `/etc/ssl/certs/ca-certificates.crt`, the `/etc/ssl/cert.pem` compatibility symlink, the standard CA directories, and `update-ca-certificates`.

Pinned source commit `1ad3e1177c39cc1c566b879898ccf2b96d231260` confirms that ChirpStack creates its Valkey/Redis pool directly from `redis.servers` using `deadpool_redis::Config::from_url` / `from_urls`. The configuration schema has no Redis-specific `ca_cert` field. TLS is selected with the documented `rediss://` URL scheme.

The same exact source pins the Rust `redis` crate with `tls-rustls` and `tokio-rustls-comp`, and its dependency graph includes `rustls-native-certs`. This establishes that the Redis TLS path uses native/system certificate roots. Therefore the production canary must keep certificate verification enabled and extend the container trust roots with the internal LoRaWAN CA rather than using an insecure Redis mode or attempting to invent a nonexistent `[redis].ca_cert` setting.

**Implementation rule for the canary:** construct a merged CA bundle from the pinned image's `/etc/ssl/certs/ca-certificates.crt` plus the required internal CA certificate, store it as a root-owned deployment artifact, and mount that merged file read-only at `/etc/ssl/certs/ca-certificates.crt` inside ChirpStack. Do not replace the system bundle with only the private CA, because ChirpStack may also require normal public trust roots for unrelated HTTPS/TLS integrations.

Phase 9.6C is **COMPLETE / PASS**. No ChirpStack service or persistent container was started.

The final ulc-01 pre-construction check also proved that `/etc/lorawan-pki/pgbouncer/ca.crt`, `/etc/lorawan-pki/valkey/ca.crt`, and `/etc/lorawan-pki/mqtt/ca.crt` are byte-identical (`SHA-256 6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`) and expose the same CA identity/fingerprint. The merged ChirpStack trust bundle therefore appends this internal CA exactly once.

**Important loader correction:** the pinned `config.rs` uses `fs::read_dir(config_dir)` and loads `.toml` files directly from that directory; it does not recursively walk a `regions/` subdirectory. Keep the pristine vetted source copy under `regions/region_as923.toml` as provenance, but install the patched active runtime copy as `/etc/lorawan-cloud/chirpstack/region_as923.toml` and mount it directly into `/etc/chirpstack/region_as923.toml` beside `chirpstack.toml`.

The next gate is Phase 9.6D: construct and inspect the ulc-01 canary runtime artifacts (`chirpstack.toml`, top-level controlled AS923 runtime TOML, merged CA bundle, protected environment file, and container definition) without starting ChirpStack.

### 9.10.5 Phase 9.6D ulc-01 pre-construction host checkpoint - 2026-08-25

The corrected root-SSH inspection reached ulc-01 successfully and proved the canary slot is still clean. `/etc/lorawan-cloud/chirpstack` contains only the already-vetted `regions/region_as923.toml`; no `chirpstack.toml`, environment file, merged CA bundle, Compose file, or ChirpStack container is present. Host port `18080` remains free.

The installed AS923 file still has the pristine upstream SHA-256 `ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654` and still contains the upstream MQTT defaults `server = "tcp://localhost:1883"`, blank username/password/client ID, `topic_prefix = "as923"`, and `share_name = "chirpstack"`. The runtime copy has therefore not yet been patched.

Commissioned CA files on ulc-01 are now proven at `/etc/lorawan-pki/pgbouncer/ca.crt`, `/etc/lorawan-pki/valkey/ca.crt`, and `/etc/lorawan-pki/mqtt/ca.crt`. Each is 1891 bytes, but equal size alone is not proof that they are byte-identical. Before constructing the merged system trust bundle, compare their SHA-256 hashes. If they are identical, append one copy of the internal CA to the pinned image's system bundle; if they differ, append the distinct required CA certificates exactly once each.

Phase 9.6D pre-construction is **PASS / READY FOR ARTIFACT BUILD**, subject only to the CA-hash comparison above. No live service was changed.

The Step-2-to-Step-3 local diagnostic then passed on ulc-03. All four protected ChirpStack secret files were readable and non-empty, PostgreSQL and Valkey URL-encoding produced non-empty results, and root-owned mode-0600 temporary-file creation succeeded. This isolates the earlier automation stop away from secret readability, URL encoding, and local temporary-file handling. Resume from artifact construction only; do not repeat the already-passed remote safety checks and do not start ChirpStack yet.
The Phase 9.6D-R continuation then completed local artifact construction through Step 6: protected environment file creation passed without printing secret values, `chirpstack.toml` generation passed, the pristine AS923 hash remained `ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654`, and the active runtime copy was intentionally patched to `ssl://mqtt.internal.lorawan.com:18883` with the ChirpStack workload username, `$CHIRPSTACK_MQTT_PASSWORD` placeholder, ulc-01 gateway client ID, and merged CA path. The runtime AS923 copy hash became `b6d91fb07a20d403fa543358ecd2c8afc7c64304c98f1cf11bf81f1b5fce8870`. Compose definition construction also passed. The observed output stops at the Step 7 heading before any evidence of staging-directory creation or file transfer, so Steps 7+ remain unproven and must not be marked complete.


A follow-up Step 7B diagnostic proved remote staging-directory creation on ulc-01 at `/tmp/phase96d-probe-535831` with mode `0700` and ownership `opsadmin:opsadmin`. The diagnostic returned to the ulc-03 shell immediately after that proof, so local probe creation, SCP transfer, remote probe verification, and cleanup were not executed in that run and remain unproven. Treat only remote staging creation as PASS.

**Harness correction:** the first Step 7C continuation used top-level `exit 1` branches directly in the interactive `opsadmin@ulc-03` login shell. If SCP or remote verification failed, that `exit 1` terminated the user's SSH session to ulc-03. This is a command-harness bug, not evidence of an infrastructure failure. All future continuation blocks that may call `exit` must run inside a subshell / `sudo bash -c` boundary so failure returns control to the login shell instead of closing it.

The safe Step 7C subshell harness was then tested from `ulc-03`. The subshell boundary worked as intended: the command returned `STEP_7C_EXIT_CODE=1` without terminating the SSH login session. The observed failure occurred before SCP or remote-file verification because the local `sudo` credential prompt failed (`Sorry, try again`). Therefore SCP, remote probe verification, and cleanup remained unproven at that checkpoint; this was a local sudo-authentication harness issue only. Future continuation commands must refresh sudo once at the start (`sudo -v`) and then run the remaining work inside a protected subshell.

Step 7D then completed the staging transport proof successfully after refreshing the sudo credential cache. Remote staging existed with mode `0700` and `opsadmin:opsadmin` ownership, local probe creation passed, SCP to ulc-01 passed, the remote probe was verified, cleanup passed, and the protected wrapper returned `STEP_7D_EXIT_CODE=0` while preserving the ulc-03 login shell. Phase 9.6D Step 7 is therefore **COMPLETE / PASS**.

**Continuation correction:** the Step 3-6 candidate files were created under a `mktemp -d` directory protected by an `EXIT` cleanup trap. Because the interrupted automation returned to the shell before the real transfer, those temporary files were deleted even though their construction logic passed. Therefore the production continuation must regenerate the candidate env/TOML/runtime-region/Compose artifacts before the actual transfer. This is regeneration of previously proven build logic, not a need to repeat the earlier host-safety or staging diagnostics. ChirpStack must still remain stopped until static validation completes.


The subsequent Step 7 remote-staging diagnostic proved only SSH reachability from ulc-03 to ulc-01 as `opsadmin` (`uid=1001`, member of `sudo` and `docker`). The diagnostic returned to the ulc-03 prompt immediately after that identity check, so remote `/tmp` staging creation and SCP transfer remain unproven. Do not infer a staging or transfer failure yet; continue with a minimal no-heredoc create/write/copy probe.


The first Phase 9.6D pre-construction probe did not reach ulc-01. It was launched from the unprivileged `opsadmin` shell while referencing `/root/.ssh/cloud-deployment-phase8`, so OpenSSH failed locally with `Identity file ... not accessible: Permission denied` and then `Permission denied (publickey)`. The pasted nested heredoc was also visibly corrupted. Treat this as a control-node command-harness failure only; it provides no evidence about ulc-01 PKI paths, port `18080`, ChirpStack files, or service state. The corrected short-command root-SSH retry then passed and produced the authoritative host facts recorded above.

The Phase 9.6D artifact-build automation has now been executed through its first two gates. Step 1 passed on ulc-03 with the complete protected secret inventory present. Step 2 passed on ulc-01: the pristine AS923 provenance file still matches its authoritative hash, the internal CA hash is unchanged, host port `18080` is still free, the canary artifact paths are still absent, and no persistent ChirpStack container exists. No later Step 3+ output has yet been recorded, so do not mark the artifact build complete and do not assume `chirpstack.toml`, `chirpstack.env`, the merged CA bundle, runtime region copy, Compose file, or pinned image pull has occurred.

## 9.11 Container definition - build only after preflight

The final Compose file must be generated from the exact image and resolved dependency paths. The intended shape is:

```yaml
services:
  chirpstack:
    image: <PINNED_IMAGE_BY_DIGEST>
    restart: unless-stopped
    env_file:
      - /etc/lorawan-cloud/chirpstack/chirpstack.env
    volumes:
      - /etc/lorawan-cloud/chirpstack/chirpstack.toml:/etc/chirpstack/chirpstack.toml:ro
      - /etc/lorawan-cloud/chirpstack/regions:/etc/chirpstack/regions:ro
      - /etc/lorawan-pki/pgbouncer/ca.crt:/run/pgbouncer-ca/ca.crt:ro
      - /etc/lorawan-pki/valkey/ca.crt:/run/valkey-ca/ca.crt:ro
      # Add MQTT CA / workload credentials only after section 9.8 decides
      # the exact authentication method supported by the live stack.
    extra_hosts:
      - "pgbouncer.internal.lorawan.com:<THIS_APP_PRIVATE_IP>"
      - "valkey.internal.lorawan.com:<THIS_APP_PRIVATE_IP>"
      # Add mqtt.internal.lorawan.com only when this app node has a
      # commissioned local/redundant MQTT frontend for that identity.
    ports:
      - "<THIS_APP_PRIVATE_IP>:<FREE_CHIRPSTACK_HOST_PORT>:8080"
    stop_grace_period: 45s
```

The container may still listen internally on `8080` if the pinned image uses that default, but **do not bind host port 8080**: it is already owned by the commissioned Spilo/PostgreSQL stack on ulc-01 and ulc-02. Before deployment, choose and prove a free private host port (for example `18080` only if the pre-bind check confirms it is free) and map `<THIS_APP_PRIVATE_IP>:<FREE_CHIRPSTACK_HOST_PORT>:8080`. Do not expose the host port on `0.0.0.0`. Do not publish optional gRPC/REST listeners unless a required integration is identified and secured.

## 9.12 Database migration control

Only one designated ChirpStack node may own an initial or upgrade migration boundary.

Before the first start:

1. verify the existing `chirpstack` database backup and hash evidence;
2. read the pinned release's migration notes;
3. determine whether startup automatically migrates the schema;
4. nominate ChirpStack-1 on ulc-01 as the first canary unless evidence requires another node;
5. keep ChirpStack-2 stopped during any first migration;
6. capture sanitized migration logs and post-migration schema/application checks;
7. only then start the same digest on ulc-02.

Never allow both nodes to race an undocumented schema migration.

## 9.13 First deployment order

After sections 9.3-9.12 pass:

1. install the pinned image and reviewed config on **ulc-01 only**;
2. start ChirpStack-1 on the selected free private host port on `10.104.0.2` (container port `8080` only if confirmed by the pinned image);
3. verify database TLS through local PgBouncer;
4. verify Valkey TLS through local `:16379`;
5. verify MQTT authentication/TLS/topic access through the commissioned MQTT route;
6. verify region loading and a harmless UI/API operation;
7. stop and fix immediately if the canary changes PostgreSQL/Valkey topology or cannot authenticate to MQTT;
8. after the canary passes, install the **same digest and shared configuration hashes** on ulc-02, changing only explicitly node-specific values;
9. start ChirpStack-2 on the same selected private host-port convention on `10.104.0.4`;
10. verify both private nodes independently and compare image/config hashes;
11. only after both are healthy, hand public `:443` and Reserved-IPv4 work to Phase 10.

Do not require a real gateway or public DNS to prove the first service canary. Real gateway uplink/downlink validation occurs after the cloud application path and public/gateway routing are ready.

## 9.14 Private health and commissioning checks

Before declaring either ChirpStack node ready, prove all of these from that node's container/network context:

- PgBouncer hostname resolves to the local app host and TLS verifies;
- a harmless PostgreSQL query reaches the current writable Patroni primary;
- `valkey.internal.lorawan.com:16379` verifies TLS and routes to `role:master`;
- the MQTT certificate verifies as `mqtt.internal.lorawan.com` through the commissioned route;
- the ChirpStack MQTT identity is authorized for required topics and denied outside its policy;
- the approved region configuration loads without duplicate/unknown-region errors;
- the selected private ChirpStack host port responds normally and maps to the image's confirmed internal HTTP listener;
- no secret is printed in logs;
- both application nodes use the same image digest and shared file hashes.

If the pinned version has an official read-only readiness endpoint, validate it and document it. Otherwise use the normal private UI/API response plus the separate dependency checks above; do not invent a writable health endpoint.

## 9.15 Public HTTPS is Phase 10, not this phase

Do **not** add the public HAProxy `:443` frontend or move the Reserved IPv4 while the ChirpStack application layer is still being commissioned. Phase 9 finishes with two healthy private ChirpStack nodes.

Phase 10 owns:

```text
chirpstack.<DOMAIN>:443 certificate deployment
HAProxy HTTP backend health for the selected private ChirpStack host port on ulc-01/ulc-02
Reserved IPv4 ownership/failover
public DNS validation
public UI/API exposure controls
```

This separation makes rollback clear: a Phase 9 failure cannot disturb the public ingress layer because that layer is not active yet.

## 9.16 Phase 9 acceptance

Phase 9 is complete only when:

- exact ChirpStack version and immutable digest are recorded;
- exact configuration schema and active region files are recorded and identical where required;
- both nodes use local PgBouncer and verify `pgbouncer.internal.lorawan.com`;
- both nodes use local writable-primary Valkey HAProxy and verify `valkey.internal.lorawan.com`;
- ChirpStack MQTT workload authentication/ACLs are explicitly validated;
- MQTT routing used by the two ChirpStack instances has no single ulc-01 HAProxy dependency;
- one controlled database migration owner is proven;
- ChirpStack-1 and ChirpStack-2 both run privately on the selected non-conflicting host port while the existing Spilo/PostgreSQL `:8080` listeners remain untouched;
- both instances use the same shared secrets, image digest, region hashes, and integration policy;
- stopping either ChirpStack instance leaves the other healthy against PostgreSQL, Valkey, and MQTT;
- no public `:443` / Reserved-IP change was needed to commission the application layer.

Next phase after these checks pass: [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md).
