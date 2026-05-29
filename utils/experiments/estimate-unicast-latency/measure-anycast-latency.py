#!/usr/bin/env python3

import logging
import math
import pathlib

import defs

from peering import Announcement, Mux, Sequencer, Update
from peering.latency import (
    MeasureLatencyCallbackData,
    round_callback as measure_latency,
)

FIRST_ROUND = 0
OUTDIR = pathlib.Path("unicast_latency_measurements")
DESCRIPTION = "Unicast Latency Measurements"


def generate_unicast_announcements() -> list[Update]:
    muxes = set(Mux)
    muxes -= {Mux.uw01, Mux.cfuseast1}
    updates: list[Update] = []
    for mux in sorted(muxes):
        upd = Update(
            withdraw=muxes - {mux},
            announce=[Announcement(muxes={mux})],
            description=f"unicast:{mux}",
        )
        updates.append(upd)
    return updates


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s")
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler(OUTDIR / "log.txt"))

    updates = generate_unicast_announcements()

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
        egress_priority=[],
        updates=updates,
    )
    cbcfg = MeasureLatencyCallbackData(
        basedir=defs.BASEDIR,
        targets_fn=defs.TARGETS_FILE,
        max_pps=len(defs.PREFIXES) * defs.PER_PFX_PPS,
        per_pfx_pps=defs.PER_PFX_PPS,
        probe_method="ICMP-echo",
        max_probes=3,
        max_replies=3,
    )

    callbacks = [Sequencer.RoundCallback(name="measure-latency", func=measure_latency, data=cbcfg)]
    sequencer = Sequencer(seqcfg)
    sequencer.run(callbacks, FIRST_ROUND)


if __name__ == "__main__":
    main()
