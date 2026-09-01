# Evidence Service Contracts

These contracts are language-independent. Go cloud services and the later Rust gateway implementation must produce the same identities and hashes for the same version.

Frozen/current source contracts:

- `gateway-checkpoint-v1`: logical fields remain defined by Gateway Integrity Guide 1; `evidence-ingest-api-v1` freezes its semantic checkpoint-digest bytes and monotonic acceptance rule.
- `gateway-journal-v1`: the exact typed record body, `GENESIS` predecessor token, RFC 8785 bytes, record-hash rule, and independent fixed vector are frozen in `gateway-journal-v1/README.md` and implemented by the Rust gateway crate.
- `gateway-journal-segment-v1`: canonical JSONL framing, torn-tail rule, `content_sha256`, the NUL-separated `segment_hash` preimage, complete-object SHA-256, and a two-record independent fixed vector are frozen in `gateway-journal-segment-v1/README.md` and implemented by the Rust gateway crate.
- `concentratord-uplink-correlation-v1`: exact Concentratord 4.7.1 / MQTT Forwarder 4.6.0 upstream commits, byte-identical `gw.proto`, required Protobuf tags, semantic journal↔MQTT correlation digest, and an independent synthetic wire vector are frozen in `concentratord-uplink-correlation-v1/README.md`; Rust implements the gateway decoder and Go source implements MQTT-side enrichment.
- `mqtt-capture-v1`: exact replicated-collector capture-key bytes are frozen in `mqtt-capture-v1/README.md` and implemented by Go `internal/mqttcapture`.
- `mqtt-collector-runtime-v1`: two direct physical-broker sessions, frozen TLS identity/topic namespace, dedicated authentication requirement, opaque-byte witness semantics, raw-object identity, duplicate/conflict behavior, and persistence-before-ACK ordering are frozen in `mqtt-collector-runtime-v1/README.md` and implemented by Go `internal/mqttcollector`.
- `trusted-decoder-normalized-v1`: exact Agriculture Kit payload-v2 input layout, validity handling, normalized JSON field/order contract, decoder identity, and fixed raw/normalized SHA-256 vectors are frozen in `trusted-decoder-normalized-v1/README.md` and implemented by Go `internal/trusteddecoder`.
- `evidence-ingest-api-v1`: checkpoint/segment routes, gateway identity binding, body/hash/idempotency/conflict/regression behavior, raw-store-before-metadata ordering, and HTTP outcomes are frozen in `evidence-ingest-api-v1/README.md` and implemented by Go `internal/ingest` at the handler/core boundary.
- `evidence-ingest-receipt-v1`: stable accepted identity/hash + original server-time acknowledgement bytes, exact retry behavior, independent receipt vectors, and the no-retirement safety boundary are frozen in `evidence-ingest-receipt-v1/README.md`; Go emits the receipt and Rust independently validates it.
- `verifier-runtime-v1`: v2 outbox discovery, `SKIP LOCKED` lease semantics, exact ChirpStack first-reception provenance, raw MQTT reopen/redecode, `concentratord-uplink-correlation-v1` matching, exact closed-journal parsing, full predecessor-object chain verification, checkpoint-digest recomputation, lineage persistence, stable reason codes, build-time decoder digest requirement, and the lease-fenced verifier-owned `verified` transition are frozen in `verifier-runtime-v1/README.md` and implemented by Go `internal/verifier`.

Still intentionally unresolved rather than guessed:

- one real captured Concentratord 4.7.1 `gw.Event` plus the corresponding MQTT Forwarder 4.6.0 `event/up` witness to prove the frozen synthetic correlation contract against physical runtime bytes;
- the Gateway OS/OpenWrt target build/package/service installation for the implemented Rust writer/uploader, including target-native `concentratord-zmq` and physical filesystem/IPC behavior. `evidence-ingest-receipt-v1` is frozen and deletion/retirement remains intentionally absent;
- one live verifier-owned `status='verified'` row. The cloud replicas and authority path are commissioned, but a real verified row still waits for one complete physical-gateway journal/MQTT/application lineage;
- the public ChirpStack/Evidence/MQTT normal path is commissioned; the remaining provider-owned item is Reserved-IP reassignment/failover authority and controlled acceptance;
- one real external Fabric handoff/transaction. The immutable disabled adapter standbys and v1/v2 RFC 8785 canonicalization vectors are already commissioned/frozen.

A version identifier must never be retained if its byte-level or security contract changes.
