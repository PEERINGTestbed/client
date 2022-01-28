#!/bin/bash
# shellcheck disable=SC2086

declare -A upstreams4
declare -A upstreams6
upstreams4=(
    ["coloclue"]="52"
    ["bit"]="60"
    ["rgnet"]="101"
    ["rnp@ufmg"]="16"
)
upstreams6=(
    ["coloclue"]="94"
    ["bit"]="95"
    ["rgnet"]="112"
    ["rnp@ufmg"]="445"
)

pfxset1a=(138.185.228.0/24 184.164.224.0/24 147.28.2.0/24 2804:269c::/48)
pfxset1b=(138.185.229.0/24 184.164.225.0/24 147.28.3.0/24 2804:269c:1::/48)

pfxset2a=(138.185.230.0/24 184.164.230.0/24 147.28.4.0/24 2804:269c:2::/48)
pfxset2b=(138.185.231.0/24 184.164.231.0/24 147.28.5.0/24 2804:269c:3::/48)

function shutdown_openvpn {
    echo "Shutting down OpenVPN tunnels"
    if [[ ! -s var/mux2dev.txt ]] ; then
        ./peering openvpn status &> /dev/null
    fi
    while read -r mux _tapdev ; do
        ./peering openvpn down $mux
    done < var/mux2dev.txt
}

function withdraw_prefixes {
    local -n pfxa=$1
    local -n pfxb=$2
    echo "Withdrawing prefixes ${pfxa[*]} ${pfxb[*]}"
    for pfx in "${pfxa[@]}" "${pfxb[@]}" ; do
        ./peering prefix withdraw $pfx
    done
}

function bgp_restart {
    echo "Stopping BGP servers"
    ./peering bgp stop
    ./peering bgp6 stop
    sleep 3s
    echo "Starting BGP servers"
    ./peering bgp start
    ./peering bgp6 start
    sleep 3s
}

function make_community_string {
    local pfx=$1
    local upstream=$2
    if [[ $pfx =~ ":" ]] ; then
        if [[ ${upstreams6[$upstream]:-undef} != undef ]] ; then
            echo "-c 47065,${upstreams6[$upstream]}"
        fi
    else
        if [[ ${upstreams4[$upstream]:-undef} != undef ]] ; then
            echo "-c 47065,${upstreams4[$upstream]}"
        fi
    fi
}

function make_announcements {
    local mux=$1
    local -n pfxa=$2
    local -n pfxb=$3
    local upstream=$4
    local commstr
    for pfx in "${pfxa[@]}" ; do
        commstr=$(make_community_string $pfx $upstream)
        echo ./peering prefix announce -P 1 -m $mux $commstr $pfx
        ./peering prefix announce -P 1 -m $mux $commstr $pfx
    done
    for pfx in "${pfxb[@]}" ; do
        commstr=$(make_community_string $pfx $upstream)
        echo ./peering prefix announce -P 1 -o 61574 -m $mux $commstr $pfx
        ./peering prefix announce -P 1 -o 61574 -m $mux $commstr $pfx
    done
}

sed -i "s/# router id 200.200.200.300;/router id 184.164.224.1;/" \
        configs/bird6/bird6.conf

mux1=wisc01
mux2=uw01

shutdown_openvpn
./peering openvpn up $mux1
sleep 5s
./peering openvpn up $mux2
sleep 5s

sleep 3s
bgp_restart
sleep 3s

withdraw_prefixes pfxset1a pfxset1b
upstream1=none
make_announcements $mux1 pfxset1a pfxset1b $upstream1
./peering bgp adv $mux1
./peering bgp6 adv $mux1

withdraw_prefixes pfxset2a pfxset2b
upstream2=none
make_announcements $mux2 pfxset2a pfxset2b $upstream2
./peering bgp adv $mux2
./peering bgp6 adv $mux2
