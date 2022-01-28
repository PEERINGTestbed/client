#!/bin/bash
set -eu

# We currently run this script on walter.ccs.neu.edu as a more reliable
# way of batching RevTr requests.

progdir=$(cd "$(dirname "$(readlink -f "$0")")"; pwd -P)
source "$progdir/config.sh"

label=$1
mkdir -p "$APILOGDIR"

pushd /home/kevin/go/src/github.com/NEU-SNS/ReverseTraceroute/cmd &> /dev/null

nohup /usr/local/go/bin/go run revtr_survey_peering/revtr_survey_peering.go \
        "$label" $APITRACES &> "$APILOGDIR/$label.txt"
