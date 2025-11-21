use std::collections::{BTreeSet, HashSet};
use std::fmt;

use serde::Serialize;

use crate::routes::{PeerType, Route};

#[derive(Debug, Clone, Eq, PartialEq, Serialize)]
pub enum Check {
    RouteMissingNeighbor {
        linenum: usize,
        as_path: Option<Vec<u32>>,
    },
    CustomerWithLargeCommunity {
        linenum: usize,
    },
    NeighborAsnInconsistency {
        linenum: usize,
        neigh_large: u32,
        peertypes_large: BTreeSet<PeerType>,
        as_path: Option<Vec<u32>>,
    },
    RouteInconsistentPeerTypes {
        linenum: usize,
        standard: BTreeSet<PeerType>,
        large: BTreeSet<PeerType>,
    },
    AsInconsistentPeerTypes {
        asn: u32,
        types: Vec<PeerType>,
    },
    InconsistentLargeCommPeerAsns {
        linenum: usize,
        neighbors: HashSet<u32>,
    },
    JsonParseFailure {
        linenum: usize,
        line: String,
    },
}

impl Check {
    pub fn name(&self) -> &'static str {
        match self {
            Check::RouteMissingNeighbor { .. } => "RouteMissingNeighbor",
            Check::CustomerWithLargeCommunity { .. } => "CustomerWithLargeCommunity",
            Check::NeighborAsnInconsistency { .. } => "NeighborAsnInconsistency",
            Check::RouteInconsistentPeerTypes { .. } => "RouteInconsistentPeerTypes",
            Check::AsInconsistentPeerTypes { .. } => "AsInconsistentPeerTypes",
            Check::InconsistentLargeCommPeerAsns { .. } => "InconsistentLargeCommPeerAsns",
            Check::JsonParseFailure { .. } => "JsonParseFailure",
        }
    }

    pub fn message(&self) -> String {
        match self {
            Check::RouteMissingNeighbor { linenum, as_path } => {
                format!("Line {}: Route does not contain neighbor after Vultr (20473) in AS path ({:?})",
                     linenum, as_path
                )
            }
            Check::CustomerWithLargeCommunity { linenum } => {
                format!(
                    "Line {}: Route from customer has large PeerType community",
                    linenum
                )
            }
            Check::NeighborAsnInconsistency {
                linenum,
                neigh_large,
                peertypes_large,
                as_path,
            } => {
                format!("Line {}: Inconsisteny in neighbor ASN inference! Large community says AS{} is {:?}, but AS-path is {:?}",
                    linenum, neigh_large, peertypes_large, as_path
                )
            }
            Check::RouteInconsistentPeerTypes {
                linenum,
                standard,
                large,
            } => {
                format!(
                    "Line {}: Route has inconsistent peer types: standard={:?}, community={:?}",
                    linenum, standard, large
                )
            }
            Check::AsInconsistentPeerTypes { asn, types } => {
                format!("AS{} has inconsistent peer types: {:?}", asn, types)
            }
            Check::InconsistentLargeCommPeerAsns { linenum, neighbors } => {
                format!(
                    "Line {}: Inconsistent large community peer ASNs: {:?}",
                    linenum, neighbors
                )
            }
            Check::JsonParseFailure { linenum, line } => {
                format!("Line {}: Failed to parse JSON: {}", linenum, line)
            }
        }
    }

    pub fn run(
        idx: usize,
        route: &Route,
        neigh_aspath: u32,
        peertypes_comm: &BTreeSet<PeerType>,
        peertypes_large: &BTreeSet<(PeerType, u32)>,
    ) -> Vec<Check> {
        let mut failed = Vec::new();

        // Filter out Unknown PeerTypes for comparison
        let comm_pts: BTreeSet<PeerType> = peertypes_comm
            .iter()
            .filter(|&&pt| pt != PeerType::Unknown)
            .cloned()
            .collect();
        let mut large_pts = BTreeSet::new();
        let mut large_neighbors = HashSet::new();
        for (pt, asn) in peertypes_large.iter() {
            if *pt != PeerType::Unknown {
                large_pts.insert(*pt);
                large_neighbors.insert(*asn);
            }
        }

        if !comm_pts.is_empty() && !large_pts.is_empty() && comm_pts != large_pts {
            let check = Check::RouteInconsistentPeerTypes {
                linenum: idx,
                standard: comm_pts.clone(),
                large: large_pts.clone(),
            };
            failed.push(check);
        }

        // Check for customer with large community
        if comm_pts.contains(&PeerType::Customer) && comm_pts.len() == 1 && !large_pts.is_empty() {
            let check = Check::CustomerWithLargeCommunity { linenum: idx };
            failed.push(check);
        }

        let neigh_large = match large_neighbors.len() {
            0 => 0,
            1 => *large_neighbors.iter().next().unwrap(),
            _ => {
                let check = Check::InconsistentLargeCommPeerAsns {
                    linenum: idx,
                    neighbors: large_neighbors.clone(),
                };
                failed.push(check);
                0
            }
        };

        // Check for neighbor ASN inconsistencies
        if neigh_large != 0
            && neigh_large != neigh_aspath
            && !large_pts.contains(&PeerType::PublicPeer)
        {
            // Only flag inconsistency if not a PublicPeer.  For PeerType::PublicPeer,
            // neigh_large is usually the IXP ASN.
            let check = Check::NeighborAsnInconsistency {
                linenum: idx,
                neigh_large,
                peertypes_large: large_pts.clone(),
                as_path: route.attributes.bgp_as_path.clone(),
            };
            failed.push(check);
        }

        failed
    }
}

impl fmt::Display for Check {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.name())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::routes::Route;

    const TEST_ROUTE_JSON: &str = r#"{"net": "168.87.160.0/22", "rtype": "unicast", "proto": "up564_64515", "since": "2025-08-27", "from": "from 169.254.169.254", "primary": "*", "info": "(100/?) [AS3360i]", "via": "216.238.98.1", "iface": "henp1s0", "attributes": {"Type": "BGP univ", "BGP.origin": "IGP", "BGP.as_path": [64515, 65534, 20473, 3356, 3360, 3360], "BGP.next_hop": "100.112.2.52", "BGP.local_pref": 100, "BGP.atomic_aggr": "", "BGP.aggregator": "15.163.14.33 AS19647", "BGP.community": "(20473,100) (20473,3356) (64515,44) (47065,10564)", "BGP.large_community": "(20473, 100, 3356)"}}"#;

    fn create_test_route() -> Route {
        serde_json::from_str(TEST_ROUTE_JSON).expect("Failed to parse test route JSON")
    }

    #[test]
    fn test_check_run_inconsistent_peer_types() {
        let route = create_test_route();
        let neigh_aspath = 3356; // Extracted from AS path after 20473
        let mut peertypes_comm = BTreeSet::new();
        peertypes_comm.insert(PeerType::Transit); // From standard community (20473,100)
        let mut peer_data_large = BTreeSet::new();
        peer_data_large.insert((PeerType::Transit, 3356)); // From large community (20473,100,3356)

        // In this case, both peer types are the same, so no inconsistency check should be created
        let checks = Check::run(0, &route, neigh_aspath, &peertypes_comm, &peer_data_large);
        let mut expected_standard = BTreeSet::new();
        expected_standard.insert(PeerType::Transit);
        let mut expected_large = BTreeSet::new();
        expected_large.insert(PeerType::Transit);
        assert!(!checks.contains(&Check::RouteInconsistentPeerTypes {
            linenum: 0,
            standard: expected_standard,
            large: expected_large,
        }));

        // Test with inconsistent peer types
        let mut peertypes_comm_inconsistent = BTreeSet::new();
        peertypes_comm_inconsistent.insert(PeerType::Customer);
        let checks = Check::run(
            0,
            &route,
            neigh_aspath,
            &peertypes_comm_inconsistent,
            &peer_data_large,
        );
        let mut expected_standard = BTreeSet::new();
        expected_standard.insert(PeerType::Customer);
        let mut expected_large = BTreeSet::new();
        expected_large.insert(PeerType::Transit);
        assert!(checks.contains(&Check::RouteInconsistentPeerTypes {
            linenum: 0,
            standard: expected_standard,
            large: expected_large,
        }));
    }

    #[test]
    fn test_check_run_customer_with_large_community() {
        let route = create_test_route();
        let neigh_aspath = 3356;
        let mut peertypes_comm = BTreeSet::new();
        peertypes_comm.insert(PeerType::Customer); // (20473,4000)
        let mut peer_data_large = BTreeSet::new();
        peer_data_large.insert((PeerType::Transit, 3356)); // (20473,100,3356)

        // Customer with large community should trigger this check
        let checks = Check::run(0, &route, neigh_aspath, &peertypes_comm, &peer_data_large);
        assert!(checks.contains(&Check::CustomerWithLargeCommunity { linenum: 0 }));
    }

    #[test]
    fn test_check_run_neighbor_asn_inconsistency() {
        let route = create_test_route();
        let neigh_aspath = 3356;
        let mut peertypes_comm = BTreeSet::new();
        peertypes_comm.insert(PeerType::Transit);
        let mut peer_data_large = BTreeSet::new();
        peer_data_large.insert((PeerType::Transit, 12345));

        // Inconsistent neighbor ASNs should trigger this check
        let checks = Check::run(0, &route, neigh_aspath, &peertypes_comm, &peer_data_large);
        assert!(checks.contains(&Check::NeighborAsnInconsistency {
            linenum: 0,
            neigh_large: 12345,
            peertypes_large: peertypes_comm,
            as_path: Some(vec![64515, 65534, 20473, 3356, 3360, 3360]),
        }));
    }

    #[test]
    fn test_check_run_no_failures() {
        let route = create_test_route();
        let neigh_aspath = 3356;
        let mut peertypes_comm = BTreeSet::new();
        peertypes_comm.insert(PeerType::Transit);
        let mut peer_data_large = BTreeSet::new();
        peer_data_large.insert((PeerType::Transit, 3356));

        // Consistent values should not trigger any checks
        let checks = Check::run(0, &route, neigh_aspath, &peertypes_comm, &peer_data_large);
        assert!(checks.is_empty());
    }
}
