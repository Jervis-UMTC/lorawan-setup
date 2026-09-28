# PKI / TLS / Service Identity — Operator Manual

## What this technology does

PKI, TLS, mTLS, and workload identities define who a service is allowed to talk to and what identity is presented across the transport boundary.

Network reachability is not authorization. A TCP connection that succeeds while certificate validation, mTLS, or application ACLs are bypassed is not a healthy recovery.

## Current trust purposes

The deployment separates certificate purposes where operationally practical:

```text
public/service HTTPS identity
Gateway MQTT CA and per-gateway client identity
Gateway evidence upload PKI
PostgreSQL / PgBouncer trust
Valkey service trust
OpenBao internal KMS trust
SeaweedFS evidence-object-store internal trust
Fabric Gateway server trust + dedicated Fabric application identity
```

The current etcd cluster remains a documented private-HTTP POC exception. Do not copy that exception to other services.

## Important current paths

Common protected locations include:

```text
/etc/lorawan-pki/postgres/
/etc/lorawan-pki/pgbouncer/
/etc/lorawan-pki/mqtt/
/etc/lorawan-pki/valkey/
/etc/lorawan-pki/openbao/
/etc/lorawan-pki/gateway-evidence/
/etc/lorawan-pki/evidence-objectstore/
/etc/lorawan-pki/fabric/
```

The exact consumer and mode vary by service. Never loosen a private key to world-readable just because a container cannot open it.

## Security hard stops

Never solve a TLS problem by permanently using:

```text
curl -k
tls_skip_verify
verify none
globally replacing verify-full with sslmode=require (or vice versa) without checking the **specific** client parser, CA and server-identity verification contract
hostname verification disabled
shared administrator identity for an application worker
copying one gateway/node private key to another
printing private keys, passwords, SecretIDs, tokens, or unrestricted DSNs
```

Fix the trust chain, SAN/name, time, permissions, client identity, or ACL at the layer that actually failed.

## Step 1 — Inventory certificates without printing private keys

Run on the affected host:

```bash
sudo find /etc/lorawan-pki -type f   \( -name '*.crt' -o -name '*.pem' \)   -printf '%M %u:%g %p\n' 2>/dev/null | sort
```

Then inspect only the certificate required by the failing service:

```bash
openssl x509 -in /path/to/certificate.crt   -noout -subject -issuer -serial -dates -fingerprint -sha256   -ext subjectAltName -ext extendedKeyUsage
```

**PASS means:** issuer, SAN, key usage, and validity window match the intended service/client role.

## Step 2 — Check clock before diagnosing certificate dates

```bash
date -u
timedatectl status
```

A host clock outside the certificate validity window can look like a PKI failure. Correct time synchronization rather than reissuing good certificates blindly.

## Step 3 — Verify hostname/SAN against the name clients use

Examples of commissioned logical names include:

```text
mqtt.internal.lorawan.com
pgbouncer.internal.lorawan.com
openbao-kms.internal.lorawan.com
evidence-objects.internal.lorawan.com
peer1.hrc.local
```

Inspect SANs:

```bash
openssl x509 -in /path/to/server.crt -noout -ext subjectAltName
```

The client-visible name must be present. Do not “fix” a mismatch by switching the client to an unrelated IP name if that bypasses the commissioned service identity.

## Step 4 — Verify a server TLS endpoint

Generic pattern:

```bash
openssl s_client   -connect '<HOST>:<PORT>'   -servername '<EXPECTED_TLS_NAME>'   -verify_hostname '<EXPECTED_TLS_NAME>'   -verify_return_error   -CAfile '/path/to/ca.crt'   </dev/null
```

Require:

```text
Verify return code: 0 (ok)
```

This proves server-auth TLS only. It does not prove application authorization or client mTLS unless a client identity is also presented.

## Step 5 — Verify certificate/private-key pairing without revealing the key

```bash
CERT_PUB="$(
  openssl x509 -in /path/to/client.crt -pubkey -noout |
  openssl pkey -pubin -outform DER |
  sha256sum | awk '{print $1}'
)"

KEY_PUB="$(
  openssl pkey -in /path/to/client.key -pubout -outform DER |
  sha256sum | awk '{print $1}'
)"

printf 'certificate_public_key_sha256=%s\n' "$CERT_PUB"
printf 'private_key_public_key_sha256=%s\n' "$KEY_PUB"
test "$CERT_PUB" = "$KEY_PUB"
```

**PASS means:** the public keys match. The private key body is never printed.

## Step 6 — Check ownership and mode

```bash
sudo stat -c '%U:%G %a %n' /path/to/ca.crt /path/to/client.crt /path/to/client.key
```

For evidence/Fabric containers, protected private keys are normally mounted for numeric runtime GID `65532` with restrictive read-only permissions; public CAs/certificates must be readable by the runtime but not writable by untrusted users.

Use the owning component's preflight as the authority for exact required mode.

## Step 7 — Verify the client-auth boundary separately

mTLS failures have two halves:

```text
client verifies server
server verifies client
```

For gateway MQTT, evidence upload, and collector broker identities, also verify:

- the client certificate chains to the expected client CA;
- Extended Key Usage permits client authentication;
- certificate identity maps to the intended workload or Gateway EUI;
- broker/API ACL grants only the intended topic/resource;
- an unrelated identity is rejected.

A valid certificate with an over-broad ACL is still a security defect.

## Step 8 — Preserve service-identity separation

Current examples:

```text
Gateway MQTT identity        -> gateway publish permissions only
Evidence-upload identity     -> one Gateway EUI upload authority
Collector identities         -> read as923/gateway/+/event/# only
Node-RED identity            -> application event subscription only
Verifier identity            -> verifier DB/object-read authority; no signing
Fabric adapter identity      -> dedicated OpenBao/Fabric authority
Grafana identity             -> read-only telemetry/evidence DB
```

Do not reuse a powerful identity across roles merely to reduce certificate count.

## Step 9 — Check certificate expiry

For one certificate:

```bash
openssl x509 -in /path/to/certificate.crt -noout -enddate
openssl x509 -in /path/to/certificate.crt -checkend $((30*24*60*60)) -noout   && echo 'EXPIRY_30D=PASS'   || echo 'EXPIRY_30D=RENEW_REQUIRED'
```

Keep certificate-expiry monitoring active. Do not wait for production TLS failure to discover expiration.

## Safe certificate rotation procedure

1. Identify every consumer of the certificate/CA/identity.
2. Prove the existing path is healthy before changing it.
3. Issue the replacement with the exact required SAN/EKU/purpose.
4. Verify the new cert/key pair offline.
5. Install it with correct owner/mode beside the current material.
6. If a CA changes, establish an overlap/trust-roll procedure where supported.
7. Rotate one service/member at a time.
8. Validate TLS/mTLS and application authorization.
9. Verify one representative real operation.
10. Revoke/remove the old identity only after every intended consumer has moved.

Do not rotate all HA members at once if one-at-a-time overlap is possible.

## CA rotation rule

A CA change is more disruptive than a leaf-certificate renewal because both trusters and presenters may need an overlap period.

Before rotating a CA, list every issued service/client identity and trust-store mount, identify clients that cannot trust old+new simultaneously, define rollback, and preserve revocation/incident records.

Never replace a root CA on one side only and then disable verification to restore service.

## Fabric-specific identity rule

The LoRaWAN Fabric adapter uses the HRC Gateway TLS root and a dedicated least-privilege client identity. It must not use HRC administrator material or unrelated benchmark identities.

The activation preflight verifies the Fabric TLS root fingerprint, `peer1.hrc.local` hostname, client certificate/private-key pairing, least-privilege identity class, and exact HRC Task 37 channel/chaincode/function contract.

Use the Fabric Adapter manual for that governed gate.

## OpenBao-specific identity rule

OpenBao server TLS is separate from the adapter's AppRole authentication. A passing TLS handshake proves the KMS endpoint identity; it does not prove RoleID/SecretID validity or Transit policy.

Do not broaden TLS trust or Transit policy to compensate for an expired/invalid AppRole SecretID.

## Gateway/evidence identity rule

Gateway MQTT and gateway evidence upload are separate trust purposes. Both must map unambiguously to the intended gateway, but one identity should not automatically grant the other's permissions.

For Gateway-01, certificate/ACL changes must preserve the commissioned Gateway EUI and plain AS923 data path.

## Troubleshooting map

| Symptom | First check |
|---|---|
| certificate expired/not-yet-valid | host clock + certificate dates |
| hostname mismatch | client name vs SAN; issue correct cert/name |
| unknown CA | correct trust chain/mounted CA |
| private key unreadable | owner/GID/mode/runtime UID |
| certificate/key mismatch | public-key hash comparison |
| server TLS passes, app says unauthorized | client identity/application ACL |
| mTLS client rejected | client chain/EKU/identity mapping |
| one HA node fails only | node-specific cert/SAN/path drift |
| rotating cert breaks peer | overlap/trust-store sequencing |
| Fabric TLS passes but submit fails | application identity/contract/Fabric layer |

## Completion checklist

- certificate chain and SAN match the name clients use;
- certificate validity and host time are correct;
- private keys have restrictive ownership/mode;
- certificate/private-key pairs match;
- TLS hostname verification is enabled;
- mTLS identities map to the intended workload/resource;
- least-privilege ACLs remain intact;
- no shared administrator identity has replaced a service identity;
- expiry monitoring/rotation procedure is known;
- representative authenticated operations pass after any rotation.

## Complete PKI issuance, trust and rotation companion

Use [PKI/TLS service identity inventory, strict trust, client-specific PostgreSQL SSL modes, private-key custody and safe rotation](PKI-TRUST-IDENTITY-ROTATION-RECOVERY.md). ChirpStack's pinned core Rust DSN `sslmode=require` with separate CA configuration is an important exception to generic libpq/PgBouncer `verify-full`; do not apply broad string replacements across services.

## Detailed references

- [`../server/cloud-production/04-host-hardening-dns-pki-and-secrets.md`](../server/cloud-production/04-host-hardening-dns-pki-and-secrets.md)
- [`../server/cloud-production/08-mqtt-and-valkey.md`](../server/cloud-production/08-mqtt-and-valkey.md)
- [`../../evidence-services/cloud/deploy/README.md`](../../evidence-services/cloud/deploy/README.md)
- [`../server/integrations/hyperledger-fabric/02-fabric-network-handoff.md`](../server/integrations/hyperledger-fabric/02-fabric-network-handoff.md)
