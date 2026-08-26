# 10. Self-Managed Public Ingress with HAProxy + Reserved IP

> **Status: ACTIVE PRE-TEST SETUP / PREFLIGHT IN PROGRESS.** Phase 9 application commissioning is complete. Phase 10 commissions the normal public HTTPS/MQTT path, manual Reserved-IP mobility, and an armed failover controller. **Do not intentionally fail a host in this phase.** Automatic host-loss takeover is tested only in Phase 15 after the full pre-test gate passes.

## 10.0 Activation preflight - read-only, no public mutation

This gate activates Phase 10 safely. It is deliberately read-only. Do **not** reserve an IP, change DNS, install certificates, reload HAProxy, edit firewall rules, or enable failover automation while running it.

### Fast execution rule

To keep this and later setup phases efficient, **batch independent read-only checks into one bounded operator block**, but keep each state change behind its own verification gate. Do not repeat a previously passed read-only check unless a later mutation could have invalidated it. For Phase 10 specifically, the host/application/listener/anchor/etcd preflight below is already recorded as passing; continue from the unresolved provider metadata and public-identity inputs instead of re-running the entire host preflight.

Prove and record all of the following before section 10.1 is treated as executable:

1. `ulc-01` (`10.104.0.2`) and `ulc-02` (`10.104.0.4`) are the two current ChirpStack/HAProxy candidates and both ChirpStack private endpoints `:18080` are `running|0` and HTTP `200`;
2. the existing HAProxy configurations validate, public `:443` is not already occupied unexpectedly, and existing `:8883` listeners are still bound only to the intended private VPC addresses rather than `0.0.0.0`;
3. both hosts expose a DigitalOcean anchor IPv4 through metadata and the anchor addresses are distinct from their normal public and private VPC addresses;
4. an authenticated `doctl` context can read both Droplets and any existing Reserved-IP inventory without creating or reassigning anything; record exact Droplet IDs and confirm both candidates are in the same datacenter/region;
5. current etcd quorum is healthy and its real transport/authentication model is recorded before designing the takeover lock;
6. current public DNS names and certificate state are inventoried rather than assumed. If `chirpstack.<DOMAIN>` or `mqtt.<DOMAIN>` is not yet allocated, record that as pending instead of inventing a domain;
7. current firewall policy is inventoried for `443/tcp` and `8883/tcp`; no rule is opened during this gate;
8. no existing public certificate, monitor certificate, DigitalOcean token, or failover-agent file is assumed merely because the draft contains a path placeholder.

**Pass condition:** the worksheet can be populated from real current state, there is no listener/address collision, both candidate Droplets are provider-compatible for Reserved-IP reassignment, and all unknown public-facing values are explicitly identified before the first mutation.

### Phase 10.0 recorded activation-preflight result - 2026-08-26

Phase 10.0 is **PARTIAL / HOST PREFLIGHT PASS; PROVIDER + PUBLIC-PKI INPUTS REQUIRED BEFORE MUTATION**.

The private application layer remained healthy throughout the read-only preflight: `ulc-01` and `ulc-02` ChirpStack were both `running|0` with HTTP `200`. Both installed HAProxy configurations passed syntax validation. No public `:443` listener exists. The existing gateway-facing `:8883`, ChirpStack-internal MQTT `:18883`, PostgreSQL `:15432/:15433`, Valkey `:16379`, and ChirpStack `:18080` listeners remain bound to the private VPC addresses, not `0.0.0.0`. The repaired ulc-02 loopback PostgreSQL-primary listener `127.0.1.1:15432` also remains present as intended.

DigitalOcean anchor addressing and candidate identity are now confirmed from host metadata. `ulc-01` has Droplet ID `593678406`, region `sgp1`, normal public IPv4 `143.198.205.54`, anchor IPv4 `10.15.0.5`, and VPC IPv4 `10.104.0.2`. `ulc-02` has Droplet ID `593678408`, region `sgp1`, normal public IPv4 `165.22.253.127`, anchor IPv4 `10.15.0.7`, and VPC IPv4 `10.104.0.4`. The anchor addresses are distinct from both ordinary public addresses and the `10.104.0.0/20` VPC path. **Phase 10.0A PASS:** both ingress candidates are independently proven to be in the same DigitalOcean region (`sgp1`), so the same-region Reserved-IP eligibility hard stop is closed. Do not repeat the metadata check unless a Droplet is rebuilt or replaced.

The etcd failover-lock dependency is healthy at this checkpoint. `etcdctl 3.4.30` successfully committed proposals against `http://10.104.0.2:2379`, `http://10.104.0.4:2379`, and `http://10.104.0.8:2379`. The currently commissioned etcd transport therefore remains private HTTP as documented; do not invent a TLS client identity for the public-ingress lock unless etcd itself is later migrated to TLS.

### Phase 10.0B operator-access decision - provider path deferred, local work continues

The current operator has **no DigitalOcean control-panel access**. Do not keep asking this operator to inspect or modify the provider panel. Reserved-IPv4 inventory/creation, DigitalOcean Cloud Firewall evidence, provider DNS changes, and issuance of a least-privilege DigitalOcean API identity remain an **external provider-owner handoff** and Phase 10 cannot claim final PASS until that handoff is completed.

This access boundary does **not** block provider-independent setup. Complete the Phase 10H host-side ingress-candidate sequence first: stage the internal HTTPS identity, commission the anchor listeners on `ulc-01` and `ulc-02` one node at a time, prove candidate HTTPS/MQTT routing locally, and stage the health/locking logic in no-action mode. Only after those host-owned steps are complete should work advance into the local portion of Phase 11 while the provider handoff remains open. Do not substitute a normal Droplet public IP, weaken TLS hostname verification, or expose a private broker port merely to bypass the provider-owner dependency.

The unresolved activation blockers are explicit. `doctl` is absent on the ulc-03 control shell, so provider API identity, existing Reserved-IP inventory, and reassignment permissions are not yet proven. No `/etc/lorawan-pki/public` directory or public ChirpStack certificate exists on either app node. The dedicated MQTT health-monitor certificate/key are also absent on both nodes. `chirpstack.<DOMAIN>` and `mqtt.<DOMAIN>` have not been assigned real public names in the repository or current operator evidence. No public-ingress environment, health-helper, failover-agent, systemd service, or timer exists on either candidate.

Host `ufw` is inactive and no local nftables rule mentioning `443`/`8883` was observed, but this **does not authorize any firewall change** and does not prove provider-side exposure. Phase 3 records the DigitalOcean Cloud Firewall as externally managed by the provider-account owner and outside the current operator's modification/verification authority. Its required `443/tcp` and `8883/tcp` policy therefore remains a provider-owner handoff item.

Do **not** install `doctl`, create a Reserved IP, issue public certificates, create DNS records, or alter firewall policy merely to make this preflight appear complete. The Droplet metadata ID/region gate is closed. Provider-owned inputs remain required before public activation, but Phase 10H may commission candidate-only anchor listeners using the internal staging HTTPS certificate and the existing internal MQTT identity. Public PKI, the public MQTT SAN, Cloud Firewall evidence, Reserved-IP control, DNS, and the least-privilege monitor identity remain required before those listeners are treated as public-ready.

### 10.0B Panel-independent host-side commissioning path

DigitalOcean Control Panel access is **not required** to continue the host-side portion of Phase 10. When the current operator cannot inspect or change provider resources, split Phase 10 into two boundaries instead of blocking all work.

**Host-owned boundary — execute now:** commission and verify both HAProxy ingress candidates on their already-proven DigitalOcean anchor addresses. Use a temporary certificate signed by the existing internal CA for HTTPS candidate testing, keep MQTT TLS pass-through to the existing Mosquitto `:8884` backends, validate one host at a time, and build the normal-condition health/locking logic without executing a Reserved-IP action. The staging HTTPS identity is `chirpstack.internal.lorawan.com`; it is for candidate validation only and is not a substitute for the later public certificate.

```text
10H-1  issue/verify internal staging HTTPS certificate on ulc-03 — COMPLETE / PASS
10H-2  add ulc-01 anchor :443 and anchor :8883 frontends — COMPLETE / PASS
10H-3  verify ulc-01 candidate locally through both anchor listeners — COMPLETE / PASS
10H-4  add ulc-02 anchor :443 and anchor :8883 frontends — COMPLETE / PASS
10H-5  verify ulc-02 candidate locally through both anchor listeners — COMPLETE / PASS
10H-6  stage/verify health helper and etcd locking logic in no-action mode — COMPLETE / PASS
```

### Phase 10H-1 execution result - COMPLETE / PASS

The host-side candidate preflight and staging HTTPS issuance completed successfully. `ulc-01` remained `running|0` with HTTP `200`, HAProxy configuration valid, anchor `10.15.0.5`, and anchor ports `443/8883` free. `ulc-02` remained `running|0` with HTTP `200`, HAProxy configuration valid, anchor `10.15.0.7`, and anchor ports `443/8883` free. The existing private MQTT frontends remain `10.104.0.2:8883` and `10.104.0.4:8883` using backend `mqtt_brokers`; no service listener was changed in H-1.

**Phase 10H-2 harness correction:** the first operator block placed several `exit 1` branches directly in the interactive `opsadmin@ulc-03` login shell. Any failed local gate therefore terminates that SSH session instead of returning to the prompt. Treat a disconnect from that block as a control-shell harness defect, not as evidence that HAProxy, ChirpStack, MQTT, or the host failed. Before any H-2 retry, inspect current ulc-01 state read-only because the block may have completed some earlier mutation steps before hitting a later failed gate. All subsequent multi-step operator blocks that can call `exit` must run inside a subshell `( ... )` or another explicit child-shell boundary so failure cannot log out the operator.

**Phase 10H-2 recovery probe result — mutation present, H-3 verification pending:** the read-only recovery probe proved HAProxy active and syntax-valid on `ulc-01`, ChirpStack still `running|0` with HTTP `200`, and the Phase 10 objects already present in the live configuration. Anchor listeners `10.15.0.5:443` and `10.15.0.5:8883` are live under the current HAProxy worker while all commissioned private listeners `10.104.0.2:15432`, `:15433`, `:16379`, `:8883`, `:18883`, and ChirpStack `:18080` remain present. The staging PEM is installed root-owned mode `0600` with the expected fingerprint, and rollback configuration `/etc/haproxy/rollback-phase10h2-20260826-062020/haproxy.cfg` is present. `ulc-02` remains `running|0` / HTTP `200` and has no Phase 10 objects or anchor listeners. Therefore do **not** append the H-2 fragment or reload blindly again. Treat H-2 as applied successfully enough to proceed directly to read-only H-3 HTTPS/MQTT/backend/application verification. Keep the rollback until H-3 passes.

**Phase 10H-3 result — initial verification harness FAIL; service path healthy:** the shell-safe verification proved HAProxy active and syntax-valid, both new anchor listeners present, both ChirpStack backends HTTP `200`, all original private listeners preserved, zero HAProxy reload-error events, both ChirpStack nodes still `running|0` with HTTP `200`, and `ulc-02` still untouched. The first HTTPS/MQTT verification attempt reported HTTP `000` / TLS failure, but Phase 10H-3D subsequently proved that this was not an anchor-network failure.

**Phase 10H-3D diagnosis — PASS / verification CA permission defect isolated:** `ulc-01` owns `10.15.0.5/16` on `eth0`; the local route table contains `local 10.15.0.5 dev eth0`, `ip route get 10.15.0.5` resolves as local via `lo`, ping to the anchor succeeds, and raw TCP connections to both `10.15.0.5:443` and `10.15.0.5:8883` return exit `0`. HAProxy remains bound to both ports. INPUT/OUTPUT policy is accept and no local rule blocked the path. The verbose HTTPS probe connected successfully to `10.15.0.5:443` before curl exited `77` with `error setting certificate file: /etc/lorawan-pki/mqtt/ca.crt`; both OpenSSL probes failed before handshake with `BIO_new_file: Permission denied` reading that same CA path as unprivileged `opsadmin`. Therefore the anchor-IP and HAProxy socket paths are healthy. The defect was solely the test harness attempting to read a service-protected CA path without `sudo`. Do not loosen `/etc/lorawan-pki/mqtt` permissions and do not copy the CA into a broadly readable permanent location.

**Phase 10H-3R result — COMPLETE / PASS:** privileged verification closed the ulc-01 candidate. HTTPS through `10.15.0.5:443` returned HTTP `200`; the presented certificate was `CN = chirpstack.internal.lorawan.com`, issued by the commissioned internal CA, and OpenSSL returned `Verify return code: 0 (ok)`. MQTT TLS pass-through through `10.15.0.5:8883` presented `CN = mqtt.internal.lorawan.com`, the same internal CA verified successfully, and OpenSSL again returned `Verify return code: 0 (ok)`. Both ChirpStack nodes remained `running|0` with HTTP `200`. Therefore Phase 10H-2 and H-3 are COMPLETE / PASS for `ulc-01`.

**Phase 10H-4/H-5 result — COMPLETE / PASS:** the same validated topology was commissioned on `ulc-02` using anchor `10.15.0.7`. The pre-mutation gate found HAProxy active/config-valid and ChirpStack `running|0` / HTTP `200`; the anchor ports were free. The staging certificate verified for `10.15.0.7`, a rollback copy was created at `/etc/haproxy/rollback-phase10h4-20260826-064542/haproxy.cfg`, the candidate configuration validated, and HAProxy reloaded successfully. Runtime then showed exactly two new anchor listeners, `10.15.0.7:443` and `10.15.0.7:8883`, while private listeners `:15432`, `:15433`, `:16379`, `:8883`, `:18883`, and ChirpStack `:18080` remained present. HTTPS through the anchor returned HTTP `200` with verified `CN = chirpstack.internal.lorawan.com`; MQTT TLS pass-through presented verified `CN = mqtt.internal.lorawan.com`. Final two-host verification showed both ChirpStack nodes `running|0` / HTTP `200` and both candidates with exactly two anchor listeners. Phase 10H-4 and H-5 are therefore COMPLETE / PASS.

**Phase 10H-6 result — COMPLETE / PASS:** both candidates passed the no-action health/locking gate. HTTPS returned HTTP `200` through `10.15.0.5:443` and `10.15.0.7:443`; MQTT TLS pass-through on both anchor `:8883` listeners presented the verified `mqtt.internal.lorawan.com` certificate. `etcdctl 3.4.30` / API `3.4` is present on both candidates and each candidate independently reached all three private etcd endpoints successfully. The staging distributed-lock test acquired `/lorawan/public-ingress-staging` from ulc-01, proved the key became visible, forced the ulc-02 contender to wait until the first holder released it, then completed with both lock commands exit `0` and no persistent key left behind. Both ChirpStack nodes remained `running|0` / HTTP `200`. No `doctl`, Reserved-IP reassignment, DNS mutation, provider API action, or production timer was executed. `PHASE10_HOST_OWNED_BOUNDARY=PASS` is therefore authoritative. The remaining Phase 10 blockers are provider-owned public activation inputs only; continue into Phase 11 provider-independent gateway setup while that handoff remains open.

The issuing CA was re-proven as the commissioned `CN = LoRaWAN PostgreSQL Internal CA` with CA certificate SHA-256 `6773c652aadcc1740e630b3e0ee13ccaff9427df5418e89571b4630584ea4ddb` and fingerprint `99:00:4B:B3:2D:7D:78:FA:38:61:7C:78:89:6D:7A:7E:FF:9F:A6:10:FC:8F:07:D4:E2:5E:35:25:36:E6:CB:3E`. The root-only staging directory is `/root/lorawan-pg-ca/public-ingress-staging`. The staging certificate verifies for `DNS:chirpstack.internal.lorawan.com`, `IP:10.15.0.5`, and `IP:10.15.0.7`; certificate SHA-256 is `4d2ce9383ab6408553ecb31fa2f23360d271883efe43f66f76b2863757a5ddab`, certificate fingerprint is `F5:D6:77:ED:D7:9B:B8:E2:B1:7F:99:0D:74:DC:30:77:99:17:B8:A6:12:65:78:69:C2:B4:B2:D5:14:8B:66:B2`, and validity is `2026-08-26 06:12:54Z` through `2028-11-28 06:12:54Z`. The CA serial-file hash was unchanged by issuance. The staging PEM/key remain root-owned mode `0600`; this identity is test-only and must not be exposed as the final Internet certificate.

**Provider-owned boundary — required later for final Phase 10 PASS:** obtain or create the `sgp1` Reserved IPv4, confirm provider Cloud Firewall policy, assign real `chirpstack.<DOMAIN>` and `mqtt.<DOMAIN>` names, install a publicly trusted ChirpStack certificate, add the public MQTT SAN to both broker certificates, provision the least-privilege DigitalOcean API identity, prove manual Reserved-IP movement, and only then arm provider-facing reassignment actions.

The absence of provider-panel access therefore blocks **public activation and final Phase 10 PASS**, but it does not block host-side candidate commissioning. Do not point ordinary Droplet public IPv4 addresses at these services as a workaround, and do not expose the temporary internal HTTPS certificate as the final public identity.

This POC does **not** buy a DigitalOcean Network Load Balancer.

Instead, reuse the HAProxy processes already running on `ulc-01` and `ulc-02` and place one DigitalOcean Reserved IPv4 address in front of them.

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
           ulc-01                ulc-02
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
ulc-01 Droplet ID:
ulc-02 Droplet ID:
ulc-01 private VPC IP:
ulc-02 private VPC IP:
ulc-01 anchor IPv4:
ulc-02 anchor IPv4:
chirpstack.<DOMAIN>:
mqtt.<DOMAIN>:
DigitalOcean failover-token protected-file reference:
etcd client certificate reference used by failover agent:
```

Do not put the DigitalOcean API token value in this worksheet.

**Hard stop:** `ulc-01`, `ulc-02`, and the Reserved IP must be in the same DigitalOcean datacenter/region that supports reassignment between those Droplets.

## 10.3 Get the Droplet IDs

From `ADMIN` with an authenticated `doctl` context:

```bash
doctl compute droplet get ulc-01 --format ID,Name,Region,PublicIPv4,PrivateIPv4 --no-header
doctl compute droplet get ulc-02 --format ID,Name,Region,PublicIPv4,PrivateIPv4 --no-header
```

Record the numeric IDs. The failover controller uses IDs, not hostnames, when assigning the Reserved IP.

## 10.4 Create one Reserved IPv4 and assign it immediately

Create it assigned to `ulc-01` initially:

```bash
doctl compute reserved-ip create --droplet-id <ULC01_DROPLET_ID>
```

Record the returned address as `<RESERVED_IP>`.

Verify:

```bash
doctl compute reserved-ip get <RESERVED_IP> --format IP,Region,DropletID,DropletName --no-header
```

Expected initial owner:

```text
ulc-01
```

Do not deliberately leave the IPv4 unassigned between tests.

## 10.5 Find the anchor IPv4 on ulc-01 and ulc-02

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
ulc-01 -> <ULC01_ANCHOR_IP>
ulc-02 -> <ULC02_ANCHOR_IP>
```

**Why:** the public HAProxy listeners bind to these anchor addresses. Internal HAProxy/PgBouncer/Valkey/OpenBao routes continue using the VPC/private addresses documented elsewhere.

## 10.5A Reissue the Mosquitto server certificate for public TLS pass-through

Public MQTT remains **TLS pass-through**. HAProxy does not terminate or rewrite the broker TLS identity, so a gateway connecting to `mqtt.<DOMAIN>:8883` must receive a Mosquitto certificate valid for that exact public name.

The currently commissioned broker certificate is verified as `mqtt.internal.lorawan.com`. Before activating public MQTT, issue replacement broker certificates whose SAN set preserves the internal identity and adds the confirmed public name:

```text
mqtt.internal.lorawan.com
mqtt.<DOMAIN>
node-private identity/IP entries required by the existing broker policy
```

Roll the certificate one broker at a time. Before touching the second broker, prove the first broker still accepts existing internal clients with SNI `mqtt.internal.lorawan.com` **and** validates with SNI `mqtt.<DOMAIN>`. Keep the same trusted MQTT CA unless an approved CA rotation is intentionally part of this change.

Do not solve a hostname mismatch by disabling certificate verification or terminating gateway TLS at HAProxy. Gateway mTLS must still reach Mosquitto so the broker can authenticate the client certificate and enforce its EUI ACL.

Only after both brokers present certificates valid for both names may the anchor `:8883` frontends be treated as public-ready.

## 10.6 Bind only public HAProxy frontends to anchor IPs

The two public listeners are:

```text
ulc-01 anchor IP :443
ulc-01 anchor IP :8883

ulc-02 anchor IP :443
ulc-02 anchor IP :8883
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

First prove `ulc-01` serves both public paths through the Reserved IP:

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

Then deliberately move the Reserved IP to `ulc-02`:

```bash
doctl compute reserved-ip-action assign <RESERVED_IP> <ULC02_DROPLET_ID>
```

Poll ownership:

```bash
doctl compute reserved-ip get <RESERVED_IP> --format DropletID,DropletName --no-header
```

Repeat the HTTPS and MQTT TLS checks **without changing DNS, port, or certificate**.

Then move it back to `ulc-01` as the stable commissioning baseline. **Do not fail either host here; automatic takeover belongs to Phase 15:**

```bash
doctl compute reserved-ip-action assign <RESERVED_IP> <ULC01_DROPLET_ID>
```

**Stop here** if manual reassignment does not preserve both public endpoints. Automation cannot fix an incorrect anchor-IP, HAProxy, certificate, firewall, or DNS design.

## 10.9 Failover-controller safety model

Run one small failover agent on `ulc-01` and one on `ulc-02`.

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

### Phase 10H-6 no-action staging boundary

Because the current operator has no provider account/control-panel access and the real Reserved IPv4, public FQDNs, DigitalOcean token, and dedicated MQTT monitor identity do not yet exist, **do not install or enable sections 10.11-10.15 as the live production controller yet**. H-6 instead proves only the host-owned logic available without provider actions:

1. both anchor HTTPS/MQTT local-health checks pass using the temporary internal staging identities;
2. both candidate hosts can reach all three current private etcd endpoints;
3. exact `etcdctl` availability/version on each candidate is recorded rather than assumed;
4. a harmless dedicated staging lock path can serialize execution without changing provider state;
5. no `doctl`, Reserved-IP action, DNS mutation, public timer, or takeover script is executed.

If `etcdctl` is absent on one or both candidates, stop H-6 after recording that fact and commission the matching client in a separate reviewed step; do not silently use a different major version. Once provider-owned values are later supplied, sections 10.10-10.16 are completed with the real public health identities and controller.

## 10.10 Install the failover prerequisites on ulc-01 and ulc-02

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

On `ulc-01` and `ulc-02`:

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

Create `/usr/local/sbin/lorawan-ingress-health` on `ulc-01` and `ulc-02`:

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

Validate files, then enable on `ulc-01` and `ulc-02`:

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

## 10.16 Arm the automatic failover controller without injecting a fault

Phase 10 ends with the failover controller **installed, enabled, and healthy under normal conditions**, not with a powered-off Droplet.

Require:

```text
Reserved IP -> ulc-01
ulc-01 local anchor HTTPS/MQTT health = PASS
ulc-02 local anchor HTTPS/MQTT health = PASS
public HTTPS/MQTT health = PASS
etcd 3/3
failover service/timer enabled on ulc-01 and ulc-02
```

Run one normal evaluator cycle on each host. A healthy public endpoint must cause **no Reserved-IP action**. Review the journals and prove no reassignment was attempted.

**Hard stop:** do not power off ulc-01/02, stop HAProxy, block the DigitalOcean API, or remove etcd quorum in Phase 10. Those scenarios are Phase 15 tests.

## 10.17 Freeze the initial ingress baseline for Phase 15

Record the Reserved IPv4/current owner, Droplet IDs, anchor IPv4s, public DNS records, HTTPS and MQTT certificate fingerprints/expiry, failover script/unit hashes, DigitalOcean token secret reference/scope, etcd lock path/endpoints, and the no-automatic-failback policy.

A returning host must never trigger automatic failback; Phase 15 will verify that behavior after a real host-loss test.

## 10.18 Phase 15 failure expectations - reference only, do not inject here

```text
ulc-01 dies while it owns Reserved IP
  -> ulc-02 should take the etcd lock and move the Reserved IP

ulc-02 dies while ulc-01 owns Reserved IP
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

This setup layer passes when:

```text
one assigned stable Reserved IPv4
public HTTPS and MQTT DNS point to it
ulc-01 anchor can serve HTTPS + MQTT
ulc-02 anchor can serve HTTPS + MQTT
Mosquitto certificates validate for both internal and public MQTT names
manual reassignment works in both directions without DNS edits
failover services/timers are installed and armed on both candidates
healthy evaluator cycles perform no reassignment
etcd lock dependency is healthy
no automatic failback is configured
```

Automatic host-loss takeover, RTO, post-takeover real uplink, API-outage behavior, and no-failback recovery are **not Phase 10 pass conditions**. They are Phase 15 acceptance tests after Phase 14B passes.

Next required setup phase: [11-raspberry-pi-4g-backhaul.md](11-raspberry-pi-4g-backhaul.md).
