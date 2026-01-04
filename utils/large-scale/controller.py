#!/usr/bin/env python3

import itertools
import json
import logging
import pathlib
import subprocess
import time
from ipaddress import IPv4Network

import defs

import peering
from peering import AnnouncementController, Update

peering.AUTO_BASE_DIR = "/home/cunha/git/peering/client/"


def withdraw_round() -> None:
    controller = AnnouncementController(
        defs.PREFIXES,
        defs.BIRD_CFG_DIR,
        defs.BIRD4_SOCK_PATH,
        schema_file=defs.ANNOUNCEMENT_SCHEMA,
        mux2tap_file=defs.MUX2TAP_FILE,
    )
    withdraw_prefixes(controller)
    time.sleep(defs.ANNOUNCEMENT_DURATION)


def run_loop(updates: list[Update], first_round: int, basedir: pathlib.Path) -> None:
    controller = AnnouncementController(
        defs.PREFIXES,
        defs.BIRD_CFG_DIR,
        defs.BIRD4_SOCK_PATH,
        schema_file=defs.ANNOUNCEMENT_SCHEMA,
        mux2tap_file=defs.MUX2TAP_FILE,
    )
    unset_egresses(controller)

    tstamps = {}
    done = False
    roundidx = first_round
    updates_iter = itertools.islice(updates, first_round * len(defs.PREFIXES), None)
    while not done:
        logging.info("#####################################################")
        logging.info("Starting round %d", roundidx)
        tstamps["round-start"] = time.time()
        withdraw_prefixes(controller)
        unset_egresses(controller)

        pfx2upd: dict[str, Update] = {}
        for prefix in defs.PREFIXES:
            try:
                update = next(updates_iter)
                pfx2upd[prefix] = update
            except StopIteration:
                done = True
                break

        if not pfx2upd:
            continue

        tstamps["deploy-pfx2ann"] = time.time()
        deploy_pfx2upd(controller, pfx2upd)
        src2mux = set_egresses(controller, pfx2upd)

        round_outdir = pathlib.Path(f"{basedir}/round{roundidx}")
        round_outdir.mkdir(parents=True, exist_ok=True)
        with open(round_outdir / "announcements.json", "w", encoding="utf8") as fd:
            json.dump(pfx2upd, fd, indent=2, default=lambda x: x.to_dict())
        with open(round_outdir / "egresses.json", "w", encoding="utf8") as fd:
            json.dump(src2mux, fd, indent=2)

        tstamps["measure-catchments-start"] = time.time()
        measure_catchments(
            round_outdir, tstamps, rounds=defs.MEASURE_CATCHMENTS_NUM_ROUNDS
        )
        tstamps["measure-catchments-end"] = time.time()
        logging.info(
            "Took %f seconds to measure catchments",
            tstamps["measure-catchments-end"] - tstamps["measure-catchments-start"],
        )

        spare_time = defs.ANNOUNCEMENT_DURATION - (
            time.time() - tstamps["deploy-pfx2ann"]
        )
        logging.info("Catchment measurement finished with %d spare seconds", spare_time)
        round_wait = max(300, spare_time)
        logging.info("Sleeping %f seconds to complete round duration", round_wait)
        time.sleep(round_wait)
        tstamps["round-end"] = time.time()

        with open(round_outdir / "timestamps.json", "w", encoding="utf8") as fd:
            json.dump(tstamps, fd, indent=2)

        roundidx += 1


def withdraw_prefixes(controller: AnnouncementController) -> None:
    for prefix in defs.PREFIXES:
        controller.withdraw(prefix)
    controller.reload_config()
    logging.info(
        "Waiting %d seconds for withdrawals to converge", defs.PROPAGATION_TIME
    )
    time.sleep(defs.PROPAGATION_TIME)


def deploy_pfx2upd(
    controller: AnnouncementController, pfx2upd: dict[str, Update]
) -> None:
    updset = peering.UpdateSet(pfx2upd)
    controller.deploy(updset)
    logging.info("PEERING deploy %s %s", time.time(), updset.to_json())
    logging.info(
        "Waiting %d seconds for announcements to propagate", defs.PROPAGATION_TIME
    )
    time.sleep(defs.PROPAGATION_TIME)


def set_egresses(
    controller: AnnouncementController, pfx2upd: dict[str, Update]
) -> dict[str, peering.MuxName]:
    src2mux = {}
    for prefix, upd in pfx2upd.items():
        octet = int(IPv4Network(prefix).network_address.packed[2])
        srcip = str(list(IPv4Network(prefix).hosts())[-1])
        announcing: list[peering.MuxName] = []
        announcing_undecorated: list[peering.MuxName] = []
        for ann in upd.announce:
            announcing.extend(ann.muxes)
            if not ann.peer_ids and not ann.communities:
                announcing_undecorated.extend(ann.muxes)
        muxes = [
            mux
            for mux in defs.EGRESS_PREFS
            if mux in announcing_undecorated and mux not in upd.withdraw
        ]
        if not muxes:
            muxes = announcing
        assert muxes
        logging.info("Setting egress for %s through %s", prefix, muxes[0])
        src2mux[srcip] = muxes[0]
        controller.set_egress(defs.PREFIX_ID_BASE + octet, srcip, muxes[0], None)
    return src2mux


def unset_egresses(controller: AnnouncementController) -> None:
    for prefix in defs.PREFIXES:
        octet = int(IPv4Network(prefix).network_address.packed[2])
        controller.unset_egress(defs.PREFIX_ID_BASE + octet)


def _run_check_log(params: list[str], check: bool, log_errors: bool = True) -> None:
    try:
        logging.info("running %s", " ".join(params))
        subprocess.run(params, capture_output=True, check=check)  # noqa: S603
    except subprocess.CalledProcessError as cpe:
        if log_errors:
            logging.error("stdout: %s", cpe.stdout)
            logging.error("stderr: %s", cpe.stderr)
        raise


def measure_catchments(
    outdir: pathlib.Path, tstamps: dict[str, float], rounds: int = 1
) -> None:
    muxes = [str(m) for m in peering.MuxName]
    tcpdumpcmd = defs.CATCHMENTS_DIR / "launch-tcpdump.sh"
    pingercmd = defs.CATCHMENTS_DIR / "launch-pinger.sh"
    killcmd = defs.CATCHMENTS_DIR / "kill-tcpdump.sh"
    for i in range(rounds):
        for prefix in defs.PREFIXES:
            octet = int(IPv4Network(prefix).network_address.packed[2])
            pfxoutdir = outdir / f"catchment_{octet}"
            pfxoutdir.mkdir(parents=True, exist_ok=True)
            srcip = str(list(IPv4Network(prefix).hosts())[-1])

            try:
                params = [
                    str(tcpdumpcmd),
                    "-i",
                    str(srcip),
                    "-o",
                    str(pfxoutdir),
                    *muxes,
                ]
                logging.debug(str(params))
                tstamps[f"round-{i}/launch-tcpdump/{octet}"] = time.time()
                _run_check_log(params, True)
                logging.info("launch-tcpdump.sh succeeded for %s", srcip)

                icmpid = defs.PREFIX_ID_BASE + octet
                params = [
                    str(pingercmd),
                    "-i",
                    str(srcip),
                    "-t",
                    str(defs.TARGETS_FILE),
                    "-I",
                    str(icmpid),
                    "-r",
                    str(defs.CATCHMENTS_PINGER_PPS),
                ]
                logging.debug(str(params))
                tstamps[f"round-{i}/launch-pinger/{octet}"] = time.time()
                _run_check_log(params, True)
                logging.info("launch-pinger.sh succeeded for %s", srcip)
            except subprocess.CalledProcessError:
                logging.exception("Error measuring catchments")
            finally:
                params = [str(killcmd), "-f", f"{pfxoutdir}/pids.txt"]
                logging.debug(str(params))
                tstamps[f"round-{i}/kill-tcpdump/{octet}"] = time.time()
                _run_check_log(params, True)
                logging.info("kill-tcpdump.sh succeeded for %s", srcip)
