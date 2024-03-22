#!/bin/bash
set -eu

DATADIR=tcpdump.filed/hijacks_r9_idx12/
ICMPBASE=44000
cc=../measure-catchments/compute-catchments.sh

for i in $(seq 5) ; do
    for idx_octet in 1_224 2_225 3_231 4_233 5_234 6_235 ; do
        idx=${idx_octet%%_*}
        octet=${idx_octet##*_}
        dir="$DATADIR/round${i}_$octet"
        label=$(jq -r '.["184.164.'$octet'.0/24"]' "$DATADIR/round$i/labels.json")
        echo $cc -I $(( ICMPBASE + idx - 1)) -d "$dir" \
                -o "$DATADIR/catch_$label.txt"
        $cc \
                -I $(( ICMPBASE + idx -1 )) \
                -d "$dir" \
                -o "$DATADIR/catch_$label.txt" \
                > "$DATADIR/catch_summary_$label.txt"
                # -I $(( ICMPBASE + i - 1)) \  FIXME
    done
done
