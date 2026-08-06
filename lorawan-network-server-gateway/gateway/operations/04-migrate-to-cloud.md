# Operations 4. Migrate the Buffered Gateway to a Cloud Broker

Migration changes the local Mosquitto bridge endpoint and certificate bundle. MQTT Forwarder must continue publishing to the local loopback broker.

## Step 1: Capture the rollback baseline

Before changing the cloud endpoint, confirm the current values that must either remain unchanged or be restored during rollback:

```text
Gateway EUI and confirmed RF plan
MQTT Forwarder server, QoS, client ID, and topic prefix
local Mosquitto configuration backup
queue limits, storage path, current size, and free-space reserve
current bridge FQDN, certificate fingerprint, and expiry
Gateway OS image reference and encrypted configuration-backup location
last successful buffer, reboot, and drain result
```

The migration changes only the remote bridge destination and identity bundle unless the cloud design deliberately uses a different confirmed region prefix. It must not change the radio profile or MQTT Forwarder's loopback endpoint.

## Step 2: Prepare cloud ingress

Verify `mqtt.<DOMAIN>:8883`, server certificate SAN, trusted gateway-client CA, exact gateway ACL, ChirpStack region prefix, and Layer-4 pass-through when used.

No Gateway Bridge or UDP ingress is required.

## Step 3: Issue the cloud identity

Prefer a separate cloud client certificate issued for the same Gateway EUI. Keep its serial, fingerprint, expiry, encrypted recovery location, and revocation method so the old and new identities can be distinguished and rolled back without exposing the private key.

## Step 4: Preserve rollback

Drain the local queue when possible. Export a fresh encrypted Gateway OS archive and preserve the previous Mosquitto configuration and certificate bundle.

## Step 5: Update the local Mosquitto bridges

Do not change MQTT Forwarder away from:

```text
Server: tcp://127.0.0.1:1883
QoS: 1
Backend: concentratord
```

Install the cloud CA, gateway certificate, and private key under `/etc/mosquitto/certs/`, then update only the bridge fields in `/etc/mosquitto/mosquitto.conf`:

```text
address mqtt.<DOMAIN>:8883
bridge_cafile /etc/mosquitto/certs/remote-ca.crt
bridge_certfile /etc/mosquitto/certs/gateway.crt
bridge_keyfile /etc/mosquitto/certs/gateway.key
topic prefix, only when the approved cloud region changes
```

Validate in the foreground, then restart only local Mosquitto. A healthy result shows hostname verification, successful client-certificate authentication, and permission only for this gateway's topics. A TLS or ACL failure should leave event/state messages in the local queue; do not bypass the queue or disable certificate validation.

## Step 6: Verify cutover

On Gateway OS:

```sh
logread -e mosquitto
logread -e chirpstack-mqtt-forwarder
```

On the cloud server:

```sh
docker compose logs -f mosquitto chirpstack
```

Pass when both bridge client IDs authenticate with the expected certificate, a real uplink reaches ChirpStack, a safe fresh downlink works, and a short WAN-outage buffer drains.

## Step 7: Roll back

Restore the previous bridge endpoint, CA, certificate, key, and approved topic prefix. Do not change MQTT Forwarder's loopback endpoint, Gateway ID, Concentratord region, or RF settings.

Preserve logs from both endpoints.
