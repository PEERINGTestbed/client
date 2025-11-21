use std::collections::HashMap;
use std::fs::File;
use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::Parser;
use log::{error, info};
use rayon::prelude::*;
use vultr_provider_matrix::{
    get_mux_protocol, inout, process_file, Args, FileResult,
};

fn main() -> Result<()> {
    let args = Args::parse();

    init_log(&args.log)?;

    let files = inout::find_table_dump_files(&args.directory)?;
    info!("Found {} files to process", files.len());

    let results: HashMap<String, FileResult> = files
        .into_par_iter()
        .filter_map(|fpath| match get_mux_protocol(&fpath) {
            Some(mux_proto) => match process_file(&fpath) {
                Ok(result) => Some((mux_proto, result)),
                Err(_e) => {
                    error!("Failed to process file {:?}: {}", fpath, _e);
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

fn init_log(log_option: &Option<PathBuf>) -> Result<(), anyhow::Error> {
    if let Some(log_path) = log_option {
        let log_file = File::create(log_path)
            .with_context(|| format!("Failed to create log file: {:?}", log_path))?;
        env_logger::Builder::new()
            .target(env_logger::Target::Pipe(Box::new(log_file)))
            .init();
    } else {
        env_logger::init();
    }
    Ok(())
}
