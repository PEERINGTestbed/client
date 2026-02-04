#!/usr/bin/env python3

import logging
import math
import pathlib

import controller
import defs
from phases import phase9

FIRST_ROUND = 0

BASEDIR = pathlib.Path("phase9_unicast1")
DESCRIPTION = "Unicast 1"


def main() -> None:
    BASEDIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler(BASEDIR / "log.txt"))

    updates = phase9()
    logging.info("Starting experiment %s", BASEDIR)
    nrounds = math.ceil(len(updates) / len(defs.PREFIXES))
    logging.info("Will deploy %d announcements in %d rounds", len(updates), nrounds)
    logging.info("Starting at %d", FIRST_ROUND)

    controller.withdraw_round()
    controller.run_loop(updates, FIRST_ROUND, BASEDIR)


if __name__ == "__main__":
    main()
