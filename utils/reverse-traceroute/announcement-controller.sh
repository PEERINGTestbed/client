#!/bin/bash
set -eu
set -x

export progdir=$(cd "$(dirname "$(readlink -f "$0")")"; pwd -P)
source "$progdir/config.sh"

echo "Copying remote scripts to $REVTR_CONTROLLER_HOST"

su $USER -c "scp -r \"$progdir/$REMOTE_SCRIPTS_DIR/\"* $REVTR_CONTROLLER_HOST:"
su $USER -c "scp -r \"$progdir/$REMOTE_SCRIPTS_DIR/\"* $REVTR_DB_HOST:"

PATH=$PATH:$progdir:$progdir/scripts

for i in $(seq $((${#mux2octet[@]} - 1)) ) ; do
    echo "Starting round $i"
    label=${REVTR_LABEL}_round_$i
    outdir="$OUTDIR/$label"
    mkdir -p "$outdir"

    take-snapshot "$outdir/pre-container-shutdown" 0
    revtr-containers stop

    take-snapshot "$outdir/pre-withdraw" 0
    announcements.py withdraws "$outdir/announce-withdraws.json"
    ./peering.py "$outdir/announce-withdraws.json"
    take-snapshot "$outdir/post-withdraw" 0
    sleep $CONVERGENCE_TIME

    take-snapshot "$outdir/pre-announcement" 1
    announcements.py legit "$outdir/announce-legit.json"
    ./peering.py "$outdir/announce-legit.json"
    take-snapshot "$outdir/post-announcement" 0
    sleep $CONVERGENCE_TIME

    take-snapshot "$outdir/pre-start-containers" 1
    revtr-containers start
    # giving Docker some slack to start the containers and the
    # RevTr controller to take the VPs in.
    sleep $CONTAINER_START_TIME

    take-snapshot "$outdir/pre-refresh-atlas" 0
    su $USER -c "ssh walter ./refresh-atlas.sh"
    # refresh atlas is asynchronous, but we need to wait for RIPE Atlas
    # and the RR aliasing probes.
    sleep $ATLAS_REFRESH_TIME

    take-snapshot "$outdir/pre-run-revtrs" 0
    su $USER -c "ssh walter ./launch-revtrs.sh $label"
    # launch-revtrs blocks until RevTr takes in the last batch, which is
    # up to 100K revtrs. we block a while to allow them to finish.
    sleep $REVTR_WAIT_TIME

    take-snapshot "$outdir/pre-hijacks" 0
    announcements.py hijacks "$outdir/announce-hijacks.json" "$i"
    ./peering.py "$outdir/announce-hijacks.json"
    take-snapshot "$outdir/post-hijacks" 0
    sleep $CONVERGENCE_TIME

    take-snapshot "$outdir/pre-compute-targets" 0
    compute-targets "$outdir/targets" "$label"

    take-snapshot "$outdir/pre-catchment" 1
    measure-catchments "$outdir/targets" "$outdir/catchments"
    # measure-catchments is synchronous
done