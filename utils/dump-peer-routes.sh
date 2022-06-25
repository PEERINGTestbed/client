#!/bin/sh

progdir=$(cd "$(dirname "$0")" && pwd -P)

BIRD_SOCKET=$(readlink -e "$progdir/../var/bird.ctl")
OUTPUT_FILE=$(pwd)/dump.json.gz

if [ ! -e "$BIRD_SOCKET" ] ; then
    echo "BIRD socket not found at $BIRD_SOCKET"
fi

echo "Dumping peer routes from BIRD instance on $BIRD_SOCKET"
echo "into $OUTPUT_FILE"

# Note: birdc prints some trash on the beginning of its "bird>" prompt.
# We use sed to get rid of it.
echo "show route table rtup all" | sudo birdc -r -s "$BIRD_SOCKET" \
        | sed 's/^bird> \r\x1b\[K//' \
        | tail -n +4 \
        | "$progdir/bird-route-parser/parse.py" --in - --out "$OUTPUT_FILE" \
                --route
