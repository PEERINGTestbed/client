#!/usr/bin/env python3

import logging
import pathlib

import controller
from peering import (
    IXP_SPECIAL_PEERS_V4,
    Announcement,
    MuxName,
    PeeringCommunities,
    Update,
)

FIRST_ROUND = 0

BASEDIR = pathlib.Path("phase2_anycast_prepend1")
DESCRIPTION = "Anycast and Prepend 1"
AS_PATH_PREPEND_LIST = [47065, 47065, 47065]

def phase2a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux in MuxName:
        description = f"anycast+prepend:{mux}"
        withdraw = []
        muxes = set(MuxName)
        muxes.discard(mux)
        announce1 = Announcement([mux], prepend=AS_PATH_PREPEND_LIST)
        announce2 = Announcement(list(muxes))
        announce = [announce1, announce2]
        updates.append(Update(withdraw, announce, description))
    return updates


def phase2b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
        for peerids in asn2peerids.values():
            description = (
                f"anycast+withdraw:{mux}+prepend:{','.join(str(p) for p in peerids)}"
            )
            withdraw = []
            muxes = set(MuxName)
            muxes.discard(mux)
            communities = [PeeringCommunities.announce_to(pid) for pid in peerids]
            announce1 = Announcement(
                [mux], prepend=AS_PATH_PREPEND_LIST, communities=communities
            )
            announce2 = Announcement(list(muxes))
            announce = [announce1, announce2]
            updates.append(Update(withdraw, announce, description))
    return updates


def main() -> None:
    BASEDIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler(BASEDIR / "log.txt"))

    updates = phase2a() + phase2b()
    logging.info("Starting experiment %s", BASEDIR)
    logging.info("Will deploy %d announcements", len(updates))

    controller.withdraw_round()
    controller.run_loop(updates, FIRST_ROUND, BASEDIR)

if __name__ == "__main__":
    main()
