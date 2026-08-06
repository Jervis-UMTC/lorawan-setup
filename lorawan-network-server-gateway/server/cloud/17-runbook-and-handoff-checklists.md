# 17. Commissioning and Incident Runbook

Use this runbook after the detailed gateway and cloud guides have been completed. It verifies the live system in dependency order and provides focused procedures for certificate rotation, Gateway OS upgrades, and buffer incidents.

## 17.1 Keep the values needed to operate and recover the system

Store these non-secret values with the encrypted configuration and backup references:

| Value | Why it is needed |
|---|---|
| Environment, gateway count, and physical gateway references | Identifies the systems covered by the runbook |
| Gateway OS Base release, factory-image hash, and rollback location | Rebuilds a failed SD card with the tested image |
| RAK5146 variant, region, sub-band, antenna gain/loss, and Concentratord plan | Prevents an invalid RF configuration during restore |
| Gateway EUI and MQTT region prefix | Links Concentratord, certificates, topics, ACLs, and ChirpStack registration |
| MQTT Forwarder loopback endpoint, QoS, backend, and client ID | Confirms traffic cannot bypass the local buffer |
| Local Mosquitto version, configuration path, queue path, finite limits, autosave, and free-space reserve | Reproduces and monitors outage buffering |
| Remote MQTT FQDN/port and certificate fingerprint/expiry | Rebuilds and rotates the mutual-TLS bridge |
| Encrypted gateway, broker, database, and infrastructure backup locations | Recovers each independent failure domain |
| Most recent outage/reboot/drain, stale-downlink, gateway restore, broker failover, and database restore results | Shows which recovery claims have actually been tested |

Do not store passwords, private keys, AppKeys, NwkKeys, or live tokens in this table.

## 17.2 Verify the public and private network boundary

From an authorized administration host, inspect DNS, TLS, and the externally reachable ports. On each server and gateway, inspect local listeners and firewall rules.

Expected public endpoints:

```text
chirpstack.<DOMAIN>:443 -> UI/API reverse proxy or load balancer
mqtt.<DOMAIN>:8883      -> MQTT TLS broker or Layer-4 TCP pass-through
```

Healthy evidence:

- MQTT `1883` and Semtech UDP `1700` are not public;
- Gateway OS LuCI, SSH, and local Mosquitto are not internet-facing;
- gateway port `1883` binds only to `127.0.0.1`;
- PostgreSQL, Valkey, etcd, Patroni, PgBouncer, and monitoring ports remain private;
- the MQTT load balancer preserves the client certificate;
- an authenticated MQTT publish/subscribe health test passes.

An open TCP port without a certificate/ACL test proves only socket reachability. Any unexpected public listener must be removed or restricted before device commissioning.

## 17.3 Verify the gateway from hardware to cloud

1. Confirm the installed Raspberry Pi, RAK5146 frequency variant, Pi HAT, antenna band/gain, cable loss, and legal region match the retained configuration.
2. In Gateway OS, verify Concentratord initializes the radio and reports the expected stable Gateway EUI.
3. Verify UDP Forwarder has no server and no unsupported alternate packet-forwarder service owns the radio.
4. Verify MQTT Forwarder uses backend `concentratord`, Protobuf, QoS 1, a fixed client ID, and `tcp://127.0.0.1:1883`.
5. Verify local Mosquitto listens only on loopback and its queue path is persistent, writable, finite, and above the free-space reserve.
6. Verify the `cloud-uplink` bridge uses QoS 1 and a persistent session for event/state topics.
7. Verify the `cloud-downlink` bridge uses QoS 0 and a clean session for command topics.
8. On the remote broker, confirm both bridge client IDs authenticate with the certificate whose Common Name equals the Gateway EUI.
9. Test that the gateway can use only its own event/state/command topics and is denied access to another Gateway EUI.
10. Perform the WAN-outage, gateway-reboot, queue-drain, queue-limit, duplicate-handling, and stale-downlink tests.
11. Complete one real OTAA join, decoded uplink, and safe Class A downlink.

A healthy gateway keeps receiving packets and growing its local queue during a remote outage, then drains after recovery without duplicate application rows. A connected bridge with no ChirpStack last-seen update points to topic prefix, ACL, Protobuf, or region configuration rather than RF hardware.

## 17.4 Verify remote MQTT and ChirpStack

1. Verify the broker certificate SAN contains `mqtt.<DOMAIN>` and the public connection requires a trusted client certificate.
2. Confirm each gateway has a unique certificate and exact EUI ACL; ChirpStack and integrations use separate identities.
3. Confirm the CA private key is absent from runtime mounts and gateways.
4. Verify every enabled ChirpStack region uses the same MQTT topic prefix as Gateway OS.
5. Confirm no server-side Gateway Bridge is present in the active path.
6. Check PostgreSQL, PgBouncer, Valkey, and each ChirpStack application node with dependency-aware health checks.
7. Verify gateway last-seen freshness, one real application event, and the expected payload-codec output.
8. Verify Node-RED derives a stable event key and TimescaleDB uniqueness constraints produce one canonical record after a deliberate retry.

A broker login is not enough. Wrong region prefixes, read/write ACL direction, client key format, or application integration topics can leave the connection established while no usable device event is processed.

## 17.5 Rotate a gateway MQTT certificate

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

## 17.6 Upgrade Gateway OS

1. Read the target release notes and verify Raspberry Pi 4B, RAK5146, Concentratord, MQTT Forwarder, and required Mosquitto packages are supported.
2. Inspect the queue and drain it when possible.
3. Preserve the old factory image, encrypted Gateway OS archive, Mosquitto configuration/data, certificate bundle, and hashes.
4. Test the exact image and package feed on spare media or a spare gateway.
5. Restore configuration without changing the Gateway EUI or RF plan.
6. Verify persistent storage, finite queue limits, both bridges, Concentratord, MQTT Forwarder, and UDP disablement.
7. Run WAN-outage/reboot/drain, OTAA, uplink, payload-codec, and safe-downlink tests.
8. Deploy one canary gateway and keep the previous image and configuration until acceptance passes.

A service that starts with a changed UCI schema, volatile queue path, or missing package is not a successful upgrade. Restore the previous tested image on spare media rather than improvising on the only production card.

## 17.7 Respond to a growing or full gateway buffer

1. Confirm Concentratord and MQTT Forwarder are healthy and MQTT Forwarder still uses loopback QoS 1.
2. Inspect local Mosquitto logs, `mosquitto.db` size, configured message/byte limits, filesystem free space, and the free-space reserve.
3. Check DNS, default route, time, 4G registration, remote TCP `8883`, TLS hostname/chain, client-certificate validity, and broker ACL errors.
4. Restore the remote path without deleting `mosquitto.db` or bypassing the local broker.
5. Watch queue size and remote ChirpStack frame counters during drain.
6. Compare unique application records with buffered event identities to identify duplicates or confirmed loss.
7. Send a new safe downlink after recovery and confirm no command created during the outage is replayed.
8. If the outage exceeded the designed queue, identify the retained frame-counter range and update traffic, storage, outage, or alert assumptions before returning to normal operation.

Stop new non-essential changes when the queue is near its finite limit or the filesystem reserve is threatened. Deleting the persistence database hides evidence and destroys recoverable uplinks.

## 17.8 Stop conditions

Do not continue with a destructive or transmitting step when the target gateway/EUI is uncertain, the legal region or antenna path is unconfirmed, the only recoverable SD card or backup could be overwritten, the queue path is volatile, storage is near exhaustion, queue limits are unlimited, a CA private key may be exposed, management access may be lost, stale downlink replay is observed, or the required database/gateway rollback has not been tested.

Resolve the lowest failing layer first and repeat the affected acceptance test before resuming.

## 17.9 Handoff demonstration

The person receiving the system should be able to use the repository without relying on undocumented memory. Have them demonstrate:

1. locating the gateway, server, cloud, and integration procedures;
2. flashing and restoring Gateway OS to spare media;
3. identifying the Gateway EUI and confirmed RF plan;
4. checking Concentratord, MQTT Forwarder, local Mosquitto, remote MQTT, and ChirpStack in order;
5. explaining why current Gateway Bridge is not the Concentratord buffer;
6. sizing and inspecting the finite queue;
7. performing a WAN-outage/reboot/drain and stale-downlink test;
8. rotating and revoking a staging gateway certificate;
9. proving cross-gateway ACL denial and application deduplication;
10. completing a real uplink, codec check, and safe downlink;
11. restoring gateway configuration and a database backup in isolation.

The handoff succeeds when the demonstration produces the expected results and the receiver can explain what an abnormal result means and where to investigate next.
