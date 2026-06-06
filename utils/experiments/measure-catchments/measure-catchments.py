#!/usr/bin/env python3

import logging
import math
import pathlib

import defs

from peering import Announcement, Mux, Sequencer, Update
from peering.catchments import (
    MeasureCatchmentsCallbackData,
    round_callback as measure_catchments,
)

FIRST_ROUND = 0
OUTDIR = pathlib.Path("vultronly+anycast+withdraw-1")
DESCRIPTION = "Vultr-only Single-site Outage Emulation"


def generate_vultronly_anycast_withdraw1() -> list[Update]:
    vultr_muxes = set(m for m in Mux if m.startswith("vtr"))
    updates = [
        Update(
            announce=[Announcement(muxes=set(vultr_muxes))],
            description="vultronly+anycast",
        )
    ]
    for mux in vultr_muxes:
        description = f"vultronly+anycast+withdraw({mux})"
        withdraw = set([mux])
        active_muxes = set(vultr_muxes)
        active_muxes.discard(mux)
        announce = [Announcement(muxes=set(active_muxes))]
        updates.append(
            Update(withdraw=withdraw, announce=announce, description=description)
        )
    return updates


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler(OUTDIR / "log.txt"))

    updates = generate_vultronly_anycast_withdraw1()

    logging.info("Starting experiment %s", OUTDIR)
    nrounds = math.ceil(len(updates) / len(defs.PREFIXES))
    logging.info("Will deploy %d announcements in %d rounds", len(updates), nrounds)
    logging.info("Starting at %d", FIRST_ROUND)

    seqcfg = Sequencer.Config(
        description=DESCRIPTION,
        basedir=defs.BASEDIR,
        outdir=OUTDIR,
        prefixes=defs.PREFIXES,
        round_duration=defs.ANNOUNCEMENT_DURATION,
        withdraw_every_round=True,
        withdraw_duration=defs.PROPAGATION_TIME,
        egress_priority=[Mux.vtrnewjersey, Mux.vtramsterdam, Mux.vtrlondon],
        updates=updates,
    )
    cbcfg = MeasureCatchmentsCallbackData(
        basedir=defs.BASEDIR,
        targets_fn=defs.TARGETS_FILE,
        pkts_per_sec=defs.PER_PFX_PPS,
    )

    callbacks = [
        Sequencer.RoundCallback(
            name="measure-catchments", func=measure_catchments, data=cbcfg
        )
    ]
    sequencer = Sequencer(seqcfg)
    sequencer.run(callbacks, FIRST_ROUND)


if __name__ == "__main__":
    main()
