#!/bin/bash
set -u
set -x

export progdir=$(cd "$(dirname "$0")"; pwd -P)
source "$progdir/scripts/peering-config"
OPENVPN_DELAY_SEC=20
CONVERGENCE_DELAY_SEC=600
BASEDIR=revtr-upstream-test
PREFIX=184.164.230.0/24
DOT1=184.164.230.1/32
IP_RULE_PREF=100

function take_snapshot {
    local basedir=$1
    local name=$2
    local out=$basedir/$name
    mkdir -p "$out"
    ./peering openvpn status > "$out/openvpn-status.txt"
    ./utils/prefix-propagation/query-route-server.py \
            --log "$out/att-routes.txt" $PREFIX &> "$out/att-routes.log"
    ip rule &> "$out/host-ip-rule.txt"
    ip route show table "$table" &> "$out/host-ip-route-table-$table.txt"
    ip addr &> "$out/host-ip-addr.txt"
    docker run --network br0 --ip "$dockerip" -it --rm busybox ip addr \
            &> "$out/busybox-ip-addr.txt"
    docker run --network br0 --ip "$dockerip" -it --rm busybox ip route \
            &> "$out/busybox-ip-route.txt"
}

load_mux2dev

# Bringing down all OpenVPN tunnels and creating tables with default routes:
for mux in "${!mux2dev[@]}" ; do
    ./peering openvpn down "$mux"
    dev=${mux2dev[$mux]}
    devid=${dev##tap}
    table=$((appns_table_base + devid))
done
./peering bgp stop
sleep $OPENVPN_DELAY_SEC
./peering bgp start
./peering prefix withdraw $PREFIX
sleep $CONVERGENCE_DELAY_SEC

ip route flush table $table || true
ip rule del pref $IP_RULE_PREF || true
ip addr add $DOT1 dev lo || true
ip rule add from $DOT1 lookup 151 prio 151 || true

mkdir -p $BASEDIR
for mux in "${!mux2dev[@]}" ; do
#     if [[ $mux = phoenix01 || $mux = saopaulo01 || $mux = uw01 || $mux = grnet01 ]] ; then
#         continue
#     fi
    if [[ $mux != amsterdam01 && $mux != seattle01 ]] ; then continue ; fi

    outdir="$BASEDIR/$mux"
    mkdir -p "$outdir"
    dev=${mux2dev[$mux]}
    devid=${dev##tap}
    octet=$((130 + devid))
    dockerip=${PREFIX%%.0/24}.$octet
    dot1=${PREFIX%%.0/24}.1
    table=$((appns_table_base + devid))

    echo "mux: $mux"
    echo "outdir: $outdir"
    echo "dev: $dev"
    echo "id: $devid"
    echo "hostip: $dot1"
    echo "dockerip: $dockerip"
    echo "table: $table"

    # OpenVPN up
    ./peering openvpn up "$mux"
    sleep $OPENVPN_DELAY_SEC

    if ! ./peering openvpn status | grep "$mux" | grep up &> /dev/null ; then
        ./peering openvpn status > "$outdir/openvpn-status.txt"
        continue
    fi

    # Announcing
    # NOTE POISONING OF PWNGP (AS101) TO PREVENT BLACKHOLING OF INTERNET2
    ./peering prefix announce -R -m "$mux" -p 101 $PREFIX
    sleep $CONVERGENCE_DELAY_SEC

    # Setting up data plane
    ip route add default via 100.$((64 + devid)).128.1 table "$table"
    ip rule add iif "$DOCKER_BRIDGE" table "$table" pref $IP_RULE_PREF

    take_snapshot "$outdir" setup

    # Testing data plane
    ping -c 4 -I $dot1 8.8.8.8 > "$outdir/host-ping.txt" || true
    docker run --network br0 --ip $dockerip -it --rm busybox \
            ping -c 4 8.8.8.8 \
            > "$outdir/busybox-ping.txt" || true
    # docker run --network br0 --ip $dockerip -it --rm --name ping1 --detach \
    #         busybox ping 8.8.8.8 \
    #         > "$outdir/busybox-ping-timeout.txt" || true
    # sleep 10s
    # docker stop ping1
    docker run --name "ptest$devid" --network=br0 --ip $dockerip \
            --restart=unless-stopped --detach \
            --log-opt max-size=1g --log-opt max-file=1 \
            -p 4381:4381 revtrvp /root.crt /plvp.config -loglevel debug
    sleep 900s
    docker stop "ptest$devid"

    # Clearing up data plane
    ip route flush table $table
    ip rule del pref $IP_RULE_PREF
    ip rule > "$outdir/clear-host-ip-rule.txt"
    ip route show table $table > "$outdir/clear-host-ip-route-table-$table.txt"
    ip addr > "$outdir/clear-host-ip-addr.txt"

    # Withdrawing
    ./peering prefix withdraw $PREFIX
    sleep $CONVERGENCE_DELAY_SEC
    ./utils/prefix-propagation/query-route-server.py \
            --log "$outdir/withdraw-routes.txt" $PREFIX

    # OpenVPN down
    ./peering openvpn down "$mux"
    sleep $OPENVPN_DELAY_SEC
    ./peering openvpn status "$mux" > "$outdir/openvpn-status-down.txt"

    take_snapshot "$outdir" teardown
done
