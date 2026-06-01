#!/bin/bash
set -eu
set -x

source peering-common.sh

OUTDIR=results-catchment-cli

if [[ $UID -ne 0 ]]; then
    term "This script requires sudo"
fi

if ! command -v uv >/dev/null 2>&1; then
    term "uv is not on PATH; try: sudo -E --preserve-env=PATH"
fi

if ! command -v tcpdump >/dev/null 2>&1; then
    term "tcpdump is not on PATH"
fi

if [[ ${VIRTUAL_ENV:-undef} = undef ]]; then
    source ../../.venv/bin/activate
fi

export PREFIX=${PREFIXES[0]}
export MUXES=(vtrnewjersey vtramsterdam)

echo "Using environment at $VIRTUAL_ENV"
echo "Using uv at $(command -v uv)"

for mux in "${MUXES[@]}" ; do
    if ! peering bgp status | grep $mux | grep -q Established; then
        term "$mux session down"
    fi
    echo "BGP session to $mux is up"

    echo "Announcing prefix $PREFIX to $mux"
    peering prefix announce -R -m $mux $PREFIX
    peering bgp adv $mux
done

echo "Waiting 30s for route convergence"
sleep 30s

rm -rf $OUTDIR

echo "Launching measure-catchments"
unxz --keep --force test-targets.txt.xz
uv run measure-catchments --prefix $PREFIX --mux ${MUXES[0]} \
    --hitlist test-targets.txt \
    --outdir $OUTDIR \
    --pps 5
rm -f test-targets.txt

echo "Withdrawing $PREFIX"
peering prefix withdraw $PREFIX

echo "=== RESULTS ==="
report_pcap_stats $OUTDIR
