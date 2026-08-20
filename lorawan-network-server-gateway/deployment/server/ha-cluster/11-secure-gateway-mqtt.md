# Server 11. Secure Gateway MQTT with Mutual TLS

## Goal

Keep two separate Mosquitto access paths on the same broker container:

```text
Docker application network
  ChirpStack / Node-RED
    -> tcp://mosquitto:1883
    -> username/password + ACL
    -> not published on the VM host

  Gateway MQTT evidence collector, when reviewed implementation exists
    -> tcp://mosquitto:1883
    -> separate username/password + read-only gateway-event ACL
    -> no publish permission

Physical gateways
  gateway-local Mosquitto bridge
    -> ssl://<MQTT_BROKER_FQDN>:8883
    -> broker certificate + required client certificate
    -> certificate CN becomes MQTT username
    -> exact Gateway-EUI ACL

Gateway evidence uploader, when v2 exists
  -> separate HTTPS/mTLS endpoint on TCP 443
  -> not carried through MQTT 8883
```

Only TCP `8883` is published to the gateway network. ChirpStack does **not** need an MQTT client certificate in this single-VM lab because it stays on the Docker-internal authenticated listener `1883`.

The next manual issues one client certificate per physical gateway and proves positive mTLS authentication plus cross-gateway ACL denial.

## Before you begin

Run on the **lab server VM** after [Server 10](10-deploy-chirpstack.md).

Confirm:

```text
Project directory: /opt/lorawan-lab
MQTT broker FQDN: <MQTT_BROKER_FQDN>
Broker bind address: <BROKER_BIND_ADDRESS>
Region topic prefix: <CONFIRMED_REGION_TOPIC_PREFIX>
Pinned Mosquitto image: ${MOSQUITTO_IMAGE}
Protected PKI backup location: <MQTT_PKI_BACKUP_LOCATION>
```

Check current service health:

```bash
cd /opt/lorawan-lab
docker compose ps mosquitto chirpstack
docker compose logs --since=5m --tail=100 mosquitto chirpstack
```

Confirm DNS from the gateway network before certificate issuance:

```bash
getent hosts <MQTT_BROKER_FQDN>
```

The name must resolve to the lab server address the physical gateway can reach.

## Step 1 - Inspect the pinned Mosquitto version

Run:

```bash
cd /opt/lorawan-lab
. ./.env
docker run --rm "$MOSQUITTO_IMAGE" mosquitto -h 2>&1 | head -20
docker image inspect "$MOSQUITTO_IMAGE" --format '{{json .RepoDigests}}'
```

Record the observed version and immutable image reference.

Mosquitto authentication/ACL directives can change between releases. The configuration below is a Mosquitto 2.x pattern. If the pinned release deprecates file ACLs or listener directives, adapt it to the supported equivalent and keep the same security result.

## Step 2 - Create the protected MQTT PKI workspace

Run on the lab server VM:

```bash
sudo install -d -m 700 \
  /root/lorawan-lab-pki/mqtt-ca \
  /root/lorawan-lab-pki/mqtt-server \
  /root/lorawan-lab-pki/client-work

sudo install -d -m 750 \
  /opt/lorawan-lab/configuration/mosquitto/certs
```

The boundary is:

```text
/root/lorawan-lab-pki/mqtt-ca/ca.key
  -> CA signing key
  -> protected backup only
  -> never mounted into Mosquitto

/root/lorawan-lab-pki/mqtt-ca/ca.crt
  -> public trust anchor

/root/lorawan-lab-pki/mqtt-server/server.key
  -> broker runtime private key source

/root/lorawan-lab-pki/mqtt-server/server.crt
  -> broker runtime certificate source

/root/lorawan-lab-pki/client-work/
  -> temporary gateway certificate issuance workspace used by Server 12
```

## Step 3 - Create the lab MQTT CA

Run:

```bash
sudo -i
umask 077
cd /root/lorawan-lab-pki

openssl genrsa -out mqtt-ca/ca.key 4096
openssl req -x509 -new -sha256 -days 825 \
  -key mqtt-ca/ca.key \
  -out mqtt-ca/ca.crt \
  -subj '/CN=LoRaWAN MQTT Lab CA'

openssl x509 -in mqtt-ca/ca.crt -noout \
  -subject -issuer -serial -dates -fingerprint -sha256
exit
```

Expected result:

- subject and issuer identify `LoRaWAN MQTT Lab CA`;
- the certificate has a valid date range;
- a SHA-256 fingerprint is printed.

Keep the fingerprint with the protected recovery record. Do not copy `ca.key` to Git, the physical gateway, or any container volume.

## Step 4 - Issue the broker server certificate

Run:

```bash
sudo -i
umask 077
cd /root/lorawan-lab-pki

openssl genrsa -out mqtt-server/server.key 3072
openssl req -new \
  -key mqtt-server/server.key \
  -out mqtt-server/server.csr \
  -subj '/CN=<MQTT_BROKER_FQDN>'

cat > mqtt-server/server.ext <<'EOF'
subjectAltName=DNS:<MQTT_BROKER_FQDN>
extendedKeyUsage=serverAuth
keyUsage=digitalSignature,keyEncipherment
EOF

openssl x509 -req -sha256 -days 397 \
  -in mqtt-server/server.csr \
  -CA mqtt-ca/ca.crt \
  -CAkey mqtt-ca/ca.key \
  -CAcreateserial \
  -out mqtt-server/server.crt \
  -extfile mqtt-server/server.ext

openssl verify \
  -CAfile mqtt-ca/ca.crt \
  mqtt-server/server.crt

openssl x509 \
  -in mqtt-server/server.crt \
  -noout -subject -issuer -serial -dates -ext subjectAltName
exit
```

Expected verification:

```text
mqtt-server/server.crt: OK
```

The Subject Alternative Name must contain exactly the DNS name gateways will use. Do not fix hostname failures by disabling verification on the gateway.

When an approved client intentionally connects by IP address, add that IP to the SAN before signing. Prefer the stable DNS name for the normal gateway bridge.

## Step 5 - Verify the broker certificate and private key match

Run:

```bash
CERT_PUB=$(openssl x509 \
  -in /root/lorawan-lab-pki/mqtt-server/server.crt \
  -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum)

KEY_PUB=$(sudo openssl pkey \
  -in /root/lorawan-lab-pki/mqtt-server/server.key \
  -pubout -outform DER | sha256sum)

printf 'certificate: %s\nkey:         %s\n' "$CERT_PUB" "$KEY_PUB"
unset CERT_PUB KEY_PUB
```

The two hashes must match.

## Step 6 - Install only the broker runtime PKI files

Run:

```bash
cd /opt/lorawan-lab

sudo install -m 0644 \
  /root/lorawan-lab-pki/mqtt-ca/ca.crt \
  configuration/mosquitto/certs/mqtt-ca.crt

sudo install -m 0644 \
  /root/lorawan-lab-pki/mqtt-server/server.crt \
  configuration/mosquitto/certs/server.crt

sudo install -m 0600 \
  /root/lorawan-lab-pki/mqtt-server/server.key \
  configuration/mosquitto/certs/server.key
```

Verify that the signing key was not copied into the runtime directory:

```bash
test ! -e configuration/mosquitto/certs/ca.key
find configuration/mosquitto/certs -maxdepth 1 -type f -printf '%m %u:%g %p\n'
```

Expected runtime files:

```text
mqtt-ca.crt
server.crt
server.key
```

## Step 7 - Confirm the internal broker identities and ACL

The ChirpStack identity was created in [Server 10](10-deploy-chirpstack.md). Node-RED adds its own identity later.

Inspect without printing password hashes unnecessarily:

```bash
cd /opt/lorawan-lab
grep -q '^chirpstack:' configuration/mosquitto/passwd \
  && echo 'chirpstack broker identity present' \
  || echo 'chirpstack broker identity missing'

grep -n '^user chirpstack$' configuration/mosquitto/acl
```

The ACL block must include only the required region gateway topics and application integration topics:

```text
user chirpstack
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/event/#
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/state/#
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/command/#
topic write application/+/device/+/event/#
topic read application/+/device/+/command/#
```

Gateway-specific identity blocks are appended in Server 12. Do not grant `#` to a gateway or application client.

### Optional future v2 gateway-event collector identity

Create this identity **only when the reviewed gateway MQTT evidence collector is ready to deploy**. Do not create an unused credential just to match the documentation.

Its minimum ACL is:

```text
user gateway_evidence_collector
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/event/#
```

It does not need gateway `state/#`, `command/#`, application command topics, or any MQTT write permission. Keep it on Docker-internal authenticated `1883`; it is a server-side witness of what the broker received, not a physical-gateway certificate identity.

## Step 8 - Configure the two Mosquitto listeners

Edit:

```text
/opt/lorawan-lab/configuration/mosquitto/mosquitto.conf
```

Use the syntax supported by the pinned Mosquitto version. Mosquitto 2.x example:

```conf
persistence true
persistence_location /mosquitto/data/
log_dest stdout
per_listener_settings true

# Internal application listener.
# Docker-only: no host port mapping.
listener 1883
protocol mqtt
allow_anonymous false
password_file /mosquitto/config/passwd
acl_file /mosquitto/config/acl

# Physical gateway listener.
# Host publishes only this listener.
listener 8883
protocol mqtt
cafile /mosquitto/config/certs/mqtt-ca.crt
certfile /mosquitto/config/certs/server.crt
keyfile /mosquitto/config/certs/server.key
require_certificate true
use_identity_as_username true
allow_anonymous false
queue_qos0_messages false
acl_file /mosquitto/config/acl
tls_version tlsv1.2
```

The two listeners deliberately use different authentication mechanisms:

```text
1883 -> Docker network + password identity + ACL
8883 -> TLS client certificate CN + ACL
```

Do not enable anonymous access on either listener.

## Step 9 - Publish only host TCP 8883

In the Mosquitto Compose service, add only:

```yaml
ports:
  - "<BROKER_BIND_ADDRESS>:8883:8883"
```

Do not publish `1883`.

Validate the rendered Compose project:

```bash
cd /opt/lorawan-lab
docker compose config --quiet
docker compose config > /tmp/lorawan-lab.rendered.yml
```

Inspect Mosquitto port mappings:

```bash
grep -n -A12 -B4 'mosquitto:' /tmp/lorawan-lab.rendered.yml
```

Pass condition: host port `8883` is present and host port `1883` is absent.

## Step 10 - Restart Mosquitto and verify listeners

Run:

```bash
cd /opt/lorawan-lab
docker compose restart mosquitto
docker compose ps mosquitto
docker compose logs --since=3m --tail=200 mosquitto
```

On the VM host:

```bash
sudo ss -lntp | grep ':8883'
sudo ss -lntp | grep ':1883' || true
```

Expected host result:

```text
8883 -> listening on <BROKER_BIND_ADDRESS>
1883 -> no host-published listener
```

Confirm ChirpStack still connects through Docker-internal `1883`:

```bash
docker compose logs --since=3m --tail=200 chirpstack mosquitto
```

A working external `8883` listener that breaks ChirpStack's internal MQTT connection is not a valid configuration.

## Step 11 - Verify the server certificate from the gateway network

From an administration host on the gateway network, copy only the public CA certificate for this test and run:

```bash
openssl s_client \
  -connect <MQTT_BROKER_FQDN>:8883 \
  -servername <MQTT_BROKER_FQDN> \
  -CAfile mqtt-ca.crt \
  -verify_return_error </dev/null
```

Expected TLS evidence:

- the server certificate chains to the lab CA;
- the certificate is valid for `<MQTT_BROKER_FQDN>`;
- the broker requests a client certificate;
- the connection does not become an authorized MQTT session without one.

This is the required negative mTLS test. The **positive** client-certificate test is performed after Server 12 issues the real gateway identity.

## Step 12 - Verify the firewall boundary

Run on the lab server VM:

```bash
sudo ufw status verbose
sudo ss -lntup
```

Required gateway-facing boundary:

```text
TCP 8883 -> allowed only from the approved gateway address/subnet
TCP 1883 -> not host-published
TCP 5432 -> not host-published
TCP 6432 -> not host-published
TCP 6379 -> not host-published
UDP 1700 -> no listener
```

Do not rely on UFW alone for an accidentally published Docker port. The Compose service itself must avoid publishing internal ports.

## Verify

Before continuing, all of these must pass:

- broker certificate SAN contains `<MQTT_BROKER_FQDN>`;
- broker certificate and private key match;
- CA private key is absent from runtime mounts;
- Mosquitto internal listener `1883` remains Docker-only;
- Mosquitto external listener `8883` requires a client certificate;
- host publishes `8883` and does not publish `1883`;
- ChirpStack remains connected to `mosquitto:1883`;
- a connection without a client certificate is not authorized;
- UFW permits `8883` only from the intended gateway source;
- protected off-VM PKI recovery exists or is scheduled before commissioning;
- when the v2 collector is deployed, its Docker-internal identity is read-only for approved gateway event topics and cannot publish them;
- the separate gateway evidence checkpoint/segment API is not exposed through this MQTT listener.

## Troubleshooting

### Broker certificate verifies by CA but hostname validation fails

Reissue the server certificate with `<MQTT_BROKER_FQDN>` in the SAN. Do not configure `bridge_insecure true` on the gateway.

### ChirpStack disconnects after enabling `per_listener_settings`

Verify the `1883` listener still has `password_file` and `acl_file`, the `chirpstack` password entry exists, and ChirpStack is configured for `tcp://mosquitto:1883` rather than `ssl://mosquitto:8883`.

### A client without a certificate reaches the gateway listener

Inspect the active listener and rendered config. `listener 8883` must include `require_certificate true` and `allow_anonymous false`.

### Host port 1883 appears in `ss`

Inspect `docker compose config` for a Mosquitto `1883:1883` mapping and remove it. Do not use a host firewall rule as a substitute for removing an unnecessary published port.

### Mosquitto cannot read `server.key`

Inspect the pinned image's runtime UID/GID and the bind-mounted file permissions. Grant only the minimum group/read permission needed by the broker; do not make the key world-readable.

## Next step

Continue with [12-provision-gateway-mqtt-identity.md](12-provision-gateway-mqtt-identity.md). That manual issues the real per-gateway certificate, appends the exact Gateway-EUI ACL, performs the positive mTLS test, and transfers the certificate bundle to Gateway OS.
