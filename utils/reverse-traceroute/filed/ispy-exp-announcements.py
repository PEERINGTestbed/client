#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import json
import pathlib
from typing import Any

import config


def create_parser():
    mparser = argparse.ArgumentParser(description="Generate RevTr announcements")
    sparser = mparser.add_subparsers(required=True, help="The type of announcements to generate")

    withdraws = sparser.add_parser("withdraws", help="Withdraw all prefixes from all muxes")
    withdraws.add_argument("file",
        action="store",
        type=pathlib.Path,
        help="The file where to store the announcement JSON configuration",
    )
    withdraws.set_defaults(func=build_withdraws)

    legit = sparser.add_parser("legit", help="Withdraw all prefixes from all muxes")
    legit.add_argument("file",
        action="store",
        type=pathlib.Path,
        help="The file where to store the announcement JSON configuration",
    )
    legit.set_defaults(func=build_legit)

    hijacks = sparser.add_parser("hijacks", help="Withdraw all prefixes from all muxes")
    hijacks.add_argument("file",
        action="store",
        type=pathlib.Path,
        help="The file where to store the announcement JSON configuration",
    )
    hijacks.add_argument("round",
        action="store",
        type=int,
        help="The hijacker is defined by the round number (1-based)",
    )
    hijacks.set_defaults(func=build_hijacks)
    return mparser


def make_mux2hijackers() -> dict[str, list[str]]:
    """Return dictionary mapping each mux to a list of other muxes"""
    muxes = list(config.mux2octet.keys())
    muxes.sort()
    mux2hijackers = {m: list(muxes) for m in muxes}
    for mux, hijackers in mux2hijackers.items():
        hijackers.remove(mux)
        hijackers.sort()
    return mux2hijackers


def get_mux_prefix_v4net(mux: str) -> ipaddress.IPv4Network:
    return ipaddress.IPv4Network(f"184.164.{config.mux2octet[mux]}.0/24")


def build_legit(opts: argparse.Namespace) -> None:
    announcement = {}
    for mux in config.mux2octet:
        v4net = get_mux_prefix_v4net(mux)
        announce: dict[str, Any] = { "muxes": [mux] }
        if mux in config.mux2peers:
            announce["peers"] = config.mux2peers[mux]
        announcement[str(v4net)] = { "announce": [announce] }
    with open(opts.file, "w", encoding="utf8") as fd:
        json.dump(announcement, fd, indent=2)


def build_hijacks(opts: argparse.Namespace) -> None:
    mux2hijackers = make_mux2hijackers()
    announcement = {}
    for mux in config.mux2octet:
        v4net = get_mux_prefix_v4net(mux)
        hijacker = mux2hijackers[mux][opts.round - 1]
        announce: dict[str, Any] = { "muxes": [hijacker] }
        if hijacker in config.mux2peers:
            announce["peers"] = config.mux2peers[hijacker]
        announcement[str(v4net)] = { "announce": [announce] }
    with open(opts.file, "w", encoding="utf8") as fd:
        json.dump(announcement, fd, indent=2)


def build_withdraws(opts: argparse.Namespace) -> None:
    announcement = {}
    muxes = list(config.mux2id.keys())
    for mux in config.mux2octet:
        v4net = get_mux_prefix_v4net(mux)
        announcement[str(v4net)] = { "withdraw": muxes }
    with open(opts.file, "w", encoding="utf8") as fd:
        json.dump(announcement, fd, indent=2)


def main():
    mparser = create_parser()
    opts = mparser.parse_args()
    opts.func(opts)


if __name__ == "__main__":
    main()
