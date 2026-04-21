#!/bin/bash
set -eu

source peering-common.sh

OUTDIR=results-latency-cli

if [[ $UID -ne 0 ]]; then
    term "This script requires sudo"
fi

if ! command -v uv >/dev/null 2>&1; then
    term "uv is not on PATH; try: sudo -E --preserve-env=PATH"
fi

if [[ ${VIRTUAL_ENV:-undef} = undef ]]; then
    source ../../.venv/bin/activate
fi

export PREFIX=${PREFIXES[0]}
export MUX=ufmg01

echo "Using environment at $VIRTUAL_ENV"
echo "Using uv at $(command -v uv)"

if ! peering bgp status | grep $MUX | grep -q Established; then
    term "$MUX session down"
fi
echo "BGP session to $MUX is up"

echo "Announcing prefix $PREFIX to $MUX"
peering prefix announce -R -m $MUX $PREFIX
peering bgp adv $MUX
echo "Waiting for route convergence"

rm -rf $OUTDIR

echo "Launching measure-latency"
unxz --keep --force test-targets.txt.xz
uv run measure-latency --prefix $PREFIX --mux $MUX \
    --hitlist test-targets.txt \
    --outdir $OUTDIR \
    --pps 5 --max-probes 1 --max-replies 1
rm -f test-targets.txt

echo "Withdrawing $PREFIX"
peering prefix withdraw $PREFIX

echo "=== RESULTS ==="
report_sc_ping_stats $OUTDIR
