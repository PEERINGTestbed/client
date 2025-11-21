use std::collections::HashMap;
use std::fs;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};

use crate::routes::PeerType;
use crate::{Args, FileResult, ProviderOutput};

pub fn find_table_dump_files(directory: &Path) -> Result<Vec<PathBuf>, anyhow::Error> {
    let mut files = Vec::new();
    for entry in walkdir::WalkDir::new(directory) {
        let entry = entry.context("Failed to read directory entry")?;
        let path = entry.path();
        if !path.is_file() {
            continue;
        }
        if let Some(true) = path
            .file_name()
            .and_then(|n| n.to_str())
            .map(|fname| fname.starts_with("vtr") && fname.ends_with(".table.jsonl.bz2"))
        {
            files.push(path.to_path_buf());
        }
    }
    Ok(files)
}

pub fn write_peers_json(args: &Args, results: &HashMap<String, FileResult>) -> anyhow::Result<()> {
    let json =
        serde_json::to_string_pretty(results).context("Failed to serialize results to JSON")?;
    fs::write(&args.output, json)
        .with_context(|| format!("Failed to write output file: {:?}", args.output))?;
    Ok(())
}

pub fn write_providers_json(
    args: &Args,
    results: &HashMap<String, FileResult>,
) -> anyhow::Result<()> {
    if args.providers.is_none() {
        return Ok(());
    }
    let provider_path: &PathBuf = args.providers.as_ref().unwrap();
    let provider2sitecnt = count_sites_per_provider(results);
    let mut mux2peers = HashMap::new();
    for (mux_proto, file_result) in results {
        let transit_peers: HashMap<_, _> = file_result
            .peers
            .iter()
            .filter(|(_asn, pi)| pi.peer_types.contains(&PeerType::Transit))
            .filter_map(|(asn, pi)| {
                provider2sitecnt.get(asn).and_then(|&(v4cnt, v6cnt)| {
                    let site_count = if file_result.ip_version == 4 {
                        v4cnt
                    } else {
                        v6cnt
                    };
                    if site_count >= args.min_sites {
                        Some((*asn, pi.clone()))
                    } else {
                        None
                    }
                })
            })
            .collect();
        mux2peers.insert(
            mux_proto.clone(),
            FileResult {
                ip_version: file_result.ip_version,
                peers: transit_peers,
                failed_checks: file_result.failed_checks.clone(),
            },
        );
    }

    let mut peer2muxes: HashMap<u32, Vec<String>> = HashMap::new();
    for (mux, file_result) in &mux2peers {
        for asn in file_result.peers.keys() {
            peer2muxes
                .entry(*asn)
                .or_default()
                .push(mux.clone());
        }
    }

    let output = ProviderOutput {
        mux2peers,
        peer2muxes,
    };

    let json = serde_json::to_string_pretty(&output)
        .context("Failed to serialize provider results to JSON")?;
    fs::write(provider_path, json)
        .with_context(|| format!("Failed to write provider output file: {:?}", provider_path))?;
    Ok(())
}

fn count_sites_per_provider(results: &HashMap<String, FileResult>) -> HashMap<u32, (usize, usize)> {
    // Count ASN appearances across muxes/sites by IP version
    let mut asn_counts: HashMap<u32, (usize, usize)> = HashMap::new();
    for file_result in results.values() {
        for (asn, peer_info) in &file_result.peers {
            if peer_info.peer_types.contains(&PeerType::Transit) {
                let counts = asn_counts.entry(*asn).or_insert((0, 0));
                if file_result.ip_version == 4 {
                    counts.0 += 1;
                } else {
                    counts.1 += 1;
                }
            }
        }
    }
    asn_counts
}
