#!/bin/bash
set -eu

source config.sh
APIKEY=49805c86bb9c3e104908c2ab59aff219a2879945

declare -gA mux2dev
while read -r fmux fdev ; do
    mux2dev[$fmux]=$fdev
done < "$CLIENTDIR/var/mux2dev.txt"

LABEL=top-rsd-nofusixtrue
tstamp=$(date +%s)

mkdir -p measurement-ids
for mux in "${MUXES[@]}" ; do
    dev=${mux2dev[$mux]}
    devid=${dev##tap}
    ip=184.164.230.$((128 + devid))
    ./generate-requests.py \
            --source $ip \
            --destinations "catchment-discovery/tcpdump/hitlist-$mux.txt" \
            --api-key $APIKEY \
            --round-duration 1 \
            --round-size 1000 \
            --label $LABEL \
            --results-log "measurement-ids/$LABEL-$mux-$tstamp.txt"
done
