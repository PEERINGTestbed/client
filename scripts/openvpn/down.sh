#!/bin/sh
set -eu

dev=$1
dev_mtu=$2
link_mtu=$3
local_ip=$4
remote_ip=$5
init_restart=$6

echo "down $1 $2 $3 $4 $5 $6" >> var/up-down.log
echo "down" > "var/$daemon_name.updown"
