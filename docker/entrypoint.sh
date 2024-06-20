#!/bin/bash

# not needed when container is privileged:
# mkdir -p /dev/net && mknod /dev/net/tun c 10 200
sysctl -w net.ipv6.conf.all.disable_ipv6=0
exec /bin/bash
