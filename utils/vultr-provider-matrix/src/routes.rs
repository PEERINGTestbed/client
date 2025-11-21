use std::collections::BTreeSet;
use std::fmt;

use anyhow::Result;
use regex::Regex;
use serde::{Deserialize, de::Deserializer};
use std::sync::OnceLock;

static COMMUNITY_REGEX: OnceLock<Regex> = OnceLock::new();
static LARGE_COMMUNITY_REGEX: OnceLock<Regex> = OnceLock::new();

fn get_community_regex() -> &'static Regex {
    COMMUNITY_REGEX.get_or_init(|| Regex::new(r"\((\d+),\s*(\d+)\)").unwrap())
}

fn get_large_community_regex() -> &'static Regex {
    LARGE_COMMUNITY_REGEX.get_or_init(|| Regex::new(r"\((\d+),\s*(\d+),\s*(\d+)\)").unwrap())
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
pub struct Route {
    pub net: String,
    pub rtype: String,
    pub proto: String,
    pub since: String,
    pub from: String,
    pub primary: Option<String>,
    pub info: Option<String>,
    pub iface: Option<String>,
    pub via: Option<String>,
    pub attributes: Attributes,
}

#[allow(dead_code)]
#[derive(Clone, Debug, Deserialize)]
pub struct Attributes {
    #[serde(rename = "Type")]
    pub bgp_type: String,
    #[serde(rename = "BGP.origin")]
    pub bgp_origin: String,
    #[serde(rename = "BGP.as_path")]
    pub bgp_as_path: Option<Vec<u32>>,
    #[serde(rename = "BGP.next_hop")]
    pub bgp_next_hop: String,
    #[serde(rename = "BGP.local_pref")]
    pub bgp_local_pref: u32,
    #[serde(rename = "BGP.atomic_aggr")]
    pub bgp_atomic_aggr: Option<String>,
    #[serde(rename = "BGP.aggregator")]
    pub bgp_aggregator: Option<String>,
    #[serde(rename = "BGP.community", deserialize_with = "deserialize_community")]
    pub bgp_community: Option<Vec<(u32, u32)>>,
    #[serde(
        rename = "BGP.large_community",
        deserialize_with = "deserialize_large_community",
        default
    )]
    pub bgp_large_community: Option<Vec<(u32, u32, u32)>>,
    #[serde(rename = "BGP.med")]
    pub bgp_med: Option<u32>,
    #[serde(rename = "BGP.otc")]
    pub bgp_otc: Option<String>,
}

impl Route {
    pub fn extract_vultr_neighbor(&self) -> Option<u32> {
        self.attributes.bgp_as_path.as_ref().and_then(|as_path| {
            as_path
                .iter()
                .position(|&asn| asn == crate::VULTR_ASN)
                .and_then(|pos| as_path.get(pos + 1))
                .copied()
        })
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, serde::Serialize, PartialOrd, Ord)]
pub enum PeerType {
    Transit,
    PublicPeer,
    PrivatePeer,
    Customer,
    VultrOrigin,
    Unknown,
}

fn parse_communities(community_str: &str) -> Vec<(u32, u32)> {
    get_community_regex()
        .captures_iter(community_str)
        .filter_map(|cap| {
            let asn: u32 = cap[1].parse().ok()?;
            let value: u32 = cap[2].parse().ok()?;
            Some((asn, value))
        })
        .collect()
}

fn parse_large_communities(community_str: &str) -> Vec<(u32, u32, u32)> {
    get_large_community_regex()
        .captures_iter(community_str)
        .filter_map(|cap| {
            let asn: u32 = cap[1].parse().ok()?;
            let type_val: u32 = cap[2].parse().ok()?;
            let peer_asn: u32 = cap[3].parse().ok()?;
            Some((asn, type_val, peer_asn))
        })
        .collect()
}

fn deserialize_community<'de, D>(deserializer: D) -> Result<Option<Vec<(u32, u32)>>, D::Error>
where
    D: Deserializer<'de>,
{
    let s: Option<String> = Option::deserialize(deserializer)?;
    Ok(s.map(|s| parse_communities(&s)))
}

#[allow(clippy::type_complexity)]
fn deserialize_large_community<'de, D>(
    deserializer: D,
) -> Result<Option<Vec<(u32, u32, u32)>>, D::Error>
where
    D: Deserializer<'de>,
{
    let s: Option<String> = Option::deserialize(deserializer)?;
    Ok(s.map(|s| parse_large_communities(&s)))
}

impl PeerType {
    pub fn detect_from_communities(communities: &[(u32, u32)]) -> BTreeSet<PeerType> {
        let mut peer_types: BTreeSet<PeerType> = communities
            .iter()
            .filter(|&&(asn, _)| asn == crate::VULTR_ASN)
            .map(|&(_, peertype)| peertype.into())
            .filter(|&pt| pt != PeerType::Unknown)
            .collect();

        if peer_types.is_empty() {
            peer_types.insert(PeerType::Unknown);
        }
        peer_types
    }

    pub fn detect_from_large(large_communities: &[(u32, u32, u32)]) -> BTreeSet<(PeerType, u32)> {
        let mut peer_data: BTreeSet<(PeerType, u32)> = large_communities
            .iter()
            .filter(|&&(asn, _, _)| asn == crate::VULTR_ASN)
            .map(|&(_, peertype, neighbor)| (peertype.into(), neighbor))
            .filter(|(pt, _)| *pt != PeerType::Unknown)
            .collect();

        if peer_data.is_empty() {
            peer_data.insert((PeerType::Unknown, 0));
        }
        peer_data
    }
}

impl fmt::Display for PeerType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            PeerType::Transit => write!(f, "transit"),
            PeerType::PublicPeer => write!(f, "public_peer"),
            PeerType::PrivatePeer => write!(f, "private_peer"),
            PeerType::Customer => write!(f, "customer"),
            PeerType::VultrOrigin => write!(f, "vultr_origin"),
            PeerType::Unknown => write!(f, "unknown"),
        }
    }
}

impl From<u32> for PeerType {
    fn from(value: u32) -> Self {
        match value {
            100 => PeerType::Transit,
            200 => PeerType::PublicPeer,
            300 => PeerType::PrivatePeer,
            4000 => PeerType::Customer,
            500 => PeerType::VultrOrigin,
            _ => PeerType::Unknown,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_communities() {
        let input = "(20473,100) (20473,3356) (64515,44)";
        let result = parse_communities(input);
        assert_eq!(result, vec![(20473, 100), (20473, 3356), (64515, 44)]);
    }

    #[test]
    fn test_parse_large_communities() {
        let input = "(20473, 100, 3356) (20473, 200, 64515)";
        let result = parse_large_communities(input);
        assert_eq!(result, vec![(20473, 100, 3356), (20473, 200, 64515)]);
    }

    #[test]
    fn test_detect_peer_type() {
        let communities = vec![(20473, 100)];
        let result = PeerType::detect_from_communities(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&PeerType::Transit));

        let communities = vec![(20473, 3356), (20473, 200)];
        let result = PeerType::detect_from_communities(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&PeerType::PublicPeer));

        let communities = vec![(20473, 300)];
        let result = PeerType::detect_from_communities(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&PeerType::PrivatePeer));

        let communities = vec![(20473, 4000)];
        let result = PeerType::detect_from_communities(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&PeerType::Customer));

        let communities = vec![(20473, 500)];
        let result = PeerType::detect_from_communities(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&PeerType::VultrOrigin));

        let communities = vec![(20473, 999)];
        let result = PeerType::detect_from_communities(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&PeerType::Unknown));
    }

    #[test]
    fn test_detect_peer_type_from_large() {
        let communities = vec![(20473, 100, 3356)];
        let result = PeerType::detect_from_large(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&(PeerType::Transit, 3356)));

        let communities = vec![(20473, 200, 64515)];
        let result = PeerType::detect_from_large(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&(PeerType::PublicPeer, 64515)));

        let communities = vec![(20473, 999, 12345), (20473, 300, 12345)];
        let result = PeerType::detect_from_large(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&(PeerType::PrivatePeer, 12345)));

        let communities = vec![(20473, 999, 12345)];
        let result = PeerType::detect_from_large(&communities);
        assert_eq!(result.len(), 1);
        assert!(result.contains(&(PeerType::Unknown, 0)));
    }

    fn create_test_route(as_path: Option<Vec<u32>>) -> Route {
        Route {
            net: "test".to_string(),
            rtype: "test".to_string(),
            proto: "test".to_string(),
            since: "test".to_string(),
            from: "test".to_string(),
            primary: None,
            info: None,
            iface: None,
            via: None,
            attributes: Attributes {
                bgp_type: "test".to_string(),
                bgp_origin: "test".to_string(),
                bgp_as_path: as_path,
                bgp_next_hop: "test".to_string(),
                bgp_local_pref: 0,
                bgp_atomic_aggr: None,
                bgp_aggregator: None,
                bgp_community: None,
                bgp_large_community: None,
                bgp_med: None,
                bgp_otc: None,
            },
        }
    }

    #[test]
    fn test_extract_vultr_neighbor() {
        let route = create_test_route(Some(vec![64515, 65534, 20473, 3356, 55644, 45271]));
        assert_eq!(route.extract_vultr_neighbor(), Some(3356));

        let route = create_test_route(Some(vec![20473, 3356]));
        assert_eq!(route.extract_vultr_neighbor(), Some(3356));

        let route = create_test_route(Some(vec![20473]));
        assert_eq!(route.extract_vultr_neighbor(), None);

        let route = create_test_route(Some(vec![12345, 67890]));
        assert_eq!(route.extract_vultr_neighbor(), None);

        let route = create_test_route(None);
        assert_eq!(route.extract_vultr_neighbor(), None);
    }

    #[test]
    fn test_parse_empty_communities() {
        assert!(parse_communities("").is_empty());
        assert!(parse_large_communities("").is_empty());
    }

    #[test]
    fn test_parse_malformed_communities() {
        let input = "(20473,100,extra) (invalid) (20473)";
        let result = parse_communities(input);
        assert!(result.is_empty());

        let input = "(20473,100) (20473,200,300,400)";
        let result = parse_large_communities(input);
        assert!(result.is_empty());
    }

    #[test]
    fn test_peer_type_from_u32() {
        assert_eq!(PeerType::from(100u32), PeerType::Transit);
        assert_eq!(PeerType::from(200u32), PeerType::PublicPeer);
        assert_eq!(PeerType::from(300u32), PeerType::PrivatePeer);
        assert_eq!(PeerType::from(4000u32), PeerType::Customer);
        assert_eq!(PeerType::from(500u32), PeerType::VultrOrigin);
        assert_eq!(PeerType::from(999u32), PeerType::Unknown);
    }
}
