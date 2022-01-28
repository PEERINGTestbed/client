#!/bin/bash
set -eu

# We currently run this script on achtung17. It migrates data from MySQL
# into Clickhouse and then extracts the list of targets for pinging into
# JSON files.

progdir=$(cd "$(dirname "$(readlink -f "$0")")"; pwd -P)
source "$progdir/config.sh"

label=$1
outdir="/home/$USER/compute-targets/$label"

mkdir -p "$outdir"

pushd /home/kevin/rankingservice &> /dev/null

python3 -m algorithms.evaluation.revtr_database_peering "$label" "$label" \
        &> "$outdir/revtr_database_peering.log"

python3 -m algorithms.evaluation.bgp_hijack_evaluation \
        "reverse_traceroutes_$label" \
        "reverse_traceroute_hops_$label" \
        "traceroutes_$label" \
        "traceroute_hops_$label" \
        "$outdir/revtr_hops_per_source.json" \
        "$outdir/fwdtr_hops_per_source.json" \
        &> "$outdir/bgp_hijack_evaluation.log"
