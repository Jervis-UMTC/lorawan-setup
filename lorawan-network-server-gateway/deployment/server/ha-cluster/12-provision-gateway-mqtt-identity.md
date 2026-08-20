# Server 12. Provision a Gateway MQTT Identity

Run this procedure once for every physical gateway after Concentratord reports a stable 16-hexadecimal Gateway EUI.

## Before you begin

Confirm the Gateway EUI, active region topic prefix, certificate lifetime, revocation method, protected recovery location, and secure transfer method. Do not issue the certificate from a guessed hostname or asset label.

Create one client certificate and one ACL entry for each Gateway OS gateway. The same certificate is used by the gateway's `cloud-uplink` and `cloud-downlink` Mosquitto bridge connections; they use separate client IDs but the same certificate identity.

## Step 1: Confirm the Gateway ID

Obtain the value from the **successful startup log of the active Concentratord chipset** on Gateway OS:

```sh
logread -e chirpstack-concentratord | tail -n 100
logread -e chirpstack-concentratord | grep -Ei 'gateway|eui|sx130|rak5146|error|fail'
```

Use the EUI from `Gateway ID retrieved, gateway_id: "<GATEWAY_EUI>"`. When the active chipset is SX1302/SX1303, do not issue a certificate from a stale `gateway_id` in an inactive SX1301 UCI section.

Validate the recorded value on the server:

```bash
printf '%s\n' '<GATEWAY_EUI>' | grep -Eq '^[0-9A-Fa-f]{16}$'
```

Confirm the physical gateway associated with the EUI, the matching region topic prefix, certificate lifetime, and encrypted recovery location. Do not issue a certificate for an unverified or duplicate Gateway EUI.

## Step 2: Issue the client certificate

The certificate Common Name must equal the 16-hexadecimal Gateway ID.

```bash
sudo -i
umask 077
cd /root/lorawan-lab-pki

openssl genrsa -out client-work/<GATEWAY_EUI>.key 3072
openssl req -new \
  -key client-work/<GATEWAY_EUI>.key \
  -out client-work/<GATEWAY_EUI>.csr \
  -subj '/CN=<GATEWAY_EUI>'

cat > client-work/<GATEWAY_EUI>.ext <<'EOF'
extendedKeyUsage=clientAuth
keyUsage=digitalSignature
EOF

openssl x509 -req -sha256 -days 397 \
  -in client-work/<GATEWAY_EUI>.csr \
  -CA mqtt-ca/ca.crt \
  -CAkey mqtt-ca/ca.key \
  -CAserial mqtt-ca/ca.srl \
  -out client-work/<GATEWAY_EUI>.crt \
  -extfile client-work/<GATEWAY_EUI>.ext

openssl verify -CAfile mqtt-ca/ca.crt client-work/<GATEWAY_EUI>.crt
openssl x509 -in client-work/<GATEWAY_EUI>.crt -noout \
  -subject -issuer -serial -dates -fingerprint -sha256
exit
```

## Step 3: Confirm the certificate and key match

```bash
CERT_PUB=$(openssl x509 \
  -in /root/lorawan-lab-pki/client-work/<GATEWAY_EUI>.crt \
  -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum)
KEY_PUB=$(openssl pkey \
  -in /root/lorawan-lab-pki/client-work/<GATEWAY_EUI>.key \
  -pubout -outform DER | sha256sum)
printf 'certificate: %s\nkey:         %s\n' "$CERT_PUB" "$KEY_PUB"
unset CERT_PUB KEY_PUB
```

The hashes must match.

## Step 4: Add the exact gateway ACL

Inspect the broker ACL before editing so repeated provisioning does not append duplicate gateway blocks:

```bash
grep -n -A4 -B1 '^user <GATEWAY_EUI>$' /opt/lorawan-lab/configuration/mosquitto/acl || true
```

Keep exactly one block for this EUI:

```text
user <GATEWAY_EUI>
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/#
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/#
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/#
```

Remove stale/wrong-EUI duplicates. Do not use wildcard Gateway IDs in a gateway identity block.

Reload or restart Mosquitto according to the pinned version and deployment method:

```bash
cd /opt/lorawan-lab
docker compose restart mosquitto
docker compose logs --since=2m --tail=200 mosquitto
```

## Step 5: Create the transfer bundle

Create a temporary protected directory:

```bash
sudo install -d -m 700 /root/lorawan-lab-pki/transfer/<GATEWAY_EUI>
sudo install -m 0644 /root/lorawan-lab-pki/mqtt-ca/ca.crt \
  /root/lorawan-lab-pki/transfer/<GATEWAY_EUI>/ca.crt
sudo install -m 0644 /root/lorawan-lab-pki/client-work/<GATEWAY_EUI>.crt \
  /root/lorawan-lab-pki/transfer/<GATEWAY_EUI>/<GATEWAY_EUI>.crt
sudo install -m 0600 /root/lorawan-lab-pki/client-work/<GATEWAY_EUI>.key \
  /root/lorawan-lab-pki/transfer/<GATEWAY_EUI>/<GATEWAY_EUI>.key
```

Transfer only these three files through the approved protected method.

## Step 6: Test positive mTLS and exact-EUI authorization before gateway import

From a protected test host with Mosquitto clients, place only the three transfer files in the current directory:

```text
ca.crt
<GATEWAY_EUI>.crt
<GATEWAY_EUI>.key
```

These exact-EUI names match the active Gateway OS certificate layout. The protected server staging key may remain `root:root 0600`; after transfer to Gateway OS, set the active key to `mosquitto:mosquitto 0600` as described in Gateway 04.

First prove that the issued certificate completes the mTLS connection and can subscribe only to its own command hierarchy:

```bash
mosquitto_sub \
  -h <MQTT_BROKER_FQDN> -p 8883 \
  --cafile ca.crt \
  --cert <GATEWAY_EUI>.crt \
  --key <GATEWAY_EUI>.key \
  -t '<CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/#' \
  -C 1 \
  -W 5 \
  -d
```

A timeout with no command is acceptable for this subscribe test. Broker logs must show the TLS client mapped to username `<GATEWAY_EUI>` rather than `anonymous` or an unrelated asset name.

For an authorization test, use a **dedicated staging topic prefix or disposable broker** so fabricated payloads cannot be consumed by the live ChirpStack gateway backend. With `<TEST_REGION_TOPIC_PREFIX>` configured in a matching test ACL, publish to this gateway's own EUI:

```bash
mosquitto_pub \
  -h <MQTT_BROKER_FQDN> -p 8883 \
  --cafile ca.crt \
  --cert <GATEWAY_EUI>.crt \
  --key <GATEWAY_EUI>.key \
  -t '<TEST_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/acl-test' \
  -m 'acl-test' \
  -d
```

Expected: the broker accepts the publish.

Now attempt the same operation against a different EUI that is **not** authorized by this certificate:

```bash
mosquitto_pub \
  -h <MQTT_BROKER_FQDN> -p 8883 \
  --cafile ca.crt \
  --cert <GATEWAY_EUI>.crt \
  --key <GATEWAY_EUI>.key \
  -t '<TEST_REGION_TOPIC_PREFIX>/gateway/<OTHER_GATEWAY_EUI>/event/acl-test' \
  -m 'must-be-denied' \
  -d
```

Expected: Mosquitto denies the publish and logs an ACL authorization failure for username `<GATEWAY_EUI>`.

Also verify a client with no certificate cannot authenticate on `8883`:

```bash
mosquitto_sub \
  -h <MQTT_BROKER_FQDN> -p 8883 \
  --cafile ca.crt \
  -t '<TEST_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/#' \
  -d
```

Expected: TLS/MQTT connection failure because the listener requires a client certificate.

Do not weaken the ACL or set `allow_anonymous true` to make a negative test connect.

## Step 7: Keep the values required for rotation and recovery

Retain only the non-secret identity details and protected storage reference:

```text
Gateway EUI
certificate serial and SHA-256 fingerprint
not-before and not-after dates
issuer
physical gateway or asset reference
renewal trigger and revocation method
encrypted recovery location
```

These values identify which credential is active without copying the private key into documentation. Delete the temporary transfer copy after the gateway imports the files and an encrypted recovery copy has been verified.

## Step 8: Configure the gateway

Continue with:

[Configure the persistent local MQTT buffer](../../gateway/setup/04-configure-local-mqtt-buffer.md)

Install the bundle under `/etc/mosquitto/certs/`, not in MQTT Forwarder. Success means the gateway's two bridge client IDs authenticate as this EUI, its own event/state/command topics work, and another gateway's topic is denied. A valid certificate by itself is not proof of correct authorization.

## Troubleshooting

### The certificate and private-key hashes differ

Discard the transfer bundle and identify the correct matching key. Do not copy a second key into the bundle until the public-key hashes match.

### The broker authenticates the certificate but denies the gateway

Confirm that the certificate Common Name equals `<GATEWAY_EUI>` exactly and that the ACL uses the same region prefix and Gateway EUI.

### The gateway can publish to another Gateway EUI

Stop commissioning and correct the ACL. Each gateway identity must use exact topic paths without a wildcard Gateway EUI.

## Completion check

- the Gateway EUI matches Concentratord and contains exactly 16 hexadecimal characters;
- certificate and key public hashes match;
- certificate Common Name equals the Gateway EUI;
- the ACL permits only this gateway's event, state, and command topics;
- cross-gateway access is denied;
- the transfer bundle contains only the CA certificate, gateway certificate, and gateway private key;
- serial, fingerprint, expiry, revocation method, and encrypted recovery location are retained;
- the temporary transfer copy is deleted after verified gateway import.

## Next step

Continue with [Configure the persistent local MQTT buffer](../../gateway/setup/04-configure-local-mqtt-buffer.md).
