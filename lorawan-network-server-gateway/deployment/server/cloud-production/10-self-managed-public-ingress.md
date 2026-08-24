# 10. Self-Managed Public Ingress with HAProxy + Reserved IP

> **Status: STANDBY / DRAFT.** Public HAProxy/Reserved-IP failover has not yet been deployed or live-validated in the current build. Do not execute this manual yet. Re-check provider access, current etcd transport, HAProxy listeners, health probes, DNS, Reserved-IP behavior, and failover safeguards when this phase becomes active.

This POC does **not** buy a DigitalOcean Network Load Balancer.

Instead, reuse the HAProxy processes already running on `ha-01` and `ha-02` and place one DigitalOcean Reserved IPv4 address in front of them.

The goal is:

```text
                     Internet
                        |
                        v
                one Reserved IPv4
               stable public address
                        |
              assigned to ONE Droplet
                        |
              +---------+---------+
              |                   |
              v                   v
           ha-01                ha-02
           HAProxy              HAProxy
           candidate            candidate
           :443                 :443
           :8883                :8883
              |                   |
              +---------+---------+
                        |
                healthy backends
```

The Reserved IP is **active/passive**, not active/active. DigitalOcean allows it to be reassigned between Droplets in the same datacenter, but only one Droplet owns it at a time.

Why this fits the POC:

- no fourth Droplet;
- no paid managed load-balancer line item;
- HAProxy is already required for the architecture;
- the public address stays unchanged during host failover;
- we prove the public-ingress failover mechanism ourselves.

This is still a real dependency: automated public failover now depends on the DigitalOcean Reserved-IP API and our failover controller. Do not describe it as a managed load balancer.

## 10.1 Provider behavior to understand first

For this design:

```text
Reserved IP
  = stable public address

Anchor IP
  = address on each Droplet where its HAProxy public listeners bind

DigitalOcean API / doctl
  = moves the Reserved IP from one Droplet to the other

etcd lock
  = prevents both hosts from making a takeover decision at the same time
```

An assigned Reserved IPv4 is free under the current DigitalOcean pricing model. An unassigned Reserved IPv4 is billable, so keep this address assigned to one of the two app Droplets instead of leaving it parked.

DigitalOcean recommends binding highly available public services to each Droplet's **anchor IP**. This prevents users from bypassing the Reserved IP by connecting to the Droplet's ordinary public address.

## 10.2 Record the ingress worksheet

From `ADMIN`, record:

```text
DigitalOcean region/datacenter:
Reserved IPv4:
ha-01 Droplet ID:
ha-02 Droplet ID:
ha-01 private VPC IP:
ha-02 private VPC IP:
ha-01 anchor IPv4:
ha-02 anchor IPv4:
chirpstack.<DOMAIN>:
mqtt.<DOMAIN>:
DigitalOcean failover-token protected-file reference:
etcd client certificate reference used by failover agent:
```

Do not put the DigitalOcean API token value in this worksheet.

**Hard stop:** `ha-01`, `ha-02`, and the Reserved IP must be in the same DigitalOcean datacenter/region that supports reassignment between those Droplets.

## 10.3 Get the Droplet IDs

From `ADMIN` with an authenticated `doctl` context:

```bash
doctl compute droplet get ha-01 --format ID,Name,Region,PublicIPv4,PrivateIPv4 --no-header
doctl compute droplet get ha-02 --format ID,Name,Region,PublicIPv4,PrivateIPv4 --no-header
```

Record the numeric IDs. The failover controller uses IDs, not hostnames, when assigning the Reserved IP.

## 10.4 Create one Reserved IPv4 and assign it immediately

Create it assigned to `ha-01` initially:

```bash
doctl compute reserved-ip create --droplet-id <HA01_DROPLET_ID>
```

Record the returned address as `<RESERVED_IP>`.

Verify:

```bash
doctl compute reserved-ip get <RESERVED_IP> --format IP,Region,DropletID,DropletName --no-header
```

Expected initial owner:

```text
ha-01
```

Do not deliberately leave the IPv4 unassigned between tests.

## 10.5 Find the anchor IPv4 on ha-01 and ha-02

Run on **each app Droplet**:

```bash
curl -fsS http://169.254.169.254/metadata/v1/interfaces/public/0/anchor_ipv4/address
echo
```

Also inspect the interface normally:

```bash
ip -br address
ip route
```

Record:

```text
ha-01 -> <HA01_ANCHOR_IP>
ha-02 -> <HA02_ANCHOR_IP>
```

**Why:** the public HAProxy listeners bind to these anchor addresses. Internal HAProxy/PgBouncer/Valkey/OpenBao routes continue using the VPC/private addresses documented elsewhere.

## 10.6 Bind only public HAProxy frontends to anchor IPs

The two public listeners are:

```text
ha-01 anchor IP :443
ha-01 anchor IP :8883

ha-02 anchor IP :443
ha-02 anchor IP :8883
```

Conceptually:

```haproxy
frontend chirpstack_https
    bind <THIS_HOST_ANCHOR_IP>:443 ssl crt /etc/lorawan-pki/public/chirpstack.pem
    ...

frontend mqtt_public
    mode tcp
    bind <THIS_HOST_ANCHOR_IP>:8883
    ...
```

Do **not** change these private listeners to anchor IPs:

```text
15432 PostgreSQL-primary route
15433 PostgreSQL-replica test route
16379 Valkey-primary route
18883 internal MQTT route
18200 OpenBao KMS route
```

Those remain private VPC services.

Before continuing:

```bash
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
sudo systemctl reload haproxy
sudo ss -lntp | grep -E ':(443|8883|15432|16379|18883)\b'
```

Pass only when `443` and `8883` are on the anchor address while the internal listeners remain on the intended private address.

## 10.7 Point both public DNS names at the Reserved IP

Create/update:

```text
chirpstack.<DOMAIN>  A  <RESERVED_IP>
mqtt.<DOMAIN>        A  <RESERVED_IP>
```

Verify from `ADMIN`:

```bash
getent ahostsv4 chirpstack.<DOMAIN>
getent ahostsv4 mqtt.<DOMAIN>
```

Both should resolve to the same Reserved IPv4.

## 10.8 Prove manual reassignment before automating it

First prove `ha-01` serves both public paths through the Reserved IP:

```bash
curl --fail --silent --show-error https://chirpstack.<DOMAIN>/ >/dev/null

openssl s_client \
  -connect mqtt.<DOMAIN>:8883 \
  -servername mqtt.<DOMAIN> \
  -CAfile <MQTT_CA> \
  -cert <STAGING_MQTT_CLIENT_CERT> \
  -key <STAGING_MQTT_CLIENT_KEY> \
  -verify_return_error </dev/null
```

Then deliberately move the Reserved IP to `ha-02`:

```bash
doctl compute reserved-ip-action assign <RESERVED_IP> <HA02_DROPLET_ID>
```

Poll ownership:

```bash
doctl compute reserved-ip get <RESERVED_IP> --format DropletID,DropletName --no-header
```

Repeat the HTTPS and MQTT TLS checks **without changing DNS, port, or certificate**.

Then move it back to `ha-01` for the initial automatic-failover test:

```bash
doctl compute reserved-ip-action assign <RESERVED_IP> <HA01_DROPLET_ID>
```

**Stop here** if manual reassignment does not preserve both public endpoints. Automation cannot fix an incorrect anchor-IP, HAProxy, certificate, firewall, or DNS design.

## 10.9 Failover-controller safety model

Run one small failover agent on `ha-01` and one on `ha-02`.

Each agent follows this logic:

```text
public endpoint healthy?
        |
       YES
        |
        +--> do nothing

       NO for 3 consecutive checks
        |
        v
is THIS host locally healthy on its anchor IP?
        |
       NO --> do nothing; this host is not a takeover candidate
        |
       YES
        |
        v
acquire etcd distributed lock
        |
        v
re-check public endpoint
        |
       healthy --> release lock; do nothing
        |
       still failed
        |
        v
is Reserved IP already assigned to THIS host?
        |
       YES --> do not flap the IP; investigate local/provider path
        |
       NO
        |
        v
assign Reserved IP to THIS Droplet using DigitalOcean API
        |
        v
verify ownership + public recovery
```

The etcd lock matters. If both app hosts observe the same outage simultaneously, only one is allowed to execute the reassignment decision at a time.

If etcd quorum is unavailable, **automatic public takeover must stop**. Do not bypass the lock automatically because that would turn a network partition into a public-ingress split-brain/flapping problem.

## 10.10 Install the failover prerequisites on ha-01 and ha-02

Required:

```text
doctl
etcdctl matching the deployed etcd major/minor compatibility
curl
openssl
timeout/coreutils
```

Confirm:

```bash
doctl version
etcdctl version
curl --version
openssl version
```

The failover identity needs only the DigitalOcean permissions required to inspect/reassign the Reserved IP under the account's current token model. Do not reuse a human administrator's broad everyday token if a narrower automation identity is available.

## 10.11 Create the protected environment file

On `ha-01` and `ha-02`:

```bash
sudo install -d -m 750 /etc/lorawan-cloud
sudo install -m 600 /dev/null /etc/lorawan-cloud/public-ingress.env
sudoedit /etc/lorawan-cloud/public-ingress.env
```

Use host-specific values:

```dotenv
RESERVED_IP=<RESERVED_IP>
THIS_DROPLET_ID=<THIS_DROPLET_ID>
THIS_ANCHOR_IP=<THIS_HOST_ANCHOR_IP>
CHIRPSTACK_FQDN=chirpstack.<DOMAIN>
MQTT_FQDN=mqtt.<DOMAIN>
PUBLIC_CA=/etc/ssl/certs/ca-certificates.crt
MQTT_CA=/etc/lorawan-pki/mqtt/ca.crt
MQTT_MONITOR_CERT=/etc/lorawan-pki/mqtt/monitor.crt
MQTT_MONITOR_KEY=/etc/lorawan-pki/mqtt/monitor.key
DIGITALOCEAN_TOKEN=<LOAD_FROM_PROTECTED_SECRET>

ETCDCTL_ENDPOINTS=http://10.104.0.2:2379,http://10.104.0.4:2379,http://10.104.0.8:2379
```

The currently tested etcd transport is HTTP on the private `10.104.0.0/20` east-west network, so no etcd client certificate is configured at this checkpoint. If etcd TLS is introduced later, give the public-ingress lock a dedicated client identity rather than reusing PostgreSQL, MQTT, OpenBao, or application credentials.

The MQTT monitor certificate should have only the broker permission needed for the health workflow; do not reuse a gateway identity.

## 10.12 Create the common health helper

Create `/usr/local/sbin/lorawan-ingress-health` on `ha-01` and `ha-02`:

```bash
#!/usr/bin/env bash
set -euo pipefail

source /etc/lorawan-cloud/public-ingress.env

https_check() {
  local connect_ip="$1"
  curl --fail --silent --show-error \
    --connect-timeout 3 --max-time 5 \
    --resolve "${CHIRPSTACK_FQDN}:443:${connect_ip}" \
    "https://${CHIRPSTACK_FQDN}/" >/dev/null
}

mqtt_tls_check() {
  local connect_ip="$1"
  timeout 6 openssl s_client \
    -connect "${connect_ip}:8883" \
    -servername "${MQTT_FQDN}" \
    -CAfile "${MQTT_CA}" \
    -cert "${MQTT_MONITOR_CERT}" \
    -key "${MQTT_MONITOR_KEY}" \
    -verify_return_error </dev/null 2>&1 \
    | grep -q 'Verify return code: 0 (ok)'
}

case "${1:-}" in
  public)
    https_check "${RESERVED_IP}" && mqtt_tls_check "${RESERVED_IP}"
    ;;
  local)
    systemctl is-active --quiet haproxy
    https_check "${THIS_ANCHOR_IP}"
    mqtt_tls_check "${THIS_ANCHOR_IP}"
    ;;
  *)
    echo "usage: $0 public|local" >&2
    exit 2
    ;;
esac
```

Protect it:

```bash
sudo chown root:root /usr/local/sbin/lorawan-ingress-health
sudo chmod 750 /usr/local/sbin/lorawan-ingress-health
```

Test on both hosts:

```bash
sudo /usr/local/sbin/lorawan-ingress-health local
sudo /usr/local/sbin/lorawan-ingress-health public
```

`local` must succeed on **both** app hosts before automatic failover is enabled.

## 10.13 Create the takeover action

Create `/usr/local/sbin/lorawan-ingress-takeover`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source /etc/lorawan-cloud/public-ingress.env

HEALTH=/usr/local/sbin/lorawan-ingress-health

# Another host may already have fixed the outage while we waited for the lock.
if "${HEALTH}" public; then
  exit 0
fi

# Never move traffic onto an unhealthy candidate.
"${HEALTH}" local

owner="$(doctl --access-token "${DIGITALOCEAN_TOKEN}" \
  compute reserved-ip get "${RESERVED_IP}" \
  --format DropletID --no-header | tr -d '[:space:]')"

if [[ "${owner}" == "${THIS_DROPLET_ID}" ]]; then
  echo "Reserved IP already belongs to this host; refusing to flap it." >&2
  exit 1
fi

echo "Moving ${RESERVED_IP} from Droplet ${owner} to ${THIS_DROPLET_ID}"
doctl --access-token "${DIGITALOCEAN_TOKEN}" \
  compute reserved-ip-action assign "${RESERVED_IP}" "${THIS_DROPLET_ID}"

for _ in $(seq 1 15); do
  owner="$(doctl --access-token "${DIGITALOCEAN_TOKEN}" \
    compute reserved-ip get "${RESERVED_IP}" \
    --format DropletID --no-header | tr -d '[:space:]')"
  [[ "${owner}" == "${THIS_DROPLET_ID}" ]] && break
  sleep 1
done

[[ "${owner}" == "${THIS_DROPLET_ID}" ]]

for _ in $(seq 1 10); do
  if "${HEALTH}" public; then
    echo "Reserved IP takeover succeeded on Droplet ${THIS_DROPLET_ID}."
    exit 0
  fi
  sleep 2
done

echo "Reserved IP moved, but public health did not recover." >&2
exit 1
```

Then:

```bash
sudo chown root:root /usr/local/sbin/lorawan-ingress-takeover
sudo chmod 750 /usr/local/sbin/lorawan-ingress-takeover
```

## 10.14 Create the evaluator

Create `/usr/local/sbin/lorawan-ingress-evaluate`:

```bash
#!/usr/bin/env bash
set -euo pipefail
source /etc/lorawan-cloud/public-ingress.env

HEALTH=/usr/local/sbin/lorawan-ingress-health
STATE=/run/lorawan-public-ingress.failures

if "${HEALTH}" public; then
  printf '0\n' > "${STATE}"
  exit 0
fi

failures=0
[[ -r "${STATE}" ]] && read -r failures < "${STATE}" || true
failures=$((failures + 1))
printf '%s\n' "${failures}" > "${STATE}"

echo "public ingress health failure ${failures}/3"
[[ "${failures}" -ge 3 ]] || exit 0

# This node must be able to serve both public frontends before it may compete.
"${HEALTH}" local

export ETCDCTL_API=3

# The command inside this distributed lock re-checks health before moving the IP.
timeout 25 etcdctl \
  --endpoints="${ETCDCTL_ENDPOINTS}" \
  lock --ttl=15 /lorawan/public-ingress \
  /usr/local/sbin/lorawan-ingress-takeover

printf '0\n' > "${STATE}"
```

Then:

```bash
sudo chown root:root /usr/local/sbin/lorawan-ingress-evaluate
sudo chmod 750 /usr/local/sbin/lorawan-ingress-evaluate
```

The three-failure gate reduces needless failover from a single transient probe failure. With a 15-second timer, takeover normally starts after roughly 30-45 seconds plus API reassignment/recovery time. Record the measured value instead of promising a fixed RTO.

## 10.15 Run it with systemd

Create `/etc/systemd/system/lorawan-public-ingress.service`:

```ini
[Unit]
Description=Evaluate LoRaWAN public Reserved-IP failover
After=network-online.target haproxy.service
Wants=network-online.target

[Service]
Type=oneshot
EnvironmentFile=/etc/lorawan-cloud/public-ingress.env
ExecStart=/usr/local/sbin/lorawan-ingress-evaluate
```

Create `/etc/systemd/system/lorawan-public-ingress.timer`:

```ini
[Unit]
Description=Periodically evaluate LoRaWAN public Reserved-IP failover

[Timer]
OnBootSec=30s
OnUnitActiveSec=15s
RandomizedDelaySec=2s
AccuracySec=1s

[Install]
WantedBy=timers.target
```

Validate files, then enable on `ha-01` and `ha-02`:

```bash
sudo systemctl daemon-reload
sudo systemctl start lorawan-public-ingress.service
sudo systemctl status lorawan-public-ingress.service --no-pager -l
sudo systemctl enable --now lorawan-public-ingress.timer
systemctl list-timers --all | grep lorawan-public-ingress
```

Watch:

```bash
journalctl -u lorawan-public-ingress.service -f
```

## 10.16 Automatic failover acceptance test

Start with:

```text
Reserved IP -> ha-01
ha-01 HAProxy healthy
ha-02 HAProxy healthy
etcd 3/3
```

Verify ownership:

```bash
doctl compute reserved-ip get <RESERVED_IP> --format DropletID,DropletName --no-header
```

Then:

1. record UTC start time;
2. power off or otherwise make **ha-01** unavailable;
3. do not edit DNS;
4. do not manually reassign the IP;
5. watch the `ha-02` failover-agent journal;
6. watch Reserved-IP ownership from `ADMIN`;
7. wait for ownership to become `ha-02`;
8. prove `https://chirpstack.<DOMAIN>` recovers;
9. prove MQTT mTLS on `mqtt.<DOMAIN>:8883` recovers;
10. send a **new** real EMU-01 uplink;
11. record RTO from failure injection to first new successfully processed post-fault uplink.

Pass when no DNS, certificate, gateway MQTT endpoint, or application URL changes are required.

## 10.17 Restore without automatic failback

When `ha-01` returns, **do not automatically move the Reserved IP back**.

Expected:

```text
Reserved IP remains on healthy ha-02
ha-01 rejoins as a ready standby candidate
```

This avoids failback flapping.

After all quorum/application checks show full health, a planned operator may manually move the Reserved IP back to `ha-01` if desired:

```bash
doctl compute reserved-ip-action assign <RESERVED_IP> <HA01_DROPLET_ID>
```

Then repeat the public health tests.

For the `ha-02` host-loss test, deliberately assign the Reserved IP to `ha-02` first, verify both candidates are healthy, then fail `ha-02` and prove automatic movement to `ha-01`.

## 10.18 Failure cases and what they mean

```text
ha-01 dies while it owns Reserved IP
  -> ha-02 should take the etcd lock and move the Reserved IP

ha-02 dies while ha-01 owns Reserved IP
  -> no public-IP move required

one ChirpStack process dies
  -> HAProxy can route to the other ChirpStack; Reserved IP should not move

Mosquitto-1 dies
  -> HAProxy uses Mosquitto-2; Reserved IP should not move

etcd loses quorum
  -> automatic Reserved-IP movement must stop

DigitalOcean API unavailable
  -> internal HA can still work, but public Reserved-IP reassignment cannot occur

both public HAProxy candidates unhealthy
  -> do not move the IP back and forth; fix the application/host problem
```

## 10.19 Troubleshooting commands

Current Reserved-IP owner:

```bash
doctl compute reserved-ip get <RESERVED_IP> --format IP,Region,DropletID,DropletName --no-header
```

Anchor IP on the current host:

```bash
curl -fsS http://169.254.169.254/metadata/v1/interfaces/public/0/anchor_ipv4/address
echo
```

Agent state:

```bash
systemctl status lorawan-public-ingress.timer --no-pager
systemctl status lorawan-public-ingress.service --no-pager -l
journalctl -u lorawan-public-ingress.service --since=-15min --no-pager
```

Local candidate health:

```bash
sudo /usr/local/sbin/lorawan-ingress-health local
```

Public health:

```bash
sudo /usr/local/sbin/lorawan-ingress-health public
```

etcd quorum/lock dependency:

```bash
ETCDCTL_API=3 etcdctl \
  --endpoints="${ETCDCTL_ENDPOINTS}" \
  endpoint health
```

HAProxy config/listeners:

```bash
sudo haproxy -c -V -f /etc/haproxy/haproxy.cfg
sudo ss -lntp | grep -E ':(443|8883|8080|8884)\b'
```

## 10.20 Security rules

- Keep the DigitalOcean token in a root-readable protected file/secret path, never Git.
- Use the narrowest DigitalOcean token permissions available for the failover task.
- Do not give the failover identity access to PostgreSQL, OpenBao Transit signing, gateway AppKeys, or Fabric identities.
- The current etcd checkpoint uses HTTP only on the private east-west network. If etcd TLS/authentication is added later, give the failover controller a dedicated least-privilege etcd client identity.
- Keep the Reserved IPv4 assigned to one app Droplet instead of parking it unassigned.
- Do not bind public `443/8883` to `0.0.0.0` merely because it is easier; use the anchor address for the self-managed ingress design.
- Treat a manual Reserved-IP move during an incident as a controlled operator action and record who moved it, when, from which Droplet, and why.

## 10.21 Final pass condition

This layer passes when:

```text
one stable Reserved IP
        |
        +-> DNS never changes during failover
        +-> ha-01 can serve it
        +-> ha-02 can serve it
        +-> manual reassignment works
        +-> automatic reassignment works with etcd quorum
        +-> one whole app-host loss recovers automatically
        +-> no automatic failback flapping
        +-> fresh real uplink succeeds after takeover
```

Next standby phase: [11-raspberry-pi-4g-backhaul.md](11-raspberry-pi-4g-backhaul.md). Use [19-cloud-ha-grafana-deployment-day-runbook.md](19-cloud-ha-grafana-deployment-day-runbook.md) only as a sequence reference until its later phases are refined.
