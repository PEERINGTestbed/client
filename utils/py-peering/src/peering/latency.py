#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import logging
import pathlib
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from pathlib import Path
from typing import Literal, TypeAlias, get_args

from pydantic import BaseModel, Field, model_validator

from peering import Announcement, DataPlane, Mux, Update, prefix2id

IPNetwork: TypeAlias = IPv4Network | IPv6Network
IPAddress: TypeAlias = IPv4Address | IPv6Address

ScamperPingMethod = Literal[
    "ICMP-echo",
    "ICMP-time",
    "TCP-syn",
    "TCP-ack",
    "TCP-ack-sport",
    "TCP-synack",
    "TCP-rst",
    "TCP-syn-sport",
    "UDP",
    "UDP-dport",
    "UDP-sport",
]

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
logging.basicConfig(level=logging.INFO, format="%(levelname)s: measure-latency %(message)s")
logger = logging.getLogger(__name__)


class MeasureLatencyCallbackData(BaseModel):
    basedir: pathlib.Path
    """Location of PEERING installation on disk"""
    targets_fn: pathlib.Path
    """File with one target IP address per line"""
    max_pps: int = Field(800, lt=4000, gt=0)
    """Max aggregate probing rate across all prefixes"""
    per_pfx_pps: int = Field(200, gt=0)
    """Per-prefix maximum probing rate"""
    probe_method: ScamperPingMethod = "ICMP-echo"
    """Scamper probing method"""
    max_probes: int = Field(6, gt=0)
    """Maximum number of probes sent to each target"""
    max_replies: int = Field(3, gt=0)
    """Maximum number of replies to expect from each target"""

    @model_validator(mode="after")
    def check_replies_le_probes(self):
        if not (fp := self.basedir / "configs/openvpn/amsterdam01.conf").exists():
            raise ValueError(f"PEERING install basedir mismatch: {fp} does not exist")
        if not self.targets_fn.exists():
            raise ValueError(f"Targets file {self.targets_fn} does not exist")
        if self.per_pfx_pps > self.max_pps:
            raise ValueError("per_pfx_pps must be less than or equal to max_pps")
        if self.max_replies > self.max_probes:
            raise ValueError("max_replies must be less than or equal to max_probes")
        return self


def round_callback(
    pfx2upd: dict[IPNetwork, Update],
    pfx2egress: dict[IPNetwork, Mux],
    outputdir: pathlib.Path,
    data: MeasureLatencyCallbackData,
) -> dict[str, float]:
    """Executes scamper instances for latency measurement"""

    dataplane = DataPlane(data.basedir)
    tasks: list[tuple[IPAddress, IPAddress, Mux, int]] = []
    for pfx, upd in pfx2upd.items():
        if not upd.is_unicast():
            logger.error("Announcement for %s is not unicast", pfx)
            continue
        mux = pfx2egress.get(pfx)
        if mux is None:
            logger.error("No egress mux selected for %s", pfx)
            continue
        pfxid = prefix2id(pfx)
        source = ipaddress.ip_interface(next(pfx.hosts()))
        gateway = dataplane.get_openvpn_gateway(pfx2egress[pfx], pfx.version)
        DataPlane.assign_ip(source)
        if not DataPlane.is_connected(gateway):
            logger.error("Gateway %s is not reachable on any directly-connected subnet", gateway)
            continue
        tasks.append((source.ip, gateway, mux, pfxid))

    tstamps: dict[str, float] = {}
    if not tasks:
        return tstamps

    pkts_per_sec = min(data.per_pfx_pps, data.max_pps // len(tasks))
    parallel_calls = data.max_pps // data.per_pfx_pps

    configs = [
        ScamperConfig(
            source=source,
            gateway=gateway,
            targets_fn=data.targets_fn,
            output_dir=outputdir,
            mux=mux,
            pfxid=pfxid,
            pkts_per_sec=pkts_per_sec,
            probe_method=data.probe_method,
            max_probes=data.max_probes,
            max_replies=data.max_replies,
        )
        for (source, gateway, mux, pfxid) in tasks
    ]

    with ThreadPoolExecutor(max_workers=min(parallel_calls, len(configs))) as executor:
        futures = {executor.submit(launch_scamper, config): config for config in configs}
        for future in as_completed(futures):
            config = futures[future]
            try:
                tstamps.update(future.result())
            except Exception:
                logger.exception(
                    "Scamper run failed for prefix id %d via %s",
                    config.pfxid,
                    config.mux,
                )
                raise

    return tstamps


class ScamperConfig(BaseModel):
    source: IPAddress
    gateway: IPAddress
    targets_fn: pathlib.Path
    output_dir: pathlib.Path
    mux: Mux
    pfxid: int
    probe_method: ScamperPingMethod
    pkts_per_sec: int = Field(..., gt=0)
    max_probes: int = Field(..., gt=0)
    max_replies: int = Field(..., gt=0)

    @model_validator(mode="after")
    def check_replies_le_probes(self):
        if self.max_replies > self.max_probes:
            raise ValueError("max_replies must be less than or equal to max_probes")
        return self


def launch_scamper(config: ScamperConfig) -> dict[str, float]:
    tstamps: dict[str, float] = {}
    config.output_dir.mkdir(parents=True, exist_ok=True)

    gateway_tmpdir = config.output_dir / f"{config.pfxid}-{config.mux}-gw-tmp"
    if gateway_tmpdir.exists():
        for f in gateway_tmpdir.iterdir():
            f.unlink()
    gateway_tmpdir.mkdir(parents=True, exist_ok=True)
    gateway_files: list[pathlib.Path] = []

    targets_output = config.output_dir / f"{config.pfxid}-{config.mux}-targets.warts.xz"
    targets_log = config.output_dir / f"{config.pfxid}-{config.mux}-targets.log"
    targets_cmd = [
        "scamper",
        "-o",
        str(targets_output),
        "-O",
        "warts.xz",
        "-p",
        str(config.pkts_per_sec),
        "-f",
        str(config.targets_fn),
        "-c",
        f"ping -S {config.source} -P {config.probe_method} -o {config.max_replies} -c {config.max_probes} -F {config.pfxid + 1000}",
    ]

    targets_proc = None
    targets_log_fh = None
    try:
        tstamps["scamper-targets-start"] = time.time()
        targets_log_fh = targets_log.open("w")
        targets_proc = subprocess.Popen(targets_cmd, stdout=targets_log_fh, stderr=targets_log_fh)
        logger.info("Started target pings (PID %d)", targets_proc.pid)

        tstamps["scamper-gateway-start"] = time.time()
        seq = 0
        while targets_proc.poll() is None:
            gateway_outfile = gateway_tmpdir / f"{seq:06d}.warts.xz"
            gateway_cmd = [
                "scamper",
                "-o",
                str(gateway_outfile),
                "-O",
                "warts.xz",
                "-p",
                "5",
                "-i",
                str(config.gateway),
                "-c",
                f"ping -P {config.probe_method} -c 60 -F {config.pfxid}",
            ]
            subprocess.run(gateway_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if gateway_outfile.exists():
                gateway_files.append(gateway_outfile)
            seq += 60
            time.sleep(1)
        tstamps["scamper-gateway-end"] = time.time()

        retcode = targets_proc.wait()
        tstamps["scamper-targets-end"] = time.time()
        duration = tstamps["scamper-targets-end"] - tstamps["scamper-targets-start"]
        if retcode == 0:
            logger.info("Target pings completed after %.3fs", duration)
        else:
            logger.error("Target pings failed after %.3fs (exit code %d)", duration, retcode)

        if gateway_files:
            gateway_output = config.output_dir / f"{config.pfxid}-{config.mux}-gw.warts.xz"
            sc_cmd = ["sc_wartscat", "-o", str(gateway_output)] + [str(f) for f in gateway_files]
            subprocess.run(sc_cmd, check=True)
            for f in gateway_files:
                f.unlink(missing_ok=True)
            gateway_tmpdir.rmdir()
            logger.info("Concatenated %d files into %s", len(gateway_files), gateway_output)
        else:
            logger.warning("No gateway warts files were generated")

    except FileNotFoundError:
        logger.error("scamper command not found")
        raise RuntimeError("scamper command not found") from None
    except KeyboardInterrupt:
        logger.info("Measurement interrupted by user")
        if targets_proc is not None:
            targets_proc.terminate()
            targets_proc.wait()
        raise
    finally:
        if targets_log_fh is not None:
            targets_log_fh.close()

    return tstamps


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure latency using scamper")

    parser.add_argument(
        "--prefix",
        dest="prefix",
        type=str,
        required=True,
        metavar="PREFIX",
        help="Source prefix, .1 address will be used as source",
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
        help="Directory for scamper outputs",
    )
    parser.add_argument(
        "--pps",
        dest="pkts_per_sec",
        type=int,
        help="Packets per second",
        default=200,
    )
    parser.add_argument(
        "--probe-method",
        dest="probe_method",
        type=str,
        help="Scamper probe method",
        default="ICMP-echo",
        choices=list(get_args(ScamperPingMethod)),
    )
    parser.add_argument(
        "--max-probes",
        dest="max_probes",
        type=int,
        help="Maximum number of probes per target",
        default=6,
    )
    parser.add_argument(
        "--max-replies",
        dest="max_replies",
        type=int,
        help="Maximum number of replies per target",
        default=3,
    )

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
    config = ScamperConfig(
        source=source.ip,
        gateway=gateway,
        targets_fn=args.targets_fn,
        output_dir=args.outdir,
        mux=args.mux,
        pfxid=prefix2id(pfx),
        pkts_per_sec=args.pkts_per_sec,
        probe_method=args.probe_method,
        max_probes=args.max_probes,
        max_replies=args.max_replies,
    )
    launch_scamper(config)
    dp.unset_egresses([pfx])
    if remove_ip:
        DataPlane.unassign_ip(source)


if __name__ == "__main__":
    main()
