#!/usr/bin/env python3

import logging
import pathlib

import controller
import defs
from peering import (
    IXP_SPECIAL_PEERS_V4,
    Announcement,
    MuxName,
    PeeringCommunities,
    Update,
    Vultr,
)

FIRST_ROUND = 6

BASEDIR = pathlib.Path("phase6_anycast_withdraw1_1vtr")
DESCRIPTION = "Anycast and Withdraw from 1 mux and 1 Vultr provider"


def phase6a() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    muxes = set(MuxName)
    nonvtr_muxes = [m for m in muxes if not m.startswith("vtr")]
    vtr_muxes = [m for m in muxes if m.startswith("vtr")]
    for provider in defs.VULTR_PROVIDERS:
        vtr_comms = Vultr.communities_do_not_announce([provider])
        vtr_ann = Announcement(vtr_muxes, communities=vtr_comms)
        for mux in nonvtr_muxes:
            description = f"anycast+withdraw:{mux},vtr{provider}"
            nonvtr_active = set(nonvtr_muxes)
            nonvtr_active.discard(mux)
            nonvtr_ann = Announcement(list(nonvtr_active))
            announce = [nonvtr_ann, vtr_ann]
            updates.append(Update([mux], announce, description))
    return updates


def phase6b() -> list[Update]:
    updates = [Update([], [Announcement(list(MuxName))], "anycast")]
    muxes = set(MuxName)
    nonvtr_muxes = [m for m in muxes if not m.startswith("vtr")]
    vtr_muxes = [m for m in muxes if m.startswith("vtr")]
    for provider in defs.VULTR_PROVIDERS:
        vtr_comms = Vultr.communities_do_not_announce([provider])
        vtr_ann = Announcement(vtr_muxes, communities=vtr_comms)
        for mux, asn2peerids in IXP_SPECIAL_PEERS_V4.items():
            nonvtr_active = set(nonvtr_muxes)
            nonvtr_active.discard(mux)
            nonvtr_active_ann = Announcement(list(nonvtr_active))
            for peerids in asn2peerids.values():
                peerids_str = ','.join(str(p) for p in peerids)
                nonvtr_subpeer_comms = [PeeringCommunities.announce_to(pid) for pid in peerids]
                nonvtr_subpeer_ann = Announcement([mux], communities=nonvtr_subpeer_comms)
                announce = [vtr_ann, nonvtr_active_ann, nonvtr_subpeer_ann]
                description = f"anycast+withdraw:{mux},vtr{provider}+announce:{peerids_str}"
                updates.append(Update([], announce, description))
    return updates


def main() -> None:
    BASEDIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler(BASEDIR / "log.txt"))

    updates = phase6a() + phase6b()
    logging.info("Starting experiment %s", BASEDIR)
    logging.info("Will deploy %d announcements", len(updates))

    controller.withdraw_round()
    controller.run_loop(updates, FIRST_ROUND, BASEDIR)

if __name__ == "__main__":
    main()
