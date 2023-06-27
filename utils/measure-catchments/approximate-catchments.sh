#!/bin/bash
set -eu

function usage {
    cat <<HELP
usage: $0 -I <ICMPID> -d <DIR>

    ICMPID: ICMP ID used to identify pings
    DIR: Directory containing the packet dumps
HELP
    exit 0
}

function die {
    msg=$1
    status=$2
    echo $msg
    exit $status
}

outdir=/dev/invalid
icmpid=invalid

while getopts "I:d:h" OPT; do
case $OPT in
I)
    icmpid=$(( OPTARG ))
    ;;
d)
    outdir=$OPTARG
    ;;
h|*)
    usage
    ;;
esac
done
shift $(( OPTIND - 1 ))
OPTIND=1

if [[ $icmpid == invalid ]] ; then
    die "ICMP ID not set" 1
fi

if [[ ! -d $outdir ]] ; then
    die "DIR does not exist or is not a directory" 1
fi

declare -gA counters
total=0
for dump in $outdir/*.tap*.pcap ; do
    lines=$(tcpdump -n -r $dump \
            "icmp and icmp[icmptype] == icmp-echoreply and icmp[5] == $icmpid" \
            | wc -l)
    total=$(( total + lines ))
    counters[$dump]=$lines
done

for dump in ${!counters[@]} ; do
    cnt=${counters[$dump]}
    echo "$dump $cnt $(( $cnt*100 / $total ))%"
done
