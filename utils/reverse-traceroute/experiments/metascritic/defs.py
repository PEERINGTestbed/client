import logging
import os
import pathlib
import subprocess
import time
from ipaddress import IPv4Address, IPv4Network

from revtr import RevTrApi
from peering import AnnouncementController, Update, UpdateSet
import peering

PFX2MUX = {
    "184.164.224.0/24": "vtramsterdam",
    "184.164.225.0/24": "vtrnewyork",
    "184.164.231.0/24": "vtrsaopaulo",
    "184.164.233.0/24": "vtrsingapore",
    "184.164.234.0/24": "vtrsydney",
    "184.164.235.0/24": "vtrtokyo",
}
MUX2PFX = {v: k for k, v in PFX2MUX.items()}
PFX2VPIP = {p: str(next(IPv4Network(p).hosts())) for p in PFX2MUX}
MUX2VPIP = {v: PFX2VPIP[k] for k, v in PFX2MUX.items()}

MUX2PROVS = {
    "vtramsterdam": [2914, 3257, 1299, 3356],
    "vtrnewyork": [2914, 3257, 1299, 3356, 174],
    "vtrsaopaulo": [2914, 3257, 174],
    "vtrsingapore": [2914, 3257, 1299],
    "vtrsydney": [2914, 3257],
    "vtrtokyo": [2914, 1299],
}

PROPAGATION_TIME = 900
REVTR_REQ_DELAY = 4
REVTR_ATLAS_REBUILD_TIME = 3600
REVTR_BATCH_TIME = 7200

BIRD_CFG_DIR = pathlib.Path("../../", peering.DEFAULT_BIRD_CFG_DIR)
BIRD4_SOCK_PATH = pathlib.Path("../../", peering.DEFAULT_BIRD4_SOCK_PATH)
ANNOUNCEMENT_SCHEMA = pathlib.Path("../../", peering.DEFAULT_ANNOUNCEMENT_SCHEMA)
REVTRKEY = open("/home/cunha/.config/revtr.apikey", encoding="utf8").read().strip()
TARGETS_FILE = pathlib.Path("targets.txt")

CATCHMENTS_DIR = pathlib.Path("../measure-catchments")
CATCHMENTS_ICMPID_BASE = 44000
CATCHMENTS_PINGER_PPS = 600


def withdraw_prefixes(controller: AnnouncementController):
    for prefix in PFX2MUX:
        controller.withdraw(prefix)
    controller.reload_config()
    logging.info("Waiting %d seconds for withdrawals to converge", PROPAGATION_TIME)
    time.sleep(PROPAGATION_TIME)


def deploy_pfx2ann(controller: AnnouncementController, pfx2ann: dict[str, Update]):
    updset = UpdateSet(pfx2ann)
    controller.deploy(updset)
    logging.info("PEERING deploy %s %s", time.time(), updset.to_json())
    logging.info("Waiting %d seconds for announcements to propagate", PROPAGATION_TIME)
    time.sleep(PROPAGATION_TIME)


def rebuild_revtr_atlas(revtr: RevTrApi, wait: bool = True):
    for vpip in PFX2VPIP.values():
        revtr.atlas_reset(IPv4Address(vpip))
        time.sleep(REVTR_REQ_DELAY)
        revtr.atlas_rebuild(IPv4Address(vpip))
        time.sleep(REVTR_REQ_DELAY)
    if wait:
        logging.info(
            "Waiting %d seconds for RevTr atlas rebuild", REVTR_ATLAS_REBUILD_TIME
        )
        time.sleep(REVTR_ATLAS_REBUILD_TIME)
    else:
        logging.info("Will build RevTr atlas in background")


def measure_catchments(outdir: pathlib.Path):
    tcpdumpcmd = CATCHMENTS_DIR / "launch-tcpdump.sh"
    pingercmd = CATCHMENTS_DIR / "launch-pinger.sh"
    killcmd = CATCHMENTS_DIR / "kill-tcpdump.sh"
    muxes = list(MUX2VPIP)
    for mux, prefix in MUX2PFX.items():
        octet = int(IPv4Network(prefix).network_address.packed[2])
        pfxoutdir = f"{outdir}_{octet}"
        os.makedirs(pfxoutdir, exist_ok=True)
        srcip = str(list(IPv4Network(prefix).hosts())[-1])
        params = [str(tcpdumpcmd), "-i", srcip, "-o", pfxoutdir] + muxes
        proc = subprocess.run(params, check=True, text=True, capture_output=True)
        logging.info("launch-tcpdump.sh succeeded for %s %s", mux, srcip)
        logging.info("%s", proc.stdout)
        icmpid = CATCHMENTS_ICMPID_BASE + muxes.index(mux)
        params = [
            str(pingercmd),
            "-i",
            str(srcip),
            "-t",
            str(TARGETS_FILE),
            "-I",
            str(icmpid),
            "-r",
            str(CATCHMENTS_PINGER_PPS),
        ]
        proc = subprocess.run(params, check=True, text=True, capture_output=True)
        logging.info("launch-pinger.sh succeeded for %s %s", mux, srcip)
        params = [str(killcmd), "-f", f"{pfxoutdir}/pids.txt"]
        logging.info(str(params))
        proc = subprocess.run(params, check=True, text=True, capture_output=True)
        logging.info("kill-tcpdump.sh succeeded for %s %s", mux, srcip)
