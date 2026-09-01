use std::process::ExitCode;

use gateway_evidence::{run_uploader_forever, CurlTransport, Uploader, UploaderConfig};

fn main() -> ExitCode {
    match run() {
        Ok(()) => ExitCode::SUCCESS,
        Err(message) => {
            eprintln!("gateway-evidence-uploader: {message}");
            ExitCode::from(2)
        }
    }
}

fn run() -> Result<(), String> {
    let mut args = std::env::args().skip(1);
    match (args.next().as_deref(), args.next()) {
        (Some("--check-config"), None) => {
            let config = UploaderConfig::from_env().map_err(|error| error.to_string())?;
            println!("{}", config.summary());
            println!("GATEWAY_EVIDENCE_UPLOADER_CONFIG=PASS");
            Ok(())
        }
        (Some("--sync-once"), None) => {
            let config = UploaderConfig::from_env().map_err(|error| error.to_string())?;
            let transport = CurlTransport::from_config(&config);
            let mut uploader =
                Uploader::open(config, transport).map_err(|error| error.to_string())?;
            let progressed = uploader.sync_once().map_err(|error| error.to_string())?;
            println!("gateway_evidence_upload_actions={progressed}");
            println!("GATEWAY_EVIDENCE_UPLOADER_SYNC_ONCE=PASS");
            Ok(())
        }
        (Some("--help"), None) | (Some("-h"), None) => {
            println!("usage: gateway-evidence-uploader [--check-config|--sync-once]");
            Ok(())
        }
        (None, None) => {
            let config = UploaderConfig::from_env().map_err(|error| error.to_string())?;
            run_uploader_forever(config).map_err(|error| error.to_string())
        }
        _ => Err("invalid arguments; use --help".to_string()),
    }
}
