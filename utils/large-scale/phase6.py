#!/usr/bin/env python3

import logging
import math
import pathlib

import controller
import defs
from phases import phase6a, phase6b

FIRST_ROUND = 0

BASEDIR = pathlib.Path("phase6_anycast_withdraw1_1vtr")
DESCRIPTION = "Anycast and Withdraw from 1 mux and 1 Vultr provider"


def main() -> None:
    BASEDIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler(BASEDIR / "log.txt"))

    updates = phase6a() + phase6b()
    logging.info("Starting experiment %s", BASEDIR)
    nrounds = math.ceil(len(updates) / len(defs.PREFIXES))
    logging.info("Will deploy %d announcements in %d rounds", len(updates), nrounds)
    logging.info("Starting at %d", FIRST_ROUND)

    controller.withdraw_round()
    controller.run_loop(updates, FIRST_ROUND, BASEDIR)


if __name__ == "__main__":
    main()
