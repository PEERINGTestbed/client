#!/bin/sh
set -eu

dev=$1
dev_mtu=$2
link_mtu=$3
local_ip=$4
remote_ip=$5
init_restart=$6

echo "cmdline $*" >> var/up-down.log
set >> var/up-down.log

# Performance tuning
ip link set "$dev" txqueuelen 20000
tc qdisc replace dev "$dev" root pfifo limit 25000

echo "up $local_ip $ifconfig_ipv6_local" > "var/$daemon_name.updown"

# echo 0 > /proc/sys/net/ipv4/conf/$dev/rp_filter
