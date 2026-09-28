# Chapter 6 — Set Up ChirpStack and Register the Gateway and Sensors

## 6.1 Know which screen and server you are using

ChirpStack is the cloud LoRaWAN network server, **not** the Gateway-01 web page. Gateway-01's ChirpStack Gateway OS sends AS923 gateway events through the local broker and LTE to cloud ChirpStack. Two ChirpStack application instances run on ULC-01 and ULC-02, sharing the commissioned PostgreSQL and Valkey service routes. The public operator address is `https://smartagri-chirpstack.duckdns.org/`; the two private application listeners use port `18080`.

1. Connect the research workstation to the Internet. Open the exact HTTPS address above in a browser; do not type a bare ULC private address into an off-site browser.
2. Confirm the browser shows the expected HTTPS origin and an uncompromised certificate. Sign in with your *existing approved ChirpStack account*. Do not record the password in screenshots or in this manual.
3. Check that the operator home page appears, then locate the tenant, applications, device profiles and gateways in the left navigation. An empty list on the wrong tenant is not proof a device was deleted.

<!-- CHIRPSTACK_LOGIN_REAL -->

**Screen 6A — the project's real ChirpStack sign-in page.** Match its site identity, then enter your own approved login; the example has no visible password.

<!-- CHIRPSTACK_OPERATOR_REAL -->

**Screen 6B — the project's real ChirpStack operator page.** Use the actual navigation shown on the screen. Do not assume an old mock-up's menu arrangement matches the running version.

**Windows PowerShell — confirm the HTTPS endpoint without revealing credentials:**

```powershell
curl.exe --silent --show-error --output NUL --write-out 'HTTPS=%{http_code}\n' 'https://smartagri-chirpstack.duckdns.org/'
```

Expected: an HTTPS response (normally `200`, or a redirect if the running ingress uses one). HTTP alone does **not** prove MQTT, LoRaWAN acceptance, OTAA, database health or sensor telemetry.

## 6.2 Find the correct Gateway-01 entry

1. In the selected tenant, open **Gateways**. Search for Gateway EUI `0016c001f139a1cb`; copy and compare all sixteen hexadecimal characters.
2. Open that gateway. Verify it belongs to the intended tenant and the expected AS923 installation. A descriptive display name is not a replacement for the EUI.
3. On the gateway **Dashboard**, read **Last seen**; open **LoRaWAN frames** to inspect received frames. Match a new frame time to the authorized uplink; an older timestamp is historical evidence.
4. Do not add a second gateway record or alter the regional plan just to force activity. If there is no new event, use §6.6 to separate cloud service availability from MQTT delivery and RF.

**Acceptance:** exactly the approved gateway EUI is found; new activity is observed *only when* an actual gateway frame is received. Note the capture time and the gateway EUI together.

## 6.3 Locate and check the registered device profile

1. In the tenant navigation, open **Device Profiles**. Find the exact profile linked under **Applications → dissertation-sensors → Devices** for the registered sensor; device profiles are tenant-level, not a submenu inside the application.
2. Verify the profile's LoRaWAN/MAC/PHY versions against that device's compiled firmware, region **AS923**, OTAA activation and RX settings. Compare across the gateway's *effective* configuration and the cloud's *active* region before changing any layer.
3. For the commissioned plain AS923 reference, inspect uplink `923.2` and `923.4 MHz`, RX1 delay `1 s`, RX1 DR offset `0`, and RX2 `923.2 MHz / DR2`. These are known commissioned settings—not a claim that a presently disconnected sensor was measured.
4. Never copy an EU868 profile, choose AS923-2/AS923-3 by guesswork, clear counters or reveal OTAA keys in a screenshot.

**Acceptance:** the profile actually assigned to the device is consistent with the same firmware and active server/gateway region. If not, record the exact mismatch before making a coordinated, backed-up migration.

## 6.4 Inspect EMU-01 / SEC-01 without revealing root keys

1. Open **Applications → dissertation-sensors → Devices** and select the registered EMU-01 by DevEUI `ac1f09fffe296d29`. SEC-01 may intentionally remain unregistered and parked for security testing: do not add or join it merely to populate a screenshot.
2. Compare the displayed DevEUI and JoinEUI with the firmware/approved protected commissioning record. Make sure the attached profile is the one checked in §6.3.
3. Open **Events** and filter to the test device. If the device is powered and joined, a new `up` event should show a recent event time, frame counter and gateway context. **An idle device has no reason to produce a new event.**
4. For join troubleshooting, distinguish JoinRequest, JoinAccept and later `up` events. Do not paste AppKey/NwkKey or API tokens into the manual, terminal, recorder or screenshot.
5. Capture the *real* device overview and one real event in this section during the connected-hardware run. Never replace them with an unrelated tenant/device screenshot.

**Acceptance:** the existing device identity and profile match the actual sensor; one fresh accepted application event is required to claim a live uplink, while a profile/registration review alone is a read-only setup check.

## 6.5 Verify both cloud application instances safely

Perform these commands on **ULC-01 and ULC-02, separately**, over your approved SSH administrator session. These are Linux/Bash commands; do not paste them into the Windows or Gateway-01 shell.

**ULC application host — inspect container and the private HTTP listener:**

```bash
echo '=== APPLICATION HOST AND UTC ==='
hostname -f
date -u
echo '=== CHIRPSTACK CONTAINER ==='
sudo docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' | grep -i chirpstack || true
echo '=== PRIVATE APP HTTP ==='
sudo ss -lntp | grep ':18080' || true
```

Expected: one intended ChirpStack container on each application node, no restart loop, and each node's private `:18080` listener. Port `:8080` on the host is *not* the commissioned public ChirpStack listener.

**ULC application host — check that node's actual VPC listener:**

```bash
APP_IP=$(hostname -I | tr ' ' '\n' | grep '^10\.104\.' | head -n 1)
test -n "$APP_IP" || { echo 'No verified VPC address'; exit 1; }
curl --silent --show-error --output /dev/null --write-out 'CHIRPSTACK_HTTP=%{http_code}\n' "http://$APP_IP:18080/"
```

Expected: `CHIRPSTACK_HTTP=200` on both hosts. A successful web response is only one layer of acceptance, not proof of fresh RF or database writes.

**ULC application host — bounded error check:**

```bash
sudo docker logs --since 10m --tail 80 chirpstack 2>&1 |
  grep -Ei 'error|panic|postgres|valkey|redis|mqtt|region' | tail -n 35 || true
```

If a container has a different *discovered* name, replace `chirpstack` above with that name shown by the first block. Do not show environment files, DSNs, certificates' private keys or full credentials.

## 6.6 Trace a fresh sensor message to the correct layer

1. In a live permitted test, keep Gateway-01, SIM7600 LTE, cloud ChirpStack and exactly the chosen registered sensor active.
2. First observe the local gateway event in Chapter 5's **one-event** MQTT command. A binary-looking payload is normal gateway Protobuf; the topic and time matter.
3. In ChirpStack **Gateways → Gateway-01 → LoRaWAN frames**, confirm a new matching frame. In **Application → Devices → selected sensor → Events**, confirm a new **application uplink**. Copy the observed DevEUI, frame counter and timestamp into the designated research recorder.
4. In the Node-RED/telemetry monitor, verify the device's received payload and timestamp independently. A gateway MQTT event alone is not a decoded application event and not a Fabric evidence acceptance.
5. Capture actual gateway-events, device-events and monitor screens for this procedure while their current record is visible. Never present saved historical screens as measurements of a different session.

**Interpretation:** local gateway topic only = radio + local broker; new gateway event in cloud = LTE/bridge/cloud ingress; new ChirpStack device uplink = accepted LoRaWAN application event; database/chart row = downstream Node-RED/telemetry path. The separate trusted gateway journal/evidence verification and Fabric anchoring require their own tests.

## 6.7 Correct a failure at the first broken layer

- **HTTPS inaccessible:** workstation DNS, TLS, network and approved HTTPS ingress; do not open private application ports publicly.
- **One application node not responding:** inspect the one container and the actual private listener before restart. Check shared PostgreSQL/PgBouncer, Valkey writable-primary route, and cloud MQTT dependency separately.
- **Gateway not found:** check the tenant and the exact EUI before creating anything.
- **Gateway found but no fresh events:** local gateway MQTT topic, both TLS bridges, LTE route, cloud broker ACL, `as923` shared subscription, then RF/forwarder.
- **JoinRequest without a completed join:** verify DevEUI/JoinEUI, protected root-key match, assigned device profile, RX1/RX2 and downlink path in that order. Do not reset frame counters as a generic fix.
- **Fresh device event but no chart row:** inspect the one active Node-RED writer and telemetry PostgreSQL; changing gateway radio settings will not fix this layer.

**Do not** rebuild two instances, rerun database migrations, rotate device keys or restart the whole HA system for an unclassified missing event. When replacing an application node, preserve both current configurations, pinned image digest, shared API secret and individual MQTT client identities; validate the surviving node before the repaired instance rejoins.
