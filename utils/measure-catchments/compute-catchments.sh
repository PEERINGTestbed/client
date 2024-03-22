#!/bin/bash
set -eu

function usage {
    cat <<HELP
usage: $0 -I <ICMPID> -d <DIR> [-o <OUTFILE>]

    ICMPID: ICMP ID used to identify pings
    DIR: Directory containing the packet dumps
    OUTFILE: Output file [catchments.txt]
HELP
    exit 0
}

function die {
    msg=$1
    status=$2
    echo "$msg"
    exit "$status"
}

mux2devdb=../../var/mux2dev.txt
outdir=/dev/invalid
outfile=catchments.txt
icmpid=invalid

while getopts "I:d:o:h" OPT; do
case $OPT in
I)
    icmpid=$(( OPTARG ))
    ;;
d)
    outdir=$OPTARG
    ;;
o)
    outfile=$OPTARG
    ;;
h|*)
    usage
    ;;
esac
done
shift $(( OPTIND - 1 ))
OPTIND=1

declare -gA dev2mux
export dev2mux
while read -r fmux fdev ; do
    dev2mux[$fdev]=$fmux
done < "$mux2devdb"

if [[ $icmpid == invalid ]] ; then
    die "ICMP ID not set" 1
fi

if [[ ! -d $outdir ]] ; then
    die "DIR does not exist or is not a directory" 1
fi

rm -f $outfile

declare -gA counters
total=0
for dump in "$outdir"/*.tap*.pcap ; do
    tap=$(echo "$dump" | grep -o "tap[0-9]*")
    mux=${dev2mux[$tap]}
    tcpdump -n -r "$dump" \
                "icmp and icmp[icmptype] == icmp-echoreply and icmp[4:2] == $icmpid" \
            | cut -d " " -f3 \
            | sed "s/$/ $tap $mux/" \
            > "$outfile.tmp"
    lines=$(wc -l "$outfile.tmp" | cut -d " " -f1)
    total=$(( total + lines ))
    label="$tap.$mux"
    counters[$label]=$lines
    echo "$label $lines"
    cat "$outfile.tmp" >> "$outfile"
done
rm -f "$outfile.tmp"

for label in "${!counters[@]}" ; do
    cnt=${counters[$label]}
    echo "$label $cnt $(( cnt*100 / total ))%"
done
