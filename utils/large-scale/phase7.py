#!/usr/bin/env python3

import logging
import math
import pathlib

import controller
import defs
from phases import phase7_muxsets, phase7_muxsets_unicast, phase7a, phase7b

FIRST_ROUND = 0

BASEDIR = pathlib.Path("phase7_unicast2")
DESCRIPTION = "Unicast announcements from 2 sites"


def main() -> None:
    BASEDIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler(BASEDIR / "log.txt"))

    updates = phase7a() + phase7b() + phase7_muxsets() + phase7_muxsets_unicast()
    logging.info("Starting experiment %s", BASEDIR)
    nrounds = math.ceil(len(updates) / len(defs.PREFIXES))
    logging.info("Will deploy %d announcements in %d rounds", len(updates), nrounds)
    logging.info("Starting at %d", FIRST_ROUND)

    controller.withdraw_round()
    controller.run_loop(updates, FIRST_ROUND, BASEDIR)


if __name__ == "__main__":
    main()
