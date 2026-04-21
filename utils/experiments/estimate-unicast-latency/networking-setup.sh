#!/bin/bash
set -eu

progdir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)
export progdir

declare -ga prefixes
prefixes=(
  184.164.226.0/24
  184.164.227.0/24
  184.164.247.0/24
  184.164.254.0/24
)

add_dot254_to_loopback() {
  echo "Got $# prefixes"
  for prefix in "$@"; do
    network=$(echo "$prefix" | cut -d'/' -f1)
    IFS='.' read -r o1 o2 o3 _o4 <<<"$network"
    dot254="${o1}.${o2}.${o3}.254"
    if ip addr show dev lo | grep -q "$dot254/32"; then
      echo "IP $dot254/32 already added to lo"
      continue
    fi
    sudo ip addr add "$dot254/32" dev lo
    if [ $? -eq 0 ]; then
      echo "Added $dot254/32 to loopback"
    else
      echo "Failed to add $dot254/32"
    fi
  done
}

add_dot254_to_loopback "${prefixes[@]}"
