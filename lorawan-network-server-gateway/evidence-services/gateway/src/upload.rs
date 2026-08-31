use std::collections::BTreeMap;

use base64::{engine::general_purpose::STANDARD, Engine as _};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::contract::{validate_gateway_id, validate_hash, validate_utc_millis};
use crate::{ClosedSegment, Error, Result};

pub const CHECKPOINT_VERSION: &str = "gateway-checkpoint-v1";
pub const RECEIPT_VERSION: &str = "evidence-ingest-receipt-v1";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SegmentUploadRequest {
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
    pub object_base64: String,
}

impl From<&ClosedSegment> for SegmentUploadRequest {
    fn from(segment: &ClosedSegment) -> Self {
        let metadata = segment.metadata();
        Self {
            segment_version: metadata.segment_version,
            gateway_id: metadata.gateway_id,
            segment_id: metadata.segment_id,
            first_sequence: metadata.first_sequence,
            last_sequence: metadata.last_sequence,
            record_count: metadata.record_count,
            previous_segment_hash: metadata.previous_segment_hash,
            final_record_hash: metadata.final_record_hash,
            segment_hash: metadata.segment_hash,
            object_sha256: metadata.object_sha256,
            object_base64: STANDARD.encode(&segment.bytes),
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CheckpointRequest {
    pub checkpoint_version: String,
    pub gateway_id: String,
    pub segment_id: u64,
    pub last_sequence: u64,
    pub last_record_hash: String,
    pub segment_hash: String,
    pub created_at: String,
}

impl CheckpointRequest {
    pub fn from_closed(segment: &ClosedSegment, created_at: impl Into<String>) -> Result<Self> {
        let created_at = created_at.into();
        validate_utc_millis(&created_at)?;
        let metadata = segment.metadata();
        if metadata.record_count == 0 {
            return Err(Error::Invalid("cannot checkpoint an empty segment"));
        }
        Ok(Self {
            checkpoint_version: CHECKPOINT_VERSION.to_string(),
            gateway_id: metadata.gateway_id,
            segment_id: metadata.segment_id,
            last_sequence: metadata.last_sequence,
            last_record_hash: metadata.final_record_hash,
            segment_hash: metadata.segment_hash,
            created_at,
        })
    }

    pub fn checkpoint_digest(&self) -> Result<String> {
        if self.checkpoint_version != CHECKPOINT_VERSION {
            return Err(Error::Invalid("unsupported checkpoint_version"));
        }
        validate_gateway_id(&self.gateway_id)?;
        if self.segment_id == 0
            || self.segment_id > i64::MAX as u64
            || self.last_sequence == 0
            || self.last_sequence > i64::MAX as u64
        {
            return Err(Error::Invalid(
                "checkpoint identity must fit positive signed 64-bit cloud contract",
            ));
        }
        validate_hash(&self.last_record_hash)?;
        validate_hash(&self.segment_hash)?;
        validate_utc_millis(&self.created_at)?;
        Ok(sha256_nul(&[
            CHECKPOINT_VERSION,
            &self.gateway_id,
            &self.segment_id.to_string(),
            &self.last_sequence.to_string(),
            &self.last_record_hash,
            &self.segment_hash,
            &self.created_at,
        ]))
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct IngestReceipt {
    pub status: String,
    pub created: bool,
    pub receipt_version: String,
    pub artifact_type: String,
    pub gateway_id: String,
    pub segment_id: u64,
    pub last_sequence: u64,
    #[serde(default)]
    pub checkpoint_digest: Option<String>,
    #[serde(default)]
    pub segment_hash: Option<String>,
    #[serde(default)]
    pub object_sha256: Option<String>,
    pub receipt_id: String,
    pub server_received_at: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StoredReceipt {
    pub receipt_id: String,
    pub receipt_version: String,
    pub artifact_type: String,
    pub gateway_id: String,
    pub segment_id: u64,
    pub last_sequence: u64,
    pub checkpoint_digest: Option<String>,
    pub segment_hash: Option<String>,
    pub object_sha256: Option<String>,
    pub server_received_at: String,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct UploadReceiptState {
    pub checkpoint_receipts: BTreeMap<u64, StoredReceipt>,
    pub segment_receipts: BTreeMap<u64, StoredReceipt>,
}

impl IngestReceipt {
    pub fn validate_checkpoint(&self, request: &CheckpointRequest) -> Result<StoredReceipt> {
        self.validate_common(
            "checkpoint",
            &request.gateway_id,
            request.segment_id,
            request.last_sequence,
        )?;
        let expected_digest = request.checkpoint_digest()?;
        if self.checkpoint_digest.as_deref() != Some(expected_digest.as_str())
            || self.segment_hash.is_some()
            || self.object_sha256.is_some()
        {
            return Err(Error::Chain(
                "checkpoint receipt does not match submitted checkpoint digest".to_string(),
            ));
        }
        let expected_receipt = receipt_id(
            "checkpoint",
            &request.gateway_id,
            request.segment_id,
            request.last_sequence,
            &expected_digest,
            "",
            &self.server_received_at,
        );
        self.finish(expected_receipt)
    }

    pub fn validate_segment(&self, request: &SegmentUploadRequest) -> Result<StoredReceipt> {
        self.validate_common(
            "segment",
            &request.gateway_id,
            request.segment_id,
            request.last_sequence,
        )?;
        validate_hash(&request.segment_hash)?;
        validate_hash(&request.object_sha256)?;
        if self.checkpoint_digest.is_some()
            || self.segment_hash.as_deref() != Some(request.segment_hash.as_str())
            || self.object_sha256.as_deref() != Some(request.object_sha256.as_str())
        {
            return Err(Error::Chain(
                "segment receipt does not match submitted segment hashes".to_string(),
            ));
        }
        let expected_receipt = receipt_id(
            "segment",
            &request.gateway_id,
            request.segment_id,
            request.last_sequence,
            &request.segment_hash,
            &request.object_sha256,
            &self.server_received_at,
        );
        self.finish(expected_receipt)
    }

    fn validate_common(
        &self,
        artifact_type: &str,
        gateway_id: &str,
        segment_id: u64,
        last_sequence: u64,
    ) -> Result<()> {
        if self.status != "accepted" || self.receipt_version != RECEIPT_VERSION {
            return Err(Error::Invalid("unsupported ingest receipt status/version"));
        }
        validate_gateway_id(&self.gateway_id)?;
        validate_hash(&self.receipt_id)?;
        validate_utc_millis(&self.server_received_at)?;
        if self.artifact_type != artifact_type
            || self.gateway_id != gateway_id
            || self.segment_id != segment_id
            || self.last_sequence != last_sequence
        {
            return Err(Error::Chain(
                "ingest receipt identity does not match submitted artifact".to_string(),
            ));
        }
        Ok(())
    }

    fn finish(&self, expected_receipt: String) -> Result<StoredReceipt> {
        if self.receipt_id != expected_receipt {
            return Err(Error::Chain("ingest receipt_id mismatch".to_string()));
        }
        Ok(StoredReceipt {
            receipt_id: self.receipt_id.clone(),
            receipt_version: self.receipt_version.clone(),
            artifact_type: self.artifact_type.clone(),
            gateway_id: self.gateway_id.clone(),
            segment_id: self.segment_id,
            last_sequence: self.last_sequence,
            checkpoint_digest: self.checkpoint_digest.clone(),
            segment_hash: self.segment_hash.clone(),
            object_sha256: self.object_sha256.clone(),
            server_received_at: self.server_received_at.clone(),
        })
    }
}

impl UploadReceiptState {
    pub fn record_checkpoint(&mut self, receipt: StoredReceipt) -> Result<()> {
        record_receipt(&mut self.checkpoint_receipts, receipt)
    }

    pub fn record_segment(&mut self, receipt: StoredReceipt) -> Result<()> {
        record_receipt(&mut self.segment_receipts, receipt)
    }
}

fn record_receipt(store: &mut BTreeMap<u64, StoredReceipt>, receipt: StoredReceipt) -> Result<()> {
    if let Some(existing) = store.get(&receipt.segment_id) {
        if existing != &receipt {
            return Err(Error::Chain(
                "stored ingest receipt conflicts with previously accepted receipt".to_string(),
            ));
        }
        return Ok(());
    }
    store.insert(receipt.segment_id, receipt);
    Ok(())
}

fn receipt_id(
    artifact_type: &str,
    gateway_id: &str,
    segment_id: u64,
    last_sequence: u64,
    primary_digest: &str,
    object_sha256: &str,
    server_received_at: &str,
) -> String {
    sha256_nul(&[
        RECEIPT_VERSION,
        artifact_type,
        gateway_id,
        &segment_id.to_string(),
        &last_sequence.to_string(),
        primary_digest,
        object_sha256,
        server_received_at,
    ])
}

fn sha256_nul(fields: &[&str]) -> String {
    let mut hasher = Sha256::new();
    for (index, field) in fields.iter().enumerate() {
        if index != 0 {
            hasher.update([0]);
        }
        hasher.update(field.as_bytes());
    }
    let digest = hasher.finalize();
    let mut out = String::with_capacity(digest.len() * 2);
    for byte in digest {
        use std::fmt::Write as _;
        write!(&mut out, "{byte:02x}").expect("writing to String cannot fail");
    }
    out
}
