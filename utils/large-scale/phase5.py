#!/usr/bin/env python3

import itertools
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

BASEDIR = pathlib.Path("phase5_anycast_withdraw2")
DESCRIPTION = "Anycast and Withdraw 2"


def phase5a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for (mux1, mux2) in itertools.combinations(MuxName, 2):
        description = f"anycast+withdraw:{mux1},{mux2}"
        withdraw = [mux1, mux2]
        muxes = set(MuxName)
        muxes.discard(mux1)
        muxes.discard(mux2)
        announce = [Announcement(list(muxes))]
        updates.append(Update(withdraw, announce, description))
    return updates


def phase5b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    for mux1 in MuxName:
        for mux2, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
            for peerids in asn2peerids.values():
                description = (
                    f"anycast+withdraw:{mux1},{mux2}+announce:{','.join(str(p) for p in peerids)}"
                )
                withdraw = [mux1]
                muxes = set(MuxName)
                muxes.discard(mux1)
                communities = [PeeringCommunities.announce_to(pid) for pid in peerids]
                announce1 = Announcement([mux2], communities=communities)
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

    updates = phase5a() + phase5b()
    logging.info("Starting experiment %s", BASEDIR)
    logging.info("Will deploy %d announcements", len(updates))

    controller.withdraw_round()
    controller.run_loop(updates, FIRST_ROUND, BASEDIR)

if __name__ == "__main__":
    main()
