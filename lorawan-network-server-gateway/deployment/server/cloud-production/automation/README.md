# Public-Ingress Certificate Automation

These files mirror the commissioned 2026-09-01 runtime on the three cloud hosts. They exist so certificate recovery does not depend on chat history or undocumented shell state.

## Live ownership model

- `ulc-01` is the ACME owner for `smartagri-chirpstack.duckdns.org` while the Reserved IPv4 is assigned there.
- Certbot writes the Let's Encrypt lineage under `/etc/letsencrypt/live/smartagri-chirpstack.duckdns.org/`.
- `lorawan-chirpstack-cert-sync` validates the certificate/key, updates the local HAProxy certificate directory, validates HAProxy before reload, and sends the same PEM to `ulc-02`.
- `ulc-02` accepts that PEM only through a source-restricted forced-command SSH key and an exact-command sudoers rule. `PermitRootLogin no` remains unchanged.
- All three hosts run the certificate-health timer daily with a 21-day warning threshold by default.

## Required ulc-01 files

```text
/usr/local/sbin/lorawan-chirpstack-cert-sync
/etc/letsencrypt/renewal-hooks/deploy/50-lorawan-chirpstack-sync
/etc/systemd/system/lorawan-chirpstack-cert-sync.service
/etc/systemd/system/lorawan-chirpstack-cert-sync.timer
/root/.ssh/lorawan-chirpstack-certsync
/root/.ssh/lorawan-chirpstack-certsync_known_hosts
```

The dedicated SSH private key is generated locally on `ulc-01` and is never stored in Git. The currently accepted `ulc-02` ED25519 host-key fingerprint is:

```text
SHA256:6At4Nz4CEKTFF3LZ80i4OI0+5SD/EpkjDtYc94t5C1k
```

Always verify the live host key before rebuilding `known_hosts`; do not blindly copy this historical fingerprint after a host rebuild.

## Required ulc-02 authorization

Install `lorawan-chirpstack-cert-receive` as `/usr/local/sbin/lorawan-chirpstack-cert-receive` mode `0750` and allow only this exact sudo command:

```text
opsadmin ALL=(root) NOPASSWD: /usr/local/sbin/lorawan-chirpstack-cert-receive
```

The dedicated public key from `ulc-01` is added to `/home/opsadmin/.ssh/authorized_keys` with:

```text
from="10.104.0.2",restrict,command="/usr/bin/sudo -n /usr/local/sbin/lorawan-chirpstack-cert-receive" <DEDICATED_CERTSYNC_PUBLIC_KEY>
```

Do not enable root SSH for certificate synchronization.

## Certificate health on all hosts

Install:

```text
/usr/local/sbin/lorawan-certificate-health
/etc/systemd/system/lorawan-certificate-health.service
/etc/systemd/system/lorawan-certificate-health.timer
```

Then run:

```sh
systemctl daemon-reload
systemctl enable --now lorawan-certificate-health.timer
systemctl start lorawan-certificate-health.service
systemctl show lorawan-certificate-health.service -p Result -p ExecMainStatus
```

The commissioned manual run returned `Result=success` and `ExecMainStatus=0` on `ulc-01`, `ulc-02`, and `ulc-03`.

## Trust split

Only ChirpStack browser/API TLS uses Let's Encrypt. MQTT and Evidence intentionally keep their private client-auth CAs; their server certificates carry the public DuckDNS SANs while preserving the existing private keys and client trust roots.
