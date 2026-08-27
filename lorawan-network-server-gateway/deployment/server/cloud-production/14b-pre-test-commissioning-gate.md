# 14B. Full Pre-Test Commissioning Gate

> **Status: REQUIRED FINAL GO/NO-GO BEFORE PHASE 15.** This is the boundary between **setup** and **testing**. Do not inject a host, process, broker, database, KMS, Fabric, or LTE failure until every required item below is commissioned and the final result is `PRE_TEST_COMMISSIONING_GATE=PASS`.

> **Scope:** keep the full commissioned HA architecture intact. Before ordinary functional/counting work, it is sufficient to re-prove normal health of the existing HA components and the real end-to-end application path; do not repeatedly execute destructive failovers, restore rehearsals, or other rigorous recovery drills when there is no failure signal. This full gate remains the hard boundary before the dedicated cloud-production Phase 15 failure-injection program. The dissertation GO/NO-GO checks under `test/` may run against the existing HA deployment without removing Patroni/Spilo, etcd, HAProxy, PgBouncer, Valkey/Sentinel, redundant MQTT, ChirpStack HA, Grafana, or other commissioned services.

## 14B.1 Rule

The cloud POC uses this lifecycle:

```text
SET UP EVERYTHING
  -> verify normal paths
  -> take final backups
  -> prove evidence capture works
  -> freeze the tested baseline
  -> ONLY THEN begin Phase 15 fault injection
```

A missing implementation is a setup blocker, not something to discover halfway through counted acceptance trials.

## 14B.2 Required execution order before this gate

The practical order after Phase 9 is:

```text
Phase 10   public HTTPS/MQTT ingress + Reserved IPv4 + failover agent armed
Phase 11   physical gateway/Gateway OS + LTE + persistent delivery buffer
Phase 13A  backup + isolated-restore safety checkpoint
Phase 12   gateway/device migration or fresh cloud cutover
Phase 12A  Node-RED -> TimescaleDB telemetry application pipeline
Phase 14A  Grafana read-only telemetry visualization
Phase 20   OpenBao Transit + Fabric outbox/adapters + one normal ledger commit
Phase 13B  final full-stack backup/configuration snapshot
Phase 14   observability/evidence harness healthy-baseline dry run
Phase 14B  this gate
Phase 15   first fault injection
```

The numbering is retained for existing filenames; **dependency order wins over numeric order**.

## 14B.3 Public ingress ready

Require:

```text
real chirpstack public FQDN
real mqtt public FQDN
one assigned Reserved IPv4
ulc-01/ulc-02 Droplet IDs + region recorded
ulc-01/ulc-02 anchor IPv4 recorded
DigitalOcean provider action method authorized
provider-owned Cloud Firewall evidence supplied
HAProxy anchor :443 and :8883 listeners healthy
public HTTPS certificate valid
Mosquitto certificate valid for BOTH mqtt public FQDN and mqtt.internal.lorawan.com
manual Reserved-IP reassignment verified in both directions without DNS changes
failover service/timer installed and armed on ulc-01/02
no automatic failback
```

Do not prove automatic host-loss takeover here. Phase 15 owns that failure test.

## 14B.4 Physical gateway/backhaul ready

Require:

```text
Gateway OS version/image recorded
RAK5146 variant + AS923 plan recorded
Gateway EUI stable
MQTT Forwarder -> 127.0.0.1:1883
local Mosquitto queue persistent, finite, and loopback-only
unique gateway mTLS identity accepted by cloud broker
LTE modem mode/APN/DNS/time/routing commissioned
mqtt public FQDN reachable over intended LTE path
real OTAA succeeds
real uplink reaches ChirpStack
one approved safe Class A downlink succeeds when the device contract defines one
```

For an all-features run, the reviewed gateway integrity journal/evidence implementation must also exist, be pinned, and have a normal healthy chain/checkpoint path. If the repository still lacks the reviewed executable/server roles required by the selected integrity contract, mark this gate **BLOCKED** rather than beginning counted Phase 15 testing.

Do not perform the LTE outage/reboot/queue-drain failure test here.

## 14B.5 Database + Node-RED application path ready

Require:

```text
Patroni 1 primary + 2 streaming replicas
TimescaleDB extension present on the HA cluster
telemetry.uplinks hypertable
telemetry.measurements hypertable
telemetry.fabric_outbox ordinary PostgreSQL table
telemetry_writer and telemetry_reader least-privilege paths pass
Node-RED loopback-only/authenticated
Node-RED private MQTT route on ulc-03 commissioned
one real application event stored after validation/normalization
replay of same event remains duplicate-safe
one selected event atomically creates telemetry + outbox work
```

Node-RED must not call Fabric synchronously.

## 14B.6 Grafana ready

Require:

```text
Grafana pinned image recorded
Grafana loopback-only on ulc-03
telemetry_reader only
TLS-verified PgBouncer data source = PASS
real stored sensor values visible
latest-reading age visible
small history panel visible
no write-capable database role configured
```

Grafana being unavailable must not be required for LoRaWAN control-plane operation, but its normal deployment must exist before the testing baseline is frozen.

## 14B.7 OpenBao + Fabric ready

For the full-feature target require:

```text
OpenBao 3-member Raft cluster healthy/unsealed
one active + two standby/raft peers as expected
stable HAProxy KMS endpoint healthy
non-exportable lorawan-evidence P-256 Transit key exists
fixed RFC 8785 canonicalization vector passes
SHA-256 digest generation from exact canonical bytes passes
OpenBao sign + verify passes
external Fabric handoff is complete
reviewed Fabric adapter source/image exists and immutable digest is recorded
adapter-1 running on ulc-01 with unique worker_id
adapter-2 running on ulc-02 with unique worker_id
one selected normal event is sealed and reaches confirmed Fabric commit
Fabric tx ID/commit status returns to the outbox
read-only digest reconstruction/verification mode required by integrity testing exists
```

The normal evidence path is:

```text
TimescaleDB source event
  -> fixed evidence projection
  -> RFC 8785 canonical JSON
  -> SHA-256 digest
  -> OpenBao Transit ECDSA signature
  -> Hyperledger Fabric attestation
```

If the reviewed adapter implementation is absent, the **full-feature pre-test gate is BLOCKED**. Do not start counted Phase 15 and later describe the missing adapter as merely a test limitation.

Do not stop an OpenBao member, adapter, or external Fabric endpoint here.

## 14B.8 Final recovery boundary ready

After every setup phase above is complete, revisit Phase 13 and create the **Phase 13B final snapshot**. Require:

```text
chirpstack dump off-Droplet + checksum
lorawan_telemetry dump off-Droplet + checksum
isolated restore rehearsal succeeds
etcd snapshot/member record off-Droplet
OpenBao recovery material protected off-host
OpenBao Raft snapshot off-host
Node-RED flow/config export
Grafana dashboard/data-source export without secrets
HAProxy/PgBouncer/Mosquitto/Valkey/ChirpStack/OpenBao non-secret configs recorded
public-ingress scripts/unit hashes + Reserved-IP worksheet recorded
Fabric handoff + adapter image/config references recorded
```

The final backup must reflect the fully commissioned pre-test system, not an earlier partial build.

## 14B.9 Evidence harness ready

Run Phase 14 once against the healthy system without injecting a fault. Prove the evidence directory can capture:

```text
host resource state
etcd quorum
Patroni roles/lag
PgBouncer pools
TimescaleDB/hypertables/latest telemetry
Valkey/Sentinel role state
MQTT broker/HAProxy state
ChirpStack health + gateway last-seen
Reserved-IP current owner + failover timer state
Node-RED state
Grafana state
OpenBao Raft/seal/Transit state
Fabric outbox + adapter state + last committed tx
```

This healthy-baseline dry run prevents discovering missing commands/permissions after a fault has already been injected.

## 14B.10 Freeze the baseline

Record immutable/non-secret references used for Phase 15:

```text
container image digests
major configuration hashes
Gateway OS image/version
region/frequency plan
public/internal FQDNs
Reserved IPv4 + current owner
Droplet IDs + anchor/VPC addresses
schema version
Node-RED flow export/hash
Grafana dashboard export/hash
OpenBao version + Transit key version metadata
Fabric adapter image digest + worker IDs
backup set identifier
```

Do not upgrade, rotate certificates, change schema, change dashboards/flows, or tune pool limits between this freeze and the corresponding Phase 15 run unless a failed pre-test gate requires a documented correction and a new baseline.

## 14B.11 Final go/no-go

`PASS` requires every required line above to be evidenced.

```text
PRE_TEST_COMMISSIONING_GATE=PASS
  -> Phase 15 may begin

PRE_TEST_COMMISSIONING_GATE=BLOCKED
  -> finish the missing setup first
  -> no counted fault injection

PRE_TEST_COMMISSIONING_GATE=FAIL
  -> repair the failed normal path
  -> repeat the healthy baseline
  -> no counted fault injection
```

Next and first failure-injection phase: [15-failover-chaos-and-acceptance-testing.md](15-failover-chaos-and-acceptance-testing.md).
