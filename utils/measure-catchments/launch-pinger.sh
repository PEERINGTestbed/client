#!/bin/bash
set -eu

progdir=$(cd "$(dirname "$0")" && pwd -P)

ip=invalid
targets=/dev/invalid
ratelimit=200
icmpid=51

function usage {
    cat <<HELP
usage: $0 -i <IP> -t <TARGETS> [-I <ICMPID>] [-r PPS]

    IP: Source IP used to send pings
    TARGETS: File with one target IP per line
    ICMPID: ICMP ID used to identify packets [$icmpid]
    PPS: Packets per second used for probing [$ratelimit]
HELP
    exit 0
}

function die {
    msg=$1
    status=$(( $2 ))
    echo "$msg"
    exit $status
}

while getopts "i:t:I:r:h" OPT; do
case $OPT in
i)
    ip=$OPTARG
    ;;
t)
    targets=$OPTARG
    ;;
I)
    icmpid=$(( OPTARG ))
    ;;
r)
    ratelimit=$(( OPTARG ))
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

if ! ip addr | grep "$ip" &> /dev/null ; then
    die "IP $ip not configured on this host" 1
fi

if [[ ! -s $targets ]] ; then
    die "File $targets empty or does not exist" 1
fi

echo "Printing egress information:"
ip route get 8.8.8.8 from "$ip"

sudo "$progdir/pinger" --source-address "$ip" --rate-limit $ratelimit \
        --identifier $icmpid < "$targets"

sleep 5s
