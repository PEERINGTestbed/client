use std::collections::HashMap;
use std::path::PathBuf;

use vultr_provider_matrix::{Args, FileResult};
use vultr_provider_matrix::inout;

#[test]
fn test_end_to_end_processing() {
    // Create a temporary directory for test output
    let temp_dir = tempfile::tempdir().expect("Failed to create temp dir");
    let output_path = temp_dir.path().join("test_output.json");

    // Test data directory
    let test_data_dir = PathBuf::from("tests/data");

    // Create args for processing
    let args = Args {
        directory: test_data_dir.clone(),
        output: output_path.clone(),
        log: None,
        providers: None,
        min_sites: 1,
    };

    // Process the files
    let results = inout::find_table_dump_files(&args.directory)
        .expect("Failed to find test files");

    println!("Processing {} files", results.len());

    let processed_results: HashMap<String, FileResult> = results
        .into_iter()
        .filter_map(|fpath| {
            println!("Processing {:?}", fpath);
            if let Some(mux_proto) = vultr_provider_matrix::get_mux_protocol(&fpath) {
                match vultr_provider_matrix::process_file(&fpath) {
                    Ok(result) => Some((mux_proto, result)),
                    Err(e) => {
                        panic!("Failed to process file {:?}: {}", fpath, e);
                    }
                }
            } else {
                None
            }
        })
        .collect();

    // Verify results
    assert!(!processed_results.is_empty(), "No results processed");

    println!("{:?}", processed_results.keys());

    // Test pass_all_checks file - should have no failed checks
    if let Some(pass_result) = processed_results.get("vtr_pass_all_checks") {
        assert_eq!(pass_result.failed_checks.len(), 0, "pass_all_checks should have no failed checks; has: {:?}", pass_result.failed_checks.keys());
        // Should have 5 peers (one for each route)
        assert_eq!(pass_result.peers.len(), 4, "pass_all_checks should have 4 peers");
    } else {
        panic!("pass_all_checks result not found");
    }

    // Test fail_route_missing_neighbor - should have RouteMissingNeighbor failures
    if let Some(fail_result) = processed_results.get("vtr_fail_route_missing_neighbor") {
        assert!(fail_result.failed_checks.contains_key("RouteMissingNeighbor"),
                "fail_route_missing_neighbor should have RouteMissingNeighbor failures");
        assert!(fail_result.failed_checks["RouteMissingNeighbor"] > 0,
                "Should have at least one RouteMissingNeighbor failure");
    } else {
        panic!("fail_route_missing_neighbor result not found");
    }

    // Test fail_customer_large_comm - should have CustomerWithLargeCommunity failures
    if let Some(fail_result) = processed_results.get("vtr_fail_customer_large_comm") {
        assert!(fail_result.failed_checks.contains_key("CustomerWithLargeCommunity"),
                "fail_customer_large_comm should have CustomerWithLargeCommunity failures");
        assert!(fail_result.failed_checks["CustomerWithLargeCommunity"] > 0,
                "Should have at least one CustomerWithLargeCommunity failure");
    } else {
        panic!("fail_customer_large_comm result not found");
    }

    // Test fail_neighbor_inconsistency - should have NeighborAsnInconsistency failures
    if let Some(fail_result) = processed_results.get("vtr_fail_neighbor_inconsistency") {
        assert!(fail_result.failed_checks.contains_key("NeighborAsnInconsistency"),
                "fail_neighbor_inconsistency should have NeighborAsnInconsistency failures");
        assert!(fail_result.failed_checks["NeighborAsnInconsistency"] > 0,
                "Should have at least one NeighborAsnInconsistency failure");
    } else {
        panic!("fail_neighbor_inconsistency result not found");
    }

    // Test fail_route_inconsistent_types - should have RouteInconsistentPeerTypes failures
    if let Some(fail_result) = processed_results.get("vtr_fail_route_inconsistent_types") {
        assert!(fail_result.failed_checks.contains_key("RouteInconsistentPeerTypes"),
                "fail_route_inconsistent_types should have RouteInconsistentPeerTypes failures");
        assert!(fail_result.failed_checks["RouteInconsistentPeerTypes"] > 0,
                "Should have at least one RouteInconsistentPeerTypes failure");
    } else {
        panic!("fail_route_inconsistent_types result not found");
    }

    // Test fail_as_inconsistent_types - should have AsInconsistentPeerTypes failures
    if let Some(fail_result) = processed_results.get("vtr_fail_as_inconsistent_types") {
        println!("failed_checks: {:?}", fail_result.failed_checks.keys());
        assert!(fail_result.failed_checks.contains_key("AsInconsistentPeerTypes"),
                "fail_as_inconsistent_types should have AsInconsistentPeerTypes failures");
        assert!(fail_result.failed_checks["AsInconsistentPeerTypes"] > 0,
                "Should have at least one AsInconsistentPeerTypes failure");
    } else {
        panic!("fail_as_inconsistent_types result not found");
    }

    // Test fail_inconsistent_large_comm - should have InconsistentLargeCommPeerAsns failures
    if let Some(fail_result) = processed_results.get("vtr_fail_inconsistent_large_comm") {
        assert!(fail_result.failed_checks.contains_key("InconsistentLargeCommPeerAsns"),
                "fail_inconsistent_large_comm should have InconsistentLargeCommPeerAsns failures");
        assert!(fail_result.failed_checks["InconsistentLargeCommPeerAsns"] > 0,
                "Should have at least one InconsistentLargeCommPeerAsns failure");
    } else {
        panic!("fail_inconsistent_large_comm result not found");
    }

    // Test fail_json_parse - should have JsonParseFailure failures
    if let Some(fail_result) = processed_results.get("vtr_fail_json_parse") {
        assert!(fail_result.failed_checks.contains_key("JsonParseFailure"),
                "fail_json_parse should have JsonParseFailure failures");
        assert!(fail_result.failed_checks["JsonParseFailure"] > 0,
                "Should have at least one JsonParseFailure failure");
    } else {
        panic!("fail_json_parse result not found");
    }

    // Write the results to verify output format
    inout::write_peers_json(&args, &processed_results)
        .expect("Failed to write output");

    // Verify output file was created
    assert!(output_path.exists(), "Output file should exist");

    // Clean up
    temp_dir.close().expect("Failed to clean up temp dir");
}
