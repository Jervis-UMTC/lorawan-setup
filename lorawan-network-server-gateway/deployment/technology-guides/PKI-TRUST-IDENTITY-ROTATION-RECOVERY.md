# PKI / TLS / Service Identity — Issuance, Trust, Rotation and Disaster Recovery

**Scope:** the commissioned authentication/trust model for the real gateway, MQTT, ULC cloud, evidence store, OpenBao and external Fabric. Complements [PKI operator guide 17](17-pki-tls-and-service-identity.md). It describes safe operator procedures and where approved material lives, **never secret values**. Do not generate, rotate or revoke production certificates merely to validate Markdown.

## 1. Identify the type of authentication before troubleshooting

| Boundary | Authentication and purpose |
|---|---|
| Gateway local Mosquitto `127.0.0.1:1883` | Anonymous only on loopback; **not** an Internet service |
| Gateway outbound bridge `smartagri-mqtt.duckdns.org:8883` | server TLS with CA/SAN plus per-Gateway-EUI client certificate and topic ACL |
| Cloud gateway-facing broker `:8884` | current commissioned mTLS EUI-scoped policy; dated earlier Phase 9 *pre-migration* docs observed server-TLS/no client-cert, do not use that to weaken current config |
| ChirpStack broker `:8885` | private server TLS plus distinct hashed user/password and directional ACL; separate from gateway mTLS |
| Node-RED broker `:8886` | private mTLS, CN mapped to separate A/B read-only identities |
| MQTT collectors | separate mTLS clientAuth identities, read-only both cloud brokers; cannot publish |
| PostgreSQL/PgBouncer | TLS peer trust plus SCRAM DB credentials; **not automatically mTLS** |
| Valkey/Sentinel | TLS with password/ACL and protected replication identity; `tls-auth-clients no` in commissioned skeleton, so do not call all Valkey connections client-cert mTLS |
| OpenBao KMS | TLS CA/hostname and **separate** AppRole/Transit policy |
| Seaweed S3 object store | server TLS/private endpoint + distinct S3 credentials + create-only HAProxy policy |
| Gateway evidence ingest | server HTTPS trust and separate per-EUI gateway client mTLS upload authority |
| HRC Fabric Gateway | private peer server CA/SAN `peer1.hrc.local` and dedicated Fabric application client identity |
| Grafana | private SSH transport + normal dashboard login; read-only SCRAM/TLS SQL datasource |
| etcd Patroni DCS | commissioned **private HTTP exception**; protect network/firewall, never describe it as already TLS |

Transport **reachability** is not authentication, and server-auth TLS is not client-auth mTLS. Even correct TLS does not prove an application topic/SQL/Fabric permission.

## 2. Locate material on the correct host; do not expose private keys

~~~text
/etc/lorawan-pki/postgres/
/etc/lorawan-pki/pgbouncer/
/etc/lorawan-pki/mqtt/
/etc/lorawan-pki/valkey/
/etc/lorawan-pki/openbao/
/etc/lorawan-pki/gateway-evidence/
/etc/lorawan-pki/evidence-objectstore/
/etc/lorawan-pki/fabric/
Gateway OpenWrt:
/etc/mosquitto/certs/{ca.crt,0016c001f139a1cb.crt,0016c001f139a1cb.key}
ULC-02/03 Node-RED candidate:
/etc/lorawan-pki/node-red-mqtt/{client.crt,client.key}
/etc/lorawan-pki/node-red-pgbouncer/ca.crt
ULC-03 Grafana public trust copy:
/etc/lorawan-pki/grafana-pgbouncer/ca.crt
~~~

A “CA” filename ending `.crt` is generally public trust material; `ca.key` is the CA *private issuance authority* and requires separate custody, not repeated distribution. Paths are intended host inventory and must be confirmed against effective container mounts and live settings; a stale config example alone is not proof the file exists or is active.

Read-only **certificate** inspection on Ubuntu, from an authorized shell:

~~~bash
date -u
sudo find /etc/lorawan-pki -type f \( -name '*.crt' -o -name '*.pem' \) \
 -printf '%M %u:%g %p\n' 2>/dev/null | sort
openssl x509 -in /path/to/APPROVED_CERTIFICATE.crt \
 -noout -subject -issuer -serial -dates -fingerprint -sha256 \
 -ext subjectAltName -ext extendedKeyUsage
~~~

The placeholder path is deliberate; resolve **one actual target** before invoking. Do not glob and print every protected file, role env, password or private key content. Check effective runtime UID/GID of its consuming container, *then* file ownership/mode and parent-directory traversal. The Go evidence runtime uses numeric 65532 with reviewed root:65532 0440 private-key mounts; Node-RED uses UID 1000 plus a host-local `node-red-secrets` supplementary GID; ownership rules are **not interchangeable**.

## 3. Verify clocks, SANs, public keys and protocol semantics

First check `date -u` / proper time sync on **both** peers. Expired or not-yet-valid certs cannot be “repaired” by disabling trust.

To verify server TLS with the actual logical hostname and CA, from an authorized host:

~~~bash
openssl s_client \
 -connect <VERIFIED_ENDPOINT_IP_OR_HOST>:<PORT> \
 -servername <APPROVED_TLS_NAME> \
 -verify_hostname <APPROVED_TLS_NAME> \
 -verify_return_error \
 -CAfile /path/to/approved-public-ca.crt \
 </dev/null
~~~

**This is a template, not a runnable command until placeholders are resolved.** Require `Verify return code: 0 (ok)` and expected SAN/issuer. For a service accessible by a private IP but verified using a logical hostname, OpenSSL `-connect IP:PORT -servername logical.name -verify_hostname logical.name` keeps verification; do not use `-k`. For PostgreSQL/PgBouncer, plain `openssl s_client -connect :6432` can fail `wrong version number` even when TLS is healthy because PostgreSQL requires its **SSLRequest/STARTTLS** handshake. The reviewed diagnostic is `openssl s_client -starttls postgres ...` with the protected public CA and expected `pgbouncer.internal.lorawan.com` name. It does not authenticate as `telemetry_writer`.

For pairing, derive and compare public-key digests without showing a private key:

~~~bash
CERT_PUB="$(openssl x509 -in /path/to/approved-client.crt -pubkey -noout |
  openssl pkey -pubin -outform DER | sha256sum | awk '{print $1}')"
KEY_PUB="$(openssl pkey -in /path/to/approved-client.key -pubout -outform DER |
  sha256sum | awk '{print $1}')"
test -n "$CERT_PUB" && test "$CERT_PUB" = "$KEY_PUB" &&
  echo 'CERT_KEY_PAIR=PASS'
~~~

A password-encrypted key may require protected non-echoed passphrase handling. Do not print the private key or feed secret values as process arguments.

**Client-specific TLS mode caveat:** the pinned **ChirpStack 4.19.1 core Rust** PostgreSQL DSN accepted `sslmode=require` with *separate approved* `[postgresql].ca_cert` (the libpq spelling `verify-full` failed that parser). PgBouncer's upstream PostgreSQL TLS and Grafana's PostgreSQL datasource use their own reviewed **verify-full** hostname/CA policies. `sslmode=require` is **not** a universal recommendation to weaken other clients; inspect the actual parser, CA and server identity. Never apply a global string replacement to fix one client.

## 4. Explain ACL separately from certificate trust

An approved client certificate proves the holder's scoped identity **only if the server maps the CN/EKU/CA to the correct ACL**. Gateway EUI `0016c001f139a1cb` may write only its `as923/gateway/EUI/event/#` and `state/#`, and read its `command/#`. Collector credentials may read only `as923/gateway/+/event/#`; the two Node-RED A/B CNs may read only `application/+/device/+/event/up`. They may not publish source events or commands.

A Mosquitto SUBACK may succeed even when ACL prevents *delivery* on a forbidden topic; test unauthorized **actual message delivery** or a denied publish in a safe controlled fixture, not SUBACK alone. Do not broaden topic permission to `#` because an application has the wrong subscription string.

On S3, a valid access key grants only the approved prefix and method surface; the create-only HAProxy header/method policy remains separate. On OpenBao, server TLS success does not mean the adapter RoleID/SecretID may sign; `fabric-evidence-signer` limits Transit operations. On HRC, peer TLS success does not imply endorsement or final commit.

## 5. Issue / rotate one leaf certificate safely

1. Inventory the exact host, client-visible name, SAN, EKU, publisher/subscriber/DB role, all consumers, expiry, expected CA and current rollback trust bundle.
2. Verify existing application operation and identify whether the task is a leaf reissue or CA/trust change. Preserve existing certificate/identity until replacement acceptance; do not overwrite a private root CA key.
3. Generate/request a **new host-specific key** through the approved protected issuance workflow. Never copy Gateway-01/Node-RED A/Fabric production private identity onto another node.
4. Issue leaf certificate with **correct EKU** (`serverAuth` for server, `clientAuth` for scoped client) and service SAN/CN per actual protocol policy. Record its public serial, validity and fingerprint; not secret contents.
5. Validate CA chain, SAN/EKU, cert/key public pairing and the target runtime's actual file readability/permissions; stage replacement beside old where possible.
6. Where CA changes, establish a reviewed period where trusters recognize old+new before switching presenters, accounting for clients that cannot load multiple roots.
7. Replace **one HA member/identity at a time**; reload only services that actually need it. Verify TLS **and** MQTT topic/SQL role/S3 operation/OpenBao policy/Fabric transaction as appropriate; prove other HA members remain available.
8. After consumers migrated, revoke/remove the old leaf per controlled custody, retain audit records and verified rollback procedure. Keep old recovery material according to retention obligations rather than silently deleting evidence.

For OpenBao AppRole SecretID rotation use the **current active OpenBao member**; an earlier standby issuance hit read-only persistence failure. For Fabric identity rotation keep standby disabled until its separate writer fence/HA gate. For Gateway-01 mTLS avoid exchanging its journal upload key and MQTT key as if they were the same authority.

## 6. Backup and disaster recovery matrix

Protect as **separately recoverable sets**: CA private issuance material, public CA certificates, per-service leaf certs/keys, OpenBao recovery/unseal shares and Raft snapshot, Fabric identity and external handoff fingerprints, database SCRAM verifier/role metadata and plaintext credential custody, gateway MQTT/evidence identities, trusted client certs on Node-RED A/B and collectors, and host-specific mounted-path manifest. A `sysupgrade` archive may omit MQTT certs/local queue and does **not** capture the external OpenBao/Fabric state.

A certificate rotation/restoration PASS includes: hostname-verified transport, correct clientAuth mapping, least-privilege negative ACL, expiry/clock, actual runtime readability, representative real operation and no unexpected duplicate signer/writer authority. A public CA file checksum is not a proof that a secret backup exists. The eventual PDF may list protected **locations and operator actions**, but no passwords, unseal shares, SecretIDs, seed keys or sensitive private-key material.

Sources: [cloud PKI and host hardening](../server/cloud-production/04-host-hardening-dns-pki-and-secrets.md), [Fabric handoff](../server/integrations/hyperledger-fabric/02-fabric-network-handoff.md), [evidence deployment](../../evidence-services/cloud/deploy/README.md), [OpenBao companion](OPENBAO-HA-PKI-APPROLE-RECOVERY.md). For the final self-contained PDF include all necessary operator logic on its own pages.
