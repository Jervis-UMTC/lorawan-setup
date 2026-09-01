use std::io::Write;
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

use crate::contract::canonical_bytes;
use crate::{
    load_retained_closed_segments, CheckpointRequest, Error, IngestReceipt, ReceiptStore, Result,
    SegmentUploadRequest, UploaderConfig,
};

#[derive(Debug)]
pub struct HttpResponse {
    pub status: u16,
    pub body: Vec<u8>,
}

pub trait HttpTransport {
    fn send_json(&mut self, method: &str, url: &str, body: &[u8]) -> Result<HttpResponse>;
}

pub struct CurlTransport {
    executable: String,
    ca_cert_path: String,
    client_cert_path: String,
    client_key_path: String,
}

impl CurlTransport {
    pub fn from_config(config: &UploaderConfig) -> Self {
        Self {
            executable: config.http_client_path.clone(),
            ca_cert_path: config.ca_cert_path.clone(),
            client_cert_path: config.client_cert_path.clone(),
            client_key_path: config.client_key_path.clone(),
        }
    }
}

impl HttpTransport for CurlTransport {
    fn send_json(&mut self, method: &str, url: &str, body: &[u8]) -> Result<HttpResponse> {
        let mut child = Command::new(&self.executable)
            .args([
                "--silent",
                "--show-error",
                "--request",
                method,
                "--header",
                "Content-Type: application/json",
                "--cacert",
                &self.ca_cert_path,
                "--cert",
                &self.client_cert_path,
                "--key",
                &self.client_key_path,
                "--connect-timeout",
                "10",
                "--max-time",
                "60",
                "--write-out",
                "\n%{http_code}",
                "--data-binary",
                "@-",
                url,
            ])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|error| Error::Io(format!("start HTTPS client: {error}")))?;
        child
            .stdin
            .take()
            .ok_or(Error::Io("HTTPS client stdin unavailable".to_string()))?
            .write_all(body)
            .map_err(|error| Error::Io(format!("write HTTPS request body: {error}")))?;
        let output = child
            .wait_with_output()
            .map_err(|error| Error::Io(format!("wait for HTTPS client: {error}")))?;
        if !output.status.success() {
            return Err(Error::Io(format!(
                "HTTPS client transport failed with exit status {}",
                output.status
            )));
        }
        parse_curl_output(output.stdout)
    }
}

pub struct Uploader<T: HttpTransport> {
    config: UploaderConfig,
    receipts: ReceiptStore,
    transport: T,
}

impl<T: HttpTransport> Uploader<T> {
    pub fn open(config: UploaderConfig, transport: T) -> Result<Self> {
        let receipts = ReceiptStore::open(&config.receipt_dir, &config.gateway_id)?;
        Ok(Self {
            config,
            receipts,
            transport,
        })
    }

    pub fn sync_once(&mut self) -> std::result::Result<usize, SyncError> {
        let segments =
            load_retained_closed_segments(&self.config.state_dir, &self.config.gateway_id)
                .map_err(SyncError::Fatal)?;
        let mut progressed = 0usize;
        for segment in segments {
            let segment_id = segment.header.segment_id;
            if !self
                .receipts
                .state()
                .segment_receipts
                .contains_key(&segment_id)
            {
                let request = SegmentUploadRequest::from(&segment);
                let url = format!(
                    "{}/v1/gateways/{}/segments/{}",
                    self.config.ingest_url.trim_end_matches('/'),
                    self.config.gateway_id,
                    segment_id
                );
                let response = self
                    .transport
                    .send_json(
                        "PUT",
                        &url,
                        &canonical_bytes(&request).map_err(SyncError::Fatal)?,
                    )
                    .map_err(SyncError::Retryable)?;
                require_success_status(response.status)?;
                let receipt: IngestReceipt = serde_json::from_slice(&response.body)
                    .map_err(|error| SyncError::Fatal(Error::Json(error.to_string())))?;
                let stored = receipt
                    .validate_segment(&request)
                    .map_err(SyncError::Fatal)?;
                self.receipts
                    .record_segment(stored)
                    .map_err(SyncError::Fatal)?;
                progressed += 1;
            }

            if !self
                .receipts
                .state()
                .checkpoint_receipts
                .contains_key(&segment_id)
            {
                let request =
                    CheckpointRequest::from_closed(&segment, segment.footer.closed_at.clone())
                        .map_err(SyncError::Fatal)?;
                let url = format!(
                    "{}/v1/gateways/{}/checkpoints",
                    self.config.ingest_url.trim_end_matches('/'),
                    self.config.gateway_id
                );
                let response = self
                    .transport
                    .send_json(
                        "POST",
                        &url,
                        &canonical_bytes(&request).map_err(SyncError::Fatal)?,
                    )
                    .map_err(SyncError::Retryable)?;
                require_success_status(response.status)?;
                let receipt: IngestReceipt = serde_json::from_slice(&response.body)
                    .map_err(|error| SyncError::Fatal(Error::Json(error.to_string())))?;
                let stored = receipt
                    .validate_checkpoint(&request)
                    .map_err(SyncError::Fatal)?;
                self.receipts
                    .record_checkpoint(stored)
                    .map_err(SyncError::Fatal)?;
                progressed += 1;
            }
        }
        Ok(progressed)
    }

    pub fn receipts(&self) -> &ReceiptStore {
        &self.receipts
    }
}

#[derive(Debug)]
pub enum SyncError {
    Retryable(Error),
    Fatal(Error),
}

impl std::fmt::Display for SyncError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Retryable(error) => write!(f, "retryable upload failure: {error}"),
            Self::Fatal(error) => write!(f, "fatal upload failure: {error}"),
        }
    }
}

pub fn run_uploader_forever(config: UploaderConfig) -> Result<()> {
    let transport = CurlTransport::from_config(&config);
    let mut uploader = Uploader::open(config.clone(), transport)?;
    let mut retry_seconds = config.retry_initial_seconds;
    loop {
        match uploader.sync_once() {
            Ok(progressed) => {
                retry_seconds = config.retry_initial_seconds;
                let sleep = if progressed == 0 {
                    config.poll_seconds
                } else {
                    1
                };
                thread::sleep(Duration::from_secs(sleep));
            }
            Err(SyncError::Retryable(error)) => {
                eprintln!("gateway-evidence-uploader: {error}");
                thread::sleep(Duration::from_secs(retry_seconds));
                retry_seconds = retry_seconds
                    .saturating_mul(2)
                    .min(config.retry_max_seconds);
            }
            Err(SyncError::Fatal(error)) => return Err(error),
        }
    }
}

fn require_success_status(status: u16) -> std::result::Result<(), SyncError> {
    match status {
        200 | 201 => Ok(()),
        408 | 425 | 429 | 500..=599 => Err(SyncError::Retryable(Error::Io(format!(
            "evidence ingest returned retryable HTTP status {status}"
        )))),
        _ => Err(SyncError::Fatal(Error::InvalidOwned(format!(
            "evidence ingest returned non-retryable HTTP status {status}"
        )))),
    }
}

fn parse_curl_output(mut output: Vec<u8>) -> Result<HttpResponse> {
    let newline = output
        .iter()
        .rposition(|byte| *byte == b'\n')
        .ok_or(Error::Io(
            "HTTPS client did not return an HTTP status marker".to_string(),
        ))?;
    let status_text = std::str::from_utf8(&output[newline + 1..])
        .map_err(|_| Error::Io("HTTPS client status marker is not UTF-8".to_string()))?;
    if status_text.len() != 3 || !status_text.bytes().all(|byte| byte.is_ascii_digit()) {
        return Err(Error::Io(
            "HTTPS client returned invalid HTTP status marker".to_string(),
        ));
    }
    let status = status_text
        .parse::<u16>()
        .map_err(|_| Error::Io("HTTPS client returned invalid HTTP status".to_string()))?;
    output.truncate(newline);
    Ok(HttpResponse {
        status,
        body: output,
    })
}

#[cfg(test)]
mod tests {
    use std::fs;
    use std::path::PathBuf;
    use std::sync::{Arc, Mutex};

    use serde_json::json;
    use sha2::{Digest, Sha256};

    use super::*;
    use crate::{ConcentratordUplink, JournalWriter, WriterConfig, RECEIPT_VERSION};

    const GATEWAY_ID: &str = "0016c001f139a1cb";
    const SERVER_TIME: &str = "2000-01-01T00:00:05.000Z";

    #[derive(Clone)]
    struct FakeTransport {
        calls: Arc<Mutex<Vec<String>>>,
    }

    impl HttpTransport for FakeTransport {
        fn send_json(&mut self, method: &str, url: &str, body: &[u8]) -> Result<HttpResponse> {
            self.calls.lock().unwrap().push(format!("{method} {url}"));
            if method == "PUT" {
                let request: SegmentUploadRequest =
                    serde_json::from_slice(body).map_err(|error| Error::Json(error.to_string()))?;
                let receipt_id = test_receipt_id(
                    "segment",
                    &request.gateway_id,
                    request.segment_id,
                    request.last_sequence,
                    &request.segment_hash,
                    &request.object_sha256,
                    SERVER_TIME,
                );
                let body = serde_json::to_vec(&json!({
                    "status": "accepted",
                    "created": true,
                    "receipt_version": RECEIPT_VERSION,
                    "artifact_type": "segment",
                    "gateway_id": request.gateway_id,
                    "segment_id": request.segment_id,
                    "last_sequence": request.last_sequence,
                    "segment_hash": request.segment_hash,
                    "object_sha256": request.object_sha256,
                    "receipt_id": receipt_id,
                    "server_received_at": SERVER_TIME
                }))
                .map_err(|error| Error::Json(error.to_string()))?;
                return Ok(HttpResponse { status: 201, body });
            }
            if method == "POST" {
                let request: CheckpointRequest =
                    serde_json::from_slice(body).map_err(|error| Error::Json(error.to_string()))?;
                let digest = request.checkpoint_digest()?;
                let receipt_id = test_receipt_id(
                    "checkpoint",
                    &request.gateway_id,
                    request.segment_id,
                    request.last_sequence,
                    &digest,
                    "",
                    SERVER_TIME,
                );
                let body = serde_json::to_vec(&json!({
                    "status": "accepted",
                    "created": true,
                    "receipt_version": RECEIPT_VERSION,
                    "artifact_type": "checkpoint",
                    "gateway_id": request.gateway_id,
                    "segment_id": request.segment_id,
                    "last_sequence": request.last_sequence,
                    "checkpoint_digest": digest,
                    "receipt_id": receipt_id,
                    "server_received_at": SERVER_TIME
                }))
                .map_err(|error| Error::Json(error.to_string()))?;
                return Ok(HttpResponse { status: 201, body });
            }
            Err(Error::Invalid("unexpected fake HTTP method"))
        }
    }

    struct TestRoot(PathBuf);

    impl TestRoot {
        fn new() -> Self {
            let path = std::env::temp_dir().join(format!(
                "gateway-uploader-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos()
            ));
            let _ = fs::remove_dir_all(&path);
            fs::create_dir_all(&path).unwrap();
            Self(path)
        }
    }

    impl Drop for TestRoot {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn test_receipt_id(
        artifact_type: &str,
        gateway_id: &str,
        segment_id: u64,
        last_sequence: u64,
        primary_digest: &str,
        object_sha256: &str,
        server_received_at: &str,
    ) -> String {
        let fields = [
            RECEIPT_VERSION.to_string(),
            artifact_type.to_string(),
            gateway_id.to_string(),
            segment_id.to_string(),
            last_sequence.to_string(),
            primary_digest.to_string(),
            object_sha256.to_string(),
            server_received_at.to_string(),
        ];
        let mut hasher = Sha256::new();
        for (index, field) in fields.iter().enumerate() {
            if index != 0 {
                hasher.update([0]);
            }
            hasher.update(field.as_bytes());
        }
        format!("{:x}", hasher.finalize())
    }

    fn seed_closed_segment(root: &TestRoot) {
        let writer_config = WriterConfig {
            gateway_id: GATEWAY_ID.to_string(),
            concentratord_event_url: crate::CONCENTRATORD_EVENT_URL.to_string(),
            state_dir: root.0.join("journal").to_string_lossy().into_owned(),
            journal_budget_bytes: 1_000_000,
            segment_max_records: 1,
            segment_max_age_seconds: 300,
        };
        let mut writer = JournalWriter::open_with_boot_id(writer_config, "upload-test").unwrap();
        let uplink = ConcentratordUplink {
            gateway_id: GATEWAY_ID.to_string(),
            uplink_id: 1,
            phy_payload: vec![1, 2, 3],
            frequency_hz: 923_200_000,
            rssi_dbm: -70,
            snr_db: 7.5,
            gateway_context: vec![4, 5],
        };
        assert_eq!(
            writer
                .process_uplink(&uplink, "2000-01-01T00:00:01.000Z")
                .unwrap(),
            Some(1)
        );
    }

    fn uploader_config(root: &TestRoot) -> UploaderConfig {
        UploaderConfig {
            gateway_id: GATEWAY_ID.to_string(),
            state_dir: root.0.join("journal").to_string_lossy().into_owned(),
            ingest_url: "https://evidence.example.invalid".to_string(),
            ca_cert_path: "/tmp/ca.crt".to_string(),
            client_cert_path: "/tmp/client.crt".to_string(),
            client_key_path: "/tmp/client.key".to_string(),
            receipt_dir: root.0.join("receipts").to_string_lossy().into_owned(),
            http_client_path: "/usr/bin/curl".to_string(),
            retry_initial_seconds: 1,
            retry_max_seconds: 10,
            poll_seconds: 5,
        }
    }

    #[test]
    fn uploader_persists_valid_receipts_and_restart_is_idempotent() {
        let root = TestRoot::new();
        seed_closed_segment(&root);
        let calls = Arc::new(Mutex::new(Vec::new()));
        let transport = FakeTransport {
            calls: Arc::clone(&calls),
        };
        let config = uploader_config(&root);
        let mut uploader = Uploader::open(config.clone(), transport).unwrap();
        assert_eq!(uploader.sync_once().unwrap(), 2);
        assert_eq!(calls.lock().unwrap().len(), 2);
        assert_eq!(uploader.receipts().state().segment_receipts.len(), 1);
        assert_eq!(uploader.receipts().state().checkpoint_receipts.len(), 1);
        drop(uploader);

        let second_calls = Arc::new(Mutex::new(Vec::new()));
        let transport = FakeTransport {
            calls: Arc::clone(&second_calls),
        };
        let mut reopened = Uploader::open(config, transport).unwrap();
        assert_eq!(reopened.sync_once().unwrap(), 0);
        assert!(second_calls.lock().unwrap().is_empty());
    }

    #[test]
    fn curl_output_parser_separates_body_and_status() {
        let response = parse_curl_output(b"{\"status\":\"accepted\"}\n201".to_vec()).unwrap();
        assert_eq!(response.status, 201);
        assert_eq!(response.body, b"{\"status\":\"accepted\"}");
    }

    #[test]
    fn status_policy_retries_only_transient_classes() {
        assert!(require_success_status(200).is_ok());
        assert!(matches!(
            require_success_status(503),
            Err(SyncError::Retryable(_))
        ));
        assert!(matches!(
            require_success_status(409),
            Err(SyncError::Fatal(_))
        ));
    }
}
