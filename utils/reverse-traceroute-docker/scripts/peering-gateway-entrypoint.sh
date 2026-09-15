#!/usr/bin/env bash
# =============================================================================
# PEERING gateway entrypoint
# -----------------------------------------------------------------------------
# Runs inside the `peering` Compose service.  Responsibilities:
#   1. Force the container's own control traffic (OpenVPN, DNS, git) out the
#      NAT'd `afrontend` interface (172.16.50.0/24).
#   2. Enable IPv4 forwarding and relax global reverse-path filtering so later
#      Makefile-driven mux/backend setup can install asymmetric routes.
#   3. Stay alive so `make openvpn` / `make bgp-start` / shells work.
#
# OpenVPN tunnels, backend policy routing, and BGP are NOT started here; see
# `make up` / `make openvpn` / `make bgp-start` and scripts/peering-openvpn-up.sh.
# =============================================================================
set -eu
set -x

CLIENT_DIR=/root/client
# Compose afrontend IPAM subnet; used to find the control-plane iface by addr.
AFRONTEND_PREFIX="172.16.50"

cd "$CLIENT_DIR"

# ----- 1. Identify afrontend and pin the default route ----------------------
# Interface names inside containers are not deterministic; resolve by subnet.
AF_IF=$(ip -o -4 addr show | awk -v pfx="${AFRONTEND_PREFIX}." '
  $4 ~ "^"pfx { print $2; exit }
')
if [[ -z "${AF_IF}" ]]; then
  echo "error: could not find afrontend iface on ${AFRONTEND_PREFIX}.0/24" >&2
  exit 1
fi
# Docker assigns .1 of each user bridge subnet to the host side; use it as GW.
AF_GW=$(ip -o -4 addr show dev "$AF_IF" | awk '{print $4}' | sed 's#\.[0-9]*/.*#.1#')
ip route replace default via "$AF_GW" dev "$AF_IF"

# ----- 2. Forwarding + relaxed RPF (global) ---------------------------------
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.all.rp_filter=0

# ----- 3. Stay alive --------------------------------------------------------
# Keep the service up for exec targets. Prefer existing up-down log if present;
# otherwise block forever.
mkdir -p var
touch var/up-down.log
exec tail -F var/up-down.log
