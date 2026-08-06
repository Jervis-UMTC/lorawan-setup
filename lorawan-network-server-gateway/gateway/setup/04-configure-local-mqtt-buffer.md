# Gateway 4. Configure the Persistent Uplink Buffer

The local Mosquitto broker provides bounded store-and-forward for gateway uplinks and state.

```text
Concentratord
  -> MQTT Forwarder, QoS 1
  -> 127.0.0.1:1883
  -> local Mosquitto persistent queue
  -> outgoing mTLS bridge, QoS 1
  -> remote broker
```

Current ChirpStack Gateway Bridge is not used. Its Concentratord backend was removed, and Gateway Bridge is not a durable queue.

## Step 1: Create a recoverable Gateway OS backup

In LuCI:

```text
System > Backup / Flash Firmware > Generate archive
```

Save the archive in encrypted storage outside the gateway and calculate a checksum so later corruption can be detected. Keep its storage location with the factory-image reference. Confirm a spare SD card and card reader are available before changing the broker configuration.

A successful backup is non-empty, readable, and stored off the SD card. An archive kept only on the gateway is not a recovery copy.

## Step 2: Confirm package and storage support

Run on Gateway OS as `root`:

```sh
opkg update
opkg list | grep -E '^mosquitto-(ssl|client-ssl) '
opkg print-architecture
df -h /
mount
```

Required evidence:

- `mosquitto-ssl` and `mosquitto-client-ssl` exist in the pinned Gateway OS feed;
- package architecture matches the gateway;
- enough persistent storage exists for the selected queue plus a free-space reserve;
- the intended queue path is not under `/tmp` or another tmpfs.

**Stop here. Do not continue until this condition is resolved.** Do not install packages from an unverified third-party feed or use volatile storage for the queue.

## Step 3: Size the finite queue

Calculate:

```text
required bytes = peak uplinks per hour
               × maximum outage hours
               × measured serialized MQTT bytes per uplink
               × safety factor
```

Use the calculation to choose these environment-specific values:

```text
<BUFFER_MAX_MESSAGES>                 finite queued-message limit
<BUFFER_MAX_BYTES>                    finite queue byte limit
<BUFFER_AUTOSAVE_SECONDS>             interval for writing broker state
<BUFFER_FREE_SPACE_RESERVE_BYTES>     storage that must remain unused
<BUFFER_MAX_OUTAGE_HOURS>             outage duration the design intends to cover
```

The peak uplink count comes from the deployed devices, the serialized byte size must be measured from representative gateway messages, and the outage target comes from the backhaul requirement. Use finite values. Include gateway state traffic, protocol overhead, expected retransmission, and SD-card endurance.

If the calculated queue plus reserve does not fit comfortably on persistent storage, reduce the outage target, reduce traffic, or move to suitable storage; do not use unlimited limits.

## Step 4: Install the open-source broker

```sh
opkg install mosquitto-ssl mosquitto-client-ssl
opkg list-installed | grep '^mosquitto'
opkg files mosquitto-ssl
```

Inspect the service before editing configuration:

```sh
sed -n '1,240p' /etc/init.d/mosquitto
```

The following procedure expects the service to start `/usr/sbin/mosquitto` with `/etc/mosquitto/mosquitto.conf`. If the pinned package uses a different supported UCI-generated path, use that package's observed mechanism and preserve the same settings below. Do not replace the init script blindly.

## Step 5: Create protected persistent paths

Use `/etc/mosquitto/data` as the default Gateway OS overlay path only after confirming `/etc` is persistent on the selected image.

```sh
mkdir -p /etc/mosquitto/data /etc/mosquitto/certs
chmod 0700 /etc/mosquitto/data /etc/mosquitto/certs

df -h /etc/mosquitto/data
mount | grep -E ' / | /overlay | /etc '
```

Never place the queue under `/tmp`. Do not assume `/var` is persistent on OpenWrt.

Install only the gateway runtime certificate files. The three placeholders come from the server-side certificate procedure: the broker CA certificate, the client certificate issued for this Gateway EUI, and its matching private key.

```sh
cp <MQTT_CA_CERT_FILE> /etc/mosquitto/certs/remote-ca.crt
cp <GATEWAY_MQTT_CERT_FILE> /etc/mosquitto/certs/gateway.crt
cp <GATEWAY_MQTT_KEY_FILE> /etc/mosquitto/certs/gateway.key
chmod 0644 /etc/mosquitto/certs/remote-ca.crt /etc/mosquitto/certs/gateway.crt
chmod 0600 /etc/mosquitto/certs/gateway.key
command -v openssl || echo 'Verify certificate and key on the protected operator workstation'
```

Verify certificate metadata and key match without printing the key:

```sh
openssl x509 -in /etc/mosquitto/certs/gateway.crt -noout \
  -subject -issuer -serial -dates -fingerprint -sha256

CERT_HASH="$(openssl x509 -in /etc/mosquitto/certs/gateway.crt -pubkey -noout | \
  openssl pkey -pubin -outform DER | sha256sum)"
KEY_HASH="$(openssl pkey -in /etc/mosquitto/certs/gateway.key -pubout -outform DER | sha256sum)"
printf 'certificate: %s\nkey:         %s\n' "$CERT_HASH" "$KEY_HASH"
unset CERT_HASH KEY_HASH
```

The hashes must match and the certificate Common Name must equal `<GATEWAY_EUI>`.

## Step 6: Create the Mosquitto configuration

Create `/etc/mosquitto/mosquitto.conf` with the complete reviewed content below:

```conf
persistence true
persistence_location /etc/mosquitto/data/
persistence_file mosquitto.db
autosave_interval <BUFFER_AUTOSAVE_SECONDS>
autosave_on_changes false

max_queued_messages <BUFFER_MAX_MESSAGES>
max_queued_bytes <BUFFER_MAX_BYTES>
max_inflight_messages 20
queue_qos0_messages false

log_dest syslog
connection_messages true
log_type error
log_type warning
log_type notice

listener 1883 127.0.0.1
protocol mqtt
allow_anonymous true

connection cloud-uplink
address <MQTT_BROKER_FQDN>:8883
bridge_protocol_version mqttv311
remote_clientid gw-up-<GATEWAY_EUI>
cleansession false
start_type automatic
restart_timeout 5 60
keepalive_interval 30
notifications false
try_private false
bridge_cafile /etc/mosquitto/certs/remote-ca.crt
bridge_certfile /etc/mosquitto/certs/gateway.crt
bridge_keyfile /etc/mosquitto/certs/gateway.key
bridge_insecure false
topic <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/event/# out 1
topic <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/# out 1

connection cloud-downlink
address <MQTT_BROKER_FQDN>:8883
bridge_protocol_version mqttv311
remote_clientid gw-down-<GATEWAY_EUI>
cleansession true
start_type automatic
restart_timeout 5 60
keepalive_interval 30
notifications false
try_private false
bridge_cafile /etc/mosquitto/certs/remote-ca.crt
bridge_certfile /etc/mosquitto/certs/gateway.crt
bridge_keyfile /etc/mosquitto/certs/gateway.key
bridge_insecure false
topic <CONFIRMED_REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/command/# in 0
```

Why two bridges:

- `cloud-uplink` has a persistent session and QoS 1 queue for event and state traffic.
- `cloud-downlink` uses a clean session and QoS 0 so time-sensitive commands are not intentionally retained for replay after an outage.

Both bridge client IDs must be unique. The remote broker authorizes them by the gateway certificate identity, not by trusting the client ID alone.

## Step 7: Validate and start Mosquitto

Stop the service before the foreground test:

```sh
/etc/init.d/mosquitto stop
mosquitto -c /etc/mosquitto/mosquitto.conf -v
```

Healthy foreground evidence:

- configuration parses;
- the listener binds only to `127.0.0.1:1883`;
- both bridge connections attempt the approved FQDN and port;
- the remote certificate hostname verifies;
- the broker accepts the gateway certificate;
- no ACL denial appears for the gateway's own topics.

Stop the foreground process, then enable the service:

```sh
/etc/init.d/mosquitto enable
/etc/init.d/mosquitto restart
logread -e mosquitto
```

Verify the listener:

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Pass only when `1883` is bound to `127.0.0.1`, not `0.0.0.0`, `::`, a LAN address, or a WAN address.

## Step 8: Preserve configuration across Gateway OS backup

Add the protected broker configuration and data path to the Gateway OS backup list only after confirming the archive will be encrypted:

```sh
printf '%s\n' '/etc/mosquitto/' >> /etc/sysupgrade.conf
sort -u /etc/sysupgrade.conf > /tmp/sysupgrade.conf
mv /tmp/sysupgrade.conf /etc/sysupgrade.conf
cat /etc/sysupgrade.conf
```

A backup now contains the gateway private key and potentially queued uplinks. Protect it as sensitive data.

Drain the queue before a planned firmware upgrade whenever possible. Test restore on a spare SD card before relying on the backup.

## Step 9: Keep the values required to operate and restore the buffer

Retain the following with the gateway configuration backup:

```text
Gateway EUI:
remote broker FQDN and port:
certificate fingerprint, expiry, and protected replacement reference:
Mosquitto configuration path and rollback copy:
queue storage path:
queue maximum messages and bytes:
autosave interval:
free-space reserve:
maximum designed outage:
Gateway OS and Mosquitto versions used by this tested configuration:
```

These values are used to monitor capacity, rotate the certificate, reproduce the bridge, and verify a restore. A separate operator/date or approval field is not required. Continue only after the foreground test parses the configuration, both bridges authenticate, and port `1883` is loopback-only.

Continue with [05-configure-mqtt-forwarder.md](05-configure-mqtt-forwarder.md).
