#!/bin/bash
set -eu

output=$1
mux=$2
{
    sed -e "s/^/184.164.224.129 /" "jc-exp/targets/targets_$mux.txt"
    sed -e "s/^/184.164.225.129 /" "jc-exp/targets/targets_joined.txt"
    sed -e "s/^/184.164.246.129 /" "jc-exp/targets/targets_joined.txt"
    sed -e "s/^/184.164.254.129 /" "jc-exp/targets/targets_joined.txt"
} > "$output"
