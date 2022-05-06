#!/bin/bash
set -eu
set -x

progdir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)
export progdir

mode="test"
unlink config.sh
unlink config.py
ln -s config-$mode.sh config.sh
ln -s config-$mode.py config.py
source "$progdir/config.sh"

su $USER -c "scp -r $REMOTE_SCRIPTS_DIR/* $REVTR_CONTROLLER_HOST:"
su $USER -c "scp -r $REMOTE_SCRIPTS_DIR/* $REVTR_DB_HOST:"

PATH=$PATH:$progdir:$progdir/scripts:$progdir/../../


function logcmd {
    echo "$@" >> "$logfile"
    "$@"
}

function announce_prefixes {
    # 224 is unicast
    # 225 is anycast
    # 246 is prepended 3 times
    # 254 is prepended 5 times
    local outdir=$1
    local mux=$2
    export logfile=$outdir/announcements.log
    logcmd peering prefix announce -m "$mux" -R 184.164.224.0/24
    logcmd source-routing setup 224 "$mux"
    for cmux in "${!mux2id[@]}" ; do
        logcmd peering prefix announce -m "$cmux" -R 184.164.225.0/24
        logcmd source-routing setup 225 "$ANYCAST_UPSTREAM_MUX"
        if [[ "$cmux" == "$mux" ]] ; then
            logcmd peering prefix announce -m "$cmux" -R 184.164.246.0/24
            logcmd source-routing setup 246 "$ANYCAST_UPSTREAM_MUX"
            logcmd peering prefix announce -m "$cmux" -R 184.164.254.0/24
            logcmd source-routing setup 254 "$ANYCAST_UPSTREAM_MUX"
        else
            logcmd peering prefix announce -m "$cmux" -P 2 -R 184.164.246.0/24
            logcmd source-routing setup 246 "$ANYCAST_UPSTREAM_MUX"
            logcmd peering prefix announce -m "$cmux" -P 4 -R 184.164.254.0/24
            logcmd source-routing setup 254 "$ANYCAST_UPSTREAM_MUX"
        fi
    done
}

function withdraw_prefixes {
    export logfile=$1/withdrawals.log
    for octet in "${octets[@]}" ; do
        logcmd peering prefix withdraw "184.164.$octet.0/24"
        logcmd source-routing teardown "$octet"
    done
}

for mux in "${!mux2id[@]}" ; do
    echo "Starting round for mux $mux"
    label=${REVTR_LABEL}_round_$mux
    outdir="$OUTDIR/$label"
    mkdir -p "$outdir"

    take-snapshot "$outdir/pre-container-shutdown" 0
    revtr-containers stop

    take-snapshot "$outdir/pre-withdraw" 0
    withdraw_prefixes "$outdir"
    take-snapshot "$outdir/post-withdraw" 0
    sleep $CONVERGENCE_TIME

    take-snapshot "$outdir/pre-announcement" 1
    announce_prefixes "$outdir" "$mux"
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
    jc-exp/compute-srcdsts.sh "$outdir/srcdsts.txt" "$mux"
    scp "$outdir/srcdsts.txt" walter:
    su $USER -c "ssh walter ./launch-revtrs.sh srcdsts.txt $label"
    # launch-revtrs blocks until RevTrs finish. we block an extra while
    # just in case.  in a previous iteration, launch-revtrs returned when it
    # dispatched the last batch, so we had to wait longer.
    sleep $REVTR_WAIT_TIME
    take-snapshot "$outdir/post-run-revtrs" 0
done