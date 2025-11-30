#!/usr/bin/env python3

import logging
import pathlib

import controller
import defs
from peering import (
    Announcement,
    MuxName,
    Update,
    Vultr,
)

FIRST_ROUND = 0

BASEDIR = pathlib.Path("phase4_anycast_prepend_vtr_1")
DESCRIPTION = "Anycast and prepend 1 Vultr provider"


def phase4() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for provider in defs.VULTR_PROVIDERS:
        description = f"anycast+prepend:vtr{provider}"
        muxes = set(MuxName)
        vtrcomm = Vultr.communities_prepend_thrice([provider])
        announce1 = Announcement([m for m in muxes if not m.startswith("vtr")])
        announce2 = Announcement([m for m in muxes if m.startswith("vtr")], communities=vtrcomm)
        announce = [announce1, announce2]
        updates.append(Update([], announce, description))
    return updates


def main() -> None:
    BASEDIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler(BASEDIR / "log.txt"))

    updates = phase4()
    logging.info("Starting experiment %s", BASEDIR)
    logging.info("Will deploy %d announcements", len(updates))

    controller.withdraw_round()
    controller.run_loop(updates, FIRST_ROUND, BASEDIR)

if __name__ == "__main__":
    main()
