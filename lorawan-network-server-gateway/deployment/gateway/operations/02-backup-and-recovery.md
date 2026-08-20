# Operations 2. Gateway Backup and Recovery

A recoverable gateway needs **four different recovery sets** because none can replace the others:

1. the exact Gateway OS Base factory image, which can boot a blank SD card;
2. an encrypted Gateway OS configuration archive, which restores UCI and service settings;
3. an encrypted MQTT/evidence-upload identity bundle, which restores the machine identities needed to reach the server; and
4. the gateway-integrity continuity record: reviewed journal implementation/version/hash, journal-format version, last valid local sequence/record/segment hash, latest accepted server checkpoint/receipt, and any closed unuploaded segments required by the retention policy.

Keep these outside the gateway and test them on spare media.

> [!IMPORTANT]
> A journal restore is not ordinary file restoration. If the server already holds a checkpoint newer than the local backup, restoring the old journal and continuing from it would be a rollback conflict. Preserve the server anchor and use the reviewed recovery/epoch procedure; never reset the local sequence or delete the newer cloud checkpoint to make an old SD image look current.

## Step 1: Inspect the running gateway before backup

```sh
cat /etc/os-release
uname -a
monit status
uci show chirpstack-concentratord
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
opkg list-installed | grep '^mosquitto'
sha256sum /etc/mosquitto/mosquitto.conf
ls -l /etc/mosquitto/data /etc/mosquitto/certs
```

Keep the queue limits, current database size, free-space reserve, certificate fingerprint/expiry, management address, and last successful drain test with the backup location. When the journal is enabled, also keep:

```text
journal implementation/version + executable SHA-256
journal format version
journal storage budget + path
last valid local sequence + record hash
last closed segment ID + segment hash
latest accepted server checkpoint ID/sequence/record hash/segment hash
unuploaded closed-segment inventory
last successful journal upload/reconciliation test
```

These values let the restored gateway be compared with the working one. Do not print or copy private-key contents or unrestricted journal payloads into notes.

## Step 2: Drain delivery work and anchor journal state before a planned backup

When WAN and the remote broker are healthy:

1. verify the outgoing Mosquitto queue has drained;
2. close/upload all journal segments that can be closed under the configured policy;
3. verify the server accepted those segment digests;
4. create or confirm a final healthy checkpoint that covers the latest closed evidence boundary;
5. record the checkpoint receipt with the backup manifest.

Do not delete `mosquitto.db` to make it appear empty. Do not truncate/rewrite the journal to make it appear synchronized. Confirm queue drain using gateway logs, remote broker events, ChirpStack frame counters, and application deduplication records; confirm journal synchronization through the server verifier/checkpoint store.

## Step 3: Export Gateway OS configuration

In LuCI:

```text
System > Backup / Flash Firmware > Generate archive
```

When CLI backup is supported by the pinned image, inspect help first:

```sh
sysupgrade --help
sysupgrade -b /tmp/gateway-os-backup-<DATE>.tar.gz
sha256sum /tmp/gateway-os-backup-<DATE>.tar.gz
```

The archive may contain `/etc/mosquitto/certs/<GATEWAY_EUI>.key` and queued uplinks. Transfer it through a protected path and encrypt it at rest.

Inspect the archive securely and verify it includes:

```text
/etc/mosquitto/mosquitto.conf
/etc/mosquitto/certs/
/etc/mosquitto/data/ when queue-state recovery is required
/etc/config/chirpstack-concentratord
/etc/config/chirpstack-mqtt-forwarder
/etc/config/chirpstack-udp-forwarder
/etc/gateway-integrity/config/ when that path is used by the reviewed implementation
/etc/gateway-integrity/state/ continuity metadata required by the reviewed restore procedure
```

Do not assume a generic Gateway OS archive is the only copy of closed journal evidence. If the retention policy requires unuploaded closed segments to survive gateway replacement, preserve them in a separately encrypted evidence backup and keep their object SHA-256/segment hashes in the manifest.

## Step 4: Preserve the factory image

Keep the official source, release, filename, calculated SHA-256, and protected storage location for the exact Raspberry Pi 4B Gateway OS Base image used by this gateway. The hash detects accidental changes to the retained artifact, while the source and release identify what should be downloaded again.

A configuration archive is not bootable. If the image file or hash cannot be matched to the tested release, obtain a fresh official image before relying on the recovery plan.

## Step 5: Preserve the MQTT identity bundle

Keep a separate encrypted recovery bundle containing:

```text
Gateway ID
remote broker CA certificate
gateway MQTT certificate and private key
MQTT certificate serial, fingerprint, expiry, and replacement reference
broker FQDN and port
region topic prefix
bridge client IDs
queue limits and storage path

evidence ingest FQDN when enabled
evidence-upload CA/client certificate/private key or protected credential reference
evidence identity fingerprint/expiry/revocation reference
journal implementation/version/hash and format version
latest accepted checkpoint/receipt reference

renewal and revocation procedure
```

Never store an unencrypted private key in Git or a general file share.

## Step 6: Restore to spare media

1. Flash the exact approved Gateway OS Base image to a spare SD card.
2. Boot on an isolated commissioning network.
3. Change the default password.
4. Restore the encrypted configuration archive.
5. Verify local Mosquitto configuration and private-key permissions.
6. Verify the queue path is persistent and not tmpfs.
7. Restore/install the exact reviewed journal implementation and verify its executable hash, format version, evidence path, permissions, and read-only Concentratord source.
8. Compare the restored local journal boundary with the **server's latest accepted checkpoint before starting new evidence writes**.
9. If the restored boundary exactly continues the accepted anchor, follow the normal continuation procedure. If the backup is older than the accepted server anchor, stop and follow the reviewed recovery/new-evidence-epoch procedure; do not rewind the server.
10. Verify MQTT Forwarder still uses `tcp://127.0.0.1:1883` at QoS 1.
11. Verify the two Mosquitto bridge connections use the approved remote endpoint and certificate.
12. Verify the journal uploader uses the approved evidence endpoint/identity and cannot reset sequence/history.
13. Keep UDP Forwarder disabled.
14. Run a fresh WAN-outage, reboot, queue drain, journal upload/reconciliation, OTAA, uplink, and safe downlink test.

Do not overwrite the production SD card during the first restore rehearsal.

## Recovery acceptance

Pass only when the restored gateway preserves the intended Gateway EUI and confirmed RF plan, authenticates with the expected identities, buffers real uplinks across WAN loss and reboot, drains them without duplicate application rows, preserves or explicitly re-establishes the approved journal/checkpoint continuity boundary, uploads/reconciles new evidence correctly, and does not replay a stale downlink. Any unexplained difference in EUI, region, queue path, journal format/sequence/anchor, or certificate identity means the restore is incomplete.
