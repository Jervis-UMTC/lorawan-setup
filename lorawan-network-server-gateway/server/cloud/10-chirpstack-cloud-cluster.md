# 10. Two-Node ChirpStack Cloud Cluster

## 10.1 Goal

Run two interchangeable ChirpStack v4 application instances behind the approved load balancer. Both instances use the same PostgreSQL cluster, Valkey service, MQTT broker, configuration, region files, token secret, and integration policy.

The application nodes are replaceable. They must not store unique production state only on a local filesystem.

## 10.2 Preconditions

- PostgreSQL primary routing through local HAProxy and PgBouncer works on both app nodes.
- ChirpStack database exists and a validated backup is available.
- Managed Valkey is reachable through TLS from both app nodes.
- MQTT TLS and ACLs are validated.
- public DNS and certificate are ready;
- exact ChirpStack image version/digest is approved;
- legal LoRaWAN region and exact region configuration file are approved;
- migration owner and rollback procedure are assigned.

**Stop here. Do not run migrations or start both nodes** until every dependency and the database backup are verified.

## 10.3 Obtain the version-specific configuration

Use the official ChirpStack release image and documentation for the pinned version. Keep the ChirpStack version and image digest, configuration-template source, enabled integrations, active region filenames and hashes, observed database-migration behavior, and rollback digest together. These values identify the configuration schema and region files that both application nodes must share.

Extract or generate the configuration template from the exact image instead of copying a historical file blindly.

```bash
docker run --rm <PINNED_CHIRPSTACK_IMAGE> --version
docker run --rm <PINNED_CHIRPSTACK_IMAGE> configfile > /tmp/chirpstack.toml.example
```

Inspect the image's supported command before using `configfile`; command names may change.

## 10.4 Shared configuration directory

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

## 10.5 Core database connection

ChirpStack connects to local PgBouncer:

```text
host: 127.0.0.1
port: 6432
database: chirpstack
user: chirpstack
TLS on app-to-PgBouncer hop: local loopback
TLS on PgBouncer-to-PostgreSQL hop: verify-full
```

Illustrative DSN stored in the protected environment file:

```dotenv
CHIRPSTACK_POSTGRESQL_DSN=postgresql://chirpstack:<SECRET_REFERENCE>@127.0.0.1:6432/chirpstack?sslmode=disable
```

Do not put the live DSN in Compose files, documentation, or logs. Confirm the exact environment-variable override supported by the pinned ChirpStack version.

## 10.6 Valkey configuration

Configure the private TLS endpoint and certificate verification. Illustrative intent:

```toml
[redis]
servers=["rediss://<VALKEY_PRIVATE_FQDN>:<PORT>"]
tls_enabled=true
```

The actual keys and URI format must come from the pinned ChirpStack configuration template. Do not disable TLS hostname verification to make a mismatched endpoint work.

## 10.7 Gateway MQTT backend and application integration

Configure every active ChirpStack region to use the approved broker and region prefix:

```toml
[regions.gateway.backend.mqtt]
server="ssl://<PRIVATE_MQTT_ENDPOINT>:8883"
client_id="chirpstack-<APP_NODE_NAME>"
ca_cert="/run/mqtt-ca/ca.crt"
tls_cert="/run/mqtt-client/chirpstack.crt"
tls_key="/run/mqtt-client/chirpstack.key"
```

The key format and exact field names must come from the pinned ChirpStack template. The gateway-backend TLS private key may require PKCS#8.

Configure `[integration.mqtt]` separately when applications consume MQTT events. Use a distinct client ID and least-privilege identity when supported.

With multiple ChirpStack nodes, validate the pinned version's supported shared-subscription or duplicate-processing behavior. Do not assume that adding a second subscriber produces correct single-consumer processing.

## 10.8 Region configuration

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

## 10.9 Token and encryption secrets

Both application nodes must use the same ChirpStack token/JWT secret and any shared application encryption secret. Generate independent strong values through the approved secret store.

Never rotate the token secret on one node only. A staggered mismatch causes tokens issued by one node to fail on the other.

## 10.10 Container definition

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
      - /etc/lorawan-pki/mqtt:/run/mqtt-ca:ro
    ports:
      - "<APP_PRIVATE_IP>:8080:8080"
    stop_grace_period: 45s
```

Replace all placeholders. Pin by immutable digest. Bind only to the private VPC address; the load balancer or reverse proxy is the public entry point.

Do not publish optional gRPC/REST listeners unless an approved integration requires them. Bind them privately and apply authentication/TLS.

## 10.11 Database migration control

Only one designated node runs schema migrations during an upgrade.

Procedure:

1. create and validate PostgreSQL backups;
2. read release notes and migration requirements;
3. stop or drain `app-02`;
4. take `app-01` out of the public load balancer if the migration requires exclusive access;
5. run the pinned version's migration/startup command and capture sanitized logs;
6. verify schema and application behavior;
7. return `app-01` to service;
8. update `app-02` and return it to service;
9. verify both image digests and configuration hashes.

Do not allow both nodes to race an irreversible migration unless the upstream version explicitly documents that as safe.

## 10.12 First deployment order

1. Start only `app-01`.
2. Watch logs for database migrations, MQTT, Valkey, and region loading.
3. Verify database connectivity through PgBouncer.
4. Verify the UI/API through the private address.
5. Register one staging gateway and prove gateway stats and one real uplink.
6. Start `app-02` with the same configuration.
7. Verify both nodes independently.
8. Add both to the public load balancer.
9. Prove session/token behavior while alternating backends.

## 10.13 Reverse proxy and public access

The public endpoint should be:

```text
https://chirpstack.<DOMAIN>
```

Use the Regional Load Balancer or a private reverse proxy for TLS. Restrict backend access to the load balancer. Preserve client IP only when the provider and application configuration support it safely.

Administrative protection options:

- identity-aware proxy or organization VPN;
- IP allowlist for management locations;
- MFA at the application/identity layer where supported;
- separate operator and service accounts;
- immediate removal of default credentials.

Do not expose the UI with a default password during commissioning.

## 10.14 Health checks

Use two levels.

### Process check

Confirms the HTTP listener accepts a request.

### Dependency-aware readiness check

Confirms the node can:

- query PostgreSQL through PgBouncer;
- reach Valkey;
- connect to MQTT;
- load the approved region configuration;
- complete a harmless authenticated API/database operation.

If ChirpStack lacks a built-in dependency-aware endpoint, run a local health agent or reverse-proxy check that performs bounded probes. Do not make the load balancer execute writes on every health interval.

## 10.15 Application validation

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

## 10.16 Final checks

- Two nodes use the same approved digest, configuration hashes, token secret, regions, and integrations.
- Both use local PgBouncer/HAProxy and shared Valkey/MQTT services.
- Database migrations run from one designated node and the resulting schema/application checks succeed.
- Public access is TLS-protected and backends are private.
- Load-balancer health removes a dependency-broken node.
- Gateway stats, real uplinks, and downlinks continue with one app node unavailable.

Next: [11-gateway-and-device-migration.md](11-gateway-and-device-migration.md)
