#!/usr/bin/env python3
"""End-to-end test for peering.Sequencer with latency.round_callback.

Uses 4 vtr muxes and 2 prefixes across 2 rounds, replicating
run-latency-test.sh but through the Sequencer orchestration layer.

Assumes OpenVPN tunnels and BIRD sessions are already established.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import pathlib
import subprocess
import sys

from peering import Announcement, Mux, Sequencer, Update
from peering.latency import MeasureLatencyCallbackData, round_callback

BASEDIR = pathlib.Path(__file__).resolve().parents[4]
PREFIXES = [
    ipaddress.IPv4Network("184.164.224.0/24"),
    ipaddress.IPv4Network("184.164.225.0/24"),
]
VTR_MUXES = [
    Mux.vtramsterdam,
    Mux.vtratlanta,
    Mux.vtrbangalore,
    Mux.vtrchicago,
]
TARGETS_XZ = pathlib.Path(__file__).resolve().parent / "test-targets.txt.xz"
TARGETS_TXT = pathlib.Path(__file__).resolve().parent / "test-targets.txt"
OUTDIR = pathlib.Path(__file__).resolve().parent / "results-latency-sequencer"

ROUND_DURATION = 120
WITHDRAW_DURATION = 15


def decompress_targets() -> None:
    if TARGETS_TXT.exists():
        return
    subprocess.run(
        ["unxz", "--keep", "--force", str(TARGETS_XZ)],
        check=True,
    )


def build_updates() -> list[Update]:
    updates: list[Update] = []
    for mux in VTR_MUXES:
        updates.append(
            Update(
                announce=[Announcement(muxes={mux})],
                description=f"unicast:{mux}",
            )
        )
    return updates


def main() -> None:
    if os.getuid() != 0:
        print("This test requires root (sudo)", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    decompress_targets()

    updates = build_updates()

    seqcfg = Sequencer.Config(
        description="E2E Sequencer test: 4 vtr muxes, 2 prefixes, 2 rounds",
        basedir=BASEDIR,
        outdir=OUTDIR,
        prefixes=PREFIXES,
        round_duration=ROUND_DURATION,
        withdraw_every_round=True,
        withdraw_duration=WITHDRAW_DURATION,
        egress_priority=[],
        updates=updates,
    )

    callbacks = [
        Sequencer.RoundCallback(
            name="measure-latency",
            func=round_callback,
            data=MeasureLatencyCallbackData(
                basedir=BASEDIR,
                targets_fn=TARGETS_TXT,
                max_pps=40,
                per_pfx_pps=20,
                max_probes=4,
                max_replies=3,
            ),
        ),
    ]

    sequencer = Sequencer(seqcfg)
    sequencer.run(callbacks)

    print(f"Test complete. Results in {OUTDIR}")


if __name__ == "__main__":
    main()
