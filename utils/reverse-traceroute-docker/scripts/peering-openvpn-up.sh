#!/usr/bin/env bash
# =============================================================================
# Bring up a PEERING OpenVPN mux tunnel, and install backend egress routes
# when the mux is the hardcoded data-plane egress (ufmg01).
#
# Invoked from the host via:
#   docker compose exec peering /peering-openvpn-up.sh <mux>
#
# Non-egress muxes only establish the tunnel (for BGP reachability). All
# revtrvp-forwarded traffic continues to egress via ufmg01 / table 10007.
# =============================================================================
set -eu
set -x

CLIENT_DIR=/root/client
# Hardcoded data-plane egress mux (no RPF that breaks return traffic).
EGRESS_MUX="${EGRESS_MUX:-ufmg01}"
AFRONTEND_PREFIX="172.16.50"
TAP_WAIT_SECS="${TAP_WAIT_SECS:-60}"

usage() {
  echo "usage: $0 <mux>" >&2
  exit 1
}

test $# -ge 1 || usage
MUX="$1"

cd "$CLIENT_DIR"

# Resolve tap device for this mux from the PEERING mux2dev DB (built on demand
# the same way peering-config does when the file is missing).
mux2dev_db="var/mux2dev.txt"
openvpn_cfgs="configs/openvpn"
mkdir -p var
if [[ ! -s "$mux2dev_db" ]]; then
  : > "$mux2dev_db"
  for fn in "$openvpn_cfgs"/*.conf; do
    name=$(basename "$fn" .conf)
    echo -n "$name " >> "$mux2dev_db"
    grep -Ee "^dev " "$fn" | cut -d " " -f 2 >> "$mux2dev_db"
  done
fi

TAPDEV=$(awk -v m="$MUX" '$1 == m { print $2; exit }' "$mux2dev_db")
if [[ -z "$TAPDEV" ]]; then
  echo "error: unknown mux '$MUX' (not in $mux2dev_db)" >&2
  exit 1
fi

# Match PEERING client's tap/table convention:
#   gateway = 100.(64 + devid).128.1 ; table = 10000 + devid
DEVID="${TAPDEV##tap}"
GWIP="100.$((64 + DEVID)).128.1"
TABLE="$((10000 + DEVID))"

# ----- OpenVPN --------------------------------------------------------------
# `peering openvpn up` is idempotent: already-up tunnels exit 0 via `term`.
./peering openvpn up "$MUX"

for i in $(seq 1 "$TAP_WAIT_SECS"); do
  if ip -4 addr show "$TAPDEV" 2>/dev/null | grep -q "inet "; then
    break
  fi
  if [[ "$i" -eq "$TAP_WAIT_SECS" ]]; then
    echo "error: $TAPDEV for mux $MUX did not get an IPv4 address in ${TAP_WAIT_SECS}s" >&2
    exit 1
  fi
  sleep 1
done

sysctl -w "net.ipv4.conf.${TAPDEV}.rp_filter=0" || true

# Non-egress muxes: tunnel only (BGP reachability).
if [[ "$MUX" != "$EGRESS_MUX" ]]; then
  echo "mux $MUX up on $TAPDEV (non-egress; skipping backend policy routes)"
  exit 0
fi

# ----- Egress policy routes for ALL backend ifaces --------------------------
# Backend = not lo, not afrontend (172.16.50/24), not tap*.
mapfile -t BACKEND_IFS < <(
  ip -o -4 addr show | awk -v pfx="${AFRONTEND_PREFIX}." '
    $2 == "lo" { next }
    $2 ~ /^tap/ { next }
    $4 ~ "^"pfx { next }
    { print $2 }
  ' | sort -u
)

if [[ ${#BACKEND_IFS[@]} -eq 0 ]]; then
  echo "error: no backend interfaces found while installing egress routes" >&2
  exit 1
fi

sysctl -w net.ipv4.conf.all.rp_filter=0 || true
ip route replace default via "$GWIP" dev "$TAPDEV" table "$TABLE"

for BB_IF in "${BACKEND_IFS[@]}"; do
  sysctl -w "net.ipv4.conf.${BB_IF}.rp_filter=0" || true
  # Idempotent: rule may already exist from a previous make openvpn.
  ip rule add iif "$BB_IF" table "$TABLE" 2>/dev/null || true
done

echo "egress mux $MUX up: backends [${BACKEND_IFS[*]}] -> table $TABLE via $GWIP dev $TAPDEV"
