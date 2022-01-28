#!/bin/bash
set -eu
set -x

LABEL=peering-anycast-hitlist-2
MEASUREMENTS_FILE=measurement-ids-$(date +%s)-$LABEL.txt
MEASUREMENT_ROUND_SEC=60
MEASUREMENT_ROUND_REVTRS=500
DSTFILE=filtered-ingresses.txt

rnd=1
cnt=0
while read -r dst ; do
    echo "[$rnd.$cnt] Issuing traceroute to $dst"
    curl --silent -XPOST -k \
            -H "Revtr-Key:49805c86bb9c3e104908c2ab59aff219a2879945" \
            https://revtr.ccs.neu.edu/api/v1/revtr \
            --data '{"revtrs": [{"dst": "'$dst'", "src": "184.164.230.129", "label": "'$LABEL'"}]}' \
            >> "$MEASUREMENTS_FILE"
    cnt=$((cnt+1))
    if [[ $cnt -eq $MEASUREMENT_ROUND_REVTRS ]] ; then
        sleep $MEASUREMENT_ROUND_SEC
        cnt=0
        rnd=$((rnd+1))
    fi
done < "$DSTFILE"

# Retrieving traceroutes
# curl -XGET -k -H "Revtr-Key:49805c86bb9c3e104908c2ab59aff219a2879945" 'https://revtr.ccs.neu.edu/api/v1/revtr?batchid=103071'
