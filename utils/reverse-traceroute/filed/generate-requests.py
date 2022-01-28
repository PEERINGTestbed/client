#!/usr/bin/env python3

import argparse
import ipaddress
import json
import logging
import pathlib
import resource
import sys
import time

import requests


REVTR_URL = "https://revtr.ccs.neu.edu/api/v1/revtr"
RESULT_URI_STR = "result_uri"


def create_parser():
    desc = """Issue Reverse Traceroute Requests"""
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument(
        "--source",
        dest="source",
        action="store",
        metavar="IP",
        type=ipaddress.IPv4Address,
        required=True,
        help="IP address of the Reverse Traceroute VP",
    )
    parser.add_argument(
        "--destinations",
        dest="destfn",
        action="store",
        metavar="FILE",
        type=pathlib.Path,
        required=True,
        help="File containing IP addresses to measure from",
    )
    parser.add_argument(
        "--api-key",
        dest="key",
        action="store",
        metavar="KEY",
        type=str,
        required=True,
        help="API key to use in the requests",
    )
    parser.add_argument(
        "--label",
        dest="label",
        action="store",
        metavar="TXT",
        type=str,
        required=True,
        help="Label to use in the Reverse Traceroute database",
    )
    parser.add_argument(
        "--results-log",
        dest="resultsfn",
        action="store",
        metavar="FILE",
        type=pathlib.Path,
        required=True,
        help="File where to store URLs to retrieve results",
    )
    parser.add_argument(
        "--round-duration",
        dest="round_duration",
        action="store",
        metavar="SECS",
        type=int,
        required=False,
        help="Round duration in seconds [%(default)s]",
        default=60,
    )
    parser.add_argument(
        "--round-size",
        dest="round_size",
        action="store",
        metavar="COUNT",
        type=int,
        required=False,
        help="Number of destinations in each round [%(default)s]",
        default=50,
    )
    return parser


def main():
    parser = create_parser()
    opts = parser.parse_args()

    resource.setrlimit(resource.RLIMIT_AS, (1 << 31, 1 << 31))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 35, 1 << 35))
    logging.basicConfig(format="%(message)s", level=logging.INFO)

    results_fd = open(opts.resultsfn, "w")
    destinations = list(
        ipaddress.IPv4Address(addr.strip()) for addr in open(opts.destfn)
    )

    round_time = time.time()
    round_num = 0
    while round_num * opts.round_size < len(destinations):
        first = round_num * opts.round_size
        last = min(len(destinations), first + opts.round_size)
        round_destinations = destinations[first:last]
        logging.info(
            "Beginning round %d @ %s [%d:%d/%d]",
            round_num,
            time.time(),
            first, last, len(destinations),
        )
        headers = {
            "Revtr-Key": opts.key,
        }
        data = {
            "revtrs": list(
                {
                    "src": str(opts.source),
                    "dst": str(dst),
                    "label": opts.label,
                    "isRunForwardTraceroute": True,
                }
                for dst in round_destinations
            )
        }
        logging.debug("headers: %s", json.dumps(headers))
        logging.debug("data: %s", json.dumps(data))
        r = requests.post(REVTR_URL, headers=headers, data=json.dumps(data))
        if r.status_code != 200:
            logging.error(
                "round %d: error making request, status_code %d.",
                round_num,
                r.status_code,
            )
            logging.info(
                "headers: %s\ndata: %s",
                json.dumps(headers),
                json.dumps(data),
            )
        else:
            results_fd.write("round %d %s\n" % (round_num, r.json()[RESULT_URI_STR]))
            results_fd.flush()

        sleep_time = round_time + opts.round_duration - time.time()
        if sleep_time > 0:
            time.sleep(sleep_time)
        round_time += opts.round_duration
        round_num += 1

    results_fd.close()


if __name__ == "__main__":
    sys.exit(main())
