#!/usr/bin/env python3

# This script is provided as a convenience, please do not misuse/abuse
# AT&T's server.

import pexpect

DESTINATIONS = [
    "138.185.228.0/24",
    "138.185.229.0/24",
    "138.185.230.0/24",
    "138.185.231.0/24",
    "184.164.224.0/24",
    "184.164.225.0/24",
    "184.164.230.0/24",
    "184.164.231.0/24",
    "147.28.2.0/24",
    "147.28.3.0/24",
    "147.28.4.0/24",
    "147.28.5.0/24",
    "2804:269c::/48",
    "2804:269c:1::/48",
    "2804:269c:2::/48",
    "2804:269c:3::/48",
]

logfile = open("query.out", "wb")

handle = pexpect.spawn("telnet route-server.ip.att.net")
handle = pexpect.spawn("telnet 12.0.1.28")
handle.logfile = logfile

handle.expect("login:")
handle.sendline("rviews")
handle.expect("Password:")
handle.sendline("rviews")

handle.expect("route-server.ip.att.net>")
for dst in DESTINATIONS:
    handle.sendline(f"show route {dst}")
    entry = handle.expect([r"---\(more\)---", "route-server.ip.att.net>"])
    if entry == 0:
        handle.send("q")
        handle.expect("route-server.ip.att.net>")

handle.sendline("exit")

handle.logfile.close()
handle.close()
