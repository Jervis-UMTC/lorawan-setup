# 9. Two-Node ChirpStack HA on the Minimum Three-Droplet Cluster

> **Status: STANDBY / DRAFT.** ChirpStack has not yet been deployed or live-validated in this cloud build. Re-check the exact ChirpStack version, configuration schema, region files, database/Valkey/MQTT settings, migrations, and listeners when this phase becomes active.

## 9.1 Goal

The minimum HA test profile runs two interchangeable ChirpStack v4 instances:

```text
ha-01 -> ChirpStack-1
ha-02 -> ChirpStack-2
```

Both use the same PostgreSQL HA endpoint, Valkey HA endpoint, active MQTT service, secrets, region files, and integration policy. A third ChirpStack instance on ha-03 is unnecessary for the defined one-Droplet-failure target.

## 9.2 Preconditions

- PgBouncer -> HAProxy -> Patroni-primary routing works on ha-01 and ha-02.
- ChirpStack database exists and a validated backup is available.
- the Valkey/Sentinel HA service is reachable through the local HAProxy endpoint on both app nodes;
- MQTT TLS and ACLs are validated.
- public DNS and certificate are ready;
- exact ChirpStack image version/digest is approved;
- legal LoRaWAN region and exact region configuration file are approved;
- migration owner and rollback procedure are assigned.

**Stop here. Do not run migrations or start both nodes** until every dependency and the database backup are verified.

## 9.3 Obtain the version-specific configuration

Use the official ChirpStack release image and documentation for the pinned version. Keep the ChirpStack version and image digest, configuration-template source, enabled integrations, active region filenames and hashes, observed database-migration behavior, and rollback digest together. These values identify the configuration schema and region files that both application nodes must share.

Extract or generate the configuration template from the exact image instead of copying a historical file blindly.

```bash
docker run --rm <PINNED_CHIRPSTACK_IMAGE> --version
docker run --rm <PINNED_CHIRPSTACK_IMAGE> configfile > /tmp/chirpstack.toml.example
```

Inspect the image's supported command before using `configfile`; command names may change.

## 9.4 Shared configuration directory

Create a root-owned directory on each app node:

```bash
sudo install -d -m 750 /etc/lorawan-cloud/chirpstack
sudo install -d -m 750 /etc/lorawan-cloud/chirpstack/regions
sudo install -m 600 /dev/null /etc/lorawan-cloud/chirpstack/chirpstack.env
```

Configuration files may need read access for the container user. Grant the minimum group permission required; do not make secret-bearing files world-readable.

Keep both nodes synchronized through configuration management. Compare a hash of every active file on both nodes and retain the expected hashes for drift and rollback checks:

```bash
sudo find /etc/lorawan-cloud/chirpstack -type f -exec sha256sum {} +
```

## 9.5 Core database connection

ChirpStack connects to the PgBouncer instance on its own application host. Because ChirpStack is containerized, use a logical name mapped to that host's private VPC IP:

```text
ChirpStack-1 -> pgbouncer.internal.lorawan.com:6432 -> PgBouncer on ha-01
ChirpStack-2 -> pgbouncer.internal.lorawan.com:6432 -> PgBouncer on ha-02

PgBouncer -> postgres-ha.internal:15432 -> local HAProxy
HAProxy -> current Patroni primary :5432
```

The application DSN stays stable during PostgreSQL failover because neither the PgBouncer endpoint nor the HAProxy endpoint changes. Patroni changes the database role; HAProxy follows the writable primary; PgBouncer replaces/reuses server connections.

Illustrative values stored in the protected environment/config workflow:

```dotenv
CHIRPSTACK_POSTGRESQL_DSN=postgresql://chirpstack:<SECRET_REFERENCE>@pgbouncer.internal.lorawan.com:6432/chirpstack?sslmode=verify-full
```

In the pinned ChirpStack configuration set the PostgreSQL CA path as well:

```toml
[postgresql]
dsn="$CHIRPSTACK_POSTGRESQL_DSN"
ca_cert="/run/pgbouncer-ca/ca.crt"
connection_recycling_method="fast"
```

`fast` is used here because the architecture deliberately places the external PgBouncer pooler in front of PostgreSQL. Mount the CA so ChirpStack can verify the PgBouncer certificate for `pgbouncer.internal.lorawan.com`. PgBouncer's server connection through HAProxy to PostgreSQL separately uses `verify-full` against `postgres-ha.internal`. Do not put live credentials in Compose files, documentation, or logs.

## 9.6 Valkey configuration

Configure ChirpStack to use a logical local-HAProxy Valkey name. Map that name to the current app host's private IP inside each ChirpStack container:

```text
valkey-ha.internal.<DOMAIN> -> local app-host private IP
HAProxy frontend            -> <THIS_APP_PRIVATE_IP>:16379
HAProxy backend             -> current Sentinel-promoted Valkey primary
```

With Valkey TLS enabled, each Valkey server certificate must include `valkey-ha.internal.<DOMAIN>` in its SAN so the same verified logical name remains valid after promotion.

The current ChirpStack Redis/Valkey configuration carries authentication in the URL. Keep the password in the protected environment file and substitute it into the TOML rather than writing the live secret in Git:

```dotenv
CHIRPSTACK_VALKEY_PASSWORD=<SECRET_REFERENCE>
```

```toml
[redis]
servers=["rediss://:$CHIRPSTACK_VALKEY_PASSWORD@valkey-ha.internal.<DOMAIN>:16379"]
cluster=false
```

The current configuration template exposes `rediss://` URLs but no separate Redis CA-file field. Therefore the internal Valkey CA must be trusted by the ChirpStack container's operating-system trust store (or the Valkey certificate must chain to an already trusted CA). Install/mount the CA into the image's documented trust path and refresh the trust store using the method supported by the pinned image **before** starting ChirpStack.

**Stop here** if a direct TLS connection from inside the ChirpStack container cannot validate `valkey-ha.internal.<DOMAIN>` without an insecure/skip-verification option.

## 9.7 Gateway MQTT backend and application integration

Configure every active ChirpStack region on **ha-01 and ha-02** to use the same logical HAProxy MQTT name and region prefix. Map `mqtt-ha.internal.<DOMAIN>` to the current app host's private IP inside each ChirpStack container. Both Mosquitto server certificates must include this internal SAN as well as the public `mqtt.<DOMAIN>` SAN.

```toml
[regions.gateway.backend.mqtt]
server="ssl://mqtt-ha.internal.<DOMAIN>:18883"
client_id="chirpstack-<APP_NODE_NAME>"
ca_cert="/run/mqtt-ca/ca.crt"
tls_cert="/run/mqtt-client/chirpstack.crt"
tls_key="/run/mqtt-client/chirpstack.key"
```

HAProxy listens on `<THIS_APP_PRIVATE_IP>:18883` for this internal MQTT path and forwards TCP to the same preferred/backup Mosquitto pool used by the public gateway path. TLS remains end-to-end to Mosquitto, so hostname verification and client-certificate authentication are preserved. The key format and exact field names must come from the pinned ChirpStack template; the gateway-backend TLS private key may require PKCS#8.

Configure `[integration.mqtt]` separately when applications consume MQTT events. Use a distinct client ID and least-privilege identity when supported.

For `[integration.mqtt]`, configure the same `share_name` on both ChirpStack instances. The current ChirpStack configuration explicitly defines this value for shared subscriptions across multiple instances. Keep distinct client IDs where required for diagnostics.

## 9.8 Region configuration

Use the exact active region-file model for the pinned ChirpStack version. For an approved AS923-3 deployment, the identifier is commonly `as923_3`, but copy it from the active region file rather than inferring it from a display label.

Verify all layers agree:

```text
End-device frequency variant
RAK5146 regional hardware variant
Gateway OS Concentratord channel plan
Gateway OS MQTT Forwarder topic prefix
ChirpStack gateway-backend MQTT topic prefix
ChirpStack enabled region ID
ChirpStack region frequencies and data rates
Device profile region/MAC settings
Antenna band and gain
Local regulatory authorization
```

**Stop here. Do not transmit** if any layer differs or the legal plan is unconfirmed.

## 9.9 Token and encryption secrets

Both application nodes must use the same ChirpStack token/JWT secret and any shared application encryption secret. Generate independent strong values through the approved secret store.

Never rotate the token secret on one node only. A staggered mismatch causes tokens issued by one node to fail on the other.

## 9.10 Container definition

Illustrative per-node Compose file:

```yaml
services:
  chirpstack:
    image: <PINNED_CHIRPSTACK_IMAGE>
    restart: unless-stopped
    env_file:
      - /etc/lorawan-cloud/chirpstack/chirpstack.env
    volumes:
      - /etc/lorawan-cloud/chirpstack/chirpstack.toml:/etc/chirpstack/chirpstack.toml:ro
      - /etc/lorawan-cloud/chirpstack/regions:/etc/chirpstack/regions:ro
      - /etc/lorawan-pki/pgbouncer/ca.crt:/run/pgbouncer-ca/ca.crt:ro
      - /etc/lorawan-pki/mqtt/ca.crt:/run/mqtt-ca/ca.crt:ro
      - /etc/lorawan-pki/mqtt-client/chirpstack.crt:/run/mqtt-client/chirpstack.crt:ro
      - /etc/lorawan-pki/mqtt-client/chirpstack.key:/run/mqtt-client/chirpstack.key:ro
      # Mount the internal Valkey CA into the pinned image's supported
      # system-trust import path when it is not signed by a public/system CA.
      - /etc/lorawan-pki/valkey/ca.crt:/run/valkey-ca/ca.crt:ro
    extra_hosts:
      - "pgbouncer.internal.lorawan.com:<APP_PRIVATE_IP>"
      - "valkey-ha.internal.<DOMAIN>:<APP_PRIVATE_IP>"
      - "mqtt-ha.internal.<DOMAIN>:<APP_PRIVATE_IP>"
    ports:
      - "<APP_PRIVATE_IP>:8080:8080"
    stop_grace_period: 45s
```

Replace all placeholders. Pin by immutable digest. Before `docker compose up`, verify the mounted files exist, the container runtime user can read only the files it needs, and the Valkey CA has been imported into the container trust store when required. ChirpStack itself remains on the private VPC address; HAProxy on the current Reserved-IP owner is the public entry point.

The `extra_hosts` entries are deliberate: they force each ChirpStack container's logical service names to its **own host's private VPC address**, where local PgBouncer/HAProxy provide the stable failover routes.

Do not publish optional gRPC/REST listeners unless an approved integration requires them. Bind them privately and apply authentication/TLS.

## 9.11 Database migration control

Only one designated node runs schema migrations during an upgrade.

Procedure:

1. create and validate PostgreSQL backups;
2. read release notes and migration requirements;
3. stop or drain ChirpStack-2 on `ha-02`;
4. take ChirpStack-1 on `ha-01` out of service if the migration requires exclusive access;
5. run the pinned version's migration/startup command and capture sanitized logs;
6. verify schema and application behavior;
7. return ChirpStack-1 on `ha-01` to service;
8. update ChirpStack-2 on `ha-02` and return it to service;
9. verify both image digests and configuration hashes.

Do not allow both nodes to race an irreversible migration unless the upstream version explicitly documents that as safe.

## 9.12 First deployment order

1. Start only ChirpStack-1 on `ha-01`.
2. Watch logs for database migrations, MQTT, Valkey, and region loading.
3. Verify database connectivity through PgBouncer -> HAProxy.
4. Verify the UI/API through the private address.
5. Register one staging gateway and prove gateway stats and one real uplink.
6. Start ChirpStack-2 on `ha-02` with the same configuration.
7. Verify both nodes independently.
8. Configure both HAProxy public candidates and prove manual Reserved-IP reassignment between them.
9. Prove session/token behavior while alternating ChirpStack backends without changing the public hostname.

## 9.13 HAProxy HTTPS frontend and public access

Use one explicit POC TLS boundary:

```text
browser / API client
      |
      | HTTPS :443
      v
DigitalOcean Reserved IPv4
      |
      | assigned to one app Droplet
      v
HAProxy on ha-01 OR ha-02 anchor :443
      |
      | TLS terminates here
      v
ChirpStack-1 / ChirpStack-2 private HTTP :8080
```

Install the same `chirpstack.<DOMAIN>` certificate/key on the two HAProxy app hosts using protected file permissions so the TLS identity remains unchanged when the Reserved IP moves.

Add on **ha-01 and ha-02 only**:

```haproxy
frontend chirpstack_https
    mode http
    bind <THIS_APP_ANCHOR_IP>:443 ssl crt /etc/lorawan-pki/public/chirpstack.pem alpn h2,http/1.1
    option httplog
    http-request set-header X-Forwarded-Proto https
    default_backend chirpstack_nodes

backend chirpstack_nodes
    mode http
    balance roundrobin
    option httpchk GET /
    # By default HAProxy treats HTTP 2xx/3xx health responses as healthy.
    default-server inter 3s fall 3 rise 2
    server chirpstack-1 <HA01_PRIVATE_IP>:8080 check
    server chirpstack-2 <HA02_PRIVATE_IP>:8080 check
```

Validate before reload:

```bash
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sudo ss -lntp | grep ':443'
```

Then test each HAProxy directly **before enabling automatic Reserved-IP failover** by resolving the public hostname to that host's anchor IP from the host itself using `curl --resolve`:

```bash
curl --fail --silent --show-error \
  --resolve chirpstack.<DOMAIN>:443:<APP_HOST_REACHABLE_IP> \
  https://chirpstack.<DOMAIN>/ >/dev/null
```

Pass only when both HAProxy hosts present a certificate valid for `chirpstack.<DOMAIN>` and can reach at least one healthy ChirpStack backend.

The final public endpoint is:

```text
https://chirpstack.<DOMAIN>
```

There is no managed NLB in this POC. The Reserved IP performs no TLS termination; it simply maps the stable public address to the currently assigned Droplet. HTTPS terminates at HAProxy and MQTT remains raw TLS pass-through to Mosquitto.

Administrative protection options:

- identity-aware proxy or organization VPN;
- IP allowlist for management locations;
- MFA at the application/identity layer where supported;
- separate operator and service accounts;
- immediate removal of default credentials.

Do not expose the UI with a default password during commissioning.

## 9.14 Health checks

Use two levels.

### HAProxy process/application check

`option httpchk GET /` removes a backend that is not serving a normal 2xx/3xx HTTP response. This is deliberately simple and read-only.

### Dependency-aware commissioning check

Before declaring either ChirpStack node ready, separately confirm it can:

- query PostgreSQL through PgBouncer -> HAProxy;
- reach Valkey;
- connect to MQTT;
- load the approved region configuration;
- complete a harmless authenticated API/database operation.

Do not invent a writable health endpoint. If the pinned ChirpStack version later provides an official read-only readiness endpoint, replace the simple `/` backend check only after staging verification. For this POC, dependency health is proven during commissioning and failure tests in addition to the HAProxy HTTP check.

## 9.15 Application validation

From an approved workstation:

```bash
curl --fail --silent --show-error https://chirpstack.<DOMAIN>/
```

Then verify:

- login through the public endpoint;
- tenant/application/device counts;
- gateway last-seen freshness;
- one real uplink and decoded event;
- one integration event on MQTT/webhook where configured;
- a safe Class A downlink after an uplink;
- successful operation when either application node is stopped;
- database primary switchover without DSN changes.

## 9.16 Final checks

- Two nodes use the same approved digest, configuration hashes, token secret, regions, and integrations.
- Both use local PgBouncer + HAProxy and the same Valkey/Sentinel and active/standby MQTT services.
- Database migrations run from one designated node and the resulting schema/application checks succeed.
- Public access is TLS-protected and backends are private.
- HAProxy backend health handles individual service failures, while the Reserved-IP failover agent moves public ingress only when the current app host/public path is persistently unavailable.
- Gateway stats, real uplinks, and downlinks continue with one app node unavailable.

Next standby phase: [10-self-managed-public-ingress.md](10-self-managed-public-ingress.md).
