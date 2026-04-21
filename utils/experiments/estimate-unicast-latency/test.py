#!/usr/bin/env python3

import logging
from ipaddress import IPv4Network

import defs

import peering
from peering import (
    Announcement,
    ControlPlane,
    MuxName,
    Update,
)


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler("log.txt"))

    controller = ControlPlane(
        [IPv4Network("184.164.224.0/24")],
        defs.BIRD_CFG_DIR,
        defs.BIRD4_SOCK_PATH,
        schema_file=defs.ANNOUNCEMENT_SCHEMA,
        mux2tap_file=defs.MUX2TAP_FILE,
    )

    pfx2upd = {
        "184.164.224.0/24": Update(
            [MuxName.amsterdam01],
            [Announcement([MuxName.ufmg01], large_communities=[(6777, 0, 0)])],
            "test",
        )
    }
    updset = peering.UpdateSet(pfx2upd)
    controller.deploy(updset)


if __name__ == "__main__":
    main()
