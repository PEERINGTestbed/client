#!/bin/bash
set -eu

for rpf_handle in /proc/sys/net/ipv4/conf/*/rp_filter ; do
    echo 2 > $rpf_handle;
done
