# Evidence Services + Gateway Journal — Current Continuation

This is the immediate execution board for gateway-integrity v2. Read it with `00-current-server-continuation-checkpoint.md`; use `00-build-execution-log.md` for historical detail only.

## 1. Current boundary

The **cloud/server evidence lane is commissioned**. Do not repeat its rollout unless a later change or failure invalidates the recorded evidence.

```text
Core cloud HA stack                                      PASS
Node-RED A active / B fenced                            PASS
Grafana server path                                     PASS
OpenBao 3-node KMS + audit                              PASS
SeaweedFS S0-S9                                         PASS
gateway_evidence migration/HBA/CONNECT/six LOGINs      PASS
PgBouncer evidence SCRAM expansion, all three nodes     PASS
Four immutable GHCR cloud image refs                    PASS
Evidence PKI                                            PASS
Four collector MQTT mTLS identities + read-only ACLs   PASS
Ingest replicas 1/2                                     PASS
Collector replicas 1/2, each connected to both brokers PASS
Verifier/trusted-decoder replicas 1/2                   PASS
Fabric adapter replicas                                 DISABLED STANDBY / PASS
Shared anchor :443 SNI split                            PASS
Grafana evidence checkpoint/verification panels         PASS
Representative gateway-style MQTT witness               PASS
Gateway Rust default source gate                        PASS, 28 tests / 0 failed
Gateway OS target package/install                       DELEGATED TO SEPARATE AGENT / DO NOT DUPLICATE HERE
Real gateway v2 lineage                                 HARDWARE DEPENDENT
Public WAN normal path                                 PASS; Reserved-IP failover authority/test still pending
Fabric ledger activation                                EXTERNAL HANDOFF PENDING
```

Current high-level markers:

```text
EVIDENCE_PREIMPLEMENTATION_GATE=PASS
EVIDENCE_CLOUD_RUNTIME=PASS
PUBLIC_INGRESS_NORMAL_PATH=PASS
PUBLIC_RESERVED_IP_FAILOVER=EXTERNAL_AUTH_PENDING
GATEWAY_EVIDENCE_RUNTIME=SERVER_PASS_GATEWAY_PENDING
GATEWAY_EVIDENCE_V2_NORMAL_PATH=NOT_YET_CLAIMED
```

## 2. Commissioned immutable cloud release

Production release files use:

```text
EVIDENCE_INGEST_IMAGE=ghcr.io/jervis-umtc/lorawan/gateway-evidence-ingest@sha256:f2fd695e8d2505a12202b4fabd92d035c562e16d4e308ccf9436a08a36aaec1a
EVIDENCE_COLLECTOR_IMAGE=ghcr.io/jervis-umtc/lorawan/gateway-mqtt-evidence-collector@sha256:0bcaaa127f913157596a87077235d4f0717fa1c29f08d8aca8568c3167ed2cff
EVIDENCE_VERIFIER_IMAGE=ghcr.io/jervis-umtc/lorawan/gateway-evidence-verifier@sha256:3416496fa563154fbd7209a575acd040b735b3c4f4159902fc886e78167195c0
EVIDENCE_ADAPTER_IMAGE=ghcr.io/jervis-umtc/lorawan/gateway-fabric-adapter@sha256:cd4308e8985d74ea7fab957a2a4adadd1831b776a8f9af2fdd6291179df83e7a
```

Placement:

```text
ulc-01: ingest-1 + collector-1 + Fabric adapter-1 disabled
ulc-02: ingest-2 + verifier-1 + trusted decoder + Fabric adapter-2 disabled
ulc-03: collector-2 + verifier-2 + trusted decoder
```

Each evidence container is commissioned with numeric `65532:65532`, read-only rootfs, `cap_drop: ALL`, `no-new-privileges`, `pids_limit: 128`, `192 MiB`, `0.20 CPU`, bounded logs, and `restart: unless-stopped`.

All three repository `preflight.sh` executions passed against the actual protected env/PKI files and immutable release references.

## 3. Storage, database, MQTT and normal-path evidence

SeaweedFS S9 was closed with the production Go helper through:

```text
https://evidence-objects.internal.lorawan.com:18443
```

The retained create-only fixture was verified from another host. Record:

```text
OBJECTSTORE_CONTRACT=PASS
SEAWEEDFS_S9_WRITE=PASS
SEAWEEDFS_S9_CROSS_HOST_VERIFY=PASS
EVIDENCE_OBJECTSTORE=PASS
```

All three PgBouncer nodes carry the same ten-entry/six-evidence SCRAM userlist:

```text
sha256 665f1592c96ca276681a454b9cbcd6ab8ab0cbfb4594b8ddd443239db58df391
mode   0640 root:postgres
```

Strict `sslmode=verify-full` evidence sessions through each physical `:6432` endpoint authenticate and route to the writable Patroni primary.

Collectors use four distinct client certificates. Each replica maintains persistent read-only subscriptions to both physical Mosquitto backends:

```text
10.104.0.2:8884
10.104.0.4:8884
TLS name: mqtt.internal.lorawan.com
topic:    as923/gateway/+/event/#
```

A controlled Gateway EUI `0016c001f139a1cb` AS923 `event/up` produced exactly one deduplicated durable witness with the expected semantic fields, including frequency `923200000`, RSSI `-72`, SNR `8.5`, uplink ID `16909060`, PHY hash/correlation identity, and immutable object reference. A collector-credential publish attempt did not create a second capture, confirming the read-only authorization boundary in practice.

## 4. Shared :443 is commissioned server-side

DigitalOcean anchor addresses are host-local ingress anchors, not the east-west VPC:

```text
ulc-01 anchor 10.15.0.5
ulc-02 anchor 10.15.0.7
service VPC     10.104.0.0/...
```

Both HAProxy nodes now use the same trust split:

```text
anchor :443 TCP ClientHello/SNI dispatcher
  evidence.internal.lorawan.com
      -> TCP passthrough -> local private ingest :18100
      -> ingest owns server TLS + gateway client-certificate validation

  chirpstack.internal.lorawan.com
      -> TCP -> 127.0.0.1:14443
      -> existing ChirpStack TLS termination / HTTP backend
```

Validated results:

```text
ChirpStack ordinary HTTPS remains HTTP 200
Evidence without a client certificate is rejected
Gateway Evidence client certificate traverses shared :443 to ingest readiness
HAProxy configuration validation PASS on both nodes
rollback copies retained on both nodes
```

Do not replace this with a second independent `:443` bind and do not globally require a gateway client certificate from ChirpStack browser/API users.

## 5. Gateway handoff bundle

The authoritative gateway identity is:

```text
Gateway EUI: 0016c001f139a1cb
Region:      AS923
MQTT prefix: as923
```

A consolidated root-only handoff set exists on `ulc-03`:

```text
/root/lorawan-gateway-handoff/0016c001f139a1cb/
  mqtt/ca.crt
  mqtt/client.crt
  mqtt/client.key
  evidence/ca.crt
  evidence/client.crt
  evidence/client.key
  manifest.txt
```

Encrypted transfer artifact:

```text
/root/lorawan-gateway-handoff/gateway-handoff-0016c001f139a1cb.tar.gz.enc
sha256 6e957385f9e4467b1924368a16a719c27d50cd0f90941435e420636af2ec94d3
```

The private keys remain `0600 root:root` in the protected source bundle. Keep the authoritative issuer copies for revocation/recovery. The bundle is **not yet claimed installed on the physical gateway**.

**Server-side plug-and-play recheck — 2026-09-01 16:25 +08:** the encrypted handoff artifact is still `0600 root:root`, 9552 bytes, and SHA-256 `6e957385f9e4467b1924368a16a719c27d50cd0f90941435e420636af2ec94d3`. Both gateway private keys remain `0600 root:root`. The Evidence client certificate is CN `0016c001f139a1cb`, valid through 2027-10-03; the MQTT client certificate has the same CN and is valid through 2027-09-29. From `ulc-03`, the real Evidence identity returned `{"status":"ready"}` through `https://smartagri-evidence.duckdns.org/readyz`, while the same request without a client certificate failed with TLS `certificate required`. The real MQTT identity received `CONNACK (0)` and `SUBACK` on `as923/gateway/0016c001f139a1cb/command/#`. `ulc-03` collector and verifier readiness remain PASS, with both MQTT broker sessions connected/subscribed and zero collector errors; the certificate-health timer is active/enabled. From the administration workstation, `https://smartagri-chirpstack.duckdns.org/` still returns HTTP `200`. This proves the server handoff is ready for the separately managed gateway lane without changing Gateway OS.

## 6. Gateway Rust source state

Pinned toolchain:

```text
Rust 1.82.0
rustc commit f6e511eec7342f59a25f7c0534f1dbea00d01b14
```

Current source includes:

```text
gateway-evidence-writer long-running entry point
gateway-evidence-uploader long-running entry point
optional concentratord-zmq SUB input
crash-safe PersistentJournal
open/closed canonical segment persistence
same-directory state replacement + directory fsync on Unix
torn-tail recovery and state-ahead rejection
finite journal budget fail-closed behavior
age/count segment rotation
durable canonical ReceiptStore
checkpoint/segment receipt validation
curl HTTPS/mTLS transport
server CA/name verification + gateway client certificate/key
bounded connect/request time
bounded exponential retry/backoff
--sync-once
continuous uploader loop
no evidence-delete/retirement API
```

Fresh default-feature verification on 2026-09-01:

```text
cargo fmt --all -- --check                         PASS
cargo test --locked                                PASS: 28 total, 0 failed
  unit tests                                       19
  contract tests                                    9
cargo clippy --locked --all-targets -- -D warnings PASS
cargo build --locked                               PASS
```

This does not replace target validation. `concentratord-zmq` must be compiled with the Gateway OS/OpenWrt-capable toolchain and proven against real IPC bytes.

## 7. Delegated gateway lane — reference only

**Coordination boundary — 2026-09-01:** Gateway OS/OpenWrt setup, target build/package, and gateway-local configuration are actively owned by a separate agent. This server continuation must not inspect, edit, build, or mutate that lane. The material below remains architecture/reference context only; consume the separate agent's accepted result when it is ready.

Repository package material is present under:

```text
evidence-services/gateway/packaging/openwrt/
```

The target lane is:

```text
1. inspect the actual pinned Gateway OS v4.12.0/OpenWrt build environment;
2. build the writer/uploader for the exact Raspberry Pi target with `concentratord-zmq`;
3. verify the OpenWrt package, UCI config, procd services, user/group ownership and persistent paths;
4. stage the consolidated MQTT + Evidence identities without weakening key permissions;
5. produce a reproducible Gateway OS package/image artifact;
6. when the physical gateway is reachable, install/boot and prove one representative normal lineage.
```

Do not treat a Windows host build or generic Linux build as target acceptance.

## 8. Public WAN normal path is commissioned

The production public names now resolve through Reserved IPv4 `129.212.208.168`, currently owned by `ulc-01`:

```text
smartagri-chirpstack.duckdns.org:443  -> shared HAProxy SNI -> ChirpStack
smartagri-evidence.duckdns.org:443    -> shared HAProxy SNI -> Evidence ingest mTLS
smartagri-mqtt.duckdns.org:8883       -> HAProxy TCP passthrough -> Mosquitto mTLS
```

Accepted normal-path evidence:

```text
ChirpStack public HTTPS with normal system trust                  PASS
Evidence public hostname + server chain                           PASS
Evidence no-client-certificate rejection                         PASS
Gateway Evidence client mTLS /readyz                              PASS
MQTT public hostname verification                                 PASS
Gateway MQTT mTLS CONNECT / authorized SUBSCRIBE                  PASS
ChirpStack certificate renewal + ulc-01 -> ulc-02 synchronization PASS
Daily certificate-expiry monitoring on ulc-01/02/03               PASS
```

ChirpStack uses a Let's Encrypt public certificate. MQTT and Evidence intentionally keep their private client-auth trust roots while their server certificates include the public DuckDNS SANs. Do not replace them with anonymous/public-client authentication merely because the server endpoints are Internet reachable.

The remaining provider boundary is **Reserved-IP mobility**, not ordinary public service activation. A suitable least-privilege DigitalOcean API identity and a controlled ulc-01 <-> ulc-02 reassignment/failover acceptance are still required before automatic public-ingress failover is claimed. Do not expose raw Droplet public IPs as a bypass.

## 9. Grafana evidence observability

The existing `LoRaWAN Telemetry Overview` dashboard on `ulc-03` now has six provisioned panels. The two evidence panels are:

```text
Evidence checkpoints
Evidence verification state
```

They use the existing strict-TLS `telemetry_reader` datasource and approved read-only evidence views. No evidence write privilege was added. Grafana loaded the six-panel file through its provisioning watcher without a container restart.

## 10. Fabric stays last

OpenBao 3/3, audit, the outbox, adapter source, immutable adapter image, and both disabled adapter standbys are ready. Do not issue an adapter SecretID or enable Fabric execution until the external handoff supplies and validates the Fabric Gateway/TLS model, MSP identity, channel, chaincode/contract/function semantics, and client identity. One real confirmed transaction plus reconciliation behavior is required before Fabric is called live-complete.

## 11. Real end-to-end acceptance

The first physical normal path must prove one real uplink, not a large chaos matrix:

```text
RAK5146 / Concentratord
  -> gateway journal record
  -> closed segment/checkpoint
  -> HTTPS/mTLS ingest
  -> replicated raw object

same uplink
  -> MQTT Forwarder QoS 1
  -> remote Mosquitto
  -> read-only collectors
  -> ChirpStack application event
  -> Node-RED / TimescaleDB

journal + checkpoint + MQTT + application + telemetry
  -> verifier + pinned trusted decoder
  -> gateway_evidence.event_verification = verified
```

Only after that may the matching v2 Fabric work become eligible. Save reboot/WAN/tamper/failover stress matrices for the later acceptance phase unless a defect requires earlier diagnosis.

## 12. Resume rule

On a new chat:

1. inspect this board and the broader current checkpoint through `jervis-lorawan`;
2. do **not** re-run completed cloud evidence commissioning;
3. do **not** inspect, edit, build, or mutate Gateway OS/OpenWrt setup/package paths from this server lane; that work is delegated to a separate agent;
4. preserve the already-PASS public normal path and server handoff while waiting for the delegated gateway result;
5. keep Reserved-IP failover authority and Fabric activation as explicit external gates;
6. consume the delegated gateway result and claim physical v2 completion only after one real gateway lineage.
