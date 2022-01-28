#!/bin/bash
set -u

export progdir=$(cd "$(dirname "$(readlink -f "$0")")"; pwd -P)
source "$progdir/config.sh"


declare -gA announce_params
announce_params=( )


function create_docker_bridges {
    teardown_docker_bridges
    echo "Creating Docker bridges"
    for octet in "${mux2octet[@]}" ; do
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
    for octet in "${mux2octet[@]}" ; do
        if docker network inspect "br$octet" &> /dev/null ; then
            echo "  br$octet"
            docker network rm "br$octet" &> /dev/null
        fi
    done
}

function establish_bgp_sessions {
    teardown_bgp_sessions
    echo "Starting OpenVPN tunnels"
    for mux in "${!mux2octet[@]}" ; do
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

function setup_source_routing {
    teardown_source_routing
    echo "Setting up source routing"
    for mux in "${!mux2octet[@]}" ; do
        devid=${mux2id[$mux]}
        octet=${mux2octet[$mux]}
        table=$((BASE_TABLE + devid))
        ip="184.164.$octet.$((128 + devid))"
        gw="100.$((64 + devid)).128.1"
        echo "  $mux: from $ip/32 table $table via $gw"
        ip route add default via $gw table $table
        ip rule add from "$ip/32" table $table pref $table
        ip rule add iif "br$octet" table $table pref $table
    done
}

function teardown_source_routing {
    echo "Tearing down source routing"
    for mux in "${!mux2octet[@]}" ; do
        devid=${mux2id[$mux]}
        table=$((BASE_TABLE + devid))
        nrules=$(ip rule show pref $table | wc -l)
        echo "  $mux: dropping table $table and $nrules rules"
        ip route flush table $table &> /dev/null || true
        while [[ $(( nrules-- )) -gt 0 ]] ; do
            ip rule del pref $table
        done
    done
}

function withdraw_prefixes {
    echo "Withdrawing prefixes"
    for octet in "${mux2octet[@]}" ; do
        local prefix=184.164.$octet.0/24
        echo "  $prefix"
        "$CDIR/peering" prefix withdraw "$prefix" &> /dev/null
    done
}

function announce_prefixes {
    withdraw_prefixes
    echo "Announcing prefixes"
    for mux in "${!mux2octet[@]}" ; do
        local octet=${mux2octet[$mux]}
        local prefix=184.164.$octet.0/24
        local params=${announce_params[$mux]:-}
        params=($params)
        echo "  announce -R -m $mux ${params[*]} $prefix"
        "$CDIR/peering" prefix announce -R -m "$mux" "${params[@]}" "$prefix" \
                &> /dev/null
        # "$CDIR/peering" bgp adv "$mux"
    done
    echo "  Waiting $CONVERGENCE_DELAY_SEC for BGP convergence"
    sleep "$CONVERGENCE_DELAY_SEC"
}

function run_data_plane_test {
    for mux in "${!mux2octet[@]}" ; do
        devid=${mux2id[$mux]}
        octet=${mux2octet[$mux]}
        ip=184.164.$octet.$((128 + devid + 1))
        echo "================================================================="
        echo "Container for $mux on br$octet using $ip"
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
# teardown_bgp_sessions
# establish_bgp_sessions
# setup_source_routing
# announce_prefixes
run_data_plane_test
# withdraw_prefixes
# teardown_bgp_sessions
# teardown_source_routing
# teardown_docker_bridges