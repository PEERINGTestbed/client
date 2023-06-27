#!/bin/bash
set -eu

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
    status=$2
    echo $msg
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

if [[ ! -s $targets ]] ; then
    die "File $targets empty or does not exist" 1
fi

echo "Printing egress information"
sudo ip addr del $ip/32 dev lo &> /dev/null || true
sudo ip addr add $ip/32 dev lo
ip route get 8.8.8.8 from $ip
echo "Please verify egress route for $ip"
echo "Press <return> to continue or <ctrl-c> to abort"
read

sudo ./pinger --source-address $ip --rate-limit $ratelimit \
        --identifier $icmpid < $targets

sudo ip addr del $ip/32 dev lo
