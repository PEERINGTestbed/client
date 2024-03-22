#!/usr/bin/env python3

import logging
import sys
import time
from ipaddress import IPv4Network

import defs
from revtr import RevTrApi

import peering
from peering import Announcement, AnnouncementController, Update

LABEL_BASE = "pythia_sigcomm24_sloc_r2"


def main():
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler("run-monocity.log"))
    logging.info("Starting %s tstamp is %s", LABEL_BASE, time.time())

    targets = [l.strip() for l in open(defs.TARGETS_FILE, encoding="utf8")]
    logging.info("Got %d targets", len(targets))

    controller = AnnouncementController(
        defs.BIRD_CFG_DIR, defs.BIRD4_SOCK_PATH, defs.ANNOUNCEMENT_SCHEMA
    )
    revtr = RevTrApi(defs.REVTRKEY)

    defs.withdraw_prefixes(controller)

    pfx2ann = {
        prefix: Update([], [Announcement([mux], [], [], [])])
        for prefix, mux in defs.PFX2MUX.items()
    }
    defs.deploy_pfx2ann(controller, pfx2ann)

    defs.rebuild_revtr_atlas(revtr)

    for mux, vpip in defs.MUX2VPIP.items():
        octet = int(IPv4Network(defs.MUX2PFX[mux]).network_address.packed[2])
        pairs = [(vpip, dst) for dst in targets]
        label = f"{LABEL_BASE}_{mux}_{octet}_anycast"
        revtr.multibatch(pairs, label)
        logging.info("Running RevTrs with label %s", label)
    logging.info("Waiting %d seconds for RevTrs to complete", defs.REVTR_BATCH_TIME)
    time.sleep(defs.REVTR_BATCH_TIME)

    rounds = max(len(l) for l in defs.MUX2PROVS.values())
    for i in range(rounds):
        defs.withdraw_prefixes(controller)

        pfx2ann = {}
        for prefix, mux in defs.PFX2MUX.items():
            prov = defs.MUX2PROVS[mux][i % len(defs.MUX2PROVS[mux])]
            comms = peering.Vultr.communities_announce_to_upstreams([prov])
            pfx2ann[prefix] = Update([], [Announcement([mux], [], comms, [])])
        defs.deploy_pfx2ann(controller, pfx2ann)

        defs.rebuild_revtr_atlas(revtr)

        for mux, vpip in defs.MUX2VPIP.items():
            octet = int(IPv4Network(defs.MUX2PFX[mux]).network_address.packed[2])
            pairs = [(vpip, dst) for dst in targets]
            provider = defs.MUX2PROVS[mux][i % len(defs.MUX2PROVS[mux])]
            label = f"{LABEL_BASE}_{mux}_{octet}_as{provider}_idx{i}"
            revtr.multibatch(pairs, label)
            logging.info("Running RevTrs with label %s", label)
        logging.info("Waiting %d seconds for RevTrs to complete", defs.REVTR_BATCH_TIME)
        time.sleep(defs.REVTR_BATCH_TIME)


if __name__ == "__main__":
    sys.exit(main())
