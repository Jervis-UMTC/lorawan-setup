# Execution 8. Resilience and Recovery
> **Reference procedure only.** Executable operator commands are published only in `chapters/lorawan_research_test_manual_final.md` after live qualification. The fenced snippets below are preserved as implementation/reference text and must not be copied as current commands.

> **Methodology reconciliation warning:** the new `chapters/Zacarias_Chapter3.pdf` requires two distinct resilience experiments: **R1 external-Internet interruption/recovery** and **R2 Fabric-unavailability/database–blockchain reconciliation**. This existing file was written around a Fabric-only reachability interruption and therefore **must not be used as the counted R1 Internet-interruption procedure**. Use [../ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md](../ZACARIAS-CHAPTER3-TEST-METRICS-SOURCE-OF-TRUTH.md) as the authority until this manual is split/reconciled.

The procedure below describes an **external-Fabric reachability interruption** and may inform the implementation of R2, but it does not by itself satisfy the new Chapter 3 resilience test set.

## What this test proves

This experiment isolates **external Fabric availability** while the production LoRaWAN/cloud path remains healthy. Gateway-01 must continue using its normal LTE/public-ingress route, the three cloud nodes and private VPC must remain available, and only the Fabric-adapter workers' reachability to the commissioned external Fabric endpoint is interrupted.

The run is INVALID if the interruption also breaks Gateway-01 LTE/public MQTT ingress, the Reserved-IP path, ChirpStack, Node-RED/TimescaleDB, the private VPC, or unrelated cloud services, because that creates a different failure condition.

## Required design

Each run:

```text
30 minutes normal
60 minutes external-Fabric interruption
30 minutes recovery
Total = 2 hours
```

Repeat 3 times.

With EMU-01 frozen on the **counted-test-15s** artifact (15-second normal uplinks, 46-byte physical payload-v2, monotonic source sequence):

```text
about 120 readings before interruption
about 240 during interruption
about 120 after Fabric reachability restoration
about 480 per run
about 1440 across three runs
```

## Current architecture behavior

Gateway-01 and the commissioned three-node DigitalOcean POC remain on their normal production path. Gateway-01 keeps its health-gated SIM7600 LTE primary route and public MQTT/TLS ingress; `ulc-01`, `ulc-02`, and `ulc-03` keep their normal private-VPC and HA services. The Hyperledger Fabric network is the isolated external dependency.

Therefore the expected behavior is:

```text
Gateway-01 + LTE/public MQTT ingress -> stays available
Reserved-IP/cloud MQTT path -> stays available
three-node cloud/VPC/HA services -> stay available
ChirpStack -> stays available
Node-RED -> stays available
TimescaleDB -> keeps storing
external Fabric endpoint -> deliberately unreachable from active adapter worker(s)
Fabric outbox -> queues pending work
Fabric reachability returns -> adapter reconciles/drains without duplicate ledger state
```

Do not claim Fabric transactions committed during the disconnected period if the external Fabric endpoint was unreachable.

## 1. Choose and rehearse one interruption method

The preferred method is a narrowly scoped, pre-rehearsed rule applied only to the active Fabric-adapter worker path that blocks the commissioned external Fabric endpoint while preserving Gateway-01 ingress, cloud/VPC connectivity, database/KMS access, and operator management.

Do not disable a cloud NIC, default route, Reserved-IP ingress, Gateway-01 LTE path, or broad Internet egress. Those actions would test a different failure mode.

Before the experiment prove:

```text
Gateway-01 production MQTT/TLS path through LTE/Reserved-IP is healthy
operator management and cloud private-VPC paths are healthy
external Fabric endpoint is reachable
```

During the interruption prove:

```text
Gateway-01 production MQTT/TLS path through LTE/Reserved-IP remains healthy
the commissioned external Fabric endpoint is not reachable from the selected active adapter worker, while unrelated Internet/cloud paths remain healthy
```

Document the exact method used so all three runs use the same interruption.

### Legacy local-VM route method - DO NOT USE on the commissioned cloud POC

The route-removal procedure below belongs only to the obsolete local single-VM laboratory topology and is retained for historical reproducibility. It is **not an authorized interruption method for the commissioned three-node cloud POC**. Before the actual resilience experiment, replace this legacy subsection with the exact external-Fabric endpoint isolation rule proven against the live Fabric handoff.

Before counted runs, record:

```text
mkdir -p "$HOME/chapter4-results/resilience"
ip route show | tee "$HOME/chapter4-results/resilience/route-before-test.txt"
ip route show default
```

Write down the exact default route, for example:

```text
default via <ROUTER_IP> dev <INTERFACE>
```

Perform one **uncounted rehearsal**:

```text
sudo ip route del default
ip route
```

Then prove all three conditions:

```text
local gateway/server subnet remains reachable
server MQTT 8883 remains reachable from the gateway over LAN
external Internet/Fabric endpoint is unreachable
```

Restore the exact recorded route, for example:

```text
sudo ip route add default via <ROUTER_IP> dev <INTERFACE>
```

Verify external reachability returns. If this method breaks the operator's only management path or local gateway-to-server communication, do not use it; use the lab router/hypervisor egress-block method instead. Freeze whichever method passes rehearsal and use it unchanged for all three runs.

## 2. Preflight

Complete [Execution 01 - Common Run Preparation](01-common-run-preparation.md).

Also confirm no pre-existing Fabric backlog:

```text
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT status,count(*) FROM telemetry.fabric_outbox GROUP BY status ORDER BY status;"
```

Record any pre-existing non-confirmed jobs. Do not attribute them to the resilience run.

## 3. Start the 30-minute normal period

Before the two-hour clock starts, create phase marker files so the three windows cannot be confused later:

```text
phase-1-normal-start.txt
phase-1-normal-end.txt
phase-2-outage-start.txt
phase-2-outage-end.txt
phase-3-recovery-start.txt
phase-3-recovery-end.txt
```

Use the same uninterrupted EMU-01 source capture and resource capture across all three phases.

At the start of Phase 1:

```text
date -u +%Y-%m-%dT%H:%M:%SZ | tee "$RUN_DIR/phase-1-normal-start.txt"
```

1. create a unique run directory;
2. start resource capture;
3. record start UTC, first EMU-01 `test_sequence`, and first LoRaWAN frame counter;
4. let EMU-01 run the exact frozen counted-test-15s artifact and 46-byte physical-sensor payload-v2 for 30 minutes;
5. confirm local services and Fabric operate normally.

At the end of this period record:

```text
expected readings ~120
stored readings
confirmed Fabric jobs
last frame counter
```

## 4. Start the 60-minute Internet interruption

At the 30-minute boundary, mark both sides of the transition **before** applying the frozen WAN-block method:

```text
date -u +%Y-%m-%dT%H:%M:%SZ | tee "$RUN_DIR/phase-1-normal-end.txt"
date -u +%Y-%m-%dT%H:%M:%SZ | tee "$RUN_DIR/phase-2-outage-start.txt"
```

Do not stop source/resource capture between phases.

Apply the pre-tested Internet block. Do not change the LoRaWAN radio, local LAN, Docker stack, EMU-01 firmware/payload, or the archived counted-test-15s cadence profile.

Immediately verify:

```text
local server reachable = yes
MQTT 8883 from gateway = yes
external Fabric endpoint reachable = no
```

Let EMU-01 continue for 60 minutes. Retain its complete source log so the expected sequence during the interruption is independently known.

During the interruption, periodically verify:

```text
docker compose ps mosquitto valkey chirpstack node-red telemetry-db openbao fabric-adapter

docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT status,count(*) FROM telemetry.fabric_outbox GROUP BY status ORDER BY status;"
```

Expected:

```text
new telemetry rows continue
Fabric jobs become pending/failed/submitted_unknown according to the failure point
adapter uses bounded retry/backoff
```

Record the outbox state at the end of 60 minutes.

## 5. Restore Internet and observe for 30 minutes

At exactly 60 minutes of outage, mark outage end, restore only the frozen WAN route/rule, then mark recovery start:

```text
date -u +%Y-%m-%dT%H:%M:%SZ | tee "$RUN_DIR/phase-2-outage-end.txt"
# restore the exact frozen route/rule here
date -u +%Y-%m-%dT%H:%M:%SZ | tee "$RUN_DIR/phase-3-recovery-start.txt"
```

At the end of the 30-minute recovery observation:

```text
date -u +%Y-%m-%dT%H:%M:%SZ | tee "$RUN_DIR/phase-3-recovery-end.txt"
```

Remove only the rule used for the test.

Record reconnection UTC.

Verify external Fabric reachability returns, then monitor:

```text
docker compose logs -f --tail=100 fabric-adapter
```

Periodically query:

```text
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT status,count(*) FROM telemetry.fabric_outbox GROUP BY status ORDER BY status;"
```

Pass recovery when retry-eligible outage work drains/reconciles without creating conflicting duplicate ledger state.

Measure recovery time from `recovery-start UTC` until the predefined recovery condition is first satisfied. If work has not recovered by the end of the 30-minute observation, report `recovery_time > 1800 s` / not recovered within observation rather than assigning a successful value.

Continue normal EMU-01 operation for the full 30-minute recovery period and keep the same source-log capture active.

## 6. Export the run records

Export telemetry for the complete two-hour window:

```text
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At -F ',' \
  -c "SELECT event_key,time,received_at,dev_eui,gateway_id,f_cnt,payload_json->>'test_sequence' AS test_sequence FROM telemetry.uplinks WHERE dev_eui='<TEST_DEV_EUI>' AND time >= '<RUN_START_UTC>' AND time < '<RUN_END_UTC>' ORDER BY time,f_cnt;" \
  > "$RUN_DIR/uplinks.csv"
```

Export outbox/Fabric state:

```text
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At -F ',' \
  -c "SELECT event_key,source_event_key,status,digest_sha256,fabric_tx_id,created_at,submitted_at,committed_at FROM telemetry.fabric_outbox WHERE created_at >= '<RUN_START_UTC>' AND created_at < '<RUN_END_UTC>' ORDER BY created_at;" \
  > "$RUN_DIR/fabric.csv"
```

Check duplicate application records:

```text
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,time,count(*) FROM telemetry.uplinks WHERE dev_eui='<TEST_DEV_EUI>' AND time >= '<RUN_START_UTC>' AND time < '<RUN_END_UTC>' GROUP BY event_key,time HAVING count(*) > 1;"
```

## 7. Record the required measures

For each period and run record:

```text
expected readings / expected EMU-01 test_sequence range
stored readings
missing readings / missing test_sequence values
duplicate readings
local service availability
Fabric commits completed before interruption
Fabric work queued during interruption
Fabric work confirmed after recovery
latency by period
recovery time
chronological/frame-counter accuracy
```

`Fabric records created during interruption` must reflect the real external-network behavior. If the ledger was unreachable, report queued local attestations separately and confirmed ledger records after reconnection.

## 8. Validate one run before repeating

For each phase compare the EMU-01 source sequence against stored rows. Explicitly list missing and duplicate `test_sequence` values rather than reporting only a percentage.

A resilience run is INVALID when:

```text
the Fabric-endpoint block also breaks Gateway-01 ingress, cloud/VPC connectivity, or another unrelated required service
EMU-01 source capture is lost
EMU-01 stops for an unrelated reason
the frozen interruption method was not applied for the full 60 minutes
a required non-Fabric service fails for an unrelated setup problem
phase boundaries cannot be reconstructed from evidence
```

A valid run can still **FAIL** if local telemetry stops or the backlog does not recover. Keep that failure as research data.

## 9. Repeat three times

Use identical configuration and interruption method.

Do not combine a resilience run with flooding, HA failover, backup restore, or intentional OpenBao sealing.

---

## Additional gateway-backhaul buffer test - not part of Table 17

The project also needs to prove the Raspberry Pi's local store-and-forward queue. Run this separately from the counted Internet test.

Temporarily block only the gateway's route to server MQTT `8883` while the gateway and EMU-01 stay powered.

Expected:

```text
EMU-01 -> gateway real RF continues
gateway local Mosquitto queue grows
server receives no new gateway events during block
restore route
gateway queue drains
ChirpStack receives delayed events
Node-RED/TimescaleDB remain duplicate-safe
stale downlinks are not replayed
```

Use [Gateway Availability Tests](../../deployment/gateway/operations/03-availability-tests.md) for the detailed queue checks.

If the reviewed gateway journal is enabled, also verify journal continuity and checkpoint/segment recovery. Do not make this optional architecture test part of the Chapter IV v1 result unless the methodology explicitly includes it.

## Pass condition

Across the three counted runs:

```text
local required services remain available during Internet loss
expected EMU-01 `test_sequence` records are stored without duplicates
record order remains correct
Fabric unavailability does not stop telemetry
queued/retryable Fabric work recovers correctly
no conflicting duplicate ledger state is produced
```

Continue to [Execution 09 - Results and Completion](09-results-and-completion.md).
