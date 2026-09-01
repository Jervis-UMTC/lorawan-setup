use std::fs;

#[cfg(feature = "concentratord-zmq")]
use std::time::Duration;

use crate::clock::parse_utc_millis;
#[cfg(feature = "concentratord-zmq")]
use crate::clock::utc_now_millis;
use crate::{ConcentratordUplink, Error, PersistentJournal, Result, WriterConfig};

pub struct JournalWriter {
    config: WriterConfig,
    journal: PersistentJournal,
    boot_id: String,
}

impl JournalWriter {
    pub fn open(config: WriterConfig) -> Result<Self> {
        let boot_id = kernel_boot_id()?;
        Self::open_with_boot_id(config, boot_id)
    }

    pub fn open_with_boot_id(config: WriterConfig, boot_id: impl Into<String>) -> Result<Self> {
        let boot_id = boot_id.into();
        validate_boot_id(&boot_id)?;
        let journal = PersistentJournal::open(
            &config.state_dir,
            &config.gateway_id,
            config.journal_budget_bytes,
        )?;
        Ok(Self {
            config,
            journal,
            boot_id,
        })
    }

    pub fn process_uplink(
        &mut self,
        uplink: &ConcentratordUplink,
        captured_at: &str,
    ) -> Result<Option<u64>> {
        crate::contract::validate_utc_millis(captured_at)?;
        if !self.journal.has_open_segment() {
            self.journal.start_segment(captured_at)?;
        }
        let state = self.journal.state().clone();
        let body = uplink.to_record_body(
            self.boot_id.clone(),
            state.next_sequence,
            captured_at.to_string(),
            state.previous_record_hash,
        )?;
        self.journal.append_record(body)?;
        if self.journal.open_record_count() >= self.config.segment_max_records {
            let closed = self.journal.close_segment(captured_at)?;
            return Ok(Some(closed.header.segment_id));
        }
        Ok(None)
    }

    pub fn process_event_bytes(&mut self, bytes: &[u8], captured_at: &str) -> Result<Option<u64>> {
        let Some(uplink) =
            ConcentratordUplink::decode_event_uplink(bytes, &self.config.gateway_id)?
        else {
            return Ok(None);
        };
        self.process_uplink(&uplink, captured_at)
    }

    pub fn close_if_aged(&mut self, now: &str) -> Result<Option<u64>> {
        if !self.journal.has_open_segment() || self.journal.open_record_count() == 0 {
            return Ok(None);
        }
        let header = self.journal.open_header().ok_or(Error::Chain(
            "open journal segment is missing its header".to_string(),
        ))?;
        let created = parse_utc_millis(&header.created_at)?;
        let current = parse_utc_millis(now)?;
        let max_age_ms = i64::try_from(self.config.segment_max_age_seconds)
            .ok()
            .and_then(|v| v.checked_mul(1_000))
            .ok_or(Error::Invalid("segment max age exceeds supported range"))?;
        if current.saturating_sub(created) < max_age_ms {
            return Ok(None);
        }
        let closed = self.journal.close_segment(now)?;
        Ok(Some(closed.header.segment_id))
    }

    pub fn journal(&self) -> &PersistentJournal {
        &self.journal
    }
}

#[cfg(feature = "concentratord-zmq")]
pub fn run_writer_forever(config: WriterConfig) -> Result<()> {
    use crate::ConcentratordEventSubscriber;

    let subscriber = ConcentratordEventSubscriber::connect(&config.concentratord_event_url)?;
    let mut writer = JournalWriter::open(config)?;
    loop {
        match subscriber.recv_uplink(&writer.config.gateway_id, Duration::from_secs(1))? {
            Some(uplink) => {
                let now = utc_now_millis()?;
                writer.process_uplink(&uplink, &now)?;
            }
            None => {
                let now = utc_now_millis()?;
                writer.close_if_aged(&now)?;
            }
        }
    }
}

fn kernel_boot_id() -> Result<String> {
    let value = fs::read_to_string("/proc/sys/kernel/random/boot_id")
        .map_err(|error| Error::Io(format!("read kernel boot ID: {error}")))?;
    let value = value.trim().to_ascii_lowercase();
    validate_boot_id(&value)?;
    Ok(value)
}

fn validate_boot_id(value: &str) -> Result<()> {
    if value.is_empty()
        || value.len() > 128
        || !value
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || b == b'-' || b == b'_')
    {
        return Err(Error::Invalid("boot_id is outside journal contract"));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};

    use super::*;

    static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(1);

    struct TestRoot(PathBuf);

    impl TestRoot {
        fn new() -> Self {
            let id = NEXT_TEST_DIR.fetch_add(1, Ordering::Relaxed);
            let path =
                std::env::temp_dir().join(format!("gateway-writer-{}-{id}", std::process::id()));
            let _ = fs::remove_dir_all(&path);
            Self(path)
        }
    }

    impl Drop for TestRoot {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn config(root: &TestRoot) -> WriterConfig {
        WriterConfig {
            gateway_id: "0016c001f139a1cb".to_string(),
            concentratord_event_url: crate::CONCENTRATORD_EVENT_URL.to_string(),
            state_dir: root.0.to_string_lossy().into_owned(),
            journal_budget_bytes: 1_000_000,
            segment_max_records: 2,
            segment_max_age_seconds: 60,
        }
    }

    fn uplink() -> ConcentratordUplink {
        ConcentratordUplink {
            gateway_id: "0016c001f139a1cb".to_string(),
            uplink_id: 1,
            phy_payload: vec![1, 2, 3],
            frequency_hz: 923_200_000,
            rssi_dbm: -70,
            snr_db: 7.5,
            gateway_context: vec![4, 5],
        }
    }

    #[test]
    fn writer_rotates_by_record_count_and_reopens_chain() {
        let root = TestRoot::new();
        let mut writer = JournalWriter::open_with_boot_id(config(&root), "boot-a").unwrap();
        assert_eq!(
            writer
                .process_uplink(&uplink(), "2000-01-01T00:00:00.000Z")
                .unwrap(),
            None
        );
        assert_eq!(
            writer
                .process_uplink(&uplink(), "2000-01-01T00:00:01.000Z")
                .unwrap(),
            Some(1)
        );
        assert_eq!(writer.journal().state().next_sequence, 3);
        drop(writer);

        let writer = JournalWriter::open_with_boot_id(config(&root), "boot-b").unwrap();
        assert_eq!(writer.journal().state().next_sequence, 3);
        assert_eq!(writer.journal().state().next_segment_id, 2);
    }

    #[test]
    fn writer_rotates_nonempty_segment_by_age() {
        let root = TestRoot::new();
        let mut writer = JournalWriter::open_with_boot_id(config(&root), "boot-a").unwrap();
        writer
            .process_uplink(&uplink(), "2000-01-01T00:00:00.000Z")
            .unwrap();
        assert_eq!(
            writer.close_if_aged("2000-01-01T00:00:59.999Z").unwrap(),
            None
        );
        assert_eq!(
            writer.close_if_aged("2000-01-01T00:01:00.000Z").unwrap(),
            Some(1)
        );
    }
}
