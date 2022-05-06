#!/bin/bash
set -u

progdir=$(cd "$(dirname "$(readlink -f "$0")")" && pwd -P)
export progdir
source "$progdir/config.sh"


declare -gA announce_params
announce_params=( )


function create_docker_bridges {
    teardown_docker_bridges
    echo "Creating Docker bridges"
    for octet in "${octets[@]}" ; do
        echo "  br$octet 184.164.$octet.128/25"
        docker network create --driver bridge \
                --opt "com.docker.network.bridge.enable_ip_masquerade=false" \
                --opt "com.docker.network.bridge.name=br$octet" \
                --subnet "184.164.$octet.128/25" \
                --ip-range "184.164.$octet.128/25" \
                --gateway "184.164.$octet.254" \
                "br$octet" &> /dev/null
    done
}

function teardown_docker_bridges {
    echo "Removing Docker bridges"
    for octet in "${octets[@]}" ; do
        if docker network inspect "br$octet" &> /dev/null ; then
            echo "  br$octet"
            docker network rm "br$octet" &> /dev/null
        fi
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

function test_withdraw_prefixes {
    echo "Withdrawing prefixes"
    for octet in "${!test_octet2mux[@]}" ; do
        local prefix=184.164.$octet.0/24
        echo "  withdraw $prefix"
        "$CDIR/peering" prefix withdraw "$prefix" &> /dev/null
    done
}

function test_teardown_source_routing {
    echo "Tearing down source routes"
    for octet in "${!test_octet2mux[@]}" ; do
        echo "  octet $octet"
        scripts/source-routing teardown "$octet"
    done
}

function test_data_plane {
    test_withdraw_prefixes
    echo "Announcing prefixes"
    for octet in "${!test_octet2mux[@]}" ; do
        local mux=${test_octet2mux[$octet]}
        local prefix=184.164.$octet.0/24
        local params=${announce_params[$mux]:-}
        params=($params)
        echo "  announce -R -m $mux ${params[*]} $prefix"
        "$CDIR/peering" prefix announce -R -m "$mux" "${params[@]}" "$prefix" \
                &> /dev/null
        # "$CDIR/peering" bgp adv "$mux"
    done
    echo "  Waiting $CONVERGENCE_TIME for BGP convergence"
    sleep "$CONVERGENCE_TIME"
    for octet in "${!test_octet2mux[@]}" ; do
        local mux=${test_octet2mux[$octet]}
        local ip=184.164.$octet.$((128 + 2))
        echo "================================================================="
        echo "Octet $octet egressing through $mux on br$octet using $ip"
        scripts/source-routing setup "$octet" "$mux"
        # docker run --network "br$octet" --ip "$ip" -it --rm \
        #         busybox ip addr show dev eth0
        # docker run --network "br$octet" --ip "$ip" -it --rm \
        #         busybox ip route
        # docker run --network "br$octet" --ip "$ip" -it --rm busybox \
        #         ping -q -c 4 "184.164.$octet.254"
        docker run --network "br$octet" --ip "$ip" -it --rm busybox \
                ping -q -c 4 8.8.8.8
        # docker run --network "br$octet" --ip "$ip" -it --rm \
        #         busybox traceroute 8.8.8.8
    done
}

# The following is the expected order in which these operations need to
# be performed to setup the networking for the revtrvp containers to
# run. Comment and uncomment as needed. As for deployment, setting up
# the network (i.e., calling the functions in this file) only needs to
# run once; after the network is setup, PEERING announcements can change
# and revtrvp containers restarted without the need reconfigure the
# network.

# create_docker_bridges
# establish_bgp_sessions

declare -ga test_octet2mux
test_octet2mux=(
    [224]=neu01
    [225]=amsterdam01
    [246]=seattle01
    [254]=utah01
)
# test_data_plane

# test_withdraw_prefixes
# test_teardown_source_routing

# teardown_bgp_sessions
# teardown_docker_bridges