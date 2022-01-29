#!/bin/bash
set -eu

progdir=$(cd "$(dirname "$(readlink -f "$0")")"; pwd -P)
source "$progdir/config.sh"

function generate_maps {
    # This function is no longer necessary as these files are now
    # generated inside measure-catchments
    local cdir=$1
    rm -f "$cdir/catchments/mux-tap-dump.txt"
    rm -f "$cdir/catchments/src-emux-remotes.txt"
    for mux in "${!mux2octet[@]}" ; do
        local octet=${mux2octet[$mux]}
        local devid=${mux2id[$mux]}
        local tap=tap$devid
        local ip="184.164.$octet.$(( 128 + devid ))"
        local dump="$cdir/catchments/$mux.dump"
        local remotes="$cdir/targets/${mux}_targets.txt"
        echo "$mux $tap $dump" >> "$cdir/catchments/mux-tap-dump.txt"
        echo "$ip $mux $remotes" >> "$cdir/catchments/src-emux-remotes.txt"
    done
}

# basedir=/.../client/utils/reverse-traceroute/results/revtr-ispy-exp
basedir=$1

for cdir in "$basedir/"* ; do
    echo "$cdir"
    # generate_maps "$cdir"
    ./build-catchments.py --mux-tap-dump "$cdir/catchments/mux-tap-dump.txt" \
            --src-emux-remotes "$cdir/catchments/src-emux-remotes.txt" \
            --out "$cdir/catchments/src2remote2tap.json"
done
