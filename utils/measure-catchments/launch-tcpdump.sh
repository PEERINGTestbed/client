#!/bin/bash
set -eu

progdir=$(cd "$(dirname "$0")" && pwd -P)
peeringdir="$progdir/../../"

function usage {
    cat <<HELP
usage: $0 -i <IP> [-o <DIR>] mux1 [mux2 ...]

    IP: IP used to ping
    DIR: Output directory where to store packet dumps [dumps_$(date +%s)]
    muxN: Mux OpenVPN tunnels to launch tcpdump on
HELP
    exit 0
}

function die {
    msg=$1
    status=$(( $2 ))
    echo "$msg"
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

# transform remaining parameters into an array:
muxes=("$@")
echo "Got ${#muxes[@]} muxes: ${muxes[*]}"

declare -gA mux2dev
export mux2dev
while read -r fmux fdev ; do
    mux2dev[$fmux]=$fdev
done < "$peeringdir/var/mux2dev.txt"

mkdir -p "$outdir"
rm -f "$outdir/pids.txt"

for mux in "${muxes[@]}" ; do
    iface=${mux2dev[$mux]}
    if ! ip link show dev "$iface" &> /dev/null ; then
        echo "$iface not found, skipping $mux"
        continue
    fi
    echo "Launching tcpdump on $iface for $mux"
    echo "icmp and host $ip" > "$outdir/$mux.$iface.filter"
    tcpdump -n -i "$iface" -w "$outdir/$mux.$iface.pcap" \
            "icmp and host $ip" \
            > /dev/null 2>&1 &
    echo $! >> "$outdir/pids.txt"
done

echo "Running PIDs saved in $outdir/pids.txt"
sleep 5s
