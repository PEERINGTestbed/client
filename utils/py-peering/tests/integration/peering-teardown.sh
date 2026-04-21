#!/bin/bash
set -eu

source peering-common.sh

peering bgp stop
peering openvpn down all

for prefix in "${PREFIXES[@]}" ; do
    network=$(echo "$prefix" | cut -d'/' -f1)
    IFS='.' read -r o1 o2 o3 _o4 <<<"$network"
    dot1="${o1}.${o2}.${o3}.1"
    if ! ip addr show dev lo | grep -q "$dot1/32"; then
      echo "IP $dot1/32 not added to lo"
      continue
    fi
    sudo ip addr del "$dot1/32" dev lo
    if [ $? -eq 0 ]; then
      echo "Removed $dot1/32 from loopback"
    else
      echo "Failed to remove $dot1/32"
    fi
done
