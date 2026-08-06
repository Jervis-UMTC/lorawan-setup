# 3. DigitalOcean VPC, Droplets, Volumes, Load Balancer, and Firewalls

## 3.1 Resolve the provisioning inputs

Before creating resources, confirm the DigitalOcean team account uses MFA and role separation, quotas cover the planned nodes and volumes, the organization controls the DNS zone, named administrators have SSH public keys, and the selected region supports every required service. Choose a non-overlapping VPC range and a protected location for Terraform/OpenTofu state or equivalent provisioning records. Identify who can recover or remove the environment if the normal administrator is unavailable.

Do not use a personal account, a shared root password, or an API token embedded in a repository. Missing quota, DNS control, state storage, or recovery access must be resolved before provisioning because later resources depend on them.

## 3.2 Prefer infrastructure as code

Use Terraform, OpenTofu, or another reviewed tool for reproducibility. This guide shows discovery commands and control points, not a complete provider module.

Before automation, inspect the current CLI surface:

```bash
doctl version
doctl compute vpc --help
doctl compute droplet --help
doctl compute firewall --help
doctl compute load-balancer --help
```

Pin provider and module versions. Keep state encrypted and access-controlled.

## 3.3 Create the VPC first

Create the VPC before Droplets and managed databases so each resource is placed correctly at creation time.

Illustrative command after replacing placeholders and confirming current syntax:

```bash
doctl compute vpc create \
  --name <ENVIRONMENT>-lorawan \
  --region <DO_REGION> \
  --ip-range <VPC_CIDR>
```

Keep the returned VPC UUID with its range and region. Later Droplet, firewall, load-balancer, and recovery commands use this exact identifier; a VPC name alone is not sufficient.

**Stop here. Do not continue** if the CIDR overlaps another routed network or selected managed services are unavailable in the region.

## 3.4 Create cloud tags

Use stable tags for firewall and load-balancer targeting:

```text
lorawan:<ENVIRONMENT>
role:app
role:postgres
role:etcd
role:monitoring
```

Do not use a tag alone as authorization evidence; verify which Droplets currently carry it before applying firewall changes.

## 3.5 Create Droplets

Use a current supported LTS distribution and the exact approved image slug. Disable password login through cloud-init and provide named SSH keys.

Illustrative pattern:

```bash
doctl compute droplet create <HOSTNAME> \
  --region <DO_REGION> \
  --image <APPROVED_LTS_IMAGE_SLUG> \
  --size <APPROVED_SIZE_SLUG> \
  --vpc-uuid <VPC_UUID> \
  --ssh-keys <SSH_KEY_FINGERPRINTS> \
  --tag-names 'lorawan:<ENVIRONMENT>,role:<ROLE>' \
  --enable-monitoring \
  --wait
```

Create one node at a time. Keep its Droplet ID, private address, role tag, and recovery access path because later firewall rules, volume attachment, monitoring, and teardown use those values. Verify cloud-init and SSH before creating the next node.

For private-only Droplets, establish a bastion, provider console, or other approved recovery path before removing public networking.

## 3.6 Attach independent PostgreSQL volumes

For each database node:

1. create one independent block volume in the same region;
2. attach it only to the intended Droplet;
3. format it once with the approved filesystem;
4. mount by stable filesystem UUID;
5. create the Spilo data path with restrictive ownership;
6. test reboot persistence before PostgreSQL bootstrap.

Example discovery:

```bash
lsblk -o NAME,SIZE,FSTYPE,UUID,MOUNTPOINTS
sudo blkid
findmnt
```

**Stop here. Do not format a device** until its provider volume ID, Linux device, target host, and lack of existing data are independently confirmed.

## 3.7 Regional Load Balancer listeners

Create only approved public listeners:

| Public listener | Backend | Purpose |
|---|---|---|
| HTTPS/443 on `chirpstack.<DOMAIN>` | application reverse proxy | ChirpStack UI/API |
| TCP/8883 on `mqtt.<DOMAIN>` | MQTT broker TLS listener | Gateway OS MQTT with mutual TLS |

When a load balancer fronts MQTT, use Layer-4 TCP pass-through so the broker receives and validates each gateway client certificate. Test the load balancer idle timeout and long-lived MQTT behavior.

Do not publish MQTT 1883, Semtech UDP, PostgreSQL, PgBouncer, Patroni REST, etcd, Valkey, monitoring endpoints, Gateway OS LuCI, or gateway SSH.

A successful TCP health check proves only that a socket opens. Add an authenticated synthetic MQTT publish/subscribe test and verify broker certificate, client certificate, ACL, and real gateway flow.

## 3.8 Cloud Firewall matrix

Apply both DigitalOcean Cloud Firewalls and host firewalls. Keep the two rule sets consistent.

### Application nodes

| Direction | Protocol/port | Source/destination | Reason |
|---|---|---|---|
| Inbound | TCP 443 | Regional Load Balancer only | UI/API |
| Inbound | TCP 8883 | Regional Load Balancer only, when broker runs here | MQTT TLS |
| Inbound | TCP 22 | Bastion or management CIDR only | SSH |
| Inbound | metrics ports | Monitoring subnet only | Metrics |
| Outbound | TCP 5432 | PostgreSQL private IPs | HAProxy database traffic |
| Outbound | TCP 8008 | PostgreSQL private IPs | Patroni health checks |
| Outbound | TLS | Managed Valkey private endpoint | ChirpStack state |
| Outbound | TCP 443 | Approved package/object endpoints | Updates and backups |

### PostgreSQL nodes

| Direction | Protocol/port | Source | Reason |
|---|---|---|---|
| Inbound | TCP 5432 | App nodes and PostgreSQL nodes | Client and replication traffic |
| Inbound | TCP 8008 | App nodes, DB nodes, monitoring, admin | Patroni REST health/control |
| Inbound | TCP 2379 | DB nodes/Patroni clients | etcd client API when co-located |
| Inbound | TCP 2380 | etcd members only | etcd peer traffic |
| Inbound | TCP 22 | Bastion or management CIDR | SSH |
| Inbound | metrics ports | Monitoring subnet | Monitoring |

### Dedicated etcd nodes

Allow 2379 only from Patroni and authorized administration clients; allow 2380 only among exact etcd members. Never expose either port publicly.

## 3.9 Host firewall verification

On every host:

```bash
sudo ss -lntup
sudo nft list ruleset
sudo ufw status verbose 2>/dev/null || true
```

Compare listeners with the firewall matrix. A listener on `0.0.0.0` is not acceptable merely because a Cloud Firewall exists.

## 3.10 DNS plan

Suggested records:

```text
chirpstack.<DOMAIN>  -> HTTPS application load balancer
mqtt.<DOMAIN>        -> Layer-4 TCP pass-through MQTT load balancer or broker public address
```

The broker certificate SAN must include `mqtt.<DOMAIN>`. Do not create a public `lns.<DOMAIN>` endpoint for this Gateway OS MQTT architecture.

Internal names should resolve only inside the approved management/VPC resolver:

```text
app-01.internal.<DOMAIN>
db-01.internal.<DOMAIN>
dcs-01.internal.<DOMAIN>
```

Use low TTL only during controlled migration. Raise it after stability is proven. Do not publish private IP records in public DNS unless the organization explicitly accepts that metadata exposure.

## 3.11 Provisioning validation

Before installing services, verify:

```bash
ip -br address
ip route
getent hosts <PEER_INTERNAL_FQDN>
ping -c 3 <PEER_PRIVATE_IP>
timedatectl
curl -fsS http://169.254.169.254/metadata/v1/id
```

Keep a sanitized provisioning result that identifies each host, private address, mounted volume UUID, and tested recovery path without API tokens or secret metadata. Prove VPC connectivity, DNS, NTP, volume mounts, console recovery, SSH key access, and denied public service ports. An unexpected public listener or missing persistent mount must be corrected before service installation.

Next: [04-host-hardening-dns-pki-and-secrets.md](04-host-hardening-dns-pki-and-secrets.md)
