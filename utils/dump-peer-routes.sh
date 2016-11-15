#!/bin/sh

BIRD_SOCKET=../var/bird.ctl

echo "show route table rtup all" | sudo birdc -r -s $BIRD_SOCKET \
        | sed 's/^.*\[K//' | tail -n +4 \
        | bird-route-parser/parse.py --in - --out dump.json.gz --route
