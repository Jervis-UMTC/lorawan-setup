# ChirpStack — Complete Commissioned Deployment, Provisioning and Recovery

**Reader:** operator rebuilding or repairing the LoRaWAN Network Server after reading the [ChirpStack operator guide](05-chirpstack.md). This describes the *real* two-node cloud, not the minimal seven-service teaching VM or the old ChirpStack 4.9 lab. The versions and host positions below are **dated commissioned facts**; inspect actual image digests, leader, dependencies and gateway activity before declaring current health. Ubuntu/Bash commands run on ULC hosts; device/firmware commands belong on the Windows research workstation.

## 1. What ChirpStack does — and does not do

~~~text
EMU-01 RAK4631 OTAA (AS923)
  -> RAK5146 Concentratord / Gateway-01 local MQTT / LTE mTLS
  -> cloud Mosquitto gateway listener :8884
  -> each application's local HAProxy MQTT :18883 -> private :8885
  -> ChirpStack-1 (ULC-01) / ChirpStack-2 (ULC-02)
     |-> PgBouncer :6432 -> local HAProxy :15432 -> current Patroni primary
     |-> Valkey :16379 -> local HAProxy -> current Sentinel-elected writable primary
     |-> application MQTT event -> one active Node-RED writer
       -> PostgreSQL telemetry + eligible evidence/Fabric outbox
~~~

ChirpStack checks LoRaWAN identities, activation/session/MIC/frame counters, region, MAC commands, RX/downlinks, and emits application events. It does **not** itself decide whether independently collected gateway journal evidence is verified; the evidence verifier and Fabric pipeline do that separately. A successful UI login or gateway last-seen is not proof of a complete application/evidence/ledger flow.

## 2. Commissioned inventory

| Item | Actual deployment contract |
|---|---|
| ChirpStack | 4.19.1, pinned image `chirpstack/chirpstack@sha256:9e0105f1dd733d3d3caa77aa7cfdbf817417fab8a093dd89639a2cd899ab9efe` |
| Instances | one container on ULC-01 `10.104.0.2` and ULC-02 `10.104.0.4`; **same digest**, distinct workload MQTT client IDs |
| Host HTTP | private `<THIS_APP_PRIVATE_IP>:18080` -> container `8080` |
| Host port 8080 | **reserved** by existing Spilo/PostgreSQL service; never bind ChirpStack on host `:8080` |
| Database | `pgbouncer.internal.lorawan.com:6432` local mapping; pooler -> local HAProxy primary route |
| Valkey | `valkey.internal.lorawan.com:16379` local mapping; must reach current master |
| MQTT | `ssl://mqtt.internal.lorawan.com:18883` via node-local HAProxy to dedicated Mosquitto `:8885` |
| Broker server identity | `mqtt.internal.lorawan.com`; TLS verification stays enabled |
| Region | **plain AS923**, region ID `as923`, gateway topic prefix `as923` |
| Gateway | Gateway-01 EUI `0016c001f139a1cb` |
| HTTP public access | approved HTTPS / Reserved-IP ingress path, not exposing `:18080` directly |

**Cloud HA does not mean two application data writers:** ChirpStack is two-node application HA, while Node-RED remains a separate **single active** writer and its standby is fenced. Do not conflate the two.

## 3. Preflight: check every dependency before installation

Run on **each** ChirpStack host:

~~~bash
hostname -f
date -u
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -i chirpstack || true
sudo ss -lntp | grep -E ':(6432|15432|16379|18883|18080|8080)\b' || true
getent ahostsv4 pgbouncer.internal.lorawan.com
getent ahostsv4 valkey.internal.lorawan.com
getent ahostsv4 mqtt.internal.lorawan.com
sudo docker compose version
~~~

**PASS:** host maps the three *logical dependency names* to its **own** VPC IP (ULC-01 10.104.0.2, ULC-02 10.104.0.4), appropriate local listeners exist, container state is expected, and host `:8080` remains reserved. A system can have the expected sockets while PostgreSQL or Valkey points at a replica. Confirm Patroni leader and PgBouncer primary routing, Sentinel primary/quorum and Valkey `ROLE`, workload Mosquitto TLS/auth/topic policy separately. A failed dependency is fixed at that layer *before* replacing ChirpStack.

**Name-resolution incident:** during original two-node commissioning, PgBouncer's c-ares resolver cached `127.0.1.1` alongside `10.104.0.4` for `postgres-ha.internal`, causing intermittent waits while HAProxy was bound only to private VPC. Do not assume that an OS `getent` result describes the running PgBouncer cache, and do not change pool limits to mask broken backend routing. Inspect the currently elected/available route and the pooler's own DNS hosts, then apply the reviewed fix to the failing routing layer only.

## 4. Config, secrets and filesystem paths

Commissioned host directory `/etc/lorawan-cloud/chirpstack/`:

~~~text
chirpstack.toml                main active server configuration (non-secret templates)
region_as923.toml              ACTIVE modified region file, top-level
regions/region_as923.toml      pristine upstream-v4.19.1 region provenance (do not edit)
chirpstack.env                 root-owned mode 0600 PROTECTED runtime secret substitutions
ca-certificates.crt            pinned-image system CA roots + current internal CA
~~~

The active Compose project is the commissioned `/opt/chirpstack` deployment or its discovered equivalent; use `sudo docker inspect chirpstack` or current Compose project ownership to locate the real file **before** starting a second instance. In the pinned version the config loader reads *.toml directly from the mounted directory; a region file only under a nested `regions/` folder is **not loaded**. The real active file must be mounted at `/etc/chirpstack/region_as923.toml` next to `chirpstack.toml`.

The upstream plain AS923 region provenance file was pinned from ChirpStack 4.19.1 source, SHA-256 `ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654`. The active file deliberately patches only the gateway-backend MQTT connection for this service: `ssl://mqtt.internal.lorawan.com:18883`, protected service identity and unique node-local client ID. **Do not** copy upstream `tcp://localhost:1883` unchanged or invent generic AS923-3 frequencies. Verify exact RX/channel plan against sensor firmware and RAK5146.

The internal PostgreSQL/PgBouncer, Valkey and MQTT CAs were byte-identical in the original commissioning, but compare actual current CA fingerprints before rebuilding; preserve public trust roots by appending the internal CA to the pinned image's normal CA bundle **once**, not replacing it with a private CA only. ChirpStack 4.19.1 has no separate `[redis].ca_cert` config key; `rediss://` uses the container/system trust roots. Never disable TLS verification or invent unsupported TOML options.

### 4.1 Recover the correct AS923 region file if the host backup is missing

The archived authoritative ChirpStack source is commit `1ad3e1177c39cc1c566b879898ccf2b96d231260`, with the accepted pristine file `chirpstack/configuration/region_as923.toml` and SHA-256 `ecb6db8db68bb195c838be2e58ff328dde35fb8f347cfa08cce0c1687fc16654`. On a trusted Linux *build/admin host*, rather than the live production application container, obtain and verify the exact source only when the preserved copy cannot be restored:

~~~bash
git clone https://github.com/chirpstack/chirpstack.git
cd chirpstack
git checkout --detach 1ad3e1177c39cc1c566b879898ccf2b96d231260
sha256sum chirpstack/configuration/region_as923.toml
~~~

**PASS:** the hash equals the value above, with region ID/topic prefix `as923`. Copy it as the protected *pristine provenance* file first; create a distinct active top-level runtime copy in which **only** the approved MQTT backend server, username/password substitution, CA location and per-node client ID are changed. Check `rx1_delay=1`, `rx1_dr_offset=0`, `rx2_dr=2`, `rx2_frequency=923200000 Hz`, min/max DR `0/5`, and the accepted uplink channels `923200000`/`923400000 Hz` against the *actual* gateway and device firmware before declaring radio equivalence. This source is a dated commissioned configuration, not authority to change a mismatched live radio without coordinated migration.

Do not place the active file solely in `/etc/lorawan-cloud/chirpstack/regions/`: the pinned loader will not recursively read it. After restoring, separately verify exact `regions/region_as923.toml` provenance SHA and *new* active runtime hash rather than claiming the patched file is identical to upstream.

### 4.2 Important PostgreSQL TLS/client dialect difference

For **this exact pinned ChirpStack 4.19.1 core PostgreSQL client**, its DSN accepted `sslmode=require` with separate `[postgresql].ca_cert` and `connection_recycling_method="fast"` for PgBouncer. An earlier attempt copied libpq's `sslmode=verify-full` into that Rust-client DSN and failed its parser; it was **not** proof of bad PKI or database. Other clients such as `psql`/PgBouncer may support `verify-full` and should keep their own reviewed TLS policies. Never mass-search-and-replace `verify-full` across the stack. The separate CA and actual TLS certificate chain remain required.

### 4.3 Exact 4.19.1 environment-substitution contract

The pinned `config.rs` performs substitution of literal `$VARNAME` across the concatenated `.toml` files **before** TOML parsing. Do not invent an unsupported `CHIRPSTACK__SECTION__FIELD` override convention. The project keeps DB, Valkey, MQTT and API secrets in the protected root-owned `chirpstack.env`, populated from the protected operator source, with the same shared API secret on both application nodes and unique per-node MQTT client IDs. Encode URL credentials before inserting them in PostgreSQL/Valkey URIs, and escape TOML-significant characters as required by the exact config parser. Do not log or Git-commit an expanded environment file; for documentation audits record metadata and SHA-256 only, not its contents.

The original control-node protected references were `/root/lorawan-secrets/chirpstack-db-auth.txt`, `valkey-auth.txt`, `chirpstack-mqtt-auth.txt` and `chirpstack-api-secret.txt` on ULC-03. Those paths are **protected lookup hints, not proof the current secret value is present or still valid**. Confirm live secret locations through approved administrator access. When restoring an existing cluster, do not regenerate a replacement secret merely because the path differs on a new host.

## 5. Build or restore the immutable Compose deployment

### 5.1 Requirements on a new replacement host

- Ubuntu 24.04 family, Docker/Compose approved versions and access to the tested pinned image digest.
- HAProxy/PgBouncer and the dedicated `:18883` workload MQTT route already healthy *on that host*.
- Protected service secrets/CA/broker ACLs and a **verified** database snapshot/restoration point.
- Exactly the same reviewed active AS923 region and non-secret TOML on both application hosts.
- **Unique** per-node MQTT client IDs: `chirpstack-ulc01-integration`, `chirpstack-ulc01-gateway` versus `chirpstack-ulc02-integration`, `chirpstack-ulc02-gateway`.

**Do not regenerate the shared ChirpStack API/JWT secret during one-node replacement**: two nodes must share consistent authentication/session semantics. Device OTAA root keys are separate protected data and must not appear in the Compose file or this manual. Restore the reviewed secrets from protected external storage with root-only file mode; don't interpolate them into terminal logs.

### 5.2 Compose shape

Create the host-specific Compose file only after checking the current deployment isn't already installed. The accepted production structure (shown with host-IP placeholder to be resolved before launch) is:

~~~yaml
services:
  chirpstack:
    container_name: chirpstack
    image: chirpstack/chirpstack@sha256:9e0105f1dd733d3d3caa77aa7cfdbf817417fab8a093dd89639a2cd899ab9efe
    restart: unless-stopped
    command: [--config, /etc/chirpstack]
    env_file:
      - /etc/lorawan-cloud/chirpstack/chirpstack.env
    volumes:
      - /etc/lorawan-cloud/chirpstack/chirpstack.toml:/etc/chirpstack/chirpstack.toml:ro
      - /etc/lorawan-cloud/chirpstack/region_as923.toml:/etc/chirpstack/region_as923.toml:ro
      - /etc/lorawan-cloud/chirpstack/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro
    extra_hosts:
      - "pgbouncer.internal.lorawan.com:<THIS_APP_PRIVATE_IP>"
      - "valkey.internal.lorawan.com:<THIS_APP_PRIVATE_IP>"
      - "mqtt.internal.lorawan.com:<THIS_APP_PRIVATE_IP>"
    ports:
      - "<THIS_APP_PRIVATE_IP>:18080:8080"
    stop_grace_period: 45s
~~~

*This is a deployment template, not executable YAML until the host IP and currently protected env/TOML files are resolved.* Set only ULC-01 to `10.104.0.2` and ULC-02 to `10.104.0.4` at the original topology; verify current topology if changed. Docker image should run as `nobody:nogroup` inside the pinned image; ensure this user can read the non-secret mounted config/CA, while protected env file is consumed by Compose from the host and is `root:root 0600`. Keep private host publication only, and do not use host `:8080`.

### 5.3 Validate *before* starting

On each host, inside its actual Compose project directory:

~~~bash
sudo docker compose config --quiet
sudo docker image inspect chirpstack/chirpstack@sha256:9e0105f1dd733d3d3caa77aa7cfdbf817417fab8a093dd89639a2cd899ab9efe --format '{{.Id}} {{.Os}}/{{.Architecture}}'
sudo ss -lntp | grep -E ':(6432|16379|18883|18080)\b' || true
~~~

`config --quiet` validates Compose structure but **not** whether a radio frame will arrive, secrets authenticate or SQL is writable. The pinned ChirpStack `configfile` parse can be run in an isolated `--network none` container using the same reviewed mounts, without launching a persistent server. Keep the exact approved config parser invocation alongside the release artifact and use it before any image upgrade; never pass unreviewed shell guesses to production.

### 5.4 Safe first start or upgrade

1. Take a verifiable PostgreSQL/ChirpStack backup and preserve current immutable image/config/env hashes. Confirm current primary and application acceptance, not only an empty backup filename.
2. Select **one migration owner** (initially ULC-01); keep the other instance stopped during a first schema creation or an upgrade that can migrate schema. The original initial migration was proven and must **not** be rerun on an already populated cluster.
3. Start only that instance with the reviewed Compose file and pinned image; inspect recent bounded logs for PostgreSQL setup/migration check, Valkey, AS923, both independent MQTT clients/subscriptions, and scheduler errors. Require private `:18080` HTTP 200 and no restart loop.
4. Confirm database schema version/expected application tables, service identity and actual SQL/Valkey/MQTT paths without printing DSNs or tokens.
5. Only then start/rejoin ULC-02 with **same image digest and schema**, node-specific broker client IDs and host mappings. Check both private health endpoints, subscriptions and no client-ID fights or unexpected migrations.
6. Verify approved HTTPS ingress through the current Reserved-IP owner, a real gateway uplink and one *single* downstream telemetry write. Keep the last good image/config until rollback conditions are clear.

An HTTP 200 is a process-level check. It does not by itself prove ingestion, OTAA, migration compatibility or end-to-end integrity.

## 6. Provisioning the real gateway and EMU-01

The accepted *2026-09-01 production registry* (read it back from live UI/gRPC before creating anything) is:

| Object | Commissioned value |
|---|---|
| Application | `dissertation-sensors` |
| Gateway | Gateway-01, EUI `0016c001f139a1cb` |
| EMU-01 device profile | `EMU-01 RAK4631 AS923` |
| Device | `dissertation-emu-01`, DevEUI `ac1f09fffe296d29` |
| JoinEUI | `0000000000000000` |
| Region | `AS923` / region id `as923` |
| MAC / regional params | LoRaWAN 1.0.2, parameters revision B |
| Activation/class | OTAA, Class A |
| ADR | default |
| Normal production cadence | nominal 300 s with ±15 s jitter; frozen research profile may use 15 s |

**Never put the AppKey/NwkKey into the guide, screenshots or PDF.** Retrieve them from protected provisioning records; register using the supported ChirpStack UI or authenticated gRPC API. A temporary global provisioning API token must be revoked after use. The security-fixture SEC device must not be silently added to the permanent production registry. Before creating a gateway/device, search exact EUI/DevEUI and application; duplicate registrations are not an acceptable fix for old last-seen timestamps.

Provisioning order for a fresh authorized replacement registry: tenant/application -> reviewed device profile with correct MAC/region/payload-v2 codec -> gateway EUI -> device record exact DevEUI/JoinEUI -> protected OTAA keys -> application integration -> normal-path proof. Never overwrite a populated production database to force this sequence.

## 7. Observe where LoRaWAN fails

**Gateway missing:** first check RAK5146 startup identity, approved RF/uplink, local MQTT, LTE/cloud broker EUI topic, then ChirpStack shared subscription and registered gateway. If cloud MQTT has the topic but last-seen remains stale, do not change RF channels yet.

**JoinRequest received but no JoinAccept:** check exact DevEUI/JoinEUI, protected root-key match, selected LoRaWAN MAC/region profile and activation; then RX1/RX2, downlink scheduling, AS923 channels, gateway duty/regulatory limits and device receive timing. Do not re-register/reset frame counters as a shortcut.

**Post-join event missing:** compare session state, MIC/frame counter, FPort/payload codec and gateway event to application event; test the MQTT app integration/Node-RED subscription only after LoRaWAN accept is evidenced.

**Application event exists but DB measurement absent:** check only the one active Node-RED writer and its transaction/idempotency/DB route. **Telemetry exists but v2 evidence missing:** inspect journal, cloud MQTT witness, raw object storage and verifier; ChirpStack is not evidence authority.

### 7.1 Read-only application checks

On ULC-01 and ULC-02:

~~~bash
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -i chirpstack || true
sudo docker logs --since=15m --tail=150 chirpstack
curl --connect-timeout 3 --max-time 5 -fsS -o /dev/null -w 'HTTP=%{http_code}\n' http://127.0.0.1:18080/
~~~

If the service binds only private VPC and not loopback, target that node's `10.104.0.x:18080` instead of misclassifying it down. Check correct device and gateway UI/API objects and one recent genuine event; raw network-server gateway payload is Protobuf. SQL app rows, sealed recorder and independent verifier must agree before an end-to-end research claim.

## 8. Recovery without damaging sessions or HA

| Failure | Appropriate next action |
|---|---|
| Only one ChirpStack container unhealthy | preserve logs/config; verify its dependencies; restart/recreate **only that node** if required; verify its peer remains healthy |
| Both unhealthy | inspect shared DB/Valkey/MQTT/PKI, not both containers simultaneously |
| PostgreSQL pool timeouts | inspect PgBouncer live backend DNS/HAProxy and Patroni primary before raising pool sizes |
| TLS trust / invalid DSN mode | verify exact image/client-specific schema, protected env DSN mode and CA; never disable TLS blindly |
| AS923 file not loaded | active TOML must be top-level direct mount in config directory |
| MQTT client conflict | unique *per node* gateway and integration client IDs, shared subscription design |
| OTAA/session rejected | compare protected identity, region and frame counters; do not wipe device sessions/keys |
| Database schema incompatible | stop upgrade; restore **reviewed compatible** image/config only after assessing migration rollback support; database restore needs approved state boundary |
| Public UI down but both private HTTP 200 | HTTPS/Reserved-IP ingress, not container reinstall |

For one-node replacement: prove healthy surviving member, restore approved image/config/secret/CA and local dependency mappings, validate as above, rejoin, check both HTTP+MQTT and one approved real uplink. If changing database schema/image, take consistent full backups first; restoring an old application image against a new migrated schema is not a proven rollback. Do not repeat disruptive HA or physical RF testing just to edit documentation.

## 9. Handoff and standalone Word document criteria

Record timestamp, selected host and actual current digest, read-only config/region hashes, private listeners and dependencies, gateway/device inventory, one real accepted application event, separate evidence result and any open gate. Do not label synthetic-only runs as real RF or non-counted rehearsals as completed formal research trials.

Maintenance authorities: [cloud ChirpStack commissioning](../server/cloud-production/09-chirpstack-cloud-cluster.md), [registry and migration](../server/cloud-production/12-gateway-and-device-migration.md), [MQTT companion](MQTT-INSTALLATION-SECURITY-RECOVERY.md), [AS923 gateway companion](RAK5146-AS923-COMMISSIONING.md), and [sensor firmware](18-rak4631-wisblock-sensor-firmware.md). The final comprehensive Word document must print the necessary procedures and measurements inside its own chapters and appendices, not require the reader to open these Markdown files.
