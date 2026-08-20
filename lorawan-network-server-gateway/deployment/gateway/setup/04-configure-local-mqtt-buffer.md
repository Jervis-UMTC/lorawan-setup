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
                              │ (Encrypted mTLS Bridge: <MQTT_BROKER_FQDN>:8883)
                              │  Using ca.crt + <GATEWAY_EUI>.crt + <GATEWAY_EUI>.key
                              ▼
  ┌─────────────────────────────────────────────────────────┐
  │ 4. Remote MQTT Broker & ChirpStack Network Server       │
  │    Receives gateway traffic under: as923/gateway/<EUI>/...│
  └─────────────────────────────────────────────────────────┘
```

#### Detailed Layer Breakdown:

1. **Physical Radio Layer (RAK5146-115 HAT):** Captures incoming LoRa radio signals from sensors on AS923 frequencies (923.2–924.6 MHz) and streams raw packets to the Raspberry Pi over the SPI bus interface (`/dev/spidev0.0`).
2. **Radio Control Daemon (Concentratord):** Interfaces directly with the SX1303 baseband chip, handles GPIO reset control, decodes raw radio frames into structured data, and serves them on a local IPC socket (`ipc:///tmp/concentratord_event`).
3. **Protocol Converter Daemon (MQTT Forwarder):** Reads frames from Concentratord and converts them into standardized ChirpStack Gateway MQTT payload messages. It publishes these messages with **QoS 1** (At-Least-Once delivery) exclusively to the local loopback broker (`tcp://127.0.0.1:1883`).
4. **Local Persistent Buffer (On-Device Mosquitto Broker):** Acts as a bounded store-and-forward queue. The configuration in this manual stores persistent broker state at `/etc/mosquitto/data/mosquitto.db`. During a WAN outage, QoS 1 uplinks can accumulate until the configured message/byte limit or available storage is reached. This is an availability control, not an immutable evidence store.
5. **Mutual TLS Bridge (WAN Transport):** The local Mosquitto broker maintains outbound mTLS bridges to your remote cloud/edge server (`<MQTT_BROKER_FQDN>:8883`). When connectivity is active, or returns after an outage, it securely streams gateway event/state traffic under `as923/gateway/<GATEWAY_EUI>/...`; the separate downlink bridge receives the gateway command hierarchy.

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

- loopback-only MQTT prevents ordinary LAN/WAN clients from writing directly to the local broker;
- Linux ownership and permissions restrict ordinary processes from reading or changing the queue and private key;
- finite queue limits prevent an outage from filling the SD card;
- mTLS protects and authenticates the gateway-to-cloud transport;
- LoRaWAN MIC/frame-counter validation occurs at ChirpStack after the gateway forwards the frame.

They **do not make `mosquitto.db` cryptographically tamper-proof against a root or physical attacker**. A privileged attacker can potentially alter, truncate, or delete files on the gateway. Do not create the authoritative Hyperledger digest on the Raspberry Pi and do not claim that a SHA-256 stored beside `mosquitto.db` would solve this problem; an attacker with the same write access could replace both the data and the local hash.

The gateway baseline now adds a separate **software integrity journal** beside Concentratord. That journal does not alter `mosquitto.db`; it records an independent sequence of raw gateway observations, hash-chains records and bounded segments, and periodically sends the current chain state to a server checkpoint service. After an outage the server verifies segment continuity and compares the journal with an independently captured remote gateway MQTT event before higher-level evidence can be promoted.

This materially strengthens tamper detection without additional gateway hardware, but it does not make a fully disconnected, root-compromised Raspberry Pi cryptographically unforgeable. A privileged attacker who controls the whole Pi throughout the unanchored offline interval can potentially rebuild a different internally consistent tail. Hardware-backed monotonic state or source-level device signatures remain future stronger mitigations for that residual threat.

The application-side Fabric manuals preserve `telemetry-attestation-v1` for historical behavior and define a gateway-verified `telemetry-attestation-v2` path. For v2, the canonical evidence is sealed through OpenBao only after the server gateway-evidence verifier reports `verified`. The evidence private key is never stored on this gateway.

> [!IMPORTANT]
> The completion condition for **this** manual is secure bounded buffering and transport. Complete [Gateway 4A](04a-configure-gateway-integrity-journal.md) separately for tamper-evident gateway history. Even with both controls, a full root compromise remains a security incident and the software-only unanchored offline tail is not claimed to be immutable.

---

## Before you begin

Complete these procedures first:

- [Configure Concentratord](03-configure-concentratord.md)
- [Secure the remote MQTT broker](../../server/ha-cluster/11-secure-gateway-mqtt.md)
- [Provision the gateway MQTT identity](../../server/ha-cluster/12-provision-gateway-mqtt-identity.md)

Have these confirmed values and files ready:

```text
Gateway address: <GATEWAY_IP>
Gateway EUI: <GATEWAY_EUI>
Region topic prefix: as923
Remote broker: <MQTT_BROKER_FQDN>:8883
Broker CA certificate: <MQTT_CA_CERT_FILE>
Gateway certificate: <GATEWAY_MQTT_CERT_FILE>
Gateway private key: <GATEWAY_MQTT_KEY_FILE>
```

---

## Step 1: Back up Gateway OS

### What this step does

Generates and downloads a baseline system backup archive (`.tar.gz`) from LuCI (**System > Backup / Flash Firmware**) to your administration workstation.

### Why we do it

Provides a clean rollback point before installing new software packages (`opkg`) or modifying OpenWrt configuration files.

### Procedure

In LuCI:

1. Open **System > Backup / Flash Firmware**.
2. Select **Generate archive**.
3. Save the archive safely on your workstation outside the gateway.

---

## Step 2: Check package feed and storage availability

### What this step does

Updates OpenWrt package feeds (`opkg update`), verifies `mosquitto-ssl` availability, and checks overlay filesystem storage space (`df -h /`).

### Why we do it

Ensures that storage space is sufficient on the microSD card overlay partition and that the official OpenWrt package feed has `mosquitto-ssl` available for installation before attempting package setup.

### Procedure

Run over SSH:

```sh
opkg update
opkg list | grep -E '^mosquitto-(ssl|client-ssl) '
opkg print-architecture
df -h /
mount
```

Continue only when:
- `mosquitto-ssl` and `mosquitto-client-ssl` are available in the package list.
- The writable overlay filesystem (`/`) has at least 50–100 MB of free storage space.

---

## Step 3: Choose finite queue limits

### What this step does

Calculates upper limits for disk space (`<BUFFER_MAX_BYTES>`), message count (`<BUFFER_MAX_MESSAGES>`), and state auto-save intervals (`<BUFFER_AUTOSAVE_SECONDS>`).

### Why we do it

Prevents unlimited disk usage from filling the SD card overlay partition during extended internet outages, which would corrupt the operating system filesystem.

### Procedure

Estimate your required queue size:

```text
required queue bytes = peak uplinks per hour
                     × maximum outage hours
                     × measured MQTT bytes per uplink
                     × safety factor (1.5)
```

Recommended production values for Raspberry Pi 4B gateway:

| Parameter | Recommended Value | Engineering & Mathematical Rationale |
| :--- | :--- | :--- |
| `<BUFFER_MAX_MESSAGES>` | `100000` | **Covers ~16–24 hrs of multi-device outages.** LoRaWAN MQTT payloads average ~1 KB. For 50 sensors transmitting every 30s (~6,000 uplinks/hr), 100,000 messages buffers ~16.6 hours of zero-loss traffic while capping RAM memory allocation (~50–80 MB) to protect against OOM crashes. |
| `<BUFFER_MAX_BYTES>` | `104857600` (100 MB) | **SD Card Protection.** Calculated as $100,000 \text{ msgs} \times ~1,000 \text{ bytes/msg} = 104,857,600 \text{ bytes}$. Capping disk buffer at 100 MB prevents Mosquitto from filling 100% of the SD card root partition during multi-day network failures, which would brick the OS. |
| `<BUFFER_AUTOSAVE_SECONDS>` | `60` | **Flash Wear vs. Data Loss Balance.** Flash memory (SD cards) has limited write cycles. Writing every 1s causes rapid SD card degradation. Writing every 60s reduces SD card write operations by 60x while limiting data loss to a maximum of 60 seconds if power is abruptly cut. |
| `<BUFFER_FREE_SPACE_RESERVE_BYTES>` | `52428800` (50 MB) | **Emergency System Reserve.** Guarantees that system services (syslog, DHCP leases, OpenWrt config commits, SSH sessions) always have 50 MB of guaranteed free disk space on `/` to prevent OS system panics. |

---

## Step 4: Install Mosquitto

### What this step does

Installs `mosquitto-ssl` and `mosquitto-client-ssl` via `opkg`, verifies the `mosquitto` system user account, and configures OpenWrt UCI to use static configuration files (`/etc/mosquitto/mosquitto.conf`).

### Why we do it

Installs the local broker software with SSL/TLS bridge capabilities and ensures OpenWrt launches Mosquitto using your static custom configuration file instead of dynamically generated UCI defaults.

### Procedure

Run over SSH:

```sh
opkg install mosquitto-ssl mosquitto-client-ssl
opkg list-installed | grep '^mosquitto'
id mosquitto
```

Confirm that the `mosquitto` user account was created.

Configure OpenWrt UCI to use static file configuration:

```sh
cp /etc/config/mosquitto /etc/config/mosquitto.before-buffer 2>/dev/null || true
```

Edit `/etc/config/mosquitto`:

```sh
vi /etc/config/mosquitto
```

Ensure the configuration contains:

```text
config owrt 'owrt'
        option use_uci '0'
```

---

## Step 5: Create persistent storage directories

### What this step does

Creates `/etc/mosquitto/data` (for persistent queue database storage) and `/etc/mosquitto/certs` (for TLS certificates) and sets strict file permissions (`chmod 0750`).

### Why we do it

Isolates queue storage and cryptographic certificates on persistent disk sectors with restricted user permissions so private keys and buffered messages are protected from unauthorized access.

### Procedure

Run over SSH:

```sh
mkdir -p /etc/mosquitto/data /etc/mosquitto/certs
chown mosquitto:mosquitto /etc/mosquitto/data
chmod 0750 /etc/mosquitto/data
chown root:mosquitto /etc/mosquitto/certs
chmod 0750 /etc/mosquitto/certs

df -h /etc/mosquitto/data
mount | grep -E 'overlay| / '
```

Verify that `/etc/mosquitto/data` resides on persistent overlay storage (not `/tmp` RAM disk).

---

## Step 6: Copy and verify certificate files

### What this step does

Installs only the known-good CA plus exact-EUI client certificate/key, cleans debris from failed setups, applies gateway-side ownership, validates certificate contents, and proves the certificate/key pair matches.

### Procedure

#### 1. Clean a reused gateway before importing credentials

```sh
/etc/init.d/mosquitto stop
mv /etc/mosquitto/certs /etc/mosquitto/certs.before-fix 2>/dev/null || true
mkdir -p /etc/mosquitto/certs
chown mosquitto:mosquitto /etc/mosquitto/certs
chmod 0750 /etc/mosquitto/certs
```

A zero-byte `ca.crt`, a certificate for an old EUI, or generic credentials from an earlier attempt can make TLS troubleshooting misleading. Keep old files outside the active directory.

#### 2. Copy only the current gateway files

On the administration workstation:

```bash
scp <MQTT_CA_CERT_FILE> root@<GATEWAY_IP>:/tmp/ca.crt
scp <GATEWAY_MQTT_CERT_FILE> root@<GATEWAY_IP>:/tmp/<GATEWAY_EUI>.crt
scp <GATEWAY_MQTT_KEY_FILE> root@<GATEWAY_IP>:/tmp/<GATEWAY_EUI>.key
```

On the gateway:

```sh
cp /tmp/ca.crt /etc/mosquitto/certs/ca.crt
cp /tmp/<GATEWAY_EUI>.crt /etc/mosquitto/certs/<GATEWAY_EUI>.crt
cp /tmp/<GATEWAY_EUI>.key /etc/mosquitto/certs/<GATEWAY_EUI>.key

chown mosquitto:mosquitto /etc/mosquitto/certs/ca.crt \
  /etc/mosquitto/certs/<GATEWAY_EUI>.crt \
  /etc/mosquitto/certs/<GATEWAY_EUI>.key
chmod 0644 /etc/mosquitto/certs/ca.crt /etc/mosquitto/certs/<GATEWAY_EUI>.crt
chmod 0600 /etc/mosquitto/certs/<GATEWAY_EUI>.key
rm -f /tmp/ca.crt /tmp/<GATEWAY_EUI>.crt /tmp/<GATEWAY_EUI>.key
ls -lah /etc/mosquitto/certs/
```

On a protected **server staging** directory, `root:root 0600` for the private key is acceptable. On the **gateway**, a root-owned `0600` key is unreadable by Mosquitto; the active key must be readable only by the Mosquitto service account.

Expected active gateway directory: exactly `ca.crt`, `<GATEWAY_EUI>.crt`, `<GATEWAY_EUI>.key`; none are zero bytes.

#### 3. Verify certificate contents and key match

```sh
openssl x509 -in /etc/mosquitto/certs/ca.crt -noout -subject -issuer
openssl x509 -in /etc/mosquitto/certs/<GATEWAY_EUI>.crt -noout -subject -issuer -dates

CERT_HASH="$(openssl x509 -in /etc/mosquitto/certs/<GATEWAY_EUI>.crt -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum | cut -d' ' -f1)"
KEY_HASH="$(openssl pkey -in /etc/mosquitto/certs/<GATEWAY_EUI>.key -pubout -outform DER | sha256sum | cut -d' ' -f1)"
echo "CERT: $CERT_HASH"
echo "KEY : $KEY_HASH"
```

The client certificate subject must be `CN = <GATEWAY_EUI>` and the hashes must match.

---

## Step 7: Create the Mosquitto configuration file

### What this step does

Writes `/etc/mosquitto/mosquitto.conf` for the loopback listener/persistence and `/etc/mosquitto/conf.d/bridge.conf` for the two mTLS bridges (`cloud-uplink` QoS 1 and `cloud-downlink` QoS 0).

### Why we do it

Binds the local listener strictly to loopback (`127.0.0.1`) so local services can connect anonymously without exposing port 1883 to the network, and creates persistent outbound mTLS bridges for reliable cloud communication.

### Procedure

Back up an existing static configuration:

```sh
[ ! -f /etc/mosquitto/mosquitto.conf ] || cp /etc/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf.before-buffer
```

Create `/etc/mosquitto/mosquitto.conf` for the loopback listener and persistence:

```sh
mkdir -p /etc/mosquitto/conf.d
cat > /etc/mosquitto/mosquitto.conf <<'EOF'
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

Create `/etc/mosquitto/conf.d/bridge.conf`:

```sh
cat > /etc/mosquitto/conf.d/bridge.conf <<'EOF'
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
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/<GATEWAY_EUI>.crt
bridge_keyfile /etc/mosquitto/certs/<GATEWAY_EUI>.key
bridge_insecure false
topic as923/gateway/<GATEWAY_EUI>/event/# out 1
topic as923/gateway/<GATEWAY_EUI>/state/# out 1

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
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/<GATEWAY_EUI>.crt
bridge_keyfile /etc/mosquitto/certs/<GATEWAY_EUI>.key
bridge_insecure false
topic as923/gateway/<GATEWAY_EUI>/command/# in 0
EOF
```

The bridge hostname must appear in the broker certificate SAN. If local DNS does not resolve the approved SAN name, add a gateway `/etc/hosts` mapping. For the working lab certificate, which contains `DNS:lora-test-server` but not `192.168.8.50`, the gateway uses:

```sh
printf '%s\n' '192.168.8.50 lora-test-server' >> /etc/hosts
```

and both bridge addresses use `lora-test-server:8883`. Do not use an IP absent from the SAN and do not set `bridge_insecure true`.

Verify both active files and replace all placeholders:

```sh
grep -n '<[^>]*>' /etc/mosquitto/mosquitto.conf /etc/mosquitto/conf.d/bridge.conf || true
```

---

## Step 8: Test the configuration in the foreground

### What this step does

Executes `mosquitto -c /etc/mosquitto/mosquitto.conf -v` in the terminal foreground to test parsing, listener binding, and mTLS certificate handshake.

### Why we do it

Catches configuration syntax errors, certificate mismatch issues, or network routing errors in real time before starting the daemon in the background.

### Procedure

Stop the service if it is running:

```sh
/etc/init.d/mosquitto stop
mosquitto -c /etc/mosquitto/mosquitto.conf -v
```

Because this configuration uses `log_dest syslog`, foreground output can appear blank after Mosquitto reports that it loaded `conf.d/bridge.conf`. That is not a hang. In another SSH session inspect:

```sh
logread -e mosquitto | tail -n 100
# or live:
logread -f -e mosquitto
```

Pass when the config parses, the listener binds to `127.0.0.1:1883`, both bridges complete mTLS, and normal keepalive `PINGREQ` / `PINGRESP` messages continue.

### Step 8A: Isolate TCP, TLS, and MQTT authorization

These are three different tests. Run them in this order when the bridge cannot connect.

**A. Raw TCP reachability**

```sh
nc -w 3 <MQTT_BROKER_FQDN> 8883 </dev/null
echo $?
```

Exit `0` proves only route + TCP port reachability. Binary output from `nc` against a TLS port is normal.

**B. TLS + hostname + client-certificate verification**

```sh
openssl s_client \
  -connect <MQTT_BROKER_FQDN>:8883 \
  -servername <MQTT_BROKER_FQDN> \
  -verify_hostname <MQTT_BROKER_FQDN> \
  -verify_return_error \
  -CAfile /etc/mosquitto/certs/ca.crt \
  -cert /etc/mosquitto/certs/<GATEWAY_EUI>.crt \
  -key /etc/mosquitto/certs/<GATEWAY_EUI>.key \
  </dev/null
```

Pass evidence includes `Verification: OK`, `Verified peername: <MQTT_BROKER_FQDN>`, and `Verify return code: 0 (ok)`.

**C. MQTT authentication + ACL**

```sh
mosquitto_pub \
  -h <MQTT_BROKER_FQDN> -p 8883 \
  --cafile /etc/mosquitto/certs/ca.crt \
  --cert /etc/mosquitto/certs/<GATEWAY_EUI>.crt \
  --key /etc/mosquitto/certs/<GATEWAY_EUI>.key \
  -i gw-cert-test-<GATEWAY_EUI> \
  -t '<REGION_TOPIC_PREFIX>/gateway/<GATEWAY_EUI>/state/test' \
  -m 'mtls-auth-test' -q 1 -d
```

`CONNACK (0)` proves MQTT authentication. `PUBACK (... RC:0)` proves the ACL allowed publication.

---

## Step 9: Enable and start Mosquitto

### What this step does

Enables Mosquitto at boot (`/etc/init.d/mosquitto enable`), restarts the service, and verifies process status and port binding (`127.0.0.1:1883`).

### Why we do it

Ensures the persistent local buffer runs automatically on every boot and verifies that port 1883 is securely bound only to local loopback.

### Procedure

Run over SSH:

```sh
/etc/init.d/mosquitto enable
/etc/init.d/mosquitto restart
sleep 3
ps w | grep '[m]osquitto'
```

Verify local loopback listener binding:

```sh
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Confirm that the output shows `127.0.0.1:1883`.

Check persistence directory creation:

```sh
ls -ld /etc/mosquitto/data /etc/mosquitto/certs
ls -l /etc/mosquitto/data
```

---

## Step 10: Include broker files in Gateway OS backups

### What this step does

Appends `/etc/mosquitto/` to `/etc/sysupgrade.conf`.

### Why we do it

Guarantees that Mosquitto configuration files, persistent queue settings, and TLS certificates are included in OpenWrt sysupgrade backups and survive future Gateway OS firmware updates.

### Procedure

Run over SSH:

```sh
grep -qxF '/etc/mosquitto/' /etc/sysupgrade.conf 2>/dev/null || printf '%s\n' '/etc/mosquitto/' >> /etc/sysupgrade.conf
cat /etc/sysupgrade.conf
```

Generate a fresh LuCI backup archive (**System > Backup / Flash Firmware > Generate archive**) and save it in a secure location off-device.

---

## Step 11: Capture an off-device configuration integrity baseline

### What this step does

Creates fingerprints for the gateway broker configuration and public certificate identity and copies the results off the gateway. This detects later configuration drift; it does **not** prove that queued message contents were never changed.

### Why we do it

If an attacker or accidental change modifies the bridge endpoint, topic rules, listener binding, or certificate files, a baseline retained somewhere other than the Raspberry Pi gives the operator an independent value to compare against. A checksum kept only beside the file it protects is not an independent security reference.

### Procedure

On the gateway, create a sanitized baseline file without copying the private key itself:

```sh
umask 077
{
  printf 'gateway_eui=%s\n' '<GATEWAY_EUI>'
  printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sha256sum /etc/mosquitto/mosquitto.conf /etc/mosquitto/conf.d/bridge.conf
  openssl x509 -in /etc/mosquitto/certs/<GATEWAY_EUI>.crt -noout -fingerprint -sha256 -serial -dates
  openssl x509 -in /etc/mosquitto/certs/ca.crt -noout -fingerprint -sha256 -subject -issuer
} > /tmp/gateway-mqtt-security-baseline.txt
cat /tmp/gateway-mqtt-security-baseline.txt
```

On the administration workstation, copy the baseline into the protected gateway records:

```bash
scp root@<GATEWAY_IP>:/tmp/gateway-mqtt-security-baseline.txt ./<GATEWAY_EUI>-mqtt-security-baseline.txt
```

Then remove the temporary gateway copy:

```sh
rm -f /tmp/gateway-mqtt-security-baseline.txt
```

Store the workstation copy with the approved Gateway OS image hash, configuration backup, certificate issuance record, and recovery documentation. During later verification, recalculate the same values and compare them with this off-device baseline. A mismatch requires investigation before normal service resumes.

---

## Troubleshooting

### Mosquitto starts with generated UCI file instead of static config
Inspect `/etc/config/mosquitto` and ensure `option use_uci '0'` is set.

### Permission denied for private key or data folder
Ensure `/etc/mosquitto/certs/<GATEWAY_EUI>.key` is owned by `mosquitto:mosquitto` with mode `0600`. A server-staging `root:root 0600` key must not be copied onto the gateway without changing ownership.

### Bridge reports connection refused or unknown CA
Verify system time (`date -u`), DNS resolution (`nslookup <MQTT_BROKER_FQDN>`), and certificate file paths.

---

## Completion check

Before moving to the next manual, verify that:
- [ ] Mosquitto runs from `/etc/mosquitto/mosquitto.conf`.
- [ ] Port `1883` listens exclusively on `127.0.0.1`.
- [ ] Both outbound mTLS bridges connect successfully over port `8883`.
- [ ] Persistent queue data directory `/etc/mosquitto/data/` exists on overlay storage.
- [ ] `/etc/mosquitto/` is added to `/etc/sysupgrade.conf`.
- [ ] An off-device configuration/certificate integrity baseline has been captured.
- [ ] The operator understands that `mosquitto.db` is a bounded availability queue and is not claimed to be root-tamper-proof.

---

## Next step

Continue with [04a-configure-gateway-integrity-journal.md](04a-configure-gateway-integrity-journal.md) to add the independent evidence path, then configure MQTT Forwarder in [05-configure-mqtt-forwarder.md](05-configure-mqtt-forwarder.md).
