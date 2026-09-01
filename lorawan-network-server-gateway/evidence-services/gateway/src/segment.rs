use serde::{Deserialize, Serialize};

use crate::contract::{
    canonical_bytes, sha256_hex, validate_gateway_id, validate_hash, validate_hash_or_genesis,
    validate_utc_millis,
};
use crate::{Error, RecordBody, RecordEnvelope, Result, GENESIS, JOURNAL_VERSION};

pub const SEGMENT_VERSION: &str = "gateway-journal-segment-v1";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SegmentHeader {
    pub segment_version: String,
    pub gateway_id: String,
    pub segment_id: u64,
    pub first_sequence: u64,
    pub previous_segment_hash: String,
    pub created_at: String,
    pub journal_version: String,
}

impl SegmentHeader {
    pub fn validate(&self) -> Result<()> {
        if self.segment_version != SEGMENT_VERSION {
            return Err(Error::Invalid("unsupported segment_version"));
        }
        validate_gateway_id(&self.gateway_id)?;
        if self.segment_id == 0 || self.segment_id > i64::MAX as u64 {
            return Err(Error::Invalid(
                "segment_id must fit the positive signed 64-bit cloud contract",
            ));
        }
        if self.first_sequence == 0 || self.first_sequence > i64::MAX as u64 {
            return Err(Error::Invalid(
                "first_sequence must fit the positive signed 64-bit cloud contract",
            ));
        }
        validate_hash_or_genesis(&self.previous_segment_hash)?;
        validate_utc_millis(&self.created_at)?;
        if self.journal_version != JOURNAL_VERSION {
            return Err(Error::Invalid("segment journal_version mismatch"));
        }
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SegmentFooter {
    pub last_sequence: u64,
    pub record_count: u64,
    pub final_record_hash: String,
    pub closed_at: String,
    pub content_sha256: String,
    pub segment_hash: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SegmentMetadata {
    pub segment_version: String,
    pub gateway_id: String,
    pub segment_id: u64,
    pub first_sequence: u64,
    pub last_sequence: u64,
    pub record_count: u64,
    pub previous_segment_hash: String,
    pub final_record_hash: String,
    pub segment_hash: String,
    pub object_sha256: String,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ClosedSegment {
    pub header: SegmentHeader,
    pub footer: SegmentFooter,
    pub bytes: Vec<u8>,
    pub object_sha256: String,
}

impl ClosedSegment {
    pub fn metadata(&self) -> SegmentMetadata {
        SegmentMetadata {
            segment_version: self.header.segment_version.clone(),
            gateway_id: self.header.gateway_id.clone(),
            segment_id: self.header.segment_id,
            first_sequence: self.header.first_sequence,
            last_sequence: self.footer.last_sequence,
            record_count: self.footer.record_count,
            previous_segment_hash: self.header.previous_segment_hash.clone(),
            final_record_hash: self.footer.final_record_hash.clone(),
            segment_hash: self.footer.segment_hash.clone(),
            object_sha256: self.object_sha256.clone(),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct VerifiedClosedSegment {
    pub header: SegmentHeader,
    pub records: Vec<RecordEnvelope>,
    pub footer: SegmentFooter,
    pub object_sha256: String,
}

impl VerifiedClosedSegment {
    pub fn metadata(&self) -> SegmentMetadata {
        SegmentMetadata {
            segment_version: self.header.segment_version.clone(),
            gateway_id: self.header.gateway_id.clone(),
            segment_id: self.header.segment_id,
            first_sequence: self.header.first_sequence,
            last_sequence: self.footer.last_sequence,
            record_count: self.footer.record_count,
            previous_segment_hash: self.header.previous_segment_hash.clone(),
            final_record_hash: self.footer.final_record_hash.clone(),
            segment_hash: self.footer.segment_hash.clone(),
            object_sha256: self.object_sha256.clone(),
        }
    }
}

#[derive(Debug, Clone, PartialEq)]
pub struct RecoveredOpenSegment {
    pub header: SegmentHeader,
    pub records: Vec<RecordEnvelope>,
    pub valid_prefix_len: usize,
    pub torn_tail_discarded: bool,
}

#[derive(Debug, Serialize, Deserialize)]
struct HeaderLine {
    kind: String,
    #[serde(flatten)]
    header: SegmentHeader,
}

#[derive(Debug, Serialize, Deserialize)]
struct RecordLine {
    kind: String,
    #[serde(flatten)]
    record: RecordEnvelope,
}

#[derive(Debug, Serialize, Deserialize)]
struct FooterLine {
    kind: String,
    #[serde(flatten)]
    footer: SegmentFooter,
}

#[derive(Clone)]
pub struct SegmentBuilder {
    header: SegmentHeader,
    bytes: Vec<u8>,
    expected_sequence: u64,
    expected_previous_record_hash: String,
    record_count: u64,
    final_record_hash: Option<String>,
}

impl SegmentBuilder {
    pub fn new(
        header: SegmentHeader,
        expected_previous_record_hash: impl Into<String>,
    ) -> Result<Self> {
        header.validate()?;
        let expected_previous_record_hash = expected_previous_record_hash.into();
        validate_hash_or_genesis(&expected_previous_record_hash)?;
        let bytes = canonical_line(&HeaderLine {
            kind: "header".to_string(),
            header: header.clone(),
        })?;
        Ok(Self {
            expected_sequence: header.first_sequence,
            header,
            bytes,
            expected_previous_record_hash,
            record_count: 0,
            final_record_hash: None,
        })
    }

    pub fn from_recovered(
        recovered: &RecoveredOpenSegment,
        expected_previous_record_hash: impl Into<String>,
    ) -> Result<Self> {
        let mut builder = Self::new(recovered.header.clone(), expected_previous_record_hash)?;
        for record in &recovered.records {
            let rebuilt_hash = builder.append(record.record_body.clone())?;
            if rebuilt_hash != record.record_hash {
                return Err(Error::Chain(
                    "recovered record hash changed while rebuilding open segment".to_string(),
                ));
            }
        }
        Ok(builder)
    }

    pub fn bytes(&self) -> &[u8] {
        &self.bytes
    }

    pub fn header(&self) -> &SegmentHeader {
        &self.header
    }

    pub fn record_count(&self) -> u64 {
        self.record_count
    }

    pub fn append(&mut self, body: RecordBody) -> Result<String> {
        if body.gateway_id != self.header.gateway_id {
            return Err(Error::Chain(
                "record gateway_id differs from segment".to_string(),
            ));
        }
        if body.sequence != self.expected_sequence {
            return Err(Error::Chain(format!(
                "expected sequence {}, got {}",
                self.expected_sequence, body.sequence
            )));
        }
        if body.previous_record_hash != self.expected_previous_record_hash {
            return Err(Error::Chain(
                "previous_record_hash does not extend durable state".to_string(),
            ));
        }
        let record = RecordEnvelope::new(body)?;
        let line = canonical_line(&RecordLine {
            kind: "record".to_string(),
            record: record.clone(),
        })?;
        self.bytes.extend_from_slice(&line);
        self.expected_sequence = self
            .expected_sequence
            .checked_add(1)
            .ok_or(Error::Invalid("sequence overflow"))?;
        self.expected_previous_record_hash = record.record_hash.clone();
        self.record_count += 1;
        self.final_record_hash = Some(record.record_hash.clone());
        Ok(record.record_hash)
    }

    pub fn close(mut self, closed_at: impl Into<String>) -> Result<ClosedSegment> {
        if self.record_count == 0 {
            return Err(Error::Invalid("cannot close an empty segment"));
        }
        let closed_at = closed_at.into();
        validate_utc_millis(&closed_at)?;
        let final_record_hash = self
            .final_record_hash
            .clone()
            .ok_or(Error::Invalid("missing final record hash"))?;
        let last_sequence = self.expected_sequence - 1;
        let content_sha256 = sha256_hex(&self.bytes);
        let segment_hash = segment_hash(
            &self.header,
            last_sequence,
            self.record_count,
            &final_record_hash,
            &closed_at,
            &content_sha256,
        )?;
        let footer = SegmentFooter {
            last_sequence,
            record_count: self.record_count,
            final_record_hash,
            closed_at,
            content_sha256,
            segment_hash,
        };
        self.bytes.extend_from_slice(&canonical_line(&FooterLine {
            kind: "footer".to_string(),
            footer: footer.clone(),
        })?);
        let object_sha256 = sha256_hex(&self.bytes);
        Ok(ClosedSegment {
            header: self.header,
            footer,
            bytes: self.bytes,
            object_sha256,
        })
    }
}

pub fn verify_closed_segment(bytes: &[u8]) -> Result<VerifiedClosedSegment> {
    if bytes.is_empty() || bytes.last() != Some(&b'\n') {
        return Err(Error::TornTail);
    }
    let mut offset = 0usize;
    let mut header: Option<SegmentHeader> = None;
    let mut footer: Option<SegmentFooter> = None;
    let mut footer_offset = None;
    let mut records = Vec::new();
    let mut expected_sequence = 0u64;
    let mut expected_previous_record_hash = String::new();

    for raw_line in bytes.split_inclusive(|byte| *byte == b'\n') {
        if raw_line == b"\n" {
            return Err(Error::Json("empty JSONL line".to_string()));
        }
        let line = &raw_line[..raw_line.len() - 1];
        let value: serde_json::Value =
            serde_json::from_slice(line).map_err(|err| Error::Json(err.to_string()))?;
        let kind = value
            .get("kind")
            .and_then(serde_json::Value::as_str)
            .ok_or(Error::Json("segment line is missing kind".to_string()))?;
        match kind {
            "header" => {
                if header.is_some() || !records.is_empty() || footer.is_some() {
                    return Err(Error::Chain(
                        "header is not the first and only header".to_string(),
                    ));
                }
                let parsed: HeaderLine =
                    serde_json::from_value(value).map_err(|err| Error::Json(err.to_string()))?;
                require_canonical(raw_line, &parsed)?;
                parsed.header.validate()?;
                expected_sequence = parsed.header.first_sequence;
                header = Some(parsed.header);
            }
            "record" => {
                if footer.is_some() {
                    return Err(Error::Chain("record appears after footer".to_string()));
                }
                let segment_header = header
                    .as_ref()
                    .ok_or(Error::Chain("record appears before header".to_string()))?;
                let parsed: RecordLine =
                    serde_json::from_value(value).map_err(|err| Error::Json(err.to_string()))?;
                require_canonical(raw_line, &parsed)?;
                parsed.record.verify()?;
                if parsed.record.record_body.gateway_id != segment_header.gateway_id {
                    return Err(Error::Chain(
                        "record gateway_id differs from segment".to_string(),
                    ));
                }
                if parsed.record.record_body.sequence != expected_sequence {
                    return Err(Error::Chain("journal sequence gap or reorder".to_string()));
                }
                if records.is_empty() {
                    expected_previous_record_hash =
                        parsed.record.record_body.previous_record_hash.clone();
                    validate_hash_or_genesis(&expected_previous_record_hash)?;
                } else if parsed.record.record_body.previous_record_hash
                    != expected_previous_record_hash
                {
                    return Err(Error::Chain(
                        "previous_record_hash chain mismatch".to_string(),
                    ));
                }
                expected_previous_record_hash = parsed.record.record_hash.clone();
                expected_sequence = expected_sequence
                    .checked_add(1)
                    .ok_or(Error::Invalid("sequence overflow"))?;
                records.push(parsed.record);
            }
            "footer" => {
                if header.is_none() || footer.is_some() {
                    return Err(Error::Chain("invalid footer placement".to_string()));
                }
                footer_offset = Some(offset);
                let parsed: FooterLine =
                    serde_json::from_value(value).map_err(|err| Error::Json(err.to_string()))?;
                require_canonical(raw_line, &parsed)?;
                footer = Some(parsed.footer);
            }
            _ => return Err(Error::Json("unsupported segment line kind".to_string())),
        }
        offset += raw_line.len();
    }

    let header = header.ok_or(Error::Chain("segment header missing".to_string()))?;
    let footer = footer.ok_or(Error::Chain("segment footer missing".to_string()))?;
    let footer_offset =
        footer_offset.ok_or(Error::Chain("segment footer offset missing".to_string()))?;
    if records.is_empty() {
        return Err(Error::Chain(
            "closed segment contains no records".to_string(),
        ));
    }
    validate_hash(&footer.final_record_hash)?;
    validate_hash(&footer.content_sha256)?;
    validate_hash(&footer.segment_hash)?;
    validate_utc_millis(&footer.closed_at)?;
    if footer.record_count != records.len() as u64
        || footer.last_sequence != records.last().unwrap().record_body.sequence
        || footer.final_record_hash != records.last().unwrap().record_hash
    {
        return Err(Error::Chain(
            "segment footer does not match record set".to_string(),
        ));
    }
    let content_sha256 = sha256_hex(&bytes[..footer_offset]);
    if content_sha256 != footer.content_sha256 {
        return Err(Error::Chain("segment content_sha256 mismatch".to_string()));
    }
    let expected_segment_hash = segment_hash(
        &header,
        footer.last_sequence,
        footer.record_count,
        &footer.final_record_hash,
        &footer.closed_at,
        &footer.content_sha256,
    )?;
    if expected_segment_hash != footer.segment_hash {
        return Err(Error::Chain("segment_hash mismatch".to_string()));
    }
    Ok(VerifiedClosedSegment {
        header,
        records,
        footer,
        object_sha256: sha256_hex(bytes),
    })
}

pub fn recover_open_segment(bytes: &[u8]) -> Result<RecoveredOpenSegment> {
    let (complete, torn_tail_discarded) = if bytes.last() == Some(&b'\n') {
        (bytes, false)
    } else {
        let last_newline = bytes
            .iter()
            .rposition(|byte| *byte == b'\n')
            .ok_or(Error::TornTail)?;
        (&bytes[..=last_newline], true)
    };
    let valid_prefix_len = complete.len();
    if complete.is_empty() {
        return Err(Error::TornTail);
    }

    let mut header: Option<SegmentHeader> = None;
    let mut records = Vec::new();
    let mut expected_sequence = 0u64;
    let mut expected_previous_record_hash: Option<String> = None;
    for raw_line in complete.split_inclusive(|byte| *byte == b'\n') {
        let line = &raw_line[..raw_line.len() - 1];
        let value: serde_json::Value =
            serde_json::from_slice(line).map_err(|err| Error::Json(err.to_string()))?;
        let kind = value
            .get("kind")
            .and_then(serde_json::Value::as_str)
            .ok_or(Error::Json("segment line is missing kind".to_string()))?;
        match kind {
            "header" => {
                if header.is_some() || !records.is_empty() {
                    return Err(Error::Chain(
                        "invalid open-segment header placement".to_string(),
                    ));
                }
                let parsed: HeaderLine =
                    serde_json::from_value(value).map_err(|err| Error::Json(err.to_string()))?;
                require_canonical(raw_line, &parsed)?;
                parsed.header.validate()?;
                expected_sequence = parsed.header.first_sequence;
                header = Some(parsed.header);
            }
            "record" => {
                let segment_header = header.as_ref().ok_or(Error::Chain(
                    "record appears before open-segment header".to_string(),
                ))?;
                let parsed: RecordLine =
                    serde_json::from_value(value).map_err(|err| Error::Json(err.to_string()))?;
                require_canonical(raw_line, &parsed)?;
                parsed.record.verify()?;
                if parsed.record.record_body.gateway_id != segment_header.gateway_id
                    || parsed.record.record_body.sequence != expected_sequence
                {
                    return Err(Error::Chain(
                        "open-segment record identity/sequence mismatch".to_string(),
                    ));
                }
                if let Some(expected) = &expected_previous_record_hash {
                    if &parsed.record.record_body.previous_record_hash != expected {
                        return Err(Error::Chain(
                            "open-segment previous_record_hash mismatch".to_string(),
                        ));
                    }
                } else {
                    validate_hash_or_genesis(&parsed.record.record_body.previous_record_hash)?;
                }
                expected_previous_record_hash = Some(parsed.record.record_hash.clone());
                expected_sequence = expected_sequence
                    .checked_add(1)
                    .ok_or(Error::Invalid("sequence overflow"))?;
                records.push(parsed.record);
            }
            "footer" => {
                return Err(Error::Chain(
                    "closed footer found in open segment".to_string(),
                ))
            }
            _ => {
                return Err(Error::Json(
                    "unsupported open-segment line kind".to_string(),
                ))
            }
        }
    }
    Ok(RecoveredOpenSegment {
        header: header.ok_or(Error::Chain("open segment header missing".to_string()))?,
        records,
        valid_prefix_len,
        torn_tail_discarded,
    })
}

fn canonical_line<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    let mut bytes = canonical_bytes(value)?;
    bytes.push(b'\n');
    Ok(bytes)
}

fn require_canonical<T: Serialize>(raw_line: &[u8], value: &T) -> Result<()> {
    if canonical_line(value)? != raw_line {
        return Err(Error::Canonical(
            "segment JSONL line is not exact JCS plus LF".to_string(),
        ));
    }
    Ok(())
}

fn segment_hash(
    header: &SegmentHeader,
    last_sequence: u64,
    record_count: u64,
    final_record_hash: &str,
    closed_at: &str,
    content_sha256: &str,
) -> Result<String> {
    header.validate()?;
    validate_hash(final_record_hash)?;
    validate_hash(content_sha256)?;
    validate_utc_millis(closed_at)?;
    let fields = [
        header.segment_version.as_str(),
        header.gateway_id.as_str(),
        &header.segment_id.to_string(),
        &header.first_sequence.to_string(),
        header.previous_segment_hash.as_str(),
        header.created_at.as_str(),
        header.journal_version.as_str(),
        &last_sequence.to_string(),
        &record_count.to_string(),
        final_record_hash,
        closed_at,
        content_sha256,
    ];
    let mut preimage = Vec::new();
    for (index, field) in fields.iter().enumerate() {
        if index != 0 {
            preimage.push(0);
        }
        preimage.extend_from_slice(field.as_bytes());
    }
    Ok(sha256_hex(&preimage))
}

pub fn genesis_header(
    gateway_id: impl Into<String>,
    created_at: impl Into<String>,
) -> SegmentHeader {
    SegmentHeader {
        segment_version: SEGMENT_VERSION.to_string(),
        gateway_id: gateway_id.into(),
        segment_id: 1,
        first_sequence: 1,
        previous_segment_hash: GENESIS.to_string(),
        created_at: created_at.into(),
        journal_version: JOURNAL_VERSION.to_string(),
    }
}
