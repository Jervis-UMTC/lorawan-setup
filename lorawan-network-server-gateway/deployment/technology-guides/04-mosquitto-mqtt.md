# Mosquitto MQTT — Operator Manual

## What this technology does

Mosquitto is used at two separate boundaries:

1. **Gateway-01 local broker** — loopback-only persistent store-and-forward buffer between MQTT Forwarder and the cloud.
2. **Cloud brokers on ULC-01/ULC-02** — preferred/backup MQTT service with separate gateway, ChirpStack, Node-RED, and evidence identities/listeners.

The cloud pair is **not** a replicated live-session cluster. Do not restore round-robin session routing.

## Current port ownership

```text
Gateway-01 local Mosquitto:                   127.0.0.1:1883
Public gateway MQTT via HAProxy:              :8883 on ingress candidate
Cloud Mosquitto gateway-facing TLS backend:   :8884
Cloud Mosquitto ChirpStack workload TLS:      :8885
Cloud Mosquitto Node-RED mTLS:                :8886
HAProxy ChirpStack MQTT service:               :18883
HAProxy Node-RED MQTT service:                 :18884
```

The exact bind address matters. A listener on the wrong interface can be both a security and routing defect.

# Part A — Gateway local broker

## Step A1 — Verify process and loopback listener

Run on Gateway-01:

```sh
ps w | grep '[m]osquitto'
ss -lntp 2>/dev/null | grep ':1883' || netstat -lntp | grep ':1883'
```

**PASS means:** Mosquitto is running and `1883` is bound to `127.0.0.1`, not `0.0.0.0`, LAN, or WAN.

## Step A2 — Verify persistence/queue limits without exposing secrets

```sh
grep -E '^(persistence|persistence_location|persistence_file|autosave_interval|max_queued_messages|max_queued_bytes|listener|protocol|allow_anonymous|include_dir)' /etc/mosquitto/mosquitto.conf
```

Expected commissioned pattern includes persistence, finite message/byte limits, and a loopback listener. Do not make an unlimited queue on an SD card.

## Step A3 — Verify cloud bridge metadata

```sh
grep -E '^(connection |address |remote_clientid|cleansession|bridge_cafile|bridge_certfile|bridge_keyfile|bridge_insecure|topic )' /etc/mosquitto/conf.d/bridge.conf
```

**PASS means:**

- bridge target is the commissioned cloud MQTT service on `8883`;
- CA/cert/key paths are configured;
- `bridge_insecure` is false;
- uplink/event/state traffic uses the intended outgoing QoS/session behavior;
- command/downlink traffic is inbound under the exact gateway EUI hierarchy.

Never `cat` the private key.

## Step A4 — Verify MQTT Forwarder publishes locally

In one gateway shell:

```sh
mosquitto_sub -h 127.0.0.1 -p 1883 -t 'as923/gateway/0016c001f139a1cb/event/#' -v
```

Generate one real approved sensor uplink.

**PASS means:** a message arrives under the correct AS923/EUI topic.

If nothing arrives, the failure is before the WAN bridge. Diagnose RAK5146/Concentratord/MQTT Forwarder/local listener first.

## Step A5 — Verify the bridge is connected

```sh
logread | grep -Ei 'mosquitto|bridge|connected|connack|tls|certificate' | tail -n 100
ss -tnp 2>/dev/null | grep ':8883' || netstat -tnp 2>/dev/null | grep ':8883' || true
```

**PASS means:** the bridge maintains an authenticated TLS/MQTT session without rapid reconnect/authentication failure.

# Part B — Cloud brokers

## Step B1 — Discover the actual service name on each broker host

Run on ULC-01 and ULC-02:

```bash
for s in mosquitto mosquitto-1 mosquitto-2 mosquitto-3; do
  sudo systemctl is-active "$s" >/dev/null 2>&1 && echo "$s"
done
```

Use the service name returned by the host. Do not assume an old unit name.

## Step B2 — Check listeners

```bash
sudo ss -lntp | grep -E ':(8884|8885|8886)\b' || true
```

Compare the actual bind addresses with the cloud runbook. A missing listener is not fixed by restarting ChirpStack.

## Step B3 — Check bounded logs

Replace `<SERVICE>` with the service name discovered in B1:

```bash
sudo journalctl -u <SERVICE> --since=-15min --no-pager | tail -n 120
```

Look for client-certificate, username/ACL, bridge, listener, or socket errors. Do not use an unbounded journal dump during routine diagnosis.

## Step B4 — Verify gateway mTLS identity behavior

The commissioned gateway certificate identity is the exact EUI `0016c001f139a1cb`, and the gateway ACL is limited to its own `as923/gateway/0016c001f139a1cb/...` hierarchy.

Use the protected test/commissioning certificate path defined by the MQTT runbook. A correct test proves:

1. trusted gateway certificate can connect;
2. it can publish only its allowed event/state hierarchy;
3. it can subscribe only to its command hierarchy;
4. a client with no certificate is rejected;
5. unrelated topic access is rejected.

Do not loosen ACLs just to make a test utility connect.

## Step B5 — Verify consumers separately from publishers

When application data is missing, prove both sides:

```text
publisher reached broker?
subscriber connected/subscribed?
message on exact expected topic?
consumer processed that message?
```

A quiet container stdout log does not prove MQTT traffic is absent. Subscribe with an authorized diagnostic identity or inspect broker/session evidence.

## Preferred/backup rule

The cloud brokers provide service failover, not session replication. Normal topology is preferred Mosquitto plus backup. If the preferred broker fails, clients reconnect through the approved HA path; when it recovers, do not create rapid round-robin switching.

## Safe change procedure

1. identify the exact listener/workload affected;
2. copy the current configuration and ACL to protected rollback storage;
3. validate file ownership/permissions;
4. change one broker first when possible;
5. validate Mosquitto configuration before service restart using the method supported by the installed package;
6. restart/reload only the broker being changed;
7. verify listeners and intended client identity;
8. verify unauthorized/no-cert rejection;
9. verify real gateway/ChirpStack/Node-RED flow;
10. only then apply the same change to the second broker.

Do not simultaneously restart both cloud brokers for a normal configuration edit.

## Common failure map

| Symptom | First check |
|---|---|
| Local gateway publish fails | Gateway local broker/Forwarder |
| Local works, bridge disconnected | LTE/DNS/TLS/client cert/cloud `8883` path |
| TLS succeeds, MQTT authorization fails | CN/username/ACL/topic |
| Cloud receives gateway event, ChirpStack does not | ChirpStack workload listener/routing/subscription |
| Node-RED misses events but ChirpStack works | Node-RED `18884/8886` path and subscription |
| Duplicate app rows after reconnect | downstream idempotency, not weaker MQTT delivery |

## Backup/recovery rules

- Gateway `mosquitto.db` is an availability queue, not immutable evidence.
- Never delete it during a transient outage merely to clear an error.
- Preserve broker config, ACLs, CA/cert/key paths, and persistence state before replacement.
- If restoring cloud brokers, restore intended preferred/backup topology; do not claim broker-session replication.

## Completion checklist

Gateway side:

- local broker running;
- `127.0.0.1:1883` only;
- persistence/finite limits present;
- real local event observed;
- TLS bridge established.

Cloud side:

- expected broker services active;
- correct workload listeners bound;
- gateway mTLS/ACL behavior correct;
- preferred/backup behavior preserved;
- one real event reaches the intended consumer.

## Complete setup and recovery companion

Start with [MQTT commissioned installation, mTLS identities, ACL, HA and recovery](MQTT-INSTALLATION-SECURITY-RECOVERY.md). This consolidates the actual two systemd cloud brokers, gateway loopback store-and-forward and protected bridge settings; older Docker/lab examples are historical, not the deployed configuration.

## Detailed runbooks

- [`../gateway/setup/04-configure-local-mqtt-buffer.md`](../gateway/setup/04-configure-local-mqtt-buffer.md)
- [`../gateway/setup/05-configure-mqtt-forwarder.md`](../gateway/setup/05-configure-mqtt-forwarder.md)
- [`../server/cloud-production/08-mqtt-and-valkey.md`](../server/cloud-production/08-mqtt-and-valkey.md)
- [`../server/cloud-production/14-observability-alerting-and-logging.md`](../server/cloud-production/14-observability-alerting-and-logging.md)
- [`../gateway/operations/05-troubleshooting.md`](../gateway/operations/05-troubleshooting.md)