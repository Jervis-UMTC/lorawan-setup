# Chapter 5 — Verify Local MQTT Buffer and Secure Cloud Bridges

## 5.1 Follow the packet, not the indicator light

Gateway-01 takes AS923 packets from the RAK5146 through Concentratord and ChirpStack MQTT Forwarder. **MQTT Forwarder publishes to the local Mosquitto broker at `127.0.0.1:1883`.** Local Mosquitto then maintains two independently authenticated connections to the approved cloud broker on TLS port `8883`: `cloud-uplink` sends gateway event/state and `cloud-downlink` receives gateway commands. The SIM7600/LTE route from Chapter 4 carries these cloud connections. A connected modem alone does not prove MQTT delivery.

Local Mosquitto is an **availability buffer**, not an immutable security log or a LoRaWAN authentication authority. Its persistence file is `/etc/mosquitto/data/mosquitto.db`. The separate gateway integrity journal and the cloud evidence verifier are handled in later chapters. Keep the queue and journal intact during troubleshooting.

## 5.2 Sign in without changing a working installation

1. Power the approved gateway and connect your laptop to its **management Ethernet**, as described in Chapter 2.
2. In Windows PowerShell, run `ssh root@192.168.20.11`, authenticate using your approved gateway credential, and confirm the prompt belongs to Gateway-01. **All shell commands in this chapter run inside Gateway-01's OpenWrt shell, not Windows PowerShell.**
3. Do not change Mosquitto, certificates, routing or the gateway region merely to make a health-check screenshot. If the gateway is unreachable, use Chapter 2's management troubleshooting before continuing.

**Gateway-01 — identify the actual device and clock:**

```sh
echo '=== GATEWAY AND UTC ==='
uname -n
date -u
echo '=== MOSQUITTO PACKAGE AND PROCESS ==='
opkg list-installed | grep '^mosquitto' || true
ps w | grep '[m]osquitto' || true
```

**Expected:** the commissioned gateway name, plausible UTC, Mosquitto package and a running broker process. If Mosquitto is absent, restore the commissioned image or follow the gateway Mosquitto provisioning procedure; do not paste arbitrary internet configuration onto a working system.

## 5.3 Read the local broker settings

1. In the same gateway SSH session, run the following block.
2. Find `option use_uci '0'`: this project uses a **static Mosquitto file**, not a newly generated default config.
3. Find `listener 1883 127.0.0.1`, `persistence true`, and `persistence_location /etc/mosquitto/data/`.
4. Check `max_queued_messages 100000`, `max_queued_bytes 104857600`, `queue_qos0_messages false`, and `autosave_interval 60` against the actual installed configuration. These are the committed baseline, **not a promise of a fixed 100 MB on-disk database or exactly 60 seconds maximum lost data**.

**Gateway-01 — safe configuration readout:**

```sh
echo '=== MOSQUITTO STARTUP MODE ==='
uci -q show mosquitto
echo '=== LOCAL BROKER BASELINE ==='
grep -E '^(user |persistence |persistence_location |persistence_file |autosave_interval |max_queued_messages |max_queued_bytes |max_inflight_messages |queue_qos0_messages |listener |allow_anonymous |include_dir )' /etc/mosquitto/mosquitto.conf
echo '=== PERSISTENT STORAGE ==='
df -h /etc/mosquitto/data
ls -ld /etc/mosquitto/data
ls -lh /etc/mosquitto/data/mosquitto.db 2>/dev/null || true
```

**Expected:** a static broker configuration, persistent queue directory on writable overlay storage and no disk-full condition. The `mosquitto.db` file may not exist until the first autosave. `allow_anonymous true` is acceptable **only** on the loopback listener; exposing it on a LAN or public address is not the project design.

## 5.4 Prove that the local MQTT port is private

1. Run the next block inside Gateway-01.
2. Read the `LISTEN` address, not just the port number.
3. Accept `127.0.0.1:1883`. Stop if the listener is `0.0.0.0:1883`, `:::1883`, or an externally reachable IP; review the effective config before touching firewall rules.

**Gateway-01 — local listener check:**

```sh
echo '=== MOSQUITTO LOCAL PORT ==='
ss -lnt 2>/dev/null | grep ':1883' || netstat -lnt 2>/dev/null | grep ':1883'
echo '=== MQTT FORWARDER TARGET ==='
uci -q show chirpstack-mqtt-forwarder
```

**Expected:** local-only broker `127.0.0.1:1883`; forwarder `tcp://127.0.0.1:1883`, topic prefix `as923` and QoS `1`. MQTT Forwarder must **not** connect straight to the cloud, which would bypass the designed buffer.

## 5.5 Read the two bridge identities and topics

1. Open the installed bridge settings using the command below. This prints **filenames and configuration entries only**, not certificate or private-key bodies.
2. Locate exactly two `connection` blocks: `cloud-uplink` and `cloud-downlink`. Each must have an approved hostname (matching the broker certificate) and port `8883`.
3. The uplink bridge exports `as923/gateway/<GATEWAY_EUI>/event/#` and `state/#` at QoS 1. The downlink bridge imports `as923/gateway/<GATEWAY_EUI>/command/#` at QoS 0. Replace the angle-bracket example in your understanding with the **actual deployed EUI**; do not type placeholders into working configuration.
4. Confirm `bridge_insecure false` for both bridges. A hostname missing from the server certificate SAN will cause a correct TLS failure; do not bypass verification.

**Gateway-01 — bridge settings, with private-key contents excluded:**

```sh
echo '=== TWO BRIDGES, DESTINATIONS AND TOPICS ==='
grep -E '^(connection |address |remote_clientid |cleansession |bridge_protocol_version |bridge_cafile |bridge_certfile |bridge_keyfile |bridge_insecure |topic )' /etc/mosquitto/conf.d/bridge.conf
echo '=== CERTIFICATE FILES ONLY — NO KEY CONTENT ==='
ls -l /etc/mosquitto/certs
echo '=== RECENT BRIDGE LOGS ==='
logread | grep -Ei 'mosquitto|bridge|connack|tls' | tail -n 28
```

**Expected:** two distinct client IDs, paths to the CA/client certificate/key, one outgoing and one incoming topic path, and no ongoing TLS or ACL rejection. The private key should be accessible to the Mosquitto service account only. Do not publish its contents in screenshots, research appendices, or test transcripts.

## 5.6 Prove both cloud connections take the LTE path

1. Run the next block. Check the approved hostname printed by Section 5.5 against the current DNS result rather than relying on a historic server IP.
2. Confirm the current default/approved broker route uses `wwan0`; Chapter 4 explains the controller-managed metric-10 LTE route.
3. Check for **two intended established connections** to `:8883`. A TCP connection is necessary but is **not** by itself proof of a successfully delivered sensor message.

**Gateway-01 — routing and two bridge sockets:**

```sh
echo '=== LTE ADDRESS AND DEFAULT ROUTE ==='
ip -4 addr show dev wwan0
ip route show default
echo '=== APPROVED MQTT BROKER RESOLUTION ==='
nslookup smartagri-mqtt.duckdns.org
echo '=== CLOUD MQTT TLS CONNECTIONS ==='
ss -tn 2>/dev/null | grep ':8883' || netstat -tn 2>/dev/null | grep ':8883' || true
echo '=== RECENT MOSQUITTO EVENTS ==='
logread | grep -Ei 'mosquitto|bridge|connack|tls' | tail -n 35
```

**Expected:** cellular interface active, cloud path via LTE and two established broker sockets without recurring authentication failures. If local MQTT passes but cloud fails, inspect LTE, DNS, gateway UTC, TLS hostname and broker ACL—in that order—before touching radio configuration.

## 5.7 Watch one real uplink reach the local broker and cloud

1. Keep Gateway-01, LTE and **one already-registered AS923 sensor** powered. On Gateway-01 open a dedicated SSH session.
2. Run the subscription below and keep it visible; `-C 1` exits after the first matching event. Replace the example EUI with the **real gateway EUI** shown by the currently installed Concentratord/ChirpStack gateway registration. The topic, not the binary payload text, is what this local view proves.
3. Cause one normal uplink from the authorized sensor. Watch for `as923/gateway/<EUI>/event/up` (or the expected gateway event topic).
4. In the cloud ChirpStack device event or Grafana sensor-ingest view, independently confirm a **new event from the same device and time interval**. Screens 5A/5B should be captured from those actual pages during a live run; a historical screenshot alone does not prove this run's delivery.

**Gateway-01 — observe exactly one matching local event:**

```sh
GW_EUI='<REPLACE_WITH_ACTUAL_GATEWAY_EUI>'
mosquitto_sub -h 127.0.0.1 -p 1883 \
  -t "as923/gateway/$GW_EUI/event/#" -v -C 1
```

**Interpret the result:** a local topic means RF → Concentratord → forwarder → local broker worked. A corresponding new ChirpStack event means the cloud path also received and processed it. A message with unreadable binary characters is normal because gateway MQTT can carry Protobuf. Do not mark the entire path PASS on a synthetic MQTT-only publication.

## 5.8 Observe an LTE interruption without erasing buffered traffic

1. Run a **planned** outage test only during the research test window and after the recorder is ready; do not unplug cables as an ordinary setup check.
2. Record the baseline `mosquitto.db` size, free disk space, LTE state and device event sequence. Keep a real authorized sensor sending.
3. During the controlled LTE loss, confirm the local listener is still working and QoS-1 gateway events can accumulate. File size alone does **not** count delivered or lost messages and may update only on autosave.
4. Restore LTE, allow the bridges to reconnect, and compare device frame counters / events at cloud ChirpStack against the test recorder. Never assume exactly-once delivery: QoS 1 can resend and downstream processing must be duplicate-aware.
5. Do not delete `mosquitto.db`, truncate logs, reset the journal or run unplanned mass service restarts to make the chart clear.

**Gateway-01 — one non-destructive before/during/after snapshot:**

```sh
echo '=== UTC AND LTE STATUS ==='
date -u
ubus call network.interface.lte status
echo '=== LOCAL BROKER AND QUEUE FILE ==='
ps w | grep '[m]osquitto'
ls -lh /etc/mosquitto/data/mosquitto.db 2>/dev/null || true
df -h /etc/mosquitto/data
echo '=== CLOUD BRIDGE STATUS ==='
ss -tn 2>/dev/null | grep ':8883' || netstat -tn 2>/dev/null | grep ':8883' || true
echo '=== RECENT BRIDGE RECONNECT EVIDENCE ==='
logread | grep -Ei 'mosquitto|bridge|connack|tls' | tail -n 30
```

**Expected after recovery:** LTE works, both cloud bridge sessions return, and the independently recorded cloud event sequence reconciles with the generated sensor uplinks. A successful reconnect without the end-to-end count comparison is an incomplete recovery result.

## 5.9 Keep the broker recoverable

1. In Gateway-01 LuCI, open **System → Backup / Flash Firmware**, generate an archive and save it **off the gateway** using the project's protected backup location.
2. Verify that `/etc/mosquitto/` is included in the approved backup manifest. TLS private keys and queue files may be sensitive; protect and restrict the archive.
3. Never display the private-key body or paste backup contents into the manual. The gateway integrity journal needs its separate documented custody procedure; a broker backup alone is not evidence preservation.

**Gateway-01 — backup preflight only; no destructive operation:**

```sh
echo '=== BACKUP INCLUSION ==='
grep -n '^/etc/mosquitto/' /etc/sysupgrade.conf || true
echo '=== BROKER FILE LOCATIONS ==='
ls -ld /etc/mosquitto /etc/mosquitto/conf.d /etc/mosquitto/data /etc/mosquitto/certs
echo '=== OVERLAY FREE SPACE ==='
df -h /
```

**Next:** configure/verify the ChirpStack MQTT Forwarder and the separate integrity journal before the full sensor → cloud → evidence → Fabric research test.
