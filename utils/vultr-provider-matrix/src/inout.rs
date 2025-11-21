use std::collections::HashMap;
use std::fs::OpenOptions;
use std::path::{Path, PathBuf};

use anyhow::Context;

use crate::routes::PeerType;
use crate::{Args, FileResult, ProviderOutput};

pub fn find_table_dump_files(directory: &Path) -> anyhow::Result<Vec<PathBuf>> {
    let files = walkdir::WalkDir::new(directory)
        .into_iter()
        .filter_map(|entry| entry.ok())
        .filter(|entry| entry.file_type().is_file())
        .filter_map(|entry| {
            let path = entry.path();
            let fname = path.file_name()?.to_str()?;
            if fname.starts_with("vtr") && fname.ends_with(".table.jsonl.bz2") {
                Some(path.to_path_buf())
            } else {
                None
            }
        })
        .collect();

    Ok(files)
}

pub fn write_peers_json(args: &Args, results: &HashMap<String, FileResult>) -> anyhow::Result<()> {
    let out_file = OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .open(&args.output)
        .with_context(|| format!("Failed to open output file: {:?}", args.output))?;
    serde_json::to_writer_pretty(&out_file, results)
        .context("Failed to serialize results to JSON")?;
    Ok(())
}

pub fn write_providers_json(
    args: &Args,
    results: &HashMap<String, FileResult>,
) -> anyhow::Result<()> {
    let Some(provider_path) = &args.providers else {
        return Ok(());
    };
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
            peer2muxes.entry(*asn).or_default().push(mux.clone());
        }
    }

    let output = ProviderOutput {
        mux2peers,
        peer2muxes,
    };

    let out_file = OpenOptions::new()
        .create(true)
        .truncate(true)
        .write(true)
        .open(provider_path)
        .with_context(|| format!("Failed to open provider output file: {:?}", provider_path))?;
    serde_json::to_writer_pretty(&out_file, &output)
        .context("Failed to serialize provider results to JSON")?;
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
