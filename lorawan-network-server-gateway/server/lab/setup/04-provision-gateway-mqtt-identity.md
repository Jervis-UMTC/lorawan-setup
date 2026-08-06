# Server 4. Provision a Gateway MQTT Identity

Create one client certificate and one ACL entry for each Gateway OS gateway. The same certificate is used by the gateway's `cloud-uplink` and `cloud-downlink` Mosquitto bridge connections; they use separate client IDs but the same certificate identity.

## Step 1: Confirm the Gateway ID

Obtain the value from the commissioned Gateway OS Concentratord page or UCI configuration.

```bash
printf '%s\n' '<GATEWAY_EUI>' | grep -Eq '^[0-9A-Fa-f]{16}$'
```

Confirm the physical gateway associated with the EUI, the matching region topic prefix, the certificate lifetime, and the encrypted recovery location. Do not issue a certificate for an unverified or duplicate Gateway EUI.

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

Append to the broker ACL:

```text
user <GATEWAY_EUI>
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/#
topic write <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/#
topic read <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/#
```

Do not use wildcard Gateway IDs in a gateway identity block.

Reload or restart Mosquitto according to the pinned version and deployment method:

```bash
cd /opt/chirpstack-docker
docker compose restart mosquitto
docker compose logs --since=2m --tail=200 mosquitto
```

## Step 5: Create the transfer bundle

Create a temporary protected directory:

```bash
sudo install -d -m 700 /root/lorawan-lab-pki/transfer/<GATEWAY_EUI>
sudo install -m 0644 /root/lorawan-lab-pki/mqtt-ca/ca.crt \
  /root/lorawan-lab-pki/transfer/<GATEWAY_EUI>/mqtt-ca.crt
sudo install -m 0644 /root/lorawan-lab-pki/client-work/<GATEWAY_EUI>.crt \
  /root/lorawan-lab-pki/transfer/<GATEWAY_EUI>/gateway.crt
sudo install -m 0600 /root/lorawan-lab-pki/client-work/<GATEWAY_EUI>.key \
  /root/lorawan-lab-pki/transfer/<GATEWAY_EUI>/gateway.key
```

Transfer only these three files through the approved protected method.

## Step 6: Test the identity before gateway import

From a protected test host with Mosquitto clients:

```bash
mosquitto_sub \
  -h <MQTT_BROKER_FQDN> -p 8883 \
  --cafile mqtt-ca.crt \
  --cert gateway.crt \
  --key gateway.key \
  -t '<CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/#' \
  -d
```

Test an allowed publish to the gateway's own event test topic and a denied publish to another gateway's topic. Do not publish fabricated production uplinks into the live ChirpStack topic hierarchy; use a staging broker or a dedicated test prefix when possible.

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

[Configure the persistent local MQTT buffer](../../../gateway/setup/04-configure-local-mqtt-buffer.md)

Install the bundle under `/etc/mosquitto/certs/`, not in MQTT Forwarder. Success means the gateway's two bridge client IDs authenticate as this EUI, its own event/state/command topics work, and another gateway's topic is denied. A valid certificate by itself is not proof of correct authorization.
