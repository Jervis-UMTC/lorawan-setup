# 4. Host Hardening, DNS, PKI, and Secrets

For the **step-by-step execution record on newly provisioned hosts**, use [04a-host-security-hardening-execution-runbook.md](04a-host-security-hardening-execution-runbook.md). That runbook records what was actually executed, why, the verification result, deviations from the supplied Ubuntu hardening document, and the explicitly excluded yellow-highlighted web-server section.

## 4.1 Baseline principles

- Use a supported LTS operating-system image and keep the exact cloud-image identifier for rebuild and rollback. This POC pins **Ubuntu Server 24.04 LTS x64 (Noble)** using the DigitalOcean `ubuntu-24-04-x64` image on `ha-01/02/03`. Do not record only "Ubuntu LTS"; the exact release matters for package repositories and repeatable rebuilds.
- Use named operator accounts, SSH keys, and least privilege.
- Keep database, etcd, MQTT, and Patroni control ports on private interfaces.
- Use a dedicated service account for each daemon where practical.
- Store secrets outside Git and outside shell history.
- Use mutual TLS for etcd and gateway-facing MQTT. When the gateway-evidence ingest service is deployed, use mutual TLS there too with a separate-purpose per-gateway upload identity when practical. Use TLS with hostname verification for PostgreSQL, internal service connections where configured, and public HTTP.
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
timedatectl show -p NTPSynchronized --value
chronyc tracking 2>/dev/null || true
chronyc sources -v 2>/dev/null || true
```

Do not start etcd, Patroni, OpenBao, or certificate-sensitive commissioning while `NTPSynchronized` is `no`. Ubuntu may use a time-sync implementation other than `chrony`, which is why the `timedatectl` synchronization state is the required gate and the `chronyc` commands are supplemental when that client exists.

Alert on clock offset. Do not manually step time on a database/quorum node without understanding PostgreSQL, etcd lease, OpenBao, and certificate effects.

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

### OpenBao and swap

A small host swap file may be useful as an emergency cushion for other processes, but **OpenBao must not be allowed to page secrets into ordinary unencrypted swap**. This is a security boundary, not a performance tweak.

Use the control that matches the OpenBao runtime selected later:

```text
native/systemd OpenBao -> verify the service has MemorySwapMax=0
containerized OpenBao  -> configure the equivalent of --memory-swappiness=0
alternative            -> use an explicitly reviewed encrypted-swap design
```

Do not use swap to make an undersized OpenBao node appear healthy. Sustained host swapping still fails the 2-GiB sizing experiment.

## 4.6 Package and container runtime trust

- Use official distribution repositories or approved vendor repositories.
- Verify repository signing keys and fingerprints through an independent source.
- Pin container images by immutable digest.
- Keep the software bill of materials and vulnerability-scan result with each immutable image digest so the deployed artifact can be traced and replaced.
- Do not mount the container runtime socket into application containers.
- Do not run a container privileged unless the exact capability need is documented.

### Install Docker Engine on the plain Ubuntu Server 24.04 LTS hosts

The DigitalOcean OS image is intentionally **not** a Docker Marketplace image, so install Docker Engine before any manual that runs `docker compose`. Docker's current Ubuntu instructions support Ubuntu Noble 24.04 LTS.

First prove that the host is the expected release. Run on **each** Droplet:

```bash
. /etc/os-release
printf 'ID=%s VERSION_ID=%s CODENAME=%s ARCH=%s\n' \
  "$ID" "$VERSION_ID" "${UBUNTU_CODENAME:-$VERSION_CODENAME}" "$(dpkg --print-architecture)"

test "$ID" = ubuntu
test "$VERSION_ID" = 24.04
test "${UBUNTU_CODENAME:-$VERSION_CODENAME}" = noble
test "$(dpkg --print-architecture)" = amd64
```

**Stop here** if any test fails. Do not adapt the repository command to a different Ubuntu release on the fly; either rebuild the mismatched Droplet or deliberately revise and revalidate the whole three-host baseline.

Before installing Docker, inspect the package names Docker currently documents as conflicts with Docker Engine from its official repository:

```bash
dpkg --get-selections \
  docker.io docker-compose docker-compose-v2 docker-doc docker-buildx \
  podman-docker containerd runc \
  2>/dev/null || true
```

A fresh POC host should not contain an existing container workload. If any conflicting package is installed, first verify that `/var/lib/docker`, `/var/lib/containerd`, and the running process list do not contain an unknown workload. Only on a confirmed fresh host, remove the conflicts using the current Docker-documented package list:

Build the removal list first so an empty result does not turn into an ambiguous `apt remove` command:

```bash
CONFLICTING_DOCKER_PACKAGES="$(dpkg --get-selections \
  docker.io docker-compose docker-compose-v2 docker-doc docker-buildx \
  podman-docker containerd runc 2>/dev/null \
  | awk '$2 == "install" {print $1}')"

printf 'conflicting installed packages:\n%s\n' \
  "${CONFLICTING_DOCKER_PACKAGES:-<none>}"
```

If the list is non-empty **and this is confirmed to be a fresh host with no workload**, remove exactly that list:

```bash
if [ -n "$CONFLICTING_DOCKER_PACKAGES" ]; then
  sudo apt remove -y $CONFLICTING_DOCKER_PACKAGES
fi
```

An empty list is normal on a plain image. Do **not** delete `/var/lib/docker` or `/var/lib/containerd` as part of this procedure, and do not run the removal block on a host whose existing container state has not been identified.

Configure Docker's official **Ubuntu** repository:

```bash
sudo apt update
sudo apt install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
apt list --all-versions docker-ce 2>/dev/null | head -n 20
```

Select and record the **approved Docker Engine version string** in the software worksheet. Do not copy a Docker version number from this manual because repository availability changes over time. Then install that reviewed engine version with Docker's current Ubuntu package set:

```bash
DOCKER_VERSION_STRING='<APPROVED_DOCKER_VERSION_STRING>'

sudo apt install -y \
  docker-ce="$DOCKER_VERSION_STRING" \
  docker-ce-cli="$DOCKER_VERSION_STRING" \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

Verify before deploying any application container:

```bash
sudo systemctl is-enabled docker
sudo systemctl is-active docker
sudo docker version
sudo docker compose version
dpkg-query -W \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker info --format '{{.ServerVersion}} {{.LoggingDriver}}'
```

Record the Docker Engine, Compose plugin, containerd, package versions, and package source in [02-capacity-cost-and-ip-plan.md](02-capacity-cost-and-ip-plan.md). Keep all three hosts on the same reviewed package baseline during initial commissioning.

### Bound container logs before creating the stack

Docker's default `json-file` driver does not rotate logs unless configured. On these 50-GiB POC disks, unbounded container logs are an avoidable failure mode.

For a new host, use Docker's rotating `local` logging driver as the default:

```bash
sudo install -d -m 0755 /etc/docker
```

If `/etc/docker/daemon.json` already exists, **stop and merge this setting with the existing reviewed JSON instead of overwriting it**. On a new empty host, create:

```bash
sudo tee /etc/docker/daemon.json >/dev/null <<'JSON'
{
  "log-driver": "local"
}
JSON

sudo systemctl restart docker
sudo docker info --format '{{.LoggingDriver}}'
```

Expected result:

```text
local
```

This default applies to newly created containers. If containers existed before the change, recreate them only through their normal deployment procedure so they inherit the reviewed logging driver.

### Docker and firewall boundary

Do not assume a host UFW rule alone protects ports published by Docker. Docker manages its own packet-filter rules. This cloud POC therefore keeps the **DigitalOcean Cloud Firewall**, explicit private/loopback/anchor IP binds, and `ss -lntup` listener verification as mandatory controls. If additional host packet filtering for Docker traffic is required, implement it through a reviewed Docker-compatible rule path rather than an ad-hoc ruleset.

Spilo maintainers encourage users to build reviewed images from source because public image releases are not regular. Build in CI, scan, sign, publish to an approved registry, and pin the digest.

## 4.7 PKI hierarchy

The POC is small, but the certificate **roles and names must match the future deployment shape**. Reduce certificate count only when two functions genuinely share the same trust boundary; do not disable TLS or hostname verification to save setup time.

Use separate trust purposes where operationally practical:

```text
Public CA
  -> chirpstack.<DOMAIN>

Gateway MQTT CA
  -> mqtt.<DOMAIN> broker server certificates
  -> unique clientAuth certificate per gateway
  -> separate ChirpStack and integration client certificates

Gateway Evidence CA or separately constrained PKI purpose
  -> evidence.<DOMAIN> HTTPS server certificate
  -> unique evidence-upload client identity per gateway
  -> no MQTT publish authorization implied by this certificate

Internal etcd CA
  -> unique peer/client certificate per etcd member
  -> Patroni etcd client certificate

Internal PostgreSQL CA
  -> unique server certificate per DB node
  -> PgBouncer server certificates
  -> optional application client certificates

Internal Valkey CA
  -> unique Valkey/Sentinel certificate per node

Internal OpenBao CA
  -> unique OpenBao server certificate per node
```

The gateway MQTT certificate Common Name equals the 16-hex Gateway ID when the broker maps certificate identity to ACL username. The evidence-upload identity must also map unambiguously to exactly one Gateway EUI, but it should use a separate key/purpose from MQTT when operationally practical. Reuse one key across MQTT and evidence upload only under an explicit reviewed PKI decision. Do not reuse one private key across gateways or nodes. Server certificates must include the exact DNS names and private IPs used by clients in Subject Alternative Names.

### 4.7A Certificate/SAN matrix for this POC

Issue or obtain these **before the consuming service is started**:

| Service | Where | Name/SAN that clients verify | Why |
|---|---|---|---|
| ChirpStack HTTPS | HAProxy `ha-01/02` anchor listeners | `chirpstack.<DOMAIN>` | Browser/API TLS through the Reserved IPv4 after ownership moves between app hosts |
| Mosquitto-1 | `ha-01` | `mqtt.<DOMAIN>`, `mqtt-ha.internal.<DOMAIN>`, node private name/IP | Same broker cert works through public and internal HAProxy TCP pass-through |
| Mosquitto-2 | `ha-02` | `mqtt.<DOMAIN>`, `mqtt-ha.internal.<DOMAIN>`, node private name/IP | Backup broker presents the same service names |
| PgBouncer | `ha-01/02/03` | `pgbouncer.internal.<DOMAIN>`, node private name/IP | Local database clients use one stable logical name |
| PostgreSQL | `ha-01/02/03` | `postgres-ha.internal.<DOMAIN>`, node private name/IP | PgBouncer/HAProxy can verify any promoted primary |
| Valkey | `ha-01/02/03` | `valkey-ha.internal.<DOMAIN>`, node private name/IP | HAProxy/ChirpStack verify any promoted primary |
| OpenBao | `ha-01/02/03` | `openbao-kms.internal.<DOMAIN>`, node private name/IP | Either active or standby can serve the stable KMS path |
| etcd | `ha-01/02/03` | each member's private DNS/IP | Peer/client mTLS must identify the actual member |

Client identities:

```text
physical gateway MQTT client -> unique cert, CN = Gateway EUI
ChirpStack MQTT client(s)     -> workload identity, never a gateway identity
Node-RED MQTT client          -> read-only application-event identity
Fabric adapter-1/2            -> separate OpenBao workload identities where practical
```

**Stop here. Do not continue** if a client will connect using a name absent from the server certificate SAN. Fix the certificate or the service name; do not fall back to `sslmode=require`, disabled hostname checks, or `verify none` as the permanent solution.

## 4.8 Certificate file layout

Example:

```text
/etc/lorawan-pki/
  public/
  etcd/
  postgres/
  pgbouncer/
  mqtt/
  valkey/
  openbao/
  gateway-ca/
  gateway-evidence/   # when the evidence-ingest service is deployed
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
- when gateway evidence is enabled, unique gateway evidence-upload client identities/private keys and lifecycle records;
- evidence-ingest service credential, protected evidence-store credential, and verifier database/object-store identities;
- ChirpStack token secret and API credentials;
- Valkey password or certificate bundle;
- object-storage access key scoped to the backup bucket **only when the later WAL/object-storage backup profile is enabled**; it is not required for the minimal HA POC;
- DigitalOcean API token used by automation, including the dedicated public-ingress Reserved-IP failover identity on `ha-01/02`;
- alerting/webhook credentials;
- OpenBao initialization/recovery material and unseal or reviewed auto-unseal material, stored independently from the running nodes;
- separate least-privilege OpenBao workload identities for Fabric adapter-1 and Fabric adapter-2;
- Fabric Gateway CA certificate, MSP ID, channel/chaincode metadata, and a protected client identity for each adapter worker where the Fabric team's policy supports separate identities;
- Fabric adapter database credentials limited to the telemetry/outbox permissions defined by the integration manual.

Keep gateway-evidence verifier credentials intentionally separate from OpenBao Transit sign authorization and the Fabric client private key. The verifier decides whether source lineage is valid; it must not also own the evidence-signing capability. Likewise, do not copy one Fabric client private key or one long-lived OpenBao adapter credential across both adapter hosts unless the external Fabric/OpenBao identity design explicitly requires and approves that sharing; separate workload identity gives clearer revocation and audit evidence.

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

# Also test evidence.<DOMAIN>:443 separately once that mTLS service exists.
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
- logs contain no live secret during a sanitized test;
- when gateway evidence is deployed, one unauthorized/unknown gateway client is rejected by the evidence API, one authorized gateway identity maps only to its own Gateway EUI, and the verifier cannot use OpenBao/Fabric signing credentials.

Next: [05-raspberry-pi-4g-backhaul.md](05-raspberry-pi-4g-backhaul.md)
