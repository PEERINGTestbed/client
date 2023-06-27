#!/bin/bash
set -eu

function usage {
    cat <<HELP
usage: $0 -i <IP> [-o <DIR>]

    IP: IP used to ping
    DIR: Output directory where to store packet dumps [dumps_$(date +%s)]
HELP
    exit 0
}

function die {
    msg=$1
    status=$2
    echo $msg
    exit $status
}

ip=invalid
outdir=dumps_$(date +%s)

while getopts "i:o:h" OPT; do
case $OPT in
i)
    ip=$OPTARG
    ;;
o)
    outdir=$OPTARG
    ;;
h|*)
    usage
    ;;
esac
done
shift $(( OPTIND - 1 ))
OPTIND=1

if [[ $ip == invalid ]] ; then
    die "IP is not set" 1
fi

declare -ga vmuxes
vmuxes=(
    amsterdam
    atlanta
    bangalore
    chicago
    dallas
    delhi
    frankfurt
    johannesburg
    london
    losangelas
    madrid
    melbourne
    mexico
    miami
    mumbai
    newyork
    osaka
    paris
    saopaulo
    seattle
    seoul
    silicon
    singapore
    stockholm
    sydney
    tokyo
    toronto
    warsaw
)

declare -gA vmux2id
vmux2id=(
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

mkdir -p $outdir
rm -f $outdir/pids.txt

for mux in ${vmuxes[@]} ; do
    idx=${vmux2id[$mux]}
    iface=tap$idx
    if ! ip link show dev $iface &> /dev/null ; then
        echo "$iface not found, skipping $mux"
        continue
    fi
    echo "Launching tcpdump on $iface for $mux"
    sudo tcpdump -n -i $iface -w $outdir/$mux.$iface.pcap icmp and host $ip \
            > /dev/null 2>&1 &
    echo $! >> $outdir/pids.txt
done

echo "Running PIDs saved in $outdir/pids.txt"
