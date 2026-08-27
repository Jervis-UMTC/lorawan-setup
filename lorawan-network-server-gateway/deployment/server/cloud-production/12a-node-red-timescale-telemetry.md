# 12A. Node-RED -> TimescaleDB Telemetry Application Layer

> **Status: REQUIRED PRE-TEST SETUP / DRAFT.** Execute this only after the public MQTT path, physical gateway normal path, and the Phase 13A backup/restore safety checkpoint are ready. This phase commissions the application ingestion path. It does **not** inject broker, database, host, LTE, or Fabric failures; those belong to Phase 15.

## 12A.1 Goal

Make Node-RED the controlled application transformation layer **before** telemetry reaches the database:

```text
LoRaWAN sensor
  -> Gateway
  -> MQTT
  -> ChirpStack
  -> application/+/device/+/event/up
  -> Node-RED
       validate
       normalize
       derive stable event_key
       build parameterized SQL
  -> one PostgreSQL statement / transaction
       -> telemetry.uplinks
       -> telemetry.measurements
       -> optional telemetry.fabric_outbox row
  -> COMMIT
```

Node-RED is not the database, KMS, Fabric adapter, or cryptographic trust anchor. It must never sign evidence or wait synchronously for Hyperledger Fabric.

## 12A.2 Preconditions

Before any Node-RED mutation, prove:

```text
Phase 9 ChirpStack two-node commissioning = PASS
Phase 10 public ingress normal path = commissioned
Phase 11 physical gateway normal MQTT path = commissioned
Phase 13A database backup + isolated restore rehearsal = PASS
Patroni = 1 primary + 2 streaming replicas
lorawan_telemetry exists with TimescaleDB enabled
telemetry_writer and telemetry_reader authentication paths = PASS
ulc-03 local PgBouncer :6432 and HAProxy :15432 = healthy
one real staging device/gateway can produce an accepted ChirpStack application uplink
```

If the deployment is a migration, Phase 12 must also have made the cloud ChirpStack path authoritative before Node-RED writes production-like telemetry.

## 12A.3 Commission a dedicated private Node-RED MQTT route on ulc-03

Do not use the obsolete `mqtt-ha.internal.<DOMAIN>` placeholder and do not pin Node-RED to ulc-01 or ulc-02.

The commissioned ChirpStack `:18883` frontends on ulc-01/02 terminate at the dedicated username/password `:8885` workload listeners and are **not** the Node-RED mTLS route. Keep them unchanged.

For Node-RED, commission a separate private HAProxy frontend on ulc-03:

```text
Node-RED
  -> mqtt.internal.lorawan.com:18884
  -> ulc-03 HAProxy 10.104.0.8:18884
  -> preferred Mosquitto-1 10.104.0.2:8886
  -> backup    Mosquitto-2 10.104.0.4:8886
```

Why `:18884`: Node-RED needs a stable private frontend on ulc-03, but live Phase 12A inventory proved the existing `:8884` listener is **not** client-certificate-authenticated (`require_certificate false`). Preserve `:8884` unchanged and commission a dedicated Node-RED-only Mosquitto mTLS listener on `:8886` on each broker. This keeps gateway-facing `:8884`, ChirpStack `:8885`, and Node-RED `:8886` as separate authentication/ACL domains.

### Broker identity and ACL

Create one Node-RED **ingestion** client certificate under the MQTT client CA. Its broker ACL is only:

```text
user <NODE_RED_MQTT_IDENTITY>
topic read application/+/device/+/event/up
```

Do not grant gateway-event reads or application/gateway command writes to this identity.

Do **not** change the existing `:8884` or `:8885` listeners for Node-RED. Create a dedicated `:8886` listener with `require_certificate true`, `use_identity_as_username true`, `allow_anonymous false`, and a Node-RED-only ACL. Roll it out one broker at a time: issue and verify the Node-RED client identity first, validate the candidate Mosquitto configuration off-path, activate `ulc-01:8886`, prove the existing `:8884` and `:8885` listeners remain healthy, then repeat on `ulc-02`. Do **not** deliberately stop a healthy broker to test failover here.

### ulc-03 HAProxy shape

Add only after both dedicated `:8886` backends accept the Node-RED certificate:

```haproxy
frontend node_red_mqtt_tls
    bind 10.104.0.8:18884
    mode tcp
    default_backend node_red_mqtt_brokers

backend node_red_mqtt_brokers
    mode tcp
    option tcp-check
    server mqtt-ulc01 10.104.0.2:8886 check
    server mqtt-ulc02 10.104.0.4:8886 check backup
```

Validate with `haproxy -c` before reload. After reload, prove TLS through `10.104.0.8:18884` using SNI/hostname `mqtt.internal.lorawan.com` and the Node-RED client certificate. Prove that `application/+/device/+/event/up` is readable and an intentionally forbidden command publication is denied.

No public listener is created on ulc-03.

## 12A.4 Database route from Node-RED

Node-RED uses:

```text
pgbouncer.internal.lorawan.com:6432
  -> ulc-03 10.104.0.8:6432
  -> local HAProxy :15432
  -> current Patroni primary
  -> lorawan_telemetry
```

Use `telemetry_writer` only. Keep hostname/CA verification enabled. Do not use `telemetry_admin`, `postgres`, or the ChirpStack role.

Before starting Node-RED, prove a rollback-only insert/duplicate test through this exact path using the procedures in:

- `../integrations/timescaledb/02-create-telemetry-schema.md`
- `../integrations/timescaledb/03-connect-and-verify.md`

The required Timescale objects are:

```text
telemetry.uplinks        hypertable
telemetry.measurements   hypertable
telemetry.device_registry
telemetry.latest_uplinks
telemetry.latest_measurements
```

`telemetry.fabric_outbox` is an ordinary PostgreSQL table and is created/protected before Fabric selection is enabled.

## 12A.5 Deploy Node-RED on ulc-03

Use the cloud profile in:

- `../integrations/node-red/01-deploy-node-red.md`
- `../integrations/node-red/02-configure-mqtt-and-postgresql.md`
- `../integrations/node-red/03-build-telemetry-flow.md`

Required cloud substitutions:

```text
Node-RED host:              ulc-03 / 10.104.0.8
Editor listener:            127.0.0.1:1880 only
MQTT host:                  mqtt.internal.lorawan.com
MQTT port:                  18884
MQTT TLS:                   mTLS, hostname/CA verification enabled
MQTT topic:                 application/+/device/+/event/up
Database host:              pgbouncer.internal.lorawan.com
Database port:              6432
Database:                   lorawan_telemetry
Database role:              telemetry_writer
```

Container host mappings:

```text
mqtt.internal.lorawan.com       -> 10.104.0.8
pgbouncer.internal.lorawan.com  -> 10.104.0.8
```

Pin the Node-RED image and PostgreSQL palette version. Protect the Node-RED credential secret and database/MQTT credentials outside Git. Require authenticated editor access through an SSH tunnel; never publish the editor publicly as a troubleshooting shortcut.

## 12A.6 Prove MQTT before database writes

Deploy only:

```text
mqtt in -> json -> debug
```

Send one real staging-device uplink through the normal gateway/ChirpStack path.

For the EMU-01 payload-v2 baseline, require the expected application event to contain the reviewed fields such as:

```text
payload_version = 2
test_sequence
sensor_validity_bitmap
approved decoded sensor values
```

The MQTT node being “connected” is not enough. A real current application event must arrive.

## 12A.7 Enable validation/normalization and atomic telemetry writes

Use the reviewed function/SQL in `../integrations/node-red/03-build-telemetry-flow.md`.

The order is:

```text
ChirpStack event
  -> validate DevEUI/time/payload version
  -> normalize approved decoded values/units
  -> derive stable event_key
  -> parameterized SQL
  -> INSERT uplink
  -> INSERT normalized measurements
  -> COMMIT
```

Invalid sensor-validity groups must not be mislabeled as measured stale values. Preserve the complete decoded object in `payload_json` while normalized metrics go into `telemetry.measurements`.

Do not decode the LoRaWAN binary payload a second time in Node-RED when ChirpStack has already run the approved codec.

## 12A.8 Prove retry safety before Fabric selection

Deliberately replay the **same application event** through the Node-RED flow without changing its stable identity.

Pass when database uniqueness rules leave:

```text
exactly one canonical telemetry.uplinks row
exactly one row per normalized metric identity
no second canonical application record
```

This is an application idempotency verification, not a service-failure injection.

## 12A.9 Create and protect the Fabric outbox, then enable one selected event

Before Node-RED can enqueue Fabric work, complete the outbox schema/permissions/immutability portion of:

`../fabric-attestation/02-create-outbox-and-adapter.md`

Node-RED may then add the reviewed outbox CTE to the **same PostgreSQL statement**:

```text
BEGIN-equivalent single statement
  telemetry.uplinks
  telemetry.measurements
  selected telemetry.fabric_outbox
COMMIT
```

For the first commissioning proof, select only the approved staging device/event. Do not send every sample to Fabric merely because the queue exists.

Node-RED stores only the source identity and queue request. It does **not** create `canonical_json`, calculate the production evidence digest, sign with OpenBao, or mark Fabric confirmation.

## 12A.10 Normal-path pass condition

Phase 12A passes only when all are true:

```text
ulc-03 private Node-RED MQTT HAProxy route :18884 exists and is private
Node-RED mTLS identity can read only approved application uplinks
Node-RED editor is authenticated and loopback-only
telemetry_writer connects through local PgBouncer/HAProxy with TLS verification
one real staging uplink reaches Node-RED
Node-RED validates/normalizes the event before database storage
one canonical uplink + reviewed measurements are stored
replaying the same event does not create duplicates
one selected event can atomically create a fabric_outbox row
Fabric/KMS are not called synchronously from Node-RED
```

Do **not** stop Mosquitto, Patroni, PgBouncer, HAProxy, Node-RED, ulc-03, or the gateway in this phase. Those failure cases belong to Phase 15 after all pre-test components are commissioned.

Next setup phase: [14a-grafana-cloud-deployment.md](14a-grafana-cloud-deployment.md).

### Recorded server-only Phase 12A preparation boundary - 2026-08-27

The database-side Fabric outbox prerequisite is now **COMPLETE / PASS**: `telemetry.fabric_outbox` is commissioned on the Patroni cluster, replicated 3/3, protected by the documented ACL and immutability rules, and contains zero commissioning rows. Node-RED outbox enqueue remains disabled.

The physical gateway is temporarily unavailable, so Phase 12A cannot yet claim its full normal-path preconditions or application-ingestion PASS. While that hardware dependency is deferred, only gateway-independent server preparation is allowed. The next checkpoint is a **read-only live-state preflight** from `ulc-03` that inventories: current Mosquitto `:8884` authentication/ACL directives on both brokers, MQTT PKI material needed for a future Node-RED client identity, ulc-03 HAProxy and target `:18884` availability, local PgBouncer/HAProxy database routes, and the absence/current state of Node-RED runtime files/listeners.

Do not assume the planning text describing `:8884` mTLS matches the current live broker state: earlier Phase 9 evidence observed `require_certificate false`. Do not add the Node-RED ACL, issue a client certificate, reload Mosquitto, add the `:18884` HAProxy frontend, or start Node-RED until the live preflight is reviewed. The repository also still contains `<PINNED_NODE_RED_IMAGE_OR_DIGEST>` rather than an approved image digest, so Node-RED deployment remains blocked on an explicit image pin in addition to the later real-uplink acceptance dependency.
### Recorded server-only preflight harness note - 2026-08-27

The first read-only server-side preflight stopped after proving ulc-03 HAProxy/PgBouncer listeners because the operator-side `openssl s_client` attempted to read `/etc/lorawan-pki/pgbouncer/ca.crt` without privilege. This path is intentionally protected by the commissioned PgBouncer PKI boundary (`750 root:postgres` directory, `640 root:postgres` files). Do **not** loosen ownership or mode for a diagnostic. No Phase 12A service/configuration mutation occurred in this failed harness attempt.

A follow-up `sudo openssl s_client` then reached `10.104.0.8:6432` but returned `ssl3_get_record:wrong version number`. This is a second **client harness/protocol mismatch**, not evidence that PgBouncer TLS is broken. PostgreSQL and PgBouncer negotiate TLS only after the client sends the PostgreSQL SSLRequest packet; raw TLS from byte zero is invalid for this port. The corrected OpenSSL probe must therefore use both privileged CA access and PostgreSQL STARTTLS negotiation: `sudo openssl s_client -starttls postgres ... -CAfile /etc/lorawan-pki/pgbouncer/ca.crt -verify_hostname pgbouncer.internal.lorawan.com`. A real `psql` client with `sslmode=verify-full`, logical `host=pgbouncer.internal.lorawan.com`, and physical `hostaddr=10.104.0.8` remains the application-level proof. Do not change PgBouncer, HAProxy, PKI ownership/mode, or TLS settings based on either harness failure.

### Recorded PgBouncer TLS preflight PASS - 2026-08-27

The corrected ulc-03 host probe is now **PASS**. Use `sudo openssl s_client -starttls postgres` for PgBouncer TLS checks: `sudo` is required to traverse/read the commissioned `750 root:postgres` / `640 root:postgres` PKI boundary, and `-starttls postgres` is required because PgBouncer/PostgreSQL expects an SSLRequest before the TLS handshake. The live probe to `10.104.0.8:6432` negotiated TLS 1.3 with `TLS_AES_256_GCM_SHA384`, verified the CA, and verified peer name `pgbouncer.internal.lorawan.com`. Keep the PKI permissions unchanged. The next server-only Phase 12A checkpoint is the read-only `:8884` Mosquitto authentication/ACL inventory on both brokers; do not issue the Node-RED certificate or reload Mosquitto until that live state is reviewed.

### Recorded ulc-01 :8884 live-auth partial inventory - 2026-08-27

The first Phase 12A MQTT-auth inventory reached `ulc-01` and captured the currently loaded listener-specific configuration before its value-summary helper aborted. `per_listener_settings true` is active. The dedicated ChirpStack listener remains `10.104.0.2:8885` with its password/ACL files. The separate gateway-facing listener in `tls.conf` is `:8884` with the commissioned MQTT CA/server certificate/key, TLS 1.3, `require_certificate false`, and `allow_anonymous false`. No `use_identity_as_username` directive was observed in the active files shown before the stop. Therefore the live `ulc-01:8884` listener is **not currently mTLS/client-certificate-authenticated**, and the earlier Phase 12A planning text that described `:8884` as an already-existing mTLS backend must not be treated as live-state evidence. Historical Phase 9 runtime proof remains relevant: unauthenticated MQTT CONNECT was rejected on both `:8884` brokers with CONNACK `0x05` while server TLS/hostname verification passed.

The inventory wrapper exited only because `set -euo pipefail` treated a no-match `grep` for an optional directive such as `use_identity_as_username` as fatal inside command substitution. This is a read-only harness defect. No Mosquitto, HAProxy, PKI, or Node-RED mutation occurred. Continue with a corrected listener-specific parser that tolerates absent optional directives and capture `ulc-02` before designing any Node-RED client-certificate transition.

### Recorded Node-RED MQTT listener design decision - 2026-08-27

The corrected listener-specific inventory completed on both brokers with identical live results. `per_listener_settings=true`; the existing `:8884` listener is TLS 1.3 with `require_certificate=false`, `allow_anonymous=false`, no `use_identity_as_username`, no listener-local password/ACL/plugin, and a verified `mqtt.internal.lorawan.com` server certificate. A TLS handshake without a client certificate succeeds on both brokers. Historical Phase 9 MQTT CONNECT evidence still proves anonymous MQTT is rejected with CONNACK `0x05`; therefore `:8884` is server-TLS with anonymous authorization denied, **not mTLS**. `:8886` is unused on both brokers. No runtime mutation occurred during this inventory.

Decision: preserve existing `:8884` and ChirpStack `:8885` exactly. Phase 12A will use a dedicated Node-RED authentication domain: `ulc-03 HAProxy :18884 -> ulc-01/ulc-02 Mosquitto :8886`. The `:8886` listener requires a `clientAuth` Node-RED certificate, maps certificate CN to MQTT username, denies anonymous access, and uses a Node-RED-only ACL permitting only `topic read application/+/device/+/event/up`. The candidate identity name is `node-red-ingest`. The Node-RED client private key lives only on the Node-RED side; brokers receive no client private key and the CA private key remains only in its existing root-controlled issuance boundary on ulc-03. When provider firewalls are enforced, permit `8886/tcp` only from the ulc-03/Node-RED path to ulc-01/02; never expose `8886` publicly.

Next boundary: read-only PKI issuance preflight on ulc-03. Prove the commissioned CA certificate/key match without printing key material, prove the `node-red-ingest` identity is not already issued/installed, and preserve the current CA serial state. Only after that passes may a new clientAuth identity be issued.

### Recorded Node-RED MQTT PKI preflight broker-check harness stop - 2026-08-27

The first Node-RED MQTT client-PKI preflight completed steps 1 through 8 successfully on `ulc-03`: the commissioned CA boundary remained `0700 root:root` with `ca.crt` `0644 root:root` and `ca.key` `0600 root:root`; CA certificate/key public-key hashes matched; the local MQTT CA copy matched SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb`; the CA serial-file baseline was captured; `node-red-ingest` was not already issued; and `/etc/lorawan-pki/node-red-mqtt` contained no prior client identity. The run then stopped on the first broker trust check because the SSH command over-escaped the remote `awk '{print $1}'` expression, so remote awk received a literal backslash before `$1` and exited with `backslash not last character on line`.

Treat this as a **read-only harness defect after eight PASS gates**, not as a broker CA mismatch or `:8886` conflict. No certificate, key, Mosquitto file, HAProxy file, firewall rule, or Node-RED runtime was created or changed. Do not repeat the already-proven CA/identity checks merely because this wrapper stopped. Continue only with broker hostname verification, remote MQTT-CA SHA comparison, and `:8886` listener absence on `ulc-01` and `ulc-02`. Avoid nested remote awk quoting: return raw `sha256sum` / `ss` output over SSH and perform parsing locally on `ulc-03`.

### Recorded Node-RED MQTT PKI preflight PASS - 2026-08-27

The complete read-only preflight is **PASS**. The commissioned CA root/key boundary on `ulc-03` is unchanged; the CA certificate and private key public-key hashes match; the ulc-03 MQTT CA copy matches the issuing CA; the CA serial-file baseline was recorded without mutation; CN `node-red-ingest` is unused; `/etc/lorawan-pki/node-red-mqtt` contains no prior client identity; both brokers trust the same CA; `:8886` is free on both brokers; and existing `:8884`/`:8885` listeners remained present. Proceed with one bounded client-certificate issuance only. Do not change Mosquitto, HAProxy, or Node-RED in the same step.
### Recorded Node-RED MQTT client certificate issuance - 2026-08-27

The dedicated Node-RED MQTT workload identity is now issued and validated under `/root/lorawan-pg-ca/node-red-ingest-issuance-20260827T142128Z` on `ulc-03`. Its Common Name is exactly `node-red-ingest`; it is RSA-3072, grants `clientAuth` only, does not grant `serverAuth`, chains to the commissioned internal CA, and matches its private key. The CA serial file remained byte-identical because issuance used an explicit random serial. All issuance files remain root-only and **no client private key has been transferred or installed into the Node-RED runtime yet**.

The next mutation is intentionally broker-local and canary-first. On `ulc-01` only, reserve `/etc/mosquitto/node-red.acl` for the exact `node-red-ingest` read-only policy and `/etc/mosquitto/conf.d/node-red.conf` for the dedicated `10.104.0.2:8886` mTLS listener. Before any live restart, validate a disposable loopback copy of the full three-listener policy (`28884`, `28885`, `28886`) while the production Mosquitto service remains active and live `:8886` remains absent. Only after that off-path validation passes may the `ulc-01` live canary be activated. `ulc-02`, HAProxy `:18884`, and the Node-RED runtime remain untouched during this preparation boundary.
