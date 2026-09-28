# Mosquitto MQTT — Commissioned Installation, Security and Recovery

**Read this first.** Gateway-01 uses its own persistent, loopback-only Mosquitto; ULC-01 and ULC-02 run the independent cloud Mosquitto preferred/backup service. This is a complete *technology-specific* setup/restore explanation and expands [operator guide 04](04-mosquitto-mqtt.md). The recorded topology is a commissioned baseline, not a claim of today's live health. **OpenWrt/BusyBox** and **Ubuntu/Bash** commands are not interchangeable.

## 1. Follow a real uplink

~~~text
Sensor -> AS923 -> RAK5146 -> Concentratord -> MQTT Forwarder (QoS 1)
  -> Gateway Mosquitto 127.0.0.1:1883 /etc/mosquitto/data/mosquitto.db
     -> outbound cloud-uplink bridge (QoS 1, persistent)
     <- inbound cloud-downlink bridge (QoS 0, clean session)
  -> SIM7600 wwan0 -> smartagri-mqtt.duckdns.org:8883 (mTLS)
  -> current public HAProxy/Reserved-IP owner
  -> preferred/backup Mosquitto broker :8884
  -> node-local ChirpStack MQTT route :18883 -> :8885
  -> ChirpStack -> application event -> node-local Node-RED MQTT :18884 -> :8886
  -> single active Node-RED -> PostgreSQL
~~~

The cloud brokers **do not replicate MQTT sessions**. HAProxy favors a healthy broker and clients reconnect after a failure; avoid round-robin session switching. QoS 1 is *at least once*, not exactly once: duplicates are handled by canonical application/database idempotency. MQTT persistence is an availability queue, **not immutable evidence**; the separate Concentratord-sourced gateway journal and cloud verifier own source-evidence integrity.

## 2. Port, identity and firewall contract

| Interface | Commissioned use | Important boundary |
|---|---|---|
| Gateway `127.0.0.1:1883` | MQTT Forwarder and local bridge | Anonymous only because **strictly loopback** |
| Public `smartagri-mqtt.duckdns.org:8883` | Two gateway mTLS bridge sessions | Gateway EUI certificate; current public IP/owner must be verified |
| Cloud `<ULC_PRIVATE_IP>:8884` | Gateway-facing Mosquitto | Client certificate required; EUI-scoped ACL |
| Cloud `10.104.0.2:8885` and `10.104.0.4:8885` | ChirpStack separate workload | TLS + hashed service password + directional ACL |
| Node-local `10.104.0.2:18883` and `10.104.0.4:18883` | HAProxy -> cloud `:8885` | TLS passthrough, broker SAN `mqtt.internal.lorawan.com` |
| Cloud `:8886` / node-local `:18884` | Node-RED service identity | Separate private listener/ACL from gateway and ChirpStack |

The historical Reserved IP `129.212.208.168` is a dated identity; don't hard-code a new deployment to it without verifying the current public bridge config and provider owner. The cloud backend and workload listeners are private. **Never expose gateway anonymous 1883, workload 8885/8886, or cloud administrative sockets to the Internet.**

## 3. Gateway-01 bootstrap from the accepted custom image

### 3.1 Inspect first; do not reinstall a working service

Run on Gateway-01:

~~~sh
ubus call system board
date -u
df -h / /etc/mosquitto/data
opkg list-installed | grep '^mosquitto' || true
ps w | grep '[m]osquitto' || true
uci show chirpstack-mqtt-forwarder
uci show chirpstack-udp-forwarder
grep -E '^(persistence|persistence_location|persistence_file|autosave_interval|max_queued_messages|max_queued_bytes|listener|allow_anonymous|include_dir)' /etc/mosquitto/mosquitto.conf 2>/dev/null || true
~~~

**PASS:** listener `127.0.0.1:1883` only; durable overlay path; finite queue budget; MQTT Forwarder `tcp://127.0.0.1:1883`, prefix `as923`, QoS **1**; UDP Forwarder disabled. The accepted September 1 image had an immutable MQTT Forwarder QoS **0** default, repaired in commissioned writable state and tracked *next-build* overlay to QoS 1. A factory flash **alone** is not cloud-ready; it contains no production private keys.

### 3.2 Install missing packages or restore the approved image

**On an entirely new gateway:** after importing reviewed package/configuration material, stop and preserve the previous broker (if any) before writing static settings. For a configuration-only update on a working gateway, make a protected off-gateway backup rather than copying a live private key/queue into an ordinary troubleshooting folder. Use `vi /etc/config/mosquitto`, `vi /etc/mosquitto/mosquitto.conf` and `vi /etc/mosquitto/conf.d/bridge.conf` only after reading their current contents and creating a rollback copy. Never paste an example bridge file over the approved gateway-specific bridge unless the entire intentional provisioning boundary is being restored.

Configuration verification must inspect the actual init/systemd owner and loaded file; successful syntax parsing alone does not authenticate to the remote broker. Before returning a modified gateway to normal operation, load only the reviewed file, reload/restart **only Mosquitto when necessary**, then prove loopback bind, two established bridge sessions and a real RF uplink. For a brand-new instance whose listener port is free, an isolated foreground `mosquitto -c /etc/mosquitto/mosquitto.conf -v` can aid syntax diagnosis; do not run it simultaneously with the existing bound broker.

The custom image normally already includes `mosquitto-ssl` and a boot-time persistent-directory initializer. If genuinely missing, preserve a protected off-gateway backup first and check compatible package feeds/storage on the matching Gateway OS kernel:

~~~sh
df -h /
opkg list-installed | grep '^mosquitto' || true
opkg update
opkg list | grep -E '^mosquitto-(ssl|client-ssl) '
~~~

Only if matching packages are available install `opkg install mosquitto-ssl mosquitto-client-ssl`. Never force mismatched OpenWrt kernel modules into this custom Gateway OS. Confirm static Mosquitto file mode, rather than a conflicting auto-generated UCI broker: the pinned configuration uses `config owrt 'owrt'` / `option use_uci '0'`. Save existing `/etc/config/mosquitto` before changing.

New installation only:

~~~sh
mkdir -p /etc/mosquitto/data /etc/mosquitto/certs /etc/mosquitto/conf.d
chown mosquitto:mosquitto /etc/mosquitto/data
chmod 0750 /etc/mosquitto/data
chown root:mosquitto /etc/mosquitto/certs
chmod 0750 /etc/mosquitto/certs
df -h /etc/mosquitto/data
~~~

Confirm `/etc/mosquitto/data` is on *persistent overlay*, not `/tmp`.

### 3.3 Local broker static settings and their meanings

The intended fresh-install `/etc/mosquitto/mosquitto.conf` is:

~~~conf
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
~~~

100000 messages and 104857600 bytes (100 MiB) are **finite** configured queue limits, not a guarantee of total SD-card usage or loss-free delivery after exceeding the cap. `autosave_interval 60` does not guarantee that an unexpected power loss can lose only exactly 60 seconds of state. Preserve disk reserve and the *separate* gateway evidence storage budget.

### 3.4 Import protected certificates after flashing

Obtain the currently approved gateway bundle from secured out-of-repository recovery storage, not the image or a lab archive:

~~~text
/etc/mosquitto/certs/ca.crt
/etc/mosquitto/certs/0016c001f139a1cb.crt
/etc/mosquitto/certs/0016c001f139a1cb.key
~~~

Transfer it over approved authenticated management access; on this minimal OpenWrt, modern default SCP/SFTP may fail because `sftp-server` is absent, so use the established compatible legacy-SCP or protected alternative. Verify incoming file hashes against the protected manifest, then install with the broker's effective user allowed to read the key; an unreviewed `root:root 0600` key may be unreadable. Do not publish the key, old Wi-Fi passphrase, password hash, protected private bundle or other secret in Markdown, logs or PDF.

~~~sh
ls -l /etc/mosquitto/certs
openssl x509 -in /etc/mosquitto/certs/0016c001f139a1cb.crt -noout -subject -issuer -dates -fingerprint -sha256
openssl x509 -in /etc/mosquitto/certs/ca.crt -noout -subject -issuer
~~~

**PASS:** nonempty CA and certificate; client CN exactly matches the authoritative RAK5146 Gateway EUI `0016c001f139a1cb`; CA/server identity and expiry valid; key matches certificate via public-key comparison without printing private contents; temp cleartext transfer files removed after protected verification.

### 3.5 Configure the two distinct mTLS bridges

Preserve current `/etc/mosquitto/conf.d/bridge.conf` before editing. For an intentional *new* provisioning, use the approved public broker FQDN, and this exact directional identity/QoS contract:

~~~conf
connection cloud-uplink
address smartagri-mqtt.duckdns.org:8883
bridge_protocol_version mqttv311
remote_clientid gw-up-0016c001f139a1cb
cleansession false
start_type automatic
restart_timeout 5 60
keepalive_interval 30
notifications false
try_private false
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/0016c001f139a1cb.crt
bridge_keyfile /etc/mosquitto/certs/0016c001f139a1cb.key
bridge_insecure false
topic as923/gateway/0016c001f139a1cb/event/# out 1
topic as923/gateway/0016c001f139a1cb/state/# out 1

connection cloud-downlink
address smartagri-mqtt.duckdns.org:8883
bridge_protocol_version mqttv311
remote_clientid gw-down-0016c001f139a1cb
cleansession true
start_type automatic
restart_timeout 5 60
keepalive_interval 30
notifications false
try_private false
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_certfile /etc/mosquitto/certs/0016c001f139a1cb.crt
bridge_keyfile /etc/mosquitto/certs/0016c001f139a1cb.key
bridge_insecure false
topic as923/gateway/0016c001f139a1cb/command/# in 0
~~~

**Why two sessions:** uplink/event/state QoS 1 retains work through LTE outages; downlink command QoS 0 clean session does not intentionally replay expired Class A commands. Never turn off server-name verification to fix wrong DNS/certificate, point MQTT Forwarder directly to the public broker, or run simultaneous arbitrary UDP forwarding.

### 3.6 Prove this boundary

~~~sh
ps w | grep '[m]osquitto'
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
logread -e mosquitto | tail -n 80
ip route get 129.212.208.168
ss -tnp 2>/dev/null | grep ':8883' || netstat -tnp 2>/dev/null | grep ':8883' || true
~~~

**PASS:** 127.0.0.1 listener, no broker auth/TLS loop, two established cloud sessions routed over `wwan0` *when LTE is commissioned and healthy*. Use the *currently configured* broker IP if it differs from the historical address. A socket alone does not prove a real uplink. With an approved powered sensor, observe a new local `as923/gateway/0016c001f139a1cb/event/#` event (binary Protobuf is normal), cloud event, ChirpStack application acceptance and one canonical database event.

## 4. Cloud brokers: reproduce the deployed layout, not the earlier plan

ULC-01/02 commissioned **Mosquitto 2.0.18 system services**. Their real installed paths are `/etc/mosquitto/mosquitto.conf`, `/etc/mosquitto/conf.d/*.conf`, `/etc/mosquitto/gateway.acl`, `/etc/mosquitto/chirpstack.passwd`, `/etc/mosquitto/chirpstack.acl` and protected `/etc/lorawan-pki/mqtt/` files. The old generic planning example for Docker-mounted `/etc/lorawan-cloud/mosquitto` is **not** the installed baseline. Rebuild a host with the exact approved package/config/identity backups rather than silently installing a newer candidate.

On *each cloud broker host*, inspect without dumping password/secret values:

~~~bash
hostname -f
dpkg-query -W -f='package=${binary:Package} version=${Version}\n' mosquitto 2>/dev/null
sudo systemctl is-active mosquitto
sudo systemctl is-enabled mosquitto
sudo ss -lntp | grep -E ':(8884|8885|8886)\b' || true
sudo grep -hE '^(per_listener_settings|listener|require_certificate|use_identity_as_username|allow_anonymous|password_file|acl_file|cafile|certfile|keyfile|tls_version)' /etc/mosquitto/mosquitto.conf /etc/mosquitto/conf.d/*.conf
sudo stat -c '%a %U:%G %n' /etc/mosquitto/gateway.acl /etc/mosquitto/chirpstack.passwd /etc/mosquitto/chirpstack.acl
~~~

The keyfile *path* may be logged; the key *contents* must not. **Expected:** per-listener auth; gateway `:8884` uses `require_certificate true`, `use_identity_as_username true` and `allow_anonymous false`; exact-EUI gateway ACL; ChirpStack private `:8885` uses TLS and its own password/ACL; Node-RED `:8886` remains separate. Check node-local HAProxy frontends `:18883` and `:18884`, and public `:8883`, rather than assuming TLS backend port is publicly reachable.

### 4.1 Least-privilege workloads

- **Gateway certificate CN EUI:** can write *only its* `as923/gateway/EUI/event/#` and `state/#`, and read *only its* `command/#`. Unrelated topics and no-cert connections denied.
- **ChirpStack workload:** private `:8885` username/password read gateway event/state, write gateway commands and application events, read application command topics as required; *no unauthorized application event read*.
- **Node-RED writer:** distinct `:8886` identity and approved application event access; not gateway or Fabric administrator.
- **Evidence witness:** independent protected read-only clients observing both cloud brokers, never rewriting gateway events.

**Negative test pitfall:** Mosquitto can SUBACK a subscription while denying actual delivery via ACL. To prove an unauthorized topic is inaccessible, verify **no message can be received/published**, not SUBACK return code alone.

### 4.2 Safe one-at-a-time restore or listener change

1. Identify preferred/backup roles, current public ingress owner and exact TLS SAN; preserve unmodified other node.
2. Back up package version, active `/etc/mosquitto` config/ACL/password files, protected MQTT PKI, systemd overrides, HAProxy config and hashes off-host. **Never** put credential bodies into the notes.
3. On isolated replacement, install *approved* Mosquitto package/version; restore intended ownership/modes and separate auth scope; restrict firewall binds. Validate config with an isolated/loopback-remapped disposable broker or installed version's supported validation procedure **without** competing for production ports.
4. Apply to a single cloud broker; check `:8884/:8885/:8886` listeners, verified SAN/CA, gateway certificate authorization, ChirpStack and Node-RED identity, denied no-cert and forbidden delivery.
5. Repeat for other broker only after the first accepts one legitimate event; check HAProxy preferred/backup behavior and that no unrelated service (especially PostgreSQL) was restarted.
6. Verify gateway two mTLS sessions over LTE and *one new real* ChirpStack/Node-RED uplink; preserve rollback copy until post-change acceptance.

Do not restart both brokers simultaneously or treat two running service processes as proof of client reconnect.

## 5. Start troubleshooting at the first failing layer

| Observed failure | Start diagnosis |
|---|---|
| No local event at Gateway | sensor/RF, Concentratord, MQTT Forwarder and loopback broker |
| Gateway buffer grows, no `:8883` sockets | QMI *public IP dataplane* + DNS/UTC, LTE route, then TLS/auth |
| Public `:8883` down, private `:8884` good | public HAProxy ingress owner/backend and provider route |
| TLS good but CONNACK/ACL denied | cert CN, separate workload identity, exact topic direction |
| Cloud gateway event exists, ChirpStack missing | node-local `:18883 -> :8885`, app auth/shared subscription, AS923 |
| ChirpStack event exists, Node-RED missing | `:18884 -> :8886`, fenced active/passive writer |
| Duplicate canonical rows after reconnect | idempotency/deduplication, not lowering QoS |
| Storage low | stop synthetic traffic; preserve queue/journal and protected backup; don't delete `mosquitto.db` |

**2026-09-21 real incident:** modem/QMI bearer reported connected and a default existed, but public IP and carrier DNS probes timed out; Mosquitto emitted `Error creating bridge: Try again`. Targeted LTE/controller recovery restored both bridge sessions *without changing certificates, broker ACL or management Ethernet*. Never reset a working LTE modem merely because the broker is unavailable or mTLS fails while public IP is healthy.

## 6. Recoverability and what counts as success

Keep separately protected: exact factory image, OpenWrt config archive, MQTT cert/key bundle, queued state as required by retention policy, journal/last accepted server checkpoint, cloud broker ACL/password hashes, CA issuance metadata, exact package version, HAProxy routes and safe rollback. A normal Gateway OS sysupgrade archive may omit `/etc/mosquitto/certs` and `/etc/mosquitto/data`; inspect actual archive contents. Never restore an old journal state past a newer accepted cloud checkpoint.

**PASS:** right listener scope, finite persistent buffer, independently authenticated cloud brokers and workload paths, two bridge sessions over intended cellular route, one real gateway event accepted by ChirpStack and written once to DB, separate gateway-evidence state explicitly checked. Controlled outage/reboot/downlink-staleness and HA failover tests are governed by research/HA runbooks, not ordinary documentation edits.

## Source runbooks and future standalone Word document

The exact implementation/configuration and historical execution evidence is in [gateway MQTT buffer setup](../gateway/setup/04-configure-local-mqtt-buffer.md), [MQTT Forwarder](../gateway/setup/05-configure-mqtt-forwarder.md), [cloud MQTT commissioning](../server/cloud-production/08-mqtt-and-valkey.md), [ChirpStack MQTT identity commissioning](../server/cloud-production/09-chirpstack-cloud-cluster.md), and the [LTE recovery companion](SIM7600-LTE-COMMISSIONING.md). Their *historical lab broker addresses and unexecuted Docker plans* must not supersede this commissioned host-service design. The comprehensive Word document must include operative instructions within the book, not redirect its reader to a Markdown source.
