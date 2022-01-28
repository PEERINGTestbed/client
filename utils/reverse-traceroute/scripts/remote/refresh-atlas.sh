#!/bin/bash
set -eux

# We currently run this script on walter.ccs.neu.edu because that is
# where the dev RevTr deployment is running and the machine is
# firewalled. So to avoid tunnels we just SSH in and run this script.
# APIHOST and APIPORT are then local.

progdir=$(cd "$(dirname "$(readlink -f "$0")")"; pwd -P)
source "$progdir/config.sh"

for mux in "${!mux2octet[@]}" ; do
        octet=${mux2octet[$mux]}
        muxid=${mux2id[$mux]}
        v4addr="184.164.$octet.$(( 128 + muxid ))"
        curl -X POST --insecure --silent --show-error \
                -H "Revtr-Key: $APIKEY" \
                -H "source:$v4addr" \
                https://$APIHOST:$APIPORT/api/v1/atlas/clean
        sleep 2s
        curl -X POST --insecure --silent --show-error \
                -H "Revtr-Key: $APIKEY" \
                -H "source:$v4addr" \
                https://$APIHOST:$APIPORT/api/v1/atlas/run
        sleep 2s
done
