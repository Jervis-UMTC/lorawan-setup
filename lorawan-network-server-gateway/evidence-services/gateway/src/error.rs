use std::fmt::{Display, Formatter};

#[derive(Debug)]
pub enum Error {
    Invalid(&'static str),
    InvalidOwned(String),
    Canonical(String),
    Json(String),
    Chain(String),
    TornTail,
}

impl Display for Error {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Invalid(message) => write!(f, "invalid gateway evidence: {message}"),
            Self::InvalidOwned(message) => write!(f, "invalid gateway evidence: {message}"),
            Self::Canonical(message) => write!(f, "canonicalization failed: {message}"),
            Self::Json(message) => write!(f, "JSON parsing failed: {message}"),
            Self::Chain(message) => write!(f, "journal continuity failed: {message}"),
            Self::TornTail => write!(f, "open segment ends with an incomplete final record"),
        }
    }
}

impl std::error::Error for Error {}

pub type Result<T> = std::result::Result<T, Error>;
