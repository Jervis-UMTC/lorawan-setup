use serde::{Deserialize, Serialize};

use crate::contract::{validate_hash, validate_hash_or_genesis};
use crate::{Error, Result, SegmentMetadata, GENESIS};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct JournalState {
    pub next_sequence: u64,
    pub previous_record_hash: String,
    pub next_segment_id: u64,
    pub previous_segment_hash: String,
}

impl JournalState {
    pub fn genesis() -> Self {
        Self {
            next_sequence: 1,
            previous_record_hash: GENESIS.to_string(),
            next_segment_id: 1,
            previous_segment_hash: GENESIS.to_string(),
        }
    }

    pub fn validate(&self) -> Result<()> {
        if self.next_sequence == 0 || self.next_segment_id == 0 {
            return Err(Error::Invalid("journal state counters must start at 1"));
        }
        validate_hash_or_genesis(&self.previous_record_hash)?;
        validate_hash_or_genesis(&self.previous_segment_hash)?;
        Ok(())
    }

    pub fn accept_record(&mut self, sequence: u64, record_hash: &str) -> Result<()> {
        self.validate()?;
        validate_hash(record_hash)?;
        if sequence != self.next_sequence {
            return Err(Error::Chain(format!(
                "durable state expected sequence {}, got {}",
                self.next_sequence, sequence
            )));
        }
        self.previous_record_hash = record_hash.to_string();
        self.next_sequence = self
            .next_sequence
            .checked_add(1)
            .ok_or(Error::Invalid("sequence overflow"))?;
        Ok(())
    }

    pub fn accept_closed_segment(&mut self, metadata: &SegmentMetadata) -> Result<()> {
        self.validate()?;
        if metadata.segment_id != self.next_segment_id {
            return Err(Error::Chain(
                "closed segment_id does not match durable state".to_string(),
            ));
        }
        if metadata.previous_segment_hash != self.previous_segment_hash {
            return Err(Error::Chain(
                "closed segment does not extend previous_segment_hash".to_string(),
            ));
        }
        if metadata.last_sequence + 1 != self.next_sequence {
            return Err(Error::Chain(
                "closed segment last_sequence disagrees with record state".to_string(),
            ));
        }
        if metadata.final_record_hash != self.previous_record_hash {
            return Err(Error::Chain(
                "closed segment final_record_hash disagrees with record state".to_string(),
            ));
        }
        validate_hash(&metadata.segment_hash)?;
        self.previous_segment_hash = metadata.segment_hash.clone();
        self.next_segment_id = self
            .next_segment_id
            .checked_add(1)
            .ok_or(Error::Invalid("segment_id overflow"))?;
        Ok(())
    }
}
