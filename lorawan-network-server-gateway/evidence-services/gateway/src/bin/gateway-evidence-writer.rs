use std::process::ExitCode;

use gateway_evidence::{JournalWriter, WriterConfig};

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("gateway-evidence-writer: {message}");
            ExitCode::from(2)
        }
    }
}

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    match (args.next().as_deref(), args.next()) {
        (Some("--check-config"), None) => {
            let config = WriterConfig::from_env().map_err(|error| error.to_string())?;
            println!("{}", config.summary());
            println!("GATEWAY_EVIDENCE_WRITER_CONFIG=PASS");
            Ok(())
        }
        (Some("--fixture-event-hex"), Some(hex)) if args.next().is_none() => {
            let config = WriterConfig::from_env().map_err(|error| error.to_string())?;
            let bytes = decode_hex(&hex)?;
            let mut writer = JournalWriter::open_with_boot_id(config, "fixture-boot")
                .map_err(|error| error.to_string())?;
            writer
                .process_event_bytes(&bytes, "2000-01-01T00:00:00.000Z")
                .map_err(|error| error.to_string())?;
            println!("GATEWAY_EVIDENCE_WRITER_FIXTURE=PASS");
            Ok(())
        }
        (Some("--help"), None) | (Some("-h"), None) => {
            println!("usage: gateway-evidence-writer [--check-config|--fixture-event-hex HEX]");
            Ok(())
        }
        (None, None) => run_forever(),
        _ => Err("invalid arguments; use --help".to_string()),
    }
}

#[cfg(feature = "concentratord-zmq")]
fn run_forever() -> Result<(), String> {
    let config = WriterConfig::from_env().map_err(|error| error.to_string())?;
    gateway_evidence::run_writer_forever(config).map_err(|error| error.to_string())
}

#[cfg(not(feature = "concentratord-zmq"))]
fn run_forever() -> Result<(), String> {
    Err("live writer requires the concentratord-zmq build feature".to_string())
}

fn decode_hex(value: &str) -> Result<Vec<u8>, String> {
    if value.is_empty() || value.len() % 2 != 0 {
        return Err("fixture hex must contain complete bytes".to_string());
    }
    value
        .as_bytes()
        .chunks_exact(2)
        .map(|pair| {
            let text =
                std::str::from_utf8(pair).map_err(|_| "fixture hex is not UTF-8".to_string())?;
            u8::from_str_radix(text, 16)
                .map_err(|_| "fixture hex contains an invalid byte".to_string())
        })
        .collect()
}
