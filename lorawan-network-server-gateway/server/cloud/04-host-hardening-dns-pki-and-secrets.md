# 4. Host Hardening, DNS, PKI, and Secrets

## 4.1 Baseline principles

- Use a supported LTS operating system and keep the exact cloud-image identifier for rebuild and rollback.
- Use named operator accounts, SSH keys, and least privilege.
- Keep database, etcd, MQTT, and Patroni control ports on private interfaces.
- Use a dedicated service account for each daemon where practical.
- Store secrets outside Git and outside shell history.
- Use mutual TLS for etcd and gateway-facing MQTT; use TLS with hostname verification for PostgreSQL, internal service connections where configured, and public HTTP.
- Apply updates through tested rolling procedures, not unattended major upgrades.

## 4.2 Initial host inspection

Run on every new host:

```bash
hostnamectl
uname -a
cat /etc/os-release
ip -br address
ip route
lsblk -f
findmnt
ss -lntup
systemctl --failed
journalctl -p warning -b --no-pager
```

Resolve unexpected listeners, failed units, duplicate addresses, or unmounted data volumes before installing the stack.

## 4.3 Operator access

Create a named operator and install an approved key through the cloud provisioning process. Confirm a second session works before changing SSH.

Back up and validate:

```bash
sudo cp -pn /etc/ssh/sshd_config /etc/ssh/sshd_config.before-lorawan-cloud
sudoedit /etc/ssh/sshd_config
sudo sshd -t
sudo systemctl reload ssh
```

Typical policy decisions:

```text
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
AllowGroups <APPROVED_SSH_GROUP>
```

Preserve distribution include files and organization policy. Keep provider-console recovery available.

## 4.4 Time synchronization

Accurate time is required for TLS, logs, database recovery, and LoRaWAN event interpretation.

```bash
timedatectl status
chronyc tracking 2>/dev/null || true
chronyc sources -v 2>/dev/null || true
```

Alert on clock offset. Do not manually step time on a production database node without understanding PostgreSQL, etcd lease, and certificate effects.

## 4.5 Kernel and resource limits

Review the limits below and change only values supported by measured demand. Keep each non-default value with the workload evidence that required it:

```text
nofile limits for MQTT, HAProxy, PgBouncer, and PostgreSQL
vm.overcommit_memory policy
TCP listen and connection tracking capacity
filesystem mount options
transparent huge pages policy for PostgreSQL
swap policy
OOM behavior and systemd resource controls
```

Do not copy generic sysctl bundles. Apply one reviewed setting at a time and compare before/after behavior.

## 4.6 Package and container runtime trust

- Use official distribution repositories or approved vendor repositories.
- Verify repository signing keys and fingerprints through an independent source.
- Pin container images by immutable digest.
- Keep the software bill of materials and vulnerability-scan result with each immutable image digest so the deployed artifact can be traced and replaced.
- Do not mount the container runtime socket into application containers.
- Do not run a container privileged unless the exact capability need is documented.

Spilo maintainers encourage users to build reviewed images from source because public image releases are not regular. Build in CI, scan, sign, publish to an approved registry, and pin the digest.

## 4.7 PKI hierarchy

Use separate trust purposes where operationally practical:

```text
Public CA
  -> chirpstack.<DOMAIN>

Gateway MQTT CA
  -> mqtt.<DOMAIN> broker server certificates
  -> unique clientAuth certificate per gateway
  -> separate ChirpStack and integration client certificates

Internal etcd CA
  -> unique peer/client certificate per etcd member
  -> Patroni etcd client certificate

Internal PostgreSQL CA
  -> unique server certificate per DB node
  -> optional application client certificates
```

The gateway MQTT certificate Common Name equals the 16-hex Gateway ID when the broker maps certificate identity to ACL username. Do not reuse one private key across gateways or nodes. Server certificates must include the exact DNS names and private IPs used by clients in Subject Alternative Names.

## 4.8 Certificate file layout

Example:

```text
/etc/lorawan-pki/
  public/
  etcd/
  postgres/
  mqtt/
  gateway-ca/
```

Recommended permissions:

```bash
sudo install -d -m 750 -o root -g <SERVICE_GROUP> /etc/lorawan-pki/<PURPOSE>
sudo install -m 640 -o root -g <SERVICE_GROUP> <CERT_FILE> /etc/lorawan-pki/<PURPOSE>/
sudo install -m 640 -o root -g <SERVICE_GROUP> <KEY_FILE> /etc/lorawan-pki/<PURPOSE>/
```

Some services require a different owner. Verify the effective service user and never loosen a private key to world-readable as a shortcut.

## 4.9 Secret inventory

At minimum, manage these independently:

- PostgreSQL superuser, replication, rewind, ChirpStack, backup, and monitoring credentials;
- PgBouncer authentication query or auth-file credential;
- etcd client and peer private keys;
- private MQTT broker administration, ChirpStack, Node-RED, and monitoring identities;
- unique Gateway OS MQTT client private keys and certificate lifecycle records;
- ChirpStack token secret and API credentials;
- Valkey password or certificate bundle;
- object-storage access key scoped to the backup bucket;
- DigitalOcean API token used by automation;
- alerting/webhook credentials.

For every secret, keep its purpose, consumers, protected storage reference, rotation or expiry trigger, and emergency revocation procedure. Do not place the secret value in the inventory.

## 4.10 Environment files

Use root-owned files outside the repository:

```bash
sudo install -d -m 750 /etc/lorawan-cloud
sudo install -m 600 /dev/null /etc/lorawan-cloud/<SERVICE>.env
sudoedit /etc/lorawan-cloud/<SERVICE>.env
```

Before using a rendered Compose configuration, remember that `docker compose config` may print expanded secret values. Prefer `docker compose config --quiet` for syntax validation, and redirect any necessary rendered output to a protected temporary file that is removed immediately.

## 4.11 DNS and certificate validation

```bash
getent ahosts <SERVICE_FQDN>
openssl s_client -connect <SERVICE_FQDN>:<PORT> -servername <SERVICE_FQDN> -showcerts </dev/null
```

Verify chain, hostname, expiry, key usage, and issuer. Automate expiry alerts with enough time for rollback.

## 4.12 Audit and logging hygiene

- Do not log AppKey, NwkKey, PostgreSQL passwords, private keys, MQTT passwords, API tokens, or complete connection strings.
- Redact authorization headers and database DSNs.
- Restrict journal and log-aggregation access.
- Define retention and legal requirements.
- Test that debug mode is off after commissioning.

## 4.13 Hardening acceptance

Complete only when:

- SSH password and root login policy is verified without lockout;
- public listeners match the approved matrix;
- every private key has a named owner and restrictive mode;
- deployed image digests, package versions, and sources can be identified;
- certificate expiry monitoring is active;
- secrets can be rotated without rebuilding the whole environment;
- logs contain no live secret during a sanitized test.

Next: [05-raspberry-pi-4g-backhaul.md](05-raspberry-pi-4g-backhaul.md)
