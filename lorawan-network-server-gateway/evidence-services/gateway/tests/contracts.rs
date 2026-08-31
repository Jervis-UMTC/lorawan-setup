use gateway_evidence::{
    canonical_bytes, recover_open_segment, verify_closed_segment, CheckpointRequest,
    ConcentratordUplink, IngestReceipt, JournalState, RecordBody, RecordEnvelope, SegmentBuilder,
    SegmentHeader, SegmentUploadRequest, UploadReceiptState, CORRELATION_VERSION, GENESIS,
    GW_PROTO_SHA256, JOURNAL_VERSION, RECEIPT_VERSION, SEGMENT_VERSION, SOURCE_CONCENTRATORD,
};

const FIXTURE_RECORD1_SHA256: &str =
    "443014973b6eab5a01b75f9715470cffdabb05318ac19620c60c5b20fe0e4823";
const FIXTURE_RECORD2_SHA256: &str =
    "0fbfe1314ab5a7c779ff4872048a02dffa77b2c9c97826f1a62bedf6a070297f";
const FIXTURE_CONTENT_SHA256: &str =
    "48f043a5b36df29eeac3848331aac65258a3c31866667982341386f306e67d4e";
const FIXTURE_SEGMENT_SHA256: &str =
    "722638f91ff762185aff7c002044911226661c0efc8b70ce71b22a7f168bae90";
const FIXTURE_OBJECT_SHA256: &str =
    "9f34ad301bc0b1b806e2cb0c39a4baaa7509e79b8822f7f367a08720835403f1";
const FIXTURE_CHECKPOINT_DIGEST: &str =
    "3f7cc53ee0161e73389a8db5764082aa2b293b53f2187023c2107fa1ba935d36";
const FIXTURE_CHECKPOINT_RECEIPT_ID: &str =
    "99e21a0f3fb156e5b9b0b553235698852eb624deb138b74da64e54615ea1333c";
const FIXTURE_SEGMENT_RECEIPT_ID: &str =
    "a5a6378baffe6a4b58aa82bc3875e5534c7964669c2a213e37e47768720930fb";
const FIXTURE_UPLINK_PROTO_HEX: &str = "0a040102030422060880d49bb8032a2d0a1030303136633030316631333961316362108486880830b8ffffffffffffffff013d000008416a04deadbeef";
const FIXTURE_EVENT_PROTO_HEX: &str = "0a3d0a040102030422060880d49bb8032a2d0a1030303136633030316631333961316362108486880830b8ffffffffffffffff013d000008416a04deadbeef";
const FIXTURE_CORRELATION_SHA256: &str =
    "a61ccd298370d1ca0edc06f9c6725ad8f2b2887a6fb1fcfa584051ae01325494";

fn fixture_body(sequence: u64, previous_record_hash: &str, captured_at: &str) -> RecordBody {
    RecordBody {
        journal_version: JOURNAL_VERSION.to_string(),
        gateway_id: "0016c001f139a1cb".to_string(),
        boot_id: "boot-fixture-1".to_string(),
        sequence,
        captured_at: captured_at.to_string(),
        source: SOURCE_CONCENTRATORD.to_string(),
        source_event_sha256: None,
        phy_payload_base64: "AQI=".to_string(),
        frequency_hz: 923_200_000,
        rssi_dbm: -72,
        snr_db: 8.5,
        gateway_context_base64: None,
        previous_record_hash: previous_record_hash.to_string(),
    }
}

fn fixture_header() -> SegmentHeader {
    SegmentHeader {
        segment_version: SEGMENT_VERSION.to_string(),
        gateway_id: "0016c001f139a1cb".to_string(),
        segment_id: 1,
        first_sequence: 1,
        previous_segment_hash: GENESIS.to_string(),
        created_at: "2000-01-01T00:00:00.000Z".to_string(),
        journal_version: JOURNAL_VERSION.to_string(),
    }
}

#[test]
fn record_fixture_is_exact_jcs_and_hash_is_stable() {
    let record = RecordEnvelope::new(fixture_body(1, GENESIS, "2000-01-01T00:00:01.000Z")).unwrap();
    let jcs = String::from_utf8(canonical_bytes(&record.record_body).unwrap()).unwrap();
    assert_eq!(
        jcs,
        "{\"boot_id\":\"boot-fixture-1\",\"captured_at\":\"2000-01-01T00:00:01.000Z\",\"frequency_hz\":923200000,\"gateway_context_base64\":null,\"gateway_id\":\"0016c001f139a1cb\",\"journal_version\":\"gateway-journal-v1\",\"phy_payload_base64\":\"AQI=\",\"previous_record_hash\":\"GENESIS\",\"rssi_dbm\":-72,\"sequence\":1,\"snr_db\":8.5,\"source\":\"concentratord\",\"source_event_sha256\":null}"
    );
    assert_eq!(record.record_hash, FIXTURE_RECORD1_SHA256);
}

#[test]
fn segment_chain_round_trip_and_upload_projection() {
    let mut builder = SegmentBuilder::new(fixture_header(), GENESIS).unwrap();
    let hash1 = builder
        .append(fixture_body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
        .unwrap();
    let hash2 = builder
        .append(fixture_body(2, &hash1, "2000-01-01T00:00:02.000Z"))
        .unwrap();
    let closed = builder.close("2000-01-01T00:00:03.000Z").unwrap();
    assert_eq!(hash1, FIXTURE_RECORD1_SHA256);
    assert_eq!(hash2, FIXTURE_RECORD2_SHA256);
    assert_eq!(closed.footer.final_record_hash, FIXTURE_RECORD2_SHA256);
    assert_eq!(closed.footer.content_sha256, FIXTURE_CONTENT_SHA256);
    assert_eq!(closed.footer.segment_hash, FIXTURE_SEGMENT_SHA256);
    assert_eq!(closed.object_sha256, FIXTURE_OBJECT_SHA256);
    let verified = verify_closed_segment(&closed.bytes).unwrap();
    assert_eq!(verified.records.len(), 2);
    assert_eq!(verified.object_sha256, closed.object_sha256);

    let upload = SegmentUploadRequest::from(&closed);
    assert_eq!(upload.object_sha256, closed.object_sha256);
    assert_eq!(upload.segment_hash, closed.footer.segment_hash);
    let checkpoint = CheckpointRequest::from_closed(&closed, "2000-01-01T00:00:04.000Z").unwrap();
    assert_eq!(checkpoint.last_sequence, 2);
    assert_eq!(checkpoint.last_record_hash, hash2);
}

#[test]
fn open_recovery_discards_only_incomplete_final_line() {
    let mut builder = SegmentBuilder::new(fixture_header(), GENESIS).unwrap();
    let hash1 = builder
        .append(fixture_body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
        .unwrap();
    let closed = builder.close("2000-01-01T00:00:02.000Z").unwrap();
    let footer_start = closed
        .bytes
        .windows(b"{\"closed_at\"".len())
        .position(|window| window == b"{\"closed_at\"")
        .unwrap();
    let mut open = closed.bytes[..footer_start].to_vec();
    open.extend_from_slice(b"{\"kind\":\"record\",\"record_body\":");
    let recovered = recover_open_segment(&open).unwrap();
    assert!(recovered.torn_tail_discarded);
    assert_eq!(recovered.records.len(), 1);
    assert_eq!(recovered.records[0].record_hash, hash1);
    assert_eq!(recovered.valid_prefix_len, footer_start);
}

#[test]
fn complete_invalid_record_is_not_treated_as_torn_tail() {
    let mut builder = SegmentBuilder::new(fixture_header(), GENESIS).unwrap();
    builder
        .append(fixture_body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
        .unwrap();
    let closed = builder.close("2000-01-01T00:00:02.000Z").unwrap();
    let footer_start = closed
        .bytes
        .windows(b"{\"closed_at\"".len())
        .position(|window| window == b"{\"closed_at\"")
        .unwrap();
    let mut open = closed.bytes[..footer_start].to_vec();
    open.extend_from_slice(b"{\"kind\":\"record\"}\n");
    assert!(recover_open_segment(&open).is_err());
}

#[test]
fn ingest_receipt_vectors_bind_submitted_identity_and_are_idempotent() {
    let mut builder = SegmentBuilder::new(fixture_header(), GENESIS).unwrap();
    let hash1 = builder
        .append(fixture_body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
        .unwrap();
    builder
        .append(fixture_body(2, &hash1, "2000-01-01T00:00:02.000Z"))
        .unwrap();
    let closed = builder.close("2000-01-01T00:00:03.000Z").unwrap();
    let segment_request = SegmentUploadRequest::from(&closed);
    let checkpoint_request =
        CheckpointRequest::from_closed(&closed, "2000-01-01T00:00:04.000Z").unwrap();
    assert_eq!(
        checkpoint_request.checkpoint_digest().unwrap(),
        FIXTURE_CHECKPOINT_DIGEST
    );

    let checkpoint_receipt = IngestReceipt {
        status: "accepted".to_string(),
        created: true,
        receipt_version: RECEIPT_VERSION.to_string(),
        artifact_type: "checkpoint".to_string(),
        gateway_id: checkpoint_request.gateway_id.clone(),
        segment_id: checkpoint_request.segment_id,
        last_sequence: checkpoint_request.last_sequence,
        checkpoint_digest: Some(FIXTURE_CHECKPOINT_DIGEST.to_string()),
        segment_hash: None,
        object_sha256: None,
        receipt_id: FIXTURE_CHECKPOINT_RECEIPT_ID.to_string(),
        server_received_at: "2000-01-01T00:00:05.000Z".to_string(),
    };
    let stored_checkpoint = checkpoint_receipt
        .validate_checkpoint(&checkpoint_request)
        .unwrap();
    let mut state = UploadReceiptState::default();
    state.record_checkpoint(stored_checkpoint.clone()).unwrap();
    state.record_checkpoint(stored_checkpoint).unwrap();

    let segment_receipt = IngestReceipt {
        status: "accepted".to_string(),
        created: true,
        receipt_version: RECEIPT_VERSION.to_string(),
        artifact_type: "segment".to_string(),
        gateway_id: segment_request.gateway_id.clone(),
        segment_id: segment_request.segment_id,
        last_sequence: segment_request.last_sequence,
        checkpoint_digest: None,
        segment_hash: Some(segment_request.segment_hash.clone()),
        object_sha256: Some(segment_request.object_sha256.clone()),
        receipt_id: FIXTURE_SEGMENT_RECEIPT_ID.to_string(),
        server_received_at: "2000-01-01T00:00:05.000Z".to_string(),
    };
    let stored_segment = segment_receipt.validate_segment(&segment_request).unwrap();
    state.record_segment(stored_segment.clone()).unwrap();
    state.record_segment(stored_segment).unwrap();

    let mut bad = segment_receipt;
    bad.receipt_id = FIXTURE_CHECKPOINT_RECEIPT_ID.to_string();
    assert!(bad.validate_segment(&segment_request).is_err());
}

#[test]
fn receipt_created_flag_does_not_change_persisted_receipt_identity() {
    let mut builder = SegmentBuilder::new(fixture_header(), GENESIS).unwrap();
    let hash1 = builder
        .append(fixture_body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
        .unwrap();
    builder
        .append(fixture_body(2, &hash1, "2000-01-01T00:00:02.000Z"))
        .unwrap();
    let closed = builder.close("2000-01-01T00:00:03.000Z").unwrap();
    let request = SegmentUploadRequest::from(&closed);
    let receipt = IngestReceipt {
        status: "accepted".to_string(),
        created: true,
        receipt_version: RECEIPT_VERSION.to_string(),
        artifact_type: "segment".to_string(),
        gateway_id: request.gateway_id.clone(),
        segment_id: request.segment_id,
        last_sequence: request.last_sequence,
        checkpoint_digest: None,
        segment_hash: Some(request.segment_hash.clone()),
        object_sha256: Some(request.object_sha256.clone()),
        receipt_id: FIXTURE_SEGMENT_RECEIPT_ID.to_string(),
        server_received_at: "2000-01-01T00:00:05.000Z".to_string(),
    };
    let first = receipt.validate_segment(&request).unwrap();
    let mut retry = receipt;
    retry.created = false;
    let second = retry.validate_segment(&request).unwrap();
    assert_eq!(first, second);
}

#[test]
fn concentratord_and_mqtt_uplink_share_frozen_semantic_identity() {
    assert_eq!(CORRELATION_VERSION, "concentratord-uplink-correlation-v1");
    assert_eq!(
        GW_PROTO_SHA256,
        "227fda5fd77fb115cb00610fb1ea1fa87c3112d972fc6534342dc7083a6dc12b"
    );
    let event_bytes = decode_hex(FIXTURE_EVENT_PROTO_HEX);
    let mqtt_bytes = decode_hex(FIXTURE_UPLINK_PROTO_HEX);
    let from_event = ConcentratordUplink::decode_event(&event_bytes, "0016c001f139a1cb").unwrap();
    let from_mqtt =
        ConcentratordUplink::decode_mqtt_uplink(&mqtt_bytes, "0016c001f139a1cb").unwrap();
    assert_eq!(from_event, from_mqtt);
    assert_eq!(from_event.uplink_id, 16_909_060);
    assert_eq!(from_event.phy_payload, vec![1, 2, 3, 4]);
    assert_eq!(from_event.frequency_hz, 923_200_000);
    assert_eq!(from_event.rssi_dbm, -72);
    assert_eq!(from_event.snr_db, 8.5);
    assert_eq!(from_event.gateway_context, vec![0xde, 0xad, 0xbe, 0xef]);
    assert_eq!(
        from_event.phy_payload_sha256(),
        "9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a"
    );
    assert_eq!(
        from_event.correlation_digest().unwrap(),
        FIXTURE_CORRELATION_SHA256
    );
    assert_eq!(
        from_mqtt.correlation_digest().unwrap(),
        FIXTURE_CORRELATION_SHA256
    );
    let body = from_event
        .to_record_body(
            "boot-fixture-protobuf",
            1,
            "2000-01-01T00:00:01.000Z",
            GENESIS,
        )
        .unwrap();
    assert_eq!(
        body.source_event_sha256.as_deref(),
        Some(FIXTURE_CORRELATION_SHA256)
    );
    assert_eq!(body.phy_payload_base64, "AQIDBA==");
    assert_eq!(body.gateway_context_base64.as_deref(), Some("3q2+7w=="));
}

#[test]
fn concentratord_adapter_rejects_non_uplink_and_gateway_mismatch() {
    assert!(ConcentratordUplink::decode_event(&[0x12, 0x00], "0016c001f139a1cb").is_err());
    assert!(ConcentratordUplink::decode_event(
        &decode_hex(FIXTURE_EVENT_PROTO_HEX),
        "0000000000000001"
    )
    .is_err());
}

fn decode_hex(value: &str) -> Vec<u8> {
    assert_eq!(value.len() % 2, 0);
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let digit = |value: u8| match value {
                b'0'..=b'9' => value - b'0',
                b'a'..=b'f' => value - b'a' + 10,
                _ => panic!("non-lowercase-hex test vector"),
            };
            (digit(pair[0]) << 4) | digit(pair[1])
        })
        .collect()
}

#[test]
fn durable_state_never_silently_renumbers() {
    let mut state = JournalState::genesis();
    let r1 = RecordEnvelope::new(fixture_body(1, GENESIS, "2000-01-01T00:00:01.000Z")).unwrap();
    state.accept_record(1, &r1.record_hash).unwrap();
    assert_eq!(state.next_sequence, 2);
    assert!(state.accept_record(3, &r1.record_hash).is_err());
}
