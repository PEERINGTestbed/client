#!/usr/bin/python3

import argparse
import glob
import os
import os.path
import subprocess
import sys

w = sys.stdout.write

class VPNTunnel(object): # {{{
    def __init__(self, fn):
        self.name = os.path.basename(fn)
        assert self.name.endswith('.conf')
        self.name = self.name[:-5]
        fd = open(fn, 'r')
        for line in fd:
            if line.startswith('remote'):
                self.remote = line.split()[1].strip()
            elif line.startswith('dev'):
                self.device = line.split()[1].strip()
        fd.close()
# }}}

def openvpn_create_parser(parser):# {{{
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--status',
            dest='status',
            action='store_true',
            default=False,
            help='List and show status of OpenVPN tunnels')
    g.add_argument('--up',
            dest='up',
            metavar='tunnel',
            type=str,
            default=None,
            help='Bring OpenVPN tunnel up')
    g.add_argument('--down',
            dest='down',
            metavar='tunnel',
            type=str,
            default=None,
            help='Bring OpenVPN tunnel down')
# }}}

def openvpn_execute(opts): # {{{
    def openvpn_status_mux(name): # {{{
        statusfn = 'openvpn/logs/%s.status' % name2config[name].device
        try:
            fd = open(statusfn, 'r')
            return fd.readline().strip()
        except (IOError, EOFError):
            return 'down'
    # }}}
    def openvpn_status(): # {{{
        for name, config in sorted(name2config.items()):
            status = openvpn_status_mux(name)
            w('%s %s %s\n' % (name, config.device, status))
    # }}}
    def openvpn_up(): # {{{
        if opts.up not in name2config:
            w('unknown mux: %s\n' % opts.up)
            sys.exit(os.EX_USAGE)
        status = openvpn_status_mux(opts.up)
        if status.startswith('up'):
            w('tunnel %s already up\n' % opts.up)
            sys.exit(os.EX_OK)
        cmd = 'openvpn --cd %s/openvpn --config configs/%s.conf' % (
                os.getcwd(), opts.up)
        subprocess.check_call(cmd.split())
    # }}}
    def openvpn_down(): # {{{
        if opts.down not in name2config:
            w('unknown mux: %s\n' % opts.up)
            sys.exit(os.EX_USAGE)
        status = openvpn_status_mux(opts.down)
        if status.startswith('down'):
            w('tunnel %s already down\n' % opts.down)
            sys.exit(os.EX_OK)
        pidfn = 'openvpn/logs/%s.pid' % name2config[opts.down].device
        try:
            fd = open(pidfn, 'r')
            pid = int(fd.readline().strip())
        except (IOError, EOFError):
            w('pid file %s not found.\n' % pidfn)
            w('you will have to terminate this tunnel manually.\n')
            sys.exit(os.EX_SOFTWARE)
        cmd = 'kill %d' % pid
        subprocess.check_call(cmd.split())
    # }}}

    name2config = dict()
    for fn in glob.iglob('openvpn/configs/*.conf'):
        config = VPNTunnel(fn)
        name2config[config.name] = config

    if opts.status:
        openvpn_status()
    elif opts.up is not None:
        openvpn_up()
    elif opts.down is not None:
        openvpn_down()
# }}}


def bgp_create_parser(_parser):# {{{
    pass
# }}}
def bgp_execute(_opts): # {{{
    pass
# }}}

def create_parser(): # {{{
    parser = argparse.ArgumentParser(description='PEERING controller')

    subparsers = parser.add_subparsers(dest='command')

    openvpn_parser = subparsers.add_parser('openvpn', help='Control OpenVPN tunnels')
    openvpn_create_parser(openvpn_parser)

    bgp_parser = subparsers.add_parser('bgp', help='Control BGP peering and announcements')
    bgp_create_parser(bgp_parser)

    return parser
# }}}

def main():# {{{
    parser = create_parser()
    opts = parser.parse_args()

    if opts.command == 'openvpn':
        openvpn_execute(opts)
    elif opts.command == 'bgp':
        bgp_execute(opts)
# }}}

if __name__ == '__main__':
    sys.exit(main())
