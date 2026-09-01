use std::env;

use crate::contract::validate_gateway_id;
use crate::{Error, Result};

pub const CONCENTRATORD_EVENT_URL: &str = "ipc:///tmp/concentratord_event";

const WRITER_GATEWAY_ID: &str = "GATEWAY_EVIDENCE_GATEWAY_ID";
const WRITER_EVENT_URL: &str = "GATEWAY_EVIDENCE_CONCENTRATORD_EVENT_URL";
const WRITER_STATE_DIR: &str = "GATEWAY_EVIDENCE_STATE_DIR";
const WRITER_BUDGET_BYTES: &str = "GATEWAY_EVIDENCE_JOURNAL_BUDGET_BYTES";
const WRITER_SEGMENT_MAX_RECORDS: &str = "GATEWAY_EVIDENCE_SEGMENT_MAX_RECORDS";
const WRITER_SEGMENT_MAX_AGE_SECONDS: &str = "GATEWAY_EVIDENCE_SEGMENT_MAX_AGE_SECONDS";

const UPLOADER_INGEST_URL: &str = "GATEWAY_EVIDENCE_INGEST_URL";
const UPLOADER_CA_CERT: &str = "GATEWAY_EVIDENCE_CA_CERT_PATH";
const UPLOADER_CLIENT_CERT: &str = "GATEWAY_EVIDENCE_CLIENT_CERT_PATH";
const UPLOADER_CLIENT_KEY: &str = "GATEWAY_EVIDENCE_CLIENT_KEY_PATH";
const UPLOADER_RECEIPT_DIR: &str = "GATEWAY_EVIDENCE_RECEIPT_DIR";
const UPLOADER_HTTP_CLIENT_PATH: &str = "GATEWAY_EVIDENCE_HTTP_CLIENT_PATH";
const UPLOADER_RETRY_INITIAL_SECONDS: &str = "GATEWAY_EVIDENCE_RETRY_INITIAL_SECONDS";
const UPLOADER_RETRY_MAX_SECONDS: &str = "GATEWAY_EVIDENCE_RETRY_MAX_SECONDS";
const UPLOADER_POLL_SECONDS: &str = "GATEWAY_EVIDENCE_POLL_SECONDS";

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WriterConfig {
    pub gateway_id: String,
    pub concentratord_event_url: String,
    pub state_dir: String,
    pub journal_budget_bytes: u64,
    pub segment_max_records: u64,
    pub segment_max_age_seconds: u64,
}

impl WriterConfig {
    pub fn from_env() -> Result<Self> {
        Self::from_lookup(|key| env::var(key).ok())
    }

    fn from_lookup(mut lookup: impl FnMut(&str) -> Option<String>) -> Result<Self> {
        let gateway_id = required(&mut lookup, WRITER_GATEWAY_ID)?;
        validate_gateway_id(&gateway_id)?;

        let concentratord_event_url = required(&mut lookup, WRITER_EVENT_URL)?;
        if concentratord_event_url != CONCENTRATORD_EVENT_URL {
            return Err(Error::InvalidOwned(format!(
                "{WRITER_EVENT_URL} must be exactly {CONCENTRATORD_EVENT_URL}"
            )));
        }

        let state_dir = required(&mut lookup, WRITER_STATE_DIR)?;
        validate_gateway_absolute_path(WRITER_STATE_DIR, &state_dir)?;

        let journal_budget_bytes = positive_u64(
            WRITER_BUDGET_BYTES,
            &required(&mut lookup, WRITER_BUDGET_BYTES)?,
        )?;
        let segment_max_records = positive_u64(
            WRITER_SEGMENT_MAX_RECORDS,
            &required(&mut lookup, WRITER_SEGMENT_MAX_RECORDS)?,
        )?;
        let segment_max_age_seconds = positive_u64(
            WRITER_SEGMENT_MAX_AGE_SECONDS,
            &required(&mut lookup, WRITER_SEGMENT_MAX_AGE_SECONDS)?,
        )?;

        Ok(Self {
            gateway_id,
            concentratord_event_url,
            state_dir,
            journal_budget_bytes,
            segment_max_records,
            segment_max_age_seconds,
        })
    }

    pub fn summary(&self) -> String {
        format!(
            "gateway_id={} event_url={} state_dir={} journal_budget_bytes={} segment_max_records={} segment_max_age_seconds={}",
            self.gateway_id,
            self.concentratord_event_url,
            self.state_dir,
            self.journal_budget_bytes,
            self.segment_max_records,
            self.segment_max_age_seconds
        )
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct UploaderConfig {
    pub gateway_id: String,
    pub state_dir: String,
    pub ingest_url: String,
    pub ca_cert_path: String,
    pub client_cert_path: String,
    pub client_key_path: String,
    pub receipt_dir: String,
    pub http_client_path: String,
    pub retry_initial_seconds: u64,
    pub retry_max_seconds: u64,
    pub poll_seconds: u64,
}

impl UploaderConfig {
    pub fn from_env() -> Result<Self> {
        Self::from_lookup(|key| env::var(key).ok())
    }

    fn from_lookup(mut lookup: impl FnMut(&str) -> Option<String>) -> Result<Self> {
        let gateway_id = required(&mut lookup, WRITER_GATEWAY_ID)?;
        validate_gateway_id(&gateway_id)?;

        let state_dir = required(&mut lookup, WRITER_STATE_DIR)?;
        validate_gateway_absolute_path(WRITER_STATE_DIR, &state_dir)?;

        let ingest_url = required(&mut lookup, UPLOADER_INGEST_URL)?;
        validate_https_url(&ingest_url)?;

        let ca_cert_path = required(&mut lookup, UPLOADER_CA_CERT)?;
        let client_cert_path = required(&mut lookup, UPLOADER_CLIENT_CERT)?;
        let client_key_path = required(&mut lookup, UPLOADER_CLIENT_KEY)?;
        validate_gateway_absolute_path(UPLOADER_CA_CERT, &ca_cert_path)?;
        validate_gateway_absolute_path(UPLOADER_CLIENT_CERT, &client_cert_path)?;
        validate_gateway_absolute_path(UPLOADER_CLIENT_KEY, &client_key_path)?;

        let receipt_dir = required(&mut lookup, UPLOADER_RECEIPT_DIR)?;
        validate_gateway_absolute_path(UPLOADER_RECEIPT_DIR, &receipt_dir)?;
        let http_client_path = required(&mut lookup, UPLOADER_HTTP_CLIENT_PATH)?;
        validate_gateway_absolute_path(UPLOADER_HTTP_CLIENT_PATH, &http_client_path)?;

        let retry_initial_seconds = positive_u64(
            UPLOADER_RETRY_INITIAL_SECONDS,
            &required(&mut lookup, UPLOADER_RETRY_INITIAL_SECONDS)?,
        )?;
        let retry_max_seconds = positive_u64(
            UPLOADER_RETRY_MAX_SECONDS,
            &required(&mut lookup, UPLOADER_RETRY_MAX_SECONDS)?,
        )?;
        if retry_max_seconds < retry_initial_seconds {
            return Err(Error::InvalidOwned(format!(
                "{UPLOADER_RETRY_MAX_SECONDS} must be >= {UPLOADER_RETRY_INITIAL_SECONDS}"
            )));
        }
        let poll_seconds = positive_u64(
            UPLOADER_POLL_SECONDS,
            &required(&mut lookup, UPLOADER_POLL_SECONDS)?,
        )?;

        Ok(Self {
            gateway_id,
            state_dir,
            ingest_url,
            ca_cert_path,
            client_cert_path,
            client_key_path,
            receipt_dir,
            http_client_path,
            retry_initial_seconds,
            retry_max_seconds,
            poll_seconds,
        })
    }

    pub fn summary(&self) -> String {
        format!(
            "gateway_id={} state_dir={} receipt_dir={} ingest_url={} http_client_path={} retry_initial_seconds={} retry_max_seconds={} poll_seconds={} mtls_paths_configured=true",
            self.gateway_id,
            self.state_dir,
            self.receipt_dir,
            self.ingest_url,
            self.http_client_path,
            self.retry_initial_seconds,
            self.retry_max_seconds,
            self.poll_seconds
        )
    }
}

fn required(lookup: &mut impl FnMut(&str) -> Option<String>, key: &'static str) -> Result<String> {
    let value = lookup(key).ok_or_else(|| Error::InvalidOwned(format!("missing {key}")))?;
    let value = value.trim();
    if value.is_empty() {
        return Err(Error::InvalidOwned(format!("{key} must not be empty")));
    }
    Ok(value.to_string())
}

fn positive_u64(key: &'static str, value: &str) -> Result<u64> {
    let parsed = value
        .parse::<u64>()
        .map_err(|_| Error::InvalidOwned(format!("{key} must be a positive integer")))?;
    if parsed == 0 {
        return Err(Error::InvalidOwned(format!(
            "{key} must be greater than zero"
        )));
    }
    Ok(parsed)
}

fn validate_gateway_absolute_path(key: &'static str, value: &str) -> Result<()> {
    if !value.starts_with('/')
        || value.contains('\0')
        || value.contains('\n')
        || value.contains('\r')
    {
        return Err(Error::InvalidOwned(format!(
            "{key} must be an absolute Gateway OS path"
        )));
    }
    Ok(())
}

fn validate_https_url(value: &str) -> Result<()> {
    let remainder = value
        .strip_prefix("https://")
        .ok_or(Error::Invalid("evidence ingest URL must use https://"))?;
    if remainder.is_empty()
        || remainder.starts_with('/')
        || remainder.contains('@')
        || remainder.contains('?')
        || remainder.contains('#')
        || remainder.chars().any(char::is_whitespace)
    {
        return Err(Error::Invalid("invalid evidence ingest HTTPS base URL"));
    }
    if let Some((_, path)) = remainder.split_once('/') {
        if !path.is_empty() {
            return Err(Error::Invalid(
                "evidence ingest URL must be a base HTTPS origin without a path",
            ));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use super::*;

    fn writer_values() -> BTreeMap<&'static str, &'static str> {
        BTreeMap::from([
            (WRITER_GATEWAY_ID, "0016c001f139a1cb"),
            (WRITER_EVENT_URL, CONCENTRATORD_EVENT_URL),
            (WRITER_STATE_DIR, "/etc/gateway-evidence"),
            (WRITER_BUDGET_BYTES, "104857600"),
            (WRITER_SEGMENT_MAX_RECORDS, "1000"),
            (WRITER_SEGMENT_MAX_AGE_SECONDS, "300"),
        ])
    }

    fn uploader_values() -> BTreeMap<&'static str, &'static str> {
        BTreeMap::from([
            (WRITER_GATEWAY_ID, "0016c001f139a1cb"),
            (WRITER_STATE_DIR, "/etc/gateway-evidence"),
            (UPLOADER_INGEST_URL, "https://evidence.example.invalid"),
            (UPLOADER_CA_CERT, "/etc/gateway-evidence/tls/ca.crt"),
            (UPLOADER_CLIENT_CERT, "/etc/gateway-evidence/tls/client.crt"),
            (UPLOADER_CLIENT_KEY, "/etc/gateway-evidence/tls/client.key"),
            (UPLOADER_RECEIPT_DIR, "/etc/gateway-evidence/upload-state"),
            (UPLOADER_HTTP_CLIENT_PATH, "/usr/bin/curl"),
            (UPLOADER_RETRY_INITIAL_SECONDS, "5"),
            (UPLOADER_RETRY_MAX_SECONDS, "300"),
            (UPLOADER_POLL_SECONDS, "5"),
        ])
    }

    #[test]
    fn writer_config_accepts_frozen_ipc_and_explicit_storage_policy() {
        let values = writer_values();
        let config = WriterConfig::from_lookup(|key| values.get(key).map(|value| (*value).into()))
            .expect("writer config");
        assert_eq!(config.gateway_id, "0016c001f139a1cb");
        assert_eq!(config.concentratord_event_url, CONCENTRATORD_EVENT_URL);
        assert_eq!(config.journal_budget_bytes, 104_857_600);
        assert_eq!(config.segment_max_records, 1000);
        assert_eq!(config.segment_max_age_seconds, 300);
    }

    #[test]
    fn writer_config_rejects_alternate_event_socket_and_zero_budget() {
        let mut values = writer_values();
        values.insert(WRITER_EVENT_URL, "ipc:///tmp/other");
        assert!(
            WriterConfig::from_lookup(|key| values.get(key).map(|value| (*value).into())).is_err()
        );

        let mut values = writer_values();
        values.insert(WRITER_BUDGET_BYTES, "0");
        assert!(
            WriterConfig::from_lookup(|key| values.get(key).map(|value| (*value).into())).is_err()
        );
    }

    #[test]
    fn uploader_config_requires_https_mtls_paths_and_bounded_backoff() {
        let values = uploader_values();
        let config =
            UploaderConfig::from_lookup(|key| values.get(key).map(|value| (*value).into()))
                .expect("uploader config");
        assert_eq!(config.retry_initial_seconds, 5);
        assert_eq!(config.retry_max_seconds, 300);
        assert_eq!(config.poll_seconds, 5);
        assert_eq!(config.http_client_path, "/usr/bin/curl");
        assert!(config.summary().contains("mtls_paths_configured=true"));
        assert!(!config.summary().contains("client.key"));
    }

    #[test]
    fn uploader_config_rejects_plain_http_credentials_and_inverted_backoff() {
        let mut values = uploader_values();
        values.insert(UPLOADER_INGEST_URL, "http://evidence.example.invalid");
        assert!(
            UploaderConfig::from_lookup(|key| values.get(key).map(|value| (*value).into()))
                .is_err()
        );

        let mut values = uploader_values();
        values.insert(UPLOADER_INGEST_URL, "https://user@evidence.example.invalid");
        assert!(
            UploaderConfig::from_lookup(|key| values.get(key).map(|value| (*value).into()))
                .is_err()
        );

        let mut values = uploader_values();
        values.insert(UPLOADER_INGEST_URL, "https://evidence.example.invalid/v1");
        assert!(
            UploaderConfig::from_lookup(|key| values.get(key).map(|value| (*value).into()))
                .is_err()
        );

        let mut values = uploader_values();
        values.insert(UPLOADER_RETRY_INITIAL_SECONDS, "60");
        values.insert(UPLOADER_RETRY_MAX_SECONDS, "10");
        assert!(
            UploaderConfig::from_lookup(|key| values.get(key).map(|value| (*value).into()))
                .is_err()
        );
    }
}
