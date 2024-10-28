#!/usr/bin/env python3

import argparse
import gzip
import json
import logging
import platform
import sys
import re
import resource

import parsers.util as util
import parsers.protocols as proto
import parsers.route as route


class CachingBufferedLineReader:
    def __init__(self, fd):
        self.fd = fd
        self.line = None
        self.read = True

    def readline(self):
        if self.read:
            self.line = self.fd.readline()
        else:
            self.read = True
            assert self.line is not None
        return self.line

    def rewind_line(self):
        self.read = False


def show_protocols(reader, outfd):
    header = reader.readline().lower()
    if header.startswith("bird") and header.endswith("ready.\n"):
        header = reader.readline().lower()
    assert header.split() == proto.HEADER_LINE_FIELDS
    results = list()
    line = reader.readline()
    while line:
        m = re.match(proto.SUMMARY_RE, line)
        if not m:
            logging.debug("parse_proto: no match [%s]", line)
            line = reader.readline()
            continue
        if m.group("proto") not in proto.SUPPORTED:
            logging.debug("parse_proto: %s not supported", m.group("proto"))
            line = reader.readline()
            continue
        logging.debug("parsing [%s]", line)
        result = m.groupdict()
        result = dict((k, v.strip()) for k, v in result.items())
        v = util.parse_by_indentation(reader)
        result.update(v)
        results.append(result)
        line = reader.readline()
    json.dump(results, outfd, indent=2)
    return results


def show_route(reader, outfd):
    routes = []
    network = None
    line = reader.readline()
    while line:
        line = line.strip()
        m = re.match(route.SUMMARY_RE, line)
        assert m, f"Could not parse SUMMARY_RE on line: [{line}]"
        if m.group(route.SUMMARY_NETWORK_KEY) is not None:
            network = m.group(route.SUMMARY_NETWORK_KEY)
        mdata = m.groupdict()
        rt = dict((k, v.strip()) for k, v in mdata.items() if v is not None)
        rt[route.SUMMARY_NETWORK_KEY] = network
        line = reader.readline()
        m = re.match(route.VIA_RE, line)
        assert m, f"Could not parse VIA_RE on line: [{line}]"
        mdata = m.groupdict()
        rt.update({(k, v.strip()) for k, v in mdata.items() if v is not None})
        v = util.parse_desc_lines(
            reader, route.DETAILS_RE, route.DETAILS_PARSERS, route.SUMMARY_RE
        )
        rt["attributes"] = v
        line = reader.readline()
        routes.append(rt)
    json.dump(routes, outfd, indent=2)
    return routes


def create_parser():
    desc = """Parse BIRD output into JSON data"""
    cmdparser = argparse.ArgumentParser(description=desc)
    cmdparser.add_argument(
        "--in",
        dest="infn",
        metavar="FILE",
        required=True,
        type=str,
        help="Input file (with BIRD output), - for STDIN",
    )
    cmdparser.add_argument(
        "--out",
        dest="outfn",
        metavar="FILE",
        required=True,
        type=str,
        help="Output file (JSON)",
    )
    cmd = cmdparser.add_mutually_exclusive_group(required=True)
    cmd.add_argument(
        "--protocols",
        dest="parser",
        action="store_const",
        const=show_protocols,
        help="Parse the output of `show protocols`",
    )
    cmd.add_argument(
        "--route",
        dest="parser",
        action="store_const",
        const=show_route,
        help="Parse the output of `show route`",
    )
    return cmdparser


def main():
    if platform.system() == "Linux":
        resource.setrlimit(resource.RLIMIT_AS, (1 << 33, 1 << 33))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 35, 1 << 35))
    logging.basicConfig(format="%(message)s", level=logging.NOTSET)

    cmdparser = create_parser()
    opts = cmdparser.parse_args()

    if opts.infn == "-":
        opts.fd = sys.stdin
    elif opts.infn.endswith(".gz"):
        opts.fd = gzip.open(opts.infn, "rt", encoding="utf8")
    else:
        opts.fd = open(opts.infn, "r", encoding="utf8")
    reader = CachingBufferedLineReader(opts.fd)

    if opts.outfn.endswith(".gz"):
        outfd = gzip.open(opts.outfn, "wt", encoding="utf8")
    else:
        outfd = open(opts.outfn, "wt", encoding="utf8")

    opts.parser(reader, outfd)

    opts.fd.close()
    outfd.close()


if __name__ == "__main__":
    sys.exit(main())
