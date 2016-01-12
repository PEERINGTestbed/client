#!/bin/sh
set -eu

TUN_DEV=$1
TUN_MTU=$2
LINK_MTU=$3
IFCONFIG_LOCAL_IP=$4
IFCONFIG_REMOTE_IP=$5
INIT_RESTART=$6

echo "up $0 $1 $2 $3 $4 $5 $6" >> logs/up-down.log

echo 0 > /proc/sys/net/ipv4/conf/$TUN_DEV/rp_filter
