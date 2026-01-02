use std::collections::{BTreeSet, HashMap};
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};

use anyhow::Context;
use bzip2::read::BzDecoder;
use log::{debug, info, warn};

pub mod checks;
pub mod inout;
pub mod routes;

pub use checks::Check;
pub use routes::{PeerType, Route};

pub const VULTR_ASN: u32 = 20473;

#[derive(serde::Serialize, Clone, Default)]
pub struct PeerInfo {
    pub peer_types: BTreeSet<PeerType>,
    pub num_routes: usize,
    pub failed_checks: HashMap<String, usize>,
}

#[derive(serde::Serialize)]
pub struct FileResult {
    pub ip_version: u8,
    pub peers: HashMap<u32, PeerInfo>,
    pub failed_checks: HashMap<String, usize>,
}

#[derive(serde::Serialize)]
pub struct ProviderOutput {
    pub mux2peers: HashMap<String, FileResult>,
    pub mux2peerlist4: HashMap<String, Vec<u32>>,
    pub mux2peerlist6: HashMap<String, Vec<u32>>,
    pub peer2muxes: HashMap<u32, Vec<String>>,
}

#[derive(clap::Parser, Debug)]
#[command(version, about, long_about = None)]
pub struct Args {
    /// Base directory to search for vtr*.table.jsonl.bz2 files
    #[arg(short, long)]
    pub directory: PathBuf,

    /// Output JSON file for results
    #[arg(short, long)]
    pub output: PathBuf,

    /// Log file for output
    #[arg(long)]
    pub log: Option<PathBuf>,

    /// Output JSON file for transit provider results
    #[arg(long)]
    pub providers: Option<PathBuf>,

    /// Minimum number of muxes/sites a provider must appear in to be included (only considered when --providers is given)
    #[arg(long, default_value = "1")]
    pub min_sites: usize,
}

pub fn get_mux_protocol(fpath: &Path) -> Option<String> {
    let Some(fname) = fpath.file_stem().and_then(|n| n.to_str()) else {
        warn!("Cannot convert file {:?} to &str", fpath);
        return None;
    };

    let Some(basename) = fname.strip_suffix(".table.jsonl") else {
        warn!("File {:?} does not follow naming convention", fpath);
        return None;
    };

    Some(basename.to_string())
}

pub fn process_file(fpath: &Path) -> anyhow::Result<FileResult> {
    let file = File::open(fpath).with_context(|| format!("Failed to open file: {:?}", fpath))?;
    let decoder = BzDecoder::new(file);
    let reader = BufReader::new(decoder);

    let mut total_routes = 0;
    let mut asn2peerinfo: HashMap<u32, PeerInfo> = HashMap::new();
    let mut check2count: HashMap<String, usize> = HashMap::new();
    let mut ip_version: u8 = 0;

    for (idx, line) in reader.lines().enumerate() {
        let line = line.with_context(|| format!("Failed to read line {} from {:?}", idx, fpath))?;
        let line = line.trim();
        if line.is_empty() {
            continue;
        }

        let route: Route = match serde_json::from_str(line) {
            Ok(route) => route,
            Err(_e) => {
                let check = Check::JsonParseFailure {
                    linenum: idx,
                    line: line.to_string(),
                };
                warn!("{}", check.message());
                *check2count.entry(check.to_string()).or_insert(0) += 1;
                continue;
            }
        };

        if ip_version == 0 {
            ip_version = if route.net.contains(':') { 6 } else { 4 };
        }

        total_routes += 1;
        let neigh_aspath = match route.extract_vultr_neighbor() {
            Some(asn) => asn,
            None => {
                let check = Check::RouteMissingNeighbor {
                    linenum: idx,
                    as_path: route.attributes.bgp_as_path.clone(),
                };
                debug!("{}", check.message());
                *check2count.entry(check.to_string()).or_insert(0) += 1;
                continue;
            }
        };

        let peer_info = asn2peerinfo.entry(neigh_aspath).or_default();
        peer_info.num_routes += 1;

        let peertypes_comm = route.attributes.bgp_community.as_ref().map_or_else(
            || BTreeSet::from([PeerType::Unknown]),
            |v| PeerType::detect_from_communities(v),
        );
        let peertypes_large = route.attributes.bgp_large_community.as_ref().map_or_else(
            || BTreeSet::from([(PeerType::Unknown, 0)]),
            |v| PeerType::detect_from_large(v),
        );

        checks::Check::run(idx, &route, neigh_aspath, &peertypes_comm, &peertypes_large)
            .iter()
            .for_each(|check| {
                *check2count.entry(check.to_string()).or_insert(0) += 1;
                *peer_info
                    .failed_checks
                    .entry(check.to_string())
                    .or_default() += 1;
                debug!("{:?} {}", fpath, check.message())
            });

        peer_info.peer_types.extend(&peertypes_comm);
        peer_info
            .peer_types
            .extend(peertypes_large.iter().map(|(pt, _)| *pt));
    }

    info!("Processed {} routes from {:?}", total_routes, fpath);
    for (asn, peer_info) in asn2peerinfo.iter_mut() {
        peer_info.peer_types.remove(&PeerType::Unknown);
        if peer_info.peer_types.is_empty() {
            peer_info.peer_types.insert(PeerType::Unknown);
        } else if peer_info.peer_types.len() > 1 {
            let types: Vec<_> = peer_info.peer_types.iter().cloned().collect();
            let check = checks::Check::AsInconsistentPeerTypes { asn: *asn, types };
            let key = format!("{}", check);
            *check2count.entry(key.clone()).or_insert(0) += 1;
            *peer_info.failed_checks.entry(key).or_insert(0) += 1;
        }
    }

    Ok(FileResult {
        ip_version,
        peers: asn2peerinfo,
        failed_checks: check2count,
    })
}
