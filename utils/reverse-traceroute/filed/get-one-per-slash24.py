#!/usr/bin/env python3

import sys
prefix2ip = dict()

for line in sys.stdin:
    line = line.strip()
    prefix = tuple(line.split(".")[0:3])
    prefix2ip[prefix] = line

for ip in prefix2ip.values():
    print(ip)
