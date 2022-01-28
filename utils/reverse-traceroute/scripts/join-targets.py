#!/usr/bin/env python3

import argparse
from collections import defaultdict
import json
import logging
import pathlib
import resource
import sys

import bogons
import config


def create_parser():
    desc = """Prepare list of targets for each mux"""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        "--workdir",
        dest="workdir",
        action="store",
        metavar="DIR",
        type=pathlib.Path,
        required=True,
        help="Directory containing hops_per_source JSON files",
    )
    return parser


def main():
    parser = create_parser()
    opts = parser.parse_args()

    resource.setrlimit(resource.RLIMIT_AS, (1 << 31, 1 << 31))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 35, 1 << 35))
    logging.basicConfig(format="%(message)s", level=logging.DEBUG)

    with open(opts.workdir / "fwdtr_hops_per_source.json") as fd:
        fwdtr_src2targets = json.load(fd)
    with open(opts.workdir / "revtr_hops_per_source.json") as fd:
        revtr_src2targets = json.load(fd)

    joined_src2targets = defaultdict(set, {
        src: set(bogons.filtr(targets)) for src, targets in fwdtr_src2targets.items()
    })
    for src, targets in revtr_src2targets.items():
        joined_src2targets[src].update(bogons.filtr(targets))

    for mux, octet in config.mux2octet.items():
        muxid = config.mux2id[mux]
        ip = f"184.164.{octet}.{128 + muxid}"
        targets = joined_src2targets.get(ip, [])
        with open(opts.workdir / f"{mux}_targets.txt", "w") as fd:
            fd.write("\n".join(targets))


if __name__ == "__main__":
    sys.exit(main())
