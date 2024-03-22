#!/usr/bin/env python3

import json
import logging
import os
import pathlib
import sys
import time
from ipaddress import IPv4Network

import defs
from revtr import RevTrApi

import peering
from peering import Announcement, AnnouncementController, Update

LABEL_BASE = "pythia_sigcomm24_hijacks_r9"
HIJACK_PROVIDER_START = 1
HIJACK_PROVIDER_END = 2


def generate_configurations() -> dict[str, Update]:
    label2update: dict[str, Update] = {}
    for ocity in defs.MUX2PFX:
        for hcity in defs.MUX2PFX:
            if ocity == hcity:
                continue
            for hprovidx in range(HIJACK_PROVIDER_START, HIJACK_PROVIDER_END):
                hprov = defs.MUX2PROVS[hcity][hprovidx % len(defs.MUX2PROVS[hcity])]
                hcomms = peering.Vultr.communities_announce_to_upstreams([hprov])
                ocomms = peering.Vultr.communities_do_not_announce([hprov])
                hann = Announcement([hcity], [], hcomms, [])
                oann = Announcement([ocity], [], ocomms, [])
                update = Update([], [oann, hann])
                label = f"{LABEL_BASE}_{ocity}_{hcity}_as{hprov}_idx{hprovidx}"
                label2update[label] = update
    logging.info("Generated %d configurations", len(label2update))
    for label, update in label2update.items():
        logging.info("%s: %s", label, update.to_json())
    return label2update


def dump_tcpdump_info(
    tcpdump_outdir: pathlib.Path, pfx2label: dict[str, str], pfx2ann: dict[str, Update]
):
    os.makedirs(tcpdump_outdir, exist_ok=True)
    with open(tcpdump_outdir / "labels.json", "w", encoding="utf8") as fd:
        json.dump(pfx2label, fd, indent=2)
    with open(tcpdump_outdir / "announcements.json", "w", encoding="utf8") as fd:
        json.dump(pfx2ann, fd, indent=2, default=lambda x: x.to_dict())


def main():
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s"
    )
    handler = logging.getLogger()
    handler.addHandler(logging.FileHandler("run-citypairs.log"))
    logging.info("Starting %s tstamp is %s", LABEL_BASE, time.time())

    targets = [l.strip() for l in open(defs.TARGETS_FILE, encoding="utf8")]
    logging.info("Got %d targets", len(targets))

    controller = AnnouncementController(
        defs.BIRD_CFG_DIR, defs.BIRD4_SOCK_PATH, defs.ANNOUNCEMENT_SCHEMA
    )
    revtr = RevTrApi(defs.REVTRKEY)

    label2update = generate_configurations()

    tasks = iter(label2update.items())
    done = False
    i = 0
    while not done:
        i += 1
        defs.withdraw_prefixes(controller)
        pfx2label: dict[str, str] = {}
        pfx2ann: dict[str, Update] = {}
        for prefix, egress in defs.PFX2MUX.items():
            try:
                label, update = next(tasks)
                pfx2label[prefix] = label
                has_egress_route = any(egress in ann.muxes for ann in update.announce)
                if not has_egress_route:
                    avoid_rpf = Announcement([egress], [], [(20473,6000)], [])
                    update.announce.append(avoid_rpf)
                pfx2ann[prefix] = update
            except StopIteration:
                done = True
                break
        defs.deploy_pfx2ann(controller, pfx2ann)
        defs.rebuild_revtr_atlas(revtr, wait=False)
        catchments_tstamp = time.time()
        tcpdump_outdir = pathlib.Path(f"tcpdump/round{i}")
        dump_tcpdump_info(tcpdump_outdir, pfx2label, pfx2ann)
        defs.measure_catchments(tcpdump_outdir)
        catchments_runtime = time.time() - catchments_tstamp
        logging.info("Took %f seconds to measure catchments", catchments_runtime)
        revtr_atlas_wait = defs.REVTR_ATLAS_REBUILD_TIME - catchments_runtime
        if revtr_atlas_wait > 1:
            logging.info(
                "Sleeping %f seconds for RevTr atlas to rebuild", revtr_atlas_wait
            )
            time.sleep(revtr_atlas_wait)

        for mux, vpip in defs.MUX2VPIP.items():
            octet = int(IPv4Network(defs.MUX2PFX[mux]).network_address.packed[2])
            pairs = [(vpip, dst) for dst in targets]
            label = f"{pfx2label[defs.MUX2PFX[mux]]}_{octet}"
            logging.info("Running %s RevTrs with label %s", len(pairs), label)
            revtr.multibatch(pairs, label)
        logging.info("Waiting %d seconds for RevTrs to complete", defs.REVTR_BATCH_TIME)
        time.sleep(defs.REVTR_BATCH_TIME)


if __name__ == "__main__":
    sys.exit(main())
