#!/usr/bin/env python

import argparse
import gzip
import json
import logging
import sys
import re
import resource

import parsers.util as util
import parsers.protocols as proto
import parsers.route as route
from cblr import CachingBufferedLineReader


def show_protocols(reader, outfd):  # {{{
    header = reader.readline()
    assert header.split() == proto.HEADER_LINE_FIELDS
    results = list()
    line = reader.readline()
    while line:
        m = re.match(proto.SUMMARY_RE, line)
        if not m:
            logging.debug('parse_proto: no match [%s]', line)
            line = reader.readline()
            continue
        line = reader.readline()
        if m.group('proto') not in proto.SUPPORTED:
            logging.debug('parse_proto: %s not supported', m.group('proto'))
            continue
        result = m.groupdict()
        v = util.parse_desc_lines(reader, proto.DETAILS_RE,
                                  proto.DETAILS_PARSERS)
        result['details'] = v
        results.append(result)
    json.dump(results, outfd, indent=2)
    return results
# }}}


def show_route(reader, outfd, return_json=False):  # {{{
    routes = list()
    network = None
    line = reader.readline()
    while line:
        m = re.match(route.SUMMARY_RE, line)
        assert m, '%s' % line
        if m.group(route.SUMMARY_NETWORK_KEY) is not None:
            network = m.group(route.SUMMARY_NETWORK_KEY)
        rt = m.groupdict()
        rt[route.SUMMARY_NETWORK_KEY] = network
        rt = dict((k, v.strip()) for k, v in rt.items() if v is not None)
        v = util.parse_desc_lines(reader, route.DETAILS_RE,
                                  route.DETAILS_PARSERS, route.SUMMARY_RE)
        rt['attributes'] = v
        line = reader.readline()
        json.dump(rt, outfd)
        if line:
            outfd.write('\n')
        if return_json:
            routes.append(rt)
    return routes
# }}}


def create_parser():  # {{{
    desc = '''Parse BIRD output'''

    cmdparser = argparse.ArgumentParser(description=desc)

    cmdparser.add_argument('--in',
                           dest='infn',
                           metavar='FILE',
                           required=True,
                           type=str,
                           help='Input file (with BIRD output), - for STDIN')

    cmdparser.add_argument('--out',
                           dest='outfn',
                           metavar='FILE',
                           required=True,
                           type=str,
                           help='Output file (JSON)')

    cmd = cmdparser.add_mutually_exclusive_group(required=True)
    cmd.add_argument('--protocols',
                     dest='parser',
                     action='store_const',
                     const=show_protocols,
                     help='Parse the output of `show protocols`')
    cmd.add_argument('--route',
                     dest='parser',
                     action='store_const',
                     const=show_route,
                     help='Parse the output of `show route`')

    return cmdparser
# }}}


def main():  # {{{
    resource.setrlimit(resource.RLIMIT_AS, (1 << 33, 1 << 33))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1 << 35, 1 << 35))
    logging.basicConfig(filename='parse.log', format='%(message)s',
                        level=logging.NOTSET)

    cmdparser = create_parser()
    opts = cmdparser.parse_args()

    if opts.infn == '-':
        opts.fd = sys.stdin
    else:
        opts.fd = open(opts.infn, 'r')
    reader = CachingBufferedLineReader(opts.fd)

    if opts.outfn.endswith('.gz'):
        outfd = gzip.open(opts.outfn, 'w+')
    else:
        outfd = open(opts.outfn, 'w+')

    opts.parser(reader, outfd)

    opts.fd.close()
    outfd.close()
# }}}


if __name__ == '__main__':
    sys.exit(main())
