#!/usr/bin/env python3

import ipaddress
import sys

ip = sys.argv[1]
net = sys.argv[2]

if ipaddress.ip_address(ip) in ipaddress.ip_interface(net).network:
    sys.exit(0)
else:
    sys.exit(1)
