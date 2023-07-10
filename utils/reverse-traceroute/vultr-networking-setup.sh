#!/bin/bash
set -eu
set -x

progdir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)
export progdir

export OPENVPN_DELAY_SEC=15
export CDIR=/root/client
export CONVERGENCE_TIME=180

declare -gA mux2id
mux2id=(
        [amsterdam]=1
        [atlanta]=2
        [bangalore]=3
        [chicago]=4
        [dallas]=5
        [delhi]=6
        [frankfurt]=7
        [johannesburg]=8
        [london]=9
        [losangelas]=10
        [madrid]=11
        [melbourne]=12
        [mexico]=13
        [miami]=14
        [mumbai]=15
        [newyork]=16
        [osaka]=17
        [paris]=18
        [saopaulo]=19
        [seattle]=20
        [seoul]=21
        [silicon]=22
        [singapore]=23
        [stockholm]=24
        [sydney]=25
        [tokyo]=26
        [toronto]=27
        [warsaw]=28
)

declare -ga prefixes
prefixes=(
    184.164.246.0/24
    # 184.164.244.0/24
    # 184.164.245.0/24
    # 184.164.247.0/24
)

declare -gA prefix2mux
prefix2mux=(
    [184.164.246.0/24]=seattle
    # [184.164.244.0/24]=seattle
    # [184.164.245.0/24]=seattle
    # [184.164.247.0/24]=seattle
)

function setup_docker_bridges {
    local idx=1
    for prefix in "${prefixes[@]}" ; do
        local mux=${prefix2mux[$prefix]}
        "$CDIR/peering" app -i $idx -b -p "$prefix" -u "$mux"
        idx=$(( idx + 1 ))
    done
}

function teardown_docker_bridges {
    local idx=1
    for _prefix in "${prefixes[@]}" ; do
        "$CDIR/peering" app -i $idx -b -d
        idx=$(( idx + 1 ))
    done
}

function establish_bgp_sessions {
    teardown_bgp_sessions
    echo "Starting OpenVPN tunnels"
    for mux in "${!mux2id[@]}" ; do
        echo "  up $mux"
        "$CDIR/peering" openvpn up "$mux"
    done
    echo "  Waiting $OPENVPN_DELAY_SEC seconds..."
    sleep "$OPENVPN_DELAY_SEC"
    "$CDIR/peering" openvpn status
    echo "Starting BGP sessions"
    "$CDIR/peering" bgp start
    echo "  Waiting $OPENVPN_DELAY_SEC seconds..."
    sleep "$OPENVPN_DELAY_SEC"
    "$CDIR/peering" bgp status
}

function teardown_bgp_sessions {
    echo "Shutting down OpenVPN tunnels and BGP sessions"
    "$CDIR/peering" bgp stop
    for mux in "${!mux2id[@]}" ; do
        "$CDIR/peering" openvpn down "$mux"
    done
    echo "  Waiting $OPENVPN_DELAY_SEC seconds..."
    sleep "$OPENVPN_DELAY_SEC"
    nopenvpn=$(pgrep openvpn | wc -l)
    if [[ $nopenvpn -gt 0 ]] ; then
        echo "Warning: Found $nopenvpn OpenVPN daemons running"
    fi
}

function announce_prefixes {
    withdraw_prefixes
    echo "Announcing prefixes"
    for prefix in "${prefixes[@]}" ; do
        local mux=${prefix2mux[$prefix]}
        echo "  announce -R -m $mux $prefix"
        "$CDIR/peering" prefix announce -R -m $mux $prefix &> /dev/null
        # "$CDIR/peering" bgp adv "$mux"
    done
    echo "  Waiting $CONVERGENCE_TIME for BGP convergence"
    sleep "$CONVERGENCE_TIME"
}

function withdraw_prefixes {
    echo "Withdrawing prefixes"
    for prefix in "${prefixes[@]}" ; do
        echo "  withdraw $prefix"
        "$CDIR/peering" prefix withdraw "$prefix" &> /dev/null
    done
}

function test_data_plane {
    local idx=1
    set +e
    for prefix in "${prefixes[@]}" ; do
        local mux=${prefix2mux[$prefix]}
        local ip=${prefix%%.0/24}.130
        echo "================================================================="
        echo "Prefix $prefix egressing through $mux on br$idx using $ip"
        # docker run --network "br$octet" --ip "$ip" -it --rm \
        #         busybox ip addr show dev eth0
        # docker run --network "br$octet" --ip "$ip" -it --rm \
        #         busybox ip route
        # docker run --network "br$octet" --ip "$ip" -it --rm busybox \
        #         ping -q -c 4 "184.164.$octet.254"
        docker run --network "pbr$idx" --ip "$ip" -it --rm --dns 1.1.1.1 \
                busybox ping -q -c 4 1.1.1.1
        docker run --network "pbr$idx" --ip "$ip" -it --rm --dns 1.1.1.1 \
                busybox ping -q -c 4 sf.net
        docker run --network "pbr$idx" --ip "$ip" --rm --dns 1.1.1.1 \
                --entrypoint=/usr/bin/ping mdeb -c4 -R sf.net
        # docker run --network "pbr$idx" --ip "$ip" -it --rm --dns 8.8.8.8 \
                # busybox traceroute 8.8.8.8
        idx=$(( idx + 1 ))
    done
    set -e
}

# The following can be run to test the control and data planes.  The
# operations should be run in the order presented.  Comment and
# uncomment as needed during test and debugging.

# establish_bgp_sessions
# setup_docker_bridges

# announce_prefixes
test_data_plane
# withdraw_prefixes

# teardown_docker_bridges
# teardown_bgp_sessions
