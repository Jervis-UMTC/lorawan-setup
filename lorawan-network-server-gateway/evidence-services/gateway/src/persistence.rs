#[cfg(unix)]
use std::fs::File;
use std::fs::{self, OpenOptions};
use std::io::Write;
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use crate::contract::{canonical_bytes, validate_gateway_id};
use crate::{
    verify_closed_segment, ClosedSegment, Error, JournalState, RecordBody, Result, SegmentBuilder,
    SegmentHeader, VerifiedClosedSegment, JOURNAL_VERSION, SEGMENT_VERSION,
};

const STATE_FILE: &str = "journal-state.json";
const OPEN_DIR: &str = "open";
const CLOSED_DIR: &str = "closed";
const STATE_TMP_PREFIX: &str = ".journal-state.tmp.";
const SEGMENT_PREFIX: &str = "segment-";
const SEGMENT_SUFFIX: &str = ".jsonl";
const SEGMENT_ID_WIDTH: usize = 20;

/// Crash-safe on-disk journal persistence for the gateway writer.
///
/// Ordering is deliberate: segment bytes are synced before `JournalState`
/// advances. On Gateway OS / Unix, state replacement uses same-directory rename
/// followed by a directory fsync. Startup reconstructs the authoritative state
/// from retained segment bytes and accepts the persisted state only when it is
/// an exact prefix of that reconstruction. No evidence-retirement path exists.
pub struct PersistentJournal {
    root: PathBuf,
    open_dir: PathBuf,
    closed_dir: PathBuf,
    state_path: PathBuf,
    gateway_id: String,
    budget_bytes: u64,
    state: JournalState,
    builder: Option<SegmentBuilder>,
    open_path: Option<PathBuf>,
    poisoned: bool,
}

impl PersistentJournal {
    pub fn open(
        root: impl AsRef<Path>,
        gateway_id: impl Into<String>,
        budget_bytes: u64,
    ) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        let gateway_id = gateway_id.into();
        validate_gateway_id(&gateway_id)?;
        if budget_bytes == 0 {
            return Err(Error::Invalid(
                "journal persistence budget must be positive",
            ));
        }

        let open_dir = root.join(OPEN_DIR);
        let closed_dir = root.join(CLOSED_DIR);
        let state_path = root.join(STATE_FILE);
        create_dir_all(&root)?;
        create_dir_all(&open_dir)?;
        create_dir_all(&closed_dir)?;

        promote_completed_open_segment(&open_dir, &closed_dir, &gateway_id)?;

        let mut state = JournalState::genesis();
        let mut snapshots = vec![state.clone()];

        let closed = load_closed_segments(&closed_dir, &gateway_id)?;
        for (_, verified) in &closed {
            require_closed_extends_state(verified, &state)?;
            for record in &verified.records {
                state.accept_record(record.record_body.sequence, &record.record_hash)?;
                snapshots.push(state.clone());
            }
            state.accept_closed_segment(&verified.metadata())?;
            snapshots.push(state.clone());
        }

        let open_files = segment_files(&open_dir)?;
        if open_files.len() > 1 {
            return Err(Error::Chain(
                "more than one open journal segment exists".to_string(),
            ));
        }

        let mut builder = None;
        let mut open_path = None;
        if let Some(path) = open_files.first() {
            let mut bytes = read_file(path)?;
            let recovered = crate::recover_open_segment(&bytes)?;
            require_open_extends_state(&recovered.header, &state, &gateway_id)?;

            if recovered.torn_tail_discarded {
                truncate_synced(path, recovered.valid_prefix_len as u64)?;
                sync_directory(&open_dir)?;
                bytes.truncate(recovered.valid_prefix_len);
            }

            let starting_previous_record_hash = state.previous_record_hash.clone();
            if let Some(first) = recovered.records.first() {
                if first.record_body.previous_record_hash != starting_previous_record_hash {
                    return Err(Error::Chain(
                        "open segment does not extend durable previous_record_hash".to_string(),
                    ));
                }
            }

            let rebuilt =
                SegmentBuilder::from_recovered(&recovered, starting_previous_record_hash)?;
            if rebuilt.bytes() != bytes.as_slice() {
                return Err(Error::Chain(
                    "recovered open segment bytes do not match canonical reconstruction"
                        .to_string(),
                ));
            }

            for record in &recovered.records {
                state.accept_record(record.record_body.sequence, &record.record_hash)?;
                snapshots.push(state.clone());
            }
            builder = Some(rebuilt);
            open_path = Some(path.clone());
        }

        if state_path.exists() {
            let persisted = read_state(&state_path)?;
            if !snapshots.iter().any(|candidate| candidate == &persisted) {
                return Err(Error::Chain(
                    "persisted journal state is not a prefix of retained evidence".to_string(),
                ));
            }
            if persisted != state {
                persist_state(&state_path, &state)?;
            }
        } else {
            persist_state(&state_path, &state)?;
        }

        let journal = Self {
            root,
            open_dir,
            closed_dir,
            state_path,
            gateway_id,
            budget_bytes,
            state,
            builder,
            open_path,
            poisoned: false,
        };
        journal.ensure_total_budget()?;
        Ok(journal)
    }

    pub fn state(&self) -> &JournalState {
        &self.state
    }

    pub fn has_open_segment(&self) -> bool {
        self.builder.is_some()
    }

    pub fn open_record_count(&self) -> u64 {
        self.builder
            .as_ref()
            .map(SegmentBuilder::record_count)
            .unwrap_or(0)
    }

    pub fn open_header(&self) -> Option<&SegmentHeader> {
        self.builder.as_ref().map(SegmentBuilder::header)
    }

    pub fn start_segment(&mut self, created_at: impl Into<String>) -> Result<SegmentHeader> {
        self.ensure_writable()?;
        if self.builder.is_some() || self.open_path.is_some() {
            return Err(Error::Chain(
                "cannot start a second open journal segment".to_string(),
            ));
        }
        let header = SegmentHeader {
            segment_version: SEGMENT_VERSION.to_string(),
            gateway_id: self.gateway_id.clone(),
            segment_id: self.state.next_segment_id,
            first_sequence: self.state.next_sequence,
            previous_segment_hash: self.state.previous_segment_hash.clone(),
            created_at: created_at.into(),
            journal_version: JOURNAL_VERSION.to_string(),
        };
        let builder = SegmentBuilder::new(header.clone(), self.state.previous_record_hash.clone())?;
        self.ensure_additional_budget(builder.bytes().len() as u64)?;

        let path = self.open_dir.join(segment_file_name(header.segment_id));
        write_new_synced(&path, builder.bytes())?;
        sync_directory(&self.open_dir)?;
        self.builder = Some(builder);
        self.open_path = Some(path);
        Ok(header)
    }

    pub fn append_record(&mut self, body: RecordBody) -> Result<String> {
        self.ensure_writable()?;
        let path = self
            .open_path
            .clone()
            .ok_or(Error::Invalid("no open journal segment"))?;
        let sequence = body.sequence;
        let mut candidate = self
            .builder
            .as_ref()
            .cloned()
            .ok_or(Error::Invalid("no open journal segment builder"))?;
        let previous_len = candidate.bytes().len();
        let record_hash = candidate.append(body)?;
        let delta = candidate.bytes()[previous_len..].to_vec();

        let mut next_state = self.state.clone();
        next_state.accept_record(sequence, &record_hash)?;
        self.ensure_state_replacement_budget_after_additional(&next_state, delta.len() as u64)?;

        // Evidence first. If state persistence subsequently fails, startup will
        // replay this synced record and catch the state file up. The in-memory
        // writer is poisoned on any post-write failure so callers cannot retry
        // against stale process state without reopening from disk.
        if let Err(error) = append_synced(&path, &delta) {
            self.poisoned = true;
            return Err(error);
        }
        if let Err(error) = persist_state(&self.state_path, &next_state) {
            self.poisoned = true;
            return Err(error);
        }
        self.builder = Some(candidate);
        self.state = next_state;
        Ok(record_hash)
    }

    pub fn close_segment(&mut self, closed_at: impl Into<String>) -> Result<ClosedSegment> {
        self.ensure_writable()?;
        let path = self
            .open_path
            .clone()
            .ok_or(Error::Invalid("no open journal segment"))?;
        let builder = self
            .builder
            .as_ref()
            .cloned()
            .ok_or(Error::Invalid("no open journal segment builder"))?;
        let previous_len = builder.bytes().len();
        let closed = builder.close(closed_at)?;
        let footer_delta = &closed.bytes[previous_len..];
        let closed_path = self
            .closed_dir
            .join(segment_file_name(closed.header.segment_id));
        if closed_path.exists() {
            return Err(Error::Chain(
                "closed segment destination already exists".to_string(),
            ));
        }

        let mut next_state = self.state.clone();
        next_state.accept_closed_segment(&closed.metadata())?;
        self.ensure_state_replacement_budget_after_additional(
            &next_state,
            footer_delta.len() as u64,
        )?;

        // Footer bytes are synced while the file is still in open/. Recovery
        // recognizes a fully closed file here and completes the rename. Any
        // failure after the durable footer write poisons this process instance;
        // reopening reconstructs from the retained evidence bytes.
        if let Err(error) = append_synced(&path, footer_delta) {
            self.poisoned = true;
            return Err(error);
        }
        if let Err(error) = verify_closed_segment(&closed.bytes) {
            self.poisoned = true;
            return Err(error);
        }
        if let Err(error) = rename_file(&path, &closed_path) {
            self.poisoned = true;
            return Err(error);
        }
        if let Err(error) = sync_directory(&self.open_dir) {
            self.poisoned = true;
            return Err(error);
        }
        if let Err(error) = sync_directory(&self.closed_dir) {
            self.poisoned = true;
            return Err(error);
        }
        if let Err(error) = persist_state(&self.state_path, &next_state) {
            self.poisoned = true;
            return Err(error);
        }

        self.builder = None;
        self.open_path = None;
        self.state = next_state;
        Ok(closed)
    }

    fn ensure_total_budget(&self) -> Result<()> {
        let used = storage_bytes(&self.root)?;
        if used > self.budget_bytes {
            return Err(Error::InvalidOwned(format!(
                "journal persistence uses {used} bytes, above configured budget {}",
                self.budget_bytes
            )));
        }
        Ok(())
    }

    fn ensure_additional_budget(&self, additional: u64) -> Result<()> {
        let used = storage_bytes(&self.root)?;
        let projected = used
            .checked_add(additional)
            .ok_or(Error::Invalid("journal persistence size overflow"))?;
        if projected > self.budget_bytes {
            return Err(Error::InvalidOwned(format!(
                "journal persistence would use {projected} bytes, above configured budget {}",
                self.budget_bytes
            )));
        }
        Ok(())
    }

    fn ensure_state_replacement_budget_after_additional(
        &self,
        state: &JournalState,
        additional: u64,
    ) -> Result<()> {
        let used = storage_bytes(&self.root)?;
        let current_state = if self.state_path.exists() {
            metadata_len(&self.state_path)?
        } else {
            0
        };
        let new_state = state_bytes(state)?.len() as u64;
        let projected = used
            .checked_add(additional)
            .and_then(|value| value.checked_sub(current_state))
            .and_then(|base| base.checked_add(new_state))
            .ok_or(Error::Invalid("journal state size overflow"))?;
        if projected > self.budget_bytes {
            return Err(Error::InvalidOwned(format!(
                "journal state replacement would use {projected} bytes, above configured budget {}",
                self.budget_bytes
            )));
        }
        Ok(())
    }

    fn ensure_writable(&self) -> Result<()> {
        if self.poisoned {
            return Err(Error::Io(
                "journal process state is poisoned after a durable I/O failure; reopen from disk"
                    .to_string(),
            ));
        }
        Ok(())
    }
}

fn require_closed_extends_state(
    closed: &VerifiedClosedSegment,
    state: &JournalState,
) -> Result<()> {
    if closed.header.segment_id != state.next_segment_id
        || closed.header.first_sequence != state.next_sequence
        || closed.header.previous_segment_hash != state.previous_segment_hash
    {
        return Err(Error::Chain(
            "closed segment does not extend reconstructed durable state".to_string(),
        ));
    }
    let first = closed.records.first().ok_or(Error::Chain(
        "closed segment contains no records".to_string(),
    ))?;
    if first.record_body.previous_record_hash != state.previous_record_hash {
        return Err(Error::Chain(
            "closed segment first record does not extend previous_record_hash".to_string(),
        ));
    }
    Ok(())
}

fn require_open_extends_state(
    header: &SegmentHeader,
    state: &JournalState,
    gateway_id: &str,
) -> Result<()> {
    if header.gateway_id != gateway_id
        || header.segment_id != state.next_segment_id
        || header.first_sequence != state.next_sequence
        || header.previous_segment_hash != state.previous_segment_hash
    {
        return Err(Error::Chain(
            "open segment header does not extend reconstructed durable state".to_string(),
        ));
    }
    Ok(())
}

fn promote_completed_open_segment(
    open_dir: &Path,
    closed_dir: &Path,
    gateway_id: &str,
) -> Result<()> {
    let open_files = segment_files(open_dir)?;
    if open_files.len() > 1 {
        return Err(Error::Chain(
            "more than one open journal segment exists".to_string(),
        ));
    }
    let Some(path) = open_files.first() else {
        return Ok(());
    };
    let bytes = read_file(path)?;
    let Ok(closed) = verify_closed_segment(&bytes) else {
        return Ok(());
    };
    if closed.header.gateway_id != gateway_id {
        return Err(Error::Chain(
            "completed open segment belongs to another gateway".to_string(),
        ));
    }
    require_segment_filename(path, closed.header.segment_id)?;
    let destination = closed_dir.join(segment_file_name(closed.header.segment_id));
    if destination.exists() {
        return Err(Error::Chain(
            "completed open segment conflicts with existing closed segment".to_string(),
        ));
    }
    rename_file(path, &destination)?;
    sync_directory(open_dir)?;
    sync_directory(closed_dir)?;
    Ok(())
}

pub fn load_retained_closed_segments(
    root: impl AsRef<Path>,
    gateway_id: &str,
) -> Result<Vec<ClosedSegment>> {
    validate_gateway_id(gateway_id)?;
    let closed_dir = root.as_ref().join(CLOSED_DIR);
    if !closed_dir.exists() {
        return Ok(Vec::new());
    }
    let verified = load_closed_segments(&closed_dir, gateway_id)?;
    let mut state = JournalState::genesis();
    let mut out = Vec::with_capacity(verified.len());
    for (path, segment) in verified {
        require_closed_extends_state(&segment, &state)?;
        for record in &segment.records {
            state.accept_record(record.record_body.sequence, &record.record_hash)?;
        }
        state.accept_closed_segment(&segment.metadata())?;
        let bytes = read_file(&path)?;
        out.push(ClosedSegment {
            header: segment.header,
            footer: segment.footer,
            object_sha256: segment.object_sha256,
            bytes,
        });
    }
    Ok(out)
}

fn load_closed_segments(
    closed_dir: &Path,
    gateway_id: &str,
) -> Result<Vec<(PathBuf, VerifiedClosedSegment)>> {
    let mut closed = Vec::new();
    for path in segment_files(closed_dir)? {
        let bytes = read_file(&path)?;
        let verified = verify_closed_segment(&bytes)?;
        if verified.header.gateway_id != gateway_id {
            return Err(Error::Chain(
                "closed segment belongs to another gateway".to_string(),
            ));
        }
        require_segment_filename(&path, verified.header.segment_id)?;
        closed.push((path, verified));
    }
    closed.sort_by_key(|(_, segment)| segment.header.segment_id);
    Ok(closed)
}

fn read_state(path: &Path) -> Result<JournalState> {
    let bytes = read_file(path)?;
    if bytes.last() != Some(&b'\n') {
        return Err(Error::TornTail);
    }
    let state: JournalState =
        serde_json::from_slice(&bytes).map_err(|error| Error::Json(error.to_string()))?;
    state.validate()?;
    if state_bytes(&state)? != bytes {
        return Err(Error::Canonical(
            "journal state file is not exact JCS plus LF".to_string(),
        ));
    }
    Ok(state)
}

fn persist_state(path: &Path, state: &JournalState) -> Result<()> {
    state.validate()?;
    let bytes = state_bytes(state)?;
    let parent = path.parent().ok_or(Error::Invalid(
        "journal state path must have a parent directory",
    ))?;
    let tmp = parent.join(format!("{STATE_TMP_PREFIX}{}", std::process::id()));
    {
        let mut file = OpenOptions::new()
            .create(true)
            .truncate(true)
            .write(true)
            .open(&tmp)
            .map_err(|error| io_error("open state temp", &tmp, error))?;
        set_private_file_mode(&tmp)?;
        file.write_all(&bytes)
            .map_err(|error| io_error("write state temp", &tmp, error))?;
        file.sync_all()
            .map_err(|error| io_error("fsync state temp", &tmp, error))?;
    }
    replace_file(&tmp, path)?;
    sync_directory(parent)?;
    Ok(())
}

fn state_bytes(state: &JournalState) -> Result<Vec<u8>> {
    let mut bytes = canonical_bytes(state)?;
    bytes.push(b'\n');
    Ok(bytes)
}

fn segment_files(dir: &Path) -> Result<Vec<PathBuf>> {
    let mut files = Vec::new();
    for entry in fs::read_dir(dir).map_err(|error| io_error("read directory", dir, error))? {
        let entry = entry.map_err(|error| io_error("read directory entry", dir, error))?;
        let path = entry.path();
        let file_type = entry
            .file_type()
            .map_err(|error| io_error("read file type", &path, error))?;
        if !file_type.is_file() {
            return Err(Error::InvalidOwned(format!(
                "unexpected non-file in journal segment directory: {}",
                path.display()
            )));
        }
        parse_segment_id(&path)?;
        files.push(path);
    }
    files.sort();
    Ok(files)
}

fn require_segment_filename(path: &Path, segment_id: u64) -> Result<()> {
    let parsed = parse_segment_id(path)?;
    if parsed != segment_id {
        return Err(Error::Chain(format!(
            "segment filename id {parsed} disagrees with content id {segment_id}"
        )));
    }
    Ok(())
}

fn parse_segment_id(path: &Path) -> Result<u64> {
    let name = path
        .file_name()
        .and_then(|value| value.to_str())
        .ok_or(Error::Invalid("segment filename must be UTF-8"))?;
    let digits = name
        .strip_prefix(SEGMENT_PREFIX)
        .and_then(|value| value.strip_suffix(SEGMENT_SUFFIX))
        .ok_or_else(|| Error::InvalidOwned(format!("unexpected journal filename: {name}")))?;
    if digits.len() != SEGMENT_ID_WIDTH || !digits.bytes().all(|byte| byte.is_ascii_digit()) {
        return Err(Error::InvalidOwned(format!(
            "journal segment filename must contain a zero-padded {SEGMENT_ID_WIDTH}-digit id"
        )));
    }
    let segment_id = digits
        .parse::<u64>()
        .map_err(|_| Error::Invalid("journal segment filename id is invalid"))?;
    if segment_id == 0 {
        return Err(Error::Invalid(
            "journal segment filename id must be positive",
        ));
    }
    Ok(segment_id)
}

fn segment_file_name(segment_id: u64) -> String {
    format!("{SEGMENT_PREFIX}{segment_id:020}{SEGMENT_SUFFIX}")
}

fn storage_bytes(path: &Path) -> Result<u64> {
    let mut total = 0u64;
    for entry in
        fs::read_dir(path).map_err(|error| io_error("read storage directory", path, error))?
    {
        let entry = entry.map_err(|error| io_error("read storage entry", path, error))?;
        let child = entry.path();
        let file_type = entry
            .file_type()
            .map_err(|error| io_error("read storage file type", &child, error))?;
        if file_type.is_dir() {
            total = total
                .checked_add(storage_bytes(&child)?)
                .ok_or(Error::Invalid("journal persistence size overflow"))?;
        } else if file_type.is_file() {
            if child
                .file_name()
                .and_then(|value| value.to_str())
                .is_some_and(|name| name.starts_with(STATE_TMP_PREFIX))
            {
                continue;
            }
            total = total
                .checked_add(metadata_len(&child)?)
                .ok_or(Error::Invalid("journal persistence size overflow"))?;
        } else {
            return Err(Error::InvalidOwned(format!(
                "unexpected special file in journal storage: {}",
                child.display()
            )));
        }
    }
    Ok(total)
}

fn create_dir_all(path: &Path) -> Result<()> {
    fs::create_dir_all(path).map_err(|error| io_error("create directory", path, error))?;
    set_private_directory_mode(path)
}

fn read_file(path: &Path) -> Result<Vec<u8>> {
    fs::read(path).map_err(|error| io_error("read file", path, error))
}

fn metadata_len(path: &Path) -> Result<u64> {
    fs::metadata(path)
        .map(|metadata| metadata.len())
        .map_err(|error| io_error("read metadata", path, error))
}

fn write_new_synced(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(path)
        .map_err(|error| io_error("create journal file", path, error))?;
    set_private_file_mode(path)?;
    file.write_all(bytes)
        .map_err(|error| io_error("write journal file", path, error))?;
    file.sync_all()
        .map_err(|error| io_error("fsync journal file", path, error))?;
    Ok(())
}

fn append_synced(path: &Path, bytes: &[u8]) -> Result<()> {
    let mut file = OpenOptions::new()
        .append(true)
        .open(path)
        .map_err(|error| io_error("open journal file for append", path, error))?;
    file.write_all(bytes)
        .map_err(|error| io_error("append journal file", path, error))?;
    file.sync_all()
        .map_err(|error| io_error("fsync journal append", path, error))?;
    Ok(())
}

fn truncate_synced(path: &Path, len: u64) -> Result<()> {
    let file = OpenOptions::new()
        .write(true)
        .open(path)
        .map_err(|error| io_error("open torn journal file", path, error))?;
    file.set_len(len)
        .map_err(|error| io_error("truncate torn journal file", path, error))?;
    file.sync_all()
        .map_err(|error| io_error("fsync truncated journal file", path, error))?;
    Ok(())
}

fn rename_file(from: &Path, to: &Path) -> Result<()> {
    fs::rename(from, to).map_err(|error| {
        Error::Io(format!(
            "rename {} -> {}: {error}",
            from.display(),
            to.display()
        ))
    })
}

#[cfg(unix)]
fn replace_file(from: &Path, to: &Path) -> Result<()> {
    // POSIX rename replaces the destination atomically on the same filesystem.
    rename_file(from, to)
}

#[cfg(not(unix))]
fn replace_file(from: &Path, to: &Path) -> Result<()> {
    // The development Windows fallback cannot provide POSIX rename-overwrite
    // semantics through safe std APIs. Gateway OS acceptance is Unix-only.
    // Recovery remains safe here because retained segment bytes are authoritative
    // if the state file is absent after an interrupted development-host replace.
    if to.exists() {
        fs::remove_file(to).map_err(|error| io_error("remove old state file", to, error))?;
    }
    rename_file(from, to)
}

#[cfg(unix)]
fn sync_directory(path: &Path) -> Result<()> {
    File::open(path)
        .and_then(|file| file.sync_all())
        .map_err(|error| io_error("fsync directory", path, error))
}

#[cfg(not(unix))]
fn sync_directory(_path: &Path) -> Result<()> {
    // Source validation on Windows does not claim target filesystem durability.
    Ok(())
}

#[cfg(unix)]
fn set_private_directory_mode(path: &Path) -> Result<()> {
    fs::set_permissions(path, fs::Permissions::from_mode(0o2750))
        .map_err(|error| io_error("set journal directory permissions", path, error))
}

#[cfg(not(unix))]
fn set_private_directory_mode(_path: &Path) -> Result<()> {
    Ok(())
}

#[cfg(unix)]
fn set_private_file_mode(path: &Path) -> Result<()> {
    fs::set_permissions(path, fs::Permissions::from_mode(0o640))
        .map_err(|error| io_error("set journal file permissions", path, error))
}

#[cfg(not(unix))]
fn set_private_file_mode(_path: &Path) -> Result<()> {
    Ok(())
}

fn io_error(operation: &str, path: &Path, error: std::io::Error) -> Error {
    Error::Io(format!("{operation} {}: {error}", path.display()))
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::{AtomicU64, Ordering};

    use super::*;
    use crate::{GENESIS, SOURCE_CONCENTRATORD};

    static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(1);
    const GATEWAY_ID: &str = "0016c001f139a1cb";

    struct TestRoot(PathBuf);

    impl TestRoot {
        fn new(label: &str) -> Self {
            let sequence = NEXT_TEST_DIR.fetch_add(1, Ordering::Relaxed);
            let path = std::env::temp_dir().join(format!(
                "gateway-evidence-{label}-{}-{sequence}",
                std::process::id()
            ));
            let _ = fs::remove_dir_all(&path);
            Self(path)
        }
    }

    impl Drop for TestRoot {
        fn drop(&mut self) {
            let _ = fs::remove_dir_all(&self.0);
        }
    }

    fn body(sequence: u64, previous_record_hash: &str, captured_at: &str) -> RecordBody {
        RecordBody {
            journal_version: JOURNAL_VERSION.to_string(),
            gateway_id: GATEWAY_ID.to_string(),
            boot_id: "persistence-test".to_string(),
            sequence,
            captured_at: captured_at.to_string(),
            source: SOURCE_CONCENTRATORD.to_string(),
            source_event_sha256: None,
            phy_payload_base64: "AQI=".to_string(),
            frequency_hz: 923_200_000,
            rssi_dbm: -70,
            snr_db: 7.5,
            gateway_context_base64: None,
            previous_record_hash: previous_record_hash.to_string(),
        }
    }

    #[test]
    fn closed_and_open_segments_reconstruct_state_after_restart() {
        let root = TestRoot::new("restart");
        let mut journal = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        journal.start_segment("2000-01-01T00:00:00.000Z").unwrap();
        let hash1 = journal
            .append_record(body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
            .unwrap();
        let hash2 = journal
            .append_record(body(2, &hash1, "2000-01-01T00:00:02.000Z"))
            .unwrap();
        journal.close_segment("2000-01-01T00:00:03.000Z").unwrap();
        journal.start_segment("2000-01-01T00:00:04.000Z").unwrap();
        let hash3 = journal
            .append_record(body(3, &hash2, "2000-01-01T00:00:05.000Z"))
            .unwrap();
        drop(journal);

        let recovered = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        assert_eq!(recovered.state().next_sequence, 4);
        assert_eq!(recovered.state().next_segment_id, 2);
        assert_eq!(recovered.state().previous_record_hash, hash3);
        assert!(recovered.has_open_segment());
        assert_eq!(recovered.open_record_count(), 1);
    }

    #[test]
    fn torn_open_tail_is_truncated_to_last_verified_line() {
        let root = TestRoot::new("torn-tail");
        let mut journal = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        journal.start_segment("2000-01-01T00:00:00.000Z").unwrap();
        journal
            .append_record(body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
            .unwrap();
        let path = journal.open_path.clone().unwrap();
        let valid_len = metadata_len(&path).unwrap();
        drop(journal);

        let mut file = OpenOptions::new().append(true).open(&path).unwrap();
        file.write_all(b"{\"kind\":\"record\",\"record_body\":")
            .unwrap();
        file.sync_all().unwrap();
        drop(file);
        assert!(metadata_len(&path).unwrap() > valid_len);

        let recovered = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        assert_eq!(metadata_len(&path).unwrap(), valid_len);
        assert_eq!(recovered.state().next_sequence, 2);
        assert_eq!(recovered.open_record_count(), 1);
    }

    #[test]
    fn fully_closed_file_left_in_open_directory_is_promoted_on_restart() {
        let root = TestRoot::new("promote-close");
        let mut journal = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        journal.start_segment("2000-01-01T00:00:00.000Z").unwrap();
        journal
            .append_record(body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
            .unwrap();
        let path = journal.open_path.take().unwrap();
        let builder = journal.builder.take().unwrap();
        let previous_len = builder.bytes().len();
        let closed = builder.close("2000-01-01T00:00:02.000Z").unwrap();
        append_synced(&path, &closed.bytes[previous_len..]).unwrap();
        drop(journal);

        let recovered = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        assert!(!recovered.has_open_segment());
        assert_eq!(recovered.state().next_sequence, 2);
        assert_eq!(recovered.state().next_segment_id, 2);
        assert!(root.0.join(CLOSED_DIR).join(segment_file_name(1)).exists());
    }

    #[test]
    fn state_ahead_of_retained_evidence_is_rejected() {
        let root = TestRoot::new("state-ahead");
        let mut journal = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        journal.start_segment("2000-01-01T00:00:00.000Z").unwrap();
        journal
            .append_record(body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
            .unwrap();
        let mut invalid_future = journal.state().clone();
        invalid_future.next_sequence = 3;
        persist_state(&journal.state_path, &invalid_future).unwrap();
        drop(journal);

        let error = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000)
            .err()
            .expect("ahead state must fail");
        assert!(error
            .to_string()
            .contains("not a prefix of retained evidence"));
    }

    #[test]
    fn append_budget_failure_does_not_advance_builder_or_disk() {
        let root = TestRoot::new("append-budget");
        let mut seed = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        seed.start_segment("2000-01-01T00:00:00.000Z").unwrap();
        let open_path = seed.open_path.clone().unwrap();
        drop(seed);

        let used = storage_bytes(&root.0).unwrap();
        let before_len = metadata_len(&open_path).unwrap();
        let mut journal = PersistentJournal::open(&root.0, GATEWAY_ID, used + 1).unwrap();
        let result = journal.append_record(body(1, GENESIS, "2000-01-01T00:00:01.000Z"));
        assert!(result.is_err());
        assert_eq!(journal.open_record_count(), 0);
        assert_eq!(journal.state().next_sequence, 1);
        assert_eq!(metadata_len(&open_path).unwrap(), before_len);
    }

    #[test]
    fn close_budget_failure_leaves_open_segment_unclosed() {
        let root = TestRoot::new("close-budget");
        let mut seed = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        seed.start_segment("2000-01-01T00:00:00.000Z").unwrap();
        seed.append_record(body(1, GENESIS, "2000-01-01T00:00:01.000Z"))
            .unwrap();
        let open_path = seed.open_path.clone().unwrap();
        drop(seed);

        let used = storage_bytes(&root.0).unwrap();
        let before_len = metadata_len(&open_path).unwrap();
        let mut journal = PersistentJournal::open(&root.0, GATEWAY_ID, used + 1).unwrap();
        let result = journal.close_segment("2000-01-01T00:00:02.000Z");
        assert!(result.is_err());
        assert_eq!(journal.open_record_count(), 1);
        assert_eq!(journal.state().next_segment_id, 1);
        assert_eq!(metadata_len(&open_path).unwrap(), before_len);
        assert!(segment_files(&journal.closed_dir).unwrap().is_empty());
    }

    #[test]
    fn configured_budget_fails_closed_before_new_segment_creation() {
        let root = TestRoot::new("budget");
        let seed = PersistentJournal::open(&root.0, GATEWAY_ID, 1_000_000).unwrap();
        drop(seed);
        let used = storage_bytes(&root.0).unwrap();
        let mut journal = PersistentJournal::open(&root.0, GATEWAY_ID, used + 1).unwrap();
        let result = journal.start_segment("2000-01-01T00:00:00.000Z");
        assert!(result.is_err());
        assert!(segment_files(&journal.open_dir).unwrap().is_empty());
    }
}
