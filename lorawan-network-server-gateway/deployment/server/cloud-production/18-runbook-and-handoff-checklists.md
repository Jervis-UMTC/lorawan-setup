# 18. Commissioning and Incident Runbook

> **Status: STANDBY / DRAFT.** Final commissioning and handoff cannot be accepted until the remaining technology phases are deployed and tested. Update this runbook incrementally from the execution log.

Use this runbook after the detailed gateway and cloud guides have been completed. It verifies the live system in dependency order and provides focused procedures for certificate rotation, Gateway OS upgrades, and buffer incidents.

## 18.1 Keep the values needed to operate and recover the system

Store these non-secret values with the encrypted configuration and backup references:

| Value | Why it is needed |
|---|---|
| Environment, gateway count, and physical gateway references | Identifies the systems covered by the runbook |
| Cloud host OS baseline: Ubuntu Server 24.04 LTS x64, slug `ubuntu-24-04-x64`, numeric image ID/Created timestamp used for commissioning, kernel release, and tested package/container baseline | Rebuilds ha-01/02/03 consistently and distinguishes the selected Ubuntu release from the exact provider image build that was tested |
| Gateway OS Base release, factory-image hash, and rollback location | Rebuilds a failed SD card with the tested image |
| RAK5146 variant, region, sub-band, antenna gain/loss, and Concentratord plan | Prevents an invalid RF configuration during restore |
| Gateway EUI and MQTT region prefix | Links Concentratord, certificates, topics, ACLs, and ChirpStack registration |
| MQTT Forwarder loopback endpoint, QoS, backend, and client ID | Confirms traffic cannot bypass the local buffer |
| Local Mosquitto version, configuration path, queue path, finite limits, autosave, and free-space reserve | Reproduces and monitors outage buffering |
| Journal implementation/format version, executable hash, evidence path/budget, last sequence/segment hash | Reproduces and verifies the gateway evidence path |
| Latest accepted checkpoint receipt/sequence/hash and evidence endpoint identity | Establishes the off-device rollback boundary during recovery/migration |
| Remote MQTT FQDN/port and certificate fingerprint/expiry | Rebuilds and rotates the mutual-TLS bridge |
| Reserved IPv4, ha-01/ha-02 Droplet IDs, anchor IPs, current owner, failover-agent version/hash, and last reassignment test | Rebuilds and proves the self-managed public ingress |
| Encrypted gateway, broker, database, and infrastructure backup locations | Recovers each independent failure domain |
| Most recent outage/reboot/drain, journal/checkpoint/reconciliation, stale-downlink, gateway restore, broker failover, database restore, OpenBao member-loss, adapter-loss, and Fabric-outage results | Shows which recovery claims have actually been tested |
| OpenBao cluster member IDs, stable KMS FQDN, recovery-material reference, Transit key name/version policy, and latest snapshot result | Rebuilds the evidence KMS without exporting its signing key |
| Fabric Gateway endpoint metadata, MSP/channel/chaincode/function names, adapter worker IDs, client-certificate fingerprints, and outbox schema version | Reconnects and reconciles the external Fabric integration |

Do not store passwords, private keys, AppKeys, NwkKeys, or live tokens in this table.

## 18.2 Verify the public and private network boundary

From an authorized administration host, inspect DNS, TLS, and the externally reachable ports. On each server and gateway, inspect local listeners and firewall rules.

Expected public endpoints:

```text
chirpstack.<DOMAIN>:443 -> Reserved IPv4 -> current HAProxy anchor listener -> ChirpStack
mqtt.<DOMAIN>:8883      -> same Reserved IPv4 -> current HAProxy anchor listener -> MQTT TLS pass-through
evidence.<DOMAIN>:443   -> gateway evidence HTTPS/mTLS ingest, only when v2 is deployed
```

Healthy evidence:

- MQTT `1883` and Semtech UDP `1700` are not public;
- Gateway OS LuCI, SSH, and local Mosquitto are not internet-facing;
- gateway port `1883` binds only to `127.0.0.1`;
- PostgreSQL, Valkey/Sentinel, etcd, Patroni, PgBouncer, OpenBao `8200/8201`, HAProxy KMS `18200`, and monitoring ports remain private;
- both public DNS names resolve to the same Reserved IPv4;
- Reserved-IP ownership is one of `ha-01/ha-02`, never `ha-03`;
- the current HAProxy MQTT path preserves the gateway client certificate;
- manual and automatic Reserved-IP reassignment have been tested without DNS edits;
- an authenticated MQTT publish/subscribe health test passes;
- when gateway evidence is enabled, the evidence endpoint requires the approved per-gateway machine identity and does not expose an unauthenticated upload API.

An open TCP port without a certificate/ACL test proves only socket reachability. Any unexpected public listener must be removed or restricted before device commissioning.

## 18.3 Verify the gateway from hardware to cloud

1. Confirm the installed Raspberry Pi, RAK5146 frequency variant, Pi HAT, antenna band/gain, cable loss, and legal region match the retained configuration.
2. In Gateway OS, verify Concentratord initializes the radio and reports the expected stable Gateway EUI.
3. Verify UDP Forwarder has no server and no unsupported alternate packet-forwarder service owns the radio.
4. Verify MQTT Forwarder uses backend `concentratord`, Protobuf, QoS 1, a fixed client ID, and `tcp://127.0.0.1:1883`.
5. Verify local Mosquitto listens only on loopback and its queue path is persistent, writable, finite, and above the free-space reserve.
6. Verify the integrity journal independently consumes the supported Concentratord event interface, its sequence/hash chain is healthy, its evidence storage budget is finite, and its latest checkpoint age is within policy.
7. Verify the `cloud-uplink` bridge uses QoS 1 and a persistent session for event/state topics.
8. Verify the `cloud-downlink` bridge uses QoS 0 and a clean session for command topics.
9. On the remote broker, confirm both bridge client IDs authenticate with the certificate whose Common Name equals the Gateway EUI.
10. Test that the gateway can use only its own event/state/command topics and is denied access to another Gateway EUI.
11. When gateway integrity is enabled, prove the dedicated server collector can read gateway event topics but cannot publish them, and the gateway uploader can write only its own evidence identity/path.
12. Perform the WAN-outage, gateway-reboot, queue-drain, journal-reconciliation, queue/journal-limit, duplicate-handling, and stale-downlink tests.
13. Complete one real OTAA join, decoded uplink, safe Class A downlink, and—when enabled—one `verified` gateway evidence lineage.

A healthy gateway keeps receiving packets and growing its local queue during a remote outage, then drains after recovery without duplicate application rows. A connected bridge with no ChirpStack last-seen update points to topic prefix, ACL, Protobuf, or region configuration rather than RF hardware.

## 18.4 Verify remote MQTT and ChirpStack

1. Verify the broker certificate SAN contains `mqtt.<DOMAIN>` and the public connection requires a trusted client certificate.
2. Confirm each gateway has a unique certificate and exact EUI ACL; ChirpStack and integrations use separate identities.
3. Confirm the CA private key is absent from runtime mounts and gateways.
4. Verify every enabled ChirpStack region uses the same MQTT topic prefix as Gateway OS.
5. Confirm no server-side Gateway Bridge is present in the active path.
6. Check PostgreSQL through PgBouncer -> HAProxy, Valkey/Sentinel, and each ChirpStack instance with dependency-aware health checks.
7. Verify gateway last-seen freshness, one real application event, and the expected payload-codec output.
8. Verify `lorawan_telemetry` has TimescaleDB enabled, `telemetry.uplinks` and `telemetry.measurements` are hypertables, and Node-RED derives a stable event key whose uniqueness constraints produce one canonical record after a deliberate retry.
9. For v2, verify the gateway evidence service uniquely links journal -> remote gateway MQTT -> ChirpStack application event, runs the pinned trusted decoder, compares the row stored in `lorawan_telemetry`, and exposes the final status without giving Node-RED permission to set it.
10. Verify OpenBao has three unsealed Raft members before testing and the stable KMS endpoint works after one member loss.
11. Check the Fabric adapter implementation gate. If the reviewed image/source is missing, mark the **overall full-feature commissioning result BLOCKED**. You may still verify the durable outbox and the other HA layers, but do not call the complete POC passed.
12. For the required full-feature pass, deploy adapter-1/2 with different worker IDs, lease-based claims and least-privilege OpenBao identities; prove one real selected event reaches valid Fabric commit status, prove adapter loss is recovered, then prove an external Fabric outage makes the outbox wait and reconcile/drain after recovery without rolling back telemetry.

A broker login is not enough. Wrong region prefixes, read/write ACL direction, client key format, or application integration topics can leave the connection established while no usable device event is processed.

## 18.5 Rotate a gateway MQTT certificate

1. Confirm the Gateway EUI, active certificate fingerprint/expiry, queue state, and encrypted rollback bundle.
2. Drain the local queue when the remote path is healthy.
3. Issue a new `clientAuth` certificate whose Common Name is the same Gateway EUI.
4. Verify issuer, validity, certificate/key match, serial, and SHA-256 fingerprint before transfer.
5. Install the CA, certificate, and key under `/etc/mosquitto/certs/` with the same restrictive ownership used by the working bundle.
6. Validate `/etc/mosquitto/mosquitto.conf` in the foreground, then restart only local Mosquitto.
7. Verify both bridge client IDs, exact topic ACLs, a real uplink, a short outage/drain test, and a fresh safe downlink.
8. Revoke the old certificate and prove it is rejected using the staging or revocation test procedure.
9. Replace the encrypted recovery bundle and certificate-expiry alert reference.

Do not change MQTT Forwarder's loopback endpoint, Gateway EUI, region, or RF plan during certificate rotation. If the new identity fails, restore the previous certificate bundle and broker ACL before changing any other layer.

## 18.6 Upgrade Gateway OS

1. Read the target release notes and verify Raspberry Pi 4B, RAK5146, Concentratord, MQTT Forwarder, required Mosquitto packages, and the reviewed journal implementation/source interface are supported.
2. Inspect the queue and drain it when possible; upload/verify closed journal segments and create/record a final healthy checkpoint when connectivity permits.
3. Preserve the old factory image, encrypted Gateway OS archive, Mosquitto configuration/data, journal configuration/version/hash and continuity metadata, certificate bundles, and hashes.
4. Test the exact image and package feed on spare media or a spare gateway.
5. Restore configuration without changing the Gateway EUI or RF plan.
6. Verify persistent storage, finite queue and journal budgets, both bridges, Concentratord, MQTT Forwarder, journal source/sequence/hash continuity, evidence uploader, and UDP disablement.
7. Run WAN-outage/reboot/drain/reconciliation, OTAA, uplink, payload-codec/trusted-decoder, and safe-downlink tests.
8. Deploy one canary gateway and keep the previous image and configuration until acceptance passes.

A service that starts with a changed UCI schema, volatile queue path, or missing package is not a successful upgrade. Restore the previous tested image on spare media rather than improvising on the only production card.

## 18.7 Respond to a growing or full gateway buffer

1. Confirm Concentratord and MQTT Forwarder are healthy and MQTT Forwarder still uses loopback QoS 1.
2. Inspect local Mosquitto logs, `mosquitto.db` size, configured message/byte limits, filesystem free space, and the free-space reserve.
3. Check DNS, default route, time, 4G registration, remote TCP `8883`, TLS hostname/chain, client-certificate validity, and broker ACL errors.
4. Restore the remote path without deleting `mosquitto.db` or bypassing the local broker.
5. Watch queue size and remote ChirpStack frame counters during drain.
6. Compare unique application records with buffered event identities to identify duplicates or confirmed loss.
7. Send a new safe downlink after recovery and confirm no command created during the outage is replayed.
8. If the outage exceeded the designed queue, identify the retained frame-counter range and update traffic, storage, outage, or alert assumptions before returning to normal operation.

Stop new non-essential changes when the queue is near its finite limit or the filesystem reserve is threatened. Deleting the persistence database destroys recoverable uplinks and transport evidence.

## 18.7A Respond to a growing or stale gateway evidence journal

1. Confirm Concentratord and the journal service are healthy and the sequence is still advancing for known real uplinks.
2. Inspect journal budget utilization, unuploaded closed-segment count/bytes, open segment, last valid record/segment hash, filesystem reserve, and latest accepted server checkpoint age.
3. Check DNS/route/time/TLS/mTLS identity and the `evidence.<DOMAIN>` ingest path independently of MQTT.
4. Restore evidence upload without deleting or rewriting unuploaded segments.
5. Verify uploaded segments extend the previously accepted server anchor and the server reports valid chain continuity.
6. If required evidence was already lost, preserve the last valid chain boundary and mark the affected interval `evidence_gap`; do not regenerate a replacement history from MQTT/`lorawan_telemetry`.
7. If a hash/payload/checkpoint conflict exists, freeze v2 promotion for that gateway and preserve all evidence for investigation.

A healthy MQTT bridge does not clear a stale-checkpoint alert. Delivery and evidence are different paths.

## 18.8 Stop conditions

Do not continue with a destructive or transmitting step when the target gateway/EUI is uncertain, the legal region or antenna path is unconfirmed, the only recoverable SD card or backup could be overwritten, the queue path is volatile, storage is near exhaustion, queue limits are unlimited, a CA private key may be exposed, management access may be lost, stale downlink replay is observed, or the required database/gateway rollback has not been tested.

Resolve the lowest failing layer first and repeat the affected acceptance test before resuming.

## 18.9 Handoff demonstration

The person receiving the system should be able to use the repository without relying on undocumented memory. Have them demonstrate:

1. locating the gateway, server, cloud, and integration procedures;
2. flashing and restoring Gateway OS to spare media;
3. identifying the Gateway EUI and confirmed RF plan;
4. checking Concentratord, MQTT Forwarder, local Mosquitto, integrity journal, remote MQTT, evidence verifier, and ChirpStack in dependency order;
5. explaining why current Gateway Bridge is not the Concentratord buffer and why the journal is not another packet forwarder;
6. sizing and inspecting the finite delivery queue and finite evidence journal separately;
7. performing a WAN-outage/reboot/drain/journal-reconciliation and stale-downlink test;
8. rotating and revoking a staging gateway certificate;
9. proving cross-gateway ACL denial and application deduplication;
10. completing a real uplink, codec/trusted-decoder check, safe downlink, and—when v2 is enabled—one verified gateway evidence lineage;
11. explaining `pending` vs `evidence_gap` vs `integrity_failure` vs `verified` and why only verified v2 work may be sealed;
12. restoring gateway configuration/journal continuity metadata and a database backup in isolation;
13. explaining the three OpenBao voters, why two are enough after one host loss, and why the adapter must never hold a fallback evidence private key;
14. showing Fabric outbox state and explaining why Fabric outage is non-blocking to LoRaWAN telemetry, then demonstrating the real adapter lease/commit/reconciliation and adapter-loss path for a full-feature handoff; if the implementation is unavailable, the handoff remains BLOCKED rather than being accepted with that feature omitted;
15. explaining that this three-Droplet build is a scale model of the future architecture: same HA relationships and technologies, deliberately tiny capacity, with no required feature removed to save resources.

The **full-feature handoff succeeds only when every required runtime demonstration produces the expected result**, including Fabric adapter execution/failover. A missing implementation can be documented as BLOCKED while other evidence is collected, but BLOCKED is not PASS.
