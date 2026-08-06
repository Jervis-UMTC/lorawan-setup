# Cloud LoRaWAN Deployment with Buffered Gateway Uplinks

Each procedure names the host that owns the command. Run gateway commands only on Gateway OS, application commands on the ChirpStack nodes, database commands on the PostgreSQL or pooler hosts, and etcd commands on the DCS members or an authorized administration host. Replace cloud placeholders only after the capacity, IP, DNS, certificate, and service-role plans define their source.

## Gateway data path

```text
LoRaWAN device
  -> RAK5146 + Gateway OS Base
  -> Concentratord
  -> MQTT Forwarder, QoS 1
  -> local persistent Mosquitto queue
  -> ssl://mqtt.<DOMAIN>:8883 with mutual TLS
  -> Layer-4 TCP pass-through, when used
  -> remote open-source MQTT broker
  -> ChirpStack application nodes
  -> PostgreSQL / Valkey / integrations
```

The local gateway broker is the outage buffer. Current ChirpStack Gateway Bridge is excluded because it no longer supports the Concentratord backend.

## Public boundary

Expose only:

```text
mqtt.<DOMAIN>:8883/TCP
chirpstack.<DOMAIN>:443/TCP
```

The remote broker validates the unique gateway certificate. A load balancer must use Layer-4 TCP pass-through so the broker receives the client certificate.

Do not publish MQTT 1883, UDP 1700, Gateway OS LuCI, SSH, databases, Valkey, or monitoring endpoints.

## Documents

| File | Purpose |
|---|---|
| [01-architecture-decisions-and-scope.md](01-architecture-decisions-and-scope.md) | Buffered gateway architecture and boundaries |
| [02-capacity-cost-and-ip-plan.md](02-capacity-cost-and-ip-plan.md) | Capacity, VPC, storage, and cost worksheet |
| [03-digitalocean-vpc-droplets-and-firewalls.md](03-digitalocean-vpc-droplets-and-firewalls.md) | VPC, MQTT endpoint, DNS, and firewalls |
| [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md) | Host security, MQTT PKI, DNS, and secrets |
| [05-raspberry-pi-4g-backhaul.md](05-raspberry-pi-4g-backhaul.md) | Gateway buffer, 4G, bridge, and outage behavior |
| [06-etcd-cluster.md](06-etcd-cluster.md) | etcd cluster operations |
| [07-spilo-patroni-postgresql-cluster.md](07-spilo-patroni-postgresql-cluster.md) | PostgreSQL HA and backups |
| [08-haproxy-and-pgbouncer.md](08-haproxy-and-pgbouncer.md) | Database routing and pooling |
| [09-mqtt-and-valkey.md](09-mqtt-and-valkey.md) | Local and remote MQTT availability and Valkey |
| [10-chirpstack-cloud-cluster.md](10-chirpstack-cloud-cluster.md) | ChirpStack nodes and region MQTT backends |
| [11-gateway-and-device-migration.md](11-gateway-and-device-migration.md) | Buffered gateway migration and devices |
| [12-backup-restore-and-disaster-recovery.md](12-backup-restore-and-disaster-recovery.md) | Backup and disaster recovery |
| [13-observability-alerting-and-logging.md](13-observability-alerting-and-logging.md) | Buffer, MQTT, application, and database monitoring |
| [14-failover-chaos-and-acceptance-testing.md](14-failover-chaos-and-acceptance-testing.md) | Buffer, broker, 4G, and acceptance tests |
| [15-operations-upgrades-and-scaling.md](15-operations-upgrades-and-scaling.md) | Gateway and platform upgrades |
| [16-troubleshooting.md](16-troubleshooting.md) | Layered diagnosis |
| [17-runbook-and-handoff-checklists.md](17-runbook-and-handoff-checklists.md) | Commissioning and incident runbook for certificate rotation, upgrades, and buffer incidents |

## Verify the production path

Complete the architecture guides in order, then test the path with real gateway traffic. A running cloud service or successful TCP health check does not prove buffer durability, certificate authorization, ChirpStack processing, or device operation.

Required acceptance:

- The local broker queue is finite, persistent, monitored, and restored from backup.
- A real WAN outage and gateway reboot preserve expected uplinks.
- Queue drain after recovery is measured.
- Duplicate QoS 1 delivery does not duplicate application rows.
- Stale downlink commands are not replayed.
- Remote mTLS and exact per-gateway ACL isolation pass.
- UDP Forwarder remains disabled.
