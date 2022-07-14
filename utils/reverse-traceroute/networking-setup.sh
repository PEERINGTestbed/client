#!/bin/bash
set -u
set -x

progdir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)
export progdir

export OPENVPN_DELAY_SEC=10
export CDIR=/home/cunha/git/peering/client
export CONVERGENCE_TIME=180

declare -gA mux2id
mux2id=([amsterdam01]=5
        [clemson01]=16
        [gatech01]=6
        [grnet01]=9
        [isi01]=2
        [neu01]=14
        [saopaulo01]=19
        [seattle01]=1
        [ufmg01]=7
        [ufms01]=18
        [utah01]=17
        [uw01]=10
        [wisc01]=11)

declare -gA prefix2mux
prefix2mux=(
    [184.164.224.0/24]=neu01
)
    # [184.164.225.0/24]=amsterdam01
    # [184.164.246.0/24]=seattle01
    # [184.164.254.0/24]=utah01

function setup_docker_bridges {
    local idx=1
    for prefix in "${!prefix2mux[@]}" ; do
        local mux=${prefix2mux[$prefix]}
        "$CDIR/peering" app -i $idx -b -p "$prefix" -u "$mux"
        idx=$(( idx + 1 ))
    done
}

function teardown_docker_bridges {
    local idx=1
    for _prefix in "${!prefix2mux[@]}" ; do
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
    test_withdraw_prefixes
    echo "Announcing prefixes"
    for prefix in "${!prefix2mux[@]}" ; do
        local mux=${prefix2mux[$prefix]}
        echo "  announce -R -m $mux $prefix"
        "$CDIR/peering" prefix announce -R -m "$mux" "$prefix" &> /dev/null
        # "$CDIR/peering" bgp adv "$mux"
    done
    echo "  Waiting $CONVERGENCE_TIME for BGP convergence"
    sleep "$CONVERGENCE_TIME"
}

function withdraw_prefixes {
    echo "Withdrawing prefixes"
    for prefix in "${!prefix2mux[@]}" ; do
        echo "  withdraw $prefix"
        "$CDIR/peering" prefix withdraw "$prefix" &> /dev/null
    done
}

function test_data_plane {
    local idx=1
    for prefix in "${!prefix2mux[@]}" ; do
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
        docker run --network "pbr$idx" --ip "$ip" -it --rm busybox \
                ping -q -c 4 8.8.8.8
        docker run --network "pbr$idx" --ip "$ip" -it --rm busybox \
                ping -q -c 4 google.com
        # docker run --network "br$octet" --ip "$ip" -it --rm \
        #         busybox traceroute 8.8.8.8
        idx=$(( idx + 1 ))
    done
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
