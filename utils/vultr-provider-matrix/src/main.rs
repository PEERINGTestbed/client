use std::collections::HashMap;

use anyhow::Context;
use clap::Parser;
use log::{debug, error, info};
use rayon::prelude::*;
use vultr_provider_matrix::{Args, FileResult, get_mux_protocol, inout, process_file};

fn main() -> anyhow::Result<()> {
    let args = Args::parse();

    init_log(args.log.as_deref())?;

    let files = inout::find_table_dump_files(&args.directory)?;
    info!("Found {} files to process", files.len());

    let results: HashMap<String, FileResult> = files
        .into_par_iter()
        .filter_map(|fpath| match get_mux_protocol(&fpath) {
            Some(mux_proto) => match process_file(&fpath) {
                Ok(result) => Some((mux_proto, result)),
                Err(e) => {
                    error!("Failed to process file {:?}: {}", fpath, e);
                    None
                }
            },
            None => None,
        })
        .collect();

    inout::write_peers_json(&args, &results)?;
    inout::write_providers_json(&args, &results)?;

    Ok(())
}

fn init_log(log_option: Option<&std::path::Path>) -> anyhow::Result<()> {
    // Build logger from environment so `RUST_LOG` is respected by default.
    let mut builder = env_logger::Builder::from_env(env_logger::Env::default());

    if let Some(log_path) = log_option {
        let log_file = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(log_path)
            .with_context(|| format!("Failed to open log file: {:?}", log_path))?;
        builder.target(env_logger::Target::Pipe(Box::new(log_file)));
    }

    builder
        .try_init()
        .context("Failed to initialize logger")?;

    debug!("Logging initialized");
    Ok(())
}
