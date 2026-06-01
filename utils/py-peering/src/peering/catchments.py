#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import logging
import pathlib
import subprocess
import time
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel, Field, model_validator

from peering import Announcement, DataPlane, Mux, Update, prefix2string

IPNetwork: TypeAlias = IPv4Network | IPv6Network
IPAddress: TypeAlias = IPv4Address | IPv6Address

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(name)s %(message)s")
logger = logging.getLogger(__name__)


class MeasureCatchmentsCallbackData(BaseModel):
    basedir: pathlib.Path
    """Location of PEERING installation on disk"""
    targets_fn: pathlib.Path
    """File with one target IP address per line"""
    pkts_per_sec: int = Field(800, lt=4000, gt=0)
    """Probing rate (one prefix at a time)"""

    @model_validator(mode="after")
    def check_replies_le_probes(self):
        if not (fp := self.basedir / "configs/openvpn/amsterdam01.conf").exists():
            raise ValueError(f"PEERING install basedir mismatch: {fp} does not exist")
        if not (fp := self.basedir / "utils/measure-catchments").exists():
            raise ValueError(f"utils/measure-catchments not found: {fp} does not exist")
        if not self.targets_fn.exists():
            raise ValueError(f"Targets file {self.targets_fn} does not exist")
        return self


def round_callback(
    pfx2upd: dict[IPNetwork, Update],
    pfx2egress: dict[IPNetwork, Mux],
    outputdir: pathlib.Path,
    data: MeasureCatchmentsCallbackData,
) -> dict[str, float]:
    """Executes catchment measurements for each announced prefix"""
    tstamps: dict[str, float] = {}
    dataplane = DataPlane(data.basedir)
    for pfx, upd in pfx2upd.items():
        mux = pfx2egress.get(pfx)
        if mux is None:
            logger.error("No egress mux selected for %s", pfx)
            continue
        source = ipaddress.ip_interface(next(pfx.hosts()))
        gateway = dataplane.get_openvpn_gateway(mux, pfx.version)
        DataPlane.assign_ip(source)
        if not DataPlane.is_connected(gateway):
            logger.error("Gateway %s is not reachable on any directly-connected subnet", gateway)
            continue
        icmp_id = dataplane.get_egress_table(pfx)
        config = PingerConfig(
            tool_dir=data.basedir / "utils" / "measure-catchments",
            source=source.ip,
            targets_fn=data.targets_fn,
            output_dir=outputdir / f"catchment-{prefix2string(pfx)}",
            icmp_id=icmp_id,
            pkts_per_sec=data.pkts_per_sec,
        )
        logger.info("Launching catchment measurements for %s", pfx)
        new_ts = launch_prefix_measurement(config)
        new_ts = {f"catchments-{prefix2string(pfx)}/{k}": v for k, v in new_ts.items()}
        tstamps.update(new_ts)
    return tstamps


class PingerConfig(BaseModel):
    tool_dir: pathlib.Path
    source: IPAddress
    targets_fn: pathlib.Path
    output_dir: pathlib.Path
    icmp_id: int
    pkts_per_sec: int = Field(..., gt=0)


def _run_check_log(params: list[str], check: bool, log_errors: bool = True) -> None:
    try:
        logger.info("running %s", " ".join(params))
        subprocess.run(params, capture_output=True, check=check)  # noqa: S603
    except subprocess.CalledProcessError as cpe:
        if log_errors:
            logger.error("stdout: %s", cpe.stdout)
            logger.error("stderr: %s", cpe.stderr)
        raise


def launch_prefix_measurement(config: PingerConfig) -> dict[str, float]:
    MUXES = [str(m) for m in Mux]
    TCPDUMPCMD = config.tool_dir / "launch-tcpdump.sh"
    PINGERCMD = config.tool_dir / "launch-pinger.sh"
    KILLCMD = config.tool_dir / "kill-tcpdump.sh"

    tstamps: dict[str, float] = {}
    config.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        params = [
            str(TCPDUMPCMD),
            "-i",
            str(config.source),
            "-o",
            str(config.output_dir),
            *MUXES,
        ]
        logger.debug(str(params))
        tstamps[f"launch-tcpdump"] = time.time()
        _run_check_log(params, True)
        logger.debug("launch-tcpdump.sh succeeded for %s", config.source)

        icmpid = config.icmp_id
        params = [
            str(PINGERCMD),
            "-i",
            str(config.source),
            "-t",
            str(config.targets_fn),
            "-I",
            str(icmpid),
            "-r",
            str(config.pkts_per_sec),
        ]
        logger.debug(str(params))
        tstamps[f"launch-pinger"] = time.time()
        _run_check_log(params, True)
        logger.info("launch-pinger.sh succeeded for %s", config.source)
    except subprocess.CalledProcessError:
        logger.exception("Error measuring catchments")
    finally:
        params = [str(KILLCMD), "-f", str(config.output_dir / "pids.txt")]
        logger.debug(str(params))
        tstamps[f"kill-tcpdump"] = time.time()
        _run_check_log(params, True)
        logger.debug("kill-tcpdump.sh succeeded for %s", config.source)

    return tstamps


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure catchments using ICMP pings")

    parser.add_argument(
        "--prefix",
        dest="prefix",
        type=str,
        required=True,
        metavar="PREFIX",
        help="Source prefix, .1 address will be used as source",
    )
    parser.add_argument(
        "--hitlist",
        dest="targets_fn",
        type=Path,
        required=True,
        metavar="FILE",
        help="File containing one target to probe per line",
    )
    parser.add_argument(
        "--outdir",
        dest="outdir",
        type=Path,
        required=True,
        metavar="DIR",
        help="Directory where to store tcpdump files",
    )
    parser.add_argument(
        "--mux",
        dest="mux",
        type=Mux,
        help="PEERING mux name to use as egress",
        required=True,
        metavar="MUX",
    )
    parser.add_argument(
        "--pps",
        dest="pkts_per_sec",
        type=int,
        help="Packets per second",
        default=200,
    )

    REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
    args = parser.parse_args()
    pfx = ipaddress.ip_network(args.prefix)
    gateway = DataPlane(REPO_ROOT).get_openvpn_gateway(args.mux, pfx.version)
    source: IPv4Interface | IPv6Interface = ipaddress.ip_interface((next(pfx.hosts()), 32))
    if not DataPlane.is_connected(gateway):
        raise RuntimeError(f"Gateway {gateway} is not reachable on any directly-connected subnet")

    remove_ip = False
    if not DataPlane.is_assigned(source):
        DataPlane.assign_ip(source)
        remove_ip = True

    dp = DataPlane(REPO_ROOT)
    dp.update_egresses({pfx: Update(announce=[Announcement(muxes={args.mux})])})
    config = PingerConfig(
        tool_dir=REPO_ROOT / "utils" / "measure-catchments",
        source=source.ip,
        targets_fn=args.targets_fn,
        output_dir=args.outdir,
        icmp_id=dp.get_egress_table(pfx),
        pkts_per_sec=args.pkts_per_sec,
    )
    launch_prefix_measurement(config)
    dp.unset_egresses([pfx])
    if remove_ip:
        DataPlane.unassign_ip(source)


if __name__ == "__main__":
    main()
