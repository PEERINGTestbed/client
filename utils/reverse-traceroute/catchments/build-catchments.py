#!/usr/bin/env python3

from __future__ import annotations

import argparse
from ipaddress import IPv4Address
import json
import logging
from pathlib import Path
import resource
import subprocess
import sys
from typing import Optional


def create_parser() -> argparse.ArgumentParser:
    desc = """Build catchment from tcpdump files"""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        "--mux-tap-dump",
        dest="mux_tap_dump_fn",
        action="store",
        metavar="FILE",
        type=Path,
        required=True,
        help="File with mapping between mux, tap device, and tcpdump file",
    )
    parser.add_argument(
        "--src-emux-remotes",
        dest="src_emux_remotes_fn",
        action="store",
        metavar="FILE",
        type=Path,
        required=True,
        help="File with mapping between source v4addr, egress mux, and file with targets",
    )
    parser.add_argument(
        "--out",
        dest="outfn",
        action="store",
        metavar="FILE",
        type=Path,
        required=True,
        help="Output file where to store the JSON mapping of src2remote2tap",
    )
    return parser


def load_mux2tap_tap2dump(
    mux_tap_dump_fn: Path,
) -> tuple[dict[str, str], dict[str, Path]]:
    mux2tap = {}
    tap2dump = {}
    with open(mux_tap_dump_fn) as fd:
        for line in fd:
            line = line.strip()
            mux, tap, dump = line.split()
            mux2tap[mux] = tap
            tap2dump[tap] = Path(dump)
            assert tap2dump[tap].exists()
    return mux2tap, tap2dump


def load_src2emux_emux2src_src2remotes(
    src_emux_remotes_fn: Path,
) -> tuple[
    dict[IPv4Address, str], dict[str, IPv4Address], dict[IPv4Address, set[IPv4Address]]
]:
    src2emux = {}
    src2remotes = {}
    with open(src_emux_remotes_fn) as fd:
        for line in fd:
            line = line.strip()
            _src, emux, remotes_fn = line.split()
            src = IPv4Address(_src)
            src2emux[src] = emux
            src2remotes[src] = set(IPv4Address(l.strip()) for l in open(remotes_fn))
    emux2src = {m: s for s, m in src2emux.items()}
    return src2emux, emux2src, src2remotes


def check_response(
    line: str,
    src2remotes: dict[IPv4Address, set[IPv4Address]],
) -> Optional[tuple[IPv4Address, IPv4Address]]:
    line = line.strip()
    tokens = line.split()
    if len(tokens) < 10:
        return None

    try:
        remote_v4addr = IPv4Address(tokens[2])
        vp_v4addr = IPv4Address(tokens[4].strip(":"))
        icmp_mode = tokens[7].strip(",")
        _icmp_id = int(tokens[9].strip(","))
    except ValueError:
        # logging.error("error parsing line %s", line)
        return None

    # cunha@20220129: should never happen because we only capture ICMP echo replies
    # Check if the packet is a response from pinger
    if icmp_mode != "reply":
        logging.info("Unknown ICMP mode: %s", icmp_mode)
        return None

    # cunha@20220129: should never happen because we only capture ICMP echo replies
    # Check if the packet is a response from pinger
    if icmp_mode != "reply":
        logging.info("Unknown ICMP mode: %s", icmp_mode)
        return None

    # Check if destination is a VP
    if vp_v4addr not in src2remotes:
        logging.debug("Destination %s not a VP", vp_v4addr)
        return None

    # Check if the src is a known remote
    if remote_v4addr not in src2remotes[vp_v4addr]:
        logging.debug("Target %s not in VP's remotes", remote_v4addr)
        return None

    return vp_v4addr, remote_v4addr


def main():
    parser = create_parser()
    opts = parser.parse_args()

    resource.setrlimit(resource.RLIMIT_AS, (1 << 31, 1 << 31))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 35, 1 << 35))
    logging.basicConfig(format="%(message)s", level=logging.INFO)

    _mux2tap, tap2dump = load_mux2tap_tap2dump(opts.mux_tap_dump_fn)
    _src2emux, _emux2src, src2remotes = load_src2emux_emux2src_src2remotes(
        opts.src_emux_remotes_fn
    )

    # initialize a None entry for each remote in src2remotes, indicating
    # lack of response:
    src2remote2tap = dict(
        (src, {rmt: None for rmt in remotes}) for src, remotes in src2remotes.items()
    )
    for tap, dump in tap2dump.items():
        cmd = f"tcpdump -n -r {dump}"
        proc = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, text=True)
        lines = 0
        responses = 0
        for line in proc.stdout:
            lines += 1
            r = check_response(line, src2remotes)
            if r is None:
                continue
            vp_v4addr, remote_v4addr = r
            src2remote2tap[vp_v4addr][remote_v4addr] = tap
            responses += 1
        logging.info(
            "processed %s with %d lines, %d valid responses", dump, lines, responses
        )

    src2remote2tap_json = {
        str(src): {str(remote): tap for remote, tap in remote2tap.items()}
        for src, remote2tap in src2remote2tap.items()
    }
    logging.info("writing %s", opts.outfn)
    with open(opts.outfn, "w") as fd:
        json.dump(src2remote2tap_json, fd)


if __name__ == "__main__":
    sys.exit(main())
