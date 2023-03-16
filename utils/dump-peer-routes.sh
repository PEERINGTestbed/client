#!/bin/bash
set -eu

progdir=$(cd "$(dirname "$0")" && pwd -P)

BIRD4_SOCKET=$(readlink -e "$progdir/../var/bird.ctl")
BIRD6_SOCKET=$(readlink -e "$progdir/../var/bird6.ctl")

OUTPUT4_PREFIX=$(pwd)/dump4
OUTPUT6_PREFIX=$(pwd)/dump6

function get_table {
    local socket=$1
    local outfn=$2
    local birdc=$3

    if [[ ! -e "$socket" ]] ; then
        echo "BIRD socket not found at $socket"
        return
    fi

    echo "Dumping routes from BIRD instance on $socket into $outfn"

    # Note: birdc prints some trash on the beginning of its "bird>" prompt.
    # We use sed to get rid of it.
    echo "show route table rtup all" | sudo "$birdc" -r -s "$socket" \
            | sed 's/^bird> \r\x1b\[K//' \
            | tail -n +4 \
            | gzip \
            > "$outfn"
}

function parse_table {
    local infn=$1
    local outfn=$2
    echo "Parsing $infn -> $outfn"
    "$progdir/bird-route-parser/parse.py" --in "$infn" --out "$outfn" \
            --bird1 --route
}

get_table "$BIRD4_SOCKET" "$OUTPUT4_PREFIX.table.gz" birdc
get_table "$BIRD6_SOCKET" "$OUTPUT6_PREFIX.table.gz" birdc6
parse_table "$OUTPUT4_PREFIX.table.gz" "$OUTPUT4_PREFIX.json.gz"
parse_table "$OUTPUT6_PREFIX.table.gz" "$OUTPUT6_PREFIX.json.gz"
