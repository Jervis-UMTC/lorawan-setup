# Operations 2. Gateway Backup and Recovery

A recoverable gateway needs three different artifacts because none can replace the others:

1. the exact Gateway OS Base factory image, which can boot a blank SD card;
2. an encrypted Gateway OS configuration archive, which restores UCI and service settings;
3. an encrypted MQTT identity bundle, which restores the gateway certificate and private key.

Keep all three outside the gateway and test them on spare media.

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

Keep the queue limits, current database size, free-space reserve, certificate fingerprint/expiry, management address, and last successful drain test with the backup location. These values let the restored gateway be compared with the working one. Do not print or copy private-key contents into notes.

## Step 2: Drain before a planned backup

When WAN and the remote broker are healthy, verify the outgoing queue has drained before a planned firmware upgrade or routine image backup.

Do not delete `mosquitto.db` to make it appear empty. Confirm drain using gateway logs, remote broker events, ChirpStack frame counters, and application deduplication records.

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

The archive may contain `/etc/mosquitto/certs/gateway.key` and queued uplinks. Transfer it through a protected path and encrypt it at rest.

Inspect the archive securely and verify it includes:

```text
/etc/mosquitto/mosquitto.conf
/etc/mosquitto/certs/
/etc/mosquitto/data/ when queue-state recovery is required
/etc/config/chirpstack-concentratord
/etc/config/chirpstack-mqtt-forwarder
/etc/config/chirpstack-udp-forwarder
```

## Step 4: Preserve the factory image

Keep the official source, release, filename, calculated SHA-256, and protected storage location for the exact Raspberry Pi 4B Gateway OS Base image used by this gateway. The hash detects accidental changes to the retained artifact, while the source and release identify what should be downloaded again.

A configuration archive is not bootable. If the image file or hash cannot be matched to the tested release, obtain a fresh official image before relying on the recovery plan.

## Step 5: Preserve the MQTT identity bundle

Keep a separate encrypted recovery bundle containing:

```text
Gateway ID
remote broker CA certificate
gateway certificate and private key
certificate serial, fingerprint, expiry, and replacement reference
broker FQDN and port
region topic prefix
bridge client IDs
queue limits and storage path
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
7. Verify MQTT Forwarder still uses `tcp://127.0.0.1:1883` at QoS 1.
8. Verify the two Mosquitto bridge connections use the approved remote endpoint and certificate.
9. Keep UDP Forwarder disabled.
10. Run a fresh WAN-outage, reboot, drain, OTAA, uplink, and safe downlink test.

Do not overwrite the production SD card during the first restore rehearsal.

## Recovery acceptance

Pass only when the restored gateway preserves the intended Gateway EUI and confirmed RF plan, authenticates with the expected certificate, buffers real uplinks across WAN loss and reboot, drains them without duplicate application rows, and does not replay a stale downlink. Any difference in EUI, region, queue path, or certificate identity means the restore is incomplete.
