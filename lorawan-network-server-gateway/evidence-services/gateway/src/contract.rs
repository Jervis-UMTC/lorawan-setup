use base64::{engine::general_purpose::STANDARD, Engine as _};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::{Error, Result};

pub const JOURNAL_VERSION: &str = "gateway-journal-v1";
pub const SOURCE_CONCENTRATORD: &str = "concentratord";
pub const GENESIS: &str = "GENESIS";

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RecordBody {
    pub journal_version: String,
    pub gateway_id: String,
    pub boot_id: String,
    pub sequence: u64,
    pub captured_at: String,
    pub source: String,
    pub source_event_sha256: Option<String>,
    pub phy_payload_base64: String,
    pub frequency_hz: u64,
    pub rssi_dbm: i32,
    pub snr_db: f64,
    pub gateway_context_base64: Option<String>,
    pub previous_record_hash: String,
}

impl RecordBody {
    pub fn validate(&self) -> Result<()> {
        if self.journal_version != JOURNAL_VERSION {
            return Err(Error::Invalid("unsupported journal_version"));
        }
        validate_gateway_id(&self.gateway_id)?;
        if self.boot_id.is_empty()
            || self.boot_id.len() > 128
            || !self
                .boot_id
                .bytes()
                .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
        {
            return Err(Error::Invalid(
                "boot_id must be 1..128 ASCII alphanumeric, '-' or '_'",
            ));
        }
        if self.sequence == 0 || self.sequence > i64::MAX as u64 {
            return Err(Error::Invalid(
                "sequence must fit the positive signed 64-bit cloud contract",
            ));
        }
        validate_utc_millis(&self.captured_at)?;
        if self.source != SOURCE_CONCENTRATORD {
            return Err(Error::Invalid(
                "gateway-journal-v1 source must be concentratord",
            ));
        }
        if let Some(hash) = &self.source_event_sha256 {
            validate_hash(hash)?;
        }
        validate_canonical_base64(&self.phy_payload_base64, false)?;
        if self.frequency_hz == 0 || self.frequency_hz > 10_000_000_000 {
            return Err(Error::Invalid("frequency_hz outside supported range"));
        }
        if !(-200..=0).contains(&self.rssi_dbm) {
            return Err(Error::Invalid("rssi_dbm outside supported range"));
        }
        if !self.snr_db.is_finite() || self.snr_db < -100.0 || self.snr_db > 100.0 {
            return Err(Error::Invalid("snr_db outside supported finite range"));
        }
        if let Some(context) = &self.gateway_context_base64 {
            validate_canonical_base64(context, true)?;
        }
        validate_hash_or_genesis(&self.previous_record_hash)?;
        Ok(())
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RecordEnvelope {
    pub record_body: RecordBody,
    pub record_hash: String,
}

impl RecordEnvelope {
    pub fn new(record_body: RecordBody) -> Result<Self> {
        record_body.validate()?;
        let record_hash = record_hash(&record_body)?;
        Ok(Self {
            record_body,
            record_hash,
        })
    }

    pub fn verify(&self) -> Result<()> {
        self.record_body.validate()?;
        validate_hash(&self.record_hash)?;
        let expected = record_hash(&self.record_body)?;
        if expected != self.record_hash {
            return Err(Error::Chain("record_hash mismatch".to_string()));
        }
        Ok(())
    }
}

pub fn canonical_bytes<T: Serialize>(value: &T) -> Result<Vec<u8>> {
    serde_jcs::to_vec(value).map_err(|err| Error::Canonical(err.to_string()))
}

pub fn record_hash(body: &RecordBody) -> Result<String> {
    body.validate()?;
    Ok(sha256_hex(&canonical_bytes(body)?))
}

pub(crate) fn sha256_hex(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    hex_lower(&digest)
}

pub(crate) fn validate_gateway_id(value: &str) -> Result<()> {
    if value.len() != 16 || !value.bytes().all(is_lower_hex) {
        return Err(Error::Invalid("gateway_id must be lowercase 16-hex"));
    }
    Ok(())
}

pub(crate) fn validate_hash(value: &str) -> Result<()> {
    if value.len() != 64 || !value.bytes().all(is_lower_hex) {
        return Err(Error::Invalid("hash must be lowercase 64-hex"));
    }
    Ok(())
}

pub(crate) fn validate_hash_or_genesis(value: &str) -> Result<()> {
    if value == GENESIS {
        return Ok(());
    }
    validate_hash(value)
}

pub(crate) fn validate_utc_millis(value: &str) -> Result<()> {
    let b = value.as_bytes();
    if b.len() != 24
        || b[4] != b'-'
        || b[7] != b'-'
        || b[10] != b'T'
        || b[13] != b':'
        || b[16] != b':'
        || b[19] != b'.'
        || b[23] != b'Z'
    {
        return Err(Error::Invalid(
            "timestamp must be UTC RFC3339 with exactly milliseconds",
        ));
    }
    for index in [
        0usize, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18, 20, 21, 22,
    ] {
        if !b[index].is_ascii_digit() {
            return Err(Error::Invalid("timestamp contains non-digit component"));
        }
    }
    let part = |start: usize, end: usize| -> Result<u32> {
        value[start..end]
            .parse::<u32>()
            .map_err(|_| Error::Invalid("timestamp component is invalid"))
    };
    let year = part(0, 4)?;
    let month = part(5, 7)?;
    let day = part(8, 10)?;
    let hour = part(11, 13)?;
    let minute = part(14, 16)?;
    let second = part(17, 19)?;
    if year == 0 || !(1..=12).contains(&month) || hour > 23 || minute > 59 || second > 59 {
        return Err(Error::Invalid(
            "timestamp component outside supported range",
        ));
    }
    let leap = (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
    let max_day = match month {
        2 if leap => 29,
        2 => 28,
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    };
    if day == 0 || day > max_day {
        return Err(Error::Invalid("timestamp day is invalid for month"));
    }
    Ok(())
}

fn validate_canonical_base64(value: &str, allow_empty: bool) -> Result<()> {
    let decoded = STANDARD
        .decode(value)
        .map_err(|_| Error::Invalid("base64 field is invalid"))?;
    if !allow_empty && decoded.is_empty() {
        return Err(Error::Invalid("PHYPayload must not be empty"));
    }
    if STANDARD.encode(&decoded) != value {
        return Err(Error::Invalid(
            "base64 field is not canonical RFC4648 encoding",
        ));
    }
    Ok(())
}

fn is_lower_hex(b: u8) -> bool {
    b.is_ascii_digit() || (b'a'..=b'f').contains(&b)
}

fn hex_lower(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for &byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}
