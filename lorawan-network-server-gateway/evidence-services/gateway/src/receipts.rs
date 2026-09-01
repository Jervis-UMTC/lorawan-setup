#[cfg(unix)]
use std::fs::File;
use std::fs::{self, OpenOptions};
use std::io::Write;
#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;
use std::path::{Path, PathBuf};

use crate::contract::canonical_bytes;
use crate::{Error, Result, StoredReceipt, UploadReceiptState};

const RECEIPTS_FILE: &str = "receipts.json";
const RECEIPTS_TMP_PREFIX: &str = ".receipts.tmp.";

pub struct ReceiptStore {
    root: PathBuf,
    path: PathBuf,
    state: UploadReceiptState,
}

impl ReceiptStore {
    pub fn open(root: impl AsRef<Path>, gateway_id: &str) -> Result<Self> {
        let root = root.as_ref().to_path_buf();
        fs::create_dir_all(&root)
            .map_err(|error| io_error("create receipt directory", &root, error))?;
        set_private_directory_mode(&root)?;
        let path = root.join(RECEIPTS_FILE);
        let state = if path.exists() {
            let bytes =
                fs::read(&path).map_err(|error| io_error("read receipt state", &path, error))?;
            if bytes.last() != Some(&b'\n') {
                return Err(Error::TornTail);
            }
            let state: UploadReceiptState =
                serde_json::from_slice(&bytes).map_err(|error| Error::Json(error.to_string()))?;
            if receipt_bytes(&state)? != bytes {
                return Err(Error::Canonical(
                    "receipt state is not exact JCS plus LF".to_string(),
                ));
            }
            state.validate_for_gateway(gateway_id)?;
            state
        } else {
            let state = UploadReceiptState::default();
            persist(&path, &state)?;
            state
        };
        Ok(Self { root, path, state })
    }

    pub fn state(&self) -> &UploadReceiptState {
        &self.state
    }

    pub fn record_checkpoint(&mut self, receipt: StoredReceipt) -> Result<()> {
        let mut next = self.state.clone();
        next.record_checkpoint(receipt)?;
        persist(&self.path, &next)?;
        self.state = next;
        Ok(())
    }

    pub fn record_segment(&mut self, receipt: StoredReceipt) -> Result<()> {
        let mut next = self.state.clone();
        next.record_segment(receipt)?;
        persist(&self.path, &next)?;
        self.state = next;
        Ok(())
    }

    pub fn root(&self) -> &Path {
        &self.root
    }
}

fn persist(path: &Path, state: &UploadReceiptState) -> Result<()> {
    let bytes = receipt_bytes(state)?;
    let parent = path
        .parent()
        .ok_or(Error::Invalid("receipt path has no parent"))?;
    let tmp = parent.join(format!("{RECEIPTS_TMP_PREFIX}{}", std::process::id()));
    {
        let mut file = OpenOptions::new()
            .create(true)
            .truncate(true)
            .write(true)
            .open(&tmp)
            .map_err(|error| io_error("open receipt temp", &tmp, error))?;
        set_private_file_mode(&tmp)?;
        file.write_all(&bytes)
            .map_err(|error| io_error("write receipt temp", &tmp, error))?;
        file.sync_all()
            .map_err(|error| io_error("fsync receipt temp", &tmp, error))?;
    }
    replace_file(&tmp, path)?;
    sync_directory(parent)?;
    Ok(())
}

fn receipt_bytes(state: &UploadReceiptState) -> Result<Vec<u8>> {
    let mut bytes = canonical_bytes(state)?;
    bytes.push(b'\n');
    Ok(bytes)
}

#[cfg(unix)]
fn replace_file(from: &Path, to: &Path) -> Result<()> {
    fs::rename(from, to).map_err(|error| {
        Error::Io(format!(
            "rename {} -> {}: {error}",
            from.display(),
            to.display()
        ))
    })
}

#[cfg(not(unix))]
fn replace_file(from: &Path, to: &Path) -> Result<()> {
    if to.exists() {
        fs::remove_file(to).map_err(|error| io_error("remove old receipt state", to, error))?;
    }
    fs::rename(from, to).map_err(|error| {
        Error::Io(format!(
            "rename {} -> {}: {error}",
            from.display(),
            to.display()
        ))
    })
}

#[cfg(unix)]
fn sync_directory(path: &Path) -> Result<()> {
    File::open(path)
        .and_then(|file| file.sync_all())
        .map_err(|error| io_error("fsync receipt directory", path, error))
}

#[cfg(not(unix))]
fn sync_directory(_path: &Path) -> Result<()> {
    Ok(())
}

#[cfg(unix)]
fn set_private_directory_mode(path: &Path) -> Result<()> {
    fs::set_permissions(path, fs::Permissions::from_mode(0o2750))
        .map_err(|error| io_error("set receipt directory permissions", path, error))
}

#[cfg(not(unix))]
fn set_private_directory_mode(_path: &Path) -> Result<()> {
    Ok(())
}

#[cfg(unix)]
fn set_private_file_mode(path: &Path) -> Result<()> {
    fs::set_permissions(path, fs::Permissions::from_mode(0o640))
        .map_err(|error| io_error("set receipt file permissions", path, error))
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

    static NEXT_TEST_DIR: AtomicU64 = AtomicU64::new(1);
    const GATEWAY_ID: &str = "0016c001f139a1cb";

    fn receipt() -> StoredReceipt {
        StoredReceipt {
            receipt_id: "99e21a0f3fb156e5b9b0b553235698852eb624deb138b74da64e54615ea1333c"
                .to_string(),
            receipt_version: crate::RECEIPT_VERSION.to_string(),
            artifact_type: "checkpoint".to_string(),
            gateway_id: GATEWAY_ID.to_string(),
            segment_id: 1,
            last_sequence: 2,
            checkpoint_digest: Some(
                "3f7cc53ee0161e73389a8db5764082aa2b293b53f2187023c2107fa1ba935d36".to_string(),
            ),
            segment_hash: None,
            object_sha256: None,
            server_received_at: "2000-01-01T00:00:05.000Z".to_string(),
        }
    }

    #[test]
    fn receipt_state_survives_restart() {
        let id = NEXT_TEST_DIR.fetch_add(1, Ordering::Relaxed);
        let root =
            std::env::temp_dir().join(format!("gateway-receipts-{}-{id}", std::process::id()));
        let _ = fs::remove_dir_all(&root);
        let mut store = ReceiptStore::open(&root, GATEWAY_ID).unwrap();
        store.record_checkpoint(receipt()).unwrap();
        drop(store);
        let reopened = ReceiptStore::open(&root, GATEWAY_ID).unwrap();
        assert_eq!(reopened.state().checkpoint_receipts.len(), 1);
        let _ = fs::remove_dir_all(root);
    }
}
