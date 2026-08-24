# 17. Cloud Troubleshooting

> **Status: STANDBY / LIVING DRAFT.** Keep only troubleshooting that matches deployed components. The etcd/network lessons can be retained now; future service sections must be refined from real failure evidence as those technologies are introduced.

Start at the lowest layer that does not show a healthy result. Do not restart every node or rotate credentials until the failing boundary is identified.

```text
RAK5146
  -> Concentratord
       |
       +-> delivery: MQTT Forwarder
       |     -> gateway-local Mosquitto listener/persistence
       |     -> DNS / 4G / MQTT mutual-TLS bridge
       |     -> Reserved IPv4 -> current HAProxy public-ingress owner
       |          |-> read-only gateway MQTT evidence collector
       |          +-> ChirpStack MQTT region backend
       |
       +-> evidence: integrity journal
             -> local sequence/hash/segments
             -> DNS / 4G / HTTPS-mTLS evidence upload
             -> checkpoint/segment store + verifier

ChirpStack -> PostgreSQL / Valkey -> application integrations
Node-RED -> lorawan_telemetry [TimescaleDB hypertables] -> trusted decoder comparison -> v2 evidence gate
lorawan_telemetry.fabric_outbox -> Fabric adapter-1/2 -> OpenBao-1/2/3 -> external Fabric Gateway
```

Gateway commands in Sections 16.1–16.3 run over SSH on the Raspberry Pi. Cloud commands run on the host that owns the named service. Use one reserved gateway and device event to compare timestamps across layers.

## 17.1 Radio or Gateway ID failure

**Failing layer:** RAK5146 hardware access or Concentratord configuration.

Run on the gateway:

```sh
monit status
uci show chirpstack-concentratord
logread -e chirpstack-concentratord
```

Healthy output shows one running Concentratord instance, the RAK5146/SX1302-or-SX1303 profile, the confirmed legal channel plan, and a stable 16-hexadecimal Gateway ID. SPI, reset, calibration, repeated restart, missing-ID, or changing-ID messages point to profile, HAT seating, power, frequency variant, or hardware trouble.

Correct only the first observed mismatch. Power down before reseating hardware, and stop RF transmission when the region is wrong. Verify by rebooting and confirming the same Gateway ID and channel plan without error loops.

## 17.2 MQTT Forwarder cannot publish locally

**Failing layer:** MQTT Forwarder to the gateway-local Mosquitto listener.

Run on the gateway:

```sh
uci show chirpstack-mqtt-forwarder
logread -e chirpstack-mqtt-forwarder
logread -e mosquitto
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

Healthy configuration uses `tcp://127.0.0.1:1883`, QoS 1, Protobuf, backend `concentratord`, and a listener bound only to loopback. Connection refusal means Mosquitto is stopped or invalid; a WAN address means the buffer is bypassed; a non-loopback listener means the broker is exposed.

Validate the broker configuration, correct the differing address, QoS, backend, or listener, and restart only the affected process. Verify with one real gateway event at the local broker.

## 17.3 The local queue grows and does not drain

**Failing layer:** gateway backhaul, DNS, time, TLS, broker ACL, remote MQTT availability, or queue capacity.

Run on the gateway:

```sh
logread -e mosquitto
nslookup mqtt.<DOMAIN>
ip route
date -u
df -h /etc/mosquitto/data
ls -l /etc/mosquitto/data/mosquitto.db
```

| Symptom | Meaning | Smallest safe action |
|---|---|---|
| DNS failure | Resolver, APN, or 4G route problem | Restore DNS or route and keep the queue running |
| Hostname or CA error | Wrong trust file or certificate SAN | Install the intended CA or endpoint; never disable verification |
| Client rejected | Certificate, expiry, EKU, CN, or key mismatch | Compare the certificate identity and private-key match |
| ACL denial | Gateway identity or regional topic mismatch | Compare Gateway EUI, certificate CN, and exact topics |
| Queue grows with a connected bridge | Remote drain rate is below incoming rate | Check broker health and measured publish rate |
| Queue reaches its finite limit | Outage exceeded the buffer design | Restore the remote path, protect free space, and identify the affected interval |
| Database missing after reboot | Volatile path or persistence failure | Stop claiming durable buffering and repair the storage path |

Healthy recovery reconnects both bridge clients, preserves the queue database, drains old events, and continues accepting new uplinks. Verify at the remote broker and then at ChirpStack; do not delete the queue to make disk usage fall.

## 17.3A Journal does not advance while MQTT is healthy

**Failing layer:** independent Concentratord evidence path.

Check the reviewed journal service, its source-interface configuration, current sequence/open segment, persistent evidence path, permissions, and free space using the implementation's approved diagnostics.

Interpretation:

```text
Concentratord + MQTT healthy, journal process down
  -> journal service/implementation fault

journal process healthy, sequence not advancing for known uplink
  -> Concentratord event subscription/filter/source-contract fault

sequence advances, writes fail
  -> journal storage/permission/capacity fault
```

Do not point the journal at Mosquitto as a shortcut. Preserve the first affected time/sequence and classify unrecoverable source evidence as `evidence_gap`.

## 17.3B MQTT is healthy but cloud checkpoint is stale

**Failing layer:** evidence uploader, DNS/4G route to `evidence.<DOMAIN>`, mTLS identity, ingest API, or evidence-store write path.

Check independently:

```text
DNS/route/time to evidence endpoint
server certificate SAN/CA
per-gateway client identity/expiry
last local sequence/closed segment
unuploaded segment count/bytes
latest accepted server checkpoint age
API rejection/conflict logs
```

Healthy MQTT does not clear this incident. Restore upload and prove the next accepted segment/checkpoint extends the previous server anchor.

## 17.3C Journal hash, checkpoint, or journal-to-MQTT conflict

**Failing layer:** evidence integrity/correlation boundary.

Freeze v2 evidence promotion for the affected gateway. Preserve the journal object, accepted checkpoint/receipt, captured remote gateway MQTT object, PHYPayload/source digests, software versions, and relevant logs.

Do not renumber records, recalculate a replacement local chain, delete the newer checkpoint, or ask Node-RED which payload to trust.

Use:

```text
missing required evidence with no contradictory bytes -> evidence_gap
proven hash/payload/rollback conflict                -> integrity_failure
```

## 17.4 The remote broker receives events but ChirpStack does not

**Failing layer:** remote MQTT authorization or the ChirpStack regional MQTT backend.

On the MQTT host, confirm the gateway event topic and certificate identity. On each ChirpStack application node, inspect the service logs and active region configuration. The regional topic prefix, Protobuf backend, broker endpoint, client certificate, and trust root must agree.

Healthy behavior updates the registered Gateway EUI's last-seen time after a fresh event. If the broker has the message and ChirpStack does not, correct only the differing regional backend, topic prefix, ACL, or credential and restart the affected ChirpStack node. This architecture does not require ChirpStack Gateway Bridge.

## 17.5 Duplicate application or telemetry rows

**Failing layer:** application idempotency after valid at-least-once MQTT delivery.

Verify the Node-RED stable event key, ChirpStack `deduplicationId` use, Timescale hypertable status, and the `lorawan_telemetry` uniqueness indexes. Replay one sanitized event. A healthy result leaves one uplink and one row per metric. More rows mean the event key or database constraint is wrong. Fix that layer; do not lower gateway QoS.

If inserts fail only after a Patroni promotion, first verify the promoted node has the compatible TimescaleDB library/preload configuration and that `SELECT extversion FROM pg_extension WHERE extname='timescaledb';` succeeds. A PostgreSQL replica is not a valid telemetry primary if its TimescaleDB runtime is missing or mismatched.

## 17.5A Telemetry row exists but v2 verification fails

**Failing layer:** application evidence comparison, not necessarily Node-RED ingestion availability.

Inspect the matching `gateway_evidence.event_verification` result and reason. If journal/MQTT/ChirpStack lineage is valid but the trusted decoder disagrees with the row stored in `lorawan_telemetry`, preserve:

```text
accepted raw ChirpStack application-data digest
trusted decoder ID/version or code hash
trusted normalized digest/value
Node-RED decoder version
stored telemetry row identity/value
verification ID/reason
```

Do not change the database value merely to make the evidence green. Determine whether the trusted decoder, Node-RED mapping, source bytes, or correlation policy is wrong, then correct the implementation and process a new governed result according to the incident procedure.

## 17.6 A stale downlink appears after reconnect

**Failing layer:** downlink session cleanup or an automation publisher.

Confirm the gateway's `cloud-downlink` bridge uses `cleansession true` and command topic `in 0`. Check the remote broker for retained command messages and duplicate client sessions. Healthy behavior does not replay a Class A command after its receive window.

Disable automatic downlinks until the retaining session or publisher is removed, then verify with one harmless, observable command.

## 17.7 Reserved-IP / MQTT public failover does not preserve service

**Failing layer:** Reserved-IP ownership, failover agent, etcd lock, DigitalOcean API, HAProxy routing, backend health, timeout behavior, or broker session design.

First check the current public owner from an authenticated admin context:

```bash
doctl compute reserved-ip get <RESERVED_IP> --format IP,Region,DropletID,DropletName --no-header
```

Then on `ha-01/02` check:

```bash
systemctl status lorawan-public-ingress.timer --no-pager
systemctl status lorawan-public-ingress.service --no-pager -l
journalctl -u lorawan-public-ingress.service --since=-15min --no-pager
sudo /usr/local/sbin/lorawan-ingress-health local
sudo /usr/local/sbin/lorawan-ingress-health public
```

If etcd quorum is unavailable, automatic Reserved-IP movement is intentionally blocked. If the DigitalOcean API/token cannot reassign the address, internal HA can remain healthy while the public endpoint stays on the failed owner.

For MQTT itself, HAProxy owns public anchor `:8883`, Mosquitto-1/2 listen on private TLS backend `:8884`, and HAProxy keeps MQTT TLS pass-through so the broker receives the gateway client certificate. A healthy recovery reconnects the gateway and resumes queue drain without changing DNS, certificate, or topics.

Check the intended listeners first:

```bash
# ha-01 / ha-02 HAProxy
sudo ss -lntp | grep -E ':(8883|18883)\b'

# Mosquitto backend host
sudo ss -lntp | grep ':8884'
```

If HAProxy and Mosquitto are both trying to bind the same VPC `:8883`, the old port-collision design is still active. Public HAProxy must bind the **anchor IP** on `:8883`; Mosquitto stays on private backend `:8884`.

Reserved-IP/HAProxy failover does not synchronize independent Mosquitto sessions, retained messages, or queues. Broker service failover still depends on the gateway's bounded local QoS 1 queue and reconnection behavior.

## 17.8 UDP Forwarder traffic appears

**Failing layer:** an unsupported gateway backend is enabled.

Run on the gateway:

```sh
uci show chirpstack-udp-forwarder
monit status
```

Healthy output has no UDP server and the service disabled. Remove the unintended entries, disable only the UDP Forwarder, and verify the MQTT path with a real uplink.

## 17.9 ChirpStack reports database or state errors

**Failing layer:** ChirpStack, PgBouncer, HAProxy, PostgreSQL/Patroni, or Valkey/Sentinel.

Check in this order.

### Step 1 - PostgreSQL/Patroni role

```bash
patronictl -c <PATRONI_CONFIG> list <PG_SCOPE> --extended
```

Expected: exactly one primary and two replicas in the normal state.

Check each Patroni role endpoint from the affected HAProxy host:

```bash
for h in <HA01_PRIVATE_IP> <HA02_PRIVATE_IP> <HA03_PRIVATE_IP>; do
  printf '%s ' "$h"
  curl -sS -o /dev/null -w '%{http_code}\n' "http://$h:8008/primary"
done
```

Exactly one should be the primary according to the pinned Patroni endpoint semantics. Adapt the command for REST TLS/auth when enabled.

### Step 2 - HAProxy DB route

```bash
psql 'host=postgres-ha.internal hostaddr=<THIS_HOST_PRIVATE_IP> port=15432 dbname=postgres user=<MONITOR_ROLE> sslmode=verify-full' \
  -c 'SELECT inet_server_addr(), pg_is_in_recovery();'
```

Expected: `pg_is_in_recovery = false`.

### Step 3 - PgBouncer

```bash
psql '<PGBOUNCER_ADMIN_DSN>' -c 'SHOW POOLS;'
psql '<PGBOUNCER_ADMIN_DSN>' -c 'SHOW SERVERS;'
```

Look for sustained `cl_waiting`, repeated login failures, stale server connections after a promotion, or a pool using an unexpected database/host.

### Step 4 - application DB route

From the affected application host, query through its normal `:6432` endpoint. Do not bypass PgBouncer to make the test pass.

An authentication error calls for checking the exact role/verifier/secret reference. Connection exhaustion calls for checking pool and PostgreSQL limits. A read-only/no-primary error calls for Patroni and HAProxy diagnosis.

Restarting all application/database nodes together destroys evidence and can remove quorum. Correct the first failing dependency, then verify one harmless API/SQL operation and one fresh uplink.

## 17.9A etcd quorum is unhealthy

**Failing layer:** Patroni coordination/DCS.

From an approved administrative shell, first use the transport that is actually deployed. The current cluster uses HTTP on `10.104.0.0/20`:

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  endpoint health

ETCDCTL_API=3 etcdctl \
  --endpoints=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379 \
  member list --write-out=table
```

If etcd TLS has been deployed since this baseline, use the matching tested CA/client credentials instead. A protocol mismatch (`https://` against the current HTTP listener, or the reverse) can look like a service failure.

Interpretation:

```text
3/3 reachable -> normal
2/3 reachable -> degraded but quorum can progress; restore the missing member before another failure
1/3 reachable -> no safe majority; stop failover testing and recover quorum
```

Do not remove/re-add multiple members at once. Preserve the member IDs and the pre-test snapshot before destructive membership repair.

## 17.9B Fabric outbox grows while telemetry is healthy

**Failing layer:** Fabric adapter worker, OpenBao KMS, external Fabric Gateway, or commit reconciliation.

Check in this order:

```text
fabric_outbox oldest pending age and status counts
adapter-1 / adapter-2 process and database connectivity
live/expired job leases
openbao-kms.internal.<DOMAIN>:18200 TLS reachability
OpenBao 3-member state, seal state, and quorum
Transit sign/verify errors
external Fabric DNS/TLS/MSP/channel/chaincode reachability
submitted_unknown reconciliation state
```

Do not make Node-RED call Fabric synchronously to reduce the queue. Restore the first failing asynchronous dependency and let the durable outbox drain under the normal retry/reconciliation rules.

## 17.9C OpenBao is sealed, degraded, or has no quorum

**Failing layer:** evidence KMS.

One unavailable OpenBao member should leave `2/3` quorum. Two unavailable voters or sealed members can stop new Raft writes/signing. Preserve the PostgreSQL outbox/telemetry, restore the missing/unsealed cluster members using the documented recovery material, and verify the stable KMS endpoint before restarting adapter retries.

Use the pinned CLI through the stable service name and, when needed, directly against members:

```bash
bao status
bao operator raft list-peers
```

Also test the HAProxy health target directly with HTTPS and the internal CA:

```bash
curl --fail --silent --show-error \
  --cacert /etc/lorawan-pki/openbao/ca.crt \
  'https://openbao-kms.internal.<DOMAIN>:18200/v1/sys/health?standbyok=true'
```

If HAProxy reports a sealed/uninitialized node healthy, its KMS health check has regressed to a TCP-only check or is using the wrong health semantics. Repair that before adapter retries.

Never export/create a replacement local signing key in the Fabric adapter to bypass OpenBao. If the historical Transit key cannot be recovered, stop attestation recovery and preserve the affected sealed/unsealed evidence for governance review.

## 17.9D Valkey/Sentinel does not fail over or HAProxy routes a replica

**Failing layer:** Valkey replication, Sentinel quorum/authentication, or HAProxy primary-role health check.

Check each Valkey node with TLS and the protected application/admin credential:

```bash
valkey-cli --tls --cacert <VALKEY_CA> -h <VALKEY_IP> -p 6379 \
  -a '<LOAD_PROTECTED_SECRET>' ROLE
```

Check every Sentinel:

```bash
valkey-cli --tls --cacert <VALKEY_CA> -h <SENTINEL_IP> -p 26379 \
  -a '<LOAD_SENTINEL_SECRET>' SENTINEL CKQUORUM lorawan-valkey

valkey-cli --tls --cacert <VALKEY_CA> -h <SENTINEL_IP> -p 26379 \
  -a '<LOAD_SENTINEL_SECRET>' SENTINEL GET-MASTER-ADDR-BY-NAME lorawan-valkey
```

Then query the app endpoint:

```bash
valkey-cli --tls --cacert <VALKEY_CA> \
  -h valkey-ha.internal.<DOMAIN> -p 16379 \
  -a '<LOAD_PROTECTED_SECRET>' ROLE
```

Expected: the HAProxy endpoint reports primary/master. If direct Sentinel state is correct but HAProxy points at a replica, inspect the HAProxy `AUTH` + `INFO replication` health check; a simple PING is insufficient because replicas also answer PING.

Restore 3 data nodes + 3 Sentinels and a passing `CKQUORUM` before another failure test.

## 17.10 An upgrade causes a regression

Preserve the Gateway OS image, local broker data/configuration, journal implementation/configuration and continuity metadata, certificates, latest accepted checkpoint/evidence objects, cloud image digests, database versions, active schema state, and logs from the failed attempt.

Restore the previously tested component without deleting data volumes or rewinding the authoritative checkpoint store. Verify the rollback in layers: gateway radio, local publish, journal source/sequence/hash, WAN queue, evidence upload/checkpoint continuity, mutual TLS, remote broker, gateway-MQTT evidence capture, ChirpStack gateway activity, OTAA/uplink, trusted decoder comparison, database state, and integrations. A process that merely starts is not a successful rollback.
