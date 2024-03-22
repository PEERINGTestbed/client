#!/bin/bash
set -eu

sysctl -w net.ipv6.conf.all.disable_ipv6=0
