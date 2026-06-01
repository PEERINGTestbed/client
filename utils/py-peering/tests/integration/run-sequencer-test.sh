#!/bin/bash
set -eu

source peering-common.sh

if [[ $UID -ne 0 ]]; then
    term "This script requires sudo"
fi

if ! command -v uv >/dev/null 2>&1; then
    term "uv is not on PATH; try: sudo -E --preserve-env=PATH"
fi

if ! command -v scamper >/dev/null 2>&1; then
    term "scamper is not on PATH; try: sudo -E --preserve-env=PATH"
fi

if [[ ${VIRTUAL_ENV:-undef} = undef ]]; then
    source ../../.venv/bin/activate
fi

RESULTSDIR=results-sequencer

echo "Using environment at $VIRTUAL_ENV"
echo "Using uv at $(command -v uv)"

rm -rf $RESULTSDIR

unxz --keep --force test-targets.txt.xz
./run-sequencer-test.py $RESULTSDIR
rm -f test-targets.txt

echo "=== RESULTS ==="
report_sc_ping_stats $RESULTSDIR
report_pcap_stats $RESULTSDIR
