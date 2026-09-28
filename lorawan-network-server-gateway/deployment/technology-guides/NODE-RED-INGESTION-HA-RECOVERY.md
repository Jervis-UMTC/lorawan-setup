# Node-RED — Commissioned Ingestion, Active/Passive Recovery and Data Integrity

**Audience:** new engineer operating the real ULC-01/02/03 cloud. Read [Node-RED operator guide 10](10-node-red.md) before changing a live flow. This chapter consolidates the commissioned installation/HA/telemetry contract; old `/opt/lorawan-lab` examples and independent `mosquitto` or `telemetry-db` containers are **not** the deployed three-server design. Dated versions/hashes must be compared with the running container and versioned source before replacement. No counted test or live service modification was performed for this documentation.

## 1. In plain English: why it exists

An agricultural sensor transmits over AS923. The gateway relays to cloud ChirpStack; ChirpStack authenticates/decodes and emits the **application** MQTT event. Node-RED normalizes it into independently queryable rows and creates an eligible *candidate* Fabric outbox job according to selection policy. PostgreSQL owns the committed state, the independent verifier owns gateway-evidence truth, and the Fabric adapter owns blockchain submission. **Node-RED has no authority to verify a journal, sign with OpenBao or claim Fabric commit.**

~~~text
EMU-01 -> gateway/ChirpStack -> MQTT application/+/device/+/event/up
         -> Node-RED A (ULC-03 normally)
         -> validate source, payload_version 2, time, event identity
         -> normalize quality/unit and preserve accepted raw_data
         -> parameterized atomic SQL through local PgBouncer :6432
         -> telemetry.uplinks + telemetry.measurements
         -> selected telemetry.fabric_outbox (not instant Fabric commit)
Independent verifier + immutable finalized bytes -> separate sole Fabric writer
Grafana <- read-only SQL (does not write telemetry)
~~~

**Critical reliability limit:** the commissioned Node-RED MQTT subscription is **QoS 0**. Its active/passive failover does not guarantee replay of events delivered while both application subscribers are absent. A retained gateway cloud-uplink QoS 1 queue protects a different earlier hop; it does not change the application's QoS 0 delivery contract. When estimating packet-delivery ratios, do not claim lossless end-to-end delivery on the basis of gateway QoS alone.

## 2. Where components actually live

| Place | Normal status | Dependency endpoint |
|---|---|---|
| ULC-03 / 10.104.0.8 | Node-RED A, only active ingestion writer | node-local `mqtt.internal.lorawan.com:18884` and `pgbouncer.internal.lorawan.com:6432` |
| ULC-02 / 10.104.0.4 | Node-RED B, installed **stopped/fenced** standby | *its own* node-local endpoints, not ULC-03 routes |
| Cloud MQTT | `ULC-01:8886` preferred / `ULC-02:8886` backup | Node-RED mTLS identity, not gateway :8884 or ChirpStack :8885 |
| Editor | `127.0.0.1:1880` on active host | authenticated, access via approved SSH tunnel, not public |
| Database | `lorawan_telemetry`, `telemetry_writer` only | PgBouncer -> HAProxy primary -> current Patroni leader |
| Source | `deployment/server/integrations/node-red/runtime/` | shared reviewable files plus separately protected node-specific env/PKI |

**Rule zero:** do not run both A and B as ordinary application MQTT subscribers. They are NOT active/active load balancers. Database uniqueness is a safety backstop, not permission to run duplicate writers.

## 3. Installed source and reproducibility inventory

The reviewed repository runtime contains `compose.yml`, `settings.js`, `flows.json`, `package.json`, `package-lock.json` and `node-red.env.example`. The commissioning record pinned:

- Node-RED image `nodered/node-red@sha256:10f40d0a83e7e5852b13d4d472b2006b05b1cca6d55e2f29a55a12c25a630cb6`; at inspection Node-RED v5.0.4 / Node.js v24.18.1 / npm v11.19.0.
- Container user UID 1000 (`node-red`); host-specific supplementary `node-red-secrets` GID grants access to its own protected client key and public CA.
- PostgreSQL palette `node-red-contrib-postgresql` version **0.16.2** in reviewed `package.json` / lockfile; do not allow a palette auto-upgrade to reinterpret `msg.query` or `msg.params` unnoticed.
- Frozen mapper ID `agriculture-kit-payload-v2-node-red-v1` in the reviewed flow; flow bytes/hashes must be recalculated from the current chosen bundle rather than a historical checksum.
- Live material belongs under `/etc/lorawan-cloud/node-red` and persistent `/srv/node-red/data`. Do not use the generic lab `/opt/lorawan-lab` directory to repair the cloud; if another operator has moved the active Compose project, discover `docker inspect` mounts/Compose project before writing a second instance.

**Read-only discovery, run separately on ULC-03 and ULC-02 (Ubuntu Bash):**

~~~bash
hostname -f
date -u
cd /etc/lorawan-cloud/node-red
sudo docker compose --env-file node-red.env ps
sudo docker compose --env-file node-red.env config --services
sudo ss -lntp | grep -E ':(1880|18884|6432)\b' || true
sudo stat -c '%a %U:%G %n' /etc/lorawan-cloud/node-red/node-red.env /srv/node-red/data
~~~

**Normal PASS:** A running, B stopped; editor only on A loopback; private MQTT and DB route on both candidate hosts; neither has secrets printed to log. Check current service ownership before using `docker compose up` on a running cluster. Use `sudo docker compose ... logs --since=15m --tail=150 node-red` only for the affected active candidate.

## 4. Fresh deployment / one-host recovery procedure

This section applies to an **authorized fresh empty** candidate or a reviewed replacement. Do not overwrite an operating candidate. Preserve protected flow/data/config backups and stable event/outbox state first. Confirm present commissioned MQTT :8886 ACL/PKI, local :18884 HAProxy, PostgreSQL/Patroni and local :6432 PgBouncer on that host. Resolve the current repository image/flow hashes and restore *separate* private identities: A CN `node-red-ingest`, B CN `node-red-ingest-standby`, each permitted only to read `application/+/device/+/event/up`; each has a **different MQTT client ID**.

### 4.1 Host directory and permission contract

Cloud folders used by the approved deployment:

~~~text
/etc/lorawan-cloud/node-red/
  compose.yml
  node-red.env             (protected host-specific values, mode 0600)
/etc/lorawan-pki/node-red-mqtt/
  client.crt               (own A/B workload identity)
  client.key               (0640 root:node-red-secrets)
/etc/lorawan-pki/node-red-pgbouncer/
  ca.crt                   (copy of approved public CA, not PG private key)
/srv/node-red/data/
  flows.json, settings.js, dependency state (numeric uid 1000)
~~~

Create directories only on a new intended host. Verify the actual `node-red-secrets` GID/UID mapping before assigning ACLs; never add a personal login user to the private-key group. Grant container UID 1000 exactly the supplementary numeric GID via `group_add`, not blanket `chmod 777`. The original PgBouncer CA path is `/etc/lorawan-pki/pgbouncer/ca.crt` and is deliberately inaccessible to arbitrary host processes: copy **only its public CA** to the Node-RED-readable path and hash-compare; never make the PgBouncer key/secret directory broadly readable.

~~~bash
sudo install -d -m 750 /etc/lorawan-cloud/node-red
sudo install -d -m 750 /etc/lorawan-pki/node-red-mqtt
sudo install -d -m 750 /etc/lorawan-pki/node-red-pgbouncer
sudo install -d -m 700 /srv/node-red/data
sudo stat -c '%a %U:%G %n' /etc/lorawan-cloud/node-red /srv/node-red/data
~~~

These create **directories**, not credential identities or a working service; apply reviewed service-user ownership/permissions before starting. Preserve existing data instead of re-chowning or clearing it blindly.

### 4.2 Deploy the reviewed shared bundle

Copy from the repository's reviewed `runtime/` into the intended cloud host, with exact hash comparison on A and B for `compose.yml`, `settings.js`, `flows.json`, `package.json` and `package-lock.json`. Do not copy a live `/srv/node-red/data` tree while A is writing. Back up the previous flow, credential-secret reference and volume before replacing anything. Use node-local protected `node-red.env` on each candidate, not Git or one shared plaintext env file.

The active reviewed runtime Compose file binds `127.0.0.1:1880:1880`, maps each candidate's MQTT/PG hostname to **its own** private IP, mounts the per-host MQTT CA/client certificate/key and the local PgBouncer public CA, and exposes `NODE_EXTRA_CA_CERTS=/run/pgbouncer/ca.crt`. It uses `FABRIC_SELECTED_DEV_EUI` and `FABRIC_SELECTED_SCHEMA_VERSION` as deployment policy. The published example env defaults `FABRIC_SELECTED_DEV_EUI=0000000000000000` (no legitimate production selection); **never call Fabric selected for EMU-01 without verifying the actual protected env**. The shared flow supports both `telemetry-attestation-v1` and `telemetry-attestation-v2`, but claiming eligible v2 requires matching independent verifier output and exact immutable `finalized_payload`. Don't silently change the selected schema solely to make pending jobs disappear.

From the intended host's `/etc/lorawan-cloud/node-red` only, after secrets/CA/image/flows are correct:

~~~bash
sudo docker compose --env-file node-red.env config --quiet
sudo docker compose --env-file node-red.env config --services
sudo stat -c '%a %U:%G %n' node-red.env /srv/node-red/data
~~~

**PASS:** Compose parses; expected one `node-red` service; private key file readable by the container's intended supplementary group, and no plaintext secret printed. On initial commissioning only **A** is started after proving B is stopped and authoritatively fenced:

~~~bash
sudo docker compose --env-file node-red.env up -d node-red
sudo docker compose --env-file node-red.env ps node-red
sudo ss -lntp | grep '127.0.0.1:1880'
~~~

Do not run the start block on B during normal operation.

### 4.3 Protect editor authentication

The approved `settings.js` rejects missing/placeholder runtime env, expects a 64-character hex `NODE_RED_CREDENTIAL_SECRET` and bcrypt `NODE_RED_ADMIN_PASSWORD_HASH`, and uses credential admin auth. Keep `NODE_RED_CREDENTIAL_SECRET` **identical** between candidates when both use the same encrypted credentials file; keep A and B's client certificates/keys distinct. Rotating the credential secret independently prevents Node-RED decrypting its existing `flows_cred.json`. Keep the editor loopback-only and use an SSH tunnel; do not publish port 1880.

From an authorized local shell on the current active ULC host:

~~~bash
curl --connect-timeout 3 --max-time 5 -fsS http://127.0.0.1:1880/auth/login
curl -sS -o /dev/null -w 'Unauthenticated flow HTTP=%{http_code}\n' http://127.0.0.1:1880/flows
~~~

**PASS:** first endpoint reports credentials authentication; unauthenticated `/flows` is denied (not HTTP 200). Neither green node status nor editor login proves that a database transaction committed.

## 5. Correct telemetry mapping and one representative operation

The reviewed MQTT subscription is **QoS 0** and exact topic `application/+/device/+/event/up`, not gateway Protobuf `as923/gateway/.../event/...`. ChirpStack has already run the approved binary codec; Node-RED must not silently re-decode raw LoRaWAN bytes into different sensor semantics. It validates `deviceInfo` identity, event time and `payload_version=2`, then selects the proper approved device-model mapping.

The frozen EMU-01 normalized fields (12 sensor values + battery) are:

| Field/group | Unit and quality |
|---|---|
| `soil_moisture_percent`; `soil_temperature_c` | %, degrees C; validity bit 0 |
| `uv_index` | index (dimensionless, explicitly named); bit 1 |
| `barometer_pressure_pa`; `barometer_temperature_c` | Pa and degrees C; bit 2 |
| `light_veml7700_lux` | lx; bit 3 |
| `light_opt3001_lux` | lx; bit 4 |
| `environment_temperature_c`; `environment_humidity_percent`; `environment_pressure_pa`; `environment_gas_resistance_ohm` | degrees C, %, Pa, ohm; bit 5 |
| `rain_wet` | Boolean wet/dry; bit 6 |
| `battery_v` | V; 0 from USB-only node is **unavailable**, not measured 0 V/0% |

Values from sensor groups with clear validity bits remain in accepted `payload_json` provenance but normalized numeric rows have `quality='invalid'` and a null value. The 46-byte original application payload is retained in `raw_data` for independent evidence decoding. v2 also carries nullable `rxInfo[0].uplinkId`, gateway reception context and `txInfo.frequency` join material; never manufacture missing join keys from nearest timestamp or treat the Node-RED decoderVersion as proof of an independent trusted decoder.

**Observe a real authorized EMU-01 uplink and inspect SQL as `telemetry_reader`:**

~~~sql
SELECT event_key,time,device_name,device_model,decoder_version,dev_eui,
       f_cnt,temperature_c,humidity_percent,battery_v
FROM telemetry.uplinks ORDER BY time DESC LIMIT 10;
SELECT event_key,time,dev_eui,metric_name,metric_value,metric_bool,unit,quality,source_field
FROM telemetry.measurements ORDER BY time DESC,metric_name LIMIT 30;
~~~

**PASS:** exact DevEUI/test sequence and time match ChirpStack; one canonical uplink and 13 reviewed metrics with correct units/quality. New real event timestamps must be after the test start; old rows alone are not a fresh-sensor proof. A repeated MQTT application event with the **same identity** must not create new canonical rows. Use a released safe fixture and compare event_key-specific counts; never replay fabricated research data during an active counted trial.

The deployed function forms a stable `eventKey` from ChirpStack `deduplicationId` or a deterministic device/frame/time fallback. It uses parameterized SQL (`msg.query`, `msg.params`, palette 0.16.2) to insert uplink and measurements atomically; selected outbox enqueue is in the same statement. Do not concatenate decoded payload into executable SQL, invent a fresh event key on retry, or manually insert outbox rows.

## 6. Troubleshoot from the earliest failing observation

| Evidence | First investigation |
|---|---|
| no physical uplink | sensor power/firmware, AS923 and gateway reception |
| gateway/cloud event but no application event | ChirpStack join/session/codec and app MQTT publication |
| ChirpStack app event but Node-RED no receipt | host-local :18884 -> cloud :8886, certificate CN/ACL, QoS 0, topic, sole active subscriber |
| Node-RED sees event but database empty | payload validation/disabled group, PostgreSQL palette, protected writer credential, PgBouncer :6432, primary route, SQL transaction error |
| uplink exists, metrics missing | mapper validity logic and exact schema/SQL transaction, not Grafana query first |
| duplicate canonical event | stable key, unique index, replay path; don't weaken gateway MQTT QoS |
| telemetry committed, outbox pending | approved selection, exact finalized bytes + verifier-owned eligibility, separate adapter |
| both Node-RED candidates running | **fencing incident**; stop duplicate writer authority without deleting rows or broker queue |

One important distinction: real source telemetry can reach PostgreSQL while the independent evidence path is degraded. Do not paint the presentation dashboard uniformly healthy or set `verified` from Node-RED.

## 7. Safe active/passive failover and restoration

**Do not promote B until A is provably stopped/fenced** — if ULC-03 is unreachable, require an authoritative host/process fencing result, not merely failure of a ping. Confirm B's reviewed bundle matches the last accepted active revision (flow, settings, palette, credential encryption secret), *its own* MQTT certificate/key works, and B's local `:18884` and `:6432` routes pass. Then start only B, verify private editor/auth, one new real accepted event stored once, and record new owner. When ULC-03 returns, leave A **stopped**, reconcile its bundle against currently active B, and use stop-before-start again for planned failback. No overlapping subscriptions.

**Data-loss boundary:** count any sensor application messages missed during QoS 0 promotion; do not write an “exactly once, zero-loss HA” claim because PostgreSQL deduplicates what *did* arrive. Automatic failover requires a proven fencing/election mechanism; the documented normal procedure is deliberately supervised fenced promotion.

**Rollback:** preserve the last accepted bundle and protected secrets; restore to the *current authorized writer only*, check SQL one event and current database leader; keep standby fenced. Backup/restoration must include protected service PKI references, env, credentialSecret custody, persistent data and migration compatibility without leaking values.

## 8. Completion and Word document publication criteria

Prove one active writer, healthy standbys without side effects, private MQTT/DB routes on both hosts, editor auth on current owner, pinned runtime/schema, real application event with accurate thirteen-row mapping and idempotency, proper outbox/verifier/Fabric separation. Preserve release timestamp and record if physical RF unavailable. The final Word document must include the operative setup and recovery content in this document and exact approved flow/migration appendices, not send the reader to a Markdown link.

Source maintenance: [cloud Phase 12A](../server/cloud-production/12a-node-red-timescale-telemetry.md), [runtime bundle](../server/integrations/node-red/runtime/README.md), and [active/passive runbook](../server/integrations/node-red/06-active-passive-ha.md).
