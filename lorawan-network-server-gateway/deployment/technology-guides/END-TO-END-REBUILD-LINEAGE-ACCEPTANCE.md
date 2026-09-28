# End-to-End LoRaWAN System — Rebuild Order, Data Lineage, Failure Isolation and Acceptance

**Purpose:** provide one foolproof, self-contained operator view of how the entire project fits together from the physical EMU-01 sensor through Gateway-01, cloud HA services, independent evidence verification, and HRC Fabric anchoring. This expands [technology guide 21](21-end-to-end-integration-and-data-lineage.md). It is an integration/recovery chapter, not a replacement for the detailed technology chapters. A dated topology or historical PASS is context only; verify current roles and identities before declaring the system healthy.

## 1. The whole system in one picture

~~~text
EMU-01 RAK4631 agricultural sensor
  payload-v2 / 46 bytes / plain AS923 / OTAA / Class A
        |
        v
RAK5146 + Concentratord on Gateway-01
        |-------------------------------> gateway-integrity-journal
        |                                      |
        v                                      v
MQTT Forwarder -> local Mosquitto         hash-chained evidence
  QoS 1          persistent queue              |
        |                                      v
        |                                  uploader / receipts
        |                                      |
SIM7600 LTE wwan0                              | HTTPS+mTLS
        |                                      v
        +---------------> cloud ----------> ingest-1/2
                           |                  -> SeaweedFS exact raw objects
                           v
                     cloud Mosquitto
                       /        \
            ChirpStack MQTT    evidence collectors 1/2
                 |                   |
                 v                   |
            ChirpStack 1/2           |
              |  |  |                |
              |  |  +-> Valkey HA    |
              |  +----> PostgreSQL <--+
              v                       |
        application MQTT              |
              |                       v
       Node-RED A only        verifier-1/2 + trusted decoder
              |                       |
              v                       v
       telemetry.uplinks      gateway_evidence.event_verification
       telemetry.measurements          |
       telemetry.fabric_outbox <-------+
              |
     eligible exact finalized bytes
              |
              v
     Fabric adapter ULC-01 only
       |                |
       v                v
OpenBao Transit      HRC Fabric Gateway
sign/verify          10.104.0.7:7051
       \                /
        +-> commit/query/digest verification
              |
              v
          confirmed

Grafana reads SQL only.
Research recorder captures and seals formal experiment evidence.
~~~

The normal telemetry path and independent evidence path deliberately meet **after** their separate source observations. Never collapse them into one process or infer gateway integrity only from application success.

## 2. Authoritative identities and boundaries

| Layer | Authoritative identity / rule |
|---|---|
| EMU-01 | DevEUI `ac1f09fffe296d29`; JoinEUI `0000000000000000`; protected AppKey |
| Gateway-01 | EUI `0016c001f139a1cb`; plain AS923; management Ethernet is not production Internet |
| Gateway backhaul | SIM7600/QMI `wwan0` is intended field production WAN; Wi-Fi fallback is not assumed unless separately configured/tested |
| MQTT | local persistent loopback broker -> public mTLS ingress -> independent ULC-01/02 cloud brokers |
| ChirpStack | two application instances, one logical LoRaWAN state through shared PostgreSQL/Valkey/MQTT |
| Database | Patroni one writable primary, two replicas; clients use local PgBouncer/HAProxy, not fixed leader IP |
| Node-RED | ULC-03 active writer; ULC-02 stopped/fenced standby |
| Grafana | ULC-03 private loopback dashboard, telemetry_reader only |
| Evidence | journal/uploader + two cloud broker witnesses + Seaweed exact objects + verifier-owned status |
| OpenBao | 3-voter KMS; non-exportable `lorawan-evidence` Transit key |
| Fabric | ULC-01 sole enabled adapter; ULC-02 disabled until explicit HA-fencing acceptance |
| HRC | source namespace `lorawan-gateway-evidence`, channel `hrc-channel`, chaincode `hrc-evidence`, private Gateway `10.104.0.7:7051` / TLS `peer1.hrc.local` |

If any live configuration disagrees with this table, stop and determine whether the infrastructure intentionally changed or the documentation is stale. Do not force a live environment back to a document without evidence.

## 3. Correct rebuild order for a complete replacement

A full environment rebuild should restore dependencies in this sequence. **This is not an instruction to restart a working system in this order.**

1. **ULC host substrate:** Ubuntu, private VPC addresses, Docker/Compose, disks, time, DNS, firewall, protected host directories.
2. **PKI/service trust:** public CA chains, host/service leaf identities, secure private-key ownership, protected secret stores.
3. **Patroni DCS etcd:** three intended private HTTP voters on 2379/2380.
4. **PostgreSQL/Patroni/TimescaleDB:** compatible image/database backup, one writable leader and replicas.
5. **HAProxy + PgBouncer:** primary-routing SQL frontends and SCRAM/TLS identities.
6. **Valkey/Sentinel:** one elected master/two replicas, 3 Sentinels/quorum and app-local writable-master routes.
7. **Cloud Mosquitto:** two independent persistent broker services, gateway/workload listeners and ACLs.
8. **SeaweedFS:** its separate metadata-etcd, master/volume/filer/S3, replication 010 and TLS create-only frontend.
9. **OpenBao:** restore existing Raft/KMS state or perform exactly-one initialization for a truly new cluster; re-establish Transit/AppRole/audit.
10. **ChirpStack:** pinned version/config/AS923 region and restored device/gateway registry; prove DB/Valkey/MQTT dependencies.
11. **Node-RED:** restore reviewed flow/palette/env/PKI; start only A while B is positively stopped/fenced.
12. **Grafana:** read-only datasource and private workstation tunnel; restore dashboards after SQL source is healthy.
13. **Gateway-01 OS/radio/backhaul:** approved image, RAK5146/AS923, local MQTT queue, SIM7600/QMI route and mTLS bridge; preserve journal/checkpoint continuity.
14. **Gateway evidence services:** ingest/collectors/verifiers and retained object/database lineage; Fabric adapter remains disabled while dependencies are validated.
15. **Fabric adapter:** activate only the authorized ULC-01 writer after preflight, exact identity and external HRC handoff; keep ULC-02 fenced.
16. **EMU-01:** correct physical assembly, accepted production firmware, credentials, OTAA and one real application uplink.
17. **Research workstation:** recorder restricted SSH, serial ownership, clock gate, Grafana tunnel and current formal readiness.

At every step, validate the **smallest representative real operation** needed to prove that layer before moving down the dependency graph.

## 4. Follow one real EMU-01 event without guessing

For a new known transmission after a recorded UTC start time:

1. **Source:** capture EMU `SENSOR_TX` with test/source sequence, validity `0x007F`, joined state and send status; reconstruct the exact 46 application bytes.
2. **RF:** confirm a new RAK5146/Concentratord uplink with correct gateway EUI, AS923 frequency/data-rate and reception timestamp.
3. **Gateway evidence:** confirm a new independent journal sequence/hash and later closed/receipted segment/checkpoint.
4. **Gateway MQTT:** observe local `as923/gateway/0016c001f139a1cb/event/#`, then prove the remote bridge used the intended LTE route.
5. **Cloud brokers:** identify the event on cloud MQTT. Collector duplicates from the same gateway uplink ID are transport witnesses, not multiple RF transmissions.
6. **ChirpStack:** confirm same DevEUI/frame/event, accepted LoRaWAN security/session and application event.
7. **Node-RED/DB:** locate exactly one canonical uplink by stable event identity and its normalized metric rows; compare `raw_data` byte-for-byte to reconstructed source bytes.
8. **Evidence verifier:** match journal object, MQTT witness, trusted decoder, exact raw application bytes, telemetry fields, and verifier-owned status.
9. **Fabric:** only if selected/eligible, inspect exact immutable `finalized_payload`, claim state, OpenBao signature, HRC transaction, commit status, source-bound query and digest MATCH.
10. **Display:** confirm Grafana shows the same timestamp/device/units, but use SQL/recorder/evidence artifacts as research authority.

A “green” later layer cannot substitute for missing earlier proof. For example, a database row cannot prove physical RF reception if the source/radio evidence is absent.

## 5. Data-quality and unit rules that must survive every layer

| Measurement | Stored/display rule |
|---|---|
| soil moisture | percent (%) when valid |
| soil temperature | °C |
| UV | UV index, explicitly dimensionless |
| barometric/environment pressure | source Pa; dashboard may convert Pa -> kPa numerically |
| ambient/soil/barometer temperature | distinct named °C series, never merged under a generic temperature without labels |
| humidity | % |
| light | lux (lx), sensor identities separate |
| gas resistance | ohm source; dashboard may convert to kΩ numerically |
| rain | Boolean wet/dry, not “% rain” |
| battery | volts only for a valid positive reading; USB sentinel 0 means unavailable, not 0 V/0% |
| RSSI | dBm |
| SNR | dB |
| network utilization | Mbps derived from byte-counter deltas/time; never an unexplained “%” |
| CPU | %, with host/container context |
| RAM | MiB used / total MiB plus % |
| latency | label the start/end events and unit; app→DB is not RF or Fabric latency |

Invalid sensor group bits should remain traceable in raw accepted payload provenance while normalized numeric value is null/invalid according to mapper policy. Never convert missing or invalid data to a visually convenient zero.

## 6. Failure isolation — start at the earliest missing fact

| Symptom | Earliest boundary to prove | Avoid |
|---|---|---|
| no EMU serial | power/USB/firmware/profile | server restarts |
| serial TX but no gateway RF | antenna/frequency/SF/BW/radio conditions | DB/Fabric changes |
| gateway RF but no local MQTT | Concentratord -> MQTT Forwarder/broker | device key reset |
| local MQTT, no cloud | SIM7600 public dataplane, route, DNS, bridge TLS | forcing Ethernet production route |
| cloud MQTT, no ChirpStack event | MQTT workload route/ACL, gateway registration/session | sensor reflashing |
| ChirpStack app event, no DB | Node-RED sole writer, payload validation, PgBouncer/primary | radio changes |
| DB telemetry, evidence pending | journal/witness/object correlation/verifier | Fabric restart |
| verified eligible row, not confirmed | adapter lease/OpenBao/HRC transaction stages | rewriting `finalized_payload` |
| Grafana blank but SQL fresh | query/time/device/dashboard version | re-running sensor test |
| research runner blocked | readiness/methodology/clock/hardware gate | bypassing status manually |

When one host fails, preserve surviving quorum and writer fencing first. Do not “recover” by starting every standby at once.

## 7. Outage behavior and what should continue

**External Internet/LTE outage:** EMU may continue transmitting; gateway RF/journal/local MQTT persistence should continue within finite storage limits; cloud reception stops; after recovery buffered QoS-1 gateway events may replay. Application QoS-0 Node-RED subscription is a different boundary and does not guarantee replay of events missed while both app subscribers are absent.

**Fabric unavailable:** telemetry and evidence can continue; eligible outbox waits/reconciles. Never block agricultural telemetry on external ledger availability.

**OpenBao unavailable:** telemetry and evidence continue; adapter cannot complete signing/submission.

**One PostgreSQL node lost:** surviving Patroni quorum/replication and HAProxy primary route should preserve service if a healthy leader exists; repair the member, not client configs.

**One cloud MQTT broker lost:** reconnects can move workloads; the evidence collectors intentionally observe both fixed broker backends because sessions are not replicated.

**One Node-RED host lost:** promote the standby only after authoritative fencing of the old writer; record any QoS-0 application events missed during the gap.

**One evidence replica lost:** repair it while the other remains; do not weaken trust requirements or delete raw evidence.

## 8. Research acceptance versus infrastructure acceptance

Infrastructure “operational” normally means required service is running, intended interface reachable, one representative real operation works, and no immediate critical error exists. That is **not automatically a completed research trial**.

Formal Chapter IV work additionally requires:
- current test status READY under the generated gate;
- exact Chapter III condition/count/duration;
- correct device firmware/profile and controlled fixture;
- time calibration within the specified tolerance;
- source denominator and all required raw streams;
- run classification PASS/FAIL/INVALID/BLOCKED based on evidence;
- sealed manifest/hashes and deterministic recomputation;
- restoration of production state after the trial.

Non-counted rehearsals, synthetic tests and historical commissioning PASS results remain useful engineering evidence, but they must not be included in counted research statistics.

## 9. Recovery boundary across gateway, database and Fabric

Do not restore these systems independently to arbitrary historical points:

~~~text
Gateway journal/checkpoint
SeaweedFS retained objects
PostgreSQL gateway_evidence + telemetry.fabric_outbox
OpenBao signing state
External HRC Fabric ledger
~~~

Before a major restore, identify the **last mutually accepted source/checkpoint/transaction**. A stale gateway journal copied back after the cloud accepted newer sequences can create continuity conflict. A database snapshot from before an already committed HRC anchor can cause a previously submitted row to look unsent. Reconcile with authoritative evidence and Fabric Query/CommitStatus before resuming writers. Preserve uncertain prepared transaction state rather than generating a new proposal.

## 10. Final whole-platform acceptance checklist

Use this after a full rebuild or materially cross-cutting change:

~~~text
[ ] three ULC host identities/time/storage/runtime sane
[ ] etcd 3/3 and one leader
[ ] Patroni one writable primary + healthy replicas
[ ] local SQL routes return the current primary
[ ] Valkey one master/two replicas + Sentinel quorum
[ ] two cloud Mosquitto brokers and private workload routes healthy
[ ] ChirpStack 1/2 same pinned release, correct AS923 and registry
[ ] Node-RED exactly one active writer; standby fenced
[ ] Grafana private/read-only
[ ] OpenBao 3 voters, unsealed, signer policy least privilege
[ ] Seaweed metadata quorum + placement/create-only endpoint healthy
[ ] evidence ingest/collectors/verifiers ready and trusted decoder passes
[ ] ULC-01 sole Fabric writer, ULC-02 disabled unless HA acceptance says otherwise
[ ] Gateway-01 RAK5146 + local MQTT + LTE production route healthy
[ ] EMU-01 correct production firmware, sensors, OTAA and one real uplink
[ ] same real event traceable source -> RF -> MQTT -> ChirpStack -> DB
[ ] same real event independently verified when required
[ ] if Fabric tested: authoritative commit + Query + Verify MATCH
[ ] no secret/private-key values exposed in retained operator evidence
[ ] any formal test run sealed and classified separately from commissioning
~~~

Do not repeat disruptive failover tests when the material change did not affect failover. Match verification to risk.

## 11. Where the comprehensive Word document will get its material

The final self-contained Word document should incorporate the complete companion chapters for Gateway OS, RAK5146/AS923, SIM7600, MQTT, ChirpStack, etcd, PostgreSQL/Patroni/TimescaleDB, HAProxy/PgBouncer, Valkey/Sentinel, Node-RED, Grafana, OpenBao, SeaweedFS, gateway evidence, Fabric, PKI/TLS, ULC runtime, EMU-01, research automation and SEC/RUI3. The numbered guides are operator entry points; this integration chapter supplies the dependency/order narrative.

The Word document must not require a reader to open repository Markdown to learn how to restore or test the system. Repository links remain provenance for maintainers, while the published manual must contain the procedures themselves.
