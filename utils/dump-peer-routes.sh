#!/bin/sh

BIRD_SOCKET=../var/bird.ctl
OUTPUT_FILE=dump.json.gz

echo "Dumping peers routes from BIRD instance on $BIRD_SOCKET"
echo "into $OUTPUT_FILE"

echo "show route table rtup all" | sudo birdc -r -s $BIRD_SOCKET \
        | sed 's/^.*\[K//' | tail -n +4 \
        | bird-route-parser/parse.py --in - --out $OUTPUT_FILE --route
