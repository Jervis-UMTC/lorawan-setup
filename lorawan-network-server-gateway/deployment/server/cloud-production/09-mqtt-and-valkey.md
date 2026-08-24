# 9. MQTT and Valkey HA on the Three-Node POC

This manual deploys the two shared runtime dependencies used by ChirpStack:

```text
MQTT transport      -> Mosquitto-1 preferred / Mosquitto-2 backup
fast shared state   -> Valkey primary + 2 replicas, managed by 3 Sentinels
```

The physical gateway's local Mosquitto queue remains separate on the Raspberry Pi. Do not confuse that edge buffer with the two cloud brokers.

## 9.1 Port plan and why the broker backend uses 8884

Use this exact separation:

```text
PUBLIC MQTT SERVICE
mqtt.<DOMAIN>:8883
  -> DigitalOcean Reserved IPv4
  -> current owner: HAProxy on ha-01 OR ha-02 anchor :8883
  -> Mosquitto backend TLS :8884

PRIVATE MQTT SERVICE
mqtt-ha.internal.<DOMAIN>:18883
  -> local HAProxy on ha-01/ha-02/ha-03
  -> same Mosquitto backend TLS :8884
```

`8883` belongs to the HAProxy public frontend on the **anchor IP** of `ha-01/02`. The Mosquitto processes listen on private backend port `8884`, so the broker and public HAProxy listener never contend for the same address/port.

**Why:** HAProxy and Mosquitto cannot both bind the same `<HOST_PRIVATE_IP>:8883`. Using `8884` internally removes that collision while preserving the normal public MQTT endpoint `mqtt.<DOMAIN>:8883`.

The cloud brokers do not need a plaintext `1883` listener. The only plaintext `1883` in this architecture is the Raspberry Pi gateway-local loopback broker at `127.0.0.1:1883`.

## 9.2 Preconditions

Before installing either service, record:

```text
ha-01 private IP:
ha-02 private IP:
ha-03 private IP:
DOMAIN:
confirmed ChirpStack region/topic prefix:
Mosquitto image/version/digest:
Valkey image/version/digest:
MQTT CA path:
Valkey CA path:
Valkey shared application secret reference:
Sentinel administration secret reference:
```

Required certificates already issued by the PKI step:

```text
Mosquitto-1 server certificate
  SAN: mqtt.<DOMAIN>
  SAN: mqtt-ha.internal.<DOMAIN>
  SAN: ha-01 private name/IP as required

Mosquitto-2 server certificate
  SAN: mqtt.<DOMAIN>
  SAN: mqtt-ha.internal.<DOMAIN>
  SAN: ha-02 private name/IP as required

Valkey-1/2/3 server certificates
  SAN: valkey-ha.internal.<DOMAIN>
  SAN: each node's own private name/IP
```

MQTT client identities required for the POC:

```text
one unique certificate per physical gateway
  CN = its 16-hex Gateway EUI

ChirpStack workload certificate(s)
  not reused by gateways

Node-RED workload certificate
  read-only application-uplink permission
```

**Stop here. Do not continue** if certificate SANs, private IPs, region prefix, or image versions are still placeholders.

## 9.3 Prepare Mosquitto on ha-01 and ha-02

Run this section on **ha-01 and ha-02 only**.

Create directories:

```bash
sudo install -d -m 750 /etc/lorawan-cloud/mosquitto
sudo install -d -m 750 /etc/lorawan-pki/mqtt
sudo install -d -m 750 /srv/mosquitto/data
sudo install -m 640 /dev/null /etc/lorawan-cloud/mosquitto/acl
```

Install the node's broker certificate/key and the gateway/workload CA using the owner/group required by the pinned Mosquitto image or package. Never copy a CA private key to a broker.

Create `/etc/lorawan-cloud/mosquitto/mosquitto.conf` on each broker host. Replace `<THIS_HOST_PRIVATE_IP>` with that host's VPC address:

```conf
persistence true
persistence_location /mosquitto/data/
autosave_interval 60
log_dest stdout

listener 8884 <THIS_HOST_PRIVATE_IP>
protocol mqtt
allow_anonymous false

cafile /mosquitto/config/certs/ca.crt
certfile /mosquitto/config/certs/server.crt
keyfile /mosquitto/config/certs/server.key
require_certificate true
use_identity_as_username true
tls_version tlsv1.2

acl_file /mosquitto/config/acl
```

`require_certificate true` makes the TLS listener require a valid client certificate. `use_identity_as_username true` maps the client-certificate Common Name to the MQTT username used by the ACL.

Do not add a cloud listener on `1883`.

## 9.4 Create the MQTT ACL

For each gateway, add only its own topics. Example shape:

```text
user <GATEWAY_EUI>
topic write <REGION_PREFIX>/gateway/<GATEWAY_EUI>/event/#
topic write <REGION_PREFIX>/gateway/<GATEWAY_EUI>/state/#
topic read  <REGION_PREFIX>/gateway/<GATEWAY_EUI>/command/#
```

For ChirpStack, give the reviewed workload identity the gateway-backend permissions it actually needs:

```text
user <CHIRPSTACK_MQTT_IDENTITY>
topic read  <REGION_PREFIX>/gateway/+/event/#
topic read  <REGION_PREFIX>/gateway/+/state/#
topic write <REGION_PREFIX>/gateway/+/command/#
topic write application/+/device/+/event/#
topic read  application/+/device/+/command/#
```

For Node-RED:

```text
user <NODE_RED_MQTT_IDENTITY>
topic read application/+/device/+/event/up
```

If the pinned ChirpStack configuration uses separate gateway-backend and application-integration certificates, split the ChirpStack ACL accordingly rather than broadening one identity.

Copy the **same reviewed ACL policy** to Mosquitto-1 and Mosquitto-2. Keep certificate/private-key files node-specific.

## 9.5 Run each Mosquitto backend

A containerized host-network example is below. Use the exact paths/user documented by the pinned image:

```yaml
services:
  mosquitto:
    image: <PINNED_MOSQUITTO_IMAGE>
    network_mode: host
    restart: unless-stopped
    volumes:
      - /etc/lorawan-cloud/mosquitto/mosquitto.conf:/mosquitto/config/mosquitto.conf:ro
      - /etc/lorawan-cloud/mosquitto/acl:/mosquitto/config/acl:ro
      - /etc/lorawan-pki/mqtt:/mosquitto/config/certs:ro
      - /srv/mosquitto/data:/mosquitto/data
```

Validate before start using the validation method supported by the pinned image, then:

```bash
sudo docker compose -f /etc/lorawan-cloud/mosquitto/compose.yml config --quiet
sudo docker compose -f /etc/lorawan-cloud/mosquitto/compose.yml up -d
sudo docker compose -f /etc/lorawan-cloud/mosquitto/compose.yml ps
sudo docker compose -f /etc/lorawan-cloud/mosquitto/compose.yml logs --since=5m --tail=100
sudo ss -lntp | grep ':8884'
```

Pass only when the listener is on the intended private address and no cloud `:1883` listener exists.

## 9.6 Prove Mosquitto TLS and ACL before HAProxy

From an approved VPC host, use a staging client certificate:

```bash
mosquitto_pub \
  -h <MOSQUITTO_PRIVATE_IP> -p 8884 \
  --cafile <MQTT_CA> \
  --cert <STAGING_CLIENT_CERT> \
  --key <STAGING_CLIENT_KEY> \
  -t '<AUTHORIZED_TEST_TOPIC>' \
  -m 'mqtt-ha-preflight' -q 1
```

Then attempt one topic that the identity is **not** allowed to publish/read. The authorized operation must work and the cross-identity operation must be denied.

A successful TLS handshake alone is not enough; ACL direction must also be proven.

## 9.7 Add the HAProxy MQTT frontends

Use the **same preferred/backup ordering on every HAProxy host** so clients do not split across two unrelated brokers.

On `ha-01` and `ha-02`, add both frontends:

```haproxy
frontend mqtt_public
    mode tcp
    bind <THIS_HOST_ANCHOR_IP>:8883
    default_backend mosquitto_active_standby

frontend mqtt_internal
    mode tcp
    bind <THIS_HOST_PRIVATE_IP>:18883
    default_backend mosquitto_active_standby

backend mosquitto_active_standby
    mode tcp
    option tcp-check
    default-server inter 2s fall 3 rise 2
    server mosquitto-1 <HA01_PRIVATE_IP>:8884 check
    server mosquitto-2 <HA02_PRIVATE_IP>:8884 check backup
```

On `ha-03`, add **only** the private internal frontend plus the same backend:

```haproxy
frontend mqtt_internal
    mode tcp
    bind <HA03_PRIVATE_IP>:18883
    default_backend mosquitto_active_standby

backend mosquitto_active_standby
    mode tcp
    option tcp-check
    default-server inter 2s fall 3 rise 2
    server mosquitto-1 <HA01_PRIVATE_IP>:8884 check
    server mosquitto-2 <HA02_PRIVATE_IP>:8884 check backup
```

The runtime HAProxy check is intentionally a Layer-4 availability check. End-to-end certificate and ACL correctness is proven separately with actual MQTT clients because the broker requires client certificates.

Validate and reload on each affected host:

```bash
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sudo ss -lntp | grep -E ':(8883|18883)\b'
```

Expected:

```text
ha-01: 8883 + 18883
ha-02: 8883 + 18883
ha-03: 18883 only
```

## 9.8 Internal MQTT naming

Map this name to the **local HAProxy host** for each local application:

```text
mqtt-ha.internal.<DOMAIN>
```

```text
ChirpStack-1 -> ha-01 private IP
ChirpStack-2 -> ha-02 private IP
Node-RED     -> ha-03 private IP
```

All three then use:

```text
ssl://mqtt-ha.internal.<DOMAIN>:18883
```

HAProxy forwards the TLS bytes unchanged to the active Mosquitto backend. The broker certificate therefore needs the shared SAN `mqtt-ha.internal.<DOMAIN>`.

**Why ha-03 also gets this frontend:** Node-RED needs ChirpStack application MQTT events. HAProxy already exists on `ha-03` for the database path, so adding the private MQTT listener avoids pinning Node-RED to `ha-01` or `ha-02` and costs no extra Droplet.

## 9.9 MQTT failover rehearsal

Before moving on to ChirpStack HA:

1. verify `Mosquitto-1` is the selected backend from all three HAProxy hosts;
2. connect one staging MQTT client through `mqtt-ha.internal.<DOMAIN>:18883`;
3. publish/receive one authorized test message;
4. stop **Mosquitto-1 only**;
5. record the stop timestamp;
6. wait for HAProxy to mark it unavailable;
7. reconnect the staging client without changing hostname, certificate, or port;
8. prove `Mosquitto-2` serves the connection;
9. restart Mosquitto-1;
10. verify it is healthy and returns to preferred status;
11. confirm no broker is unintentionally listening on cloud `1883`.

Later, repeat the same failure using the physical gateway and its local QoS 1 queue.

Do not call this broker-state replication. Mosquitto-1 and Mosquitto-2 do not share sessions or queues.

## 9.10 Prepare Valkey storage and certificates

Run on **all three hosts**:

```bash
sudo install -d -m 750 /etc/lorawan-cloud/valkey
sudo install -d -m 750 /etc/lorawan-pki/valkey
sudo install -d -m 700 /srv/valkey/data
sudo install -d -m 750 /srv/valkey/sentinel
```

Use one protected long random application/replication secret for this tiny POC and a separate Sentinel-administration secret. Keep them outside Git and shell history.

## 9.11 Configure the initial Valkey primary and replicas

Use `ha-01` as the **bootstrap primary only**. Sentinel may later promote either replica.

Common secure baseline, adapted per host:

```conf
bind <THIS_HOST_PRIVATE_IP>
protected-mode yes
port 0
tls-port 6379

tls-cert-file /run/valkey-tls/server.crt
tls-key-file /run/valkey-tls/server.key
tls-ca-cert-file /run/valkey-tls/ca.crt
tls-auth-clients no
tls-replication yes

requirepass <VALKEY_SECRET>
masterauth <VALKEY_SECRET>

appendonly yes
appendfsync everysec
maxmemory 128mb
maxmemory-policy noeviction
```

On `ha-02` and `ha-03`, additionally configure:

```conf
replicaof <HA01_PRIVATE_IP> 6379
```

Do not configure `replicaof` on the bootstrap primary `ha-01`.

`noeviction` is deliberate for the POC: memory exhaustion should fail visibly instead of silently discarding state.

If the pinned Valkey version uses ACLs instead of the password-only baseline, use a named least-privilege application/replication user and configure Sentinel authentication consistently. Do not mix incompatible ACL/password schemes accidentally.

## 9.12 Configure Sentinel on all three hosts

Create a writable `sentinel.conf` per host. Sentinel rewrites this file as topology changes, so do not mount it read-only.

Baseline:

```conf
bind <THIS_HOST_PRIVATE_IP>
protected-mode yes
port 0
tls-port 26379

tls-cert-file /run/valkey-tls/server.crt
tls-key-file /run/valkey-tls/server.key
tls-ca-cert-file /run/valkey-tls/ca.crt
tls-auth-clients no
tls-replication yes

requirepass <SENTINEL_SECRET>

sentinel monitor lorawan-valkey <HA01_PRIVATE_IP> 6379 2
sentinel auth-pass lorawan-valkey <VALKEY_SECRET>
sentinel down-after-milliseconds lorawan-valkey 5000
sentinel failover-timeout lorawan-valkey 60000
sentinel parallel-syncs lorawan-valkey 1
```

The `2` in `sentinel monitor` is the failure-detection quorum. Actual failover also needs a majority of the three Sentinel processes to authorize a leader for the failover.

Keep the Sentinel configuration/state path persistent and writable.

## 9.13 Run Valkey and Sentinel

Use the pinned Valkey image or package. If containerized, use stable host networking so Sentinel advertises the real VPC addresses instead of NAT-remapped container addresses.

A per-host container intent is:

```yaml
services:
  valkey:
    image: <PINNED_VALKEY_IMAGE>
    network_mode: host
    restart: unless-stopped
    command: ["valkey-server", "/etc/valkey/valkey.conf"]
    volumes:
      - /etc/lorawan-cloud/valkey/valkey.conf:/etc/valkey/valkey.conf:ro
      - /etc/lorawan-pki/valkey:/run/valkey-tls:ro
      - /srv/valkey/data:/data

  sentinel:
    image: <PINNED_VALKEY_IMAGE>
    network_mode: host
    restart: unless-stopped
    command: ["valkey-server", "/var/lib/valkey-sentinel/sentinel.conf", "--sentinel"]
    volumes:
      - /srv/valkey/sentinel:/var/lib/valkey-sentinel
      - /etc/lorawan-pki/valkey:/run/valkey-tls:ro
```

Place the host's writable `sentinel.conf` under `/srv/valkey/sentinel/` with ownership matching the image runtime user.

Validate the pinned image's binary/config paths before start.

## 9.14 Verify Valkey replication and Sentinel quorum

From an approved host with `valkey-cli`, use TLS and protected password input.

Check each data node:

```bash
valkey-cli --tls \
  --cacert <VALKEY_CA> \
  -h <VALKEY_PRIVATE_IP> -p 6379 \
  -a '<LOAD_FROM_PROTECTED_SOURCE>' ROLE
```

Normal initial state:

```text
ha-01 -> master/primary
ha-02 -> slave/replica
ha-03 -> slave/replica
```

Then query each Sentinel:

```bash
valkey-cli --tls \
  --cacert <VALKEY_CA> \
  -h <SENTINEL_PRIVATE_IP> -p 26379 \
  -a '<LOAD_SENTINEL_SECRET_PROTECTED>' \
  SENTINEL CKQUORUM lorawan-valkey
```

Pass only when all three Sentinels agree on the same primary and `CKQUORUM` reports enough Sentinels for quorum and failover authorization.

## 9.15 Add HAProxy Valkey primary routing on ha-01 and ha-02

ChirpStack needs a stable writable-primary endpoint:

```text
valkey-ha.internal.<DOMAIN>:16379
```

Add this on `ha-01` and `ha-02`:

```haproxy
frontend valkey_primary
    mode tcp
    bind <THIS_APP_PRIVATE_IP>:16379
    default_backend valkey_primary_nodes

backend valkey_primary_nodes
    mode tcp
    option tcp-check
    tcp-check send AUTH\ <VALKEY_SECRET>\r\n
    tcp-check expect string +OK
    tcp-check send INFO\ replication\r\n
    tcp-check expect string role:master
    default-server inter 2s fall 3 rise 2
    server valkey-1 <HA01_PRIVATE_IP>:6379 check check-ssl verify required ca-file /etc/lorawan-pki/valkey/ca.crt check-sni valkey-ha.internal.<DOMAIN>
    server valkey-2 <HA02_PRIVATE_IP>:6379 check check-ssl verify required ca-file /etc/lorawan-pki/valkey/ca.crt check-sni valkey-ha.internal.<DOMAIN>
    server valkey-3 <HA03_PRIVATE_IP>:6379 check check-ssl verify required ca-file /etc/lorawan-pki/valkey/ca.crt check-sni valkey-ha.internal.<DOMAIN>
```

The password-only POC baseline uses the same protected `<VALKEY_SECRET>` for this health check because `requirepass` provides only that password. Store the rendered HAProxy file with restrictive permissions and never commit the real secret. If the later ACL-based Valkey profile creates a dedicated health user, change the check to the version-appropriate `AUTH <USER> <PASSWORD>` form and grant only what `INFO replication` needs.

The important check is the `INFO replication` response containing `role:master`; a simple PING would also mark replicas healthy and could route ChirpStack writes to the wrong node.

Validate the exact `check-ssl` / `check-sni` syntax against the pinned HAProxy version before reload.

## 9.16 Verify the HAProxy Valkey endpoint

On each app host:

```bash
valkey-cli --tls \
  --cacert /etc/lorawan-pki/valkey/ca.crt \
  -h valkey-ha.internal.<DOMAIN> -p 16379 \
  -a '<LOAD_FROM_PROTECTED_SOURCE>' ROLE
```

Expected role: primary/master.

Now perform the controlled failover test:

1. record the current primary and replication offsets;
2. stop only the current Valkey primary;
3. record the failure timestamp;
4. watch all three Sentinel logs/state;
5. wait for Sentinel to promote a replica;
6. query `valkey-ha.internal.<DOMAIN>:16379` again without changing hostname or port;
7. verify it reports the new primary;
8. restart the old node;
9. verify it rejoins as a replica;
10. verify all three Sentinels agree again before continuing.

## 9.17 Final acceptance

MQTT passes when:

- Mosquitto-1/2 use matching CA/ACL policy and unique server keys;
- cloud brokers have no plaintext `1883` listener;
- public `8883` belongs to the HAProxy anchor listener reached through the Reserved IPv4, while brokers use private TLS `8884`;
- HAProxy uses deterministic Mosquitto-1 preferred / Mosquitto-2 backup ordering on every host;
- gateway, ChirpStack, and Node-RED validate broker TLS and use least-privilege identities;
- one broker loss requires no hostname/certificate/topic change.

Valkey passes when:

- there is one primary and two replicas;
- three Sentinels report quorum 2 and the same primary;
- Valkey/Sentinel ports are private and TLS-protected;
- HAProxy exposes only the current writable primary to ChirpStack;
- a primary loss is automatically promoted and the old node returns as a replica;
- no manual ChirpStack endpoint edit is required.

## 9.18 Phase 8 Execution Record - MQTT Foundation Deployment

Recorded deployment evidence:

```text
Date:
2026-08-24

MQTT baseline discovery:

ulc-01
10.104.0.2

ulc-02
10.104.0.4

ulc-03
10.104.0.8

Before installation:
- no MQTT packages installed
- no Valkey packages installed
- no MQTT listeners
- no Valkey listeners
- no MQTT/Valkey containers
- no MQTT/Valkey services

Mosquitto deployment:

Installed:
- mosquitto
- mosquitto-clients

Verified:
- Mosquitto version: 2.0.18
- MQTT protocol support: MQTT v5.0/v3.1.1/v3.1

Service state:

ulc-01:
mosquitto.service active (running)

ulc-02:
mosquitto.service active (running)

Result:
MQTT broker foundation installed successfully on the first two application nodes.
```

Next validation steps:

1. Configure Mosquitto TLS listeners.
2. Deploy MQTT CA and broker certificates.
3. Configure MQTT authentication and ACLs.
4. Validate broker-to-client TLS.
5. Add HAProxy MQTT routing.
6. Continue with Valkey deployment.

## 9.19 Phase 8 MQTT TLS Foundation Precheck Record

Executed on:

```text
ulc-01
10.104.0.2

ulc-02
10.104.0.4
```

Discovery results:

```text
Mosquitto:
- installed
- active
- enabled

MQTT PKI:
- /etc/lorawan-pki/mqtt does not exist yet

Existing PKI:
- PostgreSQL TLS present
- PgBouncer TLS present
- MQTT TLS material not issued yet
```

Current listeners before TLS configuration:

```text
ulc-01:
127.0.0.1:1883
[::1]:1883

ulc-02:
127.0.0.1:1883
[::1]:1883
```

Interpretation:

- Mosquitto is running in the default local-only state.
- No cloud MQTT listener is exposed.
- No TLS listener exists yet.
- No plaintext remote MQTT exposure exists.

Next execution step:

1. Issue MQTT broker certificates from the project CA.
2. Install `/etc/lorawan-pki/mqtt` on broker nodes.
3. Replace local-only Mosquitto configuration with TLS listener configuration.
4. Validate mutual TLS before HAProxy integration.

Operational note:

Gateway client certificate provisioning is intentionally deferred until the final onboarding stage. Cloud MQTT broker TLS identities must be completed, HAProxy routing must be validated, Valkey and ChirpStack integration must be operational, and production cloud-side testing must pass before issuing gateway certificates.

Certificate separation:

- Broker certificates remain only on cloud MQTT nodes.
- Gateway certificates are separate client identities.
- Broker private keys are never transferred to gateways.

Automation preference:

Deployment steps should use chained command blocks where safe. Validation, backup, permission checks, and installation actions should be grouped into reproducible runbooks instead of many isolated commands.

## Deployment ordering decision - Gateway certificate provisioning

Gateway MQTT client certificate provisioning is intentionally moved to the final deployment stage.

Reason:

- Cloud MQTT infrastructure must be completed and validated first.
- Mosquitto TLS, HAProxy routing, ACL policies, ChirpStack integration, and monitoring must exist before issuing gateway identities.
- Gateway certificates are production client credentials and should only be generated when the receiving MQTT service is ready.
- This prevents issuing gateway credentials against an unfinished broker architecture.

Final order:

```text
1. Cloud foundation
   - etcd
   - Spilo/Patroni PostgreSQL HA
   - HAProxy
   - PgBouncer

2. Cloud application services
   - Mosquitto TLS
   - Valkey
   - ChirpStack
   - integrations

3. Cloud validation
   - TLS verification
   - failover testing
   - ACL testing
   - backup/recovery testing

4. Final gateway onboarding
   - issue gateway client certificate
   - install gateway CA/client certificate/key
   - configure MQTT Forwarder
   - validate end-to-end uplink
```

Gateway certificate provisioning must not begin before the cloud MQTT stack passes acceptance testing.

## 9.20 Phase 8B - MQTT HAProxy TLS Access Layer Execution Record

Objective:

Create a single MQTT TLS endpoint for gateways while keeping TLS termination on Mosquitto brokers.

Final design:

```text
Gateway clients
      |
      | MQTT TLS :8883
      |
HAProxy TCP passthrough
ulc-01 :8883
      |
      +----------------+
      |                |
      v                v
ulc-01 Mosquitto    ulc-02 Mosquitto
TLS :8884           TLS :8884
```

Important design decision:

- HAProxy does not terminate MQTT TLS.
- Mosquitto retains broker certificates and private keys.
- HAProxy only forwards encrypted TCP traffic.
- Gateway certificates remain deferred until final onboarding.

### 9.20.1 HAProxy baseline check

Executed on ulc-01:

```bash
systemctl is-active haproxy
systemctl is-enabled haproxy
ss -H -lntp | grep haproxy
```

Existing services preserved:

```text
PostgreSQL primary:
15432

PostgreSQL replicas:
15433
```

### 9.20.2 Initial HAProxy MQTT configuration attempt

The first configuration attempted:

```haproxy
frontend mqtt_tls
    bind 10.104.0.2:8883

backend mqtt_brokers
    server mqtt-ulc01 10.104.0.2:8883 check
    server mqtt-ulc02 10.104.0.4:8883 check
```

Validation passed:

```bash
haproxy -c -f /etc/haproxy/haproxy.cfg
```

Runtime failed because Mosquitto already owned port 8883:

```text
cannot bind socket
Address already in use
```

Correction:

- HAProxy owns the external MQTT port.
- Mosquitto moves to an internal TLS port.

### 9.20.3 Move Mosquitto internal TLS listener

Mosquitto configuration changed:

Before:

```conf
listener 8883
```

After:

```conf
listener 8884

cafile /etc/lorawan-pki/mqtt/ca.crt
certfile /etc/lorawan-pki/mqtt/server.crt
keyfile /etc/lorawan-pki/mqtt/server.key

tls_version tlsv1.3
require_certificate false
```

Restart:

```bash
systemctl restart mosquitto
```

Validation:

```bash
ss -H -lntp | grep mosquitto
```

Expected:

```text
0.0.0.0:8884
[::]:8884
```

### 9.20.4 Final HAProxy MQTT configuration

Backup first:

```bash
cp /etc/haproxy/haproxy.cfg \
/etc/haproxy/haproxy.cfg.phase8b-before-$(date -u +%Y%m%d-%H%M%S)
```

Configuration added:

```haproxy
frontend mqtt_tls
    bind 10.104.0.2:8883
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

Validate:

```bash
haproxy -c -f /etc/haproxy/haproxy.cfg
```

Restart:

```bash
systemctl restart haproxy
```

Final listeners:

```text
HAProxy:
10.104.0.2:8883

Mosquitto:
ulc-01 :8884
ulc-02 :8884
```

### 9.20.5 MQTT HA TLS validation

Client validation performed from ulc-03:

```bash
openssl s_client \
-connect 10.104.0.2:8883 \
-CAfile /etc/lorawan-pki/mqtt/ca.crt \
-verify_hostname mqtt.internal.lorawan.com \
-brief \
</dev/null
```

Result:

```text
Protocol version: TLSv1.3
Cipher: TLS_AES_256_GCM_SHA384
Verification: OK
Verified peername: mqtt.internal.lorawan.com
```

PASS:

- HAProxy TLS passthrough
- broker certificate validation
- MQTT TLS endpoint

### 9.20.6 MQTT failover validation

Failure test:

Stop ulc-01 broker:

```bash
systemctl stop mosquitto
```

HAProxy detected failure:

```text
Server mqtt_brokers/mqtt-ulc01 is DOWN
reason: Layer4 connection problem
```

Client test through HAProxy remained successful:

```text
Verification: OK
Verified peername: mqtt.internal.lorawan.com
```

Recovery:

```bash
systemctl start mosquitto
```

HAProxy recovered the backend:

```text
Server mqtt_brokers/mqtt-ulc01 is UP
reason: Layer4 check passed
2 active and 0 backup servers online
```

Phase 8B result:

```text
MQTT HAProxy endpoint        PASS
TLS passthrough              PASS
ulc-01 Mosquitto backend     PASS
ulc-02 Mosquitto backend     PASS
Failover detection           PASS
Service recovery             PASS
```

## 9.21 Phase 8C - Valkey HA Deployment Execution Record

Objective:

Deploy the ChirpStack shared state backend using Valkey with future Sentinel-based high availability.

Execution boundary:

- Valkey deployment started after MQTT HA completion.
- Gateway provisioning remains deferred until cloud services are complete.
- No ChirpStack integration changes are performed until Valkey HA passes validation.
- No Git commit or push is performed during deployment sessions. Operator performs final review and commit.

Final intended architecture:

```text
                 ChirpStack
                     |
                     |
              HAProxy Valkey endpoint
                     |
                     |
              Current Valkey primary
                     |
        +------------+------------+
        |                         |
        v                         v

    Valkey replica            Valkey replica

    Sentinel quorum:
    ulc-01
    ulc-02
    ulc-03
```

## 9.21.1 Valkey foundation precheck

Validated nodes:

```text
ulc-01
10.104.0.2

ulc-02
10.104.0.4

ulc-03
10.104.0.8
```

Validation performed:

```text
Redis/Valkey packages:
none installed

Redis/Valkey services:
none configured

Listeners:
6379 unavailable
26379 unavailable
```

Resource validation:

```text
ulc-01:
RAM 1.9Gi
Available 1.3Gi

ulc-02:
RAM 1.9Gi
Available 1.4Gi

ulc-03:
RAM 1.9Gi
Available 1.4Gi
```

Result:

```text
Phase 8C.1 Foundation Precheck: PASS
```

## 9.21.2 Valkey package installation

Deployment automation:

```bash
ssh \
-i /root/.ssh/cloud-deployment-phase8 \
-o IdentitiesOnly=yes \
opsadmin@NODE
```

The deployment key is required for multi-node automation. Do not rely on default SSH keys.

Installed package:

```text
valkey-server
valkey-tools
```

Version installed:

```text
Valkey 7.2.13
```

## 9.21.3 Installation status checkpoint

### ulc-01

Status:

```text
PASS
```

Verified:

```text
valkey-server installed
service active
service enabled
```

Listener:

```text
127.0.0.1:6379
[::1]:6379
```

### ulc-02

Status:

```text
PASS
```

Verified:

```text
valkey-server installed
service active
service enabled
```

Listener:

```text
127.0.0.1:6379
[::1]:6379
```

### ulc-03

Status:

```text
PENDING
```

Reason:

Non-interactive sudo automation was not available during the first installation attempt:

```text
sudo: a terminal is required to read the password
sudo: a password is required
```

Impact:

```text
Valkey not installed on ulc-03
Valkey replication not configured
Sentinel not deployed
```

## 9.21.4 Next execution step

Before continuing:

1. Restore non-interactive sudo automation on ulc-03.
2. Install Valkey on ulc-03.
3. Verify all three Valkey services are active.
4. Configure TLS/authentication.
5. Configure replication.
6. Deploy Sentinel quorum.
7. Add HAProxy writable-primary routing.
8. Perform Valkey failover testing.

Acceptance criteria:

```text
Three Valkey nodes installed
One primary
Two replicas
Three Sentinel members
Automatic promotion tested
HAProxy follows writable primary
```

## Deployment documentation rule

All executed commands, configuration decisions, validation output, failures, and corrections must be recorded in this MDS before repository commit.

The operator performs the final Git commit and push after review.

Next: [10-chirpstack-cloud-cluster.md](10-chirpstack-cloud-cluster.md).
