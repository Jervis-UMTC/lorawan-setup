# Gateway 4. Configure the Persistent Local MQTT Buffer

This procedure installs a local Mosquitto broker on ChirpStack Gateway OS Base and configures it as a persistent, bounded store-and-forward queue for offline uplink buffering.

### Gateway Architecture & Complete End-to-End Data Path

```text
  [ LoRaWAN End Device / Sensor ]
                │
                │ (RF Transmission: 923 MHz AS923)
                ▼
  ┌─────────────────────────────────────────────────────────┐
  │ RAK5146-115 SPI Concentrator HAT                        │
  │ (SX1303 Baseband Processor + SX1250 Radios)             │
  └───────────────────────────┬─────────────────────────────┘
                              │
                              │ (Raw SPI Bus: /dev/spidev0.0)
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 1. ChirpStack Concentratord Daemon                      │
  │    Reads SPI hardware, decodes frames, exposes IPC socket│
  └───────────────────────────┬─────────────────────────────┘
                              │
                              │ (Local IPC / ZMQ Unix Socket)
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 2. ChirpStack MQTT Forwarder Daemon                     │
  │    Converts radio frames to ChirpStack MQTT Protobuf     │
  └───────────────────────────┬─────────────────────────────┘
                              │
                              │ (Local Loopback MQTT @ QoS 1: tcp://127.0.0.1:1883)
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 3. Local Mosquitto Broker (Gateway On-Device Buffer)    │
  │    Saves messages in persistent disk queue (mosquitto.db)│
  │    Guarantees store-and-forward during internet outages │
  └───────────────────────────┬─────────────────────────────┘
                              │
                              │ (Encrypted mTLS Bridge: <MQTT_SERVER_NAME>:8883)
                              │  Using ca.crt + <GATEWAY_EUI>.crt + <GATEWAY_EUI>.key
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 4. Remote MQTT Broker & ChirpStack Network Server       │
  │    Receives gateway traffic under: as923/gateway/<EUI>/...│
  └─────────────────────────────────────────────────────────┘
```

#### Detailed Layer Breakdown:

1. **Physical Radio Layer (RAK5146-115 HAT):** Captures incoming LoRa radio signals from sensors on AS923 frequencies (923.2–924.6 MHz) and streams raw packets to the Raspberry Pi over the SPI bus interface (`/dev/spidev0.0`).
2. **Radio Control Daemon (Concentratord):** Interfaces directly with the SX1303 baseband chip, decodes raw radio frames into structured data, and serves them on a local IPC socket (`ipc:///tmp/concentratord_event`).
3. **Protocol Converter Daemon (MQTT Forwarder):** Reads frames from Concentratord and converts them into standardized ChirpStack Gateway MQTT payload messages. It publishes these messages with **QoS 1** (At-Least-Once delivery) exclusively to the local loopback broker (`tcp://127.0.0.1:1883`).
4. **Local Persistent Buffer (On-Device Mosquitto Broker):** Acts as a bounded store-and-forward queue. The configuration in this manual stores persistent broker state at `/etc/mosquitto/data/mosquitto.db`. During a WAN outage, QoS 1 uplinks can accumulate until the configured message/byte limit or available storage is reached. This is an availability control, not an immutable evidence store.
5. **Mutual TLS Bridge (WAN Transport):** The local Mosquitto broker maintains an outbound mTLS bridge to the SAN-matching server name (`<MQTT_SERVER_NAME>:8883`; lab: `lora-test-server:8883`). When connectivity is active, or returns after an outage, it securely streams retained gateway event/state messages to the remote server under `as923/gateway/<GATEWAY_EUI>/...`.

### Security boundary: what this buffer proves

The gateway must be treated as a **transport and availability component**, not as the authority that proves a sensor reading is genuine.

```text
LoRaWAN sensor
  -> LoRaWAN frame with MIC and frame counter
  -> RAK5146 / Gateway OS
  -> local Mosquitto availability buffer
  -> mTLS
  -> remote MQTT
  -> ChirpStack validates LoRaWAN protocol/session state
  -> application telemetry
  -> TimescaleDB + Fabric outbox
  -> Fabric adapter creates canonical evidence and digest
  -> Hyperledger Fabric
```

The controls in this gateway manual protect different risks:
- Loopback-only MQTT prevents ordinary LAN/WAN clients from writing directly to the local broker.
- Linux ownership and permissions restrict ordinary processes from reading or changing the queue and private key.
- Finite queue limits prevent an outage from filling the SD card.
- mTLS protects and authenticates the gateway-to-cloud transport.
- LoRaWAN MIC/frame-counter validation occurs at ChirpStack after the gateway forwards the frame.

For the dissertation test track, this buffer provides **availability**, not immutable evidence. That distinction is enough for the test manual: verify that messages are retained and delivered after reconnecting.

> [!IMPORTANT]
> The completion condition for this test manual is bounded local buffering plus a working mTLS bridge. Do not claim that `mosquitto.db` itself is tamper-proof.

---

## Before you begin

Complete these first:
- [Gateway 03 - Configure Concentratord](03-configure-concentratord.md)
- [Server 02 - Build the minimum testbed](../server/02-build-minimum-testbed.md) through Section 9 (Gateway mTLS & ACL step)

Have these confirmed values and files ready:
```text
Gateway address: <GATEWAY_IP> (e.g. 192.168.8.11)
Gateway EUI: <GATEWAY_EUI> (e.g. 0016c001f139a1cb)
Region topic prefix: as923
Remote broker name: <MQTT_SERVER_NAME>:8883 (lab example: lora-test-server)
Broker CA certificate: /opt/lorawan-lab/secrets/certs/ca.crt
Gateway certificate: /opt/lorawan-lab/secrets/certs/<GATEWAY_EUI>.crt
Gateway private key: /opt/lorawan-lab/secrets/certs/<GATEWAY_EUI>.key
```

---

## Step 1: Back up Gateway OS

Generates and downloads a baseline system backup archive (`.tar.gz`) from LuCI (**System > Backup / Flash Firmware**) to your administration workstation.

In LuCI:
1. Open **System > Backup / Flash Firmware**.
2. Select **Generate archive**.

---

## Step 2: Check package feed and storage availability

Run over SSH on Gateway OS:

```sh
opkg update
opkg list | grep -E '^mosquitto-(ssl|client-ssl) '
df -h /
```

---

## Step 3: Configure UCI to use static Mosquitto configuration files

Inspect `/etc/config/mosquitto` on Gateway OS and verify it contains `option use_uci '0'`:

```sh
cat /etc/config/mosquitto
```

Ensure it contains:
```text
config owrt 'owrt'
        option use_uci '0'
```

---

## Step 4: Install Mosquitto package

Run over SSH on Gateway OS:

```sh
opkg install mosquitto-ssl mosquitto-client-ssl
```

---

## Step 5: Create persistent storage directories

Run over SSH on Gateway OS:

```sh
mkdir -p /etc/mosquitto/data /etc/mosquitto/certs /etc/mosquitto/conf.d
chown -R mosquitto:mosquitto /etc/mosquitto/data /etc/mosquitto/certs
chmod 0750 /etc/mosquitto/data /etc/mosquitto/certs
```

---

## Step 6: Transfer and verify certificate files

#### 1. Clean certificate debris on a reused gateway

Old failed attempts can leave a wrong EUI certificate or even a zero-byte CA file. Stop Mosquitto before replacing credentials:

```sh
/etc/init.d/mosquitto stop
mv /etc/mosquitto/certs /etc/mosquitto/certs.before-fix 2>/dev/null || true
mkdir -p /etc/mosquitto/certs
chown mosquitto:mosquitto /etc/mosquitto/certs
chmod 0750 /etc/mosquitto/certs
```

Keep the backup only long enough to investigate it; do not copy stale credentials back into the active directory.

#### 2. Transfer only the known-good files

Run on the **Server VM**:

```bash
export GATEWAY_EUI="<REAL_GATEWAY_EUI>"
export GATEWAY_IP="<GATEWAY_IP>"

cat /opt/lorawan-lab/secrets/certs/ca.crt | ssh root@${GATEWAY_IP} "cat > /etc/mosquitto/certs/ca.crt"
cat /opt/lorawan-lab/secrets/certs/${GATEWAY_EUI}.crt | ssh root@${GATEWAY_IP} "cat > /etc/mosquitto/certs/${GATEWAY_EUI}.crt"
cat /opt/lorawan-lab/secrets/certs/${GATEWAY_EUI}.key | ssh root@${GATEWAY_IP} "cat > /etc/mosquitto/certs/${GATEWAY_EUI}.key"

ssh root@${GATEWAY_IP} "chown mosquitto:mosquitto /etc/mosquitto/certs/ca.crt /etc/mosquitto/certs/${GATEWAY_EUI}.crt /etc/mosquitto/certs/${GATEWAY_EUI}.key && chmod 0644 /etc/mosquitto/certs/ca.crt /etc/mosquitto/certs/${GATEWAY_EUI}.crt && chmod 0600 /etc/mosquitto/certs/${GATEWAY_EUI}.key"
```

On the **server staging area**, a protected private key may correctly be `root:root 0600`. On the **gateway**, Mosquitto must be able to read it, so the active key must be `mosquitto:mosquitto 0600`.

Verify the active directory:

```sh
ls -lah /etc/mosquitto/certs/
```

Expected: exactly `ca.crt`, `<REAL_GATEWAY_EUI>.crt`, and `<REAL_GATEWAY_EUI>.key`; none may be zero bytes. Remove stale wrong-EUI files and do not use generic `gateway.crt` / `gateway.key` names in this test track.

#### 3. Verify certificate contents and the certificate/key pair

Run on the gateway:

```sh
GATEWAY_EUI='<REAL_GATEWAY_EUI>'

openssl x509 \
  -in /etc/mosquitto/certs/ca.crt \
  -noout -subject -issuer

openssl x509 \
  -in "/etc/mosquitto/certs/${GATEWAY_EUI}.crt" \
  -noout -subject -issuer -dates

CERT_HASH="$(
openssl x509 \
  -in "/etc/mosquitto/certs/${GATEWAY_EUI}.crt" \
  -pubkey -noout |
openssl pkey -pubin -outform DER |
sha256sum | cut -d' ' -f1
)"

KEY_HASH="$(
openssl pkey \
  -in "/etc/mosquitto/certs/${GATEWAY_EUI}.key" \
  -pubout -outform DER |
sha256sum | cut -d' ' -f1
)"

echo "CERT: $CERT_HASH"
echo "KEY : $KEY_HASH"
```

For the minimum lab, the CA subject should contain `CN = LoRaWAN-Lab-CA`, the client certificate subject should contain `CN = <REAL_GATEWAY_EUI>`, and the two hashes must match.

---

## Step 7: Create the Mosquitto configuration file

Writes `/etc/mosquitto/mosquitto.conf` and `/etc/mosquitto/conf.d/bridge.conf` for local loopback binding (`127.0.0.1:1883`), bounded store-and-forward persistence (100 MB max, 100,000 msgs max), and outbound mTLS bridge to the Server VM.

Run on the gateway SSH terminal:

```sh
cat << 'EOF' > /etc/mosquitto/mosquitto.conf
user mosquitto

persistence true
persistence_location /etc/mosquitto/data/
persistence_file mosquitto.db
autosave_interval 60
autosave_on_changes false

max_queued_messages 100000
max_queued_bytes 104857600
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
include_dir /etc/mosquitto/conf.d
EOF
```

The broker certificate is validated against the name used in the bridge address. For the working lab certificate, the SAN contains `DNS:lora-test-server` but not the LAN IP `192.168.8.50`. Add a local name mapping on the gateway when local DNS does not already provide it:

```sh
printf '%s\n' '<SERVER_VM_IP> lora-test-server' >> /etc/hosts
getent hosts lora-test-server 2>/dev/null || nslookup lora-test-server
```

Use a DNS name present in the certificate SAN, or issue a new server certificate whose SAN contains the IP actually used. **Never** work around a SAN mismatch with `bridge_insecure true`.

Create `/etc/mosquitto/conf.d/bridge.conf` (replace `<MQTT_SERVER_NAME>` and `<GATEWAY_EUI>` with real values; lab server name: `lora-test-server`):

```sh
cat << 'EOF' > /etc/mosquitto/conf.d/bridge.conf
# Persistent uplink/state bridge. QoS 1 messages may queue while the server is unreachable.
connection cloud-uplink
address <MQTT_SERVER_NAME>:8883
bridge_protocol_version mqttv311
remote_clientid gw-up-<GATEWAY_EUI>
cleansession false
start_type automatic
restart_timeout 5 60
keepalive_interval 30
notifications false
try_private false
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/<GATEWAY_EUI>.crt
bridge_keyfile /etc/mosquitto/certs/<GATEWAY_EUI>.key
bridge_insecure false
topic as923/gateway/<GATEWAY_EUI>/event/# out 1
topic as923/gateway/<GATEWAY_EUI>/state/# out 1

# Non-persistent downlink bridge. Expired Class A commands must not be replayed after an outage.
connection cloud-downlink
address <MQTT_SERVER_NAME>:8883
bridge_protocol_version mqttv311
remote_clientid gw-down-<GATEWAY_EUI>
cleansession true
start_type automatic
restart_timeout 5 60
keepalive_interval 30
notifications false
try_private false
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/<GATEWAY_EUI>.crt
bridge_keyfile /etc/mosquitto/certs/<GATEWAY_EUI>.key
bridge_insecure false
topic as923/gateway/<GATEWAY_EUI>/command/# in 0
EOF

# Replace every placeholder before starting Mosquitto.
vi /etc/mosquitto/conf.d/bridge.conf
if grep -n '<[^>]*>' /etc/mosquitto/conf.d/bridge.conf; then
  echo 'STOP: replace every <MQTT_SERVER_NAME> and <GATEWAY_EUI> placeholder.'
else
  echo 'Bridge configuration has no remaining placeholders.'
fi
```

---

## Step 8: Configure ChirpStack MQTT Forwarder to publish locally

Configure `chirpstack-mqtt-forwarder` via OpenWrt UCI commands to point to local loopback Mosquitto (`tcp://127.0.0.1:1883`):

```sh
uci set chirpstack-mqtt-forwarder.mqtt.server='tcp://127.0.0.1:1883'
uci set chirpstack-mqtt-forwarder.mqtt.topic_prefix='as923'
uci set chirpstack-mqtt-forwarder.mqtt.json='0'
uci commit chirpstack-mqtt-forwarder
/etc/init.d/chirpstack-mqtt-forwarder restart
```

---

## Step 9: Prove TCP, TLS, then MQTT authorization

These tests prove different layers. Do not treat a successful `nc` test as proof of TLS or MQTT authentication.

### A. Raw TCP reachability

```sh
nc -w 3 <MQTT_SERVER_NAME> 8883 </dev/null
echo $?
```

Exit `0` proves only route + TCP port reachability. Binary-looking output from `nc` against a TLS port is normal.

### B. TLS and hostname verification

```sh
GATEWAY_EUI='<REAL_GATEWAY_EUI>'
openssl s_client \
  -connect <MQTT_SERVER_NAME>:8883 \
  -servername <MQTT_SERVER_NAME> \
  -verify_hostname <MQTT_SERVER_NAME> \
  -verify_return_error \
  -CAfile /etc/mosquitto/certs/ca.crt \
  -cert "/etc/mosquitto/certs/${GATEWAY_EUI}.crt" \
  -key "/etc/mosquitto/certs/${GATEWAY_EUI}.key" \
  </dev/null
```

Pass evidence includes `Verification: OK`, `Verified peername: <MQTT_SERVER_NAME>`, and `Verify return code: 0 (ok)`.

### C. MQTT authentication + ACL

```sh
GATEWAY_EUI='<REAL_GATEWAY_EUI>'
mosquitto_pub \
  -h <MQTT_SERVER_NAME> \
  -p 8883 \
  --cafile /etc/mosquitto/certs/ca.crt \
  --cert "/etc/mosquitto/certs/${GATEWAY_EUI}.crt" \
  --key "/etc/mosquitto/certs/${GATEWAY_EUI}.key" \
  -i "gw-cert-test-${GATEWAY_EUI}" \
  -t "as923/gateway/${GATEWAY_EUI}/state/test" \
  -m 'mtls-auth-test' \
  -q 1 \
  -d
```

`CONNACK (0)` proves the MQTT client authenticated. `PUBACK (... RC:0)` proves the ACL allowed this publication.

## Step 10: Enable and start Mosquitto & Forwarder daemons

Run over SSH on Gateway OS:

```sh
/etc/init.d/mosquitto enable
/etc/init.d/mosquitto restart
/etc/init.d/chirpstack-mqtt-forwarder restart
sleep 3
ps w | grep -E '[m]osquitto|[c]hirpstack-mqtt-forwarder'
```

Verify local loopback listener binding:

```sh
netstat -lntp 2>/dev/null | grep ':1883'
```

Confirm output shows `127.0.0.1:1883`.

Verify Mosquitto bridge connection logs:

```sh
logread -e mosquitto | tail -n 100
```

For live output:

```sh
logread -f -e mosquitto
```

Because this configuration uses `log_dest syslog`, running `mosquitto -c /etc/mosquitto/mosquitto.conf -v` can appear almost blank after it loads `conf.d/bridge.conf`. That is not a hang; runtime messages are being sent to OpenWrt syslog. Healthy bridge logs include keepalive `PINGREQ` / `PINGRESP` for `gw-up-<GATEWAY_EUI>` and `gw-down-<GATEWAY_EUI>`, and persistence saves to `/etc/mosquitto/data/mosquitto.db`.

---

## Step 11: Include broker files in Gateway OS backups

Appends `/etc/mosquitto/` to `/etc/sysupgrade.conf` so persistent queue settings and certificates survive firmware updates:

```sh
grep -qxF '/etc/mosquitto/' /etc/sysupgrade.conf 2>/dev/null || printf '%s\n' '/etc/mosquitto/' >> /etc/sysupgrade.conf
cat /etc/sysupgrade.conf
```

---

## Step 12: Capture off-device configuration integrity baseline

Run on the gateway SSH terminal:

```sh
GATEWAY_EUI='<GATEWAY_EUI>'
umask 077
{
  printf 'gateway_eui=%s\n' "$GATEWAY_EUI"
  printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sha256sum /etc/mosquitto/mosquitto.conf /etc/mosquitto/conf.d/bridge.conf
  openssl x509 -in "/etc/mosquitto/certs/${GATEWAY_EUI}.crt" -noout -fingerprint -sha256 -serial -dates
  openssl x509 -in /etc/mosquitto/certs/ca.crt -noout -fingerprint -sha256 -subject -issuer
} > /tmp/gateway-mqtt-security-baseline.txt
cat /tmp/gateway-mqtt-security-baseline.txt
```

On the administration workstation terminal, copy the baseline:

```bash
scp root@<GATEWAY_IP>:/tmp/gateway-mqtt-security-baseline.txt ./<GATEWAY_EUI>-mqtt-security-baseline.txt
```

---

## Troubleshooting & Verification Checklist

1. **Mosquitto starts with generated UCI file instead of static config**:
   Inspect `/etc/config/mosquitto` and confirm `option use_uci '0'` is set.
2. **Permission denied for private key or data folder**:
   Ensure the actual `<GATEWAY_EUI>.key` is owned by `mosquitto:mosquitto` with mode `0600`, and `/etc/mosquitto/data` is writable by `mosquitto`.
3. **Bridge reports `Permission denied` for the client key**:
   Verify `ls -l /etc/mosquitto/certs/` shows the gateway `.key` owned by `mosquitto:mosquitto` with mode `0600`.
4. **Bridge reports connection refused or unknown CA**:
   Verify system time (`date -u`), reachability of `<MQTT_SERVER_NAME>:8883`, the broker certificate SAN, and topic ACLs on Mosquitto server.
5. **Bridge reports hostname/IP verification failure**:
   The broker certificate must contain the exact DNS name or IP address used in the bridge `address`. Do not change `bridge_insecure` to `true`; reissue the server certificate with the correct SAN.
