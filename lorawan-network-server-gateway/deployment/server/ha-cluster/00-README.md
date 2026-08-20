# Server Component Setup Reference

This folder contains **full-deployment component references**. It is not the dissertation testing path.

Use:

- [../../../test/00-README.md](../../../test/00-README.md) for the barebones dissertation testing track.
- [../00-README.md](../00-README.md) for the complete architecture.

The testing path deliberately skips the HA-only manuals below.

## Full-deployment component manuals

| # | Manual | Purpose |
|---:|---|---|
| 1 | [01-create-server-vm.md](01-create-server-vm.md) | Prepare a full-deployment Ubuntu/Docker environment |
| 2 | [02-docker-topology-and-network.md](02-docker-topology-and-network.md) | Full-stack networks, volumes, pins, and reference limits |
| 3 | [03-deploy-etcd-quorum.md](03-deploy-etcd-quorum.md) | Three-member Patroni DCS |
| 4 | [04-deploy-spilo-patroni-postgresql.md](04-deploy-spilo-patroni-postgresql.md) | Three PostgreSQL members |
| 5 | [05-verify-postgresql-ha.md](05-verify-postgresql-ha.md) | HA/failover verification |
| 6 | [06-deploy-haproxy.md](06-deploy-haproxy.md) | Route to the Patroni leader |
| 7 | [07-deploy-pgbouncer.md](07-deploy-pgbouncer.md) | Connection pooling |
| 8 | [08-deploy-mosquitto.md](08-deploy-mosquitto.md) | MQTT broker |
| 9 | [09-deploy-valkey.md](09-deploy-valkey.md) | ChirpStack cache dependency |
| 10 | [10-deploy-chirpstack.md](10-deploy-chirpstack.md) | Full-deployment ChirpStack path through PgBouncer |
| 11 | [11-secure-gateway-mqtt.md](11-secure-gateway-mqtt.md) | Gateway MQTT mutual TLS |
| 12 | [12-provision-gateway-mqtt-identity.md](12-provision-gateway-mqtt-identity.md) | Per-gateway certificate/ACL |
| 13 | [13-failure-recovery-tests.md](13-failure-recovery-tests.md) | Infrastructure failure/recovery |
| 14 | [14-backup-and-restore.md](14-backup-and-restore.md) | Backup/restore |

Telemetry references are under `../data/`; OpenBao/Fabric references are under `../fabric-attestation/`.

Do not deploy etcd, Patroni, HAProxy, PgBouncer, Grafana, or gateway-evidence v2 services into the dissertation test VM unless the methodology is explicitly changed to measure them.
