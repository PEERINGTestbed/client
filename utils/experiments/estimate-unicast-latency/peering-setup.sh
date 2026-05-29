#!/bin/bash
set -eu

source peering-common.sh

peering openvpn up all
peering bgp start || true

for prefix in "${PREFIXES[@]}" ; do
    network=$(echo "$prefix" | cut -d'/' -f1)
    IFS='.' read -r o1 o2 o3 _o4 <<<"$network"
    dot1="${o1}.${o2}.${o3}.1"
    if ip addr show dev lo | grep -q "$dot1/32"; then
      echo "IP $dot1/32 already added to lo"
      continue
    fi
    sudo ip addr add "$dot1/32" dev lo
    if [ $? -eq 0 ]; then
      echo "Added $dot1/32 to loopback"
    else
      echo "Failed to add $dot1/32"
    fi
done
