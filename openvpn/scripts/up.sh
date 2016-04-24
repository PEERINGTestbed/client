#!/bin/sh
set -eu

dev=$1
dev_mtu=$2
link_mtu=$3
local_ip=$4
remote_ip=$5
init_restart=$6

echo "up $1 $2 $3 $4 $5 $6" >> logs/up-down.log
echo "up $local_ip" > logs/$dev.status

# echo 0 > /proc/sys/net/ipv4/conf/$dev/rp_filter
