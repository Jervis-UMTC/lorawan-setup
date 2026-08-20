# Fabric 1. Collect the External Fabric Handoff

## Goal

Collect and verify everything the adapter needs to connect to the Fabric network operated by the other team.

Do **not** create a Fabric VM, organization, peer, orderer, CA, channel, chaincode deployment, or Fabric test network.

## Before you start

The Fabric team must have an existing staging or integration endpoint available for this work.

Create a protected client directory on the **LoRaWAN lab server VM**:

```bash
sudo install -d -m 700 /opt/fabric-adapter/crypto
sudo install -d -m 700 /opt/fabric-adapter/crypto/identity
sudo install -d -m 700 /opt/fabric-adapter/crypto/tls
```

## Step 1 - Request the connection values

Ask the Fabric team for:

```text
Fabric Gateway endpoint: <FABRIC_GATEWAY_ENDPOINT>
MSP ID: <FABRIC_MSP_ID>
Channel: <FABRIC_CHANNEL_NAME>
Chaincode: <FABRIC_CHAINCODE_NAME>
TLS server name: <FABRIC_TLS_SERVER_NAME>
Submit function: <FABRIC_SUBMIT_FUNCTION>
Submit argument contract: schema_version, event_key, event_type, digest, seal_algorithm, seal_key_id, seal_signature
Query function: <FABRIC_QUERY_FUNCTION>
Contract/schema version: <FABRIC_CONTRACT_VERSION>
Endorsement requirements: <FABRIC_ENDORSEMENT_REQUIREMENTS>
Commit timeout/behavior: <FABRIC_COMMIT_BEHAVIOR>
Rate limit: <FABRIC_RATE_LIMIT>
Maintenance window: <FABRIC_MAINTENANCE_WINDOW>
Support contact: <FABRIC_SUPPORT_CONTACT>
```

Do not substitute example values such as `Org1MSP`, `mychannel`, `basic`, or `peer0.org1.example.com` unless the Fabric team explicitly supplied those exact values. Also require the Fabric team to confirm whether the submit function accepts the seven dissertation attestation values as positional strings or as one structured object. Do not begin adapter implementation while the argument order, accepted schema versions, duplicate-key behavior, and commit-status behavior are still ambiguous.

## Step 2 - Obtain the client identity files securely

The Fabric team must provide or provision:

```text
<FABRIC_CA_CERT>
<FABRIC_CLIENT_CERT>
<FABRIC_CLIENT_KEY>
```

Transfer them using the approved protected channel. Do not paste the private key into chat, Git, Node-RED, Grafana, or a Markdown file.

Install them on the lab server as:

```bash
sudo install -m 0644 <FABRIC_CA_CERT> \
  /opt/fabric-adapter/crypto/tls/ca.crt
sudo install -m 0644 <FABRIC_CLIENT_CERT> \
  /opt/fabric-adapter/crypto/identity/cert.pem
sudo install -m 0600 <FABRIC_CLIENT_KEY> \
  /opt/fabric-adapter/crypto/identity/key.pem
```

Verify permissions without printing file contents:

```bash
sudo find /opt/fabric-adapter/crypto -maxdepth 3 -printf '%m %u:%g %p\n'
```

## Step 3 - Verify the certificate/key pair

Run on the lab server:

```bash
CERT_PUB=$(openssl x509 \
  -in /opt/fabric-adapter/crypto/identity/cert.pem \
  -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum)

KEY_PUB=$(sudo openssl pkey \
  -in /opt/fabric-adapter/crypto/identity/key.pem \
  -pubout -outform DER | sha256sum)

printf 'certificate: %s\nkey:         %s\n' "$CERT_PUB" "$KEY_PUB"
unset CERT_PUB KEY_PUB
```

The hashes must match.

Inspect the public certificate metadata:

```bash
openssl x509 \
  -in /opt/fabric-adapter/crypto/identity/cert.pem \
  -noout -subject -issuer -serial -dates -fingerprint -sha256
```

Record only the non-secret fingerprint, serial, issuer, expiry, MSP ID, and secure storage reference.

## Step 4 - Verify DNS and TCP reachability

Resolve the hostname from `<FABRIC_GATEWAY_ENDPOINT>` and test the supplied port:

```bash
getent ahosts <FABRIC_GATEWAY_HOST>
nc -vz <FABRIC_GATEWAY_HOST> <FABRIC_GATEWAY_PORT>
```

A successful TCP connection proves only network reachability. It does not prove TLS identity, MSP authorization, channel access, endorsement, or chaincode behavior.

## Step 5 - Verify TLS server identity

When the Gateway endpoint exposes TLS directly, use the supplied CA and TLS server name:

```bash
openssl s_client \
  -connect <FABRIC_GATEWAY_HOST>:<FABRIC_GATEWAY_PORT> \
  -servername <FABRIC_TLS_SERVER_NAME> \
  -CAfile /opt/fabric-adapter/crypto/tls/ca.crt \
  -verify_return_error </dev/null
```

Pass only when the chain validates and the endpoint certificate is valid for `<FABRIC_TLS_SERVER_NAME>`.

Do not disable hostname verification to make a mismatched endpoint work.

## Step 6 - Confirm the application contract

Before deploying the adapter, obtain one read-only/evaluate operation that proves the channel and chaincode contract. Prefer an operation equivalent to:

```text
GetContractVersion
ReadAttestation <NON_EXISTENT_OR_KNOWN_TEST_EVENT_KEY>
```

The exact function names must come from the Fabric team.

Confirm:

- `<FABRIC_MSP_ID>` is authorized for the intended operation;
- `<FABRIC_CHANNEL_NAME>` exists and is accessible;
- `<FABRIC_CHAINCODE_NAME>` resolves;
- the contract/schema version is the one expected by the adapter;
- duplicate event behavior is documented;
- commit-status behavior is documented.

## Step 7 - Create the local handoff record

Keep a non-secret record outside Git or in the approved operations inventory:

```text
Environment:
Fabric Gateway endpoint:
TLS server name:
MSP ID:
Channel:
Chaincode:
Submit function:
Query function:
Contract/schema version:
Endorsement requirements:
Client certificate serial:
Client certificate SHA-256 fingerprint:
Client certificate expiry:
Secure private-key location:
Rotation contact:
Support contact:
```

## Verify

Do not continue until:

- the endpoint is reachable;
- TLS validates against the supplied CA and server name;
- certificate and key match;
- MSP/channel/chaincode/function names came from the Fabric team;
- a read-only contract call is available for adapter validation;
- retry, duplicate, endorsement, and commit semantics are documented.

## Next step

Continue with [01-deploy-openbao-kms.md](01-deploy-openbao-kms.md). After the KMS passes its sign/verify tests, continue with [02-create-outbox-and-adapter.md](02-create-outbox-and-adapter.md).
