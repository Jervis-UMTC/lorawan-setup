# Operations 4. Migrate the Buffered, Journaled Gateway to Cloud

Migration changes the remote **delivery** endpoint and, when gateway-integrity v2 is enabled, the separate **evidence** endpoint/identity. MQTT Forwarder must continue publishing to the local loopback broker, and the journal must continue its existing sequence/hash history rather than starting over.

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
journal implementation/version/hash and format version
journal storage path/budget + last sequence/record hash/segment hash
latest accepted evidence checkpoint/receipt
evidence ingest endpoint/identity and unuploaded segment backlog
```

The migration changes only the remote service destinations/identities unless the cloud design deliberately uses a different confirmed region prefix. It must not change the radio profile, MQTT Forwarder's loopback endpoint, or existing journal chain identity/sequence merely because the server location changes.

## Step 2: Prepare cloud ingress

Verify the delivery boundary:

```text
mqtt.<DOMAIN>:8883
broker SAN/trust chain
trusted gateway-client CA
exact Gateway-EUI ACL
ChirpStack region prefix
Layer-4 pass-through when used
```

When gateway integrity is enabled, separately verify:

```text
evidence.<DOMAIN>:443
evidence server SAN/trust chain
per-gateway mTLS/upload identity mapping
authenticated checkpoint + closed-segment API
checkpoint conflict/rollback rejection
protected checkpoint/segment store
read-only remote gateway-MQTT evidence collector
verifier + trusted decoder
```

No Gateway Bridge or UDP ingress is required.

## Step 3: Issue the cloud identities

For MQTT, prefer a separate cloud client certificate issued for the same Gateway EUI. Keep its serial, fingerprint, expiry, encrypted recovery location, and revocation method.

For evidence upload, prefer a **separate-purpose machine identity/certificate** mapped to the same Gateway EUI so MQTT publish authorization and evidence-upload authorization are independently revocable. Reuse one key for both protocols only if a reviewed PKI policy explicitly accepts the loss of purpose separation.

## Step 4: Preserve rollback and the evidence boundary

Drain the local queue when possible. For the journal:

1. upload/verify all closable segments;
2. create/confirm the latest accepted source checkpoint;
3. record its receipt, sequence, record hash, segment ID/hash;
4. preserve any still-unuploaded closed segments;
5. export the fresh encrypted Gateway OS/journal configuration and identity recovery references.

This checkpoint is the migration rollback boundary. Never delete it merely because the target cloud uses a different database.

## Step 5: Update the local Mosquitto bridges

Do not change MQTT Forwarder away from:

```text
Server: tcp://127.0.0.1:1883
QoS: 1
Backend: concentratord
```

Install the cloud CA, gateway certificate, and private key under `/etc/mosquitto/certs/`, then update only the bridge fields in `/etc/mosquitto/conf.d/bridge.conf`:

```text
address mqtt.<DOMAIN>:8883
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/<GATEWAY_EUI>.crt
bridge_keyfile /etc/mosquitto/certs/<GATEWAY_EUI>.key
topic prefix, only when the approved cloud region changes
```

Validate in the foreground, then restart only local Mosquitto. A healthy result shows hostname verification, successful client-certificate authentication, and permission only for this gateway's topics. A TLS or ACL failure should leave event/state messages in the local queue; do not bypass the queue or disable certificate validation.

## Step 5A: Update the evidence uploader without resetting the journal

Run this step only when the gateway-integrity path exists.

Install the target evidence CA/client identity using the reviewed journal-uploader procedure, then change only:

```text
evidence endpoint FQDN/port
client identity/credential reference
server CA/trust bundle
```

Do **not** change/reset:

```text
gateway ID
journal version
sequence
boot history solely for migration
previous record hash
segment numbering
```

The target checkpoint store/verifier must recognize the reviewed migration anchor or create an explicitly governed new evidence epoch linked to the old one. A fresh target checkpoint/segment must be accepted only when it extends the approved boundary.

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

Pass when both bridge client IDs authenticate with the expected MQTT certificate, a real uplink reaches ChirpStack, a safe fresh downlink works, and a short WAN-outage buffer drains.

When integrity is enabled, also require:

- the evidence uploader authenticates with the expected target identity;
- a fresh checkpoint/closed segment extends the migration anchor;
- the target independently captures the corresponding remote gateway MQTT event;
- one real journal -> remote MQTT -> ChirpStack -> trusted-decoder lineage reaches the expected verification state.

## Step 7: Roll back

1. Stop target-side command publication and, when integrity is enabled, stop accepting new target checkpoint history for the gateway under the rollback procedure.
2. Preserve all target logs, checkpoints, segment objects, and verification results.
3. Restore the previous MQTT bridge endpoint, CA, certificate, key, and approved topic prefix.
4. Restore the previous evidence endpoint/identity using the approved anchor/epoch rollback procedure **without resetting the local journal chain**.
5. Do not change MQTT Forwarder's loopback endpoint, Gateway ID, Concentratord region, RF settings, or locally established journal sequence to make the rollback simpler.
6. Prove one new source-side checkpoint/lineage before resuming v2 evidence promotion.

Preserve logs/evidence from both endpoints.
