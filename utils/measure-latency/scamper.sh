#!/bin/bash
set -eu

src_addr=invalid
mux=invalid
targets_file=invalid

usage() {
    echo "Usage: $0 -s <addr> -m <mux> -t <targets>"
    exit 1
}

while getopts "s:m:t:p:h" opt; do
    case "$opt" in
        s) src_addr="$OPTARG" ;;
        m) mux="$OPTARG" ;;
        t) targets_file="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))

if [[ "$src_addr" == "invalid" || "$mux" == "invalid" ]]; then
    echo "Error: -s, -m, and -t are required." >&2
    usage
fi

MUX2DEV_DB="$(dirname "$0")/../../var/mux2dev.txt"
PKTS_PER_SEC=200
PROBE_METHOD=ICMP-echo
MAX_PROBES=6
MAX_REPLIES=3

load_mux2dev () {
    declare -gA mux2dev
    export mux2dev
    while read -r fmux fdev ; do
        mux2dev[$fmux]=$fdev
    done < "$MUX2DEV_DB"
}

load_mux2dev

octet=$(echo "$src_addr" | cut -d. -f3)
muxid=${mux2dev[$mux]#tap}
GATEWAY="100.$(( 64 + muxid )).128.1"

# Start the long-lived scamper instance in the background to probe targets from
# the file.  Output to a xz-compressed file.
scamper -o "$octet-$mux-output.warts.xz" -O warts.xz \
        -p $PKTS_PER_SEC -f "$targets_file" \
        -c "ping -S $src_addr -P $PROBE_METHOD -o $MAX_REPLIES -c $MAX_PROBES" &
scamper_pid=$!
echo "Started long-lived scamper instance (PID: $scamper_pid)"

# While the long-lived instance is running (checked via kill -0), run a
# short-lived scamper instance to measure latency to the gateway every second.
while kill -0 $scamper_pid 2>/dev/null; do
    # Short-lived instance: 3 pings (-c 3), 100ms between them (-i 0.1).
    # Outputting in text format for immediate visibility.
    timestamp=$(date +%s.%N)
    scamper -o "$octet-$mux-$timestamp.warts.xz" -O warts.xz \
            -p $PKTS_PER_SEC -i "$GATEWAY" \
            -c "ping -S $src_addr -c 4 -i 0.1"
    sleep 1
done

# Ensure the background process is fully cleaned up before exiting.
wait "$scamper_pid"
echo "Long-lived scamper instance has finished."
