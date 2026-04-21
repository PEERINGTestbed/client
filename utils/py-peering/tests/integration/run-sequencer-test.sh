#!/bin/bash
set -eu

source peering-common.sh

if [[ $UID -ne 0 ]] ; then
    term "This script requires sudo"
fi

if ! command -v uv >/dev/null 2>&1 ; then
    term "uv is not on PATH; try: sudo -E --preserve-env=PATH"
fi

if ! command -v scamper >/dev/null 2>&1 ; then
    term "scamper is not on PATH; try: sudo -E --preserve-env=PATH"
fi

if [[ ${VIRTUAL_ENV:-undef} = undef ]] ; then
    source ../../.venv/bin/activate
fi

echo "Using environment at $VIRTUAL_ENV"
echo "Using uv at $(command -v uv)"

rm -rf results-latency-sequencer

./run-sequencer-test.py

echo "=== RESULTS ==="
report_sc_ping_stats results-latency-sequencer
