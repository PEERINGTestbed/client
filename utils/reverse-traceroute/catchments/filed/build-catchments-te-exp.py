#!/usr/bin/env python3

from __future__ import annotations

import argparse
from collections import defaultdict
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
        "--outdir",
        dest="outdirdir",
        action="store",
        metavar="PATH",
        type=Path,
        required=True,
        help="Output directory where to store results",
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
        logging.error("Unknown ICMP mode: %s", icmp_mode)
        return None

    # cunha@20220129: should never happen because we only capture ICMP echo replies
    # Check if the packet is a response from pinger
    if icmp_mode != "reply":
        logging.error("Unknown ICMP mode: %s", icmp_mode)
        return None

    # Check if destination is a VP
    if vp_v4addr not in src2remotes:
        logging.error("Destination %s not a VP", vp_v4addr)
        return None

    # Check if the src is a known remote
    if remote_v4addr not in src2remotes[vp_v4addr]:
        logging.error("Target %s not in VP's remotes", remote_v4addr)
        return None

    return vp_v4addr, remote_v4addr


def main():
    parser = create_parser()
    opts = parser.parse_args()

    resource.setrlimit(resource.RLIMIT_AS, (1 << 31, 1 << 31))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 35, 1 << 35))
    logging.basicConfig(format="%(message)s", level=logging.INFO)

    mux2tap, tap2dump = load_mux2tap_tap2dump(opts.mux_tap_dump_fn)
    src2emux, emux2src, src2remotes = load_src2emux_emux2src_src2remotes(
        opts.src_emux_remotes_fn
    )

    tap2addr = {}
    addr2tap2vps = defaultdict(lambda: defaultdict(set))
    for tap, dump in tap2dump.items():
        tap2addr[tap] = set()
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
            tap2addr[tap].add((vp_v4addr, remote_v4addr))
            addr2tap2vps[remote_v4addr][tap].add(vp_v4addr)
            responses += 1
        logging.info(
            "processed %s with %d lines, %d valid responses", dump, lines, responses
        )

    for mux, ip in emux2src.items():
        hitlist = set(e[1] for e in tap2addr[mux2tap[mux]] if e[0] == ip)
        fname = opts.basedir / f"hitlist-{mux}.txt"
        logging.info("writing %s", fname)
        fd = open(fname, "w")
        fd.write("\n".join(str(a) for a in hitlist))
        logging.info("%s has %d destinations", mux, len(hitlist))

    addr2tap2vps_json = dict()
    for addr, tap2vps in addr2tap2vps.items():
        addr2tap2vps_json[addr] = dict((t, list(v)) for t, v in tap2vps.items())
    fname = opts.basedir / "catchments.json"
    logging.info("writing %s", fname)
    with open(fname, "w") as fd:
        json.dump(addr2tap2vps_json, fd)

    inferred_anycast = sum(1 for tap2vps in addr2tap2vps.values() if len(tap2vps) > 1)
    logging.info("%d anycast destinations", inferred_anycast)


if __name__ == "__main__":
    sys.exit(main())
