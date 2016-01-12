#!/usr/bin/python3

import sys
import os
import os.path
import argparse


class OpenVPNTool(object):
    @staticmethod
    def create_parser(parser):# {{{
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument('--status',
                dest='action',
                action='store_const',
                const='status',
                default=None,
                help='List and show status of OpenVPN tunnels')
        g.add_argument('--up',
                dest='up',
                metavar='tunnel',
                type=str,
                help='Bring OpenVPN tunnel up')
        g.add_argument('--down',
                dest='down',
                metavar='tunnel',
                type=str,
                help='Bring OpenVPN tunnel down')
    # }}}

class BGPController(object):
    @staticmethod
    def create_parser(parser):# {{{
        pass
    # }}}

def create_parser(): # {{{
    desc = 'PEERING controller'
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers()

    openvpn_parser = subparsers.add_parser('openvpn', help='Control OpenVPN tunnels')
    OpenVPNTool.create_parser(openvpn_parser)

    bgpd_parser = subparsers.add_parser('bgp', help='Control BGP peering and announcements')

    return parser
# }}}

def main():# {{{
    parser = create_parser()
    opts = parser.parse_args()
# }}}

if __name__ == '__main__':
    sys.exit(main())
