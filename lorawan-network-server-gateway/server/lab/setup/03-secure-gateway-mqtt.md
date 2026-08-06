# Server 3. Secure Gateway MQTT with Mutual TLS

Mosquitto is the only gateway-facing service. It accepts MQTT over TLS on TCP 8883 and requires a valid client certificate.

```text
Gateway local Mosquitto bridge -> ssl://<MQTT_BROKER_FQDN>:8883 -> remote Mosquitto
ChirpStack gateway backend     -> ssl://mosquitto:8883            -> remote Mosquitto
```

## Step 1: Confirm the broker and certificate inputs

Before creating certificates, resolve:

```text
Mosquitto image, digest, and observed version
MQTT broker FQDN: <MQTT_BROKER_FQDN>
Broker bind/public address
Gateway source networks, when stable
Region topic prefix: <CONFIRMED_REGION_TOPIC_PREFIX>
Certificate lifetime and renewal window
Protected PKI backup location
```

`<MQTT_BROKER_FQDN>` must be the DNS name gateways use and the name placed in the server certificate SAN. `<CONFIRMED_REGION_TOPIC_PREFIX>` comes from the active ChirpStack region and must match Gateway OS. Keep the image/version only because Mosquitto authentication and ACL syntax can differ between releases.

Inspect the pinned Mosquitto version before choosing authentication directives. Mosquitto 2.1 deprecates some legacy file and per-listener directives in favor of plugins and listener-specific settings. Use the supported mechanism for the pinned image and test it before deployment.

## Step 2: Create a protected PKI workspace

For an isolated lab without an organizational PKI:

```bash
sudo install -d -m 700 \
  /root/lorawan-lab-pki/mqtt-ca \
  /root/lorawan-lab-pki/mqtt-server \
  /root/lorawan-lab-pki/client-work

sudo install -d -m 750 \
  /opt/chirpstack-docker/configuration/mosquitto/certs \
  /opt/chirpstack-docker/configuration/chirpstack/certs
```

Boundary:

```text
mqtt-ca/ca.key                -> protected signing key; never mounted
mqtt-ca/ca.crt                -> trust anchor
mqtt-server/server.key        -> Mosquitto runtime private key
mqtt-server/server.crt        -> Mosquitto runtime certificate
client-work/<identity>.key    -> temporary issuance workspace
client-work/<identity>.crt    -> unique client certificate
runtime mounts                -> only required CA, certificate, and key files
```

## Step 3: Create the lab CA

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

Keep the CA certificate SHA-256 fingerprint with the protected PKI backup so runtime trust files can be checked later. Do not copy `ca.key` to Git, the gateway, or a container volume.

## Step 4: Issue the broker certificate

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
subjectAltName=DNS:<MQTT_BROKER_FQDN>,IP:<BROKER_IP_ADDRESS>
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

openssl verify -CAfile mqtt-ca/ca.crt mqtt-server/server.crt
exit
```

The hostname configured in the gateway's local Mosquitto bridge must appear in the server certificate SAN. A healthy `openssl verify` result proves the certificate chains to this lab CA; a hostname mismatch will still fail at the client and must be corrected in the certificate or endpoint name, not bypassed.

## Step 5: Issue the ChirpStack client certificate

Use `chirpstack` as the certificate Common Name and MQTT username identity.

```bash
sudo -i
umask 077
cd /root/lorawan-lab-pki

openssl genrsa -out client-work/chirpstack.key 3072
openssl req -new \
  -key client-work/chirpstack.key \
  -out client-work/chirpstack.csr \
  -subj '/CN=chirpstack'

cat > client-work/chirpstack.ext <<'EOF'
extendedKeyUsage=clientAuth
keyUsage=digitalSignature
EOF

openssl x509 -req -sha256 -days 397 \
  -in client-work/chirpstack.csr \
  -CA mqtt-ca/ca.crt \
  -CAkey mqtt-ca/ca.key \
  -CAserial mqtt-ca/ca.srl \
  -out client-work/chirpstack.crt \
  -extfile client-work/chirpstack.ext

openssl verify -CAfile mqtt-ca/ca.crt client-work/chirpstack.crt
exit
```

Convert the ChirpStack private key to unencrypted PKCS#8 only in the protected runtime path when required by the pinned version:

```bash
sudo openssl pkcs8 -topk8 -nocrypt \
  -in /root/lorawan-lab-pki/client-work/chirpstack.key \
  -out /opt/chirpstack-docker/configuration/chirpstack/certs/chirpstack.key
```

## Step 6: Install Mosquitto runtime files

```bash
cd /opt/chirpstack-docker
sudo install -m 0644 /root/lorawan-lab-pki/mqtt-ca/ca.crt \
  configuration/mosquitto/certs/mqtt-ca.crt
sudo install -m 0644 /root/lorawan-lab-pki/mqtt-server/server.crt \
  configuration/mosquitto/certs/server.crt
sudo install -m 0600 /root/lorawan-lab-pki/mqtt-server/server.key \
  configuration/mosquitto/certs/server.key
```

Assert that the CA private key is absent:

```bash
test ! -e configuration/mosquitto/certs/ca.key
```

## Step 7: Install ChirpStack runtime files

```bash
cd /opt/chirpstack-docker
sudo install -m 0644 /root/lorawan-lab-pki/mqtt-ca/ca.crt \
  configuration/chirpstack/certs/mqtt-ca.crt
sudo install -m 0644 /root/lorawan-lab-pki/client-work/chirpstack.crt \
  configuration/chirpstack/certs/chirpstack.crt
```

Set the private-key owner and mode after resolving the effective container user. Replace the placeholders below with the numeric identity obtained from the pinned image; do not guess them:

```bash
sudo chown <CHIRPSTACK_RUNTIME_UID>:<CHIRPSTACK_RUNTIME_GID> \
  configuration/chirpstack/certs/chirpstack.key
sudo chmod 0640 configuration/chirpstack/certs/chirpstack.key
```

## Step 8: Create the broker ACL

Create `/opt/chirpstack-docker/configuration/mosquitto/acl` with the ChirpStack identity first:

```text
user chirpstack
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/event/#
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/state/#
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/+/command/#
topic write application/+/device/+/event/#
topic read application/+/device/+/command/#
```

Gateway-specific entries are added in the next guide. Do not grant `#` to gateways or application clients.

## Step 9: Configure Mosquitto

Use the syntax supported by the pinned Mosquitto image. A Mosquitto 2.x compatibility example is:

```conf
persistence true
persistence_location /mosquitto/data/
log_dest stdout

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

For Mosquitto 2.1 or newer, prefer the supported ACL plugin and listener-specific controls when the image includes them. Do not copy deprecated settings without checking the observed version.

## Step 10: Publish only TCP 8883

Mount certificates and ACL read-only. Publish:

```yaml
ports:
  - "<BROKER_BIND_ADDRESS>:8883:8883"
```

Do not publish 1883. Restrict the host and cloud firewall to approved gateway sources when stable; mutual TLS remains mandatory even when IP filtering is used.

## Step 11: Validate

```bash
cd /opt/chirpstack-docker
docker compose config --quiet
docker compose up -d mosquitto chirpstack
docker compose ps mosquitto chirpstack
docker compose logs --since=5m --tail=300 mosquitto chirpstack
sudo ss -lntp | grep ':8883'
```

First run a negative test without a client certificate:

```bash
openssl s_client \
  -connect <MQTT_BROKER_FQDN>:8883 \
  -servername <MQTT_BROKER_FQDN> \
  -CAfile /root/lorawan-lab-pki/mqtt-ca/ca.crt \
  -verify_return_error </dev/null
```

The broker must reject or terminate this unauthenticated session because `require_certificate` is enabled.

Then run an authenticated test with the ChirpStack client identity:

```bash
openssl s_client \
  -connect <MQTT_BROKER_FQDN>:8883 \
  -servername <MQTT_BROKER_FQDN> \
  -CAfile /root/lorawan-lab-pki/mqtt-ca/ca.crt \
  -cert /opt/chirpstack-docker/configuration/chirpstack/certs/chirpstack.crt \
  -key /opt/chirpstack-docker/configuration/chirpstack/certs/chirpstack.key \
  -verify_return_error </dev/null
```

The authenticated test must show a valid server chain and a completed client-certificate handshake. Broker logs must map the connection to the `chirpstack` identity.

Continue with [04-provision-gateway-mqtt-identity.md](04-provision-gateway-mqtt-identity.md).
