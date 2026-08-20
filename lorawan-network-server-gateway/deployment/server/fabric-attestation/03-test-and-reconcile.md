# Fabric 3. Test Commits, Failures, and Reconciliation

Run these tests only after a real telemetry uplink is stored and the telemetry database backup is readable.

## Test 1: Verify the contract before submission

From the adapter or an approved Fabric sample application, evaluate `GetContractVersion` and `ReadAttestation` against the Fabric Gateway.

Pass condition:

- TLS validates the Org1 peer;
- the client identity belongs to the expected MSP;
- the channel and chaincode resolve;
- the returned contract version/support list includes the schema being tested. Keep the executable compatibility test on `telemetry-attestation-v1` until the v2 verifier implementation and separate canonicalization vector are reviewed.

## Test 2: Queue one selected uplink

Trigger one approved test-device uplink or sanitized Inject-node event with the Fabric policy enabled.

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT outbox_id,event_key,status,attempts,created_at FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 10;"
```

Pass condition: one new row appears as `pending`. Replaying the same source event does not create another outbox row.

For a v2-specific test, also query the matching gateway verification row and prove it is already `verified` before expecting the adapter to claim the outbox item.

## Test 2A: Prove the v2 gateway-evidence gate

Run this test only after the reviewed gateway-integrity implementation and v2 canonicalization vector exist.

Use isolated staging fixtures/events for each state:

```text
pending
evidence_gap
integrity_failure
verified
```

Pass when:

- `pending` v2 work is not claimed or sealed;
- `evidence_gap` follows the documented gap policy and is never presented as verified;
- `integrity_failure` enters the security-conflict/dead-letter procedure without an OpenBao sign request;
- only `verified` becomes eligible for the normal adapter seal/submit path;
- Node-RED and the adapter cannot update the verification row to make the test pass.

For the `verified` case, preserve the verification ID, journal record/segment hashes, checkpoint ID, captured gateway-event ID, trusted decoder ID/version, raw application-data digest, and normalized-result digest as acceptance evidence.

## Test 2B: Prove gateway-integrity negative cases block v2

Using copied or isolated fixtures described in [Gateway Integrity Testing](../integrations/gateway-integrity/03-testing-monitoring-and-limitations.md), prove at least:

1. one-byte journal change;
2. deleted/reordered journal record;
3. checkpoint rollback/conflict;
4. journal PHYPayload vs remote gateway MQTT PHYPayload mismatch;
5. trusted decoder vs Node-RED/TimescaleDB normalized-value mismatch.

Pass when none of these cases can produce a newly sealed `telemetry-attestation-v2` row.

## Test 3: Confirm a real Fabric commit

Watch the adapter:

```bash
docker compose logs -f --tail=100 fabric-adapter
```

Then query:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,status,digest_sha256,fabric_tx_id,submitted_at,committed_at,last_error_category FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 10;"
```

Pass condition:

- status becomes `confirmed`;
- `canonical_json` is non-null;
- `digest_sha256` contains exactly 64 lowercase hexadecimal characters;
- `evidence_signature_alg` is exactly `OPENBAO-TRANSIT-ECDSA-P256-SHA2-256`;
- `evidence_signing_key_id` has the form `openbao:transit:lorawan-evidence:v<positive-version>`;
- `evidence_signature` contains the complete OpenBao versioned signature, not only its Base64 tail;
- `evidence_sealed_at` is populated before or at `submitted_at`;
- `fabric_tx_id` is recorded;
- `committed_at` is after `submitted_at`;
- querying Fabric by event key returns the same digest and expected seal metadata.

A transaction ID without valid commit status is not a pass.

## Test 4: Verify the exact persisted evidence seal

This test proves that the bytes preserved in PostgreSQL still produce the recorded digest and still verify through the historical OpenBao Transit key version recorded in the seal. Perform it on one confirmed staging event.

Set the event key in the shell first:

```bash
export TEST_EVENT_KEY='<TEST_EVENT_KEY>'
umask 077
```

Export the stored RFC 8785 canonical JSON. `psql -At` adds one output line terminator, so strip that transport newline. JCS itself produces compact JSON with no formatting newlines; newline characters inside JSON strings are escaped and are not removed by this command.

```bash
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -v event_key="$TEST_EVENT_KEY" \
  -c "SELECT canonical_json FROM telemetry.fabric_outbox WHERE event_key=:'event_key'" \
  | tr -d '\n' > /tmp/fabric-canonical.json

test -s /tmp/fabric-canonical.json
```

Export the stored digest, algorithm, KMS key ID, and complete OpenBao versioned signature:

```bash
STORED_DIGEST="$(docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -v event_key="$TEST_EVENT_KEY" \
  -c "SELECT digest_sha256 FROM telemetry.fabric_outbox WHERE event_key=:'event_key'" \
  | tr -d '\n')"

STORED_ALG="$(docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -v event_key="$TEST_EVENT_KEY" \
  -c "SELECT evidence_signature_alg FROM telemetry.fabric_outbox WHERE event_key=:'event_key'" \
  | tr -d '\n')"

STORED_KEY_ID="$(docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -v event_key="$TEST_EVENT_KEY" \
  -c "SELECT evidence_signing_key_id FROM telemetry.fabric_outbox WHERE event_key=:'event_key'" \
  | tr -d '\n')"

STORED_SIGNATURE="$(docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -v event_key="$TEST_EVENT_KEY" \
  -c "SELECT evidence_signature FROM telemetry.fabric_outbox WHERE event_key=:'event_key'" \
  | tr -d '\n')"
test -n "$STORED_SIGNATURE"
```

Calculate the digest from the exact exported canonical bytes and compare it:

```bash
LOCAL_DIGEST="$(sha256sum /tmp/fabric-canonical.json | awk '{print $1}')"
printf 'stored digest: %s\nlocal  digest: %s\n' "$STORED_DIGEST" "$LOCAL_DIGEST"
test "$LOCAL_DIGEST" = "$STORED_DIGEST"
test "$STORED_ALG" = 'OPENBAO-TRANSIT-ECDSA-P256-SHA2-256'
```

Bind the OpenBao signature's embedded key version to the stored KMS key ID:

```bash
SIGNATURE_VERSION="$(printf '%s' "$STORED_SIGNATURE" \
  | sed -n 's/^[^:]*:v\([1-9][0-9]*\):.*/\1/p')"
test -n "$SIGNATURE_VERSION"
EXPECTED_KEY_ID="openbao:${OPENBAO_TRANSIT_MOUNT:-transit}:${OPENBAO_TRANSIT_KEY:-lorawan-evidence}:v${SIGNATURE_VERSION}"
printf 'stored key ID:   %s\nexpected key ID: %s\n' "$STORED_KEY_ID" "$EXPECTED_KEY_ID"
test "$STORED_KEY_ID" = "$EXPECTED_KEY_ID"
```

Verify the signature through OpenBao using the **same canonical bytes**. The AppRole credentials are piped on standard input so they are not written into the shell command line:

```bash
INPUT_B64="$(base64 -w0 /tmp/fabric-canonical.json)"
VERIFY_RESULT="$(
  {
    sudo cat /opt/lorawan-lab/secrets/openbao-approle/role_id
    sudo cat /opt/lorawan-lab/secrets/openbao-approle/secret_id
    printf '%s\n' "$INPUT_B64"
    printf '%s\n' "$STORED_SIGNATURE"
  } | docker compose exec -T \
        -e BAO_ADDR=http://127.0.0.1:8200 \
        openbao sh -lc '
          IFS= read -r ROLE_ID
          IFS= read -r SECRET_ID
          IFS= read -r INPUT_B64
          IFS= read -r SIGNATURE
          export BAO_TOKEN="$(bao write -field=token auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"
          bao write -field=valid transit/verify/lorawan-evidence/sha2-256 \
            input="$INPUT_B64" signature="$SIGNATURE" \
            prehashed=false marshaling_algorithm=asn1
          unset BAO_TOKEN ROLE_ID SECRET_ID INPUT_B64 SIGNATURE
        ' | tr -d '\r\n'
)"
printf 'OpenBao exact-byte verification: %s\n' "$VERIFY_RESULT"
test "$VERIFY_RESULT" = 'true'
```

**Stop the Fabric acceptance test** if the digest, algorithm, key-version binding, or OpenBao verification fails. Do not repair the row by recalculating its digest or asking OpenBao for a replacement signature.

Now prove that even a one-byte change is detected without touching PostgreSQL:

```bash
cp /tmp/fabric-canonical.json /tmp/fabric-canonical-tampered.json
printf ' ' >> /tmp/fabric-canonical-tampered.json
TAMPERED_B64="$(base64 -w0 /tmp/fabric-canonical-tampered.json)"

TAMPERED_RESULT="$(
  {
    sudo cat /opt/lorawan-lab/secrets/openbao-approle/role_id
    sudo cat /opt/lorawan-lab/secrets/openbao-approle/secret_id
    printf '%s\n' "$TAMPERED_B64"
    printf '%s\n' "$STORED_SIGNATURE"
  } | docker compose exec -T \
        -e BAO_ADDR=http://127.0.0.1:8200 \
        openbao sh -lc '
          IFS= read -r ROLE_ID
          IFS= read -r SECRET_ID
          IFS= read -r INPUT_B64
          IFS= read -r SIGNATURE
          export BAO_TOKEN="$(bao write -field=token auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"
          bao write -field=valid transit/verify/lorawan-evidence/sha2-256 \
            input="$INPUT_B64" signature="$SIGNATURE" \
            prehashed=false marshaling_algorithm=asn1
          unset BAO_TOKEN ROLE_ID SECRET_ID INPUT_B64 SIGNATURE
        ' | tr -d '\r\n'
)"
printf 'OpenBao tampered-byte verification: %s\n' "$TAMPERED_RESULT"
test "$TAMPERED_RESULT" = 'false'

rm -f /tmp/fabric-canonical.json /tmp/fabric-canonical-tampered.json
unset STORED_DIGEST STORED_ALG STORED_KEY_ID STORED_SIGNATURE LOCAL_DIGEST \
  SIGNATURE_VERSION EXPECTED_KEY_ID INPUT_B64 TAMPERED_B64 VERIFY_RESULT TAMPERED_RESULT
```

If the pinned OpenBao image has no POSIX shell, run the same AppRole login and Transit verify calls from a reviewed utility container attached only to `lorawan-lab_kms`; do not publish port 8200 to the host merely to run this test.

The negative test changes only a temporary copy. Never alter a real outbox row merely to demonstrate tamper detection.

## Test 5: Stop Fabric and prove the evidence seal does not change

Coordinate a staging outage with the Fabric team, or temporarily block only the `fabric-adapter` container's route to `<FABRIC_GATEWAY_ENDPOINT>`. Do not stop or modify Fabric infrastructure that your team does not own. Then send one selected test uplink and allow the adapter to create its local evidence seal while Fabric is unreachable.

Identify its stable event key and capture the seal before recovery:

```bash
export TEST_EVENT_KEY='<OUTAGE_TEST_EVENT_KEY>'

docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -v event_key="$TEST_EVENT_KEY" \
  -c "SELECT digest_sha256 || '|' || evidence_signing_key_id || '|' || evidence_signature FROM telemetry.fabric_outbox WHERE event_key=:'event_key'" \
  | tr -d '\n' > /tmp/fabric-seal-before.txt

test -s /tmp/fabric-seal-before.txt
```

Pass condition while Fabric is unavailable:

- Node-RED continues storing telemetry;
- the selected outbox row has a complete evidence seal before any successful Fabric commit;
- jobs remain `pending`, `failed`, or `submitted_unknown` according to the failure point;
- no telemetry row is marked invalid merely because Fabric is unavailable;
- the adapter backs off instead of retrying continuously.

Restore the adapter's Fabric route and allow the row to reconcile or retry. Capture the same fields again:

```bash
docker compose exec -T telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry -At \
  -v event_key="$TEST_EVENT_KEY" \
  -c "SELECT digest_sha256 || '|' || evidence_signing_key_id || '|' || evidence_signature FROM telemetry.fabric_outbox WHERE event_key=:'event_key'" \
  | tr -d '\n' > /tmp/fabric-seal-after.txt

diff -u /tmp/fabric-seal-before.txt /tmp/fabric-seal-after.txt
rm -f /tmp/fabric-seal-before.txt /tmp/fabric-seal-after.txt
```

`diff` must produce no output. The queue should drain without duplicate ledger state. Any changed digest, key ID, or signature means the adapter resealed or rewrote evidence during retry and the test fails.

## Test 6: Seal OpenBao and prove telemetry continues

This is a separate failure from a Fabric outage. The expected result is that telemetry ingestion continues while the Fabric adapter fails closed because it cannot create or verify evidence seals.

First confirm OpenBao is healthy and unsealed:

```bash
docker compose exec \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  openbao bao status
```

Then restart OpenBao. In this Shamir-sealed lab, a restart intentionally returns the KMS to a sealed state:

```bash
docker compose restart openbao
docker compose exec \
  -e BAO_ADDR=http://127.0.0.1:8200 \
  openbao bao status
```

Required state: `Initialized` is true and `Sealed` is true.

While OpenBao is sealed, generate one new Fabric-selected test uplink. Verify the normal telemetry row is still stored, then inspect the outbox:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,status,canonical_json IS NOT NULL AS sealed,digest_sha256,evidence_signing_key_id,fabric_tx_id,last_error_category FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 10;"

docker compose logs --since=5m --tail=200 fabric-adapter openbao node-red
```

Pass while KMS is sealed:

- MQTT, ChirpStack, Node-RED, and TimescaleDB continue processing normal telemetry;
- a newly selected event cannot obtain a new evidence signature and therefore cannot reach a valid Fabric submission;
- an already sealed row is not submitted/retried when the adapter cannot complete the required OpenBao verification;
- the adapter classifies the KMS condition as retryable infrastructure unavailability, releases its processing lease correctly, and uses bounded backoff;
- no code falls back to a local PEM key, unsigned digest, skipped verification, or direct Fabric submission.

Recover OpenBao by entering two different unseal shares at the hidden prompts:

```bash
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao operator unseal
docker compose exec -e BAO_ADDR=http://127.0.0.1:8200 openbao bao status
```

Do not pass shares on the command line and do not copy them from the protected recovery record into a shell variable.

After `Sealed` becomes false, let the adapter retry. Pass recovery only when the event receives one complete OpenBao seal, that seal passes Test 4, and the normal Fabric path resumes without duplicate ledger state.

## Test 7: Duplicate and unknown-commit behavior

Submit the same event key and digest again.

Pass condition: the chaincode returns the existing matching attestation or rejects the duplicate in a documented idempotent way.

Simulate a client timeout after submission. The adapter must set `submitted_unknown`, query the ledger, and only retry when the stable event key is absent.

A duplicate key with a different digest must become a conflict requiring operator review.

## Test 8: Recover an expired processing lease

Use a reviewed test-only pause or failure-injection hook that stops the adapter immediately after the database claim and before Fabric submission. When the adapter has no such hook, block only its route to `<FABRIC_GATEWAY_ENDPOINT>`, observe the row enter `processing`, then stop the adapter. Do not rely on racing a normal fast submission.

Do not edit the row immediately. Wait until the configured lease expiry, restore the blocked route when used, restart the adapter, and inspect:

```bash
docker compose exec telemetry-db \
  psql -U telemetry_admin -d lorawan_telemetry \
  -c "SELECT event_key,status,worker_id,processing_started_at,lease_expires_at,attempts FROM telemetry.fabric_outbox ORDER BY outbox_id DESC LIMIT 10;"
```

Pass condition:

- the abandoned row is not reclaimed before `lease_expires_at`;
- it becomes eligible after lease expiry;
- a new claim increments `attempts` and records the current worker;
- no duplicate ledger state is created;
- `submitted_unknown` rows remain outside the normal retry path.

## Test 9: Prove a completed database seal cannot be replaced normally

Use the confirmed staging event from Test 3. This command deliberately attempts to change its canonical evidence, but the transaction is expected to fail at the immutability trigger.

```bash
export TEST_EVENT_KEY='<TEST_EVENT_KEY>'

if docker compose exec -T telemetry-db \
  psql -v ON_ERROR_STOP=1 -U telemetry_admin -d lorawan_telemetry \
  -v event_key="$TEST_EVENT_KEY" <<'SQL'
BEGIN;
UPDATE telemetry.fabric_outbox
SET canonical_json = canonical_json || ' '
WHERE event_key = :'event_key';
ROLLBACK;
SQL
then
  echo 'FAIL: completed evidence seal was mutable'
  exit 1
else
  echo 'PASS: one-way evidence-seal trigger rejected the update'
fi
```

Pass condition: PostgreSQL reports the `fabric outbox evidence seal is immutable` exception and the shell prints the PASS line. Re-query the row afterward and run Test 4 again; its digest and signature must still verify.

This test uses `telemetry_admin` only to prove that the trigger is installed and firing in the normal database path. A PostgreSQL superuser can deliberately disable/bypass database controls; this test is not evidence against malicious database-superuser or host-root access.

## Test 10: Reject a locally invalid seal before Fabric

This is an application-level negative test. Use the adapter's reviewed test fixture or isolated test database, not the live staging evidence row. Present a sealed fixture whose canonical bytes, digest, or signature has been modified after signing.

Pass condition:

- the adapter rejects the fixture before opening/submitting a Fabric transaction;
- the result is categorized as a permanent local integrity/security error;
- the test record is preserved for diagnosis or moved to the configured dead-letter/security-conflict path;
- the adapter does not regenerate the seal from mutable source telemetry;
- no Fabric transaction ID is created for the invalid fixture.

If the adapter has no automated fixture for this behavior, **stop deployment and add one**. The direct OpenBao Transit negative test proves the KMS rejects changed bytes, but this test proves the adapter actually enforces that result before Fabric.

## Test 11: Grafana visibility

Verify the dashboard shows:

- pending, processing, confirmed, failed, submitted_unknown, and dead-letter counts;
- oldest pending age and expired processing leases;
- commit latency;
- latest error category;
- telemetry freshness independent of Fabric status.

Grafana is an operational view, not proof of ledger correctness. Keep the database query, Fabric query, digest comparison, and transaction ID as acceptance evidence.

## Final acceptance

The simulation passes only when:

- a real uplink is stored and visualized;
- one selected event is committed to Fabric;
- the locally stored canonical evidence recomputes to the stored digest;
- the complete OpenBao signature's key version matches the stored KMS key ID and Transit returns `valid=true` for the exact canonical bytes;
- a one-byte evidence change causes Transit verification to return `valid=false`;
- the one-way database trigger rejects replacement of a completed seal;
- Fabric outage does not change an already-created digest/signature seal;
- the adapter rejects an invalid local seal before contacting Fabric;
- the ledger digest matches the verified canonical off-chain evidence;
- when v2 is enabled, the sealed canonical evidence contains the exact verifier-owned gateway-evidence references and the event was `verified` before `evidence_sealed_at`;
- replay is idempotent;
- Fabric outage does not block telemetry;
- OpenBao sealed/unavailable state does not block telemetry and never causes KMS verification to be bypassed;
- recovery after OpenBao unseal creates/verifies the normal seal and drains eligible work;
- recovery drains the queue;
- a crashed worker is recovered through lease expiry;
- invalid identity or TLS fails closed;
- Grafana exposes queue delay and failures;
- when v2 is enabled, dashboards/queries distinguish gateway-evidence pending, gap, integrity failure, and verified states;
- credentials and private keys remain outside flows, dashboards, logs, and Git.
